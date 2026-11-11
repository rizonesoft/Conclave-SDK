import {Client} from '@modelcontextprotocol/sdk/client/index.js';
import {StreamableHTTPClientTransport} from '@modelcontextprotocol/sdk/client/streamableHttp.js';
export const ENDPOINT='https://mcp.pressable.com';
export function unpack(result){
 if(result.isError)throw Error('Pressable rejected the request. No automatic retry was attempted.');
 if(result.structuredContent)return result.structuredContent;
 const text=result.content?.filter(x=>x.type==='text').map(x=>x.text).join('\n');
 try{return JSON.parse(text);}catch{return {text:text??''};}
}
export function upstream(token){
 return async(name,args)=>{
  const client=new Client({name:'rizonetech-pressable',version:'0.2.1'});
  try{
   const transport=new StreamableHTTPClientTransport(new URL(ENDPOINT),{requestInit:{headers:{Authorization:`Bearer ${token}`},redirect:'error'},fetch:async(url,init)=>{
    if(new URL(url).origin!==new URL(ENDPOINT).origin)throw Error('Unexpected endpoint');
    const response=await fetch(url,{...init,redirect:'error',signal:AbortSignal.any([...(init?.signal?[init.signal]:[]),AbortSignal.timeout(30000)])});
    // Bound the body before the SDK parses JSON or SSE. This server returns finite responses.
    if(response.body){const reader=response.body.getReader();const parts=[];let size=0;while(true){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>4*1024*1024){await reader.cancel();throw Error('Response limit');}parts.push(value);}return new Response(Buffer.concat(parts),{status:response.status,statusText:response.statusText,headers:response.headers});}
    return response;
   }});
   await client.connect(transport,{timeout:30000});
   return unpack(await client.callTool({name,arguments:args},undefined,{timeout:45000}));
  }catch{throw Error('Pressable request failed or its outcome is uncertain. No automatic retry was attempted. For a change, inspect the site before preparing another request.');}
  finally{await client.close().catch(()=>{});}
 };
}
export function redact(value,token=''){
 if(Array.isArray(value))return value.map(x=>redact(x,token));
 if(value&&typeof value==='object')return Object.fromEntries(Object.entries(value).map(([key,v])=>[key,typeof v!=='boolean'&&/(?:password|secret|token|authorization|cookie|private_key|download_url|login_url)/i.test(key)?'[redacted]':redact(v,token)]));
 if(typeof value==='string')return (token?value.split(token).join('[redacted]'):value).replace(/Bearer\s+[^\s"<>]+/gi,'Bearer [redacted]').replace(/https?:\/\/[^\s"<>]+/g,url=>{try{const u=new URL(url);if(!u.username&&!u.password&&!u.search&&!u.hash)return url;u.username='';u.password='';u.search='';u.hash='';return u.toString();}catch{return '[redacted URL]';}});
 return value;
}