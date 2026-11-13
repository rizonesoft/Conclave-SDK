"""Run one scheduled automation, keep its log, and email the operator when it fails.

    python .conclave/automations/run.py NAME
    python .conclave/automations/run.py --check       (installers) print the folder, or refuse tasks.json
    python .conclave/automations/run.py --units DIR   (install.sh) write a systemd user unit pair per task

Windows Task Scheduler starts this through `pythonw.exe` (install.ps1 registers every task in tasks.json with it),
and on Linux and WSL a systemd user timer starts it (install.sh). It runs the task's command from the repository
root with the task's timeout, writes the combined output to `build/automations/<name>/<UTC>.log` (the newest 20
kept) and the outcome to `build/automations/<name>/last.json`, and on a non-zero exit, a timeout, or a command that
cannot start (126) sends the failure email through alert.py. Every process it starts, and every nested launch in
the tasks, carries CREATE_NO_WINDOW on Windows, so a scheduled run never opens a console on the desktop. This
wrapper is the one place a failure is reported on both schedulers. Its own exit is the command's (124 on a timeout,
or 3 when the alert could not be sent), so Task Scheduler's Last Run Result and a failed systemd unit show it too.
"""

from __future__ import annotations

import datetime
import importlib.util
import json
import os
import re
import signal
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
FOLDER = re.compile(r"^\\([A-Za-z0-9][A-Za-z0-9._-]*)\\$")
DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
KEEP_LOGS = 20
NO_WINDOW = 0x08000000
MARKER = "# conclave-automations: "


class TaskError(ValueError):
    pass


def _whole(value) -> bool:
    """A positive whole number; JSON `true` is a Python int, and is refused."""
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


# A run starts only when its operator starts it (owner decision 2026-11-12), so no scheduled task may invoke a run
# launcher. The names are the ones the owner's launcher-test hook knows (global/claude/hooks/launcher_tests.py:17);
# `unattended-run.py` launches only with `start` (its `status` and `stop` are ordinary checks).
LAUNCHER = re.compile(r"(?:^|[\\/])(start-run\.ps1|start-campaign[^\\/]*|start-unattended-run[^\\/]*|run-desktop\.sh|"
                      r"unattended-run\.py)$", re.I)
# Set for every process a scheduled task runs; a run launcher refuses to start a run under it.
AUTOMATION = "CONCLAVE_AUTOMATION"
INTERPRETERS = {"python", "python3", "pythonw", "py", "pwsh", "powershell", "bash", "sh", "wsl"}
# Each interpreter's options that take a value, so the value is not read as its script.
_PWSH = {"-executionpolicy", "-ep", "-ex", "-workingdirectory", "-wd", "-windowstyle", "-w", "-configurationname",
         "-settingsfile", "-inputformat", "-if", "-outputformat", "-of", "-o"}
VALUED = {"python": {"-w", "-x"}, "python3": {"-w", "-x"}, "pythonw": {"-w", "-x"}, "py": {"-w", "-x"},
          "pwsh": _PWSH, "powershell": _PWSH, "bash": {"-o"}, "sh": {"-o"},
          "wsl": {"-d", "--distribution", "-u", "--user", "--cd"}}


def _launcher_script(script: str, args: list[str]) -> bool:
    found = LAUNCHER.search(script.strip("'\""))
    if not found:
        return False
    if found.group(1).lower() == "unattended-run.py":
        # Its subcommand follows options its parser also takes abbreviated (`--ro /repo start`), so `start` anywhere
        # among its words is a start: no spelling of an option can hide one.
        return "start" in args
    return True


def _shell_commands(text: str, shell: str) -> list[list[tuple[str, bool]]]:
    r"""The commands of a shell command string, each its words as (text, began quoted), read by the shell's own
    rules: for "posix" (bash, sh) a backslash escapes, single quotes are literal and double quotes keep `\"`, `\\`,
    `\$` and `` \` `` escapes; for "powershell" a backtick escapes and `''` is a quote inside single quotes. Only an
    unquoted `;`, `&`, `|` or line break ends a command; in PowerShell a lone `&` that starts one is its call operator,
    kept as a word."""
    esc = "`" if shell == "powershell" else "\\"
    text = text.replace("\r\n", "\n")  # a Windows line end is a line end, for a continuation and a command break alike
    commands: list[list[tuple[str, bool]]] = []
    words: list[tuple[str, bool]] = []
    word: list[str] = []
    in_word = quoted = False
    i, n = 0, len(text)

    def flush():
        nonlocal word, in_word, quoted
        if in_word:
            words.append(("".join(word), quoted))
        word, in_word, quoted = [], False, False

    while i < n:
        ch = text[i]
        if ch == "'" or ch == '"':
            if not in_word:
                in_word, quoted = True, True
            i += 1
            while i < n:
                c = text[i]
                if c == ch and ch == "'" and shell == "powershell" and text[i + 1:i + 2] == "'":
                    word.append("'")
                    i += 2
                    continue
                if c == ch:
                    i += 1
                    break
                if ch == '"' and c == esc and i + 1 < n and (shell == "powershell" or text[i + 1] in '"\\$`\n'):
                    if text[i + 1] != "\n":  # an escaped line break inside double quotes is a continuation
                        word.append(text[i + 1])
                    i += 2
                    continue
                word.append(c)
                i += 1
            continue
        if ch == esc and i + 1 < n:
            if text[i + 1] == "\n":  # a line continuation: the command goes on on the next line
                i += 2
                continue
            in_word = True
            word.append(text[i + 1])
            i += 2
            continue
        if ch in ";&|\n":
            flush()
            if ch == "&" and shell == "powershell" and not words and text[i + 1:i + 2] != "&":
                words.append(("&", False))
                i += 1
                continue
            if words:
                commands.append(words)
            words = []
            i += 2 if text[i:i + 2] in ("&&", "||") else 1
            continue
        if ch in " \t\r":
            flush()
            i += 1
            continue
        in_word = True
        word.append(ch)
        i += 1
    flush()
    if words:
        commands.append(words)
    return commands


def _launcher_in_text(text: str, shell: str) -> str | None:
    """The launcher the first command of any command in a shell command string invokes, or None."""
    for command in _shell_commands(text, shell):
        found = launcher_in([w for w, _ in command], shell, [q for _, q in command])
        if found:
            return found
    return None

def launcher_in(command: list[str], shell: str | None = None, quoted: list[bool] | None = None) -> str | None:
    """The run launcher `command` invokes, as its program or as the script an interpreter runs (inside a shell's
    `-c` or `-Command` string too), or None. A launcher named only as data, such as an argument to `git diff`, is not
    an invocation."""
    quoted = quoted or [False] * len(command)
    pairs, call = [(w, q) for w, q in zip(command, quoted) if w], False
    while pairs and pairs[0][0] in ("&", ".", "exec", "env", "nohup") and not pairs[0][1]:
        call, pairs = call or pairs[0][0] in ("&", "."), pairs[1:]
    if not pairs:
        return None
    if shell == "powershell" and not call and pairs[0][1]:
        return None  # a quoted first word in PowerShell is a string, invoked only after `&` or `.`
    words = [w for w, _ in pairs]
    program = re.split(r"[\\/]", words[0])[-1].lower().removesuffix(".exe")
    if _launcher_script(words[0], words[1:]):
        return words[0]
    if program not in INTERPRETERS:
        return None
    rest, i = words[1:], 0
    while i < len(rest):
        word, low = rest[i], rest[i].lower()
        if program == "wsl" and low in ("--", "-e", "--exec"):
            return launcher_in(rest[i + 1:])
        if program in ("pwsh", "powershell") and low in ("-c", "-command"):
            # PowerShell runs the rest of its arguments as one command line.
            return _launcher_in_text(" ".join(rest[i + 1:]), "powershell")
        if program in ("bash", "sh") and re.fullmatch(r"-[a-z]*c[a-z]*", low):
            # bash runs the one string after -c; the words after it are $0, $1 and on, data to that string.
            return _launcher_in_text(rest[i + 1], "posix") if i + 1 < len(rest) else None
        if low in ("-file", "-f"):
            i += 1
            continue
        if low == "-m" and program in ("python", "python3", "pythonw", "py"):
            return None  # a module, not a script
        if low in VALUED[program]:
            i += 2
            continue
        if word.startswith("-"):
            i += 1
            continue
        if program == "wsl":
            return launcher_in(rest[i:])
        return word if _launcher_script(word, rest[i + 1:]) else None
    return None


def load_manifest(path: str, launchers: bool = True) -> dict:
    """tasks.json as {"folder", "prefix", "tasks" by name}, refused unless every entry is well formed.

    `folder` is the project's Task Scheduler folder (`\\Isotone\\`), and every task name starts with the folder's
    name in lower case and a hyphen (`isotone-`), so two projects never share a folder or a unit name. A freshly
    installed kit has `folder: null` and no tasks until the project names its folder. A task that invokes a run
    launcher is refused, unless `launchers` is False: an installer removing a schedule only needs its shape.
    """
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    if not isinstance(doc, dict) or doc.get("schema_version") != 1 or not isinstance(doc.get("tasks"), list):
        raise TaskError("tasks.json needs schema_version 1 and a tasks list")
    folder = doc.get("folder")
    if folder is None:
        if doc["tasks"]:
            raise TaskError("tasks.json lists tasks but no folder: set folder to \\<Project>\\ first")
        return {"folder": None, "prefix": None, "tasks": {}}
    match = FOLDER.fullmatch(folder) if isinstance(folder, str) else None
    if not match:
        raise TaskError("tasks.json folder must be one Task Scheduler folder, like \\Isotone\\")
    prefix = match.group(1).lower() + "-"
    name_rule = re.compile(re.escape(prefix) + r"[a-z0-9][a-z0-9-]*")
    out: dict[str, dict] = {}
    for task in doc["tasks"]:
        if not isinstance(task, dict):
            raise TaskError(f"every task must be an object, not {task!r}")
        name = task.get("name", "")
        if not isinstance(name, str) or not name_rule.fullmatch(name) or name in out:
            raise TaskError(f"task name {name!r} must be a unique {prefix}* name")
        if set(task) != {"name", "description", "command", "trigger", "timeout_minutes"}:
            raise TaskError(f"{name}: needs exactly name, description, command, trigger, timeout_minutes")
        description = task["description"]
        if not isinstance(description, str) or not description.strip() or "\n" in description or "\r" in description:
            raise TaskError(f"{name}: description must be one non-empty line")
        command = task["command"]
        if not isinstance(command, list) or not command or not all(isinstance(c, str) and c for c in command):
            raise TaskError(f"{name}: command must be a non-empty list of strings")
        launcher = launcher_in(command) if launchers else None
        if launcher:
            raise TaskError(f"{name}: command starts the run launcher {launcher}; a run starts only when its operator "
                            "starts it, never on a schedule (owner decision 2026-11-12)")
        if not _whole(task["timeout_minutes"]):
            raise TaskError(f"{name}: timeout_minutes must be a positive whole number")
        trigger = task["trigger"]
        if not isinstance(trigger, dict):
            raise TaskError(f"{name}: trigger must be at-logon-and-every or weekly-at")
        if set(trigger) == {"at_logon_delay_minutes", "every_minutes"}:
            if not all(_whole(trigger[k]) for k in trigger):
                raise TaskError(f"{name}: a logon trigger needs positive whole minutes")
        elif set(trigger) == {"weekly", "at"}:
            if trigger["weekly"] not in DAYS or not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", str(trigger["at"])):
                raise TaskError(f"{name}: a weekly trigger needs a day name and an HH:MM time")
        else:
            raise TaskError(f"{name}: trigger must be at-logon-and-every or weekly-at")
        out[name] = task
    return {"folder": folder, "prefix": prefix, "tasks": out}


def load_tasks(path: str) -> dict[str, dict]:
    """The tasks in tasks.json by name, refused unless every entry is well formed."""
    return load_manifest(path)["tasks"]


def resolve(command: list[str]) -> list[str]:
    """`python` is the console interpreter beside this one (Task Scheduler starts pythonw.exe)."""
    if command[0] != "python":
        return command
    here = sys.executable
    console = os.path.join(os.path.dirname(here), "python.exe")
    return [console if os.name == "nt" and os.path.isfile(console) else here] + command[1:]


def _utc(stamp: bool = False) -> str:
    now = datetime.datetime.now(datetime.timezone.utc)
    return now.strftime("%Y%m%dT%H%M%SZ" if stamp else "%Y-%m-%dT%H:%M:%SZ")


def _spawn_options() -> dict:
    """How every task starts: with no console on Windows, and in a process group of its own elsewhere, so a timeout
    stops what the task started too."""
    return {"creationflags": NO_WINDOW} if os.name == "nt" else {"start_new_session": True}


def _kill_tree(proc) -> None:
    """Stop the task and everything it started: taskkill's tree on Windows, the task's process group elsewhere."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, timeout=60,
                       creationflags=NO_WINDOW)
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:  # the group already exited between the timeout and this kill
            pass
    proc.wait(timeout=60)


def execute(name: str, task: dict, root: str, popen=subprocess.Popen, killer=_kill_tree) -> dict:
    """Run the task's command into a fresh log; returns the outcome recorded in last.json."""
    folder = os.path.join(root, "build", "automations", name)
    os.makedirs(folder, exist_ok=True)
    log = os.path.join(folder, _utc(stamp=True) + ".log")
    outcome = {"name": name, "started": _utc(), "log": os.path.relpath(log, root).replace("\\", "/"),
               "timed_out": False}
    # Every process a task starts carries the task's name, so a run launcher it reaches by any spelling (a variable,
    # an eval, a script that calls it) refuses to start a run: the launcher owns that refusal (D02 T02 §9).
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", AUTOMATION: name}
    with open(log, "wb") as out:
        try:
            proc = popen(resolve(task["command"]), cwd=root, stdout=out, stderr=subprocess.STDOUT,
                         stdin=subprocess.DEVNULL, env=env, **_spawn_options())
        except OSError as error:  # the command never started: a failed run like any other, so it is alerted
            out.write(f"run.py: could not start {task['command'][0]}: {error}\n".encode("utf-8"))
            proc = None
            outcome["exit"] = 126
        if proc is not None:
            try:
                outcome["exit"] = proc.wait(timeout=task["timeout_minutes"] * 60)
            except subprocess.TimeoutExpired:
                killer(proc)
                outcome.update(exit=124, timed_out=True)
    outcome["finished"] = _utc()
    logs = sorted(f for f in os.listdir(folder) if f.endswith(".log"))
    for old in logs[:-KEEP_LOGS]:
        os.unlink(os.path.join(folder, old))
    tmp = os.path.join(folder, "last.json.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(outcome, fh, indent=2)
    os.replace(tmp, os.path.join(folder, "last.json"))
    return outcome


def _quote(arg: str) -> str:
    """One systemd ExecStart argument: quoted, with `%` specifiers, backslashes and quotes escaped."""
    return '"' + arg.replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%") + '"'


def systemd_units(manifest: dict, root: str, python: str) -> dict[str, str]:
    """A `<name>.service` and `<name>.timer` per task, each carrying the marker that names this tasks.json.

    The service is a oneshot that runs this file with the task's name (so the failure email comes from here, as on
    Windows) and is stopped five minutes past the task's timeout. A weekly timer is `Persistent=true` with a
    five-minute random delay, as Task Scheduler's start-when-available and random delay are; a logon timer fires
    the delay after the user manager starts and then on the interval.
    """
    marker = MARKER + os.path.join(root, ".conclave", "automations", "tasks.json")
    units: dict[str, str] = {}
    for name, task in manifest["tasks"].items():
        units[f"{name}.service"] = "\n".join([
            marker,
            "[Unit]",
            f"Description={task['description'].replace('%', '%%')}",
            "",
            "[Service]",
            "Type=oneshot",
            f"WorkingDirectory={root.replace('%', '%%')}",
            "ExecStart=" + " ".join(_quote(a) for a in (python, os.path.join(root, ".conclave", "automations", "run.py"),
                                                         name)),
            f"TimeoutStartSec={task['timeout_minutes'] + 5}min",
            "",
        ])
        trigger = task["trigger"]
        if "weekly" in trigger:
            when = [f"OnCalendar={trigger['weekly'][:3]} *-*-* {trigger['at']}:00", "Persistent=true",
                    "RandomizedDelaySec=300"]
        else:
            when = [f"OnStartupSec={trigger['at_logon_delay_minutes']}min",
                    f"OnUnitActiveSec={trigger['every_minutes']}min"]
        units[f"{name}.timer"] = "\n".join([
            marker, "[Unit]", f"Description={task['description'].replace('%', '%%')}", "", "[Timer]", *when, "",
            "[Install]", "WantedBy=timers.target", "",
        ])
    return units


def write_units(out_dir: str, root: str = REPO, python: str | None = None, removal: bool = False) -> str:
    """Write every task's units into out_dir (refused without a folder); returns the marker line. `removal`: for an
    uninstall, which writes none of them, so the launcher rule is left out."""
    installable_folder(root, removal)
    manifest = load_manifest(os.path.join(root, ".conclave", "automations", "tasks.json"), launchers=not removal)
    for filename, text in systemd_units(manifest, root, python or sys.executable).items():
        tmp = os.path.join(out_dir, filename + ".tmp")
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        os.replace(tmp, os.path.join(out_dir, filename))
    return MARKER + os.path.join(root, ".conclave", "automations", "tasks.json")


def _alert_module():
    spec = importlib.util.spec_from_file_location("conclave_automations_alert", os.path.join(HERE, "alert.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def installable_folder(root: str = REPO, removal: bool = False) -> str:
    """The folder an installer registers into, refused when tasks.json is malformed or names no folder yet. `removal`
    (an uninstall) leaves the launcher rule out, so a schedule written before it can still be removed."""
    manifest = load_manifest(os.path.join(root, ".conclave", "automations", "tasks.json"), launchers=not removal)
    if manifest["folder"] is None:
        raise TaskError("tasks.json has no folder yet: set it to \\<Project>\\ before installing")
    return manifest["folder"]


def main(argv: list[str], root: str = REPO, popen=subprocess.Popen, alerter=None, killer=_kill_tree) -> int:
    removal = argv[-1:] == ["--removal"]
    check = argv[:-1] if removal else argv
    if check == ["--check"] or (len(check) == 2 and check[0] == "--units"):
        try:
            print(installable_folder(root, removal) if check[0] == "--check" else
                  write_units(check[1], root, removal=removal))
        except (TaskError, OSError, ValueError) as error:
            print(f"run: {error}", file=sys.stderr)
            return 2
        return 0
    if len(argv) != 1 or argv[0].startswith("-"):
        print(__doc__.split("\n\n")[0], file=sys.stderr)
        return 2
    manifest = load_manifest(os.path.join(root, ".conclave", "automations", "tasks.json"))
    task = manifest["tasks"].get(argv[0])
    if task is None:
        print(f"run: no task named {argv[0]} in tasks.json", file=sys.stderr)
        return 2
    outcome = execute(argv[0], task, root, popen, killer)
    if outcome["exit"] == 0:
        return 0
    alert = _alert_module()
    try:
        (alerter or alert.send_failure)(argv[0], task, outcome, alert.tail_of(os.path.join(root, outcome["log"])),
                                        manifest["folder"])
    except Exception as error:  # the run already failed; an unsent alert must still show, as exit 3
        with open(os.path.join(root, outcome["log"]), "a", encoding="utf-8") as fh:
            fh.write(f"\nrun.py: alert not sent: {type(error).__name__}: {error}\n")
        return 3
    return outcome["exit"]


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
