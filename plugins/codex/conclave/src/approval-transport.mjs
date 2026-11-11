import {Transform} from 'node:stream';
import {StringDecoder} from 'node:string_decoder';
import {approvalInstructions} from './approval-policy.mjs';
const reads=new Set(['conclave_mcp_health','search_memory','read_memory','resolve_project_context','get_current_plan','get_tool_health']);
export function addGuidance(message){
 const r=message?.result;
 if(r?.serverInfo&&r?.protocolVersion)r.instructions=approvalInstructions+" For Conclave, show the exact proposed record/request, project, sources and possible automatic commit before invoking propose_memory_write or create_approval_request. The agent may approve them only within an explicit user memory/request task; backend policy still applies. Verify the returned committed/queued outcome and perform an appropriate scoped read-back. Unknown/new tools require review before use. "+(r.instructions??'');
 if(Array.isArray(r?.tools))for(const t of r.tools){
  if(!reads.has(t.name)){
   t.description="Show exact proposed inputs and effects, run preflight checks, and approve only within the explicit user task. Test and verify afterward. A proposal may commit immediately; a request creates durable state. Unknown/new tools require review. "+(t.description??'');
   t.annotations={...t.annotations,readOnlyHint:false,idempotentHint:false};
  }
 }
 return message;
}
// Modify metadata only, preserving request IDs, tool inputs/results and backend policy.
export function approvalTransport(){
 let buffer='';const decoder=new StringDecoder('utf8');
 function consume(stream){
  let end;while((end=buffer.indexOf('\n'))>=0){const line=buffer.slice(0,end);buffer=buffer.slice(end+1);if(!line.trim())continue;if(Buffer.byteLength(line)>4194304)throw Error('Conclave protocol frame exceeds limit');let m;try{m=JSON.parse(line);}catch{throw Error('Invalid Conclave protocol frame');}stream.push(JSON.stringify(addGuidance(m))+'\n');}
  if(Buffer.byteLength(buffer)>4194304)throw Error('Conclave protocol frame exceeds limit');
 }
 return new Transform({transform(chunk,encoding,callback){try{buffer+=decoder.write(chunk);consume(this);callback();}catch(e){callback(e);}},flush(callback){try{buffer+=decoder.end();if(buffer.trim())buffer+='\n';consume(this);callback();}catch(e){callback(e);}}});
}
