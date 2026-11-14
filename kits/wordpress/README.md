# WordPress kit

Additive overlay that connects a WordPress project to its one live site on Pressable or WordPress.com: a site pin, SSH/SFTP through a pinned Conclave credential, the WordPress MCP and, on Pressable (or a WordPress.com Atomic site that asks for one), a pull-only DDEV mirror. It also brings PHPCS WordPress-Extra wiring and the `wordpress-site-safety` and `wordpress-connect` skills for Gemini (`.agents/`), Claude (`.claude/`) and Codex (`.codex/`). rizonetech-com is the reference site.

The kit copies files and never installs WordPress, WP-CLI, PHPCS, DDEV or a plugin. A local WordPress tree is optional: on Pressable the `wordpress-connect` skill creates it with DDEV, and a WordPress.com site has none unless the owner asks for the mirror on an Atomic site (SSH), as road-diamond-com did. Install `kits/base` (or `python forge.py init`) first when the repo should speak the full agent contract.

## What lands

Every host (`templates/`):

| Path | Role |
| ---- | ---- |
| `.conclave/wordpress-site.json` | Site pin: host, id, URL, environment, SSH, MCP servers |
| `scripts/lib/wp_site.py` | Reads and validates the pin; reads Conclave items by immutable id |
| `scripts/lib/site_ssh.py` | Pinned SSH, SFTP and rsync; password on a private pipe to `sshpass` |
| `bin/wp-remote`, `scripts/site-access.py` | WP-CLI on the live site; SSH/SFTP runner and `check` |
| `scripts/tests/test_site_access.py` | Pin and identity refusal tests (no network) |
| `.{agents,claude,codex}/skills/wordpress-site-safety/` | Site-safety rules |
| `.{agents,claude,codex}/skills/wordpress-connect/` | The setup runbook |
| `docs/wordpress-agent-tooling.md` | How the pieces fit |
| `phpcs.xml.dist`, `tools/phpcs/composer.json` | WordPress-Extra ruleset and isolated toolchain |
| `scripts/hooks/wordpress-phpcs-pre-push.sh` | Pre-push PHPCS run over the whole tree |

Pressable only (`hosts/pressable/templates/`):

| Path | Role |
| ---- | ---- |
| `scripts/sftp-item.py` | Resets the SFTP password into a new vault item |
| `scripts/create-application-password.py` | MCP Application Password into a new vault item |
| `scripts/mcp-headers.py`, `scripts/lib/mcp_http.py` | `headersHelper`; MCP client |
| `scripts/check-mcp.py` | Proves each pinned MCP server: identity, reads, 401 refusals |
| `mcp.wordpress.example.json` | `.mcp.json` servers: `mcp-adapter` and Pressable |
| `.ddev/providers/production.yaml`, `bin/ddev`, `bin/wp` | Pull-only DDEV provider and wrappers |
| `scripts/tests/test_pressable_access.py` | Header helper and setup helper refusal tests |

The DDEV pull itself, `scripts/production-sync.py`, is ported per site from jmrgroup-coza, because which tables and uploads hold personal data differs per site. The doctor reports it as `setup_required` until it exists.

## Install

```powershell
python forge.py kit /path/to/project wordpress --host pressable|wpcom [--agent all|gemini|claude|codex] [--dry-run]
python forge.py doctor /path/to/project wordpress [--strict]
```

`--host` defaults to `pressable`. Then run the `wordpress-connect` skill in the project: it fills the pin from the Pressable MCP or the WordPress.com connector, sets up SSH/SFTP and the WordPress MCP, and on Pressable the DDEV mirror. Every write to the live site or the host needs the owner's approval.

## Operator globals

`sshpass` (`apt install sshpass`) for every host; DDEV and Docker on Pressable projects; user-scoped WP-CLI where local WP-CLI is wanted (never an unverified PHAR in the repo); `composer install` in `tools/phpcs` after dependency approval. Credentials live in the Conclave vault and are read through `conclave-op`; no helper prints one.
