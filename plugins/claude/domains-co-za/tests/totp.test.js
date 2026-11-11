import test from 'node:test';
import assert from 'node:assert/strict';
import {totp} from '../src/totp.js';
test('RFC 6238 SHA1 reference vectors and default six-digit Google Auth format',()=>{
 const secret='GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ';const uri='otpauth://totp/test?secret='+secret+'&digits=8';
 assert.equal(totp(uri,59000),'94287082');assert.equal(totp(uri,1111111109000),'07081804');assert.equal(totp(uri,2000000000000),'69279037');assert.equal(totp(secret,59000),'287082');
});
test('rejects HOTP, pasted current codes and unsafe URI parameters',()=>{
 assert.throws(()=>totp('123456'),/Invalid/);assert.throws(()=>totp('otpauth://hotp/test?secret=GEZDGNBVGY3TQOJQ'),/Only TOTP/);assert.throws(()=>totp('otpauth://totp/test?secret=GEZDGNBVGY3TQOJQ&period=0'),/Unsupported/);
});
