# AGENTS.md

Shared instructions for agents working in `AgentForge`. Each agent loads this file alongside its own isolated entrypoint (`GEMINI.md`, `CLAUDE.md`, or `CODEX.md`).

## Purpose

`AgentForge` holds the canonical isolated agent skills (`skills/agy/`, `skills/claude/`, `skills/codex/`), rules, prompts, plugins, templates, and stdlib-only Python tooling (`forge.py` and `scripts/todo-graph.py`) used to bootstrap and synchronize projects under `R:\GitHub`.

## Architecture and Working Rules

- **Zero external dependencies:** All Python scripts (`forge.py`, `scripts/todo-graph.py`, `scripts/lib/todo_graph.py`) use the Python 3 standard library only.
- **Atomic writes:** Every file write in tooling uses a temporary file in the destination directory followed by `os.replace`.
- **Strict agent isolation:** Antigravity skills live in `skills/agy/` (`.agents/` in target repos), Claude Code skills live in `skills/claude/` (`.claude/` in target repos), and OpenAI Codex skills live in `skills/codex/` (`.codex/` in target repos). Default provisioning mode is `isolated` so every target repository is 100% self-contained.
- **Prose formatting:** Write one line per paragraph and list item in Markdown. Never use em dashes or en dashes in authored prose.
- **Output discipline:** Bound command output and run `python -m unittest discover -s tests -v` before committing changes.
