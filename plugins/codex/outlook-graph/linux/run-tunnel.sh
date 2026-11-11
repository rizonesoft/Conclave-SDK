#!/bin/sh
set -eu
case "$OUTLOOK_GRAPH_TUNNEL_ID" in tunnel_*) ;; *) exit 64;; esac
exec /opt/rizonetech-mcp/bin/tunnel-client run \
 --control-plane.tunnel-id "$OUTLOOK_GRAPH_TUNNEL_ID" \
 --control-plane.api-key "file:${CREDENTIALS_DIRECTORY}/tunnel-key" \
 --control-plane.max-inflight 1 \
 --mcp.command "command=/opt/rizonetech-mcp/node/bin/node /opt/rizonetech-mcp/outlook-graph/dist/server.mjs,channel=main" \
 --health.listen-addr "127.0.0.1:18787" --log.level warn --log.format json
