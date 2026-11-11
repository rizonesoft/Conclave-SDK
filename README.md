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
| `forge.py` / `forge.cmd` | CLI: `init`, `kit`, `doctor`, `kits`, `check`, `self-sync`. |
| `kits/base/` | Every repo: entry docs, safety skills, subagents, rules, tier check. |
| `kits/todo/` | TODO skills, `todo-graph.py`, starter `todo/` tree, workflow doc. |
| `kits/reviewer/` | Reviewer pin (one reviewer of another model family) and dispatcher. |
| `kits/automations/` | Scheduled tasks for Task Scheduler and systemd, with a failure email. |
| `kits/laravel/`, `kits/wordpress/` | Stack kits. |
| `prompts/` | Copy-pasteable prompts to import Conclave-SDK from Gemini, Claude, or Codex. |
| `plugins/` | Standalone agent plugins that belong to no kit (never installed by `forge.py`). |
| `tests/fixtures/check-pin/` | Pins and dispatchers freezing the `--check-pin` contract. |
| `todo/` | The SDK's own TODO plan. |
| `.agents/`, `.claude/`, `.codex/` | The SDK's own `base`, `todo`, `reviewer`, `automations`. |
| `scripts/`, `.conclave/` | The SDK's own todo, reviewer and automations scripts and pins. |
| `tests/` | Suites for `todo_graph.py`, `forge.py`, kits, `test_check_pin_contract.py`. |

## Importing into a New or Existing Project (Gemini, Claude, or Codex)

Conclave-SDK is a template, not a master copy. `init` and `kit` copy files into the project once and never overwrite a file that is already there, and nothing they write records which SDK the project came from or points back at it. From then on the project owns its copy: adapt the skills, scripts and pins to the project, and they never drift against the SDK because they are not tied to it. To pick up a later SDK improvement, read the kit's change and port it by hand, like any other code you borrow.

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

`kit` adds one kit and only copies missing files: every file the project already has, its own or one an earlier copy left, is listed under `preserved` and left exactly as it is. It takes `--agent all|gemini|claude|codex` and `--dry-run` to preview. `check` lists the kits a repository appears to have, judged by their files alone.

```powershell
python R:\GitHub\Conclave-SDK\forge.py kit R:\GitHub\ExistingRepo base
python R:\GitHub\Conclave-SDK\forge.py kit R:\GitHub\ExistingRepo todo

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

## Isolation

`forge.py` copies tracked skills and rules into `.agents/`, `.claude/` and `.codex/` inside the target repository with zero external path dependencies: no manifest, link or stamp points at the SDK. Every repository is 100% self-contained and each agent is isolated in its own directory.

The SDK itself is the one exception: it plans, reviews and schedules its own work with the `base`, `todo`, `reviewer` and `automations` kits, so it keeps an installed copy of them that `python forge.py self-sync` refreshes from the kits (`tests/test_forge.py` fails until the two match).

## TODO Workflow Discipline

The `todo` kit's eight skills (`add-todo`, `create-todo`, `groom-plan`, `process-phase`, `process-plan`, `process-todo-file`, `process-todo-section`, `review-todo-section`), its starter `todo/` tree and `docs/todo-workflow.md` enforce the canonical Conclave-SDK execution contract:

* **Small, single-responsibility sections:** Multi-subsystem, multi-dialog, or multi-workflow work is split into small, single-responsibility sections rather than coarse umbrella sections.
* **Readable table descriptions (`<= 88` chars):** Every section heading (`## N. <Title>`), `Deliverable` cell in `Implementation Order`, and `Scope` cell in index tables is a clear noun phrase of at most 88 characters (enforced by `todo-graph.py validate`) so raw Markdown table rows stay under 140 characters and do not wrap in raw `.md` editors.
* **Granular five-part micro-steps:** Every section carries 1 to 30 concrete micro-step items (typically 4 to 15 micro-steps, never a 1-bullet summary stub), ending with `- [ ] Commit: <message>`. Each non-Commit item names: (1) one action, (2) a concrete path/symbol/command in backticks, (3) `Done when:` observable end state in the same bullet, (4) `Cheaper substitute:` on UI and write items, and (5) a source citation when copying behavior.
* **100% complete development plan:** Running `process-plan` from start to finish leaves a 100% complete, shippable product with zero unowned SPEC controls, settings, refusal/error paths, undo/reverse paths, or persistence read-backs, and zero silent scope drops.
* **Logical step commits:** Commits follow logical steps within a section; review fix-loop commits append to the candidate range without amending.
