# WordPress kit: site connection setup

Date: 2026-10-16. Owner decision the same day: ship generic, pin-driven helpers rather than porting them per site.

## Goal

`kits/wordpress` sets up a WordPress project's connections to its one live site, the way `rizonetech-com` (the reference site) and `jmrgroup-coza` do today: SSH/SFTP through a pinned Conclave credential, the WordPress MCP, and, on Pressable only, a pull-only local DDEV mirror. The host is Pressable or WordPress.com, and the setup is driven through the Pressable MCP or the WordPress.com connector.

## Host model

| Host | SSH/SFTP | WordPress MCP | DDEV |
| --- | --- | --- | --- |
| `pressable` | `sftp-item.py` via the Pressable MCP | `mcp-adapter` | Pull only |
| `wpcom` | Owner creates it in Hosting settings | The WordPress.com connector | None |

A WordPress.com Simple site has no SSH; the connector is its only channel.

## The pin

`.conclave/wordpress-site.json` is the one place that names the site: `host`, `site_id`, `url`, `environment`, `ssh` (`item`, `ssh_host`, `sftp_host`, `port`, `username`, `wp_path`) and, on Pressable, `pressable` (`account_id`) and `mcp` (one entry per `.mcp.json` server; the Pressable control plane is the `bearer` one). Unknown values are `null` until the setup fills them. Every helper reads it through `scripts/lib/wp_site.py`, which refuses a malformed pin and reports what is still unset.

## Files

Common (both hosts): `scripts/lib/wp_site.py`, `scripts/lib/site_ssh.py` (SSH, SFTP and rsync with the password on a private pipe through `sshpass -d`, refused when the vault item drifts from the pin), `bin/wp-remote` (WP-CLI on the site), `scripts/site-access.py` (`ssh`, `sftp`, `check`), the `wordpress-site-safety` and new `wordpress-connect` skills for all three agents, the PHPCS toolchain, and tests.

Pressable only: `scripts/mcp-headers.py`, `scripts/lib/mcp_http.py`, `scripts/check-mcp.py`, `scripts/sftp-item.py`, `scripts/create-application-password.py`, `bin/ddev`, `bin/wp`, `.ddev/providers/production.yaml` (push refused) and `mcp.wordpress.example.json`.

The DDEV pull itself (`scripts/production-sync.py`) stays per site, because which tables and uploads hold personal data differs per site. The skill ports it from `jmrgroup-coza`, and the doctor reports it as `setup_required` until it exists.

## Installer and doctor

`install.sh` and `forge.py kit` take `--host pressable|wpcom` (default `pressable`) and copy `templates/` plus `hosts/<host>/templates/`. A local WordPress tree is no longer required, because on Pressable the setup creates it with DDEV and on WordPress.com there is none. The doctor reads the pin's host: both check the pin, skills, helpers and `sshpass`; Pressable also checks the WordPress root, `ddev`, the provider and `production-sync.py`; WordPress.com reports a `.ddev` directory as `unexpected`.

## Safety

Every write to the live site or the provider (`reset_ftp_password`, `toggle_site_wordpress_mcp`, an Application Password) needs the owner's approval. No helper prints a secret; credentials move only on stdin or a pipe. Novamira is never installed.

## Reversal cost

Low: the kit is additive, and a site that already has its own ported helpers keeps them, because the installer never overwrites.
