import test from 'node:test';
import assert from 'node:assert/strict';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import { fileURLToPath } from 'node:url';
import {mkdtempSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';

test('bundled stdio server initializes, discovers ten readonly tools, validates inputs and reports missing auth', async()=>{
  const isolatedConfig=mkdtempSync(join(tmpdir(),'atera-test-'));
  const client=new Client({name:'test',version:'1.0.0'});
  const transport=new StdioClientTransport({command:process.execPath,args:[fileURLToPath(new URL('../dist/server.mjs',import.meta.url))],env:{...process.env,LOCALAPPDATA:isolatedConfig,ATERA_API_TOKEN:'',ATERA_TOKEN_REFERENCE:'invalid-reference',ATERA_TEST_IMPORT:'0'},stderr:'pipe'});
  try {
    await client.connect(transport);
    const {tools}=await client.listTools();assert.equal(tools.length,10);assert.ok(tools.every(t=>t.annotations.readOnlyHint));
    const bad=await client.callTool({name:'list_agents',arguments:{page:0}});assert.equal(bad.isError,true);
    const noAuth=await client.callTool({name:'connection_status',arguments:{}});assert.equal(noAuth.isError,true);assert.match(noAuth.content[0].text,/reference/);
  } finally {await client.close();rmSync(isolatedConfig,{recursive:true,force:true});}
});
