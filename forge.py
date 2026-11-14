#!/usr/bin/env python3
"""Conclave-SDK CLI: copy agent customizations and stack kits into a project, then audit them.

    python forge.py init <target> [--agent all|agy|gemini|claude|codex] [--kit <kit>] [--with-todo] [--force]
    python forge.py kit <target> <kit> [--agent all|agy|gemini|claude|codex] [--host pressable|wpcom] [--dry-run]
    python forge.py diff <target> [kit] [--patch]
    python forge.py update <target> [kit] [--only <path>]... [--no-scripts] [--kit-new] [--dry-run]
    python forge.py record <target> [kit] [--merged <path>]... [--dry-run]
    python forge.py drift [--projects <file>]
    python forge.py doctor <target> [base|todo|reviewer|automations|unattended|laravel|wordpress] [--strict]
    python forge.py kits
    python forge.py check <target>
    python forge.py self-sync
    python forge.py skill-copies [--check]

Stdlib only. Uses atomic temp-file-then-replace writes. The SDK is a template, not a master copy: init and kit copy
files once and never overwrite one that exists, so a project owns its copy from then on. They note what they
installed in the project's `.conclave/kits.json` (the SDK commit, and each file's kit and a digest of its bytes as
installed): a note the project may delete, holding no path back to the SDK. self-sync refreshes the SDK's own
installed copy of its kits.
"""
from __future__ import annotations

import argparse
import ctypes
import difflib
import fnmatch
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import types

FORGE_ROOT = Path(__file__).resolve().parent
AGENT_CHOICES = ["all", "agy", "gemini", "claude", "codex"]


def normalize_agent(agent: str) -> str:
    return "agy" if agent == "gemini" else agent


def atomic_write(path: Path, data: bytes | str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = data if isinstance(data, bytes) else data.encode("utf-8")
    fd, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(raw)
            # mkstemp creates 0600; a provisioned file is ordinary repository content, and a script is executable.
            os.fchmod(out.fileno(), 0o755 if raw.startswith(b"#!") else 0o644)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def copy_tree_atomic(src_dir: Path, dst_dir: Path, overwrite: bool = True) -> list[str]:
    written: list[str] = []
    for item in sorted(src_dir.rglob("*")):
        if item.is_file():
            rel = item.relative_to(src_dir)
            target = dst_dir / rel
            if (target.exists() or target.is_symlink()) and not overwrite:
                continue
            atomic_write(target, item.read_bytes())
            written.append(target.as_posix())
    return written


def write_if_allowed(target: Path, content: bytes | str, overwrite: bool) -> bool:
    if (target.exists() or target.is_symlink()) and not overwrite:
        return False
    atomic_write(target, content)
    return True


def list_kits() -> list[str]:
    kits_dir = FORGE_ROOT / "kits"
    if not kits_dir.is_dir():
        return []
    return sorted(
        d.name
        for d in kits_dir.iterdir()
        if d.is_dir() and (d / "templates").is_dir()
    )


def _is_link(path: Path) -> bool:
    """A symlink, or on Windows a junction: either leads a write somewhere other than where its path says."""
    return path.is_symlink() or getattr(path, "is_junction", lambda: False)()


def _has_unsafe_parent(target_root: Path, rel_path: str) -> bool:
    parts = Path(rel_path).parts[:-1]
    current = target_root
    for part in parts:
        current = current / part
        if _is_link(current) or (current.exists() and not current.is_dir()):
            return True
    return False


def _find_laravel_app_root(target_root: Path) -> Path | None:
    if not target_root.is_dir():  # a target init has not created yet holds no app
        return None
    if (target_root / "artisan").is_file():
        return target_root
    if (target_root / "platform/artisan").is_file():
        return target_root / "platform"
    for child in sorted(target_root.iterdir()):
        if child.is_dir() and not child.is_symlink() and (child / "artisan").is_file():
            return child
    return None


def _composer_vendor_dir(app_root: Path) -> Path:
    """Where Composer keeps the app's packages: COMPOSER_VENDOR_DIR, then `config.vendor-dir` in the app's
    `composer.json` (relative to the app root), then `vendor`, the order Composer itself reads them in."""
    configured = os.environ.get("COMPOSER_VENDOR_DIR")
    if not configured:
        try:
            config = json.loads((app_root / "composer.json").read_text(encoding="utf-8")).get("config")
            configured = config.get("vendor-dir") if isinstance(config, dict) else None
        except (OSError, ValueError, RecursionError, AttributeError):
            configured = None
    if not isinstance(configured, str) or not configured.strip():
        configured = "vendor"
    return app_root / configured  # an absolute `configured` replaces the app root, as pathlib joins


def _composer_package_installed(app_root: Path, package: str) -> Path | None:
    """The app's `<vendor>/composer/installed.json` when it lists `package`, else None.

    That file is what `composer show <package>` reads, so the answer is Composer's own without Composer on PATH.
    A file that is absent, unreadable, not JSON or not a package list lists nothing."""
    installed = _composer_vendor_dir(app_root) / "composer/installed.json"
    try:
        data = json.loads(installed.read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError):
        return None
    packages = data.get("packages") if isinstance(data, dict) else data  # Composer 1 wrote the bare list
    if not isinstance(packages, list):
        return None
    listed = any(isinstance(entry, dict) and entry.get("name") == package for entry in packages)
    return installed if listed else None


def _is_wp_root(candidate: Path) -> bool:
    return (
        (candidate / "wp-load.php").is_file()
        or (candidate / "wp-config.php").is_file()
        or (candidate / "wp-includes/version.php").is_file()
    )


def _find_wordpress_root(target_root: Path) -> Path | None:
    if not target_root.is_dir():  # a target init has not created yet holds no site
        return None
    if _is_wp_root(target_root):
        return target_root
    for name in ("website", "wordpress", "wp"):
        candidate = target_root / name
        if candidate.is_dir() and not candidate.is_symlink() and _is_wp_root(candidate):
            return candidate
    for child in sorted(target_root.iterdir()):
        if child.is_dir() and not child.is_symlink() and _is_wp_root(child):
            return child
    return None


WORDPRESS_HOSTS = ("pressable", "wpcom")
TODO_SKILLS = (
    "add-todo", "create-todo", "groom-plan", "process-phase", "process-plan",
    "process-todo-file", "process-todo-section", "review-todo-section",
)
WORDPRESS_PIN = ".conclave/wordpress-site.json"
REVIEWER_PIN = ".conclave/reviewers.toml"
AUTOMATIONS_DIR = ".conclave/automations"
# The automations kit's runner, alert and installers: kit code, beside the project's own tasks.json and README.md.
AUTOMATIONS_SCRIPTS = tuple(f"{AUTOMATIONS_DIR}/{name}" for name in ("run.py", "alert.py", "install.ps1", "install.sh"))


UNATTENDED_MODULE = "scripts/lib/unattended.py"
KIT_ORDER = ("base", "todo", "reviewer", "automations", "unattended", "laravel", "wordpress")
BASE_SKILLS = ("authoring-skills", "local-tool-safety")
AGENT_DIRS = (".agents", ".claude", ".codex")
# A kit's version of a file the project changed, written beside it by `update --kit-new` for a hand merge, and the
# files forge stages a write in. None is ever kit content.
KIT_NEW = ".kit-new"
FORGE_SUFFIXES = (KIT_NEW, ".forge-new", ".forge-replace")
# The kits the SDK installs in itself (AGENTS.md), and the files of theirs `self-sync` keeps current there: skills,
# rules, subagents, scripts and the automations runner. The SDK's own docs, plan and pins are its project files.
SELF_KITS = ("base", "todo", "reviewer", "automations")
SELF_PREFIXES = tuple(f"{d}/{kind}/" for d in AGENT_DIRS for kind in ("skills", "rules")) + (
    ".claude/agents/", "scripts/", "bin/", "docs/", ".agents/hooks.json",
    ".codex/hooks.json") + AUTOMATIONS_SCRIPTS


def installed_kits(target_root: Path) -> list[str]:
    """The kits a repository already has, judged by files only that kit installs."""
    target_root = Path(target_root)

    def any_skill(names) -> bool:
        return any((target_root / d / "skills" / n / "SKILL.md").is_file() for d in AGENT_DIRS for n in names)

    found = []
    if any_skill(BASE_SKILLS) or (target_root / "scripts/verify-agent-tiers.mjs").is_file():
        found.append("base")
    if any_skill(TODO_SKILLS) or (target_root / "scripts/todo-graph.py").is_file():
        found.append("todo")
    if any_skill(("independent-review",)) or (target_root / REVIEWER_PIN).is_file():
        found.append("reviewer")
    if any_skill(("scheduled-automations",)) or (target_root / AUTOMATIONS_DIR / "run.py").is_file():
        found.append("automations")
    if (target_root / UNATTENDED_MODULE).is_file() or (target_root / "scripts/unattended-run.py").is_file():
        found.append("unattended")
    if any_skill(("laravel-boost",)) or (target_root / "scripts/lsp-diagnostics.py").is_file():
        found.append("laravel")
    if (target_root / WORDPRESS_PIN).is_file() or any_skill(("wordpress-site-safety", "wordpress-connect")):
        found.append("wordpress")
    return found


def _rel_allowed_for_agent(rel: str, agent: str) -> bool:
    if "__pycache__" in rel.split("/"):
        # Bytecode left by running a kit's own tests in the SDK checkout is not kit content.
        return False
    agent = normalize_agent(agent)
    if agent == "all":
        return True
    if rel == "GEMINI.md" or rel.startswith(".agents/"):
        return agent == "agy"
    if rel == "CLAUDE.md" or rel.startswith(".claude/"):
        return agent == "claude"
    if rel == "CODEX.md" or rel.startswith(".codex/"):
        return agent == "codex"
    return True


def kit_plan(target_root: Path, kit_name: str, *, agent: str = "all", host: str | None = None,
             read_pin: bool = True) -> tuple[list, dict]:
    """The files a kit puts in a project, and where: `(source, destination, relative path, generated)` entries and the
    kit's `extra` result fields. Install, diff and update all read this one list. A template copy has its source file;
    a generated entry (the Laravel `.mcp.json`, which `apply_kit` builds itself) has `source` None. Reads only: the
    refusals (an unknown kit, no artisan, an unknown or wrongly pinned WordPress host) are raised here.
    `read_pin=False` plans WordPress for `host` without reading the site pin (diff, when the record knows the host
    and the pin is a link or does not load).
    """
    agent = normalize_agent(agent)
    available = list_kits()
    if kit_name not in available:
        raise ValueError(f"Unknown kit '{kit_name}'. Available kits: {', '.join(available)}")

    template_root = FORGE_ROOT / "kits" / kit_name / "templates"
    extra: dict[str, str | None] = {}
    plan: list[tuple[Path | None, Path, str, bool]] = []

    def add_tree(root: Path) -> None:
        for src in sorted(root.rglob("*")):
            if src.is_file():
                rel = src.relative_to(root).as_posix()
                # forge's own leftovers (a merge copy, a staged file) are never kit content, even inside a kit.
                if rel.endswith(FORGE_SUFFIXES):
                    continue
                if _rel_allowed_for_agent(rel, agent):
                    plan.append((src, target_root / rel, rel, False))

    if kit_name == "laravel":
        app_root = _find_laravel_app_root(target_root)
        if app_root is None:
            raise ValueError(
                f"No artisan found under {target_root} (looked at root, platform/, and first-level children)."
            )
        artisan_rel = (app_root / "artisan").relative_to(target_root).as_posix()
        extra["artisan"] = artisan_rel
        boost_rel = (app_root / "boost.json").relative_to(target_root).as_posix()
        rel_items = [
            "scripts/lsp-diagnostics.py",
            "scripts/hooks/laravel-lsp-pre-push.sh",
            "docs/laravel-agent-tooling.md",
            ".agents/skills/laravel-boost/SKILL.md",
            ".claude/skills/laravel-boost/SKILL.md",
            ".codex/skills/laravel-boost/SKILL.md",
            ".codex/skills/laravel-boost/agents/openai.yaml",
        ]
        for rel in rel_items:
            if _rel_allowed_for_agent(rel, agent):
                plan.append((template_root / rel, target_root / rel, rel, False))
        plan.append((template_root / "boost.json", app_root / "boost.json", boost_rel, False))
        plan.append((None, target_root / ".mcp.json", ".mcp.json", True))
    elif kit_name == "wordpress":
        if host is not None and host not in WORDPRESS_HOSTS:
            raise ValueError(f"Unknown WordPress host '{host}'. Available hosts: {', '.join(WORDPRESS_HOSTS)}")
        pin_path = target_root / WORDPRESS_PIN
        # The pin decides which host's files are planned, so it is read only from inside the project.
        if read_pin and (_has_unsafe_parent(target_root, WORDPRESS_PIN) or _is_link(pin_path)):
            raise ValueError(f"{WORDPRESS_PIN} is a link or under one; refusing to read a site pin from outside the project")
        if read_pin and pin_path.exists():
            pin, state = _load_wordpress_pin(target_root)
            if pin is None:
                raise ValueError(f"{WORDPRESS_PIN} is {state}; fix it before re-applying the kit")
            if host is not None and host != pin["host"]:
                raise ValueError(f"{WORDPRESS_PIN} pins host '{pin['host']}', not '{host}'")
            host = pin["host"]
        host = host or "pressable"
        # A local WordPress tree is optional: on Pressable the wordpress-connect skill creates it with DDEV,
        # and a WordPress.com site has none.
        wp_root = _find_wordpress_root(target_root)
        extra["host"] = host
        extra["wordpress"] = None if wp_root is None else (wp_root.relative_to(target_root).as_posix() if wp_root != target_root else ".")
        add_tree(template_root)
        add_tree(FORGE_ROOT / "kits" / kit_name / "hosts" / host / "templates")
    else:
        add_tree(template_root)
    return plan, extra


RECORD = ".conclave/kits.json"
RECORD_AGENTS = ("agy", "claude", "codex")
_HEX40 = re.compile(r"[0-9a-f]{40}")
_HEX64 = re.compile(r"[0-9a-f]{64}")


def file_digest(data: bytes) -> str:
    """SHA-256 of a file's bytes with CRLF read as LF (as self-sync compares), so a checkout whose line endings were
    converted does not look changed."""
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def sdk_commit(run=subprocess.run) -> str | None:
    """The commit this SDK checkout is at, or None when it is not a git checkout of its own, git is missing, the
    command fails or it does not answer in 15 seconds. The install record notes it; nothing depends on it."""
    if not (FORGE_ROOT / ".git").exists():
        return None
    try:
        proc = run(["git", "-C", str(FORGE_ROOT), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        return None
    value = (proc.stdout or "").strip()
    return value if proc.returncode == 0 and _HEX40.fullmatch(value) else None


def _check_record(data) -> dict:
    """The install record, or a ValueError naming the first fault. Every level is closed: an unknown or missing key
    refuses, so a record edited or merged by hand is never half-read."""
    def fault(what: str) -> ValueError:
        return ValueError(f"{RECORD}: {what}")

    def keys(obj, expected: set, where: str) -> None:
        if not isinstance(obj, dict):
            raise fault(f"{where} must be an object")
        if set(obj) != expected:
            odd = sorted(set(obj) ^ expected)
            raise fault(f"{where} needs exactly the keys {', '.join(sorted(expected))} (see {', '.join(map(str, odd))})")

    keys(data, {"schema_version", "kits", "files"}, "the record")
    if data["schema_version"] != 1 or isinstance(data["schema_version"], bool):
        raise fault(f"schema_version must be 1, not {data['schema_version']!r}")
    if not isinstance(data["kits"], dict):
        raise fault("kits must be an object")
    if not isinstance(data["files"], dict):
        raise fault("files must be an object")
    known = list_kits()
    for name, kit in data["kits"].items():
        if name not in known:
            raise fault(f"kits names '{name}', which is not a kit")
        keys(kit, {"sdk_commit", "agents", "host"}, f"kits.{name}")
        commit = kit["sdk_commit"]
        if commit is not None and not (isinstance(commit, str) and _HEX40.fullmatch(commit)):
            raise fault(f"kits.{name}.sdk_commit must be null or a 40-character lowercase commit")
        agents = kit["agents"]
        if (not isinstance(agents, list) or not agents or not all(isinstance(a, str) and a in RECORD_AGENTS for a in agents)
                or agents != sorted(set(agents))):
            raise fault(f"kits.{name}.agents must be a non-empty sorted list of distinct names from "
                        f"{', '.join(RECORD_AGENTS)}")
        host = kit["host"]
        if host is not None and not (isinstance(host, str) and host in WORDPRESS_HOSTS):
            raise fault(f"kits.{name}.host must be null or one of {', '.join(WORDPRESS_HOSTS)}")
    for rel, entry in data["files"].items():
        parts = rel.split("/")
        if (not rel or rel.startswith("/") or "\\" in rel or ":" in parts[0]
                or any(part in ("", ".", "..") for part in parts)):
            raise fault(f"files names '{rel}', which is not a relative path inside the project")
        keys(entry, {"kit", "sha256"}, f"files.{rel}")
        if not isinstance(entry["kit"], str) or entry["kit"] not in data["kits"]:
            raise fault(f"files.{rel}.kit names {entry['kit']!r}, which kits does not hold")
        if not isinstance(entry["sha256"], str) or not _HEX64.fullmatch(entry["sha256"]):
            raise fault(f"files.{rel}.sha256 must be 64 lowercase hex characters")
    return data


def _record_refusal(target_root: Path) -> None:
    """Refuse a record that cannot be written safely: `.conclave` as a link or a file, or the record as a link or a
    folder. Checked before any template is copied, so a refusal never leaves files with no record."""
    path = target_root / RECORD
    if _has_unsafe_parent(target_root, RECORD) or _is_link(path) or path.is_dir():
        raise ValueError(f"{RECORD}: refusing a record that is a link or a folder, or a .conclave that is not a folder")


def load_record(target_root: Path) -> dict | None:
    """What forge installed in this project, from `.conclave/kits.json`; None when the project has no record. A
    record that does not load refuses with a ValueError: it is never read as empty, since that would forget which
    files are still as installed."""
    target_root = Path(target_root)
    _record_refusal(target_root)
    path = target_root / RECORD
    if not path.exists():
        return None
    def no_duplicates(pairs):
        # json keeps the last of two equal keys, which would silently drop a whole "files" object.
        found: dict = {}
        for key, value in pairs:
            if key in found:
                raise ValueError(f"the key {key!r} appears twice")
            found[key] = value
        return found

    try:
        data = json.loads(path.read_bytes().decode("utf-8"), object_pairs_hook=no_duplicates)
    except RecursionError:
        raise ValueError(f"{RECORD}: nested too deeply to be an install record") from None
    except (OSError, ValueError) as exc:  # a decoding error and a JSON error are both ValueErrors
        raise ValueError(f"{RECORD}: not readable as UTF-8 JSON ({exc})") from None
    return _check_record(data)


def write_record(target_root: Path, record: dict) -> None:
    """Write the install record with sorted keys, so two identical installs leave identical files."""
    target_root = Path(target_root)
    _record_refusal(target_root)
    _check_record(record)
    atomic_write(target_root / RECORD, json.dumps(record, indent=2, sort_keys=True) + "\n")


def _record_install(record: dict, kit_name: str, agent: str | list[str], host: str | None, digests: dict[str, str],
                    commit: str | None) -> None:
    """Merge written files into the record under their kit. The kit's agents accumulate (an install for Claude and
    a later one for Codex record both; `all` records all three, a list each it names) and its commit is the latest
    install's."""
    agents = set(RECORD_AGENTS) if agent == "all" else ({agent} if isinstance(agent, str) else set(agent))
    kit = record["kits"].setdefault(kit_name, {"sdk_commit": None, "agents": [], "host": None})
    kit["agents"] = sorted(agents | set(kit["agents"]))
    kit["sdk_commit"] = commit
    kit["host"] = host if host is not None else kit["host"]
    for rel, digest in digests.items():
        record["files"][rel] = {"kit": kit_name, "sha256": digest}


STAGED = ".forge-new"
STAGED_REPLACE = ".forge-replace"
PENDING = ".conclave/kits.pending.json"
_PENDING_KEYS = {"schema_version", "path", "kit", "new", "earlier", "destination"}


def _digest_of(path: Path) -> str | None:
    """The digest of a file's bytes, or None when there is no file there."""
    return file_digest(path.read_bytes()) if path.is_file() else None


def _remove(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def _load_pending(target_root: Path) -> dict | None:
    """The journal of a replacement that was interrupted, or None. It names the file, the digest being installed,
    the record entry the file had before (or null) and the digest of what was at the destination before (or null)."""
    path = target_root / PENDING
    if _is_link(path) or path.is_dir():
        raise ValueError(f"{PENDING}: refusing a journal that is a link or a folder")
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_bytes().decode("utf-8"))
    except (OSError, ValueError, RecursionError) as exc:
        raise ValueError(f"{PENDING}: not readable as UTF-8 JSON ({exc}); remove it after checking the file it names") from None
    hexes = [data.get(key) for key in ("new", "destination")] if isinstance(data, dict) else []
    earlier = data.get("earlier") if isinstance(data, dict) else None
    if (not isinstance(data, dict) or set(data) != _PENDING_KEYS or data["schema_version"] != 1
            or not isinstance(data["path"], str) or not isinstance(data["kit"], str)
            or not isinstance(hexes[0], str) or not _HEX64.fullmatch(hexes[0])
            or not (hexes[1] is None or (isinstance(hexes[1], str) and _HEX64.fullmatch(hexes[1])))
            or not (earlier is None or (isinstance(earlier, dict) and set(earlier) == {"kit", "sha256"}))):
        raise ValueError(f"{PENDING}: not a forge journal; remove it after checking the file it names")
    return data


def _recover(target_root: Path, record: dict) -> None:
    """Settle what an interrupted run left, before anything else is written.

    A journal means a replacement was under way. Its staged file (`<name>.forge-replace`) says how far it got, since
    the only step that takes that file away while the journal stays is the rename over the destination:

    - The staged file is gone: the rename happened. The file was installed, so its entry is the new digest, whatever
      the project has done to the file since.
    - The staged file is there and the destination still holds what it held then: nothing moved, so the replacement
      is finished (record, then rename).
    - The staged file is there and the destination changed: the project edited the file in between. It is rolled
      back: the entry returns to what it was and the project's file is left alone.

    A `<name>.forge-new` file belongs to a file that did not exist when it was staged, and has no journal. If the
    record names its bytes and the destination is still missing, it is moved into place. If a file has appeared
    there since, that file is the project's: the entry is dropped and the staged file removed. Any other staged
    file is stale and removed.
    """
    pending = _load_pending(target_root)
    if pending is not None:
        rel = pending["path"]
        if _has_unsafe_parent(target_root, rel):
            raise ValueError(f"{PENDING}: names a path with an unsafe parent: {rel}")
        dst, staged = target_root / rel, target_root / (rel + STAGED_REPLACE)
        new_entry = {"kit": pending["kit"], "sha256": pending["new"]}
        known_kit = pending["kit"] in record["kits"]
        finish = False
        if not staged.exists():
            entry = new_entry if known_kit else pending["earlier"]
        elif _digest_of(staged) == pending["new"] and _digest_of(dst) == pending["destination"] and known_kit:
            entry, finish = new_entry, True
        else:
            entry = pending["earlier"]
        if entry is None or entry["kit"] not in record["kits"]:
            changed = record["files"].pop(rel, None) is not None
        else:
            changed = record["files"].get(rel) != entry
            record["files"][rel] = entry
        if changed:
            write_record(target_root, record)
        if finish:
            os.replace(staged, dst)
        # The journal goes before a staged file that was not used, so no failure here can leave a journal without
        # its staged file, which would read as a rename that happened.
        _remove(target_root / PENDING)
        _remove(staged)
    for rel in sorted(set(record["files"]) | set(ENTRY_DOCS)):
        if _has_unsafe_parent(target_root, rel):
            continue
        stale = target_root / (rel + STAGED_REPLACE)
        if stale.is_file() and not _is_link(stale):
            _remove(stale)  # a replacement's staged file with no journal was never recorded: it is not applied
        staged = target_root / (rel + STAGED)
        entry = record["files"].get(rel)
        if not staged.is_file() or _is_link(staged):
            continue
        dst = target_root / rel
        if entry is not None and file_digest(staged.read_bytes()) == entry["sha256"]:
            if not dst.exists() and not dst.is_symlink():
                os.replace(staged, dst)
                continue
            if _digest_of(dst) != entry["sha256"]:
                del record["files"][rel]
                write_record(target_root, record)
        _remove(staged)


def _write_recorded(target_root: Path, record: dict, kit_name: str, agent: str | list[str], host: str | None,
                    copies: list[tuple[str, Path, bytes]], expect: dict[str, str | None] | None = None) -> list[str]:
    """Write `(relative path, destination, bytes)` files and record each under its kit, one file at a time, so the
    record and the files never disagree in a way a later run cannot settle (`_recover`). For each file:

    1. Its bytes are staged beside the destination: `<name>.forge-new` for a file that is not there and has no
       record entry, `<name>.forge-replace` for one that replaces something. If that fails, nothing has changed.
    2. A replacement writes a journal naming what the destination and the entry were. A new file needs none: there
       is nothing to go back to.
    3. The record is written with the file's digest. If that fails, the journal and then the staged file are removed
       and nothing has changed: a file being replaced still holds its earlier bytes under its earlier digest.
    4. The staged file is renamed over the destination, which needs no space, and the journal is removed. If the
       rename fails, the staged file and the journal stay for the next run to settle.

    So a file is on disk only with its record entry, and a failure part way leaves the files before it written and
    recorded and the failing one neither.

    `expect` maps a path to the digest its destination must still have (None: still absent) just before the file
    is staged; a file that no longer matches was changed since it was classified, is left alone, and is returned.
    """
    changed: list[str] = []
    if not copies:
        return changed
    commit = sdk_commit()
    journal = target_root / PENDING
    for rel, dst, data in copies:
        if expect is not None and rel in expect:
            now = None if not (dst.exists() or dst.is_symlink()) else (_digest_of(dst) if not _is_link(dst) else "link")
            if now != expect[rel]:
                changed.append(rel)
                continue
        earlier = record["files"].get(rel)
        replaces = earlier is not None or dst.exists() or dst.is_symlink()
        staged = dst.with_name(dst.name + (STAGED_REPLACE if replaces else STAGED))
        digest = file_digest(data)
        atomic_write(staged, data)
        try:
            if replaces:
                atomic_write(journal, json.dumps({
                    "schema_version": 1, "path": rel, "kit": kit_name, "new": digest, "earlier": earlier,
                    "destination": _digest_of(dst)}, indent=2, sort_keys=True) + "\n")
            _record_install(record, kit_name, agent, host, {rel: digest}, commit)
            write_record(target_root, record)
        except BaseException:
            # An interrupt (or a failure after the rename inside write_record) can come after the record already
            # names the new digest. Then the staged file and journal are what lets the next run finish the file
            # (_recover), so they stay; removing them would leave the old bytes recorded as the new ones.
            try:
                committed = (load_record(target_root) or {"files": {}})["files"].get(rel) == {
                    "kit": kit_name, "sha256": digest}
            except (OSError, ValueError):
                committed = False
            if committed:
                raise
            # The journal first: a journal left without its staged file would read as a rename that happened. If it
            # cannot be removed, the staged file stays with it and the next run settles the pair (_recover).
            try:
                if replaces:
                    _remove(journal)
                _remove(staged)
            except OSError:
                pass
            raise
        os.replace(staged, dst)
        if replaces:
            _remove(journal)
    return changed


def apply_kit(
    target_root: Path,
    kit_name: str,
    *,
    agent: str = "all",
    dry_run: bool = False,
    host: str | None = None,
    include=None,
) -> dict:
    """Apply an additive overlay kit ('base', 'todo', 'reviewer', 'automations', 'laravel', 'wordpress') for all or one agent without overwriting existing files.

    A file that already exists is the project's and is never replaced: the kit is a template copied once, and the
    project adapts its copy from then on. `include(rel)` can leave paths out entirely.

    `host` picks the WordPress kit's host overlay (kits/wordpress/hosts/<host>/templates); other kits ignore it. An
    existing site pin decides the host, so re-running the kit can never add another host's files; without a pin the
    default is `pressable`. The file list is `kit_plan`'s.
    """
    agent = normalize_agent(agent)
    target_root = Path(target_root)
    if not target_root.exists() or not target_root.is_dir() or target_root.is_symlink():
        raise ValueError(f"Target must be an existing non-symlink directory: {target_root}")
    target_root = target_root.resolve()

    entries, extra = kit_plan(target_root, kit_name, agent=agent, host=host)
    installed: list[str] = []
    preserved: list[str] = []
    merge_needed: list[str] = []
    # The generated entry (the Laravel .mcp.json) is written by its own step below, never copied.
    plan = [(src, dst, rel) for src, dst, rel, generated in entries if not generated]

    if include is not None:
        plan = [(src, dst, rel) for src, dst, rel in plan if include(rel)]

    # Preflight all planned destinations for symlink-parent traversal before writing any file
    for _src, dst, rel in plan:
        if dst.exists() or dst.is_symlink():
            continue
        if _has_unsafe_parent(target_root, rel):
            raise ValueError(f"Refusing destination with unsafe parent: {rel}")

    # The record is read, and its folder checked, before the first copy: a refusal here leaves nothing written.
    record = load_record(target_root) or {"schema_version": 1, "kits": {}, "files": {}}
    if not dry_run:
        _recover(target_root, record)
    copies: list[tuple[str, Path, bytes]] = []
    for src, dst, rel in plan:
        if dst.exists() or dst.is_symlink():
            preserved.append(rel)
            continue
        installed.append(rel)
        if not dry_run:
            copies.append((rel, dst, src.read_bytes()))
    # Only files this run writes are recorded, with the template's digest; a preserved file stays the project's.
    _write_recorded(target_root, record, kit_name, agent, extra.get("host"), copies)

    if kit_name == "laravel":
        mcp_path = target_root / ".mcp.json"
        server_cfg = {"command": "php", "args": [extra["artisan"], "boost:mcp"]}
        if mcp_path.exists() or mcp_path.is_symlink():
            try:
                data = json.loads(mcp_path.read_text(encoding="utf-8"))
                servers = data.get("mcpServers") if isinstance(data, dict) else None
                if isinstance(servers, dict) and "laravel-boost" in servers:
                    preserved.append(".mcp.json")
                else:
                    preserved.append(".mcp.json")
                    merge_needed.append(".mcp.json")
            except (OSError, ValueError):  # unreadable, not UTF-8 (UnicodeDecodeError) or not JSON: the project's to merge
                preserved.append(".mcp.json")
                merge_needed.append(".mcp.json")
        else:
            payload = {"mcpServers": {"laravel-boost": server_cfg}}
            if not dry_run:
                atomic_write(mcp_path, json.dumps(payload, indent=4) + "\n")
            installed.append(".mcp.json")

    result = {
        "target": target_root.as_posix(),
        "kit": kit_name,
        "agent": agent,
        "dry_run": dry_run,
        "installed": installed,
        "preserved": preserved,
        "merge_needed": merge_needed,
        **extra,
    }
    if kit_name == "todo" and ".codex/hooks.json" in installed and not dry_run:
        result["codex_hook"] = _approve_codex_hook(target_root)
    if kit_name == "todo" and not dry_run:
        result["pre_commit_hook"] = _enable_pre_commit_hook(target_root)
    return result


# The todo kit's pre-commit hook (D01 T02 §7): git runs it only once `core.hooksPath` points at the folder it is
# installed in. The install sets that where nothing else owns the repository's hooks, and the doctor says what is left.
HOOKS_PATH = "scripts/hooks"
PRE_COMMIT_HOOK = f"{HOOKS_PATH}/pre-commit"


def _git_answer(folder: Path, *args: str) -> tuple[int, str, str] | None:
    """`git <args>` run in `folder`: (exit code, stdout, stderr) stripped, or None when git cannot be run at all."""
    try:
        proc = subprocess.run(["git", *args], cwd=folder, capture_output=True, text=True, timeout=15,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def _same_folder(one: Path, other: Path) -> bool:
    try:
        return os.path.samefile(one, other)
    except OSError:
        return os.path.normcase(Path(one).resolve()) == os.path.normcase(Path(other).resolve())


def _hook_setup(target_root: Path) -> dict:
    """How the repository holding `target_root` runs hooks, read and never changed.

    `state` is one of: `no-git` (git cannot be run, `why` says so), `no-repository`, `nested` (the project is a
    subfolder of the repository at `top`), `enabled` (`core.hooksPath` resolves to the project's scripts/hooks),
    `owned` (another `core.hooksPath`, or hooks of the project's own in the default folder: `owner` names it and
    `pre_commit` is the hook git would run there) and `free` (nothing owns the repository's hooks)."""
    target_root = Path(target_root)
    top = _git_answer(target_root, "rev-parse", "--show-toplevel")
    if top is None:
        return {"state": "no-git", "why": "git is not on PATH or did not answer"}
    if top[0] != 0:
        if "not a git repository" in top[2].lower():
            return {"state": "no-repository"}
        return {"state": "no-git", "why": (top[2].splitlines() or ["git rev-parse failed"])[0]}
    top_path = Path(top[1])
    if not _same_folder(top_path, target_root):
        return {"state": "nested", "top": top_path}
    configured = _git_answer(target_root, "config", "--type=path", "--get", "core.hooksPath")
    if configured is None or configured[0] not in (0, 1):
        why = (configured[2].splitlines() or ["git config failed"])[0] if configured else "git did not answer"
        return {"state": "no-git", "why": why}
    if configured[0] == 0 and configured[1]:
        folder = Path(configured[1])
        folder = folder if folder.is_absolute() else top_path / folder  # git reads a relative path from the top level
        if _same_folder(folder, target_root / HOOKS_PATH):
            return {"state": "enabled"}
        return {"state": "owned", "owner": f"core.hooksPath is {configured[1]}", "pre_commit": folder / "pre-commit"}
    common = _git_answer(target_root, "rev-parse", "--git-common-dir")
    if common is None or common[0] != 0:
        return {"state": "no-git", "why": "git rev-parse --git-common-dir failed"}
    hooks = Path(common[1]) if Path(common[1]).is_absolute() else target_root / common[1]
    hooks = hooks / "hooks"
    own = sorted(path.name for path in hooks.iterdir() if path.is_file() and not path.name.endswith(".sample")) \
        if hooks.is_dir() else []
    if own:
        return {"state": "owned", "owner": f"{hooks.as_posix()} holds the project's own hooks ({', '.join(own)})",
                "pre_commit": hooks / "pre-commit"}
    return {"state": "free"}


def _kit_hook_problem(target_root: Path) -> tuple[str, str] | None:
    """Why git could not run the kit's hook even when asked to: a doctor (status, detail), or None when it can."""
    for rel in (PRE_COMMIT_HOOK, "scripts/todo-graph.py"):
        if not (target_root / rel).is_file():
            return "missing", f"{rel} is not installed: run python forge.py kit <project> todo (without --no-scripts)"
    if os.name != "nt" and not os.access(target_root / PRE_COMMIT_HOOK, os.X_OK):
        return "setup_required", f"chmod +x {PRE_COMMIT_HOOK}: git runs only an executable hook"
    return None


def _pre_commit_hook_check(target_root: Path) -> tuple[str, str]:
    """The doctor's `pre-commit-hook` check for the todo kit: (status, detail). It reads and never changes."""
    setup = _hook_setup(target_root)
    state = setup["state"]
    if state == "no-git":
        return "setup_required", f"git cannot be run here ({setup['why']}), so the hook cannot be checked"
    if state == "no-repository":
        return "ok", "not a git repository: no commit to check"
    if state == "nested":
        return ("setup_required",
                f"not enabled: the project is a subfolder of the repository at {setup['top'].as_posix()}, and the hook "
                "reads the plan at the repository's top level, so it cannot check a nested project; run "
                "python scripts/todo-graph.py validate and python scripts/todo-graph.py plan --check before a commit")
    problem = _kit_hook_problem(target_root)
    if state == "enabled":
        return problem or ("ok", f"core.hooksPath is {HOOKS_PATH}")
    if state == "free":
        return problem or ("setup_required", f"git config core.hooksPath {HOOKS_PATH}")
    hook = setup["pre_commit"]
    try:
        calls_kit = PRE_COMMIT_HOOK in hook.read_text(encoding="utf-8", errors="replace")
    except OSError:
        calls_kit = False
    if calls_kit:
        return problem or ("ok", f"{hook.as_posix()} calls {PRE_COMMIT_HOOK}")
    return ("setup_required",
            f"{setup['owner']}: git config core.hooksPath {HOOKS_PATH} would stop those hooks. Call {PRE_COMMIT_HOOK} "
            f"from {hook.as_posix()}, or replace that setup on purpose with git config core.hooksPath {HOOKS_PATH}")


def _enable_pre_commit_hook(target_root: Path) -> str:
    """Point the repository's `core.hooksPath` at the todo kit's hooks where nothing else owns its hooks.

    Returns `enabled` (read back from git), `already enabled`, or `left: <why>`: never an error, the install stands."""
    setup = _hook_setup(target_root)
    state = setup["state"]
    if state == "enabled":
        return "already enabled"
    if state == "no-git":
        return f"left: git cannot be run here ({setup['why']})"
    if state == "no-repository":
        return "left: not a git repository"
    if state == "nested":
        return f"left: the project is a subfolder of the repository at {setup['top'].as_posix()}"
    if state == "owned":
        return f"left: {setup['owner']}"
    problem = _kit_hook_problem(target_root)
    if problem:
        return f"left: {problem[1]}"
    written = _git_answer(target_root, "config", "core.hooksPath", HOOKS_PATH)
    if written is None or written[0] != 0:
        why = (written[2].splitlines() or [f"exit {written[0]}"])[0] if written else "git did not answer"
        return f"left: git config failed: {why}"
    read_back = _git_answer(target_root, "config", "--get", "core.hooksPath")
    if read_back is None or read_back[0] != 0 or read_back[1] != HOOKS_PATH:
        return "left: git config did not read back core.hooksPath"
    return "enabled"


def _approve_codex_hook(target_root: Path) -> str:
    """Approve the campaign Stop hook the todo kit just installed for Codex, through Codex's own app-server (the
    kit's codex-hook-trust.py), so a Codex run in the project is held by the run guard from the first session.
    A machine without Codex, or one whose Codex does not answer, is reported, never an error: the install stands
    and the doctor says what is left."""
    trust = _codex_trust_module()
    try:
        results = trust.trust(Path(target_root))
    except (trust.TrustError, OSError) as exc:
        return f"not approved: {exc}; run python scripts/codex-hook-trust.py in the project"
    return "approved" if any(r["approved"] for r in results) else "trusted"


# What `diff` says of each kit file. With a record entry: the first six. Without one (a kit installed before the
# record existed, or a file the project had before the install): missing, identical or differs. Never read: unsafe.
# A read that fails: unreadable. The generated Laravel .mcp.json has no template to compare: generated.
DIFF_STATES = ("missing", "identical", "kit-newer", "project-changed", "both-changed", "project-removed",
               "project-only", "differs", "unsafe", "unreadable", "generated")
DIFF_PATCHED = ("project-changed", "both-changed", "differs")


def _diff_agents(target_root: Path, recorded_kit: dict | None) -> list[str]:
    """The agents a kit is compared for: those the record holds, else each agent whose folder the project has, else
    all three."""
    if recorded_kit is not None:
        return list(recorded_kit["agents"])
    found = [agent for agent, folder in zip(RECORD_AGENTS, AGENT_DIRS) if (target_root / folder).is_dir()]
    return found or list(RECORD_AGENTS)


def _diff_plan(target_root: Path, kit_name: str, agents: list[str], host: str | None) -> tuple[list[tuple], dict]:
    """The union of the kit's plans for each agent, one entry per relative path, sorted by path. When the record
    knows the WordPress host and the pin is a link or does not load, the plan uses the recorded host without
    reading the pin, so the pin is reported (unsafe, unreadable, changed) beside every other file."""
    read_pin = True
    if kit_name == "wordpress" and host is not None:
        read_pin = not _unsafe_destination(target_root, WORDPRESS_PIN) and (
            not (target_root / WORDPRESS_PIN).exists() or _load_wordpress_pin(target_root)[0] is not None)
    entries: dict[str, tuple] = {}
    extra: dict = {}
    for agent in (["all"] if set(agents) == set(RECORD_AGENTS) else agents):
        plan, extra = kit_plan(target_root, kit_name, agent=agent, host=host, read_pin=read_pin)
        for entry in plan:
            entries.setdefault(entry[2], entry)
    return [entries[rel] for rel in sorted(entries)], extra


def _unsafe_destination(target_root: Path, rel: str) -> bool:
    """A destination diff must not read and update must not write: a link, a folder, or one under a parent that is
    a link or not a folder."""
    path = target_root / rel
    return _has_unsafe_parent(target_root, rel) or _is_link(path) or (path.exists() and not path.is_file())


def _diff_state(project: str | None, kit: str, recorded: str | None) -> str:
    if recorded is None:
        if project is None:
            return "missing"
        return "identical" if project == kit else "differs"
    if project is None:
        return "project-removed"
    if project == kit:
        return "identical"
    if project == recorded:
        return "kit-newer"
    if kit == recorded:
        return "project-changed"
    return "both-changed"


def _text_patch(rel: str, project: bytes, kit: bytes) -> str:
    """A unified diff from the project's file to the kit's, or `binary` when either side is not UTF-8 text."""
    if b"\0" in project or b"\0" in kit:
        return "binary"
    try:
        ours, theirs = project.decode("utf-8"), kit.decode("utf-8")
    except UnicodeDecodeError:
        return "binary"
    lines = difflib.unified_diff(
        ours.replace("\r\n", "\n").splitlines(keepends=True), theirs.replace("\r\n", "\n").splitlines(keepends=True),
        fromfile=f"project/{rel}", tofile=f"kit/{rel}")
    # A last line with no newline ends its line in the patch and is marked, as diff(1) and git do.
    return "".join(line if line.endswith("\n") else line + "\n\\ No newline at end of file\n" for line in lines)


def diff_project(target_root: Path, kit_name: str | None = None, *, patch: bool = False) -> dict:
    """`diff`: the state of every kit file in a project (DIFF_STATES), from the project's bytes, the kit's and the
    record's digest. Reads only: it never settles an interrupted run (`_recover`) or writes the record."""
    return _diff_kits(target_root, kit_name, patch=patch)[0]


def _diff_kits(target_root: Path, kit_name: str | None, *, patch: bool) -> tuple[dict, dict]:
    """`diff_project`'s report, and for each kit what `update` needs to act on it: the plan's source by path (None
    for a generated entry), the agents compared and the host."""
    target_root = Path(target_root)
    if not target_root.is_dir() or _is_link(target_root):
        raise ValueError(f"Target must be an existing non-symlink directory: {target_root}")
    target_root = target_root.resolve()
    record = load_record(target_root)
    recorded_kits = record["kits"] if record else {}
    present = set(recorded_kits) | set(installed_kits(target_root))
    if kit_name is not None:
        if kit_name not in list_kits():
            raise ValueError(f"Unknown kit '{kit_name}'. Available kits: {', '.join(list_kits())}")
        if kit_name not in present:
            raise ValueError(f"The project has no '{kit_name}' kit (it has: {', '.join(sorted(present)) or 'none'})")
        present = {kit_name}
    files = record["files"] if record else {}
    kits: dict[str, dict] = {}
    sources: dict[str, dict] = {}
    for name in [k for k in KIT_ORDER if k in present] + sorted(present - set(KIT_ORDER)):
        recorded_kit = recorded_kits.get(name)
        agents = _diff_agents(target_root, recorded_kit)
        plan, extra = _diff_plan(target_root, name, agents, recorded_kit["host"] if recorded_kit else None)
        sources[name] = {"agents": sorted(agents), "host": extra.get("host"),
                         "plan": {rel: (None if generated else src) for src, _dst, rel, generated in plan}}
        report = []
        for src, _dst, rel, generated in plan:
            if _unsafe_destination(target_root, rel):
                report.append({"path": rel, "state": "unsafe"})
                continue
            path = target_root / rel
            if generated:
                report.append({"path": rel, "state": "generated" if path.is_file() else "missing"})
                continue
            try:
                kit_bytes = src.read_bytes()
                project_bytes = path.read_bytes() if path.is_file() else None
            except OSError as exc:
                report.append({"path": rel, "state": "unreadable", "reason": f"{type(exc).__name__}: {exc.strerror or exc}"})
                continue
            entry = files.get(rel) if recorded_kit is not None else None
            state = _diff_state(None if project_bytes is None else file_digest(project_bytes), file_digest(kit_bytes),
                                None if entry is None else entry["sha256"])
            item = {"path": rel, "state": state}
            if patch and state in DIFF_PATCHED and project_bytes is not None:
                item["patch"] = _text_patch(rel, project_bytes, kit_bytes)
            report.append(item)
        planned = {entry[2] for entry in plan}
        for rel in sorted(r for r, e in files.items() if e["kit"] == name and r not in planned):
            if _unsafe_destination(target_root, rel):
                report.append({"path": rel, "state": "unsafe"})
            elif (target_root / rel).is_file():
                report.append({"path": rel, "state": "project-only"})
        # A merge copy left beside a kit file (`update --kit-new`) until the merge is recorded (`record --merged`).
        pending = sorted(rel + KIT_NEW for rel in planned
                         if not _has_unsafe_parent(target_root, rel + KIT_NEW)
                         and ((target_root / (rel + KIT_NEW)).exists() or _is_link(target_root / (rel + KIT_NEW))))
        kits[name] = {"record": recorded_kit is not None, "agents": sorted(agents), "files": report,
                      "merge_pending": pending}
    result = {"target": target_root.as_posix(), "record": record is not None, "sdk_commit": sdk_commit(), "kits": kits}
    return result, sources


UPDATE_HINT_NO_RECORD = (
    "Without a record entry a differing file's installed bytes are unknown, so it is left. `forge.py record` adopts "
    "the files identical to the kit as installed; a differing file is merged by hand (`update --kit-new` helps).")
UPDATE_HINT_GENERATED = "Generated by the kit, never copied: `forge.py kit <project> laravel` builds it."


def _only_paths(only) -> list[str]:
    """`--only` values as project-relative paths: an absolute path, a drive, `..` or nothing at all refuses."""
    paths = []
    for value in only:
        text = str(value).replace("\\", "/")
        parts = [part for part in text.split("/") if part not in ("", ".")]
        if os.path.isabs(str(value)) or text.startswith("/") or re.match(r"^[A-Za-z]:", text) or ".." in parts or not parts:
            raise ValueError(f"--only takes a file or folder inside the project, not {value!r}")
        paths.append("/".join(parts))
    return paths


def _under(rel: str, paths: list[str]) -> bool:
    return any(rel == path or rel.startswith(path + "/") for path in paths)


def update_project(target_root: Path, kit_name: str | None = None, *, only=(), dry_run: bool = False,
                   no_scripts: bool = False, kit_new: bool = False) -> dict:
    """`update`: write the kit files that are `missing` or `kit-newer` (and a `project-removed` one only when `only`
    names it or its folder), never one the project changed, and list every other differing file under `left` with
    its state and patch. Every refusal (a bad `only`, an unsafe destination in the selection) comes from a read-only
    diff before anything is written; then an interrupted run is settled, the project is diffed again and the writes
    go through `_write_recorded`, one file recorded at a time, each re-checked just before it is written.

    `kit_new` writes the kit's bytes beside each `both-changed` or `differs` file as `<path>.kit-new` (unrecorded)
    for a hand merge; a sibling already there, or a link or folder by that name, is never replaced and is listed as
    `merge-pending`. A `project-changed` file gets none: its kit bytes are the ones installed, so there is nothing
    new to merge."""
    paths = _only_paths(only)

    def chosen(rel: str) -> bool:
        return (not paths or _under(rel, paths)) and not (no_scripts and rel.startswith("scripts/"))

    first, first_sources = _diff_kits(target_root, kit_name, patch=False)
    target = Path(first["target"])
    known = [item for kit in first["kits"].values() for item in kit["files"]]
    # A selection must name what a kit ships now: a retired file (project-only) is never written, so it matches none.
    shipped = [rel for source in first_sources.values() for rel in source["plan"]]
    for path in paths:
        if not any(_under(rel, [path]) for rel in shipped):
            raise ValueError(f"--only {path}: no file a kit ships is there")
    for item in known:
        if item["state"] == "unsafe" and chosen(item["path"]):
            raise ValueError(f"Refusing destination that is a link or under one: {item['path']}")

    if not dry_run:
        _recover(target, load_record(target) or {"schema_version": 1, "kits": {}, "files": {}})
    report, sources = _diff_kits(target, kit_name, patch=True)
    record = load_record(target) or {"schema_version": 1, "kits": {}, "files": {}}
    written: list[str] = []
    left: list[dict] = []
    siblings: list[str] = []
    for name, kit in report["kits"].items():
        plan = sources[name]["plan"]
        copies: list[tuple[str, Path, bytes]] = []
        expect: dict[str, str | None] = {}
        for item in kit["files"]:
            rel, state = item["path"], item["state"]
            if state == "identical" or not chosen(rel):
                continue
            if plan.get(rel, False) is None:  # a generated entry has no source
                left.append({"path": rel, "state": state, "hint": UPDATE_HINT_GENERATED})
                continue
            take = state in ("missing", "kit-newer") or (state == "project-removed" and bool(paths))
            if not take:
                left.append(item)
                if kit_new and state in ("both-changed", "differs"):
                    sibling = target / (rel + KIT_NEW)
                    if sibling.exists() or _is_link(sibling):
                        left.append({"path": rel + KIT_NEW, "state": "merge-pending"})
                    else:
                        if not dry_run:
                            atomic_write(sibling, plan[rel].read_bytes())
                        siblings.append(rel + KIT_NEW)
                continue
            data = plan[rel].read_bytes()
            entry = record["files"].get(rel)
            expect[rel] = entry["sha256"] if state == "kit-newer" and entry else None
            copies.append((rel, target / rel, data))
        if dry_run:
            written.extend(rel for rel, _dst, _data in copies)
            continue
        agents = sources[name]["agents"]
        agent = "all" if set(agents) == set(RECORD_AGENTS) else agents
        changed = _write_recorded(target, record, name, agent, sources[name]["host"], copies, expect)
        written.extend(rel for rel, _dst, _data in copies if rel not in changed)
        left.extend({"path": rel, "state": "changed-since-diff"} for rel in changed)
    result = {"target": target.as_posix(), "dry_run": dry_run, "record": (target / RECORD).is_file(),
              "written": written, "left": left}
    if kit_new:
        result["kit_new"] = siblings
    if not all(kit["record"] for kit in report["kits"].values()) or any(i["state"] == "differs" for i in left):
        result["hint"] = UPDATE_HINT_NO_RECORD
    return result


def _record_merged(target_root: Path, kit_name: str | None, merged, dry_run: bool) -> dict:
    """`record --merged`: mark files the project merged by hand from their `.kit-new` copy. Each copy must still hold
    the kit's current bytes, so the entry names exactly the version merged; the kit moving on since would otherwise
    be hidden. All arguments are checked before anything is written; then the record is written once and the copies
    are removed."""
    paths = list(dict.fromkeys(_only_paths(merged)))
    report, sources = _diff_kits(target_root, kit_name, patch=False)
    target = Path(report["target"])
    owner = {rel: name for name, source in sources.items() for rel, src in source["plan"].items() if src is not None}
    states = {item["path"]: item["state"] for kit in report["kits"].values() for item in kit["files"]}
    digests: dict[str, str] = {}
    for rel in paths:
        if rel not in owner:
            raise ValueError(f"--merged {rel}: no file a kit ships is there")
        if states.get(rel) in ("missing", "project-removed", "unsafe", "unreadable"):
            raise ValueError(f"--merged {rel}: the file is {states.get(rel)}, so there is no merge to record")
        sibling = target / (rel + KIT_NEW)
        if _is_link(sibling) or not sibling.is_file():
            raise ValueError(f"--merged {rel}: no {rel + KIT_NEW} to check the merge against (run update --kit-new)")
        kit_digest = file_digest(sources[owner[rel]]["plan"][rel].read_bytes())
        if file_digest(sibling.read_bytes()) != kit_digest:
            raise ValueError(f"--merged {rel}: {rel + KIT_NEW} is no longer the kit's version (the kit or the copy "
                             "changed); delete it and run update --kit-new again")
        digests[rel] = kit_digest
    result = {"target": target.as_posix(), "dry_run": dry_run, "recorded": paths, "skipped": []}
    if dry_run:
        return result
    _recover(target, load_record(target) or {"schema_version": 1, "kits": {}, "files": {}})
    record = load_record(target) or {"schema_version": 1, "kits": {}, "files": {}}
    commit = sdk_commit()
    for rel in paths:
        name = owner[rel]
        if name not in record["kits"]:
            agents = sources[name]["agents"]
            _record_install(record, name, "all" if set(agents) == set(RECORD_AGENTS) else agents,
                            sources[name]["host"], {}, commit)
        record["files"][rel] = {"kit": name, "sha256": digests[rel]}
    write_record(target, record)
    for rel in paths:
        _remove(target / (rel + KIT_NEW))
    return result


def record_project(target_root: Path, kit_name: str | None = None, *, dry_run: bool = False, merged=()) -> dict:
    """`record`: adopt an install made before the record existed. Each kit file whose bytes are the kit's
    (`identical`) and that has no entry gains one, since only then are the installed bytes known; every other file
    is skipped with its state as the reason, or `recorded` when it already has an entry, which is never replaced. A
    kit the record does not name gains an entry with the current SDK commit, the agents `diff` compared and the
    plan's host; one it names is left as it is. The refusals come from a read-only diff before an interrupted run is
    settled, and the record is written once, through `write_record`. With `merged`, only the named hand merges are
    recorded (`_record_merged`)."""
    if merged:
        return _record_merged(target_root, kit_name, merged, dry_run)
    _diff_kits(target_root, kit_name, patch=False)  # every refusal, before anything is written
    target = Path(target_root).resolve()
    if not dry_run:
        _recover(target, load_record(target) or {"schema_version": 1, "kits": {}, "files": {}})
    report, sources = _diff_kits(target, kit_name, patch=False)
    record = load_record(target) or {"schema_version": 1, "kits": {}, "files": {}}
    commit = sdk_commit()
    recorded: list[str] = []
    skipped: list[dict] = []
    for name, kit in report["kits"].items():
        adopt: dict[str, str] = {}
        for item in kit["files"]:
            rel, state = item["path"], item["state"]
            if rel in record["files"]:
                skipped.append({"path": rel, "reason": "recorded"})
            elif state == "identical":
                adopt[rel] = file_digest(sources[name]["plan"][rel].read_bytes())
            else:
                skipped.append({"path": rel, "reason": state})
        if not adopt:
            continue
        if name not in record["kits"]:
            agents = sources[name]["agents"]
            _record_install(record, name, "all" if set(agents) == set(RECORD_AGENTS) else agents,
                            sources[name]["host"], {}, commit)
        for rel, digest in adopt.items():
            record["files"][rel] = {"kit": name, "sha256": digest}
        recorded.extend(adopt)
    if recorded and not dry_run:
        write_record(target, record)
    return {"target": target.as_posix(), "dry_run": dry_run, "recorded": recorded, "skipped": skipped}


PROJECTS = ".conclave/projects.json"
# What the weekly drift report counts, in its line's order: (label, the diff states it counts). Any of them fails it.
DRIFT_COUNTS = (
    ("can update", ("kit-newer",)),
    ("need a merge", ("both-changed",)),
    ("unrecorded", ("differs",)),
    ("missing", ("missing",)),
    ("retired", ("project-only",)),
    ("incomplete", ("unsafe", "unreadable")),
)
DRIFT_SHOWN = 20


def load_projects(path: Path) -> list[dict]:
    """The projects the drift report covers, from `{"schema_version": 1, "projects": [{"name", "windows", "posix"}]}`:
    each with a name and a path for at least one system. Refuses with a ValueError naming the file and the entry."""
    path = Path(path)

    def fault(what: str) -> ValueError:
        return ValueError(f"{path}: {what}")

    try:
        data = json.loads(path.read_bytes().decode("utf-8"))
    except (OSError, ValueError, RecursionError) as exc:
        raise fault(f"not readable as UTF-8 JSON ({exc})") from None
    if not isinstance(data, dict) or set(data) != {"schema_version", "projects"}:
        raise fault("needs exactly the keys projects and schema_version")
    if data["schema_version"] != 1 or isinstance(data["schema_version"], bool):
        raise fault(f"schema_version must be 1, not {data['schema_version']!r}")
    if not isinstance(data["projects"], list):
        raise fault("projects must be a list")
    seen: set[str] = set()
    for index, entry in enumerate(data["projects"]):
        where = f"projects[{index}]"
        if not isinstance(entry, dict) or set(entry) != {"name", "windows", "posix"}:
            raise fault(f"{where} needs exactly the keys name, posix and windows")
        if not isinstance(entry["name"], str) or not entry["name"].strip():
            raise fault(f"{where}.name must be a non-empty string")
        where = f"{where} ({entry['name']})"
        if entry["name"] in seen:
            raise fault(f"{where}: the name appears twice")
        seen.add(entry["name"])
        for key in ("windows", "posix"):
            if entry[key] is not None and (not isinstance(entry[key], str) or not entry[key]):
                raise fault(f"{where}.{key} must be null or a non-empty path")
        if entry["windows"] is None and entry["posix"] is None:
            raise fault(f"{where}: needs a windows or a posix path")
    return data["projects"]


def drift_report(projects: list[dict], *, system: str | None = None) -> list[dict]:
    """For each project, its path on this system and the files `diff` puts in each DRIFT_COUNTS state. A project with
    no path here, or whose path is not a folder here, is `not on this machine` and fails nothing; one whose diff
    refuses carries the error."""
    system = system or os.name
    report = []
    for project in projects:
        raw = project["windows"] if system == "nt" else project["posix"]
        path = Path(os.path.expanduser(raw)) if raw else None
        row: dict = {"name": project["name"], "path": None if path is None else str(path)}
        if path is None or not path.is_dir():
            row["state"] = "not on this machine"
        else:
            try:
                diff = diff_project(path)
            except (ValueError, OSError) as exc:
                row.update(state="error", error=str(exc))
            else:
                files = [item for kit in diff["kits"].values() for item in kit["files"]]
                row["state"] = "checked"
                row["counts"] = {label: sorted(i["path"] + (f" ({i['reason']})" if "reason" in i else "")
                                               for i in files if i["state"] in states)
                                 for label, states in DRIFT_COUNTS}
        report.append(row)
    return report


def drift_lines(report: list[dict]) -> tuple[list[str], bool]:
    """The report as text and whether any project drifted. Each drifted project's files come first, then one summary
    line per project last: the failure email carries only the tail of the output, so the summary must end it."""
    details: list[str] = []
    summary: list[str] = []
    drifted = False
    for row in report:
        if row["state"] == "not on this machine":
            summary.append(f"{row['name']}: not on this machine")
            continue
        if row["state"] == "error":
            drifted = True
            summary.append(f"{row['name']}: diff refused: {row['error']}")
            continue
        counts = row["counts"]
        drifted = drifted or any(counts.values())
        summary.append(f"{row['name']}: " + ", ".join(f"{len(counts[label])} {label}" for label, _ in DRIFT_COUNTS))
        if not any(counts.values()):
            continue
        details.append(f"{row['name']} files:")
        for label, _ in DRIFT_COUNTS:
            details.extend(f"  {label}: {rel}" for rel in counts[label][:DRIFT_SHOWN])
            if len(counts[label]) > DRIFT_SHOWN:
                details.append(f"  {label}: ... and {len(counts[label]) - DRIFT_SHOWN} more")
    return details + ([""] if details else []) + ["Summary:"] + summary, drifted


def _wordpress_pin_module() -> types.ModuleType:
    """The kit's own wp_site.py (what the helpers ship with), compiled from source so no bytecode lands in the kit."""
    validator = FORGE_ROOT / "kits/wordpress/templates/scripts/lib/wp_site.py"
    module = types.ModuleType("_forge_wp_site")
    module.__file__ = str(validator)
    exec(compile(validator.read_text(encoding="utf-8"), str(validator), "exec"), module.__dict__)
    return module


def _load_wordpress_pin(target_root: Path) -> tuple[dict | None, str]:
    """Read and validate the target's site pin without running any of the target's code."""
    pin_path = target_root / WORDPRESS_PIN
    if not pin_path.is_file():
        return None, "missing"
    try:
        return _wordpress_pin_module().load(pin_path), "ok"
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return None, f"invalid: {exc}"


def _helper_command(command) -> list[str]:
    """A `headersHelper` command as the shell splits it: quoted paths stay whole, an unbalanced quote yields nothing."""
    try:
        # Windows paths keep their backslashes: non-POSIX splitting leaves the quotes on, so they are stripped here.
        parts = shlex.split(str(command or ""), posix=os.name != "nt")
    except ValueError:
        return []
    return [part[1:-1] if len(part) > 1 and part[0] == part[-1] and part[0] in "\"'" else part for part in parts]


def _doctor_wordpress(target_root: Path, add_check) -> None:
    """Read-only WordPress checks: the site pin decides the host, then each host's own setup is checked."""
    pin, pin_state = _load_wordpress_pin(target_root)
    add_check("site-pin", "ok" if pin else "missing", f"{WORDPRESS_PIN}: {pin_state}")
    host = pin["host"] if pin else None
    wp_site = _wordpress_pin_module()
    ssh_enabled = pin is None or wp_site.ssh_enabled(pin)

    if pin:
        identity = ["site_id", "url"] + (["pressable.account_id"] if host == "pressable" else [])
        missing = wp_site.unset(pin, *identity)
        add_check("site-identity", "setup_required" if missing else "ok",
                  f"wordpress-connect step 1: {', '.join(missing)}" if missing else f"{host} {pin['site_id']} {pin['url']}")
        if ssh_enabled:
            missing = wp_site.unset(pin, "ssh.item", "ssh.ssh_host", "ssh.sftp_host", "ssh.port", "ssh.username", "ssh.wp_path")
            add_check("site-ssh", "setup_required" if missing else "ok",
                      f"wordpress-connect step 2: {', '.join(missing)}" if missing else f"{pin['ssh']['username']}@{pin['ssh']['ssh_host']}")
        else:
            add_check("site-ssh", "ok", "WordPress.com Simple site: no SSH (ssh.ssh_host is null)")

    # A Pressable site always has the DDEV mirror and the pinned MCP servers. A WordPress.com site with SSH (Atomic) may
    # opt into either: a pull-only mirror (`.ddev`) and the site's own `basic` MCP servers beside the connector.
    servers = pin.get("mcp", {}) if pin else {}
    mirror = host == "pressable" or (host == "wpcom" and ssh_enabled and (target_root / ".ddev").exists())
    own_mcp = host == "pressable" or (host == "wpcom" and bool(servers))
    helpers = ["scripts/lib/wp_site.py", "scripts/lib/site_ssh.py", "scripts/site-access.py", "bin/wp-remote"]
    if own_mcp:
        helpers += ["scripts/lib/mcp_http.py", "scripts/mcp-headers.py", "scripts/check-mcp.py",
                    "scripts/create-application-password.py"]
    if host == "pressable":
        helpers += ["scripts/sftp-item.py"]
    if mirror:
        helpers += ["bin/ddev", "bin/wp", ".ddev/providers/production.yaml"]
    for rel in helpers:
        path = target_root / rel
        add_check(f"helper:{rel}", "ok" if path.is_file() else "missing", path.as_posix())
    for agent_dir in (".agents", ".claude", ".codex"):
        for skill in ("wordpress-site-safety", "wordpress-connect"):
            sk = target_root / agent_dir / "skills" / skill / "SKILL.md"
            add_check(f"skill:{skill}:{agent_dir}", "ok" if sk.is_file() else "missing", sk.as_posix())
    phpcs_xml = target_root / "phpcs.xml.dist"
    add_check("phpcs.xml.dist", "ok" if phpcs_xml.is_file() else "missing", phpcs_xml.as_posix())
    phpcs_comp = target_root / "tools/phpcs/composer.json"
    add_check("phpcs-toolchain", "ok" if phpcs_comp.is_file() else "missing", phpcs_comp.as_posix())
    if ssh_enabled:
        sshpass = shutil.which("sshpass")
        add_check("sshpass", "ok" if sshpass else "setup_required", sshpass or "operator global: apt install sshpass")

    if mirror:
        wp_root = _find_wordpress_root(target_root)
        add_check("wordpress-root", "ok" if wp_root else "setup_required",
                  wp_root.as_posix() if wp_root else "wordpress-connect step 4: bin/ddev pull production -y")
        ddev = shutil.which("ddev")
        add_check("ddev", "ok" if ddev else "setup_required", ddev or "operator global: DDEV")
        ddev_config = target_root / ".ddev/config.yaml"
        add_check("ddev-config", "ok" if ddev_config.is_file() else "setup_required",
                  ddev_config.as_posix() if ddev_config.is_file() else "wordpress-connect step 4: bin/ddev config")
        sync = target_root / "scripts/production-sync.py"
        add_check("production-sync", "ok" if sync.is_file() else "setup_required",
                  sync.as_posix() if sync.is_file() else "wordpress-connect step 4: port from jmrgroup-coza")
    elif host == "wpcom":
        ddev_dir = target_root / ".ddev"
        add_check("no-ddev", "unexpected" if ddev_dir.exists() else "ok",
                  "a WordPress.com Simple site has no SSH, so no local DDEV mirror" if ddev_dir.exists()
                  else "WordPress.com: no local mirror")

    if host == "wpcom":
        add_check("wordpress-mcp", "ok", "the user-scope WordPress.com connector"
                  + (", plus the site's own servers below" if servers else "; nothing in .mcp.json"))
    if own_mcp:
        if host == "pressable":
            add_check("mcp-pinned", "ok" if servers else "setup_required",
                      ", ".join(sorted(servers)) if servers else "wordpress-connect step 3: pin the WordPress and Pressable connections")
        try:
            registered = json.loads((target_root / ".mcp.json").read_text(encoding="utf-8")).get("mcpServers", {})
        except (OSError, ValueError, AttributeError):
            registered = {}
        for name, entry in sorted(servers.items()):
            missing = wp_site.unset(pin, *(f"mcp.{name}.{key}" for key in wp_site.REQUIRED_MCP_KEYS[entry["scheme"]]))
            server = registered.get(name)
            if not isinstance(server, dict):
                missing.append(".mcp.json")
            else:
                if server.get("url") != entry.get("url"):
                    missing.append(".mcp.json url differs from the pin")
                if server.get("type") != "http":
                    missing.append(".mcp.json type must be http")
                # The credential comes only from this checkout's helper, which pins the item for this connection.
                helper = _helper_command(server.get("headersHelper"))
                if (len(helper) < 2 or helper[-1] != name
                        or Path(helper[-2]).resolve() != (target_root / "scripts/mcp-headers.py").resolve()):
                    missing.append(f".mcp.json headersHelper must be <python> {target_root.as_posix()}/scripts/mcp-headers.py {name}")
            add_check(f"mcp:{name}", "setup_required" if missing else "ok",
                      f"wordpress-connect step 3: {', '.join(missing)}" if missing else entry["url"])

PROBE_SECONDS = 15  # how long doctor waits on one question to a reviewer CLI


def _own_group() -> dict:
    """Popen arguments that start a child in a process group of its own, with no console window, so its whole tree
    can be ended without touching this process."""
    if os.name == "nt":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, "CREATE_NO_WINDOW", 0)}
    return {"start_new_session": True}


CREATE_SUSPENDED = 0x00000004
JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS = 9
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000


class _IO_COUNTERS(ctypes.Structure):
    _fields_ = [("ReadOperationCount", ctypes.c_uint64), ("WriteOperationCount", ctypes.c_uint64),
                ("OtherOperationCount", ctypes.c_uint64), ("ReadTransferCount", ctypes.c_uint64),
                ("WriteTransferCount", ctypes.c_uint64), ("OtherTransferCount", ctypes.c_uint64)]


class _JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", ctypes.c_uint32), ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", ctypes.c_uint32),
                ("Affinity", ctypes.c_size_t), ("PriorityClass", ctypes.c_uint32),
                ("SchedulingClass", ctypes.c_uint32)]


class _JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [("BasicLimitInformation", _JOBOBJECT_BASIC_LIMIT_INFORMATION), ("IoInfo", _IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]


_WIN32_APIS = None


def _win32():
    """Return cached (kernel32, ntdll) handles with declared signatures (Windows only)."""
    global _WIN32_APIS
    if _WIN32_APIS is None:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
        kernel32.CreateJobObjectW.restype = ctypes.c_void_p
        kernel32.SetInformationJobObject.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]
        kernel32.SetInformationJobObject.restype = ctypes.c_int
        kernel32.AssignProcessToJobObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        kernel32.AssignProcessToJobObject.restype = ctypes.c_int
        kernel32.TerminateJobObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        kernel32.TerminateJobObject.restype = ctypes.c_int
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel32.CloseHandle.restype = ctypes.c_int
        ntdll = ctypes.WinDLL("ntdll")
        ntdll.NtResumeProcess.argtypes = [ctypes.c_void_p]
        ntdll.NtResumeProcess.restype = ctypes.c_int32
        _WIN32_APIS = kernel32, ntdll
    return _WIN32_APIS


def _open_windows_job():
    """Create a Win32 job object configured with JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE so descendants die with it."""
    kernel32, _ = _win32()
    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        raise ctypes.WinError(ctypes.get_last_error())
    info = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
    info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not kernel32.SetInformationJobObject(job, JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS, ctypes.byref(info),
                                            ctypes.sizeof(info)):
        err = ctypes.get_last_error()
        kernel32.CloseHandle(job)
        raise ctypes.WinError(err)
    return job


def _assign_and_resume_windows(job, proc: subprocess.Popen) -> None:
    """Assign a suspended Windows process to `job` and resume its main thread."""
    kernel32, ntdll = _win32()
    if not kernel32.AssignProcessToJobObject(job, ctypes.c_void_p(int(proc._handle))):
        raise ctypes.WinError(ctypes.get_last_error())
    status = ntdll.NtResumeProcess(ctypes.c_void_p(int(proc._handle)))
    if status != 0:
        raise OSError(f"NtResumeProcess returned 0x{status & 0xFFFFFFFF:08x}")


def _close_windows_job(job) -> None:
    """Terminate every process in `job` and close its handle cleanly."""
    kernel32, _ = _win32()
    kernel32.TerminateJobObject(job, 1)
    kernel32.CloseHandle(job)


def _kill_tagged(tag: str) -> None:
    """End every surviving POSIX process whose environment carries `CONCLAVE_CHECK_ALL_TAG=<tag>` (even detached sessions)."""
    if os.name == "nt":
        return
    import signal

    needle = f"CONCLAVE_CHECK_ALL_TAG={tag}"
    needle_bytes = needle.encode()
    self_pid = os.getpid()
    if os.path.isdir("/proc"):
        for _ in range(2):
            try:
                entries = os.listdir("/proc")
            except OSError:
                return
            for entry in entries:
                if not entry.isdigit():
                    continue
                pid = int(entry)
                if pid == self_pid or pid <= 1:
                    continue
                try:
                    with open(f"/proc/{entry}/environ", "rb") as handle:
                        if needle_bytes in handle.read().split(b"\0"):
                            os.kill(pid, signal.SIGKILL)
                except OSError:
                    continue
        return
    try:
        out = subprocess.run(["ps", "eww", "-ax", "-o", "pid=,command="], capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return
    for line in out.splitlines():
        parts = line.split(None, 1)
        if len(parts) < 2 or not parts[0].isdigit():
            continue
        pid = int(parts[0])
        if pid == self_pid or pid <= 1:
            continue
        if needle in parts[1].split():
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                continue


def _kill_tree(proc: subprocess.Popen, job=None, tag: str | None = None) -> None:
    """End a child started with `_own_group()` and everything it started, including orphaned or detached descendants."""
    if os.name == "nt":
        if job is not None:
            _close_windows_job(job)
        else:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    else:
        import signal
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:  # the group ended before the kill
            pass
        if tag:
            _kill_tagged(tag)
    try:
        proc.kill()
    except OSError:
        pass


def _probe(argv: list, timeout: float | None = None) -> tuple[int | None, str, str]:
    """Run one bounded question to a CLI: (exit code, output, problem). The exit code is None when it could not start
    (`problem` says why) or ran past `timeout`. Its whole process tree is ended (`taskkill /T` on Windows, its process
    group elsewhere) on a timeout and on any interruption, Ctrl+C included, since the probe runs in a group of its
    own that the parent's Ctrl+C does not reach and a CLI may be a wrapper whose child would outlive it."""
    timeout = PROBE_SECONDS if timeout is None else timeout
    windows = os.name == "nt"
    group = _own_group()
    launch: list | str = argv
    if windows and Path(argv[0]).suffix.lower() in (".cmd", ".bat"):
        # A wrapper script runs through cmd.exe, which strips one pair of outer quotes from what follows /c: the whole
        # command is quoted once more, so a wrapper and an argument that both hold spaces keep their own quotes.
        launch = f'{os.environ.get("COMSPEC", "cmd.exe")} /d /s /c "{subprocess.list2cmdline(argv)}"'
    try:
        proc = subprocess.Popen(launch, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                **group)
    except OSError as exc:
        return None, "", f"could not start: {exc.strerror or exc}"

    def end_tree() -> None:
        _kill_tree(proc)
        try:
            # Bounded: a process that left the tree can hold the output pipe open long after the tree is ended. The
            # pipe is then left to it, not closed: closing a pipe that is being read waits for that read on Windows.
            proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            pass

    try:
        out, _ = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        end_tree()
        return None, "", f"no answer within {timeout:g} seconds"
    except BaseException:  # an interrupt ends the probe and its tree before it passes on
        end_tree()
        raise
    return proc.returncode, out.decode("utf-8", "replace"), ""


def _agy_flags_check(dispatch, executable: str) -> tuple[str, str]:
    """(status, detail) for one Antigravity reviewer: every flag the dispatcher passes is in the installed CLI's
    --help, and the CLI accepts the dispatcher's session settings. A probe that failed is never `ok`."""
    code, text, problem = _probe([executable, "--help"])
    if code is None:
        return "setup_required", f"{executable} --help: {problem}"
    if code != 0:
        return "unexpected", f"{executable} --help exited {code}"
    missing = dispatch.agy_flags_missing(text)
    if missing:
        return "unexpected", (f"{executable} no longer lists {', '.join(missing)}, which the dispatcher passes: every "
                              f"Antigravity review would return no review")
    fd, name = tempfile.mkstemp(prefix="forge-agy-settings-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(dispatch.AGY_REVIEW_SETTINGS, handle)
        code, text, problem = _probe([executable, "--settings", name, "agents"])
    finally:
        Path(name).unlink(missing_ok=True)
    if code is None:
        return "setup_required", f"{executable} --settings: {problem}"
    said = next((line.strip() for line in text.splitlines() if "--settings:" in line), "")
    if said:
        return "unexpected", f"{executable} refuses the dispatcher's settings: {said}"
    if code != 0:
        # Not a refusal of the settings: the CLI failed for a reason of its own (it cannot start, it is not signed in).
        first = next((line.strip() for line in text.splitlines() if line.strip()), "no output")
        return "unexpected", f"{executable} --settings <file> agents exited {code}: {first[:200]}"
    code, text, problem = _probe([executable, "--version"])
    if code is None:
        return "setup_required", f"{executable} --version: {problem}"
    if code != 0 or not text.strip():
        return "unexpected", f"{executable} --version exited {code} and named no version"
    version = text.strip().splitlines()[0]
    return "ok", f"{executable} {version} lists {', '.join(dispatch.AGY_FLAGS)} and accepts the review settings"


def _doctor_reviewer(target_root: Path, add_check) -> None:
    """Read-only reviewer checks: the pin loads under the dispatcher's own rules and each routed CLI is installed."""
    dispatcher = FORGE_ROOT / "kits/reviewer/templates/scripts/review-dispatch.py"
    module = types.ModuleType("_forge_review_dispatch")
    module.__file__ = str(dispatcher)
    exec(compile(dispatcher.read_text(encoding="utf-8"), str(dispatcher), "exec"), module.__dict__)
    pin = None
    try:
        pin = module.load_pin(target_root / REVIEWER_PIN)
        add_check("reviewer-pin", "ok", REVIEWER_PIN)
    except module.Refused as exc:
        add_check("reviewer-pin", "missing", str(exc))
    for rel in ("scripts/review-dispatch.py", "docs/review-round-prompt.md"):
        path = target_root / rel
        add_check(rel, "ok" if path.is_file() else "missing", path.as_posix())
    for agent_dir in AGENT_DIRS:
        sk = target_root / agent_dir / "skills/independent-review/SKILL.md"
        add_check(f"skill:independent-review:{agent_dir}", "ok" if sk.is_file() else "missing", sk.as_posix())
    if pin:
        flags_checked: dict = {}
        for name, reviewer in pin["reviewers"].items():
            # The dispatcher's own lookup, so doctor probes the executable a review would run: on Windows
            # shutil.which looks in the working directory first, and the dispatcher never does.
            found = module.find_cli(reviewer["cli"])
            add_check(f"reviewer:{name}", "ok" if found else "setup_required",
                      f"{reviewer['model']} via {found}" if found else f"{reviewer['cli']} CLI not installed; a round routed to this reviewer has no review")
            if found and reviewer["cli"] == "agy":
                if found not in flags_checked:  # one set of probes per executable, however many reviewers use it
                    flags_checked[found] = _agy_flags_check(module, found)
                add_check(f"reviewer-flags:{name}", *flags_checked[found])


def _doctor_unattended(target_root: Path, add_check, system: str | None = None) -> None:
    """The unattended kit's files, the todo kit it runs under (the run guard), and tmux, which holds the run: it
    exists on Linux and in WSL only, so on Windows the kit runs in WSL."""
    templates = FORGE_ROOT / "kits/unattended/templates"
    for src in sorted(p for p in templates.rglob("*") if p.is_file() and "__pycache__" not in p.parts):
        rel = src.relative_to(templates).as_posix()
        path = target_root / rel
        if rel == "docs/unattended-prompt.md":
            # The seed prompt is wherever the profile's prompt_file says, which the project may move.
            try:
                named = json.loads((target_root / ".conclave/unattended.json").read_text(encoding="utf-8"))["prompt_file"]
                path = target_root / named if isinstance(named, str) and named else path
            except (OSError, ValueError, KeyError, TypeError):
                pass
        add_check(rel, "ok" if path.is_file() else "missing", path.as_posix())
    for agent_dir in AGENT_DIRS:
        sk = target_root / agent_dir / "skills/unattended-run/SKILL.md"
        add_check(f"skill:unattended-run:{agent_dir}", "ok" if sk.is_file() else "missing", sk.as_posix())
    guard = target_root / "scripts/campaign_guard.py"
    add_check("todo-kit", "ok" if guard.is_file() else "setup_required",
              guard.as_posix() if guard.is_file() else f"install the todo kit first: python forge.py kit {target_root.as_posix()} todo")
    if (system or os.name) == "nt":
        add_check("tmux", "setup_required", "tmux runs on Linux and in WSL only: run the unattended kit in WSL (wsl.exe)")
        return
    tmux = shutil.which("tmux")
    add_check("tmux", "ok" if tmux else "setup_required", tmux or "install tmux (sudo apt install tmux)")


def _doctor_automations(target_root: Path, add_check) -> None:
    """Read-only automations checks: the task list loads under the runner's own rules, names its folder and only
    scripts that exist, and this machine has the scheduler the installers drive."""
    runner = FORGE_ROOT / "kits/automations/templates" / AUTOMATIONS_DIR / "run.py"
    module = types.ModuleType("_forge_automations_run")
    module.__file__ = str(runner)
    exec(compile(runner.read_text(encoding="utf-8"), str(runner), "exec"), module.__dict__)
    manifest = None
    tasks_json = f"{AUTOMATIONS_DIR}/tasks.json"
    try:
        manifest = module.load_manifest(str(target_root / tasks_json))
        add_check("automations-tasks", "ok", tasks_json)
    except (OSError, ValueError) as exc:  # TaskError and a JSON decode error are both ValueErrors
        add_check("automations-tasks", "missing", f"{tasks_json}: {exc}")
    if manifest is not None:
        folder = manifest["folder"]
        add_check("automations-folder", "ok" if folder else "setup_required",
                  folder or f"set folder in {tasks_json} to \\<Project>\\ before adding a task")
        for name, task in manifest["tasks"].items():
            script = task["command"][1] if task["command"][0] == "python" and len(task["command"]) > 1 else None
            ok = script is not None and (target_root / script).is_file()
            add_check(f"task:{name}", "ok" if ok else "missing",
                      " ".join(task["command"]) if ok else f"command must be python and a script that exists: {task['command']}")
    for rel in (*AUTOMATIONS_SCRIPTS, f"{AUTOMATIONS_DIR}/README.md", "scripts/tests/test_automations.py"):
        path = target_root / rel
        add_check(rel, "ok" if path.is_file() else "missing", path.as_posix())
    for agent_dir in AGENT_DIRS:
        sk = target_root / agent_dir / "skills/scheduled-automations/SKILL.md"
        add_check(f"skill:scheduled-automations:{agent_dir}", "ok" if sk.is_file() else "missing", sk.as_posix())
    if os.name == "nt":
        found = shutil.which("pythonw")
        add_check("scheduler:pythonw", "ok" if found else "setup_required",
                  found or "install Python 3 for Windows (pythonw.exe on PATH)")
    else:
        add_check("scheduler:systemctl", *_systemd_user_manager())


def _claude_stop_commands(doc) -> list:
    """Stop hook commands in Claude Code's shape: `{"hooks": {"Stop": [{"hooks": [{"command"}]}]}}`."""
    return [h.get("command") for entry in doc.get("hooks", {}).get("Stop", []) for h in entry.get("hooks", [])]


def _antigravity_stop_commands(doc) -> tuple[list, list]:
    """Stop hook commands in Antigravity's shape, each top-level key a named hook with a flat `Stop` list of handlers
    (the CLI's `hooks.md`): the enabled hooks' commands, and the disabled ones' (`"enabled": false`)."""
    enabled, disabled = [], []
    for hook in doc.values():
        if not isinstance(hook, dict) or not isinstance(hook.get("Stop", []), list):
            continue
        commands = [h.get("command") for h in hook.get("Stop", []) if isinstance(h, dict)]
        (disabled if hook.get("enabled", True) is False else enabled).extend(commands)
    return enabled, disabled


def _stop_hook_wiring(target_root: Path, hook_file: str = ".claude/settings.json") -> tuple[str, str]:
    """Whether an agent's hook file runs the campaign guard's Stop hook: `.claude/settings.json` (Claude Code's shape)
    or `.agents/hooks.json` (Antigravity's). The todo kit seeds the file when a project has none; a project's own
    file is never overwritten, so there the hook is added by hand."""
    settings = target_root / hook_file
    seed = FORGE_ROOT / "kits/todo/templates" / hook_file
    hint = f"add the Stop hook from {seed.as_posix()} to {settings.as_posix()}"
    antigravity = hook_file == ".agents/hooks.json"  # .claude/settings.json and .codex/hooks.json share one shape
    disabled: list = []
    try:
        doc = json.loads(settings.read_text(encoding="utf-8"))
        if antigravity:
            commands, disabled = _antigravity_stop_commands(doc)
        else:
            commands = _claude_stop_commands(doc)
    except FileNotFoundError:
        return "setup_required", hint
    except (OSError, ValueError, AttributeError, TypeError) as exc:
        return "setup_required", f"{settings.as_posix()} does not parse as a hook file: {exc}; {hint}"

    # Codex runs the guard through its wrapper (scripts/codex-campaign-hook.py); the others call it directly.
    markers = ("codex-campaign-hook.py",) if hook_file == ".codex/hooks.json" else ("campaign_guard.py", "stop-hook")

    def guarded(found) -> bool:
        return any(isinstance(c, str) and all(m in c for m in markers) for c in found)

    if guarded(commands):
        return "ok", settings.as_posix()
    if guarded(disabled):
        return "setup_required", f"the Stop hook in {settings.as_posix()} is disabled (\"enabled\": false); {hint}"
    if antigravity and isinstance(doc, dict) and isinstance(doc.get("hooks"), dict) and "Stop" in doc["hooks"]:
        return "setup_required", (f"{settings.as_posix()} is in Claude Code's shape, which Antigravity loads as one "
                                  f"hook named 'hooks'; {hint}")
    return "setup_required", hint


def _codex_trust_module() -> types.ModuleType:
    """The todo kit's codex-hook-trust.py, loaded from the kit (forge reads, the project's copy is the project's)."""
    path = FORGE_ROOT / "kits/todo/templates/scripts/codex-hook-trust.py"
    module = types.ModuleType("_forge_codex_hook_trust")
    module.__file__ = str(path)
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), module.__dict__)
    return module


def _codex_hook_approval(target_root: Path) -> tuple[str, str]:
    """Whether Codex will run the project's campaign Stop hook: approved against its current hash, as Codex's own
    `hooks/list` reports it (read-only). Codex skips a hook that is `untrusted` or `modified`."""
    trust = _codex_trust_module()
    fix = f"run python scripts/codex-hook-trust.py in {Path(target_root).as_posix()}"
    try:
        results = trust.trust(Path(target_root), check=True)
    except (trust.TrustError, OSError) as exc:
        return "setup_required", f"{exc}; {fix}"
    disabled = [r["key"] for r in results if not r.get("enabled", True)]
    if disabled:
        return "setup_required", f"the Stop hook is disabled in Codex ({', '.join(disabled)}); enable it in Codex's hook list"
    stale = [f"{r['key']} is {r['status']}" for r in results if r["status"] != "trusted"]
    if stale:
        return "setup_required", f"Codex skips the Stop hook until it is approved ({'; '.join(stale)}); {fix}"
    return "ok", ", ".join(r["key"] for r in results)


def _systemd_user_manager(run=subprocess.run) -> tuple[str, str]:
    """Whether this user's systemd manager answers (read-only): `systemctl` on PATH is not enough, because WSL
    without systemd, or a session with no user bus, has the binary and no manager."""
    found = shutil.which("systemctl")
    if not found:
        return "setup_required", "systemctl not on PATH: install.sh needs systemd user timers"
    try:
        proc = run([found, "--user", "show-environment"], capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return "setup_required", f"systemd user manager did not answer: {exc}"
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip().splitlines()
        return "setup_required", f"systemd user manager not reachable: {detail[0] if detail else proc.returncode}"
    return "ok", f"{found} --user answers"


def doctor_repo(target_root: Path, kit_name: str | None = None) -> dict:
    """Read-only stack health check for Laravel and/or WordPress overlays across all three agents."""
    target_root = Path(target_root).resolve()
    checks: list[dict[str, str]] = []

    def add_check(name: str, status: str, detail: str) -> None:
        checks.append({"name": name, "status": status, "detail": detail})

    if kit_name is None:
        if _find_laravel_app_root(target_root) is not None:
            kit_name = "laravel"
        elif (target_root / WORDPRESS_PIN).is_file() or _find_wordpress_root(target_root) is not None:
            kit_name = "wordpress"
        else:
            kit_name = "base"

    if kit_name == "laravel":
        app_root = _find_laravel_app_root(target_root)
        if app_root is not None:
            add_check("artisan", "ok", (app_root / "artisan").as_posix())
        else:
            add_check("artisan", "missing", f"no artisan under {target_root.as_posix()}")
        lsp_py = target_root / "scripts/lsp-diagnostics.py"
        add_check("lsp-diagnostics.py", "ok" if lsp_py.is_file() else "missing", lsp_py.as_posix())
        boost_json = (app_root / "boost.json") if app_root else (target_root / "boost.json")
        add_check("boost.json", "ok" if boost_json.is_file() else "missing", boost_json.as_posix())
        boost_package = _composer_package_installed(app_root, "laravel/boost") if app_root else None
        add_check("laravel/boost", "ok" if boost_package else "setup_required",
                  boost_package.as_posix() if boost_package else "composer require --dev laravel/boost (dependency approval)")
        for agent_dir in (".agents", ".claude", ".codex"):
            sk = target_root / agent_dir / "skills/laravel-boost/SKILL.md"
            add_check(f"skill:{agent_dir}", "ok" if sk.is_file() else "missing", sk.as_posix())
        for binary, hint in (
            ("laravel-lsp", "composer global require laravel/lsp"),
            ("tailwindcss-language-server", "npm install -g @tailwindcss/language-server"),
            ("intelephense", "npm install -g intelephense"),
        ):
            found = shutil.which(binary)
            add_check(binary, "ok" if found else "setup_required", found or hint)
    elif kit_name == "wordpress":
        _doctor_wordpress(target_root, add_check)
    elif kit_name == "reviewer":
        _doctor_reviewer(target_root, add_check)
    elif kit_name == "automations":
        _doctor_automations(target_root, add_check)
    elif kit_name == "unattended":
        _doctor_unattended(target_root, add_check)
    elif kit_name == "todo":
        for agent_dir in (".agents", ".claude", ".codex"):
            for skill in TODO_SKILLS:
                sk = target_root / agent_dir / "skills" / skill / "SKILL.md"
                add_check(f"skill:{skill}:{agent_dir}", "ok" if sk.is_file() else "missing", sk.as_posix())
        for rel in ("scripts/todo-graph.py", "scripts/lib/todo_graph.py", "scripts/campaign_guard.py",
                    "todo/README.md", "docs/todo-workflow.md"):
            path = target_root / rel
            add_check(rel, "ok" if path.is_file() else "missing", path.as_posix())
        add_check("pre-commit-hook", *_pre_commit_hook_check(target_root))
        add_check("stop-hook", *_stop_hook_wiring(target_root))
        if (target_root / ".agents").is_dir():
            add_check("stop-hook:.agents", *_stop_hook_wiring(target_root, ".agents/hooks.json"))
        if (target_root / ".codex").is_dir():
            add_check("stop-hook:.codex", *_stop_hook_wiring(target_root, ".codex/hooks.json"))
            add_check("stop-hook-approved:.codex", *_codex_hook_approval(target_root))
    else:
        for entry in ("AGENTS.md", "GEMINI.md", "CLAUDE.md", "CODEX.md"):
            p = target_root / entry
            add_check(entry, "ok" if p.is_file() else "missing", p.as_posix())

    missing_count = sum(1 for c in checks if c["status"] in ("missing", "setup_required", "unexpected"))
    return {
        "target": target_root.as_posix(),
        "kit": kit_name,
        "missing_or_setup_required": missing_count,
        "checks": checks,
    }


TODO_POINTER = (
    "\n## TODO workflow\n\n"
    "Plan and build through the TODO system: [docs/todo-workflow.md](./docs/todo-workflow.md).\n"
)
ENTRY_DOCS = ("AGENTS.md", "GEMINI.md", "CLAUDE.md", "CODEX.md")


def provision(
    target_root: Path,
    *,
    agent: str = "all",
    include_scripts: bool = True,
    with_todo: bool = False,
    kits: list[str] | None = None,
    wordpress_host: str | None = None,
    overwrite_existing_docs: bool = False,
) -> dict:
    """`init`: copy the base kit plus only the kits asked for, never the whole SDK, and never over a file the project
    already has. `with_todo` is shorthand for the `todo` kit; `overwrite_existing_docs` (`init --force`) rewrites only
    the four entry docs. The install record notes what was written and holds no path back to the SDK, so the
    project owns everything init copied.
    """
    agent = normalize_agent(agent)
    target_root = Path(target_root).resolve()
    # Checked on the resolved path, which is the one written to, so no link (dangling or retargeted before this run)
    # can lead into git's own data, or lead init over the kits' own source.
    if any(os.path.normcase(part) == ".git" for part in target_root.parts):
        raise ValueError(f"Target is inside a .git folder: {target_root}")
    if os.path.normcase(str(target_root)) == os.path.normcase(str(FORGE_ROOT)):
        raise ValueError(f"Target is the Conclave-SDK source folder itself (use self-sync): {target_root}")
    if target_root.exists() and (not target_root.is_dir() or _is_link(target_root)):
        raise ValueError(f"Target must be a folder, or a path that does not exist yet: {target_root}")

    chosen = ["base", *(["todo"] if with_todo else []), *(kits or [])]
    selected = [k for k in KIT_ORDER if k in chosen] + [k for k in dict.fromkeys(chosen) if k not in KIT_ORDER]

    def include(rel: str) -> bool:
        return include_scripts or not rel.startswith("scripts/")

    # Every kit is planned, and every destination it will write checked, before the first file is written, so a
    # kit that refuses (an unknown name, no artisan, a pinned host) or a path one cannot write leaves nothing behind.
    for kit_name in selected:
        for _src, dst, rel, _generated in kit_plan(target_root, kit_name, agent=agent, host=wordpress_host)[0]:
            if include(rel) and not (dst.exists() or dst.is_symlink()) and _has_unsafe_parent(target_root, rel):
                raise ValueError(f"Refusing destination with unsafe parent: {rel}")
    if target_root.is_dir():
        load_record(target_root)  # a record that cannot be used refuses here too, before any kit writes
    target_root.mkdir(parents=True, exist_ok=True)

    # --force: the docs it may replace, what each holds from the kit, and what init leaves in it (AGENTS.md gains the
    # TODO pointer with the todo kit). A doc already holding that is left alone.
    base_templates = FORGE_ROOT / "kits/base/templates"
    pointer = TODO_POINTER.encode("utf-8") if "todo" in selected else b""
    docs = {doc: ((base_templates / doc).read_bytes(), (base_templates / doc).read_bytes() + (pointer if doc == "AGENTS.md" else b""))
            for doc in ENTRY_DOCS if overwrite_existing_docs and _rel_allowed_for_agent(doc, agent)
            and not (target_root / doc).is_symlink()}
    for doc, (_kit_bytes, final) in docs.items():
        _check_backup(target_root, doc, final)

    kit_results = [apply_kit(target_root, kit_name, agent=agent, host=wordpress_host, include=include)
                   for kit_name in selected]

    forced: list[str] = []
    backups: list[str] = []
    if docs:
        record = load_record(target_root) or {"schema_version": 1, "kits": {}, "files": {}}
        fresh = set(kit_results[0]["installed"])  # installed by this run: the kit's bytes, the pointer still to come
        # Anything an interrupted run staged was finished by the kits' own install above.
        for doc, (_kit_bytes, final) in docs.items():
            path = target_root / doc
            current = path.read_bytes() if path.is_file() else None
            if doc in fresh or current == final:
                continue
            backup = target_root / (doc + REPLACED)
            # The project's doc is kept before anything replaces it; a backup already holding it is from a run that
            # failed after backing it up, and stays as it is.
            if current is not None and not (backup.is_file() and backup.read_bytes() == current):
                atomic_write(backup, current)
                backups.append(doc + REPLACED)
            forced.append(doc)
        # A doc --force replaces holds the kit's bytes afterwards, so it is recorded as installed, as a fresh one is.
        _write_recorded(target_root, record, "base", agent, None,
                        [(doc, target_root / doc, docs[doc][0]) for doc in forced])

    agents_md = target_root / "AGENTS.md"
    fresh_agents = "AGENTS.md" in kit_results[0]["installed"] or "AGENTS.md" in forced
    if "todo" in selected and fresh_agents and agents_md.is_file():
        atomic_write(agents_md, agents_md.read_bytes() + TODO_POINTER.encode("utf-8"))

    written = [rel for r in kit_results for rel in r["installed"]] + forced
    skipped = [rel for r in kit_results for rel in r["preserved"] if rel not in forced]
    return {
        "target": target_root.as_posix(),
        "agent": agent,
        "written": written,
        "skipped": skipped,
        "backups": backups,
        "kits": kit_results,
    }


REPLACED = ".replaced"


def _check_backup(target_root: Path, doc: str, final: bytes) -> None:
    """Refuse `init --force` before any file is written when the doc it would replace cannot be kept: its
    `<doc>.replaced` is a link, a folder, or a file holding other bytes (the only copy of an earlier version). A
    backup holding the doc's own bytes is the one an interrupted run made, so the run may go on."""
    path = target_root / doc
    if path.exists() and not path.is_file():
        raise ValueError(f"{doc} is not a file; refusing to replace it")
    current = path.read_bytes() if path.is_file() else None
    if current is None or current == final:
        return
    backup = target_root / (doc + REPLACED)
    if _is_link(backup) or (backup.exists() and not backup.is_file()):
        raise ValueError(f"{doc + REPLACED} is a link or a folder; refusing to replace {doc}")
    if backup.is_file() and backup.read_bytes() != current:
        raise ValueError(f"{doc + REPLACED} already holds an earlier {doc}; move it aside before init --force "
                         f"replaces {doc} again")


def self_sync(dry_run: bool = False) -> dict:
    """`self-sync`: bring the SDK's own installed copy of its kits (SELF_KITS) up to date with the kits, which are the
    only source (AGENTS.md). Only SELF_PREFIXES files are written; the SDK's entry docs, docs/, todo/ and pins stay
    its own. This is the one place forge overwrites, and only inside the SDK folder: projects are never synced."""
    updated: list[str] = []
    for kit_name in SELF_KITS:
        template_root = FORGE_ROOT / "kits" / kit_name / "templates"
        for src in sorted(template_root.rglob("*")):
            rel = src.relative_to(template_root).as_posix()
            if not src.is_file() or not rel.startswith(SELF_PREFIXES) or not _rel_allowed_for_agent(rel, "all"):
                continue
            dst = FORGE_ROOT / rel
            if dst.is_symlink() or _has_unsafe_parent(FORGE_ROOT, rel):
                raise ValueError(f"Refusing to write through a link in the SDK folder: {rel}")
            if dst.is_file() and dst.read_bytes().replace(b"\r\n", b"\n") == src.read_bytes().replace(b"\r\n", b"\n"):
                continue
            if not dry_run:
                atomic_write(dst, src.read_bytes())
            updated.append(rel)
    return {"target": FORGE_ROOT.as_posix(), "dry_run": dry_run, "updated": updated}


def check_repo(target_root: Path) -> dict:
    target_root = Path(target_root).resolve()
    agy_skills = sorted(p.parent.name for p in (target_root / ".agents/skills").glob("*/SKILL.md"))
    claude_skills = sorted(p.parent.name for p in (target_root / ".claude/skills").glob("*/SKILL.md"))
    codex_skills = sorted(p.parent.name for p in (target_root / ".codex/skills").glob("*/SKILL.md"))
    claude_agents = sorted(p.stem for p in (target_root / ".claude/agents").glob("*.md"))
    return {
        "target": target_root.as_posix(),
        "has_agents_md": (target_root / "AGENTS.md").is_file(),
        "has_gemini_md": (target_root / "GEMINI.md").is_file(),
        "has_claude_md": (target_root / "CLAUDE.md").is_file(),
        "has_codex_md": (target_root / "CODEX.md").is_file(),
        "has_todo_graph": (target_root / "scripts/todo-graph.py").is_file(),
        "has_verify_agent_tiers": (target_root / "scripts/verify-agent-tiers.mjs").is_file(),
        "agy_skills": agy_skills,
        "claude_skills": claude_skills,
        "codex_skills": codex_skills,
        "claude_agents": claude_agents,
        "kits": installed_kits(target_root),
    }


def _unittest_suite(name: str, folder: str, timeout: int) -> dict:
    return {"name": name, "kind": "unittest", "path": folder, "timeout": timeout,
            "argv": [sys.executable, "-B", "-m", "unittest", "discover", "-s", folder]}


# Skill copies (D01 T02 §5): a kit keeps each skill file once, under `templates/.claude/skills/`. Its Antigravity and
# Codex copies are that file plus the differences a patch file declares, so no copy drifts by hand.
SKILL_COPY_AGENTS = {"agents": ".agents", "codex": ".codex"}  # the folder under skill-patches/ -> the agent's folder
SKILL_PATCHES = "skill-patches"


class SkillCopyError(ValueError):
    """A skill patch that cannot be read, no longer applies or has no source: the command ends with exit 2."""


def load_skill_patch(path: Path) -> dict:
    """Read `<overlay>/skill-patches/<agent>/<skill path>.json`: `{"schema_version": 1, "replace": [{"find", "with"}]}`.

    Returns `{"file": path, "replace": [(find, with), ...]}` in the file's order, or raises SkillCopyError naming it."""
    where = Path(path).as_posix()
    try:
        data = json.loads(Path(path).read_bytes().decode("utf-8"))
    except (ValueError, RecursionError) as exc:
        raise SkillCopyError(f"{where}: not a JSON file in UTF-8 ({exc})") from exc
    if not isinstance(data, dict) or set(data) != {"schema_version", "replace"}:
        raise SkillCopyError(f"{where}: needs exactly the keys schema_version and replace")
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise SkillCopyError(f"{where}: schema_version must be 1")
    if not isinstance(data["replace"], list):
        raise SkillCopyError(f"{where}: replace must be a list")
    pairs: list[tuple[str, str]] = []
    for number, entry in enumerate(data["replace"], 1):
        if not isinstance(entry, dict) or set(entry) != {"find", "with"}:
            raise SkillCopyError(f"{where}: replacement {number} needs exactly the keys find and with")
        if not isinstance(entry["find"], str) or not isinstance(entry["with"], str):
            raise SkillCopyError(f"{where}: replacement {number} needs find and with as text")
        if not entry["find"]:
            raise SkillCopyError(f"{where}: replacement {number} has an empty find")
        pairs.append((entry["find"], entry["with"]))
    return {"file": Path(path), "replace": pairs}


def generate_copy(source_text: str, patch: dict | None) -> str:
    """An agent's copy of a skill file: `source_text` with the patch's replacements applied in order, each to the
    result of the one before. A `find` must occur exactly once at its turn; no patch is the source unchanged."""
    text = source_text
    for find, replacement in (patch["replace"] if patch else ()):
        # Every place the text starts, overlapping ones too: `---` is in `----` twice, and str.count says once.
        count = sum(text.startswith(find, start) for start in range(len(text) - len(find) + 1))
        if count != 1:
            raise SkillCopyError(f"{Path(patch['file']).as_posix()}: find {find!r} occurs {count} times in the source, "
                                 "not once: the patch no longer applies")
        text = text.replace(find, replacement, 1)
    return text


def _skill_overlays(root: Path) -> list[Path]:
    """Every folder that holds a `templates/` tree: each kit, and each host overlay of a kit (`hosts/<host>/`)."""
    kits = root / "kits"
    found: list[Path] = []
    for kit in (sorted(path for path in kits.iterdir() if path.is_dir()) if kits.is_dir() else []):
        hosts = kit / "hosts"
        found.append(kit)
        found.extend(sorted(path for path in hosts.iterdir() if path.is_dir()) if hosts.is_dir() else [])
    return [overlay for overlay in found if (overlay / "templates").is_dir() or (overlay / SKILL_PATCHES).is_dir()]


def _files_under(folder: Path) -> list[Path]:
    return sorted(path for path in folder.rglob("*") if path.is_file()) if folder.is_dir() else []


def _codex_interface_file(agent_dir: str, skill_path: str) -> bool:
    """Codex's own interface file, kept by hand beside each skill: `.codex/skills/<skill>/agents/openai.yaml`.
    It is never generated, patched or reported, whatever the Claude tree holds at that path."""
    parts = PurePosixPath(skill_path).parts
    return agent_dir == ".codex" and len(parts) == 3 and parts[1:] == ("agents", "openai.yaml")


def _skill_copy_plan(root: Path) -> tuple[dict[Path, bytes], list[Path]]:
    """What the generator would write (destination -> bytes) and the copies no Claude source accounts for.

    Nothing is written here: every patch is loaded and every copy built first, so a refusal leaves the tree alone."""
    outputs: dict[Path, bytes] = {}
    stray: list[Path] = []
    for overlay in _skill_overlays(root):
        source_root = overlay / "templates/.claude/skills"
        patches_root = overlay / SKILL_PATCHES
        sources = {path.relative_to(source_root).as_posix(): path for path in _files_under(source_root)}
        patches: dict[tuple[str, str], Path] = {}
        for path in _files_under(patches_root):
            parts = path.relative_to(patches_root).parts
            where = path.relative_to(root).as_posix()
            if parts[0] not in SKILL_COPY_AGENTS or len(parts) < 2 or not path.name.endswith(".json"):
                raise SkillCopyError(f"{where}: a patch is {SKILL_PATCHES}/<agents|codex>/<skill path>.json")
            skill_path = "/".join(parts[1:])[:-len(".json")]
            if skill_path in sources and _codex_interface_file(SKILL_COPY_AGENTS[parts[0]], skill_path):
                raise SkillCopyError(f"{where}: Codex's agents/openai.yaml is kept by hand and never generated, "
                                     "so it takes no patch")
            if skill_path not in sources:
                raise SkillCopyError(f"{where}: no source {(source_root / skill_path).relative_to(root).as_posix()} "
                                     "for this patch: move or delete the patch with its skill")
            patches[(parts[0], skill_path)] = path
        for skill_path, source in sources.items():
            try:
                text = source.read_bytes().decode("utf-8")
            except UnicodeDecodeError as exc:
                raise SkillCopyError(f"{source.relative_to(root).as_posix()}: not UTF-8 ({exc})") from exc
            for agent, agent_dir in SKILL_COPY_AGENTS.items():
                if _codex_interface_file(agent_dir, skill_path):
                    continue
                patch = patches.get((agent, skill_path))
                copy = generate_copy(text, load_skill_patch(patch) if patch else None)
                outputs[overlay / "templates" / agent_dir / "skills" / skill_path] = copy.encode("utf-8")
        for agent_dir in SKILL_COPY_AGENTS.values():
            copies_root = overlay / "templates" / agent_dir / "skills"
            for path in _files_under(copies_root):
                hand_kept = _codex_interface_file(agent_dir, path.relative_to(copies_root).as_posix())
                if path not in outputs and not hand_kept:
                    stray.append(path)
    return outputs, stray


def skill_copy_report(check: bool = False, root: Path | None = None) -> dict:
    """`skill-copies`: `changed` lists the copies whose bytes differ from the generated ones (a missing copy among
    them), written unless `check`; `stray` lists copies with no Claude source, which are reported and never deleted."""
    root = Path(root or FORGE_ROOT).resolve()
    outputs, stray = _skill_copy_plan(root)
    changed = [path for path, data in outputs.items() if not path.is_file() or path.read_bytes() != data]
    if not check:
        for path in changed:
            atomic_write(path, outputs[path])
    return {"changed": sorted(path.relative_to(root).as_posix() for path in changed),
            "stray": sorted(path.relative_to(root).as_posix() for path in stray)}


def skill_copies(check: bool = False, root: Path | None = None) -> list[str]:
    """The paths `skill_copy_report` names, changed and stray together: empty when every copy is the generator's."""
    report = skill_copy_report(check=check, root=root)
    return sorted(report["changed"] + report["stray"])


# Every suite the repository holds: `check-all` runs them all, and CI runs them through it (.github/workflows/tests.yml).
# `path` is the folder or script a suite stands on, `timeout` its limit in seconds; a `unittest` suite must run a test.
SUITES: list[dict] = [
    _unittest_suite("tests", "tests", 3600),
    _unittest_suite("kit-automations", "kits/automations/templates/scripts/tests", 1800),
    _unittest_suite("kit-reviewer", "kits/reviewer/templates/scripts/tests", 1800),
    _unittest_suite("kit-unattended", "kits/unattended/templates/scripts/tests", 1800),
    _unittest_suite("kit-wordpress", "kits/wordpress/templates/scripts/tests", 1800),
    _unittest_suite("kit-wordpress-pressable", "kits/wordpress/hosts/pressable/templates/scripts/tests", 1800),
    _unittest_suite("sdk-scripts", "scripts/tests", 1800),
    {"name": "agent-tiers", "kind": "command", "path": "scripts/verify-agent-tiers.mjs", "timeout": 300,
     "argv": ["node", "scripts/verify-agent-tiers.mjs"]},
    # Global suites under global/ (five unittest suites verified offline on Windows and POSIX).
    _unittest_suite("global-claude-hooks", "global/claude/hooks", 300),
    _unittest_suite("global-codex-hooks", "global/codex/hooks", 300),
    _unittest_suite("global-tests", "global/tests", 300),
    _unittest_suite("global-claude-ticktick", "global/claude/skills/process-ticktick-task/scripts", 300),
    _unittest_suite("global-codex-ticktick", "global/codex/skills/process-ticktick-task/scripts", 300),
    _unittest_suite("plugin-claude-scripts", "plugins/claude/scripts", 300),
    {"name": "plugin-codex-scripts", "kind": "command", "path": "plugins/codex/scripts", "timeout": 30,
     "argv": ["node", "--test", "plugins/codex/scripts/check-approval-policy.test.mjs"]},
    # Offline plugin suites under plugins/ (explicit test files run without external npm dependencies).
    {"name": "plugin-claude-bunny-net", "kind": "command", "path": "plugins/claude/bunny-net/tests", "timeout": 300,
     "argv": ["node", "--test", "plugins/claude/bunny-net/tests/client.test.js"]},
    {"name": "plugin-claude-domains-co-za", "kind": "command", "path": "plugins/claude/domains-co-za/tests", "timeout": 300,
     "argv": ["node", "--test", "plugins/claude/domains-co-za/tests/client.test.js",
              "plugins/claude/domains-co-za/tests/totp.test.js"]},
    {"name": "plugin-codex-atera", "kind": "command", "path": "plugins/codex/atera/tests", "timeout": 300,
     "argv": ["node", "--test", "plugins/codex/atera/tests/client.test.js",
              "plugins/codex/atera/tests/credentials.test.js",
              "plugins/codex/atera/tests/linux-credentials.test.js"]},
    {"name": "plugin-codex-conclave", "kind": "command", "path": "plugins/codex/conclave/tests", "timeout": 300,
     "argv": ["node", "--test", "plugins/codex/conclave/tests/approval.test.mjs",
              "plugins/codex/conclave/tests/launch-wsl.test.mjs",
              "plugins/codex/conclave/tests/launcher.test.mjs",
              "plugins/codex/conclave/tests/run-hidden.test.mjs"]},
    {"name": "plugin-codex-domains-co-za", "kind": "command", "path": "plugins/codex/domains-co-za/tests", "timeout": 300,
     "argv": ["node", "--test", "plugins/codex/domains-co-za/tests/client.test.js",
              "plugins/codex/domains-co-za/tests/linux-credentials.test.js",
              "plugins/codex/domains-co-za/tests/totp.test.js"]},
    {"name": "plugin-codex-outlook-graph", "kind": "command", "path": "plugins/codex/outlook-graph/tests", "timeout": 300,
     "argv": ["node", "--test", "plugins/codex/outlook-graph/tests/client.test.js",
              "plugins/codex/outlook-graph/tests/store.test.js"]},
]
TEST_FILE_PATTERNS = ("test_*.py", "*_test.py", "*.test.mjs", "*.test.js", "test-*.sh")
# Plugin tests that require third-party npm packages unavailable in this zero-dependency repository.
# Listed file by file so a new offline test file under plugins/ is caught until added to SUITES.
EXCLUDED_TESTS: dict[str, str] = {
    "plugins/claude/bunny-net/tests/changes.test.js":
        "requires npm package '@modelcontextprotocol/sdk' (not installed in zero-dependency repo)",
    "plugins/claude/bunny-net/tests/protocol.test.js":
        "requires npm package '@modelcontextprotocol/sdk' (not installed in zero-dependency repo)",
    "plugins/claude/domains-co-za/tests/changes.test.js":
        "requires npm package '@modelcontextprotocol/sdk' (not installed in zero-dependency repo)",
    "plugins/claude/domains-co-za/tests/protocol.test.js":
        "requires npm package '@modelcontextprotocol/sdk' (not installed in zero-dependency repo)",
    "plugins/codex/atera/tests/protocol.test.js":
        "requires npm package '@modelcontextprotocol/sdk' (not installed in zero-dependency repo)",
    "plugins/codex/atera/tests/tools.test.js":
        "requires npm package '@modelcontextprotocol/sdk' (not installed in zero-dependency repo)",
    "plugins/codex/bunny-net/tests/safety.test.js":
        "requires npm package '@modelcontextprotocol/sdk' (not installed in zero-dependency repo)",
    "plugins/codex/domains-co-za/tests/changes.test.js":
        "requires npm package '@modelcontextprotocol/sdk' (not installed in zero-dependency repo)",
    "plugins/codex/domains-co-za/tests/protocol.test.js":
        "requires npm package '@modelcontextprotocol/sdk' (not installed in zero-dependency repo)",
    "plugins/codex/outlook-graph/tests/attachment-references.test.js":
        "requires npm package 'parse5' (not installed in zero-dependency repo)",
    "plugins/codex/outlook-graph/tests/auth.test.js":
        "requires npm package '@azure/msal-node' (not installed in zero-dependency repo)",
    "plugins/codex/outlook-graph/tests/changes.test.js":
        "requires npm package 'zod' (not installed in zero-dependency repo)",
    "plugins/codex/outlook-graph/tests/html-drafts.test.js":
        "requires npm package 'zod' (not installed in zero-dependency repo)",
    "plugins/codex/outlook-graph/tests/protocol.test.js":
        "requires npm package '@modelcontextprotocol/sdk' (not installed in zero-dependency repo)",
    "plugins/codex/pressable/tests/safety.test.js":
        "requires npm package 'ajv' (not installed in zero-dependency repo)",
    "plugins/codex/pressable/tests/wpcli.test.js":
        "requires npm package 'ajv' (not installed in zero-dependency repo)",
    "plugins/codex/website-router/tests/files.test.js":
        "requires npm package 'ssh2' (not installed in zero-dependency repo)",
    "plugins/codex/website-router/tests/policy.test.js":
        "requires npm package 'ajv' (not installed in zero-dependency repo)",
    "plugins/codex/website-router/tests/router.test.js":
        "requires npm package 'ajv' (not installed in zero-dependency repo)",
    "plugins/codex/website-router/tests/security.test.js":
        "requires npm package 'ipaddr.js' (not installed in zero-dependency repo)",
}
TAIL_LINES = 40         # what is kept of a suite's output, however much it prints
TAIL_BYTES = 64 * 1024
RAN_TESTS = re.compile(rb"^Ran (\d+) tests? in ", re.M)


class UnownedTestsError(Exception):
    """Raised before any suite starts when check-all sees unowned tests or invalid exclusions."""


def _normalize_repo_path(raw: str) -> str:
    return PurePosixPath(raw.replace("\\", "/")).as_posix()


def _repo_test_files(root: Path) -> list[str]:
    """List every tracked or unignored untracked repository test file matching TEST_FILE_PATTERNS."""
    try:
        proc = subprocess.run(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            cwd=root,
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        raise UnownedTestsError(f"check-all: could not list repository test files with git ls-files: {exc}") from exc
    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", errors="replace").strip()
        suffix = f": {detail}" if detail else ""
        raise UnownedTestsError(f"check-all: git ls-files failed (exit {proc.returncode}){suffix}")
    found: set[str] = set()
    for raw in proc.stdout.split(b"\x00"):
        if not raw:
            continue
        rel = _normalize_repo_path(raw.decode("utf-8", errors="replace"))
        name = PurePosixPath(rel).name
        if any(fnmatch.fnmatchcase(name, pattern) for pattern in TEST_FILE_PATTERNS) and (root / rel).is_file():
            found.add(rel)
    return sorted(found)


_UNITTEST_MODULE_NAME = re.compile(r"^[_a-z]\w*\.py$", re.IGNORECASE)


def _unittest_owns_file(root: Path, suite_path: PurePosixPath, rel: str) -> bool:
    """True when `python -m unittest discover -s <suite_path>` would import and run `rel`."""
    file_path = PurePosixPath(rel)
    if not fnmatch.fnmatchcase(file_path.name, "test_*.py") or not _UNITTEST_MODULE_NAME.match(file_path.name):
        return False
    try:
        inner = file_path.relative_to(suite_path)
    except ValueError:
        return False
    if not inner.parts:
        return False
    cur = suite_path
    for part in inner.parts[:-1]:
        cur = cur / part
        if not (root / cur / "__init__.py").is_file():
            return False
    return True


def _suite_owned_tests(root: Path, suites: list[dict], files: set[str]) -> set[str]:
    owned: set[str] = set()
    for suite in suites:
        if suite.get("kind") == "unittest":
            suite_path = PurePosixPath(_normalize_repo_path(suite["path"]))
            for rel in files:
                if _unittest_owns_file(root, suite_path, rel):
                    owned.add(rel)
            continue
        for arg in suite.get("argv", ()):
            if not isinstance(arg, str) or arg.startswith("-"):
                continue
            norm = _normalize_repo_path(arg)
            if norm in files:
                owned.add(norm)
    return owned


def unowned_tests(root: Path = FORGE_ROOT, suites: list[dict] = SUITES,
                  excluded: dict[str, str] = EXCLUDED_TESTS) -> list[str]:
    """Return repository test files owned by no suite in `suites` and omitted from `excluded`."""
    files = _repo_test_files(root)
    owned = _suite_owned_tests(root, suites, set(files))
    valid_excluded = {_normalize_repo_path(path) for path, reason in excluded.items()
                      if isinstance(reason, str) and reason.strip()}
    return [rel for rel in files if rel not in owned and rel not in valid_excluded]


def _inventory_problems(root: Path, suites: list[dict], excluded: dict[str, str]) -> list[str]:
    files = _repo_test_files(root)
    file_set = set(files)
    owned = _suite_owned_tests(root, suites, file_set)
    problems: list[str] = []
    valid_excluded: set[str] = set()
    for raw_path, reason in excluded.items():
        norm = _normalize_repo_path(raw_path)
        if not isinstance(reason, str) or not reason.strip():
            problems.append(f"{norm}: EXCLUDED_TESTS entry is missing a reason")
            continue
        if norm not in file_set:
            problems.append(f"{norm}: EXCLUDED_TESTS entry does not match any repository test file")
            continue
        if norm in owned:
            problems.append(f"{norm}: EXCLUDED_TESTS entry is already covered by SUITES")
            continue
        if norm in valid_excluded:
            problems.append(f"{norm}: duplicate EXCLUDED_TESTS entry")
            continue
        valid_excluded.add(norm)
    for rel in files:
        if rel not in owned and rel not in valid_excluded:
            problems.append(f"{rel}: unowned test file (add to SUITES or EXCLUDED_TESTS)")
    return problems


def _runs_here(suite: dict) -> bool:
    """Whether this host can run the suite: one marked `"os": "posix"` runs everywhere but Windows."""
    return suite.get("os") != "posix" or os.name != "nt"


def _wait(proc: subprocess.Popen, timeout: float) -> int:
    return proc.wait(timeout=timeout)


def _end_suite(proc: subprocess.Popen, job=None, tag: str | None = None) -> None:
    """End a suite's tree and collect the suite itself, so no process of it is left behind, running or not."""
    _kill_tree(proc, job, tag)
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:  # the kill was sent; a process the system will not end is not waited on
        pass


def _run_suite(suite: dict, env: dict, cwd: Path) -> dict:
    """Run one suite to its end: its result with exit, duration, test count and the bounded tail of its output."""
    import threading
    import time

    started = time.monotonic()
    result = {"name": suite["name"], "passed": False, "skipped": False, "exit": None, "tests": None, "reason": "",
              "tail": ""}

    def done() -> dict:
        result["seconds"] = round(time.monotonic() - started, 1)
        return result

    group = _own_group()
    tag = os.urandom(8).hex()
    suite_env = {**env, "CONCLAVE_CHECK_ALL_TAG": tag}
    job = None
    proc = None
    try:
        if os.name == "nt":
            job = _open_windows_job()
            group["creationflags"] |= CREATE_SUSPENDED
        proc = subprocess.Popen(suite["argv"], cwd=cwd, env=suite_env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, **group)
        if job is not None:
            _assign_and_resume_windows(job, proc)
    except (OSError, ValueError) as exc:
        if proc is not None:
            _end_suite(proc, job, tag)
        elif job is not None:
            _close_windows_job(job)
        result["reason"] = f"could not start: {getattr(exc, 'strerror', None) or exc}"
        return done()
    except BaseException:
        if proc is not None:
            _end_suite(proc, job, tag)
        elif job is not None:
            _close_windows_job(job)
        raise
    ended = False
    finished = False
    reader = None
    out = None

    def finish_reading() -> None:
        nonlocal finished
        if finished:
            return
        finished = True
        if reader is not None and reader.is_alive():
            reader.join(5)
        # A process that outlived the suite can hold the pipe open: the reader (a daemon thread) is then left to it and
        # the pipe is not closed here, because closing a pipe that is being read waits for that read on Windows.
        if out is not None and (reader is None or not reader.is_alive()):
            try:
                out.close()
            except OSError:
                pass

    try:
        kept = {"tail": b"", "carry": b"", "tests": None}
        out = proc.stdout
        assert out is not None

        def drain() -> None:
            # Read as it is printed and keep only the end: a suite's output is never held whole.
            try:
                while chunk := out.read1(65536):
                    found = RAN_TESTS.findall(kept["carry"] + chunk)
                    if found:
                        kept["tests"] = int(found[-1])
                    kept["carry"] = (kept["carry"] + chunk)[-256:]
                    kept["tail"] = (kept["tail"] + chunk)[-TAIL_BYTES:]
            except (OSError, ValueError):  # the pipe was closed under the reader after the tree was ended
                return

        reader = threading.Thread(target=drain, daemon=True)
        try:
            reader.start()
            result["exit"] = _wait(proc, suite["timeout"])
        except subprocess.TimeoutExpired:
            _end_suite(proc, job, tag)
            ended = True
            result["reason"] = f"timed out after {suite['timeout']:g} seconds"
    finally:
        if not ended:
            _end_suite(proc, job, tag)
        finish_reading()
    text = kept["tail"].decode("utf-8", "replace")
    result["tail"] = "\n".join(text.splitlines()[-TAIL_LINES:])
    result["tests"] = kept["tests"]
    if not result["reason"]:
        if suite["kind"] == "unittest" and (result["tests"] == 0 or (result["exit"] == 0 and result["tests"] is None)):
            result["reason"] = "no tests ran"
        elif result["exit"] != 0:
            result["reason"] = f"exit {result['exit']}"
        else:
            result["passed"] = True
    return done()


def check_all(full: bool = False, only=(), skip=(), suites: list[dict] | None = None, root: Path | None = None,
              on_result=None, excluded: dict[str, str] | None = None) -> list[dict]:
    """Run every suite (those named by `only`, less those named by `skip`), each to its end whatever the one before
    did, and return each one's result. Before any suite runs, validates that every test file in `root` is owned by
    the full suite table or explicitly listed with a reason in `excluded`, raising `UnownedTestsError` otherwise.
    A suite this host cannot run is returned as skipped, neither passed nor failed. An unknown name raises ValueError
    before any suite starts. `full` sets CONCLAVE_FULL_TESTS=1 for the suites; otherwise it is removed, whatever this
    process's own environment holds."""
    table = SUITES if suites is None else suites
    target_root = FORGE_ROOT if root is None else root
    excluded_map = EXCLUDED_TESTS if excluded is None else excluded
    names = [suite["name"] for suite in table]
    unknown = [name for name in (*only, *skip) if name not in names]
    if unknown:
        raise ValueError(f"unknown suite {', '.join(unknown)} (the suites are: {', '.join(names)})")
    problems = _inventory_problems(target_root, table, excluded_map)
    if problems:
        raise UnownedTestsError("check-all: repository test inventory check failed:\n"
                                + "\n".join(f"  {item}" for item in problems))
    env = dict(os.environ)
    env.pop("CONCLAVE_FULL_TESTS", None)
    if full:
        env["CONCLAVE_FULL_TESTS"] = "1"
    # A Python suite writes as it goes: a buffered stdout would land at exit, after the summary unittest sends to
    # stderr, and push the failure out of the kept tail.
    env["PYTHONUNBUFFERED"] = "1"
    results = []
    for suite in table:
        if (only and suite["name"] not in only) or suite["name"] in skip:
            continue
        if _runs_here(suite):
            results.append(_run_suite(suite, env, target_root))
        else:  # never counted as passed, and always shown
            results.append({"name": suite["name"], "passed": False, "skipped": True, "exit": None, "tests": None,
                            "reason": "runs on POSIX only; CI's Linux job runs it", "tail": "", "seconds": 0.0})
        if on_result:
            on_result(results[-1])
    return results


def _suite_line(result: dict) -> str:
    tests = "" if result["tests"] is None else f"  {result['tests']} tests"
    reason = "" if result["passed"] else f"  ({result['reason']})"
    word = "SKIP" if result["skipped"] else "PASS" if result["passed"] else "FAIL"
    return f"{word}  {result['name']}  {result['seconds']:.1f}s{tests}{reason}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Install the base kit plus only the kits named with --kit")
    p_init.add_argument("target", help="Target repository path")
    p_init.add_argument("--agent", choices=AGENT_CHOICES, default="all")
    p_init.add_argument("--kit", action="append", default=[], help="Additive overlay kit to apply (base, todo, reviewer, automations, unattended, laravel, wordpress)")
    p_init.add_argument("--wp-host", choices=WORDPRESS_HOSTS, default=None, help="WordPress kit only: the site's host (default: the pin's, else pressable)")
    p_init.add_argument("--no-scripts", action="store_true", help="Leave out the kits' scripts/ files")
    p_init.add_argument("--with-todo", action="store_true", help="Shorthand for --kit todo")
    p_init.add_argument("--force", action="store_true",
                        help="Replace AGENTS.md, GEMINI.md, CLAUDE.md and CODEX.md with the kit's, keeping each replaced one as <name>.replaced")

    p_kit = sub.add_parser("kit", help="Apply an additive overlay kit (base, todo, reviewer, automations, unattended, laravel, wordpress) to a target repo")
    p_kit.add_argument("target", help="Target repository path")
    p_kit.add_argument("kit_name", choices=list_kits(), help="Kit name to apply")
    p_kit.add_argument("--agent", choices=AGENT_CHOICES, default="all", help="Install kit files for all agents or one agent")
    p_kit.add_argument("--host", choices=WORDPRESS_HOSTS, default=None, help="WordPress kit only: the site's host (default: the pin's, else pressable)")
    p_kit.add_argument("--dry-run", action="store_true", help="Preview files that would be installed without writing")

    p_doc = sub.add_parser("doctor", help="Run read-only stack and agent overlay health checks on a target repo")
    p_doc.add_argument("target", help="Target repository path")
    p_doc.add_argument("kit_name", nargs="?", choices=list_kits(), default=None, help="Optional kit name (auto-detects if omitted)")
    p_doc.add_argument("--strict", action="store_true", help="Exit 3 if any check is missing or setup_required")

    p_diff = sub.add_parser("diff", help="Report each kit file's state in a project (missing, kit-newer, ...) without writing")
    p_diff.add_argument("target", help="Target repository path")
    p_diff.add_argument("kit_name", nargs="?", default=None, help="Only this kit (default: every kit the project has)")
    p_diff.add_argument("--patch", action="store_true", help="Add a unified diff for each changed text file")

    p_up = sub.add_parser("update", help="Write only the kit files a project lacks or never changed; list the rest")
    p_up.add_argument("target", help="Target repository path")
    p_up.add_argument("kit_name", nargs="?", default=None, help="Only this kit (default: every kit the project has)")
    p_up.add_argument("--only", action="append", default=[], metavar="PATH",
                      help="Only this file or folder, relative to the project (repeatable)")
    p_up.add_argument("--no-scripts", action="store_true", help="Leave out the kits' scripts/ files, as init --no-scripts does")
    p_up.add_argument("--dry-run", action="store_true", help="List what would be written without writing")
    p_up.add_argument("--kit-new", action="store_true",
                      help="Write the kit's version of each file both sides changed beside it as <name>.kit-new")

    p_rec = sub.add_parser("record", help="Adopt an install made before the record: record the files identical to the kit")
    p_rec.add_argument("target", help="Target repository path")
    p_rec.add_argument("kit_name", nargs="?", default=None, help="Only this kit (default: every kit the project has)")
    p_rec.add_argument("--dry-run", action="store_true", help="List what would be recorded without writing")
    p_rec.add_argument("--merged", action="append", default=[], metavar="PATH",
                       help="Record a hand merge from PATH.kit-new (relative to the project; repeatable), then remove the copy")

    p_drift = sub.add_parser("drift", help="Report which listed projects have kit files to update or merge (exit 3 if any)")
    p_drift.add_argument("--projects", default=None, help=f"The project list (default: the SDK's {PROJECTS})")

    sub.add_parser("kits", help="List available overlay kits")
    p_self = sub.add_parser("self-sync", help="Refresh the SDK's own installed copy of base, todo, reviewer and automations")
    p_self.add_argument("--dry-run", action="store_true", help="List the files that would change without writing")

    p_copies = sub.add_parser("skill-copies", help="Write each kit's Antigravity and Codex skill files from its "
                                                   "Claude files and skill-patches/")
    p_copies.add_argument("--check", action="store_true",
                          help="Write nothing; exit 1 when a copy differs from the generated one or has no source")
    p_all = sub.add_parser("check-all", help="Run every test suite the SDK holds; exit 1 when any fails")
    p_all.add_argument("--full", action="store_true", help="Set CONCLAVE_FULL_TESTS=1: the gated stamp and adoption tests run too")
    p_all.add_argument("--only", action="append", default=[], metavar="NAME", help="Only this suite (repeatable)")
    p_all.add_argument("--skip", action="append", default=[], metavar="NAME", help="Every suite but this one (repeatable)")

    p_check = sub.add_parser("check", help="Inspect a target repository's agent setup")
    p_check.add_argument("target", help="Target repository path")

    args = parser.parse_args(argv)
    try:
        return _run(args)
    except UnownedTestsError as exc:
        print(str(exc), flush=True)
        return 1
    except ValueError as exc:
        # forge's own refusals (bad target, no app root, a pinned host) end like argparse's: one line, exit 2.
        print(f"forge.py: error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        # A failed read or write (a full disk, a file held open): one line and exit 1, never reported as done.
        print(f"forge.py: error: {exc}", file=sys.stderr)
        return 1


def _run(args: argparse.Namespace) -> int:
    if args.command == "kits":
        print(json.dumps({"kits": list_kits()}, indent=2))
        return 0
    if args.command == "self-sync":
        print(json.dumps(self_sync(dry_run=args.dry_run), indent=2))
        return 0

    if args.command == "skill-copies":
        report = skill_copy_report(check=args.check)
        print(json.dumps({"check": args.check, **report}, indent=2))
        return 1 if args.check and (report["changed"] or report["stray"]) else 0

    if args.command == "check-all":
        results = check_all(full=args.full, only=args.only, skip=args.skip,
                            on_result=lambda result: print(_suite_line(result), flush=True))
        skipped = [result for result in results if result["skipped"]]
        failed = [result for result in results if not result["passed"] and not result["skipped"]]
        for result in failed:
            print(f"\n--- {result['name']}: {result['reason']}; the end of its output ---\n{result['tail']}", flush=True)
        ran = len(results) - len(skipped)
        print(f"\ncheck-all: {ran - len(failed)} of {ran} suites passed"
              + (f", {len(skipped)} not run on this host" if skipped else ""))
        return 1 if failed else 0

    if args.command == "drift":
        lines, drifted = drift_lines(drift_report(load_projects(Path(args.projects or FORGE_ROOT / PROJECTS))))
        print("\n".join(lines))
        # Exit 3 is the report: the automations runner emails a non-zero exit with the tail of this output.
        return 3 if drifted else 0

    target = Path(args.target)

    if args.command == "kit":
        res = apply_kit(target, args.kit_name, agent=args.agent, dry_run=args.dry_run, host=args.host)
        print(json.dumps(res, indent=2))
        return 0

    if args.command == "diff":
        print(json.dumps(diff_project(target, args.kit_name, patch=args.patch), indent=2))
        return 0

    if args.command == "update":
        print(json.dumps(update_project(target, args.kit_name, only=args.only, dry_run=args.dry_run,
                                        no_scripts=args.no_scripts, kit_new=args.kit_new), indent=2))
        return 0

    if args.command == "record":
        print(json.dumps(record_project(target, args.kit_name, dry_run=args.dry_run, merged=args.merged), indent=2))
        return 0

    if args.command == "doctor":
        if not target.is_dir():  # a mistyped path would otherwise read as a project with every check missing
            print(f"doctor: not a directory: {args.target}", file=sys.stderr)
            return 2
        res = doctor_repo(target, args.kit_name)
        print(json.dumps(res, indent=2))
        if args.strict and res["missing_or_setup_required"] > 0:
            return 3
        return 0

    if args.command == "init":
        res = provision(
            target,
            agent=args.agent,
            include_scripts=not args.no_scripts,
            with_todo=args.with_todo,
            kits=args.kit,
            wordpress_host=args.wp_host,
            overwrite_existing_docs=args.force,
        )
        print(json.dumps(res, indent=2))
        return 0

    if args.command == "check":
        res = check_repo(target)
        print(json.dumps(res, indent=2))
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
