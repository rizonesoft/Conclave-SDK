# Conclave VS Code extension: foundation plan

Date: 2026-10-16. Owner: rizonetech. Status: planning; the mockup comes first and nothing is coded until the owner approves it.

This plan is what the `todo/` tree executes. It records the owner's brief (adapted where noted), the facts measured in Conclave-SDK, and the requirement IDs (`Rn`) that TODO sections cite. The design decisions the brief leaves open are settled later, in the spec written after mockup approval (`D00 T01 §4`).

## Goal

A VS Code extension, built in Conclave-SDK at `extensions/vscode/`, that brings the SDK into the editor. It manages a workspace's Conclave-SDK kits (see each kit's state and health, install any kit with a preview, update installed kits, set up a new repository), always by running `forge.py`. And it edits a project's `.conclave/reviewers.toml`, the reviewer kit's pin read by `scripts/review-dispatch.py`: reviewers and their routes, the dispatcher's own validation inline, which reviewer CLIs are installed, a test of one reviewer on a planted bug, and saves with comments kept and an atomic write.

## Deviations from the brief

| Brief | This plan | Why, and the reversal cost |
| --- | --- | --- |
| New repo `conclave-reviewers-vscode` | Conclave-SDK `extensions/vscode/` | Owner, 2026-10-16 |
| Install the base kit there | SDK installs todo and reviewer in itself | To plan and review here |
| Spec and plan after approval | Plan now; spec after approval | Plan routes; spec decides |
| Reviewer pin editor only | Plus a kit manager for every kit | Owner, 2026-10-16 |
| Kits from a checkout or GitHub | Bundled in the `.vsix`, both as overrides | Owner, 2026-10-16 |

## Sources measured in Conclave-SDK (2026-10-16, commit `b7c649b`)

Re-checked 2026-10-16 at `97cca1d`, GitHub `main`: the reviewer kit is unchanged since `b7c649b`, so every fact below still holds. The one new commit lists `reviewer` in `forge.py`'s kit help and moves the todo kit's plan title, acceptance bar and phase names into `todo/plan.json` (and installs `todo/plan.json` in every project that has the todo kit).

- `kits/reviewer/templates/.conclave/reviewers.toml`: the shipped pin. Reviewers `astra` (`codex`, `gpt-6-astra`, effort `medium`), `gemini` (`agy`, `gemini-4-argon-high`, no effort), `sonnet` (`claude`, `claude-sonnet-5-5`, effort `high`). Routes `claude = ["astra", "gemini"]`, `codex = ["gemini", "sonnet"]`, `gemini = ["astra", "sonnet"]` (**Corrected 2026-10-20:** were `claude` and `gemini` `["astra", "gemini", "sonnet"]`, before the owner's family route rule, `design/decisions.md`, Reviewer routes, 2026-10-20). Every table carries a comment above it.
- `kits/reviewer/templates/scripts/review-dispatch.py`: `WRITERS = ("claude", "codex", "gemini")`, `CLIS = ("codex", "agy", "claude")`, `EFFORTS = {"codex": low/medium/high/xhigh, "claude": low/medium/high/xhigh/max}`, `MODEL = ^[a-z0-9][a-z0-9.-]*$`, `NAME = ^[a-z0-9][a-z0-9-]*$`. `load_pin(path)` raises `Refused` on the first fault it meets, with the messages listed under R9. `review()` refuses a writer with no route (`the reviewer pin has no route for writer 'x'`). A hidden `--pin` argument loads another pin path. `main()` requires `--writer` and `--prompt`; exit 2 is a refusal, 1 is no review, 0 is a review.
- `forge.py` `_doctor_reviewer` (line 429): loads the target's pin with the SDK's own `load_pin`, checks `scripts/review-dispatch.py`, `docs/review-round-prompt.md` and the three `independent-review` skills, then reports each reviewer's CLI as `ok` (`shutil.which` found it) or `setup_required`.
- `docs/specs/2026-10-16-reviewer-kit-design.md`: routing table, the one-reviewer rule (amended 2026-10-21), the record format, and that a round with no reviewer is never an approval.
- Defect found while measuring: `load_pin` accepts `schema_version = true`, because Python's `True == 1`. Reproduced with the shipped pin edited to `schema_version = true`: the pin loads. Fixed by `D01 T01 §1`.

## Requirements

### Reviewers

- R1: one card per `[reviewers.<name>]` showing `name`, `cli` (dropdown: codex, agy, claude), `model` (text) and `effort`.
- R2: `effort` is a dropdown of `EFFORTS[cli]`: codex allows low, medium, high, xhigh; claude allows low, medium, high, xhigh, max. For `agy` the field is hidden and a note says Gemini carries the effort in the model name, for example `gemini-4-argon-high`. Changing a card's CLI to `agy` drops its effort; changing it away from `agy` asks for one.
- R3: add, rename and delete a reviewer. Renaming rewrites every route entry that names it. Deleting a reviewer that routes still name shows which routes lose it before it goes.

### Routes

- R4: one row per writer (claude, codex, gemini), each exactly one reviewer, added and removed. The reviewer is never of the writer's model family (codex is OpenAI, agy Google, claude Anthropic); the route editor never offers a reviewer the pin would refuse, and a route that another edit breaks (a reviewer's CLI changed into the writer's family) shows `load_pin`'s refusal inline at the route row with Save off. **Corrected 2026-10-20:** was an ordered failover list of any length, before the owner's family route rule (`design/decisions.md`, Reviewer routes, 2026-10-20). **Corrected 2026-10-21:** was a reviewer and at most one fallback of a third family, reordered by drag and keyboard (`design/decisions.md`, One reviewer per route, 2026-10-21).
- R5: the add menu offers only what the pin accepts: it disables, with the reason, a reviewer of the writer's family ("same family as the writer"), and a row that holds its reviewer has no add menu. **Corrected 2026-10-21:** dropped the reasons "already in this route" and "same family as the reviewer" with the fallback (`design/decisions.md`, One reviewer per route, 2026-10-21). **Corrected 2026-10-20:** the pin now refuses a same-family reviewer (`design/decisions.md`, Reviewer routes, 2026-10-20), so the warning below, the original requirement, is superseded and kept for the record: a warning when a route lets a writer review itself: writer `claude` with a reviewer whose CLI is `claude`, writer `codex` with CLI `codex`, writer `gemini` with CLI `agy`. On the shipped pin it shows twice, on last-resort failovers: `sonnet` (CLI `claude`) on the claude row and `gemini` (CLI `agy`) on the gemini row. A different model through the same CLI counts as self-review, last-resort failovers included (owner, 2026-10-17, `design/decisions.md` answer 1).
- R6: a writer with no route gets no review: the dispatcher refuses that writer. The row says so in place of an empty list, because `load_pin` refuses an empty list but accepts a missing writer.

### Validation

- R7: the extension never reimplements validation. Every check comes from the workspace's own `scripts/review-dispatch.py --check-pin --json`, run on the candidate text written to a temporary file and passed with `--pin`.
- R8: errors show inline at the field they name and match the `Refused` message text exactly. Saving is disabled while any error remains. `load_pin` stops at the first fault, so one error shows at a time, and `--check-pin` keeps reporting one error (owner, 2026-10-17, `design/decisions.md` answer 2).
- R9: the rules, as `load_pin` words them: exactly `schema_version = 1`, `[reviewers.*]` and `[routes]`; at least one reviewer; reviewer names match `NAME`; no keys beyond `cli`, `model`, `effort`; `cli` is one of the three; `model` matches `MODEL`; `agy` carries no effort; codex and claude carry an allowed effort; `[routes]` names only the three writers; each route lists exactly one reviewer, a defined one; no reviewer of the writer's family. **Corrected 2026-10-20:** the family rule and the length rule came with the owner's family route rule (`design/decisions.md`, Reviewer routes, 2026-10-20). **Corrected 2026-10-21:** was one reviewer and at most one fallback, each once, the fallback of a third family (`design/decisions.md`, One reviewer per route, 2026-10-21).

### Status and test

- R10: whether each reviewer's CLI is on PATH, as `forge.py doctor <repo> reviewer` reports it, taken from the `clis` map in the `--check-pin` output (the dispatcher's own `shutil.which`, in the environment the dispatcher runs in).
- R11: a "Test reviewer" action that runs one dispatch on a planted-bug prompt against that reviewer alone and shows the outcome: the reviewer's text, or the reason it gave no review, or the refusal. It asks before every run, naming the reviewer's model, its CLI and the writer (owner, 2026-10-17, `design/decisions.md` answer 6).

### Preview and save

- R12: a TOML preview of the candidate with a diff against the file on disk. Comments and the order of tables are kept: edits change only the values and tables they touch.
- R13: saves are atomic: write a temporary file in the same directory, then rename over the pin. A save is refused when the file on disk changed since it was loaded, and the editor offers to reload.
- R14: the pin is re-checked with `--check-pin` after every save, and the result replaces the status shown.
- R15: discard returns the editor to the text on disk; nothing is written until Save.

### Empty and failure states

- R16: no pin yet: say the reviewer kit is not installed, and show the agent request (the `adopt-conclave` skill, R41) and the equivalent `python forge.py kit <folder> reviewer` command, both copyable. **Corrected 2026-10-20 (read-only kit view, `design/decisions.md`):** offered the kit install flow in R28, preset to `reviewer`.
- R17: a pin whose TOML does not parse, or whose top level is wrong (`schema_version`, missing or extra tables): show the `Refused` message (with `tomllib`'s line and column when it is a parse error), and open the raw file for repair. A fault inside a parsable pin opens the editor with the inline error of R8 instead. **Corrected 2026-10-17:** every refused pin went to this screen; the owner chose the split in `design/decisions.md` answer 3.
- R18: no `scripts/review-dispatch.py` in the workspace, or one too old to support `--check-pin`: say which, and show the agent request and the equivalent `python forge.py sync <repo> --include-scripts` command, both copyable (**Corrected 2026-10-20 (read-only kit view, `design/decisions.md`):** offered the update flow in R29 with scripts included). An old dispatcher is detected by its output: `--check-pin` prints no JSON object with an `ok` key.
- R19: no usable Python (3.11 or later, for `tomllib`), or a workspace that is not trusted: say which, and run nothing. Python is found from `conclave.pythonPath`, then `py -3` and `python` on Windows, `python3` and `python` in WSL; a set but unusable setting is an error, never a silent fallback (owner, 2026-10-17, `design/decisions.md` answer 7).

### SDK source and entry points

- R24: every `forge.py` run uses one SDK source. By default the SDK bundled in the `.vsix`: `forge.py` and `kits/` copied from the commit the extension was built from, named by that SHA. When `conclave.sdkPath` is set, that local checkout instead. When `conclave.sdkRef` is set, the GitHub repository in `conclave.sdkRepository` (default `rizonetech/Conclave-SDK`, which is internal, so the operator must be a signed-in member of the organization) at that ref, resolved to one commit SHA before anything downloads. The download uses VS Code's GitHub sign-in with the `repo` scope (no stored token), is cached per SHA in the extension's global storage, is extracted refusing absolute paths, `..` segments and links, and none of its code runs until the operator confirms a dialog naming the repository and SHA. **Corrected 2026-10-20 (read-only kit view, `design/decisions.md`):** the GitHub source (`conclave.sdkRef`, `conclave.sdkRepository`, the archive download and its extractor) is dropped; the bundled SDK is the source, and `conclave.sdkPath` is a developer override.
- R25: folded into R29 on 2026-10-16 (the dispatcher update is the update flow with scripts included).
- R26: four ways into the reviewer editor. The Command Palette command `Conclave: Open Reviewer Settings` (`conclave.openReviewers`), an Explorer context menu item and an editor title button on `.conclave/reviewers.toml`, and a status bar item that shows the pin's state and opens the editor.

### Kit manager

- R27: a Conclave view in the Activity Bar lists, for the current folder (the only one, or in a multi-root workspace the active editor's folder, switchable), every kit `forge.py kits` returns, each as installed, partly installed or not installed (forge's own `kit --dry-run` decides) with a health badge. **Corrected 2026-10-20 (read-only kit view, `design/decisions.md`):** read only: no install, update or new repository action; a folder whose kit stamp (R38) is newer or older than the bundled kits says so (R40).
- R28 (dropped 2026-10-20, read-only kit view, `design/decisions.md`; importing is the agent's, R41): install any kit with `forge.py kit <folder> <kit>`: choose the agent (all, agy, gemini, claude, codex) and, for WordPress, the host (pressable, wpcom); see forge's `--dry-run` list of files it would add and keep; confirm; then see what it installed. A preview with `merge_needed` paths is refused.
- R29 (dropped 2026-10-20, read-only kit view, `design/decisions.md`; updating is the agent's, R41): update installed kits with `forge.py sync <folder>`, optionally with `--include-scripts`, after a confirmation that states sync's scope (skills, rules, subagents, and with the option existing scripts and `bin/` files; it adds any kit file that is missing and never changes an existing entry doc, `docs/`, `todo/` or pin file), then see what it installed and updated. **Corrected 2026-10-16:** it said sync never touches entry docs, `docs/`, `todo/` or the pin; a sync run measured that day adds a missing kit file there too (`todo/plan.json`, `.conclave/reviewers.toml`, a missing script even without `--include-scripts`) and writes only files that are missing or differ.
- R30: health per installed kit from `forge.py check` and `forge.py doctor <folder> <kit>`: every check's status (`ok`, `missing`, `setup_required`, `unexpected`) and detail, verbatim.
- R31 (dropped 2026-10-20, read-only kit view, `design/decisions.md`; setting up is the agent's, R41): set up a new repository with `forge.py init <folder>`: choose the kits (base always), agent, provisioning mode (isolated by default) and WordPress host; the extension never passes `--force`, so existing entry docs are kept; then open the folder.
- R32 (dropped 2026-10-20 with R28, R29 and R31; the agent checks the protected files with git, R41, and forge refuses a target inside `.git` and init into the SDK folder itself): every install, update and init proves by hash that `AGENTS.md`, `GEMINI.md`, `CLAUDE.md`, `CODEX.md`, `.conclave/reviewers.toml`, `.conclave/automations/tasks.json`, `.conclave/automations/README.md`, `.claude/settings.json`, `todo/` and `docs/` did not change (**Corrected 2026-10-20:** the three files after `reviewers.toml` are project-owned files the `automations` and `todo` kits added that day) unless forge reported writing them, and logs the run (argv, source and SHA, exit code, forge's lists) to the Conclave output channel. Forge has no uninstall, so the operator's git is the undo.
- R38: forge writes a kit stamp, `.conclave/kits.json`, on every `init`, `kit` and `sync` that writes: for each kit in the folder its template digest, and the SDK commit and commit date it came from (2026-10-20, `design/decisions.md`).
- R39: the extension records the digest of its bundled `forge.py` and `kits/` with its version, and a test in Conclave-SDK fails when the kits change without a new extension version (2026-10-20).
- R40: the extension compares each folder's kit stamp with its bundled digest: a folder set up with newer kits says to update the extension, one with older kits says to ask the agent to update the kits, and neither is reported as partly installed (2026-10-20).
- R41: an `adopt-conclave` skill in the base kit imports, updates and checks kits in a project through `forge.py` with the operator: `check` and `doctor` first, each kit's `--dry-run` before writing, conflicts and merges resolved with the operator, the protected files of R32 checked with git afterwards, and a report (2026-10-20).

### Feature sections

- R33: the Conclave side bar holds the Kits tree and, under it, one section per feature, each shown only while its kit is in the current folder (R27's folder); each feature is its own module with commands under `conclave.<feature>.*`, and its data comes from its kit's own script, never from the extension parsing kit files.
- R34: a Plan section (todo kit) shows the sections ready now and each phase with its verified count, from `scripts/todo-graph.py query plan`, with the phase names `todo/plan.json` gives.
- R35: a Review rounds section (reviewer kit) lists each round record and its rounds from `scripts/review-dispatch.py --list-rounds --json`, and marks a round with no reviewer as not an approval.
- R36: a WordPress site section (wordpress kit) shows the site checks of `forge.py doctor <folder> wordpress` verbatim; the extension never writes the site pin.
- R37: a Reviewers section (reviewer kit) shows the pin state from `--check-pin`, each reviewer with its CLI status and each route, and holds Open Reviewer Settings.

### Platform and ship

- R20: works the same on Windows and in WSL, including the Remote WSL extension host, where the extension runs on the Linux side and calls that side's Python.
- R21: supports pin `schema_version` 1 only, and says so for any other version.
- R22: packaged as a `.vsix`. Publishing to the marketplace waits for the owner's decision.
- R23: every fix carries a regression test that fails before it and passes after; the extension's tests run; the change gets up to three independent review rounds through `scripts/review-dispatch.py --writer claude` (Astra). **Corrected 2026-10-20:** was Astra, then Gemini 4, then Sonnet 5.5. **Corrected 2026-10-21:** was Astra failing over to Gemini 4; a route now names one reviewer (`design/decisions.md`, One reviewer per route, 2026-10-21).

## Design spec

How the extension validates, edits, saves and re-checks the pin, runs on Windows and WSL, which `schema_version` it supports, how it is packaged and where the SDK comes from: `docs/specs/2026-10-20-vscode-extension-design.md` (`D00 T01 §4`). The interface is `design/SPEC.md` (`D00 T01 §3`).

## The `--check-pin` contract (Conclave-SDK)

`python3 scripts/review-dispatch.py --check-pin [--json] [--pin <path>]` loads the pin with `load_pin` and never runs a reviewer. With `--json` it prints one object: `{"ok": true, "schema_version": 1, "reviewers": {...}, "routes": {...}, "clis": {"codex": true, "agy": true, "claude": false}}` and exits 0, or `{"ok": false, "error": "<Refused message>"}` and exits 2. `load_pin` stays the only place the rules live. Built by `D01 T01 §2` in the reviewer kit, with the SDK's own installed copy refreshed by `forge.py sync`.

## Phases

| Phase | Work | TODO files |
| --- | --- | --- |
| 0 | Mockup, approval, SPEC, design, queries, scaffold | D00 T01, D01 T01, D02 T01 §1, D06 T01 |
| 1 | Python, dispatcher, pin text, save, SDK source, forge runner, kit ops | D02 T01, D05 T01 |
| 2 | Webview, entry points, Kits view, dialogs, feature sections | D03 T01, D05 T01, D06 T01 |
| 6 | Integration tests, WSL check, `.vsix`, review rounds, docs, marketplace | D04 T01 |

The phase names above are set in `todo/plan.json`, which the generated plan reads.

## Rules

- No em or en dashes anywhere; Markdown prose is one line per paragraph; no AI attribution in commits.
- Every `npm`, `npx` and `node` command runs in `extensions/vscode/`; the Node toolchain lives only there, and the SDK's Python stays standard library only.
- Read `git status` before staging. The CRLF-only changes under `.agents/`, `.claude/`, `.codex/` and `AGENTS.md` are the owner's: never stage or revert them.
- Commit and push to `main` when a section is done; end each report with a `Layer:` line.
