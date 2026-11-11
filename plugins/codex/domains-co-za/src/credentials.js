import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import { readFile } from 'node:fs/promises';
import { homedir } from 'node:os';
import { join } from 'node:path';

const exec = promisify(execFile);
export const configPath = (env = process.env) => join(env.LOCALAPPDATA || join(homedir(), '.config'), 'Rizonetech', 'DomainsCoZa', 'config.json');
const decryptScript = `
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$ptr = [IntPtr]::Zero
try {
  $secure = Get-Content -LiteralPath $env:DOMAINS_CREDENTIAL_PATH -Raw | ConvertTo-SecureString
  $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
  [Console]::Out.Write([Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr))
} catch { [Console]::Error.Write('Cannot decrypt DomainsCoZa credential for this Windows account.'); exit 1 }
finally { if ($ptr -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }; if ($secure) { $secure.Dispose() } }
`;


export async function loadCredentials({env=process.env,platform=process.platform,readFileImpl=readFile,execImpl=exec}={}) {

  if (platform === 'linux' && env.CREDENTIALS_DIRECTORY) {
    try {
      const raw = await readFileImpl(join(env.CREDENTIALS_DIRECTORY, 'provider'), 'utf8');
      if (raw.length > 65536) throw new Error();
      const c = JSON.parse(raw);
      if (c.mode === 'login' && typeof c.username === 'string' && c.username.trim() && typeof c.password === 'string' && c.password) return c;
      if (c.mode === 'bearer' && typeof c.token === 'string' && c.token.trim() && !/[\r\n]/.test(c.token)) return c;
      throw new Error();
    } catch { throw new Error('Cannot read valid Linux service credentials. Update the encrypted systemd credential; no 1Password access attempted.'); }
  }
  if(platform!=='win32') throw new Error('Domains.co.za credentials require Windows. Configure them on this computer.');
  let config;
  try { config=JSON.parse(await readFileImpl(configPath(env),'utf8')); } catch { throw new Error('Domains.co.za is not configured. Run scripts/configure.ps1.'); }
  if(config.authMode!=='windows-dpapi') throw new Error('Configure Windows-encrypted credentials. No 1Password fallback is allowed.');
  try {
    const executable=join(env.SystemRoot||'C:\\Windows','System32','WindowsPowerShell','v1.0','powershell.exe');
    const result=await execImpl(executable,['-NoLogo','-NoProfile','-NonInteractive','-WindowStyle','Hidden','-EncodedCommand',Buffer.from(decryptScript,'utf16le').toString('base64')],{windowsHide:true,timeout:15000,maxBuffer:65536,env:Object.fromEntries(Object.entries({...env,DOMAINS_CREDENTIAL_PATH:join(env.LOCALAPPDATA,'Rizonetech','DomainsCoZa','token.dpapi')}).filter(([k])=>k.toLowerCase()!=='psmodulepath'))});
    const c=JSON.parse(result.stdout);
    if(c.mode==='login'&&typeof c.username==='string'&&c.username.trim()&&typeof c.password==='string'&&c.password) return c;
    if(c.mode==='bearer'&&typeof c.token==='string'&&c.token.trim()&&!/[\r\n]/.test(c.token)) return c;
    throw new Error();
  } catch { throw new Error('Cannot unlock valid Domains.co.za credentials. Run configure.ps1 under this Windows account. No 1Password access attempted.'); }
}
