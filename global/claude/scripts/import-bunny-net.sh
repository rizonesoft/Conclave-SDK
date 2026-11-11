#!/usr/bin/env bash
# One-time import or refresh of the bunny.net account API key from Conclave into the Claude DPAPI store.
# The key travels only through pipes: never arguments, never stdout.
set -euo pipefail
ITEM=lltjt3ppfexnc6iklydzhunv4q   # Conclave: "Bunny.net Account API"
conclave-op item get "$ITEM" --vault Conclave --reveal --format=json \
 | jq -c '{mode:"apikey", apiKey:(.fields[]|select(.label=="credential").value)}' \
 | powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File 'R:\Claude\connections\bunny-net\scripts\configure.ps1' -CredentialFromStdin -Reference "op://Conclave/$ITEM" 2>&1 | tr -d '\r' | grep -v -E 'CLIXML|<Objs'
