# Run locally only. Neither passwords nor one-time codes are accepted as plaintext arguments.
[CmdletBinding()]
param([string]$Username,[Security.SecureString]$Password,[Security.SecureString]$Code)
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'credential-store.ps1')
function Reveal([Security.SecureString]$s){$p=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($s);try{[Runtime.InteropServices.Marshal]::PtrToStringBSTR($p)}finally{[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($p)}}
$owned=@();$secure=$null
try {
 if(-not $Username){$Username=Read-Host 'Domains.co.za username'}
 if(-not $Password){$Password=Read-Host 'Password (hidden)' -AsSecureString;$owned+=,$Password}
 if(-not $Code){$Code=Read-Host 'Current authenticator code (hidden)' -AsSecureString;$owned+=,$Code}
 $body=@{username=$Username;password=(Reveal $Password);code=(Reveal $Code)}
 try{$result=Invoke-RestMethod -Uri 'https://api.domains.co.za/api/login' -Method Post -Body $body -ContentType 'application/x-www-form-urlencoded' -MaximumRedirection 0 -TimeoutSec 30}catch{throw 'Login failed. Existing credentials are unchanged.'}
 if($result.intReturnCode -ne 1 -or [string]::IsNullOrWhiteSpace($result.token)){throw 'Login did not issue a token. Check credentials and the current authenticator code.'}
 $secure=ConvertTo-SecureString (@{mode='bearer';token=$result.token}|ConvertTo-Json -Compress) -AsPlainText -Force
 Save-DomainsCoZaCredential -Token $secure
 Write-Output 'JWT saved in Windows-encrypted storage. Repeat this setup when the provider token expires.'
}finally{if($secure){$secure.Dispose()};foreach($s in $owned){$s.Dispose()};$body=$null;$result=$null}
