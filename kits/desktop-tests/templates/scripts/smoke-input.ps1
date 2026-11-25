<#
.SYNOPSIS
    Admitted runner for opt-in real-input Windows desktop UI tests (D04 T04 s1).
.DESCRIPTION
    Reads .conclave/desktop-tests.json, enforces admission (unlocked desktop, idle threshold, nightly
    window when -Scheduled, and live watcher readiness), runs discovery and each test class inside
    Windows Job Objects assigned before the child's first instruction, streams output to bounded logs,
    reconciles discovered cases case-sensitively, and records atomic mutex-guarded history.
#>
[CmdletBinding()]
param(
    [switch]$Scheduled,
    [switch]$Status,
    [switch]$Install,
    [switch]$Uninstall,
    [switch]$NoRegister,
    [string]$ProjectRoot,
    [string]$StateFolder,
    [string]$Python,
    [string]$Watcher,
    [string]$RunnerCommand,
    [string]$NowOverride,
    [switch]$TestProbes
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$repo = if ($ProjectRoot) { [IO.Path]::GetFullPath($ProjectRoot) } else { [IO.Path]::GetFullPath((Join-Path $here '..')) }
$pyExe = if ($Python) { $Python } else { 'python' }
$cfgLoader = Join-Path $here 'lib\desktop_tests.py'

# Load and validate .conclave/desktop-tests.json (exit 2 on invalid or unset config).
$cfgJson = & $pyExe -B $cfgLoader show --root $repo 2>&1
if ($LASTEXITCODE -ne 0) {
    [Console]::Error.WriteLine(($cfgJson | Out-String).Trim())
    exit 2
}
$cfg = ($cfgJson | Out-String) | ConvertFrom-Json
$prefix = [string]$cfg.prefix
$envPrefix = [string]$cfg.env_prefix
$historyLimit = [int]$cfg.history_limit
$logLimit = [int]$cfg.log_limit

# Refuse test-harness overrides when executing the real configured test_command.
if ((-not $Status) -and (-not $Install) -and (-not $Uninstall) -and (-not $RunnerCommand)) {
    if ($NowOverride -or $TestProbes -or $Watcher) {
        [Console]::Error.WriteLine('smoke-input: -NowOverride, -TestProbes, and -Watcher require -RunnerCommand in run mode')
        exit 2
    }
}

if (-not $StateFolder) {
    $localApp = if ($env:LOCALAPPDATA) { $env:LOCALAPPDATA } else { [IO.Path]::GetTempPath() }
    $StateFolder = Join-Path $localApp "$prefix-desktop-tests"
}
New-Item -ItemType Directory -Force -Path $StateFolder | Out-Null
$historyPath = Join-Path $StateFolder 'input-history.jsonl'
$installedPath = Join-Path $StateFolder 'installed.json'
$nightsPath = Join-Path $StateFolder 'scheduled-nights.json'
$logsDir = Join-Path $StateFolder 'logs'

if (-not ('ConclaveSmokeDesk' -as [type])) {
    Add-Type @'
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using Microsoft.Win32.SafeHandles;

public static class ConclaveSmokeDesk {
    [StructLayout(LayoutKind.Sequential)] struct LASTINPUTINFO { public uint cbSize; public uint dwTime; }
    [DllImport("user32.dll")] static extern bool GetLastInputInfo(ref LASTINPUTINFO info);
    [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();

    public static bool IsLocked() { return GetForegroundWindow() == IntPtr.Zero; }
    public static double IdleSecondsOrNegative() {
        var info = new LASTINPUTINFO { cbSize = (uint)Marshal.SizeOf(typeof(LASTINPUTINFO)) };
        if (!GetLastInputInfo(ref info)) return -1.0;
        return unchecked((uint)Environment.TickCount - info.dwTime) / 1000.0;
    }

    [StructLayout(LayoutKind.Sequential)]
    struct JOBOBJECT_BASIC_LIMIT_INFORMATION {
        public long PerProcessUserTimeLimit, PerJobUserTimeLimit;
        public uint LimitFlags;
        public UIntPtr MinimumWorkingSetSize, MaximumWorkingSetSize;
        public uint ActiveProcessLimit;
        public UIntPtr Affinity;
        public uint PriorityClass, SchedulingClass;
    }
    [StructLayout(LayoutKind.Sequential)]
    struct IO_COUNTERS { public ulong a, b, c, d, e, f; }
    [StructLayout(LayoutKind.Sequential)]
    struct JOBOBJECT_EXTENDED_LIMIT_INFORMATION {
        public JOBOBJECT_BASIC_LIMIT_INFORMATION BasicLimitInformation;
        public IO_COUNTERS IoInfo;
        public UIntPtr ProcessMemoryLimit, JobMemoryLimit, PeakProcessMemoryUsed, PeakJobMemoryUsed;
    }
    [StructLayout(LayoutKind.Sequential)]
    struct SECURITY_ATTRIBUTES {
        public int nLength;
        public IntPtr lpSecurityDescriptor;
        public int bInheritHandle;
    }
    [StructLayout(LayoutKind.Sequential)]
    struct STARTUPINFO {
        public int cb;
        public IntPtr lpReserved, lpDesktop, lpTitle;
        public int dwX, dwY, dwXSize, dwYSize, dwXCountChars, dwYCountChars, dwFillAttribute, dwFlags;
        public short wShowWindow, cbReserved2;
        public IntPtr lpReserved2, hStdInput, hStdOutput, hStdError;
    }
    [StructLayout(LayoutKind.Sequential)]
    struct PROCESS_INFORMATION {
        public IntPtr hProcess, hThread;
        public uint dwProcessId, dwThreadId;
    }

    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    private static extern IntPtr CreateJobObjectW(IntPtr attr, string name);
    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool SetInformationJobObject(IntPtr job, int infoClass, ref JOBOBJECT_EXTENDED_LIMIT_INFORMATION info, uint len);
    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern bool AssignProcessToJobObject(IntPtr job, IntPtr proc);
    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern bool TerminateJobObject(IntPtr job, uint code);
    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern bool CloseHandle(IntPtr handle);
    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool CreatePipe(out IntPtr readPipe, out IntPtr writePipe, ref SECURITY_ATTRIBUTES sa, uint size);
    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool SetHandleInformation(IntPtr hObject, uint dwMask, uint dwFlags);
    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    private static extern bool CreateProcessW(
        string appName, StringBuilder cmdLine, IntPtr procAttr, IntPtr threadAttr, bool inheritHandles,
        uint creationFlags, IntPtr envBlock, string curDir, ref STARTUPINFO si, out PROCESS_INFORMATION pi);
    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern uint ResumeThread(IntPtr hThread);
    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool TerminateProcess(IntPtr hProcess, uint exitCode);
    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern uint WaitForSingleObject(IntPtr hHandle, uint dwMilliseconds);
    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool GetExitCodeProcess(IntPtr hProcess, out uint lpExitCode);

    public sealed class JobChild : IDisposable {
        public IntPtr ProcessHandle;
        public int Pid;
        public StreamReader StdOut;
        public StreamReader StdErr;
        private bool _disposed;

        public bool HasExited {
            get { return WaitForSingleObject(ProcessHandle, 0) == 0; }
        }
        public int ExitCode {
            get {
                uint code;
                if (!GetExitCodeProcess(ProcessHandle, out code)) return -1;
                return unchecked((int)code);
            }
        }
        public bool WaitForExit(int ms) {
            return WaitForSingleObject(ProcessHandle, (uint)ms) == 0;
        }
        public void Dispose() {
            if (_disposed) return;
            _disposed = true;
            if (StdOut != null) StdOut.Dispose();
            if (StdErr != null) StdErr.Dispose();
            if (ProcessHandle != IntPtr.Zero) { CloseHandle(ProcessHandle); ProcessHandle = IntPtr.Zero; }
        }
    }

    public static IntPtr NewKillOnCloseJob() {
        IntPtr job = CreateJobObjectW(IntPtr.Zero, null);
        if (job == IntPtr.Zero) throw new Win32Exception(Marshal.GetLastWin32Error());
        var lim = new JOBOBJECT_EXTENDED_LIMIT_INFORMATION();
        lim.BasicLimitInformation.LimitFlags = 0x2000; // JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if (!SetInformationJobObject(job, 9, ref lim, (uint)Marshal.SizeOf(typeof(JOBOBJECT_EXTENDED_LIMIT_INFORMATION)))) {
            int err = Marshal.GetLastWin32Error();
            CloseHandle(job);
            throw new Win32Exception(err);
        }
        return job;
    }

    private static IntPtr BuildEnvBlock(IDictionary<string, string> env) {
        var sorted = new SortedDictionary<string, string>(env, StringComparer.OrdinalIgnoreCase);
        var sb = new StringBuilder();
        foreach (var kv in sorted) {
            sb.Append(kv.Key).Append('=').Append(kv.Value ?? "").Append('\0');
        }
        sb.Append('\0');
        return Marshal.StringToHGlobalUni(sb.ToString());
    }

    // Starts a child suspended, runs optional outer-job enrollment and assigns inner job BEFORE its first instruction runs.
    public static JobChild StartInJob(IntPtr job, string cmdLine, string workDir, IDictionary<string, string> envOverrides) {
        return StartInJob(job, (Action<IntPtr>)null, cmdLine, workDir, envOverrides);
    }

    public static JobChild StartInJob(IntPtr job, Action<IntPtr> enrollOuter, string cmdLine, string workDir, IDictionary<string, string> envOverrides) {
        var sa = new SECURITY_ATTRIBUTES { nLength = Marshal.SizeOf(typeof(SECURITY_ATTRIBUTES)), bInheritHandle = 1 };
        IntPtr outR = IntPtr.Zero, outW = IntPtr.Zero, errR = IntPtr.Zero, errW = IntPtr.Zero;
        if (!CreatePipe(out outR, out outW, ref sa, 0)) throw new Win32Exception(Marshal.GetLastWin32Error());
        if (!CreatePipe(out errR, out errW, ref sa, 0)) {
            CloseHandle(outR); CloseHandle(outW);
            throw new Win32Exception(Marshal.GetLastWin32Error());
        }
        SetHandleInformation(outR, 1, 0);
        SetHandleInformation(errR, 1, 0);

        var envMap = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        foreach (System.Collections.DictionaryEntry de in Environment.GetEnvironmentVariables()) {
            envMap[(string)de.Key] = (string)de.Value;
        }
        if (envOverrides != null) {
            foreach (var kv in envOverrides) envMap[kv.Key] = kv.Value;
        }
        IntPtr envPtr = BuildEnvBlock(envMap);
        var si = new STARTUPINFO();
        si.cb = Marshal.SizeOf(typeof(STARTUPINFO));
        si.dwFlags = 0x100; // STARTF_USESTDHANDLES
        si.hStdOutput = outW;
        si.hStdError = errW;
        PROCESS_INFORMATION pi;
        uint flags = 0x4 | 0x400 | 0x08000000; // CREATE_SUSPENDED | CREATE_UNICODE_ENVIRONMENT | CREATE_NO_WINDOW
        bool ok;
        int err = 0;
        try {
            ok = CreateProcessW(null, new StringBuilder(cmdLine), IntPtr.Zero, IntPtr.Zero, true, flags, envPtr, workDir, ref si, out pi);
            if (!ok) err = Marshal.GetLastWin32Error();
        } finally {
            Marshal.FreeHGlobal(envPtr);
            CloseHandle(outW);
            CloseHandle(errW);
        }
        if (!ok) {
            CloseHandle(outR); CloseHandle(errR);
            throw new Win32Exception(err);
        }
        // Enroll in outer desktop jobs FIRST, then inner per-class/discovery job SECOND (Windows nested-job order).
        if (enrollOuter != null) {
            try {
                enrollOuter(pi.hProcess);
            } catch {
                TerminateProcess(pi.hProcess, 1);
                CloseHandle(pi.hThread);
                CloseHandle(pi.hProcess);
                CloseHandle(outR); CloseHandle(errR);
                throw;
            }
        }
        if (!AssignProcessToJobObject(job, pi.hProcess)) {
            int jerr = Marshal.GetLastWin32Error();
            TerminateProcess(pi.hProcess, 1);
            CloseHandle(pi.hThread);
            CloseHandle(pi.hProcess);
            CloseHandle(outR); CloseHandle(errR);
            throw new Win32Exception(jerr, "AssignProcessToJobObject failed before child resumed");
        }
        if (ResumeThread(pi.hThread) == unchecked((uint)-1)) {
            int rerr = Marshal.GetLastWin32Error();
            TerminateProcess(pi.hProcess, 1);
            CloseHandle(pi.hThread);
            CloseHandle(pi.hProcess);
            CloseHandle(outR); CloseHandle(errR);
            throw new Win32Exception(rerr);
        }
        CloseHandle(pi.hThread);
        var utf8 = new UTF8Encoding(false);
        return new JobChild {
            ProcessHandle = pi.hProcess,
            Pid = (int)pi.dwProcessId,
            StdOut = new StreamReader(new FileStream(new SafeFileHandle(outR, true), FileAccess.Read), utf8),
            StdErr = new StreamReader(new FileStream(new SafeFileHandle(errR, true), FileAccess.Read), utf8),
        };
    }
}
'@
}

function Quote-WinArg([string]$a) {
    if ($null -eq $a -or $a.Length -eq 0) { return '""' }
    if ($a -notmatch '[\s"]') { return $a }
    $sb = [Text.StringBuilder]::new('"')
    $bs = 0
    for ($i = 0; $i -lt $a.Length; $i++) {
        $ch = $a[$i]
        if ($ch -eq '\') {
            $bs++
        } elseif ($ch -eq '"') {
            [void]$sb.Append('\', $bs * 2 + 1).Append('"')
            $bs = 0
        } else {
            if ($bs -gt 0) { [void]$sb.Append('\', $bs); $bs = 0 }
            [void]$sb.Append($ch)
        }
    }
    if ($bs -gt 0) { [void]$sb.Append('\', $bs * 2) }
    [void]$sb.Append('"')
    return $sb.ToString()
}

function Build-WinCmdLine([string]$exe, [string[]]$argList) {
    $parts = [Collections.Generic.List[string]]::new()
    $parts.Add((Quote-WinArg $exe))
    foreach ($a in @($argList)) { $parts.Add((Quote-WinArg $a)) }
    return ($parts -join ' ')
}

function Get-NowLocal {
    if ($NowOverride) {
        return [DateTime]::Parse($NowOverride, [Globalization.CultureInfo]::InvariantCulture)
    }
    if ($TestProbes) {
        $p = Join-Path $StateFolder 'probe-now'
        if (Test-Path -LiteralPath $p) {
            return [DateTime]::Parse((Get-Content -LiteralPath $p -Raw).Trim(), [Globalization.CultureInfo]::InvariantCulture)
        }
    }
    return Get-Date
}

function Parse-HHMM([string]$hhmm) {
    $parts = $hhmm.Split(':')
    return [TimeSpan]::new([int]$parts[0], [int]$parts[1], 0)
}

function Test-InWindow([DateTime]$nowLocal, [TimeSpan]$opens, [TimeSpan]$closes) {
    $t = $nowLocal.TimeOfDay
    if ($opens -lt $closes) {
        return ($t -ge $opens) -and ($t -lt $closes)
    }
    return ($t -ge $opens) -or ($t -lt $closes)
}

function Get-WindowCloseDateTime([DateTime]$nowLocal, [TimeSpan]$opens, [TimeSpan]$closes) {
    $todayClose = $nowLocal.Date.Add($closes)
    if ($opens -lt $closes) { return $todayClose }
    if ($nowLocal.TimeOfDay -ge $opens) { return $todayClose.AddDays(1) }
    return $todayClose
}

function Read-History {
    if (-not [IO.File]::Exists($historyPath)) { return @() }
    # Fail closed on transient read errors so Add-History never overwrites readable history with an empty list.
    $rawLines = [IO.File]::ReadAllLines($historyPath, [Text.UTF8Encoding]::new($false))
    $items = [Collections.Generic.List[object]]::new()
    foreach ($line in $rawLines) {
        if (-not $line.Trim()) { continue }
        try {
            $rec = $line | ConvertFrom-Json
            if ($rec.PSObject.Properties['at']) { $items.Add($rec) }
        } catch {
            continue
        }
    }
    return @($items)
}

function Write-AtomicText([string]$dest, [string]$content) {
    $dir = Split-Path $dest -Parent
    if ($dir) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
    $tmp = "$dest.$PID.$([Guid]::NewGuid().ToString('N').Substring(0,8)).tmp"
    try {
        [IO.File]::WriteAllText($tmp, $content, [Text.UTF8Encoding]::new($false))
        if ([IO.File]::Exists($dest)) {
            [IO.File]::Replace($tmp, $dest, [NullString]::Value, $true)
        } else {
            [IO.File]::Move($tmp, $dest)
        }
    } finally {
        if (Test-Path -LiteralPath $tmp) { Remove-Item -LiteralPath $tmp -Force -ErrorAction Ignore }
    }
}

function Open-StateMutex([string]$key) {
    try {
        return [Threading.Mutex]::new($false, "Global\$prefix-smoke-history-$key")
    } catch [UnauthorizedAccessException] {
        return [Threading.Mutex]::new($false, "Local\$prefix-smoke-history-$key")
    }
}

function Add-History($entry) {
    $hashBytes = [Security.Cryptography.SHA256]::HashData([Text.Encoding]::UTF8.GetBytes(([IO.Path]::GetFullPath($historyPath)).ToLowerInvariant()))
    $key = [Convert]::ToHexString($hashBytes).Substring(0, 16)
    $mtx = Open-StateMutex $key
    try {
        try { [void]$mtx.WaitOne() } catch [Threading.AbandonedMutexException] { }
        $existing = @(Read-History)
        $all = @($existing) + @($entry)
        if ($all.Count -gt $historyLimit) {
            $all = @($all | Select-Object -Last $historyLimit)
        }
        $lines = @($all | ForEach-Object { $_ | ConvertTo-Json -Compress -Depth 6 })
        Write-AtomicText $historyPath (($lines -join "`n") + "`n")
        # Record completed scheduled nights as lossless merged inclusive [start, end] date ranges
        # so history_limit eviction never creates fake missed nights and earlier genuine misses are never hidden.
        if ($entry['mode'] -eq 'scheduled' -and $entry['night']) {
            $ranges = [Collections.Generic.List[object]]::new()
            $legacyFloor = $null
            if ([IO.File]::Exists($nightsPath)) {
                $doc = [IO.File]::ReadAllText($nightsPath, [Text.UTF8Encoding]::new($false)) | ConvertFrom-Json
                if ($doc -is [string]) {
                    if ($doc) { $ranges.Add(@($doc, $doc)) }
                } elseif ($doc -is [System.Array]) {
                    foreach ($d in @($doc)) { if ($d) { $ranges.Add(@([string]$d, [string]$d)) } }
                } elseif ($doc) {
                    if ($doc.PSObject.Properties['floor_date'] -and $doc.floor_date) {
                        $legacyFloor = [string]$doc.floor_date
                    }
                    if ($doc.PSObject.Properties['ranges']) {
                        foreach ($r in @($doc.ranges)) {
                            if ($r -and $r.Count -eq 2) { $ranges.Add(@([string]$r[0], [string]$r[1])) }
                        }
                    }
                    if ($doc.PSObject.Properties['dates']) {
                        foreach ($d in @($doc.dates)) { if ($d) { $ranges.Add(@([string]$d, [string]$d)) } }
                    }
                }
            }
            $nStr = [string]$entry['night']
            $ranges.Add(@($nStr, $nStr))
            $sorted = @($ranges | Sort-Object { $_[0] }, { $_[1] })
            $merged = [Collections.Generic.List[object]]::new()
            foreach ($rng in $sorted) {
                if ($merged.Count -eq 0) {
                    $merged.Add(@([string]$rng[0], [string]$rng[1]))
                } else {
                    $last = $merged[$merged.Count - 1]
                    $lastEnd = [DateTime]::ParseExact($last[1], 'yyyy-MM-dd', [Globalization.CultureInfo]::InvariantCulture)
                    $curStart = [DateTime]::ParseExact($rng[0], 'yyyy-MM-dd', [Globalization.CultureInfo]::InvariantCulture)
                    $curEnd = [DateTime]::ParseExact($rng[1], 'yyyy-MM-dd', [Globalization.CultureInfo]::InvariantCulture)
                    if ($curStart -le $lastEnd.AddDays(1)) {
                        if ($curEnd -gt $lastEnd) { $last[1] = $curEnd.ToString('yyyy-MM-dd') }
                    } else {
                        $merged.Add(@([string]$rng[0], [string]$rng[1]))
                    }
                }
            }
            $nPayload = [ordered]@{ ranges = @($merged) }
            if ($legacyFloor) { $nPayload['floor_date'] = $legacyFloor }
            Write-AtomicText $nightsPath (ConvertTo-Json -InputObject $nPayload -Depth 4 -Compress)
        }
    } finally {
        try { $mtx.ReleaseMutex() } catch [ApplicationException] { }
        $mtx.Dispose()
    }
}

function Prune-Logs {
    if (-not (Test-Path -LiteralPath $logsDir)) { return }
    $files = @(Get-ChildItem -LiteralPath $logsDir -Filter '*.log' -File | Sort-Object LastWriteTimeUtc -Descending)
    if ($files.Count -gt $logLimit) {
        foreach ($old in ($files | Select-Object -Skip $logLimit)) {
            Remove-Item -LiteralPath $old.FullName -Force -ErrorAction Ignore
        }
    }
}

function Get-DeskState {
    if ($TestProbes) {
        $unknownFile = Join-Path $StateFolder 'probe-unknown'
        if (Test-Path -LiteralPath $unknownFile) { return [pscustomobject]@{ Unknown = $true; Locked = $false; IdleSeconds = 0.0 } }
        $lockedFile = Join-Path $StateFolder 'probe-locked'
        $locked = (Test-Path -LiteralPath $lockedFile) -and ((Get-Content -LiteralPath $lockedFile -Raw).Trim() -eq '1')
        $idleFile = Join-Path $StateFolder 'probe-idle'
        $idle = if (Test-Path -LiteralPath $idleFile) { [double](Get-Content -LiteralPath $idleFile -Raw).Trim() } else { 0.0 }
        return [pscustomobject]@{ Unknown = $false; Locked = $locked; IdleSeconds = $idle }
    }
    $idleSec = [ConclaveSmokeDesk]::IdleSecondsOrNegative()
    if ($idleSec -lt 0) {
        return [pscustomobject]@{ Unknown = $true; Locked = $false; IdleSeconds = 0.0 }
    }
    return [pscustomobject]@{ Unknown = $false; Locked = [ConclaveSmokeDesk]::IsLocked(); IdleSeconds = $idleSec }
}

function Test-OwnedAutomationTask($taskObj) {
    if (-not $taskObj -or -not $taskObj.PSObject.Properties['command']) { return $false }
    $cmd = @($taskObj.command | ForEach-Object { [string]$_ })
    if ($cmd.Count -ne 6) { return $false }
    return ($cmd[0] -ceq 'pwsh' -or $cmd[0] -ceq 'pwsh.exe') -and
           ($cmd[1] -ceq '-NoProfile') -and
           ($cmd[2] -ceq '-NonInteractive') -and
           ($cmd[3] -ceq '-File') -and
           ($cmd[4].Replace('\', '/') -ceq 'scripts/smoke-input.ps1') -and
           ($cmd[5] -ceq '-Scheduled')
}

function Test-OwnedScheduledTask($schedTask, [string]$expectedScript) {
    if (-not $schedTask -or -not $schedTask.Actions -or $schedTask.Actions.Count -ne 1) { return $false }
    $act = $schedTask.Actions[0]
    $expectedArgs = "-NoProfile -NonInteractive -File `"$expectedScript`" -Scheduled"
    return ([string]$act.Execute -ieq 'pwsh.exe') -and
           ([string]$act.Arguments -ceq $expectedArgs) -and
           ([string]$act.WorkingDirectory).TrimEnd('\') -ieq $repo.TrimEnd('\')
}

function Get-ScheduledTaskOrFailClosed([string]$tPath, [string]$tName, [string]$context) {
    $schedErr = $null
    $task = Get-ScheduledTask -TaskPath $tPath -TaskName $tName -ErrorVariable schedErr -ErrorAction SilentlyContinue
    foreach ($e in @($schedErr)) {
        if ($e -and ([string]$e.CategoryInfo.Category -ne 'ObjectNotFound')) {
            [Console]::Error.WriteLine("smoke-input: failed to query Task Scheduler ($($e.Exception.Message)); $context")
            exit 2
        }
    }
    return $task
}

# ---- Install / Uninstall ---------------------------------------------------------------------------------------
$taskName = "$prefix-real-input-smoke"
$autoDir = Join-Path $repo '.conclave\automations'
$autoManifest = Join-Path $autoDir 'tasks.json'
$autoRunner = Join-Path $autoDir 'run.py'

if ($Install) {
    $now = Get-NowLocal
    $opens = Parse-HHMM $cfg.window_opens
    $closes = Parse-HHMM $cfg.window_closes
    $durationMin = [int]((Get-WindowCloseDateTime ($now.Date.Add($opens)) $opens $closes) - ($now.Date.Add($opens))).TotalMinutes
    if ($durationMin -le 0) { $durationMin = 180 }

    # Preserve existing first_expected_night on reinstall so genuine missed nights are never erased.
    $firstNight = if ($now.TimeOfDay -ge $opens) { $now.Date.AddDays(1).ToString('yyyy-MM-dd') } else { $now.Date.ToString('yyyy-MM-dd') }
    if ([IO.File]::Exists($installedPath)) {
        try {
            $prevInst = [IO.File]::ReadAllText($installedPath, [Text.UTF8Encoding]::new($false)) | ConvertFrom-Json
            if ($prevInst.PSObject.Properties['first_expected_night'] -and $prevInst.first_expected_night) {
                $firstNight = [string]$prevInst.first_expected_night
            }
        } catch { }
    }

    $installRec = [ordered]@{
        installed_at = $now.ToString('O')
        first_expected_night = $firstNight
        task_name = $taskName
        mode = if (Test-Path -LiteralPath $autoManifest) { 'automations' } else { 'standalone' }
    }

    if (Test-Path -LiteralPath $autoManifest) {
        $doc = [IO.File]::ReadAllText($autoManifest, [Text.UTF8Encoding]::new($false)) | ConvertFrom-Json
        if (-not $doc.PSObject.Properties['folder'] -or [string]::IsNullOrWhiteSpace([string]$doc.folder)) {
            [Console]::Error.WriteLine("smoke-input: .conclave/automations/tasks.json has no folder set; configure folder before installing")
            exit 2
        }
        $tasks = [Collections.Generic.List[object]]::new()
        foreach ($t in @($doc.tasks)) {
            if ($t.name -eq $taskName) {
                if (-not (Test-OwnedAutomationTask $t)) {
                    [Console]::Error.WriteLine("smoke-input: refusing to overwrite unrelated automation task '$taskName'")
                    exit 2
                }
                continue
            }
            $tasks.Add($t)
        }
        $tasks.Add([ordered]@{
            name = $taskName
            description = "Nightly real-input desktop UI tests for $prefix"
            command = @('pwsh', '-NoProfile', '-NonInteractive', '-File', 'scripts/smoke-input.ps1', '-Scheduled')
            trigger = [ordered]@{
                daily = $true
                at = [string]$cfg.window_opens
                random_delay_minutes = 0
            }
            timeout_minutes = $durationMin
            start_when_available = $false
            wake_to_run = $false
            exact_timeout = $true
        })
        $newDoc = [ordered]@{
            schema_version = $doc.schema_version
            folder = $doc.folder
            tasks = @($tasks)
        }
        $candidateText = ($newDoc | ConvertTo-Json -Depth 8) + "`n"
        # Validate candidate manifest BEFORE replacing tasks.json or installed.json.
        if (Test-Path -LiteralPath $autoRunner) {
            $tmpCheck = Join-Path $autoDir "tasks.$PID.check.json"
            try {
                [IO.File]::WriteAllText($tmpCheck, $candidateText, [Text.UTF8Encoding]::new($false))
                $valOut = & $pyExe -B -c "import importlib.util, sys; s=importlib.util.spec_from_file_location('r', sys.argv[1]); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); m.load_manifest(sys.argv[2], launchers=False)" $autoRunner $tmpCheck 2>&1
                if ($LASTEXITCODE -ne 0) {
                    [Console]::Error.WriteLine("smoke-input: candidate automations manifest failed validation: $($valOut | Out-String)")
                    exit 2
                }
            } finally {
                if (Test-Path -LiteralPath $tmpCheck) { Remove-Item -LiteralPath $tmpCheck -Force -ErrorAction Ignore }
            }
        }
        $prevManifestText = [IO.File]::ReadAllText($autoManifest, [Text.UTF8Encoding]::new($false))
        Write-AtomicText $autoManifest $candidateText
        if (-not $NoRegister) {
            & pwsh -NoProfile -NonInteractive -File (Join-Path $autoDir 'install.ps1')
            if ($LASTEXITCODE -ne 0) {
                Write-AtomicText $autoManifest $prevManifestText
                exit $LASTEXITCODE
            }
        }
        Write-AtomicText $installedPath ($installRec | ConvertTo-Json -Depth 4)
        "smoke-input: installed nightly task '$taskName' in .conclave/automations/tasks.json"
        exit 0
    } else {
        if (-not $NoRegister) {
            $scriptFull = Join-Path $here 'smoke-input.ps1'
            $existingTask = Get-ScheduledTaskOrFailClosed "\$prefix\" $taskName 'install aborted'
            if ($existingTask -and (-not (Test-OwnedScheduledTask $existingTask $scriptFull))) {
                [Console]::Error.WriteLine("smoke-input: refusing to overwrite unrelated scheduled task '\$prefix\$taskName'")
                exit 2
            }
            $user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
            $principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
            $action = New-ScheduledTaskAction -Execute 'pwsh.exe' `
                -Argument "-NoProfile -NonInteractive -File `"$scriptFull`" -Scheduled" `
                -WorkingDirectory $repo
            $trigger = New-ScheduledTaskTrigger -Daily -At $cfg.window_opens
            $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew `
                -ExecutionTimeLimit (New-TimeSpan -Minutes $durationMin) `
                -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
            $settings.StartWhenAvailable = $false
            $settings.WakeToRun = $false
            Register-ScheduledTask -TaskPath "\$prefix\" -TaskName $taskName `
                -Description "Nightly real-input desktop UI tests for $prefix" `
                -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null
        }
        Write-AtomicText $installedPath ($installRec | ConvertTo-Json -Depth 4)
        "smoke-input: installed standalone nightly task '$taskName'"
        exit 0
    }
}

if ($Uninstall) {
    if (Test-Path -LiteralPath $autoManifest) {
        $doc = [IO.File]::ReadAllText($autoManifest, [Text.UTF8Encoding]::new($false)) | ConvertFrom-Json
        $kept = [Collections.Generic.List[object]]::new()
        $removedTask = $null
        foreach ($t in @($doc.tasks)) {
            if ($t.name -eq $taskName) {
                if (-not (Test-OwnedAutomationTask $t)) {
                    [Console]::Error.WriteLine("smoke-input: refusing to remove unrelated automation task '$taskName'")
                    exit 2
                }
                $removedTask = $t
                continue
            }
            $kept.Add($t)
        }
        if ($removedTask) {
            if (-not $doc.PSObject.Properties['folder'] -or [string]::IsNullOrWhiteSpace([string]$doc.folder)) {
                [Console]::Error.WriteLine('smoke-input: .conclave/automations/tasks.json has no folder set; manifest retained')
                exit 2
            }
            if (-not $NoRegister) {
                # Verify ownership of any live task at ($doc.folder, $taskName) BEFORE mutating tasks.json.
                $existingLive = Get-ScheduledTaskOrFailClosed ([string]$doc.folder) $taskName 'manifest retained'
                if ($existingLive) {
                    $ownerTag = "[conclave-automations:$autoRunner]"
                    $act = if ($existingLive.Actions -and $existingLive.Actions.Count -eq 1) { $existingLive.Actions[0] } else { $null }
                    $expectedArgs = "`"$autoRunner`" $taskName"
                    $argsAndDirOk = $act -and ([string]$act.Arguments -ceq $expectedArgs) -and (([string]$act.WorkingDirectory).TrimEnd('\') -ieq $repo.TrimEnd('\'))
                    $isTaggedOwned = $argsAndDirOk -and ([IO.Path]::GetFileName([string]$act.Execute) -ieq 'pythonw.exe') -and ([string]$existingLive.Description).EndsWith($ownerTag, [StringComparison]::OrdinalIgnoreCase)
                    $pwObj = Get-Command pythonw.exe -ErrorAction Ignore
                    $pwCmd = if ($pwObj) { $pwObj.Source } else { $null }
                    $isLegacyOwned = $argsAndDirOk -and $pwCmd -and ([string]$act.Execute -ieq $pwCmd) -and ([string]$existingLive.Description -ceq [string]$removedTask.description)
                    if ($isLegacyOwned) {
                        Unregister-ScheduledTask -TaskPath ([string]$doc.folder) -TaskName $taskName -Confirm:$false -ErrorAction Stop
                    } elseif (-not $isTaggedOwned) {
                        [Console]::Error.WriteLine("smoke-input: refusing to remove scheduled task '$($doc.folder)$taskName' whose ownership cannot be verified; manifest retained")
                        exit 2
                    }
                }
            }
        }
        $newDoc = [ordered]@{
            schema_version = $doc.schema_version
            folder = $doc.folder
            tasks = @($kept)
        }
        Write-AtomicText $autoManifest (($newDoc | ConvertTo-Json -Depth 8) + "`n")
        if (-not $NoRegister) {
            & pwsh -NoProfile -NonInteractive -File (Join-Path $autoDir 'install.ps1')
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        }
    } elseif (-not $NoRegister) {
        $scriptFull = Join-Path $here 'smoke-input.ps1'
        $existingTask = Get-ScheduledTaskOrFailClosed "\$prefix\" $taskName 'installed state retained'
        if ($existingTask) {
            if (-not (Test-OwnedScheduledTask $existingTask $scriptFull)) {
                [Console]::Error.WriteLine("smoke-input: refusing to remove unrelated scheduled task '\$prefix\$taskName'")
                exit 2
            }
            Unregister-ScheduledTask -TaskPath "\$prefix\" -TaskName $taskName -Confirm:$false -ErrorAction Stop
        }
    }
    if (Test-Path -LiteralPath $installedPath) { Remove-Item -LiteralPath $installedPath -Force }
    "smoke-input: removed nightly task '$taskName'"
    exit 0
}

# ---- Status ----------------------------------------------------------------------------------------------------
if ($Status) {
    $now = Get-NowLocal
    $hist = @(Read-History)
    $sched = @($hist | Where-Object { $_.mode -eq 'scheduled' })
    $ondem = @($hist | Where-Object { $_.mode -eq 'on-demand' })
    $firstNight = $null
    if ([IO.File]::Exists($installedPath)) {
        try {
            $inst = [IO.File]::ReadAllText($installedPath, [Text.UTF8Encoding]::new($false)) | ConvertFrom-Json
            if ($inst.PSObject.Properties['first_expected_night'] -and $inst.first_expected_night) {
                $firstNight = [DateTime]::ParseExact([string]$inst.first_expected_night, 'yyyy-MM-dd', [Globalization.CultureInfo]::InvariantCulture)
            }
        } catch { }
    }
    if (-not $firstNight -and $sched.Count -gt 0) {
        $firstNight = ([DateTime]::Parse([string]$sched[0].at, [Globalization.CultureInfo]::InvariantCulture)).Date
    }
    $missedDates = [Collections.Generic.List[string]]::new()
    if ($firstNight) {
        $schedDates = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
        foreach ($r in $sched) {
            $d = if ($r.PSObject.Properties['night'] -and $r.night) { [string]$r.night } else { ([DateTime]::Parse([string]$r.at, [Globalization.CultureInfo]::InvariantCulture)).ToString('yyyy-MM-dd') }
            [void]$schedDates.Add($d)
        }
        $schedRanges = [Collections.Generic.List[object]]::new()
        if ([IO.File]::Exists($nightsPath)) {
            $nDoc = [IO.File]::ReadAllText($nightsPath, [Text.UTF8Encoding]::new($false)) | ConvertFrom-Json
            if ($nDoc -is [string]) {
                if ($nDoc) { [void]$schedDates.Add($nDoc) }
            } elseif ($nDoc -is [System.Array]) {
                foreach ($nd in @($nDoc)) { if ($nd) { [void]$schedDates.Add([string]$nd) } }
            } elseif ($nDoc) {
                if ($nDoc.PSObject.Properties['floor_date'] -and $nDoc.floor_date) {
                    $floorDt = [DateTime]::ParseExact([string]$nDoc.floor_date, 'yyyy-MM-dd', [Globalization.CultureInfo]::InvariantCulture)
                    if ($floorDt -gt $firstNight) { $firstNight = $floorDt }
                }
                if ($nDoc.PSObject.Properties['ranges']) {
                    foreach ($r in @($nDoc.ranges)) {
                        if ($r -and $r.Count -eq 2) {
                            $schedRanges.Add(@(
                                [DateTime]::ParseExact([string]$r[0], 'yyyy-MM-dd', [Globalization.CultureInfo]::InvariantCulture),
                                [DateTime]::ParseExact([string]$r[1], 'yyyy-MM-dd', [Globalization.CultureInfo]::InvariantCulture)
                            ))
                        }
                    }
                }
                if ($nDoc.PSObject.Properties['dates']) {
                    foreach ($nd in @($nDoc.dates)) { if ($nd) { [void]$schedDates.Add([string]$nd) } }
                }
            }
        }
        $opens = Parse-HHMM $cfg.window_opens
        $lastExpected = if ($now.TimeOfDay -ge $opens) { $now.Date } else { $now.Date.AddDays(-1) }
        for ($d = $firstNight; $d -le $lastExpected; $d = $d.AddDays(1)) {
            $ds = $d.ToString('yyyy-MM-dd')
            $covered = $schedDates.Contains($ds)
            if (-not $covered) {
                foreach ($rng in $schedRanges) {
                    if ($d -ge $rng[0] -and $d -le $rng[1]) { $covered = $true; break }
                }
            }
            if (-not $covered) { $missedDates.Add($ds) }
        }
    }
    $skipped = @($sched | Where-Object { $_.outcome -eq 'skipped' })
    $summary = [ordered]@{
        prefix = $prefix
        total_records = $hist.Count
        last_scheduled = if ($sched.Count -gt 0) { $sched[-1] } else { $null }
        last_on_demand = if ($ondem.Count -gt 0) { $ondem[-1] } else { $null }
        skipped_nights = $skipped.Count
        skipped_reasons = @($skipped | ForEach-Object { $_.reason })
        missed_nights = $missedDates.Count
        missed_dates = @($missedDates)
    }
    $summary | ConvertTo-Json -Depth 6
    exit 0
}

# ---- Run (Scheduled or On-Demand) ------------------------------------------------------------------------------
$now = Get-NowLocal
$opens = Parse-HHMM $cfg.window_opens
$closes = Parse-HHMM $cfg.window_closes
$mode = if ($Scheduled) { 'scheduled' } else { 'on-demand' }
$nightStr = $now.ToString('yyyy-MM-dd')
$idleMin = [int]$cfg.idle_minutes

function Check-Admission {
    $cur = Get-NowLocal
    if (-not (Test-InWindow $cur $opens $closes)) {
        return 'outside-window'
    }
    $desk = Get-DeskState
    if ($desk.Unknown) { return 'desktop-unknown' }
    if ($desk.Locked) { return 'desktop-locked' }
    if ($desk.IdleSeconds -lt ($idleMin * 60)) {
        return "desktop-busy(idle=$([int]$desk.IdleSeconds)s<$(($idleMin * 60))s)"
    }
    return $null
}

$skipReason = Check-Admission
if ($skipReason) {
    Add-History ([ordered]@{ at = $now.ToString('O'); night = $nightStr; mode = $mode; outcome = 'skipped'; reason = $skipReason })
    if ($Scheduled) {
        "smoke-input: skipped ($skipReason)"
        exit 0
    } else {
        [Console]::Error.WriteLine("smoke-input: refused on-demand run ($skipReason)")
        exit 1
    }
}

# Acquire the machine-wide desktop lock before starting the watcher or any test runner.
if (-not ('Conclave.DesktopTests.DesktopLock' -as [type])) {
    $lockSrc = Join-Path $here 'lib\DesktopLock.cs'
    Add-Type -TypeDefinition ([IO.File]::ReadAllText($lockSrc, [Text.UTF8Encoding]::new($false))) -Language CSharp
}
$desktopLock = $null
try {
    $desktopLock = [Conclave.DesktopTests.DesktopLock]::Acquire($prefix, "smoke-input:$mode")
} catch [Conclave.DesktopTests.DesktopLockBusyException] {
    $ex = $_.Exception
    $holderInfo = [ordered]@{
        pid = $ex.HolderPid
        start_utc = $ex.HolderStartUtc
        start_ticks = $ex.HolderStartTicks
        label = $ex.HolderLabel
        detail = $ex.Message
    }
    Add-History ([ordered]@{ at = $now.ToString('O'); night = $nightStr; mode = $mode; outcome = 'skipped'; reason = 'desktop-locked-by-other'; holder = $holderInfo })
    if ($Scheduled) {
        "smoke-input: skipped (desktop-locked-by-other: $($ex.Message))"
        exit 0
    } else {
        [Console]::Error.WriteLine("smoke-input: refused on-demand run (desktop-locked-by-other: $($ex.Message))")
        exit 1
    }
} catch [ArgumentException] {
    [Console]::Error.WriteLine("smoke-input: invalid desktop lock setting: $($_.Exception.Message)")
    exit 2
}

try {
$enrollDesktopJob = if (-not $desktopLock.Inherited) { [Delegate]::CreateDelegate([Action[IntPtr]], $desktopLock, 'AssignProcessToJob') } else { $null }

# Recheck admission immediately after acquiring the desktop lock (in case the desktop became active or window closed while waiting).
$afterLockSkip = Check-Admission
if ($afterLockSkip) {
    Add-History ([ordered]@{ at = $now.ToString('O'); night = $nightStr; mode = $mode; outcome = 'skipped'; reason = $afterLockSkip })
    if ($Scheduled) {
        "smoke-input: skipped ($afterLockSkip)"
        exit 0
    } else {
        [Console]::Error.WriteLine("smoke-input: refused on-demand run ($afterLockSkip)")
        exit 1
    }
}

# Resolve watcher executable (compile InputWatch.cs on demand if -Watcher not passed).
$watchExe = $Watcher
if (-not $watchExe) {
    $watchBin = Join-Path $StateFolder 'bin\InputWatch.exe'
    $watchSrc = Join-Path $here 'lib\InputWatch.cs'
    if (-not (Test-Path -LiteralPath $watchBin) -or ((Get-Item $watchSrc).LastWriteTimeUtc -gt (Get-Item $watchBin).LastWriteTimeUtc)) {
        New-Item -ItemType Directory -Force -Path (Split-Path $watchBin -Parent) | Out-Null
        $csc = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
        if (-not (Test-Path -LiteralPath $csc)) {
            [Console]::Error.WriteLine("smoke-input: csc.exe not found at $csc")
            exit 1
        }
        $comp = & $csc /nologo /out:$watchBin $watchSrc 2>&1
        if ($LASTEXITCODE -ne 0) {
            [Console]::Error.WriteLine("smoke-input: failed to compile InputWatch.cs: $($comp | Out-String)")
            exit 1
        }
    }
    $watchExe = $watchBin
}

# Fresh per-run random dwExtraInfo tag (nonzero 31-bit hex) and kernel events.
$rngBytes = [byte[]]::new(4)
[Security.Cryptography.RandomNumberGenerator]::Fill($rngBytes)
$runTag = ([BitConverter]::ToUInt32($rngBytes, 0) -band 0x7FFFFFFF)
if ($runTag -eq 0) { $runTag = 0x13572468 }
$runTagHex = $runTag.ToString('X8')
$runId = [Guid]::NewGuid().ToString('N').Substring(0, 12)
$admittedName = "Local\$prefix-smoke-admitted-$runId"
$personName = "Local\$prefix-smoke-person-$runId"
$aliveName = "Local\$prefix-smoke-alive-$runId"
$watchRecord = Join-Path $StateFolder "watch-$runId.txt"

$admittedEvent = [Threading.EventWaitHandle]::new($false, [Threading.EventResetMode]::ManualReset, $admittedName)
$personEvent = [Threading.EventWaitHandle]::new($false, [Threading.EventResetMode]::ManualReset, $personName)
$watchJob = [ConclaveSmokeDesk]::NewKillOnCloseJob()
$watchProc = $null

function Check-RuntimeStop([DateTime]$dl) {
    if ($personEvent.WaitOne(0)) { return 'person-input' }
    if ($watchProc.HasExited) { return 'watcher-lost' }
    $dState = Get-DeskState
    if ($dState.Unknown) { return 'desktop-unknown' }
    if ($dState.Locked) { return 'desktop-locked' }
    if ((Get-NowLocal) -ge $dl) { return 'deadline' }
    return $null
}

try {
    # Start watcher inside its own kill-on-close Job Object with guard=1 (always block on person input).
    $psi = [Diagnostics.ProcessStartInfo]::new()
    if ($watchExe -like '*.py') {
        $psi.FileName = $pyExe
        $psi.Arguments = Build-WinCmdLine $watchExe @($watchRecord, $runTagHex, $personName, '1', $aliveName)
    } else {
        $psi.FileName = $watchExe
        $psi.Arguments = ($watchRecord, $runTagHex, $personName, '1', $aliveName | ForEach-Object { Quote-WinArg $_ }) -join ' '
    }
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $psi.RedirectStandardInput = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $watchProc = [Diagnostics.Process]::Start($psi)
    if (-not [ConclaveSmokeDesk]::AssignProcessToJobObject($watchJob, $watchProc.Handle)) {
        throw "smoke-input: failed to assign watcher to Job Object"
    }

    # Wait for explicit "watching" readiness line before admitting any test action.
    $readyTask = $watchProc.StandardOutput.ReadLineAsync()
    if (-not $readyTask.Wait(10000) -or $readyTask.Result -ne 'watching') {
        Add-History ([ordered]@{ at = $now.ToString('O'); night = $nightStr; mode = $mode; outcome = 'failed'; reason = 'watcher-failed' })
        [Console]::Error.WriteLine('smoke-input: watcher did not emit watching readiness line')
        exit 1
    }

    # Recheck full admission (including window and idle threshold) AFTER hooks are live to close the startup race.
    $postSkip = Check-Admission
    if ($postSkip) {
        Add-History ([ordered]@{ at = $now.ToString('O'); night = $nightStr; mode = $mode; outcome = 'skipped'; reason = $postSkip })
        if ($Scheduled) {
            "smoke-input: skipped ($postSkip)"
            exit 0
        } else {
            [Console]::Error.WriteLine("smoke-input: refused on-demand run ($postSkip)")
            exit 1
        }
    }

    $admittedEvent.Set() | Out-Null
    $deadline = Get-WindowCloseDateTime $now $opens $closes

    # Resolve runner command (unified command contract for discovery and class execution).
    $runnerExe = $null
    $runnerBaseArgs = @()
    if ($RunnerCommand) {
        if ($RunnerCommand -like '*.py') {
            $runnerExe = $pyExe
            $runnerBaseArgs = @('-B', $RunnerCommand)
        } else {
            $runnerExe = $RunnerCommand
        }
    } elseif ($cfg.test_command) {
        $arr = @($cfg.test_command)
        $runnerExe = [string]$arr[0]
        if ($arr.Count -gt 1) { $runnerBaseArgs = @($arr[1..($arr.Count - 1)] | ForEach-Object { [string]$_ }) }
    } else {
        Add-History ([ordered]@{ at = $now.ToString('O'); night = $nightStr; mode = $mode; outcome = 'failed'; reason = 'no-test-command' })
        [Console]::Error.WriteLine('smoke-input: no test_command configured in .conclave/desktop-tests.json and no -RunnerCommand given')
        exit 2
    }

    $childEnv = [Collections.Generic.Dictionary[string, string]]::new([StringComparer]::OrdinalIgnoreCase)
    $childEnv["${envPrefix}_SMOKE_INPUT"] = '1'
    $childEnv["${envPrefix}_SMOKE_ADMITTED"] = $admittedName
    $childEnv["${envPrefix}_SMOKE_PERSON_EVENT"] = $personName
    $childEnv["${envPrefix}_SMOKE_WATCHER_ALIVE"] = $aliveName
    $childEnv["${envPrefix}_SMOKE_TAG"] = $runTagHex
    $childEnv["${envPrefix}_DESKTOP_HELD"] = $desktopLock.HeldToken

    New-Item -ItemType Directory -Force -Path $logsDir | Out-Null
    $logFile = Join-Path $logsDir "$($now.ToString('yyyyMMdd-HHmmss'))-$runId.log"
    $logTmp = "$logFile.$PID.tmp"
    $logWriter = [IO.StreamWriter]::new($logTmp, $false, [Text.UTF8Encoding]::new($false))
    $stopReason = $null
    $failedReasons = [Collections.Generic.List[string]]::new()
    $discoveredCount = 0

    try {
        # Discover test cases inside a nested per-discovery Kill-On-Close Job Object under the outer desktop job.
        $discLines = [Collections.Generic.List[string]]::new()
        $discJob = [ConclaveSmokeDesk]::NewKillOnCloseJob()
        $discChild = $null
        $discExit = 0
        try {
            $discCmd = Build-WinCmdLine $runnerExe (@($runnerBaseArgs) + @('--discover'))
            $discChild = [ConclaveSmokeDesk]::StartInJob($discJob, $enrollDesktopJob, $discCmd, $repo, $childEnv)
            $outLineTask = $discChild.StdOut.ReadLineAsync()
            $errDrainTask = $discChild.StdErr.ReadToEndAsync()
            while ($true) {
                $stopReason = Check-RuntimeStop $deadline
                if ($stopReason) {
                    $admittedEvent.Reset() | Out-Null
                    [void][ConclaveSmokeDesk]::TerminateJobObject($discJob, 1)
                    [void]$discChild.WaitForExit(3000)
                    break
                }
                if ($outLineTask.Wait(25)) {
                    $ln = $outLineTask.Result
                    if ($null -eq $ln) { break }
                    $discLines.Add($ln)
                    $outLineTask = $discChild.StdOut.ReadLineAsync()
                } elseif ($discChild.HasExited) {
                    [void][ConclaveSmokeDesk]::TerminateJobObject($discJob, 1)
                    if ($outLineTask.Wait(1000) -and $null -ne $outLineTask.Result) {
                        $discLines.Add($outLineTask.Result)
                        while ($null -ne ($ln = $discChild.StdOut.ReadLine())) { $discLines.Add($ln) }
                    }
                    break
                }
            }
            if (-not $stopReason) {
                $discExit = $discChild.ExitCode
                [void][ConclaveSmokeDesk]::TerminateJobObject($discJob, 1)
                if ($errDrainTask.Wait(1000) -and $errDrainTask.Result) {
                    $logWriter.WriteLine("DISCOVER STDERR: $($errDrainTask.Result.TrimEnd())")
                }
            }
        } finally {
            [void][ConclaveSmokeDesk]::TerminateJobObject($discJob, 1)
            [void][ConclaveSmokeDesk]::CloseHandle($discJob)
            if ($discChild) { $discChild.Dispose() }
        }

        if ($stopReason) {
            $logWriter.Flush(); $logWriter.Dispose(); $logWriter = $null
            [IO.File]::Move($logTmp, $logFile)
            Prune-Logs
            Add-History ([ordered]@{ at = $now.ToString('O'); night = $nightStr; mode = $mode; outcome = 'interrupted'; reason = $stopReason; discovered = 0; log = (Split-Path $logFile -Leaf) })
            "smoke-input: stopped ($stopReason)"
            exit 1
        }
        if ($discExit -ne 0) {
            $logWriter.Flush(); $logWriter.Dispose(); $logWriter = $null
            [IO.File]::Move($logTmp, $logFile)
            Prune-Logs
            Add-History ([ordered]@{ at = $now.ToString('O'); night = $nightStr; mode = $mode; outcome = 'failed'; reason = 'discovery-failed'; discovered = 0; log = (Split-Path $logFile -Leaf) })
            [Console]::Error.WriteLine("smoke-input: test discovery failed (exit $discExit)")
            exit 1
        }

        # Case-sensitive, duplicate-free discovery grouping.
        $classes = [Collections.Generic.List[string]]::new()
        $expectedByClass = [Collections.Generic.Dictionary[string, Collections.Generic.List[string]]]::new([StringComparer]::Ordinal)
        $seenDisc = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
        foreach ($line in $discLines) {
            $s = $line.Trim()
            if ($s -match '^DISCOVER\s+(\S+)\s+(\S+)$') {
                $clsName = $Matches[1]; $caseName = $Matches[2]
                $pairKey = "$clsName`0$caseName"
                if (-not $seenDisc.Add($pairKey)) {
                    $logWriter.Flush(); $logWriter.Dispose(); $logWriter = $null
                    [IO.File]::Move($logTmp, $logFile)
                    Prune-Logs
                    Add-History ([ordered]@{ at = $now.ToString('O'); night = $nightStr; mode = $mode; outcome = 'failed'; reason = "discovery-duplicate:$clsName/$caseName"; discovered = $discoveredCount; log = (Split-Path $logFile -Leaf) })
                    [Console]::Error.WriteLine("smoke-input: duplicate discovered case $clsName/$caseName")
                    exit 1
                }
                if (-not $expectedByClass.ContainsKey($clsName)) {
                    $classes.Add($clsName)
                    $expectedByClass[$clsName] = [Collections.Generic.List[string]]::new()
                }
                $expectedByClass[$clsName].Add($caseName)
                $discoveredCount++
            }
        }
        if ($discoveredCount -eq 0) {
            $logWriter.Flush(); $logWriter.Dispose(); $logWriter = $null
            [IO.File]::Move($logTmp, $logFile)
            Prune-Logs
            Add-History ([ordered]@{ at = $now.ToString('O'); night = $nightStr; mode = $mode; outcome = 'failed'; reason = 'discovery-empty'; discovered = 0; log = (Split-Path $logFile -Leaf) })
            [Console]::Error.WriteLine('smoke-input: discovery returned 0 real-input cases')
            exit 1
        }

        foreach ($cls in $classes) {
            $stopReason = Check-RuntimeStop $deadline
            if ($stopReason) { break }

            $job = [ConclaveSmokeDesk]::NewKillOnCloseJob()
            $cChild = $null
            $counts = [Collections.Generic.Dictionary[string, int]]::new([StringComparer]::Ordinal)
            $expectedSet = [Collections.Generic.HashSet[string]]::new($expectedByClass[$cls], [StringComparer]::Ordinal)
            try {
                $classCmd = Build-WinCmdLine $runnerExe (@($runnerBaseArgs) + @('--run-class', $cls))
                $cChild = [ConclaveSmokeDesk]::StartInJob($job, $enrollDesktopJob, $classCmd, $repo, $childEnv)
                $logWriter.WriteLine("=== class $cls ===")
                $outTask = $cChild.StdOut.ReadLineAsync()
                $errTask = $cChild.StdErr.ReadLineAsync()
                $outEof = $false
                $errEof = $false

                while (-not ($outEof -and $errEof -and $cChild.HasExited)) {
                    $stopReason = Check-RuntimeStop $deadline
                    if ($stopReason) {
                        $admittedEvent.Reset() | Out-Null
                        [void][ConclaveSmokeDesk]::TerminateJobObject($job, 1)
                        [void]$cChild.WaitForExit(3000)
                        break
                    }
                    $progressed = $false
                    if (-not $outEof -and $outTask.IsCompleted) {
                        $ln = $outTask.Result
                        if ($null -eq $ln) {
                            $outEof = $true
                        } else {
                            $logWriter.WriteLine($ln)
                            $t = $ln.Trim()
                            if ($t -match '^CASE\s+(PASS|FAIL|SKIP)\s+(\S+)\s+(\S+)$') {
                                $statusTok = $Matches[1]; $rCls = $Matches[2]; $rCase = $Matches[3]
                                if (-not [StringComparer]::Ordinal.Equals($rCls, $cls)) {
                                    $failedReasons.Add("unexpected-class:$rCls/$rCase")
                                } else {
                                    $prev = 0
                                    [void]$counts.TryGetValue($rCase, [ref]$prev)
                                    $counts[$rCase] = $prev + 1
                                    if ($statusTok -eq 'FAIL') { $failedReasons.Add("case-failed:$cls/$rCase") }
                                    elseif ($statusTok -eq 'SKIP') { $failedReasons.Add("case-skipped:$cls/$rCase") }
                                }
                            }
                            $outTask = $cChild.StdOut.ReadLineAsync()
                        }
                        $progressed = $true
                    }
                    if (-not $errEof -and $errTask.IsCompleted) {
                        $eln = $errTask.Result
                        if ($null -eq $eln) {
                            $errEof = $true
                        } else {
                            $logWriter.WriteLine("STDERR: $eln")
                            $errTask = $cChild.StdErr.ReadLineAsync()
                        }
                        $progressed = $true
                    }
                    if ($cChild.HasExited -and (-not $outEof -or -not $errEof)) {
                        # Kill any lingering descendant holding inherited pipe handles before draining remaining buffered lines.
                        [void][ConclaveSmokeDesk]::TerminateJobObject($job, 1)
                        if (-not $outEof -and $outTask.Wait(200)) { continue }
                        if (-not $errEof -and $errTask.Wait(200)) { continue }
                        $outEof = $true; $errEof = $true
                        break
                    }
                    if (-not $progressed) {
                        [void]$personEvent.WaitOne(25)
                    }
                }
                if ($stopReason) { break }
                $exitCode = $cChild.ExitCode
                $logWriter.WriteLine("=== class $cls exit=$exitCode ===")

                foreach ($expCase in $expectedByClass[$cls]) {
                    $cnt = 0
                    if (-not $counts.TryGetValue($expCase, [ref]$cnt)) {
                        $failedReasons.Add("case-missing:$cls/$expCase")
                    } elseif ($cnt -gt 1) {
                        $failedReasons.Add("case-duplicate:$cls/$expCase")
                    }
                }
                foreach ($k in $counts.Keys) {
                    if (-not $expectedSet.Contains($k)) {
                        $failedReasons.Add("case-unexpected:$cls/$k")
                    }
                }
                if ($exitCode -ne 0) {
                    $failedReasons.Add("class-exit-nonzero:$cls($exitCode)")
                }
            } finally {
                [void][ConclaveSmokeDesk]::TerminateJobObject($job, 1)
                [void][ConclaveSmokeDesk]::CloseHandle($job)
                if ($cChild) { $cChild.Dispose() }
            }
        }

        # Final post-loop safety check so a person arriving right as the last class exits never records passed.
        if (-not $stopReason) {
            $stopReason = Check-RuntimeStop $deadline
        }
    } finally {
        if ($logWriter) {
            $logWriter.Flush()
            $logWriter.Dispose()
            $logWriter = $null
        }
    }

    if ([IO.File]::Exists($logTmp)) {
        if ([IO.File]::Exists($logFile)) { [IO.File]::Replace($logTmp, $logFile, [NullString]::Value, $true) }
        else { [IO.File]::Move($logTmp, $logFile) }
    }
    Prune-Logs

    if ($stopReason) {
        Add-History ([ordered]@{
            at = $now.ToString('O'); night = $nightStr; mode = $mode; outcome = 'interrupted'
            reason = $stopReason; discovered = $discoveredCount; log = (Split-Path $logFile -Leaf)
        })
        "smoke-input: stopped ($stopReason)"
        exit 1
    }
    if ($failedReasons.Count -gt 0) {
        Add-History ([ordered]@{
            at = $now.ToString('O'); night = $nightStr; mode = $mode; outcome = 'failed'
            reason = ($failedReasons -join ','); discovered = $discoveredCount; log = (Split-Path $logFile -Leaf)
        })
        "smoke-input: failed ($($failedReasons -join ', '))"
        exit 1
    }
    Add-History ([ordered]@{
        at = $now.ToString('O'); night = $nightStr; mode = $mode; outcome = 'passed'
        reason = 'ok'; discovered = $discoveredCount; log = (Split-Path $logFile -Leaf)
    })
    "smoke-input: passed ($discoveredCount case(s) across $($classes.Count) class(es))"
    exit 0
} finally {
    $admittedEvent.Reset() | Out-Null
    if ($watchProc) {
        try {
            if (-not $watchProc.HasExited) {
                $watchProc.StandardInput.WriteLine('release')
                $watchProc.StandardInput.WriteLine('quit')
                $watchProc.StandardInput.Flush()
                if (-not $watchProc.WaitForExit(2000)) { $watchProc.Kill() }
            }
        } catch [InvalidOperationException] { } catch [IO.IOException] { }
        $watchProc.Dispose()
    }
    [void][ConclaveSmokeDesk]::TerminateJobObject($watchJob, 1)
    [void][ConclaveSmokeDesk]::CloseHandle($watchJob)
    $admittedEvent.Dispose()
    $personEvent.Dispose()
    if (Test-Path -LiteralPath $watchRecord) { Remove-Item -LiteralPath $watchRecord -Force -ErrorAction Ignore }
}
} finally {
    if ($desktopLock) { $desktopLock.Dispose() }
}
