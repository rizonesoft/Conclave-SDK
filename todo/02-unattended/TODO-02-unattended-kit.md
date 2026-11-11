---
schema_version: 1
id: unattended-kit
domain: 02-unattended
status: active
title: "TODO-02 -- Unattended kit"
---

# TODO-02 -- Unattended kit

> **Goal:** A project installs one kit and can start a `process-plan` run that keeps going with nobody at the keyboard: a preflight that refuses a run that cannot work, a launcher that starts the agent in a session that survives the terminal, a heartbeat that restarts a dead run and nudges an idle one, a boot unit that resumes it, and a desktop shortcut that starts it.

> **Current state:** Measured 2026-11-11. No `kits/unattended/` exists; `forge.py` knows six kits (`KIT_ORDER`, `forge.py:139`). The todo kit's guard holds a run only from inside the session: its docstring says there is no keep-alive outside it (`kits/todo/templates/scripts/campaign_guard.py:19`). The two projects built the outside half separately. RasterFold (`~/projects/RasterFold` in WSL, `b33493346141f96b6b304cd3e0c393595382f056`) has `scripts/unattended-run.sh` (71 lines: lock, preflight, `exec claude`), `scripts/unattended-preflight.py` (509 lines), `docs/unattended-run.md` (60 lines) and a desktop shortcut that is not versioned; nothing restarts its run. Impossible OS (`~/projects/impossible-os` in WSL, `17a762d39ccd1958cbe711901f645fd9b042e939`) has `scripts/run.sh` (157 lines), `scripts/overnight/run-common.sh` (62), `heartbeat.sh` (105), `supervisor.py` (225), `ship_count.py` (66) and `scripts/run-desktop.sh` (80): a tmux session, a heartbeat that restarts and nudges it, and a systemd user unit that resumes it at boot. Both run in WSL and both start Claude Code only.

## Inputs

- `docs/plans/2026-11-11-sdk-audit-and-roadmap.md`: finding 8, recommendation 5 (RasterFold's unattended runner, then Impossible OS's overnight supervisor) and the `unattended` rows of the kits table.
- RasterFold at `b33493346141f96b6b304cd3e0c393595382f056`: `scripts/unattended-run.sh`, `scripts/unattended-preflight.py` (checks at `:413` to `:495`, `run` at `:75`, `kill_group` at `:135`, `write_claim` at `:288`), `docs/unattended-run.md`.
- Impossible OS at `17a762d39ccd1958cbe711901f645fd9b042e939`: `scripts/run.sh`, `scripts/overnight/run-common.sh` (`run_launch` at `:42`), `scripts/overnight/heartbeat.sh`, `scripts/overnight/supervisor.py` (`REPAIR_AFTER_HOURS` at `:31`), `scripts/overnight/ship_count.py`, `scripts/run-desktop.sh`.
- Not lifted, on purpose: Impossible OS's machinery revert (`supervisor.py:108`, which reverts commits and depends on that project's frozen-file list), its webhook alert (`notify.sh:35`), its skill-deny check and its phase guard; RasterFold's `--repair` compile database rebuild, its scout roster check and its seed prompt. Each is specific to its project.
- -> XREF: D02 T01 §5 -- the preflight runs the guard's self-test, and a Codex or Antigravity run is held by the hooks wired there

## Outcome

- `python forge.py kit <project> unattended` installs the kit, and `python forge.py doctor <project> unattended` says what the machine still needs.
- `python3 scripts/unattended-run.py start` runs the preflight and starts the agent in a tmux session; `status`, `attach` and `stop` act on that run; a run that dies is restarted and an idle run is nudged.
- A run that was live when the machine went down resumes at boot, and a desktop shortcut starts a run with one double-click.
- Limit, stated: the run lives in tmux, so it runs on Linux and in WSL. On Windows the shortcut starts it through `wsl.exe`, as RasterFold's does. There is no Windows-native launcher.

**Adjacency:** list=not-applicable (one run per project, found by its session name); document=not-applicable (nothing a user carries or files); settings=applicable @ D02 T02 §2; reporting=applicable @ D02 T02 §8; notifications=applicable @ D02 T02 §8; permissions=applicable @ D02 T02 §3; audit=applicable @ D02 T02 §4; exchange=not-applicable (no import or export); reverse=applicable @ D02 T02 §5

**Adjacency rationale:** Every tunable is a key of the run profile with a named consumer and a refusal test (§2). The health file and the stall marker are the run's reporting and its notice to the operator (§8). The preflight is the refusal side: it says why a run may not start (§3). The launch claim records who started which run and when (§4). The reverse of `start` is `stop`, which ends the whole process tree and the guard (§5).

## Implementation Order

| Order | Section | Deliverable | Depends On | Status |
| ----- | ------- | ----------- | ---------- | ------ |
| 1 | §1 | Unattended kit known to `forge.py` | -- | [ ] |
| 2 | §2 | Run profile `.conclave/unattended.json` and its loader | §1 | [ ] |
| 3 | §3 | Preflight with a PASS or FAIL line per precondition | §2 | [ ] |
| 4 | §4 | Launch lock and claim | §2 | [ ] |
| 5 | §5 | Launcher for a Claude Code run under tmux | §3, §4 | [ ] |
| 6 | §6 | Launch commands for Codex and Antigravity | §5, T01 §2, T01 §3 | [ ] |
| 7 | §7 | Heartbeat that restarts a dead run and nudges an idle one | §5 | [ ] |
| 8 | §8 | Ship counter, ship limit and stall marker | §7 | [ ] |
| 9 | §9 | Boot resume through a systemd user unit | §7 | [ ] |
| 10 | §10 | Desktop shortcut that starts the run | §5 | [ ] |
| 11 | §11 | Operator document and `unattended-run` skill | §8, §9, §10 | [ ] |

## 1. Unattended kit known to `forge.py`

The kit folder, its place in the install order, its detection and its doctor branch, so the later sections have somewhere to put files and a way to prove an install.

**Phase:** 2
**Needs:** none
**Surface:** no

**Build order:**

1. Create `kits/unattended/` with `README.md` and an empty `templates/scripts/` holding the shared module. Done when: `python forge.py kits` lists `unattended`.
2. Teach `forge.py` the kit. Done when: the checkpoint passes.

- [ ] Create `kits/unattended/README.md` and `kits/unattended/templates/scripts/lib/unattended.py` (a module with a docstring and `SCHEMA_VERSION = 1`, filled by §2). Done when: `python forge.py kits` prints `unattended` in its list.
- [ ] Add `unattended` to `KIT_ORDER` in `forge.py` after `automations`, and to the kit names in the usage docstring (`forge.py:6`) and the `--kit` help texts (`forge.py:734`, `:740`). Done when: a test installs `init --kit unattended --kit todo` and finds the todo files written first.
- [ ] Detect the kit in `installed_kits` of `forge.py` by `scripts/unattended-run.py`. Done when: a test finds `unattended` in `check_repo(...)["kits"]` after an install and not before.
- [ ] Add an `unattended` branch to `doctor_repo` in `forge.py`: each kit file present, the todo kit present (`scripts/campaign_guard.py`), and `tmux` on `PATH` (`setup_required` with the install hint when it is not). Done when: tests find `ok` for the files on a fresh install and `setup_required` for a project without the todo kit.
- [ ] List the kit in `README.md`, `kits/README.md` and `AGENTS.md` (Purpose), and state that the SDK does not install it in itself (`SELF_KITS` unchanged). Done when: the three documents name it and their table rows are within 120 characters.
- [ ] Commit: `unattended: kit skeleton known to forge.py`

**Test checkpoint:** `python -m unittest discover -s tests -p test_forge.py` ends `OK`; removing `unattended` from `KIT_ORDER` makes the order test fail.

## 2. Run profile `.conclave/unattended.json` and its loader

Everything the two projects hard-coded (agent, model, effort, prompt, branch, thresholds, session name) becomes one profile the project owns. The loader refuses a profile it cannot run.

**Phase:** 2
**Needs:** none
**Surface:** no

**Build order:**

1. Write `load_profile` in `kits/unattended/templates/scripts/lib/unattended.py` and the template profile. Done when: the template loads.
2. Test every refusal. Done when: the checkpoint passes.

- [ ] Create `kits/unattended/templates/.conclave/unattended.json` with `schema_version`, `name`, `agent`, `model`, `effort`, `prompt_file`, `branch`, `skip_permissions`, `tools`, `min_disk_gb`, `min_ram_gb`, `tick_seconds`, `idle_minutes`, `stall_hours` and `preflight`, defaulting to `claude`, `main`, 20, 2, 300, 45 and 6 (RasterFold `unattended-preflight.py` thresholds; Impossible OS `heartbeat.sh:17`, `supervisor.py:31`), with `name`, `model` and `effort` left `null` for the project to set. Done when: `python -m json.tool` reads it.
- [ ] Add `load_profile(root)` to `lib/unattended.py`, returning the profile with every key checked: `agent` one of `claude`, `codex`, `agy`; `name` matching `[a-z0-9][a-z0-9-]{1,40}`; `prompt_file` a relative path inside the repository that exists; numbers whole and positive; `preflight` a list of `{"name", "command", "timeout_seconds"}` with `command` a list of strings. Done when: a test for each fault reads a refusal naming `.conclave/unattended.json` and the key. Cheaper substitute: `dict.get` with silent defaults must fail the unknown-key and wrong-type tests.
- [ ] Refuse a profile whose `name`, `model` or `effort` is still `null` in `load_profile`, saying which to set. Done when: a test loads the shipped template unchanged and reads that refusal, and loads it with the three set and gets the profile.
- [ ] Create `kits/unattended/templates/docs/unattended-prompt.md`: a seed prompt that tells the agent to run `process-plan` to completion, never to ask the operator, and to record every decision in the run file, with no project name in it. Done when: the template profile's `prompt_file` names it and `load_profile` accepts it.
- [ ] Add `kits/unattended/templates/scripts/tests/test_unattended.py` with the loader tests, run from `tests/test_forge.py` as the other kits' tests are (`tests/test_forge.py:444`). Done when: `python -m unittest discover -s kits/unattended/templates/scripts/tests` passes and the quick suite runs it.
- [ ] Commit: `unattended: run profile and its loader`

**Test checkpoint:** `python -m unittest discover -s kits/unattended/templates/scripts/tests` ends `OK`; accepting an unknown `agent` makes its test fail.

## 3. Preflight with a PASS or FAIL line per precondition

A run that cannot work should not start. The preflight prints one line per precondition and exits 1 on any FAIL. Source: RasterFold `scripts/unattended-preflight.py:413` to `:495`, with its project-specific checks left behind.

**Phase:** 2
**Needs:** none
**Surface:** no

**Build order:**

1. Create `kits/unattended/templates/scripts/unattended-preflight.py` with the generic checks. Done when: it prints PASS lines on a ready fixture and exits 0.
2. Add the project's own checks from the profile and the process-tree stop. Done when: the checkpoint passes.

- [ ] Create `unattended-preflight.py` with the git checks: on the profile's `branch`, a clean tree, and `HEAD` not behind its upstream when one is set. Done when: tests on fixture repositories find one FAIL line for each broken state and exit 1, and exit 0 with only PASS lines otherwise. Cheaper substitute: one combined "git ok" line must fail the per-state tests.
- [ ] Add the run checks to `unattended-preflight.py`: no live campaign guard (`build/claude-campaign-guard.json`) and no other launch claim (§4). Done when: tests with a guard file and with a live claim each find their FAIL line.
- [ ] Add the tool checks to `unattended-preflight.py`: `git`, `python3`, `tmux`, the profile agent's CLI and every name in the profile's `tools` are on `PATH`. Done when: a test with a `tools` entry that does not exist finds its FAIL line naming the tool.
- [ ] Add the hook check to `unattended-preflight.py`: the profile agent's Stop hook file names `campaign_guard.py`, and `python3 scripts/campaign_guard.py --self-test` exits 0 (the self-test is built in D02 T01 §5). Done when: a test with a hook file that lacks the hook finds FAIL and one with a seeded install finds PASS.
- [ ] Add the headroom checks to `unattended-preflight.py`: free disk on the repository's volume at least `min_disk_gb` and available memory at least `min_ram_gb`, read with `shutil.disk_usage` and `/proc/meminfo`. Done when: a test with thresholds above what the machine has finds both FAIL lines with the measured values.
- [ ] Run the profile's `preflight` commands from `unattended-preflight.py`: each with no shell, its own timeout, a new process group and the whole group killed on timeout or interrupt (RasterFold `:75`, `:135`), showing only the last line of its output. Done when: a test with a command that starts a child and sleeps past its timeout finds FAIL with exit 124 and the child gone. Cheaper substitute: `subprocess.run(timeout=...)` must fail the child-gone assertion.
- [ ] Refuse to run on Windows without WSL in `unattended-preflight.py` with one line saying the run needs tmux. Done when: a test with `os.name` patched to `nt` finds exit 1 and that line.
- [ ] Commit: `unattended: preflight that refuses a run that cannot work`

**Test checkpoint:** `python -m unittest discover -s kits/unattended/templates/scripts/tests` ends `OK`; dropping the clean-tree check makes its test fail.

## 4. Launch lock and claim

Two launches at once would start two agents on one tree. A lock held for the launch and a claim file that names the run stop that, and the claim is the record of who started what. Source: RasterFold `scripts/unattended-run.sh:28` and `scripts/unattended-preflight.py:288`.

**Phase:** 2
**Needs:** none
**Surface:** no

**Build order:**

1. Add `launch_lock`, `write_claim`, `read_claim` and `clear_claim` to `lib/unattended.py`. Done when: a second launch is refused while the first holds the lock.
2. Cover the stale cases. Done when: the checkpoint passes.

- [ ] Add `launch_lock(root)` to `lib/unattended.py`: an exclusive `fcntl.flock` on `build/unattended-launch.lock`, not waiting, released when the launcher exits. Done when: a test holding the lock in one process finds a second refused naming the lock file.
- [ ] Add `write_claim(root, session, pid, agent)` to `lib/unattended.py`, writing `build/unattended-launch.json` (session id, tmux session name, pid, agent, UTC start) through a temporary file and `os.replace`. Done when: a test reads back what was written. Cheaper substitute: a plain `open(..., "w")` must fail review under the repository's atomic-write rule.
- [ ] Add `read_claim(root)` to `lib/unattended.py`, returning the claim and whether it is live: live means its tmux session exists. A claim that is not JSON or lacks a key reads as stale with the reason. Done when: tests cover a live claim, a claim whose session is gone and a malformed file.
- [ ] Add `clear_claim(root)` to `lib/unattended.py`, removing the claim only when it is stale or belongs to the session being stopped. Done when: a test finds a live claim of another session untouched and a refusal naming it.
- [ ] Commit: `unattended: launch lock and claim`

**Test checkpoint:** `python -m unittest discover -s kits/unattended/templates/scripts/tests` ends `OK`; making `read_claim` call every claim live makes the stale-claim test fail.

## 5. Launcher for a Claude Code run under tmux

`scripts/unattended-run.py` is the operator's entry point: `start`, `status`, `attach` and `stop`. `start` takes the lock, runs the preflight and starts Claude Code in a tmux session that outlives the terminal. Sources: RasterFold `scripts/unattended-run.sh:66`; Impossible OS `scripts/run.sh:4` and `scripts/overnight/run-common.sh:42`.

**Phase:** 2
**Needs:** none
**Surface:** no

**Build order:**

1. Create `kits/unattended/templates/scripts/unattended-run.py` with `start` and `status`. Done when: a stub agent runs in a tmux session named from the profile.
2. Add `attach` and `stop`, which ends the whole tree. Done when: the checkpoint passes.

- [ ] Add `start` to `unattended-run.py`: take `launch_lock`, run `unattended-preflight.py` and stop with its output on any FAIL, mint a session id, write the run marker `build/unattended-run.json` and the claim, then start the agent in a detached tmux session named `<name>-run` with `history-limit` 50,000. Done when: a test with a stub agent on `PATH` finds the tmux session, the marker and the claim. Cheaper substitute: running the agent as a child of the launcher's terminal must fail the test that closes the launcher and finds the session alive.
- [ ] Build the Claude Code command in `unattended-run.py` from the profile: `claude --model <model> --effort <effort> --session-id <id> --disallowedTools AskUserQuestion,EnterPlanMode,ExitPlanMode`, with `--dangerously-skip-permissions` only when `skip_permissions` is true, and the prompt read from `prompt_file` (RasterFold `unattended-run.sh:66` to `:71`). Done when: a test with a stub `claude` that records its arguments finds exactly those, for both values of `skip_permissions`.
- [ ] Resume in `start` of `unattended-run.py` when the marker names a session that is not running: `claude --resume <id>` with a short resume prompt, and a fresh session when the resume fails to start (Impossible OS `run-common.sh:44` to `:61`). Done when: tests cover a resume and the fallback to a fresh session.
- [ ] Add `status` to `unattended-run.py`: whether the session is alive, its start time, the guard's phase and run id when one is held, and the health file of §8 when present. Done when: a test parses its output for a live and a stopped run.
- [ ] Add `attach` to `unattended-run.py`: attach to the run's tmux session, read-only with `--watch`. Done when: a test asserts the tmux command line for each form.
- [ ] Add `stop` to `unattended-run.py`: remove the marker, end the guard with `campaign_guard.py end --reason operator-stop`, kill the heartbeat and run tmux sessions, then send `SIGKILL` to the recorded process group if any of it is still alive after 10 seconds, and clear the claim. Done when: a test with a stub agent that starts a child finds both gone and the guard, marker and claim removed. Cheaper substitute: `tmux kill-session` alone must fail the child-gone assertion.
- [ ] Refuse `stop` in `unattended-run.py` when `CONCLAVE_UNATTENDED_RUN=1` is set, which `start` sets inside the run, so a run cannot stop itself (Impossible OS `run.sh:143`). Done when: a test with the variable set finds exit 2 and the session alive.
- [ ] Commit: `unattended: launcher that starts, shows and stops a Claude Code run`

**Test checkpoint:** `python -m unittest discover -s kits/unattended/templates/scripts/tests` ends `OK` with tmux installed (the tmux tests skip with a reason where it is not); making `stop` skip the process group kill makes the child-gone test fail.

## 6. Launch commands for Codex and Antigravity

The launcher starts whichever agent the profile names. The Codex and Antigravity command lines are built only from flags their installed CLIs confirm, and each run is held by its own hook (roadmap recommendation 7).

**Phase:** 2
**Needs:** none
**Surface:** no

**Build order:**

1. Add the Codex and Antigravity commands to `kits/unattended/templates/scripts/unattended-run.py`. Done when: a profile with `agent` set to each starts its stub CLI.
2. Record the checked flags. Done when: the checkpoint passes.

- [ ] Read `codex --help` and `codex exec --help` on this machine and write, in `kits/unattended/README.md`, the flags for model, effort, a session to resume, an unattended permission mode and the prompt, with the CLI version. Done when: the README table has one row per flag with the help text's own wording quoted. Cheaper substitute: flags written from memory must fail review; each must appear in the captured help output.
- [ ] Read `agy --help` on this machine and write the same table for Antigravity in `kits/unattended/README.md`. Done when: the table is complete, or a flag the launcher needs does not exist and the README says so and what the launcher does without it.
- [ ] Add the Codex command to `unattended-run.py` from the profile and the recorded flags, for `start` and for a resume. Done when: a test with a stub `codex` finds the recorded flags and no Claude Code flag.
- [ ] Add the Antigravity command to `unattended-run.py` in the same way. Done when: a test with a stub `agy` finds the recorded flags and no Claude Code flag.
- [ ] Check in `unattended-preflight.py` that the CLI's version is the one whose flags were recorded or newer, with a FAIL line naming both versions when it is older. Done when: a test with a stub CLI reporting an older version finds that line.
- [ ] Commit: `unattended: start a Codex or an Antigravity run`

**Test checkpoint:** `python -m unittest discover -s kits/unattended/templates/scripts/tests` ends `OK`; passing `--disallowedTools` to the stub `codex` makes its test fail.

## 7. Heartbeat that restarts a dead run and nudges an idle one

Nothing restarts RasterFold's run when it dies. Impossible OS's heartbeat does: a loop outside the agent that restarts a dead session with backoff and nudges one that has gone quiet. Source: Impossible OS `scripts/overnight/heartbeat.sh` (105 lines).

**Phase:** 2
**Needs:** none
**Surface:** no

**Build order:**

1. Add `heartbeat` to `kits/unattended/templates/scripts/unattended-run.py` and start it from `start`. Done when: a killed run session is restarted on the next tick.
2. Add the backoff, the nudge and the exit conditions. Done when: the checkpoint passes.

- [ ] Add `heartbeat [--once]` to `unattended-run.py`: every `tick_seconds`, check the run; `start` launches it in its own tmux session `<name>-heartbeat`. Done when: a test with `--once` and a killed run session finds the run restarted through the resume path of §5.
- [ ] Back off restarts in `heartbeat`: wait `tick_seconds * 2 ** min(deaths, 5)`, capped at 3,600 seconds, before the next restart, and reset `deaths` after the run has been alive for one hour; keep `deaths`, `wait_until` and `last_restart` in `build/unattended-heartbeat.json`, written atomically (Impossible OS `heartbeat.sh:19`, `:31`, `:65` to `:78`). Done when: tests with an injected clock find the waits 300, 600 and 1,200 seconds and the reset. Cheaper substitute: a fixed wait must fail the 600 second assertion.
- [ ] Nudge an idle run in `heartbeat`: when the run's tmux window has shown no activity for `idle_minutes` (tmux `window_activity`, which works for every agent; Impossible OS read the Claude transcript's age at `heartbeat.sh:22`), send a one-line prompt with `tmux send-keys`, skipped when a client that is not read-only is attached (`heartbeat.sh:41`). Done when: tests find the nudge sent for an idle run, not sent for an active one and not sent with an operator attached.
- [ ] End the heartbeat loop in `heartbeat` when the run marker is gone, or when the campaign guard was held and has been released by the run itself. Done when: tests for each find the loop returning 10 and the heartbeat session gone, and a run whose guard was never acquired is not treated as finished.
- [ ] Bound what the heartbeat writes: it keeps state files only and writes no log. Done when: a test running 50 ticks finds no new file under `build/` beyond `unattended-heartbeat.json` and the health file of §8.
- [ ] Commit: `unattended: heartbeat restarts a dead run and nudges an idle one`

**Test checkpoint:** `python -m unittest discover -s kits/unattended/templates/scripts/tests` ends `OK`; removing the backoff makes the 600 second test fail.

## 8. Ship counter, ship limit and stall marker

A run that is alive but ships nothing for hours needs the operator. The heartbeat counts sections shipped, stops at a limit the operator set, and leaves a marker when nothing has shipped. Sources: Impossible OS `scripts/overnight/ship_count.py` (66 lines), `supervisor.py:189` and `run.sh:91`.

**Phase:** 2
**Needs:** none
**Surface:** no

**Build order:**

1. Add `ships_between` to `kits/unattended/templates/scripts/lib/unattended.py`. Done when: it counts Implementation Order rows turned `[x]` between two commits.
2. Add the health file, the limit and the marker to the heartbeat. Done when: the checkpoint passes.

- [ ] Add `ships_between(root, old, new)` to `lib/unattended.py`: the number of Implementation Order rows under `todo/` that are `[ ]` at `old` and `[x]` at `new`, read with `git show` and never from the working tree (`ship_count.py`). Done when: a test repository with two rows stamped between two commits returns 2, and a row unstamped again returns 0 for it. Cheaper substitute: counting `[x]` at `new` alone must fail, because it counts rows that were already done.
- [ ] Write `build/unattended-health.json` from `heartbeat` on every tick: alive, ships since the start, hours since the last ship, restarts, the last nudge. Done when: a test reads the file after a tick and finds each field.
- [ ] Add `--ships N` to `start` in `unattended-run.py`: record `N` and the start commit in the run marker, and have `heartbeat` end the run with `stop` once `ships_between` reaches `N` (`run.sh:91`). Done when: a test with `--ships 1` and one stamped row finds the run stopped and the marker gone.
- [ ] Write the marker `build/unattended-needs-operator.md` from `heartbeat` when no section has shipped for `stall_hours`, at most once per `stall_hours`, naming the last ship's commit and time, and send the run a second nudge that says nothing has shipped (`supervisor.py:189`, `heartbeat.sh:86`). Done when: tests with an injected clock find one marker at 6 hours and no second one at 7.
- [ ] Show the marker's text in `status` of `unattended-run.py` and remove the marker on the next ship. Done when: a test finds it in the `status` output and gone after a stamped row.
- [ ] Commit: `unattended: count ships, stop at a limit and mark a stall`

**Test checkpoint:** `python -m unittest discover -s kits/unattended/templates/scripts/tests` ends `OK`; making `ships_between` read the working tree makes its test fail.

## 9. Boot resume through a systemd user unit

A run that was live when the machine or WSL restarted should come back without the operator. A oneshot user unit runs `autostart` at boot, which resumes only a run whose marker is still there. Source: Impossible OS `scripts/run.sh:27`, `:41` to `:72` and `:114` to `:124`.

**Phase:** 2
**Needs:** none
**Surface:** no

**Build order:**

1. Add `autostart` and the unit writer to `kits/unattended/templates/scripts/unattended-run.py`. Done when: the unit file is written for a profile.
2. Install and remove it from `start` and `stop`. Done when: the checkpoint passes.

- [ ] Add `autostart` to `unattended-run.py`: when the run marker exists and no run session is alive, resume the run and its heartbeat through `start`'s resume path; do nothing otherwise. Done when: tests cover a marker with no session (resumed), no marker (nothing) and a live session (nothing).
- [ ] Add `unit_text(profile, root, python)` to `unattended-run.py`, returning a oneshot user unit named `<name>-unattended.service` that runs `autostart` from the repository, `WantedBy=default.target`, with every path quoted. Done when: a test asserts the unit's `ExecStart`, working directory and a path with a space quoted.
- [ ] Write and enable the unit from `start` in `unattended-run.py` into `~/.config/systemd/user/` (or the folder in `CONCLAVE_SYSTEMD_DIR`, for tests), skipped with one line when the user manager does not answer or `--no-autostart` is given. Done when: a test with the folder override finds the file, and one with a stub `systemctl` that fails finds the skip line and the run still started.
- [ ] Disable and delete the unit from `stop` in `unattended-run.py`. Done when: a test finds the file gone after `stop` and a stopped run not resumed by `autostart`.
- [ ] Add a `systemd-user` check to the `unattended` branch of `doctor_repo` in `forge.py` through `_systemd_user_manager` (`forge.py:534`). Done when: a test with a stub that fails finds `setup_required`.
- [ ] Commit: `unattended: resume a live run at boot`

**Test checkpoint:** `python -m unittest discover -s kits/unattended/templates/scripts/tests` ends `OK`; making `autostart` ignore the marker makes the no-marker test fail.

## 10. Desktop shortcut that starts the run

One double-click starts the run. RasterFold's shortcut does this and is not versioned; the kit generates it. Sources: RasterFold's shortcut (`wsl.exe -d Ubuntu --cd <project> -- bash scripts/unattended-run.sh`); Impossible OS `scripts/run-desktop.sh` (80 lines).

**Phase:** 2
**Needs:** windows-host
**Surface:** no

**Build order:**

1. Add `shortcut` to `kits/unattended/templates/scripts/unattended-run.py` for a Linux desktop entry. Done when: a `.desktop` file is written.
2. Add `kits/unattended/templates/scripts/unattended-shortcut.ps1` for Windows. Done when: the checkpoint passes.

- [ ] Add `shortcut` to `unattended-run.py`: write `<name>-unattended.desktop` to `~/.local/share/applications/` (or `--dir`), opening a terminal that runs `start` and stays open on a FAIL. Done when: a test asserts the entry's `Exec`, `Name` and `Terminal=true`, and `shortcut --remove` deletes it.
- [ ] Create `unattended-shortcut.ps1`: make `<name> Unattended Run.lnk` on the user's desktop with `WScript.Shell`, targeting `wsl.exe -d <distro> --cd <project path in WSL> -- python3 scripts/unattended-run.py start`, with the distro and path as parameters and `-Remove` to delete it. Done when: running it on Windows creates the link and reading it back through `WScript.Shell` gives that target and arguments. Cheaper substitute: a `.cmd` file on the desktop must fail review; the source is a `.lnk`.
- [ ] Refuse in `unattended-shortcut.ps1` a distro that `wsl.exe -l -q` does not list and a project path that does not exist in it, before any file is written. Done when: both refusals are shown with their message and exit 1, and no link exists afterwards.
- [ ] Translate a Windows-drive project path to its WSL path in `unattended-shortcut.ps1` with `wsl.exe wslpath`, so a project on `D:\` starts from `/mnt/d/...`. Done when: the created link's arguments hold the `/mnt/` path for a project on a Windows drive.
- [ ] Commit: `unattended: desktop shortcut that starts the run`

**Test checkpoint:** `python -m unittest discover -s kits/unattended/templates/scripts/tests` ends `OK` for the `.desktop` entry, and on Windows `pwsh scripts/unattended-shortcut.ps1 -Distro Ubuntu -Project <path>` creates a link whose target reads back as `wsl.exe`; a wrong distro name exits 1 and creates nothing.

## 11. Operator document and `unattended-run` skill

The operator needs one page that says how to start, watch, stop and resume a run, and each agent needs a skill that says the same. Source: RasterFold `docs/unattended-run.md` (60 lines).

**Phase:** 2
**Needs:** none
**Surface:** no

**Build order:**

1. Write `kits/unattended/templates/docs/unattended-run.md`. Done when: every command in it exists in `unattended-run.py`.
2. Add the skill in the three agent folders. Done when: the checkpoint passes.

- [ ] Write `docs/unattended-run.md` in the kit: set the profile, run the doctor, start (shortcut or command), watch, attach, stop, resume after a stop or a crash, what the heartbeat does, what the stall marker means and the Windows limit. Done when: a test extracts every `unattended-run.py <command>` in the document and finds each in the launcher's argument parser.
- [ ] Create `kits/unattended/templates/.claude/skills/unattended-run/SKILL.md` with a description that triggers on starting, stopping or debugging an unattended run, pointing at the document and naming what the agent must never do inside a run (stop it, ask the operator). Done when: the skill's frontmatter has `name` and `description` and its body names `docs/unattended-run.md`.
- [ ] Create the Antigravity and Codex copies under `.agents/skills/unattended-run/` and `.codex/skills/unattended-run/` (with `agents/openai.yaml` for Codex), each naming its own hook file. Done when: `python forge.py doctor <fresh install> unattended` reports the skill `ok` in all three folders.
- [ ] Fill `kits/unattended/README.md`: what the kit installs, what it needs (the todo kit, tmux, a systemd user manager for boot resume), the install command and what was not lifted from the two projects and why. Done when: the README lists every file under `kits/unattended/templates/`.
- [ ] Add a fresh-install test to `tests/test_forge.py`: `init --kit todo --kit unattended`, then the doctor, then the kit's own tests in the installed copy. Done when: it passes and fails when a template file is removed from a scratch copy of the kit.
- [ ] Commit: `unattended: operator document and skill`

**Test checkpoint:** `python -m unittest discover -s tests -p test_forge.py` ends `OK`; naming a command in `docs/unattended-run.md` that the launcher lacks makes the document test fail.

## Verification

- In WSL, a scratch project with the todo and unattended kits and a stub agent is started with `python3 scripts/unattended-run.py start --ships 1`, its run session is killed and comes back on the next heartbeat tick, a stamped section ends the run, and `stop` leaves no process, marker, claim, guard or unit behind.
- On Windows, the generated shortcut starts that run through `wsl.exe`.
- `python -m unittest discover -s tests` passes.
- `python scripts/todo-graph.py validate` and `python scripts/todo-graph.py plan --check` pass.
