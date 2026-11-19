#!/usr/bin/env python3
"""UserPromptSubmit hook: once per session, warn when the live Claude Code setup has drifted from this checkout.

On the first prompt of a session, inside a three second budget, it checks that:
- the deployed `~/.claude` files match `global/claude` (`global/deploy.py --agent claude --check`);
- `~/.claude.json` registers each Claude connection plugin as Windows Node running `plugins/claude/<name>/dist/server.mjs`
  of this checkout, and each bundle exists and was built from the sources `src/` now holds
  (`plugins/claude/scripts/register_claude.py`, which owns those rules).

A registration that points elsewhere (a moved or retired checkout, a missing entry) and whose bundle is current is
repaired, not only reported: the hook starts `register_claude.py --repair` as a detached process, so a slow `claude`
CLI never holds the prompt and is never cut off between its remove and its add. Its output goes to a new
`repair-*.log` beside the session markers, and the repaired servers connect from the next session; the next session's
check reports anything the repair could not do. `CLAUDE_DRIFT_REPAIR=0` turns the repair off and leaves only the
warning. The hook runs from the checkout `~/.claude/settings.json` names, so after moving the checkout run
`global/deploy.py --agent claude` from its new place once: that re-points the hooks and re-registers the plugins.

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
    """Lines for connection plugins registered elsewhere, or running a missing or stale bundle, and the plugins
    `register_claude.py --repair` would put right."""
    if not os.path.isfile(os.path.join(PLUGIN_SCRIPTS, "register_claude.py")):
        return ["%s is missing" % os.path.join(PLUGIN_SCRIPTS, "register_claude.py")], []
    register_claude = plugin_module()
    found = register_claude.problems(claude_json)
    return found, (register_claude.fixable(claude_json) if found else [])


def plugin_module():
    if PLUGIN_SCRIPTS not in sys.path:
        sys.path.insert(0, PLUGIN_SCRIPTS)
    import register_claude
    return register_claude


def claude_json_path(home=None):
    """The ~/.claude.json the Claude CLI uses (CLAUDE_CONFIG_DIR when set), or the one in a given test home."""
    if home:
        return os.path.join(str(home), ".claude.json")
    return str(plugin_module().config_path())


def start_repair(names):
    """Start `register_claude.py --repair` detached, its output in a new log beside the session markers; the log's path
    (None when no folder takes one), or False when nothing was started."""
    if not names or os.environ.get("CLAUDE_DRIFT_REPAIR", "1") == "0":
        return False
    log = path = None
    for folder in marker_dirs():
        try:
            os.makedirs(folder, exist_ok=True)
            fd, path = tempfile.mkstemp(prefix="repair-", suffix=".log", dir=folder)  # a new file: never a symlink
            log = os.fdopen(fd, "w", encoding="utf-8")
            break
        except OSError:
            continue
    options = {"stdin": subprocess.DEVNULL, "stdout": log or subprocess.DEVNULL, "stderr": subprocess.STDOUT}
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        options["start_new_session"] = True
    try:
        subprocess.Popen([sys.executable, os.path.join(PLUGIN_SCRIPTS, "register_claude.py"), "--repair"], **options)
    finally:
        if log:
            log.close()
    return path


def survey(home=None, deadline=None, repair=False):
    """Every drift line, the plugins a repair was started for, and its log. With repair, the detached repair is started
    here, inside the bounded check, so its log setup is charged to the budget too."""
    deadline = time.monotonic() + BUDGET if deadline is None else deadline
    found, names = plugin_drift(claude_json_path(home))  # milliseconds, so the deploy check gets the rest
    repairing, log = [], None
    if repair and names:
        try:
            log = start_repair(names)
            if log is not False:
                repairing = names
        except Exception as exc:
            found.append("the repair did not start: %s: %s" % (type(exc).__name__, exc))
    return found + deploy_drift(deadline, home), repairing, log


def check(home=None, deadline=None):
    return survey(home, deadline)[0]


def bounded_check(budget=BUDGET, run=check, wrap=lambda lines: lines):
    """The checks, abandoned at the budget: a slow disk or an unreadable file costs a prompt no more than that. A
    failure or a timeout gives wrap(lines), so a run returning more than lines can say what the rest is then."""
    done = []

    def work():
        try:
            done.append(run(deadline=time.monotonic() + budget))
        except Exception as exc:
            done.append(wrap(["the drift check failed: %s: %s" % (type(exc).__name__, exc)]))

    worker = threading.Thread(target=work, daemon=True)  # a daemon thread never holds the process open
    worker.start()
    worker.join(budget)
    return done[0] if done else wrap(["the drift check did not finish inside %g seconds: run it by hand" % budget])


def message(problems, repairing=(), log=None):
    lines = ["Conclave setup drift (checked once per session). Tell the user in one line and carry on with their request:"]
    lines += ["- %s" % p for p in problems]
    if repairing:
        lines.append("A repair was started: re-registering %s from this checkout, so they connect from the next "
                     "session; the next session's check reports anything it could not do%s."
                     % (", ".join(repairing), " (its output: %s)" % log if log else ""))
    if len(problems) > len(repairing):
        lines.append("Repair: python %s --agent claude (it also re-registers the plugins); "
                     "build_claude.py in %s rebuilds a stale bundle." % (DEPLOY, PLUGIN_SCRIPTS))
    return "\n".join(lines)


def main():
    try:
        data = json.load(sys.stdin)
    except ValueError:
        data = {}
    if not first_prompt(str(data.get("session_id") or "")):
        return 0
    problems, repairing, log = bounded_check(run=lambda deadline: survey(deadline=deadline, repair=True),
                                             wrap=lambda lines: (lines, [], None))
    if problems:
        text = message(problems, repairing, log)
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": text}}))
        print(text, file=sys.stderr)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # a drift check must never stop a prompt
        print("session_drift_check: %s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        sys.exit(0)
