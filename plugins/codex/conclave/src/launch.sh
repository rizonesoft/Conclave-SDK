set -euo pipefail
fail() {
  printf '{"state":"setup_required","detail":"%s","valuesExposed":false}\n' "$1" >&2
  exit 78
}
root="$1"
case "$root" in
  "~/"*) root="$HOME/${root:2}" ;;
esac
root="$(cd -- "$root" 2>/dev/null && pwd -P)" || fail 'Conclave checkout is missing. Update the plugin repoRoot setting.'
test -f "$root/scripts/mcp-conclave.sh" || fail 'The configured checkout has no Conclave MCP launcher.'
git_root="$(git -C "$root" rev-parse --show-toplevel 2>/dev/null)" || fail 'The configured directory is not a Git checkout.'
test "$git_root" = "$root" || fail 'repoRoot must identify the checkout root.'
test -r "$root/.nvmrc" || fail 'The Conclave Node version file is missing.'
version="$(tr -d '[:space:]' < "$root/.nvmrc")"
version="${version#v}"
[[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || fail 'The Conclave Node version file is invalid.'
node_bin="$2"
if [ -z "$node_bin" ]; then
  if [ -x "$HOME/.nvm/versions/node/v$version/bin/node" ]; then
    node_bin="$HOME/.nvm/versions/node/v$version/bin/node"
  else
    node_bin="$(command -v node || true)"
  fi
fi
test -n "$node_bin" && test -x "$node_bin" || fail 'Install the Node version named by Conclave .nvmrc, or configure nodePath.'
unset NODE_OPTIONS NODE_PATH CONCLAVE_VAULT_NAME DATABASE_URL
node_version="$("$node_bin" --version 2>/dev/null)" || fail 'The configured Node executable could not start.'
test "$node_version" = "v$version" || fail 'Install the exact Node version named by Conclave .nvmrc, or update nodePath.'
export PATH="$(dirname -- "$node_bin"):$PATH"
export CONCLAVE_REPO_ROOT="$root"
export CONCLAVE_MCP_CLIENT_PROFILE=codex
cd -- "$root"
exec bash "$root/scripts/mcp-conclave.sh"
