import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { z } from 'zod';
import { randomUUID } from 'node:crypto';
import { BunnyClient } from './client.js';

// Order matches the provider enum: the API takes the index.
export const RECORD_TYPES=['A','AAAA','CNAME','TXT','MX','Redirect','Flatten','PullZone','SRV','CAA','PTR','Script','NS','SVCB','HTTPS'];
const WRITABLE_TYPES=['A','AAAA','CNAME','TXT','MX','Redirect','Flatten','PullZone','SRV','CAA','NS'];
const id=z.number().int().positive().max(Number.MAX_SAFE_INTEGER);
const text=(max,min=0)=>z.string().min(min).max(max).refine(v=>!/[\x00-\x1f]/.test(v),'control characters are not allowed');
const label=/^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/;
const domainName=z.string().trim().toLowerCase().min(3).max(253).refine(v=>v.includes('.')&&v.split('.').every(x=>x.length<=63&&label.test(x)),'use an ASCII/punycode domain such as example.com');
const date=z.string().regex(/^\d{4}-\d{2}-\d{2}$/,'use YYYY-MM-DD');
const paging={search:text(200).optional(),page:z.number().int().min(1).max(100000).default(1),perPage:z.number().int().min(5).max(1000).default(100)};
const record={
  type:z.enum(WRITABLE_TYPES),
  name:text(253).describe('Record name relative to the zone; empty string for the apex.'),
  value:text(4096,1),
  ttl:z.number().int().min(15).max(2147483647),
  priority:z.number().int().min(0).max(65535).optional(),
  weight:z.number().int().min(0).max(65535).optional(),
  port:z.number().int().min(0).max(65535).optional(),
  flags:z.number().int().min(0).max(255).optional(),
  tag:z.enum(['issue','issuewild','iodef']).optional(),
  pullZoneId:id.optional(),
  disabled:z.boolean().optional(),
  comment:text(500).optional()
};
function checkRecord(r,ctx){
  const need=(field,types)=>{if(types.includes(r.type)&&r[field]===undefined)ctx.addIssue({code:'custom',path:[field],message:field+' is required for '+r.type+' records'});};
  need('priority',['MX','SRV']);need('weight',['SRV']);need('port',['SRV']);need('flags',['CAA']);need('tag',['CAA']);need('pullZoneId',['PullZone']);
}
const recordBody=r=>Object.fromEntries(Object.entries({Type:RECORD_TYPES.indexOf(r.type),Name:r.name,Value:r.value,Ttl:r.ttl,Priority:r.priority,Weight:r.weight,Port:r.port,Flags:r.flags,Tag:r.tag,PullZoneId:r.pullZoneId,Disabled:r.disabled,Comment:r.comment}).filter(([,v])=>v!==undefined));
const named=rec=>({...rec,TypeName:typeof rec.Type==='number'?RECORD_TYPES[rec.Type]??null:rec.Type});
async function zoneDomain(client,zoneId){const zone=await client.request('GET','/dnszone/'+zoneId);if(typeof zone.Domain!=='string')throw new Error('Unexpected DNS zone response.');return zone;}
async function currentRecord(client,zoneId,recordId){
  const zone=await zoneDomain(client,zoneId);const rec=(zone.Records||[]).find(r=>r.Id===recordId);
  if(!rec)throw new Error('Record '+recordId+' was not found in zone '+zone.Domain+'. Read the zone again and use an existing record ID.');
  const current=named(rec);
  if(!WRITABLE_TYPES.includes(current.TypeName))throw new Error(current.TypeName+' records are read-only in this version; change them in the bunny.net dashboard.');
  return {target:zone.Domain,current};
}
export const actions={
  purge_pull_zone:{shape:{pullZoneId:id,cacheTag:text(200,1).optional()},
    resolve:async(c,p)=>{const zone=await c.request('GET','/pullzone/'+p.pullZoneId,{query:{includeCertificate:false}});if(typeof zone.Name!=='string')throw new Error('Unexpected pull zone response.');return{target:zone.Name};},
    request:p=>({method:'POST',path:'/pullzone/'+p.pullZoneId+'/purgeCache',body:p.cacheTag?{CacheTag:p.cacheTag}:{}}),
    impact:'Purges the whole pull zone cache, or only one cache tag when given. Origin load rises while the cache refills.'},
  purge_url:{shape:{url:z.string().url().max(2048).refine(v=>/^https?:\/\//i.test(v),'http or https URL required').describe('Exact URL; a trailing * purges the path prefix.'),async:z.boolean().default(false)},
    resolve:async(c,p)=>({target:new URL(p.url.replace(/\*$/,'')).hostname}),
    request:p=>({method:'POST',path:'/purge',query:{url:p.url,async:p.async}}),
    impact:'Purges the URL (or wildcard prefix) from every pull zone that serves it.'},
  add_dns_zone:{shape:{domain:domainName},
    resolve:async(c,p)=>({target:p.domain}),
    request:p=>({method:'POST',path:'/dnszone',body:{Domain:p.domain}}),
    impact:'Creates a DNS zone on bunny.net. It does not change the registrar nameservers; the zone serves nothing until delegation is switched.'},
  add_dns_record:{shape:{zoneId:id,...record},refine:checkRecord,
    resolve:async(c,p)=>({target:(await zoneDomain(c,p.zoneId)).Domain}),
    request:({zoneId,...r})=>({method:'PUT',path:'/dnszone/'+zoneId+'/records',body:recordBody(r)}),
    impact:'Adds a DNS record. Live immediately if the zone is delegated to bunny.net.'},
  update_dns_record:{shape:{zoneId:id,recordId:id,...record},refine:checkRecord,
    resolve:(c,p)=>currentRecord(c,p.zoneId,p.recordId),recheck:p=>[p.zoneId,p.recordId],
    request:({zoneId,recordId,...r})=>({method:'POST',path:'/dnszone/'+zoneId+'/records/'+recordId,body:{...recordBody(r),Id:recordId}}),
    impact:'Replaces the record values shown in current with the new values. Keep current to reverse the change.'},
  delete_dns_record:{shape:{zoneId:id,recordId:id},
    resolve:(c,p)=>currentRecord(c,p.zoneId,p.recordId),recheck:p=>[p.zoneId,p.recordId],
    request:p=>({method:'DELETE',path:'/dnszone/'+p.zoneId+'/records/'+p.recordId}),
    impact:'Deletes one DNS record. Keep current to recreate it if needed.'}
};
export class Changes {
  constructor(client,{now=Date.now}={}){this.client=client;this.now=now;this.pending=new Map();}
  async prepare(operation,parameters){
    const spec=actions[operation];if(!spec)throw new Error('Unsupported change.');
    let schema=z.object(spec.shape).strict();if(spec.refine)schema=schema.superRefine(spec.refine);
    const parsed=schema.safeParse(parameters);
    if(!parsed.success)throw new Error('Invalid change parameters: '+parsed.error.issues.map(i=>i.path.join('.')+': '+i.message).join('; '));
    for(const [key,p] of this.pending)if(p.expiresAt<=this.now())this.pending.delete(key);
    if(this.pending.size>=50)throw new Error('Too many outstanding previews. Execute or allow existing previews to expire.');
    const {target,current}=await spec.resolve(this.client,parsed.data);
    const p={operation,target,request:spec.request(parsed.data),current,recheck:spec.recheck?.(parsed.data),expiresAt:this.now()+600000};
    const changeId=randomUUID();this.pending.set(changeId,p);
    return {changeId,operation,target,request:p.request,...(current?{current}:{}),impact:spec.impact,expiresAt:p.expiresAt,executed:false,instruction:'Execute only with user authorization for this exact action and target. Preview expires in 10 minutes or on plugin restart.'};
  }
  async execute(changeId,confirmedTarget){
    const p=this.pending.get(changeId);if(!p||p.expiresAt<=this.now()){this.pending.delete(changeId);throw new Error('Preview missing or expired. Prepare a fresh change.');}
    if(confirmedTarget!==p.target)throw new Error('Confirmed target does not match preview.');
    // Consume BEFORE sending: failures and concurrent calls cannot replay a destructive request.
    this.pending.delete(changeId);
    if(p.recheck){
      const {current}=await currentRecord(this.client,...p.recheck);
      if(JSON.stringify(current)!==JSON.stringify(p.current))throw new Error('The record changed after the preview was prepared. Nothing was sent; read the zone and prepare a fresh change.');
    }
    const {method,path,...options}=p.request;
    const result=await this.client.request(method,path,options);
    return {operation:p.operation,target:p.target,result,note:'Confirm with a fresh read before reporting completion. No automatic retries.'};
  }
}
const pageInfo=(data,items)=>Array.isArray(data)?{currentPage:1,totalItems:items.length,hasMoreItems:false}:{currentPage:data.CurrentPage??null,totalItems:data.TotalItems??null,hasMoreItems:data.HasMoreItems??null};
const itemsOf=data=>{const items=Array.isArray(data)?data:data.Items;if(!Array.isArray(items))throw new Error('Unexpected list response.');return items;};
export function createServer(client=new BunnyClient()){
 const server=new McpServer({name:'rizonetech-bunny-net',version:'0.1.0'});const changes=new Changes(client);
 const register=(name,description,inputSchema,handler,write=false)=>server.registerTool(name,{description,inputSchema,annotations:{readOnlyHint:!write,destructiveHint:write,idempotentHint:!write,openWorldHint:true}},async args=>{
  try{const result=await handler(args);const out=JSON.stringify(result);if(Buffer.byteLength(out)>200000)throw new Error('Result too large for chat. Use search, a smaller perPage, or a single-zone read.');return{content:[{type:'text',text:out}]};}
  catch(e){return{isError:true,content:[{type:'text',text:e.message}]};}
 });
 const list=(path,project,extra={})=>async({search,page,perPage,...rest})=>{const data=await client.request('GET',path,{query:{search,page,perPage,...extra,...rest}});const items=itemsOf(data);return{items:items.map(project),paging:pageInfo(data,items)};};
 register('connection_status','Check API key authentication with a harmless pull zone read. Returns no account data.',{},async()=>{await client.request('GET','/pullzone',{query:{page:1,perPage:5}});return{connected:true,credentialStore:'Windows DPAPI',onePasswordRuntimeAccess:false};});
 register('list_pull_zones','List pull zones with origin, hostnames and monthly usage. Use get_pull_zone for full settings. Check paging.hasMoreItems.',paging,
  list('/pullzone',z=>({Id:z.Id,Name:z.Name,OriginUrl:z.OriginUrl,Enabled:z.Enabled,Suspended:z.Suspended,Type:z.Type,StorageZoneId:z.StorageZoneId,MonthlyBandwidthUsed:z.MonthlyBandwidthUsed,MonthlyCharges:z.MonthlyCharges,Hostnames:(z.Hostnames||[]).map(h=>({Value:h.Value,ForceSSL:h.ForceSSL,HasCertificate:h.HasCertificate,IsSystemHostname:h.IsSystemHostname}))}),{includeCertificate:false}));
 register('get_pull_zone','Read one pull zone. Token keys, signing secrets, certificates and edge-rule action parameters are removed.',{pullZoneId:id},p=>client.request('GET','/pullzone/'+p.pullZoneId,{query:{includeCertificate:false}}));
 register('list_dns_zones','List DNS zones with nameserver delegation status and record counts. Check paging.hasMoreItems.',paging,
  list('/dnszone',z=>({Id:z.Id,Domain:z.Domain,RecordCount:Array.isArray(z.Records)?z.Records.length:null,NameserversDetected:z.NameserversDetected,CustomNameserversEnabled:z.CustomNameserversEnabled,Nameserver1:z.Nameserver1,Nameserver2:z.Nameserver2,DnsSecEnabled:z.DnsSecEnabled,DateModified:z.DateModified})));
 register('get_dns_zone','Read one DNS zone with all records and their IDs. TypeName gives the readable record type.',{zoneId:id},async p=>{const zone=await zoneDomain(client,p.zoneId);return{...zone,Records:(zone.Records||[]).map(named)};});
 register('export_dns_zone','Export one DNS zone as a BIND zone file.',{zoneId:id},async p=>{const r=await client.request('GET','/dnszone/'+p.zoneId+'/export');return{zoneFile:r.text??r};});
 register('list_storage_zones','List storage zones with region, usage and linked pull zones. Passwords are removed. Check paging.hasMoreItems.',{...paging,includeDeleted:z.boolean().default(false)},
  list('/storagezone',z=>({Id:z.Id,Name:z.Name,Region:z.Region,ReplicationRegions:z.ReplicationRegions,StorageUsed:z.StorageUsed,FilesStored:z.FilesStored,StorageHostname:z.StorageHostname,ZoneTier:z.ZoneTier,Deleted:z.Deleted,DateModified:z.DateModified,PullZones:(z.PullZones||[]).map(x=>({Id:x.Id,Name:x.Name}))})));
 register('get_storage_zone','Read one storage zone. Passwords and linked pull zone secrets are removed.',{storageZoneId:id},p=>client.request('GET','/storagezone/'+p.storageZoneId));
 register('get_statistics','Read traffic statistics for the account or one pull zone. Defaults to the provider range (last 30 days) when dates are omitted.',{dateFrom:date.optional(),dateTo:date.optional(),pullZoneId:id.optional(),hourly:z.boolean().default(false)},({pullZoneId,...q})=>client.request('GET','/statistics',{query:{...q,pullZone:pullZoneId}}));
 for(const [action,spec] of Object.entries(actions))register('prepare_'+action,spec.impact+' Reads current state and creates a local preview only; never changes the provider.',spec.shape,p=>changes.prepare(action,p));
 register('execute_change','Execute a prepared change exactly once after user authorization for its exact action and target. No automatic retries.',{changeId:z.string().uuid(),confirmedTarget:z.string().min(1).max(2048)},p=>changes.execute(p.changeId,p.confirmedTarget),true);
 return server;
}
if(process.env.BUNNY_TEST_IMPORT!=='1')await createServer().connect(new StdioServerTransport());
