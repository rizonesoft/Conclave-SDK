# Reviewer kit

Additive overlay that gives a project independent review by a different model: one pin that names the reviewers and the review schedule, one command that runs a review pass, and a skill for Antigravity (`.agents/`), Claude (`.claude/`) and Codex (`.codex/`). The todo kit's `review-todo-section` uses it for every pass of a section.

## Who reviews whom

| Work written by | `--writer` | Reviewer |
| --- | --- | --- |
| Claude Code | `claude` | GPT-6 Astra through Codex |
| Antigravity | `agy` (or `gemini`) | GPT-6 Astra through Codex |
| Codex | `codex` | none yet: add a reviewer of another family and a `codex` route |

A route names exactly one reviewer, never of the writer's own model family: the pin refuses anything else. `agy` and `gemini` are one writer under two names, so a route under either serves both and a pin may not route both. A reviewer that cannot review is no review, and no other reviewer runs in its place.

| Reviewer | CLI | Model | Effort |
| --- | --- | --- | --- |
| `astra` | `codex exec`, read-only sandbox | `gpt-6-astra` | `medium` |

The dispatcher can also run a reviewer through Claude Code (`cli = "claude"`, plan mode) or Antigravity (`cli = "agy"`, plan mode in its sandbox, with the effort in the model name: `gemini-4-argon-medium`). Change reviewers, models, routes or the schedule only in `.conclave/reviewers.toml`. The pin is a starting point the project owns once installed, not a link back to the SDK.

## The review schedule

The pin's `[schedule]` makes the dispatcher pick each pass's effort and lenses, so a section is reviewed the same way every time. It has two shapes.

### Three-pass (`policy = "three-pass"`, what a new install starts on)

| Pass | When | Lenses in the installed pin |
| --- | --- | --- |
| Plan review (`--kind plan`) | Before the build | plan |
| Round (`--kind round`) | After the build and its gates | the defect lenses: adversarial, integration and five more |
| Completion review (`--kind completion`) | On the final candidate | plan-delivery, record |
| Reconciliation (`--kind reconciliation`) | After a pass with gaps | adversarial, integration, plan-delivery, record |

The round's seven lenses are adversarial, integration, source-defect, consistency, quality, optimization and design (design only with `--surface`). The rules the pin and the dispatcher hold a three-pass section to:

- **Order.** For a section's findings file (`docs/reviews/<NN-domain>/D<NN>-T<NN>-s<N>.md`) the passes run in that order, each on a commit descending from the one before, and a pass out of order is refused before a reviewer runs. A section takes one pass at a time.
- **The section's own pin.** A section runs under the pin committed at its plan review's candidate, schedule and route both, so commit the pin before the plan review. A later pin change never moves a section under way.
- **One owner per lens.** A lens belongs to one of plan, the round and completion. Reconciliation may repeat lenses.
- **One verdict per lens.** The dispatcher appends each scheduled lens with its question and requires a line `LENS <name>: clean` or `LENS <name>: findings` for each. A reply missing a lens line, or its final verdict lines, is recorded as no review with its text kept, and never counts as a pass.
- **Blocking levels.** `blocking = ["P1", "P2"]`: only those severities hold the stamp. A pass whose worst finding is below them is filed as tracked work and takes no further pass. Without the key every finding holds the stamp.
- **Caps.** `pass_cap` is the most returned passes a section may take in all (33 when absent). `no_progress_cap` (optional) stops a run of reconciliations whose worst finding gets no less severe.
- **Conditional lenses.** A `[[schedule.conditional]]` entry (`lenses`, `passes`, `paths`) adds its lenses to the named passes only when a file the section changed starts with one of its repository-relative paths. A plan review, and a review outside a section, take the files from `--paths`.
- **Lenses of your own.** `[schedule.lenses]` declares extra lens names with their questions, so a project adds a lens without editing the dispatcher.
- **Effort is optional** on reviewers and steps: a step without one passes no effort to the reviewer's CLI, whose own configuration then decides. An Antigravity model name must end with every effort the schedule sets.

### Rotation (no `policy` key)

| Pass | Effort | Lenses |
| --- | --- | --- |
| Plan review (`--kind plan`), before the build | medium | plan |
| Completion review (`--kind completion`), after it | medium | completion prompt |
| Round 1 | high | adversarial, integration, source-defect, plan-delivery |
| Round 2 | medium | adversarial |
| Round 3 | low | adversarial |
| Later rounds, one lens each | low | consistency, quality, design, optimization, record |
| After a low-effort round that finds a P1 | medium | adversarial |

The design lens joins the rotation only with `--surface`. With `severity_stop_after = 0` the first round with no P1 or P2 finding ends the loop (the summary's `severity_stop` is true); the cap is 33 rounds. A rotation schedule takes none of the three-pass keys. A project on a rotation pin keeps it for as long as its pin says so:

```toml
[schedule]
severity_stop_after = 0

[schedule.plan]
effort = "medium"
lenses = ["plan"]

[schedule.completion]
effort = "medium"

[[schedule.rounds]]
effort = "high"
lenses = ["adversarial", "integration", "source-defect", "plan-delivery"]

[[schedule.rounds]]
effort = "medium"
lenses = ["adversarial"]

[[schedule.rounds]]
effort = "low"
lenses = ["adversarial"]

[schedule.rotation]
effort = "low"
lenses = ["consistency", "quality", "design", "optimization", "record"]

[schedule.escalation]
effort = "medium"
lenses = ["adversarial"]
```

### Moving an existing pin to three-pass

1. Replace the `[schedule]` block with the three-pass one from `kits/reviewer/templates/.conclave/reviewers.toml`: add `policy = "three-pass"`, keep `plan`, cut `[[schedule.rounds]]` to one entry carrying the defect lenses, give `completion` the lenses `plan-delivery` and `record`, add `reconciliation`, and delete `rotation`, `escalation` and `severity_stop_after`.
2. Take `plan-delivery` and `record` out of the round: a lens has one owner.
3. Choose `pass_cap` and, if only some severities should hold the stamp, `blocking`.
4. Commit the pin. Sections whose plan review ran before that commit finish under the rotation pin they began with; sections started after it run three-pass.

## What lands

| Path | Role |
| ---- | ---- |
| `.conclave/reviewers.toml` | The reviewers, the route for each writer and the schedule |
| `scripts/review-dispatch.py` | Runs a pass and records it |
| `scripts/review_pin.py` | Loads and checks the pin; the one copy of its rules, copyable on its own |
| `scripts/tests/test_review_dispatch.py` | Routing, rotation schedule, failed-review and record tests |
| `scripts/tests/test_three_pass.py` | Three-pass order, pin, caps, blocking, lens verdict and path tests |
| `scripts/tests/test_review_pin.py` | Pin key, schedule, cap and lens verdict tests |
| `docs/plan-review-prompt.md` | The plan review before the build |
| `docs/review-round-prompt.md` | The round prompt: candidate, lenses, severities, reply format |
| `docs/completion-review-prompt.md` | The completion and excellence review |
| `docs/reconciliation-review-prompt.md` | The pass after a completion with gaps (three-pass) |
| `.{agents,claude,codex}/skills/independent-review/` | When and how to get a review |

## Install

```powershell
python forge.py kit /path/to/project reviewer
python forge.py doctor /path/to/project reviewer
```

```bash
kits/reviewer/scripts/install.sh /path/to/project [--dry-run]
```

The doctor loads the pin under the dispatcher's own rules and reports any reviewer CLI that is not installed (a pass routed to that reviewer has no review). Operator globals: the `codex`, `agy` and `claude` CLIs, signed in.

## Running a pass

Name your own agent as the writer (`claude`, `codex` or `agy`):

```bash
python3 scripts/review-dispatch.py --kind plan --candidate <40-char SHA> --writer <writer> --prompt <scratch>/plan.md --record docs/reviews/<NN-domain>/D<NN>-T<NN>-s<N>.md
python3 scripts/review-dispatch.py --kind round --candidate <40-char SHA> --writer <writer> --prompt <scratch>/round.md --record <the same file>
python3 scripts/review-dispatch.py --kind completion --candidate <40-char SHA> --writer <writer> --prompt <scratch>/completion.md --record <the same file>
python3 scripts/review-dispatch.py --kind reconciliation --candidate <40-char SHA> --writer <writer> --prompt <scratch>/reconciliation.md --record <the same file>
```

Under a rotation pin a round needs no `--candidate`, the completion review runs before the rounds, and there is no reconciliation. A review outside a TODO section records to any other findings file (`docs/reviews/<topic>.md`) and has no order.

To ask what the pin says without running a reviewer:

```bash
python3 scripts/review_pin.py --check                       # ok, or the refusal
python3 scripts/review_pin.py --check --all                 # every independent fault, one line each
python3 scripts/review_pin.py --lenses round --paths src/ui/a.c   # that pass's lenses with their questions
python3 scripts/review_pin.py --caps                        # pass_cap and no_progress_cap
python3 scripts/review-dispatch.py --check-pin --json [--pin .conclave/reviewers.toml]
```

`--check-pin --json` prints `{"ok": true, "schema_version": 1, "reviewers": {...}, "routes": {...}, "schedule": {...}, "clis": {"codex": true, "agy": false, "claude": true}}` and exits 0: `reviewers`, `routes` and `schedule` are exactly what the pin holds (`schedule` only when the pin has one, with every key of either shape), and `clis` says which reviewer CLIs are on `PATH`. A CLI is looked for only in the absolute directories on `PATH`, never in the working directory, so a `codex.cmd` committed to the reviewed repository is neither counted nor run. A refused or missing pin prints `{"ok": false, "error": "<message>"}`, the message a review run would refuse with, and exits 2. Without `--json` it prints `ok` or `refused: <message>`.

To read the recorded passes back without running a reviewer:

```bash
python3 scripts/review-dispatch.py --list-rounds --json [--records docs/reviews]
```

It prints `{"records": [{"path", "rounds": [...], "plans": [...], "completions": [...], "reconciliations": [...]}]}` (the last three only when the file holds them), each entry with `reviewer`, `model`, `cli`, `writer`, `run`, `candidate`, `effort`, `lenses` and `skipped`, with `reviewer`, `model` and `cli` null for a pass no reviewer returned, and adds `"unreadable": [path]` for a findings file whose headings or lines are not in the format `--record` writes. Each pass `--record` writes states how many lines its review has (`- Lines: N`) and a digest of them (`- Digest:`), and the reader skips exactly that many lines and checks the digest, so a review quoting `## Round ...` lines can never pass for a round, and a hand edit inside a review makes the file unreadable. The review is stored byte for byte. Text after a pass's review belongs to no pass: notes such as `- Implemented:` and `- Filed:` lines sit there. `--record` never appends to a findings file it cannot read back, and a write that fails still prints the review: the exit is 2.

Exit 0 is a review (which may still find problems). Exit 1 means the reviewer returned no review (an outage, a reply ending `OVERALL: blocked`, or under three-pass an incomplete reply), which is never an approval; the summary's `failover` names it and the reason. Exit 2 means the pin or the arguments were refused and nothing ran, or that the findings file could not be read back or written (the review still prints).
