#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
installer="$script_dir/install.sh"
doctor="$script_dir/doctor.sh"
work=$(mktemp -d)
trap 'rm -rf -- "$work"' EXIT

target="$work/target"
outside="$work/outside"
mkdir -p "$target/resources/css" "$outside"
printf '<?php\n' > "$target/artisan"
printf '{"name":"fixture/laravel","require-dev":{}}\n' > "$target/composer.json"
printf 'locally tuned\n' > "$target/AGENTS.md"
printf '@import "tailwindcss";\n' > "$target/resources/css/app.css"
printf 'outside sentinel\n' > "$outside/sentinel"

agents_before=$(sha256sum "$target/AGENTS.md")

"$installer" "$target" >/dev/null

[ "$agents_before" = "$(sha256sum "$target/AGENTS.md")" ]
[ -f "$target/scripts/lsp-diagnostics.py" ]
[ -f "$target/scripts/hooks/laravel-lsp-pre-push.sh" ]
# Scripts are executable and nothing is world-writable, whatever modes the kit checkout reports.
[ "$(stat -c %a "$target/scripts/hooks/laravel-lsp-pre-push.sh")" = 755 ]
[ "$(stat -c %a "$target/docs/laravel-agent-tooling.md")" = 644 ]
[ -f "$target/boost.json" ]
[ -f "$target/docs/laravel-agent-tooling.md" ]
[ -f "$target/.agents/skills/laravel-boost/SKILL.md" ]
[ -f "$target/.claude/skills/laravel-boost/SKILL.md" ]
[ -f "$target/.codex/skills/laravel-boost/SKILL.md" ]
[ -f "$target/.mcp.json" ]
python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); assert d["mcpServers"]["laravel-boost"]["args"]==["artisan","boost:mcp"]' "$target/.mcp.json"

python3 "$target/scripts/lsp-diagnostics.py" --help >/dev/null

"$doctor" "$target" >/tmp/laravel-kit-doctor.out
grep -q 'artisan' /tmp/laravel-kit-doctor.out
grep -q 'lsp-diagnostics.py' /tmp/laravel-kit-doctor.out

tree_after_first=$(cd "$target" && find . -type f -print0 | sort -z | xargs -0 -r sha256sum)
"$installer" "$target" >/dev/null
[ "$tree_after_first" = "$(cd "$target" && find . -type f -print0 | sort -z | xargs -0 -r sha256sum)" ]

dry_target="$work/dry-target"
mkdir -p "$dry_target"
printf '<?php\n' > "$dry_target/artisan"
"$installer" "$dry_target" --dry-run >/dev/null
[ ! -f "$dry_target/scripts/lsp-diagnostics.py" ]
[ ! -f "$dry_target/.mcp.json" ]

if "$installer" "$target" --force >/dev/null 2>&1; then
	printf 'legacy destructive --force mode unexpectedly succeeded\n' >&2
	exit 1
fi

no_artisan="$work/empty"
mkdir -p "$no_artisan"
if "$installer" "$no_artisan" >/dev/null 2>&1; then
	printf 'install without artisan unexpectedly succeeded\n' >&2
	exit 1
fi

nested="$work/nested"
mkdir -p "$nested/platform/resources/css"
printf '<?php\n' > "$nested/platform/artisan"
printf '{"name":"fixture/nested"}\n' > "$nested/platform/composer.json"
"$installer" "$nested" >/dev/null
[ -f "$nested/scripts/lsp-diagnostics.py" ]
[ -f "$nested/platform/boost.json" ]
python3 -c 'import json; d=json.load(open("'"$nested"'/.mcp.json")); assert d["mcpServers"]["laravel-boost"]["args"][0]=="platform/artisan"'

symlink_target="$work/symlink-target"
mkdir -p "$symlink_target"
printf '<?php\n' > "$symlink_target/artisan"
ln -s "$outside" "$symlink_target/scripts"
if "$installer" "$symlink_target" >/dev/null 2>&1; then
	printf 'symlink-parent installation unexpectedly succeeded\n' >&2
	exit 1
fi
[ "$(cat "$outside/sentinel")" = "outside sentinel" ]

printf 'laravel kit installer: artisan discovery, nested platform/, additive preservation, idempotency, dry-run, force rejection, and symlink containment passed\n'
