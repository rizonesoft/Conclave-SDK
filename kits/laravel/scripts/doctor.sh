#!/usr/bin/env bash
# Read-only. Never installs. Exit 0 if the overlay is present; missing globals
# print setup_required lines on stderr and still exit 0 unless --strict.
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

missing=0
report() {
	local name=$1 status=$2 detail=$3
	printf '%-28s %s  %s\n' "$name" "$status" "$detail"
	if [ "$status" = "setup_required" ] || [ "$status" = "missing" ]; then
		missing=$((missing + 1))
	fi
}

if app_root=$(find_app_root "$target"); then
	report "artisan" "ok" "$app_root/artisan"
else
	report "artisan" "missing" "no artisan under $target"
	app_root=""
fi

if [ -f "$target/scripts/lsp-diagnostics.py" ]; then
	report "lsp-diagnostics.py" "ok" "$target/scripts/lsp-diagnostics.py"
else
	report "lsp-diagnostics.py" "missing" "run the kit installer"
fi

if [ -n "$app_root" ] && [ -f "$app_root/boost.json" ]; then
	report "boost.json" "ok" "$app_root/boost.json"
else
	report "boost.json" "missing" "run the kit installer"
fi

if [ -n "$app_root" ] && [ -f "$app_root/composer.json" ] && command -v composer >/dev/null 2>&1; then
	if (cd "$app_root" && composer show laravel/boost >/dev/null 2>&1); then
		report "laravel/boost" "ok" "composer package present"
	else
		report "laravel/boost" "setup_required" "composer require --dev laravel/boost (dependency approval)"
	fi
else
	report "laravel/boost" "setup_required" "composer show laravel/boost from the app root"
fi

if command -v laravel-lsp >/dev/null 2>&1; then
	report "laravel-lsp" "ok" "$(command -v laravel-lsp)"
else
	report "laravel-lsp" "setup_required" "composer global require laravel/lsp"
fi

if command -v tailwindcss-language-server >/dev/null 2>&1; then
	report "tailwindcss-language-server" "ok" "$(command -v tailwindcss-language-server)"
else
	report "tailwindcss-language-server" "setup_required" "npm install -g @tailwindcss/language-server"
fi

if command -v intelephense >/dev/null 2>&1; then
	report "intelephense" "ok" "$(command -v intelephense)"
else
	report "intelephense" "setup_required" "npm install -g intelephense"
fi

if [ "$strict" = 1 ] && [ "$missing" -gt 0 ]; then
	exit 3
fi
exit 0
