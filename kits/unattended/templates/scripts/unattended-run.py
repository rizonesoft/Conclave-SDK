#!/usr/bin/env python3
"""Start, show, attach to and stop an unattended agent run held in tmux.

    python3 scripts/unattended-run.py start [--no-heartbeat]   take the launch lock, run the preflight, start (or
                                                 resume) the run, and its heartbeat unless --no-heartbeat
    python3 scripts/unattended-run.py status     whether the run is live, its session, start, guard and health
    python3 scripts/unattended-run.py attach [--watch]   attach to the run's tmux session (--watch: read-only)
    python3 scripts/unattended-run.py stop       end the guard, the tmux sessions and the whole process group
    python3 scripts/unattended-run.py heartbeat [--once]   restart a dead run, nudge an idle one (start runs it)

The run lives in the detached tmux session `<name>-run` (the profile's `name`), so it outlives the terminal that
started it. `build/unattended-run.json` (the run marker) names the run: its agent session, its tmux sessions and its
process group. A `start` that finds the marker but no running session resumes that agent session, and starts a fresh
one when the resume does not stay up. `status` and `stop` follow the marker, so a profile changed during a run cannot
strand it. Linux and WSL only (tmux). Standard library only.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import shlex
import signal
import subprocess
import sys
import time
import uuid

HERE = Path(__file__).resolve().parent
# Loading the kit's own modules must not write __pycache__ into the project: that dirties the tree the preflight
# checks, and a launch would refuse itself.
sys.dont_write_bytecode = True
MARKER = "build/unattended-run.json"
# `session` is the run's tag (CONCLAVE_UNATTENDED_TAG, the claim's session, and Claude Code's own --session-id);
# `agent_session` is the agent's own session id: the tag for Claude Code, and for Codex and Antigravity, which choose
# their own, the id the run's guard records (None until then).
MARKER_KEYS = ("session", "agent_session", "tmux_session", "heartbeat_session", "agent", "pgid", "started", "resumed")
GUARD = "build/claude-campaign-guard.json"
HEALTH = "build/unattended-health.json"  # written by the heartbeat (D02 T02 §8) when it runs
HEARTBEAT_STATE = "build/unattended-heartbeat.json"
ENDED = "build/claude-campaign-ended.json"  # written by campaign_guard.py end: how the last run ended
FINISHED = 10  # the heartbeat's exit status when the run is over (stopped, or ended by its own agent)
MAX_WAIT_SECONDS = 3600
RESET_SECONDS = 3600  # a run alive this long after its last restart has its death count reset
NUDGE_PROMPT = ("The unattended run looks idle. Continue with process-plan: pick up the open section in the run file "
                "and keep going. Never ask the operator a question.")
HISTORY_LIMIT = 50000
INSIDE = "CONCLAVE_UNATTENDED_RUN"  # set inside the run, so a run cannot stop itself
# Every process of a run carries this in its environment (inherited even by one that starts its own session, such as
# a reviewer the dispatcher detaches), so a stop or a resume finds and ends the whole run, not only its group.
TAG = "CONCLAVE_UNATTENDED_TAG"
# The preflight's own checks (git, the guard self-test, Codex trust), on top of the profile's checks' own timeouts.
PREFLIGHT_SLACK_SECONDS = 900
STOP_GRACE_SECONDS = 10
# How long a started or resumed agent must stay up to count as started.
STARTUP_SECONDS = float(os.environ.get("CONCLAVE_STARTUP_GRACE") or 10)
CLAUDE_DISALLOWED = "AskUserQuestion,EnterPlanMode,ExitPlanMode"
RESUME_PROMPT = ("Resume the unattended run where it stopped: run process-plan, pick up the open section in the run "
                 "file, and keep going. Never ask the operator a question.")


class RunError(RuntimeError):
    """A launcher step that cannot go ahead, said in one line."""


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


lib = _load("unattended_lib", HERE / "lib" / "unattended.py")


def tmux(*args: str, check: bool = False) -> subprocess.CompletedProcess:
    try:
        done = subprocess.run(["tmux", *args], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        if check:
            raise RunError(f"tmux {args[0]} could not run: {exc}") from None
        return subprocess.CompletedProcess(["tmux", *args], -1, stdout="", stderr=str(exc))
    if check and done.returncode != 0:
        raise RunError(f"tmux {args[0]} failed: {(done.stderr or done.stdout).strip()[-300:]}")
    return done


def names(profile: dict) -> tuple[str, str]:
    """The run's tmux session and the heartbeat's (D02 T02 §7), from the profile."""
    return f"{profile['name']}-run", f"{profile['name']}-heartbeat"


def read_json(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def read_marker(root: Path) -> tuple[dict | None, str | None]:
    """(marker, problem): the run marker checked against its schema; no marker is (None, None), and one that cannot
    be read or does not hold the schema is (None, why)."""
    path = root / MARKER
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, None
    except (OSError, ValueError) as exc:
        return None, f"{MARKER} cannot be read ({exc})"
    if isinstance(data, dict) and set(data) == set(MARKER_KEYS) - {"agent_session"}:
        # A marker written before D02 T02 §6, when the tag was Claude Code's session and the only agent was Claude.
        data = {**data, "agent_session": data.get("session") if data.get("agent") == "claude" else None}
    if not isinstance(data, dict) or set(data) != set(MARKER_KEYS):
        return None, f"{MARKER} does not hold {', '.join(MARKER_KEYS)}"
    if not all(isinstance(data[k], str) and data[k] for k in ("session", "tmux_session", "heartbeat_session")):
        return None, f"{MARKER} names no session"
    if not isinstance(data["pgid"], int) or isinstance(data["pgid"], bool) or data["pgid"] <= 1:
        return None, f"{MARKER} holds no process group"
    if data["agent_session"] is not None and not (isinstance(data["agent_session"], str) and data["agent_session"]):
        return None, f"{MARKER} holds an agent session that is not a session id"
    return data, None


def owned_guard(root: Path, marker: dict | None) -> dict | None:
    """The guard when it is this run's: it carries the run's tag, or names the run's agent session."""
    guard = read_json(root / GUARD)
    if not guard or not marker:
        return None
    if guard.get("launch_tag") == marker["session"]:
        return guard
    if marker.get("agent_session") and str(guard.get("session_id")) == marker["agent_session"]:
        return guard
    return None


def agent_command(root: Path, profile: dict, tag: str, resume_id: str | None) -> list[str]:
    """The agent's command line, built from the profile and the flags each installed CLI's own help confirms
    (kits/unattended/README.md). A fresh start gets the seed prompt; a resume (`resume_id`, the agent's own session)
    gets a short resume prompt."""
    agent, model, effort, skip = profile["agent"], profile["model"], profile["effort"], profile["skip_permissions"]
    prompt = RESUME_PROMPT if resume_id else (root / profile["prompt_file"]).read_text(encoding="utf-8")
    if agent == "claude":
        # --disallowedTools takes a list, which would swallow the prompt: the options end with `--`.
        argv = ["claude", "--model", model, "--effort", effort]
        argv += ["--resume", resume_id] if resume_id else ["--session-id", tag]
        argv += ["--disallowedTools", CLAUDE_DISALLOWED]
        if skip:
            argv.append("--dangerously-skip-permissions")
        return argv + ["--", prompt]
    if agent == "codex":
        # Codex has no --effort: -c overrides config.toml's model_reasoning_effort (a TOML string). It chooses its own
        # session id, so a fresh start names none; `codex resume [SESSION_ID] [PROMPT]` continues one.
        options = ["-m", model, "-c", f'model_reasoning_effort="{effort}"']
        if skip:
            options.append("--dangerously-bypass-approvals-and-sandbox")
        if resume_id:
            return ["codex", "resume", *options, "--", resume_id, prompt]
        return ["codex", *options, "--", prompt]
    if agent == "agy":
        # Antigravity's flags take `--name=value`; --prompt-interactive runs the prompt and keeps the session open.
        argv = ["agy", f"--model={model}", f"--effort={effort}"]
        if resume_id:
            argv.append(f"--conversation={resume_id}")
        if skip:
            argv.append("--dangerously-skip-permissions")
        return argv + [f"--prompt-interactive={prompt}"]
    raise RunError(f"agent {agent!r} has no launch command")


def run_preflight(root: Path, resume_session: str | None, profile: dict) -> tuple[int, str]:
    """Run the preflight in its own process group, given as long as its profile checks may take plus its own checks,
    and end the whole group when it overruns or the launcher is interrupted."""
    args = [sys.executable, str(HERE / "unattended-preflight.py"), "--root", str(root)]
    if resume_session:
        args += ["--resume-session", resume_session]
    limit = PREFLIGHT_SLACK_SECONDS + sum(check["timeout_seconds"] for check in profile["preflight"])
    # Its profile checks run in sessions of their own, outside its group: the tag reaches them all.
    tag = f"preflight-{uuid.uuid4()}"
    proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            start_new_session=True, env={**os.environ, TAG: tag})
    try:
        report, _ = proc.communicate(timeout=limit)
    except subprocess.TimeoutExpired:
        end_run_processes(tag, proc.pid, grace=0)
        report, _ = proc.communicate()
        return 1, (report or "").rstrip() + f"\nFAIL preflight: ran past {limit}s; it and its checks were ended"
    except BaseException:
        end_run_processes(tag, proc.pid, grace=0)
        proc.communicate()
        raise
    return proc.returncode, (report or "").rstrip()


def _alive(name: str) -> bool | None:
    return lib.tmux_session_exists(name)


def _group_alive(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _end_group(pgid: int | None, grace: float = STOP_GRACE_SECONDS) -> bool:
    """Wait up to `grace` for process group `pgid` to end, then SIGKILL it; True once it is gone."""
    if not isinstance(pgid, int) or pgid <= 1:
        return True
    deadline = time.monotonic() + grace
    while _group_alive(pgid) and time.monotonic() < deadline:
        time.sleep(0.2)
    if _group_alive(pgid):
        try:
            os.killpg(pgid, signal.SIGKILL)
        except ProcessLookupError:
            return True  # it ended at the last moment
        deadline = time.monotonic() + grace
        while _group_alive(pgid) and time.monotonic() < deadline:
            time.sleep(0.2)
    return not _group_alive(pgid)


def tagged(session: str) -> list[int]:
    """The processes whose environment carries this run's tag, read from /proc (empty where /proc cannot say)."""
    needle = f"{TAG}={session}".encode()
    found = []
    try:
        entries = os.listdir("/proc")
    except OSError:
        return found
    for entry in entries:
        if not entry.isdigit() or int(entry) == os.getpid():
            continue
        try:
            with open(f"/proc/{entry}/environ", "rb") as handle:
                if needle in handle.read().split(b"\0"):
                    found.append(int(entry))
        except OSError:
            continue  # it ended while being read, or is not this user's
    return found


def end_run_processes(session: str, pgid: int | None, grace: float = STOP_GRACE_SECONDS) -> list[int]:
    """End the run's process group and every process tagged with its session: wait up to `grace` for them to go
    (tmux has already sent its hangup), then SIGKILL what is left. Returns the pids still alive afterwards."""
    deadline = time.monotonic() + grace
    while (tagged(session) or (pgid and _group_alive(pgid))) and time.monotonic() < deadline:
        time.sleep(0.2)
    if pgid and _group_alive(pgid):
        try:
            os.killpg(pgid, signal.SIGKILL)
        except ProcessLookupError:
            pass  # the group ended at the last moment
    for pid in tagged(session):
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass  # it ended at the last moment
    # SIGKILL lands only once a process leaves uninterruptible I/O (slow under load, as on WSL's /mnt), so the wait
    # after it is the full stop grace whatever the polite wait was.
    deadline = time.monotonic() + max(grace, STOP_GRACE_SECONDS)
    while (left := tagged(session)) and time.monotonic() < deadline:
        time.sleep(0.2)
    return tagged(session) + ([pgid] if pgid and _group_alive(pgid) else [])


def _launch(root: Path, run_session: str, argv: list[str], session: str) -> int:
    """Start `argv` as the only window of the detached tmux session `run_session`, with a 50,000-line history (tmux
    applies history-limit to new windows only, so a placeholder window is replaced), inside the repository and with
    the inside-the-run variable set, and see that it stays up for the startup check. Returns the agent's pid, which
    leads its own process group. On any failure the session and the group are ended and RunError says why."""
    tmux("new-session", "-d", "-s", run_session, "-n", "boot", "-c", str(root), "sleep 30", check=True)
    pid = None
    try:
        # A session target ending in ":" (the exact name, then its current window): set-option and new-window
        # resolve -t through a pane, and a bare "=name" names no pane in tmux 3.6.
        tmux("set-option", "-t", f"={run_session}:", "history-limit", str(HISTORY_LIMIT), check=True)
        # The agent's window opens on a placeholder, keeps its pane on exit, and only then is the agent respawned into
        # it: an agent that exits at once is still there to read, not a window that vanished before the option was set.
        tmux("new-window", "-d", "-t", f"={run_session}:", "-n", "agent", "-c", str(root), "sleep 30", check=True)
        target = f"={run_session}:agent"
        tmux("set-option", "-w", "-t", target, "remain-on-exit", "on", check=True)  # for the startup check only
        tmux("respawn-pane", "-k", "-t", target, "-c", str(root), "-e", f"{INSIDE}=1", "-e", f"{TAG}={session}",
             "exec " + shlex.join(argv), check=True)
        tmux("kill-window", "-t", f"={run_session}:boot", check=True)
        pid = int(tmux("display-message", "-p", "-t", target, "#{pane_pid}", check=True).stdout.strip())
        deadline = time.monotonic() + STARTUP_SECONDS
        while time.monotonic() < deadline:
            dead = tmux("display-message", "-p", "-t", target, "#{pane_dead} #{pane_dead_status}").stdout.split()
            if dead and dead[0] == "1":
                # The agent's own last words, from the pane's history (a dead pane's screen holds only tmux's own
                # `Pane is dead (...)` line, which is left out).
                history = tmux("capture-pane", "-p", "-J", "-S", "-200", "-t", target).stdout
                shown = [line for line in history.strip().splitlines()
                         if line.strip() and not line.startswith("Pane is dead")]
                last = shown[-1][-200:] if shown else "no output"
                raise RunError(f"the agent exited {dead[1] if len(dead) > 1 else '?'} within "
                               f"{STARTUP_SECONDS:g}s of starting: {last}")
            time.sleep(0.2)
        tmux("set-option", "-w", "-t", target, "remain-on-exit", "off", check=True)
        return pid
    except BaseException:
        tmux("kill-session", "-t", f"={run_session}")
        end_run_processes(session, pid, grace=2)
        raise


def start(root: Path, out=None, expect: str | None = None, supervise: bool = True) -> int:
    """Start or resume the run. `expect` (the heartbeat's restart) names the run it means: under the launch lock the
    marker must still name it, or nothing starts and FINISHED is returned, so a stop during a restart's backoff never
    resurrects the run. `supervise` launches the heartbeat in its own tmux session when it is not running."""
    out = out or sys.stdout
    profile = lib.load_profile(root)
    run_session, heartbeat = names(profile)
    with lib.launch_lock(root):
        marker, problem = read_marker(root)
        if expect is not None and (marker is None or marker["session"] != expect):
            print(f"start: run {expect} was stopped or replaced; nothing restarted", file=out)
            return FINISHED
        if problem:
            raise RunError(f"{problem}: stop the run (or remove {MARKER}) before starting another")
        if marker:
            run_session, heartbeat = marker["tmux_session"], marker["heartbeat_session"]
        live = _alive(run_session)
        if live is None:
            raise RunError(f"whether tmux session {run_session} is running cannot be told: tmux could not be asked")
        if live:
            raise RunError(f"tmux session {run_session} is already running: attach with "
                           "'python3 scripts/unattended-run.py attach', or stop it first")
        old = marker
        if marker:
            # The tmux session is gone, but that does not prove its processes are: a crashed run's leftovers are
            # ended before anything starts in its place.
            left = end_run_processes(marker["session"], marker["pgid"], grace=2)
            if left:
                raise RunError(f"the previous run's processes {left} are still running after SIGKILL")
        # The agent session to resume: Claude Code's is the tag; Codex's and Antigravity's is what the run's guard
        # records, and without one (the agent died before it took the guard) the run starts fresh.
        guard = owned_guard(root, old)
        resume = (old["agent_session"] or (str(guard["session_id"]) if guard else None)) if old else None
        if old and old["agent"] != profile["agent"]:
            # The profile now names another agent: a session of one cannot be resumed by the other.
            print(f"start: the crashed run was {old['agent']}, the profile now names {profile['agent']}; its "
                  f"session is not resumed, and a fresh {profile['agent']} session starts", file=out)
            resume = None
        code, report = run_preflight(root, old["session"] if old else None, profile)
        print(report, file=out)
        if code != 0:
            print("start: the preflight refused the run (FAIL lines above); nothing was started", file=out)
            return 1
        started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        session = agent_session = pid = None
        if old and not resume:
            _end_old_guard(root, old, out)  # nothing to resume: the crashed run's guard is ended before a fresh start
        if resume:
            try:
                pid = _launch(root, run_session, agent_command(root, profile, old["session"], resume), old["session"])
                session, agent_session = old["session"], resume
            except RunError as exc:
                print(f"start: the resume of session {resume} did not stay up ({exc}); starting a fresh session",
                      file=out)
                _end_old_guard(root, old, out)
        if session is None:
            session = str(uuid.uuid4())
            agent_session = session if profile["agent"] == "claude" else None
            pid = _launch(root, run_session, agent_command(root, profile, session, None), session)
        marker = {"session": session, "agent_session": agent_session, "tmux_session": run_session,
                  "heartbeat_session": heartbeat, "agent": profile["agent"], "pgid": pid, "started": started,
                  "resumed": session == (old["session"] if old else None)}
        try:
            lib.write_atomic(root / MARKER, json.dumps(marker, indent=2) + "\n")
            lib.write_claim(root, session, pid, profile["agent"], run_session, started=started)
            if read_marker(root)[0] != marker:
                raise OSError(f"{MARKER} did not read back as written")
        except OSError as exc:
            tmux("kill-session", "-t", f"={run_session}")
            end_run_processes(session, pid, grace=2)
            (root / MARKER).unlink(missing_ok=True)
            lib.clear_claim(root, session, lock_held=True)
            raise RunError(f"the run's state could not be written ({exc}); the run was ended") from None
    print(f"start: {'resumed' if marker['resumed'] else 'started'} session {session} in tmux session "
          f"{run_session} (attach: python3 scripts/unattended-run.py attach)", file=out)
    if supervise:
        _launch_heartbeat(root, heartbeat, out)
    return 0


def _launch_heartbeat(root: Path, heartbeat: str, out) -> None:
    """The heartbeat runs in its own detached tmux session, one per run: a second start leaves a live one alone."""
    if _alive(heartbeat) is not False:
        return
    command = shlex.join([sys.executable, str(HERE / "unattended-run.py"), "--root", str(root), "heartbeat"])
    tmux("new-session", "-d", "-s", heartbeat, "-c", str(root), "exec " + command, check=True)
    print(f"start: heartbeat running in tmux session {heartbeat}", file=out)


def read_state(root: Path) -> dict:
    state = read_json(root / HEARTBEAT_STATE) or {}
    return {"deaths": state.get("deaths", 0) if isinstance(state.get("deaths"), int) else 0,
            **{key: state.get(key) for key in ("wait_until", "last_restart", "last_nudge", "last_error")}}


def run_finished(root: Path, marker: dict) -> bool:
    """Whether the run's own agent ended it: the guard's end record names the run's tag or its agent session. A
    guard that is merely absent proves nothing (the agent may not have taken it yet)."""
    ended = read_json(root / ENDED)
    if not ended:
        return False
    return ended.get("launch_tag") == marker["session"] or bool(
        marker.get("agent_session") and ended.get("session_id") == marker["agent_session"])


def backoff(profile: dict, deaths: int) -> int:
    return min(profile["tick_seconds"] * 2 ** min(deaths, 5), MAX_WAIT_SECONDS)


def _nudge(root: Path, run_session: str, profile: dict, state: dict, now: float, out) -> None:
    """Prompt a run whose window has shown nothing for idle_minutes, at most once per idle_minutes, unless an
    operator is attached with a client that can type (a read-only watcher does not count)."""
    idle = profile["idle_minutes"] * 60
    target = f"={run_session}:agent"
    shown = tmux("display-message", "-p", "-t", target, "#{window_activity}").stdout.strip()
    if not shown.isdigit() or now - int(shown) < idle:
        return
    if state.get("last_nudge") and now - state["last_nudge"] < idle:
        return
    clients = tmux("list-clients", "-t", f"={run_session}", "-F", "#{client_readonly}").stdout.split()
    if "0" in clients:
        return  # an operator is attached and may be typing
    tmux("send-keys", "-t", target, "-l", NUDGE_PROMPT)
    tmux("send-keys", "-t", target, "Enter")
    state["last_nudge"] = now
    print(f"heartbeat: nudged {run_session} after {int(now - int(shown))}s without activity", file=out)
    note_resumption(root, out)


def note_resumption(root: Path, out) -> None:
    """A nudge is a heartbeat resumption: the guard's stall breaker counts it (`heartbeat-still`), and ends the run
    as a stall after enough of them with no change to the tree (process-plan's heartbeat contract)."""
    marker, _ = read_marker(root)
    guard = owned_guard(root, marker)
    if not guard:
        return
    done = subprocess.run([sys.executable, str(HERE / "campaign_guard.py"), "heartbeat-still", "--session",
                           str(guard.get("session_id")), "--root", str(root)], capture_output=True, text=True,
                          timeout=120)
    said = (done.stdout or done.stderr).strip().splitlines()
    print(f"heartbeat: {said[-1][-200:] if said else f'heartbeat-still exited {done.returncode}'}", file=out)


def finish(root: Path, marker: dict, out) -> int:
    """The run is over: its marker and its own claim go, so neither start nor a boot resume revives it."""
    with lib.launch_lock(root):
        (root / MARKER).unlink(missing_ok=True)
        lib.clear_claim(root, marker["session"], lock_held=True)
    print(f"heartbeat: run {marker['session']} ended itself; the heartbeat stops", file=out)
    return FINISHED


def tick(root: Path, now: float, state: dict, out=None, restart=None) -> int:
    """One heartbeat tick: FINISHED when the run is over, 0 otherwise. `state` is updated in place."""
    out = out or sys.stdout
    profile = lib.load_profile(root)
    marker, problem = read_marker(root)
    if marker is None:
        print(f"heartbeat: {problem or 'no run marker'}; the heartbeat stops", file=out)
        return FINISHED
    if run_finished(root, marker):
        return finish(root, marker, out)
    live = _alive(marker["tmux_session"])
    if live is None:
        state["last_error"] = "tmux could not be asked whether the run is alive"
        return 0
    if live:
        if state["deaths"] and state.get("last_restart") and now - state["last_restart"] >= RESET_SECONDS:
            state["deaths"] = 0
        state["wait_until"] = None
        _nudge(root, marker["tmux_session"], profile, state, now, out)
        return 0
    if state.get("wait_until") is None:
        state["wait_until"] = now + backoff(profile, state["deaths"])
        print(f"heartbeat: run {marker['session']} is not running; restart in "
              f"{int(state['wait_until'] - now)}s", file=out)
        return 0
    if now < state["wait_until"]:
        return 0
    try:
        code = (restart or (lambda: start(root, out, expect=marker["session"], supervise=False)))()
        error = None if code == 0 else f"start exited {code}"
    except (RunError, lib.ProfileError, lib.LaunchError, OSError, subprocess.SubprocessError) as exc:
        code, error = 1, f"{type(exc).__name__}: {exc}"
    if code == FINISHED:
        return FINISHED
    state["deaths"] += 1
    state["last_error"] = error
    if error:
        state["wait_until"] = now + backoff(profile, state["deaths"])
        print(f"heartbeat: restart failed ({error}); next try in {int(state['wait_until'] - now)}s", file=out)
    else:
        state["last_restart"], state["wait_until"] = now, None
    return 0


def heartbeat(root: Path, once: bool = False, clock=time.time, sleep=time.sleep, out=None) -> int:
    """Tick every tick_seconds until the run is over. The state is read back from its file on every tick, so a
    heartbeat started again carries on; it writes that file and nothing else."""
    unsaved = None  # the state a failed write could not keep, carried in memory until a write succeeds
    while True:
        state = unsaved or read_state(root)
        code = tick(root, clock(), state, out)
        try:
            lib.write_atomic(root / HEARTBEAT_STATE, json.dumps(state, indent=2) + "\n")
            unsaved = None
        except OSError as exc:  # a full or failing disk must not end the supervision of the run
            unsaved = state
            print(f"heartbeat: {HEARTBEAT_STATE} could not be written ({exc.strerror or exc}); kept in memory",
                  file=out or sys.stdout)
        if code == FINISHED or once:
            return code
        sleep(lib.load_profile(root)["tick_seconds"])


def _end_old_guard(root: Path, old: dict, out) -> None:
    """A fresh session cannot take the crashed run's guard, so the launcher ends it, as the operator would, with the
    guard's own session id. If it cannot, nothing fresh starts: the marker still names the crashed run."""
    guard = owned_guard(root, old)
    if guard:
        owner = str(guard.get("session_id"))
        done = _end_guard(root, owner)
        said = (done.stdout or done.stderr).strip()[-300:]
        if done.returncode != 0:
            raise RunError(f"the crashed run's guard (session {owner}) could not be ended ({said}); nothing was "
                           f"started, and {MARKER} still names that run")
        # The guard's end record says how a run's own agent ended it; this end is the launcher's, so its record goes,
        # or a heartbeat would read a recovery that failed as a run that finished.
        ended = read_json(root / ENDED)
        if ended and ended.get("run_id") == guard.get("run_id") and ended.get("reason") == "operator-stop":
            (root / ENDED).unlink(missing_ok=True)
        print(f"start: the crashed run's guard ended: {said}", file=out)


def _end_guard(root: Path, session: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(HERE / "campaign_guard.py"), "end", "--session", session,
                           "--reason", "operator-stop", "--root", str(root)],
                          capture_output=True, text=True, timeout=120)


def status(root: Path, out=None) -> int:
    out = out or sys.stdout
    profile = lib.load_profile(root)
    marker, problem = read_marker(root)
    run_session, heartbeat = (marker["tmux_session"], marker["heartbeat_session"]) if marker else names(profile)

    def state(name):
        live = _alive(name)
        return "unknown (tmux could not be asked)" if live is None else "live" if live else "stopped"
    print(f"run: {state(run_session)} (tmux session {run_session})", file=out)
    print(f"marker: {problem}" if problem else f"marker: {'present' if marker else 'none'}", file=out)
    print(f"session: {marker['session'] if marker else 'none'}", file=out)
    print(f"started: {marker['started'] if marker else 'never'}", file=out)
    print(f"heartbeat: {state(heartbeat)} (tmux session {heartbeat})", file=out)
    guard = read_json(root / GUARD)
    print(f"guard: phase {guard.get('phase')}, run {guard.get('run_id')}, session {guard.get('session_id')}"
          if guard else "guard: none", file=out)
    beat = read_json(root / HEARTBEAT_STATE)
    print(f"heartbeat state: {json.dumps(beat, sort_keys=True)}" if beat else "heartbeat state: none", file=out)
    health = read_json(root / HEALTH)
    print(f"health: {json.dumps(health, sort_keys=True)}" if health else "health: none", file=out)
    return 0


def attach_command(run_session: str, watch: bool) -> list[str]:
    return ["tmux", "attach-session", *(["-r"] if watch else []), "-t", f"={run_session}"]


def attach(root: Path, watch: bool) -> int:
    marker, _ = read_marker(root)
    run_session = marker["tmux_session"] if marker else names(lib.load_profile(root))[0]
    if _alive(run_session) is not True:
        raise RunError(f"tmux session {run_session} is not running")
    argv = attach_command(run_session, watch)
    os.execvp(argv[0], argv)
    return 0  # not reached: the launcher becomes the tmux client


def stop(root: Path, out=None) -> int:
    out = out or sys.stdout
    if os.environ.get(INSIDE) == "1":
        print(f"stop: refused inside the run ({INSIDE}=1): a run does not stop itself; stop it from a terminal",
              file=out)
        return 2
    profile = lib.load_profile(root)
    with lib.launch_lock(root):
        marker, problem = read_marker(root)
        if problem:
            print(f"stop: {problem}; stopping the profile's sessions", file=out)
        run_session, heartbeat = (marker["tmux_session"], marker["heartbeat_session"]) if marker else names(profile)
        session = marker["session"] if marker else None
        guard = read_json(root / GUARD)
        mine = owned_guard(root, marker)
        guard_failed = False
        if mine:
            done = _end_guard(root, str(mine.get("session_id")))
            guard_failed = done.returncode != 0
            print(f"stop: guard {'not ended' if guard_failed else 'ended'}: "
                  f"{(done.stdout or done.stderr).strip()[-300:]}", file=out)
        elif guard:
            print(f"stop: the guard belongs to session {guard.get('session_id')}, not this run's; left in place",
                  file=out)
        for name in (heartbeat, run_session):
            tmux("kill-session", "-t", f"={name}")
        left = end_run_processes(session, marker["pgid"]) if marker else []
        if left:
            print(f"stop: processes {left} are still running after SIGKILL; {MARKER} and the claim are kept",
                  file=out)
            return 1
        if guard_failed:
            print(f"stop: the run's guard was not ended; {MARKER} and the claim are kept, so a second stop can "
                  "end it", file=out)
            return 1
        if session:
            print(f"stop: claim {lib.clear_claim(root, session, lock_held=True)}", file=out)
        (root / MARKER).unlink(missing_ok=True)
    print(f"stop: run {session or 'with no marker'} stopped", file=out)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Start, show, attach to and stop an unattended agent run.")
    parser.add_argument("--root", default=str(HERE.parent), help="the repository (default: this script's)")
    sub = parser.add_subparsers(dest="command", required=True)
    start_parser = sub.add_parser("start")
    start_parser.add_argument("--no-heartbeat", action="store_true", help="start the run without its heartbeat")
    sub.add_parser("status")
    attach_parser = sub.add_parser("attach")
    attach_parser.add_argument("--watch", action="store_true", help="attach read-only")
    sub.add_parser("stop")
    beat_parser = sub.add_parser("heartbeat")
    beat_parser.add_argument("--once", action="store_true", help="one tick, then exit")
    args = parser.parse_args(argv)
    if os.name == "nt":
        print("unattended-run: the run lives in tmux, on Linux and in WSL: run this in WSL", file=sys.stderr)
        return 1
    root = Path(args.root).resolve()
    try:
        if args.command == "start":
            return start(root, supervise=not args.no_heartbeat)
        if args.command == "status":
            return status(root)
        if args.command == "attach":
            return attach(root, args.watch)
        if args.command == "heartbeat":
            return heartbeat(root, once=args.once)
        return stop(root)
    except (RunError, lib.ProfileError, lib.LaunchError) as exc:
        print(f"unattended-run: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
