"""Email the operator when a scheduled automation fails.

    python .conclave/automations/alert.py NAME            send the failure email for NAME's last run
    python .conclave/automations/alert.py NAME --dry-run  print that email instead, reading no key

run.py calls `send_failure` when a task exits non-zero or times out, so a failed run is reported by the
wrapper that saw it fail, whatever the command printed. The email carries the task, its exit, its start and
finish, the tail of that run's log, and how to run it again on this machine's scheduler.

It goes through SMTP2GO's `/v3/email/send`. Who sends it, who receives it and which vault item holds the key are
this owner's settings, read from `[alert]` in `.conclave/local.toml` with `.private/local.toml` as the overlay
fallback (`sender`, `to`, `key_item`; the template is `.conclave/local.example.toml`), and the email is refused
while one is unset. The key is read at send time through the vault tool `[vault] cli` names (`conclave-op` by
default, in WSL when this runs on Windows), for this run only: never written to disk, an argument, or the output.
SMTP2GO answers a refused send with HTTP 200 and `succeeded: 0`, so anything but one success and no failures is a
refusal.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shlex
import socket
import subprocess
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
LOCAL = os.path.join(".conclave", "local.toml")
OVERLAY = os.path.join(".private", "local.toml")
ENDPOINT = "https://api.smtp2go.com/v3/email/send"
LOG_LINES = 60
ADDRESS = re.compile(r"[^@\s<>\"',;]+@[^@\s<>\"',;]+")
KEY_ITEM = re.compile(r"op://[A-Za-z0-9 ._-]+/[A-Za-z0-9 ._-]+")


class Refused(Exception):
    pass


def _local_settings():
    """Load the shared local_settings helper relative to this installed script (lazy so import errors stay inside
    run.py's alert-failure handler)."""
    candidates = (
        os.path.join(REPO, "scripts", "lib", "local_settings.py"),
        os.path.normpath(os.path.join(REPO, "..", "..", "base", "templates", "scripts", "lib", "local_settings.py")),
    )
    for candidate in candidates:
        if os.path.isfile(candidate):
            spec = importlib.util.spec_from_file_location("_conclave_local_settings", candidate)
            if spec is not None and spec.loader is not None:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                return module
    raise Refused(f"scripts/lib/local_settings.py is missing next to {REPO}")


def settings(root: str = REPO) -> dict:
    """This owner's `sender`, `to`, `key_item` and vault `cli` from `.conclave/local.toml` (per-machine override)
    and `.private/local.toml` (owner overlay). Refuses, naming the key, while both files are missing, either file
    is malformed, or a value is unset or not of its shape: nothing is guessed."""
    ls = _local_settings()
    try:
        data, loaded = ls.load_local_settings(root)
    except ls.LocalSettingsError as error:
        raise Refused(str(error).replace("not readable as UTF-8 TOML", "not readable as TOML")) from None
    if not loaded:
        raise Refused(
            f"{LOCAL} is missing (and {OVERLAY} is not present): copy .conclave/local.example.toml to it and set [alert]"
        )
    sources = f"{LOCAL} / {OVERLAY}"
    alert, vault = data.get("alert", {}), data.get("vault", {})
    if not isinstance(alert, dict) or not isinstance(vault, dict):
        raise Refused(f"{sources}: [alert] and [vault] must be tables")
    found = {"cli": vault.get("cli", "conclave-op")}
    for name, shape in (("sender", ADDRESS), ("to", ADDRESS), ("key_item", KEY_ITEM)):
        value = alert.get(name, "")
        if not isinstance(value, str) or not shape.fullmatch(value):
            raise Refused(f"{sources}: set alert.{name} (see .conclave/local.example.toml)")
        found[name] = value
    if not isinstance(found["cli"], str) or not found["cli"].strip() or any(c in found["cli"] for c in "\r\n\0"):
        raise Refused(f"{sources}: vault.cli must be a command name or a path")
    return found


def key(config: dict, run=subprocess.run, windows: bool = os.name == "nt") -> str:
    """The API key, refused unless it has SMTP2GO's shape ("api-" and 32 letters or digits); never echoed."""
    read = f'{shlex.quote(config["cli"])} read {shlex.quote(config["key_item"] + "/credential")}'
    command = ["wsl.exe", "-e", "bash", "-lc", read] if windows else ["bash", "-lc", read]
    result = run(command, capture_output=True, text=True, timeout=90,
                 creationflags=0x08000000 if windows else 0)  # CREATE_NO_WINDOW: run.py has no console
    value = (result.stdout or "").strip()
    if result.returncode != 0 or not value:
        raise Refused("vault field credential is unavailable")
    if len(value) != 36 or not value.startswith("api-") or not value[4:].isalnum() or not value.isascii():
        raise Refused("vault field credential does not have the SMTP2GO key shape")
    return value


def sender(folder: str, address: str) -> str:
    """`\\Demo\\` sends as "Demo automations <address>"."""
    return f"{folder.strip(chr(92))} automations <{address}>"


def rerun(name: str, folder: str, windows: bool) -> list[str]:
    """How to start the task again, on the scheduler this machine uses."""
    if windows:
        return [f"Run again: Start-ScheduledTask -TaskPath '{folder}' -TaskName {name}",
                f"Or directly: python .conclave/automations/run.py {name}"]
    return [f"Run again: systemctl --user start {name}.service",
            f"Or directly: python3 .conclave/automations/run.py {name}"]


def message(name: str, task: dict, outcome: dict, tail: str, host: str, folder: str,
            windows: bool = os.name == "nt") -> tuple[str, str]:
    """The subject and plain-text body of the failure email."""
    exit_text = "timed out" if outcome.get("timed_out") else f"exit {outcome.get('exit')}"
    body = "\n".join([
        f"{name} failed on {host}: {exit_text}.",
        "",
        f"What it does: {task.get('description') or '(no description)'}",
        f"Command: {' '.join(task.get('command', []))}",
        f"Started: {outcome.get('started') or 'unknown'}",
        f"Finished: {outcome.get('finished') or 'unknown'}",
        "",
        f"Last {LOG_LINES} lines of this run's log ({outcome.get('log') or 'no log'}):",
        "",
        tail or "(the run wrote no output)",
        "",
        *rerun(name, folder, windows),
    ])
    return f"Automation failed: {name} on {host}", body


def send(api_key: str, subject: str, body: str, from_: str, to: str, opener=urllib.request.urlopen) -> str:
    """Post the email; refuse anything but one success and no failures."""
    payload = json.dumps({"sender": from_, "to": [to], "subject": subject, "text_body": body}).encode()
    request = urllib.request.Request(ENDPOINT, data=payload, method="POST", headers={
        "Content-Type": "application/json", "Accept": "application/json", "X-Smtp2go-Api-Key": api_key})
    with opener(request, timeout=60) as response:
        data = json.loads(response.read().decode() or "{}").get("data", {})
    if int(data.get("succeeded", 0)) < 1 or int(data.get("failed", 0)) > 0:
        raise Refused(f"SMTP2GO refused the send: {data.get('failures') or data.get('error') or data}")
    return data.get("email_id", "")


def send_failure(name: str, task: dict, outcome: dict, tail: str, folder: str, run=subprocess.run,
                 opener=urllib.request.urlopen, host: str | None = None, root: str = REPO) -> str:
    config = settings(root)
    subject, body = message(name, task, outcome, tail, host or socket.gethostname(), folder)
    return send(key(config, run), subject, body, sender(folder, config["sender"]), config["to"], opener)


def tail_of(path: str, lines: int = LOG_LINES) -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return "".join(fh.readlines()[-lines:]).rstrip()
    except OSError:
        return ""


def main(argv=None, run=subprocess.run, opener=urllib.request.urlopen, host=None, root=REPO) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("name", help="the task that failed, e.g. demo-packages")
    p.add_argument("--dry-run", action="store_true", help="print the email; read no key and send nothing")
    args = p.parse_args(argv)
    with open(os.path.join(root, ".conclave", "automations", "tasks.json"), encoding="utf-8") as fh:
        manifest = json.load(fh)
    task = {t.get("name"): t for t in manifest.get("tasks", [])}.get(args.name)
    if task is None or not manifest.get("folder"):
        print(f"alert: no task named {args.name}", file=sys.stderr)
        return 2
    folder = manifest["folder"]
    try:
        with open(os.path.join(root, "build", "automations", args.name, "last.json"), encoding="utf-8") as fh:
            outcome = json.load(fh)
    except (OSError, ValueError):
        outcome = {}
    tail = tail_of(os.path.join(root, outcome["log"])) if outcome.get("log") else ""
    try:
        config = settings(root)
        if args.dry_run:
            subject, body = message(args.name, task, outcome, tail, host or socket.gethostname(), folder)
            print(f"From: {sender(folder, config['sender'])}\nTo: {config['to']}\nSubject: {subject}\n\n{body}")
            return 0
        email_id = send_failure(args.name, task, outcome, tail, folder, run, opener, host, root)
    except (Refused, OSError, ValueError, subprocess.TimeoutExpired) as error:
        print(f"alert not sent: {error}", file=sys.stderr)
        return 1
    print(f"alert sent to {config['to']} for {args.name} (SMTP2GO email {email_id})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
