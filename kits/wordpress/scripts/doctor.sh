#!/usr/bin/env bash
# Read-only. Never installs.
set -euo pipefail

strict=0
target=.
for arg in "$@"; do
	if [ "$arg" = "--strict" ]; then
		strict=1
	else
		target=$arg
	fi
done

if [ ! -d "$target" ]; then
	printf 'doctor: not a directory: %s\n' "$target" >&2
	exit 2
fi

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
	return 1
}

missing=0
report() {
	local name=$1 status=$2 detail=$3
	printf '%-28s %s  %s\n' "$name" "$status" "$detail"
	if [ "$status" = "setup_required" ] || [ "$status" = "missing" ]; then
		missing=$((missing + 1))
	fi
}

if wp_root=$(find_wp_root "$target"); then
	report "wordpress-root" "ok" "$wp_root"
else
	report "wordpress-root" "missing" "no wp-load.php or wp-config.php"
fi

if [ -f "$target/phpcs.xml.dist" ]; then
	report "phpcs.xml.dist" "ok" "$target/phpcs.xml.dist"
else
	report "phpcs.xml.dist" "missing" "run the kit installer"
fi

if [ -f "$target/tools/phpcs/composer.json" ]; then
	report "phpcs-toolchain" "ok" "$target/tools/phpcs/composer.json"
else
	report "phpcs-toolchain" "missing" "run the kit installer"
fi

if [ -x "$target/tools/phpcs/vendor/bin/phpcs" ]; then
	report "phpcs" "ok" "$target/tools/phpcs/vendor/bin/phpcs"
else
	report "phpcs" "setup_required" "composer install in tools/phpcs (dependency approval)"
fi

if command -v wp >/dev/null 2>&1; then
	report "wp-cli" "ok" "$(command -v wp)"
else
	report "wp-cli" "setup_required" "user-scoped WP-CLI; do not drop a PHAR into the repo"
fi

if [ -f "$target/.claude/skills/wordpress-site-safety/SKILL.md" ]; then
	report "wordpress-rule" "ok" "$target/.claude/skills/wordpress-site-safety/SKILL.md"
else
	report "wordpress-rule" "missing" "run the kit installer"
fi

if [ "$strict" = 1 ] && [ "$missing" -gt 0 ]; then
	exit 3
fi
exit 0
