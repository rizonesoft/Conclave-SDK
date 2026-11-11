import { BunnyClient } from '../src/client.js';
try {await new BunnyClient().request('GET','/pullzone',{query:{page:1,perPage:5}});console.log(JSON.stringify({connected:true,credentialStore:'Windows DPAPI',onePasswordRuntimeAccess:false}));}
catch(e){console.error(e.message);process.exitCode=1;}
