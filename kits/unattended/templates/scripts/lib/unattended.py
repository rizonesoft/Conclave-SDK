"""Shared code of the unattended kit: the run profile loader, and the launch lock and claim; the ship counter comes
with D02 T02 §7.

The preflight (`scripts/unattended-preflight.py`) imports it, and the launcher (`scripts/unattended-run.py`, §5)
will.
It holds no project name: the project's own settings live in `.conclave/unattended.json` (the run profile).
"""
from __future__ import annotations

import contextlib
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

SCHEMA_VERSION = 1
PROFILE = ".conclave/unattended.json"
AGENTS = ("claude", "codex", "agy")
# Each agent's own effort values (Claude Code `--effort`, Codex `model_reasoning_effort`). Antigravity has no effort
# flag the launcher passes, so any non-empty string is kept for it as a note.
EFFORTS = {"claude": ("low", "medium", "high", "xhigh", "max"), "codex": ("minimal", "low", "medium", "high", "xhigh"),
           "agy": None}
NAME = re.compile(r"[a-z0-9][a-z0-9-]{1,40}")
WHOLE = ("min_disk_gb", "min_ram_gb", "tick_seconds", "idle_minutes", "stall_hours")
KEYS = {"schema_version", "name", "agent", "model", "effort", "prompt_file", "branch", "skip_permissions", "tools",
        "preflight", *WHOLE}
MUST_SET = ("name", "model", "effort")


class ProfileError(ValueError):
    """A run profile the launcher cannot run, named with the file and the key."""


def load_profile(root) -> dict:
    """The run profile, every key checked: a fault names `.conclave/unattended.json` and the key, never a default."""
    root = Path(root)
    path = root / PROFILE

    def fault(key: str, what: str) -> ProfileError:
        return ProfileError(f"{PROFILE}: {key}: {what}")

    try:
        data = json.loads(path.read_bytes().decode("utf-8"))
    except FileNotFoundError:
        raise ProfileError(f"{PROFILE}: missing; install the unattended kit or write the run profile") from None
    except (OSError, ValueError, RecursionError) as exc:
        raise ProfileError(f"{PROFILE}: not readable as UTF-8 JSON ({exc})") from None
    if not isinstance(data, dict):
        raise ProfileError(f"{PROFILE}: the profile must be a JSON object")
    unknown = sorted(set(data) - KEYS)
    if unknown:
        raise fault(unknown[0], "is not a run profile key")
    missing = sorted(KEYS - set(data))
    if missing:
        raise fault(missing[0], "is required")
    if data["schema_version"] != SCHEMA_VERSION or isinstance(data["schema_version"], bool):
        raise fault("schema_version", f"must be {SCHEMA_VERSION}")
    unset = [key for key in MUST_SET if data[key] is None]
    if unset:
        raise fault(unset[0], f"is null in the template; set {', '.join(unset)} for this project")
    # A NUL cannot reach a program's arguments or a file name: refuse it here, not as a ValueError at launch.
    for key in ("model", "effort", "branch", "prompt_file"):
        if isinstance(data[key], str) and "\0" in data[key]:
            raise fault(key, "must not contain a NUL character")
    if not isinstance(data["name"], str) or not NAME.fullmatch(data["name"]):
        raise fault("name", "must match [a-z0-9][a-z0-9-]{1,40}")
    if data["agent"] not in AGENTS:
        raise fault("agent", f"must be one of {', '.join(AGENTS)}")
    for key in ("model", "effort", "branch"):
        if not isinstance(data[key], str) or not data[key].strip():
            raise fault(key, "must be a non-empty string")
    efforts = EFFORTS[data["agent"]]
    if efforts is not None and data["effort"] not in efforts:
        raise fault("effort", f"must be one of {', '.join(efforts)} for {data['agent']}")
    if not isinstance(data["skip_permissions"], bool):
        raise fault("skip_permissions", "must be true or false")
    for key in WHOLE:
        value = data[key]
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise fault(key, "must be a whole number above 0")
    tools = data["tools"]
    if not isinstance(tools, list) or not all(isinstance(t, str) and t and "\0" not in t for t in tools):
        raise fault("tools", "must be a list of command names")
    prompt = data["prompt_file"]
    parts = prompt.replace("\\", "/").split("/") if isinstance(prompt, str) else []
    if (not isinstance(prompt, str) or not prompt or os.path.isabs(prompt) or prompt.startswith(("/", "\\"))
            or re.match(r"^[A-Za-z]:", prompt) or ".." in parts):
        raise fault("prompt_file", "must be a path inside the repository")
    target = (root / prompt).resolve()
    if not target.is_relative_to(root.resolve()):
        raise fault("prompt_file", f"{prompt} leads outside the repository")
    if not target.is_file():
        raise fault("prompt_file", f"{prompt} does not exist or is not a file")
    try:
        target.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise fault("prompt_file", f"{prompt} is not readable as UTF-8 ({exc})") from None
    if not isinstance(data["preflight"], list):
        raise fault("preflight", "must be a list of checks")
    for index, check in enumerate(data["preflight"]):
        where = f"preflight[{index}]"
        if not isinstance(check, dict) or set(check) != {"name", "command", "timeout_seconds"}:
            raise fault(where, "needs exactly name, command and timeout_seconds")
        if not isinstance(check["name"], str) or not check["name"]:
            raise fault(f"{where}.name", "must be a non-empty string")
        command = check["command"]
        if (not isinstance(command, list) or not command or not all(isinstance(c, str) for c in command)
                or not command[0].strip() or any("\0" in c for c in command)):
            raise fault(f"{where}.command", "must be a list of strings that starts with a program")
        timeout = check["timeout_seconds"]
        if isinstance(timeout, bool) or not isinstance(timeout, int) or timeout <= 0:
            raise fault(f"{where}.timeout_seconds", "must be a whole number above 0")
    return data


# The launch lock and claim (D02 T02 §4). Two launches at once would start two agents on one tree: the lock is held
# for the launch, and the claim names the run it started, so a later launch can tell a live run from a dead one.
LAUNCH_LOCK = "build/unattended-launch.lock"
CLAIM = "build/unattended-launch.json"
CLAIM_KEYS = ("session", "tmux_session", "pid", "agent", "started")
# What tmux says when it can confirm a session does not exist; anything else it says is a lookup that failed.
TMUX_ABSENT = ("can't find session", "no server running", "session not found")


class LaunchError(RuntimeError):
    """A launch or clear this run must not make, named with the file that says why."""


@contextlib.contextmanager
def launch_lock(root):
    """Hold `build/unattended-launch.lock` exclusively for the launch, without waiting: a second launch while the
    first holds it is refused naming the lock. The kernel releases it when the launcher exits, however it exits."""
    import fcntl  # POSIX only: the unattended run lives in tmux, on Linux and in WSL

    path = Path(root) / LAUNCH_LOCK
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(path, "a+b")
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise LaunchError(f"{LAUNCH_LOCK} is held: another launch is under way") from None
        yield path
    finally:
        handle.close()


def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass  # the replace already moved it
        raise


def write_claim(root, session: str, pid: int, agent: str, tmux_session: str, started: str | None = None) -> dict:
    """Write `build/unattended-launch.json` naming the run this launch started (the agent's session id, the tmux
    session, which is the profile's `name`, the pid, the agent and the UTC start), through a temporary file and
    os.replace, and return it."""
    claim = {"session": session, "tmux_session": tmux_session, "pid": pid, "agent": agent,
             "started": started or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    _write_atomic(Path(root) / CLAIM, json.dumps(claim, indent=2) + "\n")
    return claim


def tmux_session_exists(name: str) -> bool | None:
    """True when tmux has a session called exactly `name`, False when tmux says it has none, and None when tmux
    could not be asked (not installed, timed out, a server it cannot reach): an unknown is never an absence."""
    try:
        done = subprocess.run(["tmux", "has-session", "-t", f"={name}"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    if done.returncode == 0:
        return True
    said = (done.stderr or "").lower()
    return False if any(phrase in said for phrase in TMUX_ABSENT) else None


def read_claim(root, session_exists=tmux_session_exists) -> tuple[dict | None, bool | None, str]:
    """(claim, live, reason). Live is True when the claim's tmux session exists, False when it is stale (its session
    is gone, or the file is not JSON or lacks a key) and None when tmux could not say. No claim is (None, False)."""
    path = Path(root) / CLAIM
    try:
        claim = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, False, "no launch claim"
    except (OSError, ValueError) as exc:
        return None, False, f"{CLAIM} is not readable JSON ({exc}): stale"
    if not isinstance(claim, dict):
        return None, False, f"{CLAIM} is not a JSON object: stale"
    missing = [key for key in CLAIM_KEYS if key not in claim]
    if missing:
        return claim, False, f"{CLAIM} lacks {', '.join(missing)}: stale"
    if not isinstance(claim["tmux_session"], str) or not claim["tmux_session"]:
        return claim, False, f"{CLAIM} names no tmux session: stale"
    exists = session_exists(claim["tmux_session"])
    if exists is None:
        return claim, None, (f"whether tmux session {claim['tmux_session']} of session {claim['session']} is live "
                             "cannot be told: tmux could not be asked")
    if exists:
        return claim, True, f"session {claim['session']} is live in tmux session {claim['tmux_session']}"
    return claim, False, f"tmux session {claim['tmux_session']} is gone: stale"


def clear_claim(root, session: str, session_exists=tmux_session_exists) -> str:
    """Remove the claim when it is stale or belongs to `session`, the run being stopped. A live claim of another
    session, one whose liveness is unknown, and one replaced after it was read are left in place and refused."""
    path = Path(root) / CLAIM
    try:
        seen = path.read_bytes()
    except FileNotFoundError:
        return "no launch claim"
    claim, live, reason = read_claim(root, session_exists)
    owner = claim.get("session") if isinstance(claim, dict) else None
    if live is None:
        raise LaunchError(f"{CLAIM} is left in place: {reason}")
    if live and owner != session:
        raise LaunchError(f"{CLAIM} belongs to live session {owner} (tmux session {claim.get('tmux_session')}); "
                          f"it is not {session}'s to clear")
    moved = path.with_name(f"{path.name}.clearing-{os.getpid()}")
    try:
        os.replace(path, moved)  # taken atomically: a claim written after this lands at `path` untouched
    except FileNotFoundError:
        return "no launch claim"
    if moved.read_bytes() == seen:
        moved.unlink()
        return f"cleared ({reason})" if not live else f"cleared (session {session} stopped)"
    try:
        os.link(moved, path)  # a replacement written after the read: put back, unless a newer one is there
    except FileExistsError:
        pass  # a newer claim already stands at the path, and it is kept
    moved.unlink()
    raise LaunchError(f"{CLAIM} was replaced after it was read; the new claim is left in place")
