---
schema_version: 1
id: extension-core
domain: 02-extension-core
status: active
title: "TODO-01 -- Extension Core"
---

# TODO-01 -- Extension Core

> **Goal:** A buildable, tested VS Code extension whose host side finds a usable Python on Windows and in WSL, runs the workspace's own `scripts/review-dispatch.py --check-pin --json` to classify the workspace, edits pin text without losing comments, validates every candidate through the dispatcher, saves atomically with a stale-disk check and a re-check, runs every `forge.py` operation through one runner from the SDK bundled in the extension, a local checkout or a pinned GitHub commit, reads each folder's kit state from forge, and runs one reviewer on a planted bug. The webview in `D03 T01` drives all of it through messages and holds no rules of its own.

> **Current state:** Measured 2026-10-16 in Conclave-SDK. No extension code exists: `extensions/vscode/` holds only the contract fixtures from `D01 T01 §3` once that ships, with no `package.json`, `tsconfig.json`, `src/` or `test/` code. Node `v24.14.1`, npm `11.11.0` and VS Code `1.142.0` are installed on the Windows host. Python is available as `python` (3.14.4, `python --version` on 2026-10-16). The dispatcher has no `--check-pin` until `D01 T01 §2`.

## Inputs

- `docs/plans/2026-10-16-vscode-extension.md`: requirements R7 to R23 and the `--check-pin` contract.
- `docs/specs/*-vscode-extension-design.md` from `D00 T01 §4`: the settled decisions this file implements (temp file naming, TOML approach, atomic write API, Python order, schema range, packaging).
- `design/decisions.md` from `D00 T01 §2`: the owner's answers to the open design questions.
- `extensions/vscode/test/fixtures/pins/` and `extensions/vscode/test/fixtures/pins/expected.json` from `D01 T01 §3`: the contract fixtures every test here reuses.
- `scripts/review-dispatch.py`: `--check-pin`, `--pin`, `--writer`, `--prompt`, exit codes 0, 1 and 2.
- `forge.py` `kits`, `kit`, `sync`, `init`, `check` and `doctor` and their JSON (shapes in `D05 T01` Current state), re-checked at `97cca1d`.
- Every `npm`, `npx` and `node` command in this file runs in `extensions/vscode/`.
- -> XREF: D05 T01 §1 -- every kit operation runs forge through §9 and reads state from §10
- GitHub REST `GET /repos/{repo}/commits/{ref}` and `GET /repos/{repo}/tarball/{sha}`; `rizonetech/Conclave-SDK` is internal and has no tags (checked 2026-10-16).
- -> XREF: D00 T01 §4 -- the design spec this file implements
- -> XREF: D01 T01 §3 -- the contract and fixtures the dispatcher client depends on
- -> XREF: D03 T01 §6 -- the webview shows the candidate validation from §5
- -> XREF: D04 T01 §1 -- integration tests exercise every host module here
- -> XREF: D06 T01 §4 -- the Reviewers section shows the dispatcher state from §3
- -> XREF: D06 T01 §1 -- the kit state from §10 decides which feature sections show
- -> XREF: D03 T01 §1 -- every editor surface asserts parity with §11's fixtures
- -> XREF: D05 T01 §5 -- every Kits surface asserts parity with §11's fixtures
- -> XREF: D06 T01 §4 -- every feature section asserts parity with §11's fixtures

## Outcome

- `npm run build`, `npm run lint` and `npm test` pass on Windows; `npm test` covers every module in `extensions/vscode/src/core/` against the fixtures.
- On a workspace with the shipped pin the host reports state `ready` with the three reviewers and their CLI status; on each fixture in `extensions/vscode/test/fixtures/pins/` it reports the exact `Refused` text; on a workspace with no pin, no dispatcher, an old dispatcher, no Python or no trust it reports that state and runs nothing it should not.
- With no SDK setting, forge runs from the bundled SDK and the source label names its build commit; with `conclave.sdkRef` set it runs from `rizonetech/Conclave-SDK` at the SHA that ref resolves to, shown before anything runs; every forge summary is parsed with its lists verbatim, and each folder's kit state agrees with forge's dry run.
- An edit made through the pin text model and saved leaves every comment and table in place, lands through a temp file and rename, and is re-checked; a save over a file changed on disk is refused.

**Adjacency:** list=not-applicable (one pin per workspace folder at the fixed path .conclave/reviewers.toml); document=not-applicable (the pin file is the record; nothing is printed or sent); settings=applicable @ D02 T01 §2; reporting=not-applicable (no summaries over many pins); notifications=not-applicable (single local user; outcomes show in the editor and output channel); permissions=applicable @ D02 T01 §3; audit=applicable @ D02 T01 §3; exchange=not-applicable (TOML on disk is the only format; no import or export); reverse=applicable @ D02 T01 §6

**Adjacency rationale:** Settings are `conclave.pythonPath`, consumed by §2, and `conclave.sdkPath`, `conclave.sdkRepository` and `conclave.sdkRef`, consumed by §7. GitHub access is a second permission: §7 refuses a cancelled sign-in and a repository the operator cannot read, and proceeds when they can. Permissions are workspace trust (an untrusted workspace never runs its dispatcher) and a read-only pin (save refused), both in §3 and §6, with §3 the owner of the trust refusal. Audit is the "Conclave" output channel in §3 that logs every dispatcher command line, exit code and duration, never pin secrets (the pin holds none). Reverse is discard to disk and reload after an external change in §6; after a save, the file's git history is the undo.

## Implementation Order

| Order | Section | Deliverable | Depends On | Status |
| ----- | ------- | ----------- | ---------- | ------ |
| 1 | §1 | Extension scaffold, build and test harness | D00 T01 §4 | [x] |
| 2 | §2 | Python resolution on Windows and WSL | §1 | [x] |
| 3 | §3 | Dispatcher client and workspace states | §2, D01 T01 §3 | [x] |
| 4 | §4 | Comment-preserving pin text model | §1, D01 T01 §3 | [x] |
| 5 | §5 | Candidate validation through check-pin | §3, §4 | [x] |
| 6 | §6 | Atomic save, stale check and re-check | §5 | [x] |
| 7 | §7 | SDK source: local checkout or GitHub commit | §1 | [x] |
| 8 | §8 | Test reviewer runner | §3, §4 | [x] |
| 9 | §9 | Forge runner and summary parsing | §2, §7 | [x] |
| 10 | §10 | Workspace kit state from forge | §9 | [x] |
| 11 | §11 | Mockup parity fixtures and harness | §1, D00 T01 §2 | [ ] |
| 12 | §12 | Extractor limits at tarfile's own parse | §7 | [x] |
| 13 | §13 | Candidate folder links on Windows and shared fallbacks | §5 | [x] |
| 14 | §14 | Extractor checks each member as tarfile reads it | §12 | [x] |
| 15 | §15 | Extractor folder tracking linear in path length | §14 | [x] |
| 16 | §16 | Process tree kill that ends everything or says so | §8 | [x] |
| 17 | §17 | Tree kill: cut-short discovery and combined uncertainty | §16 | [x] |
| 18 | §18 | Kit state SDK watchers released with their last folder | §10 | [x] |
| 19 | §19 | Folder computations bound to the lifetime they were asked in | §10, D05 T01 §3 | [ ] |

## 1. Extension scaffold, build and test harness

> **Started:** 2026-10-20T12:20:23Z

Every later section needs a project that builds, lints and tests. This section creates the extension manifest, TypeScript configuration, bundler and both test layers, with one command that opens an empty placeholder panel so the harness has something real to load. Pure logic lives in `extensions/vscode/src/core/` with no `vscode` import so it runs under `node --test`; VS Code glue lives in `extensions/vscode/src/host/`. It must follow the packaging and layout the spec in `D00 T01 §4` settles; where the spec differs from a path below, the spec wins and this section is corrected first.

**Corrected 2026-10-20:** building it settled three details the section left open. Activation on `conclave.openReviewers` is implicit (VS Code 1.74 and later activate on a contributed command), so `activationEvents` lists only `workspaceContains:.conclave/reviewers.toml`. TypeScript 6 no longer includes `@types` packages by itself, so `tsconfig.json` names `node` and `mocha`; `@types/vscode` is pinned to `1.100.0`, the engine's floor, so no later API type-checks. VS Code lists no output channels, so `activate` returns `{ output }` for the integration test to read the channel. The SDK's dash and table tests now check only the files git tracks or would track (`5bec02e`), so the ignored `node_modules/` is not held to them.

**Phase:** 0
**Needs:** none
**Surface:** no

**Build order:**

1. Write `extensions/vscode/package.json`, `extensions/vscode/tsconfig.json` and `extensions/vscode/esbuild.mjs`. Done when: `npm run build` writes `extensions/vscode/dist/extension.js`.
2. Add lint and both test layers. Done when: `npm run lint`, `npm test` and `npm run test:integration` each pass with one real test.

- [x] Write `extensions/vscode/package.json` with `name` `conclave`, `publisher` from the spec, `engines.vscode` `^1.100.0`, `main` `./dist/extension.js`, `extensionKind` `["workspace"]`, `capabilities.untrustedWorkspaces` with `supported` `"limited"` and `restrictedConfigurations` `conclave.pythonPath`, `conclave.sdkPath`, `conclave.sdkRef` and `conclave.sdkRepository` (design spec section 5; **Corrected 2026-10-20:** was `supported: false`, which keeps the extension from activating in Restricted Mode, so its state could never show), and activation on the command `conclave.openReviewers` and on `workspaceContains:.conclave/reviewers.toml`. Done when: the Extension Development Host lists the extension and `conclave.openReviewers` in the Command Palette. Cheaper substitute: `extensionKind` `ui`, which would run on Windows when the workspace is in WSL.
- [x] Write `extensions/vscode/tsconfig.json` (strict, `module` `node16`, `target` `es2022`, `outDir` `out`) and `extensions/vscode/esbuild.mjs` bundling `extensions/vscode/src/extension.ts` to `extensions/vscode/dist/extension.js` with `vscode` external. Done when: `npm run build` exits 0 and `extensions/vscode/dist/extension.js` exists. Cheaper substitute: shipping unbundled `out/` with `node_modules`.
- [x] Add ESLint with `typescript-eslint` in `extensions/vscode/eslint.config.mjs` and an `npm run lint` script. Done when: `npm run lint` exits 0 and fails on an unused variable. Cheaper substitute: no lint step.
- [x] Add unit tests under `extensions/vscode/test/unit/` run by `npm test` with `node --test` over the compiled `out/test/unit/**/*.test.js`, starting with `extensions/vscode/test/unit/fixtures.test.ts` that reads `extensions/vscode/test/fixtures/pins/expected.json` and asserts every fixture file exists. Done when: `npm test` passes and fails when a fixture is renamed. Cheaper substitute: a test that asserts `true`.
- [x] Add integration tests under `extensions/vscode/test/integration/` run by `npm run test:integration` through `@vscode/test-cli` and `extensions/vscode/.vscode-test.mjs`, starting with one test that activates the extension on `extensions/vscode/test/fixtures/workspaces/shipped/` and runs `conclave.openReviewers`. Done when: the test passes in the downloaded VS Code and fails when the command is unregistered. Cheaper substitute: unit tests only.
- [x] Write `extensions/vscode/src/extension.ts` registering `conclave.openReviewers` that opens a placeholder webview panel titled "Reviewers", and `extensions/vscode/src/host/output.ts` creating the "Conclave" output channel. Done when: the integration test sees the panel and the channel. Cheaper substitute: a command that only shows an information message.
- [x] Add `extensions/vscode/.vscodeignore`, extend the SDK's `.gitignore` with `extensions/vscode/node_modules/`, `out/`, `dist/`, `sdk/`, `.vscode-test/` and `*.vsix`, and add `extensions/vscode/.vscode/launch.json` for the Extension Development Host. Done when: `git status --short` after a build shows no generated files. Cheaper substitute: committing `extensions/vscode/dist/`.
- [x] Document `npm ci`, `npm run build`, `npm run lint`, `npm test` and `npm run test:integration` in `extensions/vscode/README.md` and the SDK's `AGENTS.md`. Done when: each command named runs as written from `extensions/vscode/`. Cheaper substitute: commands left only in `extensions/vscode/package.json`.
- [x] Commit: `extension: scaffold, build and test harness`

**Test checkpoint:** `cd extensions/vscode && npm ci && npm run build && npm run lint && npm test && npm run test:integration` exits 0, and `npm run test:integration` fails when `conclave.openReviewers` is removed from `extensions/vscode/src/extension.ts`.

> **Verified:** 2026-10-20 | §1 | 476e64d36dba4c65e9846c57311ddcc4d411bcb6
> **Review:** `docs/reviews/d02-t01-s1.json`

## 2. Python resolution on Windows and WSL

> **Started:** 2026-10-20T13:06:56Z

The dispatcher is Python 3.11 or later (it imports `tomllib`). The extension runs where the workspace is (`extensionKind` `workspace`), so a Windows folder runs it on Windows and a Remote WSL folder runs it on the Linux side, each with that side's Python (plan R19, R20). This section resolves the interpreter in the order the spec sets, proves its version, and reports a clear state when none is usable. It consumes the setting `conclave.pythonPath`.

**Corrected 2026-10-20:** building it added three defaults the section left open: the probe runs with `-I` (isolated mode) so the working directory and `PYTHON*` variables cannot feed it a module; a Windows batch shim (pyenv-win's `python.bat`) is refused with that reason, since the extension never spawns through a shell; and `activate` returns the resolution and an `onDidResolvePython` event, which the integration test uses to see the re-resolution, since the output channel cannot be read back. Review round 1 added: no lookup or process in Restricted Mode (re-resolved when trust is granted), a runner that kills with `SIGKILL` and always settles (`src/host/run.ts`), a POSIX lookup that skips non-executable files, and resolution per workspace folder, since the setting is machine-overridable.

**Phase:** 1
**Needs:** none
**Surface:** no

**Build order:**

1. Write `extensions/vscode/src/core/python.ts` with a pure resolution function over an injected process runner. Done when: unit tests cover every branch with fake runners.
2. Wire the setting and the real runner in `extensions/vscode/src/host/python.ts`. Done when: on this Windows host it resolves a 3.11 or later interpreter and logs the choice.

- [x] Declare `conclave.pythonPath` (string, default empty, scope `machine-overridable`) in `extensions/vscode/package.json` `contributes.configuration` with a description naming the 3.11 minimum. Done when: the setting shows in the Settings UI. Cheaper substitute: an environment variable read silently.
- [x] Implement `resolvePython(platform, setting, run)` in `extensions/vscode/src/core/python.ts`: the setting when non-empty, else `py -3` then `python` on `win32`, else `python3` then `python`; each candidate is probed with `-c "import sys; print(sys.version_info[:2])"` (spec order wins if it differs). Done when: it returns the first candidate at 3.11 or later with its argv prefix. Cheaper substitute: always running `python`.
- [x] Resolve every candidate (`py`, `python`, `python3`) to an absolute path by searching only the absolute directories on `PATH` in `extensions/vscode/src/core/python.ts`, and spawn that path, never the bare name: on Windows `child_process` and `CreateProcess` search the working directory first, which is the workspace folder, so a `python.exe` committed to a repository would otherwise run (**Corrected 2026-10-20:** added from the measurement in `D01 T01 §5`). Done when: a unit test with a `python.exe` stub in the workspace folder and none on `PATH` resolves nothing from the workspace. Cheaper substitute: spawning the bare name.
- [x] Return a typed refusal from `resolvePython` naming each candidate tried and why it failed (not found, exit code, version too old). Done when: the refusal text lists every candidate. Cheaper substitute: `undefined` with no reason.
- [x] Refuse a `conclave.pythonPath` that is set but unusable without falling back to discovery, so the operator's choice is never silently ignored. Done when: a unit test with a bad setting gets the refusal, not the discovered Python. Cheaper substitute: falling through to `python`.
- [x] Write `extensions/vscode/test/unit/python.test.ts` covering setting, `py -3`, `python`, `python3`, too old (3.10), not found, and bad setting on both platforms. Done when: the tests pass and one fails when the version check is removed. Cheaper substitute: testing only the happy path.
- [x] Wire `extensions/vscode/src/host/python.ts` to `vscode.workspace.getConfiguration('conclave')`, `process.platform` and a `child_process.execFile` runner with a 10 second timeout, re-resolving when the setting changes. Done when: changing the setting in the Extension Development Host logs a new resolution in the output channel. Cheaper substitute: resolving once at activation.
- [x] Commit: `extension: resolve Python 3.11+ on Windows and WSL`

**Test checkpoint:** `cd extensions/vscode && npm run compile && node --test out/test/unit/python.test.js out/test/unit/which.test.js` passes, and fails when `resolvePython` accepts Python 3.10. **Corrected 2026-10-20:** was `npm test -- --test-name-pattern=python`; on Node 24.14.1 `node --test` ran a test that did not match the pattern, so the checkpoint names the test files instead.

> **Verified:** 2026-10-20 | §2 | c1fc4ca1b51087906832d3fbe251f7a93b90381d
> **Review:** `docs/reviews/d02-t01-s2.json`

## 3. Dispatcher client and workspace states

> **Started:** 2026-10-20T13:26:00Z

**Corrected 2026-10-20:** review of `D00 T01 §4` found that `load_pin` accepts TOML layouts the editor cannot edit in place (inline tables, quoted keys, arrays over several lines); a valid pin in one is the read-only `pin-layout` state (`design/decisions.md`, 2026-10-20; design spec section 2), added below.

All validation comes from the workspace's own dispatcher (plan R7). This section runs `scripts/review-dispatch.py --check-pin --json [--pin <path>]` with the resolved Python in the workspace folder and classifies the result into one state the webview renders: `ready`, `refused`, `no-pin`, `no-dispatcher`, `old-dispatcher`, `no-python`, `untrusted` or `unsupported-schema` (plan R16 to R19, R21). It owns the workspace trust refusal and the output channel audit trail.

**Corrected 2026-10-20:** building it settled four details. The checks live in `src/core/workspaceState.ts` over injected trust, files, Python and runner, so the Restricted Mode and no-dispatcher branches are unit tests that prove no process starts, since a VS Code test host cannot be made untrusted; `src/host/dispatcher.ts` wires them. The integration test builds its workspaces in a temporary folder from the kit's own dispatcher and the contract's fixture pins (adding `pin-layout`), instead of committed copies of the dispatcher that would drift. A dispatcher that cannot start or times out has no state of its own in `design/SPEC.md` §7, so it follows the frozen output rule and shows as `old-dispatcher`, with why logged; a dedicated state would be a design change. The output channel keeps its last lines in memory (`recentLog`) for the test, since VS Code cannot read a channel.

**Phase:** 1
**Needs:** none
**Surface:** no

**Build order:**

1. Write `extensions/vscode/src/core/checkPin.ts` parsing dispatcher output into a state. Done when: unit tests over every fixture in `extensions/vscode/test/fixtures/pins/expected.json` get the expected state and exact error text.
2. Write `extensions/vscode/src/host/dispatcher.ts` running the dispatcher and logging each call. Done when: the integration test on the shipped workspace reports `ready`.

- [x] Implement `parseCheckPin(stdout, exitCode)` in `extensions/vscode/src/core/checkPin.ts`: exit 0 with `ok` true is `ready`, exit 2 with `ok` false is `refused` with the `error` text verbatim, and any output that is not one JSON object with an `ok` key is `old-dispatcher` (the detection rule frozen in `D01 T01 §3`). Done when: unit tests over `extensions/vscode/test/fixtures/pins/expected.json` pass. Cheaper substitute: treating every exit 2 as refused.
- [x] Map `refused` with an error starting `no reviewer pin at` to `no-pin` in `parseCheckPin`. Done when: the missing-pin case yields `no-pin`. Cheaper substitute: checking for the file in TypeScript instead of trusting the dispatcher.
- [x] Classify a valid pin whose `schema_version` is not in the spec's supported range as `unsupported-schema` in `extensions/vscode/src/core/checkPin.ts` (plan R21). Done when: a unit test with a stubbed `schema_version` of 2 gets that state. Cheaper substitute: rendering an unknown schema as if it were 1.
- [x] Classify a valid pin of schema version 1 that `isEditableLayout(text)` (§4) rejects as `pin-layout` in `extensions/vscode/src/core/checkPin.ts`, after `--check-pin` says `ok` and before `ready`. Done when: a unit test with the inline-table pin from the design spec section 2 gets `pin-layout` and the shipped pin gets `ready`. Cheaper substitute: opening the editor on it and rewriting the layout on save.
- [x] Classify a workspace with no `scripts/review-dispatch.py` as `no-dispatcher` in `extensions/vscode/src/host/dispatcher.ts` before running Python. Done when: the integration test on `extensions/vscode/test/fixtures/workspaces/no-dispatcher/` reports it. Cheaper substitute: falling back to a bundled dispatcher.
- [x] Refuse to run anything when `vscode.workspace.isTrusted` is false and report `untrusted` in `extensions/vscode/src/host/dispatcher.ts`, re-checking on `onDidGrantWorkspaceTrust`. Done when: an integration test with trust disabled reports `untrusted` and no process starts. Cheaper substitute: relying only on the manifest's `untrustedWorkspaces` flag.
- [x] Run the dispatcher in `extensions/vscode/src/host/dispatcher.ts` with `execFile` (no shell), `cwd` the workspace folder, the Python argv from §2, a 30 second timeout, and one call in flight per folder with later requests coalesced. Done when: two rapid requests start one process. Cheaper substitute: `exec` through a shell string.
- [x] Log every dispatcher call to the "Conclave" output channel in `extensions/vscode/src/host/output.ts`: argv, cwd, exit code, duration and the state. Done when: the channel shows one line per call in the integration test. Cheaper substitute: `console.log`.
- [x] Write `extensions/vscode/test/integration/states.test.ts` over `extensions/vscode/test/fixtures/workspaces/` (`shipped`, `refused`, `no-pin`, `no-dispatcher`, `old-dispatcher`) asserting each state. Done when: every workspace gets its state and the test fails if the old-dispatcher rule is removed. Cheaper substitute: unit tests only.
- [x] Join a `PATH` directory and a file name in `findOnPath` (`extensions/vscode/src/core/which.ts`) with the platform's own separator only: on Linux a directory named `/opt/python\` is a directory whose name ends in a backslash, so `python3` in it is `/opt/python\/python3`, not `/opt/python\python3` (review round 3 of `§2`, the last round its loop allowed, filed here; **Corrected 2026-10-20**). Done when: a unit test with that directory on a Linux `PATH` finds the file and fails on the join at the end of `§2`. Cheaper substitute: treating `\` as a separator everywhere.
- [x] Commit: `extension: dispatcher client and workspace states`

**Test checkpoint:** `cd extensions/vscode && npm run compile && node --test out/test/unit/checkPin.test.js out/test/unit/workspaceState.test.js && npm run test:integration` passes, and the unit run fails when one `error` in `extensions/vscode/test/fixtures/pins/expected.json` is changed. **Corrected 2026-10-20:** names the test files, as `--test-name-pattern` does not filter on Node 24.14.1 (see `§2`).

> **Verified:** 2026-10-20 | §3 | 292f3d5a54a8f199e109738106deb143c5e5feac
> **Review:** `docs/reviews/d02-t01-s3.json`

## 4. Comment-preserving pin text model

> **Started:** 2026-10-20T13:13:28Z

**Corrected 2026-10-20:** review of `D00 T01 §4` found that `load_pin` accepts TOML layouts the editor cannot edit in place (inline tables, quoted keys, arrays over several lines); a valid pin in one is the read-only `pin-layout` state (`design/decisions.md`, 2026-10-20; design spec section 2), added below.

The pin carries a comment above every table, and the owner requires comments to survive edits (plan R12). This section builds the text model: it reads the pin into reviewers and routes for display, and applies edits as minimal text changes so everything it does not touch stays byte for byte. It implements the approach the spec settles in `D00 T01 §4` (a CST-preserving library or a narrow hand-written editor for the pin's grammar) and never validates: an edit it can express is checked by the dispatcher in §5.

**Corrected 2026-10-20:** each golden case is `input.toml`, `edits.json` (the edits in order) and `expected.toml`, written by `python design/spikes/pin_edits.py --write extensions/vscode/test/fixtures/edits`, so the TypeScript replays the reference's own edits; `remove-field-comment` moves `mini` to Antigravity first, as `remove-field` does, so its output is a pin the dispatcher accepts (removing a Codex reviewer's effort alone is refused). Review round 1 added the `route-style` golden case (a route keeps its own spacing; an unchanged route is not rewritten), lines split on `\n` only, and a route pattern without exponential backtracking, in the reference and the port alike.

**Phase:** 1
**Needs:** none
**Surface:** no

**Build order:**

1. Write `extensions/vscode/src/core/pinText.ts` with `readPin(text)` and the edit functions. Done when: unit tests over every valid fixture round-trip byte for byte with no edit.
2. Prove each edit keeps comments. Done when: golden tests under `extensions/vscode/test/fixtures/edits/` pass.

- [x] Implement `readPin(text)` in `extensions/vscode/src/core/pinText.ts` returning reviewers (name, cli, model, effort, source span) and routes (writer, names, source span) for display only. Done when: it reads every valid fixture and returns spans that slice back to the original text. Cheaper substitute: using the dispatcher's JSON for spans it does not have.
- [x] Implement `isEditableLayout(text)` in `extensions/vscode/src/core/pinText.ts`: true only when every line is blank, a comment, `schema_version = <integer>`, a `[reviewers.<name>]` or `[routes]` header, a one-line `key = "value"` or `'value'` without escapes in a reviewer table, or a one-line route array, each optionally ending in a comment (design spec section 2). Done when: unit tests accept the shipped pin and its CRLF copy and reject an inline table, a quoted key, a dotted key, an escape and a route array over two lines. Cheaper substitute: a TOML parse that accepts every layout.
- [x] Implement `setField(text, reviewer, key, value)` for `cli`, `model` and `effort`, including adding and removing an `effort` line. Done when: golden test `extensions/vscode/test/fixtures/edits/set-field/` passes with comments intact. Cheaper substitute: re-serialising the whole table.
- [x] Write the golden cases `set-field`, `add-reviewer`, `remove-field`, `add-field`, `rename-reviewer`, `delete-reviewer`, `set-route`, `remove-route` and `add-route` under `extensions/vscode/test/fixtures/edits/` from the diffs in design spec section 2, generated by `design/spikes/pin_edits.py`, plus `remove-field-comment` and `remove-route-comment` (a trailing comment stays as a comment line) and `add-field-no-final-newline` from the checks in its `main()`. Done when: each case's `input.toml` and `expected.toml` match the reference script's before and after byte for byte. Cheaper substitute: writing expected files by hand from the TypeScript output.
- [x] Implement `addReviewer(text, name, entry)` appending a `[reviewers.<name>]` table after the last reviewer table, before `[routes]`. Done when: golden test `add-reviewer` passes and `[routes]` keeps its comment. Cheaper substitute: appending at end of file after `[routes]`.
- [x] Implement `renameReviewer(text, from, to)` rewriting the table header and every route entry naming it. Done when: golden test `rename-reviewer` passes with every comment kept. Cheaper substitute: renaming the header only.
- [x] Implement `deleteReviewer(text, name)` removing the table and the comment block directly above it, and removing the name from every route. Done when: golden test `delete-reviewer` passes and no orphan comment remains. Cheaper substitute: leaving the comment above a deleted table.
- [x] Implement `setRoute(text, writer, names)` and `removeRoute(text, writer)`, writing the array on one line in the existing style. Done when: golden tests `set-route` and `remove-route` pass. Cheaper substitute: rewriting the whole `[routes]` table.
- [x] Keep line endings: an edit to a CRLF file writes CRLF, an LF file writes LF. Done when: a CRLF copy of the shipped pin round-trips each golden edit with CRLF preserved. Cheaper substitute: normalising to LF on every edit.
- [x] Write `extensions/vscode/test/unit/pinText.test.ts` running each golden case and asserting the output equals `expected.toml` byte for byte and that `scripts/review-dispatch.py --check-pin --json --pin <output>` returns `ok` true. Done when: the tests pass and fail when a comment line is dropped. Cheaper substitute: comparing parsed values only.
- [x] Commit: `extension: comment-preserving pin text model`

**Test checkpoint:** `cd extensions/vscode && npm run compile && node --test out/test/unit/pinText.test.js` passes, and fails when `deleteReviewer` stops removing the comment block above the table. **Corrected 2026-10-20:** was `npm test -- --test-name-pattern=pinText`, which does not filter on Node 24.14.1 (see `§2`).

> **Verified:** 2026-10-20 | §4 | d131b992853974b3559e06a3e1260b72f6ff1c4f
> **Review:** `docs/reviews/d02-t01-s4.json`

## 5. Candidate validation through check-pin

> **Started:** 2026-10-20T13:44:20Z

Every edit produces candidate text that must be checked by the dispatcher, not by the extension (plan R7, R8). This section writes the candidate to a temporary file named and placed as the spec says, runs `--check-pin --json --pin <temp>`, maps the `Refused` message to the field it names, and deletes the temp file. Saving stays disabled while the latest candidate is refused.

**Corrected 2026-10-20:** building it settled three details: the targets are the SPEC §4 places (name, unknown-keys, cli, model, stray-effort, effort, cards, unknown-writer, a writer's route row, the pin-refused screen for the schema and unreadable forms, and the file for anything else); the candidate folder is the spec's shared `<tmpdir>/conclave/` unless on POSIX it belongs to another account or others may enter it, then a fresh private folder for the process; and `activate` returns `checkCandidate(folder, text)` for the webview (`D03 T01`) and the integration test.

**Phase:** 1
**Needs:** none
**Surface:** no

**Build order:**

1. Write `extensions/vscode/src/core/errorTarget.ts` mapping a `Refused` message to a target (reviewer and field, route row, or file). Done when: every refused fixture maps to the field `design/SPEC.md` §4 names.
2. Write `extensions/vscode/src/host/candidate.ts` running the check on a debounced candidate. Done when: an integration test sees `ok` false within one second of a bad edit and `ok` true after the fix.

- [x] Implement `errorTarget(message)` in `extensions/vscode/src/core/errorTarget.ts` keyed on the message forms in `load_pin` (`invalid reviewer`, `has unknown keys`, `needs cli`, `has a malformed model`, `set no effort`, `needs effort`, `[routes] may only name`, `route ... must list`, `of the writer's own family`, `the fallback must be of a third family`, `unreadable reviewer pin`, `needs exactly schema_version`). **Corrected 2026-10-20:** `route ... must be` became `route ... must list`, and the two family forms are new, with the owner's family route rule (`design/decisions.md`, Reviewer routes, 2026-10-20); all three target the route row. Done when: each refused fixture maps to its target. Cheaper substitute: always targeting the file.
- [x] Fall back to a file-level target for any message `errorTarget` does not recognise, keeping the text verbatim. Done when: a unit test with an unknown message gets the file target and the same text. Cheaper substitute: dropping unknown messages.
- [x] Write the candidate in `extensions/vscode/src/host/candidate.ts` to the temp path the spec names, with a unique name per check, and delete it in a `finally`. Done when: after 50 checks the temp directory holds no candidate files. Cheaper substitute: writing the candidate over the real pin.
- [x] Debounce checks by 300 ms and discard a result that is older than the latest edit. Done when: a unit test of the sequencing with fake timers shows only the newest result applied. Cheaper substitute: applying results in completion order.
- [x] Expose `canSave` as true only when the latest candidate is `ok` true and differs from disk. Done when: a unit test covers refused, valid-unchanged and valid-changed. Cheaper substitute: enabling Save while a check is in flight.
- [x] Write `extensions/vscode/test/unit/errorTarget.test.ts` over `extensions/vscode/test/fixtures/pins/expected.json`. Done when: the tests pass and fail when one message form is removed. Cheaper substitute: testing two messages.
- [x] Strengthen the save-during-check regression in `extensions/vscode/test/integration/states.test.ts`: let the first run finish reading the valid pin and hold its completion with the `ready` reply in hand, save the refused pin, queue the fresh check, then release the first run and assert the exact publication sequence, so removing `DispatcherClient`'s generation guard fails the test (review round 3 of `§3`, the last round its loop allowed, filed here; **Corrected 2026-10-20**). Done when: the test fails with the guard removed and passes with it. Cheaper substitute: releasing the older run after the save, where both runs read the same pin.
- [x] Commit: `extension: validate every candidate through check-pin`

**Test checkpoint:** `cd extensions/vscode && npm run compile && node --test out/test/unit/errorTarget.test.js out/test/unit/candidate.test.js` passes, and fails when `canSave` ignores a refused candidate. **Corrected 2026-10-20:** names the test files, as `--test-name-pattern` does not filter on Node 24.14.1 (see `§2`).

> **Verified:** 2026-10-20 | §5 | 4de1002c523ae5121b2772a83d5177c45e43eb20
> **Review:** `docs/reviews/d02-t01-s5.json`

## 6. Atomic save, stale check and re-check

> **Started:** 2026-10-20T14:20:00Z

Saves must never leave a half-written pin and must never overwrite a change made outside the editor (plan R13 to R15). This section saves the validated candidate through a temp file in the pin's directory and a rename, refuses when the file on disk no longer matches what was loaded, re-checks the saved pin with `--check-pin`, and offers discard and reload. It owns the reverse path for the editor.

**Phase:** 1
**Needs:** none
**Surface:** no

**Build order:**

1. Write `extensions/vscode/src/host/save.ts` with the stale check, temp write and rename. Done when: an integration test saves an edit and reads back the exact candidate.
2. Add re-check, discard, reload and the read-only refusal. Done when: integration tests cover each.

- [x] Record the loaded text's SHA-256 when the editor opens or reloads, in `extensions/vscode/src/host/save.ts`. Done when: the hash is logged in the output channel. Cheaper substitute: comparing modification times only.
- [x] After the temporary file is written and synced, as the last step before the rename and again before every `EPERM` or `EBUSY` retry, re-read the pin and refuse the save with state `stale` when its hash differs from the loaded one, deleting the temporary file (design spec section 3; **Corrected 2026-10-20:** the check ran before the write, which left the write and the retry delays unguarded). Done when: integration tests that change the pin on disk mid-session, during the temporary write (a test hook between write and rename) and during a retry delay each get `stale` with the other program's text intact and no temporary file left. Cheaper substitute: checking once before writing.
- [x] Write the candidate to a temp file in `.conclave/` with the spec's name pattern and rename it over `reviewers.toml` using the API the spec names, deleting the temp file on any failure. Done when: an integration test reads back the candidate byte for byte and finds no temp file left. Cheaper substitute: `fs.writeFile` on the pin.
- [x] Refuse the save with a clear message when the pin or `.conclave/` is read-only, leaving the file untouched. Done when: an integration test with a read-only pin gets the refusal. Cheaper substitute: a raw `EPERM` error.
- [x] Re-run `--check-pin --json` on the saved pin and publish the result as the new state (plan R14). Done when: the integration test sees a check logged after every save. Cheaper substitute: reusing the pre-save result.
- [x] Implement `discard()` returning the editor to the loaded text and `reload()` re-reading disk after `stale` or an external change seen by a `FileSystemWatcher` on `.conclave/reviewers.toml`. Done when: integration tests show both return the model to the disk text. Cheaper substitute: requiring the panel to be closed and reopened.
- [x] Write `extensions/vscode/test/integration/save.test.ts` covering save, stale, read-only, re-check, discard and reload on a copy of `extensions/vscode/test/fixtures/workspaces/shipped/`. Done when: all pass and the stale test fails when the hash check is removed. Cheaper substitute: unit tests with a mocked file system only.
  Built as `PinSession` in `extensions/vscode/src/host/save.ts`, opened through the API's `openPin(folder, hooks)` (the hooks are the test points between write and rename, the rename, and the retry wait); D03 builds the editor on it. A save returns `saved` (with the re-check state and design spec section 4's toast text), `stale`, `read-only` or `failed`.
- [x] Commit: `extension: atomic save with stale check and re-check`

**Test checkpoint:** `cd extensions/vscode && npm run test:integration -- --grep save` passes, and the stale case fails when the hash comparison in `extensions/vscode/src/host/save.ts` is removed.

> **Verified:** 2026-10-20 | §6 | 90c69b62a5008e405b743cd943b6d44701defeea
> **Review:** `docs/reviews/d02-t01-s6.json`

## 7. SDK source: local checkout or GitHub commit

> **Started:** 2026-10-20T13:33:14Z

**Corrected 2026-10-20:** the design spec (section 8, approved through `D00 T01 §4`) puts the archive member checks in the extraction script that ships inside the `.vsix` (`extensions/vscode/resources/extract_sdk.py`, run with the resolved Python in isolated mode), with `tarfile`'s `filter="data"` as a second layer; this section said `src/core/sdkSource.ts`. The checks live in the script, so one place holds them, and the checkpoint's traversal case is run against it. The GitHub source also needs Python 3.11.4 or later for the data filter (spec section 5), checked before any request.

Every `forge.py` run goes through §9 from one SDK source (plan R24). This section decides which and produces a local folder holding it: the checkout in `conclave.sdkPath` when set; otherwise, when `conclave.sdkRef` is set, a download of `conclave.sdkRepository` at that ref, resolved to one commit SHA, through VS Code's GitHub sign-in, cached per SHA in the extension's global storage; otherwise the SDK bundled in the extension at `<extensionPath>/sdk/`, built by `D04 T01 §4` with its commit in `sdk/SDK_COMMIT`. It runs no SDK code itself: it returns the folder, the SHA (or `local`) and the label the confirmations show. The default repository is internal, so a cancelled sign-in or no access are expected refusals with their own states, never crashes.

**Corrected 2026-10-20:** building it added defaults the section left open: the extractor also refuses an archive of more than 20,000 members or 200 MB unpacked, and a file directly at the top; `sdkRepository` and `sdkRef` are machine-overridable like `sdkPath`; the GitHub source's label is `<owner>/<name>@<short sha>`; and two resolutions of one ref share one download.

**Phase:** 1
**Needs:** none
**Surface:** no

**Build order:**

1. Write `extensions/vscode/src/core/sdkSource.ts` with the pure parts: setting precedence, repository and ref validation, and archive entry checks. Done when: unit tests cover every branch.
2. Write `extensions/vscode/src/host/sdkSource.ts` with sign-in, ref resolution, download, extraction and cache. Done when: an integration test against a local stand-in for the GitHub API returns a cached folder holding `forge.py` and its SHA.

- [x] Declare `conclave.sdkPath` (string, default empty, scope `machine-overridable`), `conclave.sdkRepository` (string, default `rizonetech/Conclave-SDK`) and `conclave.sdkRef` (string, default empty) in `extensions/vscode/package.json` `contributes.configuration`. Done when: all three show in the Settings UI with descriptions that state the precedence. Cheaper substitute: a hard-coded `R:\GitHub\Conclave-SDK`.
- [x] Implement `chooseSource(settings)` in `extensions/vscode/src/core/sdkSource.ts`: a non-empty `sdkPath` wins and must hold `forge.py` and `kits/`; otherwise a non-empty `sdkRef` selects GitHub; otherwise the bundle. A set but unusable `sdkPath` is a refusal (`sdk-path-invalid`), never a silent fall-through. Done when: unit tests cover each precedence step and the bad path. Cheaper substitute: falling back to the bundle when the local path is wrong.
- [x] Resolve the bundled source from `<extensionPath>/sdk/`, requiring `forge.py`, `kits/` and `SDK_COMMIT`, labelled `bundled Conclave-SDK@<sha>`; in the Extension Development Host with no bundle, use the SDK checkout the extension runs from (two folders up from `extensions/vscode/`, holding `forge.py`), labelled `local Conclave-SDK (development)`. A packaged extension without its bundle is the refusal `sdk-bundle-missing`. Done when: unit tests cover packaged, development and missing. Cheaper substitute: always using the development path.
- [x] Validate `sdkRepository` against `^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$` and `sdkRef` as a git ref name (no `..`, no leading `-`, no whitespace) before any request. Done when: unit tests refuse `../x`, an empty value and a URL. Cheaper substitute: interpolating settings into request URLs unchecked.
- [x] Ask for a session with `vscode.authentication.getSession('github', ['repo'], { createIfNone: true })` only when the GitHub source is needed, and refuse with state `github-signin` when the operator cancels. Done when: an integration test with a cancelled sign-in gets that state and makes no request. Cheaper substitute: a token read from a setting or an environment variable.
- [x] Resolve `sdkRef` to a 40-character SHA with `GET /repos/{repo}/commits/{ref}`, mapping 401 and 404 to `github-no-access` (an internal repository answers 404 to a non-member), 403 with `x-ratelimit-remaining: 0` to `github-rate-limited`, and network errors to `github-offline`. Done when: unit tests over recorded responses produce each state. Cheaper substitute: downloading `main` without pinning a SHA.
- [x] Reuse `globalStorageUri/sdk/<sha>/` when it holds a complete extraction, marked by a `.complete` file written last. Done when: resolving the same SHA twice makes one download request. Cheaper substitute: downloading on every install.
- [x] Download `GET /repos/{repo}/tarball/{sha}` to a temp file in `globalStorageUri/sdk/` and extract it with the extractor the spec names into `<sha>.partial/`, after checking every member first and refusing the whole archive for any member that is not a regular file or directory, an absolute name (leading `/` or `\`, or a drive letter), a `..` segment on either separator, or a name outside the single top folder, then extracting with `filter="data"` as a second layer, then rename to `<sha>/` (atomic on the same volume; design spec section 8; **Corrected 2026-10-20:** the data filter alone strips a leading `/` and keeps links inside the target, so the member check comes first). Done when: unit tests with crafted archives holding `../evil`, `/abs`, `C:/abs`, `a\..\b`, an internal symlink, a hard link and a second top folder each refuse and leave no folder behind. Cheaper substitute: relying on the data filter alone.
- [x] Keep the three most recently used SHAs in the cache and delete older folders after a successful extraction. Done when: a fourth SHA removes the oldest folder. Cheaper substitute: an unbounded cache.
- [x] Log the source (local path, or repository and SHA), each request's status and the cache hit or miss to the "Conclave" channel, never the token. Done when: a test asserts the session token string never reaches the channel. Cheaper substitute: logging request headers.
- [x] Write `extensions/vscode/test/unit/sdkSource.test.ts` and `extensions/vscode/test/integration/sdkSource.test.ts`, the latter against a local HTTP server standing in for the GitHub API through an injected base URL. Done when: both pass and the traversal test fails when the entry check is removed. Cheaper substitute: tests that call the real GitHub.
- [x] Commit: `extension: resolve the SDK from a local checkout or a GitHub commit`

**Test checkpoint:** `cd extensions/vscode && npm run compile && node --test out/test/unit/sdkSource.test.js out/test/unit/extractSdk.test.js && npm run test:integration` passes, and fails when the member check in `extensions/vscode/resources/extract_sdk.py` accepts `../evil`. **Corrected 2026-10-20:** was `--test-name-pattern` (it does not filter on Node 24.14.1) and the entry check in `src/core/sdkSource.ts` (see above).

> **Verified:** 2026-10-20 | §7 | f8e4144e963557e2d32ed91c2841fe20b4b219c6
> **Review:** `docs/reviews/d02-t01-s7.json`

## 8. Test reviewer runner

> **Started:** 2026-10-20T14:45:00Z

The owner asked for a "Test reviewer" action (plan R11). This section builds a temporary pin with only the chosen reviewer on a route, runs `scripts/review-dispatch.py --writer <w> --prompt <planted-bug> --pin <temp>` with the resolved Python, and returns the outcome: the review text, the failover reason, or the refusal. The planted-bug prompt ships as `extensions/vscode/resources/planted-bug-prompt.md`. It runs a real model, so it asks first, and it can be cancelled.

**Phase:** 1
**Needs:** none
**Surface:** no

**Build order:**

1. Write `extensions/vscode/src/core/testPin.ts` building the single-reviewer pin text from the candidate. Done when: `--check-pin` accepts its output for each shipped reviewer.
2. Write `extensions/vscode/src/host/testReviewer.ts` running the dispatch with confirmation, cancellation and timeout. Done when: an integration test with a fake CLI on PATH returns its review text.

- [x] Write `extensions/vscode/resources/planted-bug-prompt.md`: a short review prompt over an inline code snippet with one off-by-one bug, asking for findings only. Done when: running it through `sonnet` on this host returns a review that names the bug. Cheaper substitute: a prompt with no planted bug, which proves only that the CLI starts.
  Run 2026-10-20 through the kit's dispatcher with a one-reviewer pin (`sonnet`, writer `codex`): Sonnet 5.5 named the off-by-one in the range bound, `window_sums([1, 2, 3, 4], 2)` returning `[3, 5]`, and the corrected `range(len(values) - size + 1)`.
- [x] Implement `singleReviewerPin(pinText, name)` in `extensions/vscode/src/core/testPin.ts` keeping the chosen reviewer table and setting one route to `[name]`, choosing a writer the reviewer cannot be (claude for agy and codex reviewers, codex for claude reviewers). Done when: unit tests show `--check-pin` accepts it for astra, gemini and sonnet. Cheaper substitute: running the full route, which tests failover instead of the reviewer.
- [x] Confirm before running in `extensions/vscode/src/host/testReviewer.ts` with a modal that names the reviewer, model and CLI and says a real model call is made. Done when: cancelling starts no process. Cheaper substitute: running on click.
  The default confirmation is a modal (`Run test`); the API takes a `confirm` function, so the in-card confirmation of `design/SPEC.md` section 5 replaces it when the editor is built.
- [x] Run the dispatch with a timeout from the spec and a cancellation token that kills the process tree. Done when: cancelling a fake slow CLI leaves no child process. Cheaper substitute: no cancel.
  **Corrected 2026-10-20:** the spec names no timeout for a test run, so the default is the dispatcher's `--timeout 600` for the reviewer (real reviews here take two to six minutes) and the process is killed 60 s after that. Cancel and timeout kill the whole tree through `run(..., { tree: true, signal })` in `extensions/vscode/src/host/run.ts`: `taskkill /T /F` on Windows, and on POSIX the descendants found by parent id from `ps` (stopped, then killed), since the dispatcher starts each reviewer in its own session. `run` also returns stderr now, where the dispatcher writes its refusals.
- [x] Parse the dispatcher's JSON summary into `review`, `failover` or `refused` outcomes, keeping the review text verbatim. Done when: unit tests over saved summaries cover all three. Cheaper substitute: showing raw stdout.
  `parseTestRun` in `extensions/vscode/src/core/testOutcome.ts`, over the saved answers in `extensions/vscode/test/fixtures/dispatch/` (the failover one captured from the kit's dispatcher); a run that never finished or printed no summary is never a review.
- [x] Delete the temp pin in a `finally` and log the run to the output channel. Done when: no temp pin remains after success, failure or cancel. Cheaper substitute: leaving temp files.
- [x] Write `extensions/vscode/test/integration/testReviewer.test.ts` with fake `codex`, `agy` and `claude` scripts on PATH returning a review, failing and hanging. Done when: the three outcomes are asserted and the hang case is cancelled. Cheaper substitute: calling real models in tests.
- [x] Commit: `extension: test one reviewer on a planted bug`

**Test checkpoint:** `cd extensions/vscode && npm test -- --test-name-pattern=testPin && npm run test:integration -- --grep testReviewer` passes, and fails when `singleReviewerPin` routes the reviewer to its own writer.

> **Verified:** 2026-10-20 | §8 | b630408b914a20868e24a6369620e248e7299bd5
> **Review:** `docs/reviews/d02-t01-s8.json`

## 9. Forge runner and summary parsing

> **Started:** 2026-10-20T15:10:00Z

Every kit operation in `D05 T01` runs `forge.py` the same way, so this section is the one runner. It takes the SDK folder and label from §7 and the Python prefix from §2, runs `forge.py <command> ...` with `execFile` (never a shell), a timeout and cancellation, and parses forge's JSON for `kits`, `kit`, `sync`, `init`, `check` and `doctor` into typed results that keep every list verbatim. A non-zero exit, or output that is not forge's JSON, is a typed failure carrying forge's stderr tail.

**Phase:** 1
**Needs:** none
**Surface:** no

**Build order:**

1. Write `extensions/vscode/src/core/forgeJson.ts` parsing each command's output. Done when: unit tests over recorded outputs pass.
2. Write `extensions/vscode/src/host/forge.ts` running forge. Done when: an integration test with a fake SDK runs, times out and cancels a command.

- [x] Write `extensions/vscode/scripts/record-forge-fixtures.py` (stdlib) that runs the SDK's own `forge.py` (`kits`, `kit --dry-run`, `kit`, `sync`, `init`, `check`, `doctor`) on temp folders and saves each output under `extensions/vscode/test/fixtures/forge/`. Done when: running it twice produces identical fixtures apart from the temp paths it normalises. Cheaper substitute: hand-typed fixtures.
  Two runs give identical fixtures (`diff -r` clean); a refusal is recorded as `kit-refused.stderr` with its exit code.
- [x] Implement the parsers in `extensions/vscode/src/core/forgeJson.ts`: `kits` to names; `kit` to `installed`, `updated`, `preserved`, `merge_needed`, `dry_run`; `sync` and `init` to `written`, `skipped` and per-kit summaries; `check` to its flags and per-agent skill lists; `doctor` to checks. Done when: unit tests over every fixture pass. Cheaper substitute: untyped JSON passed through.
- [x] Refuse a shape a parser does not know (missing key, wrong type) with the raw text. Done when: a unit test with `installed` missing gets the refusal. Cheaper substitute: treating missing lists as empty.
- [x] Implement `runForge(source, python, args, token)` in `extensions/vscode/src/host/forge.ts` with `execFile`, `cwd` the SDK folder, a 120 second default timeout and a cancellation token that kills the process tree. Done when: an integration test cancels a sleeping fake forge and leaves no process. Cheaper substitute: `exec` with a command string.
  Built as `runForge(source, python, args, parse, { signal, timeoutMs })` in `extensions/vscode/src/host/forge.ts`: an `AbortSignal` is the cancellation token (as in `§8`), forge runs with `-I` (it imports only the standard library), and the kill is `run`'s tree kill from `§8`. The API's `runForge(source, args, options)` picks the parser by command and refuses a command it has no parser for.
- [x] Map outcomes: exit 0 with forge's JSON is success; a non-zero exit is a failure with the last 20 lines of stderr; exit 0 without JSON is a failure naming the command. Done when: unit tests cover each. Cheaper substitute: success whenever the exit code is 0.
- [x] Log each run's argv, cwd, source label, exit code and duration to the "Conclave" output channel. Done when: the integration test reads one line per run. Cheaper substitute: no log.
- [x] Write `extensions/vscode/test/unit/forgeJson.test.ts` and `extensions/vscode/test/integration/forgeRunner.test.ts`. Done when: both pass and the unit run fails when exit 0 without JSON counts as success. Cheaper substitute: happy-path tests only.
- [x] Commit: `extension: one forge runner with typed summaries`

**Test checkpoint:** `cd extensions/vscode && npm run compile && node --test out/test/unit/forgeJson.test.js && npm run test:integration -- --grep forgeRunner` passes, and fails when a summary missing `installed` is accepted. **Corrected 2026-10-20:** was `npm test -- --test-name-pattern=forgeJson`, which does not filter on Node 24.14.1 (see `§2`).

> **Verified:** 2026-10-20 | §9 | 1746c345ee38681335d59c874a104527bc3c12b0
> **Review:** `docs/reviews/d02-t01-s9.json`

## 10. Workspace kit state from forge

> **Started:** 2026-10-20T15:45:00Z

The Kits view, the dialogs and the reviewer editor need each folder's kit state (plan R27) without reimplementing forge. The rule comes from forge itself: for each kit `forge.py kits` returns, run `forge.py kit <folder> <kit> --dry-run --agent all`. An empty `installed` list means installed; a non-empty `installed` with a non-empty `preserved` means partly installed; an empty `preserved` means not installed. The state is relative to all three agents' folders, so a repository provisioned for one agent shows partly installed and says why.

**Phase:** 1
**Needs:** none
**Surface:** no

**Build order:**

1. Write `extensions/vscode/src/core/kitState.ts` with the rule. Done when: unit tests over recorded dry runs give the expected states.
2. Write `extensions/vscode/src/host/kitState.ts` with caching and refresh. Done when: an integration test reads every kit's state for the shipped workspace and refreshes after a change.

- [x] Implement `kitState(dryRun)` in `extensions/vscode/src/core/kitState.ts` with the rule above, returning the state and the counts of files forge would add and keep. Done when: unit tests over recorded dry runs (an empty folder, a base-only folder, a folder with every kit, a claude-only folder) give not installed, installed and partly installed as expected. Cheaper substitute: one marker file per kit checked in TypeScript.
  The dry runs are recorded by `extensions/vscode/scripts/record-forge-fixtures.py` (`dry-<folder>-<kit>.json`). **Corrected 2026-10-20:** a fourth state, `unavailable`, carries forge's own refusal (the laravel kit outside a Laravel app exits 2, `No artisan found`); a file forge would update on a refresh counts as kept.
- [x] Explain partly installed with the count and the first five paths forge would add. Done when: the claude-only fixture's state names `.agents/` and `.codex/` paths. Cheaper substitute: "partly" with no reason.
  The reason leads with where the missing files are (`14 of 28 files are missing (5 in .agents/, 7 in .codex/, CODEX.md, GEMINI.md): ...`), then the first five paths.
- [x] Run the dry runs for a folder one at a time through §9 and cache them until a `FileSystemWatcher` on `.agents/`, `.claude/`, `.codex/`, `.conclave/`, `scripts/`, `todo/` or `docs/` fires or a `D05 T01` operation finishes. Done when: an integration test sees no forge call on a second read and one after a change. Cheaper substitute: re-running on every render.
  **Corrected 2026-10-20:** the root agent documents (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `CODEX.md`) are watched too, since the base kit writes them. A burst of changes (an install writes dozens of files) gives one event after 300 ms of quiet; without that, one install gave 85. A folder leaving the workspace drops its watchers and cache (`forget`), as the watchers hold a folder open on Windows.
- [x] Expose `onDidChangeKitState(folder)` for the Kits view and the reviewer editor. Done when: the test sees one event after an install. Cheaper substitute: polling.
- [x] Write `extensions/vscode/test/unit/kitState.test.ts` and `extensions/vscode/test/integration/kitState.test.ts`. Done when: both pass and the unit run fails when an empty `preserved` list is read as partly installed. Cheaper substitute: unit tests only.
- [x] Commit: `extension: workspace kit state from forge's dry run`

**Test checkpoint:** `cd extensions/vscode && npm run compile && node --test out/test/unit/kitState.test.js && npm run test:integration -- --grep kitState` passes, and fails when an empty `preserved` list is read as partly installed. **Corrected 2026-10-20:** was `npm test -- --test-name-pattern=kitState`, which does not filter on Node 24.14.1 (see `§2`).

> **Verified:** 2026-10-20 | §10 | 5ceefb0f848dc41944127b9a49be1b57eaf25d77
> **Review:** `docs/reviews/d02-t01-s10.json`

## 11. Mockup parity fixtures and harness

The build must match the approved mockup 1:1 (`design/platform-audit.md`), and a careful look is not proof. The mockup's own script already computes, for every scenario, each row's label, description, icon, badge, order and actions and every message text. This section exports that view model from the current mockup source `design/decisions.md` names (**Corrected 2026-10-20:** was the frozen mockup, which predates the family route rule) into fixtures, and gives every surface section one helper that fails on any difference. The example data (the orchard workspace, its plan and rounds) is test input fed to the extension, never product content.

**Phase:** 1
**Needs:** none
**Surface:** no

**Build order:**

1. Write `extensions/vscode/scripts/export-parity.mjs` and commit its output under `extensions/vscode/test/parity/fixtures/`. Done when: one JSON file exists per scenario, side bar state, workspace and theme the mockup offers.
2. Write `extensions/vscode/test/parity/expectParity.ts` and the webview screenshot comparison. Done when: a deliberately changed label fails both.

- [ ] Write `extensions/vscode/scripts/export-parity.mjs`: read the `data-dc-script` block of `design/mockup/project/Main.dc.html` at the current mockup source commit `design/decisions.md` names (the latest dated change's commit, else the frozen one; **Corrected 2026-10-20:** was the frozen commit, which predates the family route rule), run `Component.renderVals()` with each `scenario`, `sidebar`, `workspace` and `theme`, and write the result without functions to `extensions/vscode/test/parity/fixtures/<sidebar>.<scenario>.<workspace>.<theme>.json`. Done when: `cd extensions/vscode && node scripts/export-parity.mjs` writes every combination and a second run changes nothing. Cheaper substitute: fixtures typed by hand.
- [ ] Record the example inputs the mockup uses (the forge dry runs and doctor checks per scenario, the `--check-pin` results, `todo-graph.py query plan` and `--list-rounds` output) as fake runner outputs in `extensions/vscode/test/parity/inputs/`, so the extension renders the same example data the mockup drew. Done when: each fixture names the input set it was drawn from. Cheaper substitute: stripping the example rows from the fixtures.
- [ ] Add a check in `extensions/vscode/test/parity/fixtures.test.ts` that re-runs the export and compares it with the committed fixtures. Done when: editing a label in the mockup without re-exporting fails the test. Cheaper substitute: exporting once and never again.
- [ ] Write `expectParity(surface, fixtureId, actual)` in `extensions/vscode/test/parity/expectParity.ts`, comparing tree rows (label, description, `ThemeIcon` id and colour, decoration badge, tooltip, inline actions, order), view titles, descriptions and title actions, and webview texts and control states, and reporting every difference at once. Done when: a unit test shows one changed description, icon or row order each failing with the exact field. Cheaper substitute: comparing row counts.
- [ ] Map each mockup icon to its `ThemeIcon` id and each mockup colour class to its theme colour id from `design/platform-audit.md` in `extensions/vscode/test/parity/mapping.ts`. Done when: every icon and colour in the fixtures has a mapping. Cheaper substitute: skipping icons in the comparison.
- [ ] Compare each webview (the Reviewers editor and the installer) against the mockup by screenshot in `extensions/vscode/test/parity/webview.screens.test.ts`: render the webview HTML with the fixture's state in both themes and compare it with the same region of `design/screens/` within a small pixel tolerance. Done when: moving one button by four pixels fails the comparison. Cheaper substitute: no visual check.
- [ ] Commit: `extension: mockup parity fixtures and harness`

**Test checkpoint:** `cd extensions/vscode && npm test -- --test-name-pattern=parity` passes, and fails when one label in a fixture is edited by hand.

## 12. Extractor limits at tarfile's own parse

> **Started:** 2026-10-20T14:16:00Z

Review round 3 of `§7` (`docs/reviews/02-extension-core/D02-T01-s7.md`, the last round its loop allowed) found that the extractor's pre-pass, a separate walker over the raw tar headers, can disagree with `tarfile`: a PAX `size` override makes `tarfile` skip a block the pre-pass reads as the end of the archive, and Solaris `X` extended headers were not in its metadata set. Either lets a metadata payload far over 1 MB reach `tarfile`'s memory. The limits belong where `tarfile` parses: a `TarInfo` subclass that refuses an oversized extended or long-name header before reading it, and a size-counting file object under `tarfile` for the decompressed total, so both see the same boundaries.

**Phase:** 1
**Needs:** none
**Surface:** no

**Build order:**

1. Write the failing tests: a PAX `size` override hiding a 2 MB comment, and a Solaris `X` header carrying one. Done when: both are accepted by the extractor at the end of `§7`.
2. Move the limits into `tarfile`'s parse in `extensions/vscode/resources/extract_sdk.py` and remove the separate walker. Done when: both tests and every earlier extractor test pass on Windows and in WSL.

- [x] Add the two archives to `extensions/vscode/test/unit/extractSdk.test.ts`, built with Python's `tarfile` (a PAX header setting `size`, a zero-size file header, zeros, then a 2 MB PAX comment; and a `b"X"` header with a 2 MB comment). Done when: each fails on the extractor at the end of `§7`. Cheaper substitute: only the plain `x` header already tested.
- [x] Refuse an extended or long-name header (`x`, `g`, `X`, `L`, `K`) larger than 1 MB in a `TarInfo` subclass passed to `tarfile.open(tarinfo=...)`, checked on the header's own size before its payload is read. Done when: both new tests and the existing metadata test pass. Cheaper substitute: a second walker beside `tarfile`.
  The same subclass refuses more than 8 extended headers in a row (a chain crashed the `§7` extractor with a `RecursionError` traceback) and sparse members, in a `GNUTYPE_SPARSE` header or `GNU.sparse.*` PAX keys (accepted by the `§7` extractor; a git archive never holds one, and the 1.0 sparse map is read from the stream with no bound).
- [x] Count decompressed bytes in a file object `tarfile` reads through, refusing past the stream limit, and remove the separate pre-pass. Done when: the stream limit holds and every extractor test passes. Cheaper substitute: checking the compressed size only.
  The file object checks the position, not bytes read: `tarfile` skips member data with forward seeks that never pass through `read`. Tested with 280 members whose headers each stay under 1 MB.
- [x] Run the extractor tests on Windows and in WSL, and extract the SDK's own `git archive`. Done when: all pass and the SDK's archive still extracts. Cheaper substitute: Windows only.
- [x] Commit: `extension: extractor limits at tarfile's own parse`

**Test checkpoint:** `cd extensions/vscode && npm run compile && node --test out/test/unit/extractSdk.test.js` passes on Windows and in WSL, and the PAX `size` override case fails on the extractor at the end of `§7`.

> **Verified:** 2026-10-20 | §12 | 98f985791f16c0564207e92c840631c1ba30e29c
> **Review:** `docs/reviews/d02-t01-s12.json`

## 13. Candidate folder links on Windows and shared fallbacks

> **Started:** 2026-10-20T14:10:00Z

Review round 3 of `§5` (`docs/reviews/02-extension-core/D02-T01-s5.md`, the last round its loop allowed) found two leftovers in `extensions/vscode/src/host/candidate.ts`. `ownPrivateFolder` returns true on Windows without looking, so a junction or directory symlink at `%TEMP%\conclave` is swept through. And a host caches its fallback folder for its whole life, so when another window's activation sweep removes that folder after a day of idleness, every later check in the first window fails with `ENOENT` until it restarts.

**Phase:** 1
**Needs:** none
**Surface:** no

**Build order:**

1. Write the failing tests: a Windows junction in place of the shared folder is not swept, and a fallback removed by another sweep is recreated on the next check. Done when: both fail on the code at the end of `§5`.
2. Fix both in `extensions/vscode/src/host/candidate.ts`. Done when: both tests and every earlier candidate test pass on Windows and in WSL.

- [x] Add a test to `extensions/vscode/test/unit/candidate.test.ts` that makes the shared folder a junction (Windows) or symlink (POSIX) to a folder holding an old candidate and asserts `sweepCandidates` leaves it. Done when: it fails on Windows at the end of `§5`. Cheaper substitute: the POSIX-only symlink test.
- [x] Check the folder with `lstat` on Windows too in `ownPrivateFolder`: a real directory, not a symbolic link or junction (Node reports a junction as a symbolic link); ownership and mode stay POSIX-only. Done when: the junction test passes. Cheaper substitute: trusting the per-account temporary folder.
- [x] Recreate the fallback in `folder()` when the cached one is gone or no longer this account's private folder. Done when: a test that removes the fallback between two `withCandidate` calls sees the second succeed. Cheaper substitute: restarting the window.
- [x] Run the candidate tests on Windows and in WSL. Done when: all pass on both. Cheaper substitute: Windows only.
  WSL has Node 18.19.1, below the extension's engine (`^22.13.0 || >=24`), where `mock.timers` does not exist: the filesystem tests (links, fallbacks, sweeps, writes) pass there, the five debounce tests run on Windows.
- [x] Commit: `extension: candidate folders refuse junctions and recover a swept fallback`

**Test checkpoint:** `cd extensions/vscode && npm run compile && node --test out/test/unit/candidate.test.js` passes on Windows and in WSL, and fails on Windows when `ownPrivateFolder` returns true without `lstat`.

> **Verified:** 2026-10-20 | §13 | c79c94d16f9f4f8d7789019bc17b709f87b7f996
> **Review:** `docs/reviews/d02-t01-s13.json`

## 14. Extractor checks each member as tarfile reads it

> **Started:** 2026-10-20T14:24:00Z

Review round 3 of `§12` (`docs/reviews/02-extension-core/D02-T01-s12.md`, the last round its loop allowed) found a fourth way a small archive makes `tarfile` allocate without bound: one global PAX `path` with a trailing slash gives every member a fresh copy of a 1 MB name, and `check()` runs only after all members are read. The extractor has been patched across six review rounds (`§7` and `§12`), each finding a `tarfile` feature git never uses, reached before any per-member check. So this section changes the shape rather than adding a seventh patch: each member is checked the moment `tarfile` yields it, and the PAX headers allowed are git's own subset.

**Phase:** 1
**Needs:** none
**Surface:** no

**Build order:**

1. Write the failing test: the reviewer's global `path` archive is refused at the second member. Done when: it is accepted (or refused only after every member is read) by the extractor at the end of `§12`.
2. Check members incrementally and allow only git's PAX keys in `extensions/vscode/resources/extract_sdk.py`. Done when: every extractor test passes on Windows and in WSL, and the SDK's own `git archive` extracts.

- [x] Add the global `path` archive to `extensions/vscode/test/unit/extractSdk.test.ts` (one `g` header with `path` = a 1 MB name ending in `/`, then 100 empty members). Done when: it fails on the extractor at the end of `§12`. Cheaper substitute: only the per-member PAX tests.
  The test's archive has 20,001 members after the global `path`, so the order is proven by the reason: checked as read, the second member is refused as a repeat; at the end of `§12` the member limit refused it first.
- [x] Move the per-member rules of `check()` into `members_of` in `extensions/vscode/resources/extract_sdk.py`, applied to each member as it is read (repeated or case-colliding names, type, absolute names, `..`, Windows names, top folder), with the top-folder count checked at the end. Done when: the global `path` archive is refused at its second member and every earlier test passes. Cheaper substitute: checking after all members are read.
- [x] Allow only the PAX keys git writes (`path`, `linkpath`, `comment`) in `Bounded._apply_pax_info`, and refuse a `path` or `linkpath` value over 4096 bytes before delegating. Done when: a test with another key (`mtime` set to a huge value, or an unknown key) and one with a 5000-byte `path` are refused. Cheaper substitute: the 16-key count alone.
  At the end of `§12`, the `mtime` case crashed with an `OverflowError` traceback (exit 1, no JSON) and the 5000-character path reached extraction. Refusals now quote a name in at most 120 characters (`shown()`), since one quoted a 1 MB name; every refusal test asserts a reply under 600 characters.
- [x] Measure peak allocation with `tracemalloc` on the global `path` archive and record it in the findings file. Done when: the peak is recorded before and after. Cheaper substitute: asserting refusal only.
- [x] Run the extractor tests on Windows and in WSL, and extract the SDK's own `git archive`. Done when: all pass and the SDK's archive still extracts. Cheaper substitute: Windows only.
- [x] Commit: `extension: the extractor checks each member as tarfile reads it`

**Test checkpoint:** `cd extensions/vscode && npm run compile && node --test out/test/unit/extractSdk.test.js` passes on Windows and in WSL, and the global `path` case fails on the extractor at the end of `§12`.

> **Verified:** 2026-10-20 | §14 | 89784c74645df36e807cce6d862d8aae93551faa
> **Review:** `docs/reviews/d02-t01-s14.json`

## 15. Extractor folder tracking linear in path length

> **Started:** 2026-10-20T14:40:00Z

Review round 3 of `§14` (`docs/reviews/02-extension-core/D02-T01-s14.md`, the last round its loop allowed) found that the file-versus-folder check `§14` added keeps every ancestor of every name as its own string, so memory grows with the square of a path's depth: 16 names of about 2000 one-letter folders each, a 92,160-byte archive, peaked at 67 MB, and distinct deep prefixes reach gigabytes within every other limit. Folders are tracked instead as a trie of components with integer node ids, each name walked once, and a name may have at most 64 components (the deepest path in the local repositories under `R:\GitHub` has 14).

**Phase:** 1
**Needs:** none
**Surface:** no

**Build order:**

1. Write the failing test: the reviewer's deep-path archive is refused or stays under a measured allocation, and the conflict cases keep passing. Done when: the depth case fails on the extractor at the end of `§14`.
2. Replace the ancestor set with a component trie and cap the depth in `extensions/vscode/resources/extract_sdk.py`. Done when: every extractor test passes on Windows and in WSL and the SDK's own `git archive` extracts.

- [x] Add a name of more than 64 components to the refusal cases in `extensions/vscode/test/unit/extractSdk.test.ts`. Done when: it fails on the extractor at the end of `§14`. Cheaper substitute: the shallow conflict cases only.
- [x] Refuse a name of more than 64 components in `check_member`. Done when: the depth test passes. Cheaper substitute: a cap on name length alone.
- [x] Track files and folders in a trie keyed by `(parent node id, case-folded component)` in `Seen`, walking each name once: a component that is a file node cannot have children, and a file cannot land on a node that has children. Done when: the three conflict cases (both orders, and differing in case) still pass. Cheaper substitute: the ancestor string set.
  **Corrected 2026-10-20:** the trie was built and measured, and it was linear but heavy (about 150 bytes a node: 204.6 MB on 20,000 distinct 64-component names), so it was replaced before commit by something smaller. `Seen` keeps only the case-folded names and the set of file names; once every member is read and before anything is written, `Seen.clashes` looks each name's ancestors up among the files one prefix at a time, keeping none, which refuses both orders and case variants with one message.
- [x] Measure peak allocation with `tracemalloc` on the reviewer's 16-name archive and on 20,000 distinct 64-component names, and record both in the findings file. Done when: both peaks are recorded and bounded. Cheaper substitute: asserting refusal only.
  Validation peaks (`members_of`): the reviewer's 16 deep names, 64.3 MB at `89784c7` and 0.4 MB now (refused by depth); 20,000 distinct 64-component names, 180.4 MB at `89784c7`, 204.6 MB with the trie, 18.1 MB now (the same as with the clash pass switched off).
- [x] Run the extractor tests on Windows and in WSL, and extract the SDK's own `git archive`. Done when: all pass and the SDK's archive still extracts. Cheaper substitute: Windows only.
- [x] Commit: `extension: extractor folder tracking linear in path length`

**Test checkpoint:** `cd extensions/vscode && npm run compile && node --test out/test/unit/extractSdk.test.js` passes on Windows and in WSL, and the 65-component case fails on the extractor at the end of `§14`.

> **Verified:** 2026-10-20 | §15 | 3ef13cf8056203230a821bd22e10fb8d5b80513a
> **Review:** `docs/reviews/d02-t01-s15.json`

## 16. Process tree kill that ends everything or says so

> **Started:** 2026-10-20T15:30:00Z

Review round 3 of `§8` (`docs/reviews/02-extension-core/D02-T01-s8.md`, the last round its loop allowed) found three gaps in `killTree` in `extensions/vscode/src/host/run.ts`. On Windows the tree is read once before `taskkill`, so a process started between the snapshot and the kill is never waited for. The five-second wait ends silently, so processes still running are reported as a clean cancel and the caller deletes its temporary pin and starts another test. And the helpers (`ps`, the CIM query, `taskkill`) run with no timeout, so a stalled one means the kill is never attempted. The kill becomes a loop: snapshot, kill what is found, and look again, until a snapshot finds nothing running under the root (Windows keeps a dead parent's id on its children, so the walk still reaches them). Every helper gets a timeout, and processes still running at the deadline are an explicit result that the run and its callers report.

**Phase:** 1
**Needs:** none
**Surface:** no

**Build order:**

1. Write the failing tests: a descendant started after the first snapshot is killed and waited for; a stalled helper still ends in a kill; a tree that outlives the deadline gives a result saying so. Done when: each fails on `run.ts` at the end of `§8`.
2. Rewrite `killTree` as the loop with bounded helpers and an explicit result, and carry that result through `run` and `ReviewerTester`. Done when: the tests pass on Windows and in WSL.

- [x] Run every helper in `killTree` (`ps`, the CIM query, `taskkill`) through a timeout of a few seconds in `extensions/vscode/src/host/run.ts`, and kill the process tree when a helper stalls. Done when: a test with a helper that never answers still reaches the kill. Cheaper substitute: no helper timeout.
- [x] Loop in `killTree`: snapshot the tree under the root, kill every process found (`taskkill /F /PID` each on Windows; `SIGSTOP` then `SIGKILL` on POSIX), and snapshot again until none is running, within one deadline. Done when: a test that starts a descendant after the first snapshot sees it ended when the run settles. Cheaper substitute: one snapshot.
  The loop is `endTree(root, ops)`, with the process table, the kill, the running check and the clock as `TreeOps`, so its unit tests drive a made-up table: a descendant that appears only as its parent is killed is found by the next look. `killTree` binds it to CIM or `ps` and `taskkill /F` or `SIGSTOP` then `SIGKILL`.
- [x] Return the processes still running at the deadline from `killTree`, and make `run` settle a cancel or timeout with them in its result (for example `error: "cancelled, but 2 processes did not end"`). Done when: a test with a kill that cannot end a process gets that result, not a plain cancel. Cheaper substitute: settling as a plain cancel.
- [x] Make `ReviewerTester` keep the one-test guard and the temporary pin until the tree has ended, and report the processes that did not end in its outcome. Done when: an integration test with an unkillable fake sees the outcome say so and a second test refused until it ends. Cheaper substitute: releasing the guard at once.
  The outcome is `cancelled` with a `note` naming the processes; the guard and the temporary pin are held until they end (checked every 500 ms, at most as long as a run may last). The same `note` is carried by a cancelled forge run (`§9`'s `forgeOutcome`).
- [x] Run the run and testReviewer tests on Windows and in WSL. Done when: all pass on both. Cheaper substitute: Windows only.
  The fake-CLI integration test runs on Windows; the run tests, including the real process trees, pass in WSL too.
- [x] Commit: `extension: a process tree kill that ends everything or says so`

**Test checkpoint:** `cd extensions/vscode && npm run compile && node --test out/test/unit/run.test.js` passes on Windows and in WSL, and the late-descendant case fails with a single snapshot.

> **Verified:** 2026-10-20 | §16 | 966c418592796cd3af59bfae05456ba517d1c9c9
> **Review:** `docs/reviews/d02-t01-s16.json`

## 17. Tree kill: cut-short discovery and combined uncertainty

> **Started:** 2026-10-20T16:15:00Z

Review round 3 of `§16` (`docs/reviews/02-extension-core/D02-T01-s16.md`, the last round its loop allowed) found two gaps in `extensions/vscode/src/host/run.ts` and `extensions/vscode/src/host/testReviewer.ts`. On POSIX, discovery that the deadline cuts short while it is still finding new processes is not counted as blind, so killing those parents can reparent a child born after the last look while the end is reported confirmed. And a kill that leaves known survivors and also could not be confirmed loses the second fact: `run` reports only the survivors, and `ReviewerTester` releases the test guard once they end, though an unseen process may still run.

**Phase:** 1
**Needs:** none
**Surface:** no

**Build order:**

1. Write the failing tests: discovery cut short by the deadline is reported unverified; a kill with known survivors and an unconfirmed end keeps both in `run`'s result and holds the guard after the survivors end. Done when: each fails at the end of `§16`.
2. Fix both in `run.ts` and `testReviewer.ts`. Done when: the tests pass on Windows and in WSL.

- [x] Count POSIX discovery as complete only when a look finds nothing new, so discovery that the deadline or a failed read ends early makes the end unverified, in `endTree` in `extensions/vscode/src/host/run.ts`. Done when: a fake tree whose slow looks keep finding children is reported `verified: false`. Cheaper substitute: blind only on a failed read.
- [x] Keep `unverified: true` in `run`'s result alongside known survivors, with an error naming both. Done when: a killer returning `{ survivors: [7], verified: false }` gives a result with both. Cheaper substitute: survivors only.
- [x] Hold the test guard and the temporary pin in `ReviewerTester` whenever the end is unconfirmed, after any known survivors end. Done when: an integration test with a survivor and an unconfirmed end is still refused after the survivor ends. Cheaper substitute: releasing the guard once the survivors end.
- [x] Run the run and testReviewer tests on Windows and in WSL. Done when: all pass on both. Cheaper substitute: Windows only.
- [x] Commit: `extension: a tree kill cut short is never reported confirmed`

**Test checkpoint:** `cd extensions/vscode && npm run compile && node --test out/test/unit/run.test.js` passes on Windows and in WSL, and the cut-short discovery case fails with blind set only on a failed read.

> **Verified:** 2026-10-20 | §17 | 8038026552bdcb740961e17efff841a819c8d3a8
> **Review:** `docs/reviews/d02-t01-s17.json`

## 18. Kit state SDK watchers released with their last folder

> **Started:** 2026-10-20T16:50:00Z

Review round 3 of `§10` (`docs/reviews/02-extension-core/D02-T01-s10.md`, the last round its loop allowed) found that `KitStateService` in `extensions/vscode/src/host/kitState.ts` makes one watcher per SDK folder (on its `kits/**` and `forge.py`) and never releases it: a folder that leaves the workspace, or switches to another SDK source, leaves the watchers on the old SDK folder until the service is disposed, so switching sources accumulates them. Each SDK folder's watchers are released when the last folder using it leaves or moves to another source.

**Phase:** 1
**Needs:** none
**Surface:** no

**Build order:**

1. Write the failing tests: forgetting the last folder that uses an SDK folder, and switching a folder to another SDK folder, each release the old SDK folder's watchers. Done when: both fail at the end of `§10`.
2. Count the folders using each SDK folder in `kitState.ts` and release its watchers at zero. Done when: both tests pass.

- [x] Expose the number of SDK folders watched (for tests) and add the two tests to `extensions/vscode/test/integration/kitState.test.ts`: after the last folder using a local SDK is forgotten, no SDK folder is watched; after a folder's source changes to another SDK folder, only the new one is. Done when: both fail at the end of `§10`. Cheaper substitute: checking that events stop.
- [x] Release an SDK folder's watchers in `KitStateService` when the last folder using it is forgotten or computed from another source, and keep them while any folder uses it. Done when: both tests pass and the local SDK test from `§10` still does. Cheaper substitute: disposing every SDK watcher on any forget.
- [x] Commit: `extension: SDK watchers released with their last folder`

**Test checkpoint:** `cd extensions/vscode && npm run test:integration -- --grep kitState` passes, and the forgotten-folder case fails when watchers are never released.

> **Verified:** 2026-10-20 | §18 | 0d9a7598bd01ca6b4ae4215bf74e2ee682d2ab52
> **Review:** `docs/reviews/d02-t01-s18.json`

## 19. Folder computations bound to the lifetime they were asked in

Review round 3 of `D05 T01 §3` (`docs/reviews/05-kit-manager/D05-T01-s3.md`, the last round its loop allowed) found two gaps in how `KitHealthService` (`extensions/vscode/src/host/kitHealth.ts`) runs a folder's computation, and `KitStateService` (`extensions/vscode/src/host/kitState.ts`, `§10`) follows the same pattern. A computation checks its folder's lifetime only between attempts, so after a forget it still starts every remaining forge process (each doctor, each dry run). And a queued request captures the lifetime when it starts running, not when it was asked, so a request asked before a forget runs as part of the folder's next lifetime and answers for it. Both services move to one helper that serializes a folder's computations, captures the lifetime and generation when a request is asked, checks the lifetime before every forge process, and reruns a superseded computation, so the two services cannot drift apart again.

**Phase:** 1
**Needs:** none
**Surface:** no

**Build order:**

1. Write the failing tests: a forget while a computation is held stops it before its next forge process; a request asked before a forget answers for the forgotten lifetime even when it runs after a new read. Done when: both fail for both services at the end of `D05 T01 §3`.
2. Write the helper and move both services onto it. Done when: the tests and every earlier kitState and kitHealth test pass.

- [ ] Write `extensions/vscode/src/host/folderWork.ts` with `FolderWork<T>`: per-folder serialization, a lifetime and a generation captured when `read(folder)` is asked, `invalidate(folder)` (rerun), `forget(folder)` (stop), the retry cap, and an `alive()` check the computation calls before each process. Done when: unit-style integration tests of the helper cover asking before and after a forget. Cheaper substitute: patching each service separately.
- [ ] Move `KitStateService` and `KitHealthService` onto `FolderWork`, calling `alive()` before every `runForge`. Done when: a forget while the first dry run (or `check`) is held starts no further forge process. Cheaper substitute: checking only after the computation.
- [ ] Add the two regressions to `extensions/vscode/test/integration/kitState.test.ts` and `extensions/vscode/test/integration/kitHealth.test.ts`. Done when: each fails at the end of `D05 T01 §3`. Cheaper substitute: one service only.
- [ ] Commit: `extension: folder computations bound to the lifetime they were asked in`

**Test checkpoint:** `cd extensions/vscode && npm run test:integration -- --grep "kitState|kitHealth"` passes, and the forget-while-held case fails when the lifetime is checked only between attempts.

## Verification

- `npm ci && npm run build && npm run lint && npm test && npm run test:integration` passes on Windows.
- Every state from §3 is reached by an integration workspace under `extensions/vscode/test/fixtures/workspaces/`, and a save on the shipped workspace keeps every comment (`git diff` on the saved copy shows only the edited lines).
- `python scripts/todo-graph.py validate` and `python scripts/todo-graph.py plan --check` pass.
