import test from 'node:test';
import { fileURLToPath } from 'node:url';
import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync, rmSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
import { defaults, validateConfig, readConfig, launchEnvironment, launchSpec } from '../src/config.mjs';

test('paths remain arguments, including whitespace and shell metacharacters', () => {
  const root = '/home/test/a space; $(touch NEVER)';
  const spec = launchSpec({ ...defaults, repoRoot: root }, 'fixed script');
  assert.equal(spec.command, 'wsl.exe');
  assert.deepEqual(spec.args.slice(-4), ['fixed script', 'conclave-plugin', root, '']);
});
test('invalid configuration fails instead of silently choosing a checkout', () => {
  for (const input of [{ repoRoot: 'relative' }, { repoRoot: '/home/test\nother' }, { distribution: '--exec' }, { nodePath: 'node' }, { schemaVersion: 2 }]) assert.throws(() => validateConfig(input));
});
test('ambient credentials and shell injection variables are not inherited', () => {
  const env = launchEnvironment({ PATH: 'runtime', SystemRoot: 'windows', DATABASE_URL: 'secret', NODE_OPTIONS: 'injected', BASH_ENV: 'injected', WSLENV: 'DATABASE_URL', CONCLAVE_MCP_CLIENT_PROFILE: 'admin' });
  assert.deepEqual(env, { PATH: 'runtime', SystemRoot: 'windows' });
});
test('missing config uses defaults; malformed config fails closed', () => {
  const dir = mkdtempSync(join(tmpdir(), 'conclave-config-'));
  try {
    const path = join(dir, 'config.json');
    assert.deepEqual(readConfig(path), defaults);
    writeFileSync(path, 'broken');
    assert.throws(() => readConfig(path), /Invalid plugin configuration/);
  } finally { rmSync(dir, { recursive: true, force: true }); }
});
test('configuration update preserves unrelated settings and hides them from status', () => {
  const dir = mkdtempSync(join(tmpdir(), 'conclave-config-'));
  try {
    const path = join(dir, 'config.json');
    writeFileSync(path, JSON.stringify({ ...defaults, displayPreference: 'preserved' }));
    const result = spawnSync(process.execPath, [fileURLToPath(new URL('../scripts/configure.mjs', import.meta.url)), 'set', '--repo-root', '/home/test/new root'], { env: { ...process.env, CONCLAVE_PLUGIN_CONFIG: path }, encoding: 'utf8', windowsHide: true });
    assert.equal(result.status, 0, result.stderr);
    assert.equal(JSON.parse(readFileSync(path, 'utf8')).displayPreference, 'preserved');
    assert.equal(JSON.parse(result.stdout).repoRoot, '/home/test/new root');
    assert.ok(!result.stdout.includes('displayPreference'));
  } finally { rmSync(dir, { recursive: true, force: true }); }
});
