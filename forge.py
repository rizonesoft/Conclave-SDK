#!/usr/bin/env python3
"""AgentForge CLI: provision, synchronize, and audit isolated agent customizations across repositories.

    python forge.py init <target> [--mode isolated|hybrid|inherit] [--agent all|agy|claude|codex] [--with-todo] [--force]
    python forge.py sync <target> [--mode isolated|hybrid|inherit] [--agent all|agy|claude|codex] [--include-scripts]
    python forge.py check <target>

Stdlib only. Uses atomic temp-file-then-replace writes. Default mode is 'isolated': each agent gets
its own self-contained, tracked directory (.agents/, .claude/, .codex/) with zero external path coupling.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

FORGE_ROOT = Path(__file__).resolve().parent


def atomic_write(path: Path, data: bytes | str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = data if isinstance(data, bytes) else data.encode("utf-8")
    fd, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(raw)
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
            if target.exists() and not overwrite:
                continue
            atomic_write(target, item.read_bytes())
            written.append(target.as_posix())
    return written


def write_if_allowed(target: Path, content: bytes | str, overwrite: bool) -> bool:
    if target.exists() and not overwrite:
        return False
    atomic_write(target, content)
    return True


def provision(
    target_root: Path,
    *,
    mode: str = "isolated",
    agent: str = "all",
    include_scripts: bool = True,
    with_todo: bool = False,
    overwrite_existing_docs: bool = False,
    overwrite_skills: bool = True,
) -> dict:
    if mode == "copy":
        mode = "isolated"
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

    # 2. Antigravity isolated customizations (.agents/ and GEMINI.md)
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

    # 5. Canonical TODO graph scripts
    if include_scripts:
        for rel_script in ("scripts/todo-graph.py", "scripts/lib/todo_graph.py"):
            dst = target_root / rel_script
            record(
                dst,
                write_if_allowed(
                    dst,
                    (FORGE_ROOT / rel_script).read_bytes(),
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

    return {
        "target": target_root.as_posix(),
        "mode": mode,
        "agent": agent,
        "written": written,
        "skipped": skipped,
    }


def check_repo(target_root: Path) -> dict:
    target_root = Path(target_root).resolve()
    agy_skills = sorted(p.parent.name for p in (target_root / ".agents/skills").glob("*/SKILL.md"))
    claude_skills = sorted(p.parent.name for p in (target_root / ".claude/skills").glob("*/SKILL.md"))
    codex_skills = sorted(p.parent.name for p in (target_root / ".codex/skills").glob("*/SKILL.md"))
    return {
        "target": target_root.as_posix(),
        "has_agents_md": (target_root / "AGENTS.md").is_file(),
        "has_gemini_md": (target_root / "GEMINI.md").is_file(),
        "has_claude_md": (target_root / "CLAUDE.md").is_file(),
        "has_codex_md": (target_root / "CODEX.md").is_file(),
        "has_agy_skills_json": (target_root / ".agents/skills.json").is_file(),
        "has_agy_plugins_json": (target_root / ".agents/plugins.json").is_file(),
        "has_todo_graph": (target_root / "scripts/todo-graph.py").is_file(),
        "agy_skills": agy_skills,
        "claude_skills": claude_skills,
        "codex_skills": codex_skills,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Initialize isolated agent skills, rules, and scripts in a target repo")
    p_init.add_argument("target", help="Target repository path")
    p_init.add_argument("--mode", choices=["isolated", "copy", "hybrid", "inherit"], default="isolated")
    p_init.add_argument("--agent", choices=["all", "agy", "claude", "codex"], default="all")
    p_init.add_argument("--no-scripts", action="store_true", help="Do not copy scripts/todo-graph.py")
    p_init.add_argument("--with-todo", action="store_true", help="Seed starter todo/ directory")
    p_init.add_argument("--force", action="store_true", help="Overwrite existing AGENTS.md, GEMINI.md, CLAUDE.md, CODEX.md")

    p_sync = sub.add_parser("sync", help="Synchronize isolated skills and rules into an existing repo")
    p_sync.add_argument("target", help="Target repository path")
    p_sync.add_argument("--mode", choices=["isolated", "copy", "hybrid", "inherit"], default="isolated")
    p_sync.add_argument("--agent", choices=["all", "agy", "claude", "codex"], default="all")
    p_sync.add_argument("--include-scripts", action="store_true", help="Also update scripts/todo-graph.py")

    p_check = sub.add_parser("check", help="Inspect a target repository's agent setup")
    p_check.add_argument("target", help="Target repository path")

    args = parser.parse_args(argv)
    target = Path(args.target)

    if args.command == "init":
        res = provision(
            target,
            mode=args.mode,
            agent=args.agent,
            include_scripts=not args.no_scripts,
            with_todo=args.with_todo,
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
