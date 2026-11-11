#!/bin/sh
set -eu
case "${1:-status}" in login|check|status) action=${1:-status};; *) exit 64;; esac
# An interactive PTY keeps device sign-in codes in the operator terminal, not the journal.
exec systemd-run --quiet --wait --pty --collect \
 -p DynamicUser=yes -p User=rizonetech-outlook-graph \
 -p StateDirectory=rizonetech-outlook-graph -p StateDirectoryMode=0700 \
 -p UMask=0077 \
 -p LoadCredentialEncrypted=cache-key:/etc/rizonetech-mcp/outlook-graph.cache-key.cred \
 /opt/rizonetech-mcp/node/bin/node /opt/rizonetech-mcp/outlook-graph/dist/setup.mjs "$action"
