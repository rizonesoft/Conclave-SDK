#!/usr/bin/env bash
# Additive overlay. Never overwrites. Never installs global tools.
set -euo pipefail

# Copy to a temporary file beside the destination, then rename it into place, so an interrupted install never leaves a
# partial file that a later run would preserve as if it were the project's own.
place() {
  local mode=$1 source=$2 destination=$3 temporary
  temporary=$(mktemp -- "$(dirname -- "$destination")/.kit-install.XXXXXX")
  install -m "$mode" -- "$source" "$temporary"
  mv -f -- "$temporary" "$destination"
}

usage() {
	printf 'Usage: %s <target-project-dir> [--host pressable|wpcom] [--dry-run]\n' "$0" >&2
}

if [ "$#" -lt 1 ]; then
	usage
	exit 2
fi

target=$1
shift
mode=
host=

while [ "$#" -gt 0 ]; do
	case $1 in
		--dry-run)
			mode=--dry-run
			;;
		--host)
			if [ "$#" -lt 2 ]; then
				usage
				exit 2
			fi
			host=$2
			shift
			;;
		*)
			printf 'Unsupported option: %s. This installer never overwrites existing files.\n' "$1" >&2
			usage
			exit 2
			;;
	esac
	shift
done

if [ -n "$host" ] && [ "$host" != pressable ] && [ "$host" != wpcom ]; then
	printf 'Unsupported host: %s (expected pressable or wpcom).\n' "$host" >&2
	exit 2
fi

if [ ! -d "$target" ] || [ -L "$target" ]; then
	printf 'Target must be an existing non-symlink directory: %s\n' "$target" >&2
	exit 1
fi

# An existing site pin decides the host, so re-running the kit can never add another host's files.
pin="$target/.conclave/wordpress-site.json"
if [ -e "$pin" ]; then
	if ! pinned=$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["host"])' "$pin" 2>/dev/null) \
		|| { [ "$pinned" != pressable ] && [ "$pinned" != wpcom ]; }; then
		printf 'The site pin %s is unreadable; fix it before re-applying the kit.\n' "$pin" >&2
		exit 1
	fi
	if [ -n "$host" ] && [ "$host" != "$pinned" ]; then
		printf 'The site pin names host %s, not %s.\n' "$pinned" "$host" >&2
		exit 1
	fi
	host=$pinned
fi
host=${host:-pressable}

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
kit_root=$(cd -- "$script_dir/.." && pwd)
template_roots=("$kit_root/templates" "$kit_root/hosts/$host/templates")
target=$(cd -- "$target" && pwd -P)

is_wp_root() {
	[ -f "$1/wp-load.php" ] || [ -f "$1/wp-config.php" ] || [ -f "$1/wp-includes/version.php" ]
}

find_wp_root() {
	local root=$1 child
	if is_wp_root "$root"; then
		printf '%s\n' "$root"
		return 0
	fi
	for child in website wordpress wp; do
		if is_wp_root "$root/$child"; then
			printf '%s\n' "$root/$child"
			return 0
		fi
	done
	for child in "$root"/*; do
		[ -d "$child" ] && [ ! -L "$child" ] || continue
		if is_wp_root "$child"; then
			printf '%s\n' "$child"
			return 0
		fi
	done
	return 1
}

# A local WordPress tree is optional: on Pressable the wordpress-connect skill creates it with DDEV,
# and a WordPress.com site has none.
wp_root=$(find_wp_root "$target") || wp_root=none

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
relatives=()

for template_root in "${template_roots[@]}"; do
	while IFS= read -r -d '' source; do
		sources+=("$source")
		relatives+=("${source#"$template_root"/}")
	done < <(LC_ALL=C find "$template_root" -name __pycache__ -prune -o -type f -print0 | LC_ALL=C sort -z)
done

for relative in "${relatives[@]}"; do
	if has_unsafe_parent "$relative"; then
		printf 'Refusing destination with unsafe parent: %s\n' "$relative" >&2
		exit 1
	fi
done

for index in "${!sources[@]}"; do
	source=${sources[$index]}
	relative=${relatives[$index]}
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
			place 0755 "$source" "$destination"
		else
			place 0644 "$source" "$destination"
		fi
		printf 'installed %s\n' "$relative"
	fi
	installed=$((installed + 1))
done

printf 'summary installable=%d preserved=%d host=%s wordpress=%s mode=%s\n' \
	"$installed" "$skipped" "$host" "$wp_root" "${mode:---apply}"
printf 'Run kits/wordpress/scripts/doctor.sh %s for site, helper, WP-CLI and PHPCS health.\n' "$target"
