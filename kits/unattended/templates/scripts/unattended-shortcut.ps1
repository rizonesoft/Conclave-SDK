# Puts "<Title> <Runner> campaign" shortcuts on the Windows desktop, one per runner the run profile names (its own
# agent and its `runners`), each starting the unattended run in WSL on that runner, with the project's icon and the
# runner's badge in its corner (the shape of Office's and Isotone's campaign launchers). The run lives in tmux, in WSL;
# Windows only starts it.
#
#   pwsh scripts/unattended-shortcut.ps1 -Distro Ubuntu -Icon assets/brand/project.ico
#   pwsh scripts/unattended-shortcut.ps1 -Remove       remove every shortcut and icon this project made
#
# Each link runs PowerShell, which runs `wsl.exe -d <distro> --cd <project in WSL> --exec bash -lc <start command>`:
# the command `unattended-run.py`'s start_command gives (a test holds the two equal), which starts the run on the runner
# and, on a failure, says so and waits for Enter; a failure of WSL itself is said and waits for Enter too.
# Links and icons are written under a temporary name and moved over the old, so a failed save or icon keeps a
# working shortcut and leaves no broken one.
# The title is the launcher profile's (`.conclave/launchers.json`, read by `scripts/lib/launchers.py title`), the name
# the project's other links carry; with no profile, or its title not set yet, the links carry the folder's name.
# A link of this project's that a run does not write (an earlier title, a runner dropped) goes, with its icon.
# Removal finds this project's links by the mark in their description, so it works whatever the profile, the icon
# or the distro now are. Nothing here starts a run: only the operator's double-click does.
param(
  [string]$Distro = '',
  [string]$Icon = '',
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
# The project this script is installed in holds the profile; -Project says where the run starts when that differs
# (a project in WSL given by its \\wsl.localhost\<distro>\ path, or its Linux path).
$root = Split-Path $here
if (-not $Project) { $Project = $root }
if (-not ($Project -match '^\\\\wsl(?:\.localhost|\$)\\' -or $Project.StartsWith('/'))) {
  $found = Resolve-Path -LiteralPath $Project -ErrorAction Ignore
  if (-not $found) { "unattended-shortcut: the project folder does not exist: '$Project'; nothing was written"; exit 1 }
  # ProviderPath, not Path: for a folder on a share Path keeps the provider's prefix
  # (`Microsoft.PowerShell.Core\FileSystem::`), which the mark and wslpath would then carry.
  $Project = $found.ProviderPath.TrimEnd('\')
}
$name = Split-Path $Project -Leaf
if (-not $IconDir) { $IconDir = Join-Path $env:LOCALAPPDATA $name }

function Refuse([string]$why) { "unattended-shortcut: $why; nothing was written"; exit 1 }

# The project's identity, in its links' mark and its icons' key: one form for a project in WSL, whichever form -Project
# takes, with the distro in it, so /home/x/demo in Ubuntu and in Debian are two projects (D07 T01 section 7).
if ($Project -match '^\\\\wsl(?:\.localhost|\$)\\([^\\]+)\\(.*)$') {
  $identity = "\\wsl.localhost\$($Matches[1])\$($Matches[2].TrimEnd('\'))"
} elseif ($Project.StartsWith('/')) {
  if (-not $Distro) { Refuse "-Project '$Project' is a Linux path: -Distro names the distro it is in" }
  $identity = "\\wsl.localhost\$Distro" + ($Project.TrimEnd('/') -replace '/', '\')
} else {
  $identity = $Project
}
function Get-Key([string]$text) {
  $sha = [System.Security.Cryptography.SHA256]::Create()
  -join ($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($text.ToLowerInvariant()))[0..3] | ForEach-Object { $_.ToString('x2') })
}
$mark = "conclave-unattended: $identity"
$key = Get-Key $identity
# What the script wrote before it had one identity (the -Project form as typed) is this project's too: it goes with
# the rest, and the next run writes the new form.
$marks = @($mark, "conclave-unattended: $Project") | Select-Object -Unique
$keys = @($key, (Get-Key $Project)) | Select-Object -Unique
$labels = @{ claude = 'Claude'; codex = 'Codex'; agy = 'Carbon' }

# A link's mark, read through Shell.Application, which opens a file of any name.
# WORKAROUND: WScript.Shell opens and saves a .lnk through the ANSI code page, so it reads nothing from a link named
# by a title outside it (a CJK title, probed 2026-11-18) and cannot save one; links are saved under an ASCII
# temporary name and moved to their own.
$app = New-Object -ComObject Shell.Application
function Get-Mark([IO.FileSystemInfo]$file) {
  $item = $app.NameSpace([IO.Path]::GetDirectoryName($file.FullName)).ParseName($file.Name)
  if ($item -and $item.IsLink) { $item.GetLink.Description } else { '' }
}

function Get-Owned {
  Get-ChildItem -LiteralPath $ShortcutDir -Filter '*campaign*.lnk' -File -ErrorAction Ignore |
    Where-Object { $marks -contains (Get-Mark $_) }
}

# Named apart from the -Icon parameter: PowerShell names ignore case, and $icon would be that typed string.
function Get-Badges {
  foreach ($k in $keys) { Get-ChildItem -LiteralPath $IconDir -Filter "campaign-*-$k.ico" -File -ErrorAction Ignore }
}

if ($Remove) {
  $links = @(Get-Owned)
  foreach ($link in $links) { Remove-Item -LiteralPath $link.FullName; "removed: $($link.FullName)" }
  $badges = @(Get-Badges)
  foreach ($badge in $badges) { Remove-Item -LiteralPath $badge.FullName; "removed: $($badge.FullName)" }
  "unattended-shortcut: $($links.Count) shortcut(s) and $($badges.Count) icon(s) of $Project removed"
  exit 0
}

if (-not $Distro) { Refuse '-Distro names no WSL distro' }
if (-not $Icon -or -not (Test-Path -LiteralPath $Icon -PathType Leaf)) { Refuse "-Icon is not a file: '$Icon'" }
if (-not $Python) {
  $Python = (Get-Command python -CommandType Application -ErrorAction Ignore | Select-Object -First 1).Source
}
if (-not $Python) { Refuse 'python is not on PATH' }
if (-not $Wsl) {
  $Wsl = (Get-Command wsl.exe -CommandType Application -ErrorAction Ignore | Select-Object -First 1).Source
}
if (-not $Wsl) { Refuse 'wsl.exe is not on PATH: install WSL' }
$env:WSL_UTF8 = '1'  # wsl.exe lists its distros in UTF-16 otherwise
# Every call into WSL is --exec: `wsl.exe -- <command>` hands the command to the login shell, which eats the
# backslashes of a Windows path and parses the start command again (found by the live proof, 2026-11-13).

# The runners, read by the kit's own profile loader, so a profile the run would refuse is refused here too.
$reader = @'
import importlib.util, json, sys
spec = importlib.util.spec_from_file_location("unattended_lib", sys.argv[1])
lib = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lib)
profile = lib.load_profile(sys.argv[2])
print(json.dumps([profile["agent"], *profile.get("runners", {})]))
'@
$read = & $Python -B -c $reader (Join-Path $here 'lib\unattended.py') $root 2>&1
if ($LASTEXITCODE -ne 0) { Refuse "the run profile cannot be read: $(($read | Out-String).Trim())" }
$agents = @(($read | Select-Object -Last 1) | ConvertFrom-Json)

# The title, read by the launchers kit's own loader (which this kit brings), so a profile its links would refuse is
# refused here too; `null` is a profile with no title yet, as that kit installs it.
$title = $name
if (Test-Path -LiteralPath (Join-Path $root '.conclave\launchers.json')) {
  $loader = Join-Path $here 'lib\launchers.py'
  if (-not (Test-Path -LiteralPath $loader -PathType Leaf)) {
    Refuse ('the launcher profile cannot be read: there is no scripts/lib/launchers.py ' +
      '(python forge.py kit <project> unattended installs it)')
  }
  $read = & $Python -B $loader title --root $root 2>&1
  if ($LASTEXITCODE -ne 0) { Refuse "the launcher profile cannot be read: $(($read | Out-String).Trim())" }
  $set = ($read | Select-Object -Last 1) | ConvertFrom-Json
  if ($set) { $title = $set }
}

$listed = @(& $Wsl -l -q 2>$null | ForEach-Object { ($_ -replace "`0", '').Trim() } | Where-Object { $_ })
if ($LASTEXITCODE -ne 0 -or $listed -notcontains $Distro) {
  Refuse "WSL has no distro '$Distro' (it lists: $($listed -join ', '))"
}

# The project's path in WSL: a \\wsl.localhost\<distro>\ or \\wsl$\<distro>\ path is that distro's own path, a Linux
# path is itself, and a Windows-drive path is what wslpath says.
if ($Project -match '^\\\\wsl(?:\.localhost|\$)\\([^\\]+)\\(.*)$') {
  if ($Matches[1] -ne $Distro) { Refuse "the project is in distro '$($Matches[1])', not '$Distro'" }
  $linux = '/' + ($Matches[2] -replace '\\', '/')
} elseif ($Project.StartsWith('/')) {
  $linux = $Project
} else {
  $linux = (& $Wsl -d $Distro --exec wslpath -a $Project 2>$null | Select-Object -First 1)
  if ($LASTEXITCODE -ne 0 -or -not $linux) { Refuse "wslpath could not translate '$Project'" }
  $linux = $linux.Trim()
}
& $Wsl -d $Distro --exec test -d $linux 2>$null
if ($LASTEXITCODE -ne 0) { Refuse "the project path '$linux' does not exist in '$Distro'" }

# A PowerShell string literal of any text.
function PSQuote([string]$text) { "'" + $text.Replace("'", "''") + "'" }

# One argument as the Windows command line passes it (backslashes doubled before a quote, the quote escaped).
function Quote([string]$arg) {
  if ($arg -and $arg -notmatch '[\s"]') { return $arg }
  '"' + ($arg -replace '(\\*)"', '$1$1\"' -replace '(\\+)$', '$1$1') + '"'
}

$renderer = Join-Path $here 'campaign-icon.py'
$pwsh = (Get-Process -Id $PID).Path  # the PowerShell 7 that runs this script runs the links too
# ProviderPath, not Path: for an icon on a share (\\wsl.localhost\...) Path keeps the provider's prefix
# (`Microsoft.PowerShell.Core\FileSystem::`), and the renderer cannot open a file named that way.
$brand = (Resolve-Path -LiteralPath $Icon).ProviderPath
$shell = New-Object -ComObject WScript.Shell

# Every link and its badge, by runner. A name held by a file this project did not write (another project's link with
# the same title and runner, or a folder) is refused before anything is written: a move would replace it.
$planned = foreach ($agent in $agents) {
  $label = "$title $($labels[$agent]) campaign"
  $badge = Join-Path $IconDir "campaign-$agent-$key.ico"
  $link = Join-Path $ShortcutDir "$label.lnk"
  [pscustomobject]@{ Agent = $agent; Label = $label; Badge = $badge; BadgeTemp = "$badge.$PID.tmp.ico"; Link = $link
    LinkTemp = Join-Path $ShortcutDir "campaign-$agent-$key.$PID.tmp.lnk" }
}
foreach ($p in $planned) {
  $held = Get-Item -LiteralPath $p.Link -Force -ErrorAction Ignore
  if ($held -and ($held.PSIsContainer -or $marks -notcontains (Get-Mark $held))) {
    Refuse "the shortcut name '$($p.Label).lnk' is held by a file this project did not write: '$($held.FullName)'"
  }
}
function Clear-Temps { foreach ($p in $planned) { Remove-Item -LiteralPath $p.BadgeTemp, $p.LinkTemp -ErrorAction Ignore } }

# Two steps: every badge and link is written under its temporary name first, and only then moved over the old, so a
# failure before the moves leaves every previous link and badge as it was and no temporary file.
New-Item -ItemType Directory -Force -Path $IconDir, $ShortcutDir | Out-Null
foreach ($p in $planned) {
  & $Python -B $renderer badge $brand $p.Agent $p.BadgeTemp
  if ($LASTEXITCODE -ne 0) {
    Clear-Temps
    "unattended-shortcut: the icon for $($p.Label) could not be rendered; its shortcut is left as it was"
    exit 1
  }
  $command = "python3 scripts/unattended-run.py start --agent $($p.Agent) || " +
    "{ echo 'The run did not start: the reason is above. Press Enter to close.'; read -r _; }"
  try {
    $shortcut = $shell.CreateShortcut($p.LinkTemp)
    # PowerShell runs wsl.exe, so a failure of WSL itself (a drive gone, a distro removed) is said and waits for Enter
    # too; the command is in the link, not in a script on the project's drive, which may be the one that is gone.
    $words = @('-d', $Distro, '--cd', $linux, '--exec', 'bash', '-lc', $command)
    $code = "& $(PSQuote $Wsl) $(($words | ForEach-Object { PSQuote $_ }) -join ' '); if (`$LASTEXITCODE -ne 0) { " +
      "Write-Host ('WSL could not start the run (exit ' + `$LASTEXITCODE + '): the reason is above. ' + " +
      "'Press Enter to close.'); " +
      "[void][Console]::ReadLine() }"
    $shortcut.TargetPath = $pwsh
    $shortcut.Arguments = "-NoLogo -NoProfile -Command $(Quote $code)"
    $shortcut.WorkingDirectory = $env:USERPROFILE
    $shortcut.Description = $mark
    $shortcut.IconLocation = "$($p.Badge),0"
    $shortcut.Save()
  } catch {
    Clear-Temps
    "unattended-shortcut: the shortcut $($p.Label) could not be saved ($($_.Exception.Message)); the old one is kept"
    exit 1
  }
}
foreach ($p in $planned) {
  try {
    Move-Item -LiteralPath $p.BadgeTemp -Destination $p.Badge -Force
    Move-Item -LiteralPath $p.LinkTemp -Destination $p.Link -Force
  } catch {
    Clear-Temps
    "unattended-shortcut: the shortcut $($p.Label) could not be put in place ($($_.Exception.Message)); " +
      'the shortcuts not yet moved are left as they were'
    exit 1
  }
  "shortcut written: $($p.Link)"
}

# A link or badge of this project's that this run did not write (an earlier title, a runner dropped, the old mark's
# key) goes. Compared by file name: each list is of one folder, whose spelling (an 8.3 short name) may differ.
$writtenLinks = @($planned | ForEach-Object { Split-Path $_.Link -Leaf })
$writtenIcons = @($planned | ForEach-Object { Split-Path $_.Badge -Leaf })
foreach ($stale in @(Get-Owned | Where-Object { $writtenLinks -notcontains $_.Name })) {
  Remove-Item -LiteralPath $stale.FullName; "removed: $($stale.FullName)"
}
foreach ($stale in @(Get-Badges | Where-Object { $writtenIcons -notcontains $_.Name })) {
  Remove-Item -LiteralPath $stale.FullName; "removed: $($stale.FullName)"
}
exit 0
