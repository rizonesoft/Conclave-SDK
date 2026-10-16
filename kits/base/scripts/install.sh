#!/usr/bin/env bash
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
  printf 'Unsupported option: %s. This starter installer never overwrites existing files.\n' "$mode" >&2
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

installed=0
skipped=0
sources=()

while IFS= read -r -d '' source; do
  sources+=("$source")
done < <(LC_ALL=C find "$template_root" -name __pycache__ -prune -o -type f -print0 | LC_ALL=C sort -z)

for source in "${sources[@]}"; do
  relative=${source#"$template_root"/}
  if has_unsafe_parent "$relative"; then
    printf 'Refusing destination with unsafe parent: %s\n' "$relative" >&2
    exit 1
  fi
done

for source in "${sources[@]}"; do
  relative=${source#"$template_root"/}
  destination="$target/$relative"

  if [ -e "$destination" ] || [ -L "$destination" ]; then
    printf 'preserve existing %s\n' "$relative"
    skipped=$((skipped + 1))
    continue
  fi

  if [ "$mode" = "--dry-run" ]; then
    printf 'would install %s\n' "$relative"
  else
    mkdir -p -- "$(dirname -- "$destination")"
    # Modes come from the content, not the source: a kit checked out on a Windows drive reports 0777.
    if [ "$(head -c 2 -- "$source")" = '#!' ]; then
        install -m 0755 -- "$source" "$destination"
    else
        install -m 0644 -- "$source" "$destination"
    fi
    printf 'installed %s\n' "$relative"
  fi
  installed=$((installed + 1))
done

printf 'summary installable=%d preserved=%d mode=%s\n' "$installed" "$skipped" "${mode:---apply}"
