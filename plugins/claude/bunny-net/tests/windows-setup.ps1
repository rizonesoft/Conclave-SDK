$ErrorActionPreference='Stop'
$old=$env:LOCALAPPDATA
$testRoot=Join-Path ([IO.Path]::GetTempPath()) ('bunny-credential-test-'+[Guid]::NewGuid())
$script=Join-Path $PSScriptRoot '../scripts/configure.ps1'
function Assert($value,$message){if(-not $value){throw $message}}
try {
 $env:LOCALAPPDATA=$testRoot
 Assert (-not ((& $script -Status | ConvertFrom-Json).configurationPresent)) 'Fresh setup is not empty'
 $first=ConvertTo-SecureString 'synthetic-key-1111-2222-333333333333' -AsPlainText -Force
 & $script -ApiKey $first
 $folder=Join-Path $testRoot 'Rizonetech/Claude/BunnyNet'
 $cipher=Join-Path $folder 'token.dpapi';$config=Join-Path $folder 'config.json'
 Assert ((Get-Content $cipher -Raw) -notmatch 'synthetic-key') 'Plaintext credential found'
 Assert ((Get-Acl $folder).AreAccessRulesProtected) 'Unprotected ACL'
 $saved=Get-Content $cipher -Raw | ConvertTo-SecureString
 $ptr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($saved)
 try{Assert (([Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) | ConvertFrom-Json).apiKey -eq 'synthetic-key-1111-2222-333333333333') 'DPAPI round-trip failed'}finally{[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr);$saved.Dispose()}
 $data=Get-Content $config -Raw | ConvertFrom-Json;$data | Add-Member -NotePropertyName unrelated -NotePropertyValue 'keep';$data | ConvertTo-Json | Set-Content $config
 # Rotation through the stdin path used by WSL refreshes; stray fields are not stored.
 '{"mode":"apikey","apiKey":"synthetic-key-4444-5555-666666666666","extra":"drop-me"}' | & (Get-Process -Id $PID).Path -NoLogo -NoProfile -NonInteractive -File $script -CredentialFromStdin -Reference 'op://Conclave/synthetic'
 if($LASTEXITCODE -ne 0){throw 'Stdin rotation failed'}
 Assert ((Get-Content $config -Raw | ConvertFrom-Json).unrelated -eq 'keep') 'Unrelated configuration lost'
 Assert ((Get-Content $config -Raw | ConvertFrom-Json).tokenReference -eq 'op://Conclave/synthetic') 'Reference not recorded'
 $hash=(Get-FileHash $cipher).Hash
 foreach($badKey in @('','short','synthetic key with spaces 0000000000')){
  $bad=ConvertTo-SecureString ('{"mode":"apikey","apiKey":"'+$badKey+'"}') -AsPlainText -Force
  $rejected=$false;try{& $script -Credential $bad}catch{$rejected=$true}finally{$bad.Dispose()}
  Assert $rejected ('Invalid key accepted: '+$badKey.Length+' characters')
 }
 Assert ((Get-FileHash $cipher).Hash -eq $hash) 'Invalid update overwrote credential'
 $env:BUNNY_TEST_IMPORT='1'
 node --input-type=module -e "import {loadCredentials} from './src/credentials.js'; const c=await loadCredentials(); if(c.mode!=='apikey'||c.apiKey!=='synthetic-key-4444-5555-666666666666'||'extra' in c)throw Error('Runtime roundtrip failed'); console.log('Runtime DPAPI check passed, no 1Password subprocess.');"
 if($LASTEXITCODE -ne 0){throw 'Runtime credential check failed'}
 Write-Output 'Windows setup checks passed: encryption, ACL, rotation via stdin, invalid update rejection, configuration preservation and runtime decryption.'
} finally {
 $env:LOCALAPPDATA=$old;Remove-Item Env:BUNNY_TEST_IMPORT -ErrorAction SilentlyContinue
 foreach($s in @($first)){if($s){$s.Dispose()}}
 $resolved=[IO.Path]::GetFullPath($testRoot);$temp=[IO.Path]::GetFullPath([IO.Path]::GetTempPath())
 if($resolved.StartsWith($temp,[StringComparison]::OrdinalIgnoreCase) -and [IO.Path]::GetFileName($resolved).StartsWith('bunny-credential-test-') -and (Test-Path -LiteralPath $resolved)){Remove-Item -LiteralPath $resolved -Recurse -Force}
}
