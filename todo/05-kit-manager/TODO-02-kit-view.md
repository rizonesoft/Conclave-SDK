---
schema_version: 1
id: kit-view
domain: 05-kit-manager
status: active
title: "TODO-02 -- Read-only Kit View and Agent Import"
---

# TODO-02 -- Read-only Kit View and Agent Import

> **Goal:** The extension shows, for the current folder, which Conclave-SDK kits are installed, partly installed or not installed and how healthy they are, read from forge against the SDK bundled in the extension, and says when a folder was set up with newer or older kits than it knows. It never installs, updates or sets up a repository: an `adopt-conclave` skill in the base kit does that through `forge.py` with the operator. A digest recorded with each extension version, and a stamp forge writes into each project, keep the two in step. Supersedes `TODO-01-kit-manager.md` (owner, 2026-10-20, `design/decisions.md`, Read-only kit view and agent import).

> **Current state:** Measured 2026-10-20 at Conclave-SDK `fb5e468`. Shipped and kept: the per-folder kit state from forge's dry runs (`D02 T01 §10`, `extensions/vscode/src/host/kitState.ts`) and kit health from `check` and `doctor` (`D05 T01 §3`, `extensions/vscode/src/host/kitHealth.ts`), both through `FolderWork` (`D02 T01 §19`). Shipped and to be removed: new repository setup (`D05 T01 §4`, `extensions/vscode/src/core/repoInit.ts`, `src/host/repoInit.ts`, `src/core/protectedFiles.ts`, `src/host/protectedFiles.ts`, the `setUpRepository` API and their tests), with `D05 T01 §10`'s special-file change. Kept in `forge.py`: `provision` refuses a target inside `.git` and init into the SDK folder itself (`25bcdc0`). forge records nothing about which SDK set up a project: `installed_kits` infers kits from files. The bundled SDK is `extensions/vscode/sdk/` with `sdk/SDK_COMMIT`, written by `D04 T01 §4`'s bundle step (not built yet); `bundledSource` in `extensions/vscode/src/core/sdkSource.ts` reads it.

## Inputs

- `design/decisions.md`, Read-only kit view and agent import (2026-10-20): the owner's decision and the defaults taken.
- `docs/plans/2026-10-16-vscode-extension.md`: R27 and R30 (kept, corrected), R38 to R41 (new); R28, R29, R31 and R32 dropped.
- `forge.py` (`kits`, `kit`, `sync`, `init`, `check`, `doctor`, `provision`, `apply_kit`, `installed_kits`) and `README.md` "Importing into a New or Existing Project".
- `design/SPEC.md` §9 (corrected by `D00 T01 §8`): the read-only Kits view and health.
- Every `npm`, `npx` and `node` command in this file runs in `extensions/vscode/`; the SDK's Python stays standard library only.
- -> XREF: D00 T01 §7 -- the mockup and decision this file builds
- -> XREF: D02 T01 §10 -- the per-kit state §3 extends and §5 shows
- -> XREF: D02 T01 §21 -- the GitHub source removal that leaves the bundled SDK as the source §2 and §3 compare with
- -> XREF: D03 T01 §10 -- the no-pin and dispatcher states show §7's agent request
- -> XREF: D04 T01 §4 -- the bundle step packages the SDK whose digest §2 records
- -> XREF: D06 T01 §1 -- the feature sections share §5's container, current folder and badge

## Outcome

- The Conclave view lists every kit `forge.py kits` returns for the current folder as installed, partly installed or not installed, with a health badge and each `doctor` check, and offers no install, update or new repository action.
- A folder whose `.conclave/kits.json` names newer kits than the bundled SDK says to update the extension; one with older kits says to ask the agent to update them; neither shows as partly installed.
- Changing a kit without recording a new extension version fails `python -m unittest discover -s tests`.
- `adopt-conclave` imports, updates and checks a project's kits through `forge.py`, previewing every write and checking the protected files with git afterwards.

**Adjacency:** list=applicable @ D05 T02 §5; document=not-applicable (forge writes the files; the extension prints nothing); settings=not-applicable (only `conclave.sdkPath` and `conclave.pythonPath` remain, consumed in D02 T01 §7 and D02 T01 §2); reporting=applicable @ D05 T02 §6; notifications=not-applicable (single local user; results show in the view and output channel); permissions=not-applicable (the view only reads; trust is D02 T01 §3's and the agent asks before writing); audit=applicable @ D05 T02 §7; exchange=applicable @ D05 T02 §1; reverse=applicable @ D05 T02 §7

**Adjacency rationale:** The list is the Kits view (§5), which finds every kit without knowing its name. Reporting is the health detail (§6). Exchange is the kit stamp `.conclave/kits.json` (§1), the one format the agent's forge and the extension share. Audit and reverse belong to the agent's import (§7): it reports forge's lists and checks the protected files with git, and git is the undo, since forge has no uninstall.

## Implementation Order

| Order | Section | Deliverable | Depends On | Status |
| ----- | ------- | ----------- | ---------- | ------ |
| 1 | §1 | Kit stamp written by forge on every install | -- | [ ] |
| 2 | §2 | Bundled SDK digest and drift test | §1 | [ ] |
| 3 | §3 | Kit state for newer and older kit stamps | §1, D02 T01 §10 | [ ] |
| 4 | §4 | New repository setup removed from the extension | -- | [x] |
| 5 | §5 | Conclave view with the read-only Kits tree | §3, D03 T01 §1, D00 T01 §8 | [ ] |
| 6 | §6 | Kit health detail in the Kits tree | §5 | [ ] |
| 7 | §7 | The adopt-conclave skill in the base kit | §1 | [ ] |

## 1. Kit stamp written by forge on every install

A project must say which kits set it up, so a reader can tell "older or newer kits" from "partly installed" (plan R38). `forge.py` writes `.conclave/kits.json` whenever `init`, `kit` or `sync` writes into a folder: for each kit in the folder its template digest, and the SDK's commit and commit date. The digest is defined once, in forge, and `forge.py digest` prints it, so the extension and the drift test of §2 never compute it differently.

> **Started:** 2026-10-20T21:35:00Z

**Corrected 2026-10-20 (while building):** each kit's entry carries its own `commit` and `date`, not one top-level `sdk` object, since kits in one folder can come from different SDK versions; the stamp is written only when every file of the kit came from this SDK (a fresh install, or `sync`'s refresh), so a `kit` run that keeps files of an earlier install leaves that install's entry; and the SDK folder itself gets no stamp, because a committed stamp would name a commit it can never be part of (the item that committed the SDK's own stamp is struck).

**Phase:** 1
**Needs:** none
**Surface:** no

**Build order:**

1. Write the failing tests in `tests/test_forge.py`. Done when: they fail at `fb5e468`.
2. Add the digest, the `digest` command and the stamp to `forge.py`. Done when: the tests pass and `python forge.py sync . --include-scripts` writes the SDK's own stamp.

- [x] Add `kit_digest(kit)` to `forge.py`: SHA-256 over the sorted relative paths and SHA-256 of every file under `kits/<kit>/templates/` (and `kits/<kit>/hosts/` for WordPress), with `/` separators and each file's CRLF line endings read as LF, so a Windows checkout and a Linux one of the same commit give the same digest. Done when: a test shows a changed, added or renamed template file changes the digest and the same file with CRLF endings does not. Cheaper substitute: the kit folder's modification time.
- [x] Add `python forge.py digest` printing `{"sdk": {"commit", "date"}, "kits": {<kit>: <digest>}}`, reading the commit from `git rev-parse HEAD` and its date from `git show -s --format=%cI` in a checkout, else from `SDK_COMMIT` and `SDK_DATE` next to `forge.py` (the bundled copy). Done when: the test reads every kit `forge.py kits` lists, and the bundled form when git is absent. Cheaper substitute: the commit only, with no date to order by.
- [x] Write `.conclave/kits.json` atomically from `provision` and `apply_kit` whenever they write a file (never on `--dry-run`): `schema_version: 1`, the `sdk` object, and each installed kit's digest, keeping the entries of kits this run did not touch. Done when: tests show `init`, `kit` and `sync` each write it, a dry run writes nothing, and a second kit keeps the first kit's entry. Cheaper substitute: writing only on `init`.
- [x] Report the stamp in `forge.py check` (`kit_stamp`: the parsed file or `null`) without changing any other key. Done when: `tests/test_check_pin_contract.py` and the extension's check fixtures still pass, and a test reads the stamp from `check`. Cheaper substitute: the extension reading the file itself.
- [x] ~~Refresh the SDK's own installed copy with `python forge.py sync . --include-scripts` and commit its stamp.~~ Struck 2026-10-20: the SDK gets no stamp (see the correction above); `write_kit_stamp` refuses the SDK folder and `test_the_sdk_folder_itself_gets_no_stamp` proves it. Done when: that test passes. Cheaper substitute: none.
- [ ] Commit: `forge: kit stamp written on every install`

**Test checkpoint:** `python -m unittest tests.test_forge -k stamp` passes, and fails when `apply_kit` stops writing the stamp.

## 2. Bundled SDK digest and drift test

The extension must change when the kits change (plan R39). `extensions/vscode/sdk-digest.json` records `forge.py digest`'s output with the extension's `package.json` version, and a test in this repository fails when the kits no longer match it or when the digest changed without a version change. `D04 T01 §4`'s bundle step refuses to package kits that differ from it.

**Phase:** 1
**Needs:** none
**Surface:** no

**Build order:**

1. Write the failing test in `tests/test_sdk_digest.py`. Done when: it fails with no `sdk-digest.json`.
2. Add the record script and the first record. Done when: the test passes, and fails after a kit edit until the script runs with a new version.

- [ ] Write `extensions/vscode/scripts/record-sdk-digest.py` (standard library): run `python forge.py digest` from the SDK root and write `{"version": <package.json version>, "kits": ..., "sdk": ...}` to `extensions/vscode/sdk-digest.json` atomically, refusing when the kits digest changed and the version in `package.json` is the one already recorded. Done when: running it twice changes nothing, and after a kit edit it refuses until the version is raised. Cheaper substitute: editing the file by hand.
- [ ] Write `tests/test_sdk_digest.py`: the recorded kit digests equal `forge.py digest`'s, and the recorded version equals `extensions/vscode/package.json`'s. Done when: editing one template file fails it with the kit's name, and so does raising the version without re-recording. Cheaper substitute: checking only that the file exists.
- [ ] Record the first `sdk-digest.json` and describe the rule in `AGENTS.md` beside the SDK's own copy rule: a kit change ships with a new extension version and a re-recorded digest. Done when: `python -m unittest discover -s tests` passes. Cheaper substitute: no written rule.
- [ ] Commit: `extension: bundled SDK digest recorded with each version`

**Test checkpoint:** `python -m unittest tests.test_sdk_digest` passes, and fails after any change under `kits/*/templates/` until `record-sdk-digest.py` runs with a raised version.

## 3. Kit state for newer and older kit stamps

A folder set up with kits the extension does not know must not read as partly installed (plan R40). The kit state gains the folder's stamp from `forge.py check` and compares each kit's digest and the SDK date with the source's own `forge.py digest`: equal digests are the current kits; a newer SDK date with a different digest is `newer` (update the extension); an older one is `older` (ask the agent to update the kits). A folder with no stamp keeps today's dry-run state.

**Phase:** 1
**Needs:** none
**Surface:** no

**Build order:**

1. Write the failing tests in `extensions/vscode/test/unit/kitState.test.ts` and `test/integration/kitState.test.ts`. Done when: they fail at the end of §1.
2. Extend `kitState` and `KitStateService`. Done when: the tests pass.

- [ ] Parse `kit_stamp` from `check` and `forge.py digest` in `extensions/vscode/src/core/forgeJson.ts`, refusing malformed shapes with the field named. Done when: unit tests over recorded fixtures pass, and a stamp with a missing date is refused. Cheaper substitute: reading `.conclave/kits.json` directly.
- [ ] Add `stamp: "current" | "newer" | "older" | "none"` per kit to `kitState` in `extensions/vscode/src/core/kitState.ts`, from the rule above, keeping the dry-run state for `none` and `current`. Done when: unit tests cover all four, including a newer stamp on a kit whose dry run lists files to add. Cheaper substitute: comparing commits for equality only.
- [ ] Read the digest once per SDK source and the stamp per folder in `KitStateService`, invalidated with the folder's state when `.conclave/kits.json` changes. Done when: an integration test that rewrites a folder's stamp sees the state change. Cheaper substitute: reading the digest on every request.
- [ ] Commit: `extension: kit state for newer and older kit stamps`

**Test checkpoint:** `cd extensions/vscode && npm test && npm run test:integration -- --grep kitState` passes, and a folder with a newer stamp reads `newer`, never partly installed.

## 4. New repository setup removed from the extension

The extension no longer sets up repositories (owner, 2026-10-20). This section removes `D05 T01 §4`'s code and the uncommitted `D05 T01 §10` change it carried, and keeps what protects every caller of forge: `provision`'s refusals in `forge.py` and their tests stay.

> **Started:** 2026-10-20T21:05:00Z

**Phase:** 1
**Needs:** none
**Surface:** no

**Build order:**

1. Remove the modules, the API entry and their tests. Done when: nothing in `extensions/vscode/` imports them.
2. Run every gate. Done when: build, lint, unit and integration pass.

- [x] Delete `extensions/vscode/src/core/repoInit.ts`, `src/host/repoInit.ts`, `src/core/protectedFiles.ts`, `src/host/protectedFiles.ts`, `test/unit/repoInit.test.ts`, `test/unit/protectedFiles.test.ts` and `test/integration/repoInit.test.ts`, and the `setUpRepository` entry of `ConclaveApi` in `src/extension.ts`. Done when: `rg "repoInit|protectedFiles|setUpRepository" extensions/vscode/src extensions/vscode/test` finds nothing. Cheaper substitute: leaving the code unreached.
- [x] Keep `forge.py`'s `.git` and SDK-folder refusals and `tests/test_forge.py`'s tests of them, and note in `docs/reviews/05-kit-manager/D05-T01-s4.md` that the extension half was removed by this section. Done when: `python -m unittest tests.test_forge -k refuses` passes. Cheaper substitute: removing the forge refusals too.
- [x] Limit the forge runner to commands that only read, in `extensions/vscode/src/host/forge.ts` (`kits`, `kit` with `--dry-run`, `check`, `doctor`; `init` and `sync` and their `parseProvision` parser removed), so no caller of `runForge` or the `ConclaveApi` can install through the extension, and set the integration tests' folders up with forge directly (`test/integration/forgeFixture.ts`). Done when: `forgeRunner.test.ts` shows `init`, `sync` and `kit` without `--dry-run` refused with nothing started, and fails when they are let through. Cheaper substitute: leaving `init` in the API for tests. (**Corrected 2026-10-20:** added while building: `init` through `runForge` was new repository setup left in the API.)
- [x] Empty `extensions/vscode/out/` before `tsc` compiles (`clean-out.mjs`, run by `npm run compile`), since `tsc` never deletes the output of a removed file and the deleted tests went on running from it. Done when: after the removal `npm test` runs 107 tests, not the stale 112. Cheaper substitute: deleting `out/` by hand. (**Corrected 2026-10-20:** added while building.)
- [x] Commit: `extension: remove new repository setup`

**Test checkpoint:** `cd extensions/vscode && npm run build && npm run lint && npm test && npm run test:integration` passes with no reference to the removed modules.

> **Verified:** 2026-10-20 | §4 | 54b2e77c9f1f344e8ae764e6c8cbdfaa3558f72f
> **Review:** `docs/reviews/d05-t02-s4.json`

## 5. Conclave view with the read-only Kits tree

The kits need a home in VS Code (plan R27, corrected 2026-10-20). This section contributes a "Conclave" view container in the Activity Bar with a Kits tree for the current folder (the only folder in a one-folder window; in a multi-root workspace the active editor's folder, which a Switch folder action changes): one node per kit from `forge.py kits` with its state, stamp and health badge. It offers no install, update or new repository action; a folder with no kit says how to import kits with the agent. "Open Reviewer Settings" sits in the Reviewers section (D06 T01 §4). Carried over from `D05 T01 §5` without its write actions.

**Phase:** 2
**Needs:** none
**Surface:** yes
**Fidelity:** `design/SPEC.md` §9 Kits view and health (corrected by `D00 T01 §8`); `design/screens/9-dark.png` and `design/screens/9-light.png` as recaptured by `D00 T01 §7`.
**Job:** Show the operator, at a glance, which Conclave-SDK kits the current repository has and which need attention.
**Treatment:** A native `TreeView` with codicons per state, a description column for the state and a badge count of kits needing attention on the view container.
**Chrome:** View title actions: Refresh, and Switch folder in a multi-root workspace; the view description names the folder there; kit node inline action: Health.

**Build order:**

1. Contribute the view container and view in `extensions/vscode/package.json` and write `extensions/vscode/src/host/kitsView.ts`. Done when: the view lists every kit `forge.py kits` returns for the shipped workspace with their states.
2. Wire the actions, the stamp messages and the badge. Done when: each action works and the badge counts kits needing attention.

- [ ] Contribute `viewsContainers.activitybar` `conclave` with the icon `media/conclave.svg` and `views.conclave` `conclave.kits` named "Kits" in `extensions/vscode/package.json`. Done when: the Activity Bar shows the Conclave icon and the Kits view. Cheaper substitute: a view inside the Explorer.
- [ ] Implement the `TreeDataProvider` in `extensions/vscode/src/host/kitsView.ts`: one kit node per entry of `forge.py kits` for the current folder, with the state from D02 T01 §10 and §3 and the health from `D05 T01 §3`. Done when: the integration test reads every kit node with the shipped workspace's states. Cheaper substitute: a hard-coded kit list.
- [ ] Resolve the current folder in `extensions/vscode/src/host/kitsView.ts`: the only folder, else the active editor's folder, else the last one picked, else the first; in a multi-root workspace set `TreeView.description` to its name and contribute `conclave.kits.switchFolder` as a view title action shown only when `workspaceFolderCount > 1`. Done when: an integration test on a two-folder workspace lists only the active editor's folder and switches on the pick. Cheaper substitute: every folder listed at once.
- [ ] Show the state as description text and a `ThemeIcon` (`pass`, `pie-chart`, `circle-large-outline`) and the health as a `FileDecoration` on the kit item's `resourceUri` (`conclave-kit:` scheme): the count of checks needing attention, at most two characters, coloured `list.warningForeground`, and none when every check is ok (`design/platform-audit.md`). Done when: the test reads the state, the icon and the decoration for a healthy, an unhealthy and an uninstalled kit. Cheaper substitute: the count appended to the description.
- [ ] Show a `newer` stamp as the description "newer kits than this extension" with the tooltip "Update the Conclave extension", and an `older` one as "older kits" with a copyable agent request to update them (`D05 T02 §7`) and the equivalent `python forge.py sync <folder>` command. Done when: the integration test reads both on folders with written stamps. Cheaper substitute: showing them as partly installed.
- [ ] Add inline Health on installed kits and a context menu with Health and Copy import request (the agent request for that kit, and `python forge.py kit <folder> <kit>`). Done when: Health opens §6 and the copy places both lines on the clipboard. Cheaper substitute: actions only in the Command Palette.
- [ ] Add the view title action Refresh. Done when: it reads the state again. Cheaper substitute: reloading the window.
- [ ] Set the view container's badge to the number of the current folder's kits needing attention, with a tooltip. Done when: a folder with a `setup_required` reviewer CLI shows badge 1. Cheaper substitute: no badge.
- [ ] Show an empty-folder message when a folder has no kit, naming the `adopt-conclave` request and copying it. Done when: an empty folder shows the message and its copy action works. Cheaper substitute: an empty tree.
- [ ] Write `extensions/vscode/test/integration/kitsView.test.ts`. Done when: it passes and fails when the kit list is hard-coded instead of read from forge. Cheaper substitute: a snapshot of labels only.
- [ ] Assert mockup parity for every scenario this section draws in `extensions/vscode/test/parity/conclave-activity-bar-view-with-the-kits.parity.test.ts` with `expectParity` from D02 T01 §11. Done when: the test passes and fails when one label, description, icon, badge, order or action differs from the mockup's fixture. Cheaper substitute: comparing by eye against the mockup.
- [ ] Commit: `ui: Conclave view with the read-only Kits tree`

**Test checkpoint:** `cd extensions/vscode && npm run test:integration -- --grep kitsView` passes, and fails when the view lists a kit that `forge.py kits` did not return.

## 6. Kit health detail in the Kits tree

Health needs detail, not just a badge (plan R30). This section shows a kit's `doctor` checks from `D05 T01 §3`, one row per check with its status and forge's detail verbatim, needs attention first, with Refresh. A `setup_required` row keeps forge's hint text. Carried over from `D05 T01 §8` unchanged.

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

## 7. The adopt-conclave skill in the base kit

Importing and updating kits is the agent's job (plan R41). This section adds an `adopt-conclave` skill to the base kit for Antigravity, Claude Code and Codex: it finds the SDK (the repository it runs in when that holds `forge.py`, else `CONCLAVE_SDK`, else it asks once), runs `forge.py check` and `doctor` on the target, previews each kit with `--dry-run`, resolves `merge_needed` paths and existing project files with the operator, runs `init`, `kit` or `sync`, checks the protected files (`AGENTS.md`, `GEMINI.md`, `CLAUDE.md`, `CODEX.md`, `.conclave/`, `.claude/settings.json`, `todo/`, `docs/`) with `git diff` afterwards, runs `doctor` again and reports forge's lists. It never passes `--force` unless the operator asks for that one run.

**Phase:** 1
**Needs:** none
**Surface:** no

**Build order:**

1. Write the skill in the three agents' template folders and the tests that list it. Done when: `tests/test_forge.py`'s skill lists name it and fail until it exists in all three.
2. Refresh the SDK's own copy. Done when: `python -m unittest discover -s tests` passes.

- [ ] Write `kits/base/templates/.claude/skills/adopt-conclave/SKILL.md`, `kits/base/templates/.agents/skills/adopt-conclave/SKILL.md` and `kits/base/templates/.codex/skills/adopt-conclave/SKILL.md` (with `agents/openai.yaml` for Codex, as the other base skills have), following `authoring-skills`' layout checklist: when to use, the steps above as a numbered workflow with each forge command, the stop conditions (a dirty protected file, `merge_needed`, an untrusted target) and the report format. Done when: the three files agree in substance and pass the layout checklist. Cheaper substitute: one agent only.
- [ ] Add `adopt-conclave` to `BASE_SKILLS` in `forge.py` and the expected lists in `tests/test_forge.py`. Done when: `python -m unittest tests.test_forge` passes, and fails with the skill folder removed from one agent. Cheaper substitute: not listing it.
- [ ] Refresh the SDK's own copy with `python forge.py sync . --include-scripts` and update `README.md` "Importing into a New or Existing Project" to lead with the skill and keep the forge commands. Done when: the test that the SDK's copy matches its kits passes and the README names the skill. Cheaper substitute: README unchanged.
- [ ] Run the skill on a scratch folder (init with the todo kit, then the reviewer kit on the same folder) and record the report in `docs/reviews/05-kit-manager/D05-T02-s7.md`. Done when: the record shows the dry runs, forge's lists, a clean protected-file diff and the stamp from §1. Cheaper substitute: no live run.
- [ ] Commit: `kits: adopt-conclave skill imports kits through forge`

**Test checkpoint:** `python -m unittest tests.test_forge` passes, and fails when `kits/base/templates/.codex/skills/adopt-conclave/SKILL.md` is removed.

## Verification

- `python -m unittest discover -s tests` passes, including `tests/test_sdk_digest.py`.
- `cd extensions/vscode && npm run build && npm run lint && npm test && npm run test:integration` passes.
- `python scripts/todo-graph.py validate` and `python scripts/todo-graph.py plan --check` pass.
