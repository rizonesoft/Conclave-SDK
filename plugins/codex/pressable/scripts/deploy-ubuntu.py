#!/usr/bin/env python3
"""Install Pressable only. JSON provider token arrives on stdin; never log it."""
import sys,json,pathlib,subprocess,os,shutil
if os.geteuid()!=0:raise SystemExit('Root required')
base=pathlib.Path('/opt/rizonetech-mcp');stage=pathlib.Path(__file__).resolve().parent
secret=json.load(sys.stdin)['provider']
if not isinstance(secret,str) or not secret.strip() or len(secret)>65536 or '\n' in secret or '\r' in secret:raise SystemExit('Invalid credential')
credential=pathlib.Path('/etc/rizonetech-mcp/pressable.provider.cred')
if credential.exists():raise SystemExit('Credential exists; use explicit rotation')
plugin=base/'pressable';plugin.mkdir(mode=0o755,exist_ok=True)
for source,dest in [('server.mjs','server.mjs'),('probe.mjs','probe.mjs')]:
 shutil.copyfile(stage/source,plugin/dest);(plugin/dest).chmod(0o644)
temporary=credential.with_suffix('.pending')
r=subprocess.run(['systemd-creds','encrypt','--with-key=host','--name=provider','-',str(temporary)],input=secret.encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
if r.returncode:raise SystemExit('Credential encryption failed')
temporary.chmod(0o600);temporary.replace(credential)
subprocess.run(['systemd-run','--quiet','--wait','--pipe','--collect','-p','DynamicUser=yes','-p','LoadCredentialEncrypted=provider:'+str(credential),str(base/'node/bin/node'),str(plugin/'probe.mjs'),str(plugin/'server.mjs')],check=True)
print('Pressable installed; encrypted provider probe passed. Tunnel activation pending.')