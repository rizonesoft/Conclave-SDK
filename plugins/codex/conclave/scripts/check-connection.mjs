import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const expected = ['conclave_mcp_health', 'search_memory', 'read_memory', 'resolve_project_context', 'get_current_plan', 'get_tool_health', 'create_approval_request', 'propose_memory_write'].sort();
const child = spawn(process.execPath, [fileURLToPath(new URL('../src/launch.mjs', import.meta.url))], { stdio: ['pipe', 'pipe', 'pipe'], windowsHide: true });
const pending = new Map();
let buffer = '', bytes = 0, nextId = 0, failure, closed = false, stderrBytes = 0;
let onClose;
const closure = new Promise(resolve => { onClose = resolve; });
function fail(message) {
  failure ??= new Error(message);
  for (const { reject, timer } of pending.values()) { clearTimeout(timer); reject(failure); }
  pending.clear();
}
child.on('error', () => fail('Launcher could not start.'));
child.on('close', code => { closed = true; onClose(code); fail('Server closed before the check finished.'); });
child.stdin.on('error', () => fail('Server input closed.'));
child.stderr.on('data', chunk => { stderrBytes += chunk.length; });
child.stdout.on('data', chunk => {
  bytes += chunk.length;
  if (bytes > 4 * 1024 * 1024) { fail('Protocol response exceeded the bounded check limit.'); child.stdin.end(); return; }
  buffer += chunk.toString('utf8');
  let end;
  while ((end = buffer.indexOf('\n')) >= 0) {
    const line = buffer.slice(0, end).trim(); buffer = buffer.slice(end + 1);
    if (!line) continue;
    let message;
    try { message = JSON.parse(line); } catch { fail('Non-JSON output appeared on the MCP transport.'); return; }
    if (message.jsonrpc !== '2.0') { fail('Invalid JSON-RPC frame.'); return; }
    const entry = pending.get(message.id);
    if (entry) {
      clearTimeout(entry.timer); pending.delete(message.id);
      if (message.error) entry.reject(new Error('MCP request returned an error; inspect Conclave health locally.'));
      else entry.resolve(message.result);
    }
  }
});
function send(message) { child.stdin.write(JSON.stringify(message) + '\n'); }
function request(method, params) {
  if (failure) return Promise.reject(failure);
  const id = ++nextId;
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => { pending.delete(id); reject(new Error('MCP request timed out after 45 seconds.')); }, 45000);
    pending.set(id, { resolve, reject, timer });
    send({ jsonrpc: '2.0', id, method, params });
  });
}
function content(result) {
  if (result.isError) throw new Error('Conclave returned a tool error; no tool contents were logged.');
  if (result.structuredContent) return result.structuredContent;
  try { return JSON.parse(result.content.filter(item => item.type === 'text').map(item => item.text).join('\n')); }
  catch { throw new Error('Conclave returned an unexpected response shape.'); }
}
let report;
try {
  const init = await request('initialize', { protocolVersion: '2024-11-05', capabilities: {}, clientInfo: { name: 'rizonetech-conclave-check', version: '0.1.0' } });
  send({ jsonrpc: '2.0', method: 'notifications/initialized' });
  const listed = await request('tools/list', {});
  const names = listed.tools.map(tool => tool.name).sort();
  if (JSON.stringify(names) !== JSON.stringify(expected) || listed.nextCursor) throw new Error('Unexpected tool inventory; review the Conclave interface before accepting it.');
  const health = content(await request('tools/call', { name: 'conclave_mcp_health', arguments: {} }));
  if (!health.ok || health.clientProfile !== 'codex' || health.vaultSetupRequired || !health.approvalRuntime?.active || health.approvalRuntime?.executionAuthority !== false) throw new Error('Conclave health is not ready for the codex profile; inspect its local configuration and database.');
  const plan = content(await request('tools/call', { name: 'get_current_plan', arguments: { limit: 1 } }));
  report = { ok: true, protocolVersion: init.protocolVersion, tools: names, repoRoot: health.repoRoot, clientProfile: health.clientProfile, approvalRuntime: health.approvalRuntime.mode, executionAuthority: false, planRead: !!plan, writeCallsPerformed: 0 };
} catch (error) {
  report = { ok: false, error: error.message, stderrBytes, valuesExposed: false };
  process.exitCode = 1;
} finally {
  child.stdin.end();
  const timeout = new Promise(resolve => { const timer = setTimeout(() => resolve('timeout'), 30000); timer.unref(); });
  const exitCode = closed ? await closure : await Promise.race([closure, timeout]);
  if (exitCode === 'timeout') {
    child.kill();
    report.ok = false; report.shutdown = 'stdin-close-timeout'; process.exitCode = 1;
  } else {
    report.shutdown = exitCode === 0 ? 'clean-stdin-close' : 'nonzero-exit';
    if (exitCode !== 0) { report.ok = false; process.exitCode = 1; }
  }
  console.log(JSON.stringify(report, null, 2));
}
