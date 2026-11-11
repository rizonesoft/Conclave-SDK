import {Client} from '@modelcontextprotocol/sdk/client/index.js';
import {StdioClientTransport} from '@modelcontextprotocol/sdk/client/stdio.js';
import {fileURLToPath} from 'node:url';
const client=new Client({name:'bunny-check',version:'1'});
try{
 await client.connect(new StdioClientTransport({command:process.execPath,args:['--import',new URL('./no-1password.mjs',import.meta.url).href,process.argv[2] || fileURLToPath(new URL('../dist/server.mjs',import.meta.url))],env:{...process.env,BUNNY_TEST_IMPORT:'0'}}));
 const list=await client.listTools();if(list.tools.length!==18)throw new Error('Unexpected tool count');
 const result=await client.callTool({name:'connection_status',arguments:{}});if(result.isError)throw new Error('Bunny connection check failed');
 console.log(JSON.stringify({tools:list.tools.length,connection:JSON.parse(result.content[0].text),writesPerformed:0,onePasswordExecutionBlocked:true}));
}finally{await client.close();}
