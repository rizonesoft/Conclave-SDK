# AgentForge

AgentForge is the central repository for agent skills, rules, prompts, plugins, templates, and the canonical TODO graph tooling (`todo-graph.py`).

It provisions both new and existing repositories with isolated customizations for Google Antigravity (`.agents/`, `GEMINI.md`) and Claude Code (`.claude/`, `CLAUDE.md`), backed by one shared rule contract (`AGENTS.md`).

## Repository Layout

| Path | Purpose |
| ---- | ------- |
| `forge.py` / `forge.cmd` | Stdlib-only bootstrapper CLI to initialize, sync, or audit target repositories in `hybrid`, `copy`, or `inherit` mode. |
| `skills/agy/` | Isolated Antigravity skills installed into `.agents/skills/` or inherited via `.agents/skills.json`. |
| `skills/claude/` | Isolated Claude Code skills installed into `.claude/skills/`. |
| `rules/` | Shared and agent-specific rule templates (`AGENTS.template.md`, `GEMINI.template.md`, `CLAUDE.template.md`, `.agents/rules/`). |
| `prompts/` | Reusable prompt templates for independent review rounds, project bootstrapping, and skill isolation. |
| `plugins/todo-workflow/` | Antigravity plugin bundle (`plugin.json`) packaging the TODO workflow skills and rules. |
| `scripts/` | The canonical `todo-graph.py` CLI and `scripts/lib/todo_graph.py` engine (stdlib-only Python). |
| `templates/agy/` | Ready-to-use `skills.json` and `plugins.json` manifests for Antigravity inheritance. |
| `templates/todo/` | Starter `todo/` tree (`README.md`, `TODO-00-INDEX.md`, `findings.md`, `templates/TODO-template.md`). |
| `tests/` | Unit test suites for `todo_graph.py` and `forge.py`. |

## Quickstart

### 1. Provision a new or existing project (Hybrid mode, recommended)

Hybrid mode installs tracked `.agents/skills/`, `.claude/skills/`, `.agents/skills.json`, `GEMINI.md`, `CLAUDE.md`, and `scripts/todo-graph.py` into the target repository without overwriting existing `AGENTS.md` or `todo/` files unless `--force` is passed.

```powershell
python R:\GitHub\AgentForge\forge.py init R:\GitHub\MyProject --mode hybrid
```

### 2. Sync only Antigravity isolated skills into an existing repo

```powershell
python R:\GitHub\AgentForge\forge.py sync R:\GitHub\MyProject --agent agy
```

### 3. Check a target repository's agent setup

```powershell
python R:\GitHub\AgentForge\forge.py check R:\GitHub\MyProject
```

### 4. Run AgentForge's test suites

```powershell
python -m unittest discover -s R:\GitHub\AgentForge\tests -v
```

## Provisioning Modes

* **`hybrid` (Default):** Copies tracked skills into `.agents/skills/` and `.claude/skills/`, writes `.agents/skills.json` so Antigravity can also inherit shared skills from `R:/GitHub/AgentForge/skills/agy`, installs `scripts/todo-graph.py` and `scripts/lib/todo_graph.py`, and creates `GEMINI.md` and `CLAUDE.md` stubs.
* **`copy`:** Copies all selected skills, rules, and scripts into the target repository with no external path references in `.agents/skills.json`.
* **`inherit`:** Writes lightweight `.agents/skills.json` and `.agents/plugins.json` files pointing to `R:/GitHub/AgentForge` so Antigravity loads skills without duplicating skill Markdown files in the target repository.
