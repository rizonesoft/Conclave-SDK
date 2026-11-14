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
running this checkout's bundle, or runs a missing or stale bundle, and exits 1. Standard library only.
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
RETIRED = "r:/bin/claude"  # the retired checkout these servers used to run from


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


def problems(claude_json, root=ROOT):
    """One line for everything wrong with the plugins' registrations in claude_json or with the bundles they run."""
    found = []
    servers = registered(claude_json)
    for name in PLUGINS:
        entry = servers.get(name)
        bundle = Path(root) / name / build_claude.BUNDLE
        if not isinstance(entry, dict):
            found.append("%s is not registered in %s" % (name, claude_json))
        else:
            args = entry.get("args")
            args = [str(a) for a in args] if isinstance(args, list) else []
            words = [str(entry.get("command", ""))] + args
            if any(RETIRED in (windows_path(w) or w).replace("\\", "/").lower() for w in words):
                found.append("%s still runs from R:\\Bin\\claude" % name)
            elif entry.get("type", "stdio") != "stdio" or not same_path(words[0], NODE_WINDOWS):
                found.append("%s is not run by Windows Node (%s)" % (name, NODE_WINDOWS))
            elif len(args) != 1 or not same_path(args[0], bundle):
                found.append("%s does not run %s and nothing else" % (name, bundle))
        stale = build_claude.stale(Path(root) / name)
        if stale:
            found.append("%s: %s" % (name, stale))
    return found


def register(claude_json, root=ROOT):
    claude = shutil.which("claude")
    if not claude:
        raise SystemExit("claude is not on PATH")
    node = node_command()
    if not os.path.isfile(node):
        raise SystemExit("Windows Node not found at %s" % node)
    before = registered(claude_json)
    # The CLI takes an entry only as an argument, which any process listing can read, so an entry that carries an
    # env block is never sent through it: it is left exactly as it is, before anything is removed.
    carrying = [name for name in PLUGINS if isinstance(before.get(name), dict) and before[name].get("env")]
    if carrying:
        raise SystemExit("%s: the entry has an env block, which cannot pass through the Claude CLI without its values "
                         "showing in a process listing. Nothing was changed. These plugins read no environment: "
                         "empty the env block in %s, then run this again." % (", ".join(carrying), claude_json))
    for name in PLUGINS:
        entry = expected_entry(name, root)
        subprocess.run([claude, "mcp", "remove", name, "-s", "user"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        done = subprocess.run([claude, "mcp", "add-json", "-s", "user", name, json.dumps(entry)],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if done.returncode != 0:
            raise SystemExit("claude mcp add-json failed for %s (exit %d)" % (name, done.returncode))
        print("registered %s: %s" % (name, entry["args"][0]))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="write nothing; exit 1 when a registration is wrong")
    args = parser.parse_args(argv)
    claude_json = Path.home() / ".claude.json"
    if not args.check:
        register(claude_json)
    found = problems(claude_json)
    for line in found:
        print("FAIL  %s" % line)
    print("register_claude: %s (%s)" % ("FAIL" if found else "ok", claude_json))
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
