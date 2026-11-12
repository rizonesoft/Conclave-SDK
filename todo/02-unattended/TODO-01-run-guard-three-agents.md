---
schema_version: 1
id: run-guard-three-agents
domain: 02-unattended
status: active
title: "TODO-01 -- Run guard for Antigravity and Codex"
---

# TODO-01 -- Run guard for Antigravity and Codex

> **Goal:** A `process-plan` run is held open by the same campaign guard whichever agent drives it: Claude Code, Antigravity and Codex each have a wired hook that blocks the end of turn while the run is open, a stall breaker for a harness whose hook cannot hold it, and a self-test that drives the real wired hook.

> **Current state:** Measured 2026-11-11. `kits/todo/templates/scripts/campaign_guard.py` (937 lines) is the Stop hook for Claude Code only: `stop_hook` (`:838`) reads `session_id` and prints a `block` decision (`:810`), the guard records `"runner": "claude"` (`:204`), and the kit seeds one hook file, `kits/todo/templates/.claude/settings.json`. There is no `.agents/hooks.json`, no `.codex/hooks.json`, no `heartbeat-still` command and no `--self-test`. The Antigravity and Codex copies of `process-plan` leave out the run guard section the Claude copy has (37 lines), and `kits/todo/README.md:33` titles it "The run guard (Claude Code)". RasterFold built all of this at `b33493346141f96b6b304cd3e0c393595382f056` (`~/projects/RasterFold` in WSL): its `scripts/campaign_guard.py` is 2,435 lines.

## Inputs

- `docs/plans/2026-11-11-sdk-audit-and-roadmap.md`: findings 8 and 9, recommendation 5 (RasterFold's campaign guard) and recommendation 7 (the run guard for Antigravity and Codex through their own hook files).
- RasterFold at `b33493346141f96b6b304cd3e0c393595382f056`: `scripts/campaign_guard.py` (`stop_hook` at `:988`, `heartbeat_still` at `:771`, `_self_test` at `:1320`), `scripts/codex-campaign-hook.py` (38 lines), `.agents/hooks.json` and `.codex/hooks.json`.
- `kits/todo/templates/scripts/campaign_guard.py` and `tests/test_campaign_guard.py` (582 lines): the guard every section changes and its tests.
- Not lifted, on purpose: RasterFold's `repair` ledger (`:1090`, CI repair attempts). The kit's guard was ported without Isotone's CI repair ledger (its docstring says so) and that stays true.
- -> XREF: D02 T02 §6 -- the unattended launcher starts Codex and Antigravity runs, which only hold because of the hooks wired here
- -> XREF: D00 T02 §2 -- the Antigravity command-line flags are checked against the installed CLI there
- -> XREF: D06 T01 §4 -- `global/deploy.py` approves the owner's global Codex hooks through the same interface as §3

## Outcome

- A run acquired from an Antigravity or a Codex session is held at the end of turn by its own wired hook, and released on closeout, park, an empty ready list or the stall breaker, as a Claude Code run is.
- `python scripts/campaign_guard.py --self-test` drives each wired hook file against a throwaway workspace and fails when one is miswired.
- `python forge.py doctor <project> todo` reports the hook wiring of each agent the project has.

**Adjacency:** all=not-applicable (developer tooling: a hook script and its wiring files, with no records a user lists, exports, is notified of or reverses)

**Adjacency rationale:** The guard's own audit trail is unchanged: the run file's closeout and park lines and the recorded hook errors. The reverse of an acquired guard is the existing `end` command.

## Implementation Order

| Order | Section | Deliverable | Depends On | Status |
| ----- | ------- | ----------- | ---------- | ------ |
| 1 | §1 | Antigravity payload handled by the Stop hook | -- | [x] |
| 2 | §2 | Antigravity hook file seeded by the todo kit | §1 | [x] |
| 3 | §3 | Codex hook script and hook file | -- | [x] |
| 4 | §4 | Heartbeat stall breaker for a harness with no Stop hook | -- | [x] |
| 5 | §5 | Guard self-test through each wired hook | §2, §3 | [x] |
| 6 | §6 | Run guard steps in the Antigravity and Codex skill copies | §2, §3, §4 | [ ] |
| 7 | §7 | Live Codex run held by its approved Stop hook | §3 | [x] |

## 1. Antigravity payload handled by the Stop hook

> **Started:** 2026-11-11T21:02:26Z

Antigravity sends a different stop payload from Claude Code and expects a different answer. The hook reads both and answers each in its own format. Source: RasterFold `scripts/campaign_guard.py:988` to `:1025`.

**Corrected 2026-11-11 (validation):** RasterFold moved on (its HEAD is now `77b3ef3`); the source stays the pinned `b334933`, whose `stop_hook` is at `:988` as cited. Two choices the section left open, taken here: the workspace is read from `workspacePaths` only when it is a list of strings, else the payload is a recorded error (RasterFold ignored a bad value silently); and a payload with no session is an error only while a run is open in that workspace, so a project with no guard never collects hook errors. The guard file is read before the session is checked for that reason.

**Phase:** 2
**Needs:** none
**Surface:** no

**Build order:**

1. Teach `stop_hook` in `kits/todo/templates/scripts/campaign_guard.py` the Antigravity payload. Done when: an Antigravity payload for the guard's session is answered with `continue`.
2. Cover it in `tests/test_campaign_guard.py`, then `python forge.py self-sync`. Done when: the checkpoint passes.

- [x] Read the session from `conversationId` in `stop_hook` of `campaign_guard.py` when the payload has no `session_id`, and the workspace from `workspacePaths` when `project_dir` is not given (RasterFold `:988`). Done when: a test calls `stop_hook(payload, None)` with only `conversationId` and `workspacePaths` from a working folder that is not the workspace and the hook finds that guard, and a test with both an explicit `project_dir` and a different `workspacePaths` finds the guard under `project_dir`. Cheaper substitute: treating a missing `session_id` as "no guard" must fail this test. **Corrected 2026-11-11 (plan review):** the test helper always passed `project_dir`, so `workspacePaths` was never exercised.
- [x] Answer an Antigravity session with `{"decision": "continue", "reason": "<the same reason text>"}` in `stop_hook` where a Claude Code session gets `block` (RasterFold `:1025`). Done when: tests assert `continue` for an Antigravity payload and `block` for a Claude Code payload on the same guard, and Antigravity payloads find the guard's lifecycle unchanged: an empty answer with no guard, for another session, after this run's closeout, after its `PARKED` line and with no ready row, the block counter read back after each `continue`, and the stall breaker letting the fourth stop through. **Corrected 2026-11-11 (plan review):** always answering `continue` passed.
- [x] Allow the stop in `stop_hook` when an Antigravity payload carries `terminationReason` equal to `USER_CANCELED` or `fullyIdle` equal to `false`, without counting a block. Done when: tests for each find an empty answer and the block counter unchanged.
- [x] Keep failing open in `stop_hook`: a payload that is neither shape, or a `workspacePaths` that is not a list of strings, allows the stop and records the error through the existing hook-error path, in the workspace named by `project_dir` or the payload's `cwd` (with neither, nothing can be recorded and nothing is). A missing session is an error only while a guard is held there. Done when: separate tests for a missing session with a guard held (exit 0, empty answer, one readable hook error), a missing session with no guard (exit 0, empty answer, no hook-error file), a `workspacePaths` that is a string and one holding a number (each a recorded error under the `cwd` workspace), and a payload that is not an object. **Corrected 2026-11-11 (plan review):** one unspecified test, and no workspace to record in when `workspacePaths` was unusable.
- [x] Run `python forge.py self-sync`. Done when: `scripts/campaign_guard.py` equals the kit file.
- [x] Commit: `todo: the Stop hook answers an Antigravity session`

**Test checkpoint:** `python -m unittest discover -s tests -p test_campaign_guard.py` ends `OK`; answering `block` to an Antigravity payload makes the new test fail.

> **Verified:** 2026-11-11 | §1 | 71b4113f270d3ef4924898ca1e0861b63eb4fed8
> **Review:** `docs/reviews/d02-t01-s1.json`

## 2. Antigravity hook file seeded by the todo kit

> **Started:** 2026-11-11T21:30:16Z

The todo kit seeds `.claude/settings.json` with the Stop hook and nothing for Antigravity. It seeds `.agents/hooks.json` the same way, and the doctor reports it. Source: the Antigravity CLI's own `hooks.md` (`~/.gemini/antigravity-cli/builtin/skills/agy-customizations/docs/hooks.md`, CLI 1.5.5) and a live run of that CLI.

**Corrected 2026-11-11 (validation):** RasterFold's `.agents/hooks.json` is not a working source. Checked against `agy` 1.5.5 on this machine: (1) the file's top-level keys are hook names and `Stop` is a flat list of handlers, so RasterFold's Claude Code shape (a top-level `hooks` key and a `matcher`/`hooks` wrapper) loads as one hook named `hooks`, as the CLI's changelog warns; (2) a hook runs with its working folder set to the folder holding `hooks.json` (`.agents/`), so a command that finds the project through `os.getcwd()` looks in `.agents/scripts/`; (3) on Windows the command runs through `cmd /c` with its inner double quotes escaped, so a quoted `python -c` program arrives as a syntax error (seen in the CLI log: `SyntaxError: unterminated string literal`). A probe hook in a scratch workspace, run by `agy -p`, recorded the real Stop payload: `conversationId`, `workspacePaths` (forward slashes), `cwd`, `fullyIdle`, `terminationReason` (`NO_TOOL_CALL`), `continuationActive`, `hookEventName`, and no `CLAUDE_PROJECT_DIR`. The seed below uses a command with no quotes, relative to `.agents/`.

**Phase:** 2
**Needs:** none
**Surface:** no

**Build order:**

1. Add `kits/todo/templates/.agents/hooks.json`. Done when: a fresh `--agent all` install has it.
2. Report it in `doctor_repo` of `forge.py`, and prove it through a live `agy` run. Done when: the checkpoint passes.

- [x] Create `kits/todo/templates/.agents/hooks.json` as `{"campaign-guard": {"Stop": [{"type": "command", "command": "python3 ../scripts/campaign_guard.py stop-hook || python ../scripts/campaign_guard.py stop-hook", "timeout": 60}]}}`. Done when: a test parses the file and finds that one named hook, a flat `Stop` list, no top-level `hooks` key and no double quote in the command. Cheaper substitute: copying the Claude Code shape must fail this test, because Antigravity loads it as a hook named `hooks`. **Corrected 2026-11-11 (validation):** the `python3 -c` and `runpy` command and the Claude Code shape both fail under Antigravity.
- [x] Record in `kits/todo/README.md` the CLI version checked (`agy` 1.5.5), the file format, the working folder, the `cmd /c` quoting and the payload fields, citing the CLI's `hooks.md`. Done when: the README names the version and the three facts. **Corrected 2026-11-11 (validation):** confirmed by the probe run above, so the `third-party` stop does not apply.
- [x] Add `tests/fixtures/agy-stop-payload.json`, the probe's recorded payload with its paths replaced by placeholders, and test `stop_hook` with it in `tests/test_campaign_guard.py`: the fixture's `workspacePaths` pointed at a guarded workspace is answered `continue`. Done when: the test passes and fails when `stop_hook` ignores `workspacePaths`. **Corrected 2026-11-11 (validation):** added; §1's tests used a payload written by hand.
- [x] Generalise `_stop_hook_wiring` in `forge.py` to take the hook file and its shape, and add a `stop-hook:.agents` check to the `todo` branch of `doctor_repo` when the project has an `.agents/` folder: `ok` when an enabled named hook (`enabled` absent or `true`) has a `Stop` list holding a command naming `campaign_guard.py` and `stop-hook`. Done when: tests find `ok` for a fresh install and for a disabled copy beside an enabled one, `setup_required` naming the reason for a matching hook that is only present disabled, `setup_required` with the seed's path for a project whose own `.agents/hooks.json` lacks the hook or uses the Claude Code shape, and no check for a project with no `.agents/` folder.
- [x] Extend `test_the_todo_kit_wires_the_stop_hook_and_never_overwrites_a_projects_settings` in `tests/test_forge.py` to the Antigravity file. Done when: a project's own `.agents/hooks.json` is byte for byte unchanged after the kit runs.
- [x] Prove the seed live: in a scratch `init --kit todo` project run `agy -p` once to mint a conversation, acquire a guard for its `conversationId`, resume it with `agy --conversation <id> -p` and read from the CLI log (`--log-file`) and the guard's state that the hook answered `continue` and the CLI ran another invocation in the same turn (a second Stop hook call, `blocks` at least 2), until the stall breaker let it stop; then end the guard and resume once more, finding the turn ends at its first Stop. Done when: the run file quotes the log lines and the state for both runs. Without `agy` on the machine the item stays open and the section is not stamped. **Corrected 2026-11-11 (plan review):** a hook answer alone did not show the CLI honoured `continue`. **Corrected 2026-11-11 (validation):** added; only a live run shows the CLI runs the file.
- [x] Install the seed in the SDK itself: add `.agents/hooks.json` to the files `self_sync` keeps current (`SELF_PREFIXES` in `forge.py`), run `python forge.py self-sync`, and check the SDK's copy. Done when: the SDK's `.agents/hooks.json` equals the kit's, the self-sync parity test covers it, and `python forge.py doctor . todo` reports `stop-hook:.agents` `ok`. **Corrected 2026-11-11 (plan review):** `self_sync` filtered the file out, so the SDK would never get its own seed.
- [x] Commit: `todo: seed the Antigravity Stop hook`

**Test checkpoint:** `python -m unittest discover -s tests -p test_forge.py` ends `OK`; removing the hook command from the seed makes the doctor test fail.

> **Verified:** 2026-11-11 | §2 | c084295e6daccd6aff9fc36b38dcc22453fe0172
> **Review:** `docs/reviews/d02-t01-s2.json`

## 3. Codex hook script and hook file

> **Started:** 2026-11-11T21:55:50Z

Codex needs the `block` answer and must never be stopped by a broken hook. A small wrapper calls the guard and prints `{}` on any failure. Source: RasterFold `scripts/codex-campaign-hook.py` (38 lines) and `.codex/hooks.json`.

**Corrected 2026-11-11 (validation):** Codex runs a project's `.codex/hooks.json` only once each hook is approved: on this machine (Codex 0.167.0 on Windows, 0.166.0 in WSL) a probe hook in a scratch repository did not run under `codex exec`, `-c bypass_hook_trust=true` is ignored from session flags, and approvals live in the user's `config.toml` as `hooks.state."<key>".trusted_hash`. Codex's own app-server grants that approval: `hooks/list` returns each hook's `key`, `currentHash` and `trustStatus` (`trusted`, `untrusted`, `modified`), and `config/value/write` with `keyPath: hooks.state` and `mergeStrategy: upsert` records `trusted_hash` exactly as the interactive client does. Probed 2026-11-12: after that write the probe hook read `trusted` and `codex exec` ran it, with a payload in Claude Code's shape (`session_id`, `cwd`, `hook_event_name`, `stop_hook_active`) and its working folder at the project root. So the kit approves its own Stop hook through that interface (`scripts/codex-hook-trust.py`, below), the doctor reads trust from `hooks/list` against the current hash, and the live proof is `D02 T01 §7`, which needs no person. A first reshape filed §7 as an operator row; the owner rejected that shape for an unattended run, and `AGENTS.md` now says a person is needed only for what no tool can do.

**Phase:** 2
**Needs:** none
**Surface:** no

**Build order:**

1. Add `kits/todo/templates/scripts/codex-campaign-hook.py` and `kits/todo/templates/.codex/hooks.json`. Done when: a Codex payload for a guarded session is answered with `block`.
2. Test the wrapper and report the wiring in `forge.py doctor`. Done when: the checkpoint passes.

- [x] Create `kits/todo/templates/scripts/codex-campaign-hook.py`: read the payload from stdin up to 2,000,000 characters, remove `conversationId` so the guard answers in the `block` format, call `campaign_guard.stop_hook`, and print its answer or `{}` (RasterFold `:7`, `:16`, `:24`). Done when: subprocess tests pipe payloads to the installed wrapper and find `block` for a guarded session with the block counter read back, and an empty `{}` for no guard, for another session, after this run's closeout, after its `PARKED` line, with no ready row and from the fourth stop the breaker releases. Cheaper substitute: importing the guard by module name must fail when the hook runs from another working folder; it is loaded by file path. **Corrected 2026-11-11 (plan review):** a wrapper that always answered `block` passed.
- [x] Print `{}` and exit 0 from `codex-campaign-hook.py` on every failure: a payload over the limit, bytes that are not JSON, a missing `campaign_guard.py`, an exception in the guard (RasterFold `:33`). Done when: a test for each finds `{}` on stdout and exit 0.
- [x] Create `kits/todo/templates/.codex/hooks.json` with `command` and `commandWindows` that find the git top level, check the hook script exists there, and run it, printing `{}` when either is missing (RasterFold `.codex/hooks.json`). Done when: a test parses the file and finds both keys naming `codex-campaign-hook.py`, and tests run the command for this platform through the shell Codex uses (`sh -c`, or on Windows the `commandWindows` form) in a repository whose path holds a space, from its root and from a subfolder, finding the guarded decision, and `{}` with exit 0 outside any git repository and with the wrapper missing. **Corrected 2026-11-11 (plan review):** finding the file name in both keys proved neither command runs.
- [x] Confirm the hook file's name, keys and event against the Codex CLI installed on this machine and record the CLI version in `kits/todo/README.md`, with the approval Codex requires. Done when: the README names the version checked, the `hooks.state` key format and that `scripts/codex-hook-trust.py` approves the hook. **Corrected 2026-11-11 (validation):** the approval was not mentioned.
- [x] Add `kits/todo/templates/scripts/tests/test_codex_campaign_hook.py` or extend `tests/test_campaign_guard.py` with the wrapper's tests, and add a `stop-hook:.codex` check to `doctor_repo` in `forge.py` through the generalised `_stop_hook_wiring`. Done when: the doctor reports `ok` on a fresh install and the tests run in the quick suite.
- [x] Create `kits/todo/templates/scripts/codex-hook-trust.py`: start `codex app-server` (stdio JSON-RPC, a 30 second limit, the process tree ended on any exit), `initialize`, call `hooks/list` with the project as `cwds`, and for each hook whose `sourcePath` is this project's `.codex/hooks.json`, whose event is `stop` and whose command names `codex-campaign-hook.py`, write `{key: {"trusted_hash": currentHash}}` into `hooks.state` with `config/value/write` (`upsert`) when it is not `trusted`; `--check` lists without writing. It never approves any other hook. Done when: tests with a stub app-server (a script answering the recorded responses) find exactly the campaign hook written, another project hook and a user hook left alone, a `trusted` hook not rewritten, `--check` writing nothing, and exit 2 with one line when `codex` is missing or the server does not answer in time. Cheaper substitute: computing the hash itself must fail review; Codex computes it. **Corrected 2026-11-12 (validation):** added; Codex's own interface grants the approval.
- [x] Add a `stop-hook-approved:.codex` check to `doctor_repo` in `forge.py` through `codex-hook-trust.py --check`: `ok` when the campaign Stop hook reads `trusted` against its current hash, `setup_required` naming `python scripts/codex-hook-trust.py` when it is `untrusted` or `modified`, and when `codex` is not installed. Done when: tests with the stub find `ok`, `setup_required` for `untrusted`, for `modified` (a changed hook) and for a campaign handler that follows another Stop handler (key `stop:0:1`), and no check for a project with no `.codex/` folder. Cheaper substitute: reading `config.toml` for a key's presence must fail the `modified` test. **Corrected 2026-11-11 (validation, plan review):** added, then read from `hooks/list` so a stale approval and a handler at another index are caught.
- [x] Approve the Codex hook at install in `apply_kit` of `forge.py`: when the todo kit has just installed `.codex/hooks.json`, run `codex-hook-trust.py`'s `trust` and report the outcome as `codex_hook` in the result (`approved`, `trusted`, or `not approved` with the reason), never failing the install. Done when: a test with a stub Codex finds `codex_hook` and the doctor clean after a fresh install, and every test module that installs the todo kit answers from the stub (none records an approval in the user's `config.toml`). **Corrected 2026-11-12 (validation):** added; an install the doctor then reports `setup_required` is not done.
- [x] Install the Codex seed in the SDK itself: add `.codex/hooks.json` to `SELF_PREFIXES` in `forge.py`, run `python forge.py self-sync`, and approve it with `python scripts/codex-hook-trust.py`. Done when: `scripts/codex-campaign-hook.py`, `scripts/codex-hook-trust.py` and `.codex/hooks.json` equal the kit's, the parity test covers them, and `python forge.py doctor . todo` reports `stop-hook:.codex` and `stop-hook-approved:.codex` `ok`. **Corrected 2026-11-11 (plan review):** `self_sync` left out the hook file.
- [x] Commit: `todo: Codex Stop hook that never blocks on its own failure`

**Test checkpoint:** `python -m unittest discover -s tests` ends `OK`; making the wrapper raise on a payload that is not JSON makes its test fail.

> **Verified:** 2026-11-12 | §3 | 94061244db2b1994121bff71be66179b32efe276
> **Review:** `docs/reviews/d02-t01-s3.json`

## 4. Heartbeat stall breaker for a harness with no Stop hook

> **Started:** 2026-11-11T23:42:54Z

When a harness has no Stop hook that can hold a run, the heartbeat is the only thing that sees it. `heartbeat-still` counts heartbeat resumptions that found nothing changed and ends a run that is going nowhere. Source: RasterFold `scripts/campaign_guard.py:771` and `:89`.

**Corrected 2026-11-12 (validation):** checked against RasterFold at `b334933`. Its first call on a new fingerprint sets the baseline and counts nothing, so two calls on an unchanged tree read `hb_still` 1, not 2. It never ends the run itself (its heartbeat prompt's trips-of-2 step does); here the second trip ends the run through `end`'s own `stall` path (`_end_locked`, which already requires `trips` of 2), so a harness with no session heartbeat (the unattended kit's outside one, D02 T02 §7) stops a stuck run too. The kit's Stop hook writes its state with only its own keys, which would drop `hb_fingerprint` and `hb_still`; it keeps them, as RasterFold's does. A refusal exits 1, the guard's code for every `GuardError`.

**Phase:** 2
**Needs:** none
**Surface:** no

**Build order:**

1. Add `heartbeat-still` to `kits/todo/templates/scripts/campaign_guard.py`. Done when: six stills count one stall trip.
2. Cover the counter and its reset. Done when: the checkpoint passes.

- [x] Add `heartbeat_still(root, session)` and the `heartbeat-still --session S` command to `campaign_guard.py`: compare the tree fingerprint the stall breaker already computes with the `fingerprint` the state file holds, the one the Stop hook's breaker keeps, so both observers share one notion of progress, and count `hb_still` up when they match (RasterFold `:771`, which kept a second `hb_fingerprint`). **Corrected 2026-11-12 (plan review):** two fingerprints let one observer's first look read as progress after the other had counted stills. Done when: a test reads `hb_still` 0 after the first call (the baseline) and 2 after two more on an unchanged tree. **Corrected 2026-11-12 (validation):** said two calls read 2. Cheaper substitute: counting every call must fail the reset test below.
- [x] Reset `hb_still`, `blocks` and the shared `trips` to 0 and store the new fingerprint in `heartbeat_still` when the tree changed. Done when: a test commits a file between two calls and reads `hb_still` and `trips` as 0, and a test with one trip, then a commit, then six stills finds the guard held with `trips` 1. **Corrected 2026-11-12 (plan review):** a stale trip could end the run after real progress.
- [x] Count one stall trip in `heartbeat_still` at `MAX_HEARTBEAT_STILLS = 6` stills, and end the run with reason `stall` on the second trip, through the same path the Stop hook's breaker uses (RasterFold `:89`). Done when: a test after the baseline finds the guard held through eleven stills (one trip at six, `hb_still` back to 0, then counting to 5) and released at the twelfth with reason `stall` through `end` (the guard file gone, the pending cancellation naming the job). **Corrected 2026-11-12 (plan review):** six and twelve alone let a release at seven pass.
- [x] Share the state between the two observers in `stop_decision` of `campaign_guard.py`: it keeps `hb_still` when it writes, and a tree change either one sees resets `blocks`, `hb_still` and `trips`. Done when: interleaved tests (heartbeat stills, then Stop hook blocks, then stills, on an unchanged tree) read the one `fingerprint`, `blocks`, `hb_still` and `trips` after each call, a trip counted by either observer counts toward the other's release, and a change seen by the Stop hook resets the heartbeat's count. **Corrected 2026-11-12 (validation, plan review):** added, then the sharing defined and tested through release.
- [x] Refuse `heartbeat-still` for a session that does not hold the guard, with exit 1 (a `GuardError`) and the guard untouched. Done when: command-line tests run `python scripts/campaign_guard.py heartbeat-still --root <workspace> --session S` and read the persisted counters after a still, find the release line at the twelfth, and find exit 1 with the state file byte for byte as before for another session and for no guard. **Corrected 2026-11-12 (plan review):** only the function was tested, never the command.
- [x] Run `python forge.py self-sync` and name the command in the guard's docstring. Done when: `scripts/campaign_guard.py` equals the kit file.
- [x] Commit: `todo: heartbeat-still ends a run that changes nothing`

**Test checkpoint:** `python -m unittest discover -s tests -p test_campaign_guard.py` ends `OK`; never resetting `hb_still` makes the reset test fail.

> **Verified:** 2026-11-12 | §4 | 1332025ca229ca7bd740638c50df24f7ca2d8855
> **Review:** `docs/reviews/d02-t01-s4.json`

## 5. Guard self-test through each wired hook

> **Started:** 2026-11-12T00:48:58Z

Unit tests call `stop_hook` directly, so a hook file with a wrong command passes them. `--self-test` runs the command each hook file holds, as the harness would, against a throwaway workspace. Source: RasterFold `scripts/campaign_guard.py:1320`.

**Corrected 2026-11-12 (validation):** §2 and §3 established how each harness runs its hook, and the self-test must run each the same way or it proves nothing: Claude Code runs its command through Git Bash on Windows (`sh` elsewhere) with `CLAUDE_PROJECT_DIR` set to the project; Antigravity runs its command through `cmd /c` on Windows (`sh -c` elsewhere) with the working folder at `.agents/` and no `CLAUDE_PROJECT_DIR`; Codex runs `commandWindows` on Windows (`command` elsewhere) from the project root. RasterFold's self-test (1,000 lines) also re-tests the guard's logic, which the unit tests own here; this one tests only the wiring. It runs each command directly, so it needs neither agent installed, and Codex's approval is the doctor's check (§3), not this one's.

**Phase:** 2
**Needs:** none
**Surface:** no

**Build order:**

1. Add `--self-test` to `kits/todo/templates/scripts/campaign_guard.py`. Done when: it passes on a fresh install and fails on a broken hook file.
2. Run it from the suite. Done when: the checkpoint passes.

- [x] Add `_self_test()` and `--self-test` to `campaign_guard.py`: build a throwaway git workspace under the system temporary folder holding copies of this project's guard script, Codex wrapper and hook files, a stub `scripts/todo-graph.py` that answers `query ready` and a run file, acquire a guard in it, and remove the workspace afterwards even on failure (RasterFold `:1320`). Done when: running it leaves no folder behind and exits 0 on a fresh install. Cheaper substitute: calling `stop_hook` in process must fail review, because it does not run the wired command.
- [x] Run, in `_self_test`, the command from each hook file the project has (`.claude/settings.json`, `.agents/hooks.json`, `.codex/hooks.json`) as a subprocess the way its harness runs it (the shell, working folder and environment named above) with the matching payload on stdin, with a 60 second limit and the whole process tree ended on timeout. A hook file the project does not have is reported as `absent` and not counted as a failure; a file that is there must hold an enabled campaign Stop command (found as the doctor finds it: Claude Code's shape for `.claude` and `.codex`, a named hook's flat `Stop` list for `.agents`, skipping a hook with `enabled` false), and one that does not parse, or holds none, or only a disabled one, fails naming the file and which of those it is. **Corrected 2026-11-12 (plan review):** selection among a project's own hooks was unspecified. Done when: a test with a seeded install sees three hooks run and each answer its own format (`block`, `continue`, `block`).
- [x] Fail `_self_test` naming the hook file when its command exits non-zero, times out, or answers anything but a JSON object holding that agent's decision (`block`, `continue`, `block`) and a non-empty `reason`: `{}` (the Codex wrapper's fail-open answer), malformed JSON and the wrong decision all fail. Done when: tests that break each seed in turn (a wrong script name) find exit 1 and that file's path in the output; tests with a command printing `{}`, text that is not JSON and the other agent's decision each fail; tests with a disabled-only hook, a file with no campaign command and a file that does not parse each fail with their reason, and a disabled hook beside an enabled one passes; a test with a command that starts a child and sleeps past a shortened limit finds exit 1, the file named, both processes gone and the workspace removed; and a test finds the workspace removed after an ordinary failure. **Corrected 2026-11-12 (plan review):** `{}` with exit 0 passed, and the timeout and cleanup were untested.
- [x] Run `--self-test` from `tests/test_campaign_guard.py` against the SDK's own checkout and from `tests/test_three_pass_install.py`'s fresh install. Done when: both tests pass and the first fails when `.claude/settings.json` in a scratch copy names a missing script.
- [x] Run `python forge.py self-sync`. Done when: `scripts/campaign_guard.py` equals the kit file.
- [x] Commit: `todo: campaign guard self-test drives each wired hook`

**Test checkpoint:** `python scripts/campaign_guard.py --self-test` exits 0; renaming `stop-hook` in a scratch copy of `.agents/hooks.json` makes it exit 1 naming that file.

> **Verified:** 2026-11-12 | §5 | e747490a091796a97e401e82a6884d9de4c1678d
> **Review:** `docs/reviews/d02-t01-s5.json`

## 6. Run guard steps in the Antigravity and Codex skill copies

> **Started:** 2026-11-12T01:53:18Z

The Claude copy of `process-plan` tells the session how to start and end the run guard. The other two copies leave it out, so an Antigravity or Codex run starts with no guard. Each copy gets the steps for its own harness.

**Corrected 2026-11-12 (validation):** checked against the installed CLIs. Antigravity (agy 1.5.6) gives its agent a `schedule` tool for timers and recurring cron jobs in the conversation (its changelog and built-in `automation` skill), so its copy names that as the heartbeat; Codex (0.167.0) has no scheduled resume inside a session (`codex queue` and `codex exec resume` act from outside), so its copy says the run is held by the hook alone and resumed by the unattended kit. Each agent's shell names its own session: `ANTIGRAVITY_CONVERSATION_ID` equals the `conversationId` Antigravity's hook receives, and `CODEX_THREAD_ID` (equal to `CODEX_SESSION_ID`) the `session_id` Codex's hook receives, both read live 2026-11-12. A Codex agent started from a Claude Code session also inherits `CLAUDE_CODE_SESSION_ID`, so each copy names its own variable and warns against the other.

**Phase:** 2
**Needs:** none
**Surface:** no

**Build order:**

1. Add the run guard section to `kits/todo/templates/.agents/skills/process-plan/SKILL.md` and `kits/todo/templates/.codex/skills/process-plan/SKILL.md`. Done when: each names its own hook file and heartbeat.
2. Update `kits/todo/README.md` and `self-sync`. Done when: the checkpoint passes.

- [ ] Write the run guard section in the Antigravity copy of `process-plan`: the hook wired in `.agents/hooks.json`, `acquire` with `ANTIGRAVITY_CONVERSATION_ID` as the session, the heartbeat as a recurring timer made with Antigravity's `schedule` tool, and `heartbeat-still` on each heartbeat resumption. Done when: the section names no Claude Code tool (`CronCreate`, `CronList`) and no other agent's session variable, and a test finds every `campaign_guard.py` command it names in the guard's command list. **Corrected 2026-11-12 (validation):** the heartbeat and the session variable are named from the live check.
- [ ] Write the run guard section in the Codex copy of `process-plan` in the same way, naming `.codex/hooks.json`, `scripts/codex-campaign-hook.py`, `scripts/codex-hook-trust.py` and `CODEX_THREAD_ID`, with the warning against an inherited `CLAUDE_CODE_SESSION_ID`. Done when: the section names no Claude Code tool and every command in it exists in the guard's command list, by the same test. **Corrected 2026-11-12 (validation):** the trust step and the session variable added.
- [ ] State in both copies what happens when the harness offers no scheduled resume: the run is held by the hook alone, and the unattended kit's heartbeat (when installed) restarts and nudges it from outside. Done when: both copies carry that sentence and name `scripts/unattended-run.py`.
- [ ] State in both copies and in `kits/todo/README.md` that the stall breaker lets a turn end and keeps the guard held, and that only `end` (or the second trip through `heartbeat-still`) releases the run. Done when: the three texts carry that distinction and none says the breaker releases the run. Filed 2026-11-12 from `D02 T01 §7`'s completion review, whose Test checkpoint wording conflated the two.
- [ ] Retitle "The run guard (Claude Code)" in `kits/todo/README.md` (`:31`) to cover the three agents, with one line per agent naming its hook file. Done when: the README names all three hook files.
- [ ] Extend `test_micro_todo_and_complete_plan_rules_present_across_all_agents` or add a test in `tests/test_forge.py` asserting that each agent's `process-plan` copy names its own hook file. Done when: removing the section from the Codex copy makes it fail.
- [ ] Run `python forge.py self-sync`. Done when: the SDK's three `process-plan` copies equal the kit's.
- [ ] Commit: `todo: process-plan starts the run guard in every agent`

**Test checkpoint:** `python -m unittest discover -s tests -p test_forge.py` ends `OK`; deleting the run guard section from the Antigravity copy makes the new test fail.

## 7. Live Codex run held by its approved Stop hook

> **Started:** 2026-11-12T00:36:03Z

Filed 2026-11-11 from `D02 T01 §3`. With the Stop hook approved through `scripts/codex-hook-trust.py`, a live run proves the wrapper and the hook file hold a Codex run, as §2 proved it for Antigravity. **Corrected 2026-11-12:** first filed in Phase 99 waiting on the operator to approve the hook; Codex's own app-server grants the approval, so it needs no person and runs in Phase 2.

**Corrected 2026-11-12 (validation):** `forge.py init --kit todo` now approves the hook itself (§3), so the first item's `codex-hook-trust.py` run is expected to print `trusted`; the item stands as the check that it did. `codex exec` (0.167.0) has `--json`, `--skip-git-repo-check`, `-C` and the `resume` subcommand the items name, read from its help today.

**Phase:** 2
**Needs:** none
**Surface:** no

**Build order:**

1. Approve a scratch project's Stop hook through the tool. Done when: `python forge.py doctor <scratch> todo` reports `stop-hook-approved:.codex` `ok`.
2. Run the live proof. Done when: the checkpoint passes.

- [x] Create a scratch `init --kit todo` git project with a stub graph holding one ready row and a run file (`docs/phase-runs/2099-01-01-phase-0.md`, which `stop_decision` needs: a missing run file lets the stop through), and run `python scripts/codex-hook-trust.py` in it. Done when: the doctor reports `stop-hook-approved:.codex` `ok` for it. **Corrected 2026-11-12 (plan review):** the run file was not named.
- [x] Mint a session with `codex exec --json`, acquire a guard for its session id (`acquire --root <scratch> --session <id> --phase 0 --run-file docs/phase-runs/2099-01-01-phase-0.md --cron-id none --scope plan`, reading the guard back for that session and its run id), resume it with `codex exec resume <id>`, and read from the output and the guard's state that the hook answered `block` and Codex ran further turns until the stall breaker let it stop (`trips` 1, the guard still held: the breaker lets a turn end, it does not release the run). Every `codex` call runs under a 10 minute deadline with its whole process tree ended on a timeout, and a timeout fails the proof. Done when: the run file quotes the output and the state. **Corrected 2026-11-12 (plan review):** the acquire arguments, the difference between a stop let through and a released guard, and a deadline were missing.
- [x] End the guard with `end --reason operator-stop` (the end path that needs no marker; `stall` needs two trips), read back that the guard and state files are gone, and resume once more under the same deadline. Done when: the run file quotes a turn that ends at its first Stop. **Corrected 2026-11-12 (plan review):** the end path was not named.
- [x] Commit: `todo: a live Codex run held by its Stop hook`

**Test checkpoint:** `python forge.py doctor <scratch> todo --strict` exits 0 with `stop-hook-approved:.codex` `ok`; the run file quotes a guarded Codex run that the breaker released and a released run that stopped at its first Stop.

> **Verified:** 2026-11-12 | §7 | 67af0aad0391a245ab940079fcf3e13efbb5c33c
> **Review:** `docs/reviews/d02-t01-s7.json`

## Verification

- A fresh `python forge.py init <scratch> --kit todo` passes `python scripts/campaign_guard.py --self-test` with three hooks run, on Windows and in WSL.
- `python forge.py doctor <scratch> todo --strict` exits 0 and lists `stop-hook`, `stop-hook:.agents` and `stop-hook:.codex`.
- `python -m unittest discover -s tests` passes.
- `python scripts/todo-graph.py validate` and `python scripts/todo-graph.py plan --check` pass.
