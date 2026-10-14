#!/usr/bin/env bash
# Additive overlay. Never overwrites. Never installs global tools.
set -euo pipefail

usage() {
	printf 'Usage: %s <target-project-dir> [--dry-run]\n' "$0" >&2
}

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
	usage
	exit 2
fi

target=$1
mode=${2:-}

if [ "$mode" != "" ] && [ "$mode" != "--dry-run" ]; then
	printf 'Unsupported option: %s. This installer never overwrites existing files.\n' "$mode" >&2
	usage
	exit 2
fi

if [ ! -d "$target" ] || [ -L "$target" ]; then
	printf 'Target must be an existing non-symlink directory: %s\n' "$target" >&2
	exit 1
fi

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
kit_root=$(cd -- "$script_dir/.." && pwd)
template_root="$kit_root/templates"
target=$(cd -- "$target" && pwd -P)

find_app_root() {
	local root=$1
	if [ -f "$root/artisan" ]; then
		printf '%s\n' "$root"
		return 0
	fi
	if [ -f "$root/platform/artisan" ]; then
		printf '%s\n' "$root/platform"
		return 0
	fi
	local child
	for child in "$root"/*; do
		[ -d "$child" ] || continue
		if [ -f "$child/artisan" ]; then
			printf '%s\n' "$child"
			return 0
		fi
	done
	return 1
}

if ! app_root=$(find_app_root "$target"); then
	printf 'No artisan found under %s (looked at the root, platform/, and first-level children).\n' "$target" >&2
	exit 1
fi

artisan_rel=$(python3 -c 'import os,sys; print(os.path.relpath(sys.argv[1], sys.argv[2]))' "$app_root/artisan" "$target")

has_unsafe_parent() {
	local relative=$1
	local current=$target
	local parent=${relative%/*}
	local component

	if [ "$parent" = "$relative" ]; then
		return 1
	fi

	while IFS= read -r component; do
		[ -n "$component" ] || continue
		current="$current/$component"
		if [ -L "$current" ] || { [ -e "$current" ] && [ ! -d "$current" ]; }; then
			return 0
		fi
	done < <(printf '%s\n' "$parent" | tr '/' '\n')

	return 1
}

copy_one() {
	local source=$1
	local destination=$2
	local relative=$3
	if [ -e "$destination" ] || [ -L "$destination" ]; then
		printf 'preserve existing %s\n' "$relative"
		skipped=$((skipped + 1))
		return 0
	fi
	parent=$(dirname -- "$relative")
	if [ "$parent" != "." ] && has_unsafe_parent "$relative"; then
		printf 'Refusing destination with unsafe parent: %s\n' "$relative" >&2
		exit 1
	fi
	if [ "$mode" = "--dry-run" ]; then
		printf 'would install %s\n' "$relative"
	else
		mkdir -p -- "$(dirname -- "$destination")"
		cp -p -- "$source" "$destination"
		printf 'installed %s\n' "$relative"
	fi
	installed=$((installed + 1))
}

installed=0
skipped=0

copy_one "$template_root/scripts/lsp-diagnostics.py" "$target/scripts/lsp-diagnostics.py" "scripts/lsp-diagnostics.py"
copy_one "$template_root/scripts/hooks/laravel-lsp-pre-push.sh" "$target/scripts/hooks/laravel-lsp-pre-push.sh" "scripts/hooks/laravel-lsp-pre-push.sh"
copy_one "$template_root/docs/laravel-agent-tooling.md" "$target/docs/laravel-agent-tooling.md" "docs/laravel-agent-tooling.md"
copy_one "$template_root/.agents/skills/laravel-boost/SKILL.md" "$target/.agents/skills/laravel-boost/SKILL.md" ".agents/skills/laravel-boost/SKILL.md"
copy_one "$template_root/.claude/skills/laravel-boost/SKILL.md" "$target/.claude/skills/laravel-boost/SKILL.md" ".claude/skills/laravel-boost/SKILL.md"
copy_one "$template_root/.codex/skills/laravel-boost/SKILL.md" "$target/.codex/skills/laravel-boost/SKILL.md" ".codex/skills/laravel-boost/SKILL.md"
copy_one "$template_root/.codex/skills/laravel-boost/agents/openai.yaml" "$target/.codex/skills/laravel-boost/agents/openai.yaml" ".codex/skills/laravel-boost/agents/openai.yaml"
app_rel=${app_root#"$target"/}
if [ "$app_rel" = "$app_root" ] || [ "$app_root" = "$target" ]; then
	boost_rel="boost.json"
else
	boost_rel="$app_rel/boost.json"
fi
copy_one "$template_root/boost.json" "$app_root/boost.json" "$boost_rel"

merge_mcp() {
	python3 - "$target" "$artisan_rel" "$mode" <<'PY'
import json, sys
from pathlib import Path

target = Path(sys.argv[1])
artisan_rel = sys.argv[2]
dry = sys.argv[3] == "--dry-run"
path = target / ".mcp.json"
server = {
    "command": "php",
    "args": [artisan_rel, "boost:mcp"],
}
if path.exists() or path.is_symlink():
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        print("preserve existing .mcp.json (unreadable; merge laravel-boost by hand)", file=sys.stderr)
        print(json.dumps({"laravel-boost": server}, indent=2))
        sys.exit(0)
    if not isinstance(data, dict):
        print("preserve existing .mcp.json (not an object)")
        sys.exit(0)
    servers = data.get("mcpServers")
    if isinstance(servers, dict) and "laravel-boost" in servers:
        print("preserve existing .mcp.json laravel-boost")
        sys.exit(0)
    print("merge-needed .mcp.json laravel-boost")
    print(json.dumps({"laravel-boost": server}, indent=2))
    sys.exit(0)

payload = {"mcpServers": {"laravel-boost": server}}
if dry:
    print("would install .mcp.json")
else:
    path.write_text(json.dumps(payload, indent=4) + "\n", encoding="utf-8")
    print("installed .mcp.json")
PY
}

if [ "$mode" = "--dry-run" ]; then
	merge_mcp || true
else
	merge_mcp
fi

printf 'summary installable=%d preserved=%d artisan=%s mode=%s\n' \
	"$installed" "$skipped" "$artisan_rel" "${mode:---apply}"
printf 'Run kits/laravel/scripts/doctor.sh %s for Boost and LSP health.\n' "$target"
