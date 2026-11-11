#!/usr/bin/env bash
# Deploy a skill from skills/global/<name>/ to the global Claude Code skills folder
# on Windows and in WSL. Runs from Git Bash on Windows or from WSL.
# Usage: bash scripts/deploy-skill.sh <name>
set -euo pipefail

name="${1:?usage: deploy-skill.sh <skill-name>}"
repo="$(cd "$(dirname "$0")/.." && pwd)"
src="$repo/skills/global/$name"
[ -f "$src/SKILL.md" ] || { echo "no global skill at $src (project skills in skills/project/ are copied into repositories, not deployed)" >&2; exit 1; }

copy() {
  local dest="$1/$name"
  mkdir -p "$1"
  rm -rf "$dest"
  cp -r "$src" "$dest"
  find "$dest" -name '__pycache__' -type d -prune -exec rm -rf {} +
  echo "deployed $name to $dest"
}

if grep -qi microsoft /proc/version 2>/dev/null; then
  # WSL: deploy here, then to the Windows profile through /mnt/c.
  copy "$HOME/.claude/skills"
  win_profile="$(wslpath "$(cmd.exe /c 'echo %USERPROFILE%' 2>/dev/null | tr -d '\r')")"
  copy "$win_profile/.claude/skills"
else
  # Git Bash on Windows: deploy here, then inside WSL from the /mnt view of this repository.
  copy "$(cygpath -u "$USERPROFILE")/.claude/skills"
  wsl_src="$(wsl.exe -e wslpath -a "$(cygpath -w "$src")" | tr -d '\r\0')"
  # MSYS would rewrite the /mnt/... argument into a Git for Windows path.
  MSYS_NO_PATHCONV=1 wsl.exe -e bash -c 'set -e; dest="$HOME/.claude/skills/$2"; mkdir -p "$HOME/.claude/skills"; rm -rf "$dest"; cp -r "$1" "$dest"; find "$dest" -name __pycache__ -type d -prune -exec rm -rf {} +; echo "deployed $2 to $dest"' _ "$wsl_src" "$name"
fi
