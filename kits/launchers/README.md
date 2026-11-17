# Launchers kit

Gives any project the same family of Windows desktop links: `<Title> (<Agent>)` opens the project in a coding agent, and any further link the project declares runs a command in the project or opens its site. Every icon is the project's own icon with a mark in its corner, rendered on the machine. A Laravel, static or other web project gets the same shape as a WordPress one.

## What it needs and how to install it

It needs no other kit, and the `unattended` kit brings it with it, since that kit's campaign shortcuts draw their icons with this kit's renderer. The links are Windows shortcuts, so they are written on Windows; a project that lives in WSL is opened through `wsl.exe`, and a project on a Windows drive through PowerShell. Install it with `python forge.py kit <project> launchers`, set the project's title and icon in `.conclave/launchers.json`, and check it with `python forge.py doctor <project> launchers`. The SDK does not install this kit in itself (`SELF_KITS` in `forge.py`).

## What it installs

| File | What it is |
| ---- | ---------- |
| `.conclave/launchers.json` | The profile: the title, the icon, the agents that get a link, and further links |
| `scripts/campaign-icon.py` | The icon renderer: a runner's round badge or a link's rounded-square overlay (stdlib) |
| `scripts/lib/launchers.py` | `load_profile` and `show`: the profile, every key checked (stdlib only) |
| `scripts/tests/test_campaign_icon.py` | The renderer's tests: PNG and ICO, the badge, each overlay mark, refusals |
| `scripts/tests/test_launchers.py` | The loader's tests (one per refusal, and `show`), and no window opened |

## Icons

`python scripts/campaign-icon.py overlay <base.png or .ico> <mark> <target.ico>` draws an everyday link's icon: the project's icon with a rounded square in the bottom right, in the mark's colour on a white outline, and the mark in white from 32 pixels up. The marks are `claude`, `codex` and `agy` (the runners' colours and logos), `wordpress` (the WordPress logo, `#21759B`) and `site` (a globe, `#2563EB`). `badge` draws a campaign link's round runner badge. An unknown mark or a target that is not `.ico` exits 2 with the usage text, a base that is neither PNG nor ICO exits 1, and neither writes anything.

## Doctor

`python forge.py doctor <project> launchers` reports:

- `renderer`: `ok` when `scripts/campaign-icon.py` is there, `setup_required` with the install command when it is not.
- `profile`: `ok` with the title when `.conclave/launchers.json` loads through the kit's `scripts/lib/launchers.py`; `setup_required` with the loader's refusal (a fresh install's unset `title` among them), or with the install command when there is no file.

## The profile

`schema_version` (1), `title` (the name the links carry: 1 to 60 characters a Windows file name can hold, not starting or ending with a space or ending with a dot), `icon` (a `.png` or `.ico` file in the project, relative to it and not reached through a link), `agents` (one or more of `claude`, `codex`, `agy`, each once), `skip_permissions` (true or false) and `links` (each `label`, `mark` of `wordpress` or `site`, and one of `run`, a one-line command, or `url`, an `https://` address or `http://` on `localhost` or a `.test` or `.site` name). A label is 1 to 30 characters under the title's rule, unique without regard to case and by the icon file it names, and never an agent's link or a word ending `campaign`. `python scripts/lib/launchers.py show` prints the checked profile as one line of JSON, or the refusal with exit 1.
