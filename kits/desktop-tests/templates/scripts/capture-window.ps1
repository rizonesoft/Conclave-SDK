<#
.SYNOPSIS
    Capture a window or run a desktop capture command while holding the machine-wide desktop lock.
.DESCRIPTION
    Acquires Conclave.DesktopTests.DesktopLock before any desktop operation or output write, exports
    <ENV_PREFIX>_DESKTOP_HELD to any child capture command inside the owner's named desktop job,
    and releases the lock unconditionally after child cleanup.
#>
[CmdletBinding(PositionalBinding = $false)]
param(
    [string]$ProjectRoot,
    [string]$Out,
    [string]$Command,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$CommandArgs = @(),
    [int]$WindowPid = 0,
    [string]$Label = 'capture-window',
    [string]$Python
)

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$repo = if ($ProjectRoot) { (Resolve-Path -LiteralPath $ProjectRoot).Path } else { (Resolve-Path -LiteralPath (Join-Path $here '..')).Path }

$pyExe = $Python
if (-not $pyExe) {
    $p = Get-Command python -ErrorAction SilentlyContinue
    if (-not $p) { $p = Get-Command python3 -ErrorAction SilentlyContinue }
    if (-not $p) {
        [Console]::Error.WriteLine('capture-window: python not found on PATH')
        exit 2
    }
    $pyExe = $p.Source
}

$cfgLib = Join-Path $here 'lib\desktop_tests.py'
$cfgJson = & $pyExe -B $cfgLib show --root $repo 2>&1
if ($LASTEXITCODE -ne 0) {
    [Console]::Error.WriteLine(($cfgJson | Out-String).Trim())
    exit 2
}
$cfg = ($cfgJson | Out-String) | ConvertFrom-Json
$prefix = [string]$cfg.prefix
$envPrefix = [string]$cfg.env_prefix

if (-not ('Conclave.DesktopTests.DesktopLock' -as [type])) {
    $lockSrc = Join-Path $here 'lib\DesktopLock.cs'
    Add-Type -TypeDefinition ([IO.File]::ReadAllText($lockSrc, [Text.UTF8Encoding]::new($false))) -Language CSharp
}

function Quote-WinArg([string]$a) {
    if ($null -eq $a -or $a -eq '') { return '""' }
    if ($a -notmatch '[\s"]') { return $a }
    $sb = [Text.StringBuilder]::new('"')
    $bs = 0
    foreach ($ch in $a.ToCharArray()) {
        if ($ch -eq '\') { $bs++ }
        elseif ($ch -eq '"') {
            [void]$sb.Append('\', $bs * 2 + 1)
            [void]$sb.Append('"')
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

$lockHandle = $null
try {
    try {
        $lockHandle = [Conclave.DesktopTests.DesktopLock]::Acquire($prefix, $Label)
    } catch [Conclave.DesktopTests.DesktopLockBusyException] {
        [Console]::Error.WriteLine("capture-window: refused (busy): $($_.Exception.Message)")
        exit 1
    } catch [ArgumentException] {
        [Console]::Error.WriteLine("capture-window: invalid desktop lock configuration: $($_.Exception.Message)")
        exit 2
    }

    $lockHandle.EnsureStillHeld()

    if ($Command) {
        $childEnv = [Collections.Generic.Dictionary[string, string]]::new([StringComparer]::OrdinalIgnoreCase)
        foreach ($entry in [Environment]::GetEnvironmentVariables().GetEnumerator()) {
            $childEnv[[string]$entry.Key] = [string]$entry.Value
        }
        $childEnv["$($envPrefix)_DESKTOP_HELD"] = $lockHandle.HeldToken
        $argStr = ($CommandArgs | ForEach-Object { Quote-WinArg $_ }) -join ' '
        if (-not $lockHandle.Inherited) {
            # Keeps the child process handle open across wait + exit-code retrieval (no fast-exit PID lookup race).
            $exitCode = $lockHandle.RunProcessInJob($Command, $argStr, $repo, $childEnv)
            exit $exitCode
        } else {
            $psi = [Diagnostics.ProcessStartInfo]::new($Command, $argStr)
            $psi.WorkingDirectory = $repo
            $psi.UseShellExecute = $false
            $psi.CreateNoWindow = $true
            $psi.Environment["$($envPrefix)_DESKTOP_HELD"] = $lockHandle.HeldToken
            $proc = [Diagnostics.Process]::Start($psi)
            $proc.WaitForExit()
            $exitCode = $proc.ExitCode
            $proc.Dispose()
            exit $exitCode
        }
    }

    if ($WindowPid -gt 0 -and $Out) {
        Add-Type -AssemblyName System.Drawing
        if (-not ('ConclaveCaptureNative' -as [type])) {
            Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class ConclaveCaptureNative {
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
    public delegate bool EnumWindowsProc(IntPtr hwnd, IntPtr lParam);
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc cb, IntPtr lParam);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint pid);
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);
    [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hWnd, IntPtr hdcBlt, uint nFlags);
    public static IntPtr FindVisibleWindow(int targetPid) {
        IntPtr found = IntPtr.Zero;
        EnumWindows((h, lp) => {
            uint pid;
            GetWindowThreadProcessId(h, out pid);
            if ((int)pid == targetPid && IsWindowVisible(h)) { found = h; return false; }
            return true;
        }, IntPtr.Zero);
        return found;
    }
}
"@
        }
        $target = [Diagnostics.Process]::GetProcessById($WindowPid)
        $hwnd = $target.MainWindowHandle
        if ($hwnd -eq [IntPtr]::Zero) {
            $hwnd = [ConclaveCaptureNative]::FindVisibleWindow($WindowPid)
        }
        if ($hwnd -eq [IntPtr]::Zero) {
            [Console]::Error.WriteLine("capture-window: process $WindowPid has no visible window handle")
            exit 1
        }
        $rect = New-Object ConclaveCaptureNative+RECT
        if (-not [ConclaveCaptureNative]::GetWindowRect($hwnd, [ref]$rect)) {
            [Console]::Error.WriteLine("capture-window: GetWindowRect failed for pid $WindowPid")
            exit 1
        }
        $w = $rect.Right - $rect.Left
        $h = $rect.Bottom - $rect.Top
        if ($w -le 0 -or $h -le 0) {
            [Console]::Error.WriteLine("capture-window: window for pid $WindowPid has non-positive size (${w}x${h})")
            exit 1
        }
        $outDir = Split-Path -Parent $Out
        if ($outDir) { New-Item -ItemType Directory -Force -Path $outDir | Out-Null }
        $bmp = New-Object System.Drawing.Bitmap($w, $h)
        try {
            $g = [System.Drawing.Graphics]::FromImage($bmp)
            try {
                $hdc = $g.GetHdc()
                try {
                    $printed = [ConclaveCaptureNative]::PrintWindow($hwnd, $hdc, 2)
                    if (-not $printed) { $printed = [ConclaveCaptureNative]::PrintWindow($hwnd, $hdc, 0) }
                } finally {
                    $g.ReleaseHdc($hdc)
                }
            } finally {
                $g.Dispose()
            }
            if (-not $printed) {
                [Console]::Error.WriteLine("capture-window: PrintWindow failed for pid $WindowPid")
                exit 1
            }
            $lockHandle.EnsureStillHeld()
            $bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
        } finally {
            $bmp.Dispose()
        }
        "capture-window: saved $Out (${w}x${h})"
        exit 0
    }

    [Console]::Error.WriteLine('capture-window: specify -Command <exe> [args...] or both -WindowPid <pid> and -Out <path.png>')
    exit 2
} finally {
    if ($lockHandle) { $lockHandle.Dispose() }
}
