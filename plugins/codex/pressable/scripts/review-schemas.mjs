import {Client} from '@modelcontextprotocol/sdk/client/index.js';
import {StreamableHTTPClientTransport} from '@modelcontextprotocol/sdk/client/streamableHttp.js';
import {loadToken} from '../src/credentials.js';
import {writeFile} from 'node:fs/promises';
const reads = ['get_site_wordpress_operation','list_site_wordpress_operations','get_account_site_counts','get_account_details','get_site_creation_options','validate_site_name','list_sites','search_sites','get_site_status','get_site_details','get_site_activity_logs','get_account_activity_logs','list_site_domains','get_domain_details','get_site_edge_cache_status','get_site_php_logs','get_site_webserver_logs','list_site_plugins','get_site_plugin_security_alerts','list_site_themes','get_site_theme_security_alerts','list_site_backups','get_site_backup_details','list_site_ondemand_backups','get_site_ondemand_backup_details','get_site_statistics','get_site_performance_report','get_site_usage_report','get_site_metrics','list_site_restores','get_site_restore_status','list_alerts','get_alert','get_alert_counts','get_site_git_configuration','list_site_git_history'];
const changes = ['run_site_wpcli_commands','create_site','clone_site','update_site_display_name','update_site_php_version','update_site_wordpress_version','update_site_wp_environment_type','enable_site','disable_site','delete_site','add_site_domain','remove_site_domain','set_primary_domain','purge_site_edge_cache','flush_site_object_cache','purge_site_cdn_cache','create_site_ondemand_backup','delete_site_ondemand_backup','restore_site_backup','update_site_plugins','update_site_themes'];
const c=new Client({name:'rizonetech-pressable-schema-review',version:'0.1.0'});
try{
 const token=await loadToken();await c.connect(new StreamableHTTPClientTransport(new URL('https://mcp.pressable.com'),{requestInit:{headers:{Authorization:`Bearer ${token}`},redirect:'error'}}),{timeout:30000});
 const definitions=[];
 for(const name of [...reads,...changes]){
  const result=await c.callTool({name:'describe_tool',arguments:{tool_name:name}},undefined,{timeout:30000});
  if(result.isError){console.log('Unavailable operation: '+name);throw Error('Schema unavailable');}
  const data=result.structuredContent??JSON.parse(result.content.find(x=>x.type==='text').text);
  definitions.push({mode:reads.includes(name)?'read':'change',...data});
 }
 await writeFile(new URL('../src/operations.json',import.meta.url),JSON.stringify(definitions,null,2)+'\n');

 console.log(`Discovered ${definitions.length} operation schemas.`);
}catch(e){console.error('Schema discovery failed: '+e.name+' code '+e.code+'; no provider changes attempted.');process.exitCode=1;}finally{await c.close();}