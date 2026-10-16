#!/usr/bin/env python3
"""Conclave-SDK CLI: provision, synchronize, and audit isolated agent customizations and stack kits.

    python forge.py init <target> [--mode isolated|hybrid|inherit] [--agent all|agy|gemini|claude|codex] [--kit <kit>] [--with-todo] [--force]
    python forge.py sync <target> [--mode isolated|hybrid|inherit] [--agent all|agy|gemini|claude|codex] [--kit <kit>] [--include-scripts]
    python forge.py kit <target> <kit> [--agent all|agy|gemini|claude|codex] [--host pressable|wpcom] [--dry-run]
    python forge.py doctor <target> [laravel|wordpress] [--strict]
    python forge.py kits
    python forge.py check <target>

Stdlib only. Uses atomic temp-file-then-replace writes. Default mode is 'isolated': each agent gets
its own self-contained, tracked directory (.agents/, .claude/, .codex/) with zero external path coupling.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
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
) -> dict:
    """Apply an additive overlay kit ('base', 'todo', 'laravel', 'wordpress') for all or one agent without overwriting existing files.

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

    # Preflight all planned destinations for symlink-parent traversal before writing any file
    for _src, dst, rel in plan:
        if dst.exists() or dst.is_symlink():
            continue
        if _has_unsafe_parent(target_root, rel):
            raise ValueError(f"Refusing destination with unsafe parent: {rel}")

    for src, dst, rel in plan:
        if dst.exists() or dst.is_symlink():
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

    return {
        "target": target_root.as_posix(),
        "kit": kit_name,
        "agent": agent,
        "dry_run": dry_run,
        "installed": installed,
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
    elif kit_name == "todo":
        for agent_dir in (".agents", ".claude", ".codex"):
            for skill in TODO_SKILLS:
                sk = target_root / agent_dir / "skills" / skill / "SKILL.md"
                add_check(f"skill:{skill}:{agent_dir}", "ok" if sk.is_file() else "missing", sk.as_posix())
        for rel in ("scripts/todo-graph.py", "scripts/lib/todo_graph.py", "todo/README.md", "docs/todo-workflow.md"):
            path = target_root / rel
            add_check(rel, "ok" if path.is_file() else "missing", path.as_posix())
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
    overwrite_skills: bool = True,
) -> dict:
    if mode == "copy":
        mode = "isolated"
    agent = normalize_agent(agent)
    target_root = Path(target_root).resolve()
    target_root.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    skipped: list[str] = []

    def record(path: Path, did_write: bool) -> None:
        rel = path.relative_to(target_root).as_posix()
        (written if did_write else skipped).append(rel)

    do_agy = agent in ("all", "agy")
    do_claude = agent in ("all", "claude")
    do_codex = agent in ("all", "codex")

    # 1. Shared AGENTS.md (never overwrite unless overwrite_existing_docs is True)
    agents_md = target_root / "AGENTS.md"
    record(
        agents_md,
        write_if_allowed(
            agents_md,
            (FORGE_ROOT / "rules/AGENTS.template.md").read_bytes(),
            overwrite_existing_docs,
        ),
    )

    # 2. Antigravity / Gemini isolated customizations (.agents/ and GEMINI.md)
    if do_agy:
        gemini_md = target_root / "GEMINI.md"
        record(
            gemini_md,
            write_if_allowed(
                gemini_md,
                (FORGE_ROOT / "rules/GEMINI.template.md").read_bytes(),
                overwrite_existing_docs,
            ),
        )
        agy_rule = target_root / ".agents/rules/agy-output-and-safety.md"
        record(
            agy_rule,
            write_if_allowed(
                agy_rule,
                (FORGE_ROOT / "rules/agy-output-and-safety.md").read_bytes(),
                overwrite_skills,
            ),
        )
        if mode in ("isolated", "hybrid"):
            for p in copy_tree_atomic(
                FORGE_ROOT / "skills/agy",
                target_root / ".agents/skills",
                overwrite=overwrite_skills,
            ):
                written.append(Path(p).relative_to(target_root).as_posix())
        if mode == "isolated":
            for stale_json in (target_root / ".agents/skills.json", target_root / ".agents/plugins.json"):
                if stale_json.is_file():
                    stale_json.unlink()
        if mode in ("hybrid", "inherit"):
            skills_json = target_root / ".agents/skills.json"
            skills_manifest = {
                "entries": [
                    {"path": (FORGE_ROOT / "skills/agy").as_posix()}
                ]
            }
            record(
                skills_json,
                write_if_allowed(
                    skills_json,
                    json.dumps(skills_manifest, indent=2) + "\n",
                    overwrite_skills,
                ),
            )
        if mode == "inherit":
            plugins_json = target_root / ".agents/plugins.json"
            plugins_manifest = {
                "entries": [
                    {"path": (FORGE_ROOT / "plugins").as_posix()}
                ]
            }
            record(
                plugins_json,
                write_if_allowed(
                    plugins_json,
                    json.dumps(plugins_manifest, indent=2) + "\n",
                    overwrite_skills,
                ),
            )

    # 3. Claude Code isolated customizations (.claude/ and CLAUDE.md)
    if do_claude:
        claude_md = target_root / "CLAUDE.md"
        record(
            claude_md,
            write_if_allowed(
                claude_md,
                (FORGE_ROOT / "rules/CLAUDE.template.md").read_bytes(),
                overwrite_existing_docs,
            ),
        )
        claude_rule = target_root / ".claude/rules/claude-output-and-safety.md"
        record(
            claude_rule,
            write_if_allowed(
                claude_rule,
                (FORGE_ROOT / "rules/claude-output-and-safety.md").read_bytes(),
                overwrite_skills,
            ),
        )
        if mode in ("isolated", "hybrid"):
            for p in copy_tree_atomic(
                FORGE_ROOT / "skills/claude",
                target_root / ".claude/skills",
                overwrite=overwrite_skills,
            ):
                written.append(Path(p).relative_to(target_root).as_posix())
            if (FORGE_ROOT / "agents/claude").is_dir():
                for p in copy_tree_atomic(
                    FORGE_ROOT / "agents/claude",
                    target_root / ".claude/agents",
                    overwrite=overwrite_skills,
                ):
                    written.append(Path(p).relative_to(target_root).as_posix())

    # 4. OpenAI Codex isolated customizations (.codex/ and CODEX.md)
    if do_codex:
        codex_md = target_root / "CODEX.md"
        record(
            codex_md,
            write_if_allowed(
                codex_md,
                (FORGE_ROOT / "rules/CODEX.template.md").read_bytes(),
                overwrite_existing_docs,
            ),
        )
        codex_rule = target_root / ".codex/rules/codex-output-and-safety.md"
        record(
            codex_rule,
            write_if_allowed(
                codex_rule,
                (FORGE_ROOT / "rules/codex-output-and-safety.md").read_bytes(),
                overwrite_skills,
            ),
        )
        if mode in ("isolated", "hybrid"):
            for p in copy_tree_atomic(
                FORGE_ROOT / "skills/codex",
                target_root / ".codex/skills",
                overwrite=overwrite_skills,
            ):
                written.append(Path(p).relative_to(target_root).as_posix())

    # 5. Canonical TODO graph and agent-tier verification scripts
    if include_scripts:
        for rel_script in (
            "scripts/todo-graph.py",
            "scripts/lib/todo_graph.py",
            "scripts/verify-agent-tiers.mjs",
        ):
            src_script = FORGE_ROOT / rel_script
            if not src_script.is_file():
                continue
            dst = target_root / rel_script
            record(
                dst,
                write_if_allowed(
                    dst,
                    src_script.read_bytes(),
                    overwrite_skills,
                ),
            )

    # 6. Optional starter todo/ tree
    if with_todo:
        for p in copy_tree_atomic(
            FORGE_ROOT / "templates/todo",
            target_root / "todo",
            overwrite=overwrite_existing_docs,
        ):
            written.append(Path(p).relative_to(target_root).as_posix())

    # 7. Optional additive stack kits
    kit_results: list[dict] = []
    if kits:
        for kit_name in kits:
            kit_res = apply_kit(target_root, kit_name, agent=agent, dry_run=False, host=wordpress_host)
            kit_results.append(kit_res)
            written.extend(kit_res["installed"])
            skipped.extend(kit_res["preserved"])

    res = {
        "target": target_root.as_posix(),
        "mode": mode,
        "agent": agent,
        "written": written,
        "skipped": skipped,
    }
    if kit_results:
        res["kits"] = kit_results
    return res


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
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Initialize isolated agent skills, rules, scripts, and optional stack kits")
    p_init.add_argument("target", help="Target repository path")
    p_init.add_argument("--mode", choices=["isolated", "copy", "hybrid", "inherit"], default="isolated")
    p_init.add_argument("--agent", choices=AGENT_CHOICES, default="all")
    p_init.add_argument("--kit", action="append", default=[], help="Additive overlay kit to apply (base, todo, laravel, wordpress)")
    p_init.add_argument("--wp-host", choices=WORDPRESS_HOSTS, default=None, help="WordPress kit only: the site's host (default: the pin's, else pressable)")
    p_init.add_argument("--no-scripts", action="store_true", help="Do not copy scripts/todo-graph.py or verify-agent-tiers.mjs")
    p_init.add_argument("--with-todo", action="store_true", help="Seed starter todo/ directory")
    p_init.add_argument("--force", action="store_true", help="Overwrite existing AGENTS.md, GEMINI.md, CLAUDE.md, CODEX.md")

    p_sync = sub.add_parser("sync", help="Synchronize isolated skills and rules into an existing repo")
    p_sync.add_argument("target", help="Target repository path")
    p_sync.add_argument("--mode", choices=["isolated", "copy", "hybrid", "inherit"], default="isolated")
    p_sync.add_argument("--agent", choices=AGENT_CHOICES, default="all")
    p_sync.add_argument("--kit", action="append", default=[], help="Additive overlay kit to apply (base, todo, laravel, wordpress)")
    p_sync.add_argument("--wp-host", choices=WORDPRESS_HOSTS, default=None, help="WordPress kit only: the site's host (default: the pin's, else pressable)")
    p_sync.add_argument("--include-scripts", action="store_true", help="Also update scripts/todo-graph.py and verify-agent-tiers.mjs")

    p_kit = sub.add_parser("kit", help="Apply an additive overlay kit (base, todo, laravel, wordpress) to a target repo")
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

    p_check = sub.add_parser("check", help="Inspect a target repository's agent setup")
    p_check.add_argument("target", help="Target repository path")

    args = parser.parse_args(argv)

    if args.command == "kits":
        print(json.dumps({"kits": list_kits()}, indent=2))
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
            overwrite_skills=True,
        )
        print(json.dumps(res, indent=2))
        return 0

    if args.command == "sync":
        res = provision(
            target,
            mode=args.mode,
            agent=args.agent,
            include_scripts=args.include_scripts,
            with_todo=False,
            kits=args.kit,
            wordpress_host=args.wp_host,
            overwrite_existing_docs=False,
            overwrite_skills=True,
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
