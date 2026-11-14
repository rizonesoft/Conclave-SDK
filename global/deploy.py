#!/usr/bin/env python3
"""Deploy the global Claude Code, Codex, and Antigravity configuration from this checkout to the running user's home.

Everything is located relative to this file, so the Conclave-SDK checkout can live anywhere. Run it once on
Windows and once in WSL. Standard library only.

    python <SDK>/global/deploy.py [--agent claude|codex|agy|all] [--home DIR] [--dry-run] [--check]

Targets (home is the running user's home directory, or --home):
  claude/rules/claude-code.md     -> <home>/.claude/CLAUDE.md
  claude/skills/<name>/           -> <home>/.claude/skills/<name>/   (files copied, destination-only files kept)
  claude/hooks/*                  -> not copied: <home>/.claude/settings.json hook commands are pointed at them
  codex/rules/codex.md            -> <home>/.codex/AGENTS.md
  codex/rules/hooks.json          -> <home>/.codex/hooks.json        (template, placeholders filled in)
  codex/skills/<name>/SKILL.md    -> <home>/.agents/skills/<name>/
  ../plugins/agy/<name>/          -> <home>/.gemini/config/plugins/<name>/ (mirrored; hooks.json and DEPLOYED_FROM rendered)

A file whose content is identical is left alone. A differing file is copied to
<home>/.conclave/global-backups/<UTC timestamp>/<path relative to home> before it is replaced.
"""
import argparse
import importlib.util
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

GLOBAL = Path(__file__).resolve().parent
HOOK_SCRIPTS = ("article_rules.py", "layer_rules.py", "article_check.py")
SKIP_DIRS = {"__pycache__"}
SKIP_SUFFIXES = {".pyc", ".pyo"}


class Refusal(Exception):
    """A condition under which nothing may be written."""


# ---- pure helpers -----------------------------------------------------------------------------------------

def path_forms(hooks_dir):
    """Return (posix, windows) forms of a hooks folder given as a Windows path or a POSIX path.

    `X:\\a\\b` is `/mnt/x/a/b` in WSL and `/mnt/x/a/b` is `X:/a/b`. A path with no such mapping (a pure Linux
    path) is used unchanged for both forms. The Windows form always uses forward slashes.
    """
    text = str(hooks_dir)
    drive = re.match(r"^([A-Za-z]):(?:[\\/]+(.*))?$", text)
    if drive:
        rest = (drive.group(2) or "").replace("\\", "/").strip("/")
        letter = drive.group(1)
        return ("/mnt/%s/%s" % (letter.lower(), rest)).rstrip("/"), ("%s:/%s" % (letter.upper(), rest)).rstrip("/")
    mnt = re.match(r"^/mnt/([A-Za-z])(?:/(.*))?$", text)
    if mnt:
        rest = (mnt.group(2) or "").strip("/")
        return text.rstrip("/"), ("%s:/%s" % (mnt.group(1).upper(), rest)).rstrip("/")
    posix = text.replace("\\", "/").rstrip("/")
    return posix, posix


def render_codex_hooks(template, hooks_dir, python_windows):
    """Fill {HOOKS}, {HOOKS_WINDOWS} and {PYTHON_WINDOWS} in the template text; the result must be valid JSON."""
    posix, windows = path_forms(hooks_dir)

    def esc(value):
        return json.dumps(value)[1:-1]

    out = (template.replace("{HOOKS_WINDOWS}", esc(windows))
           .replace("{PYTHON_WINDOWS}", esc(python_windows))
           .replace("{HOOKS}", esc(posix)))
    if "{HOOKS" in out or "{PYTHON_WINDOWS" in out:
        raise Refusal("Unfilled placeholder left in the generated hooks.json")
    json.loads(out)
    return out


def python_token(path):
    """An interpreter path as it sits at the start of a command string."""
    path = str(path).replace("\\", "/")
    return '"%s"' % path if " " in path else path


def existing_windows_python(hooks_json_text):
    """The interpreter the deployed hooks.json uses in its commandWindows entries, or None."""
    try:
        data = json.loads(hooks_json_text)
    except ValueError:
        return None
    for groups in (data.get("hooks") or {}).values():
        for group in groups:
            for hook in group.get("hooks", []):
                match = re.match(r'^\s*("[^"]+"|\S+)\s', hook.get("commandWindows") or "")
                if match:
                    return match.group(1).strip('"')
    return None


def rewrite_hook_command(command, hooks_dir_posix):
    """Replace the quoted path of a hook script in a command; everything else stays as it is."""
    def swap(match):
        return '"%s/%s"' % (hooks_dir_posix, match.group(1))

    return re.sub(r'"[^"]*[\\/](%s)"' % "|".join(re.escape(s) for s in HOOK_SCRIPTS), swap, command)


def rewrite_settings(data, hooks_dir_posix):
    """Rewrite the hook commands of a parsed settings.json in place. Returns the number of commands changed."""
    changed = 0

    def walk(node):
        nonlocal changed
        if isinstance(node, dict):
            command = node.get("command")
            if isinstance(command, str) and any(s in command for s in HOOK_SCRIPTS):
                new = rewrite_hook_command(command, hooks_dir_posix)
                if new != command:
                    node["command"] = new
                    changed += 1
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(data.get("hooks", {}) if isinstance(data, dict) else {})
    return changed


def has_hook_commands(data):
    found = []

    def walk(node):
        if isinstance(node, dict):
            command = node.get("command")
            if isinstance(command, str) and any(s in command for s in HOOK_SCRIPTS):
                found.append(command)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(data.get("hooks", {}) if isinstance(data, dict) else {})
    return bool(found)


# ---- writing ----------------------------------------------------------------------------------------------

class Deployer:
    def __init__(self, home, dry_run):
        self.home = Path(home).resolve()  # a relative --home must name one folder for every step and child process
        self.dry_run = dry_run
        self.stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.results = []

    def atomic_write(self, dest, data):
        dest.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(dest.parent), prefix=".deploy-", suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
            os.replace(tmp, dest)
        except BaseException:
            if os.path.exists(tmp):
                os.unlink(tmp)
            raise

    def put(self, dest, data):
        """Write bytes to dest. Returns created, updated or unchanged."""
        if dest.exists():
            old = dest.read_bytes()
            if old == data:
                return "unchanged"
            if not self.dry_run:
                backup = self.home / ".conclave" / "global-backups" / self.stamp / dest.relative_to(self.home)
                self.atomic_write(backup, old)
                self.atomic_write(dest, data)
            return "updated"
        if not self.dry_run:
            self.atomic_write(dest, data)
        return "created"

    def record(self, label, status):
        self.results.append((label, status))
        print("%s: %s" % (status, label))

    def deploy_file(self, src, dest):
        self.record(self.shown(dest), self.put(dest, src.read_bytes()))

    def prune(self, dest, root_dir):
        """Back up and remove an orphan file inside a mirrored folder. Returns updated."""
        if not self.dry_run:
            backup = self.home / ".conclave" / "global-backups" / self.stamp / dest.relative_to(self.home)
            self.atomic_write(backup, dest.read_bytes())
            dest.unlink()
            parent = dest.parent
            while parent != root_dir and parent.is_dir():
                try:
                    parent.rmdir()
                except OSError:
                    break
                parent = parent.parent
        return "updated"

    def deploy_tree(self, src_dir, dest_dir):
        statuses = []
        count = 0
        for src in sorted(p for p in src_dir.rglob("*") if p.is_file()):
            rel = src.relative_to(src_dir)
            if SKIP_DIRS & set(rel.parts) or src.suffix in SKIP_SUFFIXES:
                continue
            statuses.append(self.put(dest_dir / rel, src.read_bytes()))
            count += 1
        if all(s == "unchanged" for s in statuses):
            status = "unchanged"
        elif all(s == "created" for s in statuses):
            status = "created"
        else:
            status = "updated"
        self.record("%s (%d files)" % (self.shown(dest_dir), count), status)

    def shown(self, path):
        try:
            return "~/" + path.relative_to(self.home).as_posix()
        except ValueError:
            return str(path)

    def skip(self, label, reason):
        self.results.append((label, "skipped"))
        print("skipped: %s: %s" % (label, reason))


def read_settings(path):
    """Parse settings.json, or return None when absent. Raises Refusal when it is not valid JSON."""
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=dict)
    except ValueError as exc:
        raise Refusal("%s is not valid JSON (%s); nothing was written" % (path, exc))


def deploy_claude(dep):
    root = GLOBAL / "claude"
    home = dep.home
    settings_path = home / ".claude" / "settings.json"
    settings = read_settings(settings_path)  # may raise, before anything is written
    dep.deploy_file(root / "rules" / "claude-code.md", home / ".claude" / "CLAUDE.md")
    skills = root / "skills"
    for folder in sorted(p for p in skills.iterdir() if p.is_dir()) if skills.is_dir() else []:
        dep.deploy_tree(folder, home / ".claude" / "skills" / folder.name)
    label = "~/.claude/settings.json (hook paths)"
    if settings is None:
        dep.skip(label, "file not found, hook entries are not invented")
    elif not has_hook_commands(settings):
        dep.skip(label, "no article_rules, layer_rules or article_check hook command found")
    else:
        hooks_posix = (root / "hooks").as_posix()
        if rewrite_settings(settings, hooks_posix):
            text = json.dumps(settings, indent=2, ensure_ascii=False) + "\n"
            dep.record(label, dep.put(settings_path, text.encode("utf-8")))
        else:
            dep.record(label, "unchanged")


def deploy_codex(dep):
    root = GLOBAL / "codex"
    home = dep.home
    dep.deploy_file(root / "rules" / "codex.md", home / ".codex" / "AGENTS.md")
    hooks_path = home / ".codex" / "hooks.json"
    if os.name == "nt":
        python = python_token(sys.executable)
    else:
        python = "python"
        if hooks_path.is_file():
            current = existing_windows_python(hooks_path.read_text(encoding="utf-8-sig"))
            if current:
                python = python_token(current)
    template = (root / "rules" / "hooks.json").read_text(encoding="utf-8")
    text = render_codex_hooks(template, str(root / "hooks"), python)
    dep.record("~/.codex/hooks.json (generated)", dep.put(hooks_path, text.encode("utf-8")))
    trust_codex_hooks(dep, hooks_path)
    skills = root / "skills"
    for folder in sorted(p for p in skills.iterdir() if p.is_dir()) if skills.is_dir() else []:
        if (folder / "SKILL.md").is_file():
            dep.deploy_tree(folder, home / ".agents" / "skills" / folder.name)


TRUST_SCRIPT = GLOBAL.parent / "kits" / "todo" / "templates" / "scripts" / "codex-hook-trust.py"


def _trust_module():
    """The todo kit's codex-hook-trust.py from this checkout: the one Codex app-server client the SDK keeps."""
    spec = importlib.util.spec_from_file_location("deploy_codex_hook_trust", TRUST_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _ours(hook, hooks_path):
    """A hook this deploy wrote: a user hook from the deployed hooks.json whose command runs a script under
    global/codex/hooks."""
    try:
        same = os.path.normcase(os.path.realpath(str(hook.get("sourcePath", "")))) == \
            os.path.normcase(os.path.realpath(str(hooks_path)))
    except (OSError, ValueError):
        same = False
    return hook.get("source") == "user" and same and "global/codex/hooks/" in str(hook.get("command", "")).replace("\\", "/")


def trust_codex_hooks(dep, hooks_path):
    """Approve in Codex the hooks this deploy wrote. Codex runs a hook only once its current hash is approved
    (`hooks.state` in the home's config.toml), and a changed hooks.json reads `modified`, so a deploy that does not
    approve what it wrote leaves its hooks skipped. The approval goes through Codex's own app-server (`hooks/list`,
    then `config/value/write`), against this deploy's home (`CODEX_HOME`), never another. A hook the operator
    disabled stays disabled. Each hook is reported: approved, trusted, disabled, or not approved with the reason."""
    if dep.dry_run:
        dep.skip("codex hook approval", "dry run")
        return
    try:
        trust = _trust_module()
    except (OSError, ImportError, SyntaxError) as exc:
        dep.skip("codex hook approval", "cannot load %s: %s" % (TRUST_SCRIPT, exc))
        return
    codex_home = hooks_path.parent
    try:
        hooks = [hook for hook in trust.list_hooks(dep.home, codex_home) if _ours(hook, hooks_path)]
    except (trust.TrustError, OSError) as exc:
        dep.skip("codex hook approval", str(exc))
        return
    if not hooks:
        dep.skip("codex hook approval", "Codex lists none of the deployed hooks")
        return
    pending = []
    for hook in hooks:
        label = "codex hook %s" % hook.get("key")
        if hook.get("enabled", True) is False:
            dep.skip(label, "disabled in Codex, left disabled")
        elif hook.get("trustStatus") == "trusted":
            dep.record(label, "unchanged")
        else:
            pending.append(hook)
    for hook in pending:
        label = "codex hook %s" % hook.get("key")
        try:
            trust.approve_hooks(dep.home, [hook], codex_home)
        except (trust.TrustError, OSError) as exc:
            dep.skip(label, "not approved: %s (run the deploy again to retry)" % exc)
            continue
        dep.record(label + " (approved)", "updated")


def render_agy_hooks(hooks_json_text, python_cmd):
    """Rewrite hooks/powertools_hook.py commands in an Antigravity hooks.json for python_cmd."""
    data = json.loads(hooks_json_text)

    def walk(node):
        if isinstance(node, dict):
            command = node.get("command")
            if isinstance(command, str) and "hooks/powertools_hook.py" in command:
                node["command"] = "%s hooks/powertools_hook.py" % python_cmd
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(data)
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def render_agy_hook_script(script_text, agy_source_posix):
    """Stamp DEPLOYED_FROM with agy_source_posix in powertools_hook.py."""
    replacement = "DEPLOYED_FROM = %s" % json.dumps(str(agy_source_posix))
    new_text, count = re.subn(r"^DEPLOYED_FROM = .*$", lambda _m: replacement, script_text, count=1, flags=re.M)
    if count != 1:
        raise Refusal("Missing DEPLOYED_FROM assignment in powertools_hook.py")
    return new_text


def deploy_agy(dep):
    agy_root = GLOBAL.parent / "plugins" / "agy"
    if not agy_root.is_dir():
        return
    py = python_token(sys.executable) if os.name == "nt" else "python3"
    agy_source_posix = agy_root.as_posix()
    for folder in sorted(p for p in agy_root.iterdir() if p.is_dir() and (p / "plugin.json").is_file()):
        dest_dir = dep.home / ".gemini" / "config" / "plugins" / folder.name
        expected = {}
        for src in sorted(p for p in folder.rglob("*") if p.is_file()):
            rel = src.relative_to(folder)
            if SKIP_DIRS & set(rel.parts) or src.suffix in SKIP_SUFFIXES:
                continue
            if rel == Path("hooks.json"):
                data = render_agy_hooks(src.read_text(encoding="utf-8"), py).encode("utf-8")
            elif rel == Path("hooks") / "powertools_hook.py":
                data = render_agy_hook_script(src.read_text(encoding="utf-8"), agy_source_posix).encode("utf-8")
            else:
                data = src.read_bytes()
            expected[rel] = data

        statuses = [dep.put(dest_dir / rel, data) for rel, data in sorted(expected.items())]
        if dest_dir.is_dir():
            for existing in sorted(p for p in dest_dir.rglob("*") if p.is_file()):
                rel = existing.relative_to(dest_dir)
                if SKIP_DIRS & set(rel.parts) or existing.suffix in SKIP_SUFFIXES:
                    continue
                if rel not in expected:
                    statuses.append(dep.prune(existing, dest_dir))

        if all(s == "unchanged" for s in statuses):
            status = "unchanged"
        elif all(s == "created" for s in statuses):
            status = "created"
        else:
            status = "updated"
        dep.record("%s (%d files)" % (dep.shown(dest_dir), len(expected)), status)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--agent", choices=("claude", "codex", "agy", "all"), default="all")
    parser.add_argument("--home", help="deploy to this directory instead of the user's home")
    parser.add_argument("--dry-run", action="store_true", help="report what would change and write nothing")
    parser.add_argument("--check", action="store_true", help="verify deployed files match this checkout and exit 1 on drift")
    args = parser.parse_args(argv)
    home = Path(args.home) if args.home else Path.home()
    dep = Deployer(home, args.dry_run or args.check)
    try:
        if args.agent in ("claude", "all"):
            deploy_claude(dep)
        if args.agent in ("codex", "all"):
            deploy_codex(dep)
        if args.agent in ("agy", "all"):
            deploy_agy(dep)
    except Refusal as exc:
        print("refused: %s" % exc, file=sys.stderr)
        return 2
    counts = {}
    for _, status in dep.results:
        counts[status] = counts.get(status, 0) + 1
    summary = ", ".join("%d %s" % (counts.get(k, 0), k) for k in ("created", "updated", "unchanged", "skipped"))
    if args.check:
        drifted = counts.get("created", 0) + counts.get("updated", 0)
        print("%s: %s" % ("drift detected" if drifted else "in sync", summary))
        return 1 if drifted else 0
    print("%s%s" % ("dry run, nothing written: " if args.dry_run else "", summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
