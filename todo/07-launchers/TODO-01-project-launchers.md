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
- `kits/launchers/templates/scripts/campaign-icon.py`: the standard-library renderer (PNG and ICO read and written, SVG path data rasterised with supersampling). §3 moved it here from the unattended kit and §4 extends it.
- `kits/unattended/templates/scripts/lib/unattended.py`: the command line each agent starts with, which §5 reuses for the permission flags.
- `forge.py`: `KIT_ORDER` (line 197), the installed-kit detection below it, `kit_plan`, `doctor_repo`, `SUITES`, and the way the Laravel kit brings the `lsp` kit with it (line 688), which is the model for §3.
- The facts of the everyday links as built, copied on 2026-11-17 so the sections can be built when the source project cannot be read:
  - Agent link, project in WSL: target `wt.exe`, arguments `wsl.exe -d <distro> --cd <linux path> -- bash -lic <agent command>`, working directory `%USERPROFILE%`. The shell is interactive (`-i`) because an owner's wrapper for the agent (one that loads a vault token, say) lives in `~/.bashrc` and exists only in an interactive shell.
  - Command link, project in WSL: target `pwsh.exe`, arguments `-NoLogo -NoProfile -Command "& '<wsl.exe>' '-d' '<distro>' '--cd' '<linux path>' '--exec' 'bash' '-lc' '<command> || { echo ''<what failed>: the reason is above. Press Enter to close.''; read -r _; }'; if ($LASTEXITCODE -ne 0) { Write-Host '<WSL failed>'; [void][Console]::ReadLine() }"`. PowerShell runs `wsl.exe --exec`, so the login shell parses the command once, and a failure stays on screen until Enter. **Corrected 2026-11-17 (D07 T01 §6 round 1):** as built, the command is never spliced into the code that watches it: in WSL it is Bash's first argument (`bash -lc '(eval "$1") || { echo ...; read -r _; }' bash '<command>'`), and on a Windows drive it runs in a child `pwsh -EncodedCommand`, because a spliced `exit`, trailing comment or `;` broke the handler.
  - Icons are copied to `%LOCALAPPDATA%\<project folder name>`, because a link cannot keep its icon on the WSL share reliably.
  - Overlay geometry on a 512 pixel icon: an outline square at x 222, y 222, 286 wide, corner radius 70; inside it the filled square at x 236, y 236, 272 wide, corner radius 60; the mark in white, centred at (372, 372), in a box 186 wide.
- -> XREF: T02 §5 -- the WordPress kit adds its dashboard link to the profile of §2 and it is written by §6
- -> XREF: D04 T04 §2 -- the desktop lock reuses §7's lock-with-holder shape (an exclusive handle the system frees, a holder named by id and start time)

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
| 1 | §1 | Launchers kit known to `forge.py` | -- | [x] |
| 2 | §2 | Launcher profile `.conclave/launchers.json` and its loader | §1 | [x] |
| 3 | §3 | Icon renderer owned by the launchers kit | §1 | [x] |
| 4 | §4 | Rounded-square overlay icons | §3 | [x] |
| 5 | §5 | Desktop links that open the project in an agent | §2, §4 | [x] |
| 6 | §6 | Declared links that run a command or open a URL | §5 | [x] |
| 7 | §7 | Campaign links under the project's title, icon read from a share | §2, §3 | [x] |
| 8 | §8 | Operator page and `project-launchers` skill | §6, §7 | [ ] |
| 9 | §9 | Agent and declared links named outside the ANSI code page | §6 | [ ] |

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

- [x] Create `kits/launchers/README.md` saying what the kit is for, that it needs no other kit, that it runs on Windows and starts WSL projects through `wsl.exe`, and listing its files as later sections add them. Done when: the Markdown format check passes on it, and a test in `tests/test_forge.py` finds in it the kit's purpose, that it needs no other kit, Windows, `wsl.exe` and a file table naming `.conclave/launchers.json`. **Planned 2026-11-17** (plan review P2). Cheaper substitute: a paragraph in `kits/unattended/README.md`, which would leave a project without unattended runs no way to get the links.
- [x] Add `launchers` to `KIT_ORDER` in `forge.py` after `automations` and before `unattended` (which brings it from §3), and to the usage text, the `kit` and `doctor` help and the module docstring that list the kits. Done when: `python forge.py kit <scratch project> launchers --dry-run` lists the kit's files and writes nothing, and a test finds `launchers` in the module docstring's `doctor` usage line and in the `kit` and `doctor` help text. **Planned 2026-11-17** (plan review P2).
- [x] Update `test_it_sits_after_automations_and_init_writes_todo_first` in `tests/test_forge.py` to hold `automations`, `launchers`, `unattended` in that order, keeping its check that `init` writes the TODO tooling before the unattended module. Done when: it passes, and fails with `launchers` placed after `unattended`. **Planned 2026-11-17** (plan review P1: the old assertion that `unattended` follows `automations` directly would fail).
- [x] Extend the installed-kit detection in `forge.py` (the function that appends `unattended` near line 235) to report `launchers` when `.conclave/launchers.json` exists. Done when: a test in `tests/test_forge.py` finds `launchers` detected in a project that has the file and absent in one that does not.
- [x] Add a `launchers` branch to `doctor_repo` in `forge.py` with one row for now, `profile`, that is `setup_required` while the file is missing. Done when: `python forge.py doctor <scratch project> launchers` prints the row and exits as the other kits do for `setup_required`. Cheaper substitute: no doctor branch, which would let a half-installed kit report healthy.
- [x] Add the kit to the table in `kits/README.md`, to the kit list in the Purpose paragraph of `AGENTS.md`, and to the sentence there naming the kits the SDK does not install in itself. Done when: `python -m unittest tests.test_forge -k markdown_table` passes and both files name the kit.
- [x] Add `kits/launchers/templates/.conclave/launchers.json` with exactly these keys: `schema_version` (1), `title` (null), `icon` (null), `agents` (`["claude"]`), `skip_permissions` (false), `links` (`[]`). Done when: a test reads the file as exactly that object, and `python forge.py kit <scratch project> launchers` writes it and records it under `launchers` in `.conclave/kits.json`. Cheaper substitute: keys in `.conclave/unattended.json`, which a project without that kit does not have. **Corrected 2026-11-17:** moved here from §2, as the kit's first file.
- [x] Add the kit to the kit list a test in `tests/test_forge.py` holds (`list_kits()`), after `laravel`. Done when: that test passes with `launchers` in the list.
- [x] Commit: `launchers: a new kit known to forge.py`

**Test checkpoint:** `python -m unittest tests.test_forge -k launchers` and `python -m unittest tests.test_forge -k after_automations` end `OK`; removing `launchers` from `KIT_ORDER`, from the help text or from the template's keys makes them fail.

> **Verified:** 2026-11-17 | §1 | a4baad6ff3f933528718fdcc49edd1def76cdf49
> **Review:** `docs/reviews/d07-t01-s1.json`

## 2. Launcher profile `.conclave/launchers.json` and its loader

Everything a project chooses about its links lives in one tracked file: the title on the desktop, the icon, which agents get a link and which further links exist. Nothing about one machine (the distro, the desktop folder, the user's name) is in it; those come from the script's parameters in §5.

> **Started:** 2026-11-17T05:15Z

**Corrected 2026-11-17:** the plan left three things open that the build would otherwise invent. The icon is relative to the project, which is the folder holding `.conclave/` (`load_profile(path)` takes it as `path.parent.parent`, or a `root` argument). `show` reads `<root>/.conclave/launchers.json`, where `--root` defaults to the project the script is installed in (`scripts/lib/` two folders down). The doctor's row loads the kit's own `launchers.py` from the SDK, as the toolchain rows load the kit's checks. A title also becomes a file name on Windows, so one that starts or ends with a space or ends with a dot is refused with the others.

**Phase:** 8
**Needs:** none
**Surface:** no

**Build order:**

1. Write the template and the loader. Done when: the loader returns the template's profile once `title` and `icon` are set.
2. Refuse every malformed profile by name. Done when: the checkpoint passes.

- [x] Add the kit's script tests to `SUITES` in `forge.py` as `kit-launchers`, in the shape of the unattended kit's suite. Done when: `python forge.py check-all --only kit-launchers` runs the suite. **Corrected 2026-11-17:** moved here from §1, which has no test folder yet; the profile template this item held moved to §1.
- [x] Add `load_profile(path, root=None)` to a new `kits/launchers/templates/scripts/lib/launchers.py`, standard library only, returning the validated profile, with `ProfileError(ValueError)` for every refusal and the project as `root` or `path.parent.parent`. Done when: it returns a dict equal to the file's own values (non-default ones included) for a valid file, and raises `ProfileError` naming the file for one that is missing, a folder, unreadable, not UTF-8, not JSON or not an object, never a traceback. **Planned 2026-11-17** (plan review P2: file system failures and fidelity).
- [x] Refuse in `load_profile`, each with a message naming the key, holding every key to its exact JSON type (`schema_version` an integer and not a boolean, `title` and `icon` strings, `agents` and `links` lists, `skip_permissions` a boolean): an unknown key; a `schema_version` other than 1; a missing key; a `title` that is null, not a string, empty, over 60 characters, starts or ends with a space, ends with a dot, or holds any of `\ / : * ? " < > |` or a control character; an `icon` that is null, absolute, leaves the project, is reached through a link, does not exist, is not a regular file (a folder named `icon.png`), or does not end in `.png` or `.ico`; `agents` that is empty, repeats a name or names anything but `claude`, `codex`, `agy`; a `skip_permissions` that is not a boolean. Done when: one test per refusal in `kits/launchers/templates/scripts/tests/test_launchers.py` passes. Cheaper substitute: defaulting a bad value silently, which would write a link the project did not ask for.
- [x] Validate `links` in `load_profile`: a list of objects, each with exactly `label`, `mark` and one of `run` or `url`; `label` 1 to 30 characters under the title's character rule, unique without regard to case and by the icon slug §6 names files with (the label in lower case, each run of other characters one hyphen, so `Admin Panel` and `Admin-Panel` collide), a slug that is not an agent's name (`claude`, `codex`, `agy`, whose icons §5 names the same way), and never `Claude`, `Codex`, `Antigravity` or a word ending `campaign`; `mark` one of `wordpress` or `site`; `run` a non-empty single line; `url` matching `https://` plus a host, or `http://` on `localhost` or a name ending `.test` or `.site`, with no whitespace. Done when: one test per rule passes, including a valid entry of each kind and the two-label slug collision. **Planned 2026-11-17** (plan review P2: slug collisions, exact types).
- [x] Add a `show` command to `scripts/lib/launchers.py` (`show [--root <project>]`, the root defaulting to the project the script is installed in) that prints the validated profile as one line of JSON, or the refusal on stderr with exit 1. Done when: `python scripts/lib/launchers.py show --root <scratch project>` prints JSON that `ConvertFrom-Json` reads, an installed copy run with no `--root` from an unrelated working directory reads its own project and prints exactly the profile's values, and it exits 1 with the refusal on stderr and no traceback for a malformed, unreadable or folder profile. **Planned 2026-11-17** (plan review P2).
- [x] Replace the doctor's `profile` row from §1, loading the kit's `launchers.py` from the SDK: `ok` with the title when the profile loads, `setup_required` naming the refusal otherwise (a fresh install's null `title` among them), and `setup_required` with the install command when the file is missing. Done when: a test in `tests/test_forge.py` sees the three states, a folder at the profile's path among the refusals, with no traceback.
- [x] Commit: `launchers: the profile and its loader`

**Test checkpoint:** `python -m unittest discover -s kits/launchers/templates/scripts/tests -p "test_launchers.py"` ends `OK`; letting `load_profile` accept an unknown key makes it fail.

> **Verified:** 2026-11-17 | §2 | 4cab4cfa9ea13f22d363d300ec632fe8ad25203f
> **Review:** `docs/reviews/d07-t01-s2.json`

## 3. Icon renderer owned by the launchers kit

Both the campaign links and the everyday links draw an icon from the project's own. One renderer serves both, so it belongs to the kit both can reach: the unattended kit brings the launchers kit with it, as the Laravel kit brings `lsp`. The file keeps its path and name (`scripts/campaign-icon.py`), so no installed project's scripts or documents change. Reversing this is moving two files back and removing one line from `forge.py`.

> **Started:** 2026-11-17T11:10Z

**Corrected 2026-11-17:** the plan left four things out that the build would otherwise invent or miss. The unattended kit's own tests read the renderer beside them: `test_shortcut.py` copies `campaign-icon.py` from its own `scripts/` folder into the scratch project, and `test_unattended.py` lists it in `WindowlessTest.KIT_FILES`, which must equal the kit folder's Python files; once the file moves, both must find it in the launchers kit in the kit tree and beside them in an installed project. An old install has no `.conclave/launchers.json` and may have no record, so `diff` must count the launchers kit present wherever the unattended kit is, or the renderer would be reported by no kit. The migration of an old record belongs where the record is read (`load_record`), so `diff`, `update`, `record` and `kit` all see the moved entry under `launchers`, and `update` writes the record even when no file changes. The checkpoint's duplicate test was owned by no item, and two toolchain kits already ship the same two files on purpose (`SHARED` in `tests/test_toolchain_kits.py`), so it allows exactly those.

**Phase:** 8
**Needs:** none
**Surface:** no

**Build order:**

1. Move the renderer and its test between the kits. Done when: both kits' suites pass.
2. Make the unattended install bring the launchers kit, and keep installed projects' records true. Done when: the checkpoint passes.

- [x] Move `kits/unattended/templates/scripts/campaign-icon.py` and `kits/unattended/templates/scripts/tests/test_campaign_icon.py` to the same paths under `kits/launchers/templates/` with `git mv`, bytes unchanged. Done when: `git diff --stat -M` shows two renames with no content change.
- [x] Make `python forge.py kit <project> unattended` bring the launchers kit, in the way `forge.py` (line 688) has the Laravel kit bring `lsp`: its files are written and recorded under `launchers` in `.conclave/kits.json`. Done when: a test installs `unattended` into a scratch project and finds `scripts/campaign-icon.py` recorded under `launchers`. Cheaper substitute: a second copy of the renderer left in the unattended kit, which the two kits would then change apart.
- [x] Make `forge.py diff` and `forge.py update` treat a project whose record lists `scripts/campaign-icon.py` under `unattended` (installed before the move) as holding the launchers kit's file: `diff` reports it by its real state and never as a file no kit ships, and `update` writes the record under `launchers`. Done when: a test builds such a record, runs both, and reads the new record back. **Corrected 2026-11-17:** the moved entries are re-attributed in `load_record` through one table of moved files in `forge.py` (the launchers kit's entry gaining the unattended kit's agents and commit), and `update` writes the record when that changed it, even with no file to write. **Planned 2026-11-17** (plan review P1): for both moved files, a copy unchanged since install, one the project edited and one it deleted each keep their recorded digest and report `identical` (or `kit-newer`), `project-changed` and `project-removed`; `diff` and `update --dry-run` leave the record byte for byte; and a record-only `update` (every file identical) writes the entries under `launchers` with the digests unchanged.
- [x] Extend `test_a_fresh_install_writes_exactly_the_planned_files` in `tests/test_forge.py` so the unattended install's brought launchers plan is written, reported under `launchers` and byte for byte the kit's, as it holds the Laravel kit's `lsp`. Done when: it passes, and fails when the unattended install stops bringing the launchers kit. **Planned 2026-11-17** (plan review P2).
- [x] Count the launchers kit present in `_diff_kits` in `forge.py` wherever the unattended kit is, so an install from before the move with no record still has its renderer reported. Done when: a test diffs a project with `.conclave/unattended.json`, the renderer and no record, and finds `scripts/campaign-icon.py` under `launchers`. **Corrected 2026-11-17:** added (plan validation).
- [x] Make `kits/unattended/templates/scripts/tests/test_shortcut.py` take the renderer beside it in an installed project and from `kits/launchers/templates/scripts/` in the kit tree, and drop `campaign-icon.py` and `tests/test_campaign_icon.py` from `KIT_FILES` in `test_unattended.py`. Done when: `python forge.py check-all --only kit-unattended` passes. Cheaper substitute: a copy of the renderer kept in the unattended kit for its tests. **Corrected 2026-11-17:** added (plan validation).
- [x] Add a windowless check to `kits/launchers/templates/scripts/tests/test_launchers.py` over the launchers kit's own Python files (the kit folder's list held complete in the kit tree, as `WindowlessTest` holds the unattended kit's): every `subprocess` start passes `creationflags`. Done when: it passes, and fails naming the file and line when `creationflags` is removed from one call in `test_campaign_icon.py`. **Corrected 2026-11-17:** added; the moved tests leave the unattended kit's windowless check, which covered them.
- [x] Add a test to `tests/test_forge.py` that no relative path is shipped by two kits' `templates/`, except the toolchain kits' shared `scripts/toolchain-check.py` and its test. Done when: it passes, and fails naming the path and both kits with a copy of the renderer under `kits/unattended/templates/scripts/`. **Corrected 2026-11-17:** added; the checkpoint named this test and no item built it.
- [x] Point the SDK's own launcher at the new path: `scripts/start-run.ps1` lines 16 and 79, and any assertion in `tests/test_start_run.py` that names the old one. Done when: `python -m unittest tests.test_start_run` passes on Windows.
- [x] Correct the renderer's path in `assets/brand/README.md` ("Launcher icons" and "Rendering") and the file tables in `kits/unattended/README.md` and `kits/launchers/README.md`. Done when: `git grep -n "kits/unattended/templates/scripts/campaign-icon.py"` prints nothing outside `docs/reviews/`, `docs/phase-runs/` and stamped TODO sections.
- [x] Add a `renderer` row to the doctor's `launchers` branch: `ok` when `scripts/campaign-icon.py` exists, `setup_required` when it does not. Done when: a test sees both states.
- [x] Commit: `launchers: the icon renderer moves here and the unattended kit brings it`

**Test checkpoint:** `python forge.py check-all --only kit-launchers` and `python forge.py check-all --only kit-unattended` both pass; restoring a copy of the renderer under `kits/unattended/templates/scripts/` makes a test in `tests/test_forge.py` fail by naming the duplicate.

> **Verified:** 2026-11-17 | §3 | e97223af705b6464f053a8d2d6fb2ce9ed21920e
> **Review:** `docs/reviews/d07-t01-s3.json`

## 4. Rounded-square overlay icons

The everyday links are told from the campaign links by the corner shape: a rounded square for a link a person uses, a circle for a run. The first project drew its overlays by hand in SVG. This section draws them in the renderer, so any project's icon gets them.

> **Started:** 2026-11-17T11:52Z

**Corrected 2026-11-17:** three facts of the renderer the plan did not match. It already ends a usage error (a mark or runner it does not know, a malformed command) with the usage text and exit 2, which a test holds for `badge`, and an unreadable base with `campaign-icon: <fault>` and exit 1; the refusals keep that split instead of exit 1 for all. The Commons file holds the W inside its ring as five separate paths, each opening with a relative `m` that is absolute on its own; the mark is the whole logo, the paths joined with each opening `M` (the third's first line written as an explicit `l`, which it was implicitly). And `write_atomic` leaves its temporary file behind when the write or the rename fails, which every `overlay` call would now share: it removes it.

**Phase:** 8
**Needs:** none
**Surface:** no

**Build order:**

1. Add the shape and the command. Done when: an overlay icon is written for the `claude` mark.
2. Add the two marks the runners do not have. Done when: the checkpoint passes.

- [x] Add an `overlay` command to `kits/launchers/templates/scripts/campaign-icon.py`: `campaign-icon.py overlay <base.png or .ico> <mark> <target.ico>`, writing every size in `SIZES` atomically through `write_atomic`. Done when: the command writes an icon that `read_ico` reads back with all ten sizes, and the usage text names it.
- [x] Draw the overlay on each frame with the geometry in Inputs, scaled from 512 pixels: a white outline square, the filled square in the mark's colour inside it, and from `MARK_FROM` pixels up the mark in white. Done when: a test on a 256 pixel frame finds the mark's colour at the filled square's centre-left, white on the outline, and the base icon's own pixel at the top left corner. Cheaper substitute: reusing `badge_frame`'s circle, which would make an everyday link look like a campaign link.
- [x] Give `overlay` the marks `claude`, `codex` and `agy` from the existing `RUNNERS` and `MARKS` tables, with the same colours. Done when: a test renders all three and finds each one's colour.
- [x] Add the `wordpress` mark: the WordPress logo (the W in its ring, **Corrected 2026-11-17**) from the path data of Wikimedia Commons `WordPress_blue_logo.svg`, colour `#21759B`, with its source and the trademark note (the WordPress Foundation's mark, drawn only into a launcher icon on the operator's own machine) in the module docstring beside the others. Done when: a test finds `#21759B` in the overlay and white pixels inside it at 256 pixels.
- [x] Add the `site` mark, drawn by this module and nobody's trademark: a globe of one circle, an upright ellipse and three horizontal lines, colour `#2563EB`. Done when: a test finds the colour and white pixels inside it at 256 pixels.
- [x] Prove the saved icons carry their marks: run the `overlay` command for all five marks, from a PNG base and from an ICO base, and decode its output. Done when: in each icon's 256 pixel frame the fill colour is at the square's centre-left and the white mark covers the mark box, each mark's white pattern differs from every other mark's, the 32 pixel frame (`MARK_FROM`) holds more white than the same overlay drawn with no mark, and the 24 pixel frame holds none beyond it. **Planned 2026-11-17** (plan review P1).
- [x] Refuse an unknown mark, a base that is not a PNG or ICO, and a target that does not end in `.ico`, writing nothing and leaving an existing target byte for byte: the mark and the target with the usage text and exit 2, the base with `campaign-icon: not a PNG` and exit 1. Done when: three tests in `kits/launchers/templates/scripts/tests/test_campaign_icon.py` pass, each asserting its exit code and diagnostic, that a new target does not exist afterwards and that an existing one keeps its bytes. **Corrected 2026-11-17:** exit 2 for a usage error, as `badge` does. **Planned 2026-11-17** (plan review P2: exit, diagnostic and an existing target asserted; the test file's path).
- [x] Make `write_atomic` in `campaign-icon.py` remove its temporary file when the write or the rename fails. Done when: a test that makes `os.replace` fail, and one that fails the temporary file's write after some bytes are on disk, each find the old icon unchanged and no other file in its folder. **Corrected 2026-11-17:** added. **Planned 2026-11-17** (plan review P2: a partial write).
- [x] Commit: `launchers: rounded-square overlay icons with agent, WordPress and site marks`

**Test checkpoint:** `python -m unittest discover -s kits/launchers/templates/scripts/tests -p "test_campaign_icon.py"` ends `OK`; drawing the overlay with `circle` in place of the rounded square makes the corner-pixel test fail.

> **Verified:** 2026-11-17 | §4 | 5e8353045b4d0efca2dcf4809b8e2b795cc1b451
> **Review:** `docs/reviews/d07-t01-s4.json`

## 5. Desktop links that open the project in an agent

`<Title> (Claude)` is the link the owner uses most: a double-click opens a terminal in the project with the agent running. This section writes one per agent in the profile, for a project in WSL and for a project on a Windows drive, and removes them again.

> **Started:** 2026-11-17T13:20Z

**Corrected 2026-11-17:** four facts the build would otherwise get wrong. The permission flags are passed by `scripts/unattended-run.py` (its `agent_command`), not `scripts/lib/unattended.py`; the launchers kit needs no other kit, so the script keeps its own table and a test in the SDK holds it equal to the run's. A `\\wsl.localhost\<distro>\` project path is not resolved from Windows (no check here can read it there): WSL says whether the folder exists (`test -d`), as for a Linux path. A link the profile no longer names (an agent taken out, an earlier title) would stay on the desktop forever, so each run removes this project's links and icons that it did not write. And the link of a project on a Windows drive starts in the project folder, not `%USERPROFILE%`.

**Phase:** 8
**Needs:** windows-host
**Surface:** no

**Build order:**

1. Write the script with its parameters and the WSL form. Done when: a link is read back with the arguments in Inputs.
2. Add the Windows form, the permission flag and removal. Done when: the checkpoint passes.

- [x] Add `kits/launchers/templates/scripts/project-shortcuts.ps1` with the parameters `-Distro`, `-Project`, `-ShortcutDir` (the desktop), `-IconDir` (`%LOCALAPPDATA%\<project folder name>`), `-Remove`, and for the tests `-Wsl` and `-Python`, resolving the project as `unattended-shortcut.ps1` does (a Windows folder, a `\\wsl.localhost\<distro>\` path or a Linux path). Done when: run with a project folder that does not exist it prints a refusal ending `nothing was written` and exits 1.
- [x] Take the distro from the project's `\\wsl.localhost\<distro>\` or `\\wsl$\<distro>\` path when `-Distro` is not given, and refuse a Linux path with no `-Distro`. Done when: a test passes a share path and reads the distro back from the link's arguments. Cheaper substitute: a default of `Ubuntu`, which is one machine's value.
- [x] Read the profile by running `scripts/lib/launchers.py show` with the Python given or found, and refuse with the loader's own message when it exits 1. Done when: a malformed profile produces that message and no link.
- [x] Render each agent's icon with `campaign-icon.py overlay <icon> <agent> <IconDir>\launcher-<agent>-<key>.ico`, where `<key>` is the 8 hex digits `unattended-shortcut.ps1` derives from the project path, and the icon's path is resolved with `.ProviderPath`. Done when: the icon file exists and the link's `IconLocation` names it.
- [x] Write `<Title> (<Label>).lnk` per agent (`Claude`, `Codex`, `Antigravity`) for a project in WSL: target `wt.exe` found with `Get-Command`, arguments `wsl.exe -d <distro> --cd <linux path> -- bash -lic <command>`, working directory `%USERPROFILE%`, description `conclave-launcher: <Project>`, written under a temporary name and moved over the old. Done when: the test reads the link back through `WScript.Shell` and finds each field. Cheaper substitute: `bash -lc`, which loses the owner's interactive wrapper for the agent. **Corrected 2026-11-17:** `--exec bash -lic` in place of `-- bash -lic`: with `--` WSL hands the rest to the login shell, which parses the agent command a second time (the campaign links found this on 2026-11-13), and the agent command now carries its own failure message.
- [x] Write the same link for a project on a Windows drive: arguments `-d "<project>" pwsh.exe -NoLogo -NoExit -Command <command>`. Done when: a test with a Windows scratch project reads those arguments back.
- [x] Build `<command>` from the agent's name alone, and with `skip_permissions` true add the flag `scripts/unattended-run.py` passes for that agent (**Corrected 2026-11-17**) (`--dangerously-skip-permissions` for `claude` and `agy`, `--dangerously-bypass-approvals-and-sandbox` for `codex`). Done when: one test finds no flag with the key false and the right flag per agent with it true.
- [x] Fall back, when `wt.exe` is not found, to `wsl.exe` or `pwsh.exe` as the link's own target with the same command. Done when: a test with `wt.exe` hidden from `PATH` reads a working target back.
- [x] Remove, on every run that writes links, this project's links (by the mark) that the run did not write and its `launcher-*-<key>.ico` icons that no written link uses, printing each. Done when: a test writes links for two agents, rewrites with one agent and a new title, and finds only the new link and its icon. **Corrected 2026-11-17:** added.
- [x] Hold the script's flag table equal to `scripts/unattended-run.py`'s, where the unattended kit is beside the launchers kit (the SDK). Done when: a test reads each agent's flag from `agent_command` and finds it in `project-shortcuts.ps1`, and skips, naming why, in an installed project without that kit. **Corrected 2026-11-17:** added.
- [x] Implement `-Remove`: delete every link in `-ShortcutDir` whose description is this project's mark and every `launcher-*-<key>.ico` in `-IconDir`, printing each, and leave the campaign links and every other project's files. Done when: a test writes links for two projects and a campaign link, removes one project's, and finds the rest untouched.
- [x] Give each project one identity, its distro and Linux path for a project in WSL (case kept, however it was written: a Linux path, `\\wsl.localhost\` or `\\wsl$\`) and its full Windows path for one on a drive, and derive the link mark (`conclave-launcher: <identity>`) and the icon key from it. Done when: a test writes the same Linux path in two distros and removes one, finding the other's links and icons intact, and removes a project through each other spelling of its path. **Planned 2026-11-17** (plan review P1).
- [x] Refuse, before anything is written, a link whose name is taken by a file that is not this project's (another project with the same title, or anything else), naming it and leaving it as it was. Done when: a test with two projects of one title finds the second refused with exit 1 and the first project's link unchanged. **Planned 2026-11-17** (plan review P1).
- [x] Prove the links run, not only read back: execute each read-back target and arguments windowless against recording stand-ins (a compiled `wt.exe` stand-in, the `wsl.exe` stand-in, PowerShell for the Windows form), for the WSL and Windows forms, with and without Windows Terminal, with a project path holding a space and an apostrophe, and with `skip_permissions` both ways, finding the argument list and working directory each receives. Done when: those tests pass, and a test where `bash` is present finds a function defined after the interactive guard in `~/.bashrc` reachable through `bash -lic` and not through `bash -lc`. **Planned 2026-11-17** (plan review P1).
- [x] Publish all or nothing: render every icon and save every link under a temporary name first, move them into place only when all succeeded, and remove stale links and icons only after that; on any failure exit 1 with the reason, remove the temporary files and leave every existing link and icon as it was. Done when: a test with a corrupt project icon and one with an existing link that cannot be replaced (read-only) each find exit 1, the earlier links and icons unchanged and no temporary file. **Planned 2026-11-17** (plan review P2).
- [x] Run `-Remove` before anything only a write needs (the profile, the icon, Python, WSL), working from the path given even when the folder is gone. Done when: a test removes with a malformed profile, a missing icon and a failing `wsl.exe`, and a second `-Remove` reports nothing removed and exits 0. **Planned 2026-11-17** (plan review P2).
- [x] Keep every failure on screen until Enter: the agent command in WSL becomes `<agent> || { echo '<Agent> did not start: the reason is above. Press Enter to close.'; read -r _; }`, and without Windows Terminal the WSL link runs PowerShell, which runs `wsl.exe` and on a WSL failure says so and waits for Enter (as the campaign links do). Done when: executing the fallback link with a failing `wsl.exe` stand-in prints the message and waits for input, and running the bash command where the agent is missing prints its message and waits. **Planned 2026-11-17** (plan review P2).
- [x] Add `kits/launchers/templates/scripts/tests/test_project_shortcuts.py` holding the tests above, every console child started with `CREATE_NO_WINDOW`, every link in a scratch folder, `wsl.exe` replaced by the stand-in `test_shortcut.py` uses, skipped where `pwsh` is missing. Done when: the suite passes on Windows and opens no window.
- [x] Commit: `launchers: desktop links that open the project in an agent`

**Test checkpoint:** `python -m unittest discover -s kits/launchers/templates/scripts/tests -p "test_project_shortcuts.py"` ends `OK` on Windows; changing `bash -lic` to `bash -lc` in the script makes it fail, as does deriving the identity without the distro.

> **Verified:** 2026-11-17 | §5 | 1dd6c56e908666ab8e9eac1b696de4e1cb46d1fa
> **Review:** `docs/reviews/d07-t01-s5.json`

## 6. Declared links that run a command or open a URL

> **Started:** 2026-11-17T19:10Z

The third link of the shape differs per project: a WordPress project opens its dashboard through a command (`T02`), a Laravel or static project opens its site. Both are entries in the profile's `links`, written by the same script.

**Phase:** 8
**Needs:** windows-host
**Surface:** no

**Build order:**

1. Write the command form. Done when: a `run` entry is read back with the arguments in Inputs.
2. Write the URL form and extend removal. Done when: the checkpoint passes.

- [x] Write `<Title> (<label>).lnk` in `scripts/project-shortcuts.ps1` for each `run` entry of a project in WSL, in the command-link form of Inputs, with `<what failed>` reading `<label> did not start`, each argument single-quoted for PowerShell with quotes doubled. Done when: the test reads the link back and runs its target and arguments, windowless, against the stand-in, which records exactly `-d <distro> --cd <linux path> --exec bash -lc <command with the failure tail>`. **Corrected 2026-11-17:** also, a stand-in `wsl.exe` that fails leaves the window open with `<label>: WSL could not open the project (exit <n>): the reason is above. Press Enter to close.` until Enter, read with the suite's `Interactive` helper (the Inputs form handles a WSL failure, which the item did not test). **Planned 2026-11-17 (plan review 1):** the label inside Bash's single-quoted message is quoted for Bash first (each `'` written `'\''`), then the whole for PowerShell, and a test runs the generated Bash command with a real Bash (the suite's `find_bash`) for a label holding an apostrophe, on success (no message, exit 0) and on failure (the message whole, then the wait). Cheaper substitute: `wt.exe ... bash -lc`, where a failure closes the window before it can be read.
- [x] Write the `run` form for a project on a Windows drive: `pwsh.exe -NoLogo -NoProfile -Command` running the command in the project folder, with the same wait for Enter on a non-zero exit. Done when: a test reads it back, runs it and finds the command ran in the project folder; a command that exits non-zero, or throws, shows `<label> did not start: the reason is above. Press Enter to close.` and the window stays open until Enter, and one that succeeds closes without waiting. **Corrected 2026-11-17:** it said "a failing command leaves the stand-in's record of the wait", which names nothing a test can read.
- [x] Write each `url` entry as a link whose target is `rundll32.exe` with the arguments `url.dll,FileProtocolHandler <url>`, so no console window appears. Done when: the test reads the target and the URL back, and nothing in the suite starts the link.
- [x] Render each entry's icon with `campaign-icon.py overlay <icon> <mark>` into `launcher-<label slug>-<key>.ico`, the slug being the label in lower case with every run of other characters as one hyphen. Done when: two entries with different marks get two icon files, each byte for byte what `campaign-icon.py overlay` renders for the project icon and that entry's own mark (so a swapped or invalid icon fails), and each link's `IconLocation` read back names its own icon. **Corrected 2026-11-17 (plan review 1):** it said only "two icon files".
- [x] Delete, on every run, a link carrying this project's mark that the profile no longer declares, with its icon. Done when: a test writes two declared links and an agent link, drops one entry from the profile, runs the script again and finds that link and its icon gone, and the other declared link, the agent link and both their icons kept. **Corrected 2026-11-17 (plan review 1):** it checked only the link.
- [x] Add a `links` row to the doctor's `launchers` branch in `forge.py`: the number of agent and declared links the profile yields. Done when: a test reads the count for a profile with two agents and one entry as 3.
- [x] Commit: `launchers: declared links that run a command or open a URL`

**Test checkpoint:** `python -m unittest discover -s kits/launchers/templates/scripts/tests -p "test_project_shortcuts.py" -k declared` ends `OK` on Windows; dropping the `|| { ...; read -r _; }` tail from the command makes it fail.

> **Verified:** 2026-11-18 | §6 | bfd6ce45246ad29989d1fd843c2a023e843e28fb
> **Review:** `docs/reviews/d07-t01-s6.json`

## 7. Campaign links under the project's title, icon read from a share

> **Started:** 2026-11-18T06:32Z

**Corrected 2026-11-18 (re-plan):** started 2026-11-17T23:20Z (written then as 2026-11-18T01:40Z, the local clock read as UTC); re-planned after its first review chain (plan review, round, completion review and 16 reconciliations, kept in `docs/reviews/07-launchers/D07-T01-s7-chain1.md`) showed one checked item promising two things no run can both do: that the old key's badges always go, and that another distro's badge never goes. The old script gave one Linux path the same key in every distro and recorded nothing that names the distro, so this re-plan keeps the old-key badges while another distro has the path, states the journal and recovery the chain built, and corrects the `title` wording below.

Two faults in the campaign link, both found on the first project that used the whole shape. Its name is the folder's (`<folder> <Runner> campaign`) while the other links carry the title, and its icon cannot be read from a `\\wsl.localhost` share.

**Phase:** 8
**Needs:** windows-host
**Surface:** no

**Build order:**

1. Fix the icon path with a test that fails first. Done when: the new test fails on the old line and passes on the new.
2. Name the link by the title. Done when: the checkpoint passes.

- [x] Add a test to `kits/unattended/templates/scripts/tests/test_shortcut.py` that passes `-Icon` as a provider-qualified path (`Microsoft.PowerShell.Core\FileSystem::<scratch>\icon.png`, which is what `Resolve-Path` returns for a file on a share). Done when: it fails with the renderer unable to open the file when `$brand` is resolved with `.Path`. **Corrected 2026-11-18 (plan review 2, P3):** it said "fails on the current script", which describes an earlier revision; the mutation is the evidence.
- [x] Change `$brand` in `kits/unattended/templates/scripts/unattended-shortcut.ps1` to `(Resolve-Path -LiteralPath $Icon).ProviderPath`, with a comment saying why. Done when: the test above passes. Cheaper substitute: stripping the prefix with a string replace, which breaks on the next provider.
- [x] Resolve `-Project` the same way in `unattended-shortcut.ps1` (`$Project` kept `$found.Path`, with the same prefix for a project on a share that is not a WSL one). Done when: a test passes `-Project` as `Microsoft.PowerShell.Core\FileSystem::<project>` and the link's mark and the `wslpath` call carry the plain path; it fails on `.Path`. **Corrected 2026-11-18:** added; the item above named only the icon, and the project path has the same fault.
- [x] Add `launchers.py title [--root]` to `kits/launchers/templates/scripts/lib/launchers.py` (`campaign_title`): it prints the profile's title as JSON when the profile loads; prints `null`, exit 0, when `.conclave/launchers.json` is missing or its `title` is `null` (the kit's template as installed), every other key still checked; and refuses any other profile with `load_profile`'s message, exit 1. **Corrected 2026-11-18 (round 1):** it said "prints nothing", while the transport item below and the build print JSON `null`; and an unset title skipped every other check, so a truncated profile passed. Done when: `test_launchers.py` holds each of the four cases (titled, missing, unset title, refused). **Corrected 2026-11-18:** added. The item below said a refused profile stops the script, but the unattended kit brings the launchers kit, whose template ships `title: null`, which `load_profile` refuses: every install that has not yet set a title would lose its campaign links (the run file of 2026-11-17 recorded it at the operator's stop).
- [x] Name each campaign link `<title> <Runner> campaign.lnk` when `scripts/lib/launchers.py title` prints a title, and by the folder's name as now when it prints `null`; a profile it refuses stops the script with the loader's message and writes nothing; a profile present with no `scripts/lib/launchers.py` beside the script is refused with the install command. Done when: one test per case (titled, no profile, unset title, refused, loader missing) reads the link names back, or finds none. **Corrected 2026-11-18:** it read the title through `show`, which refuses the unset title every fresh install carries. **Corrected 2026-11-18 (re-plan):** it said "when it prints nothing"; `title` prints JSON `null` for no title, as the item above says.
- [x] Remove, on a run that renames, the link this project wrote under the old name, found by its mark as `Get-Owned` already does. A link of this project's that the run does not write (a runner dropped from the run profile) goes the same way, with its badge, as `project-shortcuts.ps1` already does for its links. Done when: a test writes the link without a profile, adds the profile, runs again and finds one link, under the title; a second test drops a runner and finds its link and badge gone and the others kept. **Corrected 2026-11-18:** the dropped runner added, one rule for both.
- [x] Keep `start_command` in `scripts/unattended-run.py` and the link's arguments equal, as the existing test holds. Done when: that test still passes unchanged.
- [x] Give a project in WSL one identity in `unattended-shortcut.ps1`, whatever form `-Project` takes: the mark and the badge key are built from `\\wsl.localhost\<distro>\<linux path>`, so `/home/x/demo` in Ubuntu and in Debian are two projects; a Linux path with `-Remove` needs `-Distro` and is refused without it; the mark the old script wrote for the same `-Project` (the form as typed) still counts as this project's (an old Linux-path mark only when its link starts the run in this project's distro), and the badges its own links show under the old key go with the rest when no other distro has the project's Linux path in any letter case, asked of WSL; while one does, or WSL cannot say, they stay, since the old key was that path's alone in every distro. Done when: a test with two installed projects of different titles, both `-Project /home/x/demo`, one per distro, sharing the desktop and icon folders, renames one, drops a runner from it and removes it, and the other's links and badges keep their bytes; a second test seeds a link and badge under the old mark and key in a project no other distro has, runs again and finds only the new ones; a third finds the link migrated and the old badges kept while another distro has the path in another letter case, a fourth the same while WSL cannot say, and a fifth the same while this distro has the path spelt otherwise too (`/home/x/Demo` and `/home/x/demo` are two projects). **Planned 2026-11-18 (plan review 2, P1 and P3):** the old key also collides within one distro, and only the badges stay. **Corrected 2026-11-18 (re-plan):** it said the old key's badges go with the rest, always, which can remove a badge another distro's old link still shows. **Planned 2026-11-18 (plan review 1, P1):** the new stale sweep would otherwise delete another distro's links.
- [x] Refuse, before anything is written, a run whose link name is held by a file this project does not own (another project's link with the same title and runner, or a folder). Done when: a test puts another project's link at the second runner's name and finds exit 1 naming it, and both projects' links and badges byte for byte as before. **Planned 2026-11-18 (plan review 1, P1):** `Move-Item -Force` replaced it.
- [x] Write in two steps: every badge and every link to its temporary name first, then every move, then the stale sweep, so a failure before the moves leaves the previous links, badges and no temporary file. Done when: a test with a titled installation blocks the second destination, finds the old links and badges as they were and no `.tmp` file, then clears it, runs again and finds exactly the new set. **Planned 2026-11-18 (plan review 1, P1).**
- [x] Prove the provider-path icon end to end. Done when: after a rename with `-Icon` given provider-qualified, each titled link's badge is byte for byte what `campaign-icon.py badge` renders for that icon and runner, and each link run against the stand-in hands WSL `start_command(agent)`. **Planned 2026-11-18 (plan review 1, P2).**
- [x] Prove the title's transport and the refusals. Done when: a title `東京` names the links exactly; a refused profile and a missing loader each give exit 1 with the loader's message or the install command, against an existing installation whose links and badges keep their bytes; and `-Remove` works with the launcher profile malformed and with its loader missing. **Planned 2026-11-18 (plan review 1, P2):** `title` prints ASCII JSON, as `show` does. **Corrected 2026-11-18 (build):** the CJK title found that `WScript.Shell` saves and opens a `.lnk` through the ANSI code page, so it could neither save a link named `東京 ...` nor read its mark: links are saved under an ASCII temporary name (`campaign-<runner>-<key>.<pid>.tmp.lnk`) and moved to their own, and marks are read through `Shell.Application`, marked as a workaround in the script. **Corrected 2026-11-18 (round 1):** `Shell.Application` reads arguments cut at 259 characters and `WScript.Shell` still stored the arguments in ANSI, so both went: every link is written and read through IShellLinkW (`kits/launchers/templates/scripts/lib/ShellLink.cs`), with no workaround left. `project-shortcuts.ps1` (§5, §6) has the same fault and is filed as §9.
- [x] Keep the default icon folder `%LOCALAPPDATA%\<folder>`, never the title. Done when: a test with an isolated `LOCALAPPDATA` and two runners renames, then removes, and finds no badge left in that folder and no folder named by the title. **Planned 2026-11-18 (plan review 1, P2).**
- [x] Keep a journal for each run that changes links, `<icon folder>\campaign-<key>.<pid>.journal.json`, written whole (a temporary file moved over it) before each step (`writing`, `swapping`, `committed`), naming the run's start time and every temporary file, move and file moved aside. Done when: a test stops a rename while swapping and finds any next run, even a refused one, puts the previous set back byte for byte; one stopped after committing finds the next run removes what was moved aside; one stopped part way through recovery finds the run after finishes it. **Corrected 2026-11-18 (re-plan):** built at the first chain's reconciliations 6 to 11; stated here as the contract. **Corrected 2026-11-18 (completion review 2):** the journal lives in `%LOCALAPPDATA%\conclave-unattended`, not the icon folder: round 1 found runs given different icon folders missed each other's journals, so every run of the user keeps them in one place, and each journal records the folders its own run worked in.
- [x] Play a journal only when its run is no longer going (no process with its id started when it says) and every path it names is this project's own file in the desktop or icon folder, by a run's own names; take a file out only when it is this project's. Done when: tests find a journal of a live run left alone, one whose id another process has (or this run itself) played, a planted one naming any other file refused with its files untouched, and another project's link at a vacated name kept.
- [x] Keep the journal while anything it names cannot be done yet (a file held open, a name another file holds), refuse an install while one is kept, and have `-Remove` mark a stopped run's journal `committed` before it deletes anything, so nothing removed comes back. Done when: tests hold a moved-in link, an original, a temporary link and an old-key badge open in turn and find exit 1 with the journal kept, then the next run finishing it; and a refused install after a held `-Remove` restores nothing.
- [x] Write and read every link through IShellLinkW (`kits/launchers/templates/scripts/lib/ShellLink.cs`), and spell a Windows path long (`ShellPath.Long`) before it becomes a mark or a key. Done when: a CJK title names the links and reads back whole; a project handed in by its 8.3 short name is the same project; the suite passes with `TEMP` set to an 8.3 form. **Corrected 2026-11-18 (re-plan):** found at the first chain's round 1 and its CI red.
- [x] Hold an exclusive lock for the project (`<icon folder>\campaign-<key>.lock`, opened with no sharing for the run's life, so the system frees it when the process ends) for every run that changes links or plays a journal; a second run of the project waits a few seconds and then refuses, naming the lock. Done when: a test holds the lock and finds a valid install and `-Remove` each exit 1 with every link and badge byte for byte, and both succeed once it is released. **Planned 2026-11-18 (plan review 2, P1).** **Corrected 2026-11-18 (completion review 2):** the lock is `%LOCALAPPDATA%\conclave-unattended\campaign-<key>.lock`, not in the icon folder, for the same reason; no parameter moves it.
- [x] Count a journal that cannot be read or names anything but this project's files as kept: an install refuses and `-Remove` fails, both naming it, and its files stay byte for byte. Done when: a test with a valid distro finds exit 1 for each and the journal, backups, links and badges unchanged. **Planned 2026-11-18 (plan review 2, P1).**
- [x] Find this project's links by their mark among every `.lnk` in the desktop folder, whatever their name. Done when: a test renames an owned link, finds a reinstall leaves one link per runner and `-Remove` takes the renamed one with its badge, and a foreign link stays. **Planned 2026-11-18 (plan review 2, P2).**
- [x] Make `-Remove` one journaled change: every owned link is moved aside, then every badge, and only then deleted, so a stop leaves the set whole or no link without its icon, and the next run puts it back or finishes it. Done when: a test stops a two-runner `-Remove` after its first move (a journal left in `swapping`) and finds the next run restores the whole set, and a test with a badge held open finds exit 1 with both links kept. **Planned 2026-11-18 (plan review 2, P2).**
- [x] Commit: `unattended: campaign links take the project's title and read an icon from a share`

**Test checkpoint:** `python forge.py check-all --only kit-unattended` and `python forge.py check-all --only kit-launchers` pass on Windows; restoring `.Path` on the icon line, or on the project line, makes its provider-path test fail; making `title` refuse an unset title makes the unset-title tests fail. **Corrected 2026-11-18:** the launchers kit's suite added, which now holds `title`.

> **Verified:** 2026-11-18 | §7 | 9d2cb9619651a116aef9997942d947f1253ea4e7
> **Review:** `docs/reviews/d07-t01-s7.json`

## 8. Operator page and `project-launchers` skill

> **Started:** 2026-11-19T07:47Z

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

## 9. Agent and declared links named outside the ANSI code page

`scripts/project-shortcuts.ps1` saves and reads every link through `WScript.Shell`, which goes through the ANSI code page: a title outside it (`東京`, probed 2026-11-18 while building §7) cannot be saved (`Unable to save shortcut "...\?? x.lnk"`), and a link of that name reads back with an empty description, so its mark is never found and `-Remove` and the stale sweep miss it. §7 fixed the campaign links this way; this section does the same for the agent and declared links of §5 and §6.

**Phase:** 8
**Needs:** windows-host
**Surface:** no

**Build order:**

1. Write the failing test. Done when: it fails on the current script with the save error.
2. Write and read links through `scripts/lib/ShellLink.cs` (IShellLinkW). Done when: the checkpoint passes.

- [ ] Add a test to `kits/launchers/templates/scripts/tests/test_project_shortcuts.py` with the title `東京`, one agent and one declared `url` link. Done when: it fails on the current script, and after the fix finds `東京 (Claude).lnk` and `東京 (<label>).lnk`, each with the target and arguments §5 and §6 name.
- [ ] Write each link in `kits/launchers/templates/scripts/project-shortcuts.ps1` (line 232) through `[Conclave.ShellLink]::Write` from `kits/launchers/templates/scripts/lib/ShellLink.cs` (IShellLinkW, built in §7), loaded with `Add-Type -Path`, in place of `WScript.Shell`. Done when: the test above writes both links, each read back through `[Conclave.ShellLink]::Read` with its name, target, arguments, mark and icon whole, and no `.tmp` file is left. Cheaper substitute: refusing a non-ANSI title in `load_profile`, which takes a valid title from the owner.
- [ ] Read each link's mark (lines 86, 149, 181) through `[Conclave.ShellLink]::Read`, as `Get-Mark` in `kits/unattended/templates/scripts/unattended-shortcut.ps1` does, and refuse with the install command when `scripts/lib/ShellLink.cs` is missing. Done when: a second run of the test leaves the same two links (its own, not refused as another's), `-Remove` deletes both and their icons, and a test without the file finds exit 1 and nothing written. **Corrected 2026-11-18:** it named `Shell.Application`, which §7's round 1 found reads arguments cut at 259 characters.
- [ ] Commit: `launchers: agent and declared links take a title outside the ANSI code page`

**Test checkpoint:** `python forge.py check-all --only kit-launchers` passes on Windows; restoring `WScript.Shell` for the link write or the mark read makes the CJK test fail.

## Verification

- In a scratch project in WSL with a title, an icon, two agents and one `url` link, `pwsh scripts/project-shortcuts.ps1` writes three links into a scratch folder, each read back as this file describes, and `-Remove` leaves the folder empty.
- `python forge.py check-all --only kit-launchers` and `python forge.py check-all --only kit-unattended` pass, and the CI run of the stamping commit is green.
- `python forge.py doctor <project> launchers` reports `profile`, `renderer` and `links`.
- `python scripts/todo-graph.py validate` and `python scripts/todo-graph.py plan --check` pass.
