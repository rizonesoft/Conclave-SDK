import {test} from 'node:test';
import assert from 'node:assert/strict';
import {spawn,spawnSync} from 'node:child_process';
import {mkdtempSync,writeFileSync,readFileSync,rmSync,existsSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {fileURLToPath} from 'node:url';

test('approval probe teardown ends the server and its descendant',async()=>{
 const scratch=process.platform==='win32'?'R:/scratch':'/mnt/r/scratch';
 const dir=mkdtempSync(join(existsSync(scratch)?scratch:tmpdir(),'approval-probe-'));
 const pidFile=join(dir,'pid');
 const fixture=join(dir,'server.mjs');
 writeFileSync(fixture,`
 import {spawn} from 'node:child_process';
 import {writeFileSync} from 'node:fs';
 import {createInterface} from 'node:readline';
 const child=spawn(process.execPath,['-e','setTimeout(()=>{},15000)'],{stdio:'ignore',windowsHide:true});
 writeFileSync(${JSON.stringify(pidFile)},String(child.pid));
 createInterface({input:process.stdin}).on('line',line=>{
  const m=JSON.parse(line);if(!m.id)return;
  const result=m.method==='initialize'?{instructions:'agent may approve. After execution',serverInfo:{name:'fixture',version:'1'}}:{tools:[{name:'execute_change',annotations:{readOnlyHint:false},description:'verify afterward'}]};
  console.log(JSON.stringify({jsonrpc:'2.0',id:m.id,result}));
 });
 `);
 const child=spawn(process.execPath,[fileURLToPath(new URL('./check-approval-policy.mjs',import.meta.url)),fixture],{stdio:'ignore',windowsHide:true,detached:process.platform!=='win32'});
 let descendant;
 try{
  const code=await new Promise((resolve,reject)=>{
   const timer=setTimeout(()=>reject(Error('probe did not finish')),5000);
   child.once('error',error=>{clearTimeout(timer);reject(error)});
   child.once('exit',code=>{clearTimeout(timer);resolve(code)});
  });
  assert.equal(code,0);
  descendant=Number(readFileSync(pidFile,'utf8'));
  // A reaped process (or Linux zombie pending init's reap) cannot keep writing.
  let running=true;
  for(let attempt=0;attempt<50 && running;attempt++){
  try{
   process.kill(descendant,0);
   if(process.platform==='linux')running=!readFileSync('/proc/'+descendant+'/stat','utf8').match(/.*\) (.) /s)?.[1]?.includes('Z');
  }catch(error){if(!['ESRCH','ENOENT'].includes(error.code))throw error;running=false}
  if(running)await new Promise(resolve=>setTimeout(resolve,20));
  }
  assert.equal(running,false);
 }finally{
  if(process.platform==='win32')spawnSync('taskkill',['/PID',String(child.pid),'/T','/F'],{stdio:'ignore',windowsHide:true});
  else try{process.kill(-child.pid,'SIGKILL')}catch(error){if(error.code!=='ESRCH')throw error}
  try{descendant??=Number(readFileSync(pidFile,'utf8'));process.kill(descendant,'SIGKILL')}catch(error){if(!['ESRCH','ENOENT'].includes(error.code))throw error}
  rmSync(dir,{recursive:true,force:true});
 }
});

async function probeFixture(body, live=false, inspect=()=>{}) {
 const scratch=process.platform==='win32'?'R:/scratch':'/mnt/r/scratch';
 const dir=mkdtempSync(join(existsSync(scratch)?scratch:tmpdir(),'approval-case-'));
 const fixture=join(dir,'server.mjs');
 writeFileSync(fixture,body);
 const child=spawn(process.execPath,[fileURLToPath(new URL('./check-approval-policy.mjs',import.meta.url)),fixture,...(live?['--live']:[])],{stdio:['ignore','pipe','ignore'],windowsHide:true,detached:process.platform!=='win32'});
 let output='';
 child.stdout.on('data',chunk=>{output=(output+chunk.toString()).slice(0,4096)});
 try {
  return await new Promise((resolve,reject)=>{
   const timer=setTimeout(()=>reject(Error('probe did not finish')),5000);
   child.once('error',error=>{clearTimeout(timer);reject(error)});
   child.once('close',code=>{clearTimeout(timer);try{inspect(output);resolve(code)}catch(error){reject(error)}});
  });
 } finally {
  if(process.platform==='win32')spawnSync('taskkill',['/PID',String(child.pid),'/T','/F'],{stdio:'ignore',windowsHide:true});
  else try{process.kill(-child.pid,'SIGKILL')}catch(error){if(error.code!=='ESRCH')throw error}
  rmSync(dir,{recursive:true,force:true});
 }
}
function server(tools,health={connected:true},cursor=undefined) {
 return `import {createInterface} from 'node:readline';
 const timer=setTimeout(()=>process.exit(2),4000);
 createInterface({input:process.stdin}).on('line',line=>{
  const m=JSON.parse(line);if(!m.id)return;
  const result=m.method==='initialize'?{instructions:'agent may approve. After execution',serverInfo:{name:'fixture',version:'1'}}:m.method==='tools/list'?{tools:${JSON.stringify(tools)},nextCursor:${JSON.stringify(cursor)}}:{structuredContent:${JSON.stringify(health)}};
  console.log(JSON.stringify({jsonrpc:'2.0',id:m.id,result}));
 });`;
}
const writeTool={name:'execute_change',annotations:{readOnlyHint:false},description:'verify afterward'};
test('early server exit fails promptly',async()=>assert.equal(await probeFixture('process.exit(0)'),1));
test('empty inventory cannot pass approval verification',async()=>assert.equal(await probeFixture(server([])),1));
test('unrecognized mutating tools require approval guidance',async()=>assert.equal(await probeFixture(server([writeTool,{name:'new_write',annotations:{readOnlyHint:false}}])),1));
test('empty live site inventory is not connected',async()=>assert.equal(await probeFixture(server([writeTool],{sites:[]}),true),1));
test('valid approval metadata and live connection pass',async()=>assert.equal(await probeFixture(server([writeTool]),true),0));

test('read-only inventory passes without claiming write verification',async()=>assert.equal(await probeFixture(server([{name:'read',annotations:{readOnlyHint:true}}]),false,output=>assert.equal(JSON.parse(output).taskScopedApprovalAndVerification,null)),0));
test('local preview metadata is distinct from provider execution',async()=>assert.equal(await probeFixture(server([writeTool,{name:'prepare_change',annotations:{readOnlyHint:false,destructiveHint:false},description:'Create a preview'}])),0));

test('non-object JSON diagnostics do not crash the probe',async()=>assert.equal(await probeFixture('console.log("null");\n'+server([writeTool])),0));
test('paginated inventory fails closed',async()=>assert.equal(await probeFixture(server([writeTool],{},'next')),1));
test('preview without execution gateway fails',async()=>assert.equal(await probeFixture(server([{name:'prepare_change',annotations:{readOnlyHint:false,destructiveHint:false},description:'Create a preview'}])),1));
