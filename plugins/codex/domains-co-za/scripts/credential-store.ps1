# Shared by this plugin's setup entrypoints. Keep it inside the plugin package.
function Get-DomainsCoZaCredentialFolder {
    if ($env:OS -ne 'Windows_NT' -or -not $env:LOCALAPPDATA) { throw 'Credential setup requires Windows and LOCALAPPDATA.' }
    Join-Path $env:LOCALAPPDATA 'Rizonetech/DomainsCoZa'
}

function Get-DomainsCoZaCredentialStatus {
    $folder = Get-DomainsCoZaCredentialFolder
    $configPath = Join-Path $folder 'config.json'
    $config = $null
    if (Test-Path -LiteralPath $configPath) {
        try { $config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json }
        catch { throw 'The DomainsCoZa configuration is invalid. Repair it before changing credentials.' }
    }
    [PSCustomObject]@{
        authMode = $(if ($config.authMode) { $config.authMode } else { 'not-configured' })
        encryptedCredentialPresent = (Test-Path -LiteralPath (Join-Path $folder 'token.dpapi'))
        configurationPresent = ($null -ne $config)
        folder = $folder
        note = 'Presence only; use check-connection.mjs to verify API access.'
    }
}

function Save-DomainsCoZaCredential {
    param([Parameter(Mandatory=$true)][Security.SecureString]$Token, [string]$TokenReference)
    $ErrorActionPreference = 'Stop'
    $folder = Get-DomainsCoZaCredentialFolder
    $pointer = [IntPtr]::Zero
    $verifyPointer = [IntPtr]::Zero
    $normalized = $null
    $verified = $null
    $temporary = $null
    try {
        $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Token)
        $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer).Trim() -replace '^Bearer\s+', ''
        if ([string]::IsNullOrWhiteSpace($plain) -or $plain -match '[\r\n]') { throw 'The API token is empty or invalid. Existing credentials were not changed.' }
        try { $bundle = $plain | ConvertFrom-Json } catch { throw 'Credential must be a valid JSON bundle.' }
        if ($bundle.mode -eq 'login') {
            if ([string]::IsNullOrWhiteSpace($bundle.username) -or [string]::IsNullOrWhiteSpace($bundle.password)) { throw 'Username and password are required.' }
        } elseif ($bundle.mode -eq 'bearer') {
            if ([string]::IsNullOrWhiteSpace($bundle.token) -or $bundle.token -match '[\r\n]') { throw 'A valid bearer token is required.' }
        } else { throw 'Credential mode must be login or bearer.' }
        $normalized = ConvertTo-SecureString -String $plain -AsPlainText -Force
        $encrypted = ConvertFrom-SecureString -SecureString $normalized
        $verified = ConvertTo-SecureString -String $encrypted
        $verifyPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($verified)
        if ([Runtime.InteropServices.Marshal]::PtrToStringBSTR($verifyPointer) -cne $plain) { throw 'Windows credential encryption verification failed.' }

        # Preserve unrelated non-secret settings and refuse to overwrite malformed configuration.
        $configPath = Join-Path $folder 'config.json'
        $config = @{}
        if (Test-Path -LiteralPath $configPath) {
            try { $existing = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json }
            catch { throw 'The DomainsCoZa configuration is invalid. Repair it before changing credentials.' }
            foreach ($property in $existing.PSObject.Properties) { $config[$property.Name] = $property.Value }
        }
        $config.authMode = 'windows-dpapi'
        $config.schemaVersion = 1
        if ($TokenReference) { $config.tokenReference = $TokenReference }
        else { $config.Remove('tokenReference') }

        New-Item -ItemType Directory -Path $folder -Force | Out-Null
        $sid = [Security.Principal.WindowsIdentity]::GetCurrent().User
        $acl = [Security.AccessControl.DirectorySecurity]::new()
        # Set only the DACL; changing ownership is unnecessary for user-local setup.
        $acl.SetAccessRuleProtection($true, $false)
        foreach ($principal in @($sid, [Security.Principal.SecurityIdentifier]::new('S-1-5-18'))) {
            $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($principal, 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow'))
        }
        if ('System.IO.FileSystemAclExtensions' -as [type]) {
            [IO.FileSystemAclExtensions]::SetAccessControl([IO.DirectoryInfo]::new($folder), $acl)
        } else {
            ([IO.DirectoryInfo]::new($folder)).SetAccessControl($acl)
        }
        $utf8 = [Text.UTF8Encoding]::new($false)
        # Atomic per-file replacement avoids partial ciphertext/config on process interruption.
        foreach ($entry in @(@{name='token.dpapi';content=$encrypted}, @{name='config.json';content=($config | ConvertTo-Json -Depth 20)})) {
            $target = Join-Path $folder $entry.name
            $temporary = Join-Path $folder ([Guid]::NewGuid().ToString() + '.tmp')
            [IO.File]::WriteAllText($temporary, $entry.content, $utf8)
            if (Test-Path -LiteralPath $target) { [IO.File]::Replace($temporary,$target,[NullString]::Value) }
            else { [IO.File]::Move($temporary,$target) }
            $temporary = $null
        }
    } finally {
        if ($pointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
        if ($verifyPointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($verifyPointer) }
        if ($normalized) { $normalized.Dispose() }
        if ($verified) { $verified.Dispose() }
        if ($temporary -and (Test-Path -LiteralPath $temporary)) { Remove-Item -LiteralPath $temporary }
        $plain = $null
    }
}
