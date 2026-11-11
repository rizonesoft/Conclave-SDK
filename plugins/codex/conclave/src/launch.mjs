import {approvalTransport} from './approval-transport.mjs';
import { spawn } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { configPath, readConfig, launchEnvironment, launchSpec } from './config.mjs';

try {
  if (process.platform !== 'win32') throw new Error('This desktop bridge requires Windows and WSL.');
  const config = readConfig(configPath());
  const script = readFileSync(new URL('./launch.sh', import.meta.url), 'utf8').replace(/\r\n/g, '\n');
  const spec = launchSpec(config, script);
  const child = spawn(spec.command, spec.args, { stdio: ['pipe', 'pipe', 'pipe'], windowsHide: true, shell: false, env: launchEnvironment() });
  process.stdin.pipe(child.stdin);
  const guidance=approvalTransport();
  guidance.on('error',()=>{process.stderr.write('Conclave protocol guidance failed; connection closed.\n');child.kill();process.exitCode=78;});
  child.stdout.pipe(guidance).pipe(process.stdout);
  child.stderr.pipe(process.stderr);
  child.stdin.on('error', () => { process.stdin.unpipe(child.stdin); process.stdin.pause(); });
  child.on('close', () => { process.stdin.unpipe(child.stdin); process.stdin.pause(); });
  child.on('error', () => {
    process.stderr.write(JSON.stringify({ state: 'setup_required', detail: 'Could not start WSL. Check WSL installation and the configured distribution.', valuesExposed: false }) + '\n');
    process.exitCode = 78;
  });
  child.on('exit', code => { process.exitCode = code ?? 1; });
  for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => child.kill(signal));
} catch (error) {
  process.stderr.write(JSON.stringify({ state: 'setup_required', detail: error.message, valuesExposed: false }) + '\n');
  process.exitCode = 78;
}
