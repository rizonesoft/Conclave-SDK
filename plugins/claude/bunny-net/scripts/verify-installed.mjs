import {Client} from '@modelcontextprotocol/sdk/client/index.js';
import {StdioClientTransport} from '@modelcontextprotocol/sdk/client/stdio.js';
import {join} from 'node:path';
const root=process.argv[2];if(!root)throw new Error('Pass installed plugin directory.');
const client=new Client({name:'rizonetech-install-check',version:'1.0.0'});
try {
 await client.connect(new StdioClientTransport({command:process.execPath,args:['--import',new URL('./no-1password.mjs',import.meta.url).href,join(root,'dist/server.mjs')],env:{...process.env,BUNNY_TEST_IMPORT:'0'}}));
 const {tools}=await client.listTools();if(tools.length!==16)throw new Error('Unexpected tool count.');
 const r=await client.callTool({name:'connection_status',arguments:{}});if(r.isError)throw new Error(r.content[0].text);
 const zones=await client.callTool({name:'list_dns_zones',arguments:{page:1,perPage:5}});if(zones.isError)throw new Error(zones.content[0].text);
 console.log(JSON.stringify({installedTools:tools.length,connection:JSON.parse(r.content[0].text),dnsZonePaging:JSON.parse(zones.content[0].text).paging,onePasswordExecutionBlocked:true}));
} finally {await client.close();}
