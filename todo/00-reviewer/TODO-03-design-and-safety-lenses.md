---
schema_version: 1
id: design-and-safety-lenses
domain: 00-reviewer
status: active
title: "TODO-03 -- Design and safety lenses, held by path in every project"
---

# TODO-03 -- Design and safety lenses, held by path in every project

> **Goal:** A change to a user interface file, or to C++ source, is reviewed through the lens that fits it because of the path it touched, never because a section's own fields said so: the reviewer kit gives `design` by path beside `--surface`, carries a `thread-safety` and a `memory-safety` lens, names the design source on every prompt, and every project built on the kits has those rules installed, a design contract rule its agents always read, and a pin that names its own paths.

> **Current state:** Measured 2026-11-17. The kit change for the design half is built and not yet reviewed: commit `a kit change of 2026-11-17` (see §1) lets a three-pass pin keep `design` in the round and also name it in a `[[schedule.conditional]]` entry, adds the built-in `design-plan` lens, takes `design/SPEC.md` out of the `design` and `source-defect` questions, gives the reconciliation prompt a Fidelity line, makes `scripts/review-prompt.py` read a section's Fidelity from `--ref`, and adds `--no-surface` to `scripts/review_pin.py --lenses`. Its tests passed locally (the reviewer kit's suite, the installed copy's suite and the gated stamp test); the SDK's full suite was stopped after 20 minutes without a result, so CI is its first full run. No project has the change yet. A read-only survey of 21 projects the same day found: no project has a design contract rule under `.agents/rules/`; no pin has a `[[schedule.conditional]]` entry; 18 of 20 Windows projects have `scripts/design-lint.py` wired into their pre-commit hook and two (Bosun, Recto) and the WSL project (RasterFold) have none; three projects (Gemail, Office, Recto) point Antigravity at `.claude/skills` through `.agents/skills.json` and have no `.agents/skills/`; Recto has no `GEMINI.md`; Resolute has no `.agents/hooks.json`; Resolute and Bosun are on rotation pins with a dispatcher that knows neither three-pass nor conditional entries; RasterFold's reviewer scripts have no `review_pin.py`; the custom `scripts/todo-graph.py` of Resolute, ScratchPad and Gemail has no `stamp` command and no Surface validation; about 570 open `Surface: yes` sections name neither a lint nor a rendered check in their Test checkpoint, and no project but ScratchPad and Bosun has a command that renders its built app. C++ of a project's own is held by Resolute-SDK (`shared/resolute-ui/`, `shared/lucide/`), Resolute (`src/`, `tests/`) and one of the 78 tool repositories (RegStudio, `src/`); the other tool repositories and the hardware information project hold none yet. The survey's per-project notes are a head start, not a source: `build/fleet-design-facts.md` on the machine that ran it (ignored by git, so it may be gone), and every fact is reread in the project before it is written down.

## Inputs

- `kits/reviewer/templates/scripts/review_pin.py`, `kits/reviewer/templates/scripts/review-prompt.py`, `kits/reviewer/templates/.conclave/reviewers.toml` and `kits/reviewer/README.md`, with their tests in `kits/reviewer/templates/scripts/tests/`.
- `kits/todo/templates/scripts/lib/todo_graph.py` (`schedule_ok`, which replays conditional lenses from the files a candidate changed) and `tests/test_todo_graph.py`.
- `kits/todo/templates/.claude/skills/process-todo-section/SKILL.md` and `kits/todo/templates/.claude/skills/review-todo-section/SKILL.md`, the source of the other agents' copies.
- `.conclave/local.toml` `[[projects]]`: the projects on this machine (one entry on 2026-11-17, so §3 completes the list first). No project's folder is written into a tracked file.
- The owner's decisions of 2026-11-17, binding on every section here: the lens wording in §2 is used word for word; the two C++ lenses join `round` and `reconciliation` only, by path, and add no pass; findings follow `blocking = ["P1", "P2"]` with no handling per lens; Resolute moves to three-pass and Bosun stays on rotation and gets no lens; a section whose plan review already ran finishes under the pin it began on; existing C++ gets mechanical checks, review as touched and one bounded audit, never a sweep; the 570 checkpoints are not edited (the skill holds every surface section to both checks); the custom graphs get validation first and their stamp gate as its own section; only this repository is pushed without asking, and a project's commits stay local unless its own rules say to push (the tool repositories do).
- The owner's rule that a project's own `AGENTS.md` wins over this file where it is more specific: read it before the first write in that project, and skip a project whose tree another run or person holds, reporting it.

## Outcome

- `python scripts/review_pin.py --lenses round --no-surface --paths <a UI file>` prints `design` in every project with a user interface, and prints `thread-safety` and `memory-safety` for a C++ file in every C++ project on three-pass, and neither for a file outside those paths.
- A section that changed a file under a project's design paths cannot be stamped without `LENS design:` on its round and its reconciliations, whatever its Surface field says, in every project whose graph has a stamp.
- Every project has `.agents/rules/design-contract.md` naming its real contract, token source, forbidden patterns and commands, and every path that rule cites exists.
- One read-only script reports each of these per project, and what remains open is filed in the project that owns it.

**Adjacency:** all=not-applicable (developer tooling: reviewer pin rules, prompts, agent rules and checks, with no records a user lists, exports, is notified of or reverses)

**Adjacency rationale:** The settings this work adds are pin keys (`[schedule.lenses]`, `[[schedule.conditional]]`), each consumed by the pin loader and the stamp, and proven by the pin tests and by `--lenses` in each project.

## Implementation Order

| Order | Section | Deliverable | Depends On | Status |
| ----- | ------- | ----------- | ---------- | ------ |
| 1 | §1 | Design lens by path and Fidelity on every prompt | -- | [x] |
| 2 | §2 | Thread-safety and memory-safety lenses in the template pin | §1 | [x] |
| 3 | §3 | Kit refresh in every listed project | §2 | [x] |
| 4 | §4 | Agent entrypoints, hooks and native skill folders | §3 | [x] |
| 5 | §5 | Design contract rule in every project | §3 | [ ] |
| 6 | §6 | Design paths in every three-pass pin | §5 | [ ] |
| 7 | §7 | Design lint where a project has none | §3 | [ ] |
| 8 | §8 | Resolute on three-pass | §3 | [ ] |
| 9 | §9 | C++ lens entries in the C++ projects | §8 | [ ] |
| 10 | §10 | Reviewer scripts current in the WSL project | §3 | [ ] |
| 11 | §11 | Surface validation in the custom graphs | §3 | [ ] |
| 12 | §12 | Stamp gate planned in each custom graph's project | §11 | [ ] |
| 13 | §13 | Concurrency and lifetime checks in the clang-tidy ratchet | §9 | [ ] |
| 14 | §14 | Sanitizer test configuration | §13 | [ ] |
| 15 | §15 | Bounded C++ hot-spot audit | §9 | [ ] |
| 16 | §16 | Read-only verification across the projects | §6, §7, §9, §10, §11, §18 | [ ] |
| 17 | §17 | One Opus design check before a surface section's review | -- | [x] |
| 18 | §18 | Retry held projects for §3 and §5 (`Updates`, `RasterFold`) | §5 | [ ] |

## 1. Design Lens by Path and Fidelity on Every Prompt

> **Started:** 2026-11-22T21:29Z

The kit change is already in the tree (the commit `reviewer: design by path, design-plan, and Fidelity on every prompt` of 2026-11-17, written outside a section), so this section verifies each item against the code, fixes any gap found in plan review, runs the checkpoint, and takes the change through the three passes it has not had. It must not change what an existing pin schedules: `lenses_for` gives the same list as before for every pin without a conditional `design` entry, with the one exception that `design-plan` is now a reserved built-in lens name (an upgrading project that declared `design-plan` under `[schedule.lenses]` renames or removes that declaration and updates its conditional references, documented in `kits/reviewer/README.md`). **Corrected 2026-11-22:** the 2026-11-17 commit is `30bbef0b521a8e4d5c23a0e4cd7fcad888e30860` (parent `30bbef0b~1`). **Planned 2026-11-22 (plan review, P1/P2/P3):** (1) refuse blank `--fidelity`, missing `body`, or missing/ambiguous `Surface` in `resolve_fidelity()` of `review-prompt.py` rather than defaulting to `none (Surface: no)` while keeping the `Surface: no` positive case; (2) make `resolve_fidelity()` read the section from the `--candidate` commit via `git show <candidate>:<path>` when `<candidate>` is a commit in the repo, tested with differing candidate vs working-tree Fidelity; (3) document `design-plan` built-in migration in `kits/reviewer/README.md` and test both built-in refusal and migrated custom-lens scheduling; (4) scope the retrospective review to `30bbef0b^..30bbef0b` plus `30bd2f45..<candidate>` rather than the 598 intervening commits; (5) assert canonical design-contract rule lookup, path trigger, static lint, and rendered check wording directly in `tests/test_skill_copies.py`; (6) assert exit 0 and exact base lens lists for nonmatching `--no-surface` CLI calls in `test_review_pin.py`; (7) assert no hardcoded project path token in `LENSES["design"]`, `LENSES["source-defect"]`, and `LENSES["design-plan"]`; (8) run the `SURFACE_GATED` mutation once against the focused pin test, then run the required suites unmodified.

**Phase:** 9
**Needs:** none
**Surface:** no

**Build order:**

1. Verify and harden `kits/reviewer/templates/scripts/review_pin.py` (`SURFACE_GATED`, `check_conditional_overlap`, `lenses_for`) and its tests in `kits/reviewer/templates/scripts/tests/test_review_pin.py` plus `design-plan` migration notes in `kits/reviewer/README.md`. Done when: each pin item below passes with exact exit-0 base lists, built-in refusal + migrated lens scheduling, and path-free question checks.
2. Harden `kits/reviewer/templates/scripts/review-prompt.py` (`resolve_fidelity` candidate-commit lookup plus blank `--fidelity` / missing-body / missing-Surface refusals), add canonical design-contract wording assertions in `tests/test_skill_copies.py`, and run `python forge.py self-sync`. Done when: the checkpoint passes.

- [x] Confirm `check_conditional_overlap` in `kits/reviewer/templates/scripts/review_pin.py` lets a conditional entry repeat only the round's `design`. Done when: `test_a_conditional_entry_gives_the_round_its_surface_gated_design_by_path` in `kits/reviewer/templates/scripts/tests/test_review_pin.py` passes, and fails when `SURFACE_GATED` is emptied. Cheaper substitute: dropping the repeat check, which lets a pin list any lens twice.
- [x] Confirm `lenses_for` lists `design` once for a section with a surface and a matching path, and at all for one without a surface only on a matching path. Done when: the four `lenses(schedule, "round", ...)` assertions of that test pass.
- [x] Confirm the built-in `design-plan` lens in `LENSES` joins a plan review by path, that a pin declaring `design-plan` under `[schedule.lenses]` is refused as a built-in, and that migrating a custom `design-plan` declaration (documented in `kits/reviewer/README.md`) loads and schedules its intended question. Done when: `test_review_pin.py` asserts all three and `kits/reviewer/README.md` documents the migration.
- [x] Confirm the `design`, `source-defect`, and `design-plan` questions in `LENSES` name no project path. Done when: `test_review_pin.py` asserts no slash-delimited project path token appears in any of the three questions (so substituting another project path fails) alongside `Fidelity`.
- [x] Confirm `--no-surface` on `scripts/review_pin.py --lenses`. Done when: `test_no_surface_lists_design_only_for_a_file_under_a_conditional_path` asserts exit 0 and the complete expected base lens list on nonmatching calls, `design` on matching calls, and exit 2 for `--check --no-surface`.
- [x] Confirm the Fidelity line of `kits/reviewer/templates/docs/reconciliation-review-prompt.md` and that all four kinds take `--fidelity`. Done when: `test_every_kind_takes_fidelity_and_names_it_on_its_candidate` in `test_review_prompt.py` passes.
- [x] Harden `resolve_fidelity` and `--fidelity` validation in `kits/reviewer/templates/scripts/review-prompt.py`: read the section from the `--candidate` commit via `git show <candidate>:<path>` when `<candidate>` is a commit in the repo; refuse blank `--fidelity`, a graph that prints no `body`, a missing/ambiguous `Surface` field, a `Surface: yes` section with no `Fidelity`, or an unresolvable section; keep `none (Surface: no)` only for an actual `Surface: no` section (or when no `todo-graph.py` is installed). Done when: `FidelityLookup` tests in `test_review_prompt.py` prove all refusals, candidate-vs-checkout Fidelity isolation, and the `Surface: no` positive case. Cheaper substitute: defaulting to `none (Surface: no)` on a blank override, missing body, or working-tree drift.
- [x] Confirm the stamp refuses a `Surface: no` section that changed a file under a conditional `design` path when its round or reconciliation lacks the lens. Done when: `test_a_surface_no_section_that_changed_a_design_path_needs_the_design_lens_to_stamp` in `tests/test_todo_graph.py` passes under `CONCLAVE_FULL_TESTS=1`.
- [x] Confirm the skills and `kits/base/templates/GEMINI.md` name the design contract rule, path trigger, static lint, and rendered check, and that the generated copies and SDK installed copies match (`python forge.py self-sync`). Done when: `tests/test_skill_copies.py` asserts the canonical clauses in `process-todo-section/SKILL.md`, `review-todo-section/SKILL.md`, and `kits/base/templates/GEMINI.md`, `python forge.py skill-copies --check` exits 0, and `python -m unittest tests.test_skill_copies tests.test_forge -k test_the_sdk_uses_the_agent_setup_its_kits_ship` passes.
- [x] Commit: `reviewer: design by path, reviewed (D00 T03 §1)`

**Test checkpoint:** Run the `SURFACE_GATED` mutation once against `test_review_pin.py` (`test_a_conditional_entry_gives_the_round_its_surface_gated_design_by_path` fails), then on the unmodified candidate pass `python forge.py check-all --only kit-reviewer --only sdk-scripts`, `python -m unittest tests.test_skill_copies`, and `CONCLAVE_FULL_TESTS=1 python -m unittest tests.test_todo_graph -k design_path`.

> **Verified:** 2026-11-23 | §1 | 82684cdaafa6d7da4574726fc06e0228f7034f45
> **Review:** `docs/reviews/d00-t03-s1.json`

## 2. Thread-Safety and Memory-Safety Lenses in the Template Pin

> **Started:** 2026-11-23T00:53Z

A C++ project needs two questions the built-in lenses only touch: `adversarial` mentions bounds and races and `integration` asks about threads and ownership, and both stay as they are. The loader accepts a lens declared under `[schedule.lenses]` that no step names (it checks the name and the question only; verified by reading `check_three_pass` on 2026-11-17), so the template can declare both lenses active and carry the conditional entry as a commented example a C++ project fills with its own paths. **Verified 2026-11-23:** searched `forge.py` and `tests/`: no test or doctor row requires the SDK's own `.conclave/reviewers.toml` to equal the template (`forge.py` / `tests/test_forge.py:463` / `tests/test_kit_install.py:56` preserve a project's own pin and `doctor` only runs `load_pin()`; `tests/test_template_pin.py` tests the kit template, `tests/test_check_pin_contract.py` tests fixture pins and the template pin contract, and `tests/test_three_pass_install.py` tests a fresh install). Therefore the SDK's own `.conclave/reviewers.toml` stays unchanged. **Planned 2026-11-23 (plan review, P2/P3):** (1) reuse one active `[schedule.lenses]` header in the template with the commented `# concurrency = ...` key inside it before any conditional tables and test enabling it; (2) test all four pass kinds (`plan`, `round`, `completion`, `reconciliation`) before and after uncommenting the C++ conditional example on matching and non-matching paths; (3) document the opt-in C++ lenses beside "Lenses of your own" in `kits/reviewer/README.md` with placeholder prefixes to replace and verify in `tests/test_template_pin.py` that the documented snippet produces the exact schedule; (4) scope stripping `GIT_CONFIG`, `GIT_CONFIG_PARAMETERS`, and `GIT_CONFIG_COUNT` to the `_git_across_fs()` subprocess only and test all three env vars independently against the mount-boundary fixture; (5) correct the `test_check_pin_contract.py` citation above.

**Phase:** 9
**Needs:** none
**Surface:** no

**Build order:**

1. Declare both lenses under one active `[schedule.lenses]` table (keeping `# concurrency = ...` commented inside it, before conditional examples) plus the commented C++ `[[schedule.conditional]]` example in `kits/reviewer/templates/.conclave/reviewers.toml`, and test exact wording, uncommented `concurrency`, and all four pass kinds (commented vs uncommented, matching vs non-matching paths) in `tests/test_template_pin.py`. Done when: `python -m unittest tests.test_template_pin` passes and `review_pin.py --check` prints `ok` with all four default pass lists unchanged.
2. Document both opt-in lenses, the conditional example (naming placeholder prefixes to replace), and the "C++ projects" note beside "Lenses of your own" in `kits/reviewer/README.md`, and test the README wording and snippet in `tests/test_template_pin.py`. Done when: `tests.test_template_pin` and `tests.test_forge -k markdown_table` pass.
3. Strip `GIT_CONFIG`, `GIT_CONFIG_PARAMETERS`, and `GIT_CONFIG_COUNT` only in `_git_across_fs()`'s subprocess env in `kits/reviewer/templates/scripts/review-prompt.py`, test all three env vars independently plus mount-boundary refusal in `kits/reviewer/templates/scripts/tests/test_review_prompt.py`, and run `python forge.py self-sync`. Done when: the checkpoint passes.

- [x] Search `tests/` and `forge.py` for a check that an installed pin equals the template (`tests/test_template_pin.py`, `tests/test_three_pass_install.py`, the doctor's reviewer rows). Done when: the section body records, dated, what each requires.
- [x] Add `[schedule.lenses]` to `kits/reviewer/templates/.conclave/reviewers.toml` with `thread-safety = "Which state is reached from two threads (UI, worker, callback, timer) without one lock or atomic owning it, and which lock order, wait, cancellation or teardown can deadlock or run after its owner is gone?"` and `memory-safety = "Which pointer, reference, view, handle or iterator can outlive what it refers to, and which size, index or cast is trusted unchecked?"`, each on one line, word for word. Done when: the template loads and a test compares both questions with these strings. Cheaper substitute: adding them to the built-in `LENSES`, which the owner ruled out.
- [x] Add a commented `[[schedule.conditional]]` example beside it with `lenses = ["thread-safety", "memory-safety"]`, `passes = ["round", "reconciliation"]` and placeholder C++ paths. Done when: a test uncomments the example in a copy of the template and loads it, and `lenses_for` gives both lenses for a path under it and neither outside.
- [x] Refresh the SDK's own `.conclave/reviewers.toml` where the first item found the tests expect template and install to agree. Done when: `python -m unittest tests.test_template_pin` passes.
- [x] Add the two lenses to the lens table of `kits/reviewer/README.md`, the conditional example, and a "C++ projects" note saying they join the round and reconciliations by path and add no pass. Done when: the Markdown table check passes (`python -m unittest tests.test_forge -k markdown_table`).
- [x] Strip `GIT_CONFIG`, `GIT_CONFIG_PARAMETERS`, and `GIT_CONFIG_COUNT` in `_git_across_fs()` of `kits/reviewer/templates/scripts/review-prompt.py` (filed non-blocking P3 from `D00 T03 §1` Reconciliation 8) so an inherited `GIT_CONFIG` cannot disable Git's `--type=bool` parse of `GIT_DISCOVERY_ACROSS_FILESYSTEM`, then run `python forge.py self-sync`. Done when: a test in `kits/reviewer/templates/scripts/tests/test_review_prompt.py` sets `GIT_CONFIG=os.devnull` with `GIT_DISCOVERY_ACROSS_FILESYSTEM=1` and asserts `_git_across_fs()` returns `True` (and `_section_body_at_commit` refuses across a mount boundary).
- [x] Commit: `reviewer: thread-safety and memory-safety lenses in the template pin (D00 T03 §2)`

**Test checkpoint:** `python forge.py check-all --only kit-reviewer --only sdk-scripts` and `python -m unittest tests.test_template_pin` pass, and the wording test fails when one word of either question is changed.

> **Verified:** 2026-11-23 | §2 | b337c13bd64454bf9c141eada6f46ce4a95491fd
> **Review:** `docs/reviews/d00-t03-s2.json`

## 3. Kit Refresh in Every Listed Project

> **Started:** 2026-11-23T03:06Z

**Corrected 2026-11-23:** re-planned with `todo-graph.py replan`; the build first began at 2026-11-23T01:55Z; its review chain is kept as `docs/reviews/00-reviewer/D00-T03-s3-chain1.md`.

Sections 4 to 16 need the kit files of §1 and §2 in each project. `forge.py update` writes only files a project lacks or never changed and lists the rest, so a project's own edits are kept. Historically `.conclave/local.toml` held 1 entry on 2026-11-17 and 3 entries before §3 (`RasterFold` plus two existing WSL site entries kept as neutral aliases `wsl-site-1` and `wsl-site-2` in tracked docs per `AGENTS.md`); after §3 it holds all 24 entries. **Verified 2026-11-23:** Free/held survey of all 21 surveyed projects (plus `Updates`, `wsl-site-1`, `wsl-site-2`): **free (22):** `Berth`, `Busview`, `CarbonCD`, `DoubleTake`, `Gemail` (has `kits.json` for `base` only; uses panel slots and §12 owns its pin decision, so do not create a pin here), `GluonStack`, `Isotone`, `Kami`, `KitsuneBrowser`, `Merchant`, `Office` (no `kits.json`), `RasterFold` (WSL, no `kits.json`; reviewer script migration deferred to §10), `Recto` (no `kits.json`), `Resolute` (no `kits.json`, `.git/run-guard/state.json` `active: false` `ended`; three-pass script/pin migration deferred to §8), `Resolute-SDK`, `ScratchPad` (hand-port `base` and `reviewer` only per its `AGENTS.md`, preserving `campaign_review_marker`, `effort: high`, `git-runner` read-only line, and `layout.receipts`), `Steward` (`.git/run-guard/state.json` `active: false` `drained`), `Strata`, `Voxel`, `Wobble`, `wsl-site-1`, `wsl-site-2`; **held/dirty, skipped (2):** `Bosun` (live `.git/run-guard/state.json` `active: true`, 4 dirty files; stays on rotation; write-capable retry owner §5), `Updates` (2 dirty files including `docs/phase-runs/2026-11-23-phase-4.md`; write-capable retry owner §5). **Planned 2026-11-23 (plan review, P1/P2):** (1) scope every `forge.py update` call with positional kit name (`reviewer`, and `base`/`todo` only where SDK-owned, plus `--only <path>` for selective file updates, never touching `launchers`/`unattended` or project-owned forks) and route hand-port projects (`ScratchPad`, `Gemail`, `Isotone` if forked) separately; (2) enumerate and verify every §1/§2 target file (`scripts/review_pin.py`, `scripts/review-prompt.py`, `docs/plan-review-prompt.md`, `docs/review-round-prompt.md`, `docs/completion-review-prompt.md`, `docs/reconciliation-review-prompt.md`, applicable skill copies) at the target commit by byte equality, behavior-tested local port, or explicit deferral (`§8` Resolute, `§10` RasterFold, `§12` Gemail); (3) never write client-site identifiers or machine paths into tracked files; (4) verify all four `ScratchPad` invariants at its committed HEAD (`campaign_review_marker`, `effort: high`, `git-runner` via `agent_routing.py check`, and `layout.receipts` resolution); (5) give `Gemail`, `Resolute`, and `RasterFold` explicit §3 deferrals without conflicting universal pin checks; (6) preserve all 3 existing `.conclave/local.toml` entries, verify each repo's Git root on its owning host, and use kit-scoped `forge.py diff <target> reviewer`; (7) prove installed runtime capability in every applicable refreshed project by rendering all four prompt kinds (`plan`, `round`, `completion`, `reconciliation`) with `--fidelity` and asserting their exact `Fidelity:` line, plus running `scripts/review_pin.py --lenses round --no-surface --paths ...` against a temporary conditional pin on matching and nonmatching paths; (8) record each project in `docs/phase-runs/2026-11-22-phase-9.md` as `refreshed at <new SHA>`, `already verified at <SHA>`, or `deferred to <section>` (with write-capable §5 retry for held trees and §16 as the read-only independent check) and inspect post-commit `git status --short` on every changed project.

**Phase:** 9
**Needs:** windows-host
**Surface:** no

**Build order:**

1. Complete `[[projects]]` in `.conclave/local.toml` (preserving the 3 existing entries), verify each registered checkout's Git root on its owning host, and inspect kit-scoped `python forge.py diff <target> reviewer` (plus `base`/`todo` where installed). Done when: every surveyed project has a verified host root and its route (kit-scoped update, hand-port, or §8/§10/§12/§5 deferral) is recorded.
2. Refresh each free applicable project via its scoped route (`forge.py update <target> <kit> [--only <path>]` or hand-port), verify all §1/§2 files and project invariants (`ScratchPad` 4 invariants), run each project's quick checks plus the runtime 4-kind Fidelity and temporary conditional-pin `--no-surface` proofs, commit locally, and record every project's outcome (`refreshed at <new SHA>`, `already verified at <SHA>`, or `deferred to <section>`) in `docs/phase-runs/2026-11-22-phase-9.md` using neutral aliases for client sites. Done when: every refreshed project's post-commit `git status --short` is clean and the runtime checkpoint passes across all applicable projects.

- [x] Add each surveyed project to `[[projects]]` in `.conclave/local.toml` (preserving the 3 existing entries, Windows and WSL paths as existing entries show) and verify each checkout's Git root on its owning host. Done when: `python forge.py drift` prints a row per project, every host root resolves to the expected repository, and `git status --short` shows no tracked change.
- [x] For each project, read its `AGENTS.md`, `git status --short` and its run state under `build/` and `.git/run-guard/`. Done when: the section body lists, dated and without client names or machine paths, each project as free or held, and a held or dirty one is skipped with its write-capable retry owner (§5) named.
- [x] Run kit-scoped `python forge.py diff <target> reviewer` (and `base`/`todo` only where SDK-owned, never touching `launchers`/`unattended` or project-owned forks) then `python forge.py update <target> <kit> [--only <path>]` for each free project with `.conclave/kits.json` on the update route, resolving `both-changed` files via `--kit-new` and `python forge.py record <target> <kit> --merged <path>`, and verify per-file acceptance at committed HEAD across every refreshed project (`scripts/review_pin.py`, `scripts/review-prompt.py`, all four `docs/*-prompt.md` templates, `scripts/lib/todo_graph.py` `schedule_ok`+`changed_paths` replay on every stamp-capable repo, `GEMINI.md`, and `process-todo-section`/`review-todo-section` skills, with each item byte-equal, a verified local equivalent, or explicitly deferred to a named section). Done when: the per-file audit passes across all 19 refreshed projects. Cheaper substitute: running unscoped `forge.py update`, which overwrites unrelated kits or project-owned forks.
- [x] In `ScratchPad` (whose `AGENTS.md` forbids the todo/unattended kits and `forge.py update`), hand-port only the changed `reviewer` and `base` files, preserving and verifying all four invariants at the committed HEAD: `campaign_review_marker` exercised in `scripts/review-dispatch.py`, `effort: high` in `.claude/agents/`, `git-runner` read-only via `python scripts/agent_routing.py check`, and receipt resolution through `layout.receipts` (`docs/cross-model-reviews/`). Done when: all four invariants pass on the committed HEAD.
- [x] For free projects without `.conclave/kits.json` (`Office`, `Recto`), hand-copy the §1/§2 reviewer files (`scripts/review_pin.py`, `scripts/review-prompt.py`, all four `docs/*-prompt.md` templates, and applicable skills/`GEMINI.md` clauses) as their `AGENTS.md` allow; defer `Resolute` to §8, `RasterFold` (scripts and 4 prompt templates) to §10, `Gemail` pin decision to §12, and `Gemail` skills/`GEMINI.md` plus `Recto` `GEMINI.md` to §4. Done when: `Office` and `Recto` match the kit's §1/§2 files (or have a behavior-tested local port) and all deferrals are recorded.
- [x] Run each applicable refreshed project's own quick check (`python scripts/todo-graph.py validate` where a canonical TODO tree is populated, `python scripts/review_pin.py --check --all`, its pre-commit hook on the commit) plus the runtime proofs (byte-equal `review-prompt.py` across all 19, all four prompt kinds rendering their exact `Fidelity:` line, `scripts/review_pin.py --lenses round --no-surface --paths ...` with a temporary conditional pin on matching and nonmatching paths, and `schedule_ok`+`changed_paths` stamp enforcement verified on all 18 stamp-capable repos), and inspect post-commit `git status --short`. Done when: every applicable check exits 0 at the new SHA (or verified existing SHA), any unpopulated `todo/` scaffold (`wsl-site-1`) records its exact `validate` refusal (`rc=2`) beside passing hook and pin checks, and the working tree is clean. **Corrected 2026-11-23:** narrowed `todo-graph.py validate` exit-0 requirement from "where present" to "where a canonical TODO tree is populated" after chain 1 (`docs/reviews/00-reviewer/D00-T03-s3-chain1.md`) proved `wsl-site-1` has `todo-graph.py` installed on a scaffold-only `todo/` directory (`rc=2`, `"canonical TODO tree is missing or empty"`) while its `100755` pre-commit hook and pin check pass.
- [x] Commit: `chore: update the Conclave-SDK kits (design by path, safety lenses)` in each changed project, and `docs: kit refresh record (D00 T03 §3)` here with the per-project outcome list (using neutral aliases for client sites) in `docs/phase-runs/2026-11-22-phase-9.md`.

**Test checkpoint:** per-file audit at committed HEAD confirms all 19 refreshed projects hold byte-equal `scripts/review-prompt.py` (SPDX-normalized on `Office`; `ScratchPad` `--ref` JSON resolver compatibility deferred to `§11`) and all four `docs/*-prompt.md` templates, byte-equal or behavior-tested `scripts/review_pin.py`, `schedule_ok`+`changed_paths` stamp enforcement on all 18 stamp-capable repos (`ScratchPad` stamp gate deferred to `§12`), and applicable `GEMINI.md`/skill clauses (with remaining ports assigned to `§4`, `§5`, `§8`, `§10`, `§11`, `§12`); every refreshed project passes 4-kind Fidelity rendering and temporary conditional-pin `--no-surface` matching/nonmatching proofs.

> **Verified:** 2026-11-23 | §3 | 787351707d4261fd0d27db1b483a7ddaf94960b8
> **Review:** `docs/reviews/d00-t03-s3.json`

## 4. Agent Entrypoints, Hooks and Native Skill Folders

> **Started:** 2026-11-23T03:53Z

Antigravity must find each project's skills, rules and campaign Stop hook without indirection. Measured 2026-11-17: Recto has no `GEMINI.md`; Resolute has no `.agents/hooks.json` though its Claude Stop hook runs `scripts/run-guard.py hook`; Gemail, Office and Recto have `.agents/skills.json` pointing at `.claude/skills` and no `.agents/skills/`. Whether Antigravity loads `.agents/skills.json` is not verified, so the real folders are added and the stub is kept until an `agy` session proves the folders load. **Verified 2026-11-23:** (1) `Resolute/scripts/run-guard.py hook` originally took no `--runner` flag and only handled Claude's `hook_event_name`/`session_id`/`decision: block`; §4 adds `--runner antigravity` (reading `conversationId`, binding via `RESOLUTE_RUN_GUARD_SESSION`, ending on owner `USER_CANCELED`, emitting `decision: continue` without `CronCreate`) and wires `Resolute/.agents/hooks.json` to `python ../scripts/run-guard.py hook --runner antigravity`. (2) The project with `-Agent antigravity` (and no `-Runner`) is `Bosun` (`scripts/start-run.ps1` has `[ValidateSet('claude', 'antigravity')] [string]$Agent = 'claude'`), which is currently held by a live run guard; read-only inspection confirms `Bosun/scripts/tests/test_run_guard.py` already tests both `antigravity` and `agy`. (3) `agy.EXE` is installed on this host, so live skill/rule loading will be attempted once in one of the three projects (recording output or exact refusal if headless invocation is unavailable, keeping `.agents/skills.json` in place if unproven). (4) All four target projects (`Gemail`, `Office`, `Recto`, `Resolute`) have clean working trees and no active run guard.

**Phase:** 9
**Needs:** windows-host
**Surface:** no

**Build order:**

1. Add `Recto/GEMINI.md` (pointing at `AGENTS.md`, `.agents/rules/`, and the ordered design-contract fallback), add Antigravity Stop-hook support (`conversationId` + `{"decision": "continue"}` and launcher session binding) to `Resolute/scripts/run-guard.py` + `scripts/lib/run_guard.py` + `Resolute/.agents/hooks.json`, and test the configured command from `.agents/` with isolated guard state. Done when: `Recto/GEMINI.md` passes its checks and `Resolute`'s Antigravity hook test proves continue-on-active, release-on-ended, and foreign-session isolation.
2. Mirror every `.claude/skills/<name>/` folder (including referenced templates, gate cards, and `references/` resources) into `.agents/skills/<name>/` in `Gemail`, `Office`, and `Recto` (applying kit patches where anchors match and hand-porting diverged skills with `--writer agy` and `.agents/skills/` paths), port §1 design-contract clauses to `Gemail`, update stale entrypoint/structure docs (`Gemail/GEMINI.md`, `Gemail/AGENTS.md`, `Office/AGENTS.md`, `Office/CLAUDE.md`, `Recto/docs/todo-workflow.md`), attempt isolated live `agy` discovery without `.agents/skills.json`, and audit all 24 registered projects. Done when: every check passes and all per-project commits and fleet outcomes are recorded in `docs/phase-runs/2026-11-22-phase-9.md`.

- [x] Write `GEMINI.md` in `Recto`, pointing at its `AGENTS.md` and `.agents/rules/` and carrying the ordered §1 design-contract fallback (`.agents/rules/design-contract.md`, or `.claude/rules/design-contract.md`, else `AGENTS.md`, so it resolves validly before §5 creates `.agents/rules/design-contract.md`). Done when: `Recto/GEMINI.md` exists, names `AGENTS.md` and `.agents/rules/`, and its fallback resolves to an existing file. Cheaper substitute: a copy of another project's file, which names the wrong rules.
- [x] Add Antigravity Stop-hook handling (`--runner antigravity` reading `conversationId` and emitting `{"decision": "continue"}`, plus launcher binding for `-Runner agy`) to `Resolute/scripts/run-guard.py` and `Resolute/scripts/lib/run_guard.py`, and write `Resolute/.agents/hooks.json` running `python ../scripts/run-guard.py hook --runner antigravity`. Done when: `Resolute/.agents/hooks.json` parses as JSON and a test running the configured command from `.agents/` with isolated guard state asserts continue on owning active run, release on ended/cancelled run, and no interference on a foreign session.
- [x] Mirror every folder under `.claude/skills/` (including all referenced templates, gate cards, and `references/` resources) into `.agents/skills/` in `Gemail`, `Office`, and `Recto` (applying kit `skill-patches/agents/` where anchors match, hand-porting diverged project-owned skills with `--writer agy` and `.agents/skills/` paths while keeping `.claude/skills/` routing as `claude`), and port the §1 design-contract rule, path trigger, and both-checks (static lint + rendered check) clauses into `Gemail`'s `GEMINI.md`, `process-todo-section/SKILL.md`, and `review-todo-section/SKILL.md` (both `.claude/skills/` and `.agents/skills/`). Done when: full skill inventory matches `.claude/skills/` in each project, every internal reference in `.agents/skills/` resolves, a mutation removing a secondary skill or resource fails the inventory check, and `Gemail`'s `GEMINI.md` and skills carry the clauses.
- [x] Update stale entrypoint and structure docs in `Gemail` (`GEMINI.md`, `AGENTS.md`), `Office` (`AGENTS.md`, `CLAUDE.md`), and `Recto` (`docs/todo-workflow.md`) so they name `.agents/skills/` accurately and match what is on disk. Done when: effective entrypoints point Antigravity to `.agents/skills/` and `.agents/rules/` and contain no stale `skills.json`-only or "mirrors removed" claims.
- [x] Prove native loading once via `agy` in an isolated copy of one migrated project with `.agents/skills.json` removed, checking a native-only skill detail and an always-on rule; if `agy` proves native loading, record the quoted output and remove `.agents/skills.json` (or if headless `agy` cannot run here, record why, keep `.agents/skills.json` in place, and assign the live proof to `§16` / follow-up). Done when: the proof output or exact refusal and stub disposition are recorded.
- [x] Run a fleet-wide audit of `GEMINI.md`, `.agents/hooks.json` (valid JSON), and `.agents/skills/process-todo-section/SKILL.md` across all 24 registered projects, recording per-project applicability, commit SHA, and outcome in `docs/phase-runs/2026-11-22-phase-9.md` (routing any held checkout to §5 write-capable retry). Done when: all 24 projects have an audited status row.
- [x] Commit: `agents: native Antigravity entrypoint, hooks and skills` in each changed project (`Gemail`, `Office`, `Recto`, `Resolute`), and `docs: agent entrypoints and native skills record (D00 T03 §4)` here.

**Test checkpoint:** in `Gemail`, `Office`, `Recto`, and `Resolute`, `.agents/hooks.json` parses as JSON, `Resolute`'s Antigravity hook test passes from `.agents/`, full `.agents/skills/` inventory and internal references pass (and fail when a secondary skill or resource is removed), `Recto/GEMINI.md` and `Gemail`'s design-contract clauses pass, and all 24 registered projects are audited in `docs/phase-runs/2026-11-22-phase-9.md`.

> **Verified:** 2026-11-23 | §4 | 250d805a1aaf6d0594c5b4754e750f4b68c46dd0
> **Review:** `docs/reviews/d00-t03-s4.json`

## 5. Design Contract Rule in Every Project

> **Started:** 2026-11-24T20:52Z

A skill is read when invoked; a rule under `.agents/rules/` is always on. Each project gets one short rule that states its own facts, so the planner and the executor never assume `design/SPEC.md`. Every fact is reread in the project: the survey found contracts at seven different paths, token sources that range from a JSON file to a table in the SPEC to another repository's theme, and a rendered check of the built app in only two projects. **Verified 2026-11-24:** surveyed all 24 registered projects in `.conclave/local.toml`: 22 are free with clean trees (`wsl-site-1`, `wsl-site-2`, `Berth`, `Bosun`, `Busview`, `CarbonCD`, `DoubleTake`, `Gemail`, `GluonStack`, `Isotone`, `Kami`, `KitsuneBrowser`, `Merchant`, `Office`, `Recto`, `Resolute`, `Resolute-SDK`, `ScratchPad`, `Steward`, `Strata`, `Voxel`, `Wobble`) and 2 are held/dirty (`RasterFold` 14 dirty files, `Updates` 1 dirty review file `docs/reviews/00-service/D00-T04-s5.md`). `Bosun` is now free and its `AGENTS.md` (owner decision 2026-11-12) explicitly forbids importing, merging, or syncing from Conclave-SDK kits, so `Bosun` is exempt from the §3 kit refresh retry while still receiving its own design-contract rule in §5. Any project still held when §5 commits (`Updates` for §3+§5, `RasterFold` for §5) gets a newly filed write-capable retry section in this SDK graph added to §16's `Depends On`. Four free projects already carry built-app rendered-check commands (`Berth`, `Bosun`, `Resolute`, `ScratchPad`), eight already carry planned rendered-check sections in `todo/` (`CarbonCD`, `DoubleTake`, `Isotone`, `KitsuneBrowser`, `Merchant`, `Resolute-SDK`, `Voxel`, `Wobble`), and `wsl-site-1` has an empty `todo/` scaffold (`validate` rc=2) and is a live Pressable WooCommerce shop verified via browser readback (`AGENTS.md:21`, explicit exemption recorded in its rule and fleet table); each remaining free project with a populated `todo/` tree and no built-app rendered check or existing planned section gets one filed via its own `add-todo`. **Planned 2026-11-24 (plan review, P2/P3):** (1) add `trigger: always_on` frontmatter to every `.agents/rules/design-contract.md` and cite `.agents/rules/design-contract.md` in every project's `AGENTS.md` so every supported agent discovers it outside a skill invocation; (2) verify rule content against each project's authoritative sources (all five parts, applicable bans, explicit disposition for missing facts, no pointer substituted for contract); (3) for cross-repo token providers (`Busview`, `Resolute` via `sdk.json` -> `Resolute-SDK`), cite `sdk.json` and verify the provider theme at its pinned commit without machine paths; (4) run each available lint/render invocation from the project root to verify it executes and renders the built app (not a mockup), and verify each deferred section's deliverable covers a built-app rendered check; (5) record `wsl-site-1`'s explicit exemption (browser-verified live Pressable WooCommerce shop, empty `todo/` scaffold) in its rule and fleet table; (6) file any still-held project retry in the SDK graph and add it to `§16`'s `Depends On`; (7) refresh any freed held project before taking its `§5` inventory, and assign `§7` the rule/mirror/`AGENTS.md` update for every newly installed lint command; (8) verify the 24-row fleet table programmatically against `.conclave/local.toml` (24 unique neutral aliases), reading each delivered rule and mirror from its recorded commit SHA via `git show`, and verifying every retry ref resolves and blocks `§16`; (9) run the negative missing-path verifier against a scratch copy of a rule instead of renaming a live file, distinguishing file-path refs from commands and hex examples.

**Phase:** 9
**Needs:** windows-host
**Surface:** no

**Build order:**

1. Re-check held projects (`Updates`, `RasterFold`): refresh any freed project first before taking its §5 inventory, or file a write-capable retry section in this SDK graph and add it to §16's `Depends On`. Done when: every held project has a resolving SDK retry section blocking §16, and `Bosun`'s `AGENTS.md` exemption from §3 kit refresh is recorded.
2. For each free project, inspect its authoritative sources, write `.agents/rules/design-contract.md` (with `trigger: always_on` frontmatter, under 40 lines, all five parts), mirror byte-equally to `.claude/rules/design-contract.md` where `.claude/rules/` exists, file a built-app rendered-check section via its own `add-todo` where a populated `todo/` lacks one (recording `wsl-site-1`'s explicit exemption), and update `AGENTS.md` so it cites `.agents/rules/design-contract.md`, the authoritative contract and lint, and no broken unlabelled design path. Done when: every available lint/render command is verified, every referenced/filed section resolves and covers a built-app rendered check, and each free project commits cleanly.
3. Run the fleet verifier across all 24 registered projects in `.conclave/local.toml`, checking unique aliases, reading each delivered rule and mirror from its recorded commit SHA, verifying content/length/frontmatter/paths plus the scratch-copy missing-path negative check, and record the 24-row table in `docs/phase-runs/2026-11-24-phase-9.md`. Done when: the checkpoint passes.

- [x] For each free project (after refreshing any newly freed held project first), read its `AGENTS.md`, its design folder, `.conclave/design-lint.json`, its pre-commit hook, and any cross-repo dependency pin (`sdk.json` -> provider commit), and record the contract files, token source, icon registry, lint command and rendered check. Done when: each fact names a tracked file (`git ls-files <path>` prints it, or `sdk.json` plus verified provider path at its pinned revision) or states an explicit missing disposition.
- [x] Write `.agents/rules/design-contract.md` with `trigger: always_on` frontmatter and five parts: Contract, Tokens and icons, Never (raw `#RRGGBB` or `0xRRGGBB`, a hardcoded `rgb()` or `ColorF`, a literal spacing, radius or font size where a token exists, an inline unmanaged SVG or an emoji as an icon, an unapproved backdrop, plus the project's own bans), Static lint, Rendered check. Done when: the rule is under 40 lines, has `trigger: always_on`, carries all five parts and applicable bans against authoritative sources (never substituting a pointer file for the contract), and names only that project's real paths. Cheaper substitute: one rule copied to every project, which cites a contract most do not have.
- [x] Verify every available lint and built-app render invocation from the project root; where no command renders the built app, say so in the rule and require each surface section to build or name its own rendered check, and confirm an existing planned section (verifying its deliverable covers a built-app rendered check) or file one section in that project (through its own `add-todo`, where a populated `todo/` exists; recording `wsl-site-1`'s explicit live-site/empty-scaffold exemption). Done when: every available command is verified, every rule's Rendered check part is true today, and each referenced or filed section resolves and covers a built-app rendered check.
- [x] Mirror `.agents/rules/design-contract.md` to `.claude/rules/design-contract.md` wherever `.claude/rules/` exists. Done when: `git diff --no-index` of the two files prints nothing at the recorded commit.
- [x] Update each free project's `AGENTS.md` to cite `.agents/rules/design-contract.md`, the authoritative contract, and the static lint (fixing any project that omits design lint, calls a pointer file the contract, or cites a nonexistent token/design path without marking it planned). Done when: `AGENTS.md` cites `.agents/rules/design-contract.md` and every design path it cites exists or is marked planned in the same line.
- [x] Re-check `Bosun`, `Updates`, and `RasterFold`: record `Bosun/AGENTS.md`'s owner exemption from §3 kit refresh; refresh any freed held project before taking its §5 inventory; and for any project still held/dirty when §5 runs, file a dedicated write-capable retry section in this SDK graph (`todo/00-reviewer/TODO-03-design-and-safety-lenses.md`) covering every outstanding operation and add it to `§16`'s `Depends On`. Done when: `Bosun`'s exemption is recorded and every still-held project has a resolving SDK retry section that blocks `§16`.
- [ ] Commit: `rules: the design contract, always on` in each changed project, and `docs: design contract rule record (D00 T03 §5)` here with the 24-project commit-indexed table in `docs/phase-runs/2026-11-24-phase-9.md`.

**Test checkpoint:** fleet verifier script compares all 24 unique neutral aliases against `.conclave/local.toml`, reads `.agents/rules/design-contract.md` (and `.claude/rules/design-contract.md` where present) from each delivered project's recorded commit SHA, verifies `trigger: always_on`, under 40 lines, all five parts, every referenced file path exists (distinguishing paths from commands and hex examples like `#RRGGBB`), fails on a scratch copy of a rule pointing at a missing path, verifies `AGENTS.md` cites `.agents/rules/design-contract.md`, and verifies every held project's retry ref resolves and blocks `§16`.

## 6. Design Paths in Every Three-Pass Pin

With §1 installed, a pin names its user interface, style, asset, icon and design contract folders once and the stamp holds every section that touches them to `design`. Paths are repository-relative with forward slashes. Include the user interface roots a project's own plan names but has not created (ten projects have no interface source yet), so new code is covered on arrival. Bosun stays on rotation and gets no entry.

**Phase:** 9
**Needs:** windows-host
**Surface:** no

**Build order:**

1. Add two entries to each three-pass project's `.conclave/reviewers.toml`. Done when: `python scripts/review_pin.py --check --all` prints `ok`.
2. Prove each with `--lenses`. Done when: the outputs below are quoted in the commit body.

- [ ] Add `[[schedule.conditional]]` with `lenses = ["design"]`, `passes = ["round", "reconciliation"]` and the project's paths to each three-pass pin. Done when: `python scripts/review_pin.py --lenses round --no-surface --paths <a real UI file>` prints `design` and the same command with a non-UI file does not. Cheaper substitute: removing `design` from the round, which drops it from `Surface: yes` sections outside the paths.
- [ ] Add a second entry with `lenses = ["design-plan"]`, `passes = ["plan"]` and the same paths. Done when: `python scripts/review_pin.py --lenses plan --paths <a real UI file>` prints `design-plan`.
- [ ] Confirm no section in the project is between its plan review and its stamp, or record that it finishes under the pin committed at its plan review. Done when: the commit body names each such section or says none.
- [ ] Commit the pin alone, before any section's next plan review. Done when: `git log --oneline -1 -- .conclave/reviewers.toml` shows the commit.
- [ ] Commit: `review: design lens by path` in each project.

**Test checkpoint:** `python scripts/review_pin.py --check --all` exits 0 in every three-pass project, and `--lenses round --no-surface --paths <UI file>` prints `design` there and not for `README.md`.

## 7. Design Lint Where a Project Has None

Two Windows projects and the WSL project have no token or literal lint; the base kit ships `scripts/design-lint.py` with `--self-test`, `--staged` and a baseline that only shrinks unless `--allow-add --reason` is given. One of the two has its interface in XAML and C# with generated theme files checked by its own `--check` scripts; the other is C++ with no XAML. Two more projects use a narrower linter of their own, which is kept. One project's linter covers only one of its two interface roots.

**Phase:** 9
**Needs:** windows-host
**Surface:** no

**Build order:**

1. Install `scripts/design-lint.py` and `.conclave/design-lint.json` where absent. Done when: `--self-test` exits 0 and a plain run exits 0.
2. Wire it into each project's tracked pre-commit hook. Done when: a commit adding a raw `#FF00AA` to a UI file is refused.

- [ ] Install the kit's `scripts/design-lint.py` and its test, and write `.conclave/design-lint.json` with the project's `contract`, `ui_roots` and `exclude`. Done when: `python scripts/design-lint.py --self-test` prints `design-lint self-test: ok`.
- [ ] Where the first plain run reports findings, record them with `--update-baseline` in `.conclave/design-lint-baseline.json`, and only there. Done when: a plain run exits 0 and a new raw color in a scratch copy of a UI file exits 1. Cheaper substitute: a baseline in a project with no findings, which hides the first real one.
- [ ] Add the staged run to the tracked pre-commit hook (`scripts/hooks/pre-commit` or `tools/githooks/pre-commit`), LF line endings, mode `100755`, beside `python scripts/todo-graph.py validate` where the hook lacks it. Done when: `git ls-files -s <hook>` shows `100755` and `git ls-files --eol <hook>` shows `i/lf`.
- [ ] Set `core.hooksPath` in the local clone where it is unset. Done when: `git config core.hooksPath` prints the tracked hook folder.
- [ ] Widen `ui_roots` in the project whose web dashboard root is not covered, recording existing findings in its baseline. Done when: a raw color added to a file under that root exits 1.
- [ ] Keep the two projects' own linters and the document checker as they are, and update `.agents/rules/design-contract.md`, its `.claude/rules/design-contract.md` mirror (where `.claude/rules/` exists), and `AGENTS.md` for every project where §7 newly installs or widens a lint command (as well as recording retained linters). Done when: each linter exits 0 on `HEAD` and the rule, mirror, and `AGENTS.md` match the resulting commit.
- [ ] Commit: `design: token and literal lint in the pre-commit hook` in each project.

**Test checkpoint:** in each project with a user interface, `python scripts/design-lint.py --self-test` (or its own linter's) exits 0, a plain run exits 0, and the run exits 1 on a scratch fixture holding `#FF00AA`.

## 8. Resolute on Three-Pass

Resolute's pin is a rotation schedule and its `scripts/review-dispatch.py` knows neither `policy` nor conditional entries; it has no `scripts/review_pin.py` and its `scripts/todo-graph.py` is its own 1,677-line tool with no `stamp`. Follow "Moving an existing pin to three-pass" in `kits/reviewer/README.md`. Keep the Astra route, medium effort for plan and round, low for completion and reconciliation, `pass_cap = 33` and `blocking = ["P1", "P2"]`. One section there is mid-review (`D00 T04 §43`): it finishes under the rotation pin and is not migrated.

**Phase:** 9
**Needs:** windows-host
**Surface:** no

**Build order:**

1. Bring the reviewer kit's scripts and prompts current in Resolute. Done when: `python scripts/review_pin.py --check` runs there.
2. Replace the pin's schedule with the three-pass block. Done when: `--check --all` prints `ok`.

- [ ] Read Resolute's `AGENTS.md`, its review skills and its review tests for every line that describes the rotation schedule. Done when: the section body lists each `file:line`.
- [ ] Install the current `scripts/review_pin.py`, `scripts/review-dispatch.py`, `scripts/review-prompt.py`, `scripts/review_layout.py` and the four prompts, keeping any local edit the diff shows. Done when: `python scripts/review-dispatch.py --check-pin` prints `ok` under the old pin first. Cheaper substitute: editing the pin alone, which the old dispatcher refuses.
- [ ] Replace `[schedule]` in `.conclave/reviewers.toml` with the three-pass block (route `gemini` kept as it is, one name for the Antigravity writer). Done when: `python scripts/review_pin.py --check --all` prints `ok` and `--caps` prints `pass_cap 33`.
- [ ] Update the lines found in the first item so the documentation matches the pin, and say that `D00 T04 §43` finishes under rotation. Done when: a search for `rotation` in `AGENTS.md` and the skills finds only that note.
- [ ] Run Resolute's reviewer tests and its quick gate. Done when: they pass, quoted in the commit body.
- [ ] Commit: `review: three-pass pin and current reviewer scripts` in Resolute.

**Test checkpoint:** in Resolute, `python scripts/review_pin.py --check --all` prints `ok` and `python scripts/review_pin.py --lenses round` lists the round's lenses, which the rotation pin refused with "is not policy".

## 9. C++ Lens Entries in the C++ Projects

Only projects with C++ of their own get the entry: Resolute-SDK, Resolute and the one tool repository that holds any. The other 77 tool repositories keep their byte-identical pin until they hold C++. Read each tree for its real source paths and leave out the vendored toolchain, third-party code and build output.

**Phase:** 9
**Needs:** windows-host
**Surface:** no

**Build order:**

1. Add the two lens definitions and one conditional entry to each C++ project's pin. Done when: `--check` prints `ok`.
2. Prove each with `--lenses`. Done when: both lenses print for a C++ file and neither for a non-C++ file.

- [ ] List each project's C++ files with `git ls-files -- '*.cpp' '*.h' '*.hpp' '*.c'` and choose the path prefixes. Done when: the commit body names the prefixes and what was left out.
- [ ] Add `[schedule.lenses]` with the two questions of §2, word for word, and `[[schedule.conditional]]` with `lenses = ["thread-safety", "memory-safety"]`, `passes = ["round", "reconciliation"]` and those prefixes. Done when: `python scripts/review_pin.py --check` prints `ok`.
- [ ] Verify with `python scripts/review_pin.py --lenses round --paths <a real C++ file>` and with `README.md`. Done when: both lenses print for the first and neither for the second.
- [ ] In the tool repository, commit and push as its own rules say. Done when: `git status -sb` prints exactly `## main...origin/main`.
- [ ] Commit: `review: thread-safety and memory-safety lenses by path` in each project.

**Test checkpoint:** in each C++ project, `python scripts/review_pin.py --lenses round --paths <C++ file>` prints `thread-safety` and `memory-safety`, and prints neither for `README.md`.

## 10. Reviewer Scripts Current in the WSL Project

RasterFold took the base and reviewer kits long ago and keeps its own TODO system (`AGENTS.md` there says the todo kit is not installed). Measured 2026-11-17: no `scripts/review_pin.py`, no conditional handling in `scripts/review-dispatch.py`, a three-pass pin routing `gemini`, and a 12,996-line `scripts/todo-graph.py` whose `schedule_ok` replays `dispatch.scheduled` without changed paths. Its only rendered surface today is the documentation site under `docs/`.

**Phase:** 9
**Needs:** none
**Surface:** no

**Build order:**

1. Install the current reviewer scripts there. Done when: `python3 scripts/review_pin.py --check --all` prints `ok`.
2. Pass the changed files to `scheduled` in its `schedule_ok`. Done when: its own self-test covers a conditional lens.

- [ ] Read its `AGENTS.md`, `git status --short` and `build/unattended-launch.lock` (dated 2026-11-17 08:13) before any write. Done when: the body records that no run holds the tree, or the section stops there.
- [ ] Diff its `scripts/review-dispatch.py` and `scripts/review-prompt.py` against the kit's and install the kit's four reviewer scripts plus all four prompt templates (`docs/plan-review-prompt.md`, `docs/review-round-prompt.md`, `docs/completion-review-prompt.md`, `docs/reconciliation-review-prompt.md`), keeping local edits the diff shows. Done when: `python3 scripts/review-dispatch.py --check-pin` prints `ok` and all four prompt kinds render their exact `Fidelity:` line via `scripts/review-prompt.py`.
- [ ] Add a `changed_paths` replay to `schedule_ok` in its `scripts/todo-graph.py`, as `kits/todo/templates/scripts/lib/todo_graph.py` does. Done when: `python3 scripts/todo-graph.py self-test` passes with a new case that refuses a stamp whose round lacks a conditional lens. Cheaper substitute: adding the pin entry without the replay, which records the lens and never checks it.
- [ ] Add the `design` and `design-plan` entries for its site paths (`docs/_includes/`, `docs/assets/`, `docs/design/`, `assets/brand/`). Done when: `python3 scripts/review_pin.py --lenses round --no-surface --paths docs/assets/css/site-states.css` prints `design`.
- [ ] Commit: `review: current reviewer scripts and design by path` in the WSL project.

**Test checkpoint:** there, `python3 scripts/todo-graph.py validate` and `python3 scripts/todo-graph.py self-test` exit 0 and `python3 scripts/review_pin.py --check --all` prints `ok`.

## 11. Surface Validation in the Custom Graphs

Three projects keep a `scripts/todo-graph.py` of their own that never checks a Surface field or the four surface lines (Resolute 1,677 lines, ScratchPad 1,273, Gemail 10,818; Gemail and RasterFold treat a Fidelity line as the surface marker). All three use the `DNN TNN §N` grammar. The kit's rule is the model: `Surface` is `yes` or `no`, and `yes` requires `Fidelity`, `Job`, `Treatment` and `Chrome`.

**Phase:** 9
**Needs:** windows-host
**Surface:** no

**Build order:**

1. Count the sections each tool would newly refuse. Done when: the count is recorded per project.
2. Add the check to each `validate`, as a fault where the count is zero and with a recorded baseline where it is not. Done when: each tool's `self-test` covers it.

- [ ] Run a read-only scan of each project's `todo/` for sections with no `**Surface:**` line and for `Surface: yes` sections missing one of the four lines. Done when: the body records the counts, dated.
- [ ] Add the Surface check to `validate` in each custom `scripts/todo-graph.py`, keeping its own section grammar and receipts folder, and make `ScratchPad`'s `scripts/todo-graph.py resolve` emit the JSON shape `scripts/review-prompt.py --ref` expects so unoverridden `--ref` Fidelity lookup succeeds against `ScratchPad`'s candidate commits. Done when: `python scripts/todo-graph.py self-test` passes with a case that refuses `Surface: yes` without a Fidelity, and `ScratchPad`'s `review-prompt.py --ref` resolves Fidelity without `--fidelity`. Cheaper substitute: a warning, which a run does not read.
- [ ] Where existing sections would be refused, add the missing lines to the open ones and leave stamped ones as they are (a stamped section's text is its contract). Done when: `python scripts/todo-graph.py validate` exits 0.
- [ ] Commit: `todo: Surface and its four lines are validated` in each project.

**Test checkpoint:** in each of the three projects, `python scripts/todo-graph.py validate` exits 0 and `python scripts/todo-graph.py self-test` fails when the Surface check is removed.

## 12. Stamp Gate Planned in Each Custom Graph's Project

The three custom graphs have no `stamp`, so nothing there can refuse a section whose review lacked `LENS design:`. A stamp gate is a feature of each project's own tooling, so it is planned and reviewed there: this section files it and builds nothing. Gemail also has no `.conclave/reviewers.toml` (its reviewers are slots in `.conclave/panel.toml` read by `scripts/panel_slots.py`), so its filed section first decides between a pin beside the panel and a bridge from it.

**Phase:** 9
**Needs:** windows-host
**Surface:** no

**Build order:**

1. File one section per project through that project's own `add-todo`. Done when: each resolves.
2. Record the three references here. Done when: the body names them.

- [ ] In each of the three projects, search its `todo/` for a section that already owns a stamp or receipt check. Done when: the body records the home found, or none.
- [ ] File a complete section there: a `stamp` (or the project's own completion command) that reads the section's findings file, replays the pin's schedule over the files the candidate changed, and refuses a missing lens. Done when: `python scripts/todo-graph.py resolve "<ref>"` there does not exit 1 or 2. Cheaper substitute: a one-line stub, which the format refuses.
- [ ] For Gemail, state in the filed section the choice between `.conclave/reviewers.toml` with `claude` and `agy` routed to Astra on three-pass and a bridge from `.conclave/panel.toml`, with what each costs. Done when: the section names both and the files that reference the panel.
- [ ] Record the three filed references under this section, dated. Done when: each is a `DNN TNN §N` that resolves in its project.
- [ ] Commit: `todo: file the stamp gate` in each project, and `docs: custom graph stamp gates filed (D00 T03 §12)` here.

**Test checkpoint:** `python scripts/todo-graph.py resolve "<filed ref>"` in each of the three projects prints the section and exits 0 or 4.

## 13. Concurrency and Lifetime Checks in the Clang-Tidy Ratchet

Resolute's mechanical gate is `scripts/tidy-ratchet.py` (clang-tidy, a one-way ratchet) run from `scripts/check-all.ps1`, with the toolchain under `sdk/reskit/llvm-mingw`. Resolute first, then Resolute-SDK. Nothing existing blocks: current findings are recorded and only new ones fail. The change is nontrivial, so it goes through that project's pinned reviewer in a fixed number of rounds.

**Phase:** 9
**Needs:** windows-host
**Surface:** no

**Build order:**

1. Enable the checks in each project's clang-tidy configuration. Done when: the ratchet runs with them.
2. Re-baseline. Done when: a new finding fails and the recorded ones pass.

- [ ] Read `scripts/tidy-ratchet.py` and the `.clang-tidy` of each project for the checks enabled today. Done when: the body lists them, dated.
- [ ] Enable `concurrency-*` and the `bugprone-*` and `clang-analyzer-*` checks that cover lifetime, dangling and bounds. Done when: `python scripts/tidy-ratchet.py` lists findings from the new checks.
- [ ] Re-baseline the ratchet so current findings are recorded. Done when: the ratchet exits 0, and exits non-zero after a scratch edit that adds one new finding. Cheaper substitute: disabling a noisy check, which hides what it found.
- [ ] Run the project's full gate once through `bosun run -- pwsh scripts/check-all.ps1`. Done when: it passes, quoted.
- [ ] Review the change through that project's pinned reviewer. Done when: its findings file records the passes and every finding is fixed or filed.
- [ ] Commit: `tidy: concurrency and lifetime checks under the ratchet` in each project.

**Test checkpoint:** in each project, `python scripts/tidy-ratchet.py` exits 0 on `HEAD` and exits non-zero on a scratch copy with one added `bugprone-use-after-move` finding.

## 14. Sanitizer Test Configuration

No sanitizer build was found in Resolute's CMake files or gates. Not verified: whether AddressSanitizer and UndefinedBehaviorSanitizer build and run on the pinned llvm-mingw toolchain for the Catch2 suite. ThreadSanitizer does not run on Windows and is not planned. If the pinned toolchain cannot do it, the section ends there with the error: the toolchain is not swapped. A sanitizer build is a test build and never ships (`D04 T03 §2` refuses one in a shipped image).

**Phase:** 9
**Needs:** windows-host
**Surface:** no

**Build order:**

1. Probe the toolchain with a one-file program. Done when: the error is caught, or the failure is quoted.
2. Add a preset and a check of its own. Done when: the Catch2 suite runs under it.

- [ ] Build and run a probe with `-fsanitize=address,undefined` on the pinned toolchain, beside a plain control build. Done when: the sanitized probe reports the planted heap overrun and the plain one does not, or the build error is quoted and the section stops.
- [ ] Add a CMake preset for the sanitized Catch2 suite, outside the default build. Done when: `ctest --preset <name>` runs the suite.
- [ ] Add it as its own check, not inside `scripts/check-all.ps1`'s default path. Done when: the default gate's duration is unchanged and the new check has its own command.
- [ ] Fix what the run finds where the fix is cheap, each with a regression test, and file the rest in the owning project. Done when: the run passes or every remaining finding has a section.
- [ ] Commit: `test: an AddressSanitizer and UBSan run of the Catch2 suite` in each project.

**Test checkpoint:** the sanitized preset's `ctest` passes, and fails on a scratch test that reads one element past a `std::vector`.

## 15. Bounded C++ Hot-Spot Audit

One review per repository of the files most likely to hold a threading or lifetime defect, through the two lenses of §2. Resolute-SDK first, then Resolute. The tool repositories and the projects built on the SDK are covered through it and get no audit of their own. One pass only: there is no second audit round.

**Phase:** 9
**Needs:** windows-host
**Surface:** no

**Build order:**

1. Rank the files and take at most five per repository. Done when: the ranking and its counts are recorded.
2. Run one review outside a section through the pinned reviewer. Done when: `docs/reviews/<date>-cpp-safety-audit.md` exists in each.

- [ ] Rank each repository's C++ files by thread creation, locks, atomics, callbacks that cross threads and raw buffer or pointer arithmetic (a `git grep -c` per pattern). Done when: the findings file opens with the table and the five files chosen.
- [ ] Run `python scripts/review-dispatch.py --kind round` outside a section with `--paths` naming those files, recorded to `docs/reviews/<date>-cpp-safety-audit.md`. Done when: the record holds `LENS thread-safety:` and `LENS memory-safety:` lines.
- [ ] Fix each P1 and P2 finding that is cheap, with a regression test that fails before the fix. Done when: each is named with its commit under the review.
- [ ] File every other finding in the owning project through its `add-todo`. Done when: each has a `- Filed:` line with a reference that resolves.
- [ ] Commit: `docs: C++ safety audit, findings fixed or filed` in each repository.

**Test checkpoint:** `python scripts/review-dispatch.py --list-rounds --records docs/reviews` in each repository lists the audit record, and every finding in it has an `- Implemented:` or `- Filed:` line.

## 16. Read-Only Verification Across the Projects

One script, outside every repository, answers whether each project holds what this file promised, and what it cannot check it says. It reads the projects from `.conclave/local.toml` and writes nothing in any project.

**Phase:** 9
**Needs:** windows-host
**Surface:** no

**Build order:**

1. Write the script in the scratch folder `.conclave/local.toml` names. Done when: it prints one row per project.
2. Record its table. Done when: `docs/phase-runs/` holds it with each project's commit.

- [ ] Check per project: `GEMINI.md`, `.agents/hooks.json` parsing as JSON, `.agents/skills/process-todo-section/SKILL.md`, `.agents/rules/design-contract.md` and every path it cites. Done when: a renamed cited path turns that project's row red.
- [ ] Check `python scripts/review_pin.py --check --all`, the Antigravity writer's route to Astra on three-pass, `--lenses round --no-surface --paths <UI file>` printing `design`, and for C++ projects the two safety lenses. Done when: a pin with the entry removed turns the row red.
- [ ] Check `python scripts/review-prompt.py --kind round --fidelity x` writes a `- Fidelity:` line. Done when: the row quotes the line.
- [ ] Check the design linter: `--self-test`, a plain run on `HEAD`, exit 1 on a scratch fixture with `#FF00AA`, and its presence in the hook `core.hooksPath` names. Done when: each is a column.
- [ ] Check `python scripts/todo-graph.py validate` and `git status --short` empty. Done when: each is a column.
- [ ] Mark as not applicable, with the reason, what a project is exempt from by the owner's decisions (Bosun's pin, the three custom graphs' stamp gate, the checkpoints of open surface sections), verify `Office`'s SPDX-normalized `review-prompt.py` parity, and label every row with its explicit disposition (`refreshed at <SHA>`, `already verified at <SHA>`, or `deferred to <section>`). Done when: no exempt cell reads as a pass and every row names its disposition.
- [ ] Commit: `docs: design and safety lenses, verified across the projects (D00 T03 §16)`

**Test checkpoint:** `python <scratch>/verify-carbon-fleet.py` exits 0 with every applicable cell green, and exits non-zero when run against a copy of one project whose design rule cites a missing path.

## 17. One Opus Design Check Before a Surface Section's Review

> **Started:** 2026-11-19T16:56Z

Filed 2026-11-19 at the owner's request. Opus 5.5 is the strongest designer and GPT-6.2 Astra the strongest reviewer, and a review by the writer's own family is no review (global rule 7). So a surface section is written by whichever writer the plan gives it (Antigravity or Claude), checked once by Opus 5.5 for design before the review begins, fixed by its writer, and then reviewed by Astra through the pin's three passes and every lens, `design` included, exactly as now. The check is part of the build, not a review pass: it runs once, never loops, holds no stamp and adds no gate. Berth is the first project (its `AGENTS.md`), and its D04 T01 §11 (not yet built) renders a window to PNG for the check and the design lens.

**Corrected 2026-11-19 (owner):** the section waited on §1 and its last item ran the step on Berth's next `Surface: yes` section. The step needs nothing §1 builds (it reads the Fidelity field the tree already resolves), so the wait is dropped. Berth has no ready surface section, so that item could not finish inside this section: the owner runs the Berth Gemini campaign to completion and judges the result, and the item is now the kit update of every project that installs the todo kit, which the owner asked for. The step's prompt lives in one kit document instead of the skill text, and the checkpoint gains a test that fails when a copy drops the step.

**Corrected 2026-11-19 (plan review, docs/reviews/00-reviewer/D00-T03-s17.md):** the check now runs in a folder holding only copies of its inputs, so it cannot read the writer's code; it sits after the rendered check of Step 6 and requires PNGs even where that check is a layout inspection; its reply ends in `clean`, `findings` or `unavailable`, and an unavailable check is recorded once and never retried; the live proof plants a known discrepancy; the duplicate copy test is replaced by a test of the canonical text, and the rollout merges with `--kit-new` and checks each project's installed skill.

**Corrected 2026-11-19 (build):** the checkpoint ran `python -m unittest tests.test_forge -k skill`, which selects no test, so it proved nothing; it is replaced by a dry-run update of a project that must list the new prompt and the step. The step's command passes the prompt on standard input and runs with `--restricted`: `--allowedTools Read` confined nothing (with the owner's permission bypass the proof read a file in another repository) and swallowed a prompt that followed it.

**Corrected 2026-11-19 (rollout):** sixteen projects were updated. Cofactor was left out: its tree has no commit yet, only an untracked scaffold. Gemail and Isotone run their own forks of the TODO system (their scripts differ from the kit by thousands of lines), so taking the kit's files would have replaced their design: each got the step inserted before its own Step 7 and `docs/design-check-prompt.md`, and nothing else. The other thirteen took the kit, their three review-skill copies merged because their only local change was the GPT-6.2 Astra name the kit now carries. **Corrected 2026-11-19 (completion):** fourteen took the kit, not thirteen (Berth, Busview, CarbonCD, DoubleTake, GluonStack, Kami, KitsuneBrowser, Merchant, Resolute-SDK, Steward, Strata, Updates, Voxel, Wobble). After the completion review's fix all sixteen took the step again, and `git status --short` in each printed nothing except Steward's ` M global.json`, an owner change this section did not touch; the owner had it committed (Steward `dae57e7bf`, 2026-11-19), and Steward's `git status --short` then printed nothing, so all sixteen trees are clean.

**Phase:** 9
**Needs:** none
**Surface:** no

**Build order:**

1. Write the prompt and the step. Done when: the skill's three copies carry it and its test passes.
2. Prove it once on a planted discrepancy. Done when: the reply names it in the right image.
3. Update every project that installs the todo kit. Done when: each project's installed skill carries the step.

- [x] Write the check's prompt in `kits/todo/templates/docs/design-check-prompt.md`: the section's promise, its Fidelity source and the rendered PNGs, all as files in the check's own folder; the question (does each rendered state match the design source, and where is it below the standard of the best desktop software); one numbered finding per line naming the PNG it shows; a line listing every input file it opened; and a last line `DESIGN: clean`, `DESIGN: findings` or `DESIGN: unavailable` (an input it could not read, or no image to judge). Done when: the file names each placeholder, the input line and the three outcomes.
- [x] Add the step to `kits/todo/templates/.claude/skills/process-todo-section/SKILL.md` after the rendered check of Step 6 and before the commit of Step 7: on a `Surface: yes` section, whoever the writer is, save each rendered state the section changed as a PNG (also when the rendered check is a layout inspection), copy the PNGs, the Fidelity source and the filled prompt into a new empty folder under the scratch folder, and run the confined command `docs/design-check-prompt.md` names (`claude -p --model claude-opus-5-5 --effort medium --restricted --strict-mcp-config --tools Read`, the prompt on standard input) once from that folder; fix every finding, rerun the rendered check, and quote the reply's input line, findings and outcome with the fixes in the commit body; a reply that is `unavailable`, empty or missing its outcome line is quoted as such and the section goes on to its review; the check is never repeated, holds no stamp, and the pin's passes, `design` included, run as they do. Done when: the step is in the Claude file and `python forge.py skill-copies` writes its Antigravity and Codex copies.
- [x] Say in `kits/todo/templates/.claude/skills/review-todo-section/SKILL.md` that the design check is part of the build, not a review pass. Done when: `python forge.py skill-copies --check` exits 0.
- [x] Add a test to `tests/test_skill_copies.py` that reads the canonical Claude file and finds the step's `Surface: yes` condition, its place between the rendered check and the commit of Step 7, the prompt file, the scratch-folder isolation, the three outcomes and the sentence that the pin's `design` review still runs. Done when: it passes, and fails when any one of those is removed from the Claude file.
- [x] Refresh the SDK's installed copy with `python forge.py self-sync`. Done when: `python -m unittest tests.test_forge -k self_sync` passes and the SDK's `docs/design-check-prompt.md` and `.claude/skills/process-todo-section/SKILL.md` carry the step.
- [x] Prove the check once: render a reference PNG and a candidate PNG of one small surface that differ in one visible way (a control's colour or a missing label), fill the prompt with a promise and the reference as Fidelity, run the step's command, and confirm from that folder that the session cannot open a file outside it. Done when: the reply names the planted difference in the candidate image and ends `DESIGN: findings`, the outside read is refused, and both are quoted in the commit body.
- [x] Update every project that installs the todo kit with `python forge.py update <project> todo --kit-new`, merge each `.kit-new` by hand and record it with `python forge.py record <project> todo --merged <path>`, and commit in each. Impossible OS is left out (owner, 2026-11-19): it runs its own review tooling, not these kits, and has no Antigravity writer now. Done when: in each project, every installed copy of `process-todo-section` names `docs/design-check-prompt.md`, that file exists, and the project's tree is clean.
- [x] Commit: `todo: one Opus design check before a surface section's review` (061fdbe3)

**Test checkpoint:** `python -m unittest tests.test_skill_copies` and `python -m unittest tests.test_forge -k self_sync` pass, `python forge.py update <project> todo --dry-run` lists `docs/design-check-prompt.md` and `process-todo-section` for a project on the older kit, `python forge.py skill-copies --check` exits 0, and the new test fails when the outcome lines are removed from the Claude file.

> **Verified:** 2026-11-20 | §17 | e0f50c2ec7d9d59c1ce8a184493b0e3875649726
> **Review:** `docs/reviews/d00-t03-s17.json`

## 18. Retry Held Projects for §3 and §5 (`Updates`, `RasterFold`)

`Updates` (`M docs/reviews/00-service/D00-T04-s5.md`, `M src/publish/release.ts`) and `RasterFold` (14 dirty `converter/` files) were held by active edits during `§5`, so neither checkout could be written to safely. This section retries the outstanding `§3` kit refresh (`Updates` `scripts/lib/todo_graph.py`) and `§5` design-contract rule, `.claude/rules/` mirror, `AGENTS.md` citation, and rendered-check filing for both projects once their working trees and run guards are free, blocking `§16` until verified.

**Phase:** 9
**Needs:** windows-host
**Surface:** no

**Build order:**

1. Confirm `Updates` and `RasterFold` have clean working trees and no active run guard, and refresh `Updates` via kit-scoped `forge.py update` before taking its §5 inventory. Done when: `Updates` passes §3 verification (`review_pin.py --check --all`, 4-kind Fidelity rendering, temporary conditional-pin `--no-surface` proof, and `todo-graph.py validate`).
2. Write `.agents/rules/design-contract.md` (with `trigger: always_on`, under 40 lines, all five parts), mirror byte-equally to `.claude/rules/design-contract.md` where `.claude/rules/` exists, file a built-app rendered-check section where none exists, update `AGENTS.md`, and commit locally in both projects. Done when: both projects pass the §5 fleet verifier at their recorded commit SHAs with clean trees.

- [ ] Verify `Updates` and `RasterFold` have empty `git status --short` and no active `.git/run-guard/state.json`. Done when: both checkouts are free before any write.
- [ ] Refresh `Updates` via kit-scoped `python forge.py update <Updates> todo --only scripts/lib/todo_graph.py` (and resolve any `base`/`reviewer` drift without overwriting project edits), then run its §3 verification (`review_pin.py --check --all`, 4-kind Fidelity rendering, temporary conditional-pin `--no-surface` proof, and `todo-graph.py validate`) and commit locally. Done when: `Updates` passes all §3 proofs with a clean tree before §5 inventory begins.
- [ ] Write `.agents/rules/design-contract.md` (`trigger: always_on`, under 40 lines, all five parts) and mirror to `.claude/rules/design-contract.md` (where `.claude/rules/` exists) in `Updates` and `RasterFold`, filing a built-app rendered-check section via each project's `add-todo` if none exists, and update each `AGENTS.md` to cite `.agents/rules/design-contract.md`. Done when: every path cited in both rules exists and both projects commit `rules: the design contract, always on` cleanly. Cheaper substitute: copying another project's rule without reading `Updates` and `RasterFold` directly.
- [ ] Commit: `docs: retry held projects Updates and RasterFold (D00 T03 §18)`

**Test checkpoint:** in `Updates` and `RasterFold`, `.agents/rules/design-contract.md` has `trigger: always_on`, is under 40 lines, passes path verification and scratch missing-path negative check, `AGENTS.md` cites it, `Updates` passes §3 proofs, and both trees have empty `git status --short`.

## Verification

- A fresh install carries both safety lenses and `design-plan`, and `python forge.py check-all` is green on CI for the stamped commits.
- The script of §16 is green for every applicable cell, and each exemption names the owner's decision behind it.
- Every finding and every piece of work this file did not build has a section in the project that owns it.
- `python scripts/todo-graph.py validate` and `python scripts/todo-graph.py plan --check` pass.
