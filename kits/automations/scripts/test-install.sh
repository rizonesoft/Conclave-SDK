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
mkdir -p "$target/.conclave/automations" "$outside"
printf '{"schema_version": 1, "folder": "\\\\Demo\\\\", "tasks": []}\n' > "$target/.conclave/automations/tasks.json"
printf 'outside sentinel\n' > "$outside/sentinel"
tasks_before=$(sha256sum "$target/.conclave/automations/tasks.json")

"$installer" "$target" >/dev/null

# A project's own task list is never replaced; everything missing lands.
[ "$tasks_before" = "$(sha256sum "$target/.conclave/automations/tasks.json")" ]
for agent_dir in .agents .claude .codex; do
  [ -f "$target/$agent_dir/skills/scheduled-automations/SKILL.md" ]
done
[ -f "$target/.codex/skills/scheduled-automations/agents/openai.yaml" ]
for file in run.py alert.py install.ps1 README.md; do
  [ -f "$target/.conclave/automations/$file" ]
done
[ "$(stat -c %a "$target/.conclave/automations/install.sh")" = 755 ]
(cd "$target" && [ "$(python3 -B .conclave/automations/run.py --check)" = '\Demo\' ])

fresh="$work/fresh"
mkdir -p "$fresh"
"$installer" "$fresh" >/dev/null
grep -q '"folder": null' "$fresh/.conclave/automations/tasks.json"
if (cd "$fresh" && python3 -B .conclave/automations/run.py --check >/dev/null 2>&1); then
  printf 'a fresh kit with no folder unexpectedly passed the install check\n' >&2
  exit 1
fi

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
ln -s "$outside" "$symlink_target/.conclave"
if "$installer" "$symlink_target" >/dev/null 2>&1; then
  printf 'symlink-parent installation unexpectedly succeeded\n' >&2
  exit 1
fi
[ "$(cat "$outside/sentinel")" = "outside sentinel" ]

printf 'automations kit installer: existing task list preserved, skills for 3 agents, runner checks the folder, file modes, idempotency, dry-run, force rejection, and symlink containment passed\n'
