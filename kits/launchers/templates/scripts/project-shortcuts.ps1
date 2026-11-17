# Puts "<Title> (<Agent>)" links on the Windows desktop, one per agent the launcher profile names
# (.conclave/launchers.json): a double-click opens a terminal in the project with the agent running. Beside them goes
# one "<Title> (<label>)" link per entry of the profile's `links`: a `run` entry runs its command in the project, a
# `url` entry opens its address in the default browser. Each icon is the project's own icon with the agent's or the
# entry's mark in a rounded square in its corner, rendered on this machine.
#
#   pwsh scripts/project-shortcuts.ps1                    a project on a Windows drive, or one opened from its
#                                                         \\wsl.localhost\<distro>\ path (the distro is read from it)
#   pwsh scripts/project-shortcuts.ps1 -Distro Ubuntu -Project /home/me/site
#   pwsh scripts/project-shortcuts.ps1 -Remove            remove every link and icon this script made for the project
#
# A project in WSL opens in Windows Terminal as `wsl.exe -d <distro> --cd <linux path> --exec bash -lic <agent>`: the
# shell is interactive because an owner's wrapper for the agent (one that loads a token, say) lives in ~/.bashrc, after
# its "not interactive: return" guard. A project on a Windows drive opens as `wt.exe -d <project> pwsh.exe -NoLogo
# -NoExit -Command <agent>`. Without Windows Terminal the link starts PowerShell itself, which for a WSL project runs
# wsl.exe and, if WSL fails, says so and waits for Enter. An agent that does not start says so and waits for Enter too.
#
# A `run` entry opens in PowerShell. For a project in WSL it runs `wsl.exe -d <distro> --cd <linux path> --exec bash
# -lc <command> || { echo '<label> did not start: ...'; read -r _; }` (PowerShell starts wsl.exe with --exec, so the
# login shell parses the command once); for a project on a Windows drive it runs the command in the project folder.
# Either way a failure stays on screen until Enter. A `url` entry's link starts `rundll32.exe url.dll,
# FileProtocolHandler <url>`, which opens the browser with no console window.
#
# Each project has one identity: its distro and Linux path for a project in WSL (however the path was written), or its
# full Windows path. The links carry it in their description, which is how this script finds its own links, and the
# icons carry a key derived from it, so two projects never touch each other's files. Everything is written under a
# temporary name first and moved into place only when all of it succeeded; a failure leaves every earlier link and
# icon as it was. A link of this project's that the profile no longer names is removed after a successful write.
# The campaign links of the unattended kit carry their own mark and are never touched here.
param(
  [string]$Distro = '',
  [string]$Project = '',
  [string]$ShortcutDir = [Environment]::GetFolderPath('Desktop'),
  [string]$IconDir = '',
  [switch]$Remove,
  # For the tests: a stand-in for wsl.exe, and the Python that reads the profile and renders the icons.
  [string]$Wsl = '',
  [string]$Python = ''
)
$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
$root = Split-Path $here   # the project this script is installed in holds the profile
if (-not $Project) { $Project = $root }

function Refuse([string]$why) { "project-shortcuts: $why; nothing was written"; exit 1 }

# --- the project's identity ---------------------------------------------------------------------------------------
$linux = $null
if ($Project -match '^\\\\wsl(?:\.localhost|\$)\\([^\\]+)\\?(.*)$') {
  if (-not $Distro) { $Distro = $Matches[1] }
  elseif ($Matches[1] -ne $Distro) { Refuse "the project is in distro '$($Matches[1])', not '$Distro'" }
  $linux = '/' + ($Matches[2] -replace '\\', '/')
} elseif ($Project.StartsWith('/')) {
  if (-not $Distro) { Refuse "a Linux path needs -Distro to say which WSL distro holds it: '$Project'" }
  $linux = $Project
}
if ($null -ne $linux) {
  $linux = ($linux -replace '/+', '/').TrimEnd('/')
  if (-not $linux) { $linux = '/' }
  # Linux paths keep their case (/srv/Site and /srv/site are two projects); distro names ignore it.
  $identity = "wsl:$($Distro.ToLowerInvariant()):$linux"
  $name = Split-Path $linux -Leaf
} else {
  if ($Remove) {
    $Project = [IO.Path]::GetFullPath($Project).TrimEnd('\')   # removal works when the folder is gone
  } else {
    $found = Resolve-Path -LiteralPath $Project -ErrorAction Ignore
    if (-not $found) { Refuse "the project folder does not exist: '$Project'" }
    # ProviderPath: .Path keeps PowerShell's provider prefix on some paths, which no other program reads.
    $Project = $found.ProviderPath.TrimEnd('\')
  }
  $identity = $Project.ToLowerInvariant()   # Windows paths ignore case
  $name = Split-Path $Project -Leaf
}
if (-not $IconDir) { $IconDir = Join-Path $env:LOCALAPPDATA $name }
$mark = "conclave-launcher: $identity"
$sha = [System.Security.Cryptography.SHA256]::Create()
# Every comparison of an identity below is exact (-ceq): PowerShell's -eq ignores case.
$key = -join ($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($identity))[0..3] | ForEach-Object { $_.ToString('x2') })

function Get-Owned {
  $shell = New-Object -ComObject WScript.Shell
  Get-ChildItem -LiteralPath $ShortcutDir -Filter '*.lnk' -File -ErrorAction Ignore |
    Where-Object { $shell.CreateShortcut($_.FullName).Description -ceq $mark }
}

# --- removal: needs nothing but the identity ----------------------------------------------------------------------
if ($Remove) {
  $links = @(Get-Owned)
  foreach ($link in $links) { Remove-Item -LiteralPath $link.FullName -Force; "removed: $($link.FullName)" }
  $icons = @(Get-ChildItem -LiteralPath $IconDir -Filter "launcher-*-$key.ico" -File -ErrorAction Ignore)
  foreach ($file in $icons) { Remove-Item -LiteralPath $file.FullName -Force; "removed: $($file.FullName)" }
  "project-shortcuts: $($links.Count) link(s) and $($icons.Count) icon(s) of $identity removed"
  exit 0
}

# --- what to write ------------------------------------------------------------------------------------------------
if (-not $Python) {
  $Python = (Get-Command python -CommandType Application -ErrorAction Ignore | Select-Object -First 1).Source
}
if (-not $Python) { Refuse 'python is not on PATH' }
# The profile, read by the kit's own loader, so a profile it refuses is refused here with its own message.
$read = & $Python -B (Join-Path $here 'lib\launchers.py') show --root $root 2>&1
if ($LASTEXITCODE -ne 0) { Refuse "the launcher profile cannot be read: $(($read | Out-String).Trim())" }
$launch = ($read | Select-Object -Last 1) | ConvertFrom-Json
$brand = (Resolve-Path -LiteralPath (Join-Path $root $launch.icon)).ProviderPath

if ($null -ne $linux) {
  if (-not $Wsl) {
    $Wsl = (Get-Command wsl.exe -CommandType Application -ErrorAction Ignore | Select-Object -First 1).Source
  }
  if (-not $Wsl) { Refuse 'wsl.exe is not on PATH: install WSL' }
  $env:WSL_UTF8 = '1'  # wsl.exe lists its distros in UTF-16 otherwise
  $listed = @(& $Wsl -l -q 2>$null | ForEach-Object { ($_ -replace "`0", '').Trim() } | Where-Object { $_ })
  if ($LASTEXITCODE -ne 0 -or $listed -notcontains $Distro) {
    Refuse "WSL has no distro '$Distro' (it lists: $($listed -join ', '))"
  }
  & $Wsl -d $Distro --exec test -d $linux 2>$null
  if ($LASTEXITCODE -ne 0) { Refuse "the project path '$linux' does not exist in '$Distro'" }
}

$labels = [ordered]@{ claude = 'Claude'; codex = 'Codex'; agy = 'Antigravity' }
# The flag each agent's CLI takes to skip its permission prompts, as scripts/unattended-run.py passes it (a test in
# the SDK holds the two equal).
$skipFlags = @{ claude = '--dangerously-skip-permissions'; codex = '--dangerously-bypass-approvals-and-sandbox';
                agy = '--dangerously-skip-permissions' }

# One argument as the Windows command line passes it (backslashes doubled before a quote, the quote escaped).
function Quote([string]$arg) {
  if ($arg -and $arg -notmatch '[\s"]') { return $arg }
  '"' + ($arg -replace '(\\*)"', '$1$1\"' -replace '(\\+)$', '$1$1') + '"'
}
# A PowerShell string literal of any text.
function PSQuote([string]$text) { "'" + $text.Replace("'", "''") + "'" }
# A Bash single-quoted word of any text (a quote inside it closes the word, writes an escaped quote and reopens it).
function BashQuote([string]$text) { "'" + $text.Replace("'", "'\''") + "'" }

$wt = (Get-Command wt.exe -CommandType Application -ErrorAction Ignore | Select-Object -First 1).Source
$pwshExe = (Get-Process -Id $PID).Path  # the PowerShell 7 that runs this script runs the links too
$shell = New-Object -ComObject WScript.Shell
$plan = @()
foreach ($agent in $launch.agents) {
  $label = "$($launch.title) ($($labels[$agent]))"
  $link = Join-Path $ShortcutDir "$label.lnk"
  # A name another project or anything else holds is never written over.
  if (Test-Path -LiteralPath $link) {
    $holder = if (Test-Path -LiteralPath $link -PathType Leaf) { $shell.CreateShortcut($link).Description } else { '' }
    if ($holder -cne $mark) { Refuse "'$link' is already there and is not this project's link" }
  }
  $command = if ($launch.skip_permissions) { "$agent $($skipFlags[$agent])" } else { $agent }
  if ($null -ne $linux) {
    # No semicolon: Windows Terminal would read one as the start of its own next command.
    $bash = "$command || (echo '$($labels[$agent]) did not start: the reason is above. Press Enter to close.' && read -r _)"
    $wslWords = @('-d', $Distro, '--cd', $linux, '--exec', 'bash', '-lic', $bash)
    if ($wt) {
      $target = $wt; $arguments = (@($Wsl) + $wslWords | ForEach-Object { Quote $_ }) -join ' '
    } else {
      $code = "& $(PSQuote $Wsl) $(($wslWords | ForEach-Object { PSQuote $_ }) -join ' '); if (`$LASTEXITCODE -ne 0) { " +
        "Write-Host ('WSL could not open the project (exit ' + `$LASTEXITCODE + '): the reason is above. " +
        "Press Enter to close.'); [void][Console]::ReadLine() }"
      $target = $pwshExe; $arguments = "-NoLogo -NoProfile -Command $(Quote $code)"
    }
    $workdir = $env:USERPROFILE
  } else {
    $pwshWords = @('-NoLogo', '-NoExit', '-Command', $command)
    if ($wt) { $target = $wt; $words = @('-d', $Project, $pwshExe) + $pwshWords } else { $target = $pwshExe; $words = $pwshWords }
    $arguments = ($words | ForEach-Object { Quote $_ }) -join ' '
    $workdir = $Project
  }
  $plan += [pscustomobject]@{ Mark = $agent; Label = $label; Link = $link; Target = $target; Arguments = $arguments
                              Workdir = $workdir; Icon = (Join-Path $IconDir "launcher-$agent-$key.ico") }
}
# The profile's declared links (its loader has checked each: a label no agent or other entry uses, a known mark, and a
# one-line command or an http(s) address with no whitespace).
foreach ($entry in @($launch.links)) {
  $label = "$($launch.title) ($($entry.label))"
  $link = Join-Path $ShortcutDir "$label.lnk"
  if (Test-Path -LiteralPath $link) {
    $holder = if (Test-Path -LiteralPath $link -PathType Leaf) { $shell.CreateShortcut($link).Description } else { '' }
    if ($holder -cne $mark) { Refuse "'$link' is already there and is not this project's link" }
  }
  # The icon's name: the label in lower case, each run of other characters one hyphen (launchers.py's slug).
  $slug = ($entry.label.ToLowerInvariant() -creplace '[^a-z0-9]+', '-').Trim('-')
  if ($entry.PSObject.Properties['url']) {
    $target = Join-Path $env:SystemRoot 'System32\rundll32.exe'
    $arguments = "url.dll,FileProtocolHandler $($entry.url)"
    $workdir = $env:USERPROFILE
  } else {
    $failed = "$($entry.label) did not start: the reason is above. Press Enter to close."
    if ($null -ne $linux) {
      $bash = "$($entry.run) || { echo $(BashQuote $failed); read -r _; }"
      $wslWords = @('-d', $Distro, '--cd', $linux, '--exec', 'bash', '-lc', $bash)
      $wslFailed = PSQuote "$($entry.label): WSL could not open the project (exit "
      $code = "& $(PSQuote $Wsl) $(($wslWords | ForEach-Object { PSQuote $_ }) -join ' '); if (`$LASTEXITCODE -ne 0) { " +
        "Write-Host ($wslFailed + `$LASTEXITCODE + '): the reason is above. Press Enter to close.'); " +
        "[void][Console]::ReadLine() }"
      $workdir = $env:USERPROFILE
    } else {
      # A command that throws is caught, and one that exits non-zero sets $LASTEXITCODE: either way it waits.
      $code = "`$ErrorActionPreference = 'Stop'; `$LASTEXITCODE = 0; `$ok = `$true; " +
        "try { $($entry.run) } catch { Write-Host `$_; `$ok = `$false }; " +
        "if (-not `$ok -or `$LASTEXITCODE -ne 0) { Write-Host $(PSQuote $failed); [void][Console]::ReadLine() }"
      $workdir = $Project
    }
    $target = $pwshExe
    $arguments = "-NoLogo -NoProfile -Command $(Quote $code)"
  }
  $plan += [pscustomobject]@{ Mark = $entry.mark; Label = $label; Link = $link; Target = $target
                              Arguments = $arguments; Workdir = $workdir
                              Icon = (Join-Path $IconDir "launcher-$slug-$key.ico") }
}

# --- write: everything staged, then moved into place together ----------------------------------------------------
New-Item -ItemType Directory -Force -Path $IconDir, $ShortcutDir | Out-Null
$renderer = Join-Path $here 'campaign-icon.py'
$staged = [System.Collections.Generic.List[object]]::new()   # (temporary file, destination)
function Unstage { foreach ($s in $staged) { Remove-Item -LiteralPath $s.Temp -Force -ErrorAction Ignore } }
try {
  foreach ($item in $plan) {
    $iconTemp = "$($item.Icon).$PID.tmp.ico"
    $staged.Add([pscustomobject]@{ Temp = $iconTemp; Dest = $item.Icon })
    $out = & $Python -B $renderer overlay $brand $item.Mark $iconTemp 2>&1
    if ($LASTEXITCODE -ne 0) { throw "the icon for $($item.Label) could not be rendered: $(($out | Out-String).Trim())" }
    $linkTemp = Join-Path $ShortcutDir "$($item.Label).$PID.tmp.lnk"
    $staged.Add([pscustomobject]@{ Temp = $linkTemp; Dest = $item.Link })
    $shortcut = $shell.CreateShortcut($linkTemp)
    $shortcut.TargetPath = $item.Target
    $shortcut.Arguments = $item.Arguments
    $shortcut.WorkingDirectory = $item.Workdir
    $shortcut.Description = $mark
    $shortcut.IconLocation = "$($item.Icon),0"
    $shortcut.Save()
  }
} catch {
  Unstage
  "project-shortcuts: $($_.Exception.Message); every earlier link and icon is kept"
  exit 1
}
$moved = [System.Collections.Generic.List[object]]::new()   # (destination, backup or null), to put back on a failure
# A link of this project's that this run does not write (an agent taken out of the profile, an earlier title) goes,
# with its icon, so the desktop holds exactly what the profile names: moved aside in the same step as the new files.
# Compared by file name in the folder, never by full path: the folder may be spelled another way than the one the
# file system reports (a short 8.3 name, a .. segment), which once listed this run's own temporary links as stale:
# after they were renamed into place the stale step could not find them, and the whole run rolled back.
$written = @($plan | ForEach-Object { Split-Path $_.Link -Leaf }) + @($staged | ForEach-Object { Split-Path $_.Temp -Leaf })
$kept = @($plan | ForEach-Object { Split-Path $_.Icon -Leaf })
$stale = @(Get-Owned | Where-Object { $written -notcontains $_.Name } | ForEach-Object { $_.FullName }) +
         @(Get-ChildItem -LiteralPath $IconDir -Filter "launcher-*-$key.ico" -File -ErrorAction Ignore |
           Where-Object { $kept -notcontains $_.Name } | ForEach-Object { $_.FullName })
try {
  foreach ($s in $staged) {
    $backup = $null
    if (Test-Path -LiteralPath $s.Dest) {
      $backup = "$($s.Dest).$PID.old"
      Move-Item -LiteralPath $s.Dest -Destination $backup
    }
    $entry = [pscustomobject]@{ Dest = $s.Dest; Backup = $backup; Placed = $false }
    $moved.Add($entry)
    Move-Item -LiteralPath $s.Temp -Destination $s.Dest
    $entry.Placed = $true
  }
  foreach ($old in $stale) {
    $backup = "$old.$PID.old"
    Move-Item -LiteralPath $old -Destination $backup
    $moved.Add([pscustomobject]@{ Dest = $old; Backup = $backup; Placed = $false })
  }
} catch {
  $why = $_.Exception.Message
  $moved.Reverse()
  foreach ($m in $moved) {
    if ($m.Placed) { Remove-Item -LiteralPath $m.Dest -Force -ErrorAction Ignore }
    if ($m.Backup) { Move-Item -LiteralPath $m.Backup -Destination $m.Dest -Force -ErrorAction Ignore }
  }
  Unstage
  "project-shortcuts: a link or icon could not be put in place or removed ($why); every earlier link and icon is kept"
  exit 1
}
foreach ($m in $moved) { if ($m.Backup) { Remove-Item -LiteralPath $m.Backup -Force -ErrorAction Ignore } }
foreach ($item in $plan) { "link written: $($item.Link)" }
foreach ($old in $stale) { "removed: $old" }
exit 0
