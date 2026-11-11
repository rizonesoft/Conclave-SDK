import pathlib,shutil,os,subprocess
assert os.geteuid()==0
base=pathlib.Path('/opt/rizonetech-mcp');stage=pathlib.Path('/home/venom/rizonetech-mcp-migration')
for name,mode in [('run-tunnel.sh',0o755),('update-credential.py',0o755),('health.py',0o644)]:
 shutil.copyfile(stage/name,base/name);(base/name).chmod(mode)
subprocess.run(['systemctl','enable','--now','rizonetech-mcp@bunny-net'],check=True)
subprocess.run(['systemctl','is-active','rizonetech-mcp@bunny-net'],check=True)
