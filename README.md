# Conclave-SDK

Conclave-SDK is the central repository for isolated agent skills, rules, subagent definitions, stack overlay kits (`base`, `laravel`, `wordpress`), prompts, plugins, templates, and the canonical TODO graph tooling (`todo-graph.py`).

It is designed to be imported into any **new** or **existing** repository by **Google Antigravity / Gemini (`gemini` / `agy`)**, **Claude Code (`claude`)**, and **OpenAI Codex (`codex`)**:

- **Google Antigravity / Gemini (`gemini` / `agy`):** `.agents/skills/`, `.agents/rules/`, and `GEMINI.md`
- **Claude Code (`claude`):** `.claude/skills/`, `.claude/rules/`, `.claude/agents/`, and `CLAUDE.md`
- **OpenAI Codex (`codex`):** `.codex/skills/` (with `agents/openai.yaml`), `.codex/rules/`, and `CODEX.md`

Each agent reads only its own isolated folder and entrypoint alongside the shared project rules in `AGENTS.md`.

## Repository Layout

| Path | Purpose |
| ---- | ------- |
| `forge.py` / `forge.cmd` | CLI (`init`, `sync`, `kit`, `doctor`, `kits`, `check`; `isolated` default mode). |
| `skills/agy/` | Isolated Gemini / Antigravity skills (`<target>/.agents/skills/`). |
| `skills/claude/` | Isolated Claude Code skills (`<target>/.claude/skills/`). |
| `skills/codex/` | Isolated OpenAI Codex skills (`<target>/.codex/skills/` with `openai.yaml`). |
| `agents/claude/` | Claude Sonnet subagent definitions (`<target>/.claude/agents/`). |
| `kits/` | Additive project and stack overlays (`base/`, `laravel/`, `wordpress/`). |
| `rules/` | Shared and per-agent rule templates (`AGENTS`, `GEMINI`, `CLAUDE`, `CODEX`). |
| `prompts/` | Copy-pasteable prompts to import Conclave-SDK from Gemini, Claude, or Codex. |
| `plugins/todo-workflow/` | Antigravity plugin bundle (`plugin.json`) for TODO workflow skills. |
| `scripts/` | Canonical `todo-graph.py`, `lib/todo_graph.py`, and `verify-agent-tiers.mjs`. |
| `templates/todo/` | Starter `todo/` tree (`README.md`, root index, findings, section template). |
| `tests/` | Unit test suites for `todo_graph.py`, `forge.py`, and stack overlay kits. |

## Importing into a New or Existing Project (Gemini, Claude, or Codex)

### 1. New Project (All Agents + Optional Stack Kit + Starter `todo/` Tree)

Run from Windows PowerShell (or pass `/mnt/r/GitHub/Conclave-SDK/forge.py` inside WSL):

```powershell
# Generic new project
python R:\GitHub\Conclave-SDK\forge.py init R:\GitHub\MyProject --with-todo

# New Laravel or WordPress project
python R:\GitHub\Conclave-SDK\forge.py init R:\GitHub\MyLaravelApp --kit laravel --with-todo
python R:\GitHub\Conclave-SDK\forge.py init R:\GitHub\MyWordPressSite --kit wordpress --with-todo
```

### 2. Existing Project (Additive Sync + Stack Kit + Doctor)

On an existing project, `sync` and `kit` never overwrite `AGENTS.md`, `GEMINI.md`, `CLAUDE.md`, `CODEX.md`, or existing project files. You can target all three agents (`--agent all`) or a single agent (`--agent gemini`, `--agent claude`, `--agent codex`):

```powershell
# Sync all 3 isolated agents into an existing repo
python R:\GitHub\Conclave-SDK\forge.py sync R:\GitHub\ExistingRepo --include-scripts

# Sync or import a stack kit for one specific agent (gemini, claude, or codex) or all
python R:\GitHub\Conclave-SDK\forge.py sync R:\GitHub\ExistingRepo --agent gemini
python R:\GitHub\Conclave-SDK\forge.py sync R:\GitHub\ExistingRepo --agent claude
python R:\GitHub\Conclave-SDK\forge.py sync R:\GitHub\ExistingRepo --agent codex
python R:\GitHub\Conclave-SDK\forge.py kit R:\GitHub\ExistingRepo laravel --agent all

# Run read-only health and setup checks
python R:\GitHub\Conclave-SDK\forge.py check R:\GitHub\ExistingRepo
python R:\GitHub\Conclave-SDK\forge.py doctor R:\GitHub\ExistingRepo
```

### 3. Prompting Gemini, Claude, or Codex to Import Conclave-SDK

Paste the prompt from [`prompts/bootstrap-project-prompt.md`](file:///R:/GitHub/Conclave-SDK/prompts/bootstrap-project-prompt.md) into any Gemini, Claude, or Codex session open in your target repository:

```text
Import Conclave-SDK into this repository by running `python R:\GitHub\Conclave-SDK\forge.py init .` (or `sync . --include-scripts` if already initialized), apply any matching stack kit (`--kit laravel` if `artisan` exists, `--kit wordpress` if `wp-load.php` or `wp-config.php` exists), and verify with `python R:\GitHub\Conclave-SDK\forge.py check .` and `python R:\GitHub\Conclave-SDK\forge.py doctor .`.
```

## Overlay Kits (`kits/`)

| Kit | What it installs (across `.agents`, `.claude`, and `.codex`) | Auto-detects |
| --- | ------------------------------------------------------------ | ------------ |
| `base` | `AGENTS.md`, `GEMINI.md`, `CLAUDE.md`, `CODEX.md`, safety and authoring skills | Any repository |
| `laravel` | `boost.json`, `.mcp.json`, `lsp-diagnostics.py`, pre-push hook, `laravel-boost` skill | `artisan` (root or child) |
| `wordpress` | `phpcs.xml.dist`, WPCS `composer.json`, MCP example, `wordpress-site-safety` skill | `wp-load.php` / `wp-config.php` |

## Provisioning Modes

* **`isolated` (Default):** Copies tracked skills and rules into `.agents/`, `.claude/`, and `.codex/` inside the target repository with zero external path dependencies. Every repository is 100% self-contained and each agent is isolated in its own directory.
* **`hybrid`:** Optional mode that copies isolated skills and also writes `.agents/skills.json` pointing to `R:/GitHub/Conclave-SDK/skills/agy`.
* **`inherit`:** Optional mode that writes `.agents/skills.json` and `.agents/plugins.json` without copying skill Markdown files.

## TODO Workflow Discipline

All ten core skills (`add-todo`, `authoring-skills`, `create-todo`, `groom-plan`, `local-tool-safety`, `process-phase`, `process-plan`, `process-todo-file`, `process-todo-section`, `review-todo-section`) and `templates/todo/` enforce the canonical Conclave-SDK execution contract:

* **Small, single-responsibility sections:** Multi-subsystem, multi-dialog, or multi-workflow work is split into small, single-responsibility sections rather than coarse umbrella sections.
* **Readable table descriptions (`<= 88` chars):** Every section heading (`## N. <Title>`), `Deliverable` cell in `Implementation Order`, and `Scope` cell in index tables is a clear noun phrase of at most 88 characters (enforced by `todo-graph.py validate`) so raw Markdown table rows stay under 140 characters and do not wrap in raw `.md` editors.
* **Granular five-part micro-steps:** Every section carries 1 to 30 concrete micro-step items (typically 4 to 15 micro-steps, never a 1-bullet summary stub), ending with `- [ ] Commit: <message>`. Each non-Commit item names: (1) one action, (2) a concrete path/symbol/command in backticks, (3) `Done when:` observable end state in the same bullet, (4) `Cheaper substitute:` on UI and write items, and (5) a source citation when copying behavior.
* **100% complete development plan:** Running `process-plan` from start to finish leaves a 100% complete, shippable product with zero unowned SPEC controls, settings, refusal/error paths, undo/reverse paths, or persistence read-backs, and zero silent scope drops.
* **Logical step commits:** Commits follow logical steps within a section; review fix-loop commits append to the candidate range without amending.
