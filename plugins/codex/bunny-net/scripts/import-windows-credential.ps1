param([Parameter(Mandatory=$true)][string]$TokenReference)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'credential-store.ps1')
if ($TokenReference -notmatch '^op://[^\r\n]+$') { throw 'Pass a 1Password secret reference, not the API token.' }
$secure = $null
$plain = $null
try {
    $plain = & op read $TokenReference --no-newline
    if ($LASTEXITCODE -ne 0) { throw '1Password credential read failed. Existing credentials were not changed.' }
    $plain = ($plain -join "`n").Trim()
    if ([string]::IsNullOrWhiteSpace($plain)) { throw 'The 1Password credential is empty. Existing credentials were not changed.' }
    $secure = ConvertTo-SecureString -String $plain -AsPlainText -Force
    Save-BunnyNetCredential -Token $secure -TokenReference $TokenReference
    Write-Output 'BunnyNet credential imported with Windows account encryption. Normal use does not call 1Password. Start a new plugin process to use the updated token immediately.'
} finally { if ($secure) { $secure.Dispose() }; $plain = $null }
