import {BunnyClient} from '../src/client.js';
const client=new BunnyClient();
for(const [kind,page]of [['pull',0],['dns',1],['storage',0]]){
 const data=await client.core('GET','/'+kind+'zone',{page,perPage:5});const items=Array.isArray(data)?data:data.Items;
 console.log(JSON.stringify({service:kind,returned:items?.length,total:data.TotalItems??null,hasMore:data.HasMoreItems??null}));
 if(kind==='dns'&&items?.[0]){const zone=await client.core('GET','/dnszone/'+items[0].Id);console.log(JSON.stringify({dnsDetailVerified:true,records:zone.Records?.length}));}
 if(kind==='storage'&&items?.[0]){const files=await client.storage(items[0].Id,'GET','',{directory:true});console.log(JSON.stringify({storageFileAccess:true,entries:files.length}));}
}
