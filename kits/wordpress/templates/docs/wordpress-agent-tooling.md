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

## Why can an Elementor page lose its styles?

Elementor deletes its generated stylesheets when it clears its cache, including after an ordinary plugin activation, deactivation or update, and rewrites them when PHP next renders the page. The Pressable and WordPress.com page cache does not listen for that and goes on serving HTML that names the deleted files, so visitors get unstyled pages while a logged-in editor sees nothing wrong. `tools/elementor-cache-purge/conclave-elementor-cache-purge.php` is a must-use plugin that requests the host's own purge (`edge_cache_purge_domain`) when Elementor clears its styles. It is a workaround: no Elementor setting stops the deletion. Limits: a visitor in the moments before the purge runs can still get an old page, the host skips the purge during an import or an autosave, and permanently deleting a component still in use or a stylesheet that becomes empty is not covered.

```bash
python3 scripts/elementor-cache.py check            # as a visitor: exit 1 when a page names a missing stylesheet
python3 scripts/elementor-cache.py status           # Elementor, the host's purge hook and the plugin
python3 scripts/elementor-cache.py install --yes    # owner-approved: back up, write, read back, purge
```

`check --url https://example.com` needs no pin or credential. It exits 2, not 0, when it finds no Elementor stylesheet at all (combined or inlined CSS), because that proves nothing.

## How do I open the dashboard?

`scripts/open-dashboard.py` launches your browser on a one-use ticket link (`?conclave_ticket=<token>`) for the pinned site's WordPress admin as the pinned user through a one-use ticket. It generates a 64-character hex token locally, stores only the token's SHA-256 hash, the pinned WordPress user ID, and a 60-second expiry in the `conclave_login_ticket` option over the pinned SSH connection, and hands the link to the browser through a private local redirect page so the opener never prints or logs the token locally or puts it in process arguments. Because the browser redeems the ticket over HTTPS via `?conclave_ticket=<token>`, web-server or proxy access logs may record that query string; security rests on the token being consumed on the first request that reaches WordPress (right or wrong; a request that stops at a proxy before reaching WordPress leaves the ticket live until WordPress handles a request or the 60-second expiry passes) rather than access-log secrecy.

Dashboard login adds no standing login key anywhere: there is no extra password, shared secret, or API key beyond the existing pinned SSH identity. The one-use link expires after 60 seconds and is consumed on first redemption, while an established WordPress browser session follows normal WordPress session rules. Removing the plugin prevents future ticket logins but does not sign out an already-open WordPress session.

This feature requires SSH and a pinned WordPress user (`ticket-login` and `ticket-login-user` doctor rows `ok`; WordPress.com Simple and connector-only Atomic sites without a pinned user skip it), runs from WSL or Linux (native Windows is refused), and refuses WordPress multisite installs or relocated MU-plugin directories. Installing or removing the MU-plugin is an owner-approved write on the live site.

From WSL or Linux:

```bash
python3 scripts/ticket-login.py status          # read-only check: plugin is absent, current, or differs
python3 scripts/ticket-login.py install --yes   # owner-approved: install or replace the MU-plugin
python3 scripts/open-dashboard.py --check       # prove ticket store and removal; opens no browser
python3 scripts/open-dashboard.py               # open the dashboard directly from WSL or Linux
```

On Windows, after setting `title` and `icon` in `.conclave/launchers.json`, create the desktop shortcut from Windows PowerShell 7 (see `docs/launchers.md` for WSL checkout invocation with `\\wsl.localhost` or `-Distro` and `-Project`):

```powershell
pwsh scripts/project-shortcuts.ps1
```

To uninstall the MU-plugin and remove any pending ticket option (owner-approved write; verifies `plugin: absent` and `option: absent`), run from WSL or Linux:

```bash
python3 scripts/ticket-login.py remove --yes
```

## Tests

```bash
python3 -m unittest discover -s scripts/tests
```
