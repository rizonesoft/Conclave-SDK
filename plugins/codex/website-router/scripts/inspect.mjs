import {loadToken} from '../src/credentials.js';
import {validateRegistry,redact} from '../src/security.js';
import {listSiteTools,callSite} from '../src/upstream.js';
import {writeFile,mkdir} from 'node:fs/promises';
const registry=validateRegistry(JSON.parse(await loadToken()));await mkdir('.local',{recursive:true});
const report=await Promise.all(registry.connections.map(async site=>{
 try{const tools=await listSiteTools(site);await writeFile('.local/'+site.id+'-tools.json',JSON.stringify(redact(tools,registry.connections),null,2));return {id:site.id,url:site.siteUrl,environment:site.environment,connected:true,tools};}
 catch(e){return {id:site.id,url:site.siteUrl,environment:site.environment,connected:false,error:e.message};}
}));await writeFile('.local/inventory.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report.map(({tools,...row})=>({...row,tools:tools?.map(t=>t.name)}))));

