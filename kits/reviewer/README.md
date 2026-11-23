# Reviewer kit

Additive overlay that gives a project independent review by a different model: one pin that names the reviewers and the review schedule, one command that runs a review pass, and a skill for Antigravity (`.agents/`), Claude (`.claude/`) and Codex (`.codex/`). The todo kit's `review-todo-section` uses it for every pass of a section.

## Who reviews whom

| Work written by | `--writer` | Reviewer |
| --- | --- | --- |
| Claude Code | `claude` | `astra`: GPT-6.2 Astra through `codex` |
| Antigravity | `agy` (or `gemini`) | `astra`: GPT-6.2 Astra through `codex` |

Claude Code and Antigravity are the two writers. Codex is reviewer only, through `astra` (`gpt-6.2-astra`, read-only sandbox). The default pin has no Codex writer route and no Antigravity reviewer. Astra uses medium effort for plan and initial round reviews, then low for completion and reconciliation. Routes, lenses and pass limits otherwise retain their existing behavior.

| Reviewer | CLI | Model | Effort |
| --- | --- | --- | --- |
| `astra` | `codex exec`, read-only sandbox | `gpt-6.2-astra` | `medium`, then `low` |

A route names exactly one reviewer, never of the writer's own model family: the pin refuses anything else. A reviewer that cannot review is no review, and no other reviewer runs in its place.

## Updating existing projects

Keep the Claude and Antigravity writer routes pointing to Astra. Remove the Codex writer route and unused Carbon reviewer from the project's pin. Restore medium plan/round effort and low completion/reconciliation effort without changing other lenses or limits. Remove Codex campaign shortcuts and keep the Claude and Carbon writer shortcuts. Existing projects own their copies and are not changed by an SDK update.

## The review schedule

The pin's `[schedule]` makes the dispatcher pick each pass's lenses and optional effort, so a section is reviewed the same way every time. The installed pin uses medium for Astra plan/initial round reviews and low for completion/reconciliation. It has two shapes.

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
- **Blocking levels and severity rubric.** `blocking = ["P1", "P2"]`: only those severities hold the stamp. A pass whose worst finding is below them is filed as tracked work and takes no further pass. Without the key every finding holds the stamp. Severity is graded by impact times likelihood under `SEVERITY_RUBRIC` in `scripts/review_pin.py`, which `scripts/review-dispatch.py` appends once to every pass: it grades and never filters, and requires `Path:` and `Evidence:` (`ran` or `traced`) on every `P1` and `P2`.
- **Caps.** `pass_cap` is the most returned passes a section may take in all (33 when absent). `recurrence_cap` (optional) stops the chain when one finding that holds the stamp has been reported open in that many passes: each reconciliation then ends with a `RECURRING:` line, and the count holds only as far as the passes its `(recurring: ...)` marks cite. `no_progress_cap` (optional) stops a run of reconciliations whose worst finding gets no less severe; it is blunter, since sections that ran many passes at one severity often went on to pass.
- **Conditional lenses.** A `[[schedule.conditional]]` entry (`lenses`, `passes`, `paths`) adds its lenses to the named passes only when a file the section changed starts with one of its repository-relative paths. A plan review, and a review outside a section, take the files from `--paths`.
- **Design by path.** The round's `design` is the one lens a conditional entry may repeat on the round, because the round has it only with `--surface`. A pin that names its UI, style, asset, icon and design contract folders in an entry with `lenses = ["design"]` and `passes = ["round", "reconciliation"]` gives the lens to any section that changed a file there, whatever its Surface field says, and the todo kit's stamp refuses such a section whose round or reconciliation was recorded without `LENS design:`. The plan review's counterpart is the built-in `design-plan` lens (`passes = ["plan"]`). The `design` and `source-defect` questions name no path: they point the reviewer at the design contract the candidate's Fidelity line names.
- **Lenses of your own.** `[schedule.lenses]` declares extra lens names with their questions, so a project adds a lens without editing the dispatcher.
- **C++ projects (opt-in safety lenses).** The template pin declares `thread-safety` and `memory-safety` under `[schedule.lenses]` without activating them on a fresh install. A C++ project opts in by uncommenting the C++ `[[schedule.conditional]]` block in `.conclave/reviewers.toml` and replacing the placeholder repository-relative prefixes (`src/`, `include/`) with its own C++ folders; both lenses then join `round` and `reconciliation` by path and add no pass:

| Opt-in lens | Scope | Joined passes |
| --- | --- | --- |
| `thread-safety` | Cross-thread state, lock order, wait, cancel, teardown | `round`, `reconciliation` |
| `memory-safety` | Pointer, view, handle, iterator lifetime; size/index/cast | `round`, `reconciliation` |

```toml
[[schedule.conditional]]
lenses = ["thread-safety", "memory-safety"]
passes = ["round", "reconciliation"]
paths = ["src/", "include/"]
```
- **Effort is optional** on reviewers and steps: a step without one passes no effort to the reviewer's CLI, whose own configuration then decides. For non-Orchestrator Antigravity reviewers (`agy`), the model name must end with every effort a three-pass schedule sets; Orchestrator models (`gemini-pro-orchestrator` and `gemini-pro-orchestrator-*`) require an effort-free schedule, and non-Orchestrator rotation schedules ignore step effort.

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

The design lens joins the rotation only with `--surface`. With `severity_stop_after = 0` the first round with no P1 or P2 finding ends the loop (the summary's `severity_stop` is true); the cap is 33 rounds. A rotation schedule takes none of the three-pass keys. A project on a rotation pin keeps it for as long as its pin says so. Orchestrator ignores the effort settings; other reviewers retain this cadence:

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

Upgrading an existing pin when `design-plan` became a built-in lens: if a project previously declared a custom `design-plan` entry under `[schedule.lenses]`, rename it (for example to `ui-plan`) and update any `[[schedule.conditional]]` or step references to that new name, or remove the custom declaration to use the built-in `design-plan` question.

## What lands

| Path | Role |
| ---- | ---- |
| `.conclave/reviewers.toml` | The reviewers, the route for each writer and the schedule |
| `scripts/review-dispatch.py` | Runs a pass and records it |
| `scripts/review_pin.py` | Loads and checks the pin; the one copy of its rules, copyable on its own |
| `scripts/review_layout.py` | The findings folder, `layout.receipts` in `todo/plan.json` (`docs/reviews` by default) |
| `scripts/review-prompt.py` | Fills a prompt template in `docs/` and writes the prompt to send |
| `scripts/tests/test_review_dispatch.py` | Routing, rotation schedule, failed-review and record tests |
| `scripts/tests/test_three_pass.py` | Three-pass order, pin, caps, blocking, lens verdict and path tests |
| `scripts/tests/test_review_pin.py` | Pin key, schedule, cap and lens verdict tests |
| `scripts/tests/test_review_prompt.py` | Prompt filling, its refusals and a dispatcher round trip |
| `docs/plan-review-prompt.md` | The plan review before the build |
| `docs/review-round-prompt.md` | The round prompt: candidate, lenses, severities, reply format |
| `docs/completion-review-prompt.md` | The completion and excellence review |
| `docs/reconciliation-review-prompt.md` | The pass after a completion with gaps (three-pass) |
| `.{agents,claude,codex}/skills/independent-review/` | When and how to get a review |

## Install

```powershell
python forge.py kit /path/to/project reviewer [--dry-run]
python forge.py doctor /path/to/project reviewer
```

The doctor loads the pin under the dispatcher's own rules and reports any reviewer CLI that is not installed (a pass routed to that reviewer has no review). Operator globals: the `codex`, `agy` and `claude` CLIs, signed in.

## Running a pass

Fill the prompt first. `scripts/review-prompt.py` reads the template for `--kind` from `docs/`, replaces every placeholder and writes the prompt with an atomic write; a placeholder it has no value for, a malformed SHA, a missing template or an unwritable `--out` is a refusal (exit 2, nothing written, an existing `--out` untouched). `--ref` names the TODO section and, when `scripts/todo-graph.py` is beside it, finds the TODO file (pass `--todo` otherwise); without `--ref` the TODO lines are dropped, which is right for a review outside a section. `--base` makes the candidate a range, and `--fidelity` names a design source on every kind (a blank `--fidelity` is refused): with `--ref`, no `--fidelity` and `scripts/todo-graph.py` beside it, the filler reads the section's own `**Fidelity:**` value on `Surface: yes` (from the `--candidate` commit when inside a git repository), writes `none (Surface: no)` only on an explicit, unambiguous `Surface: no`, and refuses a missing section body, a missing or ambiguous `Surface` field, or a `Surface: yes` section that names no one Fidelity:

```bash
python3 scripts/review-prompt.py --kind round --candidate <40-char SHA> --ref "D<NN> T<NN> §<N>" --purpose "<one or two sentences>" --governing <the spec or plan> --out <scratch>/round.md
python3 scripts/review-prompt.py --kind reconciliation --candidate <repaired SHA> --ref "D<NN> T<NN> §<N>" --failed <completion SHA> [--last <last reviewed SHA>] --findings docs/reviews/<NN-domain>/D<NN>-T<NN>-s<N>.md --gates <scratch>/gates.txt --governing <the spec or plan> --out <scratch>/reconciliation.md
```

`plan` and `completion` fill the same way (`--purpose` is for `round` and `completion`; `--gates`, `--findings`, `--failed` and `--last` are for `reconciliation`). Each template's header still says how to fill it by hand.

Then run the pass, naming your own agent as the writer (`claude`, `codex` or `agy`):

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
python3 scripts/review_pin.py --lenses round --no-surface --paths src/ui/a.c   # as a Surface: no section gets them
python3 scripts/review_pin.py --caps                        # pass_cap, no_progress_cap and recurrence_cap
python3 scripts/review-dispatch.py --check-pin --json [--pin .conclave/reviewers.toml]
```

`--check-pin --json` prints `{"ok": true, "schema_version": 1, "reviewers": {...}, "routes": {...}, "schedule": {...}, "clis": {"codex": true, "agy": false, "claude": true}}` and exits 0: `reviewers`, `routes` and `schedule` are exactly what the pin holds (`schedule` only when the pin has one, with every key of either shape), and `clis` says which reviewer CLIs are on `PATH`. A CLI is looked for only in the absolute directories on `PATH`, never in the working directory, so a `codex.cmd` committed to the reviewed repository is neither counted nor run. A refused or missing pin prints `{"ok": false, "error": "<message>"}`, the message a review run would refuse with, and exits 2. Without `--json` it prints `ok` or `refused: <message>`.

To read the recorded passes back without running a reviewer:

```bash
python3 scripts/review-dispatch.py --list-rounds --json [--records docs/reviews]
```

It prints `{"records": [{"path", "rounds": [...], "plans": [...], "completions": [...], "reconciliations": [...]}]}` (the last three only when the file holds them), each entry with `reviewer`, `model`, `cli`, `writer`, `run`, `candidate`, `effort`, `lenses` and `skipped`, with `reviewer`, `model` and `cli` null for a pass no reviewer returned, and adds `"unreadable": [path]` for a findings file whose headings or lines are not in the format `--record` writes. Each pass `--record` writes states how many lines its review has (`- Lines: N`) and a digest of them (`- Digest:`), and the reader skips exactly that many lines and checks the digest, so a review quoting `## Round ...` lines can never pass for a round, and a hand edit inside a review makes the file unreadable. The review is stored byte for byte. Text after a pass's review belongs to no pass: notes such as `- Implemented:` and `- Filed:` lines sit there. `--record` never appends to a findings file it cannot read back, and a write that fails still prints the review: the exit is 2.

Exit 0 is a review (which may still find problems). Exit 1 means the reviewer returned no review (an outage, a reply ending `OVERALL: blocked`, or under three-pass an incomplete reply), which is never an approval; the summary's `failover` names it and the reason. Exit 2 means the pin or the arguments were refused and nothing ran, or that the findings file could not be read back or written (the review still prints).
