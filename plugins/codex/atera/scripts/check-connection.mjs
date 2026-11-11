import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import { fileURLToPath } from 'node:url';
const entry = process.argv[2] || fileURLToPath(new URL('../dist/server.mjs',import.meta.url));
const client = new Client({name:'atera-connection-check',version:'0.1.0'});
const transport = new StdioClientTransport({command:process.execPath,args:[entry],stderr:'pipe'});
try {
  await client.connect(transport);
  const tools = await client.listTools();
  const result = await client.callTool({name:'connection_status',arguments:{}}, undefined, {timeout:60000});
  console.log(JSON.stringify({toolsDiscovered:tools.tools.length,connection:result},null,2));
  if (result.isError) process.exitCode=1;
} finally { await client.close(); }
