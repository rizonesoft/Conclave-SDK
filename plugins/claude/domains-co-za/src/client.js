import { createHash } from 'node:crypto';
import { loadCredentials } from './credentials.js';
import { totp } from './totp.js';

const BASE='https://api.domains.co.za/api';
const READS=new Set(['/domain/list','/domain','/domain/check','/domain/dns','/domain/lock','/domain/transfer','/domain/dsrecords','/domain/gluerecords','/domain/tlds','/domain/funds','/reseller/pricing','/template/contact','/template/ns']);
const WRITES=new Set(['POST /domain','POST /domain/ns','POST /domain/autorenew','POST /domain/renew','POST /domain/lock','POST /domain/dns/entry','PUT /domain/dns/entry','DELETE /domain/dns/entry']);
export class ApiError extends Error {}
export function scrub(value,secrets=[]) {
  if(Array.isArray(value)) return value.map(v=>scrub(v,secrets));
  if(value&&typeof value==='object') return Object.fromEntries(Object.entries(value).filter(([k])=>!/(password|token|secret|eppkey|authcode|authorization)/i.test(k)).map(([k,v])=>[k,scrub(v,secrets)]));
  if(typeof value==='string') for(const secret of secrets) if(secret) value=value.split(secret).join('[redacted]');
  return value;
}
export class DomainsClient {
  constructor({fetchImpl=fetch,credentials=loadCredentials,now=Date.now,sleep=ms=>new Promise(r=>setTimeout(r,ms))}={}) {
    this.fetch=fetchImpl;this.credentials=credentials;this.now=now;this.sleep=sleep;this.cache=null;this.secrets=[];
  }
  async wire(method,path,params,token,retryRead=true) {
    const url=new URL(BASE+path);const encoded=new URLSearchParams();
    for(const [k,v] of Object.entries(params)) if(v!==undefined) encoded.set(k,String(v));
    // Matches the published PHP client: POST form body, other verbs query parameters.
    if(method!=='POST') url.search=encoded.toString();
    const options={method,redirect:'error',signal:AbortSignal.timeout(30000),headers:{Accept:'application/json'}};
    if(token) options.headers.Authorization='Bearer '+token;
    if(method==='POST'){options.headers['Content-Type']='application/x-www-form-urlencoded';options.body=encoded.toString();}
    let response;
    try {response=await this.fetch(url,options);} catch {throw new ApiError(method==='GET'?'API connection failed or timed out.':'Request outcome is unknown. Inspect current state before retrying; this change was not retried.');}
    if(method==='GET'&&retryRead&&[429,502,503,504].includes(response.status)) {
      await response.body?.cancel();
      const delay=Number(response.headers.get('retry-after'));
      if(Number.isFinite(delay)&&delay>5) throw new ApiError('API rate limited. Wait before trying again.');
      await this.sleep(Number.isFinite(delay)&&delay>0?delay*1000:1000);
      return this.wire(method,path,params,token,false);
    }
    if(!response.ok){await response.body?.cancel();throw new ApiError('Domains.co.za returned HTTP '+response.status+'. Check credentials, permissions or provider status. No writes were retried.');}
    let data;
    try {
      const reader=response.body.getReader();let size=0;const chunks=[];
      while(true){const {done,value}=await reader.read();if(done)break;size+=value.byteLength;if(size>5_000_000){await reader.cancel();throw new Error();}chunks.push(Buffer.from(value));}
      data=JSON.parse(Buffer.concat(chunks).toString('utf8'));
    } catch {throw new ApiError('API returned an invalid or oversized response. For changes, verify current state before retrying.');}
    const available=path==='/domain/check'&&[true,false,0,1,'0','1'].includes(data.isAvailable);
    if(![1,2].includes(Number(data.intReturnCode))&&!available) throw new ApiError('Domains.co.za rejected the request (code '+(/^[0-9]+$/.test(String(data.intReturnCode))?data.intReturnCode:'unknown')+'). Check credentials, parameters and permissions.');
    return data;
  }
  async token() {
    const c=await this.credentials();
    this.secrets=[c.password,c.token,c.totpSecret].filter(Boolean);
    if(c.mode==='bearer')return c.token.trim().replace(/^Bearer\s+/i,'');
    const fingerprint=createHash('sha256').update(JSON.stringify(c)).digest('hex');
    if(this.cache?.fingerprint===fingerprint&&this.cache.until>this.now()){this.secrets.push(this.cache.token);return this.cache.token;}
    const code=c.totpSecret?totp(c.totpSecret,this.now()):undefined;if(code)this.secrets.push(code);
    const auth=await this.wire('POST','/login',{username:c.username,password:c.password,code});
    if(typeof auth.token!=='string'||!auth.token||/[\r\n]/.test(auth.token))throw new ApiError('Login did not issue a JWT. Configure the authenticator setup secret in the Windows-encrypted credential, or obtain a JWT using the local one-time-code setup. Two-factor authentication remains enabled.');
    let until=this.now()+240000;
    try {const exp=JSON.parse(Buffer.from(auth.token.split('.')[1],'base64url')).exp;if(Number.isFinite(exp))until=Math.min(until,exp*1000-30000);}catch{}
    this.cache={fingerprint,token:auth.token,until};this.secrets.push(auth.token);return auth.token;
  }
  async request(method,path,params={}) {
    if(!(method==='GET'?READS.has(path):WRITES.has(method+' '+path)))throw new ApiError('Unsupported API operation.');
    const token=await this.token();
    const data=await this.wire(method,path,params,token);
    return scrub(data,[...this.secrets,token]);
  }
}
