param(
 [ValidateSet('Status','Configure','Install','Start','Stop','Run')][string]$Action='Status',
 [ValidatePattern('^tunnel_[a-f0-9]{32}$')][string]$TunnelId
)
$ErrorActionPreference='Stop'
$pluginRoot=Split-Path $PSScriptRoot -Parent
$repoRoot=Split-Path $pluginRoot -Parent
$exe=Join-Path $repoRoot '.local\tunnel-client\v0.0.15\tunnel-client.exe'
$store=Join-Path $env:LOCALAPPDATA 'Rizonetech\Conclave'
$packagedStore=Join-Path $env:LOCALAPPDATA 'Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Local\Rizonetech\Conclave'
if(-not(Test-Path -LiteralPath (Join-Path $store 'cloud.json')) -and (Test-Path -LiteralPath (Join-Path $packagedStore 'cloud.json'))){$store=$packagedStore}
$configPath=Join-Path $store 'cloud.json'
$taskName='Rizonetech Conclave Cloud Access'
$aliasName='rizonetech-conclave'
$script:config=$null

function Get-TunnelCredentialPath {
 $candidates=@(
  (Join-Path $env:LOCALAPPDATA 'Rizonetech\CloudAccess\token.dpapi'),
  (Join-Path $env:LOCALAPPDATA 'Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Local\Rizonetech\CloudAccess\token.dpapi')
 )
 foreach($candidate in $candidates){if(Test-Path -LiteralPath $candidate){return $candidate}}
 throw 'The existing Windows-encrypted tunnel credential is missing. Re-import it from the Conclave vault during explicit setup.'
}
function Read-CloudConfig {
 if(-not(Test-Path -LiteralPath $configPath)){return $null}
 $value=Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
 if($value.schemaVersion -ne 1 -or $value.tunnelId -notmatch '^tunnel_[a-f0-9]{32}$'){throw 'Invalid non-secret cloud configuration.'}
 return $value
}
function Invoke-Tunnel([string[]]$Arguments, [switch]$WithCredential) {
 if(-not(Test-Path -LiteralPath $exe)){throw 'The approved tunnel-client installation is missing.'}
 $info=[Diagnostics.ProcessStartInfo]::new($exe)
 $info.UseShellExecute=$false
 $info.CreateNoWindow=$true
 $info.RedirectStandardOutput=$true
 $info.RedirectStandardError=$true
 $info.WorkingDirectory=$pluginRoot
 $info.Environment['LOG_LEVEL']='warn'
 $info.Environment['CONTROL_PLANE_MAX_INFLIGHT_REQUESTS']='1'
 $bytes=$null
 $proc=$null
 try {
  if($WithCredential){
   $credentialPath=Get-TunnelCredentialPath
   $bytes=[Security.Cryptography.ProtectedData]::Unprotect([IO.File]::ReadAllBytes($credentialPath),$null,[Security.Cryptography.DataProtectionScope]::CurrentUser)
   $info.Environment['CONTROL_PLANE_API_KEY']=[Text.Encoding]::UTF8.GetString($bytes)
  }
  foreach($argument in $Arguments){$info.ArgumentList.Add($argument)}
  $proc=[Diagnostics.Process]::Start($info)
  $output=$proc.StandardOutput.ReadToEndAsync()
  $errors=$proc.StandardError.ReadToEndAsync()
  if(-not $proc.WaitForExit(45000)){$proc.Kill();throw 'Tunnel management timed out.'}
  if($proc.ExitCode -ne 0){throw 'Tunnel management failed. Check tunnel permissions, the encrypted credential and local Conclave health.'}
  return ($output.GetAwaiter().GetResult() | ConvertFrom-Json)
 } finally {
  $info.Environment.Remove('CONTROL_PLANE_API_KEY') | Out-Null
  if($bytes){[Array]::Clear($bytes,0,$bytes.Length)}
  if($proc){$proc.Dispose()}
 }
}
function Get-PublicStatus {
 $task=Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
 $result=[ordered]@{configured=($null -ne $script:config);tunnelId=$script:config.tunnelId;alias=$aliasName;taskState=[string]$task.State;running=$false;healthy=$false;ready=$false;checkedAt=[DateTime]::UtcNow.ToString('o')}
 try {
  $runtime=Invoke-Tunnel @('runtimes','status',$aliasName,'--json')
  $result.running=[bool]$runtime.process_running
  $result.healthy=[bool]$runtime.healthy
  $result.ready=[bool]$runtime.ready
 } catch { $result.state='unavailable' }
 return $result
}
function Connect-Conclave {
 if(-not $script:config){throw 'Configure the dedicated Conclave tunnel ID first.'}
 $runtime=$null
 try{$runtime=Invoke-Tunnel @('runtimes','status',$aliasName,'--json')}catch{}
 if(-not $runtime.process_running) {
  $nodePath=(Get-Command node -ErrorAction Stop).Source.Replace('\','/')
  $launchPath=(Join-Path $pluginRoot 'src\launch.mjs').Replace('\','/')
  # Paths are quoted for the tunnel client's stdio command parser, never a shell.
  $command='"'+$nodePath+'" "'+$launchPath+'"'
  Invoke-Tunnel @('runtimes','connect','--alias',$aliasName,'--tunnel-id',$script:config.tunnelId,'--profile',$aliasName,'--profile-dir',(Join-Path $store 'cloud-profiles'),'--runtime-api-key','env:CONTROL_PLANE_API_KEY','--mcp-command',$command,'--json') -WithCredential | Out-Null
 }
}
try {
 $script:config=Read-CloudConfig
 switch($Action) {
  'Status' { Get-PublicStatus | ConvertTo-Json }
  'Configure' {
   if(-not $TunnelId){throw 'Configure requires -TunnelId.'}
   if($script:config -and $script:config.tunnelId -ne $TunnelId){
    $status=Get-PublicStatus
    if($status.running -or $status.taskState -eq 'Running'){throw 'Stop the Conclave cloud runner before changing its tunnel ID.'}
   }
   New-Item -ItemType Directory -Force -Path $store | Out-Null
   $script:config=[pscustomobject]@{schemaVersion=1;tunnelId=$TunnelId;account='derick@rizonetech.com';runtime='Windows-to-WSL';alias=$aliasName}
   [IO.File]::WriteAllText($configPath,($script:config | ConvertTo-Json)+"`n",[Text.UTF8Encoding]::new($false))
   Get-PublicStatus | ConvertTo-Json
  }
  'Install' {
   if(-not $script:config){throw 'Configure the dedicated Conclave tunnel ID first.'}
   Get-TunnelCredentialPath | Out-Null
   if(-not(Test-Path -LiteralPath $exe)){throw 'The approved tunnel-client installation is missing.'}
   $pwsh=(Get-Command pwsh -ErrorAction Stop).Source
   $pythonw=(Get-Command pythonw -ErrorAction Stop).Source
   $launcher=Join-Path $PSScriptRoot 'run-hidden.py'
   $sid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value
   # Started directly, pwsh gets a console that Windows Terminal shows, even with -WindowStyle Hidden.
   $taskAction=New-ScheduledTaskAction -Execute $pythonw -Argument ('"'+$launcher+'" "'+$pwsh+'" -NoProfile -NonInteractive -File "'+$PSCommandPath+'" -Action Run') -WorkingDirectory $pluginRoot
   $trigger=New-ScheduledTaskTrigger -AtLogOn -User $sid
   $principal=New-ScheduledTaskPrincipal -UserId $sid -LogonType Interactive -RunLevel Limited
   $settings=New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
   Register-ScheduledTask -TaskName $taskName -Action $taskAction -Trigger $trigger -Principal $principal -Settings $settings -Description 'Private Conclave MCP access through the dedicated OpenAI tunnel. Uses Windows DPAPI; no runtime 1Password reads.' -Force | Out-Null
   Get-PublicStatus | ConvertTo-Json
  }
  'Start' {
   if(-not $script:config){throw 'Configure the dedicated Conclave tunnel ID first.'}
   Enable-ScheduledTask -TaskName $taskName | Out-Null
   Start-ScheduledTask -TaskName $taskName
   Get-PublicStatus | ConvertTo-Json
  }
  'Stop' {
   $task=Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
   if($task){Disable-ScheduledTask -TaskName $taskName | Out-Null; Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue}
   try{Invoke-Tunnel @('runtimes','stop',$aliasName,'--json') | Out-Null}catch{if((Get-PublicStatus).running){throw}}
   Get-PublicStatus | ConvertTo-Json
  }
  'Run' {
   if(-not $script:config){throw 'Configure the dedicated Conclave tunnel ID first.'}
   $mutex=[Threading.Mutex]::new($false,'Local\RizonetechConclaveCloudAccess')
   if(-not $mutex.WaitOne(0)){$mutex.Dispose();exit}
   try {
    while($true) {
     try {
      Connect-Conclave
      $status=Get-PublicStatus
     } catch {
      $status=@{ready=$false;state='unavailable';checkedAt=[DateTime]::UtcNow.ToString('o')}
     }
     [IO.File]::WriteAllText((Join-Path $store 'cloud-status.json'),($status | ConvertTo-Json)+"`n",[Text.UTF8Encoding]::new($false))
     Start-Sleep -Seconds 30
    }
   }finally{$mutex.ReleaseMutex();$mutex.Dispose()}
  }
 }
}catch{
 # Never emit raw provider/control-plane errors or credentials.
 [Console]::Error.WriteLine('Conclave cloud action failed: '+$_.Exception.Message)
 exit 1
}
