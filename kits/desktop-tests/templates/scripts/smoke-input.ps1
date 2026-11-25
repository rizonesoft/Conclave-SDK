<#
.SYNOPSIS
    Runs real-input desktop UI tests on demand or nightly on an idle, unlocked desktop (D04 T04 s1).
.DESCRIPTION
    Reads .conclave/desktop-tests.json (prefix, window_opens, window_closes, idle_minutes, history_limit,
    log_limit, test_command). Exports <PREFIX>_SMOKE_INPUT=1, <PREFIX>_SMOKE_ADMITTED, <PREFIX>_SMOKE_PERSON_EVENT,
    and a fresh per-run <PREFIX>_SMOKE_TAG so tests cannot send real input outside an admitted, actively watched run.
    Exit codes: 0 passed or skipped by admission guard; 1 failed, interrupted, or reconciliation error; 2 invalid config/args.
#>
param(
    [switch]$Scheduled,
    [switch]$Install,
    [switch]$Uninstall,
    [switch]$Status,
    [string]$ProjectRoot = '',
    [string]$StateFolder = '',
    [string]$Python = '',
    [string]$RunnerCommand = '',
    [string]$Watcher = '',
    [switch]$TestProbes,
    [switch]$NoRegister,
    [string]$NowOverride = ''
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$here = $PSScriptRoot
$repo = if ($ProjectRoot) { (Resolve-Path -LiteralPath $ProjectRoot).ProviderPath } else { Split-Path $here -Parent }
if (-not $Python) {
    $pyCmd = Get-Command python -CommandType Application -ErrorAction Ignore | Select-Object -First 1
    if (-not $pyCmd) { Write-Error 'smoke-input: python is not on PATH'; exit 2 }
    $Python = $pyCmd.Source
}

# Validate .conclave/desktop-tests.json (exit 2 on invalid settings).
$cfgJson = & $Python -B (Join-Path $here 'lib\desktop_tests.py') show --root $repo 2>&1
if ($LASTEXITCODE -ne 0) {
    ($cfgJson | Out-String).Trim() | Write-Error
    exit 2
}
$cfg = ($cfgJson | Select-Object -Last 1) | ConvertFrom-Json
$prefix = [string]$cfg.prefix
$envPrefix = [string]$cfg.env_prefix
$historyLimit = [int]$cfg.history_limit
$logLimit = [int]$cfg.log_limit
$idleMinutes = [int]$cfg.idle_minutes

if (-not $StateFolder) {
    $StateFolder = Join-Path $env:LOCALAPPDATA "$prefix\desktop-tests"
}
New-Item -ItemType Directory -Force -Path $StateFolder | Out-Null
$historyPath = Join-Path $StateFolder 'input-history.jsonl'
$installedPath = Join-Path $StateFolder 'installed.json'
$logsDir = Join-Path $StateFolder 'logs'

if (-not ('ConclaveSmokeDesk' -as [type])) {
    Add-Type @'
using System;
using System.Diagnostics;
using System.Runtime.InteropServices;

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

    public static IntPtr NewKillOnCloseJob() {
        IntPtr job = CreateJobObjectW(IntPtr.Zero, null);
        if (job == IntPtr.Zero) throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());
        var lim = new JOBOBJECT_EXTENDED_LIMIT_INFORMATION();
        lim.BasicLimitInformation.LimitFlags = 0x2000; // JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if (!SetInformationJobObject(job, 9, ref lim, (uint)Marshal.SizeOf(typeof(JOBOBJECT_EXTENDED_LIMIT_INFORMATION)))) {
            int err = Marshal.GetLastWin32Error();
            CloseHandle(job);
            throw new System.ComponentModel.Win32Exception(err);
        }
        return job;
    }
}
'@
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
    # Overnight wrap (e.g. 23:00 to 02:00).
    return ($t -ge $opens) -or ($t -lt $closes)
}

function Get-WindowCloseDateTime([DateTime]$nowLocal, [TimeSpan]$opens, [TimeSpan]$closes) {
    $todayClose = $nowLocal.Date.Add($closes)
    if ($opens -lt $closes) { return $todayClose }
    if ($nowLocal.TimeOfDay -ge $opens) { return $todayClose.AddDays(1) }
    return $todayClose
}

function Read-History {
    if (-not (Test-Path -LiteralPath $historyPath)) { return @() }
    $items = [Collections.Generic.List[object]]::new()
    foreach ($line in @(Get-Content -LiteralPath $historyPath -ErrorAction Ignore)) {
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

function Add-History($entry) {
    $hashBytes = [Security.Cryptography.SHA256]::HashData([Text.Encoding]::UTF8.GetBytes(([IO.Path]::GetFullPath($historyPath)).ToLowerInvariant()))
    $key = [Convert]::ToHexString($hashBytes).Substring(0, 16)
    $mtx = [Threading.Mutex]::new($false, "Local\$prefix-smoke-history-$key")
    try {
        try { [void]$mtx.WaitOne() } catch [Threading.AbandonedMutexException] { }
        $existing = @(Read-History)
        $all = @($existing) + @($entry)
        if ($all.Count -gt $historyLimit) {
            $all = @($all | Select-Object -Last $historyLimit)
        }
        $lines = @($all | ForEach-Object { $_ | ConvertTo-Json -Compress -Depth 6 })
        Write-AtomicText $historyPath (($lines -join "`n") + "`n")
    } finally {
        try { $mtx.ReleaseMutex() } catch { }
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

# ---- Install / Uninstall ---------------------------------------------------------------------------------------
$taskName = "$prefix-real-input-smoke"
$autoDir = Join-Path $repo '.conclave\automations'
$autoManifest = Join-Path $autoDir 'tasks.json'

if ($Install) {
    $now = Get-NowLocal
    $opens = Parse-HHMM $cfg.window_opens
    $closes = Parse-HHMM $cfg.window_closes
    $durationMin = [int]((Get-WindowCloseDateTime ($now.Date.Add($opens)) $opens $closes) - ($now.Date.Add($opens))).TotalMinutes
    if ($durationMin -le 0) { $durationMin = 180 }
    $firstNight = if ($now.TimeOfDay -ge $opens) { $now.Date.AddDays(1).ToString('yyyy-MM-dd') } else { $now.Date.ToString('yyyy-MM-dd') }
    $installRec = [ordered]@{
        installed_at = $now.ToString('O')
        first_expected_night = $firstNight
        task_name = $taskName
        mode = if (Test-Path -LiteralPath $autoManifest) { 'automations' } else { 'standalone' }
    }
    Write-AtomicText $installedPath ($installRec | ConvertTo-Json -Depth 4)

    if (Test-Path -LiteralPath $autoManifest) {
        $doc = Get-Content -Raw -LiteralPath $autoManifest | ConvertFrom-Json
        $tasks = [Collections.Generic.List[object]]::new()
        foreach ($t in @($doc.tasks)) {
            if ($t.name -ne $taskName) { $tasks.Add($t) }
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
        Write-AtomicText $autoManifest (($newDoc | ConvertTo-Json -Depth 8) + "`n")
        if (-not $NoRegister) {
            & pwsh -NoProfile -NonInteractive -File (Join-Path $autoDir 'install.ps1')
            if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        }
        "smoke-input: installed nightly task '$taskName' in .conclave/automations/tasks.json"
        exit 0
    } else {
        if (-not $NoRegister) {
            $user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
            $principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
            $action = New-ScheduledTaskAction -Execute 'pwsh.exe' `
                -Argument "-NoProfile -NonInteractive -File `"$(Join-Path $here 'smoke-input.ps1')`" -Scheduled" `
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
        "smoke-input: installed standalone nightly task '$taskName'"
        exit 0
    }
}

if ($Uninstall) {
    if (Test-Path -LiteralPath $autoManifest) {
        $doc = Get-Content -Raw -LiteralPath $autoManifest | ConvertFrom-Json
        $kept = @($doc.tasks | Where-Object { $_.name -ne $taskName })
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
        Unregister-ScheduledTask -TaskPath "\$prefix\" -TaskName $taskName -Confirm:$false -ErrorAction Ignore
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
    if (Test-Path -LiteralPath $installedPath) {
        try {
            $inst = Get-Content -Raw -LiteralPath $installedPath | ConvertFrom-Json
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
        $opens = Parse-HHMM $cfg.window_opens
        $lastExpected = if ($now.TimeOfDay -ge $opens) { $now.Date } else { $now.Date.AddDays(-1) }
        for ($d = $firstNight; $d -le $lastExpected; $d = $d.AddDays(1)) {
            $ds = $d.ToString('yyyy-MM-dd')
            if (-not $schedDates.Contains($ds)) { $missedDates.Add($ds) }
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

if ($Scheduled) {
    if (-not (Test-InWindow $now $opens $closes)) {
        Add-History ([ordered]@{ at = $now.ToString('O'); night = $nightStr; mode = $mode; outcome = 'skipped'; reason = 'outside-window' })
        "smoke-input: skipped (outside-window: $($cfg.window_opens)-$($cfg.window_closes))"
        exit 0
    }
    $desk = Get-DeskState
    if ($desk.Unknown) {
        Add-History ([ordered]@{ at = $now.ToString('O'); night = $nightStr; mode = $mode; outcome = 'skipped'; reason = 'desktop-unknown' })
        "smoke-input: skipped (desktop-unknown)"
        exit 0
    }
    if ($desk.Locked) {
        Add-History ([ordered]@{ at = $now.ToString('O'); night = $nightStr; mode = $mode; outcome = 'skipped'; reason = 'desktop-locked' })
        "smoke-input: skipped (desktop-locked)"
        exit 0
    }
    if ($desk.IdleSeconds -lt ($idleMinutes * 60.0)) {
        Add-History ([ordered]@{ at = $now.ToString('O'); night = $nightStr; mode = $mode; outcome = 'skipped'; reason = 'desktop-busy'; idle_seconds = [math]::Round($desk.IdleSeconds, 1) })
        "smoke-input: skipped (desktop-busy: idle $([math]::Round($desk.IdleSeconds, 1))s < $($idleMinutes * 60)s)"
        exit 0
    }
}

# Resolve runner command.
$runnerExe = $null
$runnerBaseArgs = @()
if ($RunnerCommand) {
    $runnerExe = $Python
    $runnerBaseArgs = @('-B', $RunnerCommand)
} elseif ($cfg.test_command) {
    $runnerExe = [string]$cfg.test_command[0]
    if ($cfg.test_command.Count -gt 1) { $runnerBaseArgs = @($cfg.test_command[1..($cfg.test_command.Count - 1)]) }
} else {
    Write-Error 'smoke-input: no -RunnerCommand or test_command in .conclave/desktop-tests.json'
    exit 2
}

# Compile InputWatch.cs on demand if -Watcher not supplied.
if (-not $Watcher) {
    $watchExe = Join-Path $StateFolder 'InputWatch.exe'
    $watchSrc = Join-Path $here 'lib\InputWatch.cs'
    if (-not (Test-Path -LiteralPath $watchExe) -or ((Get-Item -LiteralPath $watchSrc).LastWriteTimeUtc -gt (Get-Item -LiteralPath $watchExe).LastWriteTimeUtc)) {
        $csc = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
        if (-not (Test-Path -LiteralPath $csc)) { Write-Error "smoke-input: csc.exe not found at $csc"; exit 1 }
        $built = & $csc /nologo "/out:$watchExe" $watchSrc 2>&1
        if ($LASTEXITCODE -ne 0) { Write-Error "smoke-input: failed to compile InputWatch.cs: $($built | Out-String)"; exit 1 }
    }
    $Watcher = $watchExe
}

# Create fresh per-run tag, admittedEvent (signaled), and personEvent (unsignaled).
$rng = [Security.Cryptography.RandomNumberGenerator]::Create()
$tagBytes = New-Object byte[] 4
do {
    $rng.GetBytes($tagBytes)
    $tagVal = [BitConverter]::ToUInt32($tagBytes, 0)
} while ($tagVal -eq 0 -or $tagVal -eq 0x434E5232)
$rng.Dispose()
$runTagHex = $tagVal.ToString('X8')
$runId = [Guid]::NewGuid().ToString('N').Substring(0, 12)
$admittedName = "Local\$prefix-smoke-admitted-$runId"
$personName = "Local\$prefix-smoke-person-$runId"
$watchRecord = Join-Path $StateFolder "watch-$runId.txt"

$admittedEvent = [Threading.EventWaitHandle]::new($true, [Threading.EventResetMode]::ManualReset, $admittedName)
$personEvent = [Threading.EventWaitHandle]::new($false, [Threading.EventResetMode]::ManualReset, $personName)
$watchProc = $null

try {
    # Start watcher and require its 'watching' readiness line before any test runs.
    $wPsi = [Diagnostics.ProcessStartInfo]::new()
    if ($Watcher.EndsWith('.py', [StringComparison]::OrdinalIgnoreCase)) {
        $wPsi.FileName = $Python
        $wPsi.Arguments = "-B `"$Watcher`" --file `"$watchRecord`" --person-event `"$personName`" --tag $runTagHex" + $(if ($Scheduled) { ' --guard' } else { '' })
    } else {
        $wPsi.FileName = $Watcher
        $wPsi.Arguments = "--file `"$watchRecord`" --person-event `"$personName`" --tag $runTagHex" + $(if ($Scheduled) { ' --guard' } else { '' })
    }
    $wPsi.UseShellExecute = $false
    $wPsi.CreateNoWindow = $true
    $wPsi.RedirectStandardOutput = $true
    $wPsi.RedirectStandardError = $true
    $wPsi.RedirectStandardInput = $true
    $watchProc = [Diagnostics.Process]::Start($wPsi)
    $readyTask = $watchProc.StandardOutput.ReadLineAsync()
    if (-not $readyTask.Wait(10000) -or $readyTask.Result -ne 'watching') {
        $admittedEvent.Reset() | Out-Null
        Add-History ([ordered]@{ at = $now.ToString('O'); night = $nightStr; mode = $mode; outcome = 'failed'; reason = 'watcher-not-ready' })
        Write-Error 'smoke-input: input watcher did not report watching readiness'
        exit 1
    }

    # Discover test cases (require non-empty discovery).
    $discOut = & $runnerExe @runnerBaseArgs --discover 2>&1
    if ($LASTEXITCODE -ne 0) {
        Add-History ([ordered]@{ at = $now.ToString('O'); night = $nightStr; mode = $mode; outcome = 'failed'; reason = 'discovery-failed' })
        Write-Error "smoke-input: test discovery failed: $($discOut | Out-String)"
        exit 1
    }
    $discovered = [Collections.Generic.List[object]]::new()
    foreach ($line in @($discOut)) {
        $s = "$line".Trim()
        if ($s -match '^DISCOVER\s+(\S+)\s+(\S+)$') {
            $discovered.Add([pscustomobject]@{ Class = $Matches[1]; Case = $Matches[2] })
        }
    }
    if ($discovered.Count -eq 0) {
        Add-History ([ordered]@{ at = $now.ToString('O'); night = $nightStr; mode = $mode; outcome = 'failed'; reason = 'discovery-empty' })
        Write-Error 'smoke-input: discovery returned 0 real-input cases'
        exit 1
    }

    # Group by class preserving order.
    $classes = [Collections.Generic.List[string]]::new()
    $expectedByClass = @{}
    foreach ($d in $discovered) {
        if (-not $expectedByClass.ContainsKey($d.Class)) {
            $classes.Add($d.Class)
            $expectedByClass[$d.Class] = [Collections.Generic.List[string]]::new()
        }
        $expectedByClass[$d.Class].Add($d.Case)
    }

    $deadline = if ($Scheduled) { Get-WindowCloseDateTime $now $opens $closes } else { $now.AddHours(3) }
    $logLines = [Collections.Generic.List[string]]::new()
    $stopReason = $null
    $failedReasons = [Collections.Generic.List[string]]::new()

    foreach ($cls in $classes) {
        if ($personEvent.WaitOne(0)) { $stopReason = 'person-input'; break }
        if ($watchProc.HasExited) { $stopReason = 'watcher-lost'; break }
        if ($Scheduled) {
            $dState = Get-DeskState
            if ($dState.Unknown) { $stopReason = 'desktop-unknown'; break }
            if ($dState.Locked) { $stopReason = 'desktop-locked'; break }
            if ((Get-NowLocal) -ge $deadline) { $stopReason = 'deadline'; break }
        }

        $job = [ConclaveSmokeDesk]::NewKillOnCloseJob()
        $cProc = $null
        try {
            $cPsi = [Diagnostics.ProcessStartInfo]::new()
            $cPsi.FileName = $runnerExe
            $quotedBase = ($runnerBaseArgs | ForEach-Object { if ($_ -match '\s') { "`"$_`"" } else { $_ } }) -join ' '
            $cPsi.Arguments = "$quotedBase --run-class $cls".Trim()
            $cPsi.WorkingDirectory = $repo
            $cPsi.UseShellExecute = $false
            $cPsi.CreateNoWindow = $true
            $cPsi.RedirectStandardOutput = $true
            $cPsi.RedirectStandardError = $true
            $cPsi.EnvironmentVariables["${envPrefix}_SMOKE_INPUT"] = '1'
            $cPsi.EnvironmentVariables["${envPrefix}_SMOKE_ADMITTED"] = $admittedName
            $cPsi.EnvironmentVariables["${envPrefix}_SMOKE_PERSON_EVENT"] = $personName
            $cPsi.EnvironmentVariables["${envPrefix}_SMOKE_TAG"] = $runTagHex
            $cProc = [Diagnostics.Process]::Start($cPsi)
            [void][ConclaveSmokeDesk]::AssignProcessToJobObject($job, $cProc.Handle)
            $outTask = $cProc.StandardOutput.ReadToEndAsync()
            $errTask = $cProc.StandardError.ReadToEndAsync()

            while (-not $cProc.HasExited) {
                if ($personEvent.WaitOne(25)) { $stopReason = 'person-input'; break }
                if ($watchProc.HasExited) { $stopReason = 'watcher-lost'; break }
                if ($Scheduled) {
                    $dState = Get-DeskState
                    if ($dState.Unknown) { $stopReason = 'desktop-unknown'; break }
                    if ($dState.Locked) { $stopReason = 'desktop-locked'; break }
                    if ((Get-NowLocal) -ge $deadline) { $stopReason = 'deadline'; break }
                }
            }
            if ($stopReason) {
                $admittedEvent.Reset() | Out-Null
                [void][ConclaveSmokeDesk]::TerminateJobObject($job, 1)
                $cProc.WaitForExit(5000) | Out-Null
                break
            }
            $cProc.WaitForExit()
            $classStdout = $outTask.GetAwaiter().GetResult()
            $classStderr = $errTask.GetAwaiter().GetResult()
            $logLines.Add("=== class $cls (exit $($cProc.ExitCode)) ===")
            if ($classStdout) { $logLines.Add($classStdout.TrimEnd()) }
            if ($classStderr) { $logLines.Add("STDERR: $($classStderr.TrimEnd())") }

            # Case-level reconciliation for this class.
            $counts = @{}
            foreach ($line in @($classStdout -split "`r?`n")) {
                $t = $line.Trim()
                if ($t -match '^CASE\s+(PASS|FAIL|SKIP)\s+(\S+)\s+(\S+)$') {
                    $statusTok = $Matches[1]; $rCls = $Matches[2]; $rCase = $Matches[3]
                    if ($rCls -ne $cls) {
                        $failedReasons.Add("unexpected-class:$rCls/$rCase")
                        continue
                    }
                    if (-not $counts.ContainsKey($rCase)) { $counts[$rCase] = 0 }
                    $counts[$rCase]++
                    if ($statusTok -eq 'FAIL') { $failedReasons.Add("case-failed:$cls/$rCase") }
                    elseif ($statusTok -eq 'SKIP') { $failedReasons.Add("case-skipped:$cls/$rCase") }
                }
            }
            foreach ($expCase in $expectedByClass[$cls]) {
                if (-not $counts.ContainsKey($expCase)) {
                    $failedReasons.Add("case-missing:$cls/$expCase")
                } elseif ($counts[$expCase] -gt 1) {
                    $failedReasons.Add("case-duplicate:$cls/$expCase")
                }
            }
            foreach ($k in $counts.Keys) {
                if ($expectedByClass[$cls] -notcontains $k) {
                    $failedReasons.Add("case-unexpected:$cls/$k")
                }
            }
            if ($cProc.ExitCode -ne 0) {
                $failedReasons.Add("class-exit-nonzero:$cls($($cProc.ExitCode))")
            }
        } finally {
            [void][ConclaveSmokeDesk]::TerminateJobObject($job, 1)
            [void][ConclaveSmokeDesk]::CloseHandle($job)
            if ($cProc) { $cProc.Dispose() }
        }
    }

    New-Item -ItemType Directory -Force -Path $logsDir | Out-Null
    $logFile = Join-Path $logsDir "$($now.ToString('yyyyMMdd-HHmmss'))-$runId.log"
    Write-AtomicText $logFile (($logLines -join "`n") + "`n")
    Prune-Logs

    if ($stopReason) {
        Add-History ([ordered]@{
            at = $now.ToString('O'); night = $nightStr; mode = $mode; outcome = 'interrupted'
            reason = $stopReason; discovered = $discovered.Count; log = (Split-Path $logFile -Leaf)
        })
        "smoke-input: stopped ($stopReason)"
        exit 1
    }
    if ($failedReasons.Count -gt 0) {
        Add-History ([ordered]@{
            at = $now.ToString('O'); night = $nightStr; mode = $mode; outcome = 'failed'
            reason = ($failedReasons -join ','); discovered = $discovered.Count; log = (Split-Path $logFile -Leaf)
        })
        "smoke-input: failed ($($failedReasons -join ', '))"
        exit 1
    }
    Add-History ([ordered]@{
        at = $now.ToString('O'); night = $nightStr; mode = $mode; outcome = 'passed'
        reason = 'ok'; discovered = $discovered.Count; log = (Split-Path $logFile -Leaf)
    })
    "smoke-input: passed ($($discovered.Count) case(s) across $($classes.Count) class(es))"
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
        } catch { }
        $watchProc.Dispose()
    }
    $admittedEvent.Dispose()
    $personEvent.Dispose()
    if (Test-Path -LiteralPath $watchRecord) { Remove-Item -LiteralPath $watchRecord -Force -ErrorAction Ignore }
}
