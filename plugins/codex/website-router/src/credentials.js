import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {readFile} from 'node:fs/promises';
import {join} from 'node:path';
const exec=promisify(execFile);
const decrypt=`$ErrorActionPreference='Stop';$ptr=[IntPtr]::Zero;try{$s=(Get-Content -LiteralPath $env:WEBSITE_ROUTER_CREDENTIAL_PATH -Raw).Trim()|ConvertTo-SecureString;$ptr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($s);[Console]::Out.Write([Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr))}catch{exit 1}finally{if($ptr -ne [IntPtr]::Zero){[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)};if($s){$s.Dispose()}}`;
export async function loadToken({env=process.env,platform=process.platform,readFileImpl=readFile,execImpl=exec}={}){
 try{
  let token;
  if(platform==='linux'&&env.CREDENTIALS_DIRECTORY)token=await readFileImpl(join(env.CREDENTIALS_DIRECTORY,'provider'),'utf8');
  else if(platform==='win32'&&env.LOCALAPPDATA){
   const folder=join(env.LOCALAPPDATA,'Rizonetech','WebsiteRouter');
   const config=JSON.parse(await readFileImpl(join(folder,'config.json'),'utf8'));
   if(config.authMode!=='windows-dpapi')throw new Error();
   const result=await execImpl(join(env.SystemRoot||'C:\\Windows','System32','WindowsPowerShell','v1.0','powershell.exe'),['-NoLogo','-NoProfile','-NonInteractive','-WindowStyle','Hidden','-EncodedCommand',Buffer.from(decrypt,'utf16le').toString('base64')],{windowsHide:true,timeout:15000,maxBuffer:1048576,env:Object.fromEntries(Object.entries({...env,WEBSITE_ROUTER_CREDENTIAL_PATH:join(folder,'token.dpapi')}).filter(([k])=>k.toLowerCase()!=='psmodulepath'))});
   token=result.stdout;
  }else throw new Error();
  token=token.trim();if(!token||token.length>1048576||/[\r\n]/.test(token))throw new Error();return token;
 }catch{throw new Error('WebsiteRouter credential unavailable. Configure the encrypted store on this host. No 1Password fallback was attempted.');}
}
