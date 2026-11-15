#!/usr/bin/env bash
# Source from the project's pre-push hook. Exit 3 (missing servers) is a skip,
# not a pass: the caller must print SKIPPED. Laravel and Tailwind only;
# Intelephense stays on demand.
set -euo pipefail
root=$(git rev-parse --show-toplevel)
client="$root/scripts/lsp-diagnostics.py"
if [ ! -f "$client" ]; then
	printf 'laravel-lsp-pre-push: missing %s\n' "$client" >&2
	exit 0
fi
set +e
python3 "$client" --server laravel --server tailwind --staged
status=$?
set -e
if [ "$status" = 3 ]; then
	printf 'laravel-lsp-pre-push: SKIPPED (language servers not installed)\n' >&2
	exit 0
fi
exit "$status"
