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
mkdir -p "$target/.conclave" "$outside"
printf 'schema_version = 1\n# tuned locally\n' > "$target/.conclave/reviewers.toml"
printf 'outside sentinel\n' > "$outside/sentinel"
pin_before=$(sha256sum "$target/.conclave/reviewers.toml")

"$installer" "$target" >/dev/null

# A project's own reviewer pin is never replaced; everything missing lands.
[ "$pin_before" = "$(sha256sum "$target/.conclave/reviewers.toml")" ]
for agent_dir in .agents .claude .codex; do
  [ -f "$target/$agent_dir/skills/independent-review/SKILL.md" ]
done
[ -f "$target/.codex/skills/independent-review/agents/openai.yaml" ]
[ -f "$target/docs/review-round-prompt.md" ]
[ "$(stat -c %a "$target/scripts/review-dispatch.py")" = 755 ]
(cd "$target" && python3 -B scripts/review-dispatch.py --help >/dev/null)

fresh="$work/fresh"
mkdir -p "$fresh"
"$installer" "$fresh" >/dev/null
grep -q 'model = "gpt-6-astra"' "$fresh/.conclave/reviewers.toml"
grep -q 'codex = \["gemini", "sonnet"\]' "$fresh/.conclave/reviewers.toml"

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

printf 'reviewer kit installer: existing pin preserved, skills for 3 agents, dispatcher runnable, file modes, idempotency, dry-run, force rejection, and symlink containment passed\n'
