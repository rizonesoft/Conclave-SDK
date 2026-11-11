#!/usr/bin/env python3
import sys,pathlib,re,subprocess,os
if os.geteuid()!=0:raise SystemExit('Root required')
tunnel=sys.argv[1]
if not re.fullmatch(r'tunnel_[a-zA-Z0-9]+',tunnel):raise SystemExit('Invalid tunnel ID')
base=pathlib.Path('/opt/rizonetech-mcp/website-router')
runner=base/'run-tunnel.sh'
runner.write_text('#!/bin/sh\nset -eu\nexec /opt/rizonetech-mcp/bin/tunnel-client run \\\n --control-plane.tunnel-id '+tunnel+' \\\n --control-plane.api-key "file:${CREDENTIALS_DIRECTORY}/tunnel-key" \\\n --control-plane.max-inflight 1 \\\n --mcp.command "command=/opt/rizonetech-mcp/node/bin/node /opt/rizonetech-mcp/website-router/server.mjs,channel=main" \\\n --health.listen-addr "127.0.0.1:18785" --log.level warn --log.format json\n')
runner.chmod(0o755)
drop=pathlib.Path('/etc/systemd/system/rizonetech-mcp@website-router.service.d');drop.mkdir(exist_ok=True)
(drop/'override.conf').write_text('[Service]\nExecStart=\nExecStart=/opt/rizonetech-mcp/website-router/run-tunnel.sh\nStateDirectory=rizonetech-website-router\nStateDirectoryMode=0700\n')
subprocess.run(['systemctl','daemon-reload'],check=True)
subprocess.run(['systemctl','enable','--now','rizonetech-mcp@website-router'],check=True)
subprocess.run(['systemctl','is-active','rizonetech-mcp@website-router'],check=True)