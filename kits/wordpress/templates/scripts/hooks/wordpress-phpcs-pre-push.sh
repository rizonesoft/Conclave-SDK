#!/usr/bin/env bash
# Run from the project's pre-push hook as its own command
# (`bash scripts/hooks/wordpress-phpcs-pre-push.sh || exit 1`), never sourced: it
# exits. A missing phpcs binary is SKIPPED, not a pass.
set -euo pipefail
root=$(git rev-parse --show-toplevel)
phpcs="$root/tools/phpcs/vendor/bin/phpcs"
if [ ! -x "$phpcs" ]; then
	printf 'wordpress-phpcs-pre-push: SKIPPED (tools/phpcs not installed)\n' >&2
	exit 0
fi
exec "$phpcs"
