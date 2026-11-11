# Runs in the signed-in Windows user's context; never reads 1Password.
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$exe=Join-Path $root '.local\tunnel-client\v0.0.15\tunnel-client.exe'
# Packaged Codex redirects LocalAppData writes. Resolve that physical directory
# when running outside Codex (Task Scheduler), without copying any secrets.
$packagedLocal=Join-Path $env:LOCALAPPDATA 'Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Local'
if(-not (Test-Path (Join-Path $env:LOCALAPPDATA 'Rizonetech\CloudAccess\token.dpapi')) -and (Test-Path (Join-Path $packagedLocal 'Rizonetech\CloudAccess\token.dpapi'))){$env:LOCALAPPDATA=$packagedLocal}
$store=Join-Path $env:LOCALAPPDATA 'Rizonetech\CloudAccess'
$mutex=[Threading.Mutex]::new($false,'Local\RizonetechPluginCloudAccess')
if(-not $mutex.WaitOne(0)){exit}
function Invoke-Tunnel([string[]]$Arguments) {
  $info=[Diagnostics.ProcessStartInfo]::new($exe)
  $info.UseShellExecute=$false
  $info.CreateNoWindow=$true
  $info.RedirectStandardOutput=$true
  $info.RedirectStandardError=$true
  foreach($arg in $Arguments){$info.ArgumentList.Add($arg)}
  $p=[Diagnostics.Process]::Start($info)
  $output=$p.StandardOutput.ReadToEndAsync()
  $errorOutput=$p.StandardError.ReadToEndAsync()
  if(-not $p.WaitForExit(25000)){$p.Kill();throw 'Tunnel management timed out'}
  if($p.ExitCode -ne 0){throw 'Tunnel management failed'}
  $output.GetAwaiter().GetResult() | ConvertFrom-Json
}
$targets=@(
 @{alias='rizonetech-atera';id='tunnel_6ac348969d708191a2cb339de0c14070';plugin='atera'},
 @{alias='rizonetech-domains-co-za';id='tunnel_6ac349a7309881918622712dca192ebc';plugin='domains-co-za'}
)
try {
 while($true){
  $states=@()
  foreach($target in $targets){
   try {
    $state=Invoke-Tunnel @('runtimes','status',$target.alias,'--json')
    if(-not $state.process_running){
     $bytes=[Security.Cryptography.ProtectedData]::Unprotect([IO.File]::ReadAllBytes((Join-Path $store 'token.dpapi')),$null,[Security.Cryptography.DataProtectionScope]::CurrentUser)
     try{
      $env:CONTROL_PLANE_API_KEY=[Text.Encoding]::UTF8.GetString($bytes)
      $env:LOG_LEVEL='warn'
      $env:CONTROL_PLANE_MAX_INFLIGHT_REQUESTS='1'
      $command='node '+(($root+'\'+$target.plugin+'\dist\server.mjs') -replace '\\','/')
      $state=Invoke-Tunnel @('runtimes','connect','--alias',$target.alias,'--tunnel-id',$target.id,'--profile',$target.alias,'--profile-dir',(Join-Path $store 'profiles'),'--runtime-api-key','env:CONTROL_PLANE_API_KEY','--mcp-command',$command,'--json')
     }finally{
      Remove-Item Env:\CONTROL_PLANE_API_KEY -ErrorAction SilentlyContinue
      [Array]::Clear($bytes,0,$bytes.Length)
     }
    }
    $states+=@{plugin=$target.plugin;running=[bool]$state.process_running;healthy=[bool]$state.healthy;ready=[bool]$state.ready;checkedAt=[DateTime]::UtcNow.ToString('o')}
   }catch{
    $states+=@{plugin=$target.plugin;ready=$false;status='unavailable';checkedAt=[DateTime]::UtcNow.ToString('o')}
   }
  }
  $states | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $store 'status.json') -Encoding utf8
  Start-Sleep -Seconds 30
 }
}finally{$mutex.ReleaseMutex();$mutex.Dispose()}
