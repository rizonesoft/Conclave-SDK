import test from 'node:test';
import assert from 'node:assert/strict';
process.env.BUNNY_TEST_IMPORT='1';
const {Changes}=await import('../src/server.js');
const zone={Id:7,Domain:'example.com',Records:[{Id:11,Type:0,Name:'www',Value:'192.0.2.1',Ttl:300},{Id:12,Type:11,Name:'edge',Value:'',Ttl:300},{Id:9007199254740991,Type:3,Name:'big',Value:'v',Ttl:300}]};
const fake=(z=zone)=>{const calls=[];return{calls,request:async(method,path,options={})=>{calls.push({method,path,...options});if(method==='GET'&&path==='/dnszone/7')return typeof z==='function'?z():z;if(method==='GET'&&path==='/pullzone/3')return{Id:3,Name:'cdn-zone'};return{};}};};
const writes=calls=>calls.filter(c=>c.method!=='GET');
test('preview reads but never writes; wrong target cannot execute; preview is single use',async()=>{
 const client=fake();const c=new Changes(client);
 const p=await c.prepare('add_dns_record',{zoneId:7,type:'TXT',name:'_verify',value:'token-value',ttl:300});
 assert.equal(p.target,'example.com');assert.equal(p.executed,false);assert.equal(writes(client.calls).length,0);
 assert.deepEqual(p.request,{method:'PUT',path:'/dnszone/7/records',body:{Type:3,Name:'_verify',Value:'token-value',Ttl:300}});
 await assert.rejects(c.execute(p.changeId,'other.com'),/does not match/);assert.equal(writes(client.calls).length,0);
 await c.execute(p.changeId,'example.com');assert.equal(writes(client.calls).length,1);
 await assert.rejects(c.execute(p.changeId,'example.com'),/missing/);assert.equal(writes(client.calls).length,1);
});
test('update and delete show the current record and refuse unknown record IDs',async()=>{
 const client=fake();const c=new Changes(client);
 const u=await c.prepare('update_dns_record',{zoneId:7,recordId:11,type:'A',name:'www',value:'192.0.2.2',ttl:300});
 assert.equal(u.current.Value,'192.0.2.1');assert.equal(u.current.TypeName,'A');assert.equal(u.request.body.Id,11);assert.equal(u.request.path,'/dnszone/7/records/11');
 const d=await c.prepare('delete_dns_record',{zoneId:7,recordId:11});assert.equal(d.request.method,'DELETE');assert.equal(d.current.Name,'www');
 await assert.rejects(c.prepare('delete_dns_record',{zoneId:7,recordId:99}),/not found/);
});
test('uncertain errors consume the preview; expired previews do not execute',async()=>{
 let now=0,sent=0;const c=new Changes({request:async(m,p)=>{if(m==='GET')return{Id:3,Name:'cdn-zone'};sent++;throw new Error('unknown');}},{now:()=>now});
 const p=await c.prepare('purge_pull_zone',{pullZoneId:3});assert.equal(p.target,'cdn-zone');
 await assert.rejects(c.execute(p.changeId,'cdn-zone'),/unknown/);await assert.rejects(c.execute(p.changeId,'cdn-zone'),/missing/);assert.equal(sent,1);
 const p2=await c.prepare('purge_pull_zone',{pullZoneId:3});now=600001;await assert.rejects(c.execute(p2.changeId,'cdn-zone'),/expired/);assert.equal(sent,1);
});
test('read-only record types cannot be updated or deleted; int64 IDs are accepted',async()=>{
 const c=new Changes(fake());
 await assert.rejects(c.prepare('update_dns_record',{zoneId:7,recordId:12,type:'A',name:'edge',value:'192.0.2.9',ttl:300}),/Script records are read-only/);
 await assert.rejects(c.prepare('delete_dns_record',{zoneId:7,recordId:12}),/read-only/);
 assert.equal((await c.prepare('delete_dns_record',{zoneId:7,recordId:9007199254740991})).current.Name,'big');
});
test('update and delete send nothing when the record changed after the preview',async()=>{
 let value='192.0.2.1';const client=fake(()=>({...zone,Records:[{Id:11,Type:0,Name:'www',Value:value,Ttl:300}]}));const c=new Changes(client);
 const p=await c.prepare('delete_dns_record',{zoneId:7,recordId:11});value='192.0.2.99';
 await assert.rejects(c.execute(p.changeId,'example.com'),/changed after the preview/);assert.equal(writes(client.calls).length,0);
 await assert.rejects(c.execute(p.changeId,'example.com'),/missing/);
 const q=await c.prepare('delete_dns_record',{zoneId:7,recordId:11});await c.execute(q.changeId,'example.com');assert.equal(writes(client.calls).length,1);
});
test('full purge sends the required empty body',async()=>{
 const client=fake();const c=new Changes(client);const p=await c.prepare('purge_pull_zone',{pullZoneId:3});
 assert.deepEqual(p.request.body,{});await c.execute(p.changeId,'cdn-zone');assert.deepEqual(writes(client.calls)[0].body,{});
});
test('strict fields when prepare is called directly, and per-type requirements',async()=>{
 const c=new Changes(fake());
 await assert.rejects(c.prepare('add_dns_record',{zoneId:7,type:'A',name:'',value:'192.0.2.1',ttl:300,url:'https://evil.invalid'}),/Invalid/);
 await assert.rejects(c.prepare('add_dns_record',{zoneId:7,type:'MX',name:'',value:'mail.example.com',ttl:300}),/priority is required/);
 await assert.rejects(c.prepare('add_dns_record',{zoneId:7,type:'SRV',name:'_sip._tcp',value:'sip.example.com',ttl:300,priority:1}),/weight is required/);
 await assert.rejects(c.prepare('add_dns_record',{zoneId:7,type:'CAA',name:'',value:'letsencrypt.org',ttl:300,flags:0}),/tag is required/);
 await assert.rejects(c.prepare('add_dns_record',{zoneId:7,type:'Script',name:'',value:'x',ttl:300}),/Invalid/);
 await assert.rejects(c.prepare('add_dns_record',{zoneId:7,type:'TXT',name:'a\nb',value:'x',ttl:300}),/Invalid/);
 await assert.rejects(c.prepare('add_dns_zone',{domain:'not a domain'}),/Invalid/);
 await assert.rejects(c.prepare('purge_url',{url:'ftp://example.com/a'}),/Invalid/);
 const z=await c.prepare('add_dns_zone',{domain:'Uptime247.co.za'});assert.equal(z.target,'uptime247.co.za');
 const u=await c.prepare('purge_url',{url:'https://cdn.example.com/assets/*'});assert.equal(u.target,'cdn.example.com');assert.deepEqual(u.request.query,{url:'https://cdn.example.com/assets/*',async:false});
});
