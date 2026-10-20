#!/usr/bin/env python3
"""Conclave-SDK CLI: provision, synchronize, and audit isolated agent customizations and stack kits.

    python forge.py init <target> [--mode isolated|hybrid|inherit] [--agent all|agy|gemini|claude|codex] [--kit <kit>] [--with-todo] [--force]
    python forge.py sync <target> [--mode isolated|hybrid|inherit] [--agent all|agy|gemini|claude|codex] [--kit <kit>] [--include-scripts]
    python forge.py kit <target> <kit> [--agent all|agy|gemini|claude|codex] [--host pressable|wpcom] [--dry-run]
    python forge.py doctor <target> [laravel|wordpress|reviewer|automations|todo|base] [--strict]
    python forge.py kits
    python forge.py check <target>

Stdlib only. Uses atomic temp-file-then-replace writes. Default mode is 'isolated': each agent gets
its own self-contained, tracked directory (.agents/, .claude/, .codex/) with zero external path coupling.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
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


# Which SDK set each kit in a folder up (plan R38), so a reader can tell older or newer kits from partly installed ones.
KIT_STAMP = ".conclave/kits.json"


def kit_digest(kit_name: str) -> str:
    """SHA-256 over every file of a kit's templates and host overlays: each path relative to the kit with "/"
    separators, in that order, and each file's SHA-256 with CRLF read as LF, so a Windows and a Linux checkout of one
    commit give one digest."""
    kit_root = FORGE_ROOT / "kits" / kit_name
    # Bytecode left by running a kit's own tests is not kit content: the installer never copies it either.
    files = sorted(
        (path.relative_to(kit_root).as_posix(), path)
        for top in ("templates", "hosts")
        for path in (kit_root / top).rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    )
    digest = hashlib.sha256()
    for rel, path in files:
        body = hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        digest.update(f"{rel}\0{body}\n".encode("utf-8"))
    return digest.hexdigest()


def sdk_info() -> dict:
    """The commit and commit date of the SDK forge runs from: git's in a checkout, else SDK_COMMIT and SDK_DATE beside
    forge.py (the copy bundled in the VS Code extension), else null."""
    if (FORGE_ROOT / ".git").exists():
        try:
            run = subprocess.run(["git", "-C", str(FORGE_ROOT), "show", "-s", "--format=%H %cI", "HEAD"],
                                 capture_output=True, text=True, timeout=30, check=True)
            commit, date = run.stdout.split()
            return {"commit": commit, "date": date}
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            # A checkout where git cannot run has no known commit: said on stderr, and the stamp records null.
            print(f"forge.py: warning: could not read the SDK commit with git: {exc}", file=sys.stderr)

    def read(name: str) -> str | None:
        try:
            return (FORGE_ROOT / name).read_text(encoding="utf-8").strip() or None
        except OSError:
            return None

    return {"commit": read("SDK_COMMIT"), "date": read("SDK_DATE")}


def sdk_digest() -> dict:
    """`forge.py digest`: the SDK's commit and date and every kit's digest, the one definition the stamp, the VS Code
    extension's recorded digest and its drift test share."""
    return {"sdk": sdk_info(), "kits": {kit: kit_digest(kit) for kit in list_kits()}}


def read_kit_stamp(target_root: Path) -> dict | None:
    try:
        stamp = json.loads((Path(target_root) / KIT_STAMP).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return stamp if isinstance(stamp, dict) and isinstance(stamp.get("kits"), dict) else None


def write_kit_stamp(target_root: Path, kits: list[str]) -> bool:
    """Records kits as set up from this SDK in the folder's .conclave/kits.json, keeping the other kits' entries. Not in
    the SDK folder itself, whose stamp would name a commit it can never be part of, and never through a link."""
    target_root = Path(target_root)
    if not kits or os.path.normcase(str(target_root)) == os.path.normcase(str(FORGE_ROOT)):
        return False
    path = target_root / KIT_STAMP
    if path.is_symlink() or _has_unsafe_parent(target_root, KIT_STAMP):
        return False
    old = read_kit_stamp(target_root)
    entries = {k: v for k, v in (old or {}).get("kits", {}).items() if isinstance(v, dict)}
    sdk = sdk_info()
    for kit in kits:
        entries[kit] = {"digest": kit_digest(kit), "commit": sdk["commit"], "date": sdk["date"]}
    atomic_write(path, json.dumps({"schema_version": 1, "kits": dict(sorted(entries.items()))}, indent=2) + "\n")
    return True


def _has_unsafe_parent(target_root: Path, rel_path: str) -> bool:
    parts = Path(rel_path).parts[:-1]
    current = target_root
    for part in parts:
        current = current / part
        if current.is_symlink() or (current.exists() and not current.is_dir()):
            return True
    return False


def _find_laravel_app_root(target_root: Path) -> Path | None:
    if (target_root / "artisan").is_file():
        return target_root
    if (target_root / "platform/artisan").is_file():
        return target_root / "platform"
    for child in sorted(target_root.iterdir()):
        if child.is_dir() and not child.is_symlink() and (child / "artisan").is_file():
            return child
    return None


def _is_wp_root(candidate: Path) -> bool:
    return (
        (candidate / "wp-load.php").is_file()
        or (candidate / "wp-config.php").is_file()
        or (candidate / "wp-includes/version.php").is_file()
    )


def _find_wordpress_root(target_root: Path) -> Path | None:
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
# The automations kit's runner, alert and installers: kit code that `sync --include-scripts` refreshes, beside the
# project's own tasks.json and README.md in the same folder.
AUTOMATIONS_SCRIPTS = tuple(f"{AUTOMATIONS_DIR}/{name}" for name in ("run.py", "alert.py", "install.ps1", "install.sh"))


KIT_ORDER = ("base", "todo", "reviewer", "automations", "laravel", "wordpress")
BASE_SKILLS = ("authoring-skills", "local-tool-safety")
AGENT_DIRS = (".agents", ".claude", ".codex")
SDK_MANAGED_PREFIXES = tuple(f"{d}/{kind}/" for d in AGENT_DIRS for kind in ("skills", "rules")) + (".claude/agents/",)
SDK_MANAGED_SCRIPT_PREFIXES = ("scripts/", "bin/") + AUTOMATIONS_SCRIPTS


def _is_sdk_managed(rel: str, include_scripts: bool) -> bool:
    """Files `sync` may bring up to date: what the SDK owns, never what the project writes."""
    if rel.startswith(SDK_MANAGED_PREFIXES):
        return True
    return include_scripts and rel.startswith(SDK_MANAGED_SCRIPT_PREFIXES)


def _kit_files_current(target_root: Path, kit_name: str, host: str | None) -> bool:
    """Whether every SDK-managed file of the kit (all agents, scripts included) present in the folder is this SDK's
    file byte for byte: a link, an unsafe parent or a different file means it came from elsewhere."""
    roots = [FORGE_ROOT / "kits" / kit_name / "templates"]
    if host:
        roots.append(FORGE_ROOT / "kits" / kit_name / "hosts" / host / "templates")
    for root in roots:
        for src in root.rglob("*"):
            if not src.is_file():
                continue
            rel = src.relative_to(root).as_posix()
            if not _rel_allowed_for_agent(rel, "all") or not _is_sdk_managed(rel, True):
                continue
            dst = target_root / rel
            if not (dst.exists() or dst.is_symlink()):
                continue
            if dst.is_symlink() or not dst.is_file() or _has_unsafe_parent(target_root, rel):
                return False
            if dst.read_bytes() != src.read_bytes():
                return False
    return True


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


def apply_kit(
    target_root: Path,
    kit_name: str,
    *,
    agent: str = "all",
    dry_run: bool = False,
    host: str | None = None,
    refresh: bool = False,
    refresh_scripts: bool = False,
    include=None,
) -> dict:
    """Apply an additive overlay kit ('base', 'todo', 'reviewer', 'automations', 'laravel', 'wordpress') for all or one agent without overwriting existing files.

    `refresh` (used by `sync`) also brings SDK-managed files that already exist up to date: skills, rules and
    subagents, plus scripts and bin/ helpers when `refresh_scripts` is set. Project files (entry docs, docs/, todo/,
    site pins, config) are never overwritten. `include(rel)` can leave paths out entirely.

    `host` picks the WordPress kit's host overlay (kits/wordpress/hosts/<host>/templates); other kits ignore it. An
    existing site pin decides the host, so re-running the kit can never add another host's files; without a pin the
    default is `pressable`.
    """
    agent = normalize_agent(agent)
    target_root = Path(target_root)
    if not target_root.exists() or not target_root.is_dir() or target_root.is_symlink():
        raise ValueError(f"Target must be an existing non-symlink directory: {target_root}")
    target_root = target_root.resolve()

    available = list_kits()
    if kit_name not in available:
        raise ValueError(f"Unknown kit '{kit_name}'. Available kits: {', '.join(available)}")

    template_root = FORGE_ROOT / "kits" / kit_name / "templates"
    installed: list[str] = []
    preserved: list[str] = []
    merge_needed: list[str] = []
    extra: dict[str, str] = {}

    plan: list[tuple[Path, Path, str]] = []

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
                plan.append((template_root / rel, target_root / rel, rel))
        plan.append((template_root / "boost.json", app_root / "boost.json", boost_rel))
    elif kit_name == "wordpress":
        if host is not None and host not in WORDPRESS_HOSTS:
            raise ValueError(f"Unknown WordPress host '{host}'. Available hosts: {', '.join(WORDPRESS_HOSTS)}")
        if (target_root / WORDPRESS_PIN).exists():
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
        host_root = FORGE_ROOT / "kits" / kit_name / "hosts" / host / "templates"
        for root in (template_root, host_root):
            for src in sorted(root.rglob("*")):
                if src.is_file():
                    rel = src.relative_to(root).as_posix()
                    if _rel_allowed_for_agent(rel, agent):
                        plan.append((src, target_root / rel, rel))
    else:
        for src in sorted(template_root.rglob("*")):
            if src.is_file():
                rel = src.relative_to(template_root).as_posix()
                if _rel_allowed_for_agent(rel, agent):
                    plan.append((src, target_root / rel, rel))

    if include is not None:
        plan = [(src, dst, rel) for src, dst, rel in plan if include(rel)]

    # Preflight all planned destinations for symlink-parent traversal before writing any file
    for _src, dst, rel in plan:
        if dst.exists() or dst.is_symlink():
            continue
        if _has_unsafe_parent(target_root, rel):
            raise ValueError(f"Refusing destination with unsafe parent: {rel}")

    updated: list[str] = []
    for src, dst, rel in plan:
        if dst.exists() or dst.is_symlink():
            refreshable = refresh and _is_sdk_managed(rel, refresh_scripts) and dst.is_file() and not dst.is_symlink()
            # An existing file under a symlinked directory belongs to wherever the link points; never write through it.
            if refreshable and not _has_unsafe_parent(target_root, rel) and dst.read_bytes() != src.read_bytes():
                if not dry_run:
                    atomic_write(dst, src.read_bytes())
                updated.append(rel)
            else:
                preserved.append(rel)
            continue
        if not dry_run:
            atomic_write(dst, src.read_bytes())
        installed.append(rel)

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
            except (OSError, json.JSONDecodeError):
                preserved.append(".mcp.json")
                merge_needed.append(".mcp.json")
        else:
            payload = {"mcpServers": {"laravel-boost": server_cfg}}
            if not dry_run:
                atomic_write(mcp_path, json.dumps(payload, indent=4) + "\n")
            installed.append(".mcp.json")

    # The stamp says which SDK this kit's files came from, so it is written only when every SDK-managed file of the
    # kit in the folder matches this SDK, for every agent and with scripts. Files kept from an earlier install (sync
    # without --include-scripts, sync for one agent, kit over an install) leave that install's entry.
    if not dry_run and _kit_files_current(target_root, kit_name, extra.get("host")):
        write_kit_stamp(target_root, [kit_name])

    return {
        "target": target_root.as_posix(),
        "kit": kit_name,
        "agent": agent,
        "dry_run": dry_run,
        "installed": installed,
        "updated": updated,
        "preserved": preserved,
        "merge_needed": merge_needed,
        **extra,
    }


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

    helpers = ["scripts/lib/wp_site.py", "scripts/lib/site_ssh.py", "scripts/site-access.py", "bin/wp-remote"]
    if host == "pressable":
        helpers += ["scripts/lib/mcp_http.py", "scripts/mcp-headers.py", "scripts/check-mcp.py", "scripts/sftp-item.py",
                    "scripts/create-application-password.py", "bin/ddev", "bin/wp", ".ddev/providers/production.yaml"]
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

    if host == "pressable":
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
        servers = pin.get("mcp", {})
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
            elif server.get("url") != entry.get("url"):
                missing.append(".mcp.json url differs from the pin")
            add_check(f"mcp:{name}", "setup_required" if missing else "ok",
                      f"wordpress-connect step 3: {', '.join(missing)}" if missing else entry["url"])
    elif host == "wpcom":
        ddev_dir = target_root / ".ddev"
        add_check("no-ddev", "unexpected" if ddev_dir.exists() else "ok",
                  "a WordPress.com site has no local DDEV mirror" if ddev_dir.exists() else "WordPress.com: no local mirror")
        add_check("wordpress-mcp", "ok", "the user-scope WordPress.com connector; nothing in .mcp.json")


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
        for name, reviewer in pin["reviewers"].items():
            found = shutil.which(reviewer["cli"])
            add_check(f"reviewer:{name}", "ok" if found else "setup_required",
                      f"{reviewer['model']} via {found}" if found else f"{reviewer['cli']} CLI not installed; this reviewer is skipped")


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


def _stop_hook_wiring(target_root: Path) -> tuple[str, str]:
    """Whether .claude/settings.json runs the campaign guard's Stop hook. The todo kit seeds the file when a project
    has none; a project's own settings file is never overwritten, so there the hook is added by hand."""
    settings = target_root / ".claude/settings.json"
    seed = FORGE_ROOT / "kits/todo/templates/.claude/settings.json"
    hint = f"add the Stop hook from {seed.as_posix()} to {settings.as_posix()}"
    try:
        doc = json.loads(settings.read_text(encoding="utf-8"))
        commands = [h.get("command") for entry in doc.get("hooks", {}).get("Stop", [])
                    for h in entry.get("hooks", [])]
        commands = [c for c in commands if isinstance(c, str)]
    except FileNotFoundError:
        return "setup_required", hint
    except (OSError, ValueError, AttributeError, TypeError) as exc:
        return "setup_required", f"{settings.as_posix()} does not parse as Claude Code settings: {exc}; {hint}"
    if any("campaign_guard.py" in c and "stop-hook" in c for c in commands):
        return "ok", settings.as_posix()
    return "setup_required", hint


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
    elif kit_name == "todo":
        for agent_dir in (".agents", ".claude", ".codex"):
            for skill in TODO_SKILLS:
                sk = target_root / agent_dir / "skills" / skill / "SKILL.md"
                add_check(f"skill:{skill}:{agent_dir}", "ok" if sk.is_file() else "missing", sk.as_posix())
        for rel in ("scripts/todo-graph.py", "scripts/lib/todo_graph.py", "scripts/campaign_guard.py",
                    "todo/README.md", "docs/todo-workflow.md"):
            path = target_root / rel
            add_check(rel, "ok" if path.is_file() else "missing", path.as_posix())
        add_check("stop-hook", *_stop_hook_wiring(target_root))
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
    mode: str = "isolated",
    agent: str = "all",
    include_scripts: bool = True,
    with_todo: bool = False,
    kits: list[str] | None = None,
    wordpress_host: str | None = None,
    overwrite_existing_docs: bool = False,
    refresh: bool = False,
    refresh_scripts: bool = False,
) -> dict:
    """`init` and `sync`: install the base kit plus only the kits asked for, never the whole SDK.

    `with_todo` is shorthand for the `todo` kit. With `refresh` (`sync`), every kit the repository already has is
    included too, and its SDK-managed files are brought up to date (scripts only with `refresh_scripts`). Project
    files are never overwritten; `overwrite_existing_docs` (`init --force`) rewrites only the four entry docs.
    `hybrid` also writes `.agents/skills.json`; `inherit` writes the Antigravity manifests instead of copying its skills.
    """
    if mode == "copy":
        mode = "isolated"
    agent = normalize_agent(agent)
    target_root = Path(target_root).resolve()
    # Checked on the resolved path, which is the one written to, so no link (dangling or retargeted before this run)
    # can lead into git's own data, or lead init over the kits' own source.
    if any(os.path.normcase(part) == ".git" for part in target_root.parts):
        raise ValueError(f"Target is inside a .git folder: {target_root}")
    if not refresh and os.path.normcase(str(target_root)) == os.path.normcase(str(FORGE_ROOT)):
        raise ValueError(f"Target is the Conclave-SDK source folder itself: {target_root}")
    target_root.mkdir(parents=True, exist_ok=True)

    chosen =["base", *(["todo"] if with_todo else []), *(kits or []), *(installed_kits(target_root) if refresh else [])]
    selected = [k for k in KIT_ORDER if k in chosen] + [k for k in dict.fromkeys(chosen) if k not in KIT_ORDER]

    def include(rel: str) -> bool:
        if not include_scripts and rel.startswith("scripts/"):
            return False
        return not (mode == "inherit" and rel.startswith(".agents/skills/"))

    kit_results = [
        apply_kit(target_root, kit_name, agent=agent, host=wordpress_host, refresh=refresh,
                  refresh_scripts=refresh_scripts, include=include)
        for kit_name in selected
    ]

    forced: list[str] = []
    if overwrite_existing_docs:
        base_templates = FORGE_ROOT / "kits/base/templates"
        for doc in ENTRY_DOCS:
            if _rel_allowed_for_agent(doc, agent) and not (target_root / doc).is_symlink():
                atomic_write(target_root / doc, (base_templates / doc).read_bytes())
                forced.append(doc)

    agents_md = target_root / "AGENTS.md"
    fresh_agents = "AGENTS.md" in kit_results[0]["installed"] or "AGENTS.md" in forced
    if "todo" in selected and fresh_agents and agents_md.is_file():
        atomic_write(agents_md, agents_md.read_bytes() + TODO_POINTER.encode("utf-8"))

    if agent in ("all", "agy"):
        for stale_json in (target_root / ".agents/skills.json", target_root / ".agents/plugins.json"):
            if mode == "isolated" and stale_json.is_file():
                stale_json.unlink()
        # The manifests reference the chosen kits' own folders, so they never expose more than was asked for.
        if mode in ("hybrid", "inherit"):
            skill_dirs = [FORGE_ROOT / "kits" / k / "templates/.agents/skills" for k in selected]
            entries = [{"path": d.as_posix()} for d in skill_dirs if d.is_dir()]
            write_if_allowed(target_root / ".agents/skills.json", json.dumps({"entries": entries}, indent=2) + "\n", True)
        if mode == "inherit":
            plugin_dirs = [FORGE_ROOT / "kits" / k / "plugins" for k in selected]
            entries = [{"path": d.as_posix()} for d in plugin_dirs if d.is_dir()]
            write_if_allowed(target_root / ".agents/plugins.json", json.dumps({"entries": entries}, indent=2) + "\n", True)

    written = [rel for r in kit_results for rel in (*r["installed"], *r["updated"])] + forced
    skipped = [rel for r in kit_results for rel in r["preserved"] if rel not in forced]
    return {
        "target": target_root.as_posix(),
        "mode": mode,
        "agent": agent,
        "written": written,
        "skipped": skipped,
        "kits": kit_results,
    }


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
        "has_agy_skills_json": (target_root / ".agents/skills.json").is_file(),
        "has_agy_plugins_json": (target_root / ".agents/plugins.json").is_file(),
        "has_todo_graph": (target_root / "scripts/todo-graph.py").is_file(),
        "has_verify_agent_tiers": (target_root / "scripts/verify-agent-tiers.mjs").is_file(),
        "agy_skills": agy_skills,
        "claude_skills": claude_skills,
        "codex_skills": codex_skills,
        "claude_agents": claude_agents,
        "kit_stamp": read_kit_stamp(target_root),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Install the base kit plus only the kits named with --kit")
    p_init.add_argument("target", help="Target repository path")
    p_init.add_argument("--mode", choices=["isolated", "copy", "hybrid", "inherit"], default="isolated")
    p_init.add_argument("--agent", choices=AGENT_CHOICES, default="all")
    p_init.add_argument("--kit", action="append", default=[], help="Additive overlay kit to apply (base, todo, reviewer, automations, laravel, wordpress)")
    p_init.add_argument("--wp-host", choices=WORDPRESS_HOSTS, default=None, help="WordPress kit only: the site's host (default: the pin's, else pressable)")
    p_init.add_argument("--no-scripts", action="store_true", help="Leave out the kits' scripts/ files")
    p_init.add_argument("--with-todo", action="store_true", help="Shorthand for --kit todo")
    p_init.add_argument("--force", action="store_true", help="Overwrite existing AGENTS.md, GEMINI.md, CLAUDE.md, CODEX.md")

    p_sync = sub.add_parser("sync", help="Update the kits a repo already has (plus any --kit); project files are never overwritten")
    p_sync.add_argument("target", help="Target repository path")
    p_sync.add_argument("--mode", choices=["isolated", "copy", "hybrid", "inherit"], default="isolated")
    p_sync.add_argument("--agent", choices=AGENT_CHOICES, default="all")
    p_sync.add_argument("--kit", action="append", default=[], help="Additive overlay kit to apply (base, todo, reviewer, automations, laravel, wordpress)")
    p_sync.add_argument("--wp-host", choices=WORDPRESS_HOSTS, default=None, help="WordPress kit only: the site's host (default: the pin's, else pressable)")
    p_sync.add_argument("--include-scripts", action="store_true", help="Also update existing scripts/ and bin/ files from the kits")

    p_kit = sub.add_parser("kit", help="Apply an additive overlay kit (base, todo, reviewer, automations, laravel, wordpress) to a target repo")
    p_kit.add_argument("target", help="Target repository path")
    p_kit.add_argument("kit_name", choices=list_kits(), help="Kit name to apply")
    p_kit.add_argument("--agent", choices=AGENT_CHOICES, default="all", help="Install kit files for all agents or one agent")
    p_kit.add_argument("--host", choices=WORDPRESS_HOSTS, default=None, help="WordPress kit only: the site's host (default: the pin's, else pressable)")
    p_kit.add_argument("--dry-run", action="store_true", help="Preview files that would be installed without writing")

    p_doc = sub.add_parser("doctor", help="Run read-only stack and agent overlay health checks on a target repo")
    p_doc.add_argument("target", help="Target repository path")
    p_doc.add_argument("kit_name", nargs="?", choices=list_kits(), default=None, help="Optional kit name (auto-detects if omitted)")
    p_doc.add_argument("--strict", action="store_true", help="Exit 3 if any check is missing or setup_required")

    sub.add_parser("kits", help="List available overlay kits")
    sub.add_parser("digest", help="Print the SDK commit and date and every kit's digest as JSON")

    p_check = sub.add_parser("check", help="Inspect a target repository's agent setup")
    p_check.add_argument("target", help="Target repository path")

    args = parser.parse_args(argv)
    try:
        return _run(args)
    except ValueError as exc:
        # forge's own refusals (bad target, no app root, a pinned host) end like argparse's: one line, exit 2.
        print(f"forge.py: error: {exc}", file=sys.stderr)
        return 2


def _run(args: argparse.Namespace) -> int:
    if args.command == "kits":
        print(json.dumps({"kits": list_kits()}, indent=2))
        return 0
    if args.command == "digest":
        print(json.dumps(sdk_digest(), indent=2))
        return 0

    target = Path(args.target)

    if args.command == "kit":
        res = apply_kit(target, args.kit_name, agent=args.agent, dry_run=args.dry_run, host=args.host)
        print(json.dumps(res, indent=2))
        return 0

    if args.command == "doctor":
        res = doctor_repo(target, args.kit_name)
        print(json.dumps(res, indent=2))
        if args.strict and res["missing_or_setup_required"] > 0:
            return 3
        return 0

    if args.command == "init":
        res = provision(
            target,
            mode=args.mode,
            agent=args.agent,
            include_scripts=not args.no_scripts,
            with_todo=args.with_todo,
            kits=args.kit,
            wordpress_host=args.wp_host,
            overwrite_existing_docs=args.force,
        )
        print(json.dumps(res, indent=2))
        return 0

    if args.command == "sync":
        res = provision(
            target,
            mode=args.mode,
            agent=args.agent,
            kits=args.kit,
            wordpress_host=args.wp_host,
            refresh=True,
            refresh_scripts=args.include_scripts,
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
