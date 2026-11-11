import {approvalInstructions} from './approval-policy.mjs';
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { z } from 'zod';
import { randomUUID } from 'node:crypto';
import { DomainsClient } from './client.js';

const label=z.string().trim().toLowerCase().min(1).max(63).regex(/^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/);
const suffix=z.string().trim().toLowerCase().min(2).max(190).refine(v=>v.split('.').every(x=>label.safeParse(x).success));
export const domain={sld:label.describe('Registrable label, e.g. example; use ASCII/punycode.'),tld:suffix.describe('Full suffix, e.g. co.za. Do not split it into za.')};
const text=z.string().min(1).max(2048).refine(v=>!/[\x00-\x1f]/.test(v));
const positive=z.number().int().positive().max(2147483647);
const dns={...domain,type:z.enum(['A','AAAA','MX','TXT','CNAME','CAA','NS','PTR','SPF','SRV']),name:text,content:text,ttl:z.number().int().min(60).max(2147483647),prio:z.number().int().min(0).max(65535).default(0)};
export const actions={
  set_nameservers:{method:'POST',path:'/domain/ns',shape:{...domain,ns1:suffix,ns2:suffix,ns3:suffix.optional(),ns4:suffix.optional(),ns5:suffix.optional()},extra:{dns:'custom'},impact:'Replaces nameservers. DNS availability, mail and websites can be affected.'},
  set_autorenew:{method:'POST',path:'/domain/autorenew',shape:{...domain,autorenew:z.boolean()},impact:'Changes automatic renewal and future billing. An explicit boolean is always sent; never toggles implicitly.'},
  set_lock:{method:'POST',path:'/domain/lock',shape:{...domain,action:z.enum(['lock','unlock'])},impact:'Changes the registry transfer lock.'},
  renew_domain:{method:'POST',path:'/domain/renew',shape:{...domain,period:z.number().int().min(1).max(10),note:text.optional()},impact:'Paid renewal. Confirm provider pricing and period before executing.'},
  register_domain:{method:'POST',path:'/domain',shape:{...domain,period:z.number().int().min(1).max(10),registrantTemplate:positive,nsTemplate:positive,adminTemplate:positive.optional(),billingTemplate:positive.optional(),techTemplate:positive.optional()},impact:'Paid domain registration using existing contact and nameserver templates. Confirm availability, template ownership and provider price first.'},
  add_dns_record:{method:'POST',path:'/domain/dns/entry',shape:dns,impact:'Adds a DNS record. Requires Domains.co.za Premium DNS.'},
  update_dns_record:{method:'PUT',path:'/domain/dns/entry',shape:{...dns,dnsId:positive},impact:'Replaces the specified DNS record values. Requires Premium DNS.'},
  delete_dns_record:{method:'DELETE',path:'/domain/dns/entry',shape:{...domain,dnsId:positive},impact:'Deletes one DNS record by ID. Requires Premium DNS.'}
};
export class Changes {
  constructor(client,{now=Date.now}={}){this.client=client;this.now=now;this.pending=new Map();}
  prepare(operation,parameters){
    const spec=actions[operation];if(!spec)throw new Error('Unsupported change.');
    const parsed=z.object(spec.shape).strict().safeParse(parameters);
    if(!parsed.success)throw new Error('Invalid change parameters: '+parsed.error.issues.map(i=>i.path.join('.')+': '+i.message).join('; '));
    for(const [id,p] of this.pending)if(p.expiresAt<=this.now())this.pending.delete(id);
    if(this.pending.size>=50)throw new Error('Too many outstanding previews. Execute or allow existing previews to expire.');
    const p={operation,parameters:{...parsed.data,...spec.extra},domain:parsed.data.sld+'.'+parsed.data.tld,expiresAt:this.now()+600000};
    const changeId=randomUUID();this.pending.set(changeId,structuredClone(p));
    return {approvalRequired:true,approvalMode:"task-scoped-agent",verificationRequired:true,changeId,...structuredClone(p),impact:spec.impact,executed:false,instruction:approvalInstructions};
  }
  async execute(changeId,confirmedDomain){
    const p=this.pending.get(changeId);if(!p||p.expiresAt<=this.now()){this.pending.delete(changeId);throw new Error('Preview missing or expired. Prepare a fresh change.');}
    if(confirmedDomain!==p.domain)throw new Error('Confirmed domain does not match preview.');
    // Consume BEFORE sending: failures and concurrent calls cannot replay a paid or destructive request.
    this.pending.delete(changeId);const spec=actions[p.operation];
    const result=await this.client.request(spec.method,spec.path,p.parameters);
    return {operation:p.operation,domain:p.domain,result,pending:Number(result.intReturnCode)===2,note:'Code 2 means queued, not completed. Inspect current state before declaring completion or retrying.'};
  }
}
export function createServer(client=new DomainsClient()){
 const server=new McpServer({name:'rizonetech-domains-co-za',version:'0.1.2'},{instructions:approvalInstructions});const changes=new Changes(client);
 const register=(name,description,inputSchema,handler,write=false)=>server.registerTool(name,{description,inputSchema,annotations:{readOnlyHint:!write,destructiveHint:write,idempotentHint:!write,openWorldHint:true}},async args=>{
  try{const result=await handler(args);const out=JSON.stringify(result);if(Buffer.byteLength(out)>200000)throw new Error('Result too large for chat. Request a smaller page or narrower domain selection.');return{content:[{type:'text',text:out}]};}
  catch(e){return{isError:true,content:[{type:'text',text:e.message}]};}
 });
 register('connection_status','Check authentication and account funds read access without returning account data.',{},async()=>{await client.request('GET','/domain/funds');return{connected:true,credentialStore:process.platform==='linux'?'systemd encrypted credentials':'Windows DPAPI',onePasswordRuntimeAccess:false};});
 register('list_domains','List returned reseller inventory, including provider expiry fields. offset and limit slice the returned set locally: the documented API exposes only a tld filter. Inspect coverage; never assume complete inventory.',{tld:suffix.optional(),offset:z.number().int().min(0).max(1000000).default(0),limit:z.number().int().min(1).max(100).default(50)},async({offset,limit,...query})=>{
  const data=await client.request('GET','/domain/list',query);if(!Array.isArray(data.arrDomains))throw new Error('Unexpected inventory response.');
  const count=data.arrDomains.length;const reported=Number(data.intFilterTotal??data.intTotal);
  return{domains:data.arrDomains.slice(offset,offset+limit),coverage:{providerReturned:count,providerReportedTotal:Number.isFinite(reported)?reported:null,providerComplete:Number.isFinite(reported)&&reported===count,offset,limit,nextOffset:offset+limit<count?offset+limit:null},note:'Offsets are local slices of a fresh API response, not a stable snapshot. If provider coverage is incomplete, use TLD filters; no undocumented paging parameters are sent.'};
 });
 for(const [name,path,description] of [
  ['get_domain','/domain','Inspect a managed domain, dates, contacts, and nameservers. Transfer authorization secrets are omitted.'],
  ['check_availability','/domain/check','Check availability. Use isAvailable, not intReturnCode zero, to decide availability.'],
  ['get_dns_records','/domain/dns','Inspect Premium DNS records with their IDs.'],
  ['get_domain_lock','/domain/lock','Inspect the registry lock state.'],
  ['get_transfer_status','/domain/transfer','Inspect domain transfer status. Does not initiate or approve a transfer.'],
  ['get_dnssec_records','/domain/dsrecords','Inspect domain DS records.'],
  ['get_glue_records','/domain/gluerecords','Inspect domain glue records.']
 ])register(name,description,domain,p=>client.request('GET',path,p));
 register('list_tlds','Read supported TLDs.',{},()=>client.request('GET','/domain/tlds'));
 register('get_funds','Read account balance and billing status.',{},()=>client.request('GET','/domain/funds'));
 register('get_pricing','Read reseller TLD prices; verify fees before paid registration or renewal.',{},()=>client.request('GET','/reseller/pricing',{format:'tld'}));
 for(const kind of ['contact','ns'])register('list_'+kind+'_templates','List existing '+kind+' templates; preserve provider pagination information.',{startPoint:z.number().int().min(0).default(0),limit:z.number().int().min(1).max(100).default(25)},p=>client.request('GET','/template/'+kind,p));
 for(const [action,spec] of Object.entries(actions))register('prepare_'+action,spec.impact+' Creates a local preview only; never changes the provider.',spec.shape,p=>changes.prepare(action,p));
 register('execute_change','Show the preview and preflight evidence. The agent may approve within the explicit user task; ask for unclear/additional scope. Test and verify afterward. Execute a prepared change exactly once after user authorization for its exact action and domain. Paid actions can debit the reseller balance. No automatic retries.',{changeId:z.string().uuid(),confirmedDomain:z.string().min(3).max(253)},async p=>({result:await changes.execute(p.changeId,p.confirmedDomain),verification:{required:true,status:'not-yet-verified',instruction:approvalInstructions}}),true);
 return server;
}
if(process.env.DOMAINS_TEST_IMPORT!=='1')await createServer().connect(new StdioServerTransport());
