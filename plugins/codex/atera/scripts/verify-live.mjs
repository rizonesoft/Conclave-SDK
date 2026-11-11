import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import { fileURLToPath } from 'node:url';
const entry=process.argv[2] || fileURLToPath(new URL('../dist/server.mjs',import.meta.url));
const client=new Client({name:'atera-live-verification',version:'0.1.0'});
const transport=new StdioClientTransport({command:process.execPath,args:[entry],stderr:'pipe'});
async function check(name,args={}) {
  const result=await client.callTool({name,arguments:args},undefined,{timeout:90000});
  if(result.isError) { console.log(JSON.stringify({tool:name,status:'failed',error:result.content[0].text}));process.exitCode=1;return null; }
  const value=JSON.parse(result.content[0].text);
  console.log(JSON.stringify({tool:name,status:'passed',...(Array.isArray(value.items)?{recordsReturned:value.items.length,hasMore:value.hasMore}:{} )}));
  return value;
}
try {
  await client.connect(transport);
  console.log(JSON.stringify({toolsDiscovered:(await client.listTools()).tools.length}));
  await check('connection_status');
  const agents=await check('list_agents',{itemsInPage:1});
  if(agents?.items[0]) {
    const agent=agents.items[0];
    await check('get_agent',{agentId:agent.AgentID});
    if(agent.MachineName) await check('find_agents_by_machine',{machineName:agent.MachineName,itemsInPage:1});
    if(agent.DeviceGuid) for(const state of ['installed','available']) await check('list_agent_patches',{deviceGuid:agent.DeviceGuid,state});
  }
  const alerts=await check('list_alerts',{itemsInPage:1});
  if(alerts?.items[0]) await check('get_alert',{alertId:alerts.items[0].AlertID});
  for(const kind of ['snmp','tcp','http','generic']) {
    const monitors=await check('list_monitors',{kind,itemsInPage:1});
    if(monitors?.items[0]) await check('get_monitor',{kind,deviceId:monitors.items[0].DeviceID});
  }
  await check('monitoring_summary',{maxPages:1});
} finally {await client.close();}
