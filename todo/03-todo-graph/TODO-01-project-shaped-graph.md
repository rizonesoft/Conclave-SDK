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
| 6 | §8 | Every validation fault in one run | §1 | [x] |
| 7 | §5 | Adoption dry run on RasterFold and Impossible OS | §2, §3, §4, §7, §8 | [x] |
| 8 | §6 | Lift or leave decision for each RasterFold graph command | §5 | [x] |
| 9 | §9 | Pre-adoption stamps frozen at adoption | §4 | [ ] |
| 10 | §10 | Ready rows filtered by the hosts this session reaches | -- | [ ] |
| 11 | §11 | Root index that lists domains | §7 | [ ] |
| 12 | §12 | Validation git calls cached per run | -- | [x] |
| 13 | §13 | Section checks run when its table row cannot be read | §8 | [x] |
| 14 | §14 | Frozen files listed by `query frozen` | -- | [x] |
| 15 | §15 | Longest chain and filing couplings from `query sequence` | -- | [ ] |

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

- [x] Add `scripts/adoption-dry-run.py` to the SDK (not to a kit): clone the project with its history into a scratch folder (`git clone --local`), copy its working tree's `todo/` and its receipts folder over the clone so uncommitted work is measured too, write a `todo/plan.json` from arguments, run `§8`'s every-fault validation through the kit library with the scratch folder as its explicit root, and print the refusal classes (each fault's message with its section, path and numbers taken out) with a count of sections and one example each. Every git command it runs against a source repository passes `--no-optional-locks`, so it never takes the source's `index.lock` from under a live campaign's commit. Done when: a test on a fixture tree with two planted faults reports both classes and writes nothing outside its scratch folder, and a test finds `--no-optional-locks` on every git call the script makes against the source. Cheaper substitute: running `validate` once must fail review, because it stops at the first refusal and reports one class.
- [x] Run it on RasterFold at its current commit with a `plan.json` holding its seven Needs keys and its phase numbers, and record the commit. Done when: the output is saved under the session scratch folder, its classes are listed in the report below, and its manifest names the commit and every source file the project's own campaign changed during the copy.
- [x] Run it on Impossible OS in the same way. Done when: its classes are listed in the report and its manifest is recorded as RasterFold's is.
- [x] Write `docs/plans/<date>-todo-graph-adoption.md`: for each project, a table of refusal class, count, an example, and the decision (a new `plan.json` key, a kit change, or the project's files change), with RasterFold's host `Requires` gate (`REQUIRES_ALLOWED`, `:264`) and Impossible OS's missing Needs field each given a row. Done when: every class from the two runs has a row and a decision, and the table rows are within 120 characters.
- [x] Check the kit's agent guidance against each project's `caps` in the `plan.json` written for it: the guard `test_the_kit_guidance_names_the_configured_cap_wherever_it_states_a_default` in `tests/test_todo_graph.py` covers the stated defaults, so read `add-todo`, `create-todo` and `groom-plan` for any other limit the project's caps contradict. Done when: the report's guidance row names each line that would mislead an agent working that project, or says none (filed from `D03 T01 §3`'s completion review).
- [x] File a section through `add-todo` for each decision that is a kit change, in this file, and name each in the report. Done when: `python scripts/todo-graph.py validate` passes and the report's kit-change rows each carry a `D03 T01 §N` reference. Cheaper substitute: a list of follow-ups in the report with no section must fail review.
- [x] Record what was measured beside the output: the manifest of copied files with their SHA-256 digests, the effective `todo/plan.json`, the project's commit and the SDK commit whose validator ran. After copying, digest the copied source files again; when any changed (the project's campaign edited it mid-copy), copy again, at most three times, and list the files that moved in the manifest, so a torn snapshot never reports refusal classes the tree does not have. Done when: a fixture test with an already-dirty source file finds its digest in the manifest and the source's bytes unchanged after the run, a fixture test that changes a source file during the first copy finds the second copy consistent and the file listed as moved, a test of a valid stamped section in the snapshot reports no fault (its history and receipts came along), a genuinely broken receipt is reported, and a fault planted only in the scratch copy is found while the SDK's own tree validates.
- [x] Commit: `todo: measure what stops RasterFold and Impossible OS adopting the graph`

**Corrected 2026-11-13 (plan review):** the validator reports every fault itself (new `§8`, `validate --all`), so nothing is set aside and no file's later faults are hidden; the snapshot is a clone with history plus the working tree's `todo/` and receipts folder (Impossible OS's `.claude/overnight/reviews` too), so stamped sections validate as they do at home; the kit library runs with the scratch folder as its explicit root; and the run records its inputs' digests and leaves the sources' bytes as they were.

**Corrected 2026-11-13 (validation):** read at RasterFold `bf30b38` and Impossible OS `9f86baf50` (both trees carry another session's uncommitted work, so the dry run only ever copies from them): RasterFold's seven Needs are free-text phrases (`Idle machine (timing)` 44 times, `ffmpeg with libjxl (benchmarks)` 34, then `Network (downloads)`, `Windows host (build/test)`, `GPU (compute)`, `FPGA board` and `ARM64 device`), so its `plan.json` names each as a slug and the phrases are a refusal class of their own; neither project writes a `**Phase:**` field; Impossible OS keeps its receipts in `.claude/overnight/reviews` (`§4`'s `layout.receipts` takes it) and holds 2,595 sections; and `REQUIRES_ALLOWED` is at `scripts/todo-graph.py:264` as named.

**Corrected 2026-11-13 (live campaigns):** both projects run campaigns while this section runs (RasterFold holds `build/claude-campaign-guard.json`; Impossible OS committed `ca1de2af8` past the `9f86baf50` read above). A plain `git status` refreshes the index under `index.lock` and can fail a campaign's `git add` or `commit`, so the script's source git calls use `--no-optional-locks`; and a live tree changes for reasons of its own, so "status unchanged" was not a proof the dry run wrote nothing. The fixture tests prove that, and the run recopies when the source moved mid-copy.

**Corrected 2026-11-13 (build):** the clone is `git clone --no-hardlinks --no-checkout` then a detached checkout of the source's `HEAD`, not `--local` alone: `--local` hardlinks the object files into the scratch folder, so the snapshot would share files with the source, and a source on a detached `HEAD` would check out nothing. The stamped-section test runs the dry run on the SDK itself, under `CONCLAVE_FULL_TESTS=1`, since validating the SDK's tree takes a minute on Windows (filed as `§12`). The Impossible OS run measured file-level classes only, because the validator skips a section whose row it cannot read; that gap is filed as `§13`, and the report counts those sections' fields until it ships.

**Test checkpoint:** `python -m unittest discover -s tests` ends `OK` with the dry-run script's fixture test in it, and `python scripts/todo-graph.py validate` passes; removing a planted fault's class from the script's output makes the fixture test fail.

> **Verified:** 2026-11-13 | §5 | f7a2de4775dc65f326271897ca5fa9d729008522
> **Review:** `docs/reviews/d03-t01-s5.json`

## 6. Lift or leave decision for each RasterFold graph command

> **Started:** 2026-11-13T09:53:56Z

RasterFold's graph is ten times the kit's and has commands the kit lacks (roadmap finding 7). Each is read and given a decision: lift it into the kit as its own section, or leave it with the project and say why.

**Phase:** 3
**Needs:** none
**Surface:** no

**Build order:**

1. Read each RasterFold command the kit lacks. Done when: each has a line count, what it does and what it depends on.
2. Decide and file. Done when: the checkpoint passes.

- [x] List in `docs/plans/<date>-todo-graph-adoption.md` the subcommands `warnings`, `self-test`, `needs`, `progress` and the design baseline command, and the `query` kinds `frozen`, `findings`, `surfaces`, `calibration`, `sequence`, `plan-health`, `summary`, `run`, `budget`, `backlog` and `growth`, from RasterFold's `scripts/todo-graph.py:12687` to `:12790`, each with its function, its size and the project files it reads. Done when: all sixteen have a row.
- [x] Decide each row: `lift` when it reads only the `todo/` tree and the receipts and would serve any project, `leave` when it reads RasterFold's own files (`budget.json`, `backlog.md`, release tags), with the reason in the row. Done when: no row is undecided. Cheaper substitute: marking everything `leave` to close the section must fail review; `self-test` and `sequence` read only the tree and need a stated reason either way.
- [x] Do the same for the sibling scripts the graph loads (`todo-validate.py`, `todo-adjacency.py`, `todo-findings.py`, 4,207 lines together): what each checks that the kit's validator does not. Done when: the report has one row per check the kit lacks.
- [x] File a section through `add-todo` for each `lift` row, in this file or a second file in this domain when the count passes 55 sections, with the RasterFold function and commit as its source. Done when: `python scripts/todo-graph.py validate` passes and every `lift` row carries its section reference.
- [x] Write the two inventories into the report as fenced blocks, each taken mechanically from RasterFold at `75be196`: the commands (the `add_parser` names and the `query` `choices` the kit lacks, `scripts/todo-graph.py:12879` to `:12990`) and the checks (the 58 class names of `SEVERITY_MAP`, `:839` to `:1038`, plus the adjacency and findings checks the two sibling scripts raise outside it). Done when: each block names its source lines and the command that listed it.
- [x] Add `tests/test_adoption_report.py`: for each table, every inventory entry has exactly one row and every row names an inventory entry; each row's decision is `lift` or `leave`; a `leave` row gives a reason; a `lift` row names a `D03 T01 §N` (or another `DNN TNN §N`) that the graph resolves and whose body names the lifted command or check. Done when: the test passes on the report, and fails on copies of it with a lift row's reference removed, a reference to a section that does not exist, a row duplicated and an inventory entry with no row. Cheaper substitute: comparing `grep -c` counts must fail review, because a missing reference on one row is offset by one on another.
- [x] Commit: `todo: lift or leave decision for each RasterFold graph command`

**Corrected 2026-11-13 (validation):** read at RasterFold `75be196`: the parser moved to `scripts/todo-graph.py:12879` to `:12990` (`:12687` to `:12790` were the lines at `b334933`), and it has two commands the list above leaves out, `classify` (`cmd_classify`, `:3862`, which the kit has) and the `query design` kind (`:2584`), so each gets a row too: eighteen in all. The report's own check is one `lift` or `leave` per row and a `D03 T` reference on every `lift` row, counted over the table's rows.

**Corrected 2026-11-13 (plan review):** the report's check is a test, `tests/test_adoption_report.py`, that reconciles each table with an inventory taken from RasterFold's own source and resolves every `lift` row's section through the graph, not a pair of `grep` counts.

**Test checkpoint:** `python -m unittest tests.test_adoption_report` ends `OK`, and `python scripts/todo-graph.py validate` and `python scripts/todo-graph.py plan --check` pass with the new sections in the plan; the test's own mutated copies (a lift row without its reference, a reference to nothing, a duplicated row, an inventory entry with no row) each fail it.

> **Verified:** 2026-11-13 | §6 | 6b38b20836f0240f756bd586f7cf788600d8b61f
> **Review:** `docs/reviews/d03-t01-s6.json`

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

> **Started:** 2026-11-13T05:51:21Z

`validate` stops at the first refusal, so a tree with many faults shows them one at a time. Measuring another project's tree, or repairing a large one, needs every fault at once, the way `review_pin.py --check --all` lists a pin's.

**Phase:** 3
**Needs:** none
**Surface:** no

**Build order:**

1. Give `graph` in `kits/todo/templates/scripts/lib/todo_graph.py` a mode that records each refusal and goes on. Done when: a tree with two faulty files reports both.
2. Expose it as `validate --all`. Done when: the checkpoint passes.

- [x] Add a `faults` list argument to `graph` in `todo_graph.py`, its checks made through one `check` that records a refusal when the list is given and raises it otherwise: within a file and a section every check whose inputs are usable runs (a bad Phase does not hide bad Needs), a helper's refusal (a missing field, a receipt) is recorded and only the checks that need its result are skipped. Done when: a test section with a bad Phase and bad Needs reports both, a tree with faults in two sections of one file and in another file reports every one, and `graph` without the list raises the first refusal as before (the existing tests pass unchanged).
- [x] Collect across the cross-file checks too: file dependencies, a superseded file's successor, file status, adjacency owners, XREFs, deferral owners, filed completion gaps, the index coverage and the dependency walk, which goes on past a missing target or a cycle. Done when: a fixture with an unresolved XREF, a file missing from its domain index, a dependency cycle and a section fault reports each of the four.
- [x] Record a read failure and go on: a TODO file that cannot be read or decoded, and malformed `depends_on` JSON, are recorded with the file's path and the other files are read. Done when: a test with malformed `depends_on`, a file whose read raises `OSError` and an independent fault in a third file reports all three.
- [x] Count no fault that only follows from another: every section reference and file id is gathered first, leniently, so a reference to a section or file whose own reading failed is not reported as unresolved (dependencies, XREFs, adjacency owners, deferral owners, filed gaps), no phase order or cycle is checked through it, and a file with an unread section has no status check. Done when: a test whose section 2 has a bad Phase, with section 3 depending on it, an XREF to it and an active file whose only section it is, reports the one fault, while a reference to a section that exists nowhere is still reported.
- [x] Add `validate --all` to `kits/todo/templates/scripts/todo-graph.py`: one line per fault, `<path or reference>: <message>`, in file order, then exit 2; `valid: N sections` and exit 0 when there is none. Done when: a test runs the command on a faulty tree and reads the lines and the exit code, and on the SDK's own tree reads `valid`.
- [x] Document `validate --all` in `kits/todo/templates/todo/README.md`, copy it over `todo/README.md` and run `python forge.py self-sync`. Done when: the two READMEs are identical.
- [x] Commit: `todo: validate --all reports every fault in one run`

**Corrected 2026-11-13 (plan review):** "every fault" holds within a section and across the cross-file checks, not only per section; the faults that follow from another are suppressed for every consumer of a section or file that failed, while a truly missing reference is still reported; and unreadable files and malformed `depends_on` are recorded with their path.

**Test checkpoint:** `python -m unittest discover -s tests -p test_todo_graph.py` ends `OK`; letting a section's refusal end the run (raising in place of recording) makes the three-fault test fail.

> **Verified:** 2026-11-13 | §8 | b99ddc119a6969b33f4d32900a4b95b54604e163
> **Review:** `docs/reviews/d03-t01-s8.json`

## 9. Pre-adoption stamps frozen at adoption

A project that adopts the kit arrives with sections it stamped under its own tooling: RasterFold 126, Impossible OS 915 (`docs/plans/2026-11-13-todo-graph-adoption.md`, rows R1, R6, R10 to R13, R16, R18, R21, R22, I15 and I16). The kit never rewrites a stamped section (`todo/README.md`, Brownfield code) and already freezes old receipts by digest in `legacy-receipts.json`, but nothing writes that file for a project, so every such stamp is a refusal. Adoption freezes them once, by digest, so a later edit still refuses.

**Phase:** 3
**Needs:** none
**Surface:** no

**Build order:**

1. Add `adopt_stamps` to `kits/todo/templates/scripts/lib/todo_graph.py` and `adopt-stamps` to `kits/todo/templates/scripts/todo-graph.py`. Done when: a fixture tree with foreign-format stamps validates after one run.
2. Re-run the RasterFold dry run with the stamps adopted in its snapshot. Done when: the checkpoint passes and the report's rows are updated.

- [ ] Add `adopt_stamps(root, phase_map=None)` to `todo_graph.py`: for each `[x]` row whose `Verified:` commit is an ancestor of `HEAD`, record under a new `adopted` key of `<receipts>/legacy-receipts.json` the reference, the stamp commit, the SHA-256 of the section body and of its receipt file when one exists, written atomically; refuse when `adopted` already holds entries, since adoption runs once. Done when: a test with two foreign-format stamps writes both entries, and a second run refuses and leaves the file's bytes as they were. Cheaper substitute: freezing by reference alone must fail review, because a later edit of the body would then pass.
- [ ] Skip the receipt checks and the section-format checks (fields, Build order, checklist, checkpoint) in `graph` for an adopted section whose body digest matches its entry, keeping the graph checks (dependencies, phase order, XREFs, indexes). Done when: an adopted section with no Build order and a foreign receipt validates, and the same section with one byte of its body changed reports both faults again.
- [ ] Take an adopted section's phase from `phase_map` (a JSON object of reference or TODO file path to phase number, read by `adopt-stamps --phase-map <file>`) when its body has no `**Phase:**`, record it in the entry, and refuse at adoption a stamped section with neither. Done when: a test adopts a phase-less section through a file-path entry, the generated plan lists it under that phase, and a section with no phase anywhere is refused naming its reference.
- [ ] Add the `adopt-stamps` subcommand to `kits/todo/templates/scripts/todo-graph.py`, printing one line per adopted section and the count. Done when: a CLI test reads the lines and exit 0, and exit 2 with the refusal on a second run.
- [ ] Remove a section's `adopted` entry in `unstamp`, so a reopened section is held to the kit's format when it is stamped again. Done when: a test unstamps an adopted section and finds its entry gone and its format faults reported.
- [ ] Document `adopt-stamps` in `kits/todo/templates/todo/README.md` (Brownfield code), copy it over `todo/README.md` and run `python forge.py self-sync`. Done when: the two READMEs are identical.
- [ ] Re-run `scripts/adoption-dry-run.py` on RasterFold with the stamps adopted in its snapshot, and update the report's rows. Done when: R6, R10 to R13, R16, R18, R21 and R22 are gone from the run, R1 counts only open sections, and `docs/plans/2026-11-13-todo-graph-adoption.md` says so with the run's commit.
- [ ] Commit: `todo: a project's own stamps are frozen at adoption`

**Test checkpoint:** `python -m unittest discover -s tests -p test_todo_graph.py` ends `OK`; dropping the body digest comparison makes the one-byte test fail.

## 10. Ready rows filtered by the hosts this session reaches

> **Started:** 2026-11-13T11:21:18Z

`query ready` lists a row whose Needs name a host this session cannot reach, and `process-plan` leaves the agent to notice. RasterFold's graph checks the host itself (`REQUIRES_ALLOWED`, `scripts/todo-graph.py:264`, and `detect_context`, `:296`, at `bf30b38`; report row R23). The kit gets the same check.

**Phase:** 3
**Needs:** none
**Surface:** no

**Build order:**

1. Add the session's capability set to `kits/todo/templates/scripts/lib/todo_graph.py` (built-in probes, the project's own probes from `todo/plan.json`, and Needs the session declares) and `--have` to `query ready` and `resolve`. Done when: a row needing an absent host is left out of `ready` and `resolve` names what it lacks.
2. Point every readiness consumer at it: the runner skills, the heartbeat prompt and the Stop hook. Done when: the checkpoint passes.

- [ ] Add `--have <need,...>` to `query ready` and `resolve` in `kits/todo/templates/scripts/todo-graph.py`, read through `todo_graph.py`: a row with a Need that is neither waiting nor in the set is left out of `ready` (and counted in `blocked`), and `resolve` exits 4 with the missing Needs in its JSON as `missing_needs`; `--have auto` is the session's set from `detect` below. Done when: tests show a row needing `windows-host` listed with `--have windows-host`, left out with `--have ''`, a row needing two Needs left out until both are supplied, `resolve` exiting 4 naming the absent Need and 0 once it is supplied, and, under `--have`, a row with an unmet dependency, a waiting Need or an inactive file still held and a stamped row still exiting 3; without the flag `query ready` and `resolve` behave as today. Cheaper substitute: filtering in the skill text alone must fail review, because the heartbeat prompt and the Stop hook call the graph directly.
- [ ] Add `detect` to `todo-graph.py`, printing the comma-separated Needs this session meets, the union of three sources: the kit's built-in probes (`windows-host` on Windows; `arm64-host` on an ARM64 machine; `display-session` with an interactive Windows session, or `DISPLAY` or `WAYLAND_DISPLAY` set; `libreoffice` when `soffice` is on `PATH`; `office` when Word's registry key is present through `winreg`), the project's own probes, and the Needs the session declares in `CONCLAVE_HAVE` (comma-separated, for what no program can see, such as `attended`), ported from RasterFold's `detect_context` (`scripts/todo-graph.py:296` at `bf30b38`). Done when: tests with each built-in probe mocked print its Need and print none when it fails, and a declared Need is printed only while `CONCLAVE_HAVE` names it.
- [ ] Accept a `probes` key in `todo/plan.json` in `plan_config`: an object from a Need that `needs` lists to the command that proves it, an argument list run with no shell and a 10-second timeout, the Need met when it exits 0, so a project detects its own host Needs (RasterFold's `windows-runtime`, `linux-runtime`, `linux-display`, `ffmpeg-jxl`, `gpu`). Done when: tests refuse a probe for a Need not in `needs`, a probe that is not a non-empty list of strings and a probe for a waiting Need, each naming `todo/plan.json` and `probes`; a configured probe that exits 0 makes its row ready under `--have auto`, one that exits 1 or times out keeps it held, and the probe's process tree is stopped on timeout.
- [ ] Use `--have auto` wherever a runner asks what is ready: `query ready` and `resolve` in `process-plan` and `process-phase` under `.claude/`, `.agents/` and `.codex/` in `kits/todo/templates/`, the heartbeat prompt in `process-plan`, and `ready_rows` in `kits/todo/templates/scripts/campaign_guard.py` (`:264`, the Stop hook's count), and drop the guidance that tells the agent to skip host-bound rows by hand. Done when: a guard test finds `--have auto` on every `query ready` and `resolve` command line in the six skill files and the prompt and none without it, and a Stop hook test with only a row needing an absent host open lets the turn end.
- [ ] Document `detect`, `--have`, `CONCLAVE_HAVE` and `probes` in `kits/todo/templates/todo/README.md`, copy it over `todo/README.md` and run `python forge.py self-sync`. Done when: the two READMEs are identical.
- [ ] Commit: `todo: ready rows filtered by the hosts this session reaches`

**Corrected 2026-11-13 (`§6`):** this section is where RasterFold's `requires-unknown` check lands: a host requirement is a Need from `plan.json`'s closed list, refused when unknown as `needs-unknown` already is, and `detect` checks the host. RasterFold's `requires-no-reason` (a cited reason on each mark) is left with RasterFold: a kit Need names a host, and the section's Test checkpoint is what needs it.

**Corrected 2026-11-13 (plan review):** the session's set is the kit's built-in probes, a project's own probes from `plan.json` (`probes`, so RasterFold's `windows-runtime`, `linux-runtime`, `linux-display` and its tool Needs are detected where they are met) and the Needs a session declares in `CONCLAVE_HAVE`; every readiness consumer takes it (the runner skills' `query ready` and `resolve`, the heartbeat prompt and the Stop hook); and the tests cover `resolve`, several Needs, and the states `--have` must not change.

**Test checkpoint:** `python -m unittest discover -s tests -p test_todo_graph.py` ends `OK`; ignoring `--have` in `query ready` makes the `--have ''` test fail.

## 11. Root index that lists domains

> **Started:** 2026-11-13T10:59:44Z

Both adopting projects keep `todo/TODO-00-INDEX.md` at domain altitude, as the kit's own `todo/README.md` describes it ("root index: domain order + active work"), while the validator demands every TODO file in it (report rows R20 and I33: 33 and 223 files). A project chooses which.

**Phase:** 3
**Needs:** none
**Surface:** no

**Build order:**

1. Add `layout.root_index` to `plan_config` in `kits/todo/templates/scripts/lib/todo_graph.py` and read it in `_index_coverage`. Done when: a tree whose root index lists only domains validates under `domains`.
2. Teach the reviewer kit's reader the key name. Done when: the checkpoint passes.

- [x] Accept `root_index` in `layout` in `plan_config` of `todo_graph.py`: `files` (the default, today's rule) or `domains`. Done when: tests refuse another string and a non-string, each naming `todo/plan.json` and `layout`, and a `layout` without it keeps `files`.
- [x] Under `domains`, require in `_index_coverage` each domain's index link (`NN-domain/INDEX.md`) in the root index in place of each file, the domain indexes still listing every file. Done when: a test validates a domains-only root index, refuses one missing a domain, and refuses a domain index missing a file; under `files` the existing index tests pass unchanged.
- [x] Prove the key, not its presence, picks the rule: one tree validates under an explicit `domains`, is refused under an explicit `files` until its file entries are restored to the root index, and then validates. Done when: the test runs all three states.
- [x] Make the creating and closing workflows follow the key: `create-todo/SKILL.md` (`:33`, list the new file in the root index) and `process-todo-file/SKILL.md` (`:44`, move its root entry to Completed) under `.claude/`, `.agents/` and `.codex/` in `kits/todo/templates/` say that under `layout.root_index` `domains` the root index lists the domain's `INDEX.md` once and only the domain index lists the file, then `python forge.py self-sync`. Done when: a guard test finds `layout.root_index` within 200 characters of each of the six instructions.
- [x] Accept the `root_index` member in `kits/reviewer/templates/scripts/review_layout.py`, which checks only the names it does not read. Done when: the readers' table in `tests/test_todo_graph.py` accepts it in both readers.
- [x] Document `layout.root_index` in `kits/todo/templates/todo/README.md`, copy it over `todo/README.md` and run `python forge.py self-sync`. Done when: the two READMEs are identical.
- [ ] Commit: `todo: a root index that lists domains`

**Corrected 2026-11-13 (plan review):** the creating and closing skills of all three agents follow the key, an explicit `files` is tested against an explicit `domains` on one tree, and the evidence row is I33 (223 files), not I17.

**Test checkpoint:** `python -m unittest discover -s tests -p test_todo_graph.py` ends `OK`; reading the file rule under `domains` makes the domains-only test fail.

## 12. Validation git calls cached per run

> **Started:** 2026-11-13T09:11:30Z

`python scripts/todo-graph.py validate` takes 61 seconds on the SDK's 77 sections on Windows (measured 2026-11-13 under `cProfile`): 441 git processes (`cat-file`, `merge-base`, `show`), most of them repeats, and `plan_config` read 220 times. The pre-commit hook runs it on every commit, and a project with 915 stamps pays it many times over.

**Phase:** 3
**Needs:** none
**Surface:** no

**Build order:**

1. Cache git results and the configuration for one `graph` run in `kits/todo/templates/scripts/lib/todo_graph.py`. Done when: the SDK's `validate` takes under 15 seconds.
2. Prove the results are unchanged. Done when: the checkpoint passes.

- [x] Memoise `_git`, `commit_ok`, `is_ancestor` and the `git show` reads in `todo_graph.py` for the length of one `graph` call, keyed by root and arguments and dropped when the call returns. Done when: a test counting `subprocess.run` calls during `graph` on a fixture with two stamped sections sharing a commit and a pin sees each distinct git command once, and the faults found are the same as without the cache. Cheaper substitute: a module-level cache that outlives the call must fail review, because a stamp commits between two calls and would read a stale answer.
- [x] Prove the cache ends with its `graph` call, whether it returns or raises: in one process, a test validates, commits a new `HEAD` and rewrites `todo/plan.json`, and validates again, once after a call that returned and once after a call that raised a refusal. Done when: each second call sees the new commit (a section stamped on it validates) and the new configuration (a phase the new `phase_list` adds is accepted).
- [x] Prove a cached failure reads as an uncached one: a fixture whose stamped sections repeat failing git lookups (a stamp commit that is not in the history, named by two sections) gives the same non-empty faults with the cache and with it switched off, under `validate` (the first refusal) and `validate --all` (every fault). Done when: both comparisons run in the quick suite (not skipped) and match.
- [x] Read `todo/plan.json` once per `graph` call in `todo_graph.py`, passing the configuration to `receipts_folder` and the other readers inside it. Done when: a test counts one `plan_config` read per `graph` call.
- [x] Time `python scripts/todo-graph.py validate` on the SDK's tree on Windows before and after. Done when: the commit body quotes both times, the second under 15 seconds.
- [x] Commit: `todo: validation reads each git answer once per run`

**Corrected 2026-11-13 (validation):** the git processes start in eleven places in `todo_graph.py`: `_git` (`:259`), `commit_ok` (`:207`), `_head_commits` (`:216`), `build_start` (`:413`, `:416`, `:423`) and `plan_record` (`:470`) call `subprocess.run` themselves. All of them go through one runner that the cache serves. `graph` calls no other entry point (`projection`, `stamp` and `unstamp` call `graph`, not the reverse), so each `graph` call opens its own cache and drops it when it returns or raises, and the validation `stamp` runs after its writes reads fresh.

**Corrected 2026-11-13 (plan review):** the cache's end is proven in the same process across a new commit and a new `todo/plan.json`, after a return and after a refusal, and a cached failure is compared with an uncached one on a fixture whose faults are not empty, in both validation modes.

**Test checkpoint:** `python -m unittest discover -s tests -p test_todo_graph.py` ends `OK`; clearing the cache before each lookup makes the call-count test fail.

> **Verified:** 2026-11-13 | §12 | 941e1af27881681e36ac81076d023086e8a928c1
> **Review:** `docs/reviews/d03-t01-s12.json`

## 13. Section checks run when its table row cannot be read

> **Started:** 2026-11-13T09:37:13Z

`validate --all` (`§8`) skips a section whose Implementation Order row cannot be read (`todo_graph.py:1074`), so its own faults stay hidden although its body is readable. Every Impossible OS file failed at its table, and the dry run reported no section-level class for its 2,596 sections; the report counted their fields instead (rows I12 to I16).

**Phase:** 3
**Needs:** none
**Surface:** no

**Build order:**

1. Run a section's body checks in `graph` in `kits/todo/templates/scripts/lib/todo_graph.py` when it has no readable row. Done when: a section under a malformed row reports its missing Phase.
2. Re-measure Impossible OS. Done when: the checkpoint passes and the report's counted rows are measured ones.

- [x] Run each section's own checks in `graph` (its fields, Build order, checklist, checkpoint and freeze check) for a heading with no readable row when collecting, skipping only what the row feeds (the Deliverable length, the done status and the stamp). Done when: a test with a malformed row and a section body with no Phase reports both faults, and `graph` without `faults` raises the row fault first as before.
- [x] Keep such a section out of the graph: it is never ready, and a reference to it is not reported as unresolved. Done when: a test with a dependency and an XREF to it reports neither.
- [x] Pair the stamp with its receipt in `graph` for a section with no readable row, as the box pairs them for a section with one: a `Verified:` line with no `Review:` line, or the reverse, is a fault, and the receipt a valid stamp names is checked. Done when: a test with a malformed row and a valid stamp reports the missing receipt when there is no `Review:` line, and the receipt fault when the receipt is missing, unreadable or invalid.
- [x] Prove the section stays out of the graph on its own: a malformed row over a section whose body is otherwise valid. Done when: a test finds the section's reference absent from what `graph` returns, while a sibling section with a good row is present.
- [x] Re-run `scripts/adoption-dry-run.py` on Impossible OS and replace rows I12 to I16 of `docs/plans/2026-11-13-todo-graph-adoption.md` with the measured classes and their decisions. Done when: every class of the new run has a row, with the run's commit.
- [x] Commit: `todo: section checks run when its table row cannot be read`

**Corrected 2026-11-13 (`§5` completion review):** `§5`'s completion review held its measurement incomplete without this fix, so the first two items shipped in `§5`'s candidate, `7fe94dd` and `bc99c1d` (`graph` in `todo_graph.py`, the `row is None`, `has_table` and `front_ok` paths, so a file whose table heading or frontmatter cannot be read has its sections checked too; tests `test_a_section_under_an_unreadable_row_still_has_its_body_checked` and `..._has_its_own_stamp_checked`), and a section under an unreadable row also has its own stamp and receipt checked, since its body says whether it claims a stamp. The re-run is `§5`'s too. This section is left to verify them, review and stamp.

**Corrected 2026-11-13 (plan review):** a rowless section's stamp is paired with its receipt and its receipt checked, tested with a missing, an unreadable and an invalid receipt, and its absence from the graph is proven on a body that is otherwise valid.

**Test checkpoint:** `python -m unittest discover -s tests -p test_todo_graph.py` ends `OK`; restoring the skip at `:1074` makes the malformed-row test fail.

> **Verified:** 2026-11-13 | §13 | 904fe0bc25beb69d7611f037c39d5352985acab5
> **Review:** `docs/reviews/d03-t01-s13.json`

## 14. Frozen files listed by `query frozen`

> **Started:** 2026-11-13T10:14:33Z

RasterFold's `query frozen` (`scripts/todo-graph.py:2576` at `75be196`, eight lines) lists the frozen TODO files and how many of their sections carry a Freeze check. It reads only the tree, and a project with frozen files needs the list before it touches one (`docs/plans/2026-11-13-todo-graph-adoption.md`, RasterFold graph commands).

**Phase:** 3
**Needs:** none
**Surface:** no

**Build order:**

1. Add the `frozen` kind to `query` in `kits/todo/templates/scripts/todo-graph.py`. Done when: it lists a fixture's frozen file.
2. Document it. Done when: the checkpoint passes.

- [x] Add `frozen_files(root)` to `kits/todo/templates/scripts/lib/todo_graph.py`, reading the tree alone (no receipt, no git, and no validation that could refuse first, since a valid tree always has full coverage and the query is for one that may not): for each TODO file whose frontmatter says `frozen: true`, its path, its section count, how many sections carry a `**Freeze check:**` and the references of those that do not, in path order; a file whose frontmatter cannot be read is listed under `unreadable`, and a missing or empty `todo/` refuses as `graph` does. Ported from RasterFold's `query frozen`. Done when: a test on a tree with two frozen files of three and two sections (one missing its Freeze check), an unfrozen file and a file with broken frontmatter prints exactly `{"files": [...], "unreadable": [...]}` in path order with the counts 3 and 3, and 2 and 1 with the missing reference, and the same output when a stamped section's receipt is missing.
- [x] Add `frozen` to the `query` choices in `kits/todo/templates/scripts/todo-graph.py`, answered by `frozen_files` before the graph is validated. Done when: a CLI test reads the JSON on a tree whose validation refuses.
- [x] Document `query frozen` in `kits/todo/templates/todo/README.md` (Commands), copy it over `todo/README.md` and run `python forge.py self-sync`. Done when: the two READMEs are identical.
- [x] Commit: `todo: query frozen lists the frozen files`

**Corrected 2026-11-13 (plan review):** the query reads the tree alone, before and without validation, so it reports coverage on a tree with faults (a valid tree always has full coverage), and its tests use two frozen files of different sizes with unequal counts and an exact, ordered output.

**Test checkpoint:** `python -m unittest discover -s tests -p test_todo_graph.py` ends `OK`; listing every file in place of the frozen ones, or reporting the section count as the Freeze-check count, makes the test fail.

> **Verified:** 2026-11-13 | §14 | 0f38d9523d7d8bf2f4d5fcb5d2048960aae2127b
> **Review:** `docs/reviews/d03-t01-s14.json`

## 15. Longest chain and filing couplings from `query sequence`

> **Started:** 2026-11-13T10:41:30Z

RasterFold's `query sequence` (`scripts/todo-graph.py:2124` at `75be196`, with `_longest_chain`, `_section_edges` and `_filing_couplings` at `:4387`) prints the longest dependency chain and the sections a review filed work into. The chain is the tree's own; the couplings come from RasterFold's findings headings, which the kit does not write, but every kit receipt records the sections its completion review filed (`completion.filed`), so the kit reads them from there.

**Phase:** 3
**Needs:** none
**Surface:** no

**Build order:**

1. Add the `sequence` kind to `query` in `kits/todo/templates/scripts/todo-graph.py` and its computation to `kits/todo/templates/scripts/lib/todo_graph.py`. Done when: a fixture's longest chain prints.
2. Read the couplings from the receipts. Done when: the checkpoint passes.

- [x] Add `longest_chain(rows)` to `todo_graph.py`: the longest path through the open sections' dependencies, listed from the first prerequisite to the last consumer, ties broken by plan order (`ordered`), ported from RasterFold's `_longest_chain`. Done when: a test with chains of three and two open sections returns the three in that order, a stamped section on a path ends it, two equal chains whose file order differs from their plan order return the one plan order puts first, and a tree with every section stamped returns an empty chain.
- [x] Add `filing_couplings(root, rows)` to `todo_graph.py`: for each stamped section, read the receipt its own `Review:` line names (so a project's `layout.receipts` holds), and give one pair per section it lists under `completion.filed`: the filer, the filed section and the filed section's state as `query plan` reports it (`plan_status`, moved from the CLI into `todo_graph.py` so both read one definition: `verified`, `deferred`, `ready` or `blocked`), read afresh on each call. Done when: a test with receipts under a non-default folder, one filing two sections, one filing none and one with no `completion` (older receipts) returns the two pairs with their states, and the same pairs with a new state after the filed section is stamped.
- [x] Prove a malformed or missing receipt refuses `query sequence` as it refuses every query (the graph is validated first), never an empty list of couplings. Done when: a CLI test with a stamped section's receipt removed exits 2 with the graph's refusal.
- [x] Add `sequence` to the `query` choices in `kits/todo/templates/scripts/todo-graph.py`, printing JSON with `chain` and `couplings`. Done when: a CLI test on a valid tree with a stamped section that filed another reads the exact chain and the exact coupling with its state, both non-empty.
- [x] Document `query sequence` in `kits/todo/templates/todo/README.md` (Commands), copy it over `todo/README.md` and run `python forge.py self-sync`. Done when: the two READMEs are identical.
- [ ] Commit: `todo: query sequence prints the longest chain and the filing couplings`

**Corrected 2026-11-13 (plan review):** the chain's direction and tie break are stated and tested with an empty case; the couplings read each stamped row's own receipt path, carry `query plan`'s states from one shared `plan_status`, and are tested under a non-default receipts folder and after a state change; a bad receipt refuses; and the CLI test checks exact, non-empty values. The tests that need a valid stamp run in the full suite (`CONCLAVE_FULL_TESTS=1`) with the other stamp tests.

**Test checkpoint:** `CONCLAVE_FULL_TESTS=1 python -m unittest discover -s tests -p test_todo_graph.py` ends `OK`; counting stamped sections into the chain, or reading couplings from the default folder only, makes a test fail.

## Verification

- A scratch project whose `todo/plan.json` sets `phase_list`, `needs`, `waiting`, `caps` and `layout` validates a tree written to those values, stamps a section and regenerates its plan.
- The SDK's own tree, with none of those keys, validates and stamps exactly as before: `CONCLAVE_FULL_TESTS=1 python -m unittest discover -s tests` passes.
- The adoption report exists and every kit-change and `lift` row names a section.
- `python scripts/todo-graph.py validate` and `python scripts/todo-graph.py plan --check` pass.
