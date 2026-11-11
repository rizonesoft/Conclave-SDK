import { createHmac } from 'node:crypto';
export function totp(input,now=Date.now()) {
  let secret=input,algorithm='sha1',digits=6,period=30;
  if(typeof secret!=='string'||!secret.trim())throw new Error('Authenticator secret is missing. Configure it locally.');
  if(secret.startsWith('otpauth://')){
    const u=new URL(secret);if(u.protocol!=='otpauth:'||u.hostname!=='totp')throw new Error('Only TOTP authenticator setup URIs are supported.');
    secret=u.searchParams.get('secret');algorithm=(u.searchParams.get('algorithm')||'SHA1').toLowerCase();digits=Number(u.searchParams.get('digits')||6);period=Number(u.searchParams.get('period')||30);
  }
  if(!['sha1','sha256','sha512'].includes(algorithm)||![6,8].includes(digits)||!Number.isInteger(period)||period<15||period>120)throw new Error('Unsupported authenticator parameters.');
  secret=secret?.replace(/[\s=]/g,'').toUpperCase();
  if(!secret||!/^[A-Z2-7]{16,256}$/.test(secret))throw new Error('Invalid authenticator setup secret. Enter the setup secret, not a current six-digit code.');
  const alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';let bits=0,value=0;const bytes=[];
  for(const ch of secret){value=(value<<5)|alphabet.indexOf(ch);bits+=5;if(bits>=8){bits-=8;bytes.push((value>>bits)&255);}}
  const counter=Buffer.alloc(8);counter.writeBigUInt64BE(BigInt(Math.floor(now/1000/period)));
  const hash=createHmac(algorithm,Buffer.from(bytes)).update(counter).digest();const offset=hash.at(-1)&15;
  return String((hash.readUInt32BE(offset)&0x7fffffff)%10**digits).padStart(digits,'0');
}
