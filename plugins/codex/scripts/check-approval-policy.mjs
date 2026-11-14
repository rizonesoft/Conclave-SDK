import {spawn, spawnSync} from 'node:child_process';
import {createInterface} from 'node:readline';

if (!process.argv[2] || process.argv[2].startsWith('--')) {
  console.error('Approval-policy check requires a server path');
  process.exit(1);
}

const child = spawn(process.execPath, [process.argv[2]], {
  stdio: ['pipe', 'pipe', 'pipe'], windowsHide: true,
  detached: process.platform !== 'win32', env: process.env,
});
let stopped = false;
function stopTree() {
  if (stopped || !child.pid) return;
  stopped = true;
  if (process.platform === 'win32') {
    spawnSync('taskkill', ['/PID', String(child.pid), '/T', '/F'], {stdio: 'ignore', windowsHide: true});
  } else {
    try { process.kill(-child.pid, 'SIGKILL'); }
    catch (error) { if (error.code !== 'ESRCH') throw error; }
  }
}
process.once('exit', stopTree);
const pending = new Map();
let id = 0;
let failed = false;
function fail() {
  failed = true;
  for (const request of pending.values()) request.reject(Error('MCP transport ended'));
  pending.clear();
}
const lines = createInterface({input: child.stdout});
child.stderr.resume();
child.on('error', fail);
child.on('exit', fail);
child.stdin.on('error', fail);
lines.on('close', fail);
lines.on('line', line => {
  let message;
  try { message = JSON.parse(line); }
  catch { return; } // Non-JSON diagnostics are not protocol responses.
  if (!message || typeof message !== 'object') return;
  const request = pending.get(message.id);
  if (!request) return;
  pending.delete(message.id);
  if (message.error) request.reject(Error('MCP error'));
  else request.resolve(message.result);
});
function req(method, params) {
  if (failed) return Promise.reject(Error('MCP transport ended'));
  return new Promise((resolve, reject) => {
    pending.set(++id, {resolve, reject});
    child.stdin.write(JSON.stringify({jsonrpc: '2.0', id, method, params}) + '\n');
  });
}
for (const signal of ['SIGINT', 'SIGTERM']) {
  process.on(signal, () => { stopTree(); fail(); process.exitCode = 1; });
}
const timeout = setTimeout(() => { stopTree(); fail(); }, 180000);
try {
  const init = await req('initialize', {
    protocolVersion: '2024-11-05', capabilities: {},
    clientInfo: {name: 'approval-policy-check', version: '1'},
  });
  if (!init.instructions?.includes('agent may approve') || !init.instructions?.includes('After execution')) {
    throw Error('Approval instructions missing');
  }
  child.stdin.write(JSON.stringify({jsonrpc: '2.0', method: 'notifications/initialized'}) + '\n');
  const listing = await req('tools/list', {});
  if (listing.nextCursor) throw Error('Paginated inventory requires complete verification');
  const {tools} = listing;
  if (!Array.isArray(tools) || !tools.length) throw Error('Tool inventory missing');
  // prepare_change writes only a local preview, not provider state.
  const preview = tools.find(tool => tool.name === 'prepare_change');
  if (preview && (preview.annotations?.readOnlyHint !== false ||
      preview.annotations?.destructiveHint !== false || !/preview/i.test(preview.description ?? ''))) {
    throw Error('Preview metadata missing');
  }
  const writes = tools.filter(tool => tool.annotations?.readOnlyHint !== true && tool.name !== 'prepare_change');
  if (preview && !writes.some(tool => tool.name === 'execute_change')) throw Error('Execution gateway missing');
  for (const tool of writes) {
    if (tool.annotations?.readOnlyHint !== false || !tool.description?.includes('verify afterward')) {
      throw Error('Write approval guidance missing');
    }
  }
  let connected;
  if (process.argv.includes('--live')) {
    const name = tools.some(tool => tool.name === 'connection_status') ? 'connection_status' : 'conclave_mcp_health';
    const result = await req('tools/call', {name, arguments: {}});
    if (result.isError) throw Error('Read-only connection check failed');
    const data = result.structuredContent ?? JSON.parse(result.content.filter(c => c.type === 'text').map(c => c.text).join(''));
    connected = data.connected ?? data.ok ?? (Array.isArray(data.sites) && data.sites.length > 0 && data.sites.every(site => site.connected === true));
    if (connected !== true) throw Error('Connection not ready');
  }
  console.log(JSON.stringify({
    name: init.serverInfo.name, version: init.serverInfo.version, tools: tools.length,
    taskScopedApprovalAndVerification: writes.length ? true : null, writeTools: writes.map(tool => tool.name), connected, writesPerformed: 0,
  }));
} catch {
  console.error('Approval-policy check failed; no provider data printed');
  process.exitCode = 1;
} finally {
  clearTimeout(timeout);
  stopTree();
  lines.close();
}
