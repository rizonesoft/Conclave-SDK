import {createHash,randomUUID} from 'node:crypto';
import {session,invoke,command,quote} from './ssh-transport.js';
import {Backups} from './backups.js';
const MAX=1048576;
const sha=b=>createHash('sha256').update(b).digest('hex');
export function relativePath(p,{write=false,root=false}={}){
 if(root&&p==='.')return '';
 if(typeof p!=='string'||!p||p.length>500||/[\x00-\x1f\x7f\\]/.test(p)||p.startsWith('/')||p.endsWith('/')||p.split('/').some(x=>!x||x==='.'||x==='..'||(x.startsWith('.')&&x!=='.htaccess')||/(?:wp-config|^id_(?:rsa|ed25519)|\.(?:pem|key|sql|cred|dpapi)$)/i.test(x)))throw Error('Unsafe or protected relative file path.');
 if(write&&(!p.startsWith('wp-content/')||p.split('/').some(x=>/^(?:backups?|updraft|ai1wm-backups)$/i.test(x))))throw Error('File changes are limited to wp-content, excluding backup directories.');
 return p;
}
async function safePath(sftp,root,p,{missing=false,write=false,directory=false}={}){
 const rel=relativePath(p,{write,root:directory});const actual=await invoke(sftp,'realpath',root);
 if(actual!==root)throw Error('Configured document root changed; reconfigure.');
 let full=root;const parts=rel?rel.split('/'):[];
 for(let i=0;i<parts.length;i++){
  full+='/'+parts[i];let stat;try{stat=await invoke(sftp,'lstat',full);}catch(e){if(missing&&i===parts.length-1&&e.code===2)return full;throw Error('Remote path unavailable.');}
  if(stat.isSymbolicLink()||(i<parts.length-1&&!stat.isDirectory()))throw Error('Symlinks and non-directory parents are blocked.');
  if(await invoke(sftp,'realpath',full)!==full)throw Error('Remote path escaped the configured directory.');
 }
 return full;
}
async function bytes(sftp,file){
 const stat=await invoke(sftp,'lstat',file);if(!stat.isFile()||stat.size>MAX||stat.nlink>1)throw Error('Only single-link regular files up to 1 MiB are supported.');
 const h=await invoke(sftp,'open',file,'r');let offset=0;const chunks=[];
 try{for(;;){const b=Buffer.alloc(Math.min(65536,MAX+1-offset));if(!b.length)throw Error('File exceeds 1 MiB.');let n;try{[n]=await invoke(sftp,'read',h,b,0,b.length,offset);}catch(e){if(e.code===1)break;throw e;}if(!n)break;offset+=n;if(offset>MAX)throw Error('File exceeds 1 MiB.');chunks.push(b.subarray(0,n));}}finally{await invoke(sftp,'close',h);}
 return Buffer.concat(chunks);
}
async function snapshot(sftp,file){let st;try{st=await invoke(sftp,'lstat',file);}catch(e){if(e.code===2)return {exists:false};throw e;}if(st.isDirectory())return {exists:true,type:'directory'};const b=await bytes(sftp,file);return {exists:true,type:'file',size:b.length,sha256:sha(b),mode:st.mode&0o777};}
function decode(p){const encoding=p.encoding??'utf8';if(encoding==='base64'&&!/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(p.content))throw Error('Invalid base64.');const b=Buffer.from(p.content,encoding);if(b.length>MAX)throw Error('File exceeds 1 MiB.');return b;}
export class FileService{
 constructor(registry,{withSession=session,backups=new Backups(registry.backupKey)}={}){this.session=withSession;this.backups=backups;}
 async sftp(site,work){if(!site.files)throw Error('SSH/SFTP is not configured for this site.');return this.session(site.files.sftp,async client=>work(await invoke(client,'sftp'),site.files.sftp.root));}
 async read(site,name,p){
  if(name==='sftp/list-backups'){const all=await this.backups.list(site.id),offset=p.offset??0,limit=p.limit??30;return {total:all.length,backups:all.slice(offset,offset+limit),next_offset:offset+limit<all.length?offset+limit:null};}
  if(name.startsWith('ssh/'))return this.ssh(site,name,p);
  return this.sftp(site,async(s,root)=>{
   const file=await safePath(s,root,p.path,{directory:name==='sftp/list-directory'});
   if(name==='sftp/list-directory'){
    // Stream directory batches and stop at a hard limit, instead of unbounded readdir.
    const h=await invoke(s,'opendir',file),all=[];try{for(;;){let batch;try{batch=await invoke(s,'readdir',h);}catch(e){if(e.code===1)break;throw e;}if(!batch||!batch.length)break;all.push(...batch);if(all.length>10000)throw Error('Directory exceeds 10,000 entries; choose a subdirectory.');}}finally{await invoke(s,'close',h);}
    const entries=all.filter(e=>!['.','..'].includes(e.filename)).sort((a,b)=>a.filename.localeCompare(b.filename));const offset=p.offset??0,limit=p.limit??30;return {path:p.path,total:entries.length,next_offset:offset+limit<entries.length?offset+limit:null,entries:entries.slice(offset,offset+limit).map(e=>({name:e.filename,size:e.attrs.size,type:e.attrs.isSymbolicLink()?'symlink':e.attrs.isDirectory()?'directory':'file'}))};
   }
   const state=await snapshot(s,file);if(name==='sftp/stat-file')return {path:p.path,...state};if(!state.exists||state.type!=='file')throw Error('Regular file required.');const b=await bytes(s,file);return {path:p.path,sha256:sha(b),bytes:b.length,encoding:p.encoding??'utf8',content:b.toString(p.encoding??'utf8')};
  });
 }
 async prepare(site,name,p){
  if(name==='ssh/flush-cache'){await this.ssh(site,'ssh/diagnostics',{check:'wordpress-version'});return {command:'wp --skip-plugins --skip-themes cache flush',recovery:'Cache data is regenerated by WordPress.'};}
  await this.backups.ready();let path=p.path;
  if(name==='sftp/restore-backup')path=(await this.backups.get(p.backup_id,site.id)).path;
  if(name==='sftp/write-file')decode(p);
  return this.sftp(site,async(s,root)=>{const file=await safePath(s,root,path,{missing:true,write:true});const before=await snapshot(s,file);
   if(name==='sftp/create-directory'&&before.exists)throw Error('Destination already exists.');
   if(name==='sftp/delete-file'&&(!before.exists||before.type!=='file'))throw Error('Regular file required.');
   if(before.exists&&before.type!=='file'&&name!=='sftp/create-directory')throw Error('Regular file required.');
   return {path,before,...(name==='sftp/write-file'?{new_sha256:sha(decode(p)),new_bytes:decode(p).length}:{}),recovery:before.exists?'Encrypted backup before replacement/deletion':'New path; no previous contents'};
  });
 }
 async execute(site,name,p,expected){
  if(name==='ssh/flush-cache')return this.ssh(site,name,p);
  return this.sftp(site,async(s,root)=>{
   const file=await safePath(s,root,expected.path,{missing:true,write:true});const before=await snapshot(s,file);
   if(JSON.stringify(before)!==JSON.stringify(expected.before))throw Error('File changed since preview; prepare again.');
   let backup_id=null;
   if(before.exists){const b=await bytes(s,file);if(sha(b)!==before.sha256)throw Error('File changed during backup.');backup_id=await this.backups.save({site:site.id,path:expected.path,sha256:before.sha256,mode:before.mode,content:b.toString('base64')});}
   const recheck=async()=>{await safePath(s,root,expected.path,{missing:true,write:true});if(JSON.stringify(await snapshot(s,file))!==JSON.stringify(before))throw Error('File changed before write; prepare again.');};
   if(name==='sftp/delete-file'){await recheck();await invoke(s,'unlink',file);return {deleted:true,path:expected.path,backup_id};}
   if(name==='sftp/create-directory'){await recheck();await invoke(s,'mkdir',file,{mode:0o755});return {created:true,path:expected.path};}
   const b=name==='sftp/restore-backup'?Buffer.from((await this.backups.get(p.backup_id,site.id)).content,'base64'):decode(p);
   const staging=site.files.sftp.stagingRoot??'/tmp';if(staging===root||staging.startsWith(root+'/')||await invoke(s,'realpath',staging)!==staging||!(await invoke(s,'lstat',staging)).isDirectory())throw Error('Private upload staging directory is unavailable.');const temporary=staging+'/.website-router-'+randomUUID()+'.tmp';let made=false;
   try{const h=await invoke(s,'open',temporary,'wx',0o600);made=true;try{for(let offset=0;offset<b.length;offset+=65536)await invoke(s,'write',h,b,offset,Math.min(65536,b.length-offset),offset);}finally{await invoke(s,'close',h);}if(sha(await bytes(s,temporary))!==sha(b))throw Error('Uploaded file hash mismatch.');await recheck();await invoke(s,'chmod',temporary,before.mode??0o644);await invoke(s,'ext_openssh_rename',temporary,file);made=false;const after=await snapshot(s,file);if(after.sha256!==sha(b))throw Error('Write readback failed; inspect remote file.');return {written:true,path:expected.path,bytes:b.length,sha256:after.sha256,backup_id};}
   catch{throw Error('File change failed or its result is uncertain; inspect remote state. Recovery backup: '+(backup_id??'none (new file)')+'. Do not auto-retry.');}
   finally{if(made)try{await invoke(s,'unlink',temporary);}catch{}}
  });
 }
 async ssh(site,name,p){
  if(!site.files)throw Error('SSH is not configured.');const config=site.files.ssh;
  let suffix;
  if(name==='ssh/php-lint'){relativePath(p.path,{write:true});if(!p.path.endsWith('.php'))throw Error('PHP file required.');await this.sftp(site,async(s,root)=>{const file=await safePath(s,root,p.path,{write:true});await snapshot(s,file);});suffix='php -n -l '+quote(p.path);}
  else if(name==='ssh/flush-cache')suffix='wp --skip-plugins --skip-themes cache flush';
  else suffix={'php-version':'php -n -v','wordpress-version':'wp --skip-plugins --skip-themes core version','plugins':'wp --skip-plugins --skip-themes plugin list --format=json','themes':'wp --skip-plugins --skip-themes theme list --format=json'}[p.check];
  if(!suffix)throw Error('Unsupported SSH command.');
  // The root is operator-configured. No user-supplied shell command or arbitrary WP-CLI arguments.
  const result=await this.session(config,c=>command(c,'cd -- '+quote(config.root)+' && '+suffix));
  if(result.exit_code!==0)throw Error('SSH command failed; inspect connection and site state.');return result;
 }
}
