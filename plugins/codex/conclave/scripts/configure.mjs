import { mkdirSync, writeFileSync, renameSync, rmSync } from 'node:fs';
import { dirname } from 'node:path';
import { configPath, readConfig, publicConfig, validateConfig } from '../src/config.mjs';

try {
  const [action = 'status', ...args] = process.argv.slice(2);
  const path = configPath();
  let config = readConfig(path);
  if (action === 'set') {
    if (!args.length || args.length % 2) throw new Error('Use set --distribution Ubuntu --repo-root ~/conclave [--node-path /absolute/path/to/node].');
    const keys = { '--distribution': 'distribution', '--repo-root': 'repoRoot', '--node-path': 'nodePath' };
    for (let i = 0; i < args.length; i += 2) {
      if (!keys[args[i]]) throw new Error('Unsupported configuration option. Credentials are managed by Conclave, not this plugin.');
      config[keys[args[i]]] = args[i + 1];
    }
    config = validateConfig(config);
    mkdirSync(dirname(path), { recursive: true });
    const temp = path + '.' + process.pid + '.tmp';
    try {
      writeFileSync(temp, JSON.stringify(config, null, 2) + '\n', { flag: 'wx' });
      renameSync(temp, path);
    } finally { rmSync(temp, { force: true }); }
  } else if (action !== 'status' || args.length) throw new Error('Use status or set.');
  console.log(JSON.stringify({ path, ...publicConfig(config), clientProfile: 'codex', credentialOwner: 'Conclave WSL configuration launcher', pluginStoresCredentials: false }, null, 2));
} catch (error) { console.error(error.message); process.exitCode = 1; }
