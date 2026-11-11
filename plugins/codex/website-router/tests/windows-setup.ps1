$ErrorActionPreference='Stop'
$previous=$env:LOCALAPPDATA
$testRoot=Join-Path ([IO.Path]::GetTempPath()) ('website-router-test-'+[guid]::NewGuid())
$env:LOCALAPPDATA=$testRoot
$script=Join-Path $PSScriptRoot '../scripts/configure.ps1'
function Check($value,$message){if(!$value){throw $message}}
function Registry {
 $s=(Get-Content (Join-Path $testRoot 'Rizonetech/WebsiteRouter/token.dpapi') -Raw)|ConvertTo-SecureString
 $ptr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($s)
 try{[Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)|ConvertFrom-Json}finally{[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr);$s.Dispose()}
}
try{
 $fake=ConvertTo-SecureString 'synthetic-test-value' -AsPlainText -Force
 & $script -Id alpha -Name Alpha -SiteUrl https://alpha.example -Endpoint https://alpha.example/mcp -Environment staging -Username tester -Password $fake|Out-Null
 $configPath=Join-Path $testRoot 'Rizonetech/WebsiteRouter/config.json'
 $cfg=Get-Content $configPath -Raw|ConvertFrom-Json;$cfg|Add-Member -NotePropertyName preserveMe -NotePropertyValue 'yes';$cfg|ConvertTo-Json|Set-Content $configPath
 & $script -Id beta -Name Beta -SiteUrl https://beta.example -Endpoint https://beta.example/mcp -Environment production -Username tester -Password $fake|Out-Null
 Check ((Registry).connections.Count -eq 2) 'Adding a site lost an existing connection'
 Check ((Get-Content $configPath -Raw|ConvertFrom-Json).preserveMe -eq 'yes') 'Lost unrelated config'
 $text=Get-Content (Join-Path $testRoot 'Rizonetech/WebsiteRouter/token.dpapi') -Raw
 Check (!$text.Contains('synthetic-test-value')) 'Plaintext credential persisted'
 & $script -RemoveId alpha|Out-Null
 Check ((Registry).connections.Count -eq 1 -and (Registry).connections[0].id -eq 'beta') 'Removal affected another site'
 $failed=$false;try{& $script -Id bad -Name Bad -SiteUrl http://bad.example -Endpoint http://bad.example/mcp -Environment staging -Username tester -Password $fake|Out-Null}catch{$failed=$true}
 Check $failed 'Invalid URL accepted';Check ((Registry).connections.Count -eq 1) 'Rejected setup changed registry'
 Write-Output 'Windows encrypted add/update/remove, config preservation and invalid-input tests passed.'
}finally{
 $fake.Dispose();$env:LOCALAPPDATA=$previous
 $resolved=[IO.Path]::GetFullPath($testRoot);$temp=[IO.Path]::GetFullPath([IO.Path]::GetTempPath())
 if($resolved.StartsWith($temp,[StringComparison]::OrdinalIgnoreCase) -and [IO.Path]::GetFileName($resolved) -like 'website-router-test-*' -and (Test-Path -LiteralPath $resolved)){Remove-Item -LiteralPath $resolved -Recurse -Force}
}
