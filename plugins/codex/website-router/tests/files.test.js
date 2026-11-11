import test from 'node:test';import assert from 'node:assert/strict';
import {mkdtemp,writeFile,readFile,mkdir,chmod,rm,lstat,realpath,open,rename,unlink,readdir} from 'node:fs/promises';import {tmpdir} from 'node:os';import {join,posix} from 'node:path';import {randomBytes} from 'node:crypto';
import ssh2 from 'ssh2';const {Server,utils}=ssh2;import {connect,fingerprint,session,command} from '../src/ssh-transport.js';import {FileService,relativePath} from '../src/files.js';import {Backups} from '../src/backups.js';import {Router} from '../src/router.js';
const site={id:'test',name:'Test',siteUrl:'https://test.example',endpoint:'https://test.example/mcp',environment:'staging',username:'wp-user',password:'fixture-only',files:{}};
const auth={host:'fixture.example',port:22,username:'fixture',password:'fixture-only',hostKeys:['SHA256:'+Buffer.alloc(32).toString('base64').replace(/=/g,'')],root:'/htdocs',stagingRoot:'/private-upload'};site.files={ssh:auth,sftp:auth};
async function fixture(t){
 const dir=await mkdtemp(join(tmpdir(),'router-files-'));t.after(()=>rm(dir,{recursive:true,force:true}));await mkdir(join(dir,'htdocs','wp-content'),{recursive:true});await mkdir(join(dir,'private-upload'));await writeFile(join(dir,'htdocs','wp-content','demo.txt'),'original');
 const disk=p=>{assert.ok(p==='/htdocs'||p.startsWith('/htdocs/')||p==='/private-upload'||p.startsWith('/private-upload/'));return join(dir,...p.slice(1).split('/'));};
 const wrap=fn=>(...args)=>{const cb=args.pop();Promise.resolve().then(()=>fn(...args)).then(x=>cb(null,x),e=>cb(Object.assign(e,{code:e.code==='ENOENT'?2:e.code})));};
 const s={realpath:wrap(async p=>{await realpath(disk(p));return p;}),lstat:wrap(p=>lstat(disk(p))),open:wrap((p,flags,mode)=>{if(flags==='wx'){assert.ok(p.startsWith('/private-upload/'));assert.equal(mode,0o600);}return open(disk(p),flags,mode);}),chmod:wrap((p,mode)=>chmod(disk(p),mode)),close:wrap(h=>h.close()),mkdir:wrap((p,a)=>mkdir(disk(p),{mode:a.mode})),unlink:wrap(p=>unlink(disk(p))),ext_openssh_rename:wrap((a,b)=>rename(disk(a),disk(b)))};
 s.opendir=(p,cb)=>cb(null,{close:async()=>{},path:p,done:false});s.readdir=(h,cb)=>{if(h.done)return cb(Object.assign(Error('EOF'),{code:1}));h.done=true;cb(null,[{filename:'demo.txt',attrs:{size:8,isSymbolicLink:()=>false,isDirectory:()=>false}}]);};
 s.read=(h,b,o,l,p,cb)=>h.read(b,o,l,p).then(r=>r.bytesRead?cb(null,r.bytesRead,b,p):cb(Object.assign(Error('EOF'),{code:1})),cb);s.write=(h,b,o,l,p,cb)=>h.write(b,o,l,p).then(()=>cb(null),cb);
 const registry={schemaVersion:1,connections:[structuredClone(site)],backupKey:randomBytes(32).toString('base64')};const backups=new Backups(registry.backupKey,join(dir,'backups'));const files=new FileService(registry,{backups,withSession:async(c,work)=>work({sftp:cb=>cb(null,s)})});const router=new Router(registry,{files,call:async()=>({abilities:[]})});return {dir,router,files,backups,disk,s};
}
test('file preview, actual upload/replace/readback, encrypted recovery and one-use confirmation',async t=>{
 const f=await fixture(t);const p=await f.router.prepare('test','sftp/write-file',{path:'wp-content/demo.txt',content:'changed'});assert.equal(await readFile(f.disk('/htdocs/wp-content/demo.txt'),'utf8'),'original');await assert.rejects(f.router.execute(p.preview_id,'test',false));
 const result=(await f.router.execute(p.preview_id,'test',true)).result;assert.equal(await readFile(f.disk('/htdocs/wp-content/demo.txt'),'utf8'),'changed');assert.ok(result.backup_id);await assert.rejects(f.router.execute(p.preview_id,'test',true));
 const ciphertext=await readFile(join(f.dir,'backups',result.backup_id+'.backup'));assert.equal(ciphertext.includes(Buffer.from('original')),false);
 const restore=await f.router.prepare('test','sftp/restore-backup',{backup_id:result.backup_id});await f.router.execute(restore.preview_id,'test',true);assert.equal(await readFile(f.disk('/htdocs/wp-content/demo.txt'),'utf8'),'original');
 await assert.rejects(f.backups.get(result.backup_id,'other-site'));
});
test('stale file preview, cross-site backup, protected paths, base64 and size limits',async t=>{
 const f=await fixture(t);const p=await f.router.prepare('test','sftp/delete-file',{path:'wp-content/demo.txt'});await writeFile(f.disk('/htdocs/wp-content/demo.txt'),'concurrent');await assert.rejects(f.router.execute(p.preview_id,'test',true),/changed since preview/);assert.equal(await readFile(f.disk('/htdocs/wp-content/demo.txt'),'utf8'),'concurrent');
 for(const path of ['../secret','/etc/passwd','wp-content/../wp-config.php','wp-content/.env','wp-content/a\\b','wp-content/backups/x','wp-config.php','wp-content/secret.pem'])assert.throws(()=>relativePath(path,{write:true}));
 await assert.rejects(f.router.prepare('test','sftp/write-file',{path:'wp-content/x',content:'bad base64!',encoding:'base64'}));await assert.rejects(f.router.prepare('test','sftp/write-file',{path:'wp-content/x',content:'x'.repeat(1048577)}));
 const u=await f.router.prepare('test','sftp/write-file',{path:'wp-content/new.png',content:Buffer.from([0,1,255]).toString('base64'),encoding:'base64'});await f.router.execute(u.preview_id,'test',true);assert.deepEqual(await readFile(f.disk('/htdocs/wp-content/new.png')),Buffer.from([0,1,255]));
 const d=await f.router.prepare('test','sftp/delete-file',{path:'wp-content/new.png'});assert.ok((await f.router.execute(d.preview_id,'test',true)).result.backup_id);await assert.rejects(readFile(f.disk('/htdocs/wp-content/new.png')));
});
test('symlink components fail closed and backup corruption blocks restoration',async t=>{
 const f=await fixture(t);const original=f.s.lstat;f.s.lstat=(p,cb)=>p.endsWith('/wp-content')?cb(null,{isSymbolicLink:()=>true,isDirectory:()=>true}):original(p,cb);await assert.rejects(f.router.read('test','sftp/read-file',{path:'wp-content/demo.txt'}),/Symlinks/);f.s.lstat=original;
 const id=await f.backups.save({site:'test',path:'wp-content/demo.txt',content:'YQ=='});await writeFile(join(f.dir,'backups',id+'.backup'),'corrupted');await assert.rejects(f.router.prepare('test','sftp/restore-backup',{backup_id:id}),/authentication/);
});
test('write failure consumes preview and retains encrypted backup',async t=>{
 const f=await fixture(t);f.s.ext_openssh_rename=(a,b,cb)=>cb(Error('fixture disconnect'));const p=await f.router.prepare('test','sftp/write-file',{path:'wp-content/demo.txt',content:'new'});await assert.rejects(f.router.execute(p.preview_id,'test',true),/uncertain/);await assert.rejects(f.router.execute(p.preview_id,'test',true),/consumed/);assert.equal((await f.backups.list('test')).length,1);assert.equal(await readFile(f.disk('/htdocs/wp-content/demo.txt'),'utf8'),'original');
});
test('SSH network transport pins server key before authentication and runs bounded command',async t=>{
 const pair=utils.generateKeyPairSync('ed25519');let authenticated=0;const clients=new Set();const server=new Server({hostKeys:[pair.private]},c=>{clients.add(c);c.on('error',()=>{});c.on('close',()=>clients.delete(c));c.on('authentication',ctx=>{if(ctx.method==='password'&&ctx.password==='fixture-only'){authenticated++;ctx.accept();}else ctx.reject();});c.on('ready',()=>c.on('session',accept=>accept().on('exec',(accept,reject,info)=>{const stream=accept();stream.write('fixture command executed');stream.exit(0);stream.end();})));});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));t.after(()=>{for(const c of clients)c.end();server.close();});const config={...auth,host:'127.0.0.1',port:server.address().port,hostKeys:[fingerprint(utils.parseKey(pair.public).getPublicSSH())]};
 await assert.rejects(connect({...config,hostKeys:auth.hostKeys},{allowLoopback:true}));assert.equal(authenticated,0);const r=await session(config,c=>command(c,'php -n -v'),{allowLoopback:true});assert.equal(r.exit_code,0);assert.equal(authenticated,1);
});

test('SFTP protocol EOF ends bounded listing and file reads',async t=>{const f=await fixture(t);assert.equal((await f.router.read('test','sftp/list-directory',{path:'wp-content'})).result.total,1);assert.equal((await f.router.read('test','sftp/read-file',{path:'wp-content/demo.txt'})).result.content,'original');});
