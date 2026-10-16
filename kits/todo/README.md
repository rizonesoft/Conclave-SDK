# TODO kit

Additive overlay that brings the Conclave TODO system into a project for Gemini (`.agents/`), Claude (`.claude/`) and Codex (`.codex/`). Install it where work is planned and built through TODO files; projects that do not plan that way only need `kits/base`.

## What lands

| Path | Role |
| ---- | ---- |
| `.{agents,claude,codex}/skills/<skill>/` | The 8 TODO skills for each agent (below) |
| `scripts/todo-graph.py`, `scripts/lib/todo_graph.py` | Validate, query, stamp and plan |
| `todo/` | Starter tree: `README.md` (the format), root index, findings, section template |
| `docs/todo-workflow.md` | How the TODO system works; link it from `AGENTS.md` |

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

The files here are copies of the canonical sources: `skills/<agent>/<skill>/`, `scripts/todo-graph.py`, `scripts/lib/todo_graph.py` and `templates/todo/`. Change the canonical file, then copy it here; `tests/test_forge.py` fails while any copy differs. `forge.py init --with-todo` installs the same system from the canonical sources.
