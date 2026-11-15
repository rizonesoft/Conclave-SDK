param([ValidateSet('status','load','save')][string]$Action='status')
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
[Console]::InputEncoding=[Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false)
$pointer=[IntPtr]::Zero
$secure=$null
$temporary=$null
try {
    # A process started from WSL inherits the module path of whatever started wsl.exe, which can list
    # PowerShell 7's modules first; autoloading its Security module into this engine fails, so load this engine's own.
    Import-Module -Name (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Security\Microsoft.PowerShell.Security.psd1')
    if (-not $env:LOCALAPPDATA) { throw 'Missing Windows profile' }
    $folder=Join-Path $env:LOCALAPPDATA 'Rizonetech/OutlookGraph'
    $path=Join-Path $folder 'session.dpapi'
    if ($Action -eq 'status') {
        @{folder=$folder;credentialPresent=(Test-Path -LiteralPath $path);configurationPresent=(Test-Path -LiteralPath (Join-Path $folder 'config.json'));mode='windows-dpapi';onePasswordRuntimeAccess=$false} | ConvertTo-Json -Compress
        exit 0
    }
    if ($Action -eq 'load') {
        if (-not (Test-Path -LiteralPath $path)) { [Console]::Out.Write('null'); exit 0 }
        $secure=[IO.File]::ReadAllText($path) | ConvertTo-SecureString
        $pointer=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
        [Console]::Out.Write([Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer))
        exit 0
    }
    $plain=[Console]::In.ReadToEnd()
    if ($plain.Length -gt 4194304) { throw 'Record too large' }
    $record=$plain | ConvertFrom-Json
    if ($record.schemaVersion -ne 1 -or -not $record.config.clientId -or -not $record.config.tenantId -or -not $record.config.mailbox -or -not $record.cache) { throw 'Invalid session record' }
    $configPath=Join-Path $folder 'config.json'
    $config=@{}
    if (Test-Path -LiteralPath $configPath) {
        $existing=[IO.File]::ReadAllText($configPath) | ConvertFrom-Json
        foreach ($property in $existing.PSObject.Properties) { $config[$property.Name]=$property.Value }
    }
    $config.schemaVersion=1
    $config.authMode='windows-dpapi'
    foreach ($name in @('clientId','tenantId','mailbox')) { $config[$name]=$record.config.$name }
    $secure=ConvertTo-SecureString -String $plain -AsPlainText -Force
    $encrypted=ConvertFrom-SecureString -SecureString $secure
    $check=ConvertTo-SecureString $encrypted
    try {
        $pointer=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($check)
        if ([Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer) -cne $plain) { throw 'Encryption verification failed' }
    } finally { $check.Dispose() }
    New-Item -ItemType Directory -Force -Path $folder | Out-Null
    $acl=[Security.AccessControl.DirectorySecurity]::new()
    $acl.SetAccessRuleProtection($true,$false)
    foreach ($sid in @([Security.Principal.WindowsIdentity]::GetCurrent().User,[Security.Principal.SecurityIdentifier]::new('S-1-5-18'))) {
        $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($sid,'FullControl','ContainerInherit,ObjectInherit','None','Allow'))
    }
    if ('System.IO.FileSystemAclExtensions' -as [type]) { [IO.FileSystemAclExtensions]::SetAccessControl([IO.DirectoryInfo]::new($folder),$acl) }
    else { ([IO.DirectoryInfo]::new($folder)).SetAccessControl($acl) }
    $temporary=Join-Path $folder ([Guid]::NewGuid().ToString()+'.tmp')
    [IO.File]::WriteAllText($temporary,$encrypted,[Text.UTF8Encoding]::new($false))
    if (Test-Path -LiteralPath $path) { [IO.File]::Replace($temporary,$path,[NullString]::Value) }
    else { [IO.File]::Move($temporary,$path) }
    $temporary=$null
    $temporary=Join-Path $folder ([Guid]::NewGuid().ToString()+'.tmp')
    [IO.File]::WriteAllText($temporary,($config | ConvertTo-Json -Depth 20),[Text.UTF8Encoding]::new($false))
    if (Test-Path -LiteralPath $configPath) { [IO.File]::Replace($temporary,$configPath,[NullString]::Value) }
    else { [IO.File]::Move($temporary,$configPath) }
    $temporary=$null
    [Console]::Out.Write('{"saved":true}')
} catch { [Console]::Error.Write('Windows encrypted session store failed. Existing session was not deliberately erased.'); exit 1 }
finally {
    if ($pointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
    if ($secure) { $secure.Dispose() }
    if ($temporary -and (Test-Path -LiteralPath $temporary)) { Remove-Item -LiteralPath $temporary }
    $plain=$null
}
