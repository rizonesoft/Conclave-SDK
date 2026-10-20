#!/usr/bin/env bash
set -euo pipefail

# Git Bash makes `ln -s` copy a directory unless MSYS asks for a native link; nativestrict fails loudly instead,
# so the symlink containment checks below test a real link on Windows too. Other platforms ignore it.
export MSYS="${MSYS:+$MSYS }winsymlinks:nativestrict"

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
installer="$script_dir/install.sh"
doctor="$script_dir/doctor.sh"
work=$(mktemp -d)
kit_cache="$script_dir/../templates/scripts/lib/__pycache__"
cache_existed=0
[ -d "$kit_cache" ] && cache_existed=1
cleanup() {
	rm -rf -- "$work"
	rm -f -- "$kit_cache/stray.pyc"
	[ "$cache_existed" = 1 ] || rmdir -- "$kit_cache" 2>/dev/null || true
}
trap cleanup EXIT

target="$work/target"
outside="$work/outside"
mkdir -p "$target" "$outside"
printf '<?php\n' > "$target/wp-load.php"
printf 'locally tuned\n' > "$target/AGENTS.md"
printf 'outside sentinel\n' > "$outside/sentinel"

agents_before=$(sha256sum "$target/AGENTS.md")

# Bytecode from running the kit's own tests in the SDK checkout is never installed.
mkdir -p "$kit_cache"
touch "$kit_cache/stray.pyc"
"$installer" "$target" >/dev/null
rm -f "$kit_cache/stray.pyc"
[ ! -e "$target/scripts/lib/__pycache__" ]

[ "$agents_before" = "$(sha256sum "$target/AGENTS.md")" ]
[ -f "$target/docs/wordpress-agent-tooling.md" ]
[ -f "$target/phpcs.xml.dist" ]
[ -f "$target/tools/phpcs/composer.json" ]
[ -f "$target/.agents/skills/wordpress-site-safety/SKILL.md" ]
[ -f "$target/.claude/skills/wordpress-site-safety/SKILL.md" ]
[ -f "$target/.codex/skills/wordpress-site-safety/SKILL.md" ]
[ -f "$target/mcp.wordpress.example.json" ]
[ -f "$target/scripts/hooks/wordpress-phpcs-pre-push.sh" ]
[ -f "$target/.agents/skills/wordpress-connect/SKILL.md" ]
[ -f "$target/.ddev/providers/production.yaml" ]
python3 -c 'import json, sys; json.load(open(sys.argv[1]))' "$target/mcp.wordpress.example.json"
python3 -c 'import json, sys; sys.exit(json.load(open(sys.argv[1]))["host"] != "pressable")' "$target/.conclave/wordpress-site.json"
# Modes come from the content: scripts executable, nothing world-writable, whatever the checkout reports.
[ "$(stat -c %a "$target/bin/wp-remote")" = 755 ]
[ "$(stat -c %a "$target/phpcs.xml.dist")" = 644 ]

"$doctor" "$target" >"$work/doctor.out"
grep -q '^wordpress-root ' "$work/doctor.out"
grep -q '^site-identity  *setup_required' "$work/doctor.out"
if "$doctor" "$target" --strict >/dev/null; then
	printf 'strict doctor passed with setup still required\n' >&2
	exit 1
fi

tree_after_first=$(cd "$target" && find . -type f -print0 | sort -z | xargs -0 -r sha256sum)
"$installer" "$target" >/dev/null
[ "$tree_after_first" = "$(cd "$target" && find . -type f -print0 | sort -z | xargs -0 -r sha256sum)" ]

dry_target="$work/dry-target"
mkdir -p "$dry_target"
printf '<?php\n' > "$dry_target/wp-config.php"
"$installer" "$dry_target" --dry-run >/dev/null
[ ! -f "$dry_target/phpcs.xml.dist" ]

if "$installer" "$target" --force >/dev/null 2>&1; then
	printf 'legacy destructive --force mode unexpectedly succeeded\n' >&2
	exit 1
fi

if "$installer" "$target" --host kinsta >/dev/null 2>&1; then
	printf 'unknown host unexpectedly accepted\n' >&2
	exit 1
fi

# A WordPress.com site has no local tree, no DDEV and no project MCP servers.
wpcom="$work/wpcom"
mkdir -p "$wpcom"
"$installer" "$wpcom" --host wpcom >/dev/null
[ -f "$wpcom/bin/wp-remote" ]
[ -f "$wpcom/.claude/skills/wordpress-connect/SKILL.md" ]
[ ! -e "$wpcom/.ddev" ]
[ ! -e "$wpcom/mcp.wordpress.example.json" ]
[ ! -e "$wpcom/scripts/mcp-headers.py" ]
python3 -c 'import json, sys; sys.exit(json.load(open(sys.argv[1]))["host"] != "wpcom")' "$wpcom/.conclave/wordpress-site.json"
wpcom_report=$("$doctor" "$wpcom")
printf '%s\n' "$wpcom_report" | grep -Eq '^no-ddev +ok'
# Re-running without --host follows the pin; a conflicting --host is refused.
"$installer" "$wpcom" >/dev/null
[ ! -e "$wpcom/.ddev" ]
if "$installer" "$wpcom" --host pressable >/dev/null 2>&1; then
	printf 'conflicting host unexpectedly accepted\n' >&2
	exit 1
fi

nested="$work/nested"
mkdir -p "$nested/website"
printf '<?php\n' > "$nested/website/wp-load.php"
"$installer" "$nested" >/dev/null
[ -f "$nested/phpcs.xml.dist" ]

# The doctor finds the same first-level child the installer accepts.
child="$work/child"
mkdir -p "$child/site"
printf '<?php\n' > "$child/site/wp-load.php"
"$installer" "$child" >/dev/null
child_report=$("$doctor" "$child")
printf '%s\n' "$child_report" | grep -Eq '^wordpress-root +ok +.*/site$'

symlink_target="$work/symlink-target"
mkdir -p "$symlink_target"
printf '<?php\n' > "$symlink_target/wp-load.php"
ln -s "$outside" "$symlink_target/docs"
if "$installer" "$symlink_target" >/dev/null 2>&1; then
	printf 'symlink-parent installation unexpectedly succeeded\n' >&2
	exit 1
fi
[ "$(cat "$outside/sentinel")" = "outside sentinel" ]

printf 'wordpress kit installer: wp-load discovery, nested website/, both hosts, file modes, doctor, additive preservation, idempotency, dry-run, force rejection, and symlink containment passed\n'
