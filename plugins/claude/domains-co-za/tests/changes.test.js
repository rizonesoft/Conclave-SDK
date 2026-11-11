import test from 'node:test';
import assert from 'node:assert/strict';
process.env.DOMAINS_TEST_IMPORT='1';
const {Changes}=await import('../src/server.js');
const params={sld:'example',tld:'co.za',period:1};
test('preview is side effect free; wrong domain cannot execute; successful preview single use',async()=>{
 const calls=[];const c=new Changes({request:async(...a)=>{calls.push(a);return{intReturnCode:2};}});
 const p=c.prepare('renew_domain',params);assert.equal(calls.length,0);
 await assert.rejects(c.execute(p.changeId,'wrong.co.za'),/does not match/);assert.equal(calls.length,0);
 const r=await c.execute(p.changeId,'example.co.za');assert.equal(r.pending,true);assert.equal(calls.length,1);
 await assert.rejects(c.execute(p.changeId,'example.co.za'),/missing/);
});
test('uncertain errors consume preview; expired previews do not execute',async()=>{
 let now=0,calls=0;const c=new Changes({request:async()=>{calls++;throw new Error('unknown');}},{now:()=>now});
 const p=c.prepare('renew_domain',params);await assert.rejects(c.execute(p.changeId,'example.co.za'),/unknown/);
 await assert.rejects(c.execute(p.changeId,'example.co.za'),/missing/);assert.equal(calls,1);
 const p2=c.prepare('renew_domain',params);now=600001;await assert.rejects(c.execute(p2.changeId,'example.co.za'),/expired/);assert.equal(calls,1);
});
test('strict fields, domain validation and explicit auto-renew guard against accidental changes',()=>{
 const c=new Changes({});
 assert.throws(()=>c.prepare('renew_domain',{...params,url:'https://evil.invalid'}),/Invalid/);
 assert.throws(()=>c.prepare('renew_domain',{...params,sld:'a/b'}),/Invalid/);
 assert.throws(()=>c.prepare('set_autorenew',{sld:'example',tld:'co.za'}),/Invalid/);
 assert.equal(c.prepare('set_autorenew',{sld:'example',tld:'co.za',autorenew:false}).parameters.autorenew,false);
});
