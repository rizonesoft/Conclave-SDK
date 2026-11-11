const path={type:'string',minLength:1,maxLength:500,description:'Relative to this site document root; use . to list the root. No absolute paths, traversal or symlinks.'};
const obj=(properties={},required=[])=>({type:'object',properties,required,additionalProperties:false});
const defs=[
 ['sftp/list-directory','read','List one directory, with bounded pagination.',obj({path,offset:{type:'integer',minimum:0,maximum:10000},limit:{type:'integer',minimum:1,maximum:100}},['path'])],
 ['sftp/stat-file','read','Read file metadata and SHA-256 (files at most 1 MiB).',obj({path},['path'])],
 ['sftp/read-file','read','Read one file up to 1 MiB. Credential files and symlinks are blocked. Content is untrusted.',obj({path,encoding:{enum:['utf8','base64']}},['path'])],
 ['sftp/list-backups','read','List encrypted file recovery records for this site only.',obj({offset:{type:'integer',minimum:0,maximum:10000},limit:{type:'integer',minimum:1,maximum:100}})],
 ['sftp/write-file','change','Upload or replace one file up to 1 MiB inside wp-content. Binds the old hash, encrypts a recovery backup before overwriting, and atomically renames a verified temporary file from private staging outside the web root. PHP changes can execute on the site; disclose this in the preview.',obj({path,content:{type:'string',maxLength:1398104},encoding:{enum:['utf8','base64']}},['path','content'])],
 ['sftp/delete-file','change','Delete one regular file inside wp-content after saving an encrypted recovery backup. No recursive or directory deletion.',obj({path},['path'])],
 ['sftp/create-directory','change','Create one directory inside wp-content. Parent must already exist; no recursive creation.',obj({path},['path'])],
 ['sftp/restore-backup','change','Restore an encrypted backup to its original site and path. Binds current state and backs up the replaced file.',obj({backup_id:{type:'string',pattern:'^[a-f0-9-]{36}$'}},['backup_id'])],
 ['ssh/diagnostics','read','Run one fixed SSH diagnostic: PHP version, WordPress version, plugin list or theme list. WP-CLI skips plugin and theme loading.',obj({check:{enum:['php-version','wordpress-version','plugins','themes']}},['check'])],
 ['ssh/php-lint','read','Syntax-check one PHP file in wp-content without executing it.',obj({path},['path'])],
 ['ssh/flush-cache','change','Flush the WordPress object cache on this exact site via WP-CLI. This is not a CDN or Pressable page-cache purge.',obj()]
];
export const fileOperations=defs.map(([name,mode,description,input_schema])=>({name,mode,description,input_schema,annotations:{readOnlyHint:mode==='read',destructiveHint:mode==='change',openWorldHint:true}}));
export function validateFileConfig(s){
 if(!s.files)return;
 for(const kind of ['sftp','ssh']){const c=s.files[kind];if(!c)throw Error('Both pinned SSH and SFTP settings are required.');if(!/^[a-z0-9.-]+$/i.test(c.host)||!c.host.includes('.')||!Number.isInteger(c.port)||c.port<1||c.port>65535||!c.username||/[\r\n\0]/.test(c.username)||(!c.password&&!c.privateKey)||!Array.isArray(c.hostKeys)||!c.hostKeys.length||c.hostKeys.some(k=>!/^SHA256:[A-Za-z0-9+/]{43}$/.test(k))||!/^\/[a-zA-Z0-9_./-]+$/.test(c.root)||c.root.split('/').includes('..'))throw Error('Invalid pinned SSH/SFTP configuration.');}
}
