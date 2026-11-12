#!/usr/bin/env python3
"""Start, show, attach to and stop an unattended agent run held in tmux.

    python3 scripts/unattended-run.py start      take the launch lock, run the preflight, start (or resume) the run
    python3 scripts/unattended-run.py status     whether the run is live, its session, start, guard and health
    python3 scripts/unattended-run.py attach [--watch]   attach to the run's tmux session (--watch: read-only)
    python3 scripts/unattended-run.py stop       end the guard, the tmux sessions and the whole process group

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
MARKER_KEYS = ("session", "tmux_session", "heartbeat_session", "agent", "pgid", "started", "resumed")
GUARD = "build/claude-campaign-guard.json"
HEALTH = "build/unattended-health.json"  # written by the heartbeat (D02 T02 §8) when it runs
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
    if not isinstance(data, dict) or set(data) != set(MARKER_KEYS):
        return None, f"{MARKER} does not hold {', '.join(MARKER_KEYS)}"
    if not all(isinstance(data[k], str) and data[k] for k in ("session", "tmux_session", "heartbeat_session")):
        return None, f"{MARKER} names no session"
    if not isinstance(data["pgid"], int) or isinstance(data["pgid"], bool) or data["pgid"] <= 1:
        return None, f"{MARKER} holds no process group"
    return data, None


def agent_command(root: Path, profile: dict, session: str, resume: bool) -> list[str]:
    """The agent's command line, built from the profile. Claude Code: a fresh session with its own id, or
    `--resume <id>` with a short resume prompt; the options end with `--` because `--disallowedTools` takes a list
    that would otherwise swallow the prompt."""
    if profile["agent"] != "claude":
        raise RunError(f"agent {profile['agent']!r}: its launch command is added in D02 T02 §6; only claude starts")
    argv = ["claude", "--model", profile["model"], "--effort", profile["effort"]]
    argv += ["--resume", session] if resume else ["--session-id", session]
    argv += ["--disallowedTools", CLAUDE_DISALLOWED]
    if profile["skip_permissions"]:
        argv.append("--dangerously-skip-permissions")
    prompt = RESUME_PROMPT if resume else (root / profile["prompt_file"]).read_text(encoding="utf-8")
    return argv + ["--", prompt]


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
    deadline = time.monotonic() + max(grace, 2)
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
        tmux("new-window", "-d", "-t", f"={run_session}:", "-n", "agent", "-c", str(root), "-e", f"{INSIDE}=1",
             "-e", f"{TAG}={session}", "exec " + shlex.join(argv), check=True)
        target = f"={run_session}:agent"
        tmux("set-option", "-w", "-t", target, "remain-on-exit", "on", check=True)  # for the startup check only
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


def start(root: Path, out=None) -> int:
    out = out or sys.stdout
    profile = lib.load_profile(root)
    run_session, heartbeat = names(profile)
    with lib.launch_lock(root):
        marker, problem = read_marker(root)
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
        resume = marker["session"] if marker else None
        if marker:
            # The tmux session is gone, but that does not prove its processes are: a crashed run's leftovers are
            # ended before anything starts in its place.
            left = end_run_processes(marker["session"], marker["pgid"], grace=2)
            if left:
                raise RunError(f"the previous run's processes {left} are still running after SIGKILL")
        code, report = run_preflight(root, resume, profile)
        print(report, file=out)
        if code != 0:
            print("start: the preflight refused the run (FAIL lines above); nothing was started", file=out)
            return 1
        started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        session = pid = None
        if resume:
            try:
                pid = _launch(root, run_session, agent_command(root, profile, resume, resume=True), resume)
                session = resume
            except RunError as exc:
                print(f"start: the resume of session {resume} did not stay up ({exc}); starting a fresh session",
                      file=out)
                _end_old_guard(root, resume, out)
        if session is None:
            session = str(uuid.uuid4())
            pid = _launch(root, run_session, agent_command(root, profile, session, resume=False), session)
        marker = {"session": session, "tmux_session": run_session, "heartbeat_session": heartbeat,
                  "agent": profile["agent"], "pgid": pid, "started": started, "resumed": session == resume}
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
    return 0


def _end_old_guard(root: Path, session: str, out) -> None:
    """A fresh session cannot take the crashed session's guard, so the launcher ends it, as the operator would. If it
    cannot, nothing fresh starts: the marker still names the crashed session, which owns the guard."""
    guard = read_json(root / GUARD)
    if guard and str(guard.get("session_id")) == session:
        done = _end_guard(root, session)
        said = (done.stdout or done.stderr).strip()[-300:]
        if done.returncode != 0:
            raise RunError(f"the crashed session {session}'s guard could not be ended ({said}); nothing was started, "
                           f"and {MARKER} still names that session")
        print(f"start: the crashed session's guard ended: {said}", file=out)


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
        guard_failed = False
        if guard and session and str(guard.get("session_id")) == session:
            done = _end_guard(root, session)
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
    sub.add_parser("start")
    sub.add_parser("status")
    attach_parser = sub.add_parser("attach")
    attach_parser.add_argument("--watch", action="store_true", help="attach read-only")
    sub.add_parser("stop")
    args = parser.parse_args(argv)
    if os.name == "nt":
        print("unattended-run: the run lives in tmux, on Linux and in WSL: run this in WSL", file=sys.stderr)
        return 1
    root = Path(args.root).resolve()
    try:
        if args.command == "start":
            return start(root)
        if args.command == "status":
            return status(root)
        if args.command == "attach":
            return attach(root, args.watch)
        return stop(root)
    except (RunError, lib.ProfileError, lib.LaunchError) as exc:
        print(f"unattended-run: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
