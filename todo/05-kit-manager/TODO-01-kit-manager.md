---
schema_version: 1
id: kit-manager
domain: 05-kit-manager
status: active
title: "TODO-01 -- Kit Manager"
---

# TODO-01 -- Kit Manager

> **Goal:** From VS Code, the operator can see which Conclave-SDK kits a workspace has and how healthy they are, install any kit (previewed file by file before anything is written), update the installed kits, and set up a new repository, all by running `forge.py` from the SDK source the extension resolves (bundled, local checkout, or a pinned GitHub commit). The extension never copies kit files itself and never reimplements forge's rules: every write is forge's, and every list it shows is forge's JSON.

> **Current state:** Measured 2026-10-16 at Conclave-SDK `97cca1d`. No extension code exists. `forge.py` already has every operation this file needs, each printing JSON: `kits` (`{"kits": ["base", "laravel", "reviewer", "todo", "wordpress"]}`), `kit <target> <kit> [--agent all|agy|gemini|claude|codex] [--host pressable|wpcom] [--dry-run]` (`{target, kit, agent, dry_run, installed, updated, preserved, merge_needed}`), `sync <target> [--kit K] [--include-scripts] [--agent] [--mode]` and `init <target> [--kit K] [--agent] [--mode isolated|copy|hybrid|inherit] [--no-scripts] [--with-todo] [--force]` (both `{target, mode, agent, written, skipped, kits: [per-kit summary]}`), `check <target>` (entry docs, `has_*` flags and per-agent skill lists) and `doctor <target> [laravel|wordpress|reviewer|todo]` (`{target, kit, missing_or_setup_required, checks: [{name, status, detail}]}` with status `ok`, `missing`, `setup_required` or `unexpected`). `init` on an existing folder skips existing entry docs unless `--force`.

## Inputs

- `docs/plans/2026-10-16-vscode-extension.md`: requirements R24 and R27 to R31.
- `forge.py` (`kits`, `kit`, `sync`, `init`, `check`, `doctor`) and `README.md` "Importing into a New or Existing Project": the operations and their rules (additive, never overwrites project files).
- `design/SPEC.md` §9 to §11 (from `D00 T01 §3`): the Kits view, the install and update dialogs, health detail and the new repository flow.
- Every `npm`, `npx` and `node` command in this file runs in `extensions/vscode/`.
- -> XREF: D02 T01 §9 -- the forge runner and summary parser every section here calls
- -> XREF: D02 T01 §10 -- the per-kit workspace state the view and dialogs read
- -> XREF: D03 T01 §10 -- the reviewer editor's no-pin and old-dispatcher states call §1 and §2
- -> XREF: D04 T01 §1 -- acceptance walks every kit operation
- -> XREF: D06 T01 §1 -- the feature sections share this container, its current folder and its badge
- -> XREF: D00 T01 §3 -- `design/SPEC.md` is the Fidelity source of §5 to §9
- -> XREF: D02 T01 §11 -- the parity fixtures and `expectParity` every surface section here asserts

## Outcome

**Corrected 2026-10-20:** Conclave-SDK gained a sixth kit, `automations` (`8841942`), and the todo kit now seeds `.claude/settings.json` with the run guard's Stop hook (`688314c`). The view still lists every kit `forge.py kits` returns, now six; the protected files gain the project-owned `.conclave/automations/tasks.json` and `README.md` and `.claude/settings.json`, which forge never overwrites.

- The Conclave view in the Activity Bar lists every kit `forge.py kits` returns for the current folder (the only folder in a one-folder window; in a multi-root workspace the active editor's folder, which a Switch folder action changes) as installed, partly installed or not installed, with a health badge, read from forge.
- Installing a kit shows forge's `--dry-run` file list first, takes the agent choice and (WordPress) the host, writes only after confirmation, and lists what forge installed; updating runs `forge.py sync` and lists what it updated; health shows every `doctor` check; a new repository is set up with `forge.py init` and opened.
- Protected project files (`AGENTS.md`, `GEMINI.md`, `CLAUDE.md`, `CODEX.md`, `.conclave/reviewers.toml`, `.conclave/automations/tasks.json`, `.conclave/automations/README.md`, `.claude/settings.json`, `todo/`, `docs/`) are byte-identical before and after every install and update, proved by hash.

**Adjacency:** list=applicable @ D05 T01 §5; document=not-applicable (forge writes the files; the extension prints nothing); settings=not-applicable (the SDK source and Python settings are consumed in D02 T01 §2 and D02 T01 §7); reporting=applicable @ D05 T01 §8; notifications=not-applicable (single local user; results show in the view and output channel); permissions=applicable @ D05 T01 §1; audit=applicable @ D05 T01 §1; exchange=not-applicable (kits come only from the SDK source); reverse=applicable @ D05 T01 §2

**Adjacency rationale:** The list is the Kits view (§5), which finds every kit without knowing its name. Reporting is the health detail (§8) over `doctor` and `check`. Permissions are workspace trust (no forge run in an untrusted workspace) and the confirmation before every write, owned by §1 and reused by §2 and §4. Audit is the output channel line for every forge run (argv, source label and SHA, exit code, forge's lists), owned by §1. Reverse: forge has no uninstall, so the reverse of an install or update is the operator's git (every change forge makes is a file in the workspace), and §2's protected-file hash check proves nothing outside the kit's own files moved. An uninstall command is out of scope until forge has one.

## Implementation Order

| Order | Section | Deliverable | Depends On | Status |
| ----- | ------- | ----------- | ---------- | ------ |
| 1 | §1 | Kit install with dry-run preview | D02 T01 §9, D02 T01 §10 | [ ] |
| 2 | §2 | Kit update through forge sync | D02 T01 §9, D02 T01 §10 | [ ] |
| 3 | §3 | Kit health from forge check and doctor | D02 T01 §9 | [ ] |
| 4 | §4 | New repository setup through forge init | D02 T01 §9 | [ ] |
| 5 | §5 | Conclave Activity Bar view with the Kits tree | D02 T01 §10, D03 T01 §1 | [ ] |
| 6 | §6 | Kit installer in the side bar | §1, §5 | [ ] |
| 7 | §7 | Kit update flow | §2, §5 | [ ] |
| 8 | §8 | Kit health detail | §3, §5 | [ ] |
| 9 | §9 | New repository wizard | §4, §5 | [ ] |

## 1. Kit install with dry-run preview

Any kit can be installed into a workspace folder (plan R28). This section runs `forge.py kit <folder> <kit> --dry-run` with the chosen `--agent` (and `--host` for WordPress) to get forge's exact list of files it would install and keep, asks the operator to confirm that list, then runs the same command without `--dry-run`, checks the protected files did not change, and re-reads the folder's kit state. It owns workspace trust and the audit line for every forge run.

**Phase:** 1
**Needs:** none
**Surface:** no

**Build order:**

1. Write `extensions/vscode/src/host/kitInstall.ts` with preview, confirm and run. Done when: an integration test with a fake SDK previews, confirms and installs a kit, and cancelling writes nothing.
2. Add the protected-file guard and the state refresh. Done when: the test proves the protected files are unchanged and the view state updates.

- [ ] Build the argv in `extensions/vscode/src/host/kitInstall.ts` from the D02 T01 §9 runner: `kit <folder> <kit> --agent <agent>`, plus `--host <host>` only for `wordpress`, plus `--dry-run` for the preview. Done when: unit tests assert the argv for `todo` and for `wordpress --host wpcom`. Cheaper substitute: passing `--host` to every kit.
- [ ] Refuse every forge run when `vscode.workspace.isTrusted` is false, before any process starts. Done when: an integration test with trust disabled starts no process. Cheaper substitute: relying on the manifest flag alone.
- [ ] Run the preview and return forge's `installed`, `preserved` and `merge_needed` lists unchanged. Done when: a unit test over a recorded `--dry-run` summary returns the same lists. Cheaper substitute: computing the file list from the kit's templates in TypeScript.
- [ ] Refuse to run when the preview's `merge_needed` is not empty, showing those paths, since forge cannot add them without a merge. Done when: a fake summary with `merge_needed` gets the refusal. Cheaper substitute: running anyway.
- [ ] Hash the protected files that exist (`AGENTS.md`, `GEMINI.md`, `CLAUDE.md`, `CODEX.md`, `.conclave/reviewers.toml`, `.conclave/automations/tasks.json`, `.conclave/automations/README.md`, `.claude/settings.json`, every file under `todo/` and `docs/`) before the real run and compare after, reporting any change as a defect. Done when: an integration test asserts no change after installing `todo` into a folder that already has `AGENTS.md`. Cheaper substitute: trusting forge's additive rule unchecked.
- [ ] Log every forge run (argv, source label and SHA from D02 T01 §7, exit code, forge's lists) to the "Conclave" output channel. Done when: the channel shows one block per run in the test. Cheaper substitute: logging only failures.
- [ ] Refresh the folder's kit state from D02 T01 §10 after the run. Done when: the installed kit shows `installed` without a reload. Cheaper substitute: asking the operator to reload the window.
- [ ] Write `extensions/vscode/test/integration/kitInstall.test.ts` with a fake SDK whose `forge.py` replays recorded summaries. Done when: it passes and fails when the protected-file check is removed. Cheaper substitute: tests of the argv only.
- [ ] Commit: `extension: install a kit from the SDK source with a dry-run preview`

**Test checkpoint:** `cd extensions/vscode && npm run test:integration -- --grep kitInstall` passes, and fails when cancelling the preview still runs forge without `--dry-run`.

## 2. Kit update through forge sync

Installed kits are updated with `forge.py sync <folder>` (plan R29), which refreshes the skills, rules and subagents of every kit the folder has and, with `--include-scripts`, their existing scripts and `bin/` files, and adds any kit file that is missing; it never changes an existing entry doc, `docs/` or `todo/` file, the pin or other project files. **Corrected 2026-10-16:** it said sync never touches entry docs, `docs/`, `todo/` or the pin; measured, sync adds a missing kit file in those places too (`todo/plan.json`, `.conclave/reviewers.toml`) and writes only files that are missing or differ. The reviewer editor's no-dispatcher and old-dispatcher states call this with `--include-scripts`. It owns the reverse rule: the operator's git is the undo, and the protected-file hash proves nothing else moved.

**Phase:** 1
**Needs:** none
**Surface:** no

**Build order:**

1. Write `extensions/vscode/src/host/kitSync.ts`. Done when: the confirmation names the source, the argv and sync's scope, and cancelling runs nothing.
2. Run, guard, report and refresh. Done when: an integration test on an old-dispatcher workspace lists `scripts/review-dispatch.py` as updated and the protected hashes are unchanged.

- [ ] Build the argv `sync <folder>` with optional `--include-scripts` and `--agent` in `extensions/vscode/src/host/kitSync.ts`. Done when: unit tests assert both forms. Cheaper substitute: `forge.py kit`, which leaves an old file in place.
- [ ] Show a modal confirmation naming the source label, the argv, the kits the folder has (from D02 T01 §10) and that sync adds missing kit files but never changes an existing entry doc, `docs/`, `todo/` or `.conclave/reviewers.toml` (drawn in the mockup's `update-confirm` overlay). Done when: cancelling starts no process. Cheaper substitute: "Update kits?" with no scope.
- [ ] Reuse §1's protected-file hash check around the run. Done when: the integration test asserts the pin and `AGENTS.md` hashes are unchanged. Cheaper substitute: no check.
- [ ] Parse forge's `kits` list and return `updated` and `installed` per kit. Done when: the test sees `scripts/review-dispatch.py` under the reviewer kit's updated list. Cheaper substitute: "Done" with no list.
- [ ] Report a non-zero exit with forge's stderr tail and leave the state unchanged. Done when: a failing fake `forge.py` shows its error. Cheaper substitute: ignoring the exit code.
- [ ] Refresh the folder's kit state and, when the reviewer editor is open, its D02 T01 §3 classification. Done when: the old-dispatcher workspace reports `ready`. Cheaper substitute: asking the operator to reopen.
- [ ] Write `extensions/vscode/test/integration/kitSync.test.ts` with a fake SDK and the `extensions/vscode/test/fixtures/workspaces/old-dispatcher/` workspace. Done when: it passes and fails when the hash check is removed. Cheaper substitute: argv tests only.
- [ ] Commit: `extension: update installed kits through forge sync`

**Test checkpoint:** `cd extensions/vscode && npm run test:integration -- --grep kitSync` passes, and fails when cancelling the confirmation still starts forge.

## 3. Kit health from forge check and doctor

> **Started:** 2026-10-20T16:40:00Z

The operator sees what is missing or needs setup for each installed kit (plan R30). This section runs `forge.py check <folder>` once and `forge.py doctor <folder> <kit>` for each installed kit (**Corrected 2026-10-20:** forge doctors every kit now: `automations` has its own checks and `base` the default ones; this said `todo`, `reviewer`, `laravel`, `wordpress`), and turns the results into per-kit health: `ok`, or the count of checks that are `missing`, `setup_required` or `unexpected`, with each check's name and detail verbatim. It never runs a check of its own.

**Phase:** 1
**Needs:** none
**Surface:** no

**Build order:**

1. Write `extensions/vscode/src/core/kitHealth.ts` turning `check` and `doctor` JSON into per-kit health. Done when: unit tests over recorded outputs give the expected counts.
2. Write `extensions/vscode/src/host/kitHealth.ts` running them. Done when: an integration test on the shipped workspace reports the reviewer kit healthy.

- [x] Implement `healthFrom(check, doctors)` in `extensions/vscode/src/core/kitHealth.ts`, keeping every check's `name`, `status` and `detail` verbatim and counting non-`ok` statuses per kit. Done when: unit tests over recorded `doctor` outputs for `reviewer` (all ok, and one `setup_required` CLI) and `wordpress` (setup required) pass. Cheaper substitute: a single red or green flag per kit.
  The recorded outputs come from `extensions/vscode/scripts/record-forge-fixtures.py`, which runs the reviewer and other doctors with PATH set to a folder of stub CLIs (every CLI, or every CLI but `agy`), so the fixtures are the same on any host. `healthFrom` also lists the agent-setup flags `forge check` reports as false.
- [x] Treat an unknown status value as not ok and show it verbatim. Done when: a unit test with `status: "stale"` counts it. Cheaper substitute: dropping unknown statuses.
- [x] Run `doctor` only for installed kits, one process at a time per folder, with a 30 second timeout each. Done when: an integration test with a slow fake doctor times out one kit and still reports the others. Cheaper substitute: running doctor for every kit, including ones not installed.
  Installed means installed or partly installed in `D02 T01 §10`'s kit state. A doctor that times out or is refused makes that kit `unavailable` with forge's reason; its process tree is ended (`§9`'s runner).
- [x] Refresh health after every install and update from §1 and §2, and on demand. Done when: the test sees health refreshed after an install. Cheaper substitute: health computed once at activation.
  Health is refreshed whenever the folder's kit state changes, which every install and update does (the kit state watches what forge writes), and by `refreshKitHealth` on demand; a computation that a refresh superseded runs again.
- [x] Write `extensions/vscode/test/unit/kitHealth.test.ts` over recorded outputs saved in `extensions/vscode/test/fixtures/forge/`. Done when: the tests pass and fail when `unexpected` is counted as ok. Cheaper substitute: one recorded output.
- [ ] Commit: `extension: kit health from forge check and doctor`

**Test checkpoint:** `cd extensions/vscode && npm run compile && node --test out/test/unit/kitHealth.test.js && npm run test:integration -- --grep kitHealth` passes, and fails when `healthFrom` ignores `setup_required`. **Corrected 2026-10-20:** was `npm test -- --test-name-pattern=kitHealth`, which does not filter on Node 24.14.1 (see `D02 T01 §2`).

## 4. New repository setup through forge init

A new repository is set up from VS Code (plan R31) with `forge.py init <folder>`, the kits chosen (base always comes with init), the agent and the provisioning mode, and opened afterwards. Init on a folder that already has entry docs skips them; the extension never passes `--force`, so an existing `AGENTS.md`, `GEMINI.md`, `CLAUDE.md` or `CODEX.md` is never overwritten.

**Phase:** 1
**Needs:** none
**Surface:** no

**Build order:**

1. Write `extensions/vscode/src/host/repoInit.ts`. Done when: an integration test sets up an empty folder with the todo kit and finds `AGENTS.md` and `todo/TODO-00-INDEX.md`.
2. Open the result. Done when: the test sees the new folder opened or added to the workspace as the operator chose.

- [ ] Build the argv `init <folder> --agent <agent> --mode <mode>` plus one `--kit <kit>` per chosen kit and `--host` for WordPress, never `--force`, in `extensions/vscode/src/host/repoInit.ts`. Done when: unit tests assert the argv and that no input produces `--force`. Cheaper substitute: an "overwrite" checkbox mapped to `--force`.
- [ ] Refuse a target that is inside another workspace folder's `.git` or is the SDK source folder itself. Done when: unit tests refuse both. Cheaper substitute: no target check.
- [ ] Show which entry docs already exist in a non-empty target and say they will be kept. Done when: an integration test on a folder with `AGENTS.md` lists it as kept and its hash is unchanged after init. Cheaper substitute: no warning.
- [ ] Parse forge's `written`, `skipped` and per-kit lists and return them. Done when: the test sees `AGENTS.md` under written for an empty folder. Cheaper substitute: "Done" with no list.
- [ ] Open the folder in a new window or add it to the workspace with `vscode.openFolder` or `updateWorkspaceFolders`, as chosen. Done when: both choices work in the integration test. Cheaper substitute: leaving the operator to find the folder.
- [ ] Write `extensions/vscode/test/integration/repoInit.test.ts` with a fake SDK and a temp folder. Done when: it passes and fails if `--force` ever appears in an argv. Cheaper substitute: argv tests only.
- [ ] Commit: `extension: set up a new repository through forge init`

**Test checkpoint:** `cd extensions/vscode && npm run test:integration -- --grep repoInit` passes, and fails when an existing `AGENTS.md` changes after init.

## 5. Conclave Activity Bar view with the Kits tree

The kits need a home in VS Code (plan R27). This section contributes a "Conclave" view container in the Activity Bar with a Kits tree view for the current folder (the only folder in a one-folder window; in a multi-root workspace the active editor's folder, which a Switch folder action changes): one top-level node per kit from `forge.py kits` with its state (installed, partly installed, not installed) and health badge, and inline and context actions that open §6 to §8. It also holds "Set up a new repository" as a view title action; "Open Reviewer Settings" sits in the Reviewers section (D06 T01 §4), one of the feature sections that share this container.

**Phase:** 2
**Needs:** none
**Surface:** yes
**Fidelity:** `design/SPEC.md` §9 Kits view and health; `design/screens/9-dark.png` and `design/screens/9-light.png`.
**Job:** Show the operator, at a glance, which Conclave-SDK kits the current repository has and which need attention, and start every kit action from one place.
**Treatment:** A native `TreeView` with codicons per state, a description column for the state and a badge count of kits needing attention on the view container.
**Chrome:** View title actions: Refresh, Update kits, Set up a new repository, and Switch folder in a multi-root workspace; the view description names the folder there; kit node inline actions: Install, Health.

**Build order:**

1. Contribute the view container and view in `extensions/vscode/package.json` and write `extensions/vscode/src/host/kitsView.ts`. Done when: the view lists every kit `forge.py kits` returns for the shipped workspace with their states.
2. Wire the actions and the badge. Done when: each action opens its flow and the badge counts kits needing attention.

- [ ] Contribute `viewsContainers.activitybar` `conclave` with the icon `media/conclave.svg` and `views.conclave` `conclave.kits` named "Kits" in `extensions/vscode/package.json`. Done when: the Activity Bar shows the Conclave icon and the Kits view. Cheaper substitute: a view inside the Explorer.
- [ ] Implement the `TreeDataProvider` in `extensions/vscode/src/host/kitsView.ts`: one top-level kit node per entry of `forge.py kits` for the current folder, no folder nodes, with the state from D02 T01 §10 and the health from §3. Done when: the integration test reads five kit nodes with the shipped workspace's states. Cheaper substitute: a hard-coded kit list.
- [ ] Resolve the current folder in `extensions/vscode/src/host/kitsView.ts`: the only folder, else the active editor's folder, else the last one picked, else the first; in a multi-root workspace set `TreeView.description` to its name and contribute `conclave.kits.switchFolder` (a quick pick of the workspace folders) as a view title action shown only when `workspaceFolderCount > 1`. Done when: an integration test on a two-folder workspace lists only the active editor's folder and switches on the pick. Cheaper substitute: every folder listed at once.
- [ ] Show the state as description text and a `ThemeIcon` (`pass`, `pie-chart`, `circle-large-outline`) and the health as a `FileDecoration` on the kit item's `resourceUri` (`conclave-kit:` scheme): the count of checks needing attention, at most two characters, coloured `list.warningForeground`, and none when every check is ok (`design/platform-audit.md`). Done when: the test reads the state, the icon and the decoration for a healthy, an unhealthy and an uninstalled kit. Cheaper substitute: the count appended to the description.
- [ ] Add inline Install on kit nodes that are not fully installed, inline Health on installed ones, and a context menu with both. Done when: each opens §6 or §8 with that kit. Cheaper substitute: actions only in the Command Palette.
- [ ] Add view title actions Refresh, Update kits (§7) and Set up a new repository (§9); Open Reviewer Settings belongs to the Reviewers section (D06 T01 §4). Done when: each runs its command from the view title. Cheaper substitute: a single refresh button.
- [ ] Set the view container's badge to the number of the current folder's kits needing attention, with a tooltip. Done when: a folder with a `setup_required` reviewer CLI shows badge 1. Cheaper substitute: no badge.
- [ ] Show an empty-folder message with "Set up a new repository" when a folder has no kit at all. Done when: an empty folder shows the message. Cheaper substitute: an empty tree.
- [ ] Write `extensions/vscode/test/integration/kitsView.test.ts`. Done when: it passes and fails when the kit list is hard-coded instead of read from forge. Cheaper substitute: a snapshot of labels only.
- [ ] Assert mockup parity for every scenario this section draws in `extensions/vscode/test/parity/conclave-activity-bar-view-with-the-kits.parity.test.ts` with `expectParity` from D02 T01 §11. Done when: the test passes and fails when one label, description, icon, badge, order or action differs from the mockup's fixture. Cheaper substitute: comparing by eye against the mockup.
- [ ] Commit: `ui: Conclave view with the Kits tree`

**Test checkpoint:** `cd extensions/vscode && npm run test:integration -- --grep kitsView` passes, and fails when the view lists a kit that `forge.py kits` did not return.

## 6. Kit installer in the side bar

Installing a kit needs choices and a preview (plan R28). The owner asked on 2026-10-16 for Install to open in the Conclave side bar. This section adds an "Install Kit" view under the Kits tree in the Conclave view container, shown while an install is open: the agent (all, agy, gemini, claude, codex) and, for WordPress, the host (pressable, wpcom), then forge's `--dry-run` list from §1 grouped as "will add" and "already present", with Install, Back and Cancel. After the run it shows forge's installed list and the protected-file hash check.

**Phase:** 2
**Needs:** none
**Surface:** yes
**Fidelity:** `design/SPEC.md` §10 Kit install and update; `design/screens/10-dark.png` and `design/screens/10-light.png`.
**Job:** Let the operator see exactly which files a kit will add to their folder before saying yes.
**Treatment:** A `WebviewView` (`conclave.install`) in the Conclave view container, revealed by a context key: a dropdown for the agent, radios for the WordPress host (locked once the site pin exists), forge's lists verbatim and the source label (bundled, local or `owner/repo@sha`), as drawn in the mockup's Install artboards.
**Chrome:** Step line (Choose, Preview, Installed) at the top; Install is the primary button; Back and Cancel at every step; a Close action on the view title.

**Build order:**

1. Contribute the view and write `extensions/vscode/src/host/kitInstallView.ts` with the choice step. Done when: WordPress asks for the host and other kits do not.
2. Show the preview and the result. Done when: the integration test sees the dry-run list before Install and the installed list after.

- [ ] Contribute `conclave.install` as a webview view in the `conclave` container, shown by the context key `conclave.installing`, and reveal it from the Kits Install action. Done when: Install on a kit node shows the view under the Kits tree. Cheaper substitute: a webview panel in the editor area.
- [ ] Ask for the agent with a dropdown defaulting to `all`. Done when: the test picks `claude` and the argv carries `--agent claude`. Cheaper substitute: always `all`.
- [ ] Ask for the WordPress host (pressable, wpcom) only when the kit is `wordpress`. Done when: installing `todo` asks no host question. Cheaper substitute: asking every kit.
- [ ] Show forge's `installed` list as "will add" and `preserved` as "already present", with the source label from D02 T01 §7, before Install. Done when: the preview for `todo` on an empty folder lists `scripts/todo-graph.py` under will add. Cheaper substitute: a count of files only.
- [ ] Show the `merge_needed` refusal from §1 with its paths. Done when: a fake summary with `merge_needed` shows the paths and no Install button. Cheaper substitute: a generic error.
- [ ] Cancel cleanly at every step with Cancel or the view's Close action, running nothing, and hide the view. Done when: the test cancels at each step and no process starts. Cheaper substitute: cancel only at the end.
- [ ] Show the installed list after the run and refresh the Kits view. Done when: the kit node flips to installed. Cheaper substitute: a toast with no list.
- [ ] Write `extensions/vscode/test/integration/kitInstallView.test.ts`. Done when: it passes and fails when the host step appears for `todo`. Cheaper substitute: no installer test.
- [ ] Assert mockup parity for every scenario this section draws in `extensions/vscode/test/parity/kit-installer-in-the-side-bar.parity.test.ts` with `expectParity` from D02 T01 §11. Done when: the test passes and fails when one label, description, icon, badge, order or action differs from the mockup's fixture. Cheaper substitute: comparing by eye against the mockup.
- [ ] Commit: `ui: kit installer in the side bar with forge's dry-run preview`

**Test checkpoint:** `cd extensions/vscode && npm run test:integration -- --grep kitInstallView` passes, and fails when Install runs without showing the preview.

## 7. Kit update flow

Updating kits (plan R29) starts from the view title or a no-dispatcher or old-dispatcher state. This section shows the folder's installed kits, an "Also update scripts and bin/ files" choice that maps to `--include-scripts` (preset on when started from a dispatcher state), the scope text from §2, and afterwards forge's updated and installed lists per kit.

**Phase:** 2
**Needs:** none
**Surface:** yes
**Fidelity:** `design/SPEC.md` §10 Kit install and update; `design/screens/10-dark.png` and `design/screens/10-light.png`.
**Job:** Bring a folder's kits up to the SDK source's version without touching the operator's own files.
**Treatment:** One confirmation with the scope text and the scripts choice, then a result list grouped by kit.
**Chrome:** The source label sits under the title; "Update" is the default button.

**Build order:**

1. Write `extensions/vscode/src/host/kitUpdateFlow.ts`. Done when: the confirmation shows the kits, the scripts choice and the scope text.
2. Show the result. Done when: the integration test sees per-kit updated lists.

- [ ] Show the folder's installed kits and the scope text from §2 in the confirmation. Done when: the test reads the three installed kits of the shipped workspace. Cheaper substitute: no list.
- [ ] Offer "Also update scripts and bin/ files", off by default and on when started from D03 T01 §10's dispatcher states. Done when: both entry routes set it as specified. Cheaper substitute: always on.
- [ ] Show forge's updated and installed lists per kit after the run, with "Nothing to update" when both are empty. Done when: an up-to-date folder shows that text. Cheaper substitute: an empty dialog.
- [ ] Show the defect message from §2 when a protected file changed. Done when: a fake forge that edits `AGENTS.md` shows it. Cheaper substitute: no message.
- [ ] Write `extensions/vscode/test/integration/kitUpdateFlow.test.ts`. Done when: it passes and fails when the scripts choice is ignored. Cheaper substitute: render test only.
- [ ] Assert mockup parity for every scenario this section draws in `extensions/vscode/test/parity/kit-update-flow.parity.test.ts` with `expectParity` from D02 T01 §11. Done when: the test passes and fails when one label, description, icon, badge, order or action differs from the mockup's fixture. Cheaper substitute: comparing by eye against the mockup.
- [ ] Commit: `ui: kit update flow`

**Test checkpoint:** `cd extensions/vscode && npm run test:integration -- --grep kitUpdateFlow` passes, and fails when starting from the old-dispatcher state leaves `--include-scripts` off.

## 8. Kit health detail

Health needs detail, not just a badge (plan R30). This section shows a kit's `doctor` checks from §3, one row per check with its status and forge's detail verbatim, grouped as needs attention first, with Refresh. A `setup_required` row keeps forge's hint text (for example `wordpress-connect step 3: ...`).

**Phase:** 2
**Needs:** none
**Surface:** yes
**Fidelity:** `design/SPEC.md` §9 Kits view and health; `design/screens/9-dark.png` and `design/screens/9-light.png`.
**Job:** Tell the operator exactly what a kit still needs in this folder, in forge's own words.
**Treatment:** Child nodes under the kit in the Kits tree, one per check, with a status codicon and the detail as tooltip and description.
**Chrome:** Refresh on the kit node; checks that are `ok` are collapsed under "All good (N)".

**Build order:**

1. Render the checks as child nodes in `extensions/vscode/src/host/kitsView.ts`. Done when: the reviewer kit shows its checks.
2. Order and group them. Done when: needs-attention checks come first and ok ones are grouped.

- [ ] Render one child node per `doctor` check with a codicon per status (`ok`, `missing`, `setup_required`, `unexpected`, other) and the detail verbatim. Done when: the integration test reads the reviewer kit's checks. Cheaper substitute: the count only.
- [ ] Put non-ok checks first and group ok checks under "All good (N)". Done when: a kit with one `setup_required` check shows it first. Cheaper substitute: forge's order with no grouping.
- [ ] Copy a check's detail to the clipboard from its context menu. Done when: the test reads the clipboard. Cheaper substitute: no copy.
- [ ] Refresh the kit's health from its node. Done when: fixing a fake cause and refreshing shows ok. Cheaper substitute: reload the window.
- [ ] Write `extensions/vscode/test/integration/kitHealthView.test.ts`. Done when: it passes and fails when `unexpected` renders as ok. Cheaper substitute: no test.
- [ ] Assert mockup parity for every scenario this section draws in `extensions/vscode/test/parity/kit-health-detail.parity.test.ts` with `expectParity` from D02 T01 §11. Done when: the test passes and fails when one label, description, icon, badge, order or action differs from the mockup's fixture. Cheaper substitute: comparing by eye against the mockup.
- [ ] Commit: `ui: kit health detail in the Kits tree`

**Test checkpoint:** `cd extensions/vscode && npm run test:integration -- --grep kitHealthView` passes, and fails when ok checks are listed before a `setup_required` one.

## 9. New repository wizard

Setting up a new repository (plan R31) needs a few choices. This section is a native multi-step input: pick or create the target folder, choose kits (base is always included), the agent, the provisioning mode (isolated by default; copy, hybrid, inherit), and for WordPress the host, then a summary of forge's command and the entry docs that will be kept, and finally open the folder as chosen.

**Phase:** 2
**Needs:** none
**Surface:** yes
**Fidelity:** `design/SPEC.md` §11 New repository setup; `design/screens/11-dark.png` and `design/screens/11-light.png`.
**Job:** Start a new project with the Conclave-SDK conventions in a minute, without a terminal.
**Treatment:** `showOpenDialog` for the folder, then `QuickPick` steps (kits as multi-select), then a confirmation naming the argv.
**Chrome:** Step counter and Back in every quick pick; Escape cancels and runs nothing.

**Build order:**

1. Write the steps in `extensions/vscode/src/host/repoInitWizard.ts`. Done when: each step's choices match the SPEC.
2. Confirm, run §4 and open the result. Done when: the integration test sets up a temp folder and opens it.

- [ ] Pick the target with `showOpenDialog` (folders only, create allowed). Done when: the test picks a temp folder. Cheaper substitute: a free-text path.
- [ ] Choose kits with a multi-select `QuickPick` from `forge.py kits`, base shown as always included and not unselectable. Done when: the test selects `todo` and `reviewer`. Cheaper substitute: a hard-coded list.
- [ ] Choose the agent (default `all`) and the mode (default `isolated`, with copy, hybrid and inherit described). Done when: the argv carries the choices. Cheaper substitute: fixed defaults.
- [ ] Ask the WordPress host only when `wordpress` is selected. Done when: no host step appears without it. Cheaper substitute: always asking.
- [ ] Show the summary with the argv and any existing entry docs listed as kept, then run §4. Done when: the test sees the summary before the run. Cheaper substitute: running straight after the last pick.
- [ ] Offer "Open in new window" and "Add to workspace" after success. Done when: both work in the test. Cheaper substitute: no open step.
- [ ] Support Back on every step without losing earlier choices. Done when: going back from mode keeps the kit selection. Cheaper substitute: restart on Back.
- [ ] Write `extensions/vscode/test/integration/repoInitWizard.test.ts`. Done when: it passes and fails when base can be deselected. Cheaper substitute: no wizard test.
- [ ] Assert mockup parity for every scenario this section draws in `extensions/vscode/test/parity/new-repository-wizard.parity.test.ts` with `expectParity` from D02 T01 §11. Done when: the test passes and fails when one label, description, icon, badge, order or action differs from the mockup's fixture. Cheaper substitute: comparing by eye against the mockup.
- [ ] Commit: `ui: new repository wizard`

**Test checkpoint:** `cd extensions/vscode && npm run test:integration -- --grep repoInitWizard` passes, and fails when the summary step is skipped.

## Verification

- On a scratch workspace, the Kits view shows every kit's real state; installing `todo`, updating with scripts, reading the reviewer kit's health and setting up a new repository each work end to end, with the protected files unchanged.
- `cd extensions/vscode && npm test && npm run test:integration` passes every suite named in §1 to §9.
- `python scripts/todo-graph.py validate` and `python scripts/todo-graph.py plan --check` pass.
