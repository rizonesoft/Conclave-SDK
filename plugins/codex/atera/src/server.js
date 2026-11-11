import {approvalInstructions} from './approval-policy.mjs';
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { z } from 'zod';
import { AteraClient, pageResult, scan } from './client.js';

export function createServer(client = new AteraClient()) {
  const server = new McpServer({ name: 'rizonetech-atera', version: '0.1.5' },{instructions:approvalInstructions});
  const id = z.number().int().positive().max(Number.MAX_SAFE_INTEGER);
  const page = z.number().int().min(1).max(1000000).default(1);
  const itemsInPage = z.number().int().min(1).max(50).default(20);
  const kind = z.enum(['snmp','tcp','http','generic']);
  const register = (name, description, inputSchema, handler) => server.registerTool(name, { description, inputSchema, annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: true } }, async args => {
    try {
      const result = await handler(args);
      const text = JSON.stringify(result);
      if (Buffer.byteLength(text) > 200000) throw new Error('Result exceeds the chat response limit. Request a smaller page or an individual device.');
      return { content: [{ type: 'text', text }] };
    } catch (e) { return { isError: true, content: [{ type: 'text', text: e.message }] }; }
  });
  register('connection_status', 'Verify Atera authentication and Agents read access using a one-record request. Returns no customer or device data.', {}, async () => {
    await client.get('/api/v3/agents', {page:1,itemsInPage:1});
    return { connected: true, verifiedPermission: 'Agents: Read', mode: 'read-only', checkedAt: new Date().toISOString() };
  });
  register('list_agents', 'List Atera endpoint agents, optionally for one customer. One page only; follow nextPage to cover the full inventory. Online and LastSeen reflect Atera reporting.', { customerId:id.optional(), page, itemsInPage }, async ({customerId,...q}) => pageResult(await client.get(customerId ? `/api/v3/agents/customer/${customerId}` : '/api/v3/agents',q),q.page));
  register('get_agent', 'Get an agent by numeric AgentID, including inventory, Online, Monitored, LastSeen, and DeviceGuid. Product keys are omitted.', {agentId:id}, ({agentId}) => client.get(`/api/v3/agents/${agentId}`));
  register('find_agents_by_machine', 'Look up agents using Atera machine-name matching. This is not a general fuzzy search. Results are paginated.', {machineName:z.string().trim().min(1).max(255).refine(v => v !== '.' && v !== '..' && !/[\x00-\x1f/\\]/.test(v)),page,itemsInPage}, async ({machineName,...q}) => pageResult(await client.get(`/api/v3/agents/machine/${encodeURIComponent(machineName)}`,q),q.page));
  register('list_monitors', 'List SNMP, TCP, HTTP, or generic monitored devices. Optional customer and monitoring-agent filters. One page only. Credential fields are omitted.', {kind,customerId:id.optional(),monitoringAgentId:id.optional(),page,itemsInPage}, async ({kind,...q}) => pageResult(await client.get(`/api/v3/devices/${kind}devices`,q),q.page));
  register('get_monitor', 'Inspect one SNMP, TCP, HTTP, or generic monitor by numeric DeviceID. Credential fields and URL query strings are omitted.', {kind,deviceId:id}, ({kind,deviceId}) => client.get(`/api/v3/devices/${kind}device/${deviceId}`));
  register('list_alerts', 'List alerts by Atera status: Open, Resolved, or Snoozed. Defaults to Open. One page only; follow nextPage for coverage. No unsupported server-side customer or severity filters are sent.', {alertStatus:z.enum(['Open','Resolved','Snoozed']).default('Open'),page,itemsInPage}, async q => pageResult(await client.get('/api/v3/alerts',q),q.page));
  register('get_alert', 'Read an alert by numeric AlertID, including severity, device association, and reported timestamps.', {alertId:id}, ({alertId}) => client.get(`/api/v3/alerts/${alertId}`));
  register('list_agent_patches', 'Read installed or available patches for a DeviceGuid obtained from an agent. Does not install patches or run commands.', {deviceGuid:z.string().uuid(),state:z.enum(['installed','available'])}, ({deviceGuid,state}) => client.get(`/api/v3/agents/${deviceGuid}/${state}-patches`));
  register('monitoring_summary', 'Summarize endpoint online/monitoring state and open-alert severity with explicit scan coverage. Reads up to maxPages pages each (50 records/page). Does not include SNMP/TCP/HTTP/generic monitors; use list_monitors for those. Incomplete scans are not account-wide totals.', {maxPages:z.number().int().min(1).max(10).default(2)}, async ({maxPages}) => {
    const agents = await scan(client,'/api/v3/agents',{},maxPages);
    const alerts = await scan(client,'/api/v3/alerts',{alertStatus:'Open'},maxPages);
    const bySeverity = Object.create(null);
    for (const a of alerts.items) bySeverity[a.Severity || 'Unknown'] = (bySeverity[a.Severity || 'Unknown'] || 0) + 1;
    const coverage = ({items,...rest}) => ({...rest, recordsScanned:items.length});
    return { checkedAt:new Date().toISOString(), scope:'Endpoint agents and open alerts; excludes network monitor inventory', complete:agents.complete && alerts.complete, coverage:{agents:coverage(agents),alerts:coverage(alerts)}, agents:{online:agents.items.filter(x=>x.Online===true).length,offline:agents.items.filter(x=>x.Online===false).length,unknown:agents.items.filter(x=>typeof x.Online!=='boolean').length,unmonitored:agents.items.filter(x=>x.Monitored===false).length}, openAlerts:{bySeverity,scanned:alerts.items.length}, note:'Counts describe the scanned records at request time; pages are not an atomic snapshot.' };
  });
  return server;
}

if (process.env.ATERA_TEST_IMPORT !== '1') {
  const server = createServer();
  await server.connect(new StdioServerTransport());
}
