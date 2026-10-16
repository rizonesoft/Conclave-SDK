---
schema_version: 1
id: ship-extension
domain: 04-ship
status: active
title: "TODO-01 -- Ship Extension"
depends_on: ["reviewer-editor-ui", "kit-manager"]
---

# TODO-01 -- Ship Extension

> **Goal:** The extension is accepted end to end on Windows and in Remote WSL, documented, packaged as a `.vsix` that installs cleanly, reviewed independently for up to three rounds through the reviewer kit's dispatcher, and either published to the marketplace or explicitly kept private, as the owner decides.

> **Current state:** Measured 2026-10-16 in Conclave-SDK. Nothing to ship: no extension code and no `extensions/vscode/README.md`. The SDK carries an installed reviewer kit at its root (`.conclave/reviewers.toml`, `scripts/review-dispatch.py`, `docs/review-round-prompt.md`), and `forge.py doctor <repo> reviewer` found all three reviewer CLIs on this host on 2026-10-16.

## Inputs

- `docs/plans/2026-10-16-vscode-extension.md`: requirements R20, R22, R23.
- `docs/specs/*-vscode-extension-design.md`: packaging, publisher and the Windows and WSL table.
- `docs/review-round-prompt.md` and the `independent-review` skill in `.claude/skills/independent-review/SKILL.md`: how a review round is run and recorded.
- `design/SPEC.md`: the acceptance walk.
- -> XREF: D02 T01 §8 -- the Test reviewer run is part of the acceptance walk
- -> XREF: D03 T01 §10 -- the empty and failure states are part of the acceptance walk
- -> XREF: D05 T01 §9 -- every kit operation is part of the acceptance walk
- Every `npm`, `npx` and `node` command in this file runs in `extensions/vscode/`; the file depends on the whole of `reviewer-editor-ui` and `kit-manager` (frontmatter).

## Outcome

- A dated acceptance record for Windows and for Remote WSL in `docs/acceptance/`, each walking every `design/SPEC.md` section with the real dispatcher and real CLIs.
- `conclave-<version>.vsix` built by `npm run package`, installed with `code --install-extension`, and opened on the shipped workspace.
- Review rounds recorded in `docs/reviews/04-ship/vscode-extension.md`, every finding verified and fixed or answered, at most three rounds.
- The owner's marketplace decision recorded in `design/decisions.md`.

**Adjacency:** all=not-applicable (acceptance, packaging, documentation and review: no runtime behaviour of its own)

**Adjacency rationale:** Runtime adjacencies are owned by `D02 T01` and `D03 T01`. This file proves and ships them; any defect found here is fixed in the owning section's files with a regression test, not patched in packaging.

## Implementation Order

| Order | Section | Deliverable | Depends On | Status |
| ----- | ------- | ----------- | ---------- | ------ |
| 1 | §1 | Windows end-to-end acceptance | -- | [ ] |
| 2 | §2 | Remote WSL acceptance | §1 | [ ] |
| 3 | §3 | Extension README and SDK docs | §1 | [ ] |
| 4 | §4 | VSIX packaging and install check | §2, §3 | [ ] |
| 5 | §5 | Independent review rounds | §4 | [ ] |
| 6 | §6 | Marketplace publishing decision | §5 | [ ] |

## 1. Windows end-to-end acceptance

Unit and integration tests use fixtures and fake CLIs. This section walks the real thing on the Windows host: the installed Python, the real dispatcher, the real `codex`, `agy` and `claude`, and every section of `design/SPEC.md`, in both themes. A defect found is fixed in its owning section's files with a regression test, then the walk restarts at the affected SPEC section.

**Phase:** 6
**Needs:** windows-host, attended
**Surface:** no

**Build order:**

1. Run the full test suite. Done when: `npm ci && npm run build && npm run lint && npm test && npm run test:integration` exits 0.
2. Walk `design/SPEC.md` in the Extension Development Host on a scratch copy of the shipped workspace. Done when: `docs/acceptance/<date>-windows.md` records pass or a fixed defect for every SPEC section.

- [ ] Run `npm ci && npm run build && npm run lint && npm test && npm run test:integration` and record the counts in `docs/acceptance/<date>-windows.md`. Done when: the record shows each command's result. Cheaper substitute: running unit tests only.
- [ ] Copy the shipped workspace to `R:\scratch` and open it in the Extension Development Host. Done when: the panel opens in state `ready`. Cheaper substitute: editing this repository's own pin.
- [ ] Walk `design/SPEC.md` §1 to §7 in Dark Modern and Light Modern, recording each control's result in the acceptance file. Done when: every control has pass or a defect reference. Cheaper substitute: walking one theme.
- [ ] Edit, save and inspect the pin with `git diff --no-index` against the original. Done when: only the edited lines differ and every comment remains. Cheaper substitute: trusting the preview.
- [ ] Run Test reviewer on astra, gemini and sonnet with the real CLIs and record each outcome. Done when: each returns a review naming the planted bug or a recorded failover reason. Cheaper substitute: fake CLIs.
- [ ] Reach every empty and failure state with real causes (rename the pin, an old dispatcher copy, a bad `conclave.pythonPath`, Restricted Mode) and record each. Done when: all seven states are recorded. Cheaper substitute: fixture workspaces only.
- [ ] With `conclave.sdkPath` empty, install the reviewer kit from GitHub into an empty scratch workspace, then update an old dispatcher with "Update from Conclave-SDK", recording the SHA shown and the files forge listed. Done when: both runs are recorded with the SHA and the pin hash before and after the update. Cheaper substitute: the local checkout only.
- [ ] Walk the Kits view on a scratch folder: install `todo`, then `wordpress` with host `wpcom`, from the dry-run preview; update with scripts; read each kit's health; and set up a new repository with the wizard, recording each result and the protected-file hashes. Done when: every operation is recorded with forge's lists. Cheaper substitute: installing one kit.
- [ ] Open the editor from each entry point (Command Palette, Explorer context menu, editor title button, status bar) and record the status bar text in the ready, refused and no-pin states. Done when: all four are recorded. Cheaper substitute: the command only.
- [ ] Fix each defect found in its owning file with a regression test that fails before the fix, and cite the commit in the acceptance record. Done when: no open defect remains in the record. Cheaper substitute: a workaround in the webview.
- [ ] Commit: `docs: Windows acceptance of the reviewer editor`

**Test checkpoint:** `python -c "import glob,sys; f=sorted(glob.glob('docs/acceptance/*-windows.md')); t=open(f[-1],encoding='utf-8').read() if f else ''; sys.exit(1 if not f or 'defect: open' in t or t.count('pass')<7 else 0)"` exits 0, and exits 1 while the record is missing or an open defect remains.

## 2. Remote WSL acceptance

In a Remote WSL window the extension runs in the WSL extension host (`extensionKind` `workspace`), calls the Linux Python and finds the Linux CLIs (plan R20). This section installs the build into the WSL host and walks the same SPEC sections there, on a workspace under `/mnt/r/scratch` and one under the Linux home directory, to cover both path forms.

**Phase:** 6
**Needs:** windows-host, attended
**Surface:** no

**Build order:**

1. Open a Remote WSL window and run the extension there. Done when: the output channel logs a `python3` resolution with a Linux path.
2. Walk the SPEC on both workspaces. Done when: `docs/acceptance/<date>-wsl.md` records every SPEC section on both.

- [ ] Open `/mnt/r/scratch/<copy>` in a Remote WSL window with the extension running in the WSL host, and confirm the "Conclave" channel shows the Linux Python. Done when: the logged argv starts with a `/usr/bin/python3` or similar Linux path. Cheaper substitute: running the Windows host against a `\\wsl$` path.
- [ ] Walk `design/SPEC.md` §1 to §7 on the `/mnt/r` workspace and record results in `docs/acceptance/<date>-wsl.md`. Done when: every control has pass or a defect reference. Cheaper substitute: checking that the panel opens.
- [ ] Repeat the walk on a copy under `~/` inside WSL. Done when: the record covers both path forms. Cheaper substitute: one path form.
- [ ] Save on both workspaces and confirm the atomic rename and line endings with `file .conclave/reviewers.toml` and `git diff --no-index`. Done when: line endings match the original and no temp file remains. Cheaper substitute: not checking line endings.
- [ ] Run Test reviewer with the WSL CLIs, recording a not-installed CLI as its failover reason. Done when: each reviewer's outcome is recorded. Cheaper substitute: skipping the test action.
- [ ] Install the kit from GitHub in the Remote WSL window, confirming the sign-in carries over and the download lands in the Linux-side global storage. Done when: the record shows the SHA and the Linux cache path. Cheaper substitute: the Windows install only.
- [ ] Fix each defect in its owning file with a regression test, citing the commit in the record. Done when: no open defect remains. Cheaper substitute: a WSL-only branch in the webview.
- [ ] Commit: `docs: Remote WSL acceptance of the reviewer editor`

**Test checkpoint:** `python -c "import glob,sys; f=sorted(glob.glob('docs/acceptance/*-wsl.md')); t=open(f[-1],encoding='utf-8').read() if f else ''; sys.exit(1 if not f or 'defect: open' in t or '/mnt/r' not in t else 0)"` exits 0, and exits 1 while the record is missing, has an open defect, or omits the `/mnt/r` walk.

## 3. Extension README and SDK docs

The extension needs its own README (also the marketplace page), and the SDK's `README.md` and `AGENTS.md` need to say that `extensions/vscode/` exists, how to build and test it, and that its Node toolchain stays in that folder. This section writes all three and the changelog.

**Phase:** 6
**Needs:** none
**Surface:** no

**Build order:**

1. Write `extensions/vscode/README.md` and `extensions/vscode/CHANGELOG.md`. Done when: every setting, entry point, kit operation and empty state is described.
2. Update the SDK's `README.md` and `AGENTS.md`. Done when: both name `extensions/vscode/` and its commands.

- [ ] Write `extensions/vscode/README.md` with an answer-first opening, requirements (VS Code, Python 3.11 or later), install from `.vsix`, every setting (`pythonPath`, `sdkPath`, `sdkRepository`, `sdkRef`), the entry points, the Kits view and each kit operation, each empty state's meaning and a screenshot from `design/screens/`. Done when: every setting in `extensions/vscode/package.json` `contributes.configuration` is described. Cheaper substitute: a one-line README.
- [ ] Add `extensions/vscode/CHANGELOG.md` with the first version's entry. Done when: `vsce package` reads it without warning. Cheaper substitute: no changelog.
- [ ] Add `extensions/vscode/` to the layout table in the SDK `README.md` and an "Editor extension" section with the build and test commands. Done when: the table row is at or under 100 characters and the commands run as written. Cheaper substitute: a link only.
- [ ] Add an `extensions/vscode/` paragraph to the SDK `AGENTS.md` (Node toolchain only there, `npm` commands run there, Python stays standard library only). Done when: the paragraph names the test commands. Cheaper substitute: no rule.
- [ ] Check every Markdown file touched for em and en dashes and hard-wrapped prose. Done when: `grep -nP "[\x{2013}\x{2014}]" extensions/vscode/README.md extensions/vscode/CHANGELOG.md README.md AGENTS.md` finds nothing. Cheaper substitute: checking one file.
- [ ] Commit: `docs: extension README, changelog and SDK layout`

**Test checkpoint:** `python -c "import pathlib,sys; r=pathlib.Path('extensions/vscode/README.md'); s=pathlib.Path('README.md').read_text(encoding='utf-8'); sys.exit(1 if not r.is_file() or 'sdkRef' not in r.read_text(encoding='utf-8') or 'extensions/vscode' not in s else 0)"` exits 0, and exits 1 while the README omits a setting or the SDK README omits the folder.

## 4. VSIX packaging and install check

The extension ships as a `.vsix` (plan R22). This section adds `npm run package` with `@vscode/vsce`, checks the package holds only what it should, installs it into a clean VS Code profile and opens the shipped workspace. It does not publish: that is §6.

**Phase:** 6
**Needs:** none
**Surface:** no

**Build order:**

1. Add `npm run package`. Done when: it writes `conclave-<version>.vsix`.
2. Install and open it in a clean profile. Done when: the panel opens in state `ready` from the installed build.

- [ ] Add `npm run bundle-sdk` (`extensions/vscode/scripts/bundle-sdk.mjs`) copying `forge.py` and `kits/` from the SDK root into `extensions/vscode/sdk/` and writing `sdk/SDK_COMMIT` from `git rev-parse HEAD`, refusing when `git status --porcelain -- forge.py kits` is not empty, and run it first in `npm run package`. Done when: `sdk/SDK_COMMIT` equals `HEAD` and a dirty kit file makes the bundle refuse. Cheaper substitute: bundling an uncommitted kits tree.
- [ ] Add `@vscode/vsce` as a dev dependency and `"package": "vsce package --no-dependencies"` in `package.json`, with `repository`, `license` and `icon` set. Done when: `npm run package` exits 0 with no warnings. Cheaper substitute: `--allow-missing-repository`.
- [ ] List the package with `npx vsce ls` and tighten `.vscodeignore` until it holds `dist/`, `resources/`, `sdk/`, `README.md`, `CHANGELOG.md`, `LICENSE` and `package.json` only. Done when: no `src/`, `test/`, `todo/`, `docs/` or `.conclave/` path is listed. Cheaper substitute: shipping the whole repository.
- [ ] Install with `code --profile conclave-clean --install-extension conclave-<version>.vsix` and open a scratch copy of the shipped workspace. Done when: `conclave.openReviewers` shows state `ready`. Cheaper substitute: testing only in the Extension Development Host.
- [ ] Install the same `.vsix` into the Remote WSL host and open the WSL copy. Done when: the panel shows `ready` with the Linux Python logged. Cheaper substitute: Windows only.
- [ ] Record the package size, file list and both installs in `docs/acceptance/<date>-package.md`. Done when: the record exists. Cheaper substitute: no record.
- [ ] Commit: `build: package the extension as a vsix`

**Test checkpoint:** `cd extensions/vscode && npm run package && npx vsce ls | python -c "import sys; bad=[l for l in sys.stdin if l.split('/')[0] in ('src','test','todo','docs','.conclave')]; sys.exit(1 if bad else 0)"` exits 0, and exits 1 when `.vscodeignore` stops excluding `src/`.

## 5. Independent review rounds

The owner requires independent review of the change through the reviewer kit (plan R23): writer `claude`, so Astra reviews, with Gemini 4 and Sonnet 5.5 as failover, for up to three rounds. This section prepares the candidate range and prompt, runs the rounds with `scripts/review-dispatch.py`, verifies every finding against the code, fixes real ones with a regression test each, and records the outcome. A round with no reviewer is not an approval.

**Phase:** 6
**Needs:** none
**Surface:** no

**Build order:**

1. Write the round prompt from `docs/review-round-prompt.md` for the candidate range. Done when: the prompt names the base commit, head commit and the lenses.
2. Run up to three rounds and act on each. Done when: `docs/reviews/04-ship/vscode-extension.md` records each round and the last is clean or stopped at three with the reason.

- [ ] Write the prompt to the session scratchpad from `docs/review-round-prompt.md`, naming the range from the commit `vscode: move the extension plan into Conclave-SDK` to `HEAD`, the plan and spec paths, and lenses for correctness, validation parity with `load_pin`, atomic write and comment preservation, Windows and WSL, and webview security. Done when: the prompt file exists outside the repository. Cheaper substitute: a prompt with no range.
- [ ] Run `python scripts/review-dispatch.py --writer claude --prompt <prompt> --record docs/reviews/04-ship/vscode-extension.md`. Done when: exit 0 and a `## Round 1` section with the reviewer named. Cheaper substitute: counting exit 1 (no reviewer) as a pass.
- [ ] Verify each finding against the code, marking it real or not real with the evidence in the record. Done when: every finding has a verdict. Cheaper substitute: applying every finding blindly.
- [ ] Fix each real finding in its owning file with a regression test that fails before the fix, as new commits (never amending the candidate). Done when: each fix cites its test and commit in the record. Cheaper substitute: fixes without tests.
- [ ] Run rounds 2 and 3 only while the previous round had real findings, stopping at three. Done when: the last round is clean, or the record says stopped at 3 with the open items listed. Cheaper substitute: a fourth round.
- [ ] Commit: `review: independent review rounds for the reviewer editor`

**Test checkpoint:** `python -c "import pathlib,re,sys; t=pathlib.Path('docs/reviews/04-ship/vscode-extension.md').read_text(encoding='utf-8'); n=len(re.findall(r'^## Round \d+: (?!none)',t,re.M)); sys.exit(0 if 1<=n<=3 else 1)"` exits 0, and exits 1 when no round has a named reviewer or more than three rounds ran.

## 6. Marketplace publishing decision

Publishing to the Visual Studio Marketplace is outward-facing and the owner asked to be asked first (plan R22). This section puts the decision to the owner with what publishing needs (a publisher ID, a personal access token from the 1Password Conclave vault, the repository's visibility) and records the answer. If the answer is yes, it publishes the reviewed `.vsix`; if no, it records that the `.vsix` is the distribution.

**Phase:** 6
**Needs:** owner-decision
**Surface:** no

**Build order:**

1. Ask the owner and record the answer in `design/decisions.md`. Done when: the decision and date are recorded and the Need above reads `none`.
2. Act on it. Done when: the extension's marketplace page is live, or `README.md` states the `.vsix` is the distribution.

- [ ] Ask the owner with the facts: publisher ID needed, token source (1Password Conclave vault), repository visibility `internal`, and that the `.vsix` bundles every kit, so a public listing makes the kits public. Done when: the answer is in `design/decisions.md` with the date. Cheaper substitute: publishing without asking.
- [ ] Remove `owner-decision` from this section's `**Needs:**` line once the answer is recorded. Done when: `python scripts/todo-graph.py query ready` lists this section. Cheaper substitute: removing it before the answer.
- [ ] If yes, run `npx vsce publish --packagePath conclave-<version>.vsix` with the token from the vault, never printing it. Done when: the marketplace page shows the version. Cheaper substitute: a token pasted in chat.
- [ ] If no, state in `README.md` that the extension installs from the `.vsix` attached to a GitHub release, and attach it with `gh release create`. Done when: the release lists the `.vsix`. Cheaper substitute: a `.vsix` committed to the repository.
- [ ] Commit: `docs: record the marketplace decision`

**Test checkpoint:** `python -c "import pathlib,re,sys; t=pathlib.Path('design/decisions.md').read_text(encoding='utf-8'); sys.exit(0 if re.search(r'Marketplace: (yes|no) \(\d{4}-\d{2}-\d{2}\)',t) else 1)"` exits 0, and exits 1 while the decision is unrecorded.

## Verification

- `docs/acceptance/` holds the Windows, WSL and package records with no open defect.
- `docs/reviews/04-ship/vscode-extension.md` ends in a clean round or a recorded stop at three, and `design/decisions.md` carries the marketplace decision.
- `python scripts/todo-graph.py validate` and `python scripts/todo-graph.py plan --check` pass.
