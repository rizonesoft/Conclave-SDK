import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StreamableHTTPClientTransport } from '@modelcontextprotocol/sdk/client/streamableHttp.js';
import { loadToken } from '../src/credentials.js';
import { writeFile } from 'node:fs/promises';
const client = new Client({name:'rizonetech-pressable-discovery',version:'0.1.0'});
try {
 const token=await loadToken();
 const transport=new StreamableHTTPClientTransport(new URL('https://mcp.pressable.com'),{requestInit:{headers:{Authorization:`Bearer ${token}`},redirect:'error'}});
 await client.connect(transport,{timeout:30000});
 const tools=[];let cursor;
 do {const page=await client.listTools(cursor?{cursor}:{},{timeout:30000});tools.push(...page.tools);cursor=page.nextCursor;if(tools.length>1000)throw Error('Discovery limit');}while(cursor);
 await writeFile(new URL('../upstream-tools.json',import.meta.url),JSON.stringify(tools,null,2)+'\n');
  const operations=await client.callTool({name:'discover_tools',arguments:{}},undefined,{timeout:30000});
 await writeFile(new URL('../upstream-operations.json',import.meta.url),JSON.stringify(operations,null,2)+'\n');
 console.log('Upstream tool catalogue saved for explicit developer review.');
} catch { console.error('Pressable discovery failed; check encrypted credential and provider connectivity.');process.exitCode=1; }
finally{await client.close();}