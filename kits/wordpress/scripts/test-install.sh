#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
installer="$script_dir/install.sh"
doctor="$script_dir/doctor.sh"
work=$(mktemp -d)
trap 'rm -rf -- "$work"' EXIT

target="$work/target"
outside="$work/outside"
mkdir -p "$target" "$outside"
printf '<?php\n' > "$target/wp-load.php"
printf 'locally tuned\n' > "$target/AGENTS.md"
printf 'outside sentinel\n' > "$outside/sentinel"

agents_before=$(sha256sum "$target/AGENTS.md")

"$installer" "$target" >/dev/null

[ "$agents_before" = "$(sha256sum "$target/AGENTS.md")" ]
[ -f "$target/docs/wordpress-agent-tooling.md" ]
[ -f "$target/phpcs.xml.dist" ]
[ -f "$target/tools/phpcs/composer.json" ]
[ -f "$target/.agents/skills/wordpress-site-safety/SKILL.md" ]
[ -f "$target/.claude/skills/wordpress-site-safety/SKILL.md" ]
[ -f "$target/.codex/skills/wordpress-site-safety/SKILL.md" ]
[ -f "$target/mcp.wordpress.example.json" ]
[ -f "$target/scripts/hooks/wordpress-phpcs-pre-push.sh" ]
python3 -c 'import json; json.load(open("'"$target"'/mcp.wordpress.example.json"))'

"$doctor" "$target" >/tmp/wordpress-kit-doctor.out
grep -q 'wordpress-root' /tmp/wordpress-kit-doctor.out

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

empty="$work/empty"
mkdir -p "$empty"
if "$installer" "$empty" >/dev/null 2>&1; then
	printf 'install without WordPress unexpectedly succeeded\n' >&2
	exit 1
fi

nested="$work/nested"
mkdir -p "$nested/website"
printf '<?php\n' > "$nested/website/wp-load.php"
"$installer" "$nested" >/dev/null
[ -f "$nested/phpcs.xml.dist" ]

symlink_target="$work/symlink-target"
mkdir -p "$symlink_target"
printf '<?php\n' > "$symlink_target/wp-load.php"
ln -s "$outside" "$symlink_target/docs"
if "$installer" "$symlink_target" >/dev/null 2>&1; then
	printf 'symlink-parent installation unexpectedly succeeded\n' >&2
	exit 1
fi
[ "$(cat "$outside/sentinel")" = "outside sentinel" ]

printf 'wordpress kit installer: wp-load discovery, nested website/, additive preservation, idempotency, dry-run, force rejection, and symlink containment passed\n'
