import {Client} from '@modelcontextprotocol/sdk/client/index.js';
import {StdioClientTransport} from '@modelcontextprotocol/sdk/client/stdio.js';
import {fileURLToPath} from 'node:url';
const root=fileURLToPath(new URL('../',import.meta.url));
const target=process.argv[2]||root+'dist/server.mjs';
const c=new Client({name:'pressable-verification',version:'0.1.0'});
const t=new StdioClientTransport({command:process.execPath,args:['--import',new URL('./no-1password.mjs',import.meta.url).href,target],stderr:'pipe',env:process.env});
try{await c.connect(t,{timeout:30000});const tools=(await c.listTools()).tools;if(tools.length!==6)throw Error();const result=await c.callTool({name:'connection_status',arguments:{}},undefined,{timeout:90000});if(result.isError){console.error(result.content[0].text);throw Error();}const status=JSON.parse(result.content[0].text);if(status.connected!==true)throw Error();console.log(JSON.stringify({tools:tools.length,...status}));}catch(e){console.error('Pressable connection check failed: '+e.name+' '+e.message);process.exitCode=1;}finally{await c.close();}