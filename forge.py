#!/usr/bin/env python3
"""Conclave-SDK CLI: copy agent customizations and stack kits into a project, then audit them.

    python forge.py init <target> [--agent all|agy|gemini|claude|codex] [--kit <kit>] [--with-todo] [--force]
    python forge.py kit <target> <kit> [--agent all|agy|gemini|claude|codex] [--host pressable|wpcom] [--dry-run]
    python forge.py diff <target> [kit] [--patch]
    python forge.py update <target> [kit] [--only <path>]... [--no-scripts] [--kit-new] [--dry-run]
    python forge.py record <target> [kit] [--merged <path>]... [--dry-run]
    python forge.py drift [--projects <file>]
    python forge.py doctor <target> [base|todo|reviewer|automations|launchers|unattended|desktop-tests|lsp|toolchain-cpp|toolchain-web|laravel|wordpress] [--strict]
        (no kit named: the Laravel or WordPress kit when the project is one, else base, plus lsp when installed;
        a toolchain kit starts each pinned tool to read its version, so it is checked only when named)
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
import ast
import ctypes
import difflib
import fnmatch
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import textwrap
import tomllib
import types
import unicodedata

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
    """A symlink, or on Windows a junction (including on Python 3.11 without Path.is_junction): either leads a
    write somewhere other than where its path says."""
    if path.is_symlink():
        return True
    if hasattr(path, "is_junction"):
        return path.is_junction()
    mount_tag = getattr(stat, "IO_REPARSE_TAG_MOUNT_POINT", None)
    if mount_tag is not None:
        try:
            return getattr(path.lstat(), "st_reparse_tag", 0) == mount_tag
        except FileNotFoundError:
            return False
    return False


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
KIT_ORDER = ("base", "todo", "reviewer", "automations", "launchers", "unattended", "desktop-tests", "lsp",
             "toolchain-cpp", "toolchain-web", "laravel", "wordpress")
DESKTOP_TESTS_CONFIG = ".conclave/desktop-tests.json"
LAUNCHERS_PROFILE = ".conclave/launchers.json"  # the launchers kit's profile: the title, icon, agents and links
LAUNCHERS_RENDERER = "scripts/campaign-icon.py"  # the launchers kit's icon renderer, which the unattended kit uses
# A kit that installs another with it, by the same `apply_kit`, so the other's files are recorded under its own name.
# The Laravel kit's `lsp` has its own branch (the server table is filled once, after both). D07 T01 section 3.
BROUGHT_KITS = {"unattended": "launchers"}
# Files that moved from one kit to another, by path: (the kit that shipped it, the kit that ships it now). A record
# written before the move names the old kit and is read as naming the new one (`_move_entries`), so `diff` and
# `update` keep its digest. D07 T01 section 3.
KIT_MOVES = {
    LAUNCHERS_RENDERER: ("unattended", "launchers"),
    "scripts/tests/test_campaign_icon.py": ("unattended", "launchers"),
}
BASE_SKILLS = ("authoring-skills", "local-tool-safety")
AGENT_DIRS = (".agents", ".claude", ".codex")
# A kit's version of a file the project changed, written beside it by `update --kit-new` for a hand merge, and the
# files forge stages a write in. None is ever kit content.
KIT_NEW = ".kit-new"
FORGE_SUFFIXES = (KIT_NEW, ".forge-new", ".forge-replace")
# Folders a kit's own test runs leave in its templates (bytecode, the pytest cache): never kit content.
CACHE_DIRS = frozenset({"__pycache__", ".pytest_cache"})
# The kits the SDK installs in itself (AGENTS.md), and the files of theirs `self-sync` keeps current there: skills,
# rules, subagents, scripts, the automations runner and the local settings template. The SDK's own docs, plan and pins are its project files.
SELF_KITS = ("base", "todo", "reviewer", "automations")
SELF_PREFIXES = tuple(f"{d}/{kind}/" for d in AGENT_DIRS for kind in ("skills", "rules")) + (
    ".claude/agents/", "scripts/", "bin/", "docs/", ".agents/hooks.json",
    ".codex/hooks.json", ".conclave/local.example.toml", ".conclave/local_settings.py", ".conclave/.gitignore") + AUTOMATIONS_SCRIPTS


LSP_TABLE = ".conclave/lsp.json"  # the lsp kit's server table: the one list of a project's language servers
# Each toolchain kit's pin file: the build tools a project wants and the least version of each.
TOOLCHAIN_PINS = {"toolchain-cpp": ".conclave/toolchain-cpp.json", "toolchain-web": ".conclave/toolchain-web.json"}


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
    if (target_root / LAUNCHERS_PROFILE).is_file():
        found.append("launchers")
    if (target_root / UNATTENDED_MODULE).is_file() or (target_root / "scripts/unattended-run.py").is_file():
        found.append("unattended")
    if (target_root / DESKTOP_TESTS_CONFIG).is_file() or (target_root / "scripts/smoke-input.ps1").is_file():
        found.append("desktop-tests")
    if (target_root / LSP_TABLE).is_file():
        found.append("lsp")
    found.extend(kit for kit, pins in TOOLCHAIN_PINS.items() if (target_root / pins).is_file())
    # Not scripts/lsp-diagnostics.py: the LSP kit installs a file of that name too.
    if any_skill(("laravel-boost",)) or (target_root / "docs/laravel-agent-tooling.md").is_file():
        found.append("laravel")
    if (target_root / WORDPRESS_PIN).is_file() or any_skill(("wordpress-site-safety", "wordpress-connect")):
        found.append("wordpress")
    return found


def _rel_allowed_for_agent(rel: str, agent: str) -> bool:
    if CACHE_DIRS.intersection(rel.split("/")):
        # Bytecode or a pytest cache left by running a kit's own tests in the SDK checkout is not kit content.
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
        # In the order of the paths as text, which is the same on every system (a Path sorts by its own rules).
        for src in sorted(root.rglob("*"), key=lambda path: path.relative_to(root).as_posix()):
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
        # The diagnostics client is the lsp kit's, which `apply_kit` installs with this kit.
        rel_items = [
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
        if kit_name == "toolchain-web" and target_root.is_dir():
            app_root = _find_web_app_root(target_root)
            pins = TOOLCHAIN_PINS[kit_name]
            if app_root != ".":
                # What the kit holds for a project whose app is not at its root is the seed with that folder as
                # `root`. Standing in the plan, it is what the install writes and records, and what `diff`,
                # `update` and `record` compare the project's file with.
                plan = [(RootedPin(src, app_root) if rel == pins else src, dst, rel, generated)
                        for src, dst, rel, generated in plan]
    if kit_name in ("automations", "wordpress"):
        for shared_rel in (".conclave/local_settings.py", ".conclave/.gitignore"):
            if not any(rel == shared_rel for _src, _dst, rel, _gen in plan):
                shared_src = FORGE_ROOT / "kits" / "base" / "templates" / shared_rel
                plan.append((shared_src, target_root / shared_rel, shared_rel, False))
    return plan, extra


class RootedPin:
    """The toolchain-web seed with an app's folder as its `root`. It stands where the template's path stands in a
    kit's plan and reads as the bytes the kit installs for that project; `seed` is the template itself."""

    def __init__(self, seed: Path, app_root: str) -> None:
        self.seed = seed
        self.app_root = app_root

    def read_bytes(self) -> bytes:
        data = json.loads(self.seed.read_text(encoding="utf-8"))
        rooted = {"schema_version": data["schema_version"], "root": self.app_root,
                  **{key: value for key, value in data.items() if key != "schema_version"}}
        return (json.dumps(rooted, indent=2) + "\n").encode("utf-8")


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
    return _move_entries(_check_record(data))


def _move_entries(record: dict) -> dict:
    """The record with each file of KIT_MOVES that it names under the kit that used to ship it named under the kit
    that ships it now, its digest kept. The new kit gains an entry with the old kit's agents and commit when the
    record has none. Every reader sees the move; a run that writes the record keeps it."""
    for rel, (old, new) in KIT_MOVES.items():
        entry = record["files"].get(rel)
        if entry is None or entry["kit"] != old:
            continue
        if new not in record["kits"]:
            was = record["kits"][old]
            record["kits"][new] = {"sdk_commit": was["sdk_commit"], "agents": list(was["agents"]), "host": None}
        entry["kit"] = new
    return record


def _record_on_disk(target_root: Path) -> dict | None:
    """The record as the file holds it, before `_move_entries`: what `update` compares to decide whether to write."""
    path = Path(target_root) / RECORD
    return json.loads(path.read_bytes().decode("utf-8")) if path.is_file() else None


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
    fill_table: bool = True,
) -> dict:
    """Apply an additive overlay kit ('base', 'todo', 'reviewer', 'automations', 'launchers', 'unattended',
    'lsp', 'toolchain-cpp', 'toolchain-web', 'laravel', 'wordpress') for all or one agent without overwriting
    existing files.

    The Laravel kit brings the lsp kit with it (the diagnostics client and the server table are that kit's), by
    this same function, so its files are recorded under `lsp`; the result names them under `lsp`. The unattended
    kit brings the launchers kit (its shortcuts draw their icons with that kit's renderer) the same way, named under
    `launchers` (BROUGHT_KITS).

    A file that already exists is the project's and is never replaced: the kit is a template copied once, and the
    project adapts its copy from then on. `include(rel)` can leave paths out entirely.

    `host` picks the WordPress kit's host overlay (kits/wordpress/hosts/<host>/templates); other kits ignore it. An
    existing site pin decides the host, so re-running the kit can never add another host's files; without a pin the
    default is `pressable`. The file list is `kit_plan`'s.
    """
    agent = normalize_agent(agent)
    target_root = Path(target_root)
    if not target_root.exists() or not target_root.is_dir() or _is_link(target_root):
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

    # Preflight all planned destinations for symlink-parent traversal before writing any file, the brought kit's too
    brought_plan = []
    if kit_name in BROUGHT_KITS:
        brought_plan = [(src, dst, rel) for src, dst, rel, generated in
                        kit_plan(target_root, BROUGHT_KITS[kit_name], agent=agent)[0]
                        if not generated and (include is None or include(rel))]
    for _src, dst, rel in plan + brought_plan:
        if dst.exists() or dst.is_symlink():
            continue
        if _has_unsafe_parent(target_root, rel):
            raise ValueError(f"Refusing destination with unsafe parent: {rel}")
    if kit_name in ("base", "automations", "wordpress"):
        _preflight_settings_gitignores(target_root)

    # The record is read, and its folder checked, before the first copy: a refusal here leaves nothing written.
    record = load_record(target_root) or {"schema_version": 1, "kits": {}, "files": {}}
    if not dry_run:
        _recover(target_root, record)
    copies: list[tuple[str, Path, bytes]] = []
    repaired: list[str] = []
    for src, dst, rel in plan:
        if dst.exists() or dst.is_symlink():
            # One existing file is not yet the project's: a toolchain-web pin that is still the kit's seed byte for
            # byte while the app is not at the root, which an install stopped between the seed's copy and its root
            # left behind (before the two became one write). It is given its root, recorded, and reported as such.
            if isinstance(src, RootedPin) and dst.is_file() and not dst.is_symlink() \
                    and dst.read_bytes() == src.seed.read_bytes():
                repaired.append(rel)
                if not dry_run:
                    copies.append((rel, dst, src.read_bytes()))
            else:
                preserved.append(rel)
            continue
        installed.append(rel)
        if not dry_run:
            copies.append((rel, dst, src.read_bytes()))
    # Only files this run writes are recorded, with the digest of the bytes written; a preserved file stays the
    # project's.
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
    if kit_name in ("base", "automations", "wordpress"):
        result["private_gitignore"] = _ensure_private_gitignore(target_root, dry_run=dry_run)
        local_ig = _ensure_local_toml_gitignore(target_root, dry_run=dry_run)
        if local_ig != "already_present":
            result["local_gitignore"] = local_ig
    if kit_name == "todo" and ".codex/hooks.json" in installed and not dry_run:
        result["codex_hook"] = _approve_codex_hook(target_root)
    if kit_name == "todo" and not dry_run:
        result["pre_commit_hook"] = _enable_pre_commit_hook(target_root)
    if kit_name == "toolchain-web":
        result["app_root"] = _find_web_app_root(target_root)
        if repaired:
            result["repaired"] = repaired
    if kit_name == "laravel":
        # The table is filled once, below, after both kits' files are in place.
        with_lsp = apply_kit(target_root, "lsp", agent=agent, dry_run=dry_run, include=include, fill_table=False)
        result["lsp"] = {"installed": with_lsp["installed"], "preserved": with_lsp["preserved"]}
    if kit_name in BROUGHT_KITS:
        brought = BROUGHT_KITS[kit_name]
        with_brought = apply_kit(target_root, brought, agent=agent, dry_run=dry_run, include=include)
        result[brought] = {"installed": with_brought["installed"], "preserved": with_brought["preserved"]}
        if with_brought.get("merge_needed"):
            result[brought]["merge_needed"] = list(with_brought["merge_needed"])
            for item in with_brought["merge_needed"]:
                if item not in merge_needed:
                    merge_needed.append(item)
        if "launcher_links" in with_brought:
            result["launcher_links"] = with_brought["launcher_links"]
    if kit_name in ("lsp", "toolchain-web", "toolchain-cpp", "laravel") and fill_table:
        servers = _fill_lsp_table(target_root, dry_run, installing=kit_name)
        if servers is not None:
            result["lsp_servers"] = servers
            if "refused" in servers or "failed" in servers:
                merge_needed.append(LSP_TABLE)
            if "plugin_failed" in servers:
                merge_needed.append(f"{_lsp_plugin_module().FOLDER}/{_lsp_plugin_module().SERVERS}")
    if kit_name in ("wordpress", "launchers"):
        links = _merge_wordpress_launcher_link(target_root, dry_run, installing=kit_name, installed=installed)
        if links is not None:
            result["launcher_links"] = links
            if any(key in links for key in ("conflict", "refused", "failed")):
                merge_needed.append(LAUNCHERS_PROFILE)
    return result


WEB_MANIFESTS = ("composer.json", "package.json")


def _find_web_app_root(target_root: Path) -> str:
    """The folder of a PHP or Node project that holds its manifest (composer.json or package.json), relative to
    the project: the root, then `platform/`, then the first other first-level folder in name order. `.` when none
    does."""
    def holds(folder: Path) -> bool:
        return any((folder / manifest).is_file() for manifest in WEB_MANIFESTS)

    if holds(target_root):
        return "."
    if holds(target_root / "platform"):
        return "platform"
    for child in sorted(path for path in target_root.iterdir() if path.is_dir() and not path.is_symlink()):
        if not child.name.startswith(".") and child.name not in ("vendor", "node_modules") and holds(child):
            return child.name
    return "."


def _fill_lsp_table(target_root: Path, dry_run: bool, installing: str | None = None) -> dict | None:
    """Add a stack's language servers to the project's LSP table for the stack kits it has: with the Laravel kit,
    the `laravel` preset rooted at the folder that holds artisan; with toolchain-cpp, the `cpp` preset (clangd)
    rooted at its pin file's `root`; with toolchain-web, the `php` preset for an app
    with composer.json and the `web` preset for one with package.json. It runs when any of those kits or the lsp
    kit is installed (`installing`), so their order does not matter.

    A server the table lacks is added. One it has is never changed, with one exception: an entry that is still, key
    for key, what another preset writes for that name (the `web` preset's tailwindcss, which has no Blade) is the
    kits' own, so the Laravel preset's entry replaces it; an entry the project changed is kept and, when it is not
    the Laravel preset's, listed under `differs`; a `clangd` entry that is not the `cpp` preset's is listed there
    too. Returns None when the project has no stack kit and none is
    being installed, else what happened: {"added", "kept"} (with "replaced" and "differs" for a Laravel project,
    "differs" for a C or C++ one),
    {"not_installed": the command that installs and fills the table}, {"refused": why the table does not load} or
    {"failed": why it could not be written, "retry": the command}."""
    pins = target_root / TOOLCHAIN_PINS["toolchain-web"]
    has_web = pins.is_file() or installing == "toolchain-web"
    laravel_app = None
    if installing == "laravel" or "laravel" in installed_kits(target_root):
        laravel_app = _find_laravel_app_root(target_root)
    cpp_pins = target_root / TOOLCHAIN_PINS["toolchain-cpp"]
    has_cpp = cpp_pins.is_file() or installing == "toolchain-cpp"
    if not has_web and laravel_app is None and not has_cpp:
        return None
    retry = f"python forge.py kit {target_root.as_posix()} lsp"
    table_there = (target_root / LSP_TABLE).is_file()
    # A dry run of the Laravel install has not written the table the lsp kit brings with it: it is read as empty.
    if not table_there and not (dry_run and installing == "laravel"):
        return {"not_installed": retry}
    table = _lsp_table_module()
    module = _toolchain_module("toolchain-web")
    cpp_module = _toolchain_module("toolchain-cpp")
    try:
        servers = table.load_servers(target_root) if table_there else []
        web_root = None
        if has_web:
            web_root = module.load_pin_file(pins)["root"] if pins.is_file() else _find_web_app_root(target_root)
        cpp_root = None
        if has_cpp:
            # A dry run of that install has written no pin file yet: the seed's root, the project.
            cpp_root = cpp_module.load_pin_file(cpp_pins)["root"] if cpp_pins.is_file() else "."
    except (table.TableError, module.PinError, cpp_module.PinError) as exc:
        return {"refused": str(exc)}
    presets = table.load_presets(FORGE_ROOT / "kits/lsp/templates/scripts/lib/lsp_presets.json")
    # The Laravel preset first: its entries are the fuller ones, and the web presets then find them in place.
    wanted: list[tuple[str, str]] = []
    if laravel_app is not None:
        wanted.append(("laravel", laravel_app.relative_to(target_root).as_posix() or "."))
    if cpp_root is not None:
        wanted.append(("cpp", cpp_root))
    if web_root is not None:
        wanted += [(preset, web_root) for preset, manifest in (("php", "composer.json"), ("web", "package.json"))
                   if (target_root / web_root / manifest).is_file()]

    def a_presets_own(existing: dict, app_root: str) -> bool:
        """Whether a table entry is still exactly what a preset other than `laravel` writes for its name in the
        Laravel app's folder. One rooted elsewhere, or with any key changed, is the project's choice."""
        for other in presets["presets"]:
            if other == "laravel":
                continue
            try:
                candidates = table.resolve_preset(target_root, other, app_root, presets)
            except table.TableError:
                continue
            if any(table.stored(entry) == table.stored(existing) for entry in candidates
                   if entry["name"] == existing["name"]):
                return True
        return False

    by_name = {server["name"]: index for index, server in enumerate(servers)}
    added, replaced, kept, differs = [], [], [], []
    for preset, app_root in wanted:
        for entry in table.resolve_preset(target_root, preset, app_root, presets):
            name = entry["name"]
            if name not in by_name:
                by_name[name] = len(servers)
                servers.append(entry)
                added.append(name)
                continue
            existing = servers[by_name[name]]
            if preset != "laravel" or table.stored(existing) == table.stored(entry):
                if name not in added and name not in replaced:
                    kept.append(name)
                    # The project's own clangd entry is kept, and said to differ from the kit's.
                    if preset == "cpp" and table.stored(existing) != table.stored(entry):
                        differs.append(name)
            elif a_presets_own(existing, app_root):
                servers[by_name[name]] = entry
                replaced.append(name)
            else:
                kept.append(name)
                differs.append(name)
    if (added or replaced) and not dry_run:
        try:
            table.write_servers(target_root, servers)
        except table.TableWriteError as exc:
            again = installing if installing in ("laravel", "toolchain-web", "toolchain-cpp") else \
                ("toolchain-web" if has_web else "laravel" if laravel_app is not None else "toolchain-cpp")
            return {"failed": str(exc), "retry": f"python forge.py kit {target_root.as_posix()} {again}"}
    result = {"added": added, "kept": list(dict.fromkeys(kept))}
    if laravel_app is not None:
        result.update(replaced=replaced, differs=differs)
    elif has_cpp:
        result.update(differs=differs)
    if (added or replaced) and not dry_run:
        # A Claude Code plugin the project has generated follows the table; a project without one gets none.
        plugin = _lsp_plugin_module()
        try:
            plugin.refresh(target_root, table.load_servers(target_root))
        except (plugin.PluginWriteError, table.TableError) as exc:
            result.update(plugin_failed=str(exc), plugin_retry=plugin.COMMAND)
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
    `pre_commit` is the hook git would run there, None when the setting names no folder) and `free` (nothing owns
    the repository's hooks)."""
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
    if configured[0] == 0 and not configured[1]:
        return {"state": "owned", "owner": "core.hooksPath is set to an empty value", "pre_commit": None}
    if configured[0] == 0:
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


def _names_kit_hook(hook: Path) -> bool:
    """Whether a command line of the hook file names the kit's pre-commit hook. A comment that mentions it does not."""
    try:
        lines = hook.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return False
    return any(PRE_COMMIT_HOOK in line and not line.lstrip().startswith("#") for line in lines)


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
    if hook is None:
        return ("setup_required", f"{setup['owner']}: someone chose that, so the install left it; replace it on "
                                  f"purpose with git config core.hooksPath {HOOKS_PATH}")
    if _names_kit_hook(hook):
        if os.name != "nt" and not os.access(hook, os.X_OK):
            return "setup_required", f"chmod +x {hook.as_posix()}: git runs only an executable hook"
        # Read, not run: the doctor changes nothing and starts no hook, so this is what the file says.
        return problem or ("ok", f"{hook.as_posix()} names {PRE_COMMIT_HOOK} on a command line (read, not run)")
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
    # A kit another brings is there wherever that one is, so an install from before it was brought still has its files
    # (the renderer an unattended install shipped before D07 T01 section 3) reported by the kit that ships them now.
    present |= {BROUGHT_KITS[name] for name in present if name in BROUGHT_KITS}
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
# The diagnostics client and the Laravel hook that calls it changed together (D04 T01 §4): the servers' names
# moved into the table. The kit's hook serves either client; a hook from before does not, so the client is not
# replaced under a hook the project changed that still passes the old names.
LSP_CLIENT = "scripts/lsp-diagnostics.py"
LARAVEL_HOOK = "scripts/hooks/laravel-lsp-pre-push.sh"
# Every form a shell passes a name in: `--server laravel`, `--server=laravel`, `--server "laravel"`.
_SERVER_ARGUMENT = r"--server(?:\s+|=)[\"']?(?:%s)[\"']?(?=[\s)]|$)"
_SHELL_COMMENT = re.compile(r"(?:^|\s)#.*$")   # a whole-line comment, or one after a command
OLD_SERVER_NAMES = re.compile(_SERVER_ARGUMENT % "laravel|tailwind|php", re.MULTILINE)
TABLE_SERVER_NAMES = re.compile(_SERVER_ARGUMENT % "laravel-lsp|tailwindcss|intelephense", re.MULTILINE)
UPDATE_HINT_HELD = (f"Held: {LARAVEL_HOOK} still passes the old client's server names and is the project's own "
                    "version, so the client it calls is not replaced under it. Merge the hook first "
                    "(`forge.py update <project> --kit-new` writes the kit's beside it), then update again.")


def _hook_holds_client(target: Path) -> bool:
    """Whether the project's Laravel hook, as it is on disk now, passes only the old client's server names. A
    hook that also passes the table's names (the kit's own, which serves either client, or a project's merge of
    it) holds nothing. `update` asks when it reaches the client, after the Laravel kit's files are written, so
    the answer is what the hook is, never what a later step was going to make it."""
    hook = target / LARAVEL_HOOK
    if _unsafe_destination(target, LARAVEL_HOOK) or not hook.is_file():
        return False
    try:
        text = hook.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    # The hook's commands only: a comment that mentions a name (a note to migrate) passes nothing to the client.
    code = "\n".join(_SHELL_COMMENT.sub("", line) for line in text.splitlines())
    return bool(OLD_SERVER_NAMES.search(code)) and not TABLE_SERVER_NAMES.search(code)


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


# The unattended kit's Windows links (D02 T02 §12): unattended-shortcut.ps1 records what it wrote, and an update that
# writes the script or the runner whose commands the links run writes the links again from that record.
SHORTCUT_RECORD = "build/unattended-shortcuts.json"
SHORTCUT_SOURCES = ("scripts/unattended-shortcut.ps1", "scripts/unattended-run.py")
SHORTCUT_REFRESH = "pwsh scripts/unattended-shortcut.ps1 -Refresh"
REFRESH_SECONDS = 300  # writing every link and badge again; the limit only catches a hang


def _windows() -> bool:
    """Whether this is Windows, where the unattended kit's links are (a function, so a test can stand in for it)."""
    return os.name == "nt"


READ_SECONDS = 60  # the runner reading the record; the limit only catches a hang
SHORTCUT_READER = FORGE_ROOT / "kits/unattended/templates/scripts/unattended-run.py"  # the SDK's, never the project's


def _shortcut_folders(target: Path) -> tuple[list[str] | None, str, str]:
    """(folders, state, why) of the project's shortcut record, read by the unattended kit's runner as this SDK holds
    it (`shortcut-record`): the reader the kit installs for the shortcut script and `status`, so forge holds no copy
    that can disagree with them (D02 T02 §12, reconciliations 1 and 7 to 15), and the SDK's own code, so an update
    never runs the project's (a runner the project changed is never executed; reconciliation 16). `state` is `ok`
    (no record is no folders), `damaged` (not a record: move it aside), `busy` (cannot be opened now) or `reader` (the
    reader gave no answer)."""
    if not (target / SHORTCUT_RECORD).exists():
        return [], "ok", ""
    runner = SHORTCUT_READER
    if not runner.is_file():
        return None, "reader", f"this SDK has no {runner.name} to read it ({runner})"
    try:
        # The reader starts no process of its own, so its timeout leaves nothing behind.
        done = subprocess.run([sys.executable, "-B", str(runner), "shortcut-record", str(target / SHORTCUT_RECORD)],
                              capture_output=True, text=True, timeout=READ_SECONDS,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, "reader", f"its reader did not answer ({exc})"
    said = (done.stdout or done.stderr).strip()
    if done.returncode == 3 and said:
        return None, "damaged", said
    if done.returncode == 4 and said:
        return None, "busy", said
    if done.returncode != 0:
        return None, "reader", f"its reader ended with exit {done.returncode}" + (f": {said[-300:]}" if said else "")
    try:
        sets = json.loads(said)["sets"]
        return [entry["args"]["ShortcutDir"] for entry in sets], "ok", ""
    except (ValueError, KeyError, TypeError):
        return None, "reader", "its reader gave no answer forge can read"


def _refresh_shortcuts(target: Path) -> dict:
    """Write the project's unattended links again, each recorded folder's with the arguments it was written with:
    {refreshed, detail}. With no record, the script itself names links written before it kept one, with the command
    that writes them again. Only on Windows, where the links are; elsewhere the detail names the command to run
    there."""
    folders, state, why = _shortcut_folders(target)
    # Each state's advice is the shortcut script's for the same file: a damaged record is moved aside, a held one is
    # tried again, and a record the reader could not answer for is kept for a restored reader.
    if state == "damaged":
        return {"refreshed": False, "detail": f"{SHORTCUT_RECORD} cannot be read ({why}): move it aside, then run "
                "pwsh scripts/unattended-shortcut.ps1 -Distro <distro> -Icon <the project's icon> -ShortcutDir "
                "'<folder>' on Windows, once for each folder the links are in"}
    if state == "busy":
        return {"refreshed": False, "detail": f"{SHORTCUT_RECORD} cannot be read ({why}): it may be sound; run "
                f"{SHORTCUT_REFRESH} on Windows once nothing holds it"}
    if state == "reader":
        return {"refreshed": False, "detail": f"{SHORTCUT_RECORD} was not read ({why}); it is kept as it is: run "
                f"{SHORTCUT_REFRESH} on Windows, which reads it with the project's own runner"}
    if not _windows():
        each = "; ".join(SHORTCUT_REFRESH + " -ShortcutDir " + "'" + folder.replace("'", "''") + "'"
                         for folder in folders)
        return {"refreshed": False, "detail": f"the links are on Windows: run {each} there" if folders else
                f"the links are on Windows: run {SHORTCUT_REFRESH} there, with -ShortcutDir '<folder>' for links "
                "written outside the desktop"}
    pwsh = shutil.which("pwsh")
    if not pwsh:
        return {"refreshed": False,
                "detail": f"PowerShell 7 (pwsh) is not on PATH: install it, then run {SHORTCUT_REFRESH}"}
    refreshed, said = True, []
    if not folders:  # no record: the desktop's links; links written elsewhere need their folder named
        said.append(f"links written outside the desktop: run {SHORTCUT_REFRESH} -ShortcutDir '<folder>'")
    for folder in folders or [None]:
        argv = [pwsh, "-NoProfile", "-NonInteractive", "-File", str(target / "scripts/unattended-shortcut.ps1"),
                "-Refresh", *(["-ShortcutDir", folder] if folder else [])]
        code, out, problem = _probe(argv, timeout=REFRESH_SECONDS)
        lines = "; ".join(out.strip().splitlines()[-3:])
        if code == 0:
            said.append(lines)
            continue
        refreshed = False
        quoted = "'" + folder.replace("'", "''") + "'" if folder else ""
        again = SHORTCUT_REFRESH + (f" -ShortcutDir {quoted}" if folder else "")
        said.append(f"{problem or f'exit {code}'}: {lines}; run {again} again")
    return {"refreshed": refreshed, "detail": " | ".join(said)}


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
    if any(k in first["kits"] for k in ("base", "automations", "wordpress")):
        _preflight_settings_gitignores(target)
    if paths:
        consumers = {".conclave/automations/alert.py", "scripts/lib/wp_site.py"}
        updating_consumer = any(
            item["path"] in consumers and chosen(item["path"]) and item["state"] in ("missing", "kit-newer", "project-removed")
            for item in known
        )
        reader_rel = ".conclave/local_settings.py"
        if updating_consumer and not (target / reader_rel).is_file() and not chosen(reader_rel):
            raise ValueError(
                f"--only selection updates a settings consumer without {reader_rel}; include {reader_rel}"
            )

    if not dry_run:
        _recover(target, load_record(target) or {"schema_version": 1, "kits": {}, "files": {}})
    report, sources = _diff_kits(target, kit_name, patch=True)
    record = load_record(target) or {"schema_version": 1, "kits": {}, "files": {}}
    # A record from before a file moved kits is read as naming the new one (`_move_entries`); it is written so here,
    # even when no file is, so the next reader of the file itself (another tool, a person) sees the move too.
    if not dry_run and (target / RECORD).is_file() and _record_on_disk(target) != record:
        write_record(target, record)
    written: list[str] = []
    left: list[dict] = []
    siblings: list[str] = []
    seen_shared: set[str] = set()
    shared_base = {".conclave/local_settings.py", ".conclave/.gitignore"}
    # The Laravel kit first: its hook serves either client, so it is in place before the lsp kit's client replaces
    # an old one. An update stopped between the two leaves the new hook with the old client, which work together;
    # the other order would leave the old hook calling a client that refuses its names.
    hook_replaced = chosen(LARAVEL_HOOK) and any(
        item["path"] == LARAVEL_HOOK and item["state"] == "kit-newer"
        for kit in report["kits"].values() for item in kit["files"])
    for name, kit in sorted(report["kits"].items(), key=lambda item: item[0] != "laravel"):
        plan = sources[name]["plan"]
        copies: list[tuple[str, Path, bytes]] = []
        expect: dict[str, str | None] = {}
        for item in kit["files"]:
            rel, state = item["path"], item["state"]
            if state == "identical" or not chosen(rel) or rel in seen_shared:
                continue
            if rel in shared_base:
                seen_shared.add(rel)
            if plan.get(rel, False) is None:  # a generated entry has no source
                left.append({"path": rel, "state": state, "hint": UPDATE_HINT_GENERATED})
                continue
            # Asked of the hook on disk. Only a dry run, which has written nothing, goes by the plan.
            if rel == LSP_CLIENT and state == "kit-newer" and _hook_holds_client(target) \
                    and not (dry_run and hook_replaced):
                left.append({"path": rel, "state": state, "hint": UPDATE_HINT_HELD})
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
    if any(k in report["kits"] for k in ("base", "automations", "wordpress")):
        result["private_gitignore"] = _ensure_private_gitignore(target, dry_run=dry_run)
        local_ig = _ensure_local_toml_gitignore(target, dry_run=dry_run)
        if local_ig != "already_present":
            result["local_gitignore"] = local_ig
    # The links are written again when the update wrote what they run: for a project with a record, and for one whose
    # shortcut script the update replaced, which may have links from before the record (the script then names them,
    # with the command that writes them and the record again). Off Windows the result names the command to run there.
    replaced = {item["path"] for kit in report["kits"].values() for item in kit["files"]
                if item["state"] == "kit-newer"}
    if not dry_run and any(rel in written for rel in SHORTCUT_SOURCES) and (
            (target / SHORTCUT_RECORD).is_file() or SHORTCUT_SOURCES[0] in replaced):
        result["shortcuts"] = _refresh_shortcuts(target)
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


LOCAL = ".conclave/local.toml"  # per-machine settings override, ignored by git
OVERLAY = ".private/local.toml"  # owner settings overlay, ignored by git
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


def _has_enclosing_git(target_root: Path) -> bool:
    """True when `target_root` or any parent holds a `.git` folder or gitdir file."""
    resolved = Path(target_root).resolve()
    return any((parent / ".git").exists() for parent in (resolved, *resolved.parents))


def _clean_git_env() -> dict[str, str]:
    """Subprocess environment for inspecting a target checkout's own Git state: strips inherited repo-override
    variables (`GIT_DIR`, `GIT_WORK_TREE`, `GIT_INDEX_FILE`, `GIT_COMMON_DIR`, `GIT_OBJECT_DIRECTORY`,
    `GIT_ALTERNATE_OBJECT_DIRECTORIES`) and forces C locale so every check uses the target's own repository and
    ordinary index with English diagnostics."""
    strip = {
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_INDEX_FILE",
        "GIT_COMMON_DIR",
        "GIT_OBJECT_DIRECTORY",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    }
    env = {k: v for k, v in os.environ.items() if k not in strip}
    env["LC_ALL"] = "C"
    env["LANG"] = "C"
    return env


def _git_worktree_prefix(target_root: Path) -> str | None:
    """Return the POSIX prefix of `target_root` inside its enclosing Git worktree (`""` at the repo root, `"sub/"`
    in a subdirectory), or `None` when `target_root` is not inside any Git worktree. Raises `ValueError` when
    `git` is missing inside an existing checkout or on fatal Git errors such as dubious ownership."""
    if not shutil.which("git"):
        if _has_enclosing_git(target_root):
            raise ValueError(f"git is not on PATH; cannot verify ignore rules or tracked status in {target_root}")
        return None
    proc = subprocess.run(
        ["git", "rev-parse", "--show-prefix"],
        cwd=str(target_root),
        env=_clean_git_env(),
        capture_output=True,
        timeout=15,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or b"").decode("utf-8", errors="replace").strip()
        if "not a git repository" in detail.lower() and not _has_enclosing_git(target_root):
            return None
        raise ValueError(f"git rev-parse failed in {target_root} (exit {proc.returncode}): {detail}")
    return (proc.stdout or b"").decode("utf-8", errors="surrogateescape").rstrip("\r\n").replace("\\", "/")


def _check_untracked_in_git(target_root: Path, rel_paths: tuple[str, ...]) -> str | None:
    """Return the enclosing worktree prefix (or None outside Git), raising `ValueError` if any of `rel_paths` is
    already tracked in Git's index."""
    prefix = _git_worktree_prefix(target_root)
    if prefix is None:
        return None
    git_env = _clean_git_env()
    for rel_path in rel_paths:
        tracked = subprocess.run(
            ["git", "ls-files", "--", rel_path],
            cwd=str(target_root),
            env=git_env,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if tracked.returncode != 0:
            detail = (tracked.stderr or tracked.stdout or "").strip()
            raise ValueError(f"git ls-files failed in {target_root} (exit {tracked.returncode}): {detail}")
        if (tracked.stdout or "").strip():
            raise ValueError(f"{rel_path} is already tracked in git in {target_root}; untrack it with git rm --cached")
    return prefix


PRIVATE_GITIGNORE_RULES = (".private/", "/.private/", ".private", "/.private")
PRIVATE_GITIGNORE_RULES_BYTES = tuple(rule.encode("ascii") for rule in PRIVATE_GITIGNORE_RULES)
LOCAL_TOML_GITIGNORE_RULES_BYTES = (b"local.toml", b"/local.toml")


def _preflight_settings_gitignores(target_root: Path) -> None:
    """Refuse symlinked or non-file `.gitignore` / `.conclave/.gitignore`, hard-linked ignore files that require
    an append, unavailable Git in an existing checkout, an enclosing-repo ignore rule that excludes `target_root`
    itself, or already-tracked `.private/` / `.conclave/local.toml` before any kit file is written (and identically
    on `--dry-run`)."""
    for rel in (".gitignore", ".conclave/.gitignore"):
        path = target_root / rel
        if _is_link(path):
            raise ValueError(f"Refusing to modify symlinked {rel} in {target_root}; add ignore rules manually")
        if path.exists() and not path.is_file():
            raise ValueError(f"Refusing non-file {rel} in {target_root}; add ignore rules manually")
    prefix = _check_untracked_in_git(target_root, (".private/", LOCAL))
    if prefix is not None:
        own_sources = (f"{prefix}.gitignore", f"{prefix}.conclave/.gitignore")
        probes = (".", ".conclave/") if prefix else (".conclave/",)
        for probe_dir in probes:
            proc = subprocess.run(
                ["git", "check-ignore", "--no-index", "-v", "-z", "--stdin"],
                cwd=str(target_root),
                env=_clean_git_env(),
                input=probe_dir.encode("utf-8") + b"\0",
                capture_output=True,
                timeout=15,
            )
            if proc.returncode == 0:
                fields = (proc.stdout or b"").split(b"\0")
                if len(fields) >= 4:
                    source = fields[0].decode("utf-8", errors="surrogateescape").replace("\\", "/")
                    pattern = fields[2].decode("utf-8", errors="surrogateescape")
                    if not pattern.startswith("!") and source not in own_sources:
                        raise ValueError(
                            f"Target path {probe_dir} under {target_root} is excluded by an enclosing Git ignore rule "
                            f"({source}: {pattern}); unignore it or initialize its own repository first"
                        )
            elif proc.returncode != 1:
                detail = (proc.stderr or proc.stdout or b"").decode("utf-8", errors="replace").strip()
                raise ValueError(f"git check-ignore failed in {target_root} (exit {proc.returncode}): {detail}")
    root_ig = target_root / ".gitignore"
    if root_ig.exists():
        st = os.lstat(root_ig)
        if st.st_nlink > 1:
            git_ignored = _git_repo_ignores(
                target_root, ".private/", allowed_sources=(".gitignore",), require_patterns=PRIVATE_GITIGNORE_RULES
            )
            already = (git_ignored is True) or (
                git_ignored is None
                and _gitignore_bytes_have_unnegated_rule(_read_regular_file_bytes(root_ig), PRIVATE_GITIGNORE_RULES_BYTES)
            )
            if not already:
                raise ValueError(
                    f"Refusing hard-linked .gitignore in {target_root} (st_nlink={st.st_nlink}); add ignore rules manually"
                )
    conclave_ig = target_root / ".conclave" / ".gitignore"
    if conclave_ig.exists():
        st = os.lstat(conclave_ig)
        if st.st_nlink > 1:
            git_ignored = _git_repo_ignores(target_root, LOCAL, allowed_sources=(".gitignore", ".conclave/.gitignore"))
            already = (git_ignored is True) or (
                git_ignored is None
                and _gitignore_bytes_have_unnegated_rule(_read_regular_file_bytes(conclave_ig), LOCAL_TOML_GITIGNORE_RULES_BYTES)
            )
            if not already:
                raise ValueError(
                    f"Refusing hard-linked .conclave/.gitignore in {target_root} (st_nlink={st.st_nlink}); add ignore rules manually"
                )


def _git_repo_ignores(
    target_root: Path,
    rel_path: str,
    *,
    allowed_sources: tuple[str, ...],
    require_patterns: tuple[str, ...] | None = None,
) -> bool | None:
    """Return True if Git ignores `rel_path` via one of `allowed_sources` (in-repo `.gitignore` files relative to
    `target_root`, accounting for any enclosing monorepo prefix, never a global `core.excludesFile` or
    `.git/info/exclude`), False if not, or None if `target_root` is not inside a Git worktree.
    Uses NUL-delimited `-v -z` output so directory names containing colons or spaces parse cleanly."""
    prefix = _check_untracked_in_git(target_root, (rel_path,))
    if prefix is None:
        return None
    proc = subprocess.run(
        ["git", "check-ignore", "-v", "-z", "--stdin"],
        cwd=str(target_root),
        env=_clean_git_env(),
        input=rel_path.encode("utf-8") + b"\0",
        capture_output=True,
        timeout=15,
    )
    if proc.returncode == 1:
        return False
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or b"").decode("utf-8", errors="replace").strip()
        raise ValueError(f"git check-ignore failed in {target_root} (exit {proc.returncode}): {detail}")
    fields = (proc.stdout or b"").split(b"\0")
    if len(fields) < 4:
        return False
    source = fields[0].decode("utf-8", errors="surrogateescape").replace("\\", "/")
    pattern = fields[2].decode("utf-8", errors="surrogateescape")
    if pattern.startswith("!"):
        return False
    prefixed_allowed = tuple(f"{prefix}{src}" for src in allowed_sources)
    if source not in prefixed_allowed:
        return False
    if require_patterns is not None and pattern not in require_patterns:
        return False
    return True


def _gitignore_bytes_have_unnegated_rule(raw: bytes, accepted_rules: bytes | tuple[bytes, ...]) -> bool:
    """Conservative LF-byte-level check used when the target is not a Git repository yet or after an append.
    Returns True when any rule in `accepted_rules` appears as an exact LF-delimited rule (stripping at most one
    trailing CR) and no subsequent negation rule (`!...`) follows it; unrelated non-negation rules are allowed."""
    rules = (accepted_rules,) if isinstance(accepted_rules, bytes) else accepted_rules
    matched = False
    for part in raw.split(b"\n"):
        line = part[:-1] if part.endswith(b"\r") else part
        if not line or line.startswith(b"#"):
            continue
        if line in rules:
            matched = True
        elif matched and line.startswith(b"!"):
            matched = False
    return matched


def _read_regular_file_bytes(path: Path) -> bytes:
    """Read `path` without following symlinks or blocking on a FIFO, verifying a regular file handle before reading."""
    binary = getattr(os, "O_BINARY", 0)
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    nonblock = getattr(os, "O_NONBLOCK", 0)
    flags = os.O_RDONLY | binary | nofollow | nonblock
    if _is_link(path):
        raise ValueError(f"Refusing to read symlinked {path}; add ignore rules manually")
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        if nofollow and getattr(exc, "errno", None) == getattr(os, "ELOOP", 40):
            raise ValueError(f"Refusing to read symlinked {path}; add ignore rules manually") from None
        raise
    try:
        if _is_link(path) or not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError(f"Refusing non-regular or symlinked {path}; add ignore rules manually")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(fd)


def _open_regular_append(path: Path, *, exclusive: bool) -> int:
    """Open `path` for append-only writes without following symlinks or blocking on a FIFO, verifying a regular file."""
    binary = getattr(os, "O_BINARY", 0)
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    nonblock = getattr(os, "O_NONBLOCK", 0)
    flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT | binary | nofollow | nonblock
    if exclusive:
        flags |= os.O_EXCL
    if _is_link(path):
        raise ValueError(f"Refusing to modify symlinked {path}; add ignore rules manually")
    try:
        fd = os.open(path, flags, 0o666)
    except OSError as exc:
        if exclusive and isinstance(exc, FileExistsError):
            raise
        if nofollow and getattr(exc, "errno", None) == getattr(os, "ELOOP", 40):
            raise ValueError(f"Refusing to modify symlinked {path}; add ignore rules manually") from None
        if nonblock and getattr(exc, "errno", None) == getattr(os, "ENXIO", 6):
            raise ValueError(f"Refusing non-regular FIFO {path}; add ignore rules manually") from None
        raise
    try:
        st = os.fstat(fd)
        if _is_link(path) or not stat.S_ISREG(st.st_mode):
            raise ValueError(f"Refusing non-regular or symlinked {path}; add ignore rules manually")
        if st.st_nlink > 1:
            raise ValueError(f"Refusing hard-linked {path} (st_nlink={st.st_nlink}); add ignore rules manually")
    except Exception:
        os.close(fd)
        raise
    return fd


def _append_gitignore_rule(path: Path, rule_line: bytes, *, creating: bool) -> None:
    """Append `rule_line` to `path` in one atomic `O_APPEND` write without overwriting any concurrent edit: uses
    `O_APPEND | O_CREAT | O_EXCL` for new files and kernel-level `O_APPEND` for existing files, always prefixing
    `b'\\n'` so a concurrent writer's unterminated rule is never merged with `rule_line`, refuses any short write
    (never issuing a second write that could interleave), enforces regular-file non-symlink non-blocking handles
    on both write and post-close read, and verifies the canonical rule is present at `path` after close."""
    path.parent.mkdir(parents=True, exist_ok=True)
    canonical = rule_line.rstrip(b"\r\n")
    payload = b"\n" + rule_line
    fd: int | None = None
    if creating:
        try:
            fd = _open_regular_append(path, exclusive=True)
        except FileExistsError:
            fd = None
    if fd is None:
        fd = _open_regular_append(path, exclusive=False)
    try:
        size_before = os.fstat(fd).st_size
        written = os.write(fd, payload)
        if written != len(payload):
            if written > 0 and os.fstat(fd).st_size == size_before + written:
                os.ftruncate(fd, size_before)
            raise OSError(f"short write while updating ignore file ({written} of {len(payload)} bytes)")
    finally:
        os.close(fd)
    if not _gitignore_bytes_have_unnegated_rule(_read_regular_file_bytes(path), canonical):
        raise ValueError(f"{path} was replaced or truncated concurrently before {canonical.decode()} landed; retry")


def _ensure_private_gitignore(target_root: Path, *, dry_run: bool = False) -> str:
    """Ensure `<target_root>/.gitignore` ignores the `.private/` directory itself (so Git never descends into
    `.private/` and child negations like `!.private/README.md` cannot stage overlay files) without overwriting
    existing rules."""
    _preflight_settings_gitignores(target_root)
    gitignore = target_root / ".gitignore"
    probe = ".private/"
    git_ignored = _git_repo_ignores(
        target_root, probe, allowed_sources=(".gitignore",), require_patterns=PRIVATE_GITIGNORE_RULES
    )
    if git_ignored is True:
        return "already_present"
    if not gitignore.exists():
        if dry_run:
            return "would_create"
        _append_gitignore_rule(gitignore, b".private/\n", creating=True)
        if _git_repo_ignores(target_root, probe, allowed_sources=(".gitignore",), require_patterns=PRIVATE_GITIGNORE_RULES) is False:
            raise ValueError(f".private/ is still not ignored by .gitignore in {target_root}")
        return "created"
    raw = _read_regular_file_bytes(gitignore)
    if git_ignored is None and _gitignore_bytes_have_unnegated_rule(raw, PRIVATE_GITIGNORE_RULES_BYTES):
        return "already_present"
    if dry_run:
        return "would_add"
    _append_gitignore_rule(gitignore, b".private/\n", creating=False)
    if _git_repo_ignores(target_root, probe, allowed_sources=(".gitignore",), require_patterns=PRIVATE_GITIGNORE_RULES) is False:
        raise ValueError(f".private/ is still not ignored by .gitignore in {target_root}")
    return "added"


def _ensure_local_toml_gitignore(target_root: Path, *, dry_run: bool = False) -> str:
    """Ensure `.conclave/local.toml` is ignored by `.conclave/.gitignore` (or root `.gitignore`) even when an
    adopting project already had a custom `.conclave/.gitignore` that omitted `local.toml`."""
    _preflight_settings_gitignores(target_root)
    allowed = (".gitignore", ".conclave/.gitignore")
    git_ignored = _git_repo_ignores(target_root, LOCAL, allowed_sources=allowed)
    if git_ignored is True:
        return "already_present"
    conclave_ig = target_root / ".conclave" / ".gitignore"
    if not conclave_ig.exists():
        if dry_run:
            return "would_create"
        _append_gitignore_rule(conclave_ig, b"local.toml\n", creating=True)
        if _git_repo_ignores(target_root, LOCAL, allowed_sources=allowed) is False:
            raise ValueError(f"{LOCAL} is still not ignored by {conclave_ig}")
        return "created"
    raw = _read_regular_file_bytes(conclave_ig)
    if git_ignored is None and _gitignore_bytes_have_unnegated_rule(raw, LOCAL_TOML_GITIGNORE_RULES_BYTES):
        return "already_present"
    if dry_run:
        return "would_add"
    _append_gitignore_rule(conclave_ig, b"local.toml\n", creating=False)
    if _git_repo_ignores(target_root, LOCAL, allowed_sources=allowed) is False:
        raise ValueError(f"{LOCAL} is still not ignored by {conclave_ig}")
    return "added"


def _local_settings_module():
    """Load the base kit's shared `.conclave/local_settings.py` helper (installed copy first, kit template fallback)."""
    for candidate in (
        FORGE_ROOT / ".conclave" / "local_settings.py",
        FORGE_ROOT / "kits" / "base" / "templates" / ".conclave" / "local_settings.py",
    ):
        if candidate.is_file():
            spec = importlib.util.spec_from_file_location("_forge_local_settings", candidate)
            if spec is not None and spec.loader is not None:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                return module
    raise ValueError(f".conclave/local_settings.py is missing under {FORGE_ROOT}")


def load_projects(path: Path | None = None, *, root: Path | None = None) -> list[dict]:
    """The projects the drift report covers, from the `[[projects]]` tables of `.conclave/local.toml` (override) and
    `.private/local.toml` (overlay), or from an explicit single TOML file when `path` is passed. Returns each as
    `{"name", "windows", "posix"}`, a path left out being None; no `[[projects]]` is an empty list. Refuses with a
    ValueError naming the file(s) and the entry."""
    if path is not None and root is not None:
        raise ValueError("load_projects accepts either path or root, not both")
    ls = _local_settings_module()
    if path is not None:
        target = Path(path)
        label = str(target)
        try:
            data = ls.read_toml_file(target, label=label)
        except FileNotFoundError:
            raise ValueError(f"{label}: missing: copy .conclave/local.example.toml to it and list the projects") from None
        except ls.LocalSettingsError as exc:
            raise ValueError(str(exc)) from None
    else:
        base_root = FORGE_ROOT if root is None else Path(root)
        try:
            data, loaded = ls.load_local_settings(base_root)
        except ls.LocalSettingsError as exc:
            raise ValueError(str(exc)) from None
        if not loaded:
            raise ValueError(
                f"{LOCAL} and {OVERLAY}: missing: copy .conclave/local.example.toml to {LOCAL} or populate {OVERLAY} and list the projects"
            )
        label = " / ".join(loaded)

    def fault(what: str) -> ValueError:
        return ValueError(f"{label}: {what}")

    listed = data.get("projects", [])
    if not isinstance(listed, list):
        raise fault("projects must be [[projects]] tables")
    projects: list[dict] = []
    seen: set[str] = set()
    for index, entry in enumerate(listed):
        where = f"projects[{index}]"
        if not isinstance(entry, dict) or "name" not in entry or set(entry) - {"name", "alias", "windows", "posix"}:
            raise fault(f"{where} needs a name and only the keys name, alias, posix and windows")
        if not isinstance(entry["name"], str) or not entry["name"].strip():
            raise fault(f"{where}.name must be a non-empty string")
        where = f"{where} ({entry['name']})"
        if "alias" in entry and (not isinstance(entry["alias"], str) or not entry["alias"].strip()):
            raise fault(f"{where}.alias must be a non-empty string")
        if entry["name"] in seen:
            raise fault(f"{where}: the name appears twice")
        seen.add(entry["name"])
        for key in ("windows", "posix"):
            if key in entry and (not isinstance(entry[key], str) or not entry[key]):
                raise fault(f"{where}.{key} must be a non-empty path")
        if "windows" not in entry and "posix" not in entry:
            raise fault(f"{where}: needs a windows or a posix path")
        projects.append({"name": entry["name"], "windows": entry.get("windows"), "posix": entry.get("posix")})
    return projects


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
                  sync.as_posix() if sync.is_file() else "wordpress-connect step 4: port it for this site")
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
            raw_mcp = json.loads((target_root / ".mcp.json").read_text(encoding="utf-8")).get("mcpServers", {})
        except (OSError, ValueError, AttributeError):
            raw_mcp = {}
        registered = raw_mcp if isinstance(raw_mcp, dict) else {}
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

    ticket_files = (
        "scripts/open-dashboard.py",
        "scripts/ticket-login.py",
        "tools/ticket-login/conclave-ticket-login.php",
    )
    if not pin:
        add_check("ticket-login", "setup_required", f"see site-pin ({pin_state})")
        add_check("ticket-login-user", "setup_required", f"see site-pin ({pin_state})")
    elif not ssh_enabled:
        add_check("ticket-login", "optional", "no SSH in site pin; ticket login needs SSH")
        add_check("ticket-login-user", "optional", "no SSH in site pin; ticket login needs SSH")
    else:
        missing_files = [rel for rel in ticket_files if not (target_root / rel).is_file()]
        missing_ssh = None
        try:
            wp_site.ssh_identity(pin)
            wp_site.require(pin, "ssh.wp_path")
        except ValueError as error:
            missing_ssh = str(error).removeprefix("not set in .conclave/wordpress-site.json yet: ")
        if missing_ssh:
            add_check("ticket-login", "setup_required", f"see site-ssh: missing {missing_ssh}")
        elif missing_files:
            add_check("ticket-login", "setup_required", "missing: " + ", ".join(missing_files))
        else:
            hint = "run python scripts/ticket-login.py status to check the site"
            if os.name == "nt":
                hint += " (run from WSL or Linux)"
            add_check("ticket-login", "ok", hint)
        basic_entries = [entry for entry in servers.values()
                         if isinstance(entry, dict) and entry.get("scheme") == "basic"]
        if host == "wpcom" and not basic_entries:
            add_check("ticket-login-user", "optional",
                      "WordPress.com connector alone: add a basic MCP entry with wordpress_user_id to enable ticket login")
        else:
            try:
                uid = wp_site.pinned_user(pin)
            except ValueError as error:
                add_check("ticket-login-user", "setup_required", str(error))
            else:
                add_check("ticket-login-user", "ok", f"user ID {uid}")

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
    """End every surviving POSIX process whose environment carries `CONCLAVE_CHECK_ALL_TAG=<tag>`, or `<tag>` among the
    comma-separated `CONCLAVE_CHECK_ALL_OUTER` (a suite run inside this one), even in a detached session."""
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
                        if _tagged(handle.read().split(b"\0"), needle_bytes, tag.encode()):
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
        if _tagged([word.encode() for word in parts[1].split()], needle_bytes, tag.encode()):
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                continue


OUTER_TAGS = "CONCLAVE_CHECK_ALL_OUTER"  # the tags of the suites a suite runs inside, comma-separated


def _tagged(entries: list, needle: bytes, tag: bytes) -> bool:
    """Whether a process's environment entries carry `tag`: as its own suite's tag, or as an outer suite's."""
    if needle in entries:
        return True
    prefix = OUTER_TAGS.encode() + b"="
    return any(entry.startswith(prefix) and tag in entry[len(prefix):].split(b",") for entry in entries)


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


def _probe_agy_cli(dispatch, executable: str) -> dict:
    """Run the three read-only Antigravity CLI probes once per executable so multiple reviewers sharing a CLI never
    repeat subprocess launches."""
    code, text, problem = _probe([executable, "--help"])
    if code is None:
        return {"error": ("setup_required", f"{executable} --help: {problem}")}
    if code != 0:
        return {"error": ("unexpected", f"{executable} --help exited {code}")}
    help_text = text
    # If core non-effort flags are already missing, skip the remaining probes.
    core_missing = dispatch.agy_flags_missing(help_text, need_effort=False)
    if core_missing:
        return {"help_text": help_text}
    fd, name = tempfile.mkstemp(prefix="forge-agy-settings-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(dispatch.AGY_REVIEW_SETTINGS, handle)
        code, text, problem = _probe([executable, "--settings", name, "agents"])
    finally:
        Path(name).unlink(missing_ok=True)
    if code is None:
        return {"help_text": help_text, "error": ("setup_required", f"{executable} --settings: {problem}")}
    said = next((line.strip() for line in text.splitlines() if "--settings:" in line), "")
    if said:
        return {"help_text": help_text, "error": ("unexpected", f"{executable} refuses the dispatcher's settings: {said}")}
    if code != 0:
        # Not a refusal of the settings: the CLI failed for a reason of its own (it cannot start, it is not signed in).
        first = next((line.strip() for line in text.splitlines() if line.strip()), "no output")
        return {"help_text": help_text, "error": ("unexpected", f"{executable} --settings <file> agents exited {code}: {first[:200]}")}
    code, text, problem = _probe([executable, "--version"])
    if code is None:
        return {"help_text": help_text, "error": ("setup_required", f"{executable} --version: {problem}")}
    if code != 0 or not text.strip():
        return {"help_text": help_text, "error": ("unexpected", f"{executable} --version exited {code} and named no version")}
    return {"help_text": help_text, "version": text.strip().splitlines()[0]}


def _evaluate_agy_flags(dispatch, executable: str, probe: dict, *, need_effort: bool = False) -> tuple[str, str]:
    """Evaluate cached CLI probe output for one Antigravity reviewer with or without explicit `--effort`."""
    if "help_text" not in probe:
        return probe["error"]
    missing = dispatch.agy_flags_missing(probe["help_text"], need_effort=need_effort)
    if missing:
        if missing == [dispatch.AGY_EFFORT_FLAG]:
            return "unexpected", (f"{executable} no longer lists {dispatch.AGY_EFFORT_FLAG}, which the dispatcher "
                                  f"passes for explicit-effort Antigravity reviews: those reviews would fail")
        return "unexpected", (f"{executable} no longer lists {', '.join(missing)}, which the dispatcher passes: every "
                              f"Antigravity review would return no review")
    if "error" in probe:
        return probe["error"]
    checked_flags = dispatch.AGY_FLAGS + ((dispatch.AGY_EFFORT_FLAG,) if need_effort else ())
    return "ok", f"{executable} {probe['version']} lists {', '.join(checked_flags)} and accepts the review settings"


def _agy_flags_check(dispatch, executable: str, *, need_effort: bool = False) -> tuple[str, str]:
    """(status, detail) for one Antigravity reviewer: every flag the dispatcher passes is in the installed CLI's
    --help, and the CLI accepts the dispatcher's session settings. A probe that failed is never `ok`."""
    return _evaluate_agy_flags(dispatch, executable, _probe_agy_cli(dispatch, executable), need_effort=need_effort)


def _installed_reviewer_supports_agy_effort(target_root: Path) -> tuple[bool, str]:
    """Read-only check that the target project's installed reviewer scripts support explicit Antigravity `--effort`."""
    dispatch_path = target_root / "scripts/review-dispatch.py"
    pin_path = target_root / "scripts/review_pin.py"
    if not dispatch_path.is_file():
        return False, "scripts/review-dispatch.py is missing; repair with `python forge.py update <project> reviewer`"
    if not pin_path.is_file():
        return False, "scripts/review_pin.py is missing; repair with `python forge.py update <project> reviewer`"
    try:
        dispatch_text = dispatch_path.read_text(encoding="utf-8", errors="replace")
        pin_text = pin_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return False, f"could not read installed reviewer scripts: {exc}"
    legacy_msg = "Antigravity carries the effort in the model name"
    if legacy_msg in dispatch_text or legacy_msg in pin_text:
        return False, ("installed reviewer scripts still refuse explicit Antigravity effort; "
                       "update with `python forge.py update <project> reviewer`")
    if "AGY_EFFORT_FLAG" not in dispatch_text:
        return False, ("installed scripts/review-dispatch.py predates explicit Antigravity --effort dispatch; "
                       "update with `python forge.py update <project> reviewer`")
    return True, "scripts/review-dispatch.py and scripts/review_pin.py support explicit Antigravity --effort"


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
        schedule = pin.get("schedule")
        scheduled_efforts = bool(module.review_pin.schedule_efforts(schedule)) if schedule else False
        routed_reviewers = {chain[0] for chain in pin["routes"].values() if isinstance(chain, list) and chain}
        uses_agy_effort = any(
            reviewer["cli"] == "agy"
            and not module.review_pin.is_agy_orchestrator(reviewer["model"])
            and (
                bool(reviewer.get("effort"))
                or (name in routed_reviewers and scheduled_efforts)
            )
            for name, reviewer in pin["reviewers"].items()
        )
        if uses_agy_effort and (target_root / "scripts/review-dispatch.py").is_file():
            supported, detail = _installed_reviewer_supports_agy_effort(target_root)
            add_check("reviewer-kit-effort", "ok" if supported else "unexpected", detail)
        probed: dict[str, dict] = {}
        for name, reviewer in pin["reviewers"].items():
            # The dispatcher's own lookup, so doctor probes the executable a review would run: on Windows
            # shutil.which looks in the working directory first, and the dispatcher never does.
            found = module.find_cli(reviewer["cli"])
            add_check(f"reviewer:{name}", "ok" if found else "setup_required",
                      f"{reviewer['model']} via {found}" if found else f"{reviewer['cli']} CLI not installed; a round routed to this reviewer has no review")
            if found and reviewer["cli"] == "agy":
                need_effort = (
                    name in routed_reviewers
                    and not module.review_pin.is_agy_orchestrator(reviewer["model"])
                    and (scheduled_efforts if schedule else bool(reviewer.get("effort")))
                )
                if found not in probed:  # one set of subprocess probes per executable
                    probed[found] = _probe_agy_cli(module, found)
                add_check(f"reviewer-flags:{name}", *_evaluate_agy_flags(module, found, probed[found], need_effort=need_effort))


def _doctor_unattended(target_root: Path, add_check, system: str | None = None) -> None:
    """The unattended kit's files, the todo kit it runs under (the run guard), and tmux, which holds the run: it
    exists on Linux and in WSL only, so on Windows the kit runs in WSL."""
    templates = FORGE_ROOT / "kits/unattended/templates"
    for src in sorted(p for p in templates.rglob("*") if p.is_file() and not CACHE_DIRS.intersection(p.parts)):
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
    # The shortcuts draw their icons with the launchers kit's renderer, which this kit brings (D07 T01 section 3).
    renderer = target_root / LAUNCHERS_RENDERER
    add_check(LAUNCHERS_RENDERER, "ok" if renderer.is_file() else "missing",
              renderer.as_posix() if renderer.is_file() else
              f"{renderer.as_posix()} (the launchers kit's: python forge.py kit {target_root.as_posix()} unattended)")
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


# The kits the bare `doctor <target>` adds to the stack kit's checks when they are installed: only those whose
# checks read files and PATH. The todo and reviewer branches start other programs, so they stay behind their name.
BARE_DOCTOR_ALSO = ("lsp",)


def _lsp_table_module():
    """The lsp kit's table module, loaded from the kit (forge reads; the project's copy is the project's), so the
    doctor holds a table to the rules the kit's own tools hold it to."""
    path = FORGE_ROOT / "kits/lsp/templates/scripts/lib/lsp_table.py"
    module = types.ModuleType("_forge_lsp_table")
    module.__file__ = str(path)
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), module.__dict__)
    return module


WORDPRESS_OPENER = "scripts/open-dashboard.py"
WORDPRESS_LAUNCHER_LINK = {
    "label": "WordPress",
    "mark": "wordpress",
    "run": "python3 scripts/open-dashboard.py",
    "wsl": True,
}


def _is_regular_file(path: Path) -> bool:
    """True only when `path` itself is a regular file (never a symlink, FIFO, socket, or folder)."""
    try:
        return stat.S_ISREG(os.lstat(path).st_mode)
    except OSError:
        return False


def _installed_launchers_supports_wsl(target_root: Path) -> bool:
    """Whether any installed launchers scripts in `target_root` accept the `wsl` key on `run` links. Checked
    statically (AST for `launchers.py`, text check for `project-shortcuts.ps1`) so target code is never executed."""
    loader = target_root / "scripts/lib/launchers.py"
    if os.path.lexists(loader):
        if _has_unsafe_parent(target_root, "scripts/lib/launchers.py") or not _is_regular_file(loader):
            return False
        try:
            tree = ast.parse(loader.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, SyntaxError):
            return False
        has_wsl_key = any(
            isinstance(node, ast.Constant) and node.value == "wsl"
            for fn in tree.body
            if isinstance(fn, ast.FunctionDef) and fn.name == "load_profile"
            for node in ast.walk(fn)
        )
        if not has_wsl_key:
            return False
    ps1 = target_root / "scripts/project-shortcuts.ps1"
    if os.path.lexists(ps1):
        if _has_unsafe_parent(target_root, "scripts/project-shortcuts.ps1") or not _is_regular_file(ps1):
            return False
        try:
            text = ps1.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return False
        if "'wsl'" not in text:
            return False
    return True


def _merge_wordpress_launcher_link(target_root: Path, dry_run: bool, installing: str,
                                   installed: list[str]) -> dict | None:
    """Declare the WordPress dashboard link in `.conclave/launchers.json` when both the WordPress opener and a
    launcher profile are present (or being installed in this run), regardless of which kit was installed first."""
    opener = target_root / WORDPRESS_OPENER
    has_opener = (WORDPRESS_OPENER in installed) or (
        not _has_unsafe_parent(target_root, WORDPRESS_OPENER) and _is_regular_file(opener)
    )
    if not has_opener:
        return None
    profile_path = target_root / LAUNCHERS_PROFILE
    profile_exists = os.path.lexists(profile_path)
    seeding = (installing == "launchers") and (LAUNCHERS_PROFILE in installed)
    if not profile_exists and not seeding:
        return None
    if _has_unsafe_parent(target_root, LAUNCHERS_PROFILE) or _is_link(profile_path):
        return {"refused": f"{LAUNCHERS_PROFILE}: refusing a profile that is a link or has an unsafe parent"}
    if profile_exists and not _is_regular_file(profile_path):
        return {"refused": f"{LAUNCHERS_PROFILE}: not a regular file"}
    if not _installed_launchers_supports_wsl(target_root):
        return {
            "refused": (
                f"{LAUNCHERS_PROFILE}: installed launchers kit does not support wsl run links; "
                f"run 'python forge.py update {target_root.as_posix()} launchers' first"
            )
        }
    launchers = _toolchain_module("launchers", "lib/launchers.py")
    source_path = profile_path if profile_exists else (FORGE_ROOT / "kits/launchers/templates" / LAUNCHERS_PROFILE)
    try:
        profile = launchers.load_profile(source_path, target_root, unset=True)
    except launchers.ProfileError as exc:
        return {"refused": str(exc)}
    target_label = WORDPRESS_LAUNCHER_LINK["label"]
    target_lower = target_label.lower()
    target_slug = launchers.slug(target_label)
    for entry in profile["links"]:
        if entry == WORDPRESS_LAUNCHER_LINK:
            return {"kept": [target_label]}
        if entry["label"].lower() == target_lower or launchers.slug(entry["label"]) == target_slug:
            return {"conflict": f"{LAUNCHERS_PROFILE}: existing link {entry['label']!r} conflicts with {target_label!r}"}
    profile["links"].append(dict(WORDPRESS_LAUNCHER_LINK))
    if dry_run:
        return {"added": [target_label]}
    try:
        atomic_write(profile_path, json.dumps(profile, indent=2) + "\n")
    except OSError as exc:
        return {"failed": f"{LAUNCHERS_PROFILE}: {exc.strerror or exc}"}
    return {"added": [target_label]}


def _lsp_write_failed(result: dict) -> bool:
    """Whether a kit install could not write the server table, the Claude Code plugin that follows it, or the
    launcher profile: the files were installed, the result says what was left, and the command line exits 1 so a
    caller that reads only the exit code does not take a stale merge for a finished install."""
    servers = result.get("lsp_servers") or {}
    links = result.get("launcher_links") or {}
    return "failed" in servers or "plugin_failed" in servers or "failed" in links


def _lsp_plugin_module():
    """The lsp kit's plugin generator, loaded from the kit as the table module is, so the doctor compares a
    project's Claude Code plugin with what the kit's own tool writes."""
    path = FORGE_ROOT / "kits/lsp/templates/scripts/lib/lsp_plugin.py"
    module = types.ModuleType("_forge_lsp_plugin")
    module.__file__ = str(path)
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), module.__dict__)
    return module


def _kit_file_checks(kit: str, target_root: Path, add_check) -> None:
    """One check per file a kit installs, `ok` or `missing`. The list is the kit's own templates folder, so a file
    the kit gains is checked without a second list. A file in an agent's folder is checked only for the agents
    the project was installed for (the record's, else the agent folders it has): a project installed for one
    agent is not told the other agents' skills are missing."""
    templates = FORGE_ROOT / "kits" / kit / "templates"
    record = load_record(target_root) if (target_root / RECORD).is_file() else None
    agents = _diff_agents(target_root, (record or {}).get("kits", {}).get(kit))
    for src in sorted(templates.rglob("*"), key=lambda path: path.relative_to(templates).as_posix()):
        rel = src.relative_to(templates).as_posix()
        if not any(_rel_allowed_for_agent(rel, agent) for agent in agents):
            continue
        if src.is_file() and not CACHE_DIRS.intersection(src.parts) and not rel.endswith(FORGE_SUFFIXES):
            path = target_root / rel
            add_check(rel, "ok" if path.is_file() else "missing", path.as_posix())


_TOOLCHAIN_MODULES: dict[str, types.ModuleType] = {}


def _toolchain_module(kit: str, script: str = "toolchain-check.py") -> types.ModuleType:
    """A script of a toolchain kit (toolchain-check.py unless named), loaded from the kit (forge reads; the
    project's copy is the project's), so the doctor checks a pin file exactly as the kit's own script does. Kept
    per file, so its limits can be read back."""
    path = FORGE_ROOT / "kits" / kit / "templates/scripts" / script
    key = str(path)
    if key not in _TOOLCHAIN_MODULES:
        name = f"{kit}_{script.removesuffix('.py')}".replace("-", "_").replace("/", "_")
        module = types.ModuleType(f"_forge_{name}")
        module.__file__ = key
        exec(compile(path.read_text(encoding="utf-8"), key, "exec"), module.__dict__)
        _TOOLCHAIN_MODULES[key] = module
    return _TOOLCHAIN_MODULES[key]


CLANGD_CONFIG = ".clangd"
CLANGD_DATABASE = "compile_commands.json"   # the one file name clangd reads a database from


def _clangd_database(path: Path) -> tuple[str, str]:
    """What a `.clangd` says of the compile database, read in one form only, the seed's: one YAML document with
    `CompileFlags:` at the left margin and `CompilationDatabase:` indented under it. Returns ("folder", the value),
    ("none", why clangd is then given no folder by this file), ("unknown", why the file cannot be read that way)
    or ("unreadable", the system's reason). Nothing is guessed from a form this does not take."""
    try:
        text = path.read_bytes().decode("utf-8")
    except UnicodeDecodeError as exc:
        return "unreadable", f"not UTF-8 ({exc.reason})"
    except OSError as exc:
        return "unreadable", exc.strerror or str(exc)
    lines = [line.rstrip() for line in text.splitlines()]
    # A separator may carry a comment (`--- # the headers`), and `...` ends a document too.
    if any(re.match(r"(---|\.\.\.)(\s.*)?$", line) for line in lines):
        return "unknown", "it holds more than one document"
    if any(re.match(r"If\s*:", line) for line in lines):
        return "unknown", "it has a condition (`If:`)"
    inside = False
    for line in lines:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line[0].isspace():
            head = re.match(r"CompileFlags\s*:\s*(.*)$", line)
            inside = head is not None
            if head and head.group(1).split("#", 1)[0].strip():
                return "unknown", "`CompileFlags` is not written as a block"
            continue
        key = re.match(r"\s+CompilationDatabase\s*:\s*(.*)$", line) if inside else None
        if key:
            value = key.group(1)
            quoted = re.match(r"""(["'])(.*)\1\s*(?:#.*)?$""", value)
            value = quoted.group(2) if quoted else value.split(" #", 1)[0].strip()
            if value in ("", "Ancestors"):
                break
            return "folder", value
    return "none", "it names no `CompilationDatabase`, so clangd searches the folders above each source file"


def _doctor_clangd(target_root: Path, pin_file: dict, add_check) -> None:
    """The C and C++ kit's two checks of clangd's wiring, from files only. `clangd-server`: the project's table
    has a `clangd` server. `clangd-config`: `.clangd` gives clangd, as `CompilationDatabase`, the folder that
    compdb-check.py reads the database from. The two are compared as each program resolves them: clangd reads a
    relative folder from the folder `.clangd` is in, and looks for the database in that folder and in its `build`
    subfolder (measured with clangd 19.1.7 and 22.1.3); the check reads `<root>/<compdb.path>`."""
    root = pin_file["root"]
    if not (target_root / LSP_TABLE).is_file():
        add_check("clangd-server", "setup_required",
                  f"no {LSP_TABLE}: install the lsp kit with python forge.py kit {target_root.as_posix()} lsp")
    else:
        table = _lsp_table_module()
        try:
            entry = next((server for server in table.load_servers(target_root) if server["name"] == "clangd"), None)
        except table.TableError as exc:
            add_check("clangd-server", "unexpected", str(exc))
        else:
            if entry is not None:
                add_check("clangd-server", "ok", f"{LSP_TABLE}: clangd, in {entry['root']}")
            else:
                where = "" if root == "." else f" --root {root}"
                add_check("clangd-server", "setup_required",
                          f"{LSP_TABLE} has no clangd: python scripts/lsp-servers.py add cpp{where}")
    config = target_root / CLANGD_CONFIG
    if not config.is_file():
        return   # the kit's file check has already said it is missing
    database = target_root / root / pin_file["compdb"]["path"]
    wanted = database.parent
    try:
        shown = wanted.resolve().relative_to(target_root.resolve()).as_posix()
    except ValueError:
        shown = wanted.as_posix()
    kind, value = _clangd_database(config)
    if kind == "unreadable":
        add_check("clangd-config", "unexpected", f"{CLANGD_CONFIG} cannot be read ({value})")
    elif database.name != CLANGD_DATABASE:
        # Whatever folder clangd is given, it reads a database only under this name.
        add_check("clangd-config", "unexpected",
                  f"clangd reads a database only from a file named {CLANGD_DATABASE}, and the one the freshness "
                  f"check watches is {shown}/{database.name}: clangd never reads it")
    elif kind == "folder":
        named = Path(value) if Path(value).is_absolute() else target_root / value
        here = os.path.normcase(os.path.abspath(wanted))
        direct = value != "None" and here == os.path.normcase(os.path.abspath(named))
        # clangd looks in the folder it is given first, and in a `build` folder of it only when that has none.
        through_build = value != "None" and here == os.path.normcase(os.path.abspath(named / "build"))
        earlier = named / CLANGD_DATABASE
        if direct:
            add_check("clangd-config", "ok", f"{CLANGD_CONFIG}: CompilationDatabase {value}, where the database is")
        elif through_build and not earlier.is_file():
            add_check("clangd-config", "ok",
                      f"{CLANGD_CONFIG}: CompilationDatabase {value}, whose build folder holds the database")
        elif through_build:
            add_check("clangd-config", "unexpected",
                      f"{CLANGD_CONFIG} names CompilationDatabase {value}, where clangd finds another "
                      f"{CLANGD_DATABASE} before the one in {shown} that the freshness check watches: remove "
                      f"that one, or write `CompilationDatabase: {shown}`")
        else:
            add_check("clangd-config", "unexpected",
                      f"{CLANGD_CONFIG} names CompilationDatabase {value}, and the database the freshness check "
                      f"watches is in {shown}: write `CompilationDatabase: {shown}`")
    else:
        add_check("clangd-config", "optional",
                  f"{CLANGD_CONFIG}: {value}; whether clangd reads the database in {shown} cannot be told from the "
                  f"file: it must be given `CompilationDatabase: {shown}`")


def _doctor_toolchain(target_root: Path, add_check, kit: str) -> None:
    """A toolchain kit's checks: each file the kit installs, the project's pin file (`tool-pins`), and each pinned
    tool as `tool:<name>`. A tool that is not ok is `setup_required` when the pin requires it and `optional` when
    it does not, whatever the cause, with the check script's own detail; `optional` is shown and never counted.
    The C and C++ kit adds `compile-database`: `ok` for a current database, `setup_required` with the status and
    the reason for any other, as the kit's compdb-check.py finds it."""
    _kit_file_checks(kit, target_root, add_check)
    module = _toolchain_module(kit)
    try:
        pin_file = module.load_pin_file(target_root / TOOLCHAIN_PINS[kit])
    except module.PinError as exc:
        add_check("tool-pins", "missing", str(exc))
        if kit == "toolchain-cpp" and \
                str(exc).startswith(f"{(target_root / TOOLCHAIN_PINS[kit]).as_posix()}: hardening"):
            # The loader refuses the whole file at a policy it cannot read, so the policy is reported refused.
            add_check("hardening-policy", "missing", str(exc))
        return
    pins = pin_file["tools"]
    add_check("tool-pins", "ok", f"{TOOLCHAIN_PINS[kit]}: {', '.join(pin['name'] for pin in pins) or 'no tool'}")
    # The project's own tool folders (vendor/bin, node_modules/.bin) are read under the app the pin file names.
    folders = module.search_folders(target_root, pin_file)
    for tool in module.check_tools(pins, time_limit=module.TIME_LIMIT, output_cap=module.OUTPUT_CAP, folders=folders):
        if tool["status"] == "ok":
            add_check(f"tool:{tool['name']}", "ok", f"{tool['command']} {tool['version']}")
        else:
            add_check(f"tool:{tool['name']}", "optional" if tool["optional"] else "setup_required", tool["detail"])
    if kit == "toolchain-web":
        _doctor_web_constraints(target_root / pin_file["root"], pins, module, add_check)
        _doctor_package_manager(target_root / pin_file["root"], pins, add_check)
    if kit == "toolchain-cpp":
        compdb = _toolchain_module(kit, "compdb-check.py")
        database = compdb.check_database(target_root, pin_file)   # reads, and starts nothing
        if database["status"] == "current":
            add_check("compile-database", "ok", database["detail"])
        else:
            again = compdb.regenerate_line(database)
            add_check("compile-database", "setup_required",
                      f"{database['status']}: {database['detail']}" + (f"; {again}" if again else ""))
        _doctor_hardening(target_root, pin_file, compdb, add_check)
        _doctor_clangd(target_root, pin_file, add_check)


HARDENING_NAMED = 3   # findings a hardening row names before it counts the rest


def _named(findings: list[str]) -> str:
    """The first HARDENING_NAMED findings, then how many more there are."""
    shown = "; ".join(findings[:HARDENING_NAMED])
    rest = len(findings) - HARDENING_NAMED
    return shown + (f"; and {rest} more" if rest > 0 else "")


def _doctor_hardening(target_root: Path, pin_file: dict, compdb, add_check) -> None:
    """The C and C++ kit's memory-safety rows, from the kit's hardening-check.py, which only reads files.
    `hardening-policy`: whether a policy is declared and what it covered. `hardening:compile` and `hardening:image`
    (only with a policy): `ok`; `setup_required` naming the first findings; `unknown` when the database is not
    current, nothing is under the sources, a binary cannot be read or a pattern names no file; `optional` when the
    policy declares no such half. `unknown` and `optional` are not counted: a stale database already counts as
    `compile-database`, and a binary not built yet is no fault of the build."""
    policy = pin_file["hardening"]
    if policy is None:
        add_check("hardening-policy", "optional",
                  f"no policy declared: add a `hardening` key to {TOOLCHAIN_PINS['toolchain-cpp']} "
                  "(docs/toolchain-cpp.md, Memory safety)")
        return
    check = _toolchain_module("toolchain-cpp", "hardening-check.py")
    compiled = check.check_compile(target_root, pin_file, compdb)
    images = check.check_images(target_root, pin_file)
    binaries = images["binaries"]
    add_check("hardening-policy", "ok",
              f"{len(policy['compile'])} compile requirement(s) on {compiled['checked']} first-party entr"
              f"{'y' if compiled['checked'] == 1 else 'ies'}; {len(policy['binaries'])} binary pattern(s) matching "
              f"{len(binaries)} binar{'y' if len(binaries) == 1 else 'ies'}")
    if compiled["status"] == "none":
        add_check("hardening:compile", "optional", compiled["detail"])
    elif compiled["status"] == "missing":
        short = [f"{item['requirement']} missing on {item['lacking']} entr{'y' if item['lacking'] == 1 else 'ies'}, "
                 f"first {item['first']}" for item in compiled["requirements"] if item["status"] == "missing"]
        add_check("hardening:compile", "setup_required", f"{compiled['detail']}: {_named(short)}")
    elif compiled["status"] == "ok":
        add_check("hardening:compile", "ok", compiled["detail"])
    else:
        again = f"; {compiled['regenerate']}" if compiled["regenerate"] else ""
        add_check("hardening:compile", "unknown", compiled["detail"] + again)
    if images["status"] == "none":
        add_check("hardening:image", "optional", images["detail"])
        return
    if images["status"] == "ok":
        add_check("hardening:image", "ok", images["detail"])
        return
    # Missing binaries first, then every other one that is not ok and each pattern naming no file, so a mixed
    # result drops no diagnostic without counting it.
    findings = [entry["detail"] for entry in binaries if entry["status"] == "missing"]
    findings += [entry["detail"] for entry in binaries if entry["status"] not in ("ok", "missing")]
    findings += [f"{pattern} names no file" for pattern in images["unmatched"]]
    add_check("hardening:image", "setup_required" if images["status"] == "missing" else "unknown",
              f"{images['detail']}: {_named(findings)}")


# What a PHP or Node project says of its own runtime: (the pin it is compared with, the manifest, where in it).
WEB_CONSTRAINTS = (("php", "composer.json", "require", "php"), ("node", "package.json", "engines", "node"))
_VERSION = r"v?([0-9]{1,9}(?:\.[0-9]{1,9}){0,7})(?:\.[xX*])*"
_LOWER_BOUND = re.compile(r"(?:\^|~|>=|=)?" + _VERSION)   # ^8.3, ~8.3.0, >=8.3, =8.3.1, 8.3.*, 20.x, 8.3
_UPPER_BOUND = re.compile(r"<=?" + _VERSION)               # <9, <=22: read, and no part of the lowest version


def _lowest_allowed(constraint: str, compare) -> str | None:
    """The lowest version a Composer or npm constraint allows, or None for a form this does not read.

    A constraint is alternatives (`a || b`, Composer's `a | b`), each a set of comparators that must all hold
    (`>=8.2 <8.5`, `>=8.2, >=8.3`). An alternative's lowest version is the highest of its lower bounds; the
    constraint's is the lowest among its alternatives. Every comparator is read: one this does not know (`>8.2`,
    `!=8.2.5`, a hyphen range, a branch name), or an alternative with no lower bound, makes the answer None, so the
    doctor says the constraint was not compared and never guesses."""
    lowest = None
    for alternative in re.split(r"\|\|?", constraint):
        # `>= 8.2` is one comparator: an operator may be followed by spaces.
        joined = re.sub(r"(\^|~|>=|<=|=|<|>)\s+", r"\1", alternative.strip())
        comparators = [part for part in re.split(r"[\s,]+", joined) if part]
        bound = None
        for comparator in comparators:
            lower = _LOWER_BOUND.fullmatch(comparator)
            if lower:
                if bound is None or compare(lower.group(1), bound) > 0:
                    bound = lower.group(1)
            elif not _UPPER_BOUND.fullmatch(comparator):
                return None
        if bound is None:
            return None
        if lowest is None or compare(bound, lowest) < 0:
            lowest = bound
    return lowest


# The lock file each package manager writes: what a project uses, whatever the machine has installed.
LOCK_FILES = (("pnpm-lock.yaml", "pnpm"), ("package-lock.json", "npm"), ("npm-shrinkwrap.json", "npm"),
              ("yarn.lock", "yarn"), ("bun.lock", "bun"), ("bun.lockb", "bun"))


def _doctor_package_manager(app_root: Path, pins: list, add_check) -> None:
    """`constraint:package-manager`: the package manager the project itself names (`packageManager` in its
    package.json, and the lock files it holds) beside the `package-manager` pin. The check reports the first of
    the pin's commands that is installed, so a pin whose first command is not the project's manager makes it
    report the wrong one on a machine that has both: that is `unexpected`, as is a project that names more than
    one. No pin of that name, or nothing in the project that names a manager, is no check."""
    pin = next((pin for pin in pins if pin["name"] == "package-manager"), None)
    if pin is None:
        return
    named: dict[str, list[str]] = {}
    try:
        data = json.loads((app_root / "package.json").read_bytes().decode("utf-8"))
    except (OSError, ValueError, RecursionError):
        data = None   # `constraint:node` says what is wrong with the manifest; the lock files are still read
    field = data.get("packageManager") if isinstance(data, dict) else None
    if isinstance(field, str) and re.fullmatch(r"[a-z][a-z0-9-]*(@.*)?", field.strip()):
        named.setdefault(field.strip().split("@", 1)[0], []).append("packageManager in package.json")
    for lock, manager in LOCK_FILES:
        if (app_root / lock).is_file():
            named.setdefault(manager, []).append(lock)
    if not named:
        return
    check = "constraint:package-manager"
    shown = ", ".join(f"{manager} ({', '.join(sources)})" for manager, sources in named.items())
    if len(named) > 1:
        add_check(check, "unexpected", f"the project names more than one package manager: {shown}; keep one")
        return
    (manager,) = named
    commands = [entry["command"] for entry in pin["commands"]]
    if commands[0] == manager:
        add_check(check, "ok", f"the project uses {shown}, the pin's first command")
    elif manager in commands:
        add_check(check, "unexpected",
                  f"the project uses {shown} and the pin prefers {commands[0]}, which the check reports where both "
                  f"are installed: put {manager} first in the package-manager pin's commands")
    else:
        add_check(check, "unexpected",
                  f"the project uses {shown} and the package-manager pin names only {', '.join(commands)}: add "
                  f"{manager} as the pin's first command")


def _doctor_web_constraints(app_root: Path, pins: list, module, add_check) -> None:
    """`constraint:php` and `constraint:node`: the project's own runtime constraint beside the pin of that name. A
    pin that accepts a version the project's manifest refuses is `unexpected`; a manifest that cannot be used is
    `unexpected` with the reason; a constraint of a form this does not read is `ok`, said to be not compared."""
    for name, manifest, section, key in WEB_CONSTRAINTS:
        pin = next((pin for pin in pins if pin["name"] == name), None)
        path = app_root / manifest
        if pin is None or not path.is_file():
            continue
        check = f"constraint:{name}"
        try:
            data = json.loads(path.read_bytes().decode("utf-8"))
        except OSError as exc:
            add_check(check, "unexpected", f"{manifest} cannot be read ({exc.strerror or exc}), so it was not compared")
            continue
        except (ValueError, RecursionError) as exc:  # not UTF-8 (UnicodeDecodeError) or not JSON
            add_check(check, "unexpected", f"{manifest} is not JSON in UTF-8 ({exc}), so it was not compared")
            continue
        if not isinstance(data, dict):
            add_check(check, "unexpected", f"{manifest} is not a JSON object, so it was not compared")
            continue
        if section not in data:
            continue
        if not isinstance(data[section], dict):
            add_check(check, "unexpected", f"{manifest}: {section} is not an object, so it was not compared")
            continue
        if key not in data[section]:
            continue
        constraint = data[section][key]
        if not isinstance(constraint, str) or not constraint.strip():
            add_check(check, "unexpected", f"{manifest}: {section}.{key} is not a version constraint as text")
            continue
        accepted = pin["commands"][0]["min_version"]
        for entry in pin["commands"][1:]:
            if module.compare_versions(entry["min_version"], accepted) < 0:
                accepted = entry["min_version"]
        lowest = _lowest_allowed(constraint, module.compare_versions)
        if lowest is None:
            add_check(check, "ok", f"{manifest} requires {name} {constraint!r}, a form the doctor does not compare "
                                   f"with the pin's minimum {accepted}")
        elif module.compare_versions(accepted, lowest) < 0:
            add_check(check, "unexpected", f"{manifest} requires {name} {constraint} and the pin accepts {accepted}: "
                                           f"raise min_version of the {name} pin to {lowest}")
        else:
            add_check(check, "ok", f"{manifest} requires {name} {constraint}; the pin's minimum is {accepted}")


MCP_BRIDGE = "scripts/lsp-mcp-bridge.py"
MCP_BRIDGE_DOC = "docs/language-servers.md"


def _doctor_mcp_bridge(target_root: Path, add_check) -> None:
    """`mcp-bridge`: whether the project's `.mcp.json` registers the lsp kit's MCP bridge. Files only. It is
    `ok` with the entry's name when one of its servers names the bridge's script, `unexpected` when the file is
    not JSON, and `optional` otherwise, never `setup_required`: the bridge is for Codex and Antigravity, whose
    registration is in the user's own configuration, which this does not read, and a project's `.mcp.json` is
    Claude Code's, which has the plugin."""
    where = f"how to register it for each agent: {MCP_BRIDGE_DOC}"
    path = target_root / ".mcp.json"
    if not path.is_file():
        add_check("mcp-bridge", "optional", f"no .mcp.json; {where}")
        return
    try:
        servers = json.loads(path.read_bytes().decode("utf-8")).get("mcpServers")
    except (OSError, ValueError, AttributeError, RecursionError) as exc:
        add_check("mcp-bridge", "unexpected", f".mcp.json cannot be read as JSON ({type(exc).__name__}); {where}")
        return
    for name, server in (servers.items() if isinstance(servers, dict) else ()):
        arguments = server.get("args") if isinstance(server, dict) else None
        named = [server.get("command"), *arguments] if isinstance(arguments, list) else []
        if any(isinstance(item, str) and item.replace("\\", "/").endswith(MCP_BRIDGE) for item in named):
            add_check("mcp-bridge", "ok", f".mcp.json registers it as {name}")
            return
    add_check("mcp-bridge", "optional", f".mcp.json does not register it; {where}")


def _doctor_lsp(target_root: Path, add_check) -> None:
    """The lsp kit's checks: each file the kit installs is present, the server table loads, and each server it
    names is installed."""
    _kit_file_checks("lsp", target_root, add_check)
    table = _lsp_table_module()
    try:
        servers = table.load_servers(target_root)
    except table.TableError as exc:
        add_check("server-table", "missing", str(exc))
        return
    if not servers:
        add_check("server-table", "ok", f"{LSP_TABLE} holds no server yet: add a stack's with "
                                        "python scripts/lsp-servers.py add <preset>")
    else:
        add_check("server-table", "ok", f"{LSP_TABLE}: {', '.join(server['name'] for server in servers)}")
    for server in servers:
        found = table.find_program(target_root, server)  # the kit's own lookup: PATH, or the server's folder
        add_check(f"server:{server['name']}", "ok" if found else "setup_required", found or server["install"])
    _doctor_mcp_bridge(target_root, add_check)
    # The Claude Code plugin is generated from the table: in step with it, behind it, or never generated.
    plugin = _lsp_plugin_module()
    state = plugin.state(target_root, servers)
    if state == "current":
        add_check("claude-plugin", "ok", f"{plugin.FOLDER}: {', '.join(s['name'] for s in servers) or 'no server'}")
    elif state == "differs":
        add_check("claude-plugin", "unexpected", f"{plugin.FOLDER} is not what {LSP_TABLE} gives now: "
                                                  f"regenerate it with {plugin.COMMAND}")
    else:
        # Asked for only where Claude Code is used and there is a server to run.
        wanted = (target_root / ".claude").is_dir() and bool(servers)
        add_check("claude-plugin", "setup_required" if wanted else "optional",
                  f"not generated: {plugin.COMMAND} (Claude Code then runs the table's servers while it edits)")


def _doctor_launchers(target_root: Path, add_check) -> None:
    """The launchers kit's checks, from files only. `profile`: the project's `.conclave/launchers.json`, which the
    kit installs and the shortcut script reads, held to the kit's own loader (`scripts/lib/launchers.py`): `ok` with
    the title, `setup_required` with the loader's refusal (a fresh install's unset title among them) or with the
    install command when there is no file. `renderer`: `scripts/campaign-icon.py`, which draws every link's icon
    (D07 T01 section 3). `links`, with a readable profile: how many links the shortcut script writes from it, one
    per agent and one per declared entry."""
    renderer = target_root / LAUNCHERS_RENDERER
    add_check("renderer", "ok" if renderer.is_file() and not _is_link(renderer) else "setup_required",
              renderer.as_posix() if renderer.is_file() and not _is_link(renderer) else
              f"no {LAUNCHERS_RENDERER}: install the kit with python forge.py kit {target_root.as_posix()} launchers")
    profile = target_root / LAUNCHERS_PROFILE
    if not profile.exists():
        add_check("profile", "setup_required",
                  f"no {LAUNCHERS_PROFILE}: install the kit with python forge.py kit {target_root.as_posix()} launchers")
        return
    loader = _toolchain_module("launchers", "lib/launchers.py")
    try:
        loaded = loader.load_profile(profile, target_root)
    except loader.ProfileError as exc:
        add_check("profile", "setup_required", str(exc))
        return
    add_check("profile", "ok", f"{LAUNCHERS_PROFILE}: {loaded['title']}")
    agents, declared = len(loaded["agents"]), len(loaded["links"])
    add_check("links", "ok", f"{agents + declared} links: {agents} agent, {declared} declared (D07 T01 section 6)")


def doctor_repo(target_root: Path, kit_name: str | None = None) -> dict:
    """Read-only stack health check for Laravel and/or WordPress overlays across all three agents."""
    target_root = Path(target_root).resolve()
    checks: list[dict[str, str]] = []

    def add_check(name: str, status: str, detail: str) -> None:
        checks.append({"name": name, "status": status, "detail": detail})

    # With no kit named the doctor checks the project's stack kit, or base, and then the kits in BARE_DOCTOR_ALSO
    # that are installed. A kit that is named is checked alone.
    also: list[str] = []
    if kit_name is None:
        if _find_laravel_app_root(target_root) is not None:
            kit_name = "laravel"
        elif (target_root / WORDPRESS_PIN).is_file() or _find_wordpress_root(target_root) is not None:
            kit_name = "wordpress"
        else:
            kit_name = "base"
        found = installed_kits(target_root)
        # The Laravel branch runs the lsp kit's checks itself, so they are not listed a second time.
        also = [kit for kit in BARE_DOCTOR_ALSO if kit in found and kit != kit_name
                and not (kit == "lsp" and kit_name == "laravel")]

    if kit_name == "laravel":
        app_root = _find_laravel_app_root(target_root)
        if app_root is not None:
            add_check("artisan", "ok", (app_root / "artisan").as_posix())
        else:
            add_check("artisan", "missing", f"no artisan under {target_root.as_posix()}")
        boost_json = (app_root / "boost.json") if app_root else (target_root / "boost.json")
        add_check("boost.json", "ok" if boost_json.is_file() else "missing", boost_json.as_posix())
        boost_package = _composer_package_installed(app_root, "laravel/boost") if app_root else None
        add_check("laravel/boost", "ok" if boost_package else "setup_required",
                  boost_package.as_posix() if boost_package else "composer require --dev laravel/boost (dependency approval)")
        for agent_dir in (".agents", ".claude", ".codex"):
            sk = target_root / agent_dir / "skills/laravel-boost/SKILL.md"
            add_check(f"skill:{agent_dir}", "ok" if sk.is_file() else "missing", sk.as_posix())
        # The client and the servers are the lsp kit's, which this kit brings: its files, the table, and each
        # server the table names (the `laravel` preset's three on a fresh install).
        _doctor_lsp(target_root, add_check)
    elif kit_name == "wordpress":
        _doctor_wordpress(target_root, add_check)
    elif kit_name == "reviewer":
        _doctor_reviewer(target_root, add_check)
    elif kit_name == "automations":
        _doctor_automations(target_root, add_check)
    elif kit_name == "launchers":
        _doctor_launchers(target_root, add_check)
    elif kit_name == "unattended":
        _doctor_unattended(target_root, add_check)
    elif kit_name == "desktop-tests":
        cfg_path = target_root / DESKTOP_TESTS_CONFIG
        runner = target_root / "scripts/smoke-input.ps1"
        capture = target_root / "scripts/capture-window.ps1"
        guard = target_root / "scripts/lib/DesktopTestGuard.cs"
        desktop_lock = target_root / "scripts/lib/DesktopLock.cs"
        watcher = target_root / "scripts/lib/InputWatch.cs"
        cfg_lib = target_root / "scripts/lib/desktop_tests.py"
        for label, p in (("runner", runner), ("capture", capture), ("guard", guard),
                         ("desktop-lock", desktop_lock), ("watcher", watcher), ("config-lib", cfg_lib)):
            add_check(label, "ok" if p.is_file() else "missing", p.as_posix())
        if not cfg_path.is_file():
            add_check("config", "missing", cfg_path.as_posix())
        else:
            loader = _toolchain_module("desktop-tests", "lib/desktop_tests.py")
            try:
                cfg = loader.load_config(cfg_path, allow_unset=True)
                status = "ok" if cfg.get("prefix") else "setup_required"
                detail = f"prefix={cfg['prefix']}" if cfg.get("prefix") else "prefix: null (set in .conclave/desktop-tests.json)"
                add_check("config", status, detail)
            except loader.ConfigError as exc:
                add_check("config", "error", str(exc))
    elif kit_name == "lsp":
        _doctor_lsp(target_root, add_check)
    elif kit_name in TOOLCHAIN_PINS:
        _doctor_toolchain(target_root, add_check, kit_name)
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

    for kit in also:
        if kit == "lsp":
            _doctor_lsp(target_root, add_check)

    missing_count = sum(1 for c in checks if c["status"] in ("missing", "setup_required", "unexpected", "error"))
    return {
        "target": target_root.as_posix(),
        "kit": kit_name,
        **({"also": also} if also else {}),
        "missing_or_setup_required": missing_count,
        "checks": checks,
    }


TODO_POINTER = (
    "\n## TODO workflow\n\n"
    "Plan and build through the TODO system: [docs/todo-workflow.md](./docs/todo-workflow.md).\n"
)
ENTRY_DOCS = ("AGENTS.md", "GEMINI.md", "CLAUDE.md", "CODEX.md")
# The line under `## Goal` in the base kit's AGENTS.md that `init --goal` replaces (D05 T01 section 3).
GOAL_PLACEHOLDER = ("Not stated yet: replace this line with the project's goal in one sentence (`python forge.py init "
                    "<project> --goal \"<goal>\"` writes it for a new project).")
GOAL_LIMIT = 600   # characters


def _check_line(option: str, noun: str, text: str | None) -> None:
    """Refuse a line `init` would not write (`--goal`, `--acceptance`), before any file is written: empty, longer
    than GOAL_LIMIT, more than one line or holding a control character, or holding a dash the writing rules
    forbid."""
    if text is None:
        return
    if not text.strip():
        raise ValueError(f"{option}: the {noun} is empty")
    if len(text) > GOAL_LIMIT:
        raise ValueError(f"{option}: the {noun} is {len(text)} characters, more than {GOAL_LIMIT}")
    # Every character Python splits lines at, and every other control character (a tab, a form feed), found by
    # the review round: NEL, a vertical tab and a form feed passed a check of four line breaks.
    if text.splitlines() != [text] or any(unicodedata.category(c) in ("Cc", "Zl", "Zp") for c in text):
        raise ValueError(f"{option}: the {noun} is one line, with no line break or control character")
    if "\u2014" in text or "\u2013" in text:
        raise ValueError(f"{option}: the {noun} holds an em or en dash; use a comma, a colon or a full stop")


PLAN_JSON = "todo/plan.json"


def _with_acceptance(data: bytes, acceptance: str) -> bytes:
    """A todo/plan.json's bytes with its `acceptance` key set, written as the kit writes the file: two-space JSON
    with every other key and its order kept, and a final newline."""
    plan = json.loads(data.decode("utf-8"))
    plan["acceptance"] = acceptance.strip()
    return (json.dumps(plan, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _apply_acceptance(target_root: Path, acceptance: str, installed: bool) -> dict:
    """Write the acceptance bar into the project's todo/plan.json when that file is not yet the project's: the one
    this run installed, or one still byte for byte the kit's (what a run that failed before its write leaves).
    Nothing is read or written through a link. Returns the result's `acceptance_applied` and `acceptance_reason`."""
    path = target_root / PLAN_JSON
    if _has_unsafe_parent(target_root, PLAN_JSON) or _is_link(path):
        return {"acceptance_applied": False,
                "acceptance_reason": f"{PLAN_JSON} is reached through a link, so the bar was not written"}
    if not path.is_file():
        return {"acceptance_applied": False, "acceptance_reason": f"this install has no {PLAN_JSON}"}
    kit = (FORGE_ROOT / "kits/todo/templates" / PLAN_JSON).read_bytes()
    current = path.read_bytes()
    if current == _with_acceptance(kit, acceptance):
        return {"acceptance_applied": True, "acceptance_reason": f"{PLAN_JSON} already holds this bar"}
    if current != kit:
        return {"acceptance_applied": False,
                "acceptance_reason": f"{PLAN_JSON} is the project's own, so the bar was not written"}
    atomic_write(path, _with_acceptance(kit, acceptance))
    return {"acceptance_applied": True,
            "acceptance_reason": f"written into the {PLAN_JSON} this run installed" if installed
            else f"written into {PLAN_JSON}, which was still the kit's file"}


def _with_goal(data: bytes, goal: str) -> bytes:
    """An AGENTS.md's bytes with the goal in place of the placeholder line."""
    line = GOAL_PLACEHOLDER.encode("utf-8") + b"\n"
    if data.count(line) != 1:
        raise ValueError("the base kit's AGENTS.md has no goal placeholder line to replace")
    return data.replace(line, goal.strip().encode("utf-8") + b"\n")


def _apply_goal(target_root: Path, goal: str, wrote: str | None) -> dict:
    """Write the goal into the project's AGENTS.md when that file is not yet the project's: one this run wrote
    (`wrote` says how), or one still byte for byte the kit's, with or without the todo kit's pointer, which is
    what a run that failed before its goal was written leaves. A file that is the project's own is left as it is.
    Returns the result's `goal_applied` and `goal_reason`."""
    path = target_root / "AGENTS.md"
    if path.is_symlink() or not path.is_file():
        return {"goal_applied": False, "goal_reason": "this install has no AGENTS.md of its own to write the goal into"}
    kit = (FORGE_ROOT / "kits/base/templates/AGENTS.md").read_bytes()
    pointer = TODO_POINTER.encode("utf-8")
    current = path.read_bytes()
    if current in (_with_goal(kit, goal), _with_goal(kit, goal) + pointer):
        return {"goal_applied": True, "goal_reason": "AGENTS.md already holds this goal"}
    if current not in (kit, kit + pointer):
        return {"goal_applied": False, "goal_reason": "AGENTS.md is the project's own, so the goal was not written "
                                                     "(init --force replaces it, keeping it as AGENTS.md.replaced)"}
    atomic_write(path, _with_goal(current, goal))
    reasons = {"installed": "written into the AGENTS.md this run installed",
               "forced": "written into the AGENTS.md that --force replaced"}
    return {"goal_applied": True,
            "goal_reason": reasons.get(wrote, "written into AGENTS.md, which was still the kit's file")}


def provision(
    target_root: Path,
    *,
    agent: str = "all",
    include_scripts: bool = True,
    with_todo: bool = False,
    kits: list[str] | None = None,
    wordpress_host: str | None = None,
    overwrite_existing_docs: bool = False,
    goal: str | None = None,
    acceptance: str | None = None,
) -> dict:
    """`init`: copy the base kit plus only the kits asked for, never the whole SDK, and never over a file the project
    already has. `with_todo` is shorthand for the `todo` kit; `overwrite_existing_docs` (`init --force`) rewrites only
    the four entry docs. The install record notes what was written and holds no path back to the SDK, so the
    project owns everything init copied. `goal` (`init --goal`) is written under `## Goal` in an AGENTS.md that is
    not yet the project's (`_apply_goal`); one that is the project's own is left as it is, and the result says so.
    `acceptance` (`init --acceptance`, with the todo kit only) is set in todo/plan.json the same way
    (`_apply_acceptance`).
    """
    _check_line("--goal", "goal", goal)   # a goal or a bar init would not write refuses before anything is
    _check_line("--acceptance", "bar", acceptance)
    agent = normalize_agent(agent)
    raw_target = Path(target_root)
    if _is_link(raw_target):
        raise ValueError(f"Target must be a folder, or a path that does not exist yet: {raw_target}")
    target_root = raw_target.resolve()
    # Checked on the resolved path, which is the one written to, so no link (dangling or retargeted before this run)
    # can lead into git's own data, or lead init over the kits' own source.
    if any(os.path.normcase(part) == ".git" for part in target_root.parts):
        raise ValueError(f"Target is inside a .git folder: {target_root}")
    if os.path.normcase(str(target_root)) == os.path.normcase(str(FORGE_ROOT)):
        raise ValueError(f"Target is the Conclave-SDK source folder itself (use self-sync): {target_root}")
    if target_root.exists() and (not target_root.is_dir() or _is_link(target_root)):
        raise ValueError(f"Target must be a folder, or a path that does not exist yet: {target_root}")

    chosen = ["base", *(["todo"] if with_todo else []), *(kits or [])]
    chosen += [BROUGHT_KITS[k] for k in chosen if k in BROUGHT_KITS]   # planned and preflighted with the rest
    selected = [k for k in KIT_ORDER if k in chosen] + [k for k in dict.fromkeys(chosen) if k not in KIT_ORDER]
    if acceptance is not None and "todo" not in selected:
        raise ValueError("--acceptance: the bar is written into the todo kit's plan; add --kit todo")

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
    def finished(doc: str) -> bytes:
        """What --force leaves in a doc: the kit's bytes, and in AGENTS.md the goal and the TODO pointer."""
        data = (base_templates / doc).read_bytes()
        if doc != "AGENTS.md":
            return data
        return (_with_goal(data, goal) if goal is not None else data) + pointer

    docs = {doc: ((base_templates / doc).read_bytes(), finished(doc))
            for doc in ENTRY_DOCS if overwrite_existing_docs and _rel_allowed_for_agent(doc, agent)
            and not (target_root / doc).is_symlink()}
    def staged(doc: str) -> tuple[bytes, ...]:
        """What a --force run leaves in a doc it replaced before it wrote the goal (the kit's bytes, in AGENTS.md
        with the TODO pointer or without): the kit's, not the project's, so it is neither refused nor backed up."""
        data = (base_templates / doc).read_bytes()
        return (data, data + TODO_POINTER.encode("utf-8")) if doc == "AGENTS.md" and goal is not None else ()

    for doc, (_kit_bytes, final) in docs.items():
        _check_backup(target_root, doc, final, staged(doc))

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
            # A doc still holding the kit's bytes is what a run that failed before its goal left: the project's
            # original is already in the backup, which is never written over with the kit's text.
            if current is not None and current not in staged(doc) and not (backup.is_file() and backup.read_bytes() == current):
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
    result = {
        "target": target_root.as_posix(),
        "agent": agent,
        "written": written,
        "skipped": skipped,
        "backups": backups,
        "kits": kit_results,
    }
    if goal is not None:
        wrote = "forced" if "AGENTS.md" in forced else "installed" if "AGENTS.md" in kit_results[0]["installed"] else None
        result.update(_apply_goal(target_root, goal, wrote))
    if acceptance is not None:
        todo_result = next(r for name, r in zip(selected, kit_results) if name == "todo")
        result.update(_apply_acceptance(target_root, acceptance, PLAN_JSON in todo_result["installed"]))
    return result


REPLACED = ".replaced"


def _check_backup(target_root: Path, doc: str, final: bytes, staged: tuple[bytes, ...] = ()) -> None:
    """Refuse `init --force` before any file is written when the doc it would replace cannot be kept: its
    `<doc>.replaced` is a link, a folder, or a file holding other bytes (the only copy of an earlier version). A
    backup holding the doc's own bytes is the one an interrupted run made, so the run may go on, and so may a doc
    that holds what an interrupted run leaves in it (`staged`: the kit's bytes, before the goal was written)."""
    path = target_root / doc
    if path.exists() and not path.is_file():
        raise ValueError(f"{doc} is not a file; refusing to replace it")
    current = path.read_bytes() if path.is_file() else None
    if current is None or current == final or current in staged:
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
        # Folders first: an empty one for an unknown agent holds no file for the walk below to refuse.
        for child in (sorted(patches_root.iterdir()) if patches_root.is_dir() else []):
            if child.is_dir() and child.name not in SKILL_COPY_AGENTS:
                raise SkillCopyError(f"{child.relative_to(root).as_posix()}: a patch folder is "
                                     f"{SKILL_PATCHES}/agents or {SKILL_PATCHES}/codex")
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
    _unittest_suite("kit-base", "kits/base/templates/scripts/tests", 600),
    _unittest_suite("kit-automations", "kits/automations/templates/scripts/tests", 1800),
    _unittest_suite("kit-reviewer", "kits/reviewer/templates/scripts/tests", 1800),
    _unittest_suite("kit-launchers", "kits/launchers/templates/scripts/tests", 600),
    _unittest_suite("kit-unattended", "kits/unattended/templates/scripts/tests", 1800),
    _unittest_suite("kit-desktop-tests", "kits/desktop-tests/templates/scripts/tests", 600),
    _unittest_suite("kit-wordpress", "kits/wordpress/templates/scripts/tests", 1800),
    _unittest_suite("kit-wordpress-pressable", "kits/wordpress/hosts/pressable/templates/scripts/tests", 1800),
    _unittest_suite("kit-lsp", "kits/lsp/templates/scripts/tests", 600),
    _unittest_suite("kit-toolchain-cpp", "kits/toolchain-cpp/templates/scripts/tests", 600),
    _unittest_suite("kit-toolchain-web", "kits/toolchain-web/templates/scripts/tests", 600),
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
    # A suite run inside another (a test that runs a kit's suite) keeps the outer suite's tag too, so ending the outer
    # suite ends this one, whatever session it is in.
    outer = [t for t in env.get(OUTER_TAGS, "").split(",") + [env.get("CONCLAVE_CHECK_ALL_TAG", "")] if t]
    suite_env = {**env, "CONCLAVE_CHECK_ALL_TAG": tag, **({OUTER_TAGS: ",".join(outer)} if outer else {})}
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


# A shard of a unittest suite (D01 T02 §10): the named modules loaded with the suite's folder first on the path, as
# `unittest discover -s <folder>` loads them, and run by the same runner, so it prints the same `Ran N tests` line and
# exits non-zero on any failure or error (an import error included).
SHARD_RUNNER = """import sys, unittest
folder, names = sys.argv[1], sys.argv[2:]
sys.path.insert(0, folder)
suite = unittest.defaultTestLoader.loadTestsFromNames(names)
result = unittest.TextTestRunner().run(suite)
sys.exit(0 if result.wasSuccessful() else 1)
"""


def parse_shard(text: str) -> tuple[int, int]:
    """`K/N` as (K, N), 1 <= K <= N; anything else is a ValueError naming the form."""
    match = re.fullmatch(r"([1-9][0-9]*)/([1-9][0-9]*)", text or "")
    if not match or int(match[1]) > int(match[2]):
        raise ValueError(f"--shard takes K/N with 1 <= K <= N, not {text!r}")
    return int(match[1]), int(match[2])


def shard_weights(folder: Path, system: str | None = None) -> dict[str, float]:
    """Each test file's weight for `shard_modules`: the seconds `<folder>/shard-seconds.json` measured for it on this
    system (`seconds_posix` or `seconds_nt`, by `os.name`), else in its shared `seconds` (`{"seconds": {"test_x":
    12}}`), a file the table does not list taking the listed files' mean; without that file, or one that is
    unreadable, each file's size, as before (a byte count is no runtime: one 17-minute test held one Windows runner
    for 38 minutes while its partner took 7, 2026-11-20; and Windows' times left Linux's first shard 18 seconds long
    while its second took 14 minutes, the shortcut tests being Windows's)."""
    files = sorted(folder.glob("test*.py"))
    try:
        table = json.loads((folder / "shard-seconds.json").read_text(encoding="utf-8"))
        listed = table.get(f"seconds_{system or os.name}") or table["seconds"]
        listed = {str(k): float(v) for k, v in listed.items() if float(v) >= 0}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        listed = {}
    if not listed:
        return {f.stem: float(f.stat().st_size) for f in files}
    mean = sum(listed.values()) / len(listed)
    return {f.stem: listed.get(f.stem, mean) for f in files}


def shard_modules(folder: Path, k: int, n: int, system: str | None = None) -> list[str]:
    """The module names of shard `k` of `n` of the test files (`test*.py`) in a suite's folder: the files assigned
    heaviest first (`shard_weights`) to the lightest shard, so the shards take about the same time,
    deterministically (equal weights go by name). Every file is in exactly one shard."""
    weights = shard_weights(folder, system)
    loads = [0.0] * n
    shards: list[list[str]] = [[] for _ in range(n)]
    for stem in sorted(weights, key=lambda s: (-weights[s], s)):
        lightest = min(range(n), key=lambda i: (loads[i], i))
        shards[lightest].append(stem)
        loads[lightest] += weights[stem]
    return sorted(shards[k - 1])


def check_all(full: bool = False, only=(), skip=(), suites: list[dict] | None = None, root: Path | None = None,
              on_result=None, excluded: dict[str, str] | None = None, shard: tuple[int, int] | None = None) -> list[dict]:
    """Run every suite (those named by `only`, less those named by `skip`), each to its end whatever the one before
    did, and return each one's result. Before any suite runs, validates that every test file in `root` is owned by
    the full suite table or explicitly listed with a reason in `excluded`, raising `UnownedTestsError` otherwise.
    A suite this host cannot run is returned as skipped, neither passed nor failed. An unknown name raises ValueError
    before any suite starts. `full` sets CONCLAVE_FULL_TESTS=1 for the suites; otherwise it is removed, whatever this
    process's own environment holds. With `shard` (K, N), each unittest suite runs only its shard K of N
    (`shard_modules`), a shard holding no test file of a suite is returned as skipped, and a suite of another kind
    runs whole in shard 1 only."""
    table = SUITES if suites is None else suites
    target_root = FORGE_ROOT if root is None else root
    excluded_map = EXCLUDED_TESTS if excluded is None else excluded
    names = [suite["name"] for suite in table]
    unknown = [name for name in (*only, *skip) if name not in names]
    if unknown:
        raise ValueError(f"unknown suite {', '.join(unknown)} (the suites are: {', '.join(names)})")
    problems = _inventory_problems(target_root, table, excluded_map)
    if shard is not None:
        # Every test file of a sharded suite must fall in one of its shards, or no CI job would run it.
        for suite in table:
            if suite["kind"] == "unittest":
                folder = Path(target_root) / suite["path"]
                covered = {m for k in range(1, shard[1] + 1) for m in shard_modules(folder, k, shard[1])}
                problems += [f"{suite['path']}/{f.name}: left out of every shard of {suite['name']}"
                             for f in sorted(folder.glob("test*.py")) if f.stem not in covered]
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
        if shard is not None:
            k, n = shard
            if suite["kind"] != "unittest":
                if k != 1:
                    continue
            else:
                modules = shard_modules(Path(target_root) / suite["path"], k, n)
                if not modules:
                    results.append({"name": suite["name"], "passed": False, "skipped": True, "exit": None,
                                    "tests": None, "reason": f"shard {k}/{n} holds no test file of this suite",
                                    "tail": "", "seconds": 0.0, "modules": []})
                    if on_result:
                        on_result(results[-1])
                    continue
                suite = {**suite, "argv": [sys.executable, "-B", "-c", SHARD_RUNNER, suite["path"], *modules]}
        if _runs_here(suite):
            results.append(_run_suite(suite, env, target_root))
            if shard is not None and suite["kind"] == "unittest":
                results[-1]["modules"] = suite["argv"][5:]
        else:  # never counted as passed, and always shown
            results.append({"name": suite["name"], "passed": False, "skipped": True, "exit": None, "tests": None,
                            "reason": "runs on POSIX only; CI's Linux job runs it", "tail": "", "seconds": 0.0})
        if on_result:
            on_result(results[-1])
    return results


def _print_encodable(text: str) -> None:
    """Print a suite's output whatever stdout can hold: a character its encoding lacks is written as an escape.
    A redirected stdout on Windows is cp1252, and a failed suite's tail (any bytes, decoded with replacement) must
    never be lost to an encoding error: on 2026-11-15 one ended check-all before it showed which test failed."""
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    print(text.encode(encoding, errors="backslashreplace").decode(encoding, errors="replace"), flush=True)


def _suite_line(result: dict) -> str:
    tests = "" if result["tests"] is None else f"  {result['tests']} tests"
    reason = "" if result["passed"] else f"  ({result['reason']})"
    word = "SKIP" if result["skipped"] else "PASS" if result["passed"] else "FAIL"
    return f"{word}  {result['name']}  {result['seconds']:.1f}s{tests}{reason}"


class _WholeWordFormatter(argparse.RawDescriptionHelpFormatter):
    """Help text wrapped at spaces only: argparse's own wrapper also breaks at a hyphen, which split a kit name such
    as `toolchain-cpp` over two lines once the kit list grew (CI red on 2026-11-17 at c24fcdf)."""

    def _split_lines(self, text, width):
        return textwrap.wrap(" ".join(text.split()), width, break_on_hyphens=False, break_long_words=False)


class _Parser(argparse.ArgumentParser):
    """forge.py's parser and each of its subcommands', all with the whole-word help formatter."""

    def __init__(self, *args, formatter_class=_WholeWordFormatter, **kwargs):
        super().__init__(*args, formatter_class=formatter_class, **kwargs)


def main(argv: list[str] | None = None) -> int:
    parser = _Parser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Install the base kit plus only the kits named with --kit")
    p_init.add_argument("target", help="Target repository path")
    p_init.add_argument("--agent", choices=AGENT_CHOICES, default="all")
    p_init.add_argument("--kit", action="append", default=[], help="Additive overlay kit to apply (base, todo, reviewer, automations, launchers, unattended, desktop-tests, lsp, "
                             "toolchain-cpp, toolchain-web, laravel, wordpress)")
    p_init.add_argument("--wp-host", choices=WORDPRESS_HOSTS, default=None, help="WordPress kit only: the site's host (default: the pin's, else pressable)")
    p_init.add_argument("--no-scripts", action="store_true", help="Leave out the kits' scripts/ files")
    p_init.add_argument("--with-todo", action="store_true", help="Shorthand for --kit todo")
    p_init.add_argument("--goal", default=None,
                        help="The project's goal in one sentence, written under ## Goal in the AGENTS.md init installs "
                             "(at most 600 characters, one line)")
    p_init.add_argument("--acceptance", default=None,
                        help="The plan's acceptance bar, set in the todo/plan.json init installs (needs --kit todo; at "
                             "most 600 characters, one line)")
    p_init.add_argument("--force", action="store_true",
                        help="Replace AGENTS.md, GEMINI.md, CLAUDE.md and CODEX.md with the kit's, keeping each replaced one as <name>.replaced")

    p_kit = sub.add_parser("kit", help="Apply an additive overlay kit (base, todo, reviewer, automations, launchers, "
                                          "unattended, desktop-tests, lsp, toolchain-cpp, toolchain-web, laravel, wordpress) "
                                          "to a target repo")
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
    p_drift.add_argument("--projects", default=None, help=f"The project list (default: the SDK's {LOCAL} and {OVERLAY})")

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
    p_all.add_argument("--shard", metavar="K/N", help="Run shard K of N of each unittest suite's test files (CI's parallel jobs)")

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
        try:
            shard = parse_shard(args.shard) if args.shard is not None else None
        except ValueError as exc:
            print(f"forge.py: error: {exc}", file=sys.stderr)
            return 2

        def show(result):
            if "modules" in result:
                print(f"shard {args.shard} of {result['name']}: {', '.join(result['modules']) or 'no test file'}",
                      flush=True)
            print(_suite_line(result), flush=True)
        results = check_all(full=args.full, only=args.only, skip=args.skip, on_result=show, shard=shard)
        skipped = [result for result in results if result["skipped"]]
        failed = [result for result in results if not result["passed"] and not result["skipped"]]
        for result in failed:
            _print_encodable(f"\n--- {result['name']}: {result['reason']}; the end of its output ---\n"
                             f"{result['tail']}")
        ran = len(results) - len(skipped)
        print(f"\ncheck-all: {ran - len(failed)} of {ran} suites passed"
              + (f", {len(skipped)} not run on this host" if skipped else ""))
        return 1 if failed else 0

    if args.command == "drift":
        projects = load_projects(Path(args.projects)) if args.projects else load_projects(root=FORGE_ROOT)
        lines, drifted = drift_lines(drift_report(projects))
        print("\n".join(lines))
        # Exit 3 is the report: the automations runner emails a non-zero exit with the tail of this output.
        return 3 if drifted else 0

    target = Path(args.target)

    if args.command == "kit":
        res = apply_kit(target, args.kit_name, agent=args.agent, dry_run=args.dry_run, host=args.host)
        print(json.dumps(res, indent=2))
        return 1 if _lsp_write_failed(res) else 0

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
            goal=args.goal,
            acceptance=args.acceptance,
        )
        print(json.dumps(res, indent=2))
        return 1 if any(_lsp_write_failed(kit) for kit in res.get("kits", [])) else 0

    if args.command == "check":
        res = check_repo(target)
        print(json.dumps(res, indent=2))
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
