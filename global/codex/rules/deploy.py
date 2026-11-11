"""Preview or install the global Codex instructions and Codex-owned hook definitions."""
import argparse
import copy
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

SOURCE = Path(__file__).resolve().parent


def merge_hooks(existing, desired):
    """Replace exact Codex-owned definitions and preserve all other handlers."""
    merged = copy.deepcopy(existing)
    events = merged.setdefault("hooks", {})
    for event, groups in list(events.items()):
        kept = []
        for group in groups:
            retained = []
            for handler in group["hooks"]:
                ours = any(group.get("matcher") == wanted.get("matcher")
                           and handler in wanted["hooks"]
                           for wanted in desired["hooks"].get(event, []))
                if not ours:
                    retained.append(handler)
            if retained:
                kept.append({**group, "hooks": retained})
        events[event] = kept
    for event, groups in desired["hooks"].items():
        events.setdefault(event, []).extend(copy.deepcopy(groups))
    return merged


def write_if_changed(path, content):
    if path.exists() and path.read_bytes() == content:
        print(f"Unchanged: {path}")
        return
    if path.exists():
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        backup = path.with_name(path.name + "." + stamp + ".bak")
        shutil.copy2(path, backup)
        print(f"Backup: {backup}")
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    if path.read_bytes() != content:
        raise RuntimeError(f"Read-back mismatch: {path}")
    print(f"Installed: {path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write after preflight; default is preview only")
    args = parser.parse_args()
    target = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).resolve()
    override = target / "AGENTS.override.md"
    if override.exists() and override.read_text(encoding="utf-8").strip():
        raise SystemExit(f"Active global override needs review: {override}")
    hook_source = SOURCE / "hooks"
    for name in ("article_rules.py", "article_check.py", "layer_rules.py"):
        if not (hook_source / name).is_file():
            raise SystemExit(f"Missing Codex hook dependency: {hook_source / name}")
    if os.name == "nt" and not Path("C:/Python314/python.exe").is_file():
        raise SystemExit("Update commandWindows in hooks.json for the installed Python path")
    desired = json.loads((SOURCE / "hooks.json").read_text(encoding="utf-8"))
    hook_path = target / "hooks.json"
    existing = json.loads(hook_path.read_text(encoding="utf-8-sig")) if hook_path.exists() else {}
    hooks = merge_hooks(existing, desired)
    content = (SOURCE / "codex.md").read_bytes()
    print(f"Target: {target}")
    print(f"AGENTS.md SHA256: {hashlib.sha256(content).hexdigest()}")
    print(json.dumps(hooks, indent=2))
    if args.apply:
        target.mkdir(parents=True, exist_ok=True)
        write_if_changed(target / "AGENTS.md", content)
        write_if_changed(hook_path, (json.dumps(hooks, indent=2) + "\n").encode("utf-8"))


if __name__ == "__main__":
    main()
