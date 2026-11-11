#!/usr/bin/env python3
"""Install this plugin's cloud bundle and a host-encrypted cache key, without starting a service."""
import os
from pathlib import Path
import shutil
import subprocess

def main():
    if os.geteuid() != 0:
        raise SystemExit('Run as root on the intended Ubuntu host.')
    source = Path(__file__).resolve().parents[1]
    base = Path('/opt/rizonetech-mcp/outlook-graph')
    credential = Path('/etc/rizonetech-mcp/outlook-graph.cache-key.cred')
    for name in ('server.mjs', 'setup.mjs'):
        if not (source / 'dist' / name).is_file():
            raise SystemExit('Build and stage the complete plugin first.')
    for path in ('/opt/rizonetech-mcp/node/bin/node', '/opt/rizonetech-mcp/bin/tunnel-client'):
        if not Path(path).is_file():
            raise SystemExit('The existing Rizonetech Ubuntu runtime is required.')
    base.mkdir(parents=True, exist_ok=True)
    (base / 'dist').mkdir(exist_ok=True)
    for name in ('server.mjs', 'setup.mjs'):
        shutil.copy2(source / 'dist' / name, base / 'dist' / name)
    for name in ('run-tunnel.sh', 'session.sh'):
        shutil.copy2(source / 'linux' / name, base / name)
        (base / name).chmod(0o755)
    credential.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not credential.exists():
        pending = credential.with_suffix('.pending')
        if pending.exists():
            raise SystemExit('Previous pending key requires inspection; no overwrite.')
        result = subprocess.run(['systemd-creds', 'encrypt', '--with-key=host', '--name=cache-key', '-', str(pending)], input=os.urandom(32), capture_output=True)
        if result.returncode:
            raise SystemExit('Host credential encryption failed.')
        pending.chmod(0o600)
        pending.replace(credential)
    shutil.copy2(source / 'linux' / 'outlook-graph.service', '/etc/systemd/system/rizonetech-outlook-graph.service')
    subprocess.run(['systemctl', 'daemon-reload'], check=True)
    print('Bundle and encrypted cache key installed. No service started. Run session.sh login interactively, then check before tunnel activation.')

if __name__ == '__main__':
    main()
