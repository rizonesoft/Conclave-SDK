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

**Adjacency:** all=not-applicable (developer tooling: a pin loader, a review dispatcher and stamp rules; the records it keeps are its own findings files, which `query rounds` lists with any chain `replan` kept, and no user exports, is notified of or reverses them)

**Corrected 2026-11-19:** the Adjacency line said the tooling keeps "no records a user lists"; since `D00 T01 §9`, `query rounds` lists each section's kept review chains, so the line names them (the completion review of §9).

**Adjacency rationale:** The settings this work adds are the pin's own keys, each consumed by the loader and proven by a refusal test in §1; the audit trail is the findings file the dispatcher already writes.

## Implementation Order

| Order | Section | Deliverable | Depends On | Status |
| ----- | ------- | ----------- | ---------- | ------ |
| 1 | §1 | Pin loader module with the three-pass keys | -- | [x] |
| 2 | §2 | Three-pass dispatcher | §1 | [x] |
| 3 | §3 | Three-pass stamp rules in the todo kit | §2 | [x] |
| 4 | §4 | Template pin, prompts, skills and READMEs on three-pass | §3 | [x] |
| 5 | §5 | Pin check that reports every fault at once | §1 | [x] |
| 6 | §6 | Reviewer process tree ended on Windows by a job object | §2 | [x] |
| 7 | §7 | Review prompt filler | §2 | [x] |
| 8 | §8 | Stamp that recovers from a write cut short | §3 | [x] |
| 9 | §9 | Re-plan route for a chain that cannot settle, recovery planned up front | §4 | [ ] |
| 10 | §10 | P2 gate by kind with two filing caps | §9 | [ ] |

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
- [x] Commit: `reviewer: move pin handling into review_pin.py with the three-pass keys`

**Test checkpoint:** `python -m unittest discover -s kits/reviewer/templates/scripts/tests` and `python -m unittest discover -s tests` both end `OK`, and `bash kits/reviewer/scripts/test-install.sh` passes; removing the one-owner check from `review_pin.py` makes `test_review_pin.py` fail.

> **Verified:** 2026-11-11 | §1 | 0ecf0655c9dc685e985a604755e1215767eed3f0
> **Review:** `docs/reviews/d00-t01-s1.json`

## 2. Three-pass dispatcher

> **Started:** 2026-11-11T10:16:17Z

The dispatcher runs the three-pass kinds from the pin §1 loads: order, the section's own pin, the pass cap, lens verdict lines, conditional lenses from the candidate's changed files, blocking levels and optional effort (R1 to R3, R7 to R10, R12).

**Phase:** 0
**Needs:** none
**Surface:** no

**Build order:**

1. Add the reconciliation kind, the round `Candidate` line and `returned_one_pass` to `kits/reviewer/templates/scripts/review-dispatch.py`. Done when: a reconciliation is recorded and read back.
2. Add `section_pin`, `check_three_pass_order` and the changed-file lookup, and wire them in `main`. Done when: an out-of-order pass refuses before a reviewer starts.
3. Extend `tests/test_check_pin_contract.py` and `tests/fixtures/check-pin/`. Done when: the checkpoint passes.

- [x] Add `--kind reconciliation` to `review-dispatch.py`, recorded as `## Reconciliation review` and listed by `--list-rounds` (plan R1). Done when: a test records two reconciliations in one findings file and reads both back. Cheaper substitute: recording it as a completion review must fail.
- [x] Record an optional `- Candidate:` line on a round in `review-dispatch.py` and accept `--candidate` with `--kind round` (plan R1). Done when: a test reads the candidate back and a malformed SHA is refused.
- [x] Add `valid_one_pass_footer` and `returned_one_pass` to `review-dispatch.py` and use them where a one-pass review is counted. Done when: a completion reply without its `COMPLETION:` line does not block a later completion pass.
- [x] Add `section_pin` to `review-dispatch.py`: the pin at the returned plan review's candidate, read with `git show`, else the current pin (plan R2). Done when: a test changes the committed pin after a plan review and the next pass runs under the earlier pin.
- [x] Add `check_three_pass_order` to `review-dispatch.py` for a section findings file: plan first, one round on a descendant candidate, one completion, reconciliations only after gaps (plan R1). Done when: tests refuse a second plan review, a round before the plan, a second round, a completion before the round and a reconciliation after `COMPLETION: complete`, each before a reviewer runs.
- [x] Refuse a reconciliation once the section has spent `pass_cap` returned passes, or `no_progress_cap` passes in a row without progress, in `review-dispatch.py` (plan R3, R10). Done when: a test with `pass_cap = 4` refuses the second reconciliation naming the cap, and the same file under a cap of 5 runs it.
- [x] Refuse a reconciliation after a pass whose `HIGHEST` is below the pin's `blocking` levels, and report `blocking` in the JSON summary, in `review-dispatch.py` (plan R9). Done when: a test with `blocking = ["P1", "P2"]` refuses a reconciliation after a completion ending `HIGHEST: P3` then `COMPLETION: gaps`, and runs it after `HIGHEST: P2`.
- [x] Append the lens block from `review_pin.lens_block` and record a three-pass reply missing a lens line or its final verdict line as no review, keeping its text and naming the reason, in `review-dispatch.py` (plan R7). Done when: a test round whose reply lacks one `LENS` line is recorded as `## Round 1: none` with the lens named, exits 1 and does not count as the section's round.
- [x] Compute a section pass's changed files as `git diff --name-only <plan candidate> <candidate>` and take `--paths` for a plan review or a standalone review, in `review-dispatch.py` (plan R8). Done when: tests show a conditional lens joins a round whose candidate changed a file under its path and not one that did not, and `--surface` still gates `design` on a pin without conditional entries.
- [x] Pass no effort flag to Codex or Claude Code when neither the step nor the reviewer sets one, in `command` of `review-dispatch.py` (plan R10). Done when: a test argv for each CLI has no effort argument and the record has no `- Effort:` line. **Corrected 2026-11-11:** shipped with §1 in `b7a6324` and `0ecf065` (`test_a_reviewer_without_an_effort_runs_with_no_effort_argument`, `test_a_scheduled_step_without_an_effort_passes_none_whatever_the_reviewers`), because the loader change would otherwise have passed `None` as an effort.
- [x] Accept `agy` as a writer name in `review_pin.py` and `--writer` of `review-dispatch.py`, with `gemini` kept as an alias of the same writer (owner decision 2026-11-11): a route under either name serves both, and a pin that routes both names is refused. Done when: tests run `--writer agy` against a `gemini` route and `--writer gemini` against an `agy` route, refuse a pin with both, and refuse an `agy` route to an Antigravity reviewer as the writer's own family. Cheaper substitute: accepting the name in argparse without the route lookup must fail.
- [x] Decode a reviewer's reply as strict UTF-8 and otherwise as Windows-1252 with undefined bytes replaced, on every platform, in `review-dispatch.py`, so a curly quote a CLI wrote in the Windows code page is kept (seen in the plan review of §1, recorded with replacement characters). Done when: a test reply holding byte 0x92 is recorded with its apostrophe, a UTF-8 reply is unchanged, and a reply holding byte 0x81 (undefined in Windows-1252) is recorded with a replacement character and no exception. **Corrected 2026-11-11 (plan review):** said "the platform encoding", which is UTF-8 on WSL and in Python's UTF-8 mode.
- [x] Read a recorded `- Lenses:` line with any well-formed distinct names in `review-dispatch.py`, so a pin-declared lens reads back. Done when: a test records and reads a round with a declared lens.
- [x] Report a three-pass round's JSON summary without reading `severity_stop_after`, which a three-pass pin lacks, in `main` of `review-dispatch.py`. Done when: a test drives a whole three-pass chain through the command line (plan, round, completion with gaps, reconciliation complete) with a stub reviewer and asserts each exit code, each JSON summary (`position`, `severity_stop` false, `kind`, `candidate`) and the findings file read back, and the rotation tests still pass. **Corrected 2026-11-11 (plan review):** added; the round summary would have raised after the reviewer ran.
- [x] Require every three-pass section pass's `--candidate` to resolve to a commit, in `review-dispatch.py`. Done when: tests refuse a round with no candidate, a candidate that is not a commit and one that does not descend from the plan review's, and a completion and a reconciliation on a candidate before the preceding pass's, each before a reviewer runs. **Corrected 2026-11-11 (plan review):** added; the stamp in §3 is too late to save the review.
- [x] Run a section's plan review under the pin committed at its own `--candidate`, and every later pass under the pin at the returned plan review's candidate, refusing when that pin is missing or does not load instead of falling back to the working tree's, in `section_pin` of `review-dispatch.py` (plan R2). Done when: tests change the route and the schedule after the plan candidate and the later passes still use the earlier ones, a working-tree pin that is invalid or has switched policy does not stop a section under way, and a plan candidate with no loadable pin refuses naming the commit. A findings file not named for a section keeps the working tree's pin. **Corrected 2026-11-11 (plan review):** added; the plan review's own pin was unspecified and the fallback was silent.
- [x] Cover the pass order as a state machine in `test_review_dispatch.py`. Done when: tests refuse a second completion, a reconciliation before the completion and one after `RECONCILIATION: complete`; accept the valid final lines of each kind; and show that an incomplete or failed plan, round, completion or reconciliation can be run again, does not advance the order and does not count toward `pass_cap`. **Corrected 2026-11-11 (plan review):** added.
- [x] Cover `no_progress_cap` in `test_review_dispatch.py`: progress is a worst finding less severe than the pass before. Done when: tests show reconciliations at the same severity reach the limit and the next is refused naming `no_progress_cap`, a less severe pass resets the count, an attempt that returned no review does not count, and a pin without the key never refuses on it. **Corrected 2026-11-11 (plan review):** added; only `pass_cap` had a test.
- [x] List changed files NUL-delimited with `core.quotepath` off, refusing when git fails, in `changed_paths` of `review-dispatch.py`. Done when: a test with a non-ASCII filename under a conditional path gets its lens, a failing git lookup refuses before a reviewer runs, and command line tests pass `--paths` to a plan review and to a standalone review and see the lens in the prompt the stub reviewer received. **Corrected 2026-11-11 (plan review):** added; plain `--name-only` quotes such names.
- [x] Prove the promised outputs in `test_review_dispatch.py`. Done when: tests assert the `highest` and `blocking` JSON values for `HIGHEST: P2`, `P3`, `none` and a reply with no `HIGHEST` line (which blocks), the kept text of an incomplete reply in the JSON and the findings file, and a pin-declared lens's question in the prompt the stub reviewer received. **Corrected 2026-11-11 (plan review):** added.
- [x] Extend `tests/test_check_pin_contract.py` and `tests/fixtures/check-pin/pins/` with a valid three-pass pin and one refused pin per new key, with `schedule` reported when the pin has one (plan R12). Done when: every existing fixture keeps its verdict, the new ones give theirs, and the test compares the reported `schedule` with the pin's own table, key for key. **Corrected 2026-11-11 (plan review):** added the content comparison. Cheaper substitute: editing an existing fixture's expected verdict must fail review.
- [x] Update the module docstring of `review-dispatch.py` and run `python forge.py self-sync`. Done when: `scripts/review-dispatch.py` equals the kit file.
- [x] Commit: `reviewer: three-pass kinds, order, caps and lens verdicts in the dispatcher`

**Test checkpoint:** `python -m unittest discover -s kits/reviewer/templates/scripts/tests` and `python -m unittest discover -s tests` both end `OK`; removing the cap check from `check_three_pass_order` makes the cap test fail.

> **Verified:** 2026-11-11 | §2 | bc43402e48e8e7080ca3aef270722a666d07391a
> **Review:** `docs/reviews/d00-t01-s2.json`

## 3. Three-pass stamp rules in the todo kit

> **Started:** 2026-11-11T11:59:51Z

`stamp` accepts the three-pass chain and holds every pass to the pin the section began under (R2, R13).

**Phase:** 0
**Needs:** none
**Surface:** no

**Build order:**

1. Teach `kits/todo/templates/scripts/lib/todo_graph.py` the section pin and the `reconciled` verdict. Done when: a three-pass receipt validates.
2. Add the chain check and the cap from the pin. Done when: a receipt past the cap refuses.
3. Cover both policies in `tests/test_todo_graph.py`. Done when: the checkpoint passes.

- [x] Reach `review_pin.py` in `todo_graph.py` through the dispatcher that loads it, and hold a three-pass section's receipt to the pin committed at its plan review's candidate, recorded as `schedule_sha` in new receipts (plan R2, R5). Done when: a test changes the three-pass pin after the plan review and the stamp still checks the earlier schedule; a rotation section's receipt is held to the stamped commit's pin as before; a section that began under a rotation pin and is stamped after the pin became three-pass is held to its plan candidate's rotation pin; and a receipt without `schedule_sha` is still held to the stamped commit's pin. **Corrected 2026-11-11:** the dispatcher in §2 binds only three-pass sections to the plan candidate's pin (review round 1 and 4 of §2), so the stamp replays that rule and not "every section". Cheaper substitute: reading the working tree's pin must fail.
- [x] Add the completion verdict `reconciled` to `completion_record` in `todo_graph.py`: a returned reconciliation ending `RECONCILIATION: complete`, the last one, on the stamped candidate (plan R13). Done when: tests accept it and refuse it with no reconciliation or with one ending gaps.
- [x] Add `three_pass_ok` to `todo_graph.py`: one plan review, exactly one returned round with a candidate, one completion, reconciliations up to the pin's `pass_cap`, each on a candidate at or after the one before, the last on the stamped commit, and every returned pass reviewed by the reviewer the section's pin routes its writer to (plan R13). Done when: tests refuse two rounds, a round without a candidate, a chain out of order, a chain over a `pass_cap` of 4, a last pass on another commit than the stamped one and a pass by another reviewer than the pinned one. **Corrected 2026-11-11:** added the last-candidate and reviewer checks.
- [x] Accept the three-pass round verdict `fixed` as the loop's last, and under `blocking` accept `filed` when the last pass ended gaps below the blocking levels with its `- Filed:` lines, in `todo_graph.py` (plan R9). Done when: tests accept both and refuse `filed` after a pass whose `HIGHEST` is `P1`.
- [x] Replay each three-pass pass's lenses with the conditional lenses for the files changed between the plan review's candidate and its own (listed without rename detection, as the dispatcher lists them), and accept on a plan review any of the conditional lenses whose entry names plan, in `schedule_ok` of `todo_graph.py` (plan R8, R10). Done when: tests refuse a round recorded without a conditional lens its changed files call for and one recorded with a lens they do not call for, accept a plan review recorded with a plan-conditional lens, and accept a pass recorded with no effort under a step that sets none. **Corrected 2026-11-11:** a step without an effort records none since §1 (`0ecf065`), so the replay compares efforts as it always did and nothing is skipped; the plan review's conditional lenses come from `--paths`, which the stamp cannot recompute.
- [x] Replay each reconciliation's eligibility in `three_pass_ok` of `todo_graph.py`, as `check_three_pass_order` enforces it at dispatch: the pass before it ended gaps, its worst finding blocks when the pin sets `blocking`, and fewer than `no_progress_cap` reconciliations in a row had made no progress. Done when: tests refuse a receipt whose findings file holds a reconciliation after `COMPLETION: complete`, one after a pass below the blocking levels, and one past a stalled chain, each naming the rule. **Corrected 2026-11-11 (plan review):** added; only counts, order and ancestry were checked.
- [x] Refuse the completion verdict `completed` under three-pass in `three_pass_ok`, leaving it as it is for rotation receipts. Done when: a test with a three-pass completion ending `COMPLETION: gaps` refuses `completed` and stamps as `reconciled` after a reconciliation ending `RECONCILIATION: complete`, and the existing rotation test of `completed` passes unchanged. **Corrected 2026-11-11 (plan review):** added; `completed` would have stamped blocking gaps.
- [x] Hold every receipt to the schedule of the commit the section pin rule selects, in `receipt_data_ok` of `todo_graph.py`: a `schedule_sha` must be that commit, and a receipt without the field is valid only when its schedule is that commit's schedule. Done when: read-back tests change the pin after a three-pass plan review, stamp, then delete `schedule_sha` from the receipt and replace it with the stamped commit, and the graph refuses both. **Corrected 2026-11-11 (plan review):** added; dropping the field moved a receipt onto the stamped commit's pin.
- [x] Record `passes_spent` and `pass_cap` in a three-pass receipt in `stamp`, and check them in `receipt_data_ok` against the findings file and the section pin (a rotation receipt carries neither and keeps `rounds_spent` and `round_cap`). Done when: tests under a pin with `pass_cap = 45` stamp a clean completion, a successful reconciliation and a below-blocking `filed` chain through `stamp`, re-read each through `graph`, and find `passes_spent` 3, 4 and 3 with `pass_cap` 45; and a receipt whose `passes_spent` or `pass_cap` is edited refuses. **Corrected 2026-11-11 (plan review):** added; the existing accounting counts rounds against a closed list of round caps.
- [x] Test `blocking` with pairs in `tests/test_todo_graph.py`: the same chain ending `HIGHEST: P2` and gaps, with its `- Filed:` lines resolving, refuses `filed` under `blocking = ["P1", "P2"]` and stamps under `blocking = ["P1"]`, once with the completion as the last pass and once with a reconciliation. Done when: the four cases behave so. **Corrected 2026-11-11 (plan review):** added; rejecting only `P1` would have passed.
- [x] Refuse a section contract that changed between a failed completion and its reconciliation, in `todo_graph.py`. Done when: a test that edits a `Done when:` between the two refuses and one that only ticks boxes passes.
- [x] Keep every rotation receipt valid: run the existing stamp tests unchanged in `tests/test_todo_graph.py` (plan R4). Done when: they pass with no edit to their expectations. Cheaper substitute: loosening an existing assertion must fail review.
- [x] Read `kits/todo/templates/scripts/campaign_guard.py` for anything that names the round cap or the schedule and correct it. Done when: `tests/test_campaign_guard.py` passes and the file states no cap of its own.
- [x] Run `python forge.py self-sync`. Done when: `scripts/lib/todo_graph.py` equals the kit file.
- [x] Commit: `todo: stamp the three-pass chain against the section's own pin`

**Test checkpoint:** `python -m unittest discover -s tests` ends `OK`; removing the cap check from `three_pass_ok` makes its test fail.

> **Verified:** 2026-11-11 | §3 | b7351fc348bad9c42c1abb4744c4234714641f98
> **Review:** `docs/reviews/d00-t01-s3.json`

## 4. Template pin, prompts, skills and READMEs on three-pass

> **Started:** 2026-11-11T13:36:48Z

Everything a project reads when it installs the kits describes the three-pass shape, and new installs start on it (R14, R15).

**Phase:** 0
**Needs:** none
**Surface:** no

**Build order:**

1. Rewrite `kits/reviewer/templates/.conclave/reviewers.toml` as a three-pass pin with the decision recorded. Done when: `--check-pin` prints `ok` for it.
2. Update the prompts and add `kits/reviewer/templates/docs/reconciliation-review-prompt.md`. Done when: each prompt names its final verdict lines.
3. Update the skills and READMEs, then `python forge.py self-sync`. Done when: the checkpoint passes.

- [x] Rewrite `kits/reviewer/templates/.conclave/reviewers.toml` as a three-pass pin: `pass_cap`, `blocking`, completion lenses `plan-delivery` and `record`, a commented example of a conditional entry and of a declared lens, and a comment recording that new installs start on three-pass and how to keep rotation (plan Decisions). Done when: `python kits/reviewer/templates/scripts/review-dispatch.py --check-pin --pin kits/reviewer/templates/.conclave/reviewers.toml` prints `ok`. **Corrected 2026-11-11:** said the commented example is a conditional `design` entry; `design` stays in the round, gated by `--surface`, and the example shows a project lens instead. Cheaper substitute: leaving the rotation pin with a comment must fail.
- [x] Ask for the `HIGHEST:` line on every three-pass pass in `review-dispatch.py` and `review_pin.lens_block`, also when the pass has no lenses (a completion step without lenses, as in a pin written before completion had its own). Done when: a test under such a pin shows the prompt the stub reviewer received asks for `HIGHEST:` and a reply carrying it is recorded as the completion review. **Corrected 2026-11-11:** added; since §3 a three-pass reply without the line is incomplete, and a pass with no lenses was never asked for it. Cheaper substitute: relying on the prompt template alone must fail, because a project owns its templates.
- [x] Route `agy` to the installed reviewer in the template pin and name the writers `claude`, `codex` and `agy` (with `gemini` as another name for `agy`) wherever a skill, prompt or README shows `--writer` (owner decision 2026-11-11). Done when: `python kits/reviewer/templates/scripts/review-dispatch.py --check-pin --json --pin kits/reviewer/templates/.conclave/reviewers.toml` reports an `agy` route and no file under `kits/reviewer` or `kits/todo` shows `--writer claude` as the only choice. **Corrected 2026-11-11:** added.
- [x] Move the SDK's own `.conclave/reviewers.toml` to the three-pass template pin in the same commit as the template, and say in `AGENTS.md` that the SDK reviews its own sections three-pass. Done when: `python scripts/review-dispatch.py --check-pin` prints `ok` for a three-pass pin, and this section, whose plan review read the rotation pin, still finishes under rotation (its remaining passes run and the stamp accepts them). **Corrected 2026-11-11:** added; the pin is not covered by `self-sync`.
- [x] Add `kits/reviewer/templates/docs/reconciliation-review-prompt.md` and list it in `kits/reviewer/scripts/install.sh`, `kits/reviewer/scripts/test-install.sh` and the `forge.py` kit manifest if one names the prompts. Done when: the install test finds it in a fresh install.
- [x] Update `plan-review-prompt.md`, `review-round-prompt.md` and `completion-review-prompt.md` in `kits/reviewer/templates/docs/` for the lens verdict lines, the `HIGHEST:` line and the three-pass order (plan R7, R9). Done when: each names the lines the dispatcher checks and none promises a 33-round loop as the only shape.
- [x] Rewrite `kits/reviewer/README.md` for both policies: the pin keys, the passes, the lens verdict lines, conditional lenses, blocking, the caps, `review_pin.py` and how an existing pin moves to three-pass. Done when: every table row is at most 120 characters and every key the loader accepts is named.
- [x] Update the `independent-review` skill in `.agents`, `.claude` and `.codex` under `kits/reviewer/templates/`. Done when: the three files state the same rules and name `--kind reconciliation`.
- [x] Update the `review-todo-section`, `process-todo-section` and `process-phase` skills in `.agents`, `.claude` and `.codex` under `kits/todo/templates/` for the three-pass flow, keeping the rotation flow for pins that use it (plan R14). Done when: each agent's copy describes plan, round, completion, reconciliation, the cap from the pin and the stamp arguments for both policies. **Corrected 2026-11-11:** said `groom-plan`; it and `process-plan` state no schedule, cap or writer and needed no change, while `process-phase` did.
- [x] Update `kits/todo/README.md`, `kits/todo/templates/docs/todo-workflow.md` and `kits/todo/templates/todo/README.md` where they describe review rounds. Done when: none states 33 rounds as the only rule. **Corrected 2026-11-11:** only `todo/README.md` described rounds; the other two name no cap or schedule and are unchanged.
- [x] State the three-pass stopping and recovery rules in `review-todo-section` of the three agent folders: a reply recorded as incomplete is run again and does not count; a last pass below the `blocking` levels is filed (`- Filed:` lines, `--completion '<file>:filed'`) and takes no further pass; a blocking gap needs a reconciliation that ends complete; at `pass_cap` or `no_progress_cap` with gaps open the section stays unstamped and the run carries on with other rows. Done when: each copy names every one of those cases with the command that applies, and no command in it is refused by `review-dispatch.py --help` or `todo-graph.py stamp --help`. **Corrected 2026-11-11 (plan review):** added; naming the passes alone would have let a skill retry after a non-blocking finding or stamp at the cap.
- [x] Say in `independent-review` and in the audit stance of `review-todo-section` how a review outside a section runs under a three-pass pin: a findings file not named for a section has no order and no cap, each `--kind round` call takes the pin's round lenses, `--paths` names the changed files for conditional lenses, and the writer stops when a round returns no blocking finding. Done when: the three copies of both skills say so. **Corrected 2026-11-11 (plan review):** added.
- [x] Give `reconciliation-review-prompt.md` the failed completion's candidate, the last reviewed candidate, the repaired candidate, the findings file with the `- Implemented:` lines and the gate output, and the three things to check (each gap closed, no regression in the repair, the section's promise unchanged). Done when: `tests/test_three_pass_install.py` fills it, sends it through the installed dispatcher with a stub reviewer and reads back a recorded reconciliation ending `RECONCILIATION: complete`. **Corrected 2026-11-11 (plan review):** added; existence and verdict lines alone proved nothing.
- [x] Add `tests/test_three_pass_install.py`: install the reviewer and todo kits into a scratch git repository with `forge.py`, assert the installed pin's `policy`, completion lenses, `pass_cap` and `blocking`, write one TODO section, and run plan, round, completion with gaps and reconciliation through the installed `scripts/review-dispatch.py` with a stub Codex on `PATH`, then `scripts/todo-graph.py stamp` with `reconciled` and read the receipt back through `validate`. Done when: the test passes, asserts `passes_spent` 4 and the pin's `pass_cap` in the receipt, and fails when the template pin is put back to rotation. **Corrected 2026-11-11 (plan review):** added; `--check-pin` also prints `ok` for a rotation pin, and equal copies can be equally wrong.
- [x] Refresh the SDK's own `todo/README.md` from `kits/todo/templates/todo/README.md` by hand (`self-sync` does not cover `todo/`) and compare the two. Done when: `git diff --no-index kits/todo/templates/todo/README.md todo/README.md` is empty or shows only the SDK's own first paragraph. **Corrected 2026-11-11 (plan review):** added.
- [x] Run `python forge.py self-sync` and copy the kits' `docs/` prompts and the template pin into the SDK's own `docs/` and `.conclave/reviewers.toml` (plan R15). Done when: `python -m unittest discover -s tests` passes and `git diff --no-index` between each kit file and its installed copy is empty.
- [x] Commit: `reviewer, todo: template pin, prompts, skills and READMEs on three-pass`

**Test checkpoint:** `python -m unittest discover -s tests` ends `OK` and `python scripts/review-dispatch.py --check-pin` prints `ok`; a prompt or skill left unsynced makes the self-sync test fail.

> **Verified:** 2026-11-11 | §4 | a741c81183efb6f2fbc550d7a6590000998c245f
> **Review:** `docs/reviews/d00-t01-s4.json`

## 5. Pin check that reports every fault at once

> **Started:** 2026-11-11T15:11:40Z

Filed 2026-11-11 from the completion review of §1 (an out-of-scope excellence item): `load_pin` stops at the first fault, so a pin with three independent mistakes takes three runs of `--check` to correct. A diagnostic mode lists them together, and the fail-fast `load_pin` every caller relies on does not change.

**Phase:** 0
**Needs:** none
**Surface:** no

**Build order:**

1. Add a fault-collecting pass to `kits/reviewer/templates/scripts/review_pin.py` behind `--check --all`. Done when: a pin with three independent faults prints three refusals.
2. Cover it in `kits/reviewer/templates/scripts/tests/test_review_pin.py` and run `python forge.py self-sync`. Done when: the checkpoint passes.

- [x] Add `faults(pin_bytes)` to `review_pin.py`, returning every independent refusal message of a pin in file order, with `load_pin` still raising the first. Done when: a test pin with a bad `pass_cap`, an unknown lens and a bad `blocking` yields those three messages, and `load_pin` on it raises the first. Cheaper substitute: catching one exception and returning a one-item list must fail.
- [x] Keep `load_pin`'s own order of checks in `review_pin.py` whatever order `faults` reports in: `faults` lists faults in the order of the pin's tables (reviewers, routes, then the schedule's keys), and `load_pin` raises the fault it always raised first. Done when: a test pin with a bad `pass_cap` and an unknown lens in a later step shows `load_pin` raising the lens refusal as today while `faults` lists `pass_cap` first. **Corrected 2026-11-11 (plan review):** added; file order and the loader's order differ.
- [x] Collect across every area in `faults`: each reviewer, each route, the schedule's shape, every step, `[schedule.lenses]`, the caps, `blocking`, each conditional entry and the one-owner rule, for both rotation and three-pass. A check that depends on a part already reported is skipped (a route naming a reviewer whose own entry is at fault, the one-owner rule when a step's lenses are at fault, everything under a schedule whose key set is wrong), so no fault is reported twice and none is invented. Done when: tests with mixed faults (a bad reviewer plus a bad route plus a bad cap; a rotation schedule with two bad steps; a bad `[schedule.lenses]` entry plus a bad conditional entry) list exactly those faults, and a route to the bad reviewer adds none. **Corrected 2026-11-11 (plan review):** added; three schedule fields alone proved nothing about the rest.
- [x] Report a pin that cannot be read as its one fault in `faults` and `--check --all`: a missing file, a directory, bytes that are not UTF-8, TOML that does not parse. Done when: tests assert exit 2, the same message `--check` gives and no traceback for each, exit 0 and `ok` for a valid pin, and that `--all` without `--check` is refused by the argument parser. **Corrected 2026-11-11 (plan review):** added.
- [x] Add `--all` to `--check` in `review_pin.py`: one `review-pin refused:` line per fault and exit 2, or `ok`. Done when: a test asserts the three lines for the pin above and `ok` for a valid pin.
- [x] Name `--check --all` in `kits/reviewer/README.md` and run `python forge.py self-sync`. Done when: `scripts/review_pin.py` equals the kit file.
- [x] Commit: `reviewer: report every pin fault in one check`

**Test checkpoint:** `python -m unittest discover -s kits/reviewer/templates/scripts/tests -p test_review_pin.py` ends `OK`; making `faults` return only its first message makes the three-fault test fail.

> **Verified:** 2026-11-11 | §5 | 761b8749b2bd1264d27c5bb482ba279e066c00cc
> **Review:** `docs/reviews/d00-t01-s5.json`

## 6. Reviewer process tree ended on Windows by a job object

> **Started:** 2026-11-11T15:11:40Z

Filed 2026-11-11 from the completion review of §2 (an out-of-scope gap). `kill_tree` in `review-dispatch.py` ends a reviewer's children on Windows with `taskkill /T`, which reaches them only while the reviewer itself is alive (the line carries a `WORKAROUND` comment). RasterFold's dispatcher starts the reviewer suspended inside a Win32 job object with kill-on-close, so every descendant ends with the job. Source: RasterFold `scripts/review-dispatch.py` at `b334933`, `create_windows_job`, `bind_and_resume_windows_job`, `close_windows_job` and its `run`.

**Phase:** 0
**Needs:** windows-host
**Surface:** no

**Build order:**

1. Port the job object functions into `kits/reviewer/templates/scripts/review-dispatch.py` and use them in `run` and `kill_tree` on Windows. Done when: a reviewer that exits leaving a child running has no surviving child.
2. Cover it in `kits/reviewer/templates/scripts/tests/test_review_dispatch.py`, then `python forge.py self-sync`. Done when: the checkpoint passes.

- [x] Add `create_windows_job`, `bind_and_resume_windows_job` and `close_windows_job` to `review-dispatch.py` with `ctypes` (standard library), from RasterFold's dispatcher. Done when: on Windows a process started suspended is assigned to a kill-on-close job before it runs. Cheaper substitute: keeping `taskkill /T` as the only mechanism must fail the orphan test.
- [x] Start the reviewer suspended in the job in `run` and end the job in `kill_tree` of `review-dispatch.py`, leaving the Linux process group path as it is. Done when: the orphan test that skips Windows today (`test_review_dispatch.py`, the child survival test) runs on Windows and passes, and the Linux run is unchanged.
- [x] Write the job object code in `review-dispatch.py` to this contract, not as a copy: `CreateJobObjectW`, `SetInformationJobObject` with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`, the reviewer started with `CREATE_SUSPENDED`, `AssignProcessToJobObject`, then `NtResumeProcess`; the dispatcher owns the job handle from creation until `kill_tree` terminates the job and closes the handle, exactly once, on every path. **Corrected 2026-11-11 (plan review):** the RasterFold file is not in this repository, so the section carries the contract itself.
- [x] Handle a failure to create, configure, assign or resume the job in `run` of `review-dispatch.py`: the suspended reviewer is killed and reaped, the job handle closed, and the pass returns no review with a reason naming the step. Done when: tests inject a failure at each of the four steps (assignment before resume among them) and see a `could not start` reason, exit 1, no process left and no hang. **Corrected 2026-11-11 (plan review):** added; a suspended reviewer could have been left behind.
- [x] Check child survival on Windows without `os.kill(pid, 0)`, which terminates the process there: open the process with `OpenProcess` and read `GetExitCodeProcess` (still active or not), in `test_review_dispatch.py`. Done when: the survival test passes on Windows with the job in place and fails when the job assignment is disabled, and the same check is used after a timeout and after an output flood, where the descendants must be gone too. **Corrected 2026-11-11 (plan review):** added; the existing liveness check would have killed the child it was looking for, and only a normal exit was covered.
- [x] Remove the `WORKAROUND` comment and the note about a child outliving its reviewer from `kill_tree` and `remove_scratch` in `review-dispatch.py`. Done when: neither function describes a child that cannot be reached.
- [x] Run `python forge.py self-sync`. Done when: `scripts/review-dispatch.py` equals the kit file.
- [x] Commit: `reviewer: end the reviewer's whole process tree on Windows with a job object`

**Test checkpoint:** `python -m unittest discover -s kits/reviewer/templates/scripts/tests` ends `OK` on Windows with the child survival test run, not skipped, and with `CONCLAVE_FULL_TESTS=1` set `python -m unittest discover -s tests` ends `OK`; removing the job assignment makes the survival test fail.

> **Verified:** 2026-11-11 | §6 | 305209d965b5ce4bd767efe8c3aced5a1de13a5b
> **Review:** `docs/reviews/d00-t01-s6.json`

## 7. Review prompt filler

> **Started:** 2026-11-11T15:11:40Z

Filed 2026-11-11 from the completion review of §2 (an out-of-scope excellence item). A writer fills each prompt template by hand today. RasterFold has `scripts/review-prompt.py`, which writes the filled prompt for a section, a kind and a candidate. Source: RasterFold `scripts/review-prompt.py` at `b334933` (265 lines), with its project paths removed.

**Phase:** 0
**Needs:** none
**Surface:** no

**Build order:**

1. Add `kits/reviewer/templates/scripts/review-prompt.py` that fills a template in `docs/` for `--kind`, `--ref` and `--candidate`. Done when: its output has no unfilled placeholder.
2. Cover it in `kits/reviewer/templates/scripts/tests/test_review_prompt.py`, name it in the skills and README, then `python forge.py self-sync`. Done when: the checkpoint passes.

- [x] Add `review-prompt.py` under `kits/reviewer/templates/scripts/`: `--kind plan|round|completion|reconciliation`, `--ref`, `--candidate`, `--base`, `--purpose`, `--gates <file>` and `--out`, reading the template after its `---` line and writing the filled prompt with an atomic write. Done when: a test fills each of the four templates and finds no `<...>` placeholder left. Cheaper substitute: a filler that leaves an unknown placeholder in place without refusing must fail.
- [x] Give every placeholder a named source in `review-prompt.py`: `--candidate` (the tip), `--base` (a range `<base>..<tip>` instead of a single commit), `--ref` (optional: a review outside a TODO section omits it and the TODO lines are dropped), `--todo` (the TODO file, looked up with `scripts/todo-graph.py resolve` when `--ref` is given and the todo kit is installed), `--fidelity` (default `none (Surface: no)`), `--purpose`, `--governing` (the plan or spec; `AGENTS.md` is always named), `--gates <file>`, and for a reconciliation `--findings`, `--failed` (the failed completion's candidate) and `--last` (the last reviewed candidate, which differs from `--failed` after a first reconciliation). A template placeholder with no value is a refusal naming it. **Corrected 2026-11-11 (plan review):** added; several values had no source.
- [x] Test the filled prompts for what they hold, not only for what they lack, in `test_review_prompt.py`. Done when: tests assert each filled prompt keeps its `## Reply format` section and its final verdict line text, holds the supplied values (a single commit and a range, a surface fidelity, a second reconciliation whose `--failed` and `--last` differ), read the saved file back, and send a filled round prompt through the installed dispatcher with a stub reviewer; and a round prompt without `--ref` holds no TODO line and no unfilled placeholder. **Corrected 2026-11-11 (plan review):** added; an empty output would have passed.
- [x] Fail with a message and a non-zero exit, leaving an existing output file as it was, when `--gates` cannot be read or the output cannot be written or replaced, in `review-prompt.py`. Done when: tests cover an unreadable gates file and an output path whose folder is a file, and find the earlier output unchanged. **Corrected 2026-11-11 (plan review):** added.
- [x] Refuse in `review-prompt.py` when a placeholder has no value, a template is missing or `--candidate` is not a 40-character SHA, naming what is missing. Done when: tests assert each refusal and that nothing is written.
- [x] Name `review-prompt.py` in `kits/reviewer/README.md` and in the `independent-review`, `review-todo-section` and `process-todo-section` skills of the three agent folders, in place of "write the prompt to a scratch file from" the template. Done when: each skill shows the command.
- [x] Add install assertions for `review-prompt.py` to `kits/reviewer/scripts/test-install.sh` and run `python forge.py self-sync`. Done when: `bash kits/reviewer/scripts/test-install.sh` passes and `scripts/review-prompt.py` equals the kit file.
- [x] Commit: `reviewer: fill review prompts with review-prompt.py`

**Test checkpoint:** `python -m unittest discover -s kits/reviewer/templates/scripts/tests -p test_review_prompt.py` ends `OK`; removing the unfilled-placeholder refusal makes its test fail.

> **Verified:** 2026-11-11 | §7 | b9a87e42dbcc9eb0a7a23966e77b2244753cd984
> **Review:** `docs/reviews/d00-t01-s7.json`

## 8. Stamp that recovers from a write cut short

> **Started:** 2026-11-11T15:11:40Z

Filed 2026-11-11 from the completion review of §3 (an out-of-scope gap). `stamp` in `lib/todo_graph.py` writes the receipt, then the TODO file, then the plan, and rolls back when one of them raises. A process killed between the writes cannot roll back: the receipt exists, the TODO file is unstamped, and the next `stamp` refuses with "receipt already exists" until someone deletes the receipt by hand.

**Phase:** 0
**Needs:** none
**Surface:** no

**Build order:**

1. Make `stamp` in `kits/todo/templates/scripts/lib/todo_graph.py` recognise a receipt left by a stamp that never reached the TODO file, and finish or replace it. Done when: a retry after a kill at each write boundary succeeds.
2. Cover each boundary in `tests/test_todo_graph.py`, then `python forge.py self-sync`. Done when: the checkpoint passes.

- [x] Detect in `stamp` of `todo_graph.py` a receipt for a section whose TODO file carries no `Verified:` line for it, and replace it when it names the same commit and reviews, refusing only when it differs. Done when: a test writes the receipt, skips the TODO write, and a second `stamp` with the same arguments succeeds; one with another commit refuses naming the leftover receipt. Cheaper substitute: deleting any existing receipt unconditionally must fail.
- [x] Regenerate a stale `todo/implementation-plan.md` on the retry in `stamp` when the TODO file was stamped and the plan was not. Done when: a test stops after the TODO write and `python scripts/todo-graph.py plan --check` passes after the retry.
- [x] Check a retry against the persisted receipt before anything is written, in `stamp` of `todo_graph.py`: on a section already stamped in the TODO file, a retry whose commit, reviews, plan and completion match the receipt regenerates a stale plan and reports success; any other is refused as already verified, with the receipt, the TODO file and the plan untouched. Done when: tests cover a matching retry and one with another commit and one with another review verdict. **Corrected 2026-11-11 (plan review):** added; regenerating the plan for any retry would have reported success for a different request.
- [x] Leave a retryable state when the retry itself fails, in `stamp` of `todo_graph.py`: a receipt that was already on disk before this call is never deleted by its rollback, and a plan write that fails after the TODO file is stamped leaves receipt and TODO as they are. Done when: a test injects a failing plan write on the retry, finds the receipt and the stamped TODO still there, and a further retry succeeds. **Corrected 2026-11-11 (plan review):** added; the rollback deleted the receipt unconditionally.
- [x] Name the recovery in `kits/todo/templates/todo/README.md` under stamps and receipts, copy that file over the SDK's own `todo/README.md` (`self-sync` does not cover `todo/`), and run `python forge.py self-sync`. Done when: `scripts/lib/todo_graph.py` equals the kit file and the two READMEs are identical. **Corrected 2026-11-11 (plan review):** added the SDK's own README.
- [x] Commit: `todo: a stamp cut short between its writes can be retried`

**Test checkpoint:** with `CONCLAVE_FULL_TESTS=1` set, `python -m unittest discover -s tests` ends `OK` with the stamp tests run, not skipped; removing the leftover-receipt check makes its test fail. **Corrected 2026-11-11 (plan review):** the stamp tests are skipped without that variable, so the earlier command could pass without running them.

> **Verified:** 2026-11-11 | §8 | 89ff448ffb36806b77593755e3021c3145783e3a
> **Review:** `docs/reviews/d00-t01-s8.json`

## 9. Re-plan route for a chain that cannot settle, recovery planned up front

> **Started:** 2026-11-19T06:17Z

Filed 2026-11-18 from `D07 T01 §7`, which spent 19 passes before a re-plan: its reconciliations kept raising edges in crash recovery one at a time, and then alternated between two findings that asked opposite things of one checked item, which no build could satisfy while `stamp` held the contract fixed. Two lessons belong in the kits the next section reads: plan the recovery of a change that replaces files on disk (one locked, journaled change, own-files-only, kept until done) before the build, and when a chain cannot settle, re-plan the item instead of spending passes on code (the route `D07 T01 §7` took by hand: a dated correction, a new `Started:`, the first findings file kept as `D<NN>-T<NN>-s<N>-chain1.md`, a new chain).

**Corrected 2026-11-19:** the third item placed `scripts/review-dispatch.py` in the todo kit; it is the reviewer kit's (`kits/reviewer/templates/scripts/review-dispatch.py`). `stamp` already refuses a kept chain file as `--plan` or `--completion`, since it takes only the section's own findings file by its exact name (`kits/todo/templates/scripts/lib/todo_graph.py`, `findings_path`), so that half needs a test, not code; the dispatcher's half is to refuse `--record` naming a kept chain, which is closed. The first item's rule goes beside step 2's table, not in a row: a row holding it would pass 120 characters. The re-plan rule sits with the gap-reopened-twice rule (`233681c`) in step 3, and names it: a redesign keeps the item, a re-plan changes it.

**Corrected 2026-11-19 (plan review, docs/reviews/00-reviewer/D00-T01-s9.md):** `stamp` refuses a kept chain only by the three-pass same-file check, not under a rotation pin, so it gains an explicit refusal; the route becomes a command (`todo-graph.py replan`) so that following it is what the test proves, not a hand-built archive; the recovery rule names the four things a multi-file replacement's plan must state; `query rounds` lists each kept chain; the checkpoint adds the graph and dispatcher tests. The third item previously ended "Done when: a test with a kept chain file and a new chain stamps the section, `query rounds` counts both chains' passes, and the dispatcher's test finds a kept chain refused."

**Corrected 2026-11-19:** the checkpoint named `kits/todo/templates/scripts/tests`, which does not exist: the todo kit's graph and stamp tests are the SDK's `tests/test_todo_graph.py`, its slow ones behind `CONCLAVE_FULL_TESTS`.

**Phase:** 8
**Needs:** none
**Surface:** no

**Build order:**

1. Write the two rules in the skills. Done when: the skill tests read them.
2. Make the dispatcher and `stamp` recognise a kept chain file. Done when: the checkpoint passes.

- [x] Add to `kits/todo/templates/.claude/skills/process-todo-section/SKILL.md` step 2 (the Sufficiency check, beside its table): a section that writes, moves or deletes files outside the repository (links, icons, caches, a user's data) states before its plan review the lock that keeps a second run out, the durable record of a change in progress, the ownership check before a file is replaced or deleted, and when that record may be removed, and how a failure and a stop are recovered from it. Done when: a test in `tests/test_forge.py` finds the rule and each of the four in the skill and its Codex and Antigravity copies.
- [x] Add to `kits/todo/templates/.claude/skills/review-todo-section/SKILL.md` step 3 a "When a chain cannot settle" rule, beside the gap-reopened-twice rule (a redesign keeps the item; a re-plan changes it): when two passes in a row raise opposite demands on one checked item, or a finding is a checked item's own contradiction, the item is re-planned with `python scripts/todo-graph.py replan '<ref>'` (below), a dated correction of the item, one commit of the changed checklist with the new `Started:`, and a new plan review on it; the run file records the decision. Done when: a test finds the rule and the route's steps in the skill and its copies.
- [x] Add `replan <ref>` to `kits/todo/templates/scripts/lib/todo_graph.py`: it moves the section's findings file to the next unused `D<NN>-T<NN>-s<N>-chain<k>.md` (never over an archive; a retry after the move finds the archive and no own file and goes on), replaces the section's `Started:` line with the current instant and keeps the old one in a dated `**Corrected YYYY-MM-DD:**` note, and prints the steps left (correct the item, commit, plan review). Done when: a test from a section with a chain runs `replan`, a new plan review and the passes with the stub reviewer, and stamps; a second `replan` writes `-chain2.md` and leaves `-chain1.md` byte-identical; a retry after the move changes nothing more.
- [x] Teach `kits/reviewer/templates/scripts/review-dispatch.py` and `stamp` in `kits/todo/templates/scripts/lib/todo_graph.py` that a `-chain<k>.md` file beside a section's findings file is a kept earlier chain: the dispatcher refuses `--record` naming one before any reviewer runs, `stamp` refuses one as `--plan` or `--completion` under a three-pass and a rotation pin alike, and `review_rounds` (`query rounds`) lists each section's kept chains (`kept_chains`: each file and its returned passes). Done when: the dispatcher's test finds a kept chain refused with the stub reviewer never started and the file byte-identical; stamp tests refuse a chain file as `--plan` and as `--completion` under both schedules with otherwise valid evidence; a `query rounds` test names two chains with different counts (one holding an incomplete attempt that adds none) and finds a section without archives unchanged.
- [x] Run `python forge.py skill-copies` and `python forge.py self-sync`. Done when: `python forge.py skill-copies --check` exits 0 and the self-sync test passes.
- [x] Commit: `todo: a chain that cannot settle is re-planned, and recovery is planned before the build`

**Test checkpoint:** `python -m unittest tests.test_forge -k skill`, `CONCLAVE_FULL_TESTS=1 python -m unittest tests.test_todo_graph` (the todo kit's graph tests, which live in the SDK's `tests/`) and the reviewer kit's dispatcher tests pass; removing the re-plan rule from the review skill, the chain refusal from `stamp` or the dispatcher, or the next-unused numbering from `replan` makes its test fail.

## 10. P2 gate by kind with two filing caps

> **Started:** 2026-11-19T08:09Z

Filed 2026-11-19 at the owner's request. A P2 finding held `D02 T02 §12` through 20 reconciliations; blocking on P1 alone would ship real P2 defects (that chain's P2s included a deleted record and another folder's icons removed). It sits in Phase 9 because a two-digit reference widens Phase 8's plan table past 120 characters; as the owner's request it is taken next, out of table order. The owner chose a gate by kind: a P2 that endangers the user's data holds the stamp longer than an ordinary one, and neither holds it forever. A pass's P2 findings are tagged by the reviewer; the stamp reads the tags.

**Phase:** 9
**Needs:** none
**Surface:** no

**Build order:**

1. Add the pin keys and the reply tag. Done when: the pin tests read them.
2. Make the stamp and the dispatcher apply them. Done when: the checkpoint passes.

- [ ] Add `p2_file_after` (default 3) and `p2_data_file_after` (default 6) to `[schedule]` in `kits/reviewer/templates/scripts/review_pin.py`, each a whole number of reconciliations, `p2_data_file_after` at least `p2_file_after`, read only with `blocking` naming `P2`; set both in `kits/reviewer/templates/.conclave/reviewers.toml` and the SDK's `.conclave/reviewers.toml`. Done when: `test_review_pin.py` loads both, refuses a value that is not a whole number, a data cap below the ordinary one, and either key without `P2` blocking.
- [ ] Ask in `kits/reviewer/templates/docs/review-round-prompt.md`, `completion-review-prompt.md` and `reconciliation-review-prompt.md` for each P2 to be tagged `P2 data` (it loses, corrupts or exposes the user's data, or reports a failure as success) or `P2` (any other), and for a `P2 DATA: yes|no` line beside `HIGHEST:`; the dispatcher reads the line (`p2_data` in its summary) and records an absent one as `yes`. Done when: a dispatcher test records `yes`, `no` and an absent line read as `yes`.
- [ ] Apply the gate in `stamp` (`kits/todo/templates/scripts/lib/todo_graph.py`): a last pass whose worst finding is P2 takes `:filed` once the chain has spent `p2_file_after` reconciliations, or `p2_data_file_after` when that pass says `P2 DATA: yes`, with a `- Filed:` line for each open P2; before that it needs a reconciliation, as now; P1 always does. Done when: stamp tests take `filed` after 3 ordinary and after 6 data reconciliations, refuse it after 2 ordinary and after 5 data, refuse it for a P1, and read an absent `P2 DATA` line as data.
- [ ] Make the dispatcher refuse a reconciliation the stamp would no longer need (the last pass's P2 is past its cap), as it refuses one below the blocking levels now. Done when: a dispatcher test finds that reconciliation refused before a reviewer runs.
- [ ] Write the rule in `kits/todo/templates/.claude/skills/review-todo-section/SKILL.md` ("How a section ends") and `kits/reviewer/README.md`, run `python forge.py skill-copies` and `python forge.py self-sync`. Done when: a test finds the rule in the skill's three copies and `skill-copies --check` exits 0.
- [ ] Commit: `review: a P2 holds the stamp by kind, an ordinary one for 3 reconciliations, a data one for 6`

**Test checkpoint:** `python -m unittest discover -s kits/reviewer/templates/scripts/tests`, `CONCLAVE_FULL_TESTS=1 python -m unittest tests.test_todo_graph` and `python -m unittest tests.test_forge -k skill` pass; reading an absent `P2 DATA` line as `no`, or filing an ordinary P2 before `p2_file_after`, makes its test fail.

## Verification

- A scratch repository with the template pin runs plan, round, completion and reconciliation through `scripts/review-dispatch.py` with a stub reviewer and stamps the section; the same run with the rotation pin stamps as before.
- `python -m unittest discover -s tests -v` passes.
- `python scripts/todo-graph.py validate` and `python scripts/todo-graph.py plan --check` pass.
