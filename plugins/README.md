# Plugins

Standalone agent plugins that are not part of any kit: a Claude Code plugin, a Codex plugin or an Antigravity plugin bundle that you load on its own, by path or from a marketplace. `forge.py` never copies anything from here into a project.

A plugin that only makes sense together with a kit lives in that kit instead (`kits/<kit>/plugins/`), so choosing the kit is what brings it in.

Give each plugin its own folder, named for its capability, with its manifest and a README that says which agent loads it and how.

## Imported plugins

These plugins connect one owner's own accounts and services. They are account-bound tools and `forge.py` never installs them. Each plugin folder has its own README, manifest, source and tests. Test counts are `test(` and `it(` declarations under each plugin's `tests/`.

| Plugin | Agent | Service it connects | Tests |
| ------ | ----- | ------------------- | ----- |
| `codex/website-router` | Codex | WordPress sites over MCP, SSH and SFTP | 19 |
| `codex/pressable` | Codex | Pressable hosting and reviewed WP-CLI | 15 |
| `codex/outlook-graph` | Codex | Outlook mail and drafts through Microsoft Graph | 82 |
| `codex/atera` | Codex | Atera devices, monitors, patches, alerts | 16 |
| `codex/domains-co-za` | Codex | Domains.co.za domains, DNS, renewals | 17 |
| `codex/bunny-net` | Codex | Bunny.net CDN, DNS and Storage | 18 |
| `codex/cloud-access` | Codex | Private ChatGPT tunnel access (scripts) | 0 |
| `codex/conclave` | Codex | Conclave WSL MCP server for cloud access | 16 |
| `claude/domains-co-za` | Claude | Domains.co.za domains, DNS, renewals | 14 |
| `claude/bunny-net` | Claude | Bunny.net CDN, DNS and Storage | 16 |

Shared design notes for the Codex plugins are in `codex/DESIGN.md`, with the approval and Windows credential rules in `codex/docs/`.

## Claude helper scripts

`claude/scripts/` holds the helpers for the two Claude plugins. Each finds the plugin folders from its own location, so the servers run straight from this checkout: `<SDK>\plugins\claude\<name>\dist\server.mjs` under Windows Node, on Windows and in WSL alike.

- `build_claude.py [--check] [name ...]` runs `npm ci` and `npm run build`, then records the digest of the sources in `dist/source.sha256`. `dist/server.mjs` and the stamp are tracked in git, so a fresh checkout runs the servers with no build step; `--check` reports a missing or stale bundle.
- `register_claude.py [--check]` registers (or re-registers) every Claude connection plugin with Claude Code at user scope through `claude mcp add-json`. The CLI takes an entry only as an argument, so an entry that carries an `env` block is refused and left untouched, never sent or printed (the plugins read no environment). Run it once on Windows and once in WSL. `--check` writes nothing and reports an entry that is missing, is not exactly Windows Node running this checkout's bundle, or runs a stale bundle. `register-claude.sh` runs the same script.
- The once-per-session drift check (`global/claude/hooks/session_drift_check.py`) applies the same `--check` rules on the first prompt of every Claude Code session.
- Tests: `python -m unittest discover -s plugins/claude/scripts -p "test_*.py"`.
- `import-bunny-net.sh` and `import-domains-co-za.sh` seed the encrypted credential store from the Conclave vault.

In the plugin READMEs, `<SDK>` means the Conclave-SDK checkout.

## Account identifiers

The Codex cloud plugins carry mail addresses, hostnames and connector identifiers (`CLOUD.md` in `codex/conclave`, `codex/pressable` and `codex/website-router`, and the `codex/cloud-access` README and `linux/` scripts). Review those before any change of ownership.

The Codex plugins are listed in one private catalogue, `codex/.agents/plugins/marketplace.json`, with paths relative to `codex/`: register it with `codex plugin marketplace add <SDK>\plugins\codex` and install a plugin by name.

## Registered from this checkout

Since 2026-11-16 every plugin above runs from this checkout and nothing runs from the retired `R:\Bin` copies. Claude Code runs the two Claude servers straight from `<SDK>\plugins\claude\<name>\dist\server.mjs`, on Windows and in WSL. Codex reads the `rizonetech` marketplace from `<SDK>\plugins\codex` (`/mnt/d/Conclave-SDK/plugins/codex` in WSL) and runs each plugin from the copy it installs under `~/.codex/plugins/cache/rizonetech/<name>/<version>`, so a change here reaches Codex only after `codex plugin add <name>@rizonetech` refreshes that copy. On the owner's machine Codex on Windows has the seven MCP plugins installed and Codex in WSL has `outlook-graph`; `codex/cloud-access` is scripts with no MCP server, so it has nothing to register.

To register them on a new machine, on Windows and again in WSL:

1. Clone the SDK, then run `python plugins/claude/scripts/register_claude.py` for the two Claude servers.
2. Run `codex plugin marketplace add <SDK>\plugins\codex`, then `codex plugin add <name>@rizonetech` for each Codex plugin that system uses.
3. Seed each plugin's encrypted credential store from the Conclave vault with its own import script (each plugin README names it), because the stores are bound to the Windows account and machine.
4. Check: `register_claude.py --check` prints `ok`, and `echo '{"session_id":"<a new id each run>"}' | python global/codex/hooks/session_drift_check.py` prints nothing (it runs once per session id, and it compares the marketplace source and every installed copy's bundles, `scripts/`, source and MCP manifest with this checkout, and names what differs).

## Antigravity plugins

General-purpose Antigravity bundles under `agy/` have no host or account bindings and install globally by mirroring into `.gemini/config/plugins/` through `global/deploy.py --agent agy`. Run `global/deploy.py --agent agy --check` to verify sync; `powertools` also checks for drift once per session against its deployed checkout.

| Plugin | Purpose |
| ------ | ------- |
| `agy/powertools` | Global rules, lifecycle hooks, debugging, verification, review, and config skills |
| `agy/craft` | Anti-slop frontend design plus `docx`, `xlsx`, `pptx`, and `pdf` authoring skills |
