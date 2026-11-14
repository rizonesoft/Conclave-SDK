---
name: wordpress-connect
description: "Connect a WordPress project to its one live site on Pressable or WordPress.com: site pin, SSH/SFTP through a Conclave credential, the WordPress MCP and, on Pressable (or a WordPress.com Atomic site that asks for one), a pull-only DDEV mirror. Use when setting up or repairing a WordPress project's site access, or when the WordPress kit was just installed."
---

# Connect a WordPress project to its site

The reference is rizonetech-com (`/home/derickpayne/www/rizonetech-com`, Pressable; `docs/production-access.md`). jmrgroup-coza (`docs/connections.md`) is the closest production-only port. Follow `wordpress-site-safety` throughout: every write to the live site or the host (a password reset, enabling the MCP, an Application Password) needs the owner's approval first, and no secret is ever printed, put in an argument or written to the repository.

## 1. Bind the site and fill the pin

`.conclave/wordpress-site.json` names the site; `host` was set by the kit installer (`--host pressable|wpcom`). Fill `site_id`, `url` (the canonical `https://` address, no trailing slash) and `environment` from the host, never from memory:

- **Pressable:** the Pressable MCP `get_site_details` (through `execute_tool`): `id`, `https_url`, `account_id` (into `pressable.account_id`, which the setup helpers require), `staging`, PHP version and data centre.
- **WordPress.com:** the WordPress.com connector `wpcom-user-sites` (search the domain): the blog ID and `platform`. Only `atomic` has SSH/SFTP; a `simple` site's only channel is the connector, so set `ssh.ssh_host` and `ssh.port` to null (the doctor then skips SSH) and skip step 2. Cross-check with `automattic-agencies` `get-site-details` when the site is agency-managed.

Run `python3 forge.py doctor <repo> wordpress` after each step; it lists what is still unset.

## 2. SSH/SFTP

Look for an existing Conclave item first (`conclave-op item list --vault Conclave`, titles only). Reuse a working one instead of resetting.

- **Pressable:** with the owner's approval, `python3 scripts/sftp-item.py --title "<Site> Production SSH SFTP"` resets the owner FTP account's password through the Pressable MCP and pipes it straight into a new vault item. It needs the Pressable MCP connection from step 3 pinned first. Put the printed `item_id` and `username` into `ssh.item` and `ssh.username`.
- **WordPress.com (Atomic):** the connector cannot create SFTP credentials, so this is the owner's step: Hosting Dashboard, the site, Settings, SFTP/SSH, Create credentials, then Enable SSH access. Ask the owner to create a Conclave Login item (never paste the password in chat) with fields labelled `username`, `password`, `hostname` (the SFTP URL shown there), `ssh_hostname` (`ssh.wp.com`), `port`, `site_id`, `site_url` and `environment`, matching the pin exactly. Both hosts are checked, so an edited pin can never send the password elsewhere. Copy the SFTP URL and username into `ssh.sftp_host` and `ssh.username`, and the item's id into `ssh.item`.

Then add the SSH host key once (`ssh-keyscan -t ed25519 <ssh_host> >> ~/.ssh/known_hosts`) and record its SHA-256 fingerprint in `docs/connections.md`. On WordPress.com, log in once with `python3 scripts/site-access.py ssh 'pwd; ls'` to find the WordPress root and set `ssh.wp_path`. Prove it with `python3 scripts/site-access.py check` (SSH reads `home` and it must equal the pinned URL; SFTP lists its home).

## 3. WordPress MCP

- **Pressable:** pin two `mcp` entries and merge `mcp.wordpress.example.json` into `.mcp.json` with the same names:
  1. `<site>-pressable`, `scheme: bearer`, `url: https://mcp.pressable.com`, `item`: the account's shared Pressable MCP token item (reuse it; never create a second).
  2. `<site>-wordpress`, `scheme: basic`, `url: <url>/wp-json/mcp/mcp-adapter-default-server`, `username` and `wordpress_user_id` from `bin/wp-remote user list --role=administrator`.

  With approval, enable the adapter with Pressable `toggle_site_wordpress_mcp` (Pressable installs and updates `mcp-adapter`). If Elementor 4.3+ is active and `bin/wp-remote option get elementor_mcp_enabled` is missing or false, Elementor removes the adapter's default server: set the option to `1` after a backup (rizonetech-com, "The Elementor 4.3 trap"). With approval, run `python3 scripts/create-application-password.py <site>-wordpress --title "<Site> Production WordPress MCP"` and put the printed UUID into `application_password_uuid` and the item id into `item`. Prove both with `python3 scripts/check-mcp.py`.
- **WordPress.com:** the WordPress.com connector (user scope) is the WordPress MCP. Confirm `wpcom-user-sites` reports `mcp_access: available` for the site. Add nothing to `.mcp.json` and never install `mcp-adapter`, unless the owner asks for the site's own MCP servers (the MCP Adapter or Elementor MCP) beside the connector: then pin each as a `basic` entry whose url is on the pinned site under `/wp-json/`, with its Application Password in a new vault item, and port `mcp-headers.py`, `check-mcp.py`, `create-application-password.py` and `lib/mcp_http.py` from `hosts/pressable/templates/scripts/` as road-diamond-com did. `wp_site.py` refuses any other url and every `bearer` entry on a WordPress.com pin.

If the site still has Novamira, ask before removing it and follow jmrgroup-coza's "Novamira removal" recipe; never install it.

## 4. Local DDEV (Pressable; WordPress.com Atomic on request)

WordPress.com sites get no DDEV unless the owner asks for the mirror on an Atomic site (SSH; a Simple site never has one): then copy `.ddev/providers/production.yaml`, `bin/ddev` and `bin/wp` from `hosts/pressable/templates/` as road-diamond-com did. Match production's PHP and database versions (`bin/wp-remote cli info`, `bin/wp-remote db query 'SELECT VERSION()'`):

```bash
bin/ddev config --project-type=wordpress --docroot=public --php-version=<x.y> --database=mariadb:<x.y> --router-http-port=8088 --router-https-port=8448
```

`.ddev/providers/production.yaml` refuses every push. Port `scripts/production-sync.py` from jmrgroup-coza: keep its read-only command allowlist and pinned rsync, and rewrite its list of private post types, tables and upload folders for this site, so personal data stays on the server. Back up the local database (`bin/ddev snapshot`) before the first `bin/ddev pull production -y`.

## 5. Record it

Write `docs/connections.md` the way jmrgroup-coza does: how the environments work, the verified site identity (with the date), the Conclave items by immutable id and what each is for, the MCP clients, the commands, and open findings with evidence. Finish with `python3 forge.py doctor <repo> wordpress` showing no `missing` and no `setup_required` other than what the doc says is pending.
