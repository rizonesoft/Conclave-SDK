# WordPress kit

Additive overlay that connects a WordPress project to its one live site on Pressable or WordPress.com: a site pin, SSH/SFTP through a pinned Conclave credential, the WordPress MCP and, on Pressable (or a WordPress.com Atomic site that asks for one), a pull-only DDEV mirror. It also brings PHPCS WordPress-Extra wiring and the `wordpress-site-safety` and `wordpress-connect` skills for Gemini (`.agents/`), Claude (`.claude/`) and Codex (`.codex/`). No site, vault or owner is named in the kit: the vault and its tool come from `[vault]` in `.conclave/local.toml` or `.private/local.toml`, and the projects the setup is modelled on from `[wordpress]` there (the base kit's `.conclave/local.example.toml` is the template).

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
| `tools/ticket-login/conclave-ticket-login.php` | Plugin that logs the admin in from a one-use ticket; holds no key |
| `tools/elementor-cache-purge/` | Plugin that purges the page cache when Elementor deletes its CSS |
| `scripts/elementor-cache.py`, `scripts/tests/test_elementor_cache.py` | Its check, status and install, and tests |
| `scripts/tests/test_ticket_login.py`, `ticket_login_harness.php` | The plugin's text and behaviour tests (PHP CLI) |
| `.{agents,claude,codex}/skills/wordpress-site-safety/` | Site-safety rules |
| `.{agents,claude,codex}/skills/wordpress-connect/` | The setup runbook |
| `docs/wordpress-agent-tooling.md` | How the pieces fit |
| `phpcs.xml.dist`, `tools/phpcs/composer.json` | WordPress-Extra ruleset for site code, and its toolchain |
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

The DDEV pull itself, `scripts/production-sync.py`, is ported per site from the project `wordpress.port_source` names in `.conclave/local.toml` or `.private/local.toml`, because which tables and uploads hold personal data differs per site. The doctor reports it as `setup_required` until it exists.

## Install

```powershell
python forge.py kit /path/to/project wordpress --host pressable|wpcom [--agent all|gemini|claude|codex] [--dry-run]
python forge.py doctor /path/to/project wordpress [--strict]
```

`--host` defaults to `pressable`. Then run the `wordpress-connect` skill in the project: it fills the pin from the Pressable MCP or the WordPress.com connector, sets up SSH/SFTP and the WordPress MCP, and on Pressable the DDEV mirror. Every write to the live site or the host needs the owner's approval.

## Operator globals

The `toolchain-web` kit checks PHP, Composer, Node and a package manager against pins the project owns (`python forge.py kit <project> toolchain-web`, then `python forge.py doctor <project> toolchain-web`). This kit's own PHP_CodeSniffer lives in `tools/phpcs`, which that kit's `search` folders do not read: add `tools/phpcs/vendor/bin` to `search` in `.conclave/toolchain-web.json` to have it checked.

`sshpass` (`apt install sshpass`) for every host; DDEV and Docker on Pressable projects; user-scoped WP-CLI where local WP-CLI is wanted (never an unverified PHAR in the repo); `composer install` in `tools/phpcs` after dependency approval. Credentials live in the Conclave vault and are read through `conclave-op`; no helper prints one.
