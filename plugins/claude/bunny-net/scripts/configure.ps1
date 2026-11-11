[CmdletBinding(DefaultParameterSetName='Prompt')]
param(
 [Parameter(Mandatory=$true,ParameterSetName='Key')][Security.SecureString]$ApiKey,
 [Parameter(Mandatory=$true,ParameterSetName='Bundle')][Security.SecureString]$Credential,
 [Parameter(Mandatory=$true,ParameterSetName='Stdin')][switch]$CredentialFromStdin,
 [Parameter(Mandatory=$true,ParameterSetName='Import')][switch]$ImportFrom1Password,
 [Parameter(ParameterSetName='Import')][string]$Item='Bunny.net Account API',
 [Parameter(ParameterSetName='Stdin')][Parameter(ParameterSetName='Import')][string]$Reference,
 [Parameter(Mandatory=$true,ParameterSetName='Status')][switch]$Status
)
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'credential-store.ps1')
if($Status){Get-BunnyNetCredentialStatus | ConvertTo-Json; return}
function Reveal([Security.SecureString]$value){
 $p=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($value)
 try { [Runtime.InteropServices.Marshal]::PtrToStringBSTR($p) } finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($p) }
}
$secure=$null; $prompted=$false; $raw=$null; $key=$null
try {
 if($Credential){Save-BunnyNetCredential -Token $Credential; Write-Output 'Saved with Windows account encryption.'; return}
 if($CredentialFromStdin){
  # For scripted refresh from another shell (for example WSL piping a Conclave read): a JSON bundle on stdin, never an argument.
  $raw=[Console]::In.ReadToEnd()
  $secure=ConvertTo-SecureString $raw.Trim() -AsPlainText -Force
 } else {
  if($ImportFrom1Password){
   # Only explicit imports invoke op. Conclave is the required AI vault.
   $raw=& op item get $Item --vault Conclave --format json
   if($LASTEXITCODE -ne 0){throw '1Password import failed; existing Windows credentials are unchanged.'}
   $entry=($raw -join "`n") | ConvertFrom-Json
   $key=($entry.fields | Where-Object {$_.label -in @('credential','API key')} | Where-Object {$_.value} | Select-Object -First 1).value
   if(-not $key){throw 'Fill the credential field in the Conclave item first.'}
  } elseif($ApiKey){$key=Reveal $ApiKey}
  else {$ApiKey=Read-Host 'bunny.net account API key (hidden)' -AsSecureString;$prompted=$true;$key=Reveal $ApiKey}
  $secure=ConvertTo-SecureString (@{mode='apikey';apiKey=$key.Trim()} | ConvertTo-Json -Compress) -AsPlainText -Force
 }
 Save-BunnyNetCredential -Token $secure -TokenReference $Reference
 Write-Output 'Saved with Windows account encryption. Normal plugin use never calls 1Password. Credentials reload on each operation.'
} finally {if($secure){$secure.Dispose()};if($prompted -and $ApiKey){$ApiKey.Dispose()};$raw=$null;$entry=$null;$key=$null}
