[CmdletBinding(DefaultParameterSetName='Prompt')]
param(
    [Parameter(Mandatory=$true,ParameterSetName='Import')][string]$TokenReference,
    [Parameter(Mandatory=$true,ParameterSetName='Secure')][Security.SecureString]$Token,
    [Parameter(Mandatory=$true,ParameterSetName='Status')][switch]$Status
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'credential-store.ps1')
if ($Status) { Get-AteraCredentialStatus | ConvertTo-Json; return }
if ($PSCmdlet.ParameterSetName -eq 'Import') {
    & (Join-Path $PSScriptRoot 'import-windows-credential.ps1') -TokenReference $TokenReference
    return
}
$prompted = $false
try {
    if ($null -eq $Token) { $Token = Read-Host 'Enter the Atera API token (input hidden)' -AsSecureString; $prompted = $true }
    Save-AteraCredential -Token $Token
    Write-Output 'Atera credential saved with Windows account encryption. This command also replaces an existing credential. Start a new plugin process to use it immediately.'
} finally { if ($prompted -and $Token) { $Token.Dispose() } }
