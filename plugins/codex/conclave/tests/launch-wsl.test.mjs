import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { defaults, launchSpec, launchEnvironment } from '../src/config.mjs';
const script = readFileSync(new URL('../src/launch.sh', import.meta.url), 'utf8');
const options = { skip: process.platform !== 'win32' || process.env.CONCLAVE_TEST_WSL !== '1' };
test('WSL missing-checkout failure is bounded and leaves stdout clean', options, () => {
  const spec = launchSpec({ ...defaults, repoRoot: '/nonexistent/conclave-plugin-test-;$(echo SHOULD-NOT-RUN)' }, script);
  const result = spawnSync(spec.command, spec.args, { env: launchEnvironment(), encoding: 'utf8', windowsHide: true, timeout: 15000 });
  assert.equal(result.status, 78, result.stderr);
  assert.equal(result.stdout, '');
  const detail = JSON.parse(result.stderr.trim());
  assert.equal(detail.state, 'setup_required');
  assert.match(detail.detail, /checkout is missing/);
  assert.equal(detail.valuesExposed, false);
});
test('WSL wrong-runtime failure does not run the backend or install dependencies', options, () => {
  const harness = `set -eu
scratch="$(mktemp -d -t conclave-plugin-test.XXXXXX)"
trap 'rm -rf -- "$scratch"' EXIT
git init -q "$scratch"
mkdir "$scratch/scripts"
printf '#!/bin/sh\\necho BACKEND-MUST-NOT-RUN\\n' > "$scratch/scripts/mcp-conclave.sh"
printf '999.0.0\\n' > "$scratch/.nvmrc"
bash --noprofile --norc -c "$1" conclave-plugin "$scratch" /usr/bin/node
`;
  const result = spawnSync('wsl.exe', ['--distribution', 'Ubuntu', '--exec', '/usr/bin/env', '-u', 'BASH_ENV', '-u', 'ENV', 'bash', '--noprofile', '--norc', '-c', harness, 'conclave-test', script], { env: launchEnvironment(), encoding: 'utf8', windowsHide: true, timeout: 15000 });
  assert.equal(result.status, 78, result.stderr);
  assert.equal(result.stdout, '');
  assert.match(JSON.parse(result.stderr.trim()).detail, /exact Node version/);
});
