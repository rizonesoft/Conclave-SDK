import test from 'node:test';
import assert from 'node:assert/strict';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
test('built MCP initializes, lists tools, previews without credentials and guards execution',async()=>{
 const transport=new StdioClientTransport({command:process.execPath,args:['dist/server.mjs'],env:{...process.env,BUNNY_TEST_IMPORT:'0'}});
 const c=new Client({name:'protocol-test',version:'1.0.0'});
 try{
  await c.connect(transport);const list=await c.listTools();assert.equal(list.tools.length,16);
  assert.equal(list.tools.find(t=>t.name==='execute_change').annotations.readOnlyHint,false);
  assert(list.tools.filter(t=>t.name!=='execute_change').every(t=>t.annotations.readOnlyHint===true));
  const p=await c.callTool({name:'prepare_add_dns_zone',arguments:{domain:'example.com'}});assert(!p.isError);const preview=JSON.parse(p.content[0].text);assert.equal(preview.executed,false);
  // The MCP SDK strips unknown fields before the handler runs, so they can never reach the request.
  const extra=await c.callTool({name:'prepare_add_dns_zone',arguments:{domain:'example.com',url:'https://evil.invalid'}});
  assert.deepEqual(JSON.parse(extra.content[0].text).request.body,{Domain:'example.com'});
  const bad=await c.callTool({name:'execute_change',arguments:{changeId:preview.changeId,confirmedTarget:'other.com'}});assert.equal(bad.isError,true);
 }finally{await c.close();}
});
