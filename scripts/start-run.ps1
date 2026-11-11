# Starts the SDK's own unattended run: an interactive Claude Code session in this checkout, on the latest Opus, with
# every permission prompt off and its goal set.
#
#   pwsh scripts/start-run.ps1                    start the run in this window
#   pwsh scripts/start-run.ps1 -InstallShortcut   put "Conclave-SDK unattended run" on the desktop, which runs the line above
#   pwsh scripts/start-run.ps1 -DryRun            print what would run, and change nothing
#   pwsh scripts/start-run.ps1 -Model sonnet      start on another model
#
# The goal is a Claude Code /goal, which is checked after every turn: the plan finished through the process-plan
# skill. That skill starts the run guard itself (scripts/campaign_guard.py and a heartbeat inside the session), so this
# file starts no guard. Starting it is the operator's word to resume: when a guard from an earlier session is still
# held, it says so and waits for Enter, and the new session takes the run over.
#
# The model is the alias `opus`, which Claude Code resolves to the newest Opus, so the shortcut never needs editing
# when a new one ships.
#
# The session signs in with the long-lived token (`claude setup-token`, valid one year) kept in the user variable
# CLAUDE_CODE_OAUTH_TOKEN. A window opened before the token was stored does not have it yet, so it is read from the
# user's own variables here. When none is stored, the session uses the claude.ai sign-in and the start goes ahead.
# The token is never printed, and this file never creates or changes one.
#
# This file belongs to the SDK alone: it is not part of a kit and is never installed in a project.
param(
  [switch]$InstallShortcut,
  [switch]$DryRun,
  [string]$ShortcutDir = [Environment]::GetFolderPath('Desktop'),
  [string]$Model = 'opus',
  [string]$UserEnvKey = 'HKCU:\Environment',
  [string]$Goal = ''
)
$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot
$tokenName = 'CLAUDE_CODE_OAUTH_TOKEN'
$shortcutName = 'Conclave-SDK unattended run.lnk'

if (-not $Goal) {
  # One line with no double quote: it is passed to claude as a single argument. Claude Code allows 4,000 characters.
  $Goal = (@'
Finish the Conclave-SDK implementation plan (todo/implementation-plan.md) 100% complete and aim for excellence: the best set of agent kits of its kind for Claude Code, Codex and Antigravity, better than what any large vendor would ship. Act autonomously under AGENTS.md: decide and act instead of asking, fix what breaks at its owning layer, and improve the repo, its tools and its methods whenever they slow the work or let a defect through. Work it with the process-plan skill, as the prompt `process plan` does, without stopping between sections or phases. Never ask the operator a question: take the industry-standard option and record the decision, and what reversing it would cost, in the run file. This launch is the operator's word to resume: when a guard from an earlier session is still held, take the run over with `acquire --handover resumed-from-launcher`. The goal is met only when `python scripts/todo-graph.py query stats` shows verified equal to total, or every row still open is in phase 99 or waits on a Need this session cannot meet and the run file carries its PARKED line and park record.
'@).Trim()
}
if ($Goal.Contains('"') -or $Goal.Contains("`n")) { 'the goal must be one line with no double quote'; exit 1 }
if ($Goal.Length -gt 4000) { "the goal is $($Goal.Length) characters; Claude Code allows 4,000"; exit 1 }

if ($InstallShortcut) {
  $pwsh = (Get-Process -Id $PID).Path
  $link = Join-Path $ShortcutDir $shortcutName
  $shortcut = (New-Object -ComObject WScript.Shell).CreateShortcut($link)
  $shortcut.TargetPath = $pwsh
  $shortcut.Arguments = "-NoExit -NoProfile -File `"$PSCommandPath`""
  $shortcut.WorkingDirectory = $repo
  $shortcut.Description = 'Start the unattended Conclave-SDK run in Claude Code'
  $icon = Join-Path $repo 'assets\brand\conclave-sdk.ico'
  if (Test-Path -LiteralPath $icon) { $shortcut.IconLocation = "$icon,0" }
  $shortcut.Save()
  "shortcut written: $link"
  exit 0
}

$session = [guid]::NewGuid().ToString()
$arguments = @('--session-id', $session, '--dangerously-skip-permissions', '--model', $Model, "/goal $Goal")
if ($DryRun) {
  "in $repo"
  "claude $($arguments[0..4] -join ' ') `"$($arguments[5])`""
  exit 0
}

# Looked up, not assumed: a missing tool is named with its fix instead of failing as a bare "not recognized".
$python = (Get-Command python -CommandType Application -ErrorAction Ignore | Select-Object -First 1).Source
$claude = (Get-Command claude -ErrorAction Ignore | Select-Object -First 1).Source
if (-not $python) { 'python is not on PATH: install Python 3, then start again'; exit 1 }
if (-not $claude) { 'claude is not on PATH: install Claude Code, then start again'; exit 1 }

# The sign-in. Each line says where it came from, never the token itself.
if ([Environment]::GetEnvironmentVariable($tokenName)) {
  'sign-in: the long-lived token this window already has'
} else {
  $token = if (Test-Path -LiteralPath $UserEnvKey) { (Get-Item -LiteralPath $UserEnvKey).GetValue($tokenName, $null) }
  if ($token) {
    [Environment]::SetEnvironmentVariable($tokenName, $token)
    $token = $null
    'sign-in: the long-lived token from your user variables'
  } else {
    'sign-in: no long-lived token is stored, so the session uses the claude.ai sign-in'
    "          to store one: run ``claude setup-token`` and keep its output as the user variable $tokenName"
  }
}

Set-Location -LiteralPath $repo
# Two sessions must never write to one tree. A guard file means an earlier session held the run: it may be dead, or
# still working in another window, and only the operator knows which.
$guard = Join-Path $repo 'build\claude-campaign-guard.json'
if (Test-Path -LiteralPath $guard) {
  $held = try { (Get-Content -LiteralPath $guard -Raw | ConvertFrom-Json).session } catch { 'an unreadable guard file' }
  "a run guard is held by session $held"
  'If that session is still working in another window, close this one now.'
  [void](Read-Host 'Press Enter to start a new session that takes the run over')
}
& $claude @arguments
