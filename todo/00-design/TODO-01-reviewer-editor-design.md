---
schema_version: 1
id: reviewer-editor-design
domain: 00-design
status: active
title: "TODO-01 -- Reviewer Editor Design"
---

# TODO-01 -- Reviewer Editor Design

> **Goal:** The owner has approved a clickable mockup of the reviewer pin editor, the open design questions have recorded answers, `design/SPEC.md` describes every control and state of the approved surface with screenshots, and a design spec settles how the extension validates, edits, saves and runs on Windows and WSL. No extension code is written before the approval in §2.

> **Current state:** Measured 2026-10-16. Moved from `rizonetech/Conclave-VSC` (last commit `e1e7e46`) into Conclave-SDK the same day. The mockup is published at https://claude.ai/artifact/RRxxX5W6pYFQ3b2Z4Fq2mv with its source in `design/mockup/project/`; it predates the kit manager, the bundled SDK source and the entry points, which are open items in §1. There is no `design/SPEC.md`, `design/decisions.md` or `docs/specs/*-vscode-extension-design.md` yet.

## Inputs

- `docs/plans/2026-10-16-vscode-extension.md`: requirements R1 to R23, the `--check-pin` contract, and the SDK facts measured at `b7c649b`.
- `.conclave/reviewers.toml`: the shipped pin the mockup is filled with, comments included.
- `scripts/review-dispatch.py` `load_pin`: the exact `Refused` message text the mockup's inline errors use.
- `R:\GitHub\Conclave-SDK\forge.py` `_doctor_reviewer`: what the status column reports.
- -> XREF: D01 T01 §2 -- the `--check-pin` output shape the mockup's status and errors are drawn from
- -> XREF: D02 T01 §1 -- the scaffold starts only after the design spec in §4
- -> XREF: D03 T01 §1 -- every surface section cites `design/SPEC.md` from §3
- -> XREF: D05 T01 §5 -- the Kits view and dialogs cite `design/SPEC.md` §9 to §11
- -> XREF: D06 T01 §4 -- the feature sections cite `design/SPEC.md` §12

## Outcome

- A published, clickable mockup Artifact in both VS Code Dark Modern and Light Modern themes, with its source at `design/mockup/project/Main.dc.html` and its link in `design/README.md`.
- The owner's approval and the answers to every open design question, recorded in `design/decisions.md` with the date.
- `design/SPEC.md` with one section per surface region and state, and screenshots under `design/screens/`.
- `docs/specs/2026-10-16-vscode-extension-design.md` (dated the day it is written) settling validation, comment-preserving edits, atomic writes, re-check after save, Windows and WSL behaviour, the supported `schema_version` range and packaging.

**Adjacency:** all=not-applicable (design documents only: no runtime records, settings or behaviour ship from this file)

**Adjacency rationale:** This file produces the mockup, decisions and specifications that later files implement. Every runtime adjacency (settings consumers, reverse paths, permissions and audit) is declared in `D02 T01` and `D03 T01`, which own the behaviour.

## Implementation Order

| Order | Section | Deliverable | Depends On | Status |
| ----- | ------- | ----------- | ---------- | ------ |
| 1 | §1 | Clickable reviewer editor mockup | -- | [x] |
| 2 | §2 | Owner approval and open design answers | §1 | [x] |
| 3 | §3 | Interface SPEC and screenshots | §2, §5 | [ ] |
| 4 | §4 | Reviewer config design spec | §2, §5 | [ ] |
| 5 | §5 | Mockup and plan follow the family route rule | §2 | [x] |

## 1. Clickable reviewer editor mockup

> **Started:** 2026-10-16T19:40:00Z

The owner asked for a mockup before any code. This section builds one static, clickable HTML page that looks like a real VS Code webview editor for `.conclave/reviewers.toml`, filled with the shipped pin, and publishes it as an Artifact. It is a design artifact: its interactions are simulated in page script and it calls no dispatcher. It must not add any extension code (`package.json`, `src/`).

**Corrected 2026-10-16:** moved with the whole plan from `rizonetech/Conclave-VSC` into Conclave-SDK; every path is relative to the SDK root and the settings are now `conclave.*`.

**Corrected 2026-10-16:** the plan named one file, `design/mockup/reviewer-editor.html`. The Artifact tool's Design type stores a canvas as `project/canvas.json` plus one `.dc.html` file per artboard, so the source is `design/mockup/project/` (the whole editor is `Main.dc.html`; the other artboards mount it with a theme and a scenario) and the requirement map is in `design/README.md`. Paths below are corrected to match.

**Phase:** 0
**Needs:** none
**Surface:** no

**Build order:**

1. Read `docs/plans/2026-10-16-vscode-extension.md`, `.conclave/reviewers.toml` and `load_pin` in `scripts/review-dispatch.py`. Done when: every R1 to R19 requirement maps to a region of the mockup in the requirement map in `design/README.md`.
2. Build the Design canvas under `design/mockup/project/` (`canvas.json`, `Main.dc.html` and one artboard per highlighted state) with both themes and every state. Done when: `Main.dc.html` reaches each state from a scenario switcher and both themes from a theme switcher.
3. Publish it with the Artifact tool and record the link. Done when: the link opens the published page and appears in `design/README.md`.

- [x] Write the theme tokens for Dark Modern and Light Modern in `design/mockup/project/Main.dc.html` (`.t-dark` and `.t-light`, one token per VS Code theme colour used, for example `--bg-editor` for `editor.background` and `--err` for `errorForeground`; `design/SPEC.md` §1 maps each to its `--vscode-*` variable), with a theme switcher. Done when: switching themes repaints every region with no hard-coded colour outside the token blocks and the mockup control bar. Cheaper substitute: a single dark palette with the light theme left as a CSS invert filter.
- [x] Fill the page from the shipped pin in `.conclave/reviewers.toml` (reviewers `astra`, `gemini`, `sonnet` and routes `claude`, `gemini`, `codex`, cited in plan R1 and R4). Done when: every name, CLI, model, effort and route entry on the page equals the file. Cheaper substitute: placeholder reviewers such as `reviewer-1`.
- [x] Draw one reviewer card per reviewer in `design/mockup/project/Main.dc.html` with name, `cli` dropdown (codex, agy, claude), `model` text and `effort` dropdown per plan R1 and R2. Done when: the codex card offers low, medium, high, xhigh; the claude card adds max; the agy card hides effort and shows the note naming `gemini-4-argon-high`. Cheaper substitute: one shared effort list for every CLI.
- [x] Simulate add, rename and delete on the cards per plan R3. Done when: renaming `sonnet` rewrites it in every route row, and deleting a routed reviewer first lists the routes that lose it. Cheaper substitute: rename that leaves stale route entries.
- [x] Draw the three route rows (claude, codex, gemini) as ordered failover lists with drag handles, keyboard move buttons, add and remove per plan R4. Done when: dragging reorders a row, a reviewer already in a row is greyed out in that row's add menu, and removal works. Cheaper substitute: a comma-separated text field per route.
- [x] Show the self-review warning and the no-route notice per plan R5 and R6. Done when: the shipped pin shows warnings on `sonnet` in the claude row and `gemini` in the gemini row, adding `astra` to the codex row warns, and removing every entry from a row shows that the writer gets no review. Cheaper substitute: a single banner that does not say which row or reviewer.
- [x] Show inline validation errors using the exact `Refused` strings from `load_pin` for every rule in plan R9, with Save disabled while one shows. Done when: a state switcher entry per rule shows its error at the field it names and a disabled Save button. Cheaper substitute: paraphrased error text that differs from the dispatcher's.
- [x] Draw the status column and the Test reviewer action per plan R10 and R11. Done when: each card shows its CLI as found or not found, and Test reviewer shows a running state, a returned review and a failover reason. Cheaper substitute: a status column with no not-found state.
- [x] Draw the TOML preview with a diff against disk per plan R12. Done when: after one simulated edit the preview shows the shipped file with its comments intact and only the edited line marked changed. Cheaper substitute: a preview regenerated without comments.
- [x] Draw the empty and failure states per plan R16 to R19: no pin, refused pin, missing dispatcher, dispatcher too old, no Python, untrusted workspace. Done when: each is reachable from the state switcher and names the command it would run or the fix it needs. Cheaper substitute: one generic "something went wrong" panel.
- [x] List the open design questions in `design/mockup/open-questions.md`, starting with: same-CLI self-review, one error versus all errors from `--check-pin`, custom editor versus webview panel, the comment-preserving TOML approach, Test reviewer cost and confirmation, and the Python resolution order. Done when: each question has options and a recommended answer. Cheaper substitute: questions left only in chat.
- [x] Show the SDK source in the no-pin install confirmation per plan R24: `bundled Conclave-SDK@<sha>` by default, the local path when `conclave.sdkPath` is set, and `rizonetech/Conclave-SDK@<sha>` when `conclave.sdkRef` is set, with a mockup control for all three. Done when: all three labels show in `design/mockup/project/Main.dc.html` before Run. Cheaper substitute: a confirmation that names only the command.
- [x] Draw the SDK source refusals per plan R24 (sign-in cancelled, no access to the internal repository, rate limited, offline, and an unusable `sdkPath`), each with its action. Done when: each is reachable from the scenario switcher. Cheaper substitute: one "download failed" message. Shipped: `SRC_FAIL` and the five `src-*` scenarios in `design/mockup/project/Main.dc.html`, each with its actions and a working Use the bundled SDK; artboard `SourceRefused.dc.html`.
- [x] Replace the copy-only actions on the no-dispatcher and old-dispatcher states with "Update from Conclave-SDK" per plan R29: a confirmation stating sync's scope, then forge's updated file list, with Copy command kept as the secondary action. Done when: both states run the simulated update and land in the editor. Cheaper substitute: keeping copy only. Shipped: the `e.sync` phases in `emptyFor` (confirm, refusal, forge's added and updated lists, the hash check, then the editor); artboard `SyncDispatcher.dc.html`.
- [x] Draw the entry points per plan R26: the Command Palette entry, the Explorer context menu on `.conclave/reviewers.toml`, the editor title button, and the status bar item showing the state. Done when: each is visible on an artboard in both themes. Cheaper substitute: the status bar text alone. Shipped: `EntryMenu`, `EntryMenuLight`, `EntryPalette` and `EntryPaletteLight` artboards; the title bar search opens the palette and a right-click on the pin opens the menu.
- [x] Draw the Conclave Activity Bar view with the Kits tree per plan R27 and R30: each kit's state and health badge, inline Install and Health, and the view title actions. Done when: an artboard shows the tree for a folder with installed, partly installed and missing kits. Cheaper substitute: a flat list with no states.
- [x] Draw the kit install dialog per plan R28: agent choice, the WordPress host step, forge's dry-run list as will add and already present, the `merge_needed` refusal, and the installed list after. Done when: the WordPress path and the `todo` path are both clickable. Cheaper substitute: a confirmation with no file list.
- [x] Draw the kit update flow and the health detail per plan R29 and R30: the scope text, the scripts choice, forge's updated lists, and one row per doctor check with its status and detail. Done when: both are reachable on an artboard. Cheaper substitute: a single updated toast. Shipped: the `update-pick` quick pick, the `update-confirm` dialog and the UPDATE KITS pane (`UpdatePick`, `UpdateConfirm`, `UpdateDone`); the health detail is the doctor rows under each kit (`Kits.dc.html`).
- [x] Draw the new repository wizard per plan R31: folder, kits with base always on, agent, mode, WordPress host, the summary with kept entry docs, and the open choice. Done when: every step is clickable with Back. Cheaper substitute: one form with no summary. Shipped: the `repo` quick pick steps with Back, the `repo-confirm` dialog and the result notification with Open, Open in New Window and Add to Workspace (`RepoKits`, `RepoConfirm`).
- [x] Rename the mockup's settings to `conclave.*`, its output channel to "Conclave", and its example workspace away from `Conclave-VSC`. Done when: `grep -c conclaveReviewers design/mockup/project/Main.dc.html` prints 0. Cheaper substitute: leaving the old names.
- [x] Add question 9 (SDK source from GitHub) and question 10 (entry points) to `design/mockup/open-questions.md`, and update question 8. Done when: each has options and a recommendation. Cheaper substitute: questions left only in chat.
- [x] Draw the feature sections per plan R33 to R37 under the Kits tree in `design/mockup/project/Main.dc.html` (`featurePanes`): Reviewers, Plan, Review rounds and WordPress site, each shown only while its kit is in the folder. Done when: the `sections` artboard shows all four and a folder without the kits shows none. Cheaper substitute: placeholder panes with no rows.
- [x] Audit the mockup against the VS Code extension API in `design/platform-audit.md`, changing every native element the API cannot render (codicons from `@vscode/codicons` 0.0.45, `FileDecoration` kit badges, plain group labels, hover-only view title actions, no dirty dot on the webview tab). Done when: every element is classed native, webview or chrome and no native element shows something its API lacks. Cheaper substitute: fixing the gaps during the build.
- [x] Pull the published canvases into the repository: `design/mockup/project/` matches the live mockup file for file and `design/icon-concepts/project/` holds the icon canvas. Done when: `cmp` reports every published file identical to the repository copy. Cheaper substitute: treating the live canvas as the only copy.
- [x] Publish `design/mockup/project/Main.dc.html` with the Artifact tool and write the link into `design/README.md`. Done when: the link opens the published page in both themes. Cheaper substitute: a local file path in place of a link. Shipped: canvas version 22 at the link in `design/README.md`, opened in both themes 2026-10-16.
- [x] Commit: `design: reviewer editor mockup and open questions`

**Test checkpoint:** `python -c "import pathlib,sys; t=pathlib.Path('design/mockup/project/Main.dc.html').read_text(encoding='utf-8'); m=[s for s in ('gpt-6-astra','gemini-4-argon-high','claude-sonnet-5-5','Light Modern','Dark Modern','check-pin','No route','old-dispatcher','no-python','untrusted','rizonetech/Conclave-SDK','Update from Conclave-SDK','Open Reviewer Settings','bundled Conclave-SDK','Kits','Set up a new repository','Open in Conclave Reviewers','Set Up a New Repository (','GitHub returned 404','Update the kits in') if s not in t]; sys.exit(m or None)"` exits 0, and fails with the missing strings when a required region is absent.

**Corrected 2026-10-16:** the checkpoint gained `Open in Conclave Reviewers`, `Set Up a New Repository (`, `GitHub returned 404` and `Update the kits in`, so it also fails when the entry points, the wizard, the SDK source refusals or the update confirmation are missing.

> **Verified:** 2026-10-16 | §1 | 5a72d3268e8fbaca64126cecf39b5fde365a189c
> **Review:** `docs/reviews/d00-t01-s1.json`

## 2. Owner approval and open design answers

> **Started:** 2026-10-17T00:13:45Z

The owner said no code is written until they approve the mockup. This section is that gate: it records the approval, any changes asked for, and the answer to every question in `design/mockup/open-questions.md`. Every code section in the tree depends on it. When the owner asks for changes, they are made in §1's files and republished to the same Artifact link before approval is recorded.

**Phase:** 0
**Needs:** none
**Surface:** no

**Build order:**

1. Present the Artifact link and `design/mockup/open-questions.md` to the owner. Done when: the owner has answered in the session or in an Artifact comment.
2. Record the outcome in `design/decisions.md`. Done when: the file names the approval date and one answer per question, and `**Needs:**` above reads `none`.

- [x] Apply every change the owner asks for to `design/mockup/project/Main.dc.html` and republish to the link in `design/README.md`. Done when: the owner confirms the republished page. Cheaper substitute: a new Artifact link that leaves the old one stale. Shipped: none asked for; the owner approved canvas version 22 as it is on 2026-10-17 (`design/decisions.md`).
- [x] Freeze the approved mockup: record in `design/decisions.md` the commit of `design/mockup/project/` and the canvas version the owner approved, and change the design afterwards only by a dated decision applied to the mockup first. Done when: `design/decisions.md` names both. Cheaper substitute: approving the live canvas, which keeps changing. Shipped: `design/decisions.md` names commit `22cdeed` and canvas version 22, plus the content-identical later in-page save.
- [x] Write `design/decisions.md` with the approval date and one dated answer per question in `design/mockup/open-questions.md`. Done when: every question has an answer and none says "TBD". Cheaper substitute: answers kept only in the conversation. Shipped: `design/decisions.md`, approved 2026-10-17, answers 1 to 14 dated, none TBD.
- [x] Update `docs/plans/2026-10-16-vscode-extension.md` where an answer changes a requirement (for example R5 or R8). Done when: no requirement contradicts `design/decisions.md`. Cheaper substitute: a decisions file that silently overrides the plan. Shipped: R5 (answer 1) and R8 (answer 2) no longer call their questions open, R11 (answer 6), R17 (answer 3, dated correction) and R19 (answer 7); R24, R26, R32 and R35 already matched answers 9, 10, 12 and 13.
- [x] Remove `owner-decision` from this section's `**Needs:**` line. Done when: `python scripts/todo-graph.py query ready` lists `D00 T01 §3` and `D00 T01 §4`. Cheaper substitute: removing the Need before the answers are written. Shipped: the Needs line reads none.
- [x] Commit: `design: record mockup approval and design answers`

**Test checkpoint:** `python -c "import pathlib,re,sys; t=pathlib.Path('design/decisions.md').read_text(encoding='utf-8'); sys.exit(0 if re.search(r'Approved: \d{4}-\d{2}-\d{2}', t) and 'TBD' not in t else 1)"` exits 0, and exits 1 while the approval line is missing or an answer is TBD.

> **Verified:** 2026-10-17 | §2 | 50654274e5ed759c2e559eacc2de40b76fe1ee46
> **Review:** `docs/reviews/d00-t01-s2.json`

## 3. Interface SPEC and screenshots

Surface sections in `D03 T01` cite `design/SPEC.md` for their Fidelity. This section writes it from the approved mockup: one section per region and state, with every control, its states, its keyboard path and the message it shows, plus a screenshot per state in both themes. It changes no mockup behaviour.

**Phase:** 0
**Needs:** none
**Surface:** no

**Build order:**

1. Write `design/SPEC.md` from `design/mockup/project/Main.dc.html` and `design/decisions.md`. Done when: every control in the mockup appears in exactly one SPEC section.
2. Capture screenshots into `design/screens/`. Done when: each SPEC section links a Dark Modern and a Light Modern screenshot that exist on disk.

- [ ] Write `design/SPEC.md` §1 Layout and theming: regions, spacing, the theme tokens used (cite `design/mockup/project/Main.dc.html`). Done when: the section names every token the mockup uses. Cheaper substitute: a screenshot with no written token list.
- [ ] Write `design/SPEC.md` §2 Reviewer cards: fields, per-CLI effort, agy note, add, rename, delete and their confirmations (plan R1 to R3). Done when: each control lists its states and keyboard path. Cheaper substitute: a field list without states.
- [ ] Write `design/SPEC.md` §3 Route rows: the reviewer and fallback chips, drag and keyboard reorder, the add menu with its disabled reasons, remove, the no-route notice, and a hand-edited route's inline refusal (plan R4 to R6). Done when: each disabled reason, the notice and the three route refusals have their exact text written out. Cheaper substitute: "shows a reason" with no text. **Corrected 2026-10-20:** was the self-review warning, before `design/decisions.md`, Reviewer routes, 2026-10-20.
- [ ] Write `design/SPEC.md` §4 Validation and Save: where each `Refused` message attaches, Save gating, Discard (plan R7 to R9, R13 to R15). Done when: every rule in plan R9 maps to a field. Cheaper substitute: errors shown only in a banner.
- [ ] Write `design/SPEC.md` §5 Status and Test reviewer (plan R10 and R11). Done when: running, review, failover and refused outcomes each have their layout. Cheaper substitute: only the success outcome.
- [ ] Write `design/SPEC.md` §6 TOML preview and diff (plan R12). Done when: added, removed and unchanged line styling is specified. Cheaper substitute: an unstyled text dump.
- [ ] Write `design/SPEC.md` §7 Empty and failure states (plan R16 to R19). Done when: all six states are specified with their action and text. Cheaper substitute: one shared error state.
- [ ] Write `design/SPEC.md` §8 Entry points and SDK source: the command title, both menu entries, the status bar text for every state, the source label, the sign-in and access refusals, and the sync confirmation text (plan R24 to R26). Done when: every status bar text and refusal text is written out. Cheaper substitute: a list of entry points with no texts.
- [ ] Write `design/SPEC.md` §9 Kits view and health: the view container, tree nodes and their states, badges, actions and the doctor check rows (plan R27, R30). Done when: every state and status has its codicon and text. Cheaper substitute: the tree with no states.
- [ ] Write `design/SPEC.md` §10 Kit install and update: each step, the preview groups, the refusal, the scope text and the result lists (plan R28, R29). Done when: every text is written out. Cheaper substitute: steps without texts.
- [ ] Write `design/SPEC.md` §11 New repository setup: each wizard step, the defaults, the summary and the open choice (plan R31). Done when: every step's choices are listed. Cheaper substitute: the first step only.
- [ ] Write `design/SPEC.md` §12 Feature sections: the Reviewers, Plan, Review rounds and WordPress site sections, when each shows, their rows, codicons, descriptions and actions (plan R33 to R37). Done when: every row type has its codicon and text. Cheaper substitute: one screenshot of the side bar.
- [ ] Capture one screenshot per SPEC section and theme into `design/screens/` as `<section>-<dark|light>.png`. Done when: every image link in `design/SPEC.md` resolves to a file. Cheaper substitute: dark theme screenshots only.
- [ ] Commit: `design: interface SPEC from the approved mockup`

**Test checkpoint:** `python -c "import pathlib,re,sys; t=pathlib.Path('design/SPEC.md').read_text(encoding='utf-8'); links=re.findall(r'\]\((screens/[^)]+)\)',t); bad=[l for l in links if not pathlib.Path('design',l).is_file()]; sys.exit(1 if len(re.findall(r'^## \d+\.',t,re.M))<11 or not links or bad else 0)"` exits 0, and exits 1 when a section or a linked screenshot is missing.

## 4. Reviewer config design spec

The brief requires a spec that settles seven decisions before the extension is built, and the owner added an eighth on 2026-10-16: where the SDK comes from (bundled by default). This section writes `docs/specs/<date>-vscode-extension-design.md`, dated the day it is written, from the plan, the approved mockup and `design/decisions.md`. Each decision records the options weighed, the choice, and the cost of reversing it.

**Phase:** 0
**Needs:** none
**Surface:** no

**Build order:**

1. Write the spec with one section per decision. Done when: the spec has the eight sections listed in the checklist, each ending in a reversal cost.
2. Link it from the plan. Done when: `docs/plans/2026-10-16-vscode-extension.md` names the spec path.

- [ ] Settle validation in the spec: the extension never reimplements it and always runs the workspace's own `scripts/review-dispatch.py --check-pin --json --pin <candidate>` (plan R7). Done when: the spec states how the candidate temp file is named, where it lives and when it is deleted. Cheaper substitute: a TypeScript port of `load_pin`.
- [ ] Settle comment-preserving TOML edits in the spec: name the parser or the hand-written editor, and the edits it supports (set a field, add, rename and delete a reviewer table, set a route array) (plan R12). Done when: the spec shows a before and after of the shipped pin for each edit with comments intact. Cheaper substitute: parse and re-serialise, which drops comments.
- [ ] Settle atomic writes in the spec: temp file in the pin's directory, then rename, and the stale-disk check before rename (plan R13). Done when: the spec names the Node or VS Code API used on Windows and in WSL. Cheaper substitute: `fs.writeFile` over the pin.
- [ ] Settle the re-check after every save in the spec (plan R14). Done when: the spec states what the UI shows when the saved pin is refused. Cheaper substitute: trusting the pre-save check.
- [ ] Settle Windows and WSL behaviour in the spec: `extensionKind`, the Remote WSL extension host, the Python resolution order (setting, then `py -3` or `python` on Windows, `python3` on Linux), the 3.11 minimum and workspace trust (plan R19 and R20). Done when: the spec has a table of host, Python command and path form. Cheaper substitute: "uses python" with no resolution order.
- [ ] Settle the supported `schema_version` range in the spec (plan R21). Done when: the spec states the extension's behaviour for 1 and for any other value. Cheaper substitute: no stated range.
- [ ] Settle packaging in the spec: `@vscode/vsce package`, the publisher field, the `.vsix` name, and that marketplace publishing waits for the owner (plan R22). Done when: the spec names `D04 T01 §6` as the decision point. Cheaper substitute: publishing assumed.
- [ ] Settle the SDK source in the spec: the bundle in the `.vsix` (`forge.py` and `kits/` from the build commit, named by `sdk/SDK_COMMIT`) as the default, the local `sdkPath` override, and for the optional GitHub source the REST tarball versus `git clone`, the `repo` scope through VS Code's GitHub sign-in, pinning a ref to a SHA, the cache under `globalStorageUri/sdk/`, the extractor (the `tar` npm package, or the resolved Python's `tarfile` with `filter='data'`, which needs Python 3.11.4 or later), and that downloaded code runs only after a confirmation naming the SHA (plan R24, R25). Done when: the spec names the extractor, the cache layout and every refusal state. Cheaper substitute: "downloads the SDK" with no pinning or extraction rules.
- [ ] Link the spec from `docs/plans/2026-10-16-vscode-extension.md`. Done when: the plan names the spec path. Cheaper substitute: an unlinked spec.
- [ ] Commit: `docs: reviewer config design spec`

**Test checkpoint:** `python -c "import glob,sys; f=glob.glob('docs/specs/*-vscode-extension-design.md'); t=open(f[0],encoding='utf-8').read() if f else ''; m=[s for s in ('--check-pin','comment','atomic','re-check','WSL','schema_version','vsix','GitHub','Reversal cost') if s not in t]; sys.exit(m or not f)"` exits 0, and fails when the spec is missing or a decision is absent.

## 5. Mockup and plan follow the family route rule

> **Started:** 2026-10-20T07:54:32Z

**Corrected 2026-10-20:** validation found that `design/README.md`'s requirement map also describes the self-review warning (R5: "Ready: sonnet on claude, gemini on gemini"), so the section gained a step for it; and that plan R9, `D01 T01 §3`'s fixtures, `D02 T01 §5`'s `errorTarget` and `D03 T01 §5` (built on `selfReview`) also carry the old rule, so the last correction step names them.

**Corrected 2026-10-20:** review round 1 found that "the editor never builds a route the pin refuses" overclaims: changing a reviewer's CLI can break a route, which the mockup shows as `load_pin`'s refusal with Save off. The default is scoped in `design/decisions.md`, plan R4 and `D03 T01 §4`: the route editor never offers a reviewer the pin would refuse, and a route another edit breaks shows the refusal inline. It also found the parity fixtures still read the frozen approval commit, so `design/decisions.md` names the current mockup source commit and `D02 T01 §11` reads it.

The owner decided on 2026-10-20: "the reviewers fallback, it should only be a different family reviewer + 1 fallback". The reviewer kit ships it (`9bd9cb1`, `1bcd0b7`): `load_pin` in `kits/reviewer/templates/scripts/review-dispatch.py` refuses a route longer than two, a reviewer of the writer's family (`FAMILY` and `WRITER_FAMILY`: codex is OpenAI, agy Google, claude Anthropic), and a fallback of the reviewer's own family, and the shipped routes became claude `["astra", "gemini"]`, codex `["gemini", "sonnet"]`, gemini `["astra", "sonnet"]`. The approved design predates it: plan R4 allows a failover list of any length, R5 and `design/decisions.md` answer 1 warn on a same-CLI reviewer that the pin now refuses, R23 names a three-reviewer chain, and the mockup draws all three. `design/decisions.md` says a later design change is a new dated entry applied to the mockup first, so this section makes that change before `§3` writes the SPEC and `§4` the design spec from them.

**Phase:** 0
**Needs:** none
**Surface:** no

**Build order:**

1. Record the decision in `design/decisions.md` as a dated entry, with the editor behaviour it implies taken as a default. Done when: the entry quotes the owner, states the default and its reversal cost, and marks answer 1 superseded.
2. Apply it to `design/mockup/project/Main.dc.html` and republish to the link in `design/README.md`. Done when: the route rows hold at most two chips, offer only reviewers the pin accepts, and the shipped routes and pin comments equal the kit pin.
3. Correct the plan and the later sections that cite the old rule. Done when: no requirement or open section describes a route longer than two or a same-family reviewer.

- [x] Add a dated entry to `design/decisions.md` quoting the owner's 2026-10-20 decision, taking as the default that the editor never builds a route the pin refuses (a route row holds the reviewer and one fallback, the add menu greys out a reviewer of the writer's family and a fallback of the reviewer's family with the reason, and an on-disk route that breaks the rule shows `load_pin`'s refusal inline per answer 3), naming the reversal cost, and marking answer 1 superseded. Done when: the entry is dated 2026-10-20 and answer 1 points to it. Cheaper substitute: a plan change with no decision entry.
- [x] Replace `HEAD` and `ROUTES_COMMENT` in `design/mockup/project/Main.dc.html` with the header and routes comment of `kits/reviewer/templates/.conclave/reviewers.toml`, and the mockup's routes with the shipped ones. Done when: the mockup's preview of the unchanged pin equals the kit pin text line for line. Cheaper substitute: new routes with the old comments.
- [x] Limit each route row in `design/mockup/project/Main.dc.html` to two chips, labelled reviewer and fallback, and hide the add button on a full row. Done when: the claude row reads `1 astra, 2 gemini` with no add button, and removing one chip brings the add button back. Cheaper substitute: allowing a third chip that Save then refuses.
- [x] Grey out in each row's add menu a reviewer of the writer's family and, for the fallback, a reviewer of the first chip's family, each with its reason, in place of the self-review warning (`SELF_CLI` and the chip warnings). Done when: on the codex row the menu greys out `astra` as "same family as the writer", and on a claude row holding `astra` it greys out any other `codex` reviewer as "same family as the reviewer". Cheaper substitute: keeping the warning and letting Save refuse.
- [x] Make the mockup's `validate()` imitate the new `load_pin` refusals with their exact text (`must list one reviewer and at most one fallback`, `of the writer's own family`, `the fallback must be of a third family`), and add a scenario per refusal for a pin edited outside the editor. Done when: each scenario shows its refusal inline at the route row and disables Save. Cheaper substitute: one generic route error.
- [x] Republish `design/mockup/project/` with the Artifact tool to the link in `design/README.md`, and record the new canvas version and commit in `design/decisions.md`. Done when: the link shows the two-chip rows in both themes. Cheaper substitute: a new link that leaves the approved one stale.
- [x] Correct plan R4, R5, R9 and R23 and the shipped-pin fact in `docs/plans/2026-10-16-vscode-extension.md` with dated `**Corrected 2026-10-20:**` notes. Done when: R4 says a route is a reviewer and one fallback of other families, R5 describes the greyed-out choices in place of the warning, R9 lists the three new rules, and R23 names Astra then Gemini 4. Cheaper substitute: a decisions entry the plan contradicts.
- [x] Update the R4 and R5 rows of the requirement map in `design/README.md` to the two-chip rows and the greyed-out add menu, and name the three new refusal scenarios. Done when: no row of the map describes the self-review warning. Cheaper substitute: a map that still points at the removed warning.
- [x] Correct, with dated `**Corrected 2026-10-20:**` notes, the open sections that cite the old rule: `D01 T01 §3` (three refused fixtures), `D02 T01 §5` (`errorTarget`'s message forms), the `D03 T01` Outcome, `§4` (two chips, `routeChoices`) and `§5` (retitled No-route notice, `selfReview` removed with its reason), and `D04 T01 §5` (the review chain). Done when: no open section describes a route longer than two, a self-review warning or a Sonnet fallback for Claude work. Cheaper substitute: leaving the correction to whoever builds them.
- [x] Commit: `design: reviewer routes follow the family rule`

**Test checkpoint:** `python -c "import pathlib,sys; t=pathlib.Path('design/mockup/project/Main.dc.html').read_text(encoding='utf-8'); d=pathlib.Path('design/decisions.md').read_text(encoding='utf-8'); p=pathlib.Path('docs/plans/2026-10-16-vscode-extension.md').read_text(encoding='utf-8'); bad=[s for s in ('must list one reviewer and at most one fallback','the fallback must be of a third family',\"writer: 'claude', names: ['astra', 'gemini'] }\") if s not in t]+[s for s in ('SELF_CLI',) if s in t]+([] if 'different family reviewer + 1 fallback' in d else ['decision'])+([] if 'Corrected 2026-10-20' in p else ['plan']); sys.exit(bad or None)"` exits 0, and fails naming what is missing while the mockup, the decision or the plan still carries the old rule.

**Corrected 2026-10-20:** the checkpoint looked for the TOML line `claude = ["astra", "gemini"]`, which the mockup builds at run time from `shipped()` and never holds as text; it now looks for the route as `shipped()` stores it.

> **Verified:** 2026-10-20 | §5 | 1f0963f337e42f758fd065cea88791d6e897963c
> **Review:** `docs/reviews/d00-t01-s5.json`

## Verification

- The Artifact link in `design/README.md` opens the approved mockup in both themes, and `design/decisions.md` carries the approval date.
- `design/SPEC.md` and `docs/specs/*-vscode-extension-design.md` exist and every check in §3 and §4 passes.
- `python scripts/todo-graph.py validate` and `python scripts/todo-graph.py plan --check` pass.
