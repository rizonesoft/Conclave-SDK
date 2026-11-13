#!/usr/bin/env bash
# Read-only. Never installs. The checks live in forge.py's doctor so this script and
# `python forge.py doctor <target> wordpress` can never disagree.
set -euo pipefail

strict=0
target=.
for arg in "$@"; do
	if [ "$arg" = "--strict" ]; then
		strict=1
	else
		target=$arg
	fi
done

if [ ! -d "$target" ]; then
	printf 'doctor: not a directory: %s\n' "$target" >&2
	exit 2
fi

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
forge="$script_dir/../../../forge.py"

report=$(python3 "$forge" doctor "$target" wordpress)
printf '%s\n' "$report" | python3 -c '
import json
import sys

report = json.load(sys.stdin)
for check in report["checks"]:
    print("%-40s %-15s %s" % (check["name"], check["status"], check["detail"]))
print("missing_or_setup_required=%d" % report["missing_or_setup_required"])
sys.exit(3 if report["missing_or_setup_required"] else 0)
' && missing=0 || missing=$?

if [ "$missing" -ne 0 ] && [ "$missing" -ne 3 ]; then
	exit "$missing"
fi
if [ "$strict" = 1 ] && [ "$missing" = 3 ]; then
	exit 3
fi
exit 0
