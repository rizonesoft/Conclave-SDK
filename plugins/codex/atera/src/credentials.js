import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { readFile } from 'node:fs/promises';
import { homedir } from 'node:os';
import { join } from 'node:path';

const exec = promisify(execFile);
export const configPath = (env = process.env) => join(env.LOCALAPPDATA || join(homedir(), '.config'), 'Rizonetech', 'Atera', 'config.json');
const decryptScript = `
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$ptr = [IntPtr]::Zero
try {
  $secure = Get-Content -LiteralPath $env:ATERA_CREDENTIAL_PATH -Raw | ConvertTo-SecureString
  $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
  [Console]::Out.Write([Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr))
} catch { [Console]::Error.Write('Cannot decrypt Atera credential for this Windows account.'); exit 1 }
finally { if ($ptr -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }; if ($secure) { $secure.Dispose() } }
`;

export async function loadToken({env=process.env, platform=process.platform, readFileImpl=readFile, execImpl=exec} = {}) {

  if (platform === 'linux' && env.CREDENTIALS_DIRECTORY) {
    try {
      const token = (await readFileImpl(join(env.CREDENTIALS_DIRECTORY, 'provider'), 'utf8')).trim();
      if (!token || token.length > 65536 || /[\r\n]/.test(token)) throw new Error();
      return token.replace(/^Bearer\s+/i, '');
    } catch { throw new Error('Cannot read the Linux service credential. Update the encrypted systemd credential; no 1Password fallback was attempted.'); }
  }
  let token = env.ATERA_API_TOKEN;
  if (!token) {
    let config = {};
    try { config = JSON.parse(await readFileImpl(configPath(env), 'utf8')); }
    catch { if (!env.ATERA_TOKEN_REFERENCE) throw new Error('Atera is not configured. Follow the credential setup instructions.'); }
    if (config.authMode === 'windows-dpapi') {
      if (platform !== 'win32') throw new Error('This credential is protected for Windows. Configure credentials separately on this host.');
      try {
        const executable = join(env.SystemRoot || 'C:\\Windows', 'System32', 'WindowsPowerShell', 'v1.0', 'powershell.exe');
        const result = await execImpl(executable, ['-NoLogo','-NoProfile','-NonInteractive','-WindowStyle','Hidden','-EncodedCommand',Buffer.from(decryptScript,'utf16le').toString('base64')], {
          windowsHide:true,timeout:15000,maxBuffer:65536,
          env:Object.fromEntries(Object.entries({...env,ATERA_CREDENTIAL_PATH:join(env.LOCALAPPDATA || join(homedir(),'.config'),'Rizonetech','Atera','token.dpapi')}).filter(([key]) => key.toLowerCase() !== 'psmodulepath'))
        });
        token = result.stdout;
      } catch { throw new Error('Cannot unlock the Windows-encrypted Atera credential. Run credential import again under this Windows account. No 1Password fallback was attempted.'); }
    } else {
      const reference = env.ATERA_TOKEN_REFERENCE || config.tokenReference;
      if (typeof reference !== 'string' || !/^op:\/\/[^\r\n]+$/.test(reference)) throw new Error('Invalid 1Password token reference.');
      try {
        const result = await execImpl('op', ['read',reference,'--no-newline'], {windowsHide:true,timeout:30000,maxBuffer:65536});
        token = result.stdout;
      } catch { throw new Error('Cannot read the Atera token. Unlock 1Password, approve CLI access, and fill the credential field in Atera API.'); }
    }
  }
  token = token.trim().replace(/^Bearer\s+/i,'');
  if (!token || /[\r\n]/.test(token)) throw new Error('The Atera credential is empty or invalid. Update the configured credential store.');
  return token;
}
