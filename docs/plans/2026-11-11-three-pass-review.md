# Three-pass review in the reviewer and todo kits

Date: 2026-11-11. Owner request, same day. Built through `todo/00-reviewer/`.

## Why

RasterFold and Impossible OS already review each TODO section in three passes (one plan review, one combined round, one completion review, then reconciliation passes after a completion with gaps). The kits still ship only the rotation schedule (three rounds at falling effort, then one lens per round, up to 33 rounds). This plan brings the kits up to the three-pass shape and adds five improvements to the pin, so both projects can take a copy afterwards. Files are copied between repositories, never linked.

## Sources

- RasterFold `scripts/review-dispatch.py` (commit `b334933`): the newer source for three-pass.
- Impossible OS `scripts/review_pin.py` (staged in its repair clone, 2026-11-11): the reference for the new keys and their validation. Its one-writer rule and its missing `effort` key are that project's own and are not copied.

## Requirements

- R1: `policy = "three-pass"` in `[schedule]`: the kinds plan, round, completion and reconciliation, run in that order for a section's findings file, refused before a review is spent when out of order.
- R2: a section keeps the pin at its plan review's candidate (schedule and route), in the dispatcher and in the stamp.
- R3: a section that has spent its passes is refused a further reconciliation.
- R4: the rotation schedule keeps loading and working: a rotation pin, and a pin without `pass_cap`, behave as before.
- R5: pin handling lives in `scripts/review_pin.py` (load, validate, schedule lookup, caps), imported by `review-dispatch.py` and by the todo kit's graph. It holds no project path or rule, so a project can copy that one file.
- R6 (one owner per lens): under three-pass, completion may carry its own lenses, and a lens listed in more than one of plan, the round and completion is refused. Reconciliation may repeat lenses.
- R7 (one verdict per lens): the dispatcher appends each scheduled lens with its question and requires `LENS <name>: clean` or `LENS <name>: findings` for each. A returned review missing a lens line is recorded as incomplete, never as clean.
- R8 (conditional lenses): `[[schedule.conditional]]` with `lenses`, `passes` and `paths` (repository-relative prefixes) adds its lenses to the named passes only when the section's changed files fall under a path. `--surface` keeps working for pins without it. `[schedule.lenses]` declares extra lens names with their questions.
- R9 (blocking levels): `blocking = ["P1", "P2"]` under `[schedule]`: only those levels hold the stamp, `P1` must be among them, and a review whose `HIGHEST` is below them does not trigger another pass.
- R10 (caps and effort): `pass_cap` under `[schedule]` replaces the constant 33 (absent reads as 33), `no_progress_cap` is optional, and `effort` is optional on reviewers and schedule steps (absent: no effort flag, the reviewer CLI's own configuration decides). Under three-pass an Antigravity reviewer's model name must agree with every effort the schedule sets.
- R11: every new key refuses a wrong value (type, unknown name, duplicate, out of range) with a message naming the key.
- R12: the `--check-pin --json` contract gains the new keys without breaking a reader of the current contract; its fixtures live in `tests/fixtures/check-pin/` and gain a three-pass pin.
- R13: the todo kit's stamp accepts the three-pass chain (plan, one round, completion, reconciliations up to the pin's cap) and holds each pass to the section's pin.
- R14: the template pin, both kit READMEs, the `review-todo-section`, `process-todo-section`, `groom-plan` and `independent-review` skills in `.agents`, `.claude` and `.codex`, and the four prompt templates describe the three-pass shape.
- R15: the SDK's own installed copies match the kits.

## Decisions

- The pin stays `schema_version = 1`: every new key is optional, so an existing pin loads unchanged.
- New installs start on three-pass (the template pin). Reason: it is the shape both downstream projects run, and it bounds a section at three passes when nothing is wrong, where rotation runs until a round is clean. A project on the rotation pin keeps it until it edits its own pin.
- The new keys (`blocking`, `pass_cap`, `no_progress_cap`, `conditional`, `lenses`) and the lens verdict lines belong to three-pass only, so rotation behaviour does not move. `effort` is optional under both.
- The VS Code extension was removed on 2026-11-11 (owner decision), so nothing in this plan touches an editor.

## Not ported from RasterFold

Its Muse reviewer CLI, its retired writer keys, its Codex to Carbon route, its Win32 job object process cleanup and its `review-prompt.py` prompt filler are that project's own choices or separate work, and stay out of this plan.
