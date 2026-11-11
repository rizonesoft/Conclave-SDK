import {createHash} from 'node:crypto';
import {loadToken} from './credentials.js';
export class BunnyError extends Error{}
const hosts=new Set(['storage.bunnycdn.com',...['uk','ny','la','sg','se','br','jh','syd'].map(r=>r+'.storage.bunnycdn.com')]);
export function scrub(v,secrets=[]){
 if(Array.isArray(v))return v.map(x=>scrub(x,secrets));
 if(v&&typeof v==='object')return Object.fromEntries(Object.entries(v).filter(([k])=>!/(password|secret|token|accesskey|securitykey|certificate|authorization|headers|environ?mentalvariables)/i.test(k)).map(([k,x])=>[k,scrub(x,secrets)]));
 if(typeof v==='string'){for(const s of secrets)if(s)v=v.split(s).join('[redacted]');v=v.replace(/(https?:\/\/)[^/@\s]+:[^/@\s]+@/gi,'$1[redacted]@').replace(/([?&](?:token|key|password|secret|signature|accesskey)=)[^&#\s]*/gi,'$1[redacted]');}return v;
}
export function objectPath(path,{directory=false}={}){
 if(typeof path!=='string'||path.length>1024||/[\\%?#\x00-\x1f]/.test(path))throw new BunnyError('Invalid storage path. Use a relative unencoded path.');
 if(path.startsWith('/')||(!directory&&(!path||path.endsWith('/'))))throw new BunnyError('File path must be relative and nonempty.');
 const parts=path.replace(/\/$/,'').split('/');if(path&&parts.some(s=>!s||s==='.'||s==='..'))throw new BunnyError('Storage traversal or empty segments are not allowed.');
 return parts.filter(Boolean).map(encodeURIComponent).join('/')+(directory&&path?'/':'');
}
function allowed(method,path){
 if(method==='GET')return /^\/(pullzone|dnszone|storagezone)(\/\d+)?$/.test(path)||path==='/statistics';
 return (method==='POST'&&(/^\/pullzone\/\d+\/purgeCache$/.test(path)||path==='/purge'||/^\/dnszone\/\d+\/records\/\d+$/.test(path)))||(method==='PUT'&&/^\/dnszone\/\d+\/records$/.test(path))||(method==='DELETE'&&/^\/dnszone\/\d+\/records\/\d+$/.test(path));
}
export class BunnyClient{
 constructor({fetchImpl=fetch,credentials=loadToken,sleep=ms=>new Promise(r=>setTimeout(r,ms)),now=Date.now}={}){this.fetch=fetchImpl;this.credentials=credentials;this.sleep=sleep;this.now=now;this.retryAfter=0;}
 async wire(url,method,key,{body,query={},raw=false,text=false,maxBytes=2000000,retry=true}={}){
  if(this.retryAfter>this.now())throw new BunnyError('Bunny.net rate limit remains active. Wait before retrying.');
  const u=new URL(url);for(const[k,v]of Object.entries(query))if(v!==undefined)u.searchParams.set(k,String(v));
  const headers={AccessKey:key,Accept:text?'text/plain':'application/json'};
  if(body!==undefined){headers['Content-Type']=raw?'application/octet-stream':'application/json';if(raw)headers.Checksum=createHash('sha256').update(body).digest('hex').toUpperCase();}
  let r;try{r=await this.fetch(u,{method,headers,body:body===undefined?undefined:raw?body:JSON.stringify(body),redirect:'error',signal:AbortSignal.timeout(30000)});}catch{throw new BunnyError(method==='GET'?'Bunny.net connection failed or timed out.':'Change outcome is unknown. Inspect provider state before retrying; no write was retried.');}
  if(!r.ok){await r.body?.cancel();if(r.status===429){const h=r.headers.get('retry-after');const delay=h===null?1000:/^\d+(\.\d+)?$/.test(h)?Number(h)*1000:Date.parse(h)-this.now();this.retryAfter=this.now()+(Number.isFinite(delay)?Math.max(1000,delay):1000);}
   if(method==='GET'&&retry&&[429,502,503,504].includes(r.status)){const wait=Math.max(1000,this.retryAfter-this.now());if(wait<=5000){await this.sleep(wait);return this.wire(url,method,key,{body,query,raw,text,maxBytes,retry:false});}}
   throw new BunnyError('Bunny.net returned HTTP '+r.status+'. Check credentials, permissions or provider status. No writes were retried.');}
  if(r.status===204)return {success:true};
  try{const chunks=[];let size=0;if(r.body){const reader=r.body.getReader();while(true){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>maxBytes){await reader.cancel();throw new Error();}chunks.push(Buffer.from(value));}}
   const buf=Buffer.concat(chunks);if(!buf.length)return {success:true};if(text){const value=new TextDecoder('utf-8',{fatal:true}).decode(buf);if(value.includes('\0'))throw new Error();return value;}return JSON.parse(buf.toString('utf8'));
  }catch{throw new BunnyError('Invalid or oversized Bunny.net response. For changes, inspect provider state before retrying.');}
 }
 async core(method,path,query={},body){if(!allowed(method,path))throw new BunnyError('Unsupported Bunny.net operation.');const key=await this.credentials();return scrub(await this.wire('https://api.bunny.net'+path,method,key,{query,body}),[key]);}
 async storage(zoneId,method,path,{body,directory=false,text=false}={}){
  if(!Number.isSafeInteger(zoneId)||zoneId<=0||!['GET','PUT','DELETE'].includes(method))throw new BunnyError('Invalid storage operation.');
  const encoded=objectPath(path,{directory});if(method!=='GET'&&directory)throw new BunnyError('Directory changes are not supported.');
  const accountKey=await this.credentials();const z=await this.wire('https://api.bunny.net/storagezone/'+zoneId,'GET',accountKey);
  if(z.Id!==zoneId||typeof z.Name!=='string'||!/^[a-zA-Z0-9-]+$/.test(z.Name))throw new BunnyError('Invalid storage zone response.');
  const host=z.StorageHostname||(z.Region?z.Region+'.storage.bunnycdn.com':'storage.bunnycdn.com');if(!hosts.has(host))throw new BunnyError('Unsupported storage region hostname. No credential was sent.');
  const key=method==='GET'?(z.ReadOnlyPassword||z.Password):z.Password;if(typeof key!=='string'||!key||/[\r\n]/.test(key))throw new BunnyError('The account cannot obtain the storage zone credential.');
  const data=await this.wire('https://'+host+'/'+encodeURIComponent(z.Name)+'/'+encoded,method,key,{body,raw:method==='PUT',text,maxBytes:text?65536:2000000});
  return scrub(data,[accountKey,z.Password,z.ReadOnlyPassword]);
 }
}

// Some Bunny endpoints return arrays despite their documented paged response.
export function zonePage(data,page,perPage,start=0){
 if(Array.isArray(data)){const offset=(page-start)*perPage;return {Items:data.slice(offset,offset+perPage),TotalReturned:data.length,HasMoreItems:offset+perPage<data.length,nextPage:offset+perPage<data.length?page+1:null,pagination:'local slice of provider array',coverage:'Provider did not supply completeness metadata.'};}
 if(!data||!Array.isArray(data.Items))throw new BunnyError('Invalid zone listing response.');
 return {...data,nextPage:data.HasMoreItems===true?page+1:null,pagination:'provider',coverage:typeof data.HasMoreItems==='boolean'?'Provider pagination metadata supplied.':'Provider completeness is unknown.'};
}
