import test from 'node:test';
import assert from 'node:assert/strict';
import { DomainsClient,scrub } from '../src/client.js';
import { loadCredentials } from '../src/credentials.js';
const credentials=async()=>({mode:'bearer',token:'test-secret'});
const ok=data=>new Response(JSON.stringify({intReturnCode:1,...data}));
test('login sends password in form body and caches JWT; rotation invalidates cache',async()=>{
 let password='password-one';const calls=[];
 const client=new DomainsClient({credentials:async()=>({mode:'login',username:'user',password}),fetchImpl:async(u,o)=>{calls.push({url:String(u),...o});return ok(String(u).endsWith('/login')?{token:'test-jwt'}:{balance:12});}});
 await client.request('GET','/domain/funds');await client.request('GET','/domain/funds');
 assert.equal(calls.filter(c=>c.url.endsWith('/login')).length,1);
 assert.equal(calls[0].body,'username=user&password=password-one');assert(!calls[0].url.includes('password'));
 password='replacement';await client.request('GET','/domain/funds');assert.equal(calls.filter(c=>c.url.endsWith('/login')).length,2);
 assert(calls.every(c=>c.redirect==='error'));
});
test('availability code zero is successful only with isAvailable',async()=>{
 const c=new DomainsClient({credentials,fetchImpl:async()=>ok({intReturnCode:0,isAvailable:true})});
 assert.equal((await c.request('GET','/domain/check',{sld:'example',tld:'co.za'})).isAvailable,true);
 const bad=new DomainsClient({credentials,fetchImpl:async()=>ok({intReturnCode:0})});await assert.rejects(bad.request('GET','/domain/check'),/rejected/);
});
test('no arbitrary endpoints and no credential loading for unsupported calls',async()=>{
 let reads=0;const c=new DomainsClient({credentials:async()=>{reads++;return credentials();}});
 await assert.rejects(c.request('POST','/billing/manualTopup'),/Unsupported/);assert.equal(reads,0);
});
test('POST body and documented PUT/DELETE query encoding; autorenew false stays explicit',async()=>{
 const calls=[];const c=new DomainsClient({credentials,fetchImpl:async(u,o)=>{calls.push([String(u),o]);return ok({});}});
 await c.request('POST','/domain/autorenew',{sld:'example',tld:'co.za',autorenew:false});
 assert(calls[0][1].body.includes('autorenew=false'));
 await c.request('PUT','/domain/dns/entry',{dnsId:1,content:'a&b'});assert(calls[1][0].includes('content=a%26b'));assert.equal(calls[1][1].body,undefined);
 await c.request('DELETE','/domain/dns/entry',{dnsId:1});assert(calls[2][0].includes('dnsId=1'));
});
test('GET retries once; failed writes never retry and suppress response secrets',async()=>{
 let n=0;const c=new DomainsClient({credentials,sleep:async()=>{},fetchImpl:async()=>{n++;return n===1?new Response('private',{status:503}):ok({});}});
 await c.request('GET','/domain/funds');assert.equal(n,2);
 n=0;const w=new DomainsClient({credentials,fetchImpl:async()=>{n++;return new Response('test-secret',{status:503});}});
 await assert.rejects(w.request('POST','/domain/renew',{}),e=>!e.message.includes('test-secret'));assert.equal(n,1);
});
test('provider errors redact body and nested credential fields',async()=>{
 const c=new DomainsClient({credentials,fetchImpl:async()=>ok({intReturnCode:6,strMessage:'test-secret'})});
 await assert.rejects(c.request('GET','/domain/funds'),e=>!e.message.includes('test-secret'));
 assert.deepEqual(scrub({a:[{eppKey:'value',normal:'test-secret'}],token:'secret'},['test-secret']),{a:[{normal:'[redacted]'}]});
});
test('DPAPI mode only; no 1Password fallback or environment token mode',async()=>{
 let executions=0;const execImpl=async()=>{executions++;throw new Error();};
 await assert.rejects(loadCredentials({platform:'win32',env:{DOMAINS_API_TOKEN:'ignored'},readFileImpl:async()=>{throw new Error();},execImpl}),/not configured/);
 await assert.rejects(loadCredentials({platform:'win32',readFileImpl:async()=>JSON.stringify({authMode:'1password'}),execImpl}),/No 1Password fallback/);
 assert.equal(executions,0);
});
test('runtime invokes only hidden bounded Windows decryption',async()=>{
 let command;const result=await loadCredentials({platform:'win32',env:{LOCALAPPDATA:'C:/isolated',SystemRoot:'C:/Windows',PSModulePath:'unsafe'},readFileImpl:async()=>JSON.stringify({authMode:'windows-dpapi'}),execImpl:async(exe,args,options)=>{command={exe,args,options};return{stdout:JSON.stringify({mode:'bearer',token:'synthetic'})};}});
 assert.equal(result.mode,'bearer');assert(command.exe.endsWith('powershell.exe'));assert.equal(command.options.windowsHide,true);assert.equal(command.options.timeout,15000);assert(!('PSModulePath'in command.options.env));
});
