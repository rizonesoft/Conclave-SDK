---
schema_version: 1
id: wordpress-dashboard-login
domain: 07-launchers
status: active
title: "TODO-02 -- WordPress dashboard login by one-use ticket"
---

# TODO-02 -- WordPress dashboard login by one-use ticket

> **Goal:** A project on the WordPress kit can open its site's dashboard, already logged in, from one command and from a desktop link, with no standing key anywhere: not in the repository, not in the vault, not on the site. The kit carries the plugin that redeems the ticket, the script that makes it, and the commands that put the plugin on the site, check it and take it off again.

> **Current state:** Measured 2026-11-17. The WordPress kit (`kits/wordpress/`) has the site pin, pinned SSH and SFTP (`scripts/lib/site_ssh.py`, `scripts/lib/wp_site.py`, `scripts/site-access.py`) and nothing that logs a person in. One project built the login as its own files on 2026-11-16, in no kit: the project `[wordpress] port_source` names in `.conclave/local.toml`, with `scripts/open-dashboard.py`, a must-use plugin under its WordPress tree's `wp-content/mu-plugins/`, `scripts/tests/test_open_dashboard.py` and the record in its `docs/connections.md`. Its option name, query variable and plugin name carry that site's initials, the plugin was put on the site by a hand-typed SFTP command, nothing removes it, and the script opens a browser only from WSL. It was proven on that project's staging site on 2026-11-16: the right token returned 302 to `/wp-admin/` with the login cookies once; a wrong token, the same token again, an expired ticket and a malformed one each returned 403; a wrong token also consumes the ticket.

> **Owner decision 2026-11-16, carried here 2026-11-17:** the owner chose the one-use ticket over the host's own one-click login and over a plugin holding a secret key, and asked on 2026-11-17 for the plugin to be imported into the SDK. It is a commitment of the governing plan (`docs/plans/2026-11-11-sdk-audit-and-roadmap.md`, "Project launchers"). A run never swaps the design for a standing key or an Application Password login without the owner.

## Inputs

- `docs/plans/2026-11-11-sdk-audit-and-roadmap.md`, "Project launchers (owner decision 2026-11-17)".
- `kits/wordpress/templates/scripts/lib/wp_site.py` (`load`, `require`, `URL`) and `scripts/lib/site_ssh.py` (`run`): every remote call here goes through them, so the site identity checks and the vault read are theirs.
- `kits/wordpress/README.md` and `kits/wordpress/templates/.claude/skills/wordpress-site-safety/SKILL.md`: every write to the live site needs the owner's approval, which is why §3's `install` and `remove` are commands a person or an approved step runs and never a side effect of opening the dashboard.
- The design as built, copied on 2026-11-17 so the sections can be built when the source project cannot be read:
  - The script makes a token of 64 lower-case hex characters (`secrets.token_hex(32)`) and its SHA-256 hash. Only the hash goes to the site.
  - It stores one option on the site through WP-CLI over the pinned SSH connection (`cd <ssh.wp_path> && wp eval <php>`), an array of `hash`, `expires` (now plus 60 seconds) and `user` (a WordPress user ID), not autoloaded. The hash arrives on the remote command's stdin and is checked there against `/^[0-9a-f]{64}$/`; the user ID and expiry are digits the script checked. The PHP echoes `stored` after reading the option back, and the script refuses anything else.
  - It opens `<site url>/?<query>=<token>`. The link reaches the browser on a child process's stdin, never in an argument, and neither the token nor the link is ever printed or logged. When the browser cannot be started the ticket is removed again.
  - The plugin hooks `init` at priority 1. When the query variable is present it sends no-cache headers, reads the option, deletes it before judging anything (so a ticket works once, and a wrong token consumes it), and accepts only when the option is an array with all three keys, the token matches `/^[0-9a-f]{64}$/`, `hash_equals` matches the stored hash to the token's SHA-256, and the expiry has not passed. The user must exist and hold `manage_options`. On success: `wp_set_current_user`, `wp_set_auth_cookie( $id, false )`, the `wp_login` action, `wp_safe_redirect( admin_url() )`, exit. On any failure: `wp_die` with status 403 and one fixed sentence.
  - The 60 seconds limit only how long the link can be redeemed. The session it starts lasts as long as any WordPress login.
  - The user is the one WordPress user the pin names: the `wordpress_user_id` shared by every `basic` entry under `mcp` in `.conclave/wordpress-site.json`. None, or two different ones, is a refusal.
  - `--check` stores a ticket, proves the site holds it, removes it and opens nothing.
- -> XREF: T01 §6 -- the launchers kit writes the desktop link from the `links` entry this file's §5 adds to its profile

## Outcome

- `python scripts/open-dashboard.py` in a connected project opens the pinned site's dashboard logged in as the pinned user, and `--check` proves the round trip without opening anything.
- `python scripts/ticket-login.py install`, `status` and `remove` put the plugin on the pinned site, compare it with the kit's copy and take it and its option off again.
- A project with the launchers kit has a `<Title> (WordPress)` link on the desktop that runs the opener.
- No file in the kit, the project or the vault can mint a login: without SSH access to the site there is no ticket to redeem.

**Adjacency:** list=not-applicable (one ticket exists at a time, for at most 60 seconds); document=not-applicable (nothing is sent, printed or filed); settings=not-applicable (the lifetime and the names are constants a test holds equal on both sides); reporting=not-applicable (no data to summarise); notifications=not-applicable (WordPress's own `wp_login` action fires, and nothing else is announced); permissions=applicable @ D07 T02 §1; audit=applicable @ D07 T02 §1; exchange=not-applicable (nothing is imported or exported); reverse=applicable @ D07 T02 §3

**Adjacency rationale:** Permissions is the refusal set of §1: a user without `manage_options`, a wrong, used, expired or malformed token, each a 403. Audit is WordPress's own `wp_login` action, which §1 fires so that any activity log the site runs records the login like any other. Reverse is `ticket-login.py remove` in §3, which deletes the plugin and the option; a stored ticket is reversed by the opener itself when the browser does not start.

## Implementation Order

| Order | Section | Deliverable | Depends On | Status |
| ----- | ------- | ----------- | ---------- | ------ |
| 1 | §1 | Ticket login plugin in the WordPress kit | -- | [x] |
| 2 | §2 | Dashboard opener `scripts/open-dashboard.py` | §1 | [ ] |
| 3 | §3 | Plugin install, status and removal on the pinned site | §1 | [ ] |
| 4 | §4 | Doctor rows and host refusals for the ticket login | §2, §3 | [ ] |
| 5 | §5 | WordPress link in the launcher profile | §2, T01 §6 | [ ] |
| 6 | §6 | `wordpress-connect` step and tooling page | §4, §5 | [ ] |
| 7 | §7 | Live proof on a staging site | §6 | [ ] |

## 1. Ticket login plugin in the WordPress kit

The plugin is the half of the design that runs on the site. It is one small file with no settings and no key, and it must pass the kit's own PHPCS ruleset. It ships in the kit under a neutral name, in a folder outside any WordPress tree, because a project on this kit may have no local tree at all.

> **Started:** 2026-11-17T12:36Z

**Corrected 2026-11-17:** the kit's `phpcs.xml.dist` lints the whole project (`<file>.</file>`), so the harness of WordPress stand-ins this section adds under `scripts/tests/` would fail every project's pre-push PHPCS run; the ruleset now excludes `*/scripts/tests/*`, the kit's own test tooling, which is not site code. Reversing it costs one line, and the harness then needs WordPress-Extra's docblocks and prefixes.

**Phase:** 8
**Needs:** none
**Surface:** no

**Build order:**

1. Write the plugin from the design in Inputs. Done when: PHPCS reports nothing on it.
2. Hold its order of operations with tests that read the file. Done when: the checkpoint passes.

- [x] Add `kits/wordpress/templates/tools/ticket-login/conclave-ticket-login.php` implementing the plugin of Inputs, with the constants `CONCLAVE_TICKET_OPTION = 'conclave_login_ticket'` and `CONCLAVE_TICKET_QUERY = 'conclave_ticket'`, the plugin name `Conclave ticket login`, a `Version` header, and a header comment explaining how it works and that it holds no key. Done when: the file names no site, owner or client. Cheaper substitute: a plugin that checks a shared secret from `wp-config.php`, which is the standing key the owner ruled out.
- [x] Guard the file with `defined( 'ABSPATH' ) || exit;` and wrap each constant in a `defined` check, so a site that already loads a copy does not fatal. Done when: `php -l` passes and a test finds both guards.
- [x] Mark the two reads of `$_GET` with the PHPCS ignore `WordPress.Security.NonceVerification.Recommended` and its reason (the one-use ticket is the proof; a nonce needs a session this request does not have yet). Done when: `tools/phpcs/vendor/bin/phpcs --standard=phpcs.xml.dist` reports no error or warning on the file in a project with the toolchain installed.
- [x] Add `kits/wordpress/templates/scripts/tests/test_ticket_login.py` with tests that read the plugin's text: `delete_option(` comes before `hash_equals(`; `hash_equals` is used and `==` on the hash is not; `manage_options` is required; the failure path is `wp_die` with `403`; the redirect is `wp_safe_redirect( admin_url() )`; `wp_set_auth_cookie` is called with `false` as its second argument. Done when: each passes, and each fails on a copy of the text with that one property changed.
- [x] Consume the ticket exclusively: the plugin goes on only when `delete_option( CONCLAVE_TICKET_OPTION )` returns `true`, so of two requests that read the same ticket only the one whose delete removed the row logs in, and a delete that fails refuses. Done when: the harness below runs a request whose delete returns `false` with a valid ticket and finds a 403, no auth cookie and no `wp_login`. **Planned 2026-11-17** (plan review P1: concurrent redemption). **Corrected 2026-11-17** (round 1 P1): `delete_option` deletes by name only, so a request that read ticket A could still delete a newer ticket B stored in between and log in with A; the plugin reads the row from the table and deletes it by name and exact value through `$wpdb` (the Options API has no compare-and-delete, marked `WORKAROUND:`), drops the cache entry, and goes on only when one row was removed. The harness test runs that interleaving and finds the 403 with B left in place.
- [x] Check every type before it is used: the query value must be a string (an array such as `?conclave_ticket[]=x` is a 403, never a PHP error), and the stored option an array whose `hash` is a string, `expires` an integer and `user` a positive integer. Done when: harness tests for an array query value and for each malformed option field end in the fixed 403. **Planned 2026-11-17** (plan review P2).
- [x] Make the bootstrap idempotent: every function and the `add_action` sit behind one `defined( 'CONCLAVE_TICKET_LOADED' )` guard, so a second copy loaded on the same site declares nothing and registers no second handler. Done when: a harness test loads two copies of the file, finds no fatal and exactly one `init` callback. **Planned 2026-11-17** (plan review P2).
- [x] Add `kits/wordpress/templates/scripts/tests/ticket_login_harness.php`, a stand-in for the WordPress functions the plugin calls (`add_action`, `get_option`, `delete_option`, `get_userdata`, `user_can`, `wp_set_current_user`, `wp_set_auth_cookie`, `do_action`, `admin_url`, `wp_safe_redirect`, `wp_die`, `nocache_headers`), recording each call and driven by a JSON case on stdin, and run it from `test_ticket_login.py` with the PHP CLI (the tests skip, naming PHP, where it is missing). Done when: harness tests prove the handler is registered on `init` at priority 1; a request without the query variable leaves the ticket untouched; a valid ticket sends no-cache headers, sets the user, calls `wp_set_auth_cookie( <id>, false )`, fires `wp_login` with the user's login and object and redirects to `admin_url()`; and an expired, missing, wrong (consumed too), malformed or array token, a user that does not exist and one without `manage_options` each end in the 403 with no auth cookie and no `wp_login`. **Planned 2026-11-17** (plan review P1: behaviour, not text).
- [x] List the plugin in the file tables of `kits/wordpress/README.md` (every host) with its role in under 88 characters. Done when: the Markdown format check passes.
- [x] Commit: `wordpress: the one-use ticket login plugin`

**Test checkpoint:** `python -m unittest discover -s kits/wordpress/templates/scripts/tests -p "test_ticket_login.py"` ends `OK` with the harness tests run (PHP present); moving `delete_option` below `hash_equals`, or ignoring its return value, in the plugin makes it fail. **Corrected 2026-11-17** (completion review P3): since round 1 the ticket is consumed by a `DELETE` of its row by name and exact value (`$wpdb`), not `delete_option`, so where this checkpoint and the items above say `delete_option` and its return value they read that `DELETE FROM` and its count of removed rows (`1 !== $removed`); the checkpoint's mutations are moving the `DELETE FROM` below `hash_equals`, deleting by name only, or ignoring the count, each of which makes it fail.

> **Verified:** 2026-11-17 | §1 | ee283634d61c432e1effb3480d8147c599cac40b
> **Review:** `docs/reviews/d07-t02-s1.json`

## 2. Dashboard opener `scripts/open-dashboard.py`

> **Started:** 2026-11-20T09:14Z

The opener is the half that runs on the operator's machine. The first build opens a browser only from WSL through Windows PowerShell; the kit's scripts run on Windows and on Linux too. **Corrected 2026-11-20 (validation):** the pinned SSH it stores the ticket through (`scripts/lib/site_ssh.py`) hands the password to `sshpass` on a pipe with `pass_fds`, which native Windows has not, and the kit's README asks for `apt install sshpass`: the opener runs in WSL or on Linux, and on native Windows it refuses before it makes a ticket. On Linux `xdg-open` takes the link only as an argument, which `/proc/<pid>/cmdline` shows to every user of the machine, so the link goes into a redirect page in a private folder and `xdg-open` gets the page's path. Default, cheap to reverse: making `site_ssh` work on native Windows would bring back `os.startfile`.

**Corrected 2026-11-20 (plan review, `docs/reviews/07-launchers/D07-T02-s2.md`):** the checklist below replaces the one the plan review read and closes its nine gaps: the store and removal PHP run under WordPress stand-ins instead of a text search (gap 1); both command-line paths run end to end (gap 2); removal deletes only the ticket this run stored, by its exact row as §1's redemption does (gap 3); each launch on Linux gets its own redirect page (gap 4); failures print fixed messages only (gap 5); every `basic` entry must name the same user, and a pin with no SSH or no `ssh.wp_path` is refused before any remote call (gap 6); the store refuses a site where §1's plugin is not loaded (gap 7); the browser dispatch and the redirect target are checked, not only where the link travels (gap 8); and every remote call goes through `site_ssh.wp` (gap 9). The expiry is the site's clock plus `LIFETIME`, computed in the store PHP, since §1 judges it by the site's `time()`.

**Phase:** 8
**Needs:** none
**Surface:** no

**Build order:**

1. Write the opener and its two PHP programs from the design in Inputs, with the kit's names. Done when: the tests that need no PHP pass.
2. Run the PHP under the stand-ins and open the browser on each system the kit runs on. Done when: the checkpoint passes.

- [x] Add `kits/wordpress/templates/scripts/open-dashboard.py`, standard library only, with `ticket()`, `link(site_url, token)`, `pinned_user(pin)`, `store(pin, digest, user_id)`, `drop(pin, digest)`, `open_browser(url)` and `main(argv)`, using `QUERY = "conclave_ticket"`, `OPTION = "conclave_login_ticket"` and `LIFETIME = 60`, every remote call through `site_ssh.wp(["--url=<pinned url>", "eval", <php>], input=<digest line>, pin=pin)`. Done when: `python scripts/open-dashboard.py --help` prints its usage in a scratch project. Cheaper substitute: passing the hash or the link as a command-line argument, where a process list shows it. **Corrected 2026-11-20 (round 1, `docs/reviews/07-launchers/D07-T02-s2.md`):** every call names the pinned site with `--url`: on a multisite all sites share `ssh.wp_path`, and WP-CLI acts on the main site unless told which. **Corrected 2026-11-21:** `--url=<pinned url>` goes before `eval` (`9d6cc5f4`), because Pressable's `wp` refuses a global flag after `eval <code>`.
- [x] Make `ticket()` return a token of 64 lower-case hex characters (`secrets.token_hex(32)`) and its SHA-256 hex digest. Done when: a test finds the digest equal to `hashlib.sha256(token.encode()).hexdigest()` and two calls give different tokens.
- [x] Refuse in `link` a site URL that does not match `wp_site.URL` and a token that is not 64 lower-case hex characters, with `ValueError("refused to build a login link")`, and build `<site url>/?conclave_ticket=<token>`. Done when: tests refuse a short token, an upper-case one, a non-hex one, an `http://` site, a site with a query string and a site ending in a newline, and accept a site under a subpath (`https://example.com/blog`).
- [x] Refuse in `pinned_user` a pin whose `basic` entries name no `wordpress_user_id`, where one `basic` entry names none, or where two name different IDs; a `bearer` entry is ignored. Done when: tests cover one user named twice (accepted), none, one entry unset beside one set, two different IDs, and a `bearer` entry beside one `basic` entry (accepted).
- [x] Refuse in `main`, before a ticket is made, a pin with no SSH (`wp_site.ssh_enabled` false), one with no `url` or no `ssh.wp_path`, and native Windows (`os.name == "nt"`: the pinned SSH needs WSL or Linux), each with exit 2 and a fixed message naming what is missing; a pin the validator refuses is told in a fixed sentence pointing at `site-access.py check`, never in the validator's text. **Corrected 2026-11-20 (round 1, `docs/reviews/07-launchers/D07-T02-s2.md`):** the validator's text, which can carry an unknown key's name, reached stderr. Done when: a test of each case finds exit 2, its message, and no call to `ticket`, `site_ssh.wp` or `open_browser`.
- [x] Write `STORE`, the PHP `store` runs: it answers `no plugin` when `CONCLAVE_TICKET_LOADED` is not defined (§1's plugin is not active), reads the digest from `STDIN` and refuses one not matching `/^[0-9a-f]{64}$/`, stores `array( 'hash' => <digest>, 'expires' => time() + LIFETIME, 'user' => <user id> )` with integer `expires` and `user` through `update_option( OPTION, ..., false )`, reads it back and echoes `stored` only when the read-back matches. `store` returns only on SSH exit 0 and output exactly `stored`, and raises a fixed refusal otherwise (`no plugin` names `python scripts/ticket-login.py install`). Done when: tests run `STORE` under PHP against `ticket_login_harness.php` and find the option holding the digest, the integer user, an integer expiry `LIFETIME` seconds after the stand-in's clock and autoload off; a missing plugin, a bad digest and a failed read-back each refuse; and a recorder in place of `site_ssh.wp` finds only the digest on stdin and never the token.
- [x] Write `DROP`, the PHP `drop` runs: it reads the digest from `STDIN`, reads the option's row straight from the table, and deletes it by its exact value only when its `hash` is that digest (as §1's redemption deletes), echoing `dropped`, `absent`, `gone` or `not ours`, and `failed` when the read fails (`wpdb::get_var` answers `null` with `last_error` set); `drop` raises a fixed refusal on anything else. Done when: tests under the stand-ins find run A's drop leaving run B's newer ticket in place (`not ours`), its own ticket removed (`dropped`), a failed delete refused, a failed read refused, and `--check` confirming the removal. **Corrected 2026-11-20 (round 1, `docs/reviews/07-launchers/D07-T02-s2.md`):** a failed read answered `absent`, so a ticket could stay while `--check` passed.
- [x] Make `open_browser(url)` hand the link on stdin to `pwsh.exe`, or `powershell.exe` when there is no `pwsh.exe`, from WSL (`WSL_DISTRO_NAME` set) with the working directory `/mnt/c`, running `Start-Process` on the line it reads; and on Linux write a redirect page of its own per launch (`tempfile.mkstemp` in `~/.cache/conclave-dashboard/`, folder `0700`, file `0600`, the link HTML-escaped in a `meta refresh` and `location.replace`), remove the pages there older than `LIFETIME` seconds, and hand the page to the desktop entry that opens https links (`xdg-mime query default x-scheme-handler/https`, its `Exec` line from `$XDG_DATA_HOME` or `$XDG_DATA_DIRS`, its field codes given the page), started and not waited for; raise a fixed refusal naming what is missing (no PowerShell, no `/mnt/c`, no `xdg-mime`, no browser set for https links, its entry or its command missing, a cache folder it cannot write, a child that failed). Done when: tests with the platform faked and the child replaced by a recorder find the link on stdin and `Start-Process` in the command (WSL, both PowerShells), the page's redirect target parsed equal to the link with the folder `0700` and the file `0600` (Linux), two launches giving two pages each redirecting to its own link, a page younger than `LIFETIME` kept and an older one removed, each missing piece refused, and the link in no argument and no message. Cheaper substitute: `xdg-open <link>`, which puts the token in the process list. **Corrected 2026-11-20 (round 1, `docs/reviews/07-launchers/D07-T02-s2.md`):** `xdg-open` on an HTML file picks the `text/html` handler, which can be an editor showing the page's source; the page goes to the https browser instead.
- [x] Remove the ticket with `drop(pin, digest)` when `open_browser` raises, and when `store` fails after the write may have landed (its SSH reply lost); and on an interrupt (Ctrl+C, exit 130) after the store; when that removal cannot be confirmed, say the ticket expires within `LIFETIME` seconds. Done when: tests with a failing opener, a lost store reply and an interrupt find the `drop` call before the exit and the fixed message for each outcome. **Corrected 2026-11-20 (round 1, `docs/reviews/07-launchers/D07-T02-s2.md`):** `KeyboardInterrupt` escaped `except Exception` and left the ticket on the site.
- [x] Run both paths of `main` end to end with `site_ssh.wp` replaced by the stand-ins: the default stores a ticket and opens exactly `<pinned url>/?conclave_ticket=<the stored token>` (a pin under a subpath included), and `--check` stores, confirms, drops, confirms the removal and opens nothing. Done when: both tests pass and each prints its fixed success line.
- [x] Print only fixed messages: each refusal is a sentence written in the opener, any other exception prints `open-dashboard: <exception type>: unexpected failure` and nothing of its text, and nothing prints the token, the digest or the link. Done when: tests make each step raise an exception whose text holds the token, a link fragment and a child's output, also with the cleanup failing, and compare stdout and stderr with the exact expected lines.
- [x] Add to `scripts/tests/test_ticket_login.py` the agreement test: the plugin's two constants equal the opener's `OPTION` and `QUERY`. Done when: renaming either constant on one side makes it fail.
- [ ] Commit: `wordpress: the dashboard opener, from WSL and Linux, refused on native Windows`

**Test checkpoint:** `python kits/wordpress/templates/scripts/tests/test_open_dashboard.py` and `python -m unittest discover -s kits/wordpress/templates/scripts/tests -p "test_ticket_login.py"` end `OK`, run where PHP is on the path (WSL or CI's Linux runner) so the stand-in tests run and are not skipped; changing `QUERY` in the opener alone makes the second fail. **Corrected 2026-11-20 (plan review gap 2):** a discovery run of the opener's tests could report `Ran 0 tests` and `OK`, so the file is run directly.

## 3. Plugin install, status and removal on the pinned site

The first site got its plugin from a hand-typed SFTP command, and nothing takes it off. A login plugin that cannot be seen or removed from the project is not finished. These are writes to a live site: each runs only when a person or an approved step asks for it by name.

**Phase:** 8
**Needs:** none
**Surface:** no

**Build order:**

1. Add `status`, which only reads. Done when: it tells an absent plugin from a current one and a different one.
2. Add `install` and `remove` with their read-backs. Done when: the checkpoint passes.

- [ ] Add `kits/wordpress/templates/scripts/ticket-login.py` with the commands `status`, `install` and `remove`, standard library only, every remote call through `site_ssh.run` with the pin. Done when: `python scripts/ticket-login.py` with no command prints its usage and exits 2.
- [ ] Implement `status`: read the SHA-256 of `<ssh.wp_path>/wp-content/mu-plugins/conclave-ticket-login.php` on the site and compare it with the kit copy's, printing `absent`, `current` or `differs` and whether the option exists, never the option's value. Done when: tests with `site_ssh.run` replaced by a recorder cover the three states.
- [ ] Implement `install`: upload `tools/ticket-login/conclave-ticket-login.php` over the pinned SFTP to `wp-content/mu-plugins/`, creating that folder when it is missing, then run `status` and refuse anything but `current`. Done when: a test's recorder sees the upload followed by the digest read, and a mismatched digest exits 1. Cheaper substitute: an upload with no read-back, which reports success on a truncated file.
- [ ] Implement `remove`: delete the plugin file and the option, then read both back as gone. Done when: a test sees both deletions and both read-backs, and exits 1 when either is still present.
- [ ] Refuse `install` and `remove` unless `--yes` is given, printing the site URL and what will change. Done when: a test without `--yes` records no remote call.
- [ ] Refuse every command, before any connection, when the pin has no `ssh.wp_path` or its host has no SSH (a WordPress.com site that is not Atomic), with a message saying the ticket login needs SSH. Done when: a test with such a pin records no remote call.
- [ ] Commit: `wordpress: install, check and remove the ticket login plugin`

**Test checkpoint:** `python -m unittest discover -s kits/wordpress/templates/scripts/tests -p "test_ticket_login.py" -k plugin_on_site` ends `OK`; skipping the read-back in `install` makes it fail.

## 4. Doctor rows and host refusals for the ticket login

`forge.py doctor <project> wordpress` is where a person sees what a project lacks. The ticket login is optional, so its rows must never turn a project red for not wanting it.

**Phase:** 8
**Needs:** none
**Surface:** no

**Build order:**

1. Add the rows. Done when: each state below is printed by a test.

- [ ] Add a `ticket-login` row to `_doctor_wordpress` in `forge.py` (line 1603), read from files alone with no connection: `optional` when the pin has no SSH, `setup_required` naming the missing file when `scripts/open-dashboard.py` or the plugin copy is absent, `ok` otherwise with the words `run ticket-login.py status to check the site`. Done when: a test in `tests/test_forge.py` sees the three states. Cheaper substitute: a row that connects to the site, which would make the doctor slow and write to nothing but still need a credential.
- [ ] Add a `ticket-login-user` row: `ok` with the user ID when `open-dashboard.py`'s `pinned_user` rule holds on the pin, `setup_required` saying which case failed otherwise. Done when: a test sees one user, none and two.
- [ ] Add both scripts and the plugin to the kit's install list for both hosts, and prove `--host wpcom` installs them. Done when: a test installs each host into a scratch project and finds the three files recorded under `wordpress`.
- [ ] Commit: `wordpress: doctor rows for the ticket login`

**Test checkpoint:** `python -m unittest tests.test_forge -k ticket_login` ends `OK`; making the row `ok` for a pin with no SSH makes it fail.

## 5. WordPress link in the launcher profile

The desktop link is the launchers kit's to write (`T01 §6`). This section only declares it: installing the WordPress kit into a project that has a launcher profile adds one entry, as the Laravel kit adds its servers to the `lsp` table.

**Phase:** 8
**Needs:** none
**Surface:** no

**Build order:**

1. Add the entry at install. Done when: the profile holds it once, however often the kit is installed.

- [ ] Make `python forge.py kit <project> wordpress` add `{"label": "WordPress", "mark": "wordpress", "run": "python3 scripts/open-dashboard.py"}` to `links` in `.conclave/launchers.json` when that file exists and has no entry labelled `WordPress`, written atomically, and report it under a `launcher_links` key as `added` or `kept`. Done when: a test installs twice and finds one entry and the reports `added` then `kept`. Cheaper substitute: a second shortcut script in the WordPress kit, which is the per-project script this plan replaces.
- [ ] Leave a profile that does not load exactly as it was and report it under `merge_needed`. Done when: a test with a malformed profile finds its bytes unchanged.
- [ ] Make `python forge.py kit <project> launchers` add the same entry when the project already has `scripts/open-dashboard.py`, so the order of the two kits does not matter. Done when: a test installs the kits in both orders and reads the same profile back.
- [ ] Commit: `wordpress: the dashboard link in the launcher profile`

**Test checkpoint:** `python -m unittest tests.test_forge -k launcher_links` ends `OK`; adding the entry without the label check makes the install-twice test fail.

## 6. `wordpress-connect` step and tooling page

The setup runbook ends at "Record it" today. A project connected by it should be told that the dashboard login exists, that putting the plugin on the site is a write the owner approves, and how to take it off.

**Phase:** 8
**Needs:** none
**Surface:** no

**Build order:**

1. Add the step to the skill and generate its copies. Done when: the copies match.
2. Add the section to the tooling page. Done when: the checkpoint passes.

- [ ] Add a step "Dashboard login (optional)" to `kits/wordpress/templates/.claude/skills/wordpress-connect/SKILL.md` before "Record it": ask the owner once before `python scripts/ticket-login.py install --yes`, prove it with `python scripts/open-dashboard.py --check`, and add the desktop link through the launchers kit. Done when: the step names the three commands and the approval.
- [ ] Run `python forge.py skill-copies`. Done when: `python forge.py skill-copies --check` exits 0.
- [ ] Add "How do I open the dashboard?" to `kits/wordpress/templates/docs/wordpress-agent-tooling.md`: how the ticket works, what is stored where and for how long, that no key exists anywhere, the commands, how to remove it, and that it needs SSH. Done when: a test in `tests/test_forge.py` finds each of those topics on the page.
- [ ] Add one rule to `kits/wordpress/templates/.claude/skills/wordpress-site-safety/SKILL.md`: a ticket link is a credential while it lives and is never printed, pasted or logged, and generate its copies. Done when: the copies match.
- [ ] Commit: `wordpress: the dashboard login in the connect runbook and the tooling page`

**Test checkpoint:** `python -m unittest tests.test_forge -k dashboard_login_page` ends `OK`; removing the removal command from the page makes it fail.

## 7. Live proof on a staging site

No test without a network can show that a real WordPress accepts the right token once and refuses everything else. This is the one section a person starts: it installs a login plugin on a real site, which the owner approves per site.

**Phase:** 99
**Needs:** operator
**Surface:** no

**Build order:**

1. Install the kit's files into one connected project and put the plugin on its staging site. Done when: `status` prints `current`.
2. Run the five requests and record them. Done when: the checkpoint's evidence is in this section.

- [ ] Ask the owner which connected project's staging site takes the kit's plugin, and record the answer here as the site's environment and date, never its address. Done when: the answer is recorded and the Need can be removed.
- [ ] Install the kit's three files into that project with `python forge.py update <project> wordpress` and run `python scripts/ticket-login.py install --yes`. Done when: `python scripts/ticket-login.py status` prints `current`.
- [ ] Run `python scripts/open-dashboard.py --check`. Done when: it prints that a ticket was stored and removed again.
- [ ] Prove the five cases with a ticket stored by `store` and requests that send no cookies and follow no redirect: the right token returns 302 to `/wp-admin/` with the login cookies; a wrong token, the same token again, a ticket past its expiry and a malformed token each return 403. Done when: the five status codes are recorded here with the date, and no token.
- [ ] Remove the site's earlier project-own copy of the plugin and its option when the chosen project is the one that built the first version, so one login plugin is left. Done when: a listing of `wp-content/mu-plugins/` shows `conclave-ticket-login.php` alone.
- [ ] Commit: `wordpress: live proof of the ticket login on a staging site`

**Test checkpoint:** `python scripts/open-dashboard.py --check` in the chosen project prints `login ticket stored and removed again` and exits 0; with the plugin removed by `ticket-login.py remove --yes`, the right token returns 200 or 404 and never 302.

## Verification

- In a connected project, `python scripts/ticket-login.py status` prints `current` and `python scripts/open-dashboard.py --check` exits 0.
- `git grep -n -i "sot_\|ticket" kits/wordpress` shows only the neutral names `conclave_login_ticket` and `conclave_ticket`.
- `python forge.py check-all --only kit-wordpress` passes, and the CI run of the stamping commit is green.
- `python scripts/todo-graph.py validate` and `python scripts/todo-graph.py plan --check` pass.
