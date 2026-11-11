#!/usr/bin/env python3
"""Rotate only Pressable's host-encrypted runtime token from a hidden prompt."""
import pathlib,os,getpass,tempfile,subprocess
if os.geteuid()!=0 or not os.isatty(0):raise SystemExit('Run with sudo in an interactive SSH session')
value=getpass.getpass('Replacement Pressable MCP token (hidden): ').strip()
if not value or len(value)>65536 or '\r' in value or '\n' in value:raise SystemExit('Invalid token; credential unchanged')
target=pathlib.Path('/etc/rizonetech-mcp/pressable.provider.cred')
r=subprocess.run(['systemd-creds','encrypt','--with-key=host','--name=provider','-','-'],input=value.encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
if r.returncode:raise SystemExit('Encryption failed; credential unchanged')
fd,tmp=tempfile.mkstemp(prefix='.pressable-',dir=target.parent)
try:
 with os.fdopen(fd,'wb') as f:f.write(r.stdout)
 os.chmod(tmp,0o600);os.replace(tmp,target)
finally:
 if os.path.exists(tmp):os.unlink(tmp)
subprocess.run(['systemctl','restart','rizonetech-mcp@pressable'],check=True)
print('Pressable credential replaced. Run the read-only probe; update Conclave recovery separately.')