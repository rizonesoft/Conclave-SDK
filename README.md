# AgentForge

AgentForge is the central repository for isolated agent skills, rules, prompts, plugins, templates, and the canonical TODO graph tooling (`todo-graph.py`).

It provisions new and existing repositories with strictly isolated, self-contained customizations for all three agents:

- **Google Antigravity (`agy`):** `.agents/skills/`, `.agents/rules/`, and `GEMINI.md`
- **Claude Code (`claude`):** `.claude/skills/`, `.claude/rules/`, and `CLAUDE.md`
- **OpenAI Codex (`codex`):** `.codex/skills/`, `.codex/rules/`, and `CODEX.md`

Each agent reads only its own isolated folder and entrypoint alongside the shared project rules in `AGENTS.md`.

## Repository Layout

| Path | Purpose |
| ---- | ------- |
| `forge.py` / `forge.cmd` | Stdlib-only bootstrapper CLI to initialize, sync, or check target repositories (`isolated` default mode). |
| `skills/agy/` | Isolated Antigravity skills installed into `<target>/.agents/skills/`. |
| `skills/claude/` | Isolated Claude Code skills installed into `<target>/.claude/skills/`. |
| `skills/codex/` | Isolated OpenAI Codex skills installed into `<target>/.codex/skills/`. |
| `rules/` | Shared and per-agent rule templates (`AGENTS.template.md`, `GEMINI.template.md`, `CLAUDE.template.md`, `CODEX.template.md`, and per-agent safety rules). |
| `prompts/` | Reusable prompt templates for independent review rounds, project bootstrapping, and skill isolation. |
| `plugins/todo-workflow/` | Optional Antigravity plugin bundle (`plugin.json`) packaging the TODO workflow skills and rules. |
| `scripts/` | The canonical `todo-graph.py` CLI and `scripts/lib/todo_graph.py` engine (stdlib-only Python). |
| `templates/todo/` | Starter `todo/` tree (`README.md`, `TODO-00-INDEX.md`, `findings.md`, `templates/TODO-template.md`). |
| `tests/` | Unit test suites for `todo_graph.py` and `forge.py`. |

## Quickstart

### 1. Provision a new or existing project (Isolated mode, default)

By default, `forge.py` runs in `isolated` mode: it copies self-contained `.agents/`, `.claude/`, and `.codex/` directories plus `GEMINI.md`, `CLAUDE.md`, `CODEX.md`, and `scripts/todo-graph.py` into the target repository without creating external path links and without overwriting an existing `AGENTS.md`.

```powershell
python R:\GitHub\AgentForge\forge.py init R:\GitHub\MyProject
```

### 2. Sync isolated skills into an existing repo (all agents or one agent)

```powershell
python R:\GitHub\AgentForge\forge.py sync R:\GitHub\MyProject --agent all
python R:\GitHub\AgentForge\forge.py sync R:\GitHub\MyProject --agent agy
python R:\GitHub\AgentForge\forge.py sync R:\GitHub\MyProject --agent codex
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

* **`isolated` (Default):** Copies tracked skills and rules into `.agents/`, `.claude/`, and `.codex/` inside the target repository with zero external path dependencies. Every repository is 100% self-contained and each agent is isolated in its own directory.
* **`hybrid`:** Optional mode that copies isolated skills and also writes `.agents/skills.json` pointing to `R:/GitHub/AgentForge/skills/agy`.
* **`inherit`:** Optional mode that writes `.agents/skills.json` and `.agents/plugins.json` without copying skill Markdown files.

## TODO Workflow Discipline

All eight TODO skills (`add-todo`, `create-todo`, `groom-plan`, `process-todo-section`, `review-todo-section`, `process-todo-file`, `process-phase`, `process-plan`) and `templates/todo/` enforce the canonical AgentForge execution contract:

* **Small, single-responsibility sections:** Multi-subsystem, multi-dialog, or multi-workflow work is split into small, single-responsibility sections rather than coarse umbrella sections.
* **Granular five-part micro-steps:** Every section carries 1 to 30 concrete micro-step items (typically 4 to 15 micro-steps, never a 1-bullet summary stub), ending with `- [ ] Commit: <message>`. Each non-Commit item names: (1) one action, (2) a concrete path/symbol/command in backticks, (3) `Done when:` observable end state in the same bullet, (4) `Cheaper substitute:` on UI and write items, and (5) a source citation when copying behavior.
* **100% complete development plan:** Running `process-plan` from start to finish leaves a 100% complete, shippable product with zero unowned SPEC controls, settings, refusal/error paths, undo/reverse paths, or persistence read-backs, and zero silent scope drops.
* **Logical step commits:** Commits follow logical steps within a section; review fix-loop commits append to the candidate range without amending.
