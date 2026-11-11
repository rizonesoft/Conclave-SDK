import {randomBytes} from 'node:crypto';import {session,invoke,command,quote} from '../src/ssh-transport.js';import {validateRegistry} from '../src/security.js';
try{
 let raw='';for await(const chunk of process.stdin){raw+=chunk;if(raw.length>2097152)throw Error();}
 const {registry,requests}=JSON.parse(raw);if(!Array.isArray(requests)||requests.length>100)throw Error();
 for(const r of requests){const site=registry.connections.find(s=>s.id===r.siteId);if(!site)throw Error();const auth={port:r.port,username:r.username,password:r.password,privateKey:r.privateKey,hostKeys:[r.hostKey]};
 const root=await session({...auth,host:r.sftpHost},async c=>{const s=await invoke(c,'sftp');const root=await invoke(s,'realpath',r.sftpRoot);const st=await invoke(s,'stat',root+'/wp-content');if(!st.isDirectory())throw Error();return root;});
 const ssh=await session({...auth,host:r.sshHost},c=>command(c,'cd -- '+quote(r.sshRoot)+' && pwd -P'));
 if(ssh.exit_code!==0||ssh.stdout.trim()!==r.sshRoot)throw Error();
 site.files={vaultItemId:r.vaultItemId,sftp:{...auth,host:r.sftpHost,root,stagingRoot:'/tmp'},ssh:{...auth,host:r.sshHost,root:r.sshRoot}};
 }
 registry.backupKey??=randomBytes(32).toString('base64');validateRegistry(registry);process.stdout.write(JSON.stringify(registry));
}catch{process.stderr.write('SSH/SFTP setup validation failed. No credentials printed.\n');process.exitCode=1;}
