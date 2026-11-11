import test from 'node:test';
import assert from 'node:assert/strict';
import {loadToken} from '../src/credentials.js';

test('DPAPI uses only a hidden Windows decryptor even with a 1Password reference',async()=>{
  const calls=[];
  const token=await loadToken({platform:'win32',env:{LOCALAPPDATA:'C:/test',SystemRoot:'C:/Windows',PSModulePath:'incompatible-pwsh-modules',ATERA_TOKEN_REFERENCE:'op://unused/item/credential'},readFileImpl:async()=>JSON.stringify({authMode:'windows-dpapi',tokenReference:'op://unused/item/credential'}),execImpl:async(command,args,options)=>{calls.push(command);assert.match(command,/powershell.exe$/);assert.equal(options.windowsHide,true);assert.equal(options.env.PSModulePath,undefined);assert.ok(args.includes('-NonInteractive'));assert.match(options.env.ATERA_CREDENTIAL_PATH,/token.dpapi$/);return {stdout:'sample-token'};}});
  assert.equal(token,'sample-token');assert.equal(calls.length,1);assert.ok(!calls.includes('op'));
});
test('DPAPI failure never falls back to 1Password or includes underlying errors',async()=>{
  let calls=0;
  await assert.rejects(loadToken({platform:'win32',env:{},readFileImpl:async()=>'{"authMode":"windows-dpapi"}',execImpl:async()=>{calls++;throw new Error('private-details');}}),e=> /No 1Password fallback/.test(e.message) && !e.message.includes('private-details'));
  assert.equal(calls,1);
});
test('encrypted Windows credentials are not treated as portable',async()=>{
  await assert.rejects(loadToken({platform:'linux',env:{},readFileImpl:async()=>'{"authMode":"windows-dpapi"}'}),/protected for Windows/);
});
test('legacy reference mode and securely injected tokens still work',async()=>{
  const token=await loadToken({env:{ATERA_TOKEN_REFERENCE:'op://vault/item/credential'},readFileImpl:async()=>{throw new Error('no file');},execImpl:async(command)=>{assert.equal(command,'op');return {stdout:'legacy-token'};}});
  assert.equal(token,'legacy-token');
  assert.equal(await loadToken({env:{ATERA_API_TOKEN:'Bearer direct-token'}}),'direct-token');
});
