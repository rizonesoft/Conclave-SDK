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
mkdir -p "$target/todo" "$outside"
printf 'project plan index\n' > "$target/todo/TODO-00-INDEX.md"
printf 'outside sentinel\n' > "$outside/sentinel"
index_before=$(sha256sum "$target/todo/TODO-00-INDEX.md")

"$installer" "$target" >/dev/null

# An existing plan is never touched; everything missing lands.
[ "$index_before" = "$(sha256sum "$target/todo/TODO-00-INDEX.md")" ]
for agent_dir in .agents .claude .codex; do
  for skill in add-todo create-todo groom-plan process-phase process-plan process-todo-file process-todo-section review-todo-section; do
    [ -f "$target/$agent_dir/skills/$skill/SKILL.md" ]
  done
done
[ -f "$target/.codex/skills/add-todo/agents/openai.yaml" ]
[ -f "$target/todo/README.md" ]
[ -f "$target/todo/templates/TODO-template.md" ]
[ -f "$target/docs/todo-workflow.md" ]
# Scripts are executable and nothing is world-writable, whatever modes the kit checkout reports.
[ "$(stat -c %a "$target/scripts/todo-graph.py")" = 755 ]
[ "$(stat -c %a "$target/todo/README.md")" = 644 ]
# The installed tool runs from the target.
(cd "$target" && python3 -B scripts/todo-graph.py --help >/dev/null)

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

printf 'todo kit installer: existing plan preserved, skills for 3 agents, todo-graph runnable, file modes, idempotency, dry-run, force rejection, and symlink containment passed\n'
