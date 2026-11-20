# WordPress agent tooling

Every WordPress project Conclave starts or adopts gets this overlay. The reference site is the project `wordpress.reference` names in `.conclave/local.toml`; its `docs/production-access.md` records the whole setup, and the `docs/connections.md` of the project `wordpress.port_source` names in `.conclave/local.toml` is the closest production-only port. The `wordpress-connect` skill walks through the setup.

## Bind one site first

`.conclave/wordpress-site.json` is the one place that names the live site: its host (`pressable` or `wpcom`), id, URL, environment, SSH identity and its MCP connections (always on Pressable; on WordPress.com only the site's own `basic` servers, when the owner asks for them). Every helper reads it through `scripts/lib/wp_site.py`, and `null` means not set up yet. Fill it from the host (the Pressable MCP or the WordPress.com connector), never from memory. Local, staging, production and multisite scopes stay distinct. A write that does not name the site is refused.

| Host | SSH/SFTP | WordPress MCP | Local mirror |
| --- | --- | --- | --- |
| Pressable | `scripts/sftp-item.py` | `mcp-adapter` | DDEV, pull only |
| WordPress.com Atomic | Owner, in Hosting > Settings | Connector, own on request | DDEV if asked |
| WordPress.com Simple | None | WordPress.com connector | None |

## SSH, SFTP and WP-CLI

`scripts/lib/site_ssh.py` reads the Conclave item named by `ssh.item` and refuses it unless its `hostname`, `ssh_hostname`, `port`, `username`, `site_id`, `site_url` and `environment` match the pin. The password goes to `sshpass` on a private pipe, never in an argument or the environment. `sshpass` is the one operator global it needs.

```bash
python3 scripts/site-access.py check          # SSH reads home (must equal the pin's url); SFTP lists its home
bin/wp-remote option get home                 # WP-CLI on the live site, in ssh.wp_path
bin/wp-remote db export ~/backups/x.sql       # ~/ maps to the server's home
```

Locally, WP-CLI is user-scoped (`wp --info`) or DDEV's (`bin/wp`). Do not drop an unverified PHAR into the repository.

## MCP

On Pressable, `.mcp.json` names two servers (see `mcp.wordpress.example.json`): the site's `mcp-adapter` (enabled with Pressable `toggle_site_wordpress_mcp`, Basic auth with a dedicated Application Password) and the Pressable control plane (`https://mcp.pressable.com`, the account's bearer token, which the pin allows to go nowhere else). Both use `scripts/mcp-headers.py` as `headersHelper`; its stdout is the client's private pipe, so never run it in a terminal. `python3 scripts/check-mcp.py` proves identity, reads and 401 refusals.

A WordPress.com site uses the WordPress.com connector instead and gets no `mcp-adapter` unless the owner asks for the site's own servers (the MCP Adapter or Elementor MCP) beside it: then each is a `basic` pin entry on the pinned site under `/wp-json/` and an `.mcp.json` server with the same `headersHelper`, as road-diamond-com did (`wordpress-connect` step 3). It never carries the Pressable bearer token. Novamira is discontinued: never install it, and ask before removing it from a site that still has it.

## DDEV (Pressable; WordPress.com Atomic on request)

`.ddev/providers/production.yaml` pulls through `scripts/production-sync.py` and refuses every push. That script is ported per site from the port source, because which tables and uploads hold personal data differs per site. `bin/ddev` and `bin/wp` run DDEV with fresh Docker group membership.

## PHPCS

`phpcs.xml.dist` is WordPress-Extra. The toolchain lives in `tools/phpcs/` so the site's own `composer.json` is not polluted. After `composer install` in that directory:

```bash
tools/phpcs/vendor/bin/phpcs
```

`scripts/hooks/wordpress-phpcs-pre-push.sh` is the pre-push snippet. Run it from the project's hook as its own command (`bash scripts/hooks/wordpress-phpcs-pre-push.sh || exit 1`), never sourced, since it exits. A missing binary is SKIPPED, not a silent pass.

## Tests

```bash
python3 -m unittest discover -s scripts/tests
```
