#!/usr/bin/env python3
"""UserPromptSubmit hook: once per session, warn when the live Claude Code setup has drifted from this checkout.

On the first prompt of a session, inside a three second budget, it checks that:
- the deployed `~/.claude` files match `global/claude` (`global/deploy.py --agent claude --check`);
- `~/.claude.json` registers each Claude connection plugin from `plugins/claude` of this checkout, never from the
  retired `R:\\Bin\\claude`, and each `dist/server.mjs` exists and was built from the sources `src/` now holds
  (`plugins/claude/scripts/register_claude.py`, which owns those rules).

It prints nothing when all is well. On drift it adds a short warning to the prompt's context and to stderr. It never
blocks a prompt: any failure of its own is one stderr line and exit 0. The session is remembered by an empty marker
file in `R:\\scratch\\claude-drift` (`/mnt/r/scratch/claude-drift` in WSL), or the temporary folder where `R:` is
absent; `CLAUDE_DRIFT_DIR` names another folder. Standard library only.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SDK = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
DEPLOY = os.path.join(SDK, "global", "deploy.py")
PLUGIN_SCRIPTS = os.path.join(SDK, "plugins", "claude", "scripts")
BUDGET = 3.0


def marker_dirs():
    """Where session markers go, best first."""
    named = os.environ.get("CLAUDE_DRIFT_DIR")
    if named:
        return [named]
    scratch = r"R:\scratch" if os.name == "nt" else "/mnt/r/scratch"
    dirs = [os.path.join(scratch, "claude-drift")] if os.path.isdir(scratch) else []
    return dirs + [os.path.join(tempfile.gettempdir(), "claude-drift")]


def first_prompt(session):
    """True exactly once per session: creating the marker is the test, so two prompts cannot both win."""
    name = re.sub(r"[^\w.-]", "_", session or "default")
    for folder in marker_dirs():
        try:
            os.makedirs(folder, exist_ok=True)
            os.close(os.open(os.path.join(folder, name), os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            return True
        except FileExistsError:
            return False
        except OSError:
            continue
    return False


def deploy_drift(deadline, home=None):
    """Lines for deployed files that differ from global/claude."""
    command = [sys.executable, DEPLOY, "--agent", "claude", "--check"] + (["--home", str(home)] if home else [])
    try:
        done = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True, text=True,
                              encoding="utf-8", errors="replace",
                              timeout=max(0.1, deadline - time.monotonic()))
    except subprocess.TimeoutExpired:
        return ["the deploy check did not finish inside %g seconds: run it by hand" % BUDGET]
    if done.returncode == 0:
        return []
    drifted = [line.split(": ", 1)[1] for line in done.stdout.splitlines() if line.startswith(("created: ", "updated: "))]
    if drifted:
        return ["deployed files differ from global/claude: %s" % ", ".join(drifted)]
    reason = (done.stderr.strip().splitlines() or ["exit %d" % done.returncode])[-1]
    return ["the deploy check failed: %s" % reason]


def plugin_drift(claude_json):
    """Lines for connection plugins registered elsewhere, or running a missing or stale bundle."""
    if not os.path.isfile(os.path.join(PLUGIN_SCRIPTS, "register_claude.py")):
        return ["%s is missing" % os.path.join(PLUGIN_SCRIPTS, "register_claude.py")]
    if PLUGIN_SCRIPTS not in sys.path:
        sys.path.insert(0, PLUGIN_SCRIPTS)
    import register_claude
    return register_claude.problems(claude_json)


def check(home=None, deadline=None):
    deadline = time.monotonic() + BUDGET if deadline is None else deadline
    claude_json = os.path.join(str(home) if home else os.path.expanduser("~"), ".claude.json")
    problems = plugin_drift(claude_json)  # milliseconds, so the slower deploy check gets the rest of the budget
    return problems + deploy_drift(deadline, home)


def bounded_check(budget=BUDGET, run=check):
    """The checks, abandoned at the budget: a slow disk or an unreadable file costs a prompt no more than that."""
    done = []

    def work():
        try:
            done.append(run(deadline=time.monotonic() + budget))
        except Exception as exc:
            done.append(["the drift check failed: %s: %s" % (type(exc).__name__, exc)])

    worker = threading.Thread(target=work, daemon=True)  # a daemon thread never holds the process open
    worker.start()
    worker.join(budget)
    return done[0] if done else ["the drift check did not finish inside %g seconds: run it by hand" % budget]


def message(problems):
    lines = ["Conclave setup drift (checked once per session). Tell the user in one line and carry on with their request:"]
    lines += ["- %s" % p for p in problems]
    lines.append("Repair: python %s --agent claude, then python %s (build_claude.py beside it rebuilds a stale bundle)."
                 % (DEPLOY, os.path.join(PLUGIN_SCRIPTS, "register_claude.py")))
    return "\n".join(lines)


def main():
    try:
        data = json.load(sys.stdin)
    except ValueError:
        data = {}
    if not first_prompt(str(data.get("session_id") or "")):
        return 0
    problems = bounded_check()
    if problems:
        text = message(problems)
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": text}}))
        print(text, file=sys.stderr)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # a drift check must never stop a prompt
        print("session_drift_check: %s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        sys.exit(0)
