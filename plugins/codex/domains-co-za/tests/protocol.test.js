import test from 'node:test';
import assert from 'node:assert/strict';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
test('built MCP initializes, lists tools, previews without credentials and guards execution',async()=>{
 const transport=new StdioClientTransport({command:process.execPath,args:['dist/server.mjs'],env:{...process.env,DOMAINS_TEST_IMPORT:'0'}});
 const c=new Client({name:'protocol-test',version:'1.0.0'});
 try{
  await c.connect(transport);const list=await c.listTools();assert.equal(list.tools.length,23);
  assert.equal(list.tools.find(t=>t.name==='execute_change').annotations.readOnlyHint,false);
  const p=await c.callTool({name:'prepare_renew_domain',arguments:{sld:'example',tld:'co.za',period:1}});assert(!p.isError);const preview=JSON.parse(p.content[0].text);assert.equal(preview.executed,false);
  const bad=await c.callTool({name:'execute_change',arguments:{changeId:preview.changeId,confirmedDomain:'other.co.za'}});assert.equal(bad.isError,true);
 }finally{await c.close();}
});
