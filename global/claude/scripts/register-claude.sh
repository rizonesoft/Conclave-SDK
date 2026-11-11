#!/usr/bin/env bash
# Register (or re-register) every connection in this repository with Claude Code at user scope.
# Each server runs under Windows Node so it can decrypt its Windows DPAPI credential store.
set -euo pipefail
NODE="/mnt/c/Program Files/nodejs/node.exe"
ROOT='R:\Claude'
for name in domains-co-za bunny-net; do
  claude mcp remove "$name" -s user >/dev/null 2>&1 || true
  claude mcp add --scope user "$name" -- "$NODE" "$ROOT\\connections\\$name\\dist\\server.mjs" >/dev/null
  claude mcp get "$name" | grep -E '^\s+(Status|Args):'
done
