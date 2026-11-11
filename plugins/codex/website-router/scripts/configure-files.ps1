[CmdletBinding(DefaultParameterSetName='Vault')]
param(
 [Parameter(Mandatory,ParameterSetName='Vault')][string]$SiteId,
 [Parameter(Mandatory,ParameterSetName='Vault')][string]$ItemId,
 [Parameter(Mandatory,ParameterSetName='Vault')][string]$HostKey,
 [Parameter(ParameterSetName='Vault')][string]$SftpHost='sftp.pressable.com',
 [Parameter(ParameterSetName='Vault')][string]$SshHost='ssh.pressable.com',
 [Parameter(ParameterSetName='Vault')][int]$Port=22,
 [Parameter(ParameterSetName='Vault')][string]$SftpRoot='.',
 [Parameter(ParameterSetName='Vault')][string]$SshRoot='/srv/htdocs',
 [Parameter()][string]$BackupKeyItemId,
 [Parameter(Mandatory,ParameterSetName='Inventory')][switch]$ImportVerifiedInventory
)
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'credential-store.ps1')
function Read-EncryptedJson([string]$Path){
 $s=(Get-Content -LiteralPath $Path -Raw).Trim()|ConvertTo-SecureString
 $ptr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($s)
 try{[Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)|ConvertFrom-Json -AsHashtable}finally{[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr);$s.Dispose()}
}
$folder=Get-WebsiteRouterCredentialFolder
$registry=Read-EncryptedJson (Join-Path $folder 'token.dpapi')
if($ImportVerifiedInventory){
 # Explicit one-time setup inventory. Never called by the plugin runtime.
 $entries=Read-EncryptedJson (Join-Path $folder 'ssh-import.dpapi')
 $HostKey='SHA256:9F8knmxHsFLLSu12HuHGojvBoRdEEF8Ceo6eHhFyQ50'
 # Pin verified against both existing WSL known_hosts entries and the Conclave JMR server host key.
}else{
 $raw=& op item get $ItemId --vault Conclave --format json
 if($LASTEXITCODE -ne 0){throw 'Conclave credential read failed.'}
 $entries=@($raw|ConvertFrom-Json -AsHashtable);$raw=$null
}
if($BackupKeyItemId){
 $raw=& op item get $BackupKeyItemId --vault Conclave --format json
 if($LASTEXITCODE -ne 0){throw 'Backup key recovery failed.'}
 $recovery=$raw|ConvertFrom-Json -AsHashtable;$raw=$null
 $key=@($recovery.fields|Where-Object {$_.label -eq 'password'})[0].value
 if(!$key -or ($registry.backupKey -and $registry.backupKey -cne $key)){throw 'Backup key missing or conflicts with the existing key. Nothing changed.'}
 $registry.backupKey=$key;$registry.backupKeyVaultItemId=$BackupKeyItemId;$key=$null;$recovery=$null
}
$requests=@()
foreach($entry in $entries){
 if($entry.title -match 'Novamira'){continue}
 $f=@{};foreach($field in $entry.fields){$f[$field.label]=$field.value}
 $siteMatches=@(if($ImportVerifiedInventory){$registry.connections|Where-Object {$_.siteUrl.TrimEnd('/') -eq ([string]$f.site_url).TrimEnd('/')}}else{$registry.connections|Where-Object {$_.id -eq $SiteId}})
 if($siteMatches.Count -ne 1 -or !$f.username -or (!$f.password -and !$f.'private key')){continue}
 $requests+=@{siteId=$siteMatches[0].id;vaultItemId=$entry.id;hostKey=$HostKey;sftpHost=$SftpHost;sshHost=$SshHost;port=$Port;sftpRoot=$SftpRoot;sshRoot=$SshRoot;username=$f.username;password=$f.password;privateKey=$f.'private key'}
}
if(!$requests.Count){throw 'No matching registered site with credentials. Existing configuration unchanged.'}
$payload=@{registry=$registry;requests=$requests}|ConvertTo-Json -Depth 30 -Compress
# stdin/stdout are captured in memory; never display the provider registry.
$result=$payload | & node (Join-Path $PSScriptRoot 'configure-files.mjs')
$payload=$null
if($LASTEXITCODE -ne 0){throw 'SSH/SFTP verification failed; existing encrypted registry unchanged.'}
try{$updated=$result|ConvertFrom-Json -AsHashtable}catch{throw 'Invalid configuration result; existing registry unchanged.'}
if(!$updated.backupKeyVaultItemId){
 $item=@{title='Website Router Backup Encryption';category='PASSWORD';fields=@(@{id='password';label='password';purpose='PASSWORD';type='CONCEALED';value=$updated.backupKey},@{id='notesPlain';label='notesPlain';purpose='NOTES';type='STRING';value='Recovery key for Website Router AES-256-GCM file backups. Keep with encrypted backup files when moving hosts. Runtime uses DPAPI/systemd encryption and never reads 1Password.'})}|ConvertTo-Json -Depth 10 -Compress
 $saved=$item|& op item create --vault Conclave --format json
 if($LASTEXITCODE -ne 0){throw 'Could not save the backup recovery key in Conclave. Existing registry unchanged.'}
 $updated.backupKeyVaultItemId=($saved|ConvertFrom-Json).id;$saved=$null;$item=$null
}
$secure=ConvertTo-SecureString ($updated|ConvertTo-Json -Depth 30 -Compress) -AsPlainText -Force
try{Save-WebsiteRouterCredential $secure}finally{$secure.Dispose();$result=$null}
$updated.connections|ForEach-Object{[pscustomobject]@{id=$_.id;url=$_.siteUrl;ssh=[bool]$_.files;sftp=[bool]$_.files}}|ConvertTo-Json

