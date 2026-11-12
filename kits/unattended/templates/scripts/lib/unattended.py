"""Shared code of the unattended kit: the run profile loader so far; the launch lock and claim and the ship counter
come with D02 T02 §6 and §7.

The launcher (`scripts/unattended-run.py`) and the preflight (`scripts/unattended-preflight.py`) will import it.
It holds no project name: the project's own settings live in `.conclave/unattended.json` (the run profile).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re

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
    if not isinstance(data["tools"], list) or not all(isinstance(t, str) and t for t in data["tools"]):
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
                or not command[0].strip()):
            raise fault(f"{where}.command", "must be a list of strings that starts with a program")
        timeout = check["timeout_seconds"]
        if isinstance(timeout, bool) or not isinstance(timeout, int) or timeout <= 0:
            raise fault(f"{where}.timeout_seconds", "must be a whole number above 0")
    return data
