#Requires -Version 7.0
<#
.SYNOPSIS
  Registers this project's automations in Windows Task Scheduler, under the folder tasks.json names.
.DESCRIPTION
  Reads every task from tasks.json (the one list; nothing here names a task) and registers it to run
  `pythonw.exe .conclave\automations\run.py <name>` from this repository, as the signed-in user, only while
  that user is logged on (no stored password). Idempotent: re-run it after editing tasks.json. A task in the
  project's folder that tasks.json no longer lists is unregistered. On Linux and WSL, install.sh is the
  systemd equivalent.

  Settings on every task: start when available (a run missed while the PC was off fires at the next chance,
  as systemd's Persistent=true does), ignore a new start while one runs, an execution limit five minutes past
  the task's timeout, and run on battery. Weekly tasks carry a five-minute random delay.
.EXAMPLE
  pwsh .conclave/automations/install.ps1
  pwsh .conclave/automations/install.ps1 -Uninstall
#>
[CmdletBinding()]
param([switch]$Uninstall)
$ErrorActionPreference = 'Stop'

$here = $PSScriptRoot
$repo = (Resolve-Path (Join-Path $here '..\..')).Path
$pythonw = (Get-Command pythonw.exe -ErrorAction Ignore).Source  # absent is the throw below
if (-not $pythonw) { throw 'pythonw.exe is not on PATH; install Python 3 for Windows first' }
$runner = Join-Path $here 'run.py'

# run.py's own loader checks tasks.json, so nothing is registered that the runner would refuse.
# An uninstall checks the manifest's shape only: a schedule a newer rule refuses (a run launcher) must still go.
$checkArgs = @('--check')
if ($Uninstall) { $checkArgs += '--removal' }
$folder = & (Join-Path (Split-Path $pythonw) 'python.exe') $runner @checkArgs
if ($LASTEXITCODE -ne 0) { throw 'tasks.json was refused (above); nothing was registered' }
$manifest = Get-Content -Raw -Path (Join-Path $here 'tasks.json') | ConvertFrom-Json
$existing = @(Get-ScheduledTask | Where-Object TaskPath -eq $folder)

function Test-OwnedByManifest($schedTask) {
  if (-not $schedTask -or -not $schedTask.Actions -or $schedTask.Actions.Count -ne 1) { return $false }
  $act = $schedTask.Actions[0]
  return ([string]$act.Arguments).IndexOf($runner, [StringComparison]::OrdinalIgnoreCase) -ge 0 -and
         ([string]$act.WorkingDirectory).TrimEnd('\') -ieq $repo.TrimEnd('\')
}

if ($Uninstall) {
  $removed = 0
  foreach ($task in $existing) {
    if (Test-OwnedByManifest $task) {
      Unregister-ScheduledTask -TaskPath $folder -TaskName $task.TaskName -Confirm:$false
      $removed++
    }
  }
  Write-Host "Removed $removed task(s) from $folder"
  return
}

$existingByName = @{}
foreach ($e in $existing) { $existingByName[$e.TaskName] = $e }
foreach ($task in $manifest.tasks) {
  if ($existingByName.ContainsKey($task.name) -and (-not (Test-OwnedByManifest $existingByName[$task.name]))) {
    throw "Refusing to replace task '$($task.name)' in $folder that this repository's automations did not create"
  }
}

$user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited

foreach ($task in $manifest.tasks) {
  $action = New-ScheduledTaskAction -Execute $pythonw -Argument "`"$runner`" $($task.name)" -WorkingDirectory $repo
  $trigger = $task.trigger
  if ($null -ne $trigger.PSObject.Properties['every_minutes'] -and $null -ne $trigger.every_minutes) {
    # Two triggers: after each logon (with the delay), and on the interval from now on. A logon trigger's
    # repetition starts only at the next logon, so on its own it would never tick in the current one.
    $every = New-TimeSpan -Minutes $trigger.every_minutes
    $logon = New-ScheduledTaskTrigger -AtLogOn -User $user
    $logon.Delay = "PT$($trigger.at_logon_delay_minutes)M"
    $logon.Repetition = (New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval $every).Repetition
    $t = @($logon, (New-ScheduledTaskTrigger -Once -At (Get-Date).Add($every) -RepetitionInterval $every))
  } elseif ($null -ne $trigger.PSObject.Properties['daily'] -and $trigger.daily -eq $true) {
    $delayMin = if ($null -ne $trigger.PSObject.Properties['random_delay_minutes']) { [int]$trigger.random_delay_minutes } else { 0 }
    if ($delayMin -gt 0) {
      $t = New-ScheduledTaskTrigger -Daily -At $trigger.at -RandomDelay (New-TimeSpan -Minutes $delayMin)
    } else {
      $t = New-ScheduledTaskTrigger -Daily -At $trigger.at
    }
  } else {
    $t = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $trigger.weekly -At $trigger.at -RandomDelay (New-TimeSpan -Minutes 5)
  }
  $exactTimeout = ($null -ne $task.PSObject.Properties['exact_timeout'] -and $task.exact_timeout -eq $true)
  $limitMinutes = if ($exactTimeout) { [int]$task.timeout_minutes } else { [int]$task.timeout_minutes + 5 }
  $startWhenAvail = if ($null -ne $task.PSObject.Properties['start_when_available']) { [bool]$task.start_when_available } else { $true }
  $wakeToRun = if ($null -ne $task.PSObject.Properties['wake_to_run']) { [bool]$task.wake_to_run } else { $false }
  $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew `
      -ExecutionTimeLimit (New-TimeSpan -Minutes $limitMinutes) `
      -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
  $settings.StartWhenAvailable = $startWhenAvail
  $settings.WakeToRun = $wakeToRun
  Register-ScheduledTask -TaskPath $folder -TaskName $task.name -Description $task.description `
      -Action $action -Trigger $t -Settings $settings -Principal $principal -Force | Out-Null
}

$listed = @($manifest.tasks | ForEach-Object { $_.name })
foreach ($task in $existing) {
  if ($listed -notcontains $task.TaskName -and (Test-OwnedByManifest $task)) {
    Unregister-ScheduledTask -TaskPath $folder -TaskName $task.TaskName -Confirm:$false
    Write-Host "Removed $($task.TaskName): tasks.json no longer lists it"
  }
}
Get-ScheduledTask -TaskPath $folder | Get-ScheduledTaskInfo |
    Select-Object TaskName, NextRunTime, LastRunTime, LastTaskResult | Format-Table -AutoSize
