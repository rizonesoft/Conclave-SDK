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
| 2 | §2 | Needs values and waiting Needs read from `todo/plan.json` | §1 | [ ] |
| 3 | §3 | Caps read from `todo/plan.json` | §1 | [ ] |
| 4 | §4 | Receipts folder and plan path read from `todo/plan.json` | §1 | [ ] |
| 5 | §5 | Adoption dry run on RasterFold and Impossible OS | §2, §3, §4 | [ ] |
| 6 | §6 | Lift or leave decision for each RasterFold graph command | §5 | [ ] |

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
- [ ] Commit: `todo: Needs values and waiting Needs come from todo/plan.json`

**Corrected 2026-11-13 (plan review):** `none` is reserved, since it is a section's no-Need sentinel; the stamped-section check is proven both ways with a real stamp; and the stamp tests run, not skipped: they are in the full suite (`CONCLAVE_FULL_TESTS=1`), run focused locally and by CI's Linux job.

**Corrected 2026-11-13 (validation):** the line references moved with `§1` (`:969` is `:978`, `:1142` is `disposition` at `:1151`, `:1342` is `:1357`, `:1017` is `:1026`); `disposition` and its callers in the CLI have no configuration, so each section carries its waiting Needs, worked out once from the configured `waiting` when the graph is built.

**Test checkpoint:** `python -m unittest discover -s tests -p test_todo_graph.py` ends `OK`, and with `CONCLAVE_FULL_TESTS=1` the waiting stamp tests run and pass; leaving the stamp on the constant `WAITING` makes the `gpu` stamp test fail.

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
- [ ] Commit: `todo: size caps come from todo/plan.json`

**Corrected 2026-11-13 (plan review):** the agent skills and `docs/todo-workflow.md` state the caps too, so they name the configured ones; `sections_per_file` and both sides of `deliverable_len` get tests both ways, with a lowered cap; the caps are whole numbers with typed refusals and tested bounds; and `items_per_section` starts at 2, the fewest a section can hold (the README's `1 to 30` is corrected with it).

**Corrected 2026-11-13 (validation):** the checks moved (`:942`, `:963` and `:996` are `:954`, `:975` and `:1009`), and the table row cap is read by the plan's projection at `:1260`, which pads every row to the widest Deliverable: a longer `deliverable_len` needs a longer `table_row`, so the README says so and a test shows the plan refusing a 100 character Deliverable under the default row cap and rendering it under a raised one.

**Test checkpoint:** `python -m unittest discover -s tests -p test_todo_graph.py` ends `OK`; ignoring the configured `items_per_section` makes the 40 item test fail.

## 4. Receipts folder and plan path read from `todo/plan.json`

Receipts and findings files go to `docs/reviews/` through string literals in four places. A project that keeps reviews elsewhere states the folder once.

**Phase:** 3
**Needs:** none
**Surface:** no

**Build order:**

1. Add `layout` to `plan_config` in `kits/todo/templates/scripts/lib/todo_graph.py` and route every `docs/reviews/` literal through it. Done when: a stamp writes its receipt under the configured folder.
2. Run the full suite, because this touches the stamp. Done when: the checkpoint passes.

- [ ] Accept an optional `layout` key in `plan_config` of `todo_graph.py`: an object with `receipts` (default `docs/reviews`) and `plan` (default `todo/implementation-plan.md`), each a relative path with no `..`, no leading slash and no backslash. Done when: tests refuse an absolute path, a `..` segment and an unknown layout name, each naming `layout`.
- [ ] Replace the `docs/reviews/` literals in `todo_graph.py` (the receipt check at `:202`, the findings file check at `:291`, the findings path at `:414`, the receipt path at `:1351` and `LEGACY_RECEIPTS` at `:43`) with paths built from the configured `receipts`. Done when: `grep -n "docs/reviews" kits/todo/templates/scripts/lib/todo_graph.py` shows only the default and comments.
- [ ] Use the configured `plan` path wherever `PLAN` is read in `todo_graph.py`. Done when: a test with `plan` set to `docs/plan.md` finds `plan --sync` writing there and `plan --check` reading there.
- [ ] Pass the receipts folder to the dispatcher: `kits/reviewer/templates/scripts/review-dispatch.py` writes findings files where `--record` says, so check that `review-todo-section` in the three agent folders builds its `--record` path from the configured folder and not the literal. Done when: a test asserts the skill text names the configured folder's source (`todo/plan.json`) beside the default.
- [ ] Stamp a section end to end under a configured folder in `tests/test_three_pass_install.py`. Done when: with `CONCLAVE_FULL_TESTS=1` the fresh-install test stamps with `receipts` set to `reviews` and finds the receipt at `reviews/<slug>.json` and nothing under `docs/reviews/`. Cheaper substitute: a unit test of the path helper alone must fail review, because the pre-commit hook and the dispatcher also read the folder.
- [ ] Check `kits/todo/templates/scripts/hooks/pre-commit` for the `docs/reviews/` literal and read the folder from `todo/plan.json` there too. Done when: `tests/test_pre_commit_hook.py` passes with a configured folder.
- [ ] Document `layout` in `kits/todo/templates/todo/README.md`, copy it over `todo/README.md` and run `python forge.py self-sync`. Done when: the two READMEs are identical.
- [ ] Commit: `todo: receipts folder and plan path come from todo/plan.json`

**Test checkpoint:** with `CONCLAVE_FULL_TESTS=1` set, `python -m unittest discover -s tests` ends `OK` with the stamp tests run, not skipped; leaving the receipt path literal at `:1351` makes the configured-folder stamp test fail.

## 5. Adoption dry run on RasterFold and Impossible OS

The keys above remove the differences that were known. What else stops each project is measured, not guessed: the kit's validator runs on a scratch copy of each tree and every class of refusal is recorded.

**Phase:** 3
**Needs:** none
**Surface:** no

**Build order:**

1. Copy each project's `todo/` tree to scratch with a `plan.json` written for it and run the kit's `validate` until it stops finding new classes of refusal. Done when: each refusal class is counted.
2. Write the report and file the sections it calls for. Done when: the checkpoint passes.

- [ ] Add `scripts/adoption-dry-run.py` to the SDK (not to a kit): copy a project's `todo/` and `docs/reviews/` into a scratch folder, write a `todo/plan.json` from arguments, run the kit's `validate` with each refusal caught and the offending file set aside, and print the refusal classes with a count and one example each. Done when: a test on a fixture tree with two planted faults reports both classes and writes nothing outside its scratch folder. Cheaper substitute: running `validate` once must fail review, because it stops at the first refusal and reports one class.
- [ ] Run it on RasterFold at its current commit with a `plan.json` holding its seven Needs keys and its phase numbers, and record the commit. Done when: the output is saved under the session scratch folder and its classes are listed in the report below, and `git -C ~/projects/RasterFold status --short` is unchanged.
- [ ] Run it on Impossible OS in the same way. Done when: its classes are listed in the report and its tree is unchanged.
- [ ] Write `docs/plans/<date>-todo-graph-adoption.md`: for each project, a table of refusal class, count, an example, and the decision (a new `plan.json` key, a kit change, or the project's files change), with RasterFold's host `Requires` gate (`REQUIRES_ALLOWED`, `:264`) and Impossible OS's missing Needs field each given a row. Done when: every class from the two runs has a row and a decision, and the table rows are within 120 characters.
- [ ] Check the kit's agent guidance against each project's `caps` in the `plan.json` written for it: the guard `test_the_kit_guidance_names_the_configured_cap_wherever_it_states_a_default` in `tests/test_todo_graph.py` covers the stated defaults, so read `add-todo`, `create-todo` and `groom-plan` for any other limit the project's caps contradict. Done when: the report's guidance row names each line that would mislead an agent working that project, or says none (filed from `D03 T01 §3`'s completion review).
- [ ] File a section through `add-todo` for each decision that is a kit change, in this file, and name each in the report. Done when: `python scripts/todo-graph.py validate` passes and the report's kit-change rows each carry a `D03 T01 §N` reference. Cheaper substitute: a list of follow-ups in the report with no section must fail review.
- [ ] Commit: `todo: measure what stops RasterFold and Impossible OS adopting the graph`

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

## Verification

- A scratch project whose `todo/plan.json` sets `phase_list`, `needs`, `waiting`, `caps` and `layout` validates a tree written to those values, stamps a section and regenerates its plan.
- The SDK's own tree, with none of those keys, validates and stamps exactly as before: `CONCLAVE_FULL_TESTS=1 python -m unittest discover -s tests` passes.
- The adoption report exists and every kit-change and `lift` row names a section.
- `python scripts/todo-graph.py validate` and `python scripts/todo-graph.py plan --check` pass.
