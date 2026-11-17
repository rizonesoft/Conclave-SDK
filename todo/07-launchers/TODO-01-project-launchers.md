---
schema_version: 1
id: project-launchers
domain: 07-launchers
status: active
title: "TODO-01 -- Project launchers: one desktop shape for every project"
---

# TODO-01 -- Project launchers: one desktop shape for every project

> **Goal:** Any project that installs the new `launchers` kit gets the same family of Windows desktop links from one script and one profile: `<Title> (<Agent>)` opens the project in a coding agent, `<Title> <Runner> campaign` starts its unattended run, and any further link the project declares runs a command in the project or opens its site. Every icon is the project's own icon with a mark in the bottom right corner, rendered on the machine. A Laravel, static or other web project has the same shape as a WordPress one, without the dashboard login.

> **Current state:** Measured 2026-11-17. Only the campaign link is in a kit: `kits/unattended/templates/scripts/unattended-shortcut.ps1` writes `<folder> <Runner> campaign.lnk` with a round runner badge drawn by `kits/unattended/templates/scripts/campaign-icon.py` (`badge`, `frames`). The two everyday links exist in one project only, as that project's own files, in no kit: a hand-written `scripts/desktop-shortcuts.ps1` with the distro, the Linux path, the title and the icon folder typed into it, and icons drawn by hand as SVG and committed as `.ico`. That project is the one `[wordpress] port_source` names in `.conclave/local.toml`; its `docs/connections.md` ("Site icon and desktop shortcuts") describes the three links. Three gaps follow from it. The campaign link is named after the folder while the everyday links carry the project's title, so one project shows two names on the desktop. `unattended-shortcut.ps1:123` resolves the icon with `.Path`, which keeps the `Microsoft.PowerShell.Core\FileSystem::` prefix for an icon on a `\\wsl.localhost` share, and Python cannot open that; the project fixed its own copy with `.ProviderPath` and the kit still has the fault. No kit can draw the rounded-square overlay the everyday icons use.

> **Owner decision 2026-11-17:** the owner asked for this shape in the SDK, for every web project and not only WordPress ones, with the WordPress dashboard login as the one WordPress-only part (`T02`). It is a commitment of the governing plan (`docs/plans/2026-11-11-sdk-audit-and-roadmap.md`, "Project launchers"). A run corrects a drifted claim in place and ships every section; it never retires the file, moves it to phase 99 or rewrites it out of scope without the owner.

## Inputs

- `docs/plans/2026-11-11-sdk-audit-and-roadmap.md`, "Project launchers (owner decision 2026-11-17)": the shape, the kit that owns it and the decisions below.
- `kits/unattended/templates/scripts/unattended-shortcut.ps1` and `scripts/tests/test_shortcut.py` beside it: the model for every link here. Links and icons are written under a temporary name and moved over the old; a link is found again by a mark in its description; the tests run against a stand-in for `wsl.exe`, windowless, in a scratch folder.
- `kits/unattended/templates/scripts/campaign-icon.py`: the standard-library renderer (PNG and ICO read and written, SVG path data rasterised with supersampling). §3 moves it and §4 extends it.
- `kits/unattended/templates/scripts/lib/unattended.py`: the command line each agent starts with, which §5 reuses for the permission flags.
- `forge.py`: `KIT_ORDER` (line 197), the installed-kit detection below it, `kit_plan`, `doctor_repo`, `SUITES`, and the way the Laravel kit brings the `lsp` kit with it (line 688), which is the model for §3.
- The facts of the everyday links as built, copied on 2026-11-17 so the sections can be built when the source project cannot be read:
  - Agent link, project in WSL: target `wt.exe`, arguments `wsl.exe -d <distro> --cd <linux path> -- bash -lic <agent command>`, working directory `%USERPROFILE%`. The shell is interactive (`-i`) because an owner's wrapper for the agent (one that loads a vault token, say) lives in `~/.bashrc` and exists only in an interactive shell.
  - Command link, project in WSL: target `pwsh.exe`, arguments `-NoLogo -NoProfile -Command "& '<wsl.exe>' '-d' '<distro>' '--cd' '<linux path>' '--exec' 'bash' '-lc' '<command> || { echo ''<what failed>: the reason is above. Press Enter to close.''; read -r _; }'; if ($LASTEXITCODE -ne 0) { Write-Host '<WSL failed>'; [void][Console]::ReadLine() }"`. PowerShell runs `wsl.exe --exec`, so the login shell parses the command once, and a failure stays on screen until Enter.
  - Icons are copied to `%LOCALAPPDATA%\<project folder name>`, because a link cannot keep its icon on the WSL share reliably.
  - Overlay geometry on a 512 pixel icon: an outline square at x 222, y 222, 286 wide, corner radius 70; inside it the filled square at x 236, y 236, 272 wide, corner radius 60; the mark in white, centred at (372, 372), in a box 186 wide.
- -> XREF: T02 §5 -- the WordPress kit adds its dashboard link to the profile of §2 and it is written by §6

## Outcome

- `python forge.py kit <project> launchers` installs the kit, and `pwsh scripts/project-shortcuts.ps1` in that project writes one link per agent and per declared link, each read back with the target, arguments and icon this file names; `-Remove` deletes exactly those links and icons.
- The campaign links carry the same title as the everyday links and render their icon from a `\\wsl.localhost` share.
- One renderer draws both the round runner badge and the rounded-square overlay, and no kit holds a second copy of it.
- A project with no WordPress in it (a Laravel application, a static site) gets the agent link, the campaign link and a link that opens its site.

**Adjacency:** list=not-applicable (the links are files on the desktop, found by name and by their mark); document=not-applicable (nothing is sent, printed or filed); settings=applicable @ D07 T01 §2; reporting=not-applicable (no data to summarise); notifications=not-applicable (no lifecycle to announce); permissions=applicable @ D07 T01 §5; audit=not-applicable (each run prints every link it wrote or removed, and keeps no log); exchange=not-applicable (nothing is imported or exported); reverse=applicable @ D07 T01 §5

**Adjacency rationale:** The profile of §2 is the one place a project tunes its links, and each key has a named reader in §5, §6 or §7. Permissions means the agent's permission prompts: `skip_permissions` is off unless the project turns it on, and §5 tests both ways. Reverse is `-Remove`, built in §5 and extended to declared links in §6; the campaign links keep their own `-Remove`.

## Implementation Order

| Order | Section | Deliverable | Depends On | Status |
| ----- | ------- | ----------- | ---------- | ------ |
| 1 | §1 | Launchers kit known to `forge.py` | -- | [ ] |
| 2 | §2 | Launcher profile `.conclave/launchers.json` and its loader | §1 | [ ] |
| 3 | §3 | Icon renderer owned by the launchers kit | §1 | [ ] |
| 4 | §4 | Rounded-square overlay icons | §3 | [ ] |
| 5 | §5 | Desktop links that open the project in an agent | §2, §4 | [ ] |
| 6 | §6 | Declared links that run a command or open a URL | §5 | [ ] |
| 7 | §7 | Campaign links under the project's title, icon read from a share | §2, §3 | [ ] |
| 8 | §8 | Operator page and `project-launchers` skill | §6, §7 | [ ] |

## 1. Launchers kit known to `forge.py`

A kit that `forge.py` does not list cannot be installed, diffed or checked. This section adds the kit, its first file and its plumbing, so each later section only adds files to it.

> **Started:** 2026-11-17T03:10Z

**Corrected 2026-11-17:** `list_kits` in `forge.py` lists a kit only when its `templates/` folder exists, and git keeps no empty folder, so an empty kit is never listed; and `check-all` cannot run a `kit-launchers` suite before its test folder exists. The profile template (from §2) is therefore the kit's first file here, and the suite is added in §2 with the kit's first test.

**Phase:** 8
**Needs:** none
**Surface:** no

**Build order:**

1. Create the kit folder with its README and its first file. Done when: `list_kits()` in `forge.py` returns `launchers`.
2. Teach install, detection and the doctor about it. Done when: the checkpoint passes.

- [ ] Create `kits/launchers/README.md` saying what the kit is for, that it needs no other kit, that it runs on Windows and starts WSL projects through `wsl.exe`, and listing its files as later sections add them. Done when: the Markdown format check passes on it, and a test in `tests/test_forge.py` finds in it the kit's purpose, that it needs no other kit, Windows, `wsl.exe` and a file table naming `.conclave/launchers.json`. **Planned 2026-11-17** (plan review P2). Cheaper substitute: a paragraph in `kits/unattended/README.md`, which would leave a project without unattended runs no way to get the links.
- [ ] Add `launchers` to `KIT_ORDER` in `forge.py` after `automations` and before `unattended` (which brings it from §3), and to the usage text, the `kit` and `doctor` help and the module docstring that list the kits. Done when: `python forge.py kit <scratch project> launchers --dry-run` lists the kit's files and writes nothing, and a test finds `launchers` in the module docstring's `doctor` usage line and in the `kit` and `doctor` help text. **Planned 2026-11-17** (plan review P2).
- [ ] Update `test_it_sits_after_automations_and_init_writes_todo_first` in `tests/test_forge.py` to hold `automations`, `launchers`, `unattended` in that order, keeping its check that `init` writes the TODO tooling before the unattended module. Done when: it passes, and fails with `launchers` placed after `unattended`. **Planned 2026-11-17** (plan review P1: the old assertion that `unattended` follows `automations` directly would fail).
- [ ] Extend the installed-kit detection in `forge.py` (the function that appends `unattended` near line 235) to report `launchers` when `.conclave/launchers.json` exists. Done when: a test in `tests/test_forge.py` finds `launchers` detected in a project that has the file and absent in one that does not.
- [ ] Add a `launchers` branch to `doctor_repo` in `forge.py` with one row for now, `profile`, that is `setup_required` while the file is missing. Done when: `python forge.py doctor <scratch project> launchers` prints the row and exits as the other kits do for `setup_required`. Cheaper substitute: no doctor branch, which would let a half-installed kit report healthy.
- [ ] Add the kit to the table in `kits/README.md`, to the kit list in the Purpose paragraph of `AGENTS.md`, and to the sentence there naming the kits the SDK does not install in itself. Done when: `python -m unittest tests.test_forge -k markdown_table` passes and both files name the kit.
- [ ] Add `kits/launchers/templates/.conclave/launchers.json` with exactly these keys: `schema_version` (1), `title` (null), `icon` (null), `agents` (`["claude"]`), `skip_permissions` (false), `links` (`[]`). Done when: a test reads the file as exactly that object, and `python forge.py kit <scratch project> launchers` writes it and records it under `launchers` in `.conclave/kits.json`. Cheaper substitute: keys in `.conclave/unattended.json`, which a project without that kit does not have. **Corrected 2026-11-17:** moved here from §2, as the kit's first file.
- [ ] Add the kit to the kit list a test in `tests/test_forge.py` holds (`list_kits()`), after `laravel`. Done when: that test passes with `launchers` in the list.
- [ ] Commit: `launchers: a new kit known to forge.py`

**Test checkpoint:** `python -m unittest tests.test_forge -k launchers` and `python -m unittest tests.test_forge -k after_automations` end `OK`; removing `launchers` from `KIT_ORDER`, from the help text or from the template's keys makes them fail.

## 2. Launcher profile `.conclave/launchers.json` and its loader

Everything a project chooses about its links lives in one tracked file: the title on the desktop, the icon, which agents get a link and which further links exist. Nothing about one machine (the distro, the desktop folder, the user's name) is in it; those come from the script's parameters in §5.

**Phase:** 8
**Needs:** none
**Surface:** no

**Build order:**

1. Write the template and the loader. Done when: the loader returns the template's profile once `title` and `icon` are set.
2. Refuse every malformed profile by name. Done when: the checkpoint passes.

- [ ] Add the kit's script tests to `SUITES` in `forge.py` as `kit-launchers`, in the shape of the unattended kit's suite. Done when: `python forge.py check-all --only kit-launchers` runs the suite. **Corrected 2026-11-17:** moved here from §1, which has no test folder yet; the profile template this item held moved to §1.
- [ ] Add `load_profile(path)` to a new `kits/launchers/templates/scripts/lib/launchers.py`, standard library only, returning the validated profile. Done when: it returns a dict for a valid file and raises `ValueError` naming the file for one that is not JSON or not an object.
- [ ] Refuse in `load_profile`, each with a message naming the key: an unknown key; a `schema_version` other than 1; a `title` that is null, empty, over 60 characters, or holds any of `\ / : * ? " < > |` or a control character; an `icon` that is null, absolute, leaves the project, is reached through a link, does not exist, or does not end in `.png` or `.ico`; `agents` that is empty, repeats a name or names anything but `claude`, `codex`, `agy`; a `skip_permissions` that is not a boolean. Done when: one test per refusal in `kits/launchers/templates/scripts/tests/test_launchers.py` passes. Cheaper substitute: defaulting a bad value silently, which would write a link the project did not ask for.
- [ ] Validate `links` in `load_profile`: a list of objects, each with exactly `label`, `mark` and one of `run` or `url`; `label` 1 to 30 characters under the title's character rule, unique without regard to case, and never `Claude`, `Codex`, `Antigravity` or a word ending `campaign`; `mark` one of `wordpress` or `site`; `run` a non-empty single line; `url` matching `https://` plus a host, or `http://` on `localhost` or a name ending `.test` or `.site`, with no whitespace. Done when: one test per rule passes, including a valid entry of each kind.
- [ ] Add a `show` command to `scripts/lib/launchers.py` that prints the validated profile as one line of JSON, or the refusal on stderr with exit 1. Done when: `python scripts/lib/launchers.py show` in a scratch project prints JSON that `ConvertFrom-Json` reads, and exits 1 on a malformed file.
- [ ] Replace the doctor's `profile` row from §1: `ok` with the title when the profile loads, `setup_required` naming the first refusal otherwise. Done when: a test in `tests/test_forge.py` sees both states.
- [ ] Commit: `launchers: the profile and its loader`

**Test checkpoint:** `python -m unittest discover -s kits/launchers/templates/scripts/tests -p "test_launchers.py"` ends `OK`; letting `load_profile` accept an unknown key makes it fail.

## 3. Icon renderer owned by the launchers kit

Both the campaign links and the everyday links draw an icon from the project's own. One renderer serves both, so it belongs to the kit both can reach: the unattended kit brings the launchers kit with it, as the Laravel kit brings `lsp`. The file keeps its path and name (`scripts/campaign-icon.py`), so no installed project's scripts or documents change. Reversing this is moving two files back and removing one line from `forge.py`.

**Phase:** 8
**Needs:** none
**Surface:** no

**Build order:**

1. Move the renderer and its test between the kits. Done when: both kits' suites pass.
2. Make the unattended install bring the launchers kit, and keep installed projects' records true. Done when: the checkpoint passes.

- [ ] Move `kits/unattended/templates/scripts/campaign-icon.py` and `kits/unattended/templates/scripts/tests/test_campaign_icon.py` to the same paths under `kits/launchers/templates/` with `git mv`, bytes unchanged. Done when: `git diff --stat -M` shows two renames with no content change.
- [ ] Make `python forge.py kit <project> unattended` bring the launchers kit, in the way `forge.py` (line 688) has the Laravel kit bring `lsp`: its files are written and recorded under `launchers` in `.conclave/kits.json`. Done when: a test installs `unattended` into a scratch project and finds `scripts/campaign-icon.py` recorded under `launchers`. Cheaper substitute: a second copy of the renderer left in the unattended kit, which the two kits would then change apart.
- [ ] Make `forge.py diff` and `forge.py update` treat a project whose record lists `scripts/campaign-icon.py` under `unattended` (installed before the move) as holding the launchers kit's file: `diff` reports it by its real state and never as a file no kit ships, and `update` writes the record under `launchers`. Done when: a test builds such a record, runs both, and reads the new record back.
- [ ] Point the SDK's own launcher at the new path: `scripts/start-run.ps1` lines 16 and 79, and any assertion in `tests/test_start_run.py` that names the old one. Done when: `python -m unittest tests.test_start_run` passes on Windows.
- [ ] Correct the renderer's path in `assets/brand/README.md` ("Launcher icons" and "Rendering") and the file tables in `kits/unattended/README.md` and `kits/launchers/README.md`. Done when: `git grep -n "kits/unattended/templates/scripts/campaign-icon.py"` prints nothing outside `docs/reviews/`, `docs/phase-runs/` and stamped TODO sections.
- [ ] Add a `renderer` row to the doctor's `launchers` branch: `ok` when `scripts/campaign-icon.py` exists, `setup_required` when it does not. Done when: a test sees both states.
- [ ] Commit: `launchers: the icon renderer moves here and the unattended kit brings it`

**Test checkpoint:** `python forge.py check-all --only kit-launchers` and `python forge.py check-all --only kit-unattended` both pass; restoring a copy of the renderer under `kits/unattended/templates/scripts/` makes a test in `tests/test_forge.py` fail by naming the duplicate.

## 4. Rounded-square overlay icons

The everyday links are told from the campaign links by the corner shape: a rounded square for a link a person uses, a circle for a run. The first project drew its overlays by hand in SVG. This section draws them in the renderer, so any project's icon gets them.

**Phase:** 8
**Needs:** none
**Surface:** no

**Build order:**

1. Add the shape and the command. Done when: an overlay icon is written for the `claude` mark.
2. Add the two marks the runners do not have. Done when: the checkpoint passes.

- [ ] Add an `overlay` command to `kits/launchers/templates/scripts/campaign-icon.py`: `campaign-icon.py overlay <base.png or .ico> <mark> <target.ico>`, writing every size in `SIZES` atomically through `write_atomic`. Done when: the command writes an icon that `read_ico` reads back with all ten sizes, and the usage text names it.
- [ ] Draw the overlay on each frame with the geometry in Inputs, scaled from 512 pixels: a white outline square, the filled square in the mark's colour inside it, and from `MARK_FROM` pixels up the mark in white. Done when: a test on a 256 pixel frame finds the mark's colour at the filled square's centre-left, white on the outline, and the base icon's own pixel at the top left corner. Cheaper substitute: reusing `badge_frame`'s circle, which would make an everyday link look like a campaign link.
- [ ] Give `overlay` the marks `claude`, `codex` and `agy` from the existing `RUNNERS` and `MARKS` tables, with the same colours. Done when: a test renders all three and finds each one's colour.
- [ ] Add the `wordpress` mark: the WordPress logo's W from the path data of Wikimedia Commons `WordPress_blue_logo.svg`, colour `#21759B`, with its source and the trademark note (the WordPress Foundation's mark, drawn only into a launcher icon on the operator's own machine) in the module docstring beside the others. Done when: a test finds `#21759B` in the overlay and white pixels inside it at 256 pixels.
- [ ] Add the `site` mark, drawn by this module and nobody's trademark: a globe of one circle, an upright ellipse and three horizontal lines, colour `#2563EB`. Done when: a test finds the colour and white pixels inside it at 256 pixels.
- [ ] Refuse an unknown mark, a base that is not a PNG or ICO, and a target that does not end in `.ico`, each with the usage text and exit 1, writing nothing. Done when: three tests in `scripts/tests/test_campaign_icon.py` pass, each asserting the target does not exist afterwards.
- [ ] Commit: `launchers: rounded-square overlay icons with agent, WordPress and site marks`

**Test checkpoint:** `python -m unittest discover -s kits/launchers/templates/scripts/tests -p "test_campaign_icon.py"` ends `OK`; drawing the overlay with `circle` in place of the rounded square makes the corner-pixel test fail.

## 5. Desktop links that open the project in an agent

`<Title> (Claude)` is the link the owner uses most: a double-click opens a terminal in the project with the agent running. This section writes one per agent in the profile, for a project in WSL and for a project on a Windows drive, and removes them again.

**Phase:** 8
**Needs:** windows-host
**Surface:** no

**Build order:**

1. Write the script with its parameters and the WSL form. Done when: a link is read back with the arguments in Inputs.
2. Add the Windows form, the permission flag and removal. Done when: the checkpoint passes.

- [ ] Add `kits/launchers/templates/scripts/project-shortcuts.ps1` with the parameters `-Distro`, `-Project`, `-ShortcutDir` (the desktop), `-IconDir` (`%LOCALAPPDATA%\<project folder name>`), `-Remove`, and for the tests `-Wsl` and `-Python`, resolving the project as `unattended-shortcut.ps1` does (a Windows folder, a `\\wsl.localhost\<distro>\` path or a Linux path). Done when: run with a project folder that does not exist it prints a refusal ending `nothing was written` and exits 1.
- [ ] Take the distro from the project's `\\wsl.localhost\<distro>\` or `\\wsl$\<distro>\` path when `-Distro` is not given, and refuse a Linux path with no `-Distro`. Done when: a test passes a share path and reads the distro back from the link's arguments. Cheaper substitute: a default of `Ubuntu`, which is one machine's value.
- [ ] Read the profile by running `scripts/lib/launchers.py show` with the Python given or found, and refuse with the loader's own message when it exits 1. Done when: a malformed profile produces that message and no link.
- [ ] Render each agent's icon with `campaign-icon.py overlay <icon> <agent> <IconDir>\launcher-<agent>-<key>.ico`, where `<key>` is the 8 hex digits `unattended-shortcut.ps1` derives from the project path, and the icon's path is resolved with `.ProviderPath`. Done when: the icon file exists and the link's `IconLocation` names it.
- [ ] Write `<Title> (<Label>).lnk` per agent (`Claude`, `Codex`, `Antigravity`) for a project in WSL: target `wt.exe` found with `Get-Command`, arguments `wsl.exe -d <distro> --cd <linux path> -- bash -lic <command>`, working directory `%USERPROFILE%`, description `conclave-launcher: <Project>`, written under a temporary name and moved over the old. Done when: the test reads the link back through `WScript.Shell` and finds each field. Cheaper substitute: `bash -lc`, which loses the owner's interactive wrapper for the agent.
- [ ] Write the same link for a project on a Windows drive: arguments `-d "<project>" pwsh.exe -NoLogo -NoExit -Command <command>`. Done when: a test with a Windows scratch project reads those arguments back.
- [ ] Build `<command>` from the agent's name alone, and with `skip_permissions` true add the flag `scripts/lib/unattended.py` uses for that agent (`--dangerously-skip-permissions` for `claude` and `agy`, `--dangerously-bypass-approvals-and-sandbox` for `codex`). Done when: one test finds no flag with the key false and the right flag per agent with it true.
- [ ] Fall back, when `wt.exe` is not found, to `wsl.exe` or `pwsh.exe` as the link's own target with the same command. Done when: a test with `wt.exe` hidden from `PATH` reads a working target back.
- [ ] Implement `-Remove`: delete every link in `-ShortcutDir` whose description is this project's mark and every `launcher-*-<key>.ico` in `-IconDir`, printing each, and leave the campaign links and every other project's files. Done when: a test writes links for two projects and a campaign link, removes one project's, and finds the rest untouched.
- [ ] Add `kits/launchers/templates/scripts/tests/test_project_shortcuts.py` holding the tests above, every console child started with `CREATE_NO_WINDOW`, every link in a scratch folder, `wsl.exe` replaced by the stand-in `test_shortcut.py` uses, skipped where `pwsh` is missing. Done when: the suite passes on Windows and opens no window.
- [ ] Commit: `launchers: desktop links that open the project in an agent`

**Test checkpoint:** `python -m unittest discover -s kits/launchers/templates/scripts/tests -p "test_project_shortcuts.py"` ends `OK` on Windows; changing `bash -lic` to `bash -lc` in the script makes it fail.

## 6. Declared links that run a command or open a URL

The third link of the shape differs per project: a WordPress project opens its dashboard through a command (`T02`), a Laravel or static project opens its site. Both are entries in the profile's `links`, written by the same script.

**Phase:** 8
**Needs:** windows-host
**Surface:** no

**Build order:**

1. Write the command form. Done when: a `run` entry is read back with the arguments in Inputs.
2. Write the URL form and extend removal. Done when: the checkpoint passes.

- [ ] Write `<Title> (<label>).lnk` in `scripts/project-shortcuts.ps1` for each `run` entry of a project in WSL, in the command-link form of Inputs, with `<what failed>` reading `<label> did not start`, each argument single-quoted for PowerShell with quotes doubled. Done when: the test reads the link back and runs its target and arguments, windowless, against the stand-in, which records exactly `-d <distro> --cd <linux path> --exec bash -lc <command with the failure tail>`. Cheaper substitute: `wt.exe ... bash -lc`, where a failure closes the window before it can be read.
- [ ] Write the `run` form for a project on a Windows drive: `pwsh.exe -NoLogo -NoProfile -Command` running the command in the project folder, with the same wait for Enter on a non-zero exit. Done when: a test reads it back and a failing command leaves the stand-in's record of the wait.
- [ ] Write each `url` entry as a link whose target is `rundll32.exe` with the arguments `url.dll,FileProtocolHandler <url>`, so no console window appears. Done when: the test reads the target and the URL back, and nothing in the suite starts the link.
- [ ] Render each entry's icon with `campaign-icon.py overlay <icon> <mark>` into `launcher-<label slug>-<key>.ico`, the slug being the label in lower case with every run of other characters as one hyphen. Done when: two entries with different marks get two icon files.
- [ ] Delete, on every run, a link carrying this project's mark that the profile no longer declares, with its icon. Done when: a test writes a link, drops the entry from the profile, runs the script again and finds the link gone.
- [ ] Add a `links` row to the doctor's `launchers` branch in `forge.py`: the number of agent and declared links the profile yields. Done when: a test reads the count for a profile with two agents and one entry as 3.
- [ ] Commit: `launchers: declared links that run a command or open a URL`

**Test checkpoint:** `python -m unittest discover -s kits/launchers/templates/scripts/tests -p "test_project_shortcuts.py" -k declared` ends `OK` on Windows; dropping the `|| { ...; read -r _; }` tail from the command makes it fail.

## 7. Campaign links under the project's title, icon read from a share

Two faults in the campaign link, both found on the first project that used the whole shape. Its name is the folder's (`<folder> <Runner> campaign`) while the other links carry the title, and its icon cannot be read from a `\\wsl.localhost` share.

**Phase:** 8
**Needs:** windows-host
**Surface:** no

**Build order:**

1. Fix the icon path with a test that fails first. Done when: the new test fails on the old line and passes on the new.
2. Name the link by the title. Done when: the checkpoint passes.

- [ ] Add a test to `kits/unattended/templates/scripts/tests/test_shortcut.py` that passes `-Icon` as a provider-qualified path (`Microsoft.PowerShell.Core\FileSystem::<scratch>\icon.png`, which is what `Resolve-Path` returns for a file on a share). Done when: it fails on the current script with the renderer unable to open the file.
- [ ] Change `kits/unattended/templates/scripts/unattended-shortcut.ps1` line 123 to `(Resolve-Path -LiteralPath $Icon).ProviderPath`, with a comment saying why. Done when: the test above passes. Cheaper substitute: stripping the prefix with a string replace, which breaks on the next provider.
- [ ] Name each campaign link `<title> <Runner> campaign.lnk` when `.conclave/launchers.json` loads through `scripts/lib/launchers.py show`, and by the folder's name as now when the file is missing; a profile that exists and is refused stops the script with the loader's message. Done when: one test per case reads the link's name back.
- [ ] Remove, on a run that renames, the link this project wrote under the old name, found by its mark as `Get-Owned` already does. Done when: a test writes the link without a profile, adds the profile, runs again and finds one link, under the title.
- [ ] Keep `start_command` in `scripts/unattended-run.py` and the link's arguments equal, as the existing test holds. Done when: that test still passes unchanged.
- [ ] Commit: `unattended: campaign links take the project's title and read an icon from a share`

**Test checkpoint:** `python forge.py check-all --only kit-unattended` passes on Windows; restoring `.Path` on line 123 makes the provider-path test fail.

## 8. Operator page and `project-launchers` skill

A person or an agent in a project needs one place that says how to set the title and icon, write the links and remove them. The page is the operator's; the skill points each agent at it.

**Phase:** 8
**Needs:** none
**Surface:** no

**Build order:**

1. Write the page. Done when: every command on it is one a test in this file runs.
2. Write the skill and generate its copies. Done when: the checkpoint passes.

- [ ] Write `kits/launchers/templates/docs/launchers.md` with question-shaped headings: what the links are; how to set `title`, `icon`, `agents` and `skip_permissions`; how to declare a `run` or `url` link; how to write the links (`pwsh scripts/project-shortcuts.ps1`, by its `\\wsl.localhost` path for a project in WSL); how to remove them; what each refusal means; and that the icon wants a square PNG of 256 pixels or more. Done when: a test in `tests/test_forge.py` finds each topic on the page and the Markdown format check passes.
- [ ] Add the page's worked example for a web project that is not WordPress: a Laravel application with `{"label": "Site", "mark": "site", "url": "https://example.test"}`. Done when: the example loads through `load_profile` in a test.
- [ ] Write `kits/launchers/templates/.claude/skills/project-launchers/SKILL.md`: when to use it (the operator asks for desktop shortcuts, or a project's title or icon changed), the steps (fill the profile, run the script from Windows PowerShell, read the printed links back), and the rule that a link is only ever started by the operator. Done when: the skill names no project and no machine path.
- [ ] Run `python forge.py skill-copies` to write the Antigravity and Codex copies, and add Codex's `agents/openai.yaml` by hand. Done when: `python forge.py skill-copies --check` exits 0.
- [ ] Point at the page from `kits/unattended/templates/docs/unattended-run.md` (the shortcuts section) and from the file table in `kits/launchers/README.md`. Done when: both links resolve in a test.
- [ ] Commit: `launchers: the operator's page and the project-launchers skill`

**Test checkpoint:** `python -m unittest tests.test_forge -k launchers_page` ends `OK`; removing the removal heading from the page makes it fail.

## Verification

- In a scratch project in WSL with a title, an icon, two agents and one `url` link, `pwsh scripts/project-shortcuts.ps1` writes three links into a scratch folder, each read back as this file describes, and `-Remove` leaves the folder empty.
- `python forge.py check-all --only kit-launchers` and `python forge.py check-all --only kit-unattended` pass, and the CI run of the stamping commit is green.
- `python forge.py doctor <project> launchers` reports `profile`, `renderer` and `links`.
- `python scripts/todo-graph.py validate` and `python scripts/todo-graph.py plan --check` pass.
