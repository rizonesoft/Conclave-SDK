#!/usr/bin/env python3
"""Check the build tools a project pins: which are installed, and whether each is new enough.

    python scripts/toolchain-check.py --pins .conclave/toolchain-cpp.json [--json]

The pin file names each tool, the commands that satisfy it in order of preference and, for each command, how to
ask its version and the least version the project accepts:

    {"schema_version": 1,
     "tools": [{"name": "compiler-cache",
                "commands": [{"command": "ccache", "version_args": ["--version"],
                              "version_pattern": "ccache version ([0-9.]+)", "min_version": "4.0"},
                             {"command": "sccache", "version_args": ["--version"],
                              "version_pattern": "sccache ([0-9.]+)", "min_version": "0.5"}],
                "install": "apt install ccache", "optional": true}]}

It prints one line per tool and exits 3 when a tool that is not optional is not ok, 2 when the pin file does not
load. It reads and reports: it installs nothing and writes nothing. Standard library only.
"""
import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

TIME_LIMIT = 15.0        # seconds a tool gets to print its version
OUTPUT_CAP = 64 * 1024   # bytes read from a tool before it is stopped
PATTERN_LIMIT = 5.0      # seconds a version pattern gets to read that output
PATTERN_LENGTH = 500     # characters a version pattern may hold

NAME = re.compile(r"[a-z0-9][a-z0-9+.-]*")
COMMAND = re.compile(r"[A-Za-z0-9][A-Za-z0-9+._-]*")  # a bare name: found on PATH, never a path into the project
# What a version argument may hold. On Windows a .cmd launcher is started through cmd.exe, which reads other
# characters as its own syntax; none of them is needed to ask a tool its version.
ARGUMENT = re.compile(r"[A-Za-z0-9=_./:+-]+")
# At most eight parts of at most nine digits: no release is numbered past that, and a longer run of digits is
# output to refuse, not a number to convert.
VERSION = re.compile(r"[0-9]{1,9}(?:\.[0-9]{1,9}){0,7}")
TOP_KEYS = {"schema_version", "tools"}
TOOL_KEYS = {"name", "commands", "install", "optional"}
COMMAND_KEYS = {"command", "version_args", "version_pattern", "min_version"}


class PinError(ValueError):
    """A pin file that cannot be used: the message names the file and, where there is one, the tool and the key."""


def _keys(where, found, required, optional=()):
    unknown = sorted(set(found) - set(required) - set(optional))
    if unknown:
        raise PinError(f"{where}: unknown key {unknown[0]!r}")
    missing = sorted(set(required) - set(found))
    if missing:
        raise PinError(f"{where}: missing key {missing[0]!r}")


def _load_command(where, entry):
    if not isinstance(entry, dict):
        raise PinError(f"{where}: a command is an object with the keys {', '.join(sorted(COMMAND_KEYS))}")
    name = entry.get("command")
    if not isinstance(name, str) or not COMMAND.fullmatch(name):
        raise PinError(f"{where}: command: a bare program name, not a path: {name!r}")
    where = f"{where}: command {name!r}"
    _keys(where, entry, COMMAND_KEYS)
    args = entry["version_args"]
    if not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
        raise PinError(f"{where}: version_args: a list of strings")
    for arg in args:
        if not ARGUMENT.fullmatch(arg):
            raise PinError(f"{where}: version_args: {arg!r} holds a character outside A-Z a-z 0-9 = _ . / : + -")
    pattern = entry["version_pattern"]
    if not isinstance(pattern, str):
        raise PinError(f"{where}: version_pattern: a regular expression as text")
    if len(pattern) > PATTERN_LENGTH:
        raise PinError(f"{where}: version_pattern: longer than {PATTERN_LENGTH} characters")
    try:
        compiled = re.compile(pattern)
    except (re.error, RecursionError, OverflowError) as exc:
        raise PinError(f"{where}: version_pattern: does not compile ({exc or type(exc).__name__})") from exc
    if compiled.groups != 1:
        raise PinError(f"{where}: version_pattern: needs exactly one group, has {compiled.groups}")
    minimum = entry["min_version"]
    if not isinstance(minimum, str) or not VERSION.fullmatch(minimum):
        raise PinError(f"{where}: min_version: dotted numbers such as 1.10, not {str(minimum)[:40]!r}")
    return {"command": name, "version_args": list(args), "version_pattern": pattern, "min_version": minimum}


def load_pins(path):
    """The tools a pin file names, checked: a list of {"name", "commands", "install", "optional"}.

    Raises PinError, naming the file and what is wrong with it, for anything the format does not allow."""
    where = Path(path).as_posix()
    try:
        data = json.loads(Path(path).read_bytes().decode("utf-8"))
    except OSError as exc:
        raise PinError(f"{where}: cannot be read ({exc.strerror or exc})") from exc
    except UnicodeDecodeError as exc:
        raise PinError(f"{where}: not UTF-8 ({exc})") from exc
    except (ValueError, RecursionError) as exc:
        raise PinError(f"{where}: not JSON ({exc})") from exc
    if not isinstance(data, dict):
        raise PinError(f"{where}: a pin file is an object with the keys schema_version and tools")
    _keys(where, data, TOP_KEYS)
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise PinError(f"{where}: schema_version: must be 1")
    if not isinstance(data["tools"], list):
        raise PinError(f"{where}: tools: a list of tools")
    tools, seen = [], set()
    for number, tool in enumerate(data["tools"], 1):
        if not isinstance(tool, dict):
            raise PinError(f"{where}: tool {number}: a tool is an object with the keys {', '.join(sorted(TOOL_KEYS))}")
        name = tool.get("name")
        if not isinstance(name, str) or not NAME.fullmatch(name):
            raise PinError(f"{where}: tool {number}: name: lowercase letters, digits, +, . and -, not {name!r}")
        tool_where = f"{where}: tool {name!r}"
        if name in seen:
            raise PinError(f"{tool_where}: name: used by two tools")
        seen.add(name)
        _keys(tool_where, tool, TOOL_KEYS - {"optional"}, ("optional",))
        if not isinstance(tool["commands"], list) or not tool["commands"]:
            raise PinError(f"{tool_where}: commands: a list of at least one command")
        commands = [_load_command(tool_where, entry) for entry in tool["commands"]]
        install = tool["install"]
        if not isinstance(install, str) or not install.strip() or "\n" in install or "\r" in install:
            raise PinError(f"{tool_where}: install: a one-line hint")
        optional = tool.get("optional", False)
        if not isinstance(optional, bool):
            raise PinError(f"{tool_where}: optional: true or false")
        tools.append({"name": name, "commands": commands, "install": install, "optional": optional})
    return tools


def parse_version(text):
    """A captured version as a tuple of numbers, or None when the capture is not dotted numbers."""
    if not isinstance(text, str) or not VERSION.fullmatch(text):
        return None
    return tuple(int(part) for part in text.split("."))


def compare_versions(found, wanted):
    """-1, 0 or 1 as `found` is older than, the same as or newer than `wanted`, number by number. A missing
    trailing part is zero, so 1.2 is 1.2.0, and 1.10 is newer than 1.9."""
    left, right = parse_version(found), parse_version(wanted)
    if left is None or right is None:
        raise ValueError(f"not a version: {found if left is None else wanted!r}")
    width = max(len(left), len(right))
    left += (0,) * (width - len(left))
    right += (0,) * (width - len(right))
    return (left > right) - (left < right)


def _end_tree(proc):
    """End a tool and everything it started: a version command that hangs must leave nothing behind.

    Each step may find the process already gone, which is the outcome wanted, so that is not an error here; the
    caller's result still says which limit was hit."""
    if os.name == "nt":
        taskkill = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "taskkill.exe")
        try:
            subprocess.run([taskkill, "/T", "/F", "/PID", str(proc.pid)], capture_output=True, timeout=15,
                           creationflags=subprocess.CREATE_NO_WINDOW)
        except (OSError, subprocess.SubprocessError):
            pass
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)  # the tool leads its own session, so the group is its tree
        except (ProcessLookupError, PermissionError):
            pass
    try:
        proc.kill()
    except OSError:
        pass
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        pass


def run_bounded(argv, time_limit=TIME_LIMIT, output_cap=OUTPUT_CAP):
    """Run `argv` with no shell and no console window, reading standard output and standard error together.

    Returns {"output", "exit", "stopped", "error"}: `stopped` is "time" or "output" when a limit ended the run (the
    whole process tree is then ended), and `error` is the system's reason when the program could not be started."""
    windows = os.name == "nt"
    try:
        # Its own process group on Windows and its own session on POSIX, so its whole tree can be ended.
        proc = subprocess.Popen(
            argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            creationflags=(subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP) if windows else 0,
            start_new_session=not windows)
    except OSError as exc:
        return {"output": "", "exit": None, "stopped": None, "error": exc.strerror or str(exc)}
    chunks, over = [], threading.Event()

    def read():
        total = 0
        while True:
            try:
                data = proc.stdout.read1(4096)
            except (OSError, ValueError):
                return
            if not data:
                return
            room = output_cap - total
            chunks.append(data[:max(room, 0)])
            total += len(data)
            if total > output_cap:
                over.set()
                return

    reader = threading.Thread(target=read, daemon=True)
    stopped = None
    try:
        reader.start()
        deadline = time.monotonic() + time_limit
        while reader.is_alive() and time.monotonic() < deadline:
            reader.join(0.05)
        if over.is_set():
            stopped = "output"
        elif reader.is_alive():
            stopped = "time"
        else:
            try:
                proc.wait(timeout=max(deadline - time.monotonic(), 0.05))
            except subprocess.TimeoutExpired:
                stopped = "time"
    finally:
        # Every way out, an interrupt (Ctrl+C) included: the tool leads its own session, so nothing else ends it.
        if proc.poll() is None:
            _end_tree(proc)
        reader.join(5)
        proc.stdout.close()
    return {"output": b"".join(chunks).decode("utf-8", errors="replace"), "exit": proc.returncode,
            "stopped": stopped, "error": None}


_SEARCH = """import json, re, sys
job = json.load(sys.stdin)
found = re.search(job['pattern'], job['text'])
json.dump({'matched': found is not None, 'group': found.group(1) if found else None}, sys.stdout)
"""


def search_bounded(pattern, text, limit=None):
    """`re.search(pattern, text)` under a time limit: {"matched", "group"}, or None when it did not finish.

    The standard library cannot stop a match that backtracks without end, and a thread running one cannot be
    stopped either, so the match runs in a second interpreter that can."""
    limit = PATTERN_LIMIT if limit is None else limit
    try:
        ran = subprocess.run([sys.executable, "-I", "-S", "-c", _SEARCH], capture_output=True, timeout=limit,
                             input=json.dumps({"pattern": pattern, "text": text}).encode("utf-8"),
                             creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        return json.loads(ran.stdout.decode("utf-8")) if ran.returncode == 0 else None
    except (subprocess.TimeoutExpired, OSError, ValueError):
        return None


def check_tool(pin, time_limit=TIME_LIMIT, output_cap=OUTPUT_CAP):
    """One pinned tool: {"name", "status", "detail", "version", "command", "optional"}, `status` being `ok` or
    `setup_required`. The first of its commands found on PATH is the one checked, against its own minimum."""
    result = {"name": pin["name"], "status": "setup_required", "detail": "", "version": None, "command": None,
              "optional": pin["optional"]}
    for entry in pin["commands"]:
        path = shutil.which(entry["command"])
        if path:
            break
    else:
        names = ", ".join(entry["command"] for entry in pin["commands"])
        result["detail"] = f"not installed ({names} not on PATH). Install: {pin['install']}"
        return result
    result["command"] = path
    shown = " ".join([path, *entry["version_args"]])
    ran = run_bounded([path, *entry["version_args"]], time_limit, output_cap)
    if ran["error"] is not None:
        result["detail"] = f"{path} could not be started: {ran['error']}"
    elif ran["stopped"] == "time":
        result["detail"] = f"{shown} did not answer within {time_limit:g} seconds and was stopped"
    elif ran["stopped"] == "output":
        result["detail"] = f"{shown} printed more than {output_cap} bytes and was stopped"
    elif ran["exit"] != 0:
        result["detail"] = f"{shown} exited {ran['exit']}"
    else:
        found = search_bounded(entry["version_pattern"], ran["output"])
        if found is None:
            result["detail"] = (f"{shown}: the pattern {entry['version_pattern']!r} did not finish reading its output "
                                f"within {PATTERN_LIMIT:g} seconds")
        elif not found["matched"]:
            result["detail"] = f"{shown}: the pattern {entry['version_pattern']!r} does not match its output"
        elif parse_version(found["group"]) is None:
            result["detail"] = f"{shown}: the pattern captured {str(found['group'])[:40]!r}, which is not a version"
        else:
            result["version"] = found["group"]
            if compare_versions(found["group"], entry["min_version"]) < 0:
                result["detail"] = (f"{path} is {found['group']}, older than the pinned {entry['min_version']}. "
                                    f"Install: {pin['install']}")
            else:
                result["status"], result["detail"] = "ok", path
    return result


def check_tools(pins, time_limit=TIME_LIMIT, output_cap=OUTPUT_CAP):
    """Every pinned tool, in the file's order: one that fails never stops the next from being checked."""
    return [check_tool(pin, time_limit, output_cap) for pin in pins]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check the build tools a pin file names. Installs nothing.")
    parser.add_argument("--pins", required=True, help="the pin file, for example .conclave/toolchain-cpp.json")
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    args = parser.parse_args(argv)
    try:
        pins = load_pins(args.pins)
    except PinError as exc:
        print(f"toolchain-check: {exc}", file=sys.stderr)
        return 2
    tools = check_tools(pins)
    required_not_ok = sum(1 for tool in tools if tool["status"] != "ok" and not tool["optional"])
    if args.json:
        print(json.dumps({"pins": Path(args.pins).as_posix(), "tools": tools, "required_not_ok": required_not_ok},
                         indent=2))
    else:
        for tool in tools:
            print(f"{tool['name']}  {tool['status']}  {tool['detail']}")
    return 3 if required_not_ok else 0


if __name__ == "__main__":
    sys.exit(main())
