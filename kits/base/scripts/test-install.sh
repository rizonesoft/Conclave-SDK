#!/usr/bin/env bash
set -euo pipefail

# Git Bash makes `ln -s` copy a directory unless MSYS asks for a native link; nativestrict fails loudly instead,
# so the symlink containment checks below test a real link on Windows too. Other platforms ignore it.
export MSYS="${MSYS:+$MSYS }winsymlinks:nativestrict"

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
installer="$script_dir/install.sh"
work=$(mktemp -d)
trap 'rm -rf -- "$work"' EXIT

target="$work/target"
outside="$work/outside"
mkdir -p "$target/.claude/skills/local-tool-safety" "$target/.codex" "$outside"
printf 'locally tuned\n' > "$target/AGENTS.md"
printf 'custom skill\n' > "$target/.claude/skills/local-tool-safety/SKILL.md"
printf 'custom settings\n' > "$target/.codex/settings.toml"
printf 'outside sentinel\n' > "$outside/sentinel"

agents_before=$(sha256sum "$target/AGENTS.md")
skill_before=$(sha256sum "$target/.claude/skills/local-tool-safety/SKILL.md")
settings_before=$(sha256sum "$target/.codex/settings.toml")

"$installer" "$target" >/dev/null

[ "$agents_before" = "$(sha256sum "$target/AGENTS.md")" ]
[ "$skill_before" = "$(sha256sum "$target/.claude/skills/local-tool-safety/SKILL.md")" ]
[ "$settings_before" = "$(sha256sum "$target/.codex/settings.toml")" ]
[ -f "$target/.agents/skills/authoring-skills/SKILL.md" ]
[ -f "$target/.agents/agents/code-explorer.md" ]
[ -f "$target/.claude/skills/authoring-skills/SKILL.md" ]
[ -f "$target/.codex/skills/authoring-skills/SKILL.md" ]
[ -f "$target/scripts/agy-subagent.py" ]
# Nothing is world-writable, whatever modes the kit checkout reports.
[ "$(stat -c %a "$target/.claude/skills/authoring-skills/SKILL.md")" = 644 ]
[ "$(stat -c %a "$target/scripts/agy-subagent.py")" = 755 ]

tree_after_first=$(cd "$target" && find . -type f -print0 | sort -z | xargs -0 -r sha256sum)
"$installer" "$target" >/dev/null
[ "$tree_after_first" = "$(cd "$target" && find . -type f -print0 | sort -z | xargs -0 -r sha256sum)" ]

dry_target="$work/dry-target"
mkdir -p "$dry_target"
"$installer" "$dry_target" --dry-run >/dev/null
[ -z "$(find "$dry_target" -mindepth 1 -print -quit)" ]

if "$installer" "$target" --force >/dev/null 2>&1; then
  printf 'legacy destructive --force mode unexpectedly succeeded\n' >&2
  exit 1
fi

symlink_target="$work/symlink-target"
mkdir -p "$symlink_target"
ln -s "$outside" "$symlink_target/scripts"
if "$installer" "$symlink_target" >/dev/null 2>&1; then
  printf 'symlink-parent installation unexpectedly succeeded\n' >&2
  exit 1
fi
[ "$(cat "$outside/sentinel")" = "outside sentinel" ]
[ "$(find "$outside" -mindepth 1 ! -name sentinel -print -quit)" = "" ]
[ "$(find "$symlink_target" -type f -print -quit)" = "" ]

printf 'base kit installer: additive preservation, idempotency, dry-run, force rejection, preflight atomicity, and symlink containment passed\n'
