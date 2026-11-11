import {loadToken} from '../src/credentials.js';import {validateRegistry,redact} from '../src/security.js';import {withSite,unpack} from '../src/upstream.js';import {writeFile} from 'node:fs/promises';
const r=validateRegistry(JSON.parse(await loadToken()));
const report=await Promise.all(r.connections.map(async s=>{try{return await withSite(s,async c=>{const d=unpack(await c.callTool({name:'mcp-adapter-discover-abilities',arguments:{}}));await writeFile('.local/'+s.id+'-abilities.json',JSON.stringify(redact(d,r.connections),null,2));return {site:s.id,data:d};});}catch(e){return {site:s.id,error:e.message};}}));console.log(JSON.stringify(report.map(({data,...row})=>({...row,abilities:data?.abilities?.length}))));

