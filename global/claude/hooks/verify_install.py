#!/usr/bin/env python3
"""Prove the global hooks are installed and apply in the given repositories. Run after any change to the hooks, to
~/.claude/settings.json or to a repository's own hook settings, on Windows and on WSL:

    python  <SDK>/global/claude/hooks/verify_install.py <path-to-repo>
    python3 <SDK>/global/claude/hooks/verify_install.py ~/www/rizonetech-com

With no arguments it checks the repositories listed in verify-repos.txt beside this file that exist in this
environment. It never writes to a repository. Exit 1 on any FAIL.

Checks:
- ~/.claude/settings.json runs both hooks on every event they need, from this folder.
- No managed settings file and no repository settings file sets disableAllHooks, and managed settings do not set
  allowManagedHooksOnly (either would silently switch the global hooks off).
- Replayed from inside each repository: the article hook routes a draft to the right checker, and the layer hook
  warns on an added masking pattern and asks for the Layer line at the end of the turn.
"""
import json
import os
import re
import subprocess
import sys
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import article_rules  # noqa: E402
import layer_rules  # noqa: E402

REQUIRED = [
    ("UserPromptSubmit", None, "article_rules.py"),
    ("UserPromptSubmit", None, "layer_rules.py"),
    ("PreToolUse", "Bash", "article_rules.py"),
    ("PreToolUse", "Write", "layer_rules.py"),
    ("PreToolUse", "Edit", "layer_rules.py"),
    ("PreToolUse", "MultiEdit", "layer_rules.py"),
    ("PostToolUse", "Write", "article_rules.py"),
    ("PostToolUse", "Edit", "article_rules.py"),
    ("PostToolUse", "Write", "layer_rules.py"),
    ("PostToolUse", "Edit", "layer_rules.py"),
    ("PostToolUse", "MultiEdit", "layer_rules.py"),
    ("Stop", None, "layer_rules.py"),
]
MANAGED = [r"C:\Program Files\ClaudeCode\managed-settings.json", r"C:\ProgramData\ClaudeCode\managed-settings.json",
           "/etc/claude-code/managed-settings.json"]


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def matches(matcher, tool):
    if tool is None or matcher in (None, "", "*"):
        return True
    return tool in matcher.split("|")


def script_path(command, script):
    """The path of `script` in a hook command, if the command runs it from this folder."""
    for part in re.findall(r'"([^"]+)"|(\S+)', command):
        candidate = (part[0] or part[1]).replace("\\", "/")
        if candidate.endswith("/" + script):
            return candidate
    return None


def check_wiring(settings):
    """FAIL lines for every required (event, tool, script) the settings do not run from this folder."""
    problems = []
    hooks = settings.get("hooks", {})
    for event, tool, script in REQUIRED:
        found = False
        for group in hooks.get(event, []):
            if not matches(group.get("matcher"), tool):
                continue
            for hook in group.get("hooks", []):
                path = script_path(hook.get("command", ""), script)
                if path and os.path.isfile(path) and os.path.samefile(os.path.dirname(path), HERE):
                    found = True
        if not found:
            problems.append(f"{event} {tool or '*'} does not run {script} from {HERE}")
    return problems


def check_switches(paths, keys):
    problems = []
    for path in paths:
        if os.path.isfile(path):
            data = load(path)
            problems += [f"{path} sets {k}" for k in keys if data.get(k)]
    return problems


def run_hook(script, payload, cwd):
    out = subprocess.run([sys.executable, os.path.join(HERE, script)], input=json.dumps(payload), cwd=cwd,
                         capture_output=True, text=True, encoding="utf-8")
    return json.loads(out.stdout) if out.stdout.strip() else None


def replay(repo):
    """FAIL lines for the hooks' behaviour inside `repo`. Nothing is written to the repository."""
    problems = []
    draft = os.path.join(repo, "drafts", "verify-install.md")
    if not article_rules.is_draft(draft):
        problems.append(f"{draft} is not treated as a draft")
    checker = article_rules.repo_checker(draft)
    print(f"INFO  {repo}: drafts go to the {'repository' if checker else 'global'} article checker")
    prompt = run_hook("article_rules.py", {"hook_event_name": "UserPromptSubmit", "prompt": "Rewrite the blog post"}, repo)
    if not prompt:
        problems.append(f"{repo}: an article prompt gets no writing rules")
    session = "verify-" + uuid.uuid4().hex
    edit = {"session_id": session, "tool_name": "Edit", "cwd": repo,
            "tool_input": {"file_path": os.path.join(repo, "verify-install.php"), "old_string": "", "new_string": "ob_start();"}}
    try:
        warned = run_hook("layer_rules.py", {"hook_event_name": "PreToolUse", **edit}, repo)
        run_hook("layer_rules.py", {"hook_event_name": "PostToolUse", **edit}, repo)
        stopped = run_hook("layer_rules.py", {"hook_event_name": "Stop", "session_id": session, "cwd": repo,
                                              "stop_hook_active": True, "last_assistant_message": "Done."}, repo)
    finally:
        layer_rules.clear_state(session)
    if not warned:
        problems.append(f"{repo}: an added ob_start( is not flagged")
    if not stopped or stopped.get("decision") != "block":
        problems.append(f"{repo}: a turn that changed code is not asked for the Layer line")
    return problems


def repos_from_args(argv):
    if argv:
        return [os.path.expanduser(a) for a in argv]
    listed = os.path.join(HERE, "verify-repos.txt")
    names = [line.strip() for line in open(listed, encoding="utf-8") if line.strip() and not line.startswith("#")]
    return [p for p in (os.path.expanduser(n) for n in names) if os.path.isdir(p)]


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    argv = sys.argv[1:] if argv is None else argv
    settings_path = os.path.expanduser("~/.claude/settings.json")
    problems = check_wiring(load(settings_path))
    problems += check_switches(MANAGED, ("disableAllHooks", "allowManagedHooksOnly"))
    repos = repos_from_args(argv)
    for repo in repos:
        problems += check_switches([os.path.join(repo, ".claude", n) for n in ("settings.json", "settings.local.json")],
                                   ("disableAllHooks",))
        problems += replay(repo)
    for p in problems:
        print(f"FAIL  {p}")
    print(f"verify_install: {'FAIL' if problems else 'ok'} ({settings_path}; {len(repos)} repositories: "
          f"{', '.join(repos) or 'none'})")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
