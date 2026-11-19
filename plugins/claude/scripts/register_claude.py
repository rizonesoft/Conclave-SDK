#!/usr/bin/env python3
"""Register (or re-register) every Claude connection plugin in plugins/claude/ with Claude Code at user scope.

    python  <SDK>/plugins/claude/scripts/register_claude.py [--check]     (Windows)
    python3 <SDK>/plugins/claude/scripts/register_claude.py [--check]     (WSL)

Each server is registered as Windows Node running `<SDK>\\plugins\\claude\\<name>\\dist\\server.mjs`, because only
Windows Node can decrypt the plugin's Windows DPAPI credential store: in WSL the command is the `/mnt/c` path of the
same `node.exe` and the bundle keeps its Windows path. The registration goes through the Claude CLI
(`claude mcp remove`, then `claude mcp add-json`), which owns `~/.claude.json`. The CLI takes an entry only as an
argument, so an entry that carries an `env` block is refused and left untouched, never sent or printed: the plugins
read no environment. `--check` writes nothing: it reports each entry that is missing, is not exactly Windows Node
running this checkout's bundle, or runs a missing or stale bundle, and exits 1. `--repair` re-registers only the
entries `fixable` names (wrong or missing, bundle current, no env block) and leaves correct ones alone, so it is safe
to run on every session start or deploy: `global/deploy.py --agent claude` and the session drift hook both use it, and
a moved checkout heals itself. Standard library only.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import build_claude  # beside this file: a caller that imports this module puts its folder on sys.path first

ROOT = build_claude.ROOT
PLUGINS = build_claude.PLUGINS
NODE_WINDOWS = r"C:\Program Files\nodejs\node.exe"
CLI_TIMEOUT = 60  # seconds for one `claude mcp` call, so a hung CLI never holds a repair open


def windows_path(path):
    """The Windows form of a path, or None when it has none: `/mnt/d/a` and `D:/a` are both `D:\\a`."""
    text = str(path).replace("\\", "/")
    mnt = re.match(r"^/mnt/([A-Za-z])(/.*)?$", text)
    if mnt:
        text = "%s:%s" % (mnt.group(1).upper(), mnt.group(2) or "/")
    if not re.match(r"^[A-Za-z]:/", text):
        return None
    return text[0].upper() + text[1:].replace("/", "\\")


def same_path(left, right):
    """Whether two paths name one Windows file, whichever form (drive letter or /mnt) and slash each uses."""
    a, b = windows_path(left), windows_path(right)
    if a is None or b is None:
        return str(left) == str(right)
    return a.lower() == b.lower()


def config_path():
    """The ~/.claude.json the Claude CLI reads and writes: under CLAUDE_CONFIG_DIR when that is set, as the CLI does."""
    named = os.environ.get("CLAUDE_CONFIG_DIR")
    return Path(named) / ".claude.json" if named else Path.home() / ".claude.json"


def node_command():
    """Windows Node as this platform starts it."""
    if os.name == "nt":
        return NODE_WINDOWS
    return "/mnt/c/Program Files/nodejs/node.exe"


def expected_entry(name, root=ROOT):
    bundle = windows_path(Path(root) / name / build_claude.BUNDLE)
    if bundle is None:
        raise SystemExit("%s has no Windows path, and the plugins need Windows Node for their credential store" % root)
    return {"type": "stdio", "command": node_command(), "args": [bundle], "env": {}}


def registered(claude_json):
    """The mcpServers table of a ~/.claude.json, empty when the file is absent."""
    path = Path(claude_json)
    if not path.is_file():
        return {}
    servers = json.loads(path.read_text(encoding="utf-8-sig")).get("mcpServers")
    return servers if isinstance(servers, dict) else {}


def entry_problem(name, entry, claude_json, root=ROOT):
    """What is wrong with one plugin's registration, or None when it is Windows Node running this checkout's bundle."""
    bundle = Path(root) / name / build_claude.BUNDLE
    if not isinstance(entry, dict):
        return "%s is not registered in %s" % (name, claude_json)
    args = entry.get("args")
    args = [str(a) for a in args] if isinstance(args, list) else []
    command = str(entry.get("command", ""))
    # Each field must be in the form its consumer reads: the command is started by this platform (the /mnt/c path in
    # WSL, a drive path on Windows), and the bundle is read by Windows Node (never a /mnt path).
    if entry.get("type", "stdio") != "stdio" or not same_path(command, NODE_WINDOWS) \
            or command.startswith("/mnt/") != (os.name != "nt"):
        return "%s is not run by Windows Node as %s" % (name, node_command())
    if len(args) != 1 or not same_path(args[0], bundle) or args[0].startswith("/mnt/"):
        return "%s does not run %s and nothing else" % (name, windows_path(bundle) or bundle)
    return None


def problems(claude_json, root=ROOT):
    """One line for everything wrong with the plugins' registrations in claude_json or with the bundles they run."""
    found = []
    servers = registered(claude_json)
    for name in PLUGINS:
        entry = servers.get(name)
        wrong = entry_problem(name, entry, claude_json, root)
        if wrong and isinstance(entry, dict) and entry.get("env"):
            wrong += (" (its env block keeps it from being repaired automatically: these plugins read no environment, "
                      "so empty that env block in %s, then run global/deploy.py --agent claude)" % claude_json)
        if wrong:
            found.append(wrong)
        stale = build_claude.stale(Path(root) / name)
        if stale:
            found.append("%s: %s" % (name, stale))
    return found


def blocker(root=ROOT):
    """Why register() cannot run on this machine, or None: the Claude CLI, Windows Node and a Windows path for the
    checkout are all needed."""
    if not shutil.which("claude"):
        return "claude is not on PATH"
    if not os.path.isfile(node_command()):
        return "Windows Node not found at %s" % node_command()
    if windows_path(Path(root)) is None:
        return "%s has no Windows path, and the plugins need Windows Node for their credential store" % root
    return None


def fixable(claude_json, root=ROOT):
    """The plugins whose registration is wrong and that register() can put right without a person: the bundle is
    present and current, and the entry carries no env block (which could not pass through the CLI unseen). Empty when
    blocker() names a reason register() cannot run."""
    if blocker(root):
        return []
    servers = registered(claude_json)
    names = []
    for name in PLUGINS:
        entry = servers.get(name)
        if isinstance(entry, dict) and entry.get("env"):
            continue
        if entry_problem(name, entry, claude_json, root) and not build_claude.stale(Path(root) / name):
            names.append(name)
    return names


def register(claude_json, root=ROOT, names=PLUGINS, only_wrong=False):
    """Register each named plugin through the CLI. With only_wrong, each entry is read again just before it is touched
    and left alone when it is already right (another session repaired it), and a missing entry is only added."""
    reason = blocker(root)
    if reason:
        raise SystemExit(reason)
    claude = shutil.which("claude")
    before = registered(claude_json)
    # The CLI takes an entry only as an argument, which any process listing can read, so an entry that carries an
    # env block is never sent through it: it is left exactly as it is, before anything is removed.
    carrying = [name for name in names if isinstance(before.get(name), dict) and before[name].get("env")]
    if carrying:
        raise SystemExit("%s: the entry has an env block, which cannot pass through the Claude CLI without its values "
                         "showing in a process listing. Nothing was changed. These plugins read no environment: "
                         "empty the env block in %s, then run this again." % (", ".join(carrying), claude_json))
    for name in names:
        entry = expected_entry(name, root)
        if only_wrong:
            now = registered(claude_json).get(name)
            if isinstance(now, dict) and now.get("env"):
                print("left %s: its entry gained an env block" % name)
                continue
            if entry_problem(name, now, claude_json, root) is None:
                continue
        else:
            now = before.get(name)
        if now is not None:
            subprocess.run([claude, "mcp", "remove", name, "-s", "user"], stdin=subprocess.DEVNULL,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=CLI_TIMEOUT)
        done = subprocess.run([claude, "mcp", "add-json", "-s", "user", name, json.dumps(entry)], stdin=subprocess.DEVNULL,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=CLI_TIMEOUT)
        if done.returncode != 0:
            raise SystemExit("claude mcp add-json failed for %s (exit %d)" % (name, done.returncode))
        print("registered %s: %s" % (name, entry["args"][0]))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="write nothing; exit 1 when a registration is wrong")
    mode.add_argument("--repair", action="store_true", help="re-register only the entries that are wrong and fixable")
    args = parser.parse_args(argv)
    claude_json = config_path()
    if args.repair:
        names = fixable(claude_json)
        if names:
            register(claude_json, names=names, only_wrong=True)
    elif not args.check:
        register(claude_json)
    found = problems(claude_json)
    for line in found:
        print("FAIL  %s" % line)
    print("register_claude: %s (%s)" % ("FAIL" if found else "ok", claude_json))
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
