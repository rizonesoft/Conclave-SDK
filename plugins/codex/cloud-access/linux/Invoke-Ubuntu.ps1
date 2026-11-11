param([Parameter(Mandatory)][string]$RemoteCommand,[switch]$IncludePluginCredentials)
$ErrorActionPreference='Stop'
$store=Join-Path $env:LOCALAPPDATA 'Rizonetech\CloudAccess'
function Unprotect-Text($Path){
 $secure=(Get-Content -LiteralPath $Path -Raw).Trim() | ConvertTo-SecureString
 $ptr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
 try{[Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)}finally{[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr);$secure.Dispose()}
}
$password=Unprotect-Text (Join-Path $store 'migration-password.dpapi')
$inputText=$password+[char]10
if($IncludePluginCredentials){
 $a=Unprotect-Text (Join-Path $env:LOCALAPPDATA 'Rizonetech\Atera\token.dpapi')
 $d=Unprotect-Text (Join-Path $env:LOCALAPPDATA 'Rizonetech\DomainsCoZa\token.dpapi')
 $t=[Security.Cryptography.ProtectedData]::Unprotect([IO.File]::ReadAllBytes((Join-Path $store 'token.dpapi')),$null,[Security.Cryptography.DataProtectionScope]::CurrentUser)
 $inputText+=(@{atera=$a;domains=$d;tunnel=[Text.Encoding]::UTF8.GetString($t)} | ConvertTo-Json -Compress)
 [Array]::Clear($t,0,$t.Length)
}
$info=[Diagnostics.ProcessStartInfo]::new('C:\Windows\System32\OpenSSH\ssh.exe')
$info.UseShellExecute=$false;$info.CreateNoWindow=$true
$info.RedirectStandardInput=$true;$info.RedirectStandardOutput=$true;$info.RedirectStandardError=$true
foreach($arg in @('-F','NUL','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=10','venom@100.83.89.28',('sudo -S -p "" '+$RemoteCommand))){$info.ArgumentList.Add($arg)}
$p=[Diagnostics.Process]::Start($info)
$out=$p.StandardOutput.ReadToEndAsync();$err=$p.StandardError.ReadToEndAsync()
$p.StandardInput.Write($inputText);$p.StandardInput.Close()
$inputText=$null;$password=$null;$a=$null;$d=$null
if(-not $p.WaitForExit(300000)){$p.Kill();throw 'Remote command timeout'}
[Console]::Out.Write($out.GetAwaiter().GetResult())
if($p.ExitCode -ne 0){[Console]::Error.Write($err.GetAwaiter().GetResult());throw 'Remote command failed'}
