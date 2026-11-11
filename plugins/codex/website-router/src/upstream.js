import {Client} from '@modelcontextprotocol/sdk/client/index.js';
import {StreamableHTTPClientTransport} from '@modelcontextprotocol/sdk/client/streamableHttp.js';
import {siteFetch} from './security.js';
export function unpack(result){
 if(result.isError)throw Error('Website rejected the operation. No retry was attempted.');
 if(result.structuredContent)return result.structuredContent;
 const text=result.content?.filter(x=>x.type==='text').map(x=>x.text).join('\n');
 try{return JSON.parse(text);}catch{return {text:text??''};}
}
export async function withSite(site,work){
 const client=new Client({name:'rizonetech-website-router',version:'0.1.0'});
 let transport;
 try{
 transport=new StreamableHTTPClientTransport(new URL(site.endpoint),{fetch:siteFetch(site),requestInit:{redirect:'error'}});
 await client.connect(transport,{timeout:35000});
 return await work(client);
 }catch{throw Error('Website MCP request failed or its outcome is uncertain. No automatic retry. Check authentication, endpoint and availability; inspect the site before repeating a change.');}
 finally{await transport?.terminateSession().catch(()=>{});await client.close().catch(()=>{});}
}
export async function listSiteTools(site){return withSite(site,async c=>{const all=[];let cursor;for(let page=0;page<10;page++){const r=await c.listTools(cursor?{cursor}:{});all.push(...r.tools);if(all.length>500)throw Error('Too many tools.');cursor=r.nextCursor;if(!cursor)return all;}throw Error('Tool list exceeds pagination bound.');});}
export async function callSite(site,name,args){return withSite(site,async c=>unpack(await c.callTool({name,arguments:args},undefined,{timeout:45000})));}
