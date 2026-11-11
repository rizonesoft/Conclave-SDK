import test from 'node:test';
import assert from 'node:assert/strict';
import {loadToken} from '../src/credentials.js';
test('Linux reads only the systemd provider credential',async()=>{let reads=0;const value=await loadToken({platform:'linux',env:{CREDENTIALS_DIRECTORY:'/run/credentials/test'},readFileImpl:async p=>{reads++;assert.match(p.replaceAll('\\\\','/'),/provider$/);return 'test-token';},execImpl:()=>{throw new Error('Must not execute 1Password or PowerShell');}});assert.deepEqual(value,'test-token');assert.equal(reads,1);});
test('Linux credential errors are sanitized and never fall back',async()=>{await assert.rejects(loadToken({platform:'linux',env:{CREDENTIALS_DIRECTORY:'/run/credentials/test'},readFileImpl:async()=>{throw new Error('secret-value');},execImpl:()=>{throw new Error('Unexpected execution');}}),e=>/Linux service credential/.test(e.message)&&!e.message.includes('secret-value'));});
