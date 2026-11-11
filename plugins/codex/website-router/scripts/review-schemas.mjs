import {loadToken} from '../src/credentials.js';import {validateRegistry,redact} from '../src/security.js';import {withSite,unpack} from '../src/upstream.js';import {readFile,writeFile} from 'node:fs/promises';
const registry=validateRegistry(JSON.parse(await loadToken()));
for(let start=0;start<registry.connections.length;start+=3){await Promise.all(registry.connections.slice(start,start+3).map(async s=>{try{await withSite(s,async c=>{
const names=JSON.parse(await readFile('.local/'+s.id+'-abilities.json','utf8')).abilities.map(a=>a.name);const definitions=[];
for(let n=0;n<names.length;n+=3){definitions.push(...await Promise.all(names.slice(n,n+3).map(async name=>unpack(await c.callTool({name:'mcp-adapter-get-ability-info',arguments:{ability_name:name}},undefined,{timeout:45000})))));}
await writeFile('.local/'+s.id+'-definitions.json',JSON.stringify(redact(definitions,registry.connections),null,2));console.log(JSON.stringify({site:s.id,schemas:definitions.length}));});}catch(e){console.log(JSON.stringify({site:s.id,error:e.message}));}}));}
