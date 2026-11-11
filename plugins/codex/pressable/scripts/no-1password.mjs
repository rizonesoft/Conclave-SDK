// Verification preload: make any accidental runtime 1Password execution fail.
import cp from 'node:child_process';
import {syncBuiltinESMExports} from 'node:module';
import {promisify} from 'node:util';
for(const name of ['exec','execSync','execFile','execFileSync','spawn','spawnSync']){
 const original=cp[name];cp[name]=function(command,...args){if(/(?:^|[\\/\s])(?:op(?:\.exe)?|1password)(?:$|\s)/i.test(String(command)))throw new Error('1Password runtime execution blocked by verification');return original.call(this,command,...args);};
}
for(const name of ['exec','execFile'])Object.defineProperty(cp[name],promisify.custom,{value:(...args)=>new Promise((resolve,reject)=>cp[name](...args,(error,stdout,stderr)=>error?reject(error):resolve({stdout,stderr})))});
syncBuiltinESMExports();
