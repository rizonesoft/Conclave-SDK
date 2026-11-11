import {spawn} from 'node:child_process';import {createInterface} from 'node:readline';
const child=spawn(process.execPath,[process.argv[2]],{stdio:['pipe','pipe','pipe'],windowsHide:true,env:process.env});
const pending=new Map();let id=0;const lines=createInterface({input:child.stdout});child.stderr.resume();
lines.on('line',s=>{try{const m=JSON.parse(s),p=pending.get(m.id);if(p){pending.delete(m.id);m.error?p.reject(Error('MCP error')):p.resolve(m.result)}}catch{}});
const req=(method,params)=>new Promise((resolve,reject)=>{pending.set(++id,{resolve,reject});child.stdin.write(JSON.stringify({jsonrpc:'2.0',id,method,params})+'\n')});
const timeout=setTimeout(()=>{child.kill();process.exit(1)},180000);
try{
 const init=await req('initialize',{protocolVersion:'2024-11-05',capabilities:{},clientInfo:{name:'approval-policy-check',version:'1'}});
 if((!init.instructions?.includes('agent may approve')||!init.instructions?.includes('After execution')))throw Error('Approval instructions missing');
 child.stdin.write(JSON.stringify({jsonrpc:'2.0',method:'notifications/initialized'})+'\n');
 const {tools}=await req('tools/list',{});
 const writes=tools.filter(t=>t.name==='execute_change'||['propose_memory_write','create_approval_request'].includes(t.name));
 for(const t of writes)if(t.annotations?.readOnlyHint!==false||!t.description.includes('verify afterward'))throw Error('Write approval guidance missing');
 let connected;
 if(process.argv.includes('--live')){const name=tools.some(t=>t.name==='connection_status')?'connection_status':'conclave_mcp_health';const result=await req('tools/call',{name,arguments:{}});if(result.isError)throw Error('Read-only connection check failed');const d=result.structuredContent??JSON.parse(result.content.filter(c=>c.type==='text').map(c=>c.text).join(''));connected=d.connected??d.ok??d.sites?.every(s=>s.connected);if(connected!==true)throw Error('Connection not ready');}
 console.log(JSON.stringify({name:init.serverInfo.name,version:init.serverInfo.version,tools:tools.length,taskScopedApprovalAndVerification:true,writeTools:writes.map(t=>t.name),connected,writesPerformed:0}));
}catch{console.error('Approval-policy check failed; no provider data printed');process.exitCode=1}finally{clearTimeout(timeout);child.stdin.end();lines.close();setTimeout(()=>child.kill(),3000).unref();}
