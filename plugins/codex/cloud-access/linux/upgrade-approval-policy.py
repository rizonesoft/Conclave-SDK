#!/usr/bin/env python3
"""Code-only upgrade. Verify all candidates before touching running plugin bundles."""
import json,os,pathlib,shutil,subprocess
if os.geteuid()!=0:raise SystemExit('Root required')
stage=pathlib.Path(__file__).resolve().parent
base=pathlib.Path('/opt/rizonetech-mcp')
names=['atera','bunny-net','domains-co-za','pressable','website-router']
reports=[]
for name in names:
 dest=base/name;candidate=dest/'approval-candidate';candidate.mkdir(mode=0o755,exist_ok=True)
 for source,target in [(stage/(name+'.mjs'),candidate/'server.mjs'),(stage/'check-approval-policy.mjs',candidate/'check.mjs')]:
  shutil.copyfile(source,target);target.chmod(0o644)
 command=['systemd-run','--quiet','--wait','--pipe','--collect','-p','DynamicUser=yes','-p','LoadCredentialEncrypted=provider:/etc/rizonetech-mcp/'+name+'.provider.cred',str(base/'node/bin/node'),str(candidate/'check.mjs'),str(candidate/'server.mjs'),'--live']
 p=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=190)
 if p.returncode:raise SystemExit('Candidate verification failed for '+name+'; current code unchanged')
 try:report=json.loads(p.stdout)
 except Exception:raise SystemExit('Unexpected sanitized probe output for '+name)
 reports.append(report)
for name in names:
 target=base/name/'server.mjs';backup=base/name/'server.mjs.pre-approval-policy'
 shutil.copyfile(target,backup)
 pending=base/name/'server.mjs.pending';shutil.copyfile(stage/(name+'.mjs'),pending);pending.chmod(0o644);pending.replace(target)
 p=subprocess.run(['systemctl','restart','rizonetech-mcp@'+name],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 healthy=subprocess.run(['systemctl','is-active','--quiet','rizonetech-mcp@'+name])
 if p.returncode or healthy.returncode:
  shutil.copyfile(backup,target);subprocess.run(['systemctl','restart','rizonetech-mcp@'+name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  raise SystemExit('Activation failed for '+name+'; previous bundle restored. Earlier services may already be updated.')
print(json.dumps({'updated':names,'candidateChecks':reports,'providerWritesPerformed':0}))
