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
            $childPid = $lockHandle.StartProcessInJob($Command, $argStr, $repo, $childEnv)
            $proc = [Diagnostics.Process]::GetProcessById($childPid)
            $proc.WaitForExit()
            $exitCode = $proc.ExitCode
            $proc.Dispose()
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
        $target = [Diagnostics.Process]::GetProcessById($WindowPid)
        $hwnd = $target.MainWindowHandle
        if ($hwnd -eq [IntPtr]::Zero) {
            [Console]::Error.WriteLine("capture-window: process $WindowPid has no main window handle")
            exit 1
        }
        if (-not ('ConclaveCaptureNative' -as [type])) {
            Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class ConclaveCaptureNative {
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);
    [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hWnd, IntPtr hdcBlt, uint nFlags);
}
"@
        }
        $rect = New-Object ConclaveCaptureNative+RECT
        if (-not [ConclaveCaptureNative]::GetWindowRect($hwnd, [ref]$rect)) {
            [Console]::Error.WriteLine("capture-window: GetWindowRect failed for pid $WindowPid")
            exit 1
        }
        $w = [Math]::Max(1, $rect.Right - $rect.Left)
        $h = [Math]::Max(1, $rect.Bottom - $rect.Top)
        $outDir = Split-Path -Parent $Out
        if ($outDir) { New-Item -ItemType Directory -Force -Path $outDir | Out-Null }
        $bmp = New-Object System.Drawing.Bitmap($w, $h)
        try {
            $g = [System.Drawing.Graphics]::FromImage($bmp)
            try {
                $hdc = $g.GetHdc()
                try {
                    [void][ConclaveCaptureNative]::PrintWindow($hwnd, $hdc, 2)
                } finally {
                    $g.ReleaseHdc($hdc)
                }
            } finally {
                $g.Dispose()
            }
            $lockHandle.EnsureStillHeld()
            $bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
        } finally {
            $bmp.Dispose()
        }
        "capture-window: saved $Out (${w}x${h})"
        exit 0
    }

    if ($Out) {
        $outDir = Split-Path -Parent $Out
        if ($outDir) { New-Item -ItemType Directory -Force -Path $outDir | Out-Null }
        $lockHandle.EnsureStillHeld()
        [IO.File]::WriteAllText($Out, "captured pid=$($lockHandle.HolderPid) lock=$($lockHandle.LockName)`n", [Text.UTF8Encoding]::new($false))
        "capture-window: wrote $Out"
        exit 0
    }

    [Console]::Error.WriteLine('capture-window: specify -Command or -Out')
    exit 2
} finally {
    if ($lockHandle) { $lockHandle.Dispose() }
}
