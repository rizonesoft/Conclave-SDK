#!/usr/bin/env python3
import os,sys,json,getpass,pathlib,subprocess,tempfile
if os.geteuid()!=0 or len(sys.argv)!=2 or sys.argv[1] not in ('atera','domains-co-za','bunny-net','tunnel-key'):
 raise SystemExit('Usage: sudo python3 update-credential.py atera|domains-co-za|bunny-net|tunnel-key')
if not sys.stdin.isatty(): raise SystemExit('Use an interactive SSH terminal for hidden credential entry')
name=sys.argv[1]
value=getpass.getpass('Replacement credential (hidden): ')
if not value or len(value)>65536 or '\n' in value or '\r' in value: raise SystemExit('Invalid credential')
if name=='domains-co-za':
 try:
  c=json.loads(value)
  assert (c.get('mode')=='login' and isinstance(c.get('username'),str) and c['username'].strip() and isinstance(c.get('password'),str) and c['password']) or (c.get('mode')=='bearer' and isinstance(c.get('token'),str) and c['token'].strip())
 except Exception: raise SystemExit('Invalid Domains credential JSON')
folder=pathlib.Path('/etc/rizonetech-mcp')
target=folder/(name+'.cred' if name=='tunnel-key' else name+'.provider.cred')
fd,tmp=tempfile.mkstemp(prefix='.update-',dir=folder);os.close(fd)
try:
 r=subprocess.run(['systemd-creds','encrypt','--with-key=host','--name='+('tunnel-key' if name=='tunnel-key' else 'provider'),'-','-'],input=value.encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 if r.returncode: raise SystemExit('Encryption failed; previous credential retained')
 with open(tmp,'wb') as f: f.write(r.stdout)
 os.chmod(tmp,0o600);os.replace(tmp,target)
finally:
 if os.path.exists(tmp): os.unlink(tmp)
services=['atera','domains-co-za','bunny-net'] if name=='tunnel-key' else [name]
subprocess.run(['systemctl','restart']+['rizonetech-mcp@'+s for s in services],check=True)
print('Encrypted credential replaced. Run the harmless connection check.')