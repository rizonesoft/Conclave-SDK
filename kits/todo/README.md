# TODO kit

Additive overlay that brings the Conclave TODO system into a project for Gemini (`.agents/`), Claude (`.claude/`) and Codex (`.codex/`). Install it where work is planned and built through TODO files; projects that do not plan that way only need `kits/base`. Install `kits/reviewer` with it: `review-todo-section` and the plan and completion reviews run through `scripts/review-dispatch.py`.

## What lands

| Path | Role |
| ---- | ---- |
| `.{agents,claude,codex}/skills/<skill>/` | The 8 TODO skills for each agent (below) |
| `scripts/todo-graph.py`, `scripts/lib/todo_graph.py` | Validate, query, stamp and plan |
| `todo/` | Starter tree: `README.md` (the format), root index, findings, section template |
| `docs/todo-workflow.md` | How the TODO system works; link it from `AGENTS.md` |
| `scripts/campaign_guard.py` | The `process-plan` run guard: Stop hook, guard file, heartbeat |
| `.claude/settings.json` | Wires the Stop hook (seeded only when the project has none) |
| `.agents/hooks.json` | Wires the Stop hook for Antigravity (seeded only when the project has none) |
| `.codex/hooks.json` | Wires the Stop hook for Codex through `scripts/codex-campaign-hook.py` (seeded likewise) |
| `scripts/codex-hook-trust.py` | Approves that Codex hook through Codex's own app-server |
| `scripts/ci_status.py` | The CI state of main: each watched workflow's latest verdict |
| `scripts/merge_prs.py` | Merges dependency pull requests that pass every safety rule |
| `scripts/hooks/pre-commit` | Runs `todo-graph.py validate` and `plan --check` on TODO commits |

## Reading the plan from another program

`python scripts/todo-graph.py query plan` prints the plan as JSON: `title`, `acceptance` and `phases` (number to name) from `todo/plan.json`, and `sections`, every section in plan order with its `ref`, `path`, `title`, `phase`, `depends` and `status` (`verified`, `ready`, `blocked`, or `deferred` when its file is not active). A program that shows the plan reads this instead of parsing `todo/`; an unreadable `todo/plan.json` is refused with exit 2, as every other query.

## CI status and dependency merges

`python scripts/ci_status.py [--json] [--branch main] [--workflow <file>]` reads each watched workflow's recent runs through `gh` and reports its latest completed verdict (a cancelled run carries none) and how many newer runs are still in progress, naming the failed jobs of a red one. It watches the `--workflow` files, else the `workflows` list in `.conclave/ci.json` (`{"workflows": ["ci.yml"]}`), else every workflow in `.github/workflows/`. Exit 1 means a watched workflow is red; exit 3 means `gh` failed and the state is unknown, never green.

`python scripts/merge_prs.py [--dry-run] [--scheduled]` merges open pull requests into main one at a time, only when it is safe (a clean tree, `HEAD` at `origin/main`, no TODO section in progress and, with `--scheduled`, no campaign run guard held) and each one passes every rule: a known producer (Dependabot by default, which may change only `.github/` files), the `dependencies` label, mergeable, and every check finished green (a pull request with no checks never merges). An optional `merge` object in `.conclave/ci.json` adds `required_checks`, `labels`, `producers` (each with `authors`, a `branch` pattern and the `files` it may touch) and `excluded_branches`; an unknown key or a bad pattern refuses the run. The automations kit README shows a scheduled task that runs it.

The pre-commit hook checks a commit that touches `todo/` or `docs/reviews/`. Enable it once per clone with `git config core.hooksPath scripts/hooks`.

## The run guard (Claude Code, Antigravity and Codex)

`process-plan` keeps a campaign alive in each agent with the same guard file and its agent's own Stop hook. The stall breaker lets a turn end after 3 pushes with no change and counts a trip; a turn let end is not a released run. Only `end` releases it, or the second trip counted through `heartbeat-still`.

- Claude Code: `.claude/settings.json` runs the hook (`block`), and a `CronCreate` heartbeat inside the session resumes it when idle.
- Antigravity: `.agents/hooks.json` runs the hook (`continue`), and a recurring timer made with its `schedule` tool resumes it; the session is `ANTIGRAVITY_CONVERSATION_ID`.
- Codex: `.codex/hooks.json` runs `scripts/codex-campaign-hook.py` (`block`); Codex has no scheduled resume inside a session, so the hook alone holds the run; the session is `CODEX_THREAD_ID`.

Only a run started through the unattended kit's launcher is restarted from outside the session; there is no other keep-alive. `python scripts/campaign_guard.py --self-test` runs each hook file's own command as its harness does. `campaign_guard.py` owns the guard file and the hook, runs the same on Windows and WSL (`python3` in the hook command, an OS file lock on both), and is tested by `tests/test_campaign_guard.py`. A project that already has `.claude/settings.json` keeps it: `forge.py doctor <repo> todo` reports `stop-hook` as `setup_required` until the Stop hook from `templates/.claude/settings.json` is added by hand. Codex runs `.codex/hooks.json` (Claude Code's shape, `command` and `commandWindows`), checked against Codex 0.167.0 on Windows and 0.166.0 in WSL on 2026-11-12. Its Stop payload is Claude Code's (`session_id`, `cwd`, `hook_event_name`, `stop_hook_active`), the hook runs from the project root, and `scripts/codex-campaign-hook.py` answers `block` or, on any failure, `{}`. Codex runs a project's hook only once the project is trusted and the hook approved: the approvals are `projects.<path>.trust_level` and `hooks.state."<path>/.codex/hooks.json:stop:0:0".trusted_hash` in the user's `config.toml`. `scripts/codex-hook-trust.py` records both through Codex's own app-server (`hooks/list` gives each hook's `currentHash` and `trustStatus`, `config/value/write` records them), for this project's campaign Stop hook only; `forge.py kit <repo> todo` runs it after installing the hook, and `forge.py doctor <repo> todo` reports `stop-hook:.codex` and `stop-hook-approved:.codex` (approved against the current hash, so a changed hook reads `modified`).

Antigravity runs `.agents/hooks.json`, checked against `agy` 1.5.5 and its own `hooks.md` (`~/.gemini/antigravity-cli/builtin/skills/agy-customizations/docs/hooks.md`) with a live run on 2026-11-11. Three facts shape the seed. Each top-level key is a named hook and its `Stop` list holds the handlers directly: Claude Code's shape (a top-level `hooks` key) loads as one hook named `hooks`. A hook runs with its working folder set to the folder holding `hooks.json`, so the command reaches the guard as `../scripts/campaign_guard.py`. On Windows it runs through `cmd /c` with its inner double quotes escaped, so the command holds no quotes: `python3 ../scripts/campaign_guard.py stop-hook || python ../scripts/campaign_guard.py stop-hook`. The Stop payload carries `conversationId` (the session the guard is acquired for), `workspacePaths`, `cwd`, `fullyIdle`, `terminationReason` and `continuationActive`, and no `CLAUDE_PROJECT_DIR`; the guard answers `{"decision": "continue"}`, which re-enters the loop. `forge.py doctor <repo> todo` reports it as `stop-hook:.agents`, and only an enabled hook (`enabled` absent or `true`) counts.

Skills: `add-todo`, `create-todo`, `groom-plan`, `process-phase`, `process-plan`, `process-todo-file`, `process-todo-section`, `review-todo-section`.

## Install

```powershell
python forge.py kit /path/to/project todo [--agent all|gemini|claude|codex] [--dry-run]
python forge.py doctor /path/to/project todo
```

Like every kit it only adds missing files: an existing `todo/` plan, skill or script is kept byte for byte. After installing, add a line to the project's `AGENTS.md` pointing at `docs/todo-workflow.md`.

## Keeping it current

This kit is the only source of the TODO system. Change a file in `templates/`, then run `python forge.py self-sync` to refresh the SDK's own `.agents/`, `.claude/`, `.codex/` and `scripts/` (`tests/test_forge.py` fails until they match). Projects keep the copy they took; port a change into one by hand when it wants it. `tests/test_todo_graph.py` tests `templates/scripts/`.
