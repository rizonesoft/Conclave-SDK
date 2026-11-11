import { DomainsClient } from '../src/client.js';
try {await new DomainsClient().request('GET','/domain/funds');console.log(JSON.stringify({connected:true,credentialStore:'Windows DPAPI',onePasswordRuntimeAccess:false}));}
catch(e){console.error(e.message);process.exitCode=1;}
