# Reviewer kit

Additive overlay that gives a project independent review by a different model: one pin that names the reviewers, one command that runs a review round, and a skill for Gemini (`.agents/`), Claude (`.claude/`) and Codex (`.codex/`). The todo kit's `review-todo-section` uses it for its review rounds.

## Who reviews whom

| Work written by | Reviewer |
| --- | --- |
| Claude | GPT-6.1 Sol |
| Codex | Sonnet 5.5 |
| Gemini | GPT-6.1 Sol |

Each route names exactly one reviewer, never of the writer's own model family: the pin refuses anything else. A reviewer that cannot review is no review, and no other reviewer runs in its place.

| Reviewer | CLI | Model | Effort |
| --- | --- | --- | --- |
| `sol` | `codex exec`, read-only sandbox | `gpt-6.1-sol` | `xhigh` |
| `sonnet` | `claude -p`, plan mode | `claude-sonnet-5-5` | `high` |

A reviewer can also run through Antigravity (`cli = "agy"`, plan mode in its sandbox), with the effort in the model name (`gemini-4-argon-medium`). All three CLIs were tested headless on 2026-10-16: each found a planted bug and changed no file. Change reviewers, models or routes only in `.conclave/reviewers.toml`.

## What lands

| Path | Role |
| ---- | ---- |
| `.conclave/reviewers.toml` | The reviewers and the route for each writer |
| `scripts/review-dispatch.py` | Runs a round and records it |
| `scripts/tests/test_review_dispatch.py` | Routing, failed-review and record tests with fake CLIs |
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

The doctor loads the pin under the dispatcher's own rules and reports any reviewer CLI that is not installed (a round routed to that reviewer has no review). Operator globals: the `codex`, `agy` and `claude` CLIs, signed in.

## Running a round

```bash
python3 scripts/review-dispatch.py --writer claude --prompt <scratch>/review-prompt.md --record docs/reviews/<topic>.md
```

To read the recorded rounds back (the editor extension's Review rounds section does), without running a reviewer:

```bash
python3 scripts/review-dispatch.py --list-rounds --json [--records docs/reviews]
```

It prints `{"records": [{"path", "rounds": [{"number", "reviewer", "model", "cli", "writer", "run", "effort", "skipped": [{"reviewer", "reason"}]}]}]}`, with `reviewer`, `model` and `cli` null for a round no reviewer returned, and adds `"unreadable": [path]` for a findings file whose round headings or lines are not in the format `--record` writes, never dropping it, or a file that cannot be read or is not UTF-8. Without `--json` it prints one line per round. Each round `--record` writes states how many lines its review has (`- Lines: N`, lines split on newline only) and a digest of them (`- Digest:`, the first 16 hex digits of their SHA-256), and the reader skips exactly that many lines and checks the digest, so a review quoting `## Round ...` lines can never pass for a round, and a hand edit inside a review, even one that keeps its line count, makes the file unreadable. The review is stored byte for byte, carriage returns included; a CRLF checkout reads the same. Text after a round's review belongs to no round: notes such as `## Response to round N` sit there and are not read. Rounds recorded before the count run to the next round heading, and rounds recorded before the digest are read by their count alone. `--record` never appends to a findings file it cannot read back: the review still prints, nothing is written, and the exit is 2.

To ask whether the pin loads, the same way a review run would load it, without running a reviewer (the editor extension validates every edit this way):

```bash
python3 scripts/review-dispatch.py --check-pin --json [--pin .conclave/reviewers.toml]
```

A pin that loads prints `{"ok": true, "schema_version": 1, "reviewers": {...}, "routes": {...}, "clis": {"codex": true, "agy": false, "claude": true}}` and exits 0: `reviewers` and `routes` are exactly what `load_pin` returns, and `clis` says which reviewer CLIs are on `PATH`. A CLI is looked for only in the absolute directories on `PATH`, never in the working directory, so a `codex.cmd` committed to the reviewed repository is neither counted nor run. A refused or missing pin prints `{"ok": false, "error": "<message>"}`, the message a review run would refuse with, and exits 2. Without `--json` it prints `ok` or `refused: <message>`. `--writer` and `--prompt` are not needed.

Exit 0 is a review (which may still find problems). Exit 1 means the reviewer returned no review (a reply ending `OVERALL: blocked` is not one), which is never an approval; the summary's `failover` names it and the reason. Exit 2 means the pin or the arguments were refused and nothing ran, or that `--record` named a findings file it cannot read back (the review still prints).
