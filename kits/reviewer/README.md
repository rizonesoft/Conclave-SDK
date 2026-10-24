# Reviewer kit

Additive overlay that gives a project independent review by a different model: one pin that names the reviewers, one command that runs a review round, and a skill for Gemini (`.agents/`), Claude (`.claude/`) and Codex (`.codex/`). The todo kit's `review-todo-section` uses it for its review rounds.

## Who reviews whom

| Work written by | Reviewer |
| --- | --- |
| Claude | GPT-6 Astra through Codex, effort set by the schedule |

The starting pin routes Claude's work to Astra and no other writer, so a round for Codex or Gemini work refuses until the project adds a route. The route names exactly one reviewer, never of the writer's own model family: the pin refuses anything else. A reviewer that cannot review is no review, and no other reviewer runs in its place.

| Reviewer | CLI | Model | Default effort |
| --- | --- | --- | --- |
| `astra` | `codex exec`, read-only sandbox | `gpt-6-astra` | `medium` |

The dispatcher can also run a reviewer through Claude Code (`cli = "claude"`, plan mode) or Antigravity (`cli = "agy"`, plan mode in its sandbox, with the effort in the model name: `gemini-4-argon-medium`). Change reviewers, models, routes or the schedule only in `.conclave/reviewers.toml`. The pin is a starting point the project owns once installed, not a link back to the SDK.

## The review schedule

The pin's `[schedule]` table makes the dispatcher pick each pass's effort and lenses, so the loop runs the same way every time:

| Pass | Effort | Lenses |
| --- | --- | --- |
| Plan review (`--kind plan`), before the build | medium | plan |
| Completion review (`--kind completion`), after it | medium | completion prompt |
| Round 1 | high | adversarial, integration, source-defect, plan-delivery |
| Round 2 | medium | adversarial |
| Round 3 | low | adversarial |
| Later rounds, one lens each | low | consistency, quality, design, optimization, record |
| After a low-effort round that finds a P1 | medium | adversarial |

The design lens joins the rotation only with `--surface`. Each review tags its findings `P1`, `P2` or `P3` and ends with a `HIGHEST:` line. With `severity_stop_after = 0` the first round with no P1 or P2 finding ends the loop (the summary's `severity_stop` is true); the cap stays 33 rounds. Delete the whole `[schedule]` block to review every round at the reviewer's own effort with the prompt's fallback lens list.

## What lands

| Path | Role |
| ---- | ---- |
| `.conclave/reviewers.toml` | The reviewers and the route for each writer |
| `scripts/review-dispatch.py` | Runs a round and records it |
| `scripts/tests/test_review_dispatch.py` | Routing, schedule, failed-review and record tests |
| `docs/review-round-prompt.md` | The round prompt: candidate, lenses, severities, reply format |
| `docs/plan-review-prompt.md` | The one-pass plan review before the build |
| `docs/completion-review-prompt.md` | The one-pass completion and excellence review |
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

Before the build, and again once it is built, run the one-pass reviews (neither counts as a round, and a findings file holds one returned review of each kind):

```bash
python3 scripts/review-dispatch.py --kind plan --candidate <40-char SHA> --writer claude --prompt <scratch>/plan-prompt.md --record docs/reviews/<topic>.md
python3 scripts/review-dispatch.py --kind completion --candidate <40-char SHA> --writer claude --prompt <scratch>/completion-prompt.md --record docs/reviews/<topic>.md
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

A pin that loads prints `{"ok": true, "schema_version": 1, "reviewers": {...}, "routes": {...}, "schedule": {...}, "clis": {"codex": true, "agy": false, "claude": true}}` and exits 0: `reviewers`, `routes` and `schedule` are exactly what `load_pin` returns (`schedule` only when the pin has one), and `clis` says which reviewer CLIs are on `PATH`. A CLI is looked for only in the absolute directories on `PATH`, never in the working directory, so a `codex.cmd` committed to the reviewed repository is neither counted nor run. A refused or missing pin prints `{"ok": false, "error": "<message>"}`, the message a review run would refuse with, and exits 2. Without `--json` it prints `ok` or `refused: <message>`. `--writer` and `--prompt` are not needed.

Exit 0 is a review (which may still find problems). Exit 1 means the reviewer returned no review (a reply ending `OVERALL: blocked` is not one), which is never an approval; the summary's `failover` names it and the reason. Exit 2 means the pin or the arguments were refused and nothing ran, or that `--record` named a findings file it cannot read back (the review still prints).
