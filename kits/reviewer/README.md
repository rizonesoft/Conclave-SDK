# Reviewer kit

Additive overlay that gives a project independent review by a different model: one pin that names the reviewers, one command that runs a review round with failover, and a skill for Gemini (`.agents/`), Claude (`.claude/`) and Codex (`.codex/`). The todo kit's `review-todo-section` uses it for its review rounds.

## Who reviews whom

| Work written by | Reviewer | Fallback |
| --- | --- | --- |
| Claude | GPT-6 Astra | Gemini 4 |
| Codex | Gemini 4 | Sonnet 5.5 |
| Gemini | GPT-6 Astra | Sonnet 5.5 |

A reviewer is never of the writer's own model family, and a route has one fallback at most: the pin refuses anything else.

| Reviewer | CLI | Model | Effort |
| --- | --- | --- | --- |
| `astra` | `codex exec`, read-only sandbox | `gpt-6-astra` | `medium` |
| `gemini` | `agy -p`, plan mode in its sandbox | `gemini-4-argon-high` | in the model name |
| `sonnet` | `claude -p`, plan mode | `claude-sonnet-5-5` | `high` |

All three were tested headless on 2026-10-16: each found a planted bug and changed no file. Change reviewers, models or routes only in `.conclave/reviewers.toml`.

## What lands

| Path | Role |
| ---- | ---- |
| `.conclave/reviewers.toml` | The reviewers and the route for each writer |
| `scripts/review-dispatch.py` | Runs a round with failover and records it |
| `scripts/tests/test_review_dispatch.py` | Routing, failover and record tests with fake CLIs |
| `docs/review-round-prompt.md` | The prompt template: candidate, lenses, reply format |
| `.{agents,claude,codex}/skills/independent-review/` | When and how to get a review |

## Install

```powershell
python forge.py kit /path/to/project reviewer
python forge.py doctor /path/to/project reviewer
```

```bash
kits/reviewer/scripts/install.sh /path/to/project [--dry-run]
```

The doctor loads the pin under the dispatcher's own rules and reports any reviewer CLI that is not installed (that reviewer is skipped at run time). Operator globals: the `codex`, `agy` and `claude` CLIs, signed in.

## Running a round

```bash
python3 scripts/review-dispatch.py --writer claude --prompt <scratch>/review-prompt.md --record docs/reviews/<topic>.md
```

To read the recorded rounds back (the editor extension's Review rounds section does), without running a reviewer:

```bash
python3 scripts/review-dispatch.py --list-rounds --json [--records docs/reviews]
```

It prints `{"records": [{"path", "rounds": [{"number", "reviewer", "model", "cli", "writer", "run", "effort", "skipped": [{"reviewer", "reason"}]}]}]}`, with `reviewer`, `model` and `cli` null for a round no reviewer returned, and adds `"unreadable": [path]` for a findings file whose round headings or lines are not in the format `--record` writes, never dropping it. Without `--json` it prints one line per round.

Exit 0 is a review (which may still find problems). Exit 1 means neither the reviewer nor its fallback returned a review (a reply ending `OVERALL: blocked` is not one), which is never an approval. Exit 2 means the pin or the arguments were refused and nothing ran.
