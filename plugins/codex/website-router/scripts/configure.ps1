[CmdletBinding(DefaultParameterSetName='Status')]
param(
 [Parameter(Mandatory,ParameterSetName='ImportAll')][switch]$ImportAllWordPress,
 [Parameter(Mandatory,ParameterSetName='Import')][string]$ItemId,
 [Parameter(Mandatory,ParameterSetName='Manual')][string]$Id,
 [Parameter(Mandatory,ParameterSetName='Manual')][string]$Name,
 [Parameter(Mandatory,ParameterSetName='Manual')][string]$SiteUrl,
 [Parameter(Mandatory,ParameterSetName='Manual')][string]$Endpoint,
 [Parameter(Mandatory,ParameterSetName='Manual')][ValidateSet('production','staging','development','unknown')][string]$Environment,
 [Parameter(Mandatory,ParameterSetName='Manual')][string]$Username,
 [Parameter(ParameterSetName='Manual')][Security.SecureString]$Password,
 [Parameter(Mandatory,ParameterSetName='Remove')][string]$RemoveId,
 [Parameter(ParameterSetName='Status')][switch]$Status
)
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'credential-store.ps1')
function Check-Connection($c){
 if($c.id -notmatch '^[a-z0-9][a-z0-9-]{0,79}$'){throw 'Invalid connection ID.'}
 if(!$c.name -or !$c.username -or !$c.password -or $c.username -match '[:\r\n]' -or $c.password -match '[\r\n]'){throw 'Name and valid credentials are required.'}
 foreach($value in @($c.siteUrl,$c.endpoint)){
  $u=$null
  if(-not [uri]::TryCreate($value,[UriKind]::Absolute,[ref]$u) -or $u.Scheme -ne 'https' -or $u.UserInfo -or $u.Query -or $u.Fragment -or $u.Port -ne 443 -or $u.HostNameType -ne [UriHostNameType]::Dns -or $u.Host -notmatch '\.' -or $u.Host -match '(?i)(\.local|\.localhost|\.internal|\.test|\.invalid)$'){throw 'Use a public HTTPS endpoint without credentials, query or fragment.'}
 }
 if(([uri]$c.siteUrl).Authority -ne ([uri]$c.endpoint).Authority){throw 'Site URL and MCP endpoint must have the same authority.'}
 if($c.environment -notin @('production','staging','development','unknown')){throw 'Set a valid environment.'}
}
if($PSCmdlet.ParameterSetName -eq 'Status'){Get-WebsiteRouterCredentialStatus|ConvertTo-Json;return}
$folder=Get-WebsiteRouterCredentialFolder
$store=[ordered]@{schemaVersion=1;connections=@()}
$blob=Join-Path $folder 'token.dpapi'
if(Test-Path -LiteralPath $blob){
 $s=(Get-Content -LiteralPath $blob -Raw)|ConvertTo-SecureString
 $p=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($s)
 try{$store=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($p)|ConvertFrom-Json -AsHashtable}finally{[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($p);$s.Dispose()}
 if($store.schemaVersion -ne 1){throw 'Unknown registry schema; existing credentials unchanged.'}
}
$changes=@();$skipped=@()
if($PSCmdlet.ParameterSetName -in @('Import','ImportAll')){
 if($ImportAllWordPress){
  $items=(& op item list --vault Conclave --format json)|ConvertFrom-Json
  if($LASTEXITCODE -ne 0){throw 'Cannot list Conclave. Existing registry unchanged.'}
  $items=@($items|Where-Object {$_.title -match 'WordPress' -and $_.title -notmatch 'Novamira'})
 }else{$items=@(@{id=$ItemId})}
 foreach($item in $items){
  $raw=& op item get $item.id --vault Conclave --format json
  if($LASTEXITCODE -ne 0){throw 'Conclave import failed. Existing registry unchanged.'}
  $entry=$raw|ConvertFrom-Json;$raw=$null
  if($entry.title -match 'Novamira'){throw 'Novamira is discontinued and cannot be imported.'}
  $f=@{};foreach($field in $entry.fields){$f[$field.label]=$field.value}
  $slug=($entry.title -replace '(?i)\s*(WordPress|MCP)\s*',' ').Trim().ToLowerInvariant() -replace '[^a-z0-9]+','-'
  $previous=@($store.connections|Where-Object {$_.vaultItemId -eq $entry.id})
  if($previous.Count){$slug=$previous[0].id}
  $envName=[string]$f.environment
  if($envName -match '(?i)staging|launch'){$envName='staging'}elseif($envName -match '(?i)production|live'){$envName='production'}elseif($envName -match '(?i)dev|local'){$envName='development'}else{$envName='unknown'}
  $c=@{id=$slug;name=$entry.title;siteUrl=[string]$f.site_url;endpoint=[string]$f.endpoint;environment=$envName;username=[string]$f.username;password=[string]$f.password;vaultItemId=$entry.id}
  try{Check-Connection $c;$changes+=,$c}catch{$skipped+=@{name=$entry.title;reason=$_.Exception.Message}}
  $entry=$null;$f=$null
 }
}elseif($PSCmdlet.ParameterSetName -eq 'Manual'){
 $prompted=$false
 try{
  if(!$Password){$Password=Read-Host 'WordPress application password (hidden)' -AsSecureString;$prompted=$true}
  $p=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($Password)
  try{$c=@{id=$Id;name=$Name;siteUrl=$SiteUrl;endpoint=$Endpoint;environment=$Environment;username=$Username;password=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($p)};Check-Connection $c;$changes+=,$c}finally{[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($p)}
 }finally{if($prompted){$Password.Dispose()}}
}elseif($RemoveId){$store.connections=@($store.connections|Where-Object {$_.id -ne $RemoveId})}
foreach($change in $changes){
 $collision=@($store.connections|Where-Object {$_.id -eq $change.id -and $_.vaultItemId -and $change.vaultItemId -and $_.vaultItemId -ne $change.vaultItemId})
 if($collision.Count){throw 'Duplicate connection ID across vault items. Use explicit manual setup; nothing saved.'}
 $old=@($store.connections|Where-Object {$_.id -eq $change.id})
 if($old.Count -and $old[0].files){$change.files=$old[0].files}
 $store.connections=@($store.connections|Where-Object {$_.id -ne $change.id})+@($change)
}
if(!$changes.Count -and !$RemoveId){$skipped|ConvertTo-Json;throw 'No valid connections imported; existing registry unchanged.'}
if(@($store.connections).Count -gt 100){throw 'At most 100 connections are supported; existing registry unchanged.'}
$encoded=$store|ConvertTo-Json -Depth 20 -Compress
$secure=ConvertTo-SecureString $encoded -AsPlainText -Force
try{Save-WebsiteRouterCredential -Token $secure}finally{$secure.Dispose();$encoded=$null}
[pscustomobject]@{saved=$changes.Count;total=@($store.connections).Count;connections=@($store.connections|ForEach-Object{[pscustomobject]@{id=$_.id;name=$_.name;siteUrl=$_.siteUrl;endpoint=$_.endpoint;environment=$_.environment}});skipped=$skipped;next='Restart the local plugin. Use sync-ubuntu.ps1 to update the cloud copy; no code changes or new tunnel are required.'}|ConvertTo-Json -Depth 6
