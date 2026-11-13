---
schema_version: 1
id: project-shaped-graph
domain: 03-todo-graph
status: active
title: "TODO-01 -- Todo graph that takes a project's shape"
---

# TODO-01 -- Todo graph that takes a project's shape

> **Goal:** A project with its own phases, Needs values, caps and receipts folder can run the kit's todo graph by stating them in `todo/plan.json`, with today's values as the defaults, and the two projects that are ahead of the kit have a measured list of what still stops them adopting it.

> **Current state:** Measured 2026-11-11. `kits/todo/templates/scripts/lib/todo_graph.py` (1,513 lines) fixes a project's shape in module constants: `PHASES = (0, 1, 2, 3, 4, 5, 6, 7, 99)` (`:68`), `NEEDS` with ten values (`:27`), `WAITING` (`:29`), `MAX_SECTIONS_PER_FILE = 55` (`:71`), `MAX_ITEMS_PER_SECTION = 30` (`:72`), `MAX_DELIVERABLE_LEN = 88` (`:73`), `MAX_TABLE_ROW = 120` (`:75`), `PLAN = "todo/implementation-plan.md"` (`:19`), and the receipts folder `docs/reviews/` as inline literals (`:202`, `:291`, `:414`, `:1351`). `todo/plan.json` accepts exactly `title`, `acceptance` and `phases` (`plan_config`, `:1170`, key check at `:1179`), and a phase key must be in `PHASES` (`:1190`). Neither project's tree passes this validator. RasterFold (`~/projects/RasterFold` in WSL, `b33493346141f96b6b304cd3e0c393595382f056`) has a 12,802 line `scripts/todo-graph.py` with seven Needs labels of its own (`NEEDS_ALLOWED`, `:236`), a `Requires` list checked against the host (`REQUIRES_ALLOWED`, `:264`; `detect_context`, `:296`), no `plan.json`, and subcommands the kit lacks (`warnings`, `self-test`, `needs`, `progress`, and eleven more `query` kinds). Impossible OS (`~/projects/impossible-os` in WSL, `17a762d39ccd1958cbe711901f645fd9b042e939`) has `scripts/todo-graph/validate.py` (3,213 lines) and `build.py` (2,448), no Needs field at all, and keeps review receipts under `.claude/overnight/reviews/`.

## Inputs

- `docs/plans/2026-11-11-sdk-audit-and-roadmap.md`: findings 5, 6 and 7 and recommendation 6. Until this file ships, Impossible OS and RasterFold must not take the kit's graph.
- `kits/todo/templates/scripts/lib/todo_graph.py`, `kits/todo/templates/todo/README.md`, `kits/todo/templates/todo/plan.json` and `tests/test_todo_graph.py` (2,185 lines): every section changes them.
- Decision recorded here: the `todo/` folder itself stays fixed. Both projects use `todo/`, and the configuration that would move it lives inside it.
- -> XREF: D05 T01 §4 -- `init --acceptance` writes the `acceptance` key of the same `todo/plan.json`

## Outcome

- A `todo/plan.json` that lists its own phase numbers, Needs values, waiting Needs, caps and receipts folder validates a tree written to those lists, and a tree with no such keys behaves exactly as it does today.
- `docs/reviews/` is no longer written anywhere in `todo_graph.py` except as the default.
- A report in `docs/plans/` lists, for RasterFold and for Impossible OS, every class of refusal the kit's validator still raises on a copy of their tree, each with a section that owns it or a recorded decision to leave it.

**Adjacency:** all=not-applicable (developer tooling: a validator's configuration, with no records a user lists, exports, is notified of or reverses)

**Adjacency rationale:** Every new setting is a key of `todo/plan.json` consumed by `plan_config` and proven by a refusal test in its own section. The validator's refusals are the permission side and are tested both ways in each section.

## Implementation Order

| Order | Section | Deliverable | Depends On | Status |
| ----- | ------- | ----------- | ---------- | ------ |
| 1 | §1 | Phase list read from `todo/plan.json` | -- | [x] |
| 2 | §2 | Needs values and waiting Needs read from `todo/plan.json` | §1 | [x] |
| 3 | §3 | Caps read from `todo/plan.json` | §1 | [x] |
| 4 | §4 | Receipts folder read from `todo/plan.json` | §1 | [x] |
| 5 | §7 | Plan path read from `todo/plan.json` | §4 | [x] |
| 6 | §8 | Every validation fault in one run | §1 | [ ] |
| 7 | §5 | Adoption dry run on RasterFold and Impossible OS | §2, §3, §4, §7, §8 | [ ] |
| 8 | §6 | Lift or leave decision for each RasterFold graph command | §5 | [ ] |

## 1. Phase list read from `todo/plan.json`

> **Started:** 2026-11-13T02:16:11Z

A project names its phases in `todo/plan.json` but may only use the numbers the kit fixed. The list of allowed numbers becomes a key, defaulting to today's.

**Phase:** 3
**Needs:** none
**Surface:** no

**Build order:**

1. Add `phase_list` to `plan_config` in `kits/todo/templates/scripts/lib/todo_graph.py` and pass the loaded configuration to the checks that use `PHASES`. Done when: a tree with phase 12 validates under a plan that lists it.
2. Cover the refusals and the default, then `python forge.py self-sync`. Done when: the checkpoint passes.

- [x] Accept an optional `phase_list` key in `plan_config` of `todo_graph.py`: a non-empty list of distinct whole numbers from 0 to 999, defaulting to `PHASES`. Done when: tests refuse a string, an empty list, a duplicate, a negative number, a boolean, a fractional number and 1000, each naming `todo/plan.json` and `phase_list`, and accept 999. Cheaper substitute: accepting any JSON value must fail the type tests.
- [x] Check a section's `**Phase:**` (`:966`) and the keys of `phases` (`:1190`) against the configured list in `todo_graph.py`, not the constant. Done when: a test tree with `**Phase:** 12` validates when `phase_list` holds 12 and refuses with `invalid Phase` when it does not; a name for phase 12 is accepted and shown in the generated plan, and a name for a phase the list leaves out is refused.
- [x] Order phases in `todo_graph.py` one way everywhere (`phase_rank`: numeric, with the manual phase 99 last when the list runs past it), for the generated plan, `ordered()` and the check that refuses a prerequisite in a later phase. Done when: a test with `phase_list` of `[0, 12, 3]` renders the phases in the order 0, 3, 12, and one of `[0, 99, 100]` orders 100 before 99, accepts a manual section that depends on phase 100 and refuses a phase-100 section that depends on the manual one.
- [x] Keep today's behaviour with no key: a `plan.json` without `phase_list` accepts exactly 0 to 7 and 99. Done when: the existing phase tests in `tests/test_todo_graph.py` pass unchanged and a new test refuses phase 8 under the default.
- [x] Document `phase_list` in `kits/todo/templates/todo/README.md` (What every section declares), copy the file over the SDK's own `todo/README.md`, and run `python forge.py self-sync`. Done when: the two READMEs are identical and `scripts/lib/todo_graph.py` equals the kit file.
- [x] Commit: `todo: phase numbers come from todo/plan.json`

**Corrected 2026-11-13 (plan review):** the manual phase is last in the dependency check and `ordered()` too, not only in the plan; the `phases` name map is tested against the configured list; and the type and bound refusals add a fractional number and 1000, with 999 accepted.

**Test checkpoint:** `python -m unittest discover -s tests -p test_todo_graph.py` ends `OK`; checking the constant in place of the configured list makes the phase 12 test fail.

> **Verified:** 2026-11-13 | §1 | e6ddddc7be41677a1eb5cd661acfef47e3d60a98
> **Review:** `docs/reviews/d03-t01-s1.json`

## 2. Needs values and waiting Needs read from `todo/plan.json`

> **Started:** 2026-11-13T02:27:48Z

RasterFold's Needs are `ffmpeg-jxl`, `network`, `gpu` and four more; the kit accepts ten values of its own and holds three of them out of the ready list. Both lists become keys.

**Phase:** 3
**Needs:** none
**Surface:** no

**Build order:**

1. Add `needs` and `waiting` to `plan_config` in `kits/todo/templates/scripts/lib/todo_graph.py`. Done when: a tree using a project's own Need validates.
2. Use the configured lists wherever `NEEDS` and `WAITING` are read. Done when: the checkpoint passes.

- [x] Accept optional `needs` and `waiting` keys in `plan_config` of `todo_graph.py`: each a list of distinct names matching `[a-z0-9][a-z0-9-]*`, `waiting` a subset of `needs`, defaulting to `NEEDS` and `WAITING`. Done when: tests refuse a non-list, a malformed name, a duplicate, the reserved name `none` (which a section's `**Needs:** none` means as no Need) and a `waiting` value that is not in `needs`, each naming the key.
- [x] Check a section's `**Needs:**` (`:978`) against the configured `needs` in `todo_graph.py`. Done when: a test tree with `**Needs:** gpu` validates when `needs` holds `gpu` and refuses naming the value when it does not.
- [x] Use the configured `waiting` list at the three places `WAITING` is read in `todo_graph.py`: the ready query (`disposition`, `:1151`), the stamp (`:1357`) and the stamped-section check (`:1026`). Done when: a test with `waiting` of `["gpu"]` finds a `gpu` section out of `query ready` and refused by `stamp` naming `gpu`, and an `owner-decision` section ready under that same plan; a stamp of the `gpu` section under a `waiting` without `gpu` succeeds, its receipt read back and the graph valid, and adding `gpu` to `waiting` afterwards makes the graph refuse it as a stamped section with a waiting Need. Cheaper substitute: changing only the ready query must fail the stamp assertion.
- [x] Keep today's behaviour with no keys. Done when: the existing Needs tests pass unchanged.
- [x] Document both keys in `kits/todo/templates/todo/README.md`, including that "Unattended runs never take" names the default values, copy it over `todo/README.md` and run `python forge.py self-sync`. Done when: the two READMEs are identical.
- [x] Commit: `todo: Needs values and waiting Needs come from todo/plan.json`

**Corrected 2026-11-13 (plan review):** `none` is reserved, since it is a section's no-Need sentinel; the stamped-section check is proven both ways with a real stamp; and the stamp tests run, not skipped: they are in the full suite (`CONCLAVE_FULL_TESTS=1`), run focused locally and by CI's Linux job.

**Corrected 2026-11-13 (validation):** the line references moved with `§1` (`:969` is `:978`, `:1142` is `disposition` at `:1151`, `:1342` is `:1357`, `:1017` is `:1026`); `disposition` and its callers in the CLI have no configuration, so each section carries its waiting Needs, worked out once from the configured `waiting` when the graph is built.

**Test checkpoint:** `python -m unittest discover -s tests -p test_todo_graph.py` ends `OK`, and with `CONCLAVE_FULL_TESTS=1` the waiting stamp tests run and pass; leaving the stamp on the constant `WAITING` makes the `gpu` stamp test fail.

> **Verified:** 2026-11-13 | §2 | 2b3bd843a297779439e53180309d9609422a9277
> **Review:** `docs/reviews/d03-t01-s2.json`

## 3. Caps read from `todo/plan.json`

> **Started:** 2026-11-13T02:47:41Z

The four size caps suit the SDK's own files. A project with longer sections sets its own, within bounds.

**Phase:** 3
**Needs:** none
**Surface:** no

**Build order:**

1. Add `caps` to `plan_config` in `kits/todo/templates/scripts/lib/todo_graph.py`. Done when: a 40 item section validates under a cap of 40.
2. Cover the bounds. Done when: the checkpoint passes.

- [x] Accept an optional `caps` key in `plan_config` of `todo_graph.py`: an object with any of `sections_per_file` (1 to 200), `items_per_section` (2 to 200, since a section needs one work item and its `Commit:`), `deliverable_len` (20 to 200) and `table_row` (60 to 400), each a whole number (not a boolean or a fraction) defaulting to its constant. Done when: tests refuse a `caps` that is not an object, an unknown cap name, each cap one past either bound, a boolean, a fraction and a string, each naming `todo/plan.json`, `caps` and the name; they accept each bound; and a cap left out keeps its default.
- [x] Use the configured caps at the four checks in `todo_graph.py` (`:954` sections per file, `:975` deliverable, `:1009` items per section and the plan's table row check at `:1260`). Done when: a test section with 40 items validates under `items_per_section` of 40 and refuses under the default and at 39; a two-item section validates at 2; a 100 character Deliverable and a 100 character heading each validate under `deliverable_len` of 100 and refuse under the default; a file of 60 sections validates under `sections_per_file` of 60 and refuses at 59 and under the default; and a lowered cap (`items_per_section` of 3) refuses a four-item section.
- [x] Leave the review caps where they are: `REVIEW_ROUND_CAP` and the pass cap belong to the reviewer pin (`.conclave/reviewers.toml`), not `plan.json`. Done when: a test with `"caps": {"pass_cap": 45}` refuses it as an unknown cap name.
- [x] Name the configured caps beside the defaults wherever the kit's agent guidance states a fixed one: `add-todo`, `create-todo` and `groom-plan` in `.claude/`, `.agents/` and `.codex/`, and `docs/todo-workflow.md`, under `kits/todo/templates/`, then run `python forge.py self-sync`. Done when: each of those files names `todo/plan.json` `caps` beside 30, 55 and 88 where it states them, the three agents' copies match, and `python -m unittest tests.test_forge` passes.
- [x] Document `caps` in `kits/todo/templates/todo/README.md`, copy it over `todo/README.md` and run `python forge.py self-sync`. Done when: the two READMEs are identical.
- [x] Commit: `todo: size caps come from todo/plan.json`

**Corrected 2026-11-13 (plan review):** the agent skills and `docs/todo-workflow.md` state the caps too, so they name the configured ones; `sections_per_file` and both sides of `deliverable_len` get tests both ways, with a lowered cap; the caps are whole numbers with typed refusals and tested bounds; and `items_per_section` starts at 2, the fewest a section can hold (the README's `1 to 30` is corrected with it).

**Corrected 2026-11-13 (validation):** the checks moved (`:942`, `:963` and `:996` are `:954`, `:975` and `:1009`), and the table row cap is read by the plan's projection at `:1260`, which pads every row to the widest Deliverable: a longer `deliverable_len` needs a longer `table_row`, so the README says so and a test shows the plan refusing a 100 character Deliverable under the default row cap and rendering it under a raised one.

**Test checkpoint:** `python -m unittest discover -s tests -p test_todo_graph.py` ends `OK`; ignoring the configured `items_per_section` makes the 40 item test fail.

> **Verified:** 2026-11-13 | §3 | 0db1979078fc87d3bb49c2be76789ce13b387602
> **Review:** `docs/reviews/d03-t01-s3.json`

## 4. Receipts folder read from `todo/plan.json`

> **Started:** 2026-11-13T03:19:14Z

Receipts and findings files go to `docs/reviews/` through literals in the graph, the pre-commit hook, the dispatcher, the prompt filler and the skills' commands. A project that keeps reviews elsewhere states the folder once.

**Phase:** 3
**Needs:** none
**Surface:** no

**Build order:**

1. Add `layout.receipts` to `plan_config` in `kits/todo/templates/scripts/lib/todo_graph.py` and route every `docs/reviews/` literal in the todo and reviewer kits through it. Done when: a stamp writes its receipt under the configured folder.
2. Run the full suite, because this touches the stamp. Done when: the checkpoint passes.

- [x] Accept an optional `layout` key in `plan_config` of `todo_graph.py`: an object whose `receipts` member (default `docs/reviews`) is a non-empty relative POSIX path with no leading slash, backslash, drive letter or `.` or `..` segment, that stays inside the repository through any symlink or junction. Done when: tests refuse a `layout` that is not an object, an unknown member, a non-string, an empty string, an absolute path, `C:/reviews`, a backslash, a `..` segment and a folder that is a symlink out of the repository, each naming `todo/plan.json` and `layout`, and a `layout` without `receipts` keeps `docs/reviews`.
- [x] Replace the `docs/reviews/` literals in `todo_graph.py` (the receipt check at `:214`, the findings file check at `:303`, the findings path at `:426`, the receipt path at `:1397` and `LEGACY_RECEIPTS` at `:44`) with paths built from the configured `receipts`. Done when: `grep -n "docs/reviews" kits/todo/templates/scripts/lib/todo_graph.py` shows only the default and comments.
- [x] Read the folder in the reviewer kit from `todo/plan.json` when it is there, with the graph's path rules: `SECTION_FINDINGS` in `kits/reviewer/templates/scripts/review-dispatch.py` (`:853`), the `--list-rounds` default folder (`:1314`) and the findings placeholder in `kits/reviewer/templates/scripts/review-prompt.py` (`:133`). Done when: reviewer-kit tests with `receipts` set to `reviews` find `reviews/03-x/D03-T01-s1.md` treated as a section's findings file and `docs/reviews/03-x/D03-T01-s1.md` not, `--list-rounds` without a folder list a findings file under `reviews/`, an explicit folder still wins, the prompt's findings placeholder fills under `reviews/`, a malformed `layout` is refused with the graph's message, and nothing changes without the key.
- [x] Prove the two readers agree in `tests/test_todo_graph.py`: one table of `layout` values run through `plan_config` and the reviewer kit's reader. Done when: each value is accepted by both with the same folder or refused by both. Cheaper substitute: testing each reader alone must fail review, because the kits would drift apart unseen.
- [x] Write the commands in `process-todo-section` and `review-todo-section` in `.claude/`, `.agents/` and `.codex/` under `kits/todo/templates/` with `<receipts>/` where they write `docs/reviews/` (the plan review's `--record`, the round's and the completion's, and the stamp's `--plan`, `--completion` and `--review`), saying once that `<receipts>` is `layout.receipts` in `todo/plan.json`, `docs/reviews` by default. Done when: a test finds no `docs/reviews/` in any command line of those six files.
- [x] Read the receipts folder in `kits/todo/templates/scripts/hooks/pre-commit` from the graph (`scripts/todo-graph.py`), for the trigger and the unstaged and untracked checks. Done when: `tests/test_pre_commit_hook.py` shows, with `receipts` set to `reviews`, a commit touching only `reviews/` checked, an unstaged change under `reviews/` refused, a fully staged valid commit accepted and a malformed `layout` refused with the graph's message.
- [x] Stamp, validate, unstamp and validate again under a configured folder in `tests/test_three_pass_install.py`. Done when: with `CONCLAVE_FULL_TESTS=1` the fresh-install test, with `receipts` set to `reviews`, reads the receipt back at `reviews/<slug>.json`, finds nothing under `docs/reviews/`, and after `unstamp` finds the revoked receipt under `reviews/` and the section reopened. Cheaper substitute: a unit test of the path helper alone must fail review, because the hook and the dispatcher also read the folder.
- [x] Document `layout.receipts` in `kits/todo/templates/todo/README.md`, copy it over `todo/README.md` and run `python forge.py self-sync`. Done when: the two READMEs are identical.
- [x] Commit: `todo: the receipts folder comes from todo/plan.json`

**Corrected 2026-11-13 (validation):** the line references moved (`:202`, `:291`, `:414`, `:1351` and `:43` are `:214`, `:303`, `:426`, `:1397` and `:44`), and the reviewer kit reads the folder in three places the plan did not name: the dispatcher's `SECTION_FINDINGS`, its `--list-rounds` default and `review-prompt.py`'s findings placeholder, so an item covers them.

**Corrected 2026-11-13 (plan review):** the section is split: the plan path, whose destination can collide with a source file and which the hook must also check, moves to `§7`, and this section keeps the receipts folder. It adds the skills' commands that write the folder, the hook's trigger and unstaged checks, the full path rules with containment through links, the reviewer kit's listing and prompt behaviour with a test that both kits read the key alike, and an unstamp in the end to end proof.

**Test checkpoint:** with `CONCLAVE_FULL_TESTS=1` set, `python -m unittest discover -s tests` ends `OK` with the stamp tests run, not skipped; leaving the receipt path literal at `:1397` makes the configured-folder stamp test fail.

> **Verified:** 2026-11-13 | §4 | 5a8728885056401542175f9c8cbf9e95f4ff51ab
> **Review:** `docs/reviews/d03-t01-s4.json`

## 5. Adoption dry run on RasterFold and Impossible OS

> **Started:** 2026-11-13T05:35:33Z

The keys above remove the differences that were known. What else stops each project is measured, not guessed: the kit's validator runs on a scratch copy of each tree and every class of refusal is recorded.

**Phase:** 3
**Needs:** none
**Surface:** no

**Build order:**

1. Copy each project's `todo/` tree to scratch with a `plan.json` written for it and run the kit's `validate` until it stops finding new classes of refusal. Done when: each refusal class is counted.
2. Write the report and file the sections it calls for. Done when: the checkpoint passes.

- [ ] Add `scripts/adoption-dry-run.py` to the SDK (not to a kit): clone the project with its history into a scratch folder (`git clone --local`), copy its working tree's `todo/` and its receipts folder over the clone so uncommitted work is measured too, write a `todo/plan.json` from arguments, run `§8`'s every-fault validation through the kit library with the scratch folder as its explicit root, and print the refusal classes (each fault's message with its section, path and numbers taken out) with a count of sections and one example each. Done when: a test on a fixture tree with two planted faults reports both classes and writes nothing outside its scratch folder. Cheaper substitute: running `validate` once must fail review, because it stops at the first refusal and reports one class.
- [ ] Run it on RasterFold at its current commit with a `plan.json` holding its seven Needs keys and its phase numbers, and record the commit. Done when: the output is saved under the session scratch folder and its classes are listed in the report below, and `git -C ~/projects/RasterFold status --short` is unchanged.
- [ ] Run it on Impossible OS in the same way. Done when: its classes are listed in the report and its tree is unchanged.
- [ ] Write `docs/plans/<date>-todo-graph-adoption.md`: for each project, a table of refusal class, count, an example, and the decision (a new `plan.json` key, a kit change, or the project's files change), with RasterFold's host `Requires` gate (`REQUIRES_ALLOWED`, `:264`) and Impossible OS's missing Needs field each given a row. Done when: every class from the two runs has a row and a decision, and the table rows are within 120 characters.
- [ ] Check the kit's agent guidance against each project's `caps` in the `plan.json` written for it: the guard `test_the_kit_guidance_names_the_configured_cap_wherever_it_states_a_default` in `tests/test_todo_graph.py` covers the stated defaults, so read `add-todo`, `create-todo` and `groom-plan` for any other limit the project's caps contradict. Done when: the report's guidance row names each line that would mislead an agent working that project, or says none (filed from `D03 T01 §3`'s completion review).
- [ ] File a section through `add-todo` for each decision that is a kit change, in this file, and name each in the report. Done when: `python scripts/todo-graph.py validate` passes and the report's kit-change rows each carry a `D03 T01 §N` reference. Cheaper substitute: a list of follow-ups in the report with no section must fail review.
- [ ] Commit: `todo: measure what stops RasterFold and Impossible OS adopting the graph`

- [ ] Record what was measured beside the output: the manifest of copied files with their SHA-256 digests, the effective `todo/plan.json`, the project's commit and the SDK commit whose validator ran; and digest the source files before and after. Done when: a fixture test with an already-dirty source file finds its digest in the manifest and the source unchanged after the run, a test of a valid stamped section in the snapshot reports no fault (its history and receipts came along), a genuinely broken receipt is reported, and a fault planted only in the scratch copy is found while the SDK's own tree validates.

**Corrected 2026-11-13 (plan review):** the validator reports every fault itself (new `§8`, `validate --all`), so nothing is set aside and no file's later faults are hidden; the snapshot is a clone with history plus the working tree's `todo/` and receipts folder (Impossible OS's `.claude/overnight/reviews` too), so stamped sections validate as they do at home; the kit library runs with the scratch folder as its explicit root; and the run records its inputs' digests and leaves the sources' bytes as they were.

**Corrected 2026-11-13 (validation):** read at RasterFold `bf30b38` and Impossible OS `9f86baf50` (both trees carry another session's uncommitted work, so the dry run only ever copies from them): RasterFold's seven Needs are free-text phrases (`Idle machine (timing)` 44 times, `ffmpeg with libjxl (benchmarks)` 34, then `Network (downloads)`, `Windows host (build/test)`, `GPU (compute)`, `FPGA board` and `ARM64 device`), so its `plan.json` names each as a slug and the phrases are a refusal class of their own; neither project writes a `**Phase:**` field; Impossible OS keeps its receipts in `.claude/overnight/reviews` (`§4`'s `layout.receipts` takes it) and holds 2,595 sections; and `REQUIRES_ALLOWED` is at `scripts/todo-graph.py:264` as named.

**Test checkpoint:** `python -m unittest discover -s tests` ends `OK` with the dry-run script's fixture test in it, and `python scripts/todo-graph.py validate` passes; removing a planted fault's class from the script's output makes the fixture test fail.

## 6. Lift or leave decision for each RasterFold graph command

RasterFold's graph is ten times the kit's and has commands the kit lacks (roadmap finding 7). Each is read and given a decision: lift it into the kit as its own section, or leave it with the project and say why.

**Phase:** 3
**Needs:** none
**Surface:** no

**Build order:**

1. Read each RasterFold command the kit lacks. Done when: each has a line count, what it does and what it depends on.
2. Decide and file. Done when: the checkpoint passes.

- [ ] List in `docs/plans/<date>-todo-graph-adoption.md` the subcommands `warnings`, `self-test`, `needs`, `progress` and the design baseline command, and the `query` kinds `frozen`, `findings`, `surfaces`, `calibration`, `sequence`, `plan-health`, `summary`, `run`, `budget`, `backlog` and `growth`, from RasterFold's `scripts/todo-graph.py:12687` to `:12790`, each with its function, its size and the project files it reads. Done when: all sixteen have a row.
- [ ] Decide each row: `lift` when it reads only the `todo/` tree and the receipts and would serve any project, `leave` when it reads RasterFold's own files (`budget.json`, `backlog.md`, release tags), with the reason in the row. Done when: no row is undecided. Cheaper substitute: marking everything `leave` to close the section must fail review; `self-test` and `sequence` read only the tree and need a stated reason either way.
- [ ] Do the same for the sibling scripts the graph loads (`todo-validate.py`, `todo-adjacency.py`, `todo-findings.py`, 4,207 lines together): what each checks that the kit's validator does not. Done when: the report has one row per check the kit lacks.
- [ ] File a section through `add-todo` for each `lift` row, in this file or a second file in this domain when the count passes 55 sections, with the RasterFold function and commit as its source. Done when: `python scripts/todo-graph.py validate` passes and every `lift` row carries its section reference.
- [ ] Commit: `todo: lift or leave decision for each RasterFold graph command`

**Test checkpoint:** `python scripts/todo-graph.py validate` and `python scripts/todo-graph.py plan --check` pass with the new sections in the plan; a `lift` row with no section reference fails the report's own check (`grep -c "lift" ` against `grep -c "D03 T"` in the table, which must match).

## 7. Plan path read from `todo/plan.json`

> **Started:** 2026-11-13T04:18:35Z

The generated plan is written to `todo/implementation-plan.md`. A project that keeps it elsewhere states the path once, and the path can never land on a file the plan does not own.

**Phase:** 3
**Needs:** none
**Surface:** no

**Build order:**

1. Add `layout.plan` to `plan_config` in `kits/todo/templates/scripts/lib/todo_graph.py` with its collision refusals, and read it wherever `PLAN` is read. Done when: `plan --sync` writes the configured path.
2. Cover the hook and the stamp's write and rollback. Done when: the checkpoint passes.

- [x] Accept `plan` in `layout` in `plan_config` of `todo_graph.py` (default `todo/implementation-plan.md`) under `§4`'s path rules, ending `.md`, and refuse a destination the plan does not own: `todo/plan.json`, `todo/README.md`, any file in a `todo/NN-domain/` folder, any path in the receipts folder, and an existing file that does not carry the generated plan's notice (the stable `Generated by ... plan --sync; do not edit by hand` line, not the title, which `title` changes). Done when: tests refuse each before anything is written, naming `todo/plan.json` and `layout`; a plan regenerates in place after `title` changes; an unrelated document with the same heading is refused and left byte for byte; and a `layout` without `plan` keeps the default.
- [x] Accept `plan` beside `receipts` in the reviewer kit's `kits/reviewer/templates/scripts/review_layout.py`, which checks only the key names it does not read. Done when: the readers' table in `tests/test_todo_graph.py` accepts `{"receipts": ..., "plan": ...}` in both readers, and with both keys set a reviewer-kit test runs a dispatch to a section's findings file, fills a prompt from `--ref` and lists the rounds.
- [x] Use the configured path wherever `PLAN` is read in `todo_graph.py`: `projections` (`:1326`), the stamp's plan write and rollback (`:1471`) and `unstamp` (`:1561`). Done when: a test with `plan` set to `docs/plan.md` finds `plan --sync` writing there, `plan --check` reading there and nothing at `todo/implementation-plan.md`.
- [x] Read the plan path in `kits/todo/templates/scripts/hooks/pre-commit` from the graph through a `todo-graph.py plan-path` query beside `§4`'s `receipts` (with its `--config -` for the staged `todo/plan.json`), for the trigger and the unstaged and untracked checks. Done when: `tests/test_pre_commit_hook.py` refuses, with `plan` set to `docs/plan.md`, a commit staging only a corrupted plan and a commit whose staged plan is stale while an unstaged copy is current, its message telling the operator to stage `docs/plan.md`, and accepts a fully staged valid commit.
- [x] Name the configured plan path beside the default wherever the todo kit's skills and `docs/todo-workflow.md` name `todo/implementation-plan.md` as a path to read or write. Done when: a guard test like `§3`'s finds every such mention naming `layout.plan` within 80 characters.
- [x] Stamp, validate, unstamp and validate again with both `receipts` and `plan` configured in `tests/test_three_pass_install.py`, and fail the stamp's plan write once. Done when: with `CONCLAVE_FULL_TESTS=1` the receipt is read back under the configured folder, the configured plan shows the section verified and then reopened, and after the failed write the TODO file, the receipt folder and the plan hold their bytes from before the stamp. Cheaper substitute: checking the plan's path alone must fail review, because the rollback writes it too.
- [x] Document `layout.plan` in `kits/todo/templates/todo/README.md`, copy it over `todo/README.md` and run `python forge.py self-sync`. Done when: the two READMEs are identical.
- [x] Commit: `todo: the plan path comes from todo/plan.json`

**Corrected 2026-11-13 (plan review):** the reviewer kit's reader accepts `plan` too, proven with both keys set; an owned plan is recognised by its generated notice, not its title; the hook's recovery message names the configured plan; and the checkpoint's mutation is the notice check, since the `.md` rule alone already refuses `todo/plan.json`.

**Corrected 2026-11-13 (validation):** the references moved with `§4` (`:1288` is `:1326`, the stamp's plan write is `:1471` and `unstamp`'s is `:1561`), and the hook reads the plan path the way `§4` made it read the receipts folder: a CLI query, watched for the staged and the working `todo/plan.json` alike.

**Test checkpoint:** with `CONCLAVE_FULL_TESTS=1` set, `python -m unittest discover -s tests` ends `OK` with the stamp tests run, not skipped; leaving `projections` on the constant `PLAN` makes the `docs/plan.md` test fail, and dropping the notice check makes the unrelated document's test fail with its bytes changed.

> **Verified:** 2026-11-13 | §7 | f0ec67fb65b61484c6b29682682218188a49324a
> **Review:** `docs/reviews/d03-t01-s7.json`

## 8. Every validation fault in one run

`validate` stops at the first refusal, so a tree with many faults shows them one at a time. Measuring another project's tree, or repairing a large one, needs every fault at once, the way `review_pin.py --check --all` lists a pin's.

**Phase:** 3
**Needs:** none
**Surface:** no

**Build order:**

1. Give `graph` in `kits/todo/templates/scripts/lib/todo_graph.py` a mode that records each refusal and goes on. Done when: a tree with two faulty files reports both.
2. Expose it as `validate --all`. Done when: the checkpoint passes.

- [ ] Add a `faults` list argument to `graph` in `todo_graph.py`: given one, a refusal in a file's front matter or tables is recorded with the file's path and the rest of that file skipped, a refusal in a section is recorded with its reference and the next section read, and the cross-file checks run over what was read. Done when: a test tree with two faults in different sections of one file and one in another file reports all three, and `graph` without the list still raises the first.
- [ ] Count no fault that only follows from another: a reference to a section whose own reading failed is not reported as unknown, and its dependants are not reported for phase order or cycles through it. Done when: a test whose section 2 has a bad Phase and whose section 3 depends on it reports one fault, not two.
- [ ] Add `validate --all` to `kits/todo/templates/scripts/todo-graph.py`: one line per fault, `<path or reference>: <message>`, in file order, then exit 2; `valid: N sections` and exit 0 when there is none. Done when: a test runs the command on a faulty tree and reads the lines and the exit code, and on the SDK's own tree reads `valid`.
- [ ] Document `validate --all` in `kits/todo/templates/todo/README.md`, copy it over `todo/README.md` and run `python forge.py self-sync`. Done when: the two READMEs are identical.
- [ ] Commit: `todo: validate --all reports every fault in one run`

**Test checkpoint:** `python -m unittest discover -s tests -p test_todo_graph.py` ends `OK`; letting a section's refusal end the run (raising in place of recording) makes the three-fault test fail.

## Verification

- A scratch project whose `todo/plan.json` sets `phase_list`, `needs`, `waiting`, `caps` and `layout` validates a tree written to those values, stamps a section and regenerates its plan.
- The SDK's own tree, with none of those keys, validates and stamps exactly as before: `CONCLAVE_FULL_TESTS=1 python -m unittest discover -s tests` passes.
- The adoption report exists and every kit-change and `lift` row names a section.
- `python scripts/todo-graph.py validate` and `python scripts/todo-graph.py plan --check` pass.
