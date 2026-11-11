import test from 'node:test';
import assert from 'node:assert/strict';
import { BunnyClient,scrub } from '../src/client.js';
import { loadCredentials } from '../src/credentials.js';
const KEY='00000000-test-key-0000-000000000000';
const credentials=async()=>({mode:'apikey',apiKey:KEY});
const json=(data,init={})=>new Response(JSON.stringify(data),{headers:{'content-type':'application/json'},...init});
test('AccessKey header only, no redirects, query encoding and JSON bodies',async()=>{
 const calls=[];const c=new BunnyClient({credentials,fetchImpl:async(u,o)=>{calls.push({url:String(u),...o});return json({Items:[],CurrentPage:1,TotalItems:0,HasMoreItems:false});}});
 await c.request('GET','/dnszone',{query:{search:'a&b',page:1,perPage:5,skip:undefined}});
 assert.equal(calls[0].headers.AccessKey,KEY);assert.equal(calls[0].redirect,'error');assert(!calls[0].url.includes(KEY));
 assert(calls[0].url.includes('search=a%26b'));assert(!calls[0].url.includes('skip'));
 await c.request('PUT','/dnszone/7/records',{body:{Type:0,Name:'',Value:'192.0.2.1',Ttl:300}});
 assert.equal(calls[1].headers['Content-Type'],'application/json');assert.deepEqual(JSON.parse(calls[1].body),{Type:0,Name:'',Value:'192.0.2.1',Ttl:300});
});
test('unsupported endpoints are refused before credentials load',async()=>{
 let reads=0;const c=new BunnyClient({credentials:async()=>{reads++;return credentials();}});
 for(const [m,p] of [['DELETE','/pullzone/1'],['POST','/pullzone/1/resetSecurityKey'],['GET','/apikey'],['POST','/storagezone/1/resetPassword'],['GET','/dnszone/1/../apikey']])await assert.rejects(c.request(m,p),/Unsupported/);
 assert.equal(reads,0);
});
test('204 responses become empty objects; zone export returns text whatever its content type',async()=>{
 for(const type of ['text/plain','application/json']){
  const c=new BunnyClient({credentials,fetchImpl:async u=>String(u).endsWith('/export')?new Response('$ORIGIN example.com.',{headers:{'content-type':type}}):new Response(null,{status:204})});
  assert.deepEqual(await c.request('DELETE','/dnszone/1/records/2'),{});
  assert.deepEqual(await c.request('GET','/dnszone/1/export'),{text:'$ORIGIN example.com.'});
 }
});
test('GET retries once; writes never retry and outcome-unknown is reported',async()=>{
 let n=0;const c=new BunnyClient({credentials,sleep:async()=>{},fetchImpl:async()=>{n++;return n===1?new Response('busy',{status:503}):json({});}});
 await c.request('GET','/pullzone');assert.equal(n,2);
 n=0;const w=new BunnyClient({credentials,fetchImpl:async()=>{n++;return new Response('busy',{status:503});}});
 await assert.rejects(w.request('POST','/purge',{query:{url:'https://example.com/a'}}),/not retried/);assert.equal(n,1);
 n=0;const lost=new BunnyClient({credentials,fetchImpl:async()=>{n++;throw new Error('reset');}});
 await assert.rejects(lost.request('DELETE','/dnszone/1/records/2'),/outcome is unknown/);assert.equal(n,1);
});
test('provider error messages are included but redact the API key',async()=>{
 const c=new BunnyClient({credentials,fetchImpl:async()=>json({ErrorKey:'x',Message:'bad key '+KEY},{status:400})});
 await assert.rejects(c.request('PUT','/dnszone/1/records',{body:{}}),e=>e.message.includes('HTTP 400: bad key [redacted]')&&!e.message.includes(KEY));
 const u=new BunnyClient({credentials,fetchImpl:async()=>new Response('',{status:401})});
 await assert.rejects(u.request('GET','/pullzone'),/configure\.ps1/);
});
test('responses drop credential-bearing fields and redact the key anywhere',async()=>{
 const zone={Id:1,Name:'cdn',ZoneSecurityKey:'s1',AWSSigningKey:'s2',AWSSigningSecret:'s3',LogForwardingToken:'s4',OptimizerStaticHtmlWordPressBypassCookie:'s5',
  Hostnames:[{Value:'cdn.example.com',Certificate:'pem',CertificateKey:'pem-key',CertificateKeyType:0,HasCertificate:true}],
  EdgeRules:[{Guid:'g',ActionType:5,ActionParameter1:'Authorization',ActionParameter2:'Bearer origin-secret',ExtraActions:[{ActionParameter1:'x'}],Triggers:[{Type:1,Parameter1:'X-Preview-Secret',PatternMatches:['gate-secret']}],Description:'origin auth',Enabled:true}],
  OriginUrl:'https://user:origin-pass@origin.example.com/app?token=query-secret&k='+KEY};
 const storage={Id:2,Name:'files',Password:'p1',ReadOnlyPassword:'p2',PullZones:[{Id:1,ZoneSecurityKey:'s6'}]};
 const record={Id:3,Type:3,Value:'v',EnviromentalVariables:[{Name:'TOKEN',Value:'s7'}]};
 const out=JSON.stringify(scrub([zone,storage,record],[KEY]));
 for(const secret of ['s1','s2','s3','s4','s5','s6','s7','pem','origin-secret','gate-secret','origin-pass','query-secret','p1','p2',KEY])assert(!out.includes(secret),secret+' leaked');
 const back=JSON.parse(out);assert.equal(back[0].Hostnames[0].CertificateKeyType,0);assert.equal(back[0].EdgeRules[0].Description,'origin auth');assert.equal(back[0].Hostnames[0].HasCertificate,true);
 assert.equal(back[0].EdgeRules[0].Triggers[0].Parameter1,'X-Preview-Secret');assert.equal(back[0].OriginUrl,'https://origin.example.com/app [credentials or query removed]');
 assert.equal(scrub({OriginUrl:'https://origin.example.com/'}).OriginUrl,'https://origin.example.com/');
});
test('DPAPI mode only; no 1Password fallback or environment key mode',async()=>{
 let executions=0;const execImpl=async()=>{executions++;throw new Error();};
 await assert.rejects(loadCredentials({platform:'win32',env:{BUNNY_API_KEY:'ignored'},readFileImpl:async()=>{throw new Error();},execImpl}),/not configured/);
 await assert.rejects(loadCredentials({platform:'win32',readFileImpl:async()=>JSON.stringify({authMode:'1password'}),execImpl}),/No 1Password fallback/);
 await assert.rejects(loadCredentials({platform:'linux',env:{BUNNY_API_KEY:KEY},execImpl}),/require Windows/);
 assert.equal(executions,0);
});
test('runtime invokes only hidden bounded Windows decryption and validates the key shape',async()=>{
 let command;const run=stdout=>loadCredentials({platform:'win32',env:{LOCALAPPDATA:'C:/isolated',SystemRoot:'C:/Windows',PSModulePath:'unsafe'},readFileImpl:async()=>JSON.stringify({authMode:'windows-dpapi'}),execImpl:async(exe,args,options)=>{command={exe,args,options};return{stdout};}});
 assert.equal((await run(JSON.stringify({mode:'apikey',apiKey:KEY}))).apiKey,KEY);
 assert(command.exe.endsWith('powershell.exe'));assert.equal(command.options.windowsHide,true);assert.equal(command.options.timeout,15000);assert(!('PSModulePath'in command.options.env));
 await assert.rejects(run(JSON.stringify({mode:'apikey',apiKey:'short'})),/Cannot unlock/);
 await assert.rejects(run(JSON.stringify({mode:'apikey',apiKey:KEY+'\r\nX-Evil: 1'})),/Cannot unlock/);
});
