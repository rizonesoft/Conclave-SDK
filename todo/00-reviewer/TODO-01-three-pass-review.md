---
schema_version: 1
id: three-pass-review
domain: 00-reviewer
status: active
title: "TODO-01 -- Three-pass review"
---

# TODO-01 -- Three-pass review

> **Goal:** The reviewer and todo kits run the three-pass review (plan, one combined round, completion, reconciliations up to a cap read from the pin) beside the older rotation schedule, with the pin handled by one copyable loader that also carries lens owners, lens verdict lines, conditional lenses, blocking levels and optional effort.

> **Current state:** Measured 2026-11-11. `kits/reviewer/templates/scripts/review-dispatch.py` (859 lines) loads the pin itself and knows only the rotation schedule (`check_schedule`, `scheduled`), with the kinds round, completion and plan. `kits/todo/templates/scripts/lib/todo_graph.py` stamps against that schedule with `REVIEW_ROUND_CAP = 33` and checks the pin at the stamped commit. There is no `review_pin.py`, no reconciliation kind and no `docs/reconciliation-review-prompt.md`. The `--check-pin` fixtures are in `tests/fixtures/check-pin/`.

## Inputs

- `docs/plans/2026-11-11-three-pass-review.md`: requirements R1 to R15 and the decisions each section cites.
- `kits/reviewer/templates/scripts/review-dispatch.py` and its tests in `kits/reviewer/templates/scripts/tests/test_review_dispatch.py`: the dispatcher every section changes or reads.
- `kits/todo/templates/scripts/lib/todo_graph.py` and `tests/test_todo_graph.py`: the stamp rules §3 changes.
- `tests/test_check_pin_contract.py` and `tests/fixtures/check-pin/`: the `--check-pin --json` contract §2 extends.

## Outcome

- A pin with `policy = "three-pass"` runs plan, round, completion and reconciliation passes in order, refuses a pass out of order or past the cap, and stamps; a rotation pin behaves as it did.
- `scripts/review_pin.py` is the only place the pin's rules live, and `python -m unittest discover -s tests -v` passes with the SDK's installed copies equal to the kits.

**Adjacency:** all=not-applicable (developer tooling: a pin loader, a review dispatcher and stamp rules, with no records a user lists, exports, is notified of or reverses)

**Adjacency rationale:** The settings this work adds are the pin's own keys, each consumed by the loader and proven by a refusal test in §1; the audit trail is the findings file the dispatcher already writes.

## Implementation Order

| Order | Section | Deliverable | Depends On | Status |
| ----- | ------- | ----------- | ---------- | ------ |
| 1 | §1 | Pin loader module with the three-pass keys | -- | [ ] |
| 2 | §2 | Three-pass dispatcher | §1 | [ ] |
| 3 | §3 | Three-pass stamp rules in the todo kit | §2 | [ ] |
| 4 | §4 | Template pin, prompts, skills and READMEs on three-pass | §3 | [ ] |

## 1. Pin loader module with the three-pass keys

> **Started:** 2026-11-11T08:45:37Z

Pin handling moves out of the dispatcher into `review_pin.py` and learns the three-pass policy and the new keys (R4 to R11). The dispatcher imports it and its behaviour on a rotation pin does not change. The module names no project path or rule beyond the conventional pin location beside its own folder.

**Phase:** 0
**Needs:** none
**Surface:** no

**Build order:**

1. Create `kits/reviewer/templates/scripts/review_pin.py` with `Refused`, `load_pin`, `check_schedule`, the lens table, `scheduled`, the caps and the blocking and lens verdict helpers. Done when: `python kits/reviewer/templates/scripts/review_pin.py --check --pin kits/reviewer/templates/.conclave/reviewers.toml` prints `ok`.
2. Make `kits/reviewer/templates/scripts/review-dispatch.py` load the module from its own folder and drop its copy of the rules. Done when: the existing dispatcher tests pass with their behavioural assertions kept. **Corrected 2026-11-11 (plan review):** said "pass unchanged"; the test harness must copy `review_pin.py` beside the dispatcher, and the assertions that a missing `effort` refuses become assertions that it loads (plan R10).
3. Add `kits/reviewer/templates/scripts/tests/test_review_pin.py` and install the file through `kits/reviewer/scripts/install.sh` and `forge.py self-sync`. Done when: the checkpoint passes.

- [x] Move `load_pin`, `check_step`, `check_schedule`, `LENSES`, `highest`, `returned_review` and `scheduled` into `kits/reviewer/templates/scripts/review_pin.py`, loaded by `review-dispatch.py` from its own folder by file path (plan R5). Done when: `review-dispatch.py` defines none of them itself, the `Harness` in `test_review_dispatch.py` copies `review_pin.py` into its scratch repository, and `python -m unittest discover -s kits/reviewer/templates/scripts/tests` passes with no behavioural assertion removed except the missing-effort refusals (plan R10). **Corrected 2026-11-11 (plan review):** the harness change was not named. Cheaper substitute: a second copy of the rules left in the dispatcher must fail review.
- [x] Accept `policy = "three-pass"` in `check_schedule` of `review_pin.py`: `plan`, exactly one `rounds` entry, `completion` and `reconciliation`, with `lenses` optional on `completion` (plan R1, R6). Done when: a test loads such a pin and a second round, a missing `reconciliation` and an unknown `policy` each refuse with a message naming the key. Cheaper substitute: accepting any `policy` string must fail.
- [x] Refuse a lens listed in more than one of plan, the round and completion under three-pass, and allow reconciliation to repeat lenses, in `review_pin.py` (plan R6). Done when: a test with `plan-delivery` in both the round and completion refuses naming the lens, and the same lens in reconciliation loads.
- [x] Add `[schedule.lenses]` (extra lens names with questions) to `review_pin.py` and resolve every schedule lens against the built-in table plus it (plan R8). Done when: tests refuse a non-string question, a malformed name and a name that redefines a built-in lens, each naming `[schedule.lenses]`, and a schedule may name a declared lens.
- [x] Add `[[schedule.conditional]]` (`lenses`, `passes`, `paths`) and `lenses_for(schedule, kind, changed_paths)` to `review_pin.py` (plan R8). Done when: tests show the lenses join only a named pass with a changed file under a path, and refuse a wrong type, an unknown pass, an absolute or `..` path, a duplicate and a lens the pass always has.
- [x] Add `blocking` and `blocks(schedule, highest)` to `review_pin.py` (plan R9). Done when: tests refuse a list without `P1`, an unknown level, a duplicate and a non-list, each naming `blocking`, and `blocks` is true for `P1` and `P2` and false for `P3` and `none` under `["P1", "P2"]`, true for a review with no `HIGHEST` line, and true for every level when the key is absent. **Corrected 2026-11-11 (plan review):** added the positive cases, so a `blocks` that always returns false fails.
- [x] Add `pass_cap` (3 to 999, absent reads as 33) and optional `no_progress_cap` (1 to `pass_cap`) with `pass_cap(schedule)` and `no_progress_cap(schedule)` in `review_pin.py` (plan R10). Done when: tests refuse `pass_cap` of `true`, `2` and `1000` and `no_progress_cap` of `true`, `0` and one above `pass_cap`, each naming its key; `pass_cap = 45` reads 45 and a pin without the key reads 33; `no_progress_cap = 3` reads 3 and a pin without it reads `None`. **Corrected 2026-11-11 (plan review):** added the configured-value reads and the `no_progress_cap` lower bound, type and absent result.
- [x] Make `effort` optional on a non-Antigravity reviewer and on every schedule step in `review_pin.py`, and under three-pass refuse an Antigravity model name that disagrees with an effort the schedule sets (plan R10). Done when: tests load a pin with no effort anywhere, refuse an invalid effort naming the step, and refuse `gemini-4-argon-high` against a `medium` step.
- [x] Refuse the three-pass keys on a rotation schedule in `review_pin.py`, so a rotation pin means what it meant (plan R4). Done when: a test loads the shipped rotation pin with `scheduled` returning the same steps as before, and a rotation schedule with `pass_cap` refuses with the existing "needs exactly" message.
- [x] Add `lens_block` and `missing_lens_verdicts` to `review_pin.py`: the prompt text naming each lens, its question and the `LENS <name>: clean` or `LENS <name>: findings` line it owes, and the lenses a reply gave no line for (plan R7). Done when: tests show the block holds each scheduled lens's question (a built-in one and one declared in `[schedule.lenses]`) and its `LENS <name>:` line, a reply missing one lens line names that lens, a line with another value (`LENS quality: maybe`) does not count, and a reply with every line names none. **Corrected 2026-11-11 (plan review):** added the prompt content and the invalid verdict value.
- [x] Add a `--check`, `--lenses <kind>` and `--caps` command line to `review_pin.py` with `--pin <path>`: `--lenses` prints one `name: question` line per lens of that pass, the conditional ones only for the files given with `--paths`, and `--caps` prints `pass_cap N` and `no_progress_cap N` (or `none`). Done when: a test asserts the exact lines for a three-pass pin with and without `--paths`, the configured caps, and that `--check` exits 2 with the refusal on a bad pin. **Corrected 2026-11-11 (plan review):** the output was undefined and conditional lenses had no input.
- [x] Write `kits/reviewer/templates/scripts/tests/test_review_pin.py` covering every item above. Done when: `python -m unittest discover -s kits/reviewer/templates/scripts/tests -p test_review_pin.py` passes and fails when a refusal is removed.
- [x] Install `review_pin.py` and its test: `kits/reviewer/scripts/install.sh` copies the template tree recursively, so add fresh-install assertions for both files to `kits/reviewer/scripts/test-install.sh`, name them in `kits/reviewer/README.md`, and run `python forge.py self-sync`. Done when: `bash kits/reviewer/scripts/test-install.sh` passes and fails with `review_pin.py` removed from the template, `scripts/review_pin.py` equals the kit file, and `python -m unittest discover -s tests` passes. **Corrected 2026-11-11 (plan review):** said the installer lists files; it discovers them. Cheaper substitute: copying the file into the SDK by hand without the install assertion must fail review.
- [ ] Commit: `reviewer: move pin handling into review_pin.py with the three-pass keys`

**Test checkpoint:** `python -m unittest discover -s kits/reviewer/templates/scripts/tests` and `python -m unittest discover -s tests` both end `OK`, and `bash kits/reviewer/scripts/test-install.sh` passes; removing the one-owner check from `review_pin.py` makes `test_review_pin.py` fail.

## 2. Three-pass dispatcher

The dispatcher runs the three-pass kinds from the pin §1 loads: order, the section's own pin, the pass cap, lens verdict lines, conditional lenses from the candidate's changed files, blocking levels and optional effort (R1 to R3, R7 to R10, R12).

**Phase:** 0
**Needs:** none
**Surface:** no

**Build order:**

1. Add the reconciliation kind, the round `Candidate` line and `returned_one_pass` to `kits/reviewer/templates/scripts/review-dispatch.py`. Done when: a reconciliation is recorded and read back.
2. Add `section_pin`, `check_three_pass_order` and the changed-file lookup, and wire them in `main`. Done when: an out-of-order pass refuses before a reviewer starts.
3. Extend `tests/test_check_pin_contract.py` and `tests/fixtures/check-pin/`. Done when: the checkpoint passes.

- [ ] Add `--kind reconciliation` to `review-dispatch.py`, recorded as `## Reconciliation review` and listed by `--list-rounds` (plan R1). Done when: a test records two reconciliations in one findings file and reads both back. Cheaper substitute: recording it as a completion review must fail.
- [ ] Record an optional `- Candidate:` line on a round in `review-dispatch.py` and accept `--candidate` with `--kind round` (plan R1). Done when: a test reads the candidate back and a malformed SHA is refused.
- [ ] Add `valid_one_pass_footer` and `returned_one_pass` to `review-dispatch.py` and use them where a one-pass review is counted. Done when: a completion reply without its `COMPLETION:` line does not block a later completion pass.
- [ ] Add `section_pin` to `review-dispatch.py`: the pin at the returned plan review's candidate, read with `git show`, else the current pin (plan R2). Done when: a test changes the committed pin after a plan review and the next pass runs under the earlier pin.
- [ ] Add `check_three_pass_order` to `review-dispatch.py` for a section findings file: plan first, one round on a descendant candidate, one completion, reconciliations only after gaps (plan R1). Done when: tests refuse a second plan review, a round before the plan, a second round, a completion before the round and a reconciliation after `COMPLETION: complete`, each before a reviewer runs.
- [ ] Refuse a reconciliation once the section has spent `pass_cap` returned passes, or `no_progress_cap` passes in a row without progress, in `review-dispatch.py` (plan R3, R10). Done when: a test with `pass_cap = 4` refuses the second reconciliation naming the cap, and the same file under a cap of 5 runs it.
- [ ] Refuse a reconciliation after a pass whose `HIGHEST` is below the pin's `blocking` levels, and report `blocking` in the JSON summary, in `review-dispatch.py` (plan R9). Done when: a test with `blocking = ["P1", "P2"]` refuses a reconciliation after a completion ending `HIGHEST: P3` then `COMPLETION: gaps`, and runs it after `HIGHEST: P2`.
- [ ] Append the lens block from `review_pin.lens_block` and record a three-pass reply missing a lens line or its final verdict line as no review, keeping its text and naming the reason, in `review-dispatch.py` (plan R7). Done when: a test round whose reply lacks one `LENS` line is recorded as `## Round 1: none` with the lens named, exits 1 and does not count as the section's round.
- [ ] Compute a section pass's changed files as `git diff --name-only <plan candidate> <candidate>` and take `--paths` for a plan review or a standalone review, in `review-dispatch.py` (plan R8). Done when: tests show a conditional lens joins a round whose candidate changed a file under its path and not one that did not, and `--surface` still gates `design` on a pin without conditional entries.
- [ ] Pass no effort flag to Codex or Claude Code when neither the step nor the reviewer sets one, in `command` of `review-dispatch.py` (plan R10). Done when: a test argv for each CLI has no effort argument and the record has no `- Effort:` line.
- [ ] Read a recorded `- Lenses:` line with any well-formed distinct names in `review-dispatch.py`, so a pin-declared lens reads back. Done when: a test records and reads a round with a declared lens.
- [ ] Extend `tests/test_check_pin_contract.py` and `tests/fixtures/check-pin/pins/` with a valid three-pass pin and one refused pin per new key, with `schedule` reported when the pin has one (plan R12). Done when: every existing fixture keeps its verdict and the new ones give theirs. Cheaper substitute: editing an existing fixture's expected verdict must fail review.
- [ ] Update the module docstring of `review-dispatch.py` and run `python forge.py self-sync`. Done when: `scripts/review-dispatch.py` equals the kit file.
- [ ] Commit: `reviewer: three-pass kinds, order, caps and lens verdicts in the dispatcher`

**Test checkpoint:** `python -m unittest discover -s kits/reviewer/templates/scripts/tests` and `python -m unittest discover -s tests` both end `OK`; removing the cap check from `check_three_pass_order` makes the cap test fail.

## 3. Three-pass stamp rules in the todo kit

`stamp` accepts the three-pass chain and holds every pass to the pin the section began under (R2, R13).

**Phase:** 0
**Needs:** none
**Surface:** no

**Build order:**

1. Teach `kits/todo/templates/scripts/lib/todo_graph.py` the section pin and the `reconciled` verdict. Done when: a three-pass receipt validates.
2. Add the chain check and the cap from the pin. Done when: a receipt past the cap refuses.
3. Cover both policies in `tests/test_todo_graph.py`. Done when: the checkpoint passes.

- [ ] Load `review_pin.py` in `todo_graph.py` beside the dispatcher and read the section's pin at its plan review's candidate, recording it as `schedule_sha` in new receipts (plan R2, R5). Done when: a test changes the pin after the plan review and the stamp still checks the earlier schedule, and a receipt without `schedule_sha` is still held to the stamped commit's pin. Cheaper substitute: reading the working tree's pin must fail.
- [ ] Add the completion verdict `reconciled` to `completion_record` in `todo_graph.py`: a returned reconciliation ending `RECONCILIATION: complete`, the last one, on the stamped candidate (plan R13). Done when: tests accept it and refuse it with no reconciliation or with one ending gaps.
- [ ] Add `three_pass_ok` to `todo_graph.py`: one plan review, exactly one returned round with a candidate, one completion, reconciliations up to the pin's `pass_cap`, each on a candidate at or after the one before, the last on the stamped commit (plan R13). Done when: tests refuse two rounds, a round without a candidate, a chain out of order and a chain over a `pass_cap` of 4.
- [ ] Accept the three-pass round verdict `fixed` as the loop's last, and under `blocking` accept `filed` when the last pass ended gaps below the blocking levels with its `- Filed:` lines, in `todo_graph.py` (plan R9). Done when: tests accept both and refuse `filed` after a pass whose `HIGHEST` is `P1`.
- [ ] Replay each three-pass pass's lenses with the conditional lenses for its changed files, and skip the effort comparison for a step that sets none, in `schedule_ok` of `todo_graph.py` (plan R8, R10). Done when: tests refuse a round recorded without a conditional lens its changed files call for, and accept a pass with no effort under a pin that sets none.
- [ ] Refuse a section contract that changed between a failed completion and its reconciliation, in `todo_graph.py`. Done when: a test that edits a `Done when:` between the two refuses and one that only ticks boxes passes.
- [ ] Keep every rotation receipt valid: run the existing stamp tests unchanged in `tests/test_todo_graph.py` (plan R4). Done when: they pass with no edit to their expectations. Cheaper substitute: loosening an existing assertion must fail review.
- [ ] Read `kits/todo/templates/scripts/campaign_guard.py` for anything that names the round cap or the schedule and correct it. Done when: `tests/test_campaign_guard.py` passes and the file states no cap of its own.
- [ ] Run `python forge.py self-sync`. Done when: `scripts/lib/todo_graph.py` equals the kit file.
- [ ] Commit: `todo: stamp the three-pass chain against the section's own pin`

**Test checkpoint:** `python -m unittest discover -s tests` ends `OK`; removing the cap check from `three_pass_ok` makes its test fail.

## 4. Template pin, prompts, skills and READMEs on three-pass

Everything a project reads when it installs the kits describes the three-pass shape, and new installs start on it (R14, R15).

**Phase:** 0
**Needs:** none
**Surface:** no

**Build order:**

1. Rewrite `kits/reviewer/templates/.conclave/reviewers.toml` as a three-pass pin with the decision recorded. Done when: `--check-pin` prints `ok` for it.
2. Update the prompts and add `kits/reviewer/templates/docs/reconciliation-review-prompt.md`. Done when: each prompt names its final verdict lines.
3. Update the skills and READMEs, then `python forge.py self-sync`. Done when: the checkpoint passes.

- [ ] Rewrite `kits/reviewer/templates/.conclave/reviewers.toml` as a three-pass pin: `pass_cap`, `blocking`, completion lenses `plan-delivery` and `record`, a conditional `design` entry left as a commented example, and a comment recording that new installs start on three-pass and how to keep rotation (plan Decisions). Done when: `python kits/reviewer/templates/scripts/review-dispatch.py --check-pin --pin kits/reviewer/templates/.conclave/reviewers.toml` prints `ok`. Cheaper substitute: leaving the rotation pin with a comment must fail.
- [ ] Add `kits/reviewer/templates/docs/reconciliation-review-prompt.md` and list it in `kits/reviewer/scripts/install.sh`, `kits/reviewer/scripts/test-install.sh` and the `forge.py` kit manifest if one names the prompts. Done when: the install test finds it in a fresh install.
- [ ] Update `plan-review-prompt.md`, `review-round-prompt.md` and `completion-review-prompt.md` in `kits/reviewer/templates/docs/` for the lens verdict lines, the `HIGHEST:` line and the three-pass order (plan R7, R9). Done when: each names the lines the dispatcher checks and none promises a 33-round loop as the only shape.
- [ ] Rewrite `kits/reviewer/README.md` for both policies: the pin keys, the passes, the lens verdict lines, conditional lenses, blocking, the caps, `review_pin.py` and how an existing pin moves to three-pass. Done when: every table row is at most 100 characters and every key the loader accepts is named.
- [ ] Update the `independent-review` skill in `.agents`, `.claude` and `.codex` under `kits/reviewer/templates/`. Done when: the three files state the same rules and name `--kind reconciliation`.
- [ ] Update the `review-todo-section`, `process-todo-section` and `groom-plan` skills in `.agents`, `.claude` and `.codex` under `kits/todo/templates/` for the three-pass flow, keeping the rotation flow for pins that use it (plan R14). Done when: each agent's copy describes plan, round, completion, reconciliation, the cap from the pin and the stamp arguments for both policies.
- [ ] Update `kits/todo/README.md`, `kits/todo/templates/docs/todo-workflow.md` and `kits/todo/templates/todo/README.md` where they describe review rounds. Done when: none states 33 rounds as the only rule.
- [ ] Run `python forge.py self-sync` and copy the kits' `docs/` prompts and the template pin into the SDK's own `docs/` and `.conclave/reviewers.toml` (plan R15). Done when: `python -m unittest discover -s tests` passes and `git diff --no-index` between each kit file and its installed copy is empty.
- [ ] Commit: `reviewer, todo: template pin, prompts, skills and READMEs on three-pass`

**Test checkpoint:** `python -m unittest discover -s tests` ends `OK` and `python scripts/review-dispatch.py --check-pin` prints `ok`; a prompt or skill left unsynced makes the self-sync test fail.

## Verification

- A scratch repository with the template pin runs plan, round, completion and reconciliation through `scripts/review-dispatch.py` with a stub reviewer and stamps the section; the same run with the rotation pin stamps as before.
- `python -m unittest discover -s tests -v` passes.
- `python scripts/todo-graph.py validate` and `python scripts/todo-graph.py plan --check` pass.
