import {approvalInstructions} from './approval-policy.mjs';
import Ajv from 'ajv';
import {Server} from '@modelcontextprotocol/sdk/server/index.js';
import {StdioServerTransport} from '@modelcontextprotocol/sdk/server/stdio.js';
import {ListToolsRequestSchema,CallToolRequestSchema} from '@modelcontextprotocol/sdk/types.js';
import {loadToken} from './credentials.js';
import {Gateway,operationCount} from './gateway.js';
import {upstream,redact} from './upstream.js';
const obj=(properties,required=[])=>({type:'object',properties,required,additionalProperties:false});
const str={type:'string',minLength:1,maxLength:200};
const args={type:'object'};
const read={readOnlyHint:true,destructiveHint:false,idempotentHint:true,openWorldHint:true};
const tools=[
 {name:'connection_status',description:'Verify Pressable authentication with a harmless account-capacity read. Returns no account details.',inputSchema:obj({}),annotations:read},
 {name:'discover_operations',description:'List reviewed Pressable hosting and reviewed WP-CLI operations and their read/change routing. New upstream tools are not automatically granted access.',inputSchema:obj({query:{type:'string',maxLength:200}}),annotations:{...read,openWorldHint:false}},
 {name:'describe_operation',description:'Get the exact input schema and effects of one reviewed Pressable hosting or WP-CLI operation, including command restrictions.',inputSchema:obj({operation:str},['operation']),annotations:{...read,openWorldHint:false}},
 {name:'read_operation',description:'Run a reviewed read-only Pressable hosting operation. One bounded page per call; preserve pagination and incomplete coverage. Use get_site_wordpress_operation to check queued WP-CLI jobs. Cannot submit commands or execute changes.',inputSchema:obj({operation:str,parameters:args},['operation']),annotations:read},
 {name:'prepare_change',description:'Create a five-minute single-use preview of an exact Pressable hosting or single WP-CLI command change, including site details and consequences. Does not change Pressable. Present the complete preview to the user.',inputSchema:obj({operation:str,parameters:args},['operation','parameters']),annotations:{readOnlyHint:false,destructiveHint:false,idempotentHint:false,openWorldHint:true}},
 {name:'execute_change',description:'Show the preview and preflight evidence. The agent may approve within the explicit user task; ask for unclear/additional scope. Test and verify afterward. Execute a prepared Pressable change once, only within the explicit user task or separately approved scope. Confirmed is an assertion by the caller, not independent human authentication. Never retry uncertain writes.',inputSchema:obj({preview_id:str,confirmed:{type:'boolean',const:true}},['preview_id','confirmed']),annotations:{readOnlyHint:false,destructiveHint:true,idempotentHint:false,openWorldHint:true}}
];
const validators=new Map(tools.map(t=>[t.name,new Ajv({strict:false}).compile(t.inputSchema)]));
const server=new Server({name:'pressable',version:'0.2.2'},{capabilities:{tools:{}},instructions:approvalInstructions});
let token;let gateway;
async function service(){if(!gateway){token=await loadToken();gateway=new Gateway(upstream(token));}return gateway;}
server.setRequestHandler(ListToolsRequestSchema,async()=>({tools}));
server.setRequestHandler(CallToolRequestSchema,async request=>{
 try{
 const {name,arguments:a={}}=request.params;if(!validators.get(name)?.(a))throw Error('Invalid tool arguments.');const g=await service();let data;
 switch(name){
 case 'connection_status':await g.read('get_account_site_counts',{});data={connected:true,provider:'Pressable',operations:operationCount,credentialMode:process.platform==='win32'?'windows-dpapi':'systemd-encrypted',runtime1Password:false};break;
 case 'discover_operations':data=g.discover(a.query);break;
 case 'describe_operation':data=g.describe(a.operation);break;
 case 'read_operation':data=await g.read(a.operation,a.parameters??{});break;
 case 'prepare_change':data=await g.prepare(a.operation,a.parameters);break;
 case 'execute_change':data={result:await g.execute(a.preview_id,a.confirmed),verification:{required:true,status:'not-yet-verified',instruction:approvalInstructions}};break;
 default:throw Error('Unknown tool.');}
 return {content:[{type:'text',text:JSON.stringify(redact(data,token))}]};
 }catch(e){return {isError:true,content:[{type:'text',text:redact(e.message,token)}]};}
});
await server.connect(new StdioServerTransport());
process.stdin.on('end',()=>{server.close().finally(()=>process.exit(0));});