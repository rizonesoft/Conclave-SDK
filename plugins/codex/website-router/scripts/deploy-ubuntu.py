#!/usr/bin/env python3
"""Install/update only Website Router; encrypted registry arrives through stdin."""
import sys,json,pathlib,subprocess,os,shutil,tempfile
if os.geteuid()!=0:raise SystemExit('Root required')
base=pathlib.Path('/opt/rizonetech-mcp');stage=pathlib.Path(__file__).resolve().parent
try:
 secret=json.load(sys.stdin)['provider']
 if not isinstance(secret,str) or len(secret)>1048576:raise ValueError()
 data=json.loads(secret)
 if data.get('schemaVersion')!=1 or not isinstance(data.get('connections'),list) or len(data['connections'])>100:raise ValueError()
except Exception:raise SystemExit('Invalid registry; existing encrypted store unchanged')
plugin=base/'website-router';plugin.mkdir(mode=0o755,exist_ok=True)
for name in ['server.mjs','probe.mjs']:
 if (stage/name).exists():
  shutil.copyfile(stage/name,plugin/(name+'.pending'));(plugin/(name+'.pending')).chmod(0o644)
  (plugin/(name+'.pending')).replace(plugin/name)
r=subprocess.run(['systemd-creds','encrypt','--with-key=host','--name=provider','-','-'],input=secret.encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
if r.returncode:raise SystemExit('Encryption failed; existing store unchanged')
target=pathlib.Path('/etc/rizonetech-mcp/website-router.provider.cred')
fd,tmp=tempfile.mkstemp(prefix='.website-router-',dir=target.parent)
try:
 with os.fdopen(fd,'wb') as f:f.write(r.stdout)
 os.chmod(tmp,0o600)
 # Registry validation probe before replacing the live credential. No provider writes.
 probe=subprocess.run(['systemd-run','--quiet','--wait','--pipe','--collect','-p','DynamicUser=yes','-p','LoadCredentialEncrypted=provider:'+tmp,str(base/'node/bin/node'),str(plugin/'probe.mjs'),str(plugin/'server.mjs'),'--registry-only'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 if probe.returncode:raise SystemExit('Registry validation failed; existing credential unchanged')
 os.replace(tmp,target)
finally:
 if os.path.exists(tmp):os.unlink(tmp)
drop=pathlib.Path('/etc/systemd/system/rizonetech-mcp@website-router.service.d');drop.mkdir(exist_ok=True)
(drop/'storage.conf').write_text('[Service]\nStateDirectory=rizonetech-website-router\nStateDirectoryMode=0700\n')
subprocess.run(['systemctl','daemon-reload'],check=True)
active=subprocess.run(['systemctl','is-enabled','--quiet','rizonetech-mcp@website-router'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
if active.returncode==0:subprocess.run(['systemctl','restart','rizonetech-mcp@website-router'],check=True)
print('Website Router registry securely installed. Connections: '+str(len(data['connections'])))
