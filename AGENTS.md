# AGENTS.md

Shared instructions for agents working in `AgentForge`. Antigravity loads this file alongside `GEMINI.md`; Claude Code loads it through `CLAUDE.md`.

## Purpose

`AgentForge` holds the canonical agent skills, rules, prompts, plugins, templates, and stdlib-only Python tooling (`forge.py` and `scripts/todo-graph.py`) used to bootstrap and synchronize projects under `R:\GitHub`.

## Architecture and Working Rules

- **Zero external dependencies:** All Python scripts (`forge.py`, `scripts/todo-graph.py`, `scripts/lib/todo_graph.py`) use the Python 3 standard library only.
- **Atomic writes:** Every file write in tooling uses a temporary file in the destination directory followed by `os.replace`.
- **Agent isolation:** Antigravity skills live under `skills/agy/` (installed into `.agents/skills/` in target repos) and Claude Code skills live under `skills/claude/` (installed into `.claude/skills/` in target repos). Keep both sets synchronized when workflow semantics change, while respecting each agent's native toolset.
- **Prose formatting:** Write one line per paragraph and list item in Markdown. Never use em dashes or en dashes in authored prose.
- **Output discipline:** Bound command output and run `python -m unittest discover -s tests -v` before committing changes.
