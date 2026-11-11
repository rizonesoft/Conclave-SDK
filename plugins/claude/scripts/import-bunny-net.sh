#!/usr/bin/env bash
# One-time import or refresh of the bunny.net account API key from Conclave into the Claude DPAPI store.
# The key travels only through pipes: never arguments, never stdout.
set -euo pipefail
# Windows form of a path (powershell.exe and Windows Node need it): wslpath when available, else cygpath.
winpath() { if command -v wslpath >/dev/null 2>&1; then wslpath -w "$1"; else cygpath -w "$1"; fi; }
PLUGIN_WIN="$(winpath "$(cd "$(dirname "$0")/../bunny-net" && pwd)")"
ITEM=lltjt3ppfexnc6iklydzhunv4q   # Conclave: "Bunny.net Account API"
conclave-op item get "$ITEM" --vault Conclave --reveal --format=json \
 | jq -c '{mode:"apikey", apiKey:(.fields[]|select(.label=="credential").value)}' \
 | powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$PLUGIN_WIN/scripts/configure.ps1" -CredentialFromStdin -Reference "op://Conclave/$ITEM" 2>&1 | tr -d '\r' | grep -v -E 'CLIXML|<Objs'
