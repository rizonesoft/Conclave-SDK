import ssh2 from 'ssh2';const {Client}=ssh2;
import {lookup} from 'node:dns/promises';
import {createHash} from 'node:crypto';
import {publicAddress} from './security.js';
export const fingerprint=key=>'SHA256:'+createHash('sha256').update(key).digest('base64').replace(/=+$/,'');
export const invoke=(object,method,...args)=>new Promise((resolve,reject)=>object[method](...args,(e,...values)=>e?reject(e):resolve(values.length>1?values:values[0])));
export async function connect(config,{allowLoopback=false}={}){
 const rows=await lookup(config.host,{all:true});
 if(!rows.length||rows.some(r=>!publicAddress(r.address)&&!(allowLoopback&&r.address==='127.0.0.1')))throw Error('SSH destination must resolve to a public address.');
 const client=new Client();
 await new Promise((resolve,reject)=>{
  client.once('ready',resolve);client.on('error',()=>{client.destroy();reject(Error('SSH authentication, host-key verification or connection failed.'));});
  client.once('close',()=>reject(Error('SSH connection closed.')));
  client.connect({host:rows[0].address,port:config.port??22,username:config.username,password:config.password,privateKey:config.privateKey,passphrase:config.passphrase,hostVerifier:key=>config.hostKeys.includes(fingerprint(key)),algorithms:{serverHostKey:['ssh-ed25519']},readyTimeout:15000,keepaliveInterval:5000,keepaliveCountMax:2,agentForward:false});
 });
 return client;
}
export async function session(config,work,options){
 let client;let timer;
 try{return await Promise.race([(async()=>{client=await connect(config,options);return await work(client);})(),new Promise((_,reject)=>{timer=setTimeout(()=>{client?.destroy();reject(Error('SSH/SFTP operation timed out; inspect remote state before another change.'));},45000);})]);}
 finally{clearTimeout(timer);client?.end();}
}
export function command(client,text){return new Promise((resolve,reject)=>{
 client.exec(text,{pty:false},(error,stream)=>{
  if(error)return reject(Error('SSH command could not start.'));
  let stdout='',stderr='',size=0;
  const append=kind=>chunk=>{size+=chunk.length;if(size>262144){stream.close();reject(Error('SSH output exceeded 256 KiB.'));return;}if(kind==='out')stdout+=chunk.toString();else stderr+=chunk.toString();};
  stream.on('data',append('out'));stream.stderr.on('data',append('err'));stream.on('error',()=>reject(Error('SSH command interrupted.')));
  stream.on('close',code=>resolve({exit_code:code??null,stdout,stderr}));stream.end();
 });
});}
export const quote=s=>"'"+s.replace(/'/g,"'\\''")+"'";
