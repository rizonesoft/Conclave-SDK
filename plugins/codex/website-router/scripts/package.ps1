param([string]$Output)
$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
if(!$Output){$Output=Join-Path (Split-Path $root -Parent) '.local/releases/website-router-0.2.1.zip'}
New-Item -ItemType Directory -Path (Split-Path $Output -Parent) -Force|Out-Null
Add-Type -AssemblyName System.IO.Compression
$stream=[IO.File]::Open($Output,[IO.FileMode]::Create)
$zip=[IO.Compression.ZipArchive]::new($stream,[IO.Compression.ZipArchiveMode]::Create)
$count=0
try{
 $files=@(Get-ChildItem -LiteralPath $root -File)
 foreach($dir in @('src','dist','scripts','skills','assets','tests')){$files+=Get-ChildItem -LiteralPath (Join-Path $root $dir) -File -Recurse}
 foreach($file in $files){
  $relative=[IO.Path]::GetRelativePath($root,$file.FullName).Replace('\','/')
  if($relative -match '(?i)(\.dpapi|\.cred|\.env|\.log)$'){throw 'Sensitive file extension in package'}
  [IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip,$file.FullName,$relative,[IO.Compression.CompressionLevel]::Optimal)|Out-Null
  $count++
 }
}finally{$zip.Dispose();$stream.Dispose()}
[pscustomobject]@{package=$Output;entries=$count;bytes=(Get-Item -LiteralPath $Output).Length}|ConvertTo-Json
