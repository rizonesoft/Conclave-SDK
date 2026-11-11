#!/bin/sh
set -eu
case "$1" in
atera) tunnel=tunnel_6ac348969d708191a2cb339de0c14070; port=18781 ;;
domains-co-za) tunnel=tunnel_6ac349a7309881918622712dca192ebc; port=18782 ;;
bunny-net) tunnel=tunnel_6ac48be40bf0819186a83bbc42dcd6bb; port=18783 ;;
*) exit 64 ;;
esac
exec /opt/rizonetech-mcp/bin/tunnel-client run \
 --control-plane.tunnel-id "$tunnel" \
 --control-plane.api-key "file:${CREDENTIALS_DIRECTORY}/tunnel-key" \
 --control-plane.max-inflight 1 \
 --mcp.command "command=/opt/rizonetech-mcp/node/bin/node /opt/rizonetech-mcp/$1/server.mjs,channel=main" \
 --health.listen-addr "127.0.0.1:$port" --log.level warn --log.format json
