param([Parameter(Mandatory)][string]$RemoteCommand,[switch]$IncludeProvider)
$ErrorActionPreference='Stop'
# Explicit deployment/maintenance helper only. Never called by the MCP server.
$password=$null;$payload=$null;$ptr=[IntPtr]::Zero;$secure=$null
try{
 $password=(& op read 'op://Conclave/hnp4ojje5p7ldgaec4f6z2sc3q/password' --no-newline)
 if($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($password)){throw 'Ubuntu credential read failed.'}
 $payload=$password+[char]10
 if($IncludeProvider){
  $secure=(Get-Content (Join-Path $env:LOCALAPPDATA 'Rizonetech/Pressable/token.dpapi') -Raw).Trim()|ConvertTo-SecureString
  $ptr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
  $payload+=(@{provider=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)}|ConvertTo-Json -Compress)
 }
 $info=[Diagnostics.ProcessStartInfo]::new('C:\Windows\System32\OpenSSH\ssh.exe')
 $info.UseShellExecute=$false;$info.CreateNoWindow=$true
 $info.RedirectStandardInput=$true;$info.RedirectStandardOutput=$true;$info.RedirectStandardError=$true
 foreach($arg in @('-F','NUL','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=10','venom@100.83.89.28',('sudo -S -p "" '+$RemoteCommand))){$info.ArgumentList.Add($arg)}
 $p=[Diagnostics.Process]::Start($info)
 $out=$p.StandardOutput.ReadToEndAsync();$err=$p.StandardError.ReadToEndAsync()
 $p.StandardInput.Write($payload);$p.StandardInput.Close();$payload=$null;$password=$null
 if(-not $p.WaitForExit(180000)){$p.Kill();throw 'Remote maintenance timed out.'}
 if($p.ExitCode -ne 0){throw 'Remote maintenance failed. Provider or sudo data was not printed.'}
 [Console]::Out.Write($out.GetAwaiter().GetResult())
}finally{if($ptr -ne [IntPtr]::Zero){[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)};if($secure){$secure.Dispose()};$payload=$null;$password=$null}