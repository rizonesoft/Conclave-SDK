import https from 'node:https';
import {validateFileConfig} from './file-operations.js';
import {lookup} from 'node:dns';
import ipaddr from 'ipaddr.js';
export function publicAddress(address){try{return ipaddr.process(address).range()==='unicast';}catch{return false;}}
export function endpointURL(value){
 const u=new URL(value);
 if(u.protocol!=='https:'||u.port||u.username||u.password||u.search||u.hash||!u.hostname.includes('.')||/\.(?:local|localhost|internal|test|invalid)$/i.test(u.hostname)||ipaddr.isValid(u.hostname))throw Error('Only configured public HTTPS DNS endpoints are supported.');
 return u;
}
export function validateRegistry(data){
 if(data?.schemaVersion!==1||!Array.isArray(data.connections)||data.connections.length>100)throw Error('Invalid encrypted connection registry.');
 const ids=new Set();
 for(const s of data.connections){
 if(!/^[a-z0-9][a-z0-9-]{0,79}$/.test(s.id)||ids.has(s.id)||typeof s.name!=='string'||!s.name||typeof s.username!=='string'||!s.username||/[:\r\n]/.test(s.username)||typeof s.password!=='string'||!s.password||/[\r\n]/.test(s.password))throw Error('Invalid or duplicate site connection.');
 if(endpointURL(s.endpoint).origin!==endpointURL(s.siteUrl).origin)throw Error('Site and endpoint origins must match.');
 if(!['production','staging','development','unknown'].includes(s.environment))throw Error('Invalid environment.');
 validateFileConfig(s);ids.add(s.id);
 }
 return data;
}
// Resolve and pin the verified public IP on the actual HTTPS socket; no DNS check/use gap.
export function pinnedLookup(host,options,callback){
 lookup(host,{all:true,verbatim:true},(err,rows)=>{
 if(err||!rows?.length||rows.some(r=>!publicAddress(r.address)))return callback(Error('Public destination validation failed.'));
 const choices=options?.family?rows.filter(r=>r.family===options.family):rows;
 if(!choices.length)return callback(Error('No matching public address.'));
 if(options?.all)callback(null,choices);else callback(null,choices[0].address,choices[0].family);
 });
}
export function siteFetch(site){
 const endpoint=endpointURL(site.endpoint);
 const auth='Basic '+Buffer.from(site.username+':'+site.password).toString('base64');
 return async (url,init={})=>{
 const target=endpointURL(String(url));
 if(target.href!==endpoint.href)throw Error('Unexpected MCP destination.');
 const headers=new Headers(init.headers);headers.set('Authorization',auth);
 return await new Promise((resolve,reject)=>{
 const req=https.request(target,{method:init.method??'GET',headers:Object.fromEntries(headers),lookup:pinnedLookup,agent:false,signal:init.signal},res=>{
 if(res.statusCode>=300&&res.statusCode<400){res.destroy();req.destroy();reject(Error('Endpoint redirects are blocked.'));return;}
 const chunks=[];let size=0;
 res.on('data',chunk=>{size+=chunk.length;if(size>4*1024*1024){res.destroy();req.destroy();reject(Error('MCP response exceeds 4 MiB.'));}else chunks.push(chunk);});
 res.on('error',()=>reject(Error('MCP response interrupted.')));
 res.on('end',()=>{const h=new Headers();for(const [k,v]of Object.entries(res.headers)){if(v!==undefined)h.set(k,Array.isArray(v)?v.join(', '):v);}resolve(new Response([204,205,304].includes(res.statusCode)?null:Buffer.concat(chunks),{status:res.statusCode,headers:h}));});
 });
 const deadline=setTimeout(()=>req.destroy(Error('MCP request timed out.')),30000);deadline.unref();
 req.on('close',()=>clearTimeout(deadline));req.on('error',()=>reject(Error('HTTPS connection failed.')));
 if(init.body!==undefined&&typeof init.body!=='string'&&!Buffer.isBuffer(init.body)){req.destroy();reject(Error('Unsupported request body.'));return;}
 req.end(init.body);
 });
 };
}
export function redact(value,sites=[]){
 if(Array.isArray(value))return value.map(x=>redact(x,sites));
 if(value&&typeof value==='object')return Object.fromEntries(Object.entries(value).map(([k,v])=>[k,typeof v!=='boolean'&&/(password|secret|token|authorization|cookie|private_key|privateKey|backupKey|passphrase|api_key|license_key)/i.test(k)?'[redacted]':redact(v,sites)]));
 if(typeof value==='string'){for(const s of sites){for(const secret of [s.files?.ssh?.password,s.files?.sftp?.password,s.files?.ssh?.privateKey,s.files?.ssh?.passphrase,s.files?.sftp?.privateKey,s.files?.sftp?.passphrase,s.password,Buffer.from(s.username+':'+s.password).toString('base64')])if(secret)value=value.split(secret).join('[redacted]');}return value.replace(/(?:Basic|Bearer)\s+[^\s"<>]+/gi,'[redacted authentication]');}
 return value;
}

