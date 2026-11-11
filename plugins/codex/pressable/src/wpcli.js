// Commands are provider-logged. Keep one explicit site and command per preview.
const prefixes=[['core','version'],['core','check-update'],['core','verify-checksums'],['plugin','list'],['plugin','status'],['theme','list'],['theme','status'],['theme','mod','get'],['theme','mod','list'],['theme','mod','set'],['media','import'],['post','list'],['post','get'],['post','update'],['post','meta','get'],['post','meta','list'],['post','meta','update'],['post','meta','patch'],['option','get'],['option','list'],['option','update'],['option','patch'],['menu','list'],['menu','location','list'],['menu','item','list'],['menu','item','update'],['menu','item','add-custom'],['widget','list'],['widget','update'],['sidebar','list'],['cache','flush']];
export function validateWPCLI(commands){
 if(!Array.isArray(commands)||commands.length!==1||typeof commands[0]!=='string'||!commands[0].trim()||commands[0].length>8192)throw Error('Submit exactly one WP-CLI command, up to 8192 characters, per preview.');
 const command=commands[0];let quote='',word='',active=false;const words=[];
 for(const c of command){
  if(/[\x00-\x1f\x7f$`\\]/.test(c))throw Error('Control characters, escapes and command substitution are not supported.');
  if(quote){if(c===quote)quote='';else word+=c;active=true;continue;}
  if(c==='"'||c==="'"){quote=c;active=true;continue;}
  if(/[;&|<>()*?{}~#]/.test(c))throw Error('Shell operators, globbing and comments are not supported. Quote literal data.');
  if(/\s/.test(c)){if(active){words.push(word);word='';active=false;}}else{word+=c;active=true;}
 }
 if(quote)throw Error('Unclosed command quote.');if(active)words.push(word);
 if(!prefixes.some(p=>p.every((v,i)=>words[i]===v)))throw Error('WP-CLI subcommand is outside the reviewed content/diagnostic scope. See WPCLI.md. Omit the wp prefix.');
 for(const word of words){
  if(/^--(?:path|url|ssh|ssh-args|http|alias|user|require|exec|prompt|config|allow-root)(?:=|$)/i.test(word)||word.startsWith('@'))throw Error('WP-CLI target changes, PHP loaders, impersonation and interactive flags are blocked.');
  if(/(?:password|passwd|secret|token|api[_-]?key|private[_-]?key|authorization|user_pass|wp-config|\.env)/i.test(word))throw Error('Do not submit credentials through provider-logged WP-CLI commands.');
  for(const match of word.matchAll(/https?:\/\/[^\s'"<>]+/g)){const url=new URL(match[0]);if(url.username||url.password||url.search||url.hash)throw Error('Use a URL without credentials, query strings or fragments; commands are logged by Pressable.');}
 }
 return {command,subcommand:prefixes.find(p=>p.every((v,i)=>words[i]===v)).join(' ')};
}
export const wpcliPolicy={maxCommands:1,maxCharacters:8192,requiresPreview:true,providerLogsCommands:true,allowedSubcommands:prefixes.map(p=>p.join(' ')),completion:'Poll get_site_wordpress_operation with the returned job_id. Success output can be truncated to 500 characters; verify the intended website result separately.'};
