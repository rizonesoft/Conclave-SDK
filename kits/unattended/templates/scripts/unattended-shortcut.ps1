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

function Refuse([string]$why) { "unattended-shortcut: $why; nothing was written"; exit 1 }

# Links are written and read through the shell's own IShellLinkW (`scripts/lib/ShellLink.cs`, the launchers kit's,
# which this kit brings), which keeps a name, a mark, a path or an argument in any script at its full length, and
# spells a path long.
$linkCode = Join-Path $here 'lib\ShellLink.cs'
if (-not (Test-Path -LiteralPath $linkCode -PathType Leaf)) {
  Refuse 'there is no scripts/lib/ShellLink.cs (python forge.py kit <project> unattended installs it)'
}
Add-Type -Path $linkCode

if (-not $Project) { $Project = $root }
if (-not ($Project -match '^\\\\wsl(?:\.localhost|\$)\\' -or $Project.StartsWith('/'))) {
  $found = Resolve-Path -LiteralPath $Project -ErrorAction Ignore
  if (-not $found) { "unattended-shortcut: the project folder does not exist: '$Project'; nothing was written"; exit 1 }
  # ProviderPath, not Path: for a folder on a share Path keeps the provider's prefix
  # (`Microsoft.PowerShell.Core\FileSystem::`), which the mark and wslpath would then carry. Spelt long, so a folder
  # handed in by its 8.3 short name (C:\Users\RUNNER~1) is the same project as by its own.
  $Project = [Conclave.ShellPath]::Long($found.ProviderPath).TrimEnd('\')
}
$name = Split-Path $Project -Leaf
if (-not $IconDir) { $IconDir = Join-Path $env:LOCALAPPDATA $name }

# A PowerShell string literal of any text.
function PSQuote([string]$text) { "'" + $text.Replace("'", "''") + "'" }

# The project's identity, in its links' mark and its icons' key: one form for a project in WSL, whichever form -Project
# takes, with the distro in it, so /home/x/demo in Ubuntu and in Debian are two projects (D07 T01 section 7).
$projectDistro = ''
if ($Project -match '^\\\\wsl(?:\.localhost|\$)\\([^\\]+)\\(.*)$') {
  $projectDistro = $Matches[1]
  $identity = "\\wsl.localhost\$($Matches[1])\$($Matches[2].TrimEnd('\'))"
} elseif ($Project.StartsWith('/')) {
  if (-not $Distro) { Refuse "-Project '$Project' is a Linux path: -Distro names the distro it is in" }
  $projectDistro = $Distro
  $identity = "\\wsl.localhost\$Distro" + ($Project.TrimEnd('/') -replace '/', '\')
} else {
  $identity = $Project
}
# The form identities are compared in: a Windows path is spelt long and ignores case; in WSL the distro's name ignores
# case and the Linux path keeps it, since /home/x/Demo and /home/x/demo are two folders there.
function Get-Normal([string]$id) {
  if ($id -match '^\\\\wsl(?:\.localhost|\$)\\([^\\]+)(.*)$') {
    return '\\wsl.localhost\' + $Matches[1].ToLowerInvariant() + $Matches[2]
  }
  if ($id.StartsWith('/')) { return $id }
  [Conclave.ShellPath]::Long($id).ToLowerInvariant()
}
function Get-Key([string]$text) {
  $sha = [System.Security.Cryptography.SHA256]::Create()
  -join ($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($text))[0..3] | ForEach-Object { $_.ToString('x2') })
}
$prefix = 'conclave-unattended: '
$mark = "$prefix$identity"
$normal = Get-Normal $identity
$key = Get-Key $normal
$labels = @{ claude = 'Claude'; codex = 'Codex'; agy = 'Carbon' }

# A link's fields, or nothing for a file the shell cannot load as one.
function Get-Link([IO.FileSystemInfo]$file) {
  try { [Conclave.ShellLink]::Read($file.FullName) } catch { $null }
}

function Get-Mark([IO.FileSystemInfo]$file) {
  $link = Get-Link $file
  if ($link) { $link.Description } else { '' }
}

# Whether a link is this project's: its mark names this identity, or it is the mark the script wrote before it had one
# identity (the -Project form as typed). An old mark of a Linux path names no distro, so it is this project's only when
# its link starts the run in this project's distro.
function Test-Owned([IO.FileSystemInfo]$file) {
  $text = Get-Mark $file
  if (-not $text.StartsWith($prefix)) { return $false }
  $id = Get-Normal $text.Substring($prefix.Length)
  if ($id -ceq $normal) { return $true }
  if (-not $Project.StartsWith('/') -or $id -cne $Project) { return $false }
  $words = "$(PSQuote '-d') $(PSQuote $projectDistro) "
  (Get-Link $file).Arguments.IndexOf($words, [StringComparison]::OrdinalIgnoreCase) -ge 0
}

function Get-Owned {
  # A run's temporary links (`<name>.<pid>.tmp.lnk`) are not the project's links: they are leftovers.
  Get-ChildItem -LiteralPath $ShortcutDir -Filter '*campaign*.lnk' -File -ErrorAction Ignore |
    Where-Object { $_.Name -notmatch '\.\d+\.tmp\.lnk$' -and (Test-Owned $_) }
}

# This project's badges: those under its key, and those its own links show (an old mark's, under the old key).
# Named apart from the -Icon parameter: PowerShell names ignore case, and $icon would be that typed string.
function Get-Badges([object[]]$owned) {
  $found = @{}
  foreach ($badge in @(Get-ChildItem -LiteralPath $IconDir -Filter "campaign-*-$key.ico" -File -ErrorAction Ignore)) {
    $found[$badge.Name] = $badge
  }
  foreach ($link in $owned) {
    $where = (Get-Link $link).IconPath
    $shown = if ($where) { Get-Item -LiteralPath $where -ErrorAction Ignore }
    if ($shown -and $shown.Name -like 'campaign-*.ico' -and
        [IO.Path]::GetFileName($shown.DirectoryName) -eq [IO.Path]::GetFileName($IconDir.TrimEnd('\'))) {
      $found[$shown.Name] = $shown
    }
  }
  $found.Values
}

# The links and badges are derived files: running the script again writes every one of them. So a run stopped part way
# (its window closed, the machine lost power) is put right by the next run that writes, or by -Remove: each first
# removes this project's leftovers, its own files moved aside (`<name>.<pid>.old`) or written under a temporary name
# (`<name>.<pid>.tmp.<ext>`) by a run no longer running, and then writes or removes the whole set. Nothing is put back
# from a guess, so nothing removed can come back; a run that refuses touches nothing.
function Remove-Leftovers {
  foreach ($folder in @($ShortcutDir, $IconDir)) {
    $left = @(Get-ChildItem -LiteralPath $folder -File -ErrorAction Ignore |
      Where-Object { $_.Name -match '\.(\d+)\.(old|tmp\.lnk|tmp\.ico)$' })
    foreach ($file in $left) {
      [void]($file.Name -match '\.(\d+)\.(old|tmp\.lnk|tmp\.ico)$')
      $owner = [int]$Matches[1]
      if ($owner -eq $PID -or (Get-Process -Id $owner -ErrorAction Ignore)) { continue }
      # This project's: a badge under its key, a link with its mark. Another project's leftovers are its own.
      $mine = if ($file.Name -like 'campaign-*.ico.*') { $file.Name -like "campaign-*-$key.ico.*" }
        else { Test-Owned $file }
      if (-not $mine) { continue }
      try { Remove-Item -LiteralPath $file.FullName; "removed: $($file.FullName)" }
      catch { "unattended-shortcut: $($file.FullName) could not be removed ($_)" }
    }
  }
}

if ($Remove) {
  Remove-Leftovers
  $links = @(Get-Owned)
  $badges = @(Get-Badges $links)
  foreach ($link in $links) { Remove-Item -LiteralPath $link.FullName; "removed: $($link.FullName)" }
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

# Every link and its badge, by runner. A name held by a file this project did not write (another project's link with
# the same title and runner, or a folder) is refused before anything is written: a move would replace it.
$planned = foreach ($agent in $agents) {
  $label = "$title $($labels[$agent]) campaign"
  $badge = Join-Path $IconDir "campaign-$agent-$key.ico"
  $link = Join-Path $ShortcutDir "$label.lnk"
  [pscustomobject]@{ Agent = $agent; Label = $label; Badge = $badge; BadgeTemp = "$badge.$PID.tmp.ico"; Link = $link
    LinkTemp = Join-Path $ShortcutDir "$label.$PID.tmp.lnk" }
}
foreach ($p in $planned) {
  $held = Get-Item -LiteralPath $p.Link -Force -ErrorAction Ignore
  if ($held -and ($held.PSIsContainer -or -not (Test-Owned $held))) {
    Refuse "the shortcut name '$($p.Label).lnk' is held by a file this project did not write: '$($held.FullName)'"
  }
}
function Clear-Temps {
  foreach ($p in $planned) { Remove-Item -LiteralPath $p.BadgeTemp, $p.LinkTemp -ErrorAction Ignore }
}

# A link or badge of this project's that this run does not write (an earlier title, a runner dropped, an old mark's)
# goes in the same change. Compared by file name: each list is of one folder, whose spelling (an 8.3 short name) may
# differ.
$writtenLinks = @($planned | ForEach-Object { Split-Path $_.Link -Leaf })
$writtenIcons = @($planned | ForEach-Object { Split-Path $_.Badge -Leaf })
$owned = @(Get-Owned)
$stale = @($owned | Where-Object { $writtenLinks -notcontains $_.Name }) +
  @(Get-Badges $owned | Where-Object { $writtenIcons -notcontains $_.Name })
$moves = foreach ($p in $planned) {
  [pscustomobject]@{ from = $p.BadgeTemp; to = $p.Badge }
  [pscustomobject]@{ from = $p.LinkTemp; to = $p.Link }
}
function Stop-Run([string]$why) {
  Clear-Temps
  "unattended-shortcut: $why"
  exit 1
}

# Two steps: every badge and link is written under its temporary name first, and only then moved over the old, so a
# failure before the moves leaves every previous link and badge as it was and no temporary file.
New-Item -ItemType Directory -Force -Path $IconDir, $ShortcutDir | Out-Null
Remove-Leftovers
foreach ($p in $planned) {
  & $Python -B $renderer badge $brand $p.Agent $p.BadgeTemp
  if ($LASTEXITCODE -ne 0) { Stop-Run "the icon for $($p.Label) could not be rendered; its shortcut is left as it was" }
  $command = "python3 scripts/unattended-run.py start --agent $($p.Agent) || " +
    "{ echo 'The run did not start: the reason is above. Press Enter to close.'; read -r _; }"
  try {
    # PowerShell runs wsl.exe, so a failure of WSL itself (a drive gone, a distro removed) is said and waits for Enter
    # too; the command is in the link, not in a script on the project's drive, which may be the one that is gone.
    $words = @('-d', $Distro, '--cd', $linux, '--exec', 'bash', '-lc', $command)
    $code = "& $(PSQuote $Wsl) $(($words | ForEach-Object { PSQuote $_ }) -join ' '); if (`$LASTEXITCODE -ne 0) { " +
      "Write-Host ('WSL could not start the run (exit ' + `$LASTEXITCODE + '): the reason is above. ' + " +
      "'Press Enter to close.'); " +
      "[void][Console]::ReadLine() }"
    $data = [Conclave.ShellLinkData]::new()
    $data.Target = $pwsh
    $data.Arguments = "-NoLogo -NoProfile -Command $(Quote $code)"
    $data.WorkingDirectory = $env:USERPROFILE
    $data.Description = $mark
    $data.IconPath = $p.Badge
    [Conclave.ShellLink]::Write($p.LinkTemp, $data)
  } catch {
    Stop-Run "the shortcut $($p.Label) could not be saved ($($_.Exception.Message)); the old one is kept"
  }
}

# The new set goes in as one change: every link and badge it replaces or retires is moved aside first, each link moved
# aside is checked again (now that no other writer can change it, so one another installer put there after the check
# above is never taken), then each new file is moved in (never over a file), and on any failure each file moved in is
# taken out and each file moved aside is put back. A run stopped part way is put right by the next (Remove-Leftovers).
$asidePlan = @(@($moves | Where-Object { Test-Path -LiteralPath $_.to } | ForEach-Object { $_.to }) +
  @($stale | ForEach-Object { $_.FullName }) | ForEach-Object { [pscustomobject]@{ to = $_; old = "$_.$PID.old" } })
$aside = [Collections.Generic.List[object]]::new()
$placed = [Collections.Generic.List[string]]::new()
try {
  foreach ($old in $asidePlan) { Move-Item -LiteralPath $old.to -Destination $old.old; $aside.Add($old) }
  foreach ($old in $aside) {
    if ($old.to.EndsWith('.lnk') -and -not (Test-Owned (Get-Item -LiteralPath $old.old))) {
      throw "$($old.to) was written by another project while this run was working"
    }
  }
  foreach ($m in $moves) { Move-Item -LiteralPath $m.from -Destination $m.to; $placed.Add($m.to) }
} catch {
  $why = $_.Exception.Message
  $whole = $true
  foreach ($to in $placed) { try { Remove-Item -LiteralPath $to -ErrorAction Stop } catch { $whole = $false } }
  foreach ($old in $aside) {
    try { Move-Item -LiteralPath $old.old -Destination $old.to -ErrorAction Stop } catch { $whole = $false }
  }
  if ($whole) { Stop-Run "the shortcuts could not be put in place ($why); the previous ones are kept" }
  $left = @($aside | Where-Object { Test-Path -LiteralPath $_.old } | ForEach-Object { $_.to })
  Stop-Run ("the shortcuts could not be put in place ($why), and $($left -join ', ') could not be put back (another " +
    'file holds the name); free the name and run the script again, which writes the whole set')
}
foreach ($p in $planned) { "shortcut written: $($p.Link)" }
foreach ($file in $stale) { "removed: $($file.FullName)" }
# A file moved aside that cannot be deleted now is a leftover the next run removes.
foreach ($old in $aside) { Remove-Item -LiteralPath $old.old -ErrorAction Ignore }
exit 0
