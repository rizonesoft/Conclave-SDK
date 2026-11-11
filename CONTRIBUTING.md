# Contributing to Conclave-SDK

Thank you for improving the SDK. This page says how a change gets in. The working rules every agent and person follows are in [`AGENTS.md`](AGENTS.md).

## Before you start

- **Find the home of the work.** The SDK plans its own work in [`todo/`](todo/README.md). Search it before proposing something new: `python scripts/todo-graph.py query ready` lists what can be built now, and [`todo/implementation-plan.md`](todo/implementation-plan.md) shows every phase.
- **Open an issue for anything that is not in the plan.** Say what is wrong or missing, where (a file and line), and how you would know it is fixed.
- **Change a kit in the kit.** The SDK's own `.agents/`, `.claude/`, `.codex/` and `scripts/` are an installed copy of the kits. Edit `kits/<kit>/templates/...`, then run `python forge.py self-sync`.

## The rules a change must keep

- **Standard library only.** `forge.py` and every script in the kits use Python 3 with no package to install.
- **Atomic writes.** A file is written to a temporary file in the same folder and then moved into place with `os.replace`.
- **Three agents, kept in step.** A skill exists for Claude Code (`.claude/`), Codex (`.codex/`) and Antigravity (`.agents/`). Change all three together.
- **A project owns its copy.** `forge.py` never overwrites a file a project already has, and nothing it writes points back at the SDK.
- **Fix at the owning layer.** A setting is fixed in its setting, behaviour in the code that produces it. No filter that hides a problem.
- **Writing.** One line per paragraph and per list item in Markdown, no em dashes or en dashes anywhere, and every table row at or under 120 characters.

## Tests

Every code change comes with a test that fails before the change and passes after it.

```powershell
python -m unittest discover -s tests                                     # the quick suite, about a minute
$env:CONCLAVE_FULL_TESTS = '1'; python -m unittest discover -s tests     # the full suite, several minutes
python scripts/todo-graph.py validate                                    # the TODO tree and the generated plan
```

Run the quick suite before every commit. Run the full suite when a change touches the stamp (`lib/todo_graph.py`), the review dispatcher or the pin loader.

## Commits and review

- Commit in logical steps, with a subject that says what now works: `forge: update writes only missing and kit-newer files`.
- A change that is not trivial is reviewed by a model of another family than the one that wrote it, through `scripts/review-dispatch.py` and the pin in `.conclave/reviewers.toml`. The `independent-review` skill has the steps.
- A TODO section is closed only by `python scripts/todo-graph.py stamp`, after its plan review, its round and its completion review are on record.

## Pull requests

Keep a pull request to one subject. Say what changed, how you tested it and what you left out, using the template. A pull request that changes a kit says which projects it was tried in.
