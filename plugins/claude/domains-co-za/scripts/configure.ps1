[CmdletBinding(DefaultParameterSetName='Login')]
param(
 [Parameter(ParameterSetName='Login')][string]$Username,
 [Parameter(ParameterSetName='Login')][Security.SecureString]$Password,
 [Parameter(ParameterSetName='Login')][Security.SecureString]$TotpSecret,
 [Parameter(Mandatory=$true,ParameterSetName='Bearer')][Security.SecureString]$Token,
 [Parameter(Mandatory=$true,ParameterSetName='Bundle')][Security.SecureString]$Credential,
 [Parameter(Mandatory=$true,ParameterSetName='Import')][switch]$ImportFrom1Password,
 [Parameter(ParameterSetName='Import')][string]$Item='Domains.co.za Reseller API',
 [Parameter(Mandatory=$true,ParameterSetName='Status')][switch]$Status
)
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'credential-store.ps1')
if($Status){Get-DomainsCoZaCredentialStatus | ConvertTo-Json; return}
function Reveal([Security.SecureString]$value){
 $p=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($value)
 try { [Runtime.InteropServices.Marshal]::PtrToStringBSTR($p) } finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($p) }
}
$bundle=$null; $secure=$null; $prompted=$false; $raw=$null
try {
 if($Credential){Save-DomainsCoZaCredential -Token $Credential; return}
 if($ImportFrom1Password){
  # Only explicit imports invoke op. Conclave is the required AI vault.
  $raw=& op item get $Item --vault Conclave --format json
  if($LASTEXITCODE -ne 0){throw '1Password import failed; existing Windows credentials are unchanged.'}
  $entry=($raw -join "
") | ConvertFrom-Json
  $u=($entry.fields | Where-Object {$_.id -eq 'username'} | Select-Object -First 1).value
  $p=($entry.fields | Where-Object {$_.id -eq 'password'} | Select-Object -First 1).value
  $t=($entry.fields | Where-Object {$_.label -eq 'API token'} | Select-Object -First 1).value
  $otp=($entry.fields | Where-Object {$_.type -eq 'OTP' -or $_.label -eq 'Authenticator secret'} | Where-Object {$_.value} | Select-Object -First 1).value
  if($u -and $p){$bundle=@{mode='login';username=$u;password=$p};if($otp){$bundle.totpSecret=$otp}}
  elseif($t){$bundle=@{mode='bearer';token=$t}}
  else {throw 'Fill username and password, or API token, in the Conclave placeholder first.'}
 } elseif($Token){$bundle=@{mode='bearer';token=(Reveal $Token)}}
 else {
  if(-not $Username){$Username=Read-Host 'Domains.co.za API username'}
  if(-not $Password){$Password=Read-Host 'Domains.co.za API password (hidden)' -AsSecureString;$prompted=$true}
  $bundle=@{mode='login';username=$Username;password=(Reveal $Password)}
  if($TotpSecret){$bundle.totpSecret=Reveal $TotpSecret}
 }
 if($bundle.totpSecret){
  # Validate without putting secrets on the command line or exposing generated codes.
  $bundle.totpSecret | node (Join-Path $PSScriptRoot 'validate-totp.mjs')
  if($LASTEXITCODE -ne 0){throw 'Invalid authenticator setup secret. Existing credentials are unchanged.'}
 }
 $secure=ConvertTo-SecureString ($bundle | ConvertTo-Json -Compress) -AsPlainText -Force
 Save-DomainsCoZaCredential -Token $secure
 Write-Output 'Saved with Windows account encryption. Normal plugin use never calls 1Password. Credentials reload on each operation.'
} finally {if($secure){$secure.Dispose()};if($prompted -and $Password){$Password.Dispose()};$bundle=$null;$raw=$null;$entry=$null;$p=$null;$t=$null;$otp=$null}
