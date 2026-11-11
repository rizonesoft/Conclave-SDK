#!/usr/bin/env python3
import sys,json,pathlib,subprocess,shutil,os
if os.geteuid()!=0:raise SystemExit('Root required')
base=pathlib.Path('/opt/rizonetech-mcp');stage=pathlib.Path(__file__).resolve().parent
secret=json.load(sys.stdin)['bunny'];assert isinstance(secret,str) and secret.strip() and len(secret)<65536 and '\n' not in secret
credential=pathlib.Path('/etc/rizonetech-mcp/bunny-net.provider.cred')
if credential.exists():raise SystemExit('Bunny credential exists; use explicit rotation')
plugin=base/'bunny-net';plugin.mkdir(mode=0o755,exist_ok=True)
shutil.copyfile(stage/'bunny-net.mjs',plugin/'server.mjs');(plugin/'server.mjs').chmod(0o644)
r=subprocess.run(['systemd-creds','encrypt','--with-key=host','--name=provider','-',str(credential)],input=secret.encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
if r.returncode:raise SystemExit('Credential encryption failed')
credential.chmod(0o600)
subprocess.run(['systemd-run','--quiet','--wait','--pipe','--collect','-p','DynamicUser=yes','-p','LoadCredentialEncrypted=provider:'+str(credential),str(base/'node/bin/node'),str(base/'probe.mjs'),str(plugin/'server.mjs'),'18'],check=True)
print('Bunny bundle installed and encrypted-credential provider probe passed. Tunnel activation pending.')
