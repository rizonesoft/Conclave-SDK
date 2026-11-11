$ErrorActionPreference = 'Stop'
$originalLocalAppData = $env:LOCALAPPDATA
$testRoot = Join-Path ([IO.Path]::GetTempPath()) ('pressable-credential-test-' + [Guid]::NewGuid())
$configScript = Join-Path $PSScriptRoot '../scripts/configure.ps1'
$first = $null
$second = $null
$empty = $null
function Assert-True($condition,$message) { if (-not $condition) { throw $message } }
function Assert-Decrypts($path,$expected) {
    $secure = Get-Content -LiteralPath $path -Raw | ConvertTo-SecureString
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try { Assert-True ([Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer) -ceq $expected) 'Synthetic token round-trip failed' }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer); $secure.Dispose() }
}
try {
    $env:LOCALAPPDATA = $testRoot
    $before = & $configScript -Status | ConvertFrom-Json
    Assert-True (-not $before.configurationPresent) 'Fresh profile must be unconfigured'
    $first = ConvertTo-SecureString 'synthetic-first-token' -AsPlainText -Force
    & $configScript -Token $first | Out-Null
    $folder = Join-Path $testRoot 'Rizonetech/Pressable'
    $cipherPath = Join-Path $folder 'token.dpapi'
    Assert-Decrypts $cipherPath 'synthetic-first-token'
    Assert-True ((Get-Content $cipherPath -Raw) -notmatch 'synthetic-first-token') 'Token written in plaintext'
    Assert-True ((Get-Acl $folder).AreAccessRulesProtected) 'Credential ACL inherits access'
    $configPath = Join-Path $folder 'config.json'
    $config = Get-Content $configPath -Raw | ConvertFrom-Json
    $config | Add-Member -NotePropertyName unrelatedSetting -NotePropertyValue 'preserve-me'
    $config | ConvertTo-Json | Set-Content $configPath -Encoding utf8
    $second = ConvertTo-SecureString 'synthetic-replacement-token' -AsPlainText -Force
    & $configScript -Token $second | Out-Null
    Assert-Decrypts $cipherPath 'synthetic-replacement-token'
    Assert-True ((Get-Content $configPath -Raw | ConvertFrom-Json).unrelatedSetting -eq 'preserve-me') 'Unrelated configuration lost'
    $hash = (Get-FileHash $cipherPath).Hash
    $empty = [Security.SecureString]::new()
    $rejected = $false
    try { & $configScript -Token $empty | Out-Null } catch { $rejected = $true }
    Assert-True $rejected 'Empty token must fail'
    Assert-True ((Get-FileHash $cipherPath).Hash -eq $hash) 'Invalid update overwrote valid credential'
    $status = & $configScript -Status | ConvertFrom-Json
    Assert-True ($status.authMode -eq 'windows-dpapi' -and $status.encryptedCredentialPresent) 'Status is incorrect'
    Write-Output 'Windows setup checks passed: fresh profile, encryption, rotation, preserved configuration, rejected empty update, safe status.'
} finally {
    $env:LOCALAPPDATA = $originalLocalAppData
    foreach ($secure in @($first,$second,$empty)) { if ($secure) { $secure.Dispose() } }
    $resolved = [IO.Path]::GetFullPath($testRoot)
    $tempBase = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
    if ($resolved.StartsWith($tempBase,[StringComparison]::OrdinalIgnoreCase) -and [IO.Path]::GetFileName($resolved).StartsWith('pressable-credential-test-') -and (Test-Path -LiteralPath $resolved)) { Remove-Item -LiteralPath $resolved -Recurse -Force }
}
