# TODO kit

Additive overlay that brings the Conclave TODO system into a project for Gemini (`.agents/`), Claude (`.claude/`) and Codex (`.codex/`). Install it where work is planned and built through TODO files; projects that do not plan that way only need `kits/base`.

## What lands

| Path | Role |
| ---- | ---- |
| `.{agents,claude,codex}/skills/<skill>/` | The 8 TODO skills for each agent (below) |
| `scripts/todo-graph.py`, `scripts/lib/todo_graph.py` | Validate, query, stamp and plan |
| `todo/` | Starter tree: `README.md` (the format), root index, findings, section template |
| `docs/todo-workflow.md` | How the TODO system works; link it from `AGENTS.md` |
| `scripts/campaign_guard.py` | The `process-plan` run guard: Stop hook, guard file, heartbeat |
| `.claude/settings.json` | Wires the Stop hook (seeded only when the project has none) |

## The run guard (Claude Code)

`process-plan` keeps a campaign alive with two parts: the Stop hook, which blocks the campaign session's end of turn while its run is open and trips a stall breaker after 3 pushes with no change, and a `CronCreate` heartbeat inside the session that resumes it when idle. There is no keep-alive outside the session. `campaign_guard.py` owns the guard file and the hook, runs the same on Windows and WSL (`python3` in the hook command, an OS file lock on both), and is tested by `tests/test_campaign_guard.py`. A project that already has `.claude/settings.json` keeps it: `forge.py doctor <repo> todo` reports `stop-hook` as `setup_required` until the Stop hook from `templates/.claude/settings.json` is added by hand. Gemini and Codex have no Stop hook or `CronCreate`, so their skills carry no guard.

Skills: `add-todo`, `create-todo`, `groom-plan`, `process-phase`, `process-plan`, `process-todo-file`, `process-todo-section`, `review-todo-section`.

## Install

```powershell
python forge.py kit /path/to/project todo [--agent all|gemini|claude|codex] [--dry-run]
python forge.py doctor /path/to/project todo
```

```bash
kits/todo/scripts/install.sh /path/to/project [--dry-run]
```

Like every kit it only adds missing files: an existing `todo/` plan, skill or script is kept byte for byte. After installing, add a line to the project's `AGENTS.md` pointing at `docs/todo-workflow.md`.

## Keeping it current

This kit is the only source of the TODO system. Change a file in `templates/`, copy skill changes into the SDK's own `.agents/`, `.claude/` or `.codex/` (`tests/test_forge.py` fails until they match), and run `forge.py sync <repo>` in projects that should pick it up. `tests/test_todo_graph.py` tests `templates/scripts/`.
