import { readFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { join } from 'node:path';

export const defaults = Object.freeze({ schemaVersion: 1, distribution: 'Ubuntu', repoRoot: '~/conclave', nodePath: '' });
export function configPath(env = process.env) {
  return env.CONCLAVE_PLUGIN_CONFIG || join(env.LOCALAPPDATA || join(homedir(), 'AppData', 'Local'), 'Rizonetech', 'Conclave', 'config.json');
}
export function validateConfig(input) {
  if (!input || typeof input !== 'object' || Array.isArray(input)) throw new Error('Configuration must be a JSON object.');
  const config = { ...defaults, ...input };
  if (config.schemaVersion !== 1) throw new Error('Unsupported configuration version.');
  if (typeof config.distribution !== 'string' || !/^[a-zA-Z0-9][a-zA-Z0-9._-]{0,79}$/.test(config.distribution)) throw new Error('Use a valid WSL distribution name.');
  if (typeof config.repoRoot !== 'string' || !/^(\/|~\/)/.test(config.repoRoot) || /[\x00-\x1f\x7f]/.test(config.repoRoot)) throw new Error('repoRoot must be an absolute Linux path or start with ~/.');
  if (typeof config.nodePath !== 'string' || (config.nodePath && (!config.nodePath.startsWith('/') || /[\x00-\x1f\x7f]/.test(config.nodePath)))) throw new Error('nodePath must be empty or an absolute Linux path.');
  return config;
}
export function readConfig(path = configPath()) {
  try { return validateConfig(JSON.parse(readFileSync(path, 'utf8').replace(/^\uFEFF/, ''))); }
  catch (error) {
    if (error.code === 'ENOENT') return { ...defaults };
    throw new Error('Invalid plugin configuration. Run the configuration status command and repair the non-secret JSON file.');
  }
}
export function publicConfig(config) {
  return Object.fromEntries(Object.keys(defaults).map(key => [key, config[key]]));
}
export function launchEnvironment(env = process.env) {
  const allowed = new Set(['systemroot', 'windir', 'systemdrive', 'comspec', 'path', 'pathext', 'temp', 'tmp', 'userprofile', 'localappdata', 'appdata', 'programdata', 'programfiles', 'programfiles(x86)', 'commonprogramfiles', 'username', 'userdomain', 'home', 'lang', 'lc_all']);
  return Object.fromEntries(Object.entries(env).filter(([key]) => allowed.has(key.toLowerCase())));
}
export function launchSpec(config, script) {
  validateConfig(config);
  return {
    command: 'wsl.exe',
    args: ['--distribution', config.distribution, '--exec', '/usr/bin/env', '-u', 'BASH_ENV', '-u', 'ENV', 'bash', '--noprofile', '--norc', '-c', script, 'conclave-plugin', config.repoRoot, config.nodePath],
  };
}
