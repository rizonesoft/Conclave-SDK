#!/usr/bin/env python3
"""Upgrade code only; preserve Pressable's encrypted credentials and tunnel."""
import os,pathlib,shutil,subprocess
if os.geteuid()!=0:raise SystemExit('Root required')
stage=pathlib.Path(__file__).resolve().parent
base=pathlib.Path('/opt/rizonetech-mcp');dest=base/'pressable'
candidate=dest/'candidate';candidate.mkdir(mode=0o755,exist_ok=True)
for name in ['server.mjs','probe.mjs']:
 shutil.copyfile(stage/name,candidate/name);(candidate/name).chmod(0o644)
probe=subprocess.run(['systemd-run','--quiet','--wait','--pipe','--collect','-p','DynamicUser=yes','-p','LoadCredentialEncrypted=provider:/etc/rizonetech-mcp/pressable.provider.cred',str(base/'node/bin/node'),str(candidate/'probe.mjs'),str(candidate/'server.mjs')],capture_output=True)
if probe.returncode:raise SystemExit('Candidate verification failed; current runtime unchanged')
for name in ['server.mjs','probe.mjs']:
 target=dest/name
 if target.exists():shutil.copyfile(target,dest/(name+'.previous'))
 shutil.copyfile(stage/name,dest/(name+'.pending'));(dest/(name+'.pending')).chmod(0o644);(dest/(name+'.pending')).replace(target)
r=subprocess.run(['systemctl','restart','rizonetech-mcp@pressable'])
if r.returncode:raise SystemExit('Restart failed; previous code copies retained for recovery')
subprocess.run(['systemctl','is-active','rizonetech-mcp@pressable'],check=True)
print(probe.stdout.decode().strip())
