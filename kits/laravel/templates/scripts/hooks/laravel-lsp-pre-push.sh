#!/usr/bin/env bash
# Source from the project's pre-push hook. Exit 3 (no server could check anything) is a skip,
# not a pass: the caller must print SKIPPED. Laravel and Tailwind only; Intelephense stays on
# demand. The servers are the ones the project's table (.conclave/lsp.json) names.
set -euo pipefail
root=$(git rev-parse --show-toplevel)
client="$root/scripts/lsp-diagnostics.py"
if [ ! -f "$client" ]; then
	printf 'laravel-lsp-pre-push: missing %s\n' "$client" >&2
	exit 0
fi
# The LSP kit's client takes the table's names. A project still on its own client from before
# that kit (one that does not use lsp_client) is asked by the names that client knows, so the
# two work together until the project has moved to the kit's client.
if grep -q 'lsp_client' "$client"; then
	servers=(--server laravel-lsp --server tailwindcss)
else
	servers=(--server laravel --server tailwind)
fi
set +e
python3 "$client" "${servers[@]}" --staged
status=$?
set -e
if [ "$status" = 3 ]; then
	printf 'laravel-lsp-pre-push: SKIPPED (language servers not installed)\n' >&2
	exit 0
fi
exit "$status"
