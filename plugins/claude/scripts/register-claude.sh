#!/usr/bin/env bash
# Register (or re-register) every Claude connection plugin in plugins/claude/ with Claude Code at user scope.
# Each server runs under Windows Node so it can decrypt its Windows DPAPI credential store.
set -euo pipefail
NODE="/mnt/c/Program Files/nodejs/node.exe"
# Windows form of a path (powershell.exe and Windows Node need it): wslpath when available, else cygpath.
winpath() { if command -v wslpath >/dev/null 2>&1; then wslpath -w "$1"; else cygpath -w "$1"; fi; }
ROOT="$(winpath "$(cd "$(dirname "$0")/.." && pwd)")"
for name in domains-co-za bunny-net; do
  claude mcp remove "$name" -s user >/dev/null 2>&1 || true
  claude mcp add --scope user "$name" -- "$NODE" "$ROOT/$name/dist/server.mjs" >/dev/null
  claude mcp get "$name" | grep -E '^\s+(Status|Args):'
done
