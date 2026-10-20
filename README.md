# Conclave-SDK

Conclave-SDK is the central repository of overlay kits that carry agent skills, rules and subagent definitions (`base`, `todo`, `reviewer`, `automations`, `laravel`, `wordpress`), prompts, plugins, templates, and the canonical TODO graph tooling (`todo-graph.py`).

It is designed to be imported into any **new** or **existing** repository by **Google Antigravity / Gemini (`gemini` / `agy`)**, **Claude Code (`claude`)**, and **OpenAI Codex (`codex`)**:

- **Google Antigravity / Gemini (`gemini` / `agy`):** `.agents/skills/`, `.agents/rules/`, and `GEMINI.md`
- **Claude Code (`claude`):** `.claude/skills/`, `.claude/rules/`, `.claude/agents/`, and `CLAUDE.md`
- **OpenAI Codex (`codex`):** `.codex/skills/` (with `agents/openai.yaml`), `.codex/rules/`, and `CODEX.md`

Each agent reads only its own isolated folder and entrypoint alongside the shared project rules in `AGENTS.md`.

## Repository Layout

| Path | Purpose |
| ---- | ------- |
| `forge.py` / `forge.cmd` | CLI: `init`, `sync`, `kit`, `doctor`, `kits`, `check`. |
| `kits/base/` | Every repo: entry docs, safety skills, subagents, rules, tier check. |
| `kits/todo/` | TODO skills, `todo-graph.py`, starter `todo/` tree, workflow doc. |
| `kits/reviewer/` | Reviewer pin (another model family, one fallback) and dispatcher. |
| `kits/automations/` | Scheduled tasks for Task Scheduler and systemd, with a failure email. |
| `kits/laravel/`, `kits/wordpress/` | Stack kits. |
| `prompts/` | Copy-pasteable prompts to import Conclave-SDK from Gemini, Claude, or Codex. |
| `plugins/` | Standalone agent plugins that belong to no kit (never installed by `forge.py`). |
| `extensions/` | Editor extensions (`vscode/`), never installed by `forge.py`. |
| `todo/`, `design/` | The SDK's own TODO plan and interface design (the VS Code extension). |
| `.agents/`, `.claude/`, `.codex/` | The SDK's own `base`, `todo`, `reviewer`, `automations`. |
| `scripts/`, `.conclave/` | The SDK's own todo, reviewer and automations scripts and pins. |
| `tests/` | Unit test suites for `todo_graph.py`, `forge.py`, and stack overlay kits. |

## Importing into a New or Existing Project (Gemini, Claude, or Codex)

Nothing is installed unless you ask for it: `init` always installs the `base` kit and adds only the kits you name. Run from Windows PowerShell (or pass `/mnt/r/GitHub/Conclave-SDK/forge.py` inside WSL).

### 1. New Project

```powershell
# Base only: AGENTS.md and the entry docs, safety and authoring skills, subagents, rules, verify-agent-tiers.mjs
python R:\GitHub\Conclave-SDK\forge.py init R:\GitHub\MyProject

# Add the TODO system (--with-todo is shorthand for --kit todo), or a stack kit
python R:\GitHub\Conclave-SDK\forge.py init R:\GitHub\MyProject --kit todo
python R:\GitHub\Conclave-SDK\forge.py init R:\GitHub\MyWordPressSite --kit wordpress --wp-host wpcom
python R:\GitHub\Conclave-SDK\forge.py init R:\GitHub\MyLaravelApp --kit todo --kit laravel
```

### 2. Existing Project

`kit` adds one kit and only copies missing files. `sync` updates the kits the repository already has (plus any `--kit` you add): it refreshes their skills, rules and subagents, and with `--include-scripts` their `scripts/` and `bin/` files. Neither ever overwrites `AGENTS.md`, `GEMINI.md`, `CLAUDE.md`, `CODEX.md`, `docs/`, a `todo/` plan, a site pin or other project files. Both take `--agent all|gemini|claude|codex`.

```powershell
python R:\GitHub\Conclave-SDK\forge.py kit R:\GitHub\ExistingRepo base
python R:\GitHub\Conclave-SDK\forge.py kit R:\GitHub\ExistingRepo todo
python R:\GitHub\Conclave-SDK\forge.py sync R:\GitHub\ExistingRepo --include-scripts

# Read-only health and setup checks
python R:\GitHub\Conclave-SDK\forge.py check R:\GitHub\ExistingRepo
python R:\GitHub\Conclave-SDK\forge.py doctor R:\GitHub\ExistingRepo
```

### 3. Prompting Gemini, Claude, or Codex to Import Conclave-SDK

Paste the prompt from [`prompts/bootstrap-project-prompt.md`](file:///R:/GitHub/Conclave-SDK/prompts/bootstrap-project-prompt.md) into any Gemini, Claude, or Codex session open in your target repository.

## Overlay Kits (`kits/`)

| Kit | What it installs (for `.agents`, `.claude` and `.codex`) | Install when |
| --- | --- | --- |
| `base` | Entry docs, safety and authoring skills, subagents, rules | Every repository |
| `todo` | 8 TODO skills, `todo-graph.py`, starter `todo/` tree | Work planned in TODO files |
| `reviewer` | Reviewer pin, `review-dispatch.py`, review skill | Independent review |
| `automations` | `tasks.json`, runner, failure email, installers, skill | Scheduled checks |
| `laravel` | `boost.json`, `.mcp.json`, LSP diagnostics, `laravel-boost` | `artisan` exists |
| `wordpress` | Site pin, SSH/SFTP, WordPress MCP, DDEV, PHPCS | A WordPress site |

## Provisioning Modes

* **`isolated` (Default):** Copies tracked skills and rules into `.agents/`, `.claude/`, and `.codex/` inside the target repository with zero external path dependencies. Every repository is 100% self-contained and each agent is isolated in its own directory.
* **`hybrid`:** Optional mode that copies isolated skills and also writes `.agents/skills.json` pointing at the Antigravity skill folders of the chosen kits.
* **`inherit`:** Optional mode that writes `.agents/skills.json` and `.agents/plugins.json` without copying skill Markdown files.

## TODO Workflow Discipline

The `todo` kit's eight skills (`add-todo`, `create-todo`, `groom-plan`, `process-phase`, `process-plan`, `process-todo-file`, `process-todo-section`, `review-todo-section`), its starter `todo/` tree and `docs/todo-workflow.md` enforce the canonical Conclave-SDK execution contract:

* **Small, single-responsibility sections:** Multi-subsystem, multi-dialog, or multi-workflow work is split into small, single-responsibility sections rather than coarse umbrella sections.
* **Readable table descriptions (`<= 88` chars):** Every section heading (`## N. <Title>`), `Deliverable` cell in `Implementation Order`, and `Scope` cell in index tables is a clear noun phrase of at most 88 characters (enforced by `todo-graph.py validate`) so raw Markdown table rows stay under 140 characters and do not wrap in raw `.md` editors.
* **Granular five-part micro-steps:** Every section carries 1 to 30 concrete micro-step items (typically 4 to 15 micro-steps, never a 1-bullet summary stub), ending with `- [ ] Commit: <message>`. Each non-Commit item names: (1) one action, (2) a concrete path/symbol/command in backticks, (3) `Done when:` observable end state in the same bullet, (4) `Cheaper substitute:` on UI and write items, and (5) a source citation when copying behavior.
* **100% complete development plan:** Running `process-plan` from start to finish leaves a 100% complete, shippable product with zero unowned SPEC controls, settings, refusal/error paths, undo/reverse paths, or persistence read-backs, and zero silent scope drops.
* **Logical step commits:** Commits follow logical steps within a section; review fix-loop commits append to the candidate range without amending.
