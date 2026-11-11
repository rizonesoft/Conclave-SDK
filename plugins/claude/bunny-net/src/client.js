import { loadCredentials, validApiKey } from './credentials.js';

const BASE='https://api.bunny.net';
// Only the operations this plugin implements. Anything else is refused before credentials load.
const ROUTES=[
  ['GET',/^\/pullzone$/],['GET',/^\/pullzone\/\d+$/],
  ['GET',/^\/dnszone$/],['GET',/^\/dnszone\/\d+$/],['GET',/^\/dnszone\/\d+\/export$/],
  ['GET',/^\/storagezone$/],['GET',/^\/storagezone\/\d+$/],
  ['GET',/^\/statistics$/],
  ['POST',/^\/pullzone\/\d+\/purgeCache$/],['POST',/^\/purge$/],
  ['POST',/^\/dnszone$/],['PUT',/^\/dnszone\/\d+\/records$/],
  ['POST',/^\/dnszone\/\d+\/records\/\d+$/],['DELETE',/^\/dnszone\/\d+\/records\/\d+$/]
];
// Provider fields that carry credentials: storage passwords, token-auth keys, S3 signing secrets,
// log forwarding tokens, TLS private keys, DNS script environment variables and edge-rule
// parameters (which can set origin authorization headers) and trigger patterns (which can hold
// shared secrets for header, query string or cookie gates).
const SECRET_FIELD=/(password|secret|accesskey|apikey|privatekey|securitykey|signingkey|forwardingtoken|bypasscookie|^certificate$|^certificatekey$|^enviromentalvariables$|^environmentalvariables$|^actionparameter\d*$|^extraactions$|^patternmatches$|^authorization$)/i;
export class ApiError extends Error {}
// Origin URLs keep scheme, host and path; credentials in userinfo or the query string are dropped.
function originUrl(value) {
  try {const u=new URL(value);if(!u.username&&!u.password&&!u.search)return value;u.username='';u.password='';u.search='';return u.toString()+' [credentials or query removed]';}
  catch {return value;}
}
export function scrub(value,secrets=[]) {
  if(Array.isArray(value)) return value.map(v=>scrub(v,secrets));
  if(value&&typeof value==='object') return Object.fromEntries(Object.entries(value).filter(([k])=>!SECRET_FIELD.test(k)).map(([k,v])=>[k,scrub(/^originurl$/i.test(k)&&typeof v==='string'?originUrl(v):v,secrets)]));
  if(typeof value==='string') for(const secret of secrets) if(secret) value=value.split(secret).join('[redacted]');
  return value;
}
async function readLimited(response,limit) {
  const reader=response.body?.getReader();if(!reader)return '';
  let size=0;const chunks=[];
  while(true){const {done,value}=await reader.read();if(done)break;size+=value.byteLength;if(size>limit){await reader.cancel();throw new Error('oversized');}chunks.push(Buffer.from(value));}
  return Buffer.concat(chunks).toString('utf8');
}
export class BunnyClient {
  constructor({fetchImpl=fetch,credentials=loadCredentials,sleep=ms=>new Promise(r=>setTimeout(r,ms))}={}) {
    this.fetch=fetchImpl;this.credentials=credentials;this.sleep=sleep;
  }
  async wire(method,path,{query={},body}={},key,retryRead=true) {
    const url=new URL(BASE+path);
    for(const [k,v] of Object.entries(query)) if(v!==undefined) url.searchParams.set(k,String(v));
    const options={method,redirect:'error',signal:AbortSignal.timeout(30000),headers:{Accept:'application/json',AccessKey:key}};
    if(body!==undefined){options.headers['Content-Type']='application/json';options.body=JSON.stringify(body);}
    let response;
    try {response=await this.fetch(url,options);} catch {throw new ApiError(method==='GET'?'API connection failed or timed out.':'Request outcome is unknown. Inspect current state before retrying; this change was not retried.');}
    if(method==='GET'&&retryRead&&[429,502,503,504].includes(response.status)) {
      await response.body?.cancel();
      const delay=Number(response.headers.get('retry-after'));
      if(Number.isFinite(delay)&&delay>5) throw new ApiError('API rate limited. Wait before trying again.');
      await this.sleep(Number.isFinite(delay)&&delay>0?delay*1000:1000);
      return this.wire(method,path,{query,body},key,false);
    }
    if(!response.ok) {
      let detail='';
      try {const text=await readLimited(response,16384);const parsed=JSON.parse(text);if(typeof parsed?.Message==='string')detail=': '+scrub(parsed.Message,[key]).slice(0,300);} catch {}
      const hint=response.status===401?' Check the API key with scripts/configure.ps1.':method==='GET'?'':' The change was not retried; inspect current state before trying again.';
      throw new ApiError('bunny.net returned HTTP '+response.status+detail+'.'+hint);
    }
    let text;
    try {text=await readLimited(response,5_000_000);} catch {throw new ApiError('API returned an oversized response. Narrow the request.');}
    if(!text) return {};
    if(/\/export$/.test(path)) return {text};
    if((response.headers.get('content-type')||'').includes('json')) {
      try {return JSON.parse(text);} catch {throw new ApiError('API returned invalid JSON. For changes, verify current state before retrying.');}
    }
    return {text};
  }
  async request(method,path,options={}) {
    if(!ROUTES.some(([m,p])=>m===method&&p.test(path)))throw new ApiError('Unsupported API operation.');
    const c=await this.credentials();
    if(c?.mode!=='apikey'||!validApiKey(c.apiKey))throw new ApiError('Invalid bunny.net credential. Run scripts/configure.ps1.');
    const data=await this.wire(method,path,options,c.apiKey);
    return scrub(data,[c.apiKey]);
  }
}
