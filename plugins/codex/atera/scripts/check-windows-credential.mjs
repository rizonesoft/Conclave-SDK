import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import assert from 'node:assert/strict';
import {loadToken} from '../src/credentials.js';
import {AteraClient} from '../src/client.js';
const exec=promisify(execFile);
let decryptions=0;
const client=new AteraClient({tokenProvider:()=>loadToken({env:{...process.env,ATERA_API_TOKEN:''},execImpl:async(command,args,options)=>{
  assert.match(command,/powershell.exe$/i,'Only the Windows decryptor may run; 1Password calls are blocked in this verification.');
  decryptions++;
  return exec(command,args,options);
}})});
try {
  await client.get('/api/v3/agents',{page:1,itemsInPage:1});
  assert.equal(decryptions,1);
  console.log(JSON.stringify({connected:true,credentialSource:'windows-dpapi',onePasswordCalls:0}));
} catch (error) {
  console.error(error.message);
  process.exitCode=1;
}
