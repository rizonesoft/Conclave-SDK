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
| `codex/outlook-graph` | Codex | Outlook mail and drafts through Microsoft Graph | 81 |
| `codex/atera` | Codex | Atera devices, monitors, patches, alerts | 16 |
| `codex/domains-co-za` | Codex | Domains.co.za domains, DNS, renewals | 17 |
| `codex/bunny-net` | Codex | Bunny.net CDN, DNS and Storage | 18 |
| `codex/cloud-access` | Codex | Private ChatGPT tunnel access (scripts) | 0 |
| `codex/conclave` | Codex | Conclave WSL MCP server for cloud access | 16 |
| `claude/domains-co-za` | Claude | Domains.co.za domains, DNS, renewals | 14 |
| `claude/bunny-net` | Claude | Bunny.net CDN, DNS and Storage | 16 |

Shared design notes for the Codex plugins are in `codex/DESIGN.md`, with the approval and Windows credential rules in `codex/docs/`.

## Claude helper scripts

`claude/scripts/` holds the shell helpers for the two Claude plugins. Each finds the plugin folders from its own location and converts paths with `wslpath -w` (or `cygpath -w`) where Windows needs them.

- `register-claude.sh` registers (or re-registers) every Claude connection plugin with Claude Code at user scope.
- `import-bunny-net.sh` and `import-domains-co-za.sh` seed the encrypted credential store from the Conclave vault.

In the plugin READMEs, `<SDK>` means the Conclave-SDK checkout.

## Account identifiers

The Codex cloud plugins carry mail addresses, hostnames and connector identifiers (`CLOUD.md` in `codex/conclave`, `codex/pressable` and `codex/website-router`, and the `codex/cloud-access` README and `linux/` scripts). Review those before any change of ownership.

The Codex plugins are listed in one private catalogue, `codex/.agents/plugins/marketplace.json`, with paths relative to `codex/`: register it with `codex plugin marketplace add <SDK>\plugins\codex` and install a plugin by name.
