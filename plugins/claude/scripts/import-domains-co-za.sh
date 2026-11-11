#!/usr/bin/env bash
# One-time import or refresh of the Domains.co.za credential from Conclave into the Claude DPAPI store.
# Secrets travel only through pipes: never arguments, never stdout.
set -euo pipefail
ITEM=eahm2wl4mc23kbdw7e62tcbifq   # Conclave: "Domains.co.za Reseller API"
TOTP_FIELD=bnib4ypcgrkcql5ft543vlrlwa
# Windows form of a path (powershell.exe and Windows Node need it): wslpath when available, else cygpath.
winpath() { if command -v wslpath >/dev/null 2>&1; then wslpath -w "$1"; else cygpath -w "$1"; fi; }
PLUGIN="$(cd "$(dirname "$0")/../domains-co-za" && pwd)"
PLUGIN_WIN="$(winpath "$PLUGIN")"
conclave-op read "op://Conclave/$ITEM/$TOTP_FIELD" | node "$PLUGIN/scripts/validate-totp.mjs"
PS='$ErrorActionPreference="Stop"; $ProgressPreference="SilentlyContinue"; . "'"$PLUGIN_WIN"'/scripts/credential-store.ps1"; $s=ConvertTo-SecureString ([Console]::In.ReadToEnd().Trim()) -AsPlainText -Force; try { Save-DomainsCoZaCredential -Token $s -TokenReference "op://Conclave/'"$ITEM"'" } finally { $s.Dispose() }; Get-DomainsCoZaCredentialStatus | ConvertTo-Json -Compress'
conclave-op item get "$ITEM" --vault Conclave --reveal --format=json \
 | jq -c '{mode:"login", username:(.fields[]|select(.id=="username").value), password:(.fields[]|select(.id=="password").value), totpSecret:(.fields[]|select(.label=="Authenticator secret").value)}' \
 | powershell.exe -NoLogo -NoProfile -NonInteractive -EncodedCommand "$(printf '%s' "$PS" | iconv -t UTF-16LE | base64 -w0)" 2>/dev/null | tr -d '\r'
