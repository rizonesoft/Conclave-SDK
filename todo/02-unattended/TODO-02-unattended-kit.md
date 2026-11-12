---
schema_version: 1
id: unattended-kit
domain: 02-unattended
status: active
title: "TODO-02 -- Unattended kit"
---

# TODO-02 -- Unattended kit

> **Goal:** A project installs one kit and can start a `process-plan` run that keeps going with nobody at the keyboard: a preflight that refuses a run that cannot work, a launcher that starts the agent in a session that survives the terminal, a heartbeat that nudges an idle run and records a dead one as ended, and a desktop shortcut that starts it; nothing restarts or resumes a run without its operator (owner decision 2026-11-12).

> **Current state:** Measured 2026-11-11. No `kits/unattended/` exists; `forge.py` knows six kits (`KIT_ORDER`, `forge.py:139`). The todo kit's guard holds a run only from inside the session: its docstring says there is no keep-alive outside it (`kits/todo/templates/scripts/campaign_guard.py:19`). The two projects built the outside half separately. RasterFold (`~/projects/RasterFold` in WSL, `b33493346141f96b6b304cd3e0c393595382f056`) has `scripts/unattended-run.sh` (71 lines: lock, preflight, `exec claude`), `scripts/unattended-preflight.py` (509 lines), `docs/unattended-run.md` (60 lines) and a desktop shortcut that is not versioned; nothing restarts its run. Impossible OS (`~/projects/impossible-os` in WSL, `17a762d39ccd1958cbe711901f645fd9b042e939`) has `scripts/run.sh` (157 lines), `scripts/overnight/run-common.sh` (62), `heartbeat.sh` (105), `supervisor.py` (225), `ship_count.py` (66) and `scripts/run-desktop.sh` (80): a tmux session, a heartbeat that restarts and nudges it, and a systemd user unit that resumes it at boot. Both run in WSL and both start Claude Code only. **Corrected 2026-11-11:** the SDK itself now has a Windows launcher of its own, `scripts/start-run.ps1` with a desktop shortcut (Claude Code on the `opus` alias, permission prompts off, a `/goal`, the stored long-lived token), written on the owner's request the same day and modelled on Bosun's `scripts/start-run.ps1`. It is not part of a kit, restarts nothing and is Windows-native, so it does not replace any section below; §5 and §10 may take its goal and token handling as a further source.

## Inputs

- `docs/plans/2026-11-11-sdk-audit-and-roadmap.md`: finding 8, recommendation 5 (RasterFold's unattended runner, then Impossible OS's overnight supervisor) and the `unattended` rows of the kits table.
- RasterFold at `b33493346141f96b6b304cd3e0c393595382f056`: `scripts/unattended-run.sh`, `scripts/unattended-preflight.py` (checks at `:413` to `:495`, `run` at `:75`, `kill_group` at `:135`, `write_claim` at `:288`), `docs/unattended-run.md`.
- Impossible OS at `17a762d39ccd1958cbe711901f645fd9b042e939`: `scripts/run.sh`, `scripts/overnight/run-common.sh` (`run_launch` at `:42`), `scripts/overnight/heartbeat.sh`, `scripts/overnight/supervisor.py` (`REPAIR_AFTER_HOURS` at `:31`), `scripts/overnight/ship_count.py`, `scripts/run-desktop.sh`.
- Not lifted, on purpose: Impossible OS's machinery revert (`supervisor.py:108`, which reverts commits and depends on that project's frozen-file list), its webhook alert (`notify.sh:35`), its skill-deny check and its phase guard; RasterFold's `--repair` compile database rebuild, its scout roster check and its seed prompt. Each is specific to its project.
- -> XREF: D02 T01 §5 -- the preflight runs the guard's self-test, and a Codex or Antigravity run is held by the hooks wired there

## Outcome

- `python forge.py kit <project> unattended` installs the kit, and `python forge.py doctor <project> unattended` says what the machine still needs.
- `python3 scripts/unattended-run.py start` runs the preflight and starts the agent in a tmux session; `status`, `attach` and `stop` act on that run; an idle run is nudged, and a run that dies is recorded as ended, its processes stopped, never restarted.
- Nothing resumes a run without its operator: no boot unit, scheduled task, watchdog or heartbeat restart, which tests prove; a desktop shortcut starts a run with one double-click.
- Limit, stated: the run lives in tmux, so it runs on Linux and in WSL. On Windows the shortcut starts it through `wsl.exe`, as RasterFold's does. There is no Windows-native launcher.

**Adjacency:** list=not-applicable (one run per project, found by its session name); document=not-applicable (nothing a user carries or files); settings=applicable @ D02 T02 §2; reporting=applicable @ D02 T02 §8; notifications=applicable @ D02 T02 §8; permissions=applicable @ D02 T02 §3; audit=applicable @ D02 T02 §4; exchange=not-applicable (no import or export); reverse=applicable @ D02 T02 §5

**Adjacency rationale:** Every tunable is a key of the run profile with a named consumer and a refusal test (§2). The health file and the stall marker are the run's reporting and its notice to the operator (§8). The preflight is the refusal side: it says why a run may not start (§3). The launch claim records who started which run and when (§4). The reverse of `start` is `stop`, which ends the whole process tree and the guard (§5).

## Implementation Order

| Order | Section | Deliverable | Depends On | Status |
| ----- | ------- | ----------- | ---------- | ------ |
| 1 | §1 | Unattended kit known to `forge.py` | -- | [x] |
| 2 | §2 | Run profile `.conclave/unattended.json` and its loader | §1 | [x] |
| 3 | §3 | Preflight with a PASS or FAIL line per precondition | §2 | [x] |
| 4 | §4 | Launch lock and claim | §2 | [x] |
| 5 | §5 | Launcher for a Claude Code run under tmux | §3, §4 | [x] |
| 6 | §6 | Launch commands for Codex and Antigravity | §5, T01 §2, T01 §3 | [x] |
| 7 | §7 | Heartbeat that nudges an idle run and records a dead one as ended | §5 | [x] |
| 8 | §8 | Ship counter, ship limit and stall marker | §7 | [ ] |
| 9 | §9 | Nothing resumes a run without its operator | §7 | [ ] |
| 10 | §10 | Desktop shortcut that starts the run | §5 | [ ] |
| 11 | §11 | Operator document and `unattended-run` skill | §8, §9, §10 | [ ] |

## 1. Unattended kit known to `forge.py`

> **Started:** 2026-11-12T04:37:56Z

The kit folder, its place in the install order, its detection and its doctor branch, so the later sections have somewhere to put files and a way to prove an install.

**Corrected 2026-11-12 (validation):** `forge.py` grew through D01 T01 and D02 T01, so the line numbers below no longer hold; the items name `KIT_ORDER`, the usage docstring and the `--kit` help texts of `init` and `kit` instead. tmux runs only on Linux and in WSL, so on Windows the doctor's `tmux` check reads `setup_required` with the hint to run the kit in WSL, which is the true state there (the Outcome's stated limit).

**Phase:** 2
**Needs:** none
**Surface:** no

**Build order:**

1. Create `kits/unattended/` with `README.md` and an empty `templates/scripts/` holding the shared module. Done when: `python forge.py kits` lists `unattended`.
2. Teach `forge.py` the kit. Done when: the checkpoint passes.

- [x] Create `kits/unattended/README.md` and `kits/unattended/templates/scripts/lib/unattended.py` (a module with a docstring and `SCHEMA_VERSION = 1`, filled by §2). Done when: `python forge.py kits` prints `unattended` in its list, and a test installs the kit and reads `scripts/lib/unattended.py` back with `SCHEMA_VERSION` 1 on import. **Corrected 2026-11-12 (plan review):** listing proved only that the folder exists.
- [x] Add `unattended` to `KIT_ORDER` in `forge.py` after `automations`, and to the kit names in the usage docstring and the `--kit` help texts of `init` and `kit`. Done when: a test asserts `unattended` sits immediately after `automations` in `KIT_ORDER` and that `init --kit unattended --kit todo` writes the todo files first. **Corrected 2026-11-12 (plan review):** an unknown kit is appended after the known ones, so the install order alone could not catch its removal.
- [x] Detect the kit in `installed_kits` of `forge.py` by `scripts/lib/unattended.py`, the file this section installs (`scripts/unattended-run.py` arrives with §5). Done when: a test finds `unattended` in `check_repo(...)["kits"]` after a real `kit <project> unattended` and not before. **Corrected 2026-11-12 (plan review):** the launcher is not installed until §5.
- [x] Add an `unattended` branch to `doctor_repo` in `forge.py`: each kit file present, the todo kit present (`scripts/campaign_guard.py`), and `tmux` on `PATH` (`setup_required` with the install hint when it is not, and on Windows the hint to run the kit in WSL). Done when: tests find `ok` for the files on a fresh install, `missing` naming a kit file removed from it, `setup_required` for a project without the todo kit, `ok` and `setup_required` for `tmux` found and not found on `PATH` (`shutil.which` controlled), and on Windows (`os.name` patched to `nt`) `setup_required` with the WSL hint. **Corrected 2026-11-12 (plan review):** missing files, the tmux cases and the Windows hint were untested.
- [x] List the kit in `README.md`, `kits/README.md` and `AGENTS.md` (Purpose), and state that the SDK does not install it in itself (`SELF_KITS` unchanged). Done when: the three documents name it and their table rows are within 120 characters.
- [x] Commit: `unattended: kit skeleton known to forge.py`

**Test checkpoint:** `python -m unittest discover -s tests -p test_forge.py` ends `OK`; removing `unattended` from `KIT_ORDER` makes the order test fail.

> **Verified:** 2026-11-12 | §1 | 8d42b130b87d19edad556c6101a28ae15a89d722
> **Review:** `docs/reviews/d02-t02-s1.json`

## 2. Run profile `.conclave/unattended.json` and its loader

> **Started:** 2026-11-12T05:49:28Z

Everything the two projects hard-coded (agent, model, effort, prompt, branch, thresholds, session name) becomes one profile the project owns. The loader refuses a profile it cannot run.

**Phase:** 2
**Needs:** none
**Surface:** no

**Build order:**

1. Write `load_profile` in `kits/unattended/templates/scripts/lib/unattended.py` and the template profile. Done when: the template loads.
2. Test every refusal. Done when: the checkpoint passes.

- [x] Create `kits/unattended/templates/.conclave/unattended.json` with `schema_version`, `name`, `agent`, `model`, `effort`, `prompt_file`, `branch`, `skip_permissions`, `tools`, `min_disk_gb`, `min_ram_gb`, `tick_seconds`, `idle_minutes`, `stall_hours` and `preflight`, defaulting to `claude`, `main`, 20, 2, 300, 45 and 6 (RasterFold `unattended-preflight.py` thresholds; Impossible OS `heartbeat.sh:17`, `supervisor.py:31`), with `name`, `model` and `effort` left `null` for the project to set. Done when: `python -m json.tool` reads it.
- [x] Add `load_profile(root)` to `lib/unattended.py`, returning the profile with every key checked: `agent` one of `claude`, `codex`, `agy`; `name` matching `[a-z0-9][a-z0-9-]{1,40}`; `prompt_file` a relative path inside the repository that exists; numbers whole and positive; `preflight` a list of `{"name", "command", "timeout_seconds"}` with `command` a list of strings. Done when: a test for each fault reads a refusal naming `.conclave/unattended.json` and the key. **Corrected 2026-11-12 (plan review):** also `schema_version` exactly 1; `model` and `branch` non-empty strings; `effort` one of the agent's own values (`claude`: low, medium, high, xhigh, max; `codex`: minimal, low, medium, high, xhigh; `agy` has no effort flag the launcher passes, so any non-empty string, recorded); `skip_permissions` a JSON boolean; `tools` non-empty strings; booleans refused in every number; `preflight` with a non-empty `name`, a `command` whose first entry is non-empty and a whole `timeout_seconds` above 0, exactly those keys; `prompt_file` a readable UTF-8 file, not a folder, inside the repository after symlinks resolve; a missing, unreadable or malformed profile, or one whose root is not an object, refused with a message naming the file; and a configured profile read back with every value, then edited and reloaded to show the change. Cheaper substitute: `dict.get` with silent defaults must fail the unknown-key and wrong-type tests.
- [x] Refuse a profile whose `name`, `model` or `effort` is still `null` in `load_profile`, saying which to set. Done when: a test loads the shipped template unchanged and reads that refusal, and loads it with the three set and gets the profile.
- [x] Create `kits/unattended/templates/docs/unattended-prompt.md`: a seed prompt that tells the agent to run `process-plan` to completion, never to ask the operator, and to record every decision in the run file, with no project name in it. Done when: the template profile's `prompt_file` names it, `load_profile` accepts the template with `name`, `model` and `effort` set, and a test finds `process-plan`, the never-ask rule and the run file (`docs/phase-runs/`) as where decisions go, and no project name. **Corrected 2026-11-12 (plan review):** a path that loads proved nothing about the text.
- [x] Add `kits/unattended/templates/scripts/tests/test_unattended.py` with the loader tests, run from `tests/test_forge.py` as the reviewer kit's tests are (`test_reviewer_kit_dispatcher_tests_pass`), but in the quick suite. Done when: `python -m unittest discover -s kits/unattended/templates/scripts/tests` passes and the quick suite runs it.
- [x] Commit: `unattended: run profile and its loader`

**Test checkpoint:** `python -m unittest discover -s kits/unattended/templates/scripts/tests` ends `OK`; accepting an unknown `agent` makes its test fail.

> **Verified:** 2026-11-12 | §2 | ca056763b2555fadfb3a3e96feb3311b49284144
> **Review:** `docs/reviews/d02-t02-s2.json`

## 3. Preflight with a PASS or FAIL line per precondition

> **Started:** 2026-11-12T08:38:39Z

A run that cannot work should not start. The preflight prints one line per precondition and exits 1 on any FAIL. Source: RasterFold `scripts/unattended-preflight.py:413` to `:495`, with its project-specific checks left behind.

**Corrected 2026-11-12 (validation):** the launch claim and `read_claim` are built in §4, after this section, so the claim check moves to §4, which owns the claim; here the run check is the campaign guard alone. The Codex hook file names `codex-campaign-hook.py`, not `campaign_guard.py`, so the hook check reads the agent's file with the guard's own `HOOK_FILES` and `_campaign_command` (one source for the markers and the parsing). The upstream check compares with the last fetch and does not fetch: a preflight that needs the network would refuse an offline run for a reason that has nothing to do with the tree (reversing it is one `git fetch` call). The Windows refusal comes first and alone, since nothing after it can run there.

**Phase:** 2
**Needs:** none
**Surface:** no

**Build order:**

1. Create `kits/unattended/templates/scripts/unattended-preflight.py` with the generic checks. Done when: it prints PASS lines on a ready fixture and exits 0.
2. Add the project's own checks from the profile and the process-tree stop. Done when: the checkpoint passes.

- [x] Create `unattended-preflight.py` with the git checks: on the profile's `branch`, a clean tree, and `HEAD` not behind its upstream when one is set. Done when: tests on fixture repositories find one FAIL line for each broken state and exit 1, and exit 0 with only PASS lines otherwise. Cheaper substitute: one combined "git ok" line must fail the per-state tests.
- [x] Add the run check to `unattended-preflight.py`: no live campaign guard (`build/claude-campaign-guard.json`). Done when: a test with a guard file finds its FAIL line and one without finds PASS, and with `--resume-session <id>` a guard held by that session passes (the run being resumed after a crash) while one held by another session still fails naming it. **Corrected 2026-11-12:** the claim check moved to §4; **(plan review)** a killed agent leaves its guard behind, and §5 and §7 resume through this preflight.
- [x] Add the tool checks to `unattended-preflight.py`: `git`, `python3`, `tmux`, the profile agent's CLI and every name in the profile's `tools` are on `PATH`. Done when: a test with a `tools` entry that does not exist finds its FAIL line naming the tool, and a test for each of `git`, `python3`, `tmux` and each agent's CLI missing finds the FAIL naming it. **Corrected 2026-11-12 (plan review):** one extra tool alone proved nothing about the required ones.
- [x] Add the hook check to `unattended-preflight.py`: the profile agent's Stop hook file holds an enabled campaign Stop command, read with `HOOK_FILES` and `_campaign_command` from the project's `scripts/campaign_guard.py` (`codex-campaign-hook.py` for Codex), and `python3 scripts/campaign_guard.py --self-test --hook-file <the agent's file>` exits 0 (the self-test is built in D02 T01 §5; `--hook-file`, added here in the todo kit, tests that one file, so an unused agent's broken hook does not block the run). For Codex the preflight also runs `scripts/codex-hook-trust.py`, which approves the campaign hook through Codex's app-server when it is not yet trusted, and FAILs when it cannot. Done when: tests find FAIL for a hook file that lacks the hook, a disabled hook, a malformed file and a self-test that exits nonzero; PASS for a seeded install of each agent; PASS for the selected agent while another agent's hook file is broken; and, against the stub app-server, PASS for a trusted and for a modified hook (approved), FAIL for a refused approval and for a server that does not start. **Corrected 2026-11-12 (plan review):** wiring alone does not show Codex runs the hook, and the self-test covered every agent's file.
- [x] Add the headroom checks to `unattended-preflight.py`: free disk on the repository's volume at least `min_disk_gb` and available memory at least `min_ram_gb`, read with `shutil.disk_usage` and `/proc/meminfo`. Done when: tests with measurements injected below, exactly at and above each threshold find FAIL, PASS and PASS with the measured values, and changing the profile's thresholds changes the result. **Corrected 2026-11-12 (plan review):** only the insufficient case was tested.
- [x] Run the profile's `preflight` commands from `unattended-preflight.py`: each with no shell, its own timeout, a new process group and the whole group killed on timeout or interrupt (RasterFold `:75`, `:135`), showing only the last line of its output. Done when: a test with a command that starts a child and sleeps past its timeout finds FAIL reporting exit 124 (the check's status; the preflight itself exits 1) and the child gone. Cheaper substitute: `subprocess.run(timeout=...)` must fail the child-gone assertion. **Corrected 2026-11-12 (plan review):** also each command runs from the repository root with its arguments exactly as listed; a nonzero exit is a FAIL with that exit; a program that cannot start is a FAIL saying why; empty output is reported as such; a child left behind by a command that exited is ended; an interrupt ends the group; and output is kept as a bounded in-memory tail of stdout and stderr together (4 KiB), never written to disk, so a check that writes 50 MB, or one long unterminated line, costs no more than that. Each has a test.
- [x] Report every operational error in `unattended-preflight.py` as a FAIL line, never a traceback: a profile the loader refuses is one FAIL and stops (every check reads it); a missing `git`, a failed git query, a guard script that does not load, unreadable memory or disk figures each FAIL their own check with the reason while the independent checks still run. Done when: tests through `preflight()` find each FAIL line and exit 1 with no traceback. **Added 2026-11-12 (plan review).**
- [x] Refuse to run on Windows without WSL in `unattended-preflight.py` with one line saying the run needs tmux. Done when: a test with `os.name` patched to `nt` finds exit 1 and that line.
- [x] Commit: `unattended: preflight that refuses a run that cannot work`

**Test checkpoint:** `python -m unittest discover -s kits/unattended/templates/scripts/tests` ends `OK`; dropping the clean-tree check makes its test fail.

> **Verified:** 2026-11-12 | §3 | d103f250801f07efa5cdee3f2bc10b0af0daed4c
> **Review:** `docs/reviews/d02-t02-s3.json`

## 4. Launch lock and claim

> **Started:** 2026-11-12T09:57:08Z

Two launches at once would start two agents on one tree. A lock held for the launch and a claim file that names the run stop that, and the claim is the record of who started what. Source: RasterFold `scripts/unattended-run.sh:28` and `scripts/unattended-preflight.py:288`.

**Phase:** 2
**Needs:** none
**Surface:** no

**Build order:**

1. Add `launch_lock`, `write_claim`, `read_claim` and `clear_claim` to `lib/unattended.py`. Done when: a second launch is refused while the first holds the lock.
2. Cover the stale cases. Done when: the checkpoint passes.

- [x] Add `launch_lock(root)` to `lib/unattended.py`: an exclusive `fcntl.flock` on `build/unattended-launch.lock`, not waiting, released when the launcher exits. Done when: a test holding the lock in one process finds a second refused naming the lock file.
- [x] Add `write_claim(root, session, pid, agent, tmux_session)` to `lib/unattended.py`, writing `build/unattended-launch.json` (the agent's session id, the tmux session the launcher starts, `<name>-run` in §5, the pid, the agent, the UTC start) through a temporary file and `os.replace`. Done when: a test reads back what was written. Cheaper substitute: a plain `open(..., "w")` must fail review under the repository's atomic-write rule.
- [x] Add `read_claim(root)` to `lib/unattended.py`, returning the claim, whether it is live and why: live means its tmux session exists, stale means tmux itself says it does not (`can't find session`, `no server running`), and unknown means tmux could not be asked (missing, timed out, a socket it cannot reach), which is never read as stale. A claim that is not JSON or lacks a key reads as stale with the reason. Done when: tests cover no claim, a live claim, a claim whose session is gone, a malformed file and a lookup that fails (unknown), and a real tmux session in WSL. **Corrected 2026-11-12 (plan review):** a failed lookup must not let another launch in.
- [x] Add `clear_claim(root, session)` to `lib/unattended.py`, removing the claim only when it is stale or belongs to `session`, the run being stopped, and never one whose liveness is unknown or that was replaced after it was read. Done when: tests find a live claim of another session untouched and a refusal naming it, an unknown one refused, the owner's own and a stale claim removed (read back from the disk), a claim replaced between the read and the removal left in place, and a second clear of an absent claim a no-op. **Corrected 2026-11-12 (plan review):** the owner is passed explicitly.
- [x] Add the claim check to `unattended-preflight.py`: no other live launch claim, read with `read_claim`. Done when: tests find PASS with no claim, FAIL naming the session for a live claim of another session, PASS with the reason for a stale claim, PASS for the resumed run's own live claim (`--resume-session`), and FAIL for a claim whose liveness is unknown. **Corrected 2026-11-12:** moved here from §3, which runs before the claim exists.
- [x] Commit: `unattended: launch lock and claim`

**Test checkpoint:** `python -m unittest discover -s kits/unattended/templates/scripts/tests` ends `OK`; making `read_claim` call every claim live makes the stale-claim test fail.

> **Verified:** 2026-11-12 | §4 | 70bcee7677c393ac9767ed0122c18796aeea51a7
> **Review:** `docs/reviews/d02-t02-s4.json`

## 5. Launcher for a Claude Code run under tmux

> **Started:** 2026-11-12T11:24:37Z

`scripts/unattended-run.py` is the operator's entry point: `start`, `status`, `attach` and `stop`. `start` takes the lock, runs the preflight and starts Claude Code in a tmux session that outlives the terminal. Sources: RasterFold `scripts/unattended-run.sh:66`; Impossible OS `scripts/run.sh:4` and `scripts/overnight/run-common.sh:42`.

**Corrected 2026-11-12 (validation):** every Claude Code flag named below exists in the installed CLI (`claude --help`, 2.1.322); `--disallowedTools` takes a list (`<tools...>`), so the command ends its options with `--` before the prompt. tmux applies `history-limit` to new windows only, so the session starts with a placeholder window, sets the option, opens the agent's window and closes the placeholder; session-scoped commands target `=<name>-run:`. The agent runs through `exec` in its pane, so the pane's pid leads the process group `stop` kills. The marker and claim are written once the agent's pid is known, still under the launch lock. The heartbeat's session is `<name>-heartbeat` (§7); `stop` kills it when it exists. Codex and Antigravity are refused with a pointer to §6, which adds them.

**Corrected 2026-11-12 (plan review):** the marker `build/unattended-run.json` has a fixed schema (`session`, `tmux_session`, `heartbeat_session`, `agent`, `pgid`, `started`, `resumed`), is written atomically and read back with validation, and `status` and `stop` follow the marker's own session names, so a profile `name` changed during a run cannot strand it. `start` keeps the agent's window on exit (`remain-on-exit`) for a bounded startup check, so an agent that exits at once is reported with its last output and cleaned up; a tmux or persistence failure after the agent started ends the session and its process group and leaves no marker or claim. A resume passes `--resume-session` to the preflight; when it falls back to a fresh session, the crashed session's guard is ended first (`operator-stop`), so the new session acquires its own (decision; reversing it needs a guard handover path). `stop` runs under the launch lock, ends the guard only when the marker's session owns it, and removes the marker and claim only after the process group is gone; a second `stop` is a no-op.

**Phase:** 2
**Needs:** none
**Surface:** no

**Build order:**

1. Create `kits/unattended/templates/scripts/unattended-run.py` with `start` and `status`. Done when: a stub agent runs in a tmux session named from the profile.
2. Add `attach` and `stop`, which ends the whole tree. Done when: the checkpoint passes.

- [x] Add `start` to `unattended-run.py`: take `launch_lock`, run `unattended-preflight.py` and stop with its output on any FAIL, mint a session id, write the run marker `build/unattended-run.json` and the claim, then start the agent in a detached tmux session named `<name>-run` with `history-limit` 50,000. Done when: a test with a stub agent on `PATH` finds the tmux session, the marker and the claim. Cheaper substitute: running the agent as a child of the launcher's terminal must fail the test that closes the launcher and finds the session alive.
- [x] Build the Claude Code command in `unattended-run.py` from the profile: `claude --model <model> --effort <effort> --session-id <id> --disallowedTools AskUserQuestion,EnterPlanMode,ExitPlanMode`, with `--dangerously-skip-permissions` only when `skip_permissions` is true, and the prompt read from `prompt_file` (RasterFold `unattended-run.sh:66` to `:71`). Done when: a test with a stub `claude` that records its arguments finds exactly those, for both values of `skip_permissions`.
- [x] Resume in `start` of `unattended-run.py` when the marker names a session that is not running: `claude --resume <id>` with a short resume prompt, and a fresh session when the resume fails to start (Impossible OS `run-common.sh:44` to `:61`). Done when: tests cover a resume and the fallback to a fresh session.
- [x] Add `status` to `unattended-run.py`: whether the session is alive, its start time, the guard's phase and run id when one is held, and the health file of §8 when present. Done when: a test parses its output for a live and a stopped run.
- [x] Add `attach` to `unattended-run.py`: attach to the run's tmux session, read-only with `--watch`. Done when: a test asserts the tmux command line for each form.
- [x] Add `stop` to `unattended-run.py`: remove the marker, end the guard with `campaign_guard.py end --reason operator-stop`, kill the heartbeat and run tmux sessions, then send `SIGKILL` to the recorded process group if any of it is still alive after 10 seconds, and clear the claim. Done when: a test with a stub agent that starts a child finds both gone and the guard, marker and claim removed. Cheaper substitute: `tmux kill-session` alone must fail the child-gone assertion.
- [x] Refuse `stop` in `unattended-run.py` when `CONCLAVE_UNATTENDED_RUN=1` is set, which `start` sets inside the run, so a run cannot stop itself (Impossible OS `run.sh:143`). Done when: a test with the variable set finds exit 2 and the session alive.
- [x] Commit: `unattended: launcher that starts, shows and stops a Claude Code run`

**Test checkpoint:** `python -m unittest discover -s kits/unattended/templates/scripts/tests` ends `OK` with tmux installed (the tmux tests skip with a reason where it is not); making `stop` skip the process group kill makes the child-gone test fail.

> **Verified:** 2026-11-12 | §5 | 237aa237c2693d4cdb0b5ef7d5dcb16293515440
> **Review:** `docs/reviews/d02-t02-s5.json`

## 6. Launch commands for Codex and Antigravity

> **Started:** 2026-11-12T12:53:44Z

The launcher starts whichever agent the profile names. The Codex and Antigravity command lines are built only from flags their installed CLIs confirm, and each run is held by its own hook (roadmap recommendation 7).

**Corrected 2026-11-12 (validation):** read on this machine: `codex-cli 0.166.0` in WSL (0.167.0 on Windows) and `agy 1.5.5` in WSL (1.5.6 on Windows). Codex has no flag that sets a new session's id and no `--effort` (effort is `-c model_reasoning_effort=<value>`, a config override); it resumes with `codex resume [SESSION_ID] [PROMPT]`. Antigravity resumes with `--conversation <id>` and starts with an initial prompt through `--prompt-interactive`; it does take `--effort` (`low|medium|high|xhigh|max`), so §2's loader, which left Antigravity's effort free, now checks it against those values. Since neither CLI takes an id the launcher mints, the run is matched by its tag: `campaign_guard.py acquire` (todo kit) also records `CONCLAVE_UNATTENDED_TAG` from its environment as `launch_tag`, which every process of a run carries (§5), and the launcher and the preflight's `--resume-session` treat a guard as the run's when its session or its tag matches; a Codex or Antigravity resume uses the agent session id the run's guard holds, and starts fresh when there is none. With `skip_permissions` false neither gets a permission flag, as with Claude Code.

**Corrected 2026-11-12 (plan review):** the two ids have fixed roles. The run's tag (a uuid the launcher mints; for Claude Code also its `--session-id`) is the marker's `session`, the claim's session and `CONCLAVE_UNATTENDED_TAG`; the marker's `agent_session` is the agent's own id (Claude Code: the tag; Codex and Antigravity: unknown until the run's guard records it). A guard is the run's when its `launch_tag` is the tag or its `session_id` is the agent session, and `campaign_guard.py end` gets the guard's own `session_id`. Tests use unequal ids for crash resume, missing-session fallback, stop, and another run's guard left alone. The help of `codex`, `codex resume` and `agy` is quoted per command surface. The version check passes the recorded version and a newer one, and FAILs an older one, an undiscoverable one and unparseable output, which stops the launch. Each real CLI gets a bounded live proof through `unattended-run.py start` in a scratch project: the seed prompt makes it acquire the guard (its native session id recorded with the run's tag), a killed session resumes, and `stop` leaves nothing.

**Phase:** 2
**Needs:** none
**Surface:** no

**Build order:**

1. Add the Codex and Antigravity commands to `kits/unattended/templates/scripts/unattended-run.py`. Done when: a profile with `agent` set to each starts its stub CLI.
2. Record the checked flags. Done when: the checkpoint passes.

- [x] Read `codex --help` and `codex exec --help` on this machine and write, in `kits/unattended/README.md`, the flags for model, effort, a session to resume, an unattended permission mode and the prompt, with the CLI version. Done when: the README table has one row per flag with the help text's own wording quoted. Cheaper substitute: flags written from memory must fail review; each must appear in the captured help output.
- [x] Read `agy --help` on this machine and write the same table for Antigravity in `kits/unattended/README.md`. Done when: the table is complete, or a flag the launcher needs does not exist and the README says so and what the launcher does without it.
- [x] Add the Codex command to `unattended-run.py` from the profile and the recorded flags, for `start` and for a resume. Done when: a test with a stub `codex` finds the recorded flags and no Claude Code flag.
- [x] Add the Antigravity command to `unattended-run.py` in the same way. Done when: a test with a stub `agy` finds the recorded flags and no Claude Code flag.
- [x] Check in `unattended-preflight.py` that the CLI's version is the one whose flags were recorded or newer, with a FAIL line naming both versions when it is older. Done when: a test with a stub CLI reporting an older version finds that line.
- [x] Commit: `unattended: start a Codex or an Antigravity run`

**Test checkpoint:** `python -m unittest discover -s kits/unattended/templates/scripts/tests` ends `OK`; passing `--disallowedTools` to the stub `codex` makes its test fail.

> **Verified:** 2026-11-12 | §6 | d43ab1f44ad33c95029c2e2377bcc88d459a3b2a
> **Review:** `docs/reviews/d02-t02-s6.json`

## 7. Heartbeat that nudges an idle run and records a dead one as ended

> **Started:** 2026-11-12T18:14:16Z

**Corrected 2026-11-12 (stamp):** the Started line said 2026-11-12T14:04:33Z, the first build's start, which the re-plan (`b141bea`) superseded without restarting it; the re-planned build began after its plan review (run 2026-11-12T18:14:16Z on `b141bea`) and was committed at `acd040c`.

A run nobody watches can go quiet, and one can die. The heartbeat, a loop outside the agent, nudges a live run that has gone quiet, and when the run has died it records the run as ended and stops everything it started; it never restarts it. Source: Impossible OS `scripts/overnight/heartbeat.sh` (105 lines), whose restart half is not lifted.

**Owner decision 2026-11-12:** a run never restarts itself. It starts only when the operator starts it; `stop`, a crash or a reboot ends it, and no heartbeat, watchdog, scheduled task or boot unit resumes it. Nudging a live run inside its session stays. The first build of this section restarted a dead run with backoff (commits `6387d7f`, `11a2ce7`, `6daece2`); its review record is kept as `docs/reviews/02-unattended/D02-T02-s7.superseded-2026-11-12.md`, and the section is reviewed again from its plan.

**Phase:** 2
**Needs:** none
**Surface:** no

**Build order:**

1. Re-scope `heartbeat` in `kits/unattended/templates/scripts/unattended-run.py`: no restart. Done when: a killed run session is recorded as ended on the next tick.
2. Keep the nudge, the end conditions and the bounded writes. Done when: the checkpoint passes.

- [x] Run `heartbeat [--once]` in `unattended-run.py` every `tick_seconds`; `start` launches it in its own tmux session `<name>-heartbeat` unless `--no-heartbeat` is given. Done when: a test with an ordinary `start` finds exactly one heartbeat session, and `stop` removes it.
- [x] Record a dead run as ended in `heartbeat`: when the run's tmux session is gone, end every process tagged with the run and its process group, end the run's own guard (`campaign_guard.py end --reason operator-stop` with the guard's session), remove the marker and the run's claim, and exit 10, starting nothing. Done when: a test kills the run's session under the heartbeat and finds no agent started again, the stub's children gone, no guard, marker or claim, and a later `start` beginning a fresh session. Cheaper substitute: a restart through `start` must fail the no-agent-started assertion.
- [x] Nudge an idle run in `heartbeat`: when the run's tmux window has shown no activity for `idle_minutes` (tmux `window_activity`), send a one-line prompt with `tmux send-keys`, at most once per `idle_minutes`, skipped when a client that can type is attached (a read-only watcher does not count), and count it with `campaign_guard.py heartbeat-still` for the run's guard (process-plan's heartbeat contract). Done when: tests find the nudge sent for an idle run, not for an active one, not with an operator attached, sent with a watcher, not twice within `idle_minutes`, and `heartbeat-still` run for each nudge.
- [x] End the heartbeat loop in `heartbeat` when the run marker is gone, or when the guard's end record (`build/claude-campaign-ended.json`, written by `campaign_guard.py end`) names the run's tag or agent session; a run whose guard was never taken is not treated as finished. Done when: tests for each find exit 10, the heartbeat session gone, and for the run's own end the marker and claim removed.
- [x] Keep the heartbeat's state in `build/unattended-heartbeat.json` (`last_nudge`, `last_error`, `ended`), read back on every tick and kept in memory when a write fails. Done when: a test running 50 ticks with nudges writes no new file under `build/` beyond it, and one with a failing write keeps supervising.
- [x] Commit: `unattended: heartbeat nudges an idle run and records a dead one as ended`

**Corrected 2026-11-12 (plan review):** ending a run is one verified cleanup, done under the launch lock after re-reading the marker and finding it still names the run the tick observed (an operator's new run is never touched): the run's tmux session, every process tagged with the run and its process group are stopped, its own guard is ended, and only once all of that is confirmed are the marker and the run's claim removed; a cleanup that fails keeps both, records `last_error` and is retried on the next tick, never by a restart. This applies as well when the run ends itself (the guard's end record, a stall): nothing it started keeps running. A nudge counts (`last_nudge`, `heartbeat-still`) only when tmux answered the client query and accepted the prompt; a query that fails sends nothing and is recorded. The heartbeat's state names its run's tag: a tick whose marker names another run starts from fresh state, and `ended` holds the reason and time. Tests cover an operator start between observation and cleanup, a failed guard end, processes that outlive SIGKILL, failed tmux queries and sends, the prompt reaching a real pane, and state reloaded by a new heartbeat with the throttle kept and a fresh run's state fresh.

**Test checkpoint:** `python -m unittest discover -s kits/unattended/templates/scripts/tests` ends `OK`; making the heartbeat restart a dead run through `start` makes the no-agent-started test fail.

> **Verified:** 2026-11-12 | §7 | 3f81c42269e125420a3076aac02a50c4382fd893
> **Review:** `docs/reviews/d02-t02-s7.json`

## 8. Ship counter, ship limit and stall marker

> **Started:** 2026-11-12T21:05:31Z

A run that is alive but ships nothing for hours needs the operator. The heartbeat counts sections shipped, stops at a limit the operator set, and leaves a marker when nothing has shipped. Sources: Impossible OS `scripts/overnight/ship_count.py` (66 lines), `supervisor.py:189` and `run.sh:91`.

**Phase:** 2
**Needs:** none
**Surface:** no

**Build order:**

1. Add `ships_between` to `kits/unattended/templates/scripts/lib/unattended.py`. Done when: it counts Implementation Order rows turned `[x]` commit by commit between two commits.
2. Add the health file, the limit and the marker to the heartbeat. Done when: the checkpoint passes.

- [ ] Add `ships_between(root, old, new)` to `lib/unattended.py`: along the first-parent commits from `old` to `new`, one commit at a time, the number of Implementation Order rows under `todo/` that the commit turns from `[ ]` to `[x]`, read with `git diff` and never from the working tree, each row recognised by the todo kit's own `ROW` pattern (`scripts/lib/todo_graph.py:23`) (`ship_count.py`). Done when: a test repository with two rows stamped in two commits returns 2, a row reopened and stamped again inside the range counts both ships, an unstamp or a stamped row's edit counts 0, and an uncommitted `[x]` in the working tree counts nothing. Cheaper substitute: comparing the two endpoints must fail the reopened-row case.
- [ ] Count incrementally in `heartbeat`: the state keeps the ships so far and the last commit counted, and each tick counts only the commits after it. Done when: a test of 20 ticks over an unchanged `HEAD` runs `git diff` for no commit twice.
- [ ] Write `build/unattended-health.json` from `heartbeat` on every tick, through `lib.write_atomic`: `alive`, `ships` since the start, `hours_since_ship` (from the run's start until the first ship), `last_ship` (commit and time), `last_nudge` and `updated`; a write that fails is recorded in `last_error` and never ends supervision. Done when: a test reads each field after a tick, and one with a failing write keeps ticking.
- [ ] Add `--ships N` to `start` in `unattended-run.py`: record `ship_limit` and `start_commit` in the run marker (a marker without them, written before this section, reads as unbounded), keep both across the operator's resume of the same run (`run.sh:91`: a recovery keeps its bound), and refuse `0` or a non-number. Have `heartbeat` end the run through `end_run` (reason `the ship limit was reached`) once `ships_between(start_commit, HEAD)` reaches `ship_limit`. Done when: a test with `--ships 1` and one stamped row finds the run ended, the marker and claim gone and the heartbeat exited 10; a resumed run keeps its bound; `--ships 0` exits 2.
- [ ] Write the marker `build/unattended-needs-operator.md` from `heartbeat` when no section has shipped for `stall_hours`, at most once per `stall_hours`, naming the last ship's commit and time (or the run's start), and send an idle run the stall nudge in place of the plain one, saying nothing has shipped and to find out why before more section work (`supervisor.py:189`, `heartbeat.sh:86`). Done when: tests with an injected clock find one marker at 6 hours, none rewritten at 7, and the stall nudge's text sent to the pane.
- [ ] Show the marker's text in `status` of `unattended-run.py` and remove the marker on the next ship. Done when: a test finds it in the `status` output and gone after a stamped row.
- [ ] Commit: `unattended: count ships, stop at a limit and mark a stall`

**Corrected 2026-11-12 (validation):** the first item compared the endpoints (`[ ]` at `old`, `[x]` at `new`) and said a row unstamped again returns 0; the source counts commit by commit because endpoints miss a section reopened and shipped again in the range (`ship_count.py:51`), and its own row reader takes the first numeric cell, which in this layout is `Order`, so rows are read with the todo kit's `ROW`. The limit ended the run "with `stop`", which also kills the heartbeat's own tmux session mid-stop; it ends through `end_run`, the heartbeat's verified cleanup (§7). The incremental count, the health file's atomic write and the marker's new keys were unstated.

**Test checkpoint:** `python -m unittest discover -s kits/unattended/templates/scripts/tests` ends `OK`; making `ships_between` compare the endpoints makes the reopened-row test fail, and making it read the working tree makes the uncommitted-row test fail.

## 9. Nothing resumes a run without its operator

**Owner decision 2026-11-12:** a run never restarts itself. It starts only when the operator starts it; `stop`, a crash or a reboot ends it, and no heartbeat, watchdog, scheduled task or boot unit resumes it. Nudging a live run inside its session stays. This section proves it across the kits and the SDK: the boot resume the plan first held (a systemd user unit running `autostart`) is not built, and nothing else starts a run on its own.

**Phase:** 2
**Needs:** none
**Surface:** no

**Build order:**

1. Add the refusals and the tests. Done when: the checkpoint passes.

- [ ] Refuse a run launcher as a scheduled command in the automations kit's task loader (`kits/automations/templates/.conclave/automations/run.py`): a task whose command runs `unattended-run.py start`, `start-run.ps1` or another run launcher is refused naming the rule, at load and at install. Done when: tests find the refusal for each launcher form and an ordinary check task accepted.
- [ ] Scan every kit template and the SDK's own scripts for a resume path in `tests/test_forge.py`: a systemd unit, a cron or `@reboot` line, `Register-ScheduledTask`, `schtasks`, a Windows Run key, or an `autostart` command. Done when: the test passes on the tree and fails on a scratch copy that adds any one of them.
- [ ] Prove in `kits/unattended/templates/scripts/tests/test_run.py` that a dead session is not resumed by the heartbeat and a crashed agent is not restarted, over 20 ticks. Done when: the test finds one agent start in all.
- [ ] Record in `kits/unattended/README.md` and the roadmap that a run never restarts itself, and why. Done when: both say it and neither promises a boot resume.
- [ ] Commit: `unattended: nothing resumes a run without its operator`

**Test checkpoint:** `python -m unittest discover -s tests -p test_forge.py` ends `OK`; adding `Register-ScheduledTask` to a scratch copy of a kit template makes the scan fail.

## 10. Desktop shortcut that starts the run

One double-click starts the run. RasterFold's shortcut does this and is not versioned; the kit generates it. Sources: RasterFold's shortcut (`wsl.exe -d Ubuntu --cd <project> -- bash scripts/unattended-run.sh`); Impossible OS `scripts/run-desktop.sh` (80 lines).

**Phase:** 2
**Needs:** windows-host
**Surface:** no

**Build order:**

1. Add `shortcut` to `kits/unattended/templates/scripts/unattended-run.py` for a Linux desktop entry. Done when: a `.desktop` file is written.
2. Add `kits/unattended/templates/scripts/unattended-shortcut.ps1` for Windows. Done when: the checkpoint passes.

- [ ] Add `shortcut` to `unattended-run.py`: write `<name>-unattended.desktop` to `~/.local/share/applications/` (or `--dir`), opening a terminal that runs `start` and stays open on a FAIL. Done when: a test asserts the entry's `Exec`, `Name` and `Terminal=true`, and `shortcut --remove` deletes it.
- [ ] Create `unattended-shortcut.ps1`: make `<Project> <Runner> campaign.lnk` on the user's desktop with `WScript.Shell`, one per runner the project uses (`Claude`, `Carbon` for Antigravity, `Codex`), each passing its agent to `start`, with an icon rendered by `scripts/campaign-icon.py badge` from the project's own icon into `%LOCALAPPDATA%\<Project>\` (the shape of Office's and Isotone's campaign launchers, owner 2026-11-12), targeting `wsl.exe -d <distro> --cd <project path in WSL> -- python3 scripts/unattended-run.py start`, with the distro and path as parameters and `-Remove` to delete it. Done when: running it on Windows creates the link and reading it back through `WScript.Shell` gives that target and arguments. Cheaper substitute: a `.cmd` file on the desktop must fail review; the source is a `.lnk`.
- [ ] Refuse in `unattended-shortcut.ps1` a distro that `wsl.exe -l -q` does not list and a project path that does not exist in it, before any file is written. Done when: both refusals are shown with their message and exit 1, and no link exists afterwards.
- [ ] Translate a Windows-drive project path to its WSL path in `unattended-shortcut.ps1` with `wsl.exe wslpath`, so a project on `D:\` starts from `/mnt/d/...`. Done when: the created link's arguments hold the `/mnt/` path for a project on a Windows drive.
- [ ] Commit: `unattended: desktop shortcut that starts the run`

**Corrected 2026-11-12 (owner):** the launchers take the shape of Office's and Isotone's: named `<Project> Claude campaign` and `<Project> Carbon campaign`, each with the project's icon and its runner's badge in the corner. `scripts/campaign-icon.py` (built with the SDK's own launchers, `scripts/start-run.ps1`) renders it with the standard library alone; `start` takes the runner as `--agent` over the profile's `agent`.

**Test checkpoint:** `python -m unittest discover -s kits/unattended/templates/scripts/tests` ends `OK` for the `.desktop` entry, and on Windows `pwsh scripts/unattended-shortcut.ps1 -Distro Ubuntu -Project <path>` creates a link whose target reads back as `wsl.exe`; a wrong distro name exits 1 and creates nothing.

## 11. Operator document and `unattended-run` skill

The operator needs one page that says how to start, watch, stop and resume a run, and each agent needs a skill that says the same. Source: RasterFold `docs/unattended-run.md` (60 lines).

**Phase:** 2
**Needs:** none
**Surface:** no

**Build order:**

1. Write `kits/unattended/templates/docs/unattended-run.md`. Done when: every command in it exists in `unattended-run.py`.
2. Add the skill in the three agent folders. Done when: the checkpoint passes.

- [ ] Write `docs/unattended-run.md` in the kit: set the profile, run the doctor, start (shortcut or command), watch, attach, stop, start again after a stop or a crash (nothing restarts a run on its own), what the heartbeat does, what the stall marker means and the Windows limit. Done when: a test extracts every `unattended-run.py <command>` in the document and finds each in the launcher's argument parser.
- [ ] Create `kits/unattended/templates/.claude/skills/unattended-run/SKILL.md` with a description that triggers on starting, stopping or debugging an unattended run, pointing at the document and naming what the agent must never do inside a run (stop it, ask the operator). Done when: the skill's frontmatter has `name` and `description` and its body names `docs/unattended-run.md`.
- [ ] Create the Antigravity and Codex copies under `.agents/skills/unattended-run/` and `.codex/skills/unattended-run/` (with `agents/openai.yaml` for Codex), each naming its own hook file. Done when: `python forge.py doctor <fresh install> unattended` reports the skill `ok` in all three folders.
- [ ] Fill `kits/unattended/README.md`: what the kit installs, what it needs (the todo kit and tmux; nothing resumes a run at boot), the install command and what was not lifted from the two projects and why. Done when: the README lists every file under `kits/unattended/templates/`.
- [ ] Add a fresh-install test to `tests/test_forge.py`: `init --kit todo --kit unattended`, then the doctor, then the kit's own tests in the installed copy. Done when: it passes and fails when a template file is removed from a scratch copy of the kit.
- [ ] Commit: `unattended: operator document and skill`

**Test checkpoint:** `python -m unittest discover -s tests -p test_forge.py` ends `OK`; naming a command in `docs/unattended-run.md` that the launcher lacks makes the document test fail.

## Verification

- In WSL, a scratch project with the todo and unattended kits and a stub agent is started with `python3 scripts/unattended-run.py start --ships 1`, a stamped section ends the run; a second run's session is killed and the heartbeat records it as ended without restarting it; and `stop` leaves no process, marker, claim or guard behind.
- On Windows, the generated shortcut starts that run through `wsl.exe`.
- `python -m unittest discover -s tests` passes.
- `python scripts/todo-graph.py validate` and `python scripts/todo-graph.py plan --check` pass.
