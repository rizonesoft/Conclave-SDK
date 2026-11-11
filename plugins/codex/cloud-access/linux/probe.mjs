import {spawn} from 'node:child_process';import {createInterface} from 'node:readline';
const child=spawn(process.execPath,[process.argv[2]],{stdio:['pipe','pipe','pipe'],env:process.env});
let id=0;const waiting=new Map();const lines=createInterface({input:child.stdout});
lines.on('line',line=>{try{const m=JSON.parse(line);if(waiting.has(m.id)){const w=waiting.get(m.id);waiting.delete(m.id);m.error?w.reject(new Error('MCP request failed')):w.resolve(m.result);}}catch{}});
const request=(method,params)=>new Promise((resolve,reject)=>{const key=++id;waiting.set(key,{resolve,reject});child.stdin.write(JSON.stringify({jsonrpc:'2.0',id:key,method,params})+'\n');});
const timeout=setTimeout(()=>{child.kill();process.exit(1)},25000);
try{await request('initialize',{protocolVersion:'2024-11-05',capabilities:{},clientInfo:{name:'rizonetech-linux-check',version:'1'}});
child.stdin.write(JSON.stringify({jsonrpc:'2.0',method:'notifications/initialized'})+'\n');
const tools=await request('tools/list',{});if(tools.tools.length!==Number(process.argv[3]))throw new Error('Tool count mismatch');
const r=await request('tools/call',{name:'connection_status',arguments:{}});if(r.isError)throw new Error('Provider connection failed');
console.log(JSON.stringify({tools:tools.tools.length,providerConnected:true,credentialStore:'systemd',writesPerformed:0}));
}catch(e){console.error(e.message);process.exitCode=1}finally{clearTimeout(timeout);child.kill();lines.close();}
