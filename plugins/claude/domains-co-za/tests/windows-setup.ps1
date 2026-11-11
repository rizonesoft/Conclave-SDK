$ErrorActionPreference='Stop'
$old=$env:LOCALAPPDATA
$testRoot=Join-Path ([IO.Path]::GetTempPath()) ('domains-credential-test-'+[Guid]::NewGuid())
$script=Join-Path $PSScriptRoot '../scripts/configure.ps1'
function Assert($value,$message){if(-not $value){throw $message}}
try {
 $env:LOCALAPPDATA=$testRoot
 Assert (-not ((& $script -Status | ConvertFrom-Json).configurationPresent)) 'Fresh setup is not empty'
 $first=ConvertTo-SecureString '{"mode":"login","username":"synthetic","password":"synthetic-password"}' -AsPlainText -Force
 & $script -Credential $first
 $folder=Join-Path $testRoot 'Rizonetech/Claude/DomainsCoZa'
 $cipher=Join-Path $folder 'token.dpapi';$config=Join-Path $folder 'config.json'
 Assert ((Get-Content $cipher -Raw) -notmatch 'synthetic-password') 'Plaintext credential found'
 Assert ((Get-Acl $folder).AreAccessRulesProtected) 'Unprotected ACL'
 $saved=Get-Content $cipher -Raw | ConvertTo-SecureString
 $ptr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($saved)
 try{Assert (([Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) | ConvertFrom-Json).password -eq 'synthetic-password') 'DPAPI round-trip failed'}finally{[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr);$saved.Dispose()}
 $data=Get-Content $config -Raw | ConvertFrom-Json;$data | Add-Member -NotePropertyName unrelated -NotePropertyValue 'keep';$data | ConvertTo-Json | Set-Content $config
 $second=ConvertTo-SecureString '{"mode":"bearer","token":"synthetic-token"}' -AsPlainText -Force
 & $script -Credential $second
 Assert ((Get-Content $config -Raw | ConvertFrom-Json).unrelated -eq 'keep') 'Unrelated configuration lost'
 $hash=(Get-FileHash $cipher).Hash
 $bad=ConvertTo-SecureString '{"mode":"login","username":"synthetic","password":""}' -AsPlainText -Force
 $rejected=$false;try{& $script -Credential $bad}catch{$rejected=$true}
 Assert $rejected 'Empty password accepted';Assert ((Get-FileHash $cipher).Hash -eq $hash) 'Invalid update overwrote credential'
 $env:DOMAINS_TEST_IMPORT='1'
 node --input-type=module -e "import {loadCredentials} from './src/credentials.js'; const c=await loadCredentials(); if(c.mode!=='bearer'||c.token!=='synthetic-token')throw Error('Runtime roundtrip failed'); console.log('Runtime DPAPI check passed, no 1Password subprocess.');"
 if($LASTEXITCODE -ne 0){throw 'Runtime credential check failed'}
 Write-Output 'Windows setup checks passed: encryption, ACL, rotation, invalid update rejection, configuration preservation and runtime decryption.'
} finally {
 $env:LOCALAPPDATA=$old;Remove-Item Env:DOMAINS_TEST_IMPORT -ErrorAction SilentlyContinue
 foreach($s in @($first,$second,$bad)){if($s){$s.Dispose()}}
 $resolved=[IO.Path]::GetFullPath($testRoot);$temp=[IO.Path]::GetFullPath([IO.Path]::GetTempPath())
 if($resolved.StartsWith($temp,[StringComparison]::OrdinalIgnoreCase) -and [IO.Path]::GetFileName($resolved).StartsWith('domains-credential-test-') -and (Test-Path -LiteralPath $resolved)){Remove-Item -LiteralPath $resolved -Recurse -Force}
}
