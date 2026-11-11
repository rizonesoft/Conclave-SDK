import test from 'node:test';
import assert from 'node:assert/strict';
import { AteraClient, pageResult, sanitize, scan } from '../src/client.js';

const json = x => new Response(JSON.stringify(x),{headers:{'content-type':'application/json'}});
const make = fetchImpl => new AteraClient({fetchImpl, tokenProvider:async()=> 'private-test-token', sleep:async()=>{}});

test('fixed origin, GET, Bearer auth, query encoding, no redirects, secret redaction',async()=>{
  const c=make(async(url,init)=>{
    assert.equal(url.origin,'https://api.atera.com'); assert.equal(url.pathname,'/api/v3/agents');
    assert.equal(url.searchParams.get('page'),'2'); assert.equal(init.method,'GET');
    assert.equal(init.headers.Authorization,'Bearer private-test-token'); assert.equal(init.redirect,'error');
    return json({items:[{Community:'private',Authentication:{password:'private'},WindowsSerialNumber:'key',Name:'private-test-token',URL:'https://u:p@example.org/path?token=s'}]});
  });
  const result=await c.get('/api/v3/agents',{page:2});
  assert.deepEqual(result.items,[{Name:'[REDACTED]',URL:'https://example.org/path'}]);
  await assert.rejects(c.get('https://attacker.test/'),/Unsupported/);
  await assert.rejects(c.get('/api/v3/tickets'),/Unsupported/);
});
test('401 is not retried and upstream response bodies never leak',async()=>{
  let count=0; const c=make(async()=>{count++;return new Response('private-test-token',{status:401});});
  await assert.rejects(c.get('/api/v3/alerts'),/rejected the token/);assert.equal(count,1);
});
test('429 honors Retry-After and retries with bounded attempts',async()=>{
  let count=0, clock=0;const waits=[];
  const c=new AteraClient({tokenProvider:async()=> 't',now:()=>clock,sleep:async ms=>{waits.push(ms);clock+=ms;},fetchImpl:async()=> ++count===1?new Response('',{status:429,headers:{'retry-after':'2'}}):json({ok:true})});
  assert.deepEqual(await c.get('/api/v3/alerts'),{ok:true});assert.deepEqual(waits,[2000]);assert.equal(count,2);
});
test('long rate limit never causes an early retry, including next call',async()=>{
  let count=0;const c=make(async()=>{count++;return new Response('',{status:429,headers:{'retry-after':'120'}});});
  await assert.rejects(c.get('/api/v3/alerts'),/120 seconds/);
  await assert.rejects(c.get('/api/v3/alerts'),/rate limited/);assert.equal(count,1);
});
test('network and malformed JSON errors are safe',async()=>{
  await assert.rejects(make(async()=>{throw new Error('secret');}).get('/api/v3/agents'),/timed out/);
  await assert.rejects(make(async()=>new Response('<html>secret')).get('/api/v3/agents'),/invalid or oversized/);
});
test('pagination ignores upstream links and reports incomplete coverage',async()=>{
  const c={get:async(path,q)=>({items:[{AgentID:q.page}],totalPages:3,totalItemCount:3,nextLink:'https://evil.test'})};
  const partial=await scan(c,'/api/v3/agents',{},2);assert.equal(partial.complete,false);assert.equal(partial.nextPage,3);assert.equal(partial.items.length,2);
  const all=await scan(c,'/api/v3/agents',{},5);assert.equal(all.complete,true);assert.equal(all.pagesFetched,3);
  assert.throws(()=>pageResult({},1),/pagination/);
  assert.equal(pageResult({items:[],totalPages:0,totalItemCount:0},1).hasMore,false);
});
test('nested sensitive fields are omitted',()=>assert.deepEqual(sanitize({nested:{Privacy:'s',OfficeSerialNumber:'s',ok:true}}),{nested:{ok:true}}));

test('credentials stay in memory for five minutes and refresh after expiration or 401',async()=>{
  let tokens=0, clock=0, rejected=false;
  const c=new AteraClient({now:()=>clock,sleep:async ms=>{clock+=ms;},tokenProvider:async()=>{tokens++;return 't';},fetchImpl:async()=>rejected?new Response('',{status:401}):json({ok:true})});
  await c.get('/api/v3/agents');await c.get('/api/v3/agents');assert.equal(tokens,1);
  clock+=300001;await c.get('/api/v3/agents');assert.equal(tokens,2);
  rejected=true;await assert.rejects(c.get('/api/v3/agents'),/rejected/);
  rejected=false;await c.get('/api/v3/agents');assert.equal(tokens,3);
});
