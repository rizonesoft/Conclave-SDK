import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { InMemoryTransport } from '@modelcontextprotocol/sdk/inMemory.js';
process.env.ATERA_TEST_IMPORT='1';
const {createServer}=await import('../src/server.js');
const spec=JSON.parse(readFileSync(new URL('../docs/openapi.json',import.meta.url)));

test('tool routing agrees with the saved Atera OpenAPI paths, parameters and read methods', async()=>{
  const requests=[];
  const server=createServer({get:async(path,query={})=>{requests.push({path,query});return {items:[{Online:false,Monitored:false,Severity:'Critical'}],page:query.page,totalPages:3,totalItemCount:150};}});
  const client=new Client({name:'route-test',version:'1.0.0'});
  const [a,b]=InMemoryTransport.createLinkedPair();
  await Promise.all([server.connect(a),client.connect(b)]);
  try {
    const cases=[
      ['list_agents',{customerId:17,page:2},'/api/v3/agents/customer/17','/api/v3/agents/customer/{customerId}'],
      ['get_agent',{agentId:7},'/api/v3/agents/7','/api/v3/agents/{agentId}'],
      ['find_agents_by_machine',{machineName:'LAB PC'},'/api/v3/agents/machine/LAB%20PC','/api/v3/agents/machine/{machineName}'],
      ['list_alerts',{},'/api/v3/alerts','/api/v3/alerts'],
      ['get_alert',{alertId:8},'/api/v3/alerts/8','/api/v3/alerts/{alertId}'],
      ['list_agent_patches',{deviceGuid:'123e4567-e89b-12d3-a456-426614174000',state:'available'},'/api/v3/agents/123e4567-e89b-12d3-a456-426614174000/available-patches','/api/v3/agents/{deviceGuid}/available-patches']
    ];
    for(const kind of ['snmp','tcp','http','generic']) {
      cases.push(['list_monitors',{kind,customerId:17},`/api/v3/devices/${kind}devices`,`/api/v3/devices/${kind}devices`]);
      cases.push(['get_monitor',{kind,deviceId:10},`/api/v3/devices/${kind}device/10`,`/api/v3/devices/${kind}device/{deviceId}`]);
    }
    for(const [name,args,path,template] of cases) {
      const result=await client.callTool({name,arguments:args}); assert.ok(!result.isError,JSON.stringify(result));
      const actual=requests.at(-1); assert.equal(actual.path,path);
      const operation=spec.paths[template].get; assert.ok(operation);
      const params=new Set(operation.parameters.filter(p=>p.in==='query').map(p=>p.name));
      for(const key of Object.keys(actual.query)) assert.ok(params.has(key),`${template}: undocumented ${key}`);
    }
    const summary=JSON.parse((await client.callTool({name:'monitoring_summary',arguments:{maxPages:1}})).content[0].text);
    assert.equal(summary.complete,false);assert.equal(summary.coverage.agents.nextPage,2);assert.equal(summary.agents.offline,1);assert.equal(summary.openAlerts.bySeverity.Critical,1);
    assert.equal((await client.callTool({name:'get_agent',arguments:{agentId:-1}})).isError,true);
    assert.equal((await client.callTool({name:'find_agents_by_machine',arguments:{machineName:'..'}})).isError,true);
  } finally {await client.close();await server.close();}
});
