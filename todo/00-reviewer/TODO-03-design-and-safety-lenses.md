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
| 1 | §1 | Design lens by path and Fidelity on every prompt | -- | [ ] |
| 2 | §2 | Thread-safety and memory-safety lenses in the template pin | §1 | [ ] |
| 3 | §3 | Kit refresh in every listed project | §2 | [ ] |
| 4 | §4 | Agent entrypoints, hooks and native skill folders | §3 | [ ] |
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
| 16 | §16 | Read-only verification across the projects | §6, §7, §9, §10, §11 | [ ] |
| 17 | §17 | One Opus design check before a surface section's review | -- | [x] |

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
- [ ] Commit: `reviewer: design by path, reviewed (D00 T03 §1)`

**Test checkpoint:** Run the `SURFACE_GATED` mutation once against `test_review_pin.py` (`test_a_conditional_entry_gives_the_round_its_surface_gated_design_by_path` fails), then on the unmodified candidate pass `python forge.py check-all --only kit-reviewer --only sdk-scripts`, `python -m unittest tests.test_skill_copies`, and `CONCLAVE_FULL_TESTS=1 python -m unittest tests.test_todo_graph -k design_path`.

## 2. Thread-Safety and Memory-Safety Lenses in the Template Pin

A C++ project needs two questions the built-in lenses only touch: `adversarial` mentions bounds and races and `integration` asks about threads and ownership, and both stay as they are. The loader accepts a lens declared under `[schedule.lenses]` that no step names (it checks the name and the question only; verified by reading `check_three_pass` on 2026-11-17), so the template can declare both lenses active and carry the conditional entry as a commented example a C++ project fills with its own paths. Not verified: whether a test or a doctor check requires an installed pin to match the template; check before editing.

**Phase:** 9
**Needs:** none
**Surface:** no

**Build order:**

1. Declare both lenses in `kits/reviewer/templates/.conclave/reviewers.toml`. Done when: a fresh install's `python scripts/review_pin.py --check` prints `ok` and `--lenses round` is unchanged.
2. Document them in `kits/reviewer/README.md`. Done when: the lens table, the conditional example and a short C++ projects note name both.

- [ ] Search `tests/` and `forge.py` for a check that an installed pin equals the template (`tests/test_template_pin.py`, `tests/test_three_pass_install.py`, the doctor's reviewer rows). Done when: the section body records, dated, what each requires.
- [ ] Add `[schedule.lenses]` to `kits/reviewer/templates/.conclave/reviewers.toml` with `thread-safety = "Which state is reached from two threads (UI, worker, callback, timer) without one lock or atomic owning it, and which lock order, wait, cancellation or teardown can deadlock or run after its owner is gone?"` and `memory-safety = "Which pointer, reference, view, handle or iterator can outlive what it refers to, and which size, index or cast is trusted unchecked?"`, each on one line, word for word. Done when: the template loads and a test compares both questions with these strings. Cheaper substitute: adding them to the built-in `LENSES`, which the owner ruled out.
- [ ] Add a commented `[[schedule.conditional]]` example beside it with `lenses = ["thread-safety", "memory-safety"]`, `passes = ["round", "reconciliation"]` and placeholder C++ paths. Done when: a test uncomments the example in a copy of the template and loads it, and `lenses_for` gives both lenses for a path under it and neither outside.
- [ ] Refresh the SDK's own `.conclave/reviewers.toml` where the first item found the tests expect template and install to agree. Done when: `python -m unittest tests.test_template_pin` passes.
- [ ] Add the two lenses to the lens table of `kits/reviewer/README.md`, the conditional example, and a "C++ projects" note saying they join the round and reconciliations by path and add no pass. Done when: the Markdown table check passes (`python -m unittest tests.test_forge -k markdown_table`).
- [ ] Commit: `reviewer: thread-safety and memory-safety lenses in the template pin (D00 T03 §2)`

**Test checkpoint:** `python forge.py check-all --only kit-reviewer --only sdk-scripts` and `python -m unittest tests.test_template_pin` pass, and the wording test fails when one word of either question is changed.

## 3. Kit Refresh in Every Listed Project

Sections 4 to 16 need the kit files of §1 and §2 in each project. `forge.py update` writes only files a project lacks or never changed and lists the rest, so a project's own edits are kept. The projects list holds one entry today, so it is completed first, in the ignored `.conclave/local.toml`.

**Phase:** 9
**Needs:** windows-host
**Surface:** no

**Build order:**

1. Complete `[[projects]]` in `.conclave/local.toml` and read `python forge.py drift`. Done when: drift lists every project of the survey.
2. Update each project with `python forge.py update <project>`. Done when: each project's `python scripts/review_pin.py --check` prints `ok` and its commit is confirmed.

- [ ] Add each surveyed project to `[[projects]]` in `.conclave/local.toml` (Windows and WSL paths as the file's one entry shows). Done when: `python forge.py drift` prints a row per project and `git status --short` shows no tracked change.
- [ ] For each project, read its `AGENTS.md`, `git status --short` and its run state under `build/` and `.git/run-guard/`. Done when: the section body lists, dated, each project as free or held, and a held or dirty one is skipped and named.
- [ ] Run `python forge.py diff <project> --patch` then `python forge.py update <project>` for each project with an install record (`.conclave/kits.json`), and resolve each file both sides changed with `--kit-new` and `python forge.py record <project> --merged <path>`. Done when: `python forge.py diff <project>` reports no `kit-newer` file for the `base`, `reviewer` and `todo` kits. Cheaper substitute: copying the kit over the project, which destroys its own edits.
- [ ] In the one project whose `AGENTS.md` forbids the todo and unattended kits and `forge.py update`, copy only the changed `reviewer` and `base` files by hand, keeping its `campaign_review_marker` edit in `scripts/review-dispatch.py` and `layout.receipts`. Done when: `git diff` there shows that edit intact and `python scripts/agent_routing.py check` exits 0.
- [ ] For each project with no install record, run `python forge.py record <project> --dry-run`, then record or hand-copy the three changed reviewer files as the dry run and its `AGENTS.md` allow. Done when: `scripts/review_pin.py` and `scripts/review-prompt.py` there are byte-equal to the kit's, or the difference is recorded with its reason.
- [ ] Run each project's own quick check after its update (`python scripts/todo-graph.py validate`, `python scripts/review_pin.py --check --all`, its pre-commit hook on the commit). Done when: each exits 0 and the commit is confirmed with `git log --oneline -1`.
- [ ] Commit: `chore: update the Conclave-SDK kits (design by path, safety lenses)` in each project, and `docs: kit refresh record (D00 T03 §3)` here with the per-project commit list in `docs/phase-runs/`.

**Test checkpoint:** `python forge.py drift` shows no project behind on the `reviewer` kit except those the record names with a reason, and `python scripts/review-prompt.py --kind reconciliation --help` in a refreshed project lists `--fidelity`.

## 4. Agent Entrypoints, Hooks and Native Skill Folders

Antigravity must find each project's skills, rules and campaign Stop hook without indirection. Measured 2026-11-17: Recto has no `GEMINI.md`; Resolute has no `.agents/hooks.json` though its Claude Stop hook runs `scripts/run-guard.py hook`; Gemail, Office and Recto have `.agents/skills.json` pointing at `.claude/skills` and no `.agents/skills/`. Whether Antigravity loads `.agents/skills.json` is not verified, so the real folders are added and the stub is kept until an `agy` session proves the folders load.

**Phase:** 9
**Needs:** windows-host
**Surface:** no

**Build order:**

1. Add the missing entrypoint and hook files, modelled on `kits/base/templates/GEMINI.md` and a sibling project's `.agents/hooks.json`. Done when: each parses and names files that exist.
2. Generate `.agents/skills/<name>/SKILL.md` in the three projects from their `.claude/skills/`. Done when: every skill folder has its Antigravity copy.

- [ ] Write `GEMINI.md` in the project that lacks one, pointing at its `AGENTS.md` and `.agents/rules/`. Done when: `GEMINI.md` exists in every listed project. Cheaper substitute: a copy of another project's file, which names the wrong rules.
- [ ] Write `.agents/hooks.json` in the project that lacks one, running its existing guard (`scripts/run-guard.py hook --runner antigravity`, as its sibling project does). Done when: the file parses as JSON and the guard script it names exists and accepts that runner name (`python scripts/run-guard.py --help`).
- [ ] Create `.agents/skills/<name>/SKILL.md` for every folder under `.claude/skills/` in the three stub projects, applying the kit's `skill-patches/agents/` where the skill is a kit skill. Done when: `.agents/skills/process-todo-section/SKILL.md` exists in each and each copy's commands name `agy` as the writer.
- [ ] Update each of the three projects' `AGENTS.md` and structure document where they say skills live only under `.claude/skills/`. Done when: a search for `skills.json` in those files finds only lines that match what is on disk.
- [ ] Prove the loading once: start `agy` in one of the three projects and ask it to list its skills and rules. Done when: the reply names `process-todo-section` and the output is quoted in the commit body; if it cannot be started here, record why and leave `.agents/skills.json` in place.
- [ ] Check the run launcher's agent parameter in the project that owns the desktop shortcut: `-Agent antigravity` is accepted and `-Agent agy` is not, and there is no `-Runner`. Done when: the launcher's test names both spellings, or the mismatch with the shortcut is filed in that project.
- [ ] Commit: `agents: native Antigravity entrypoint, hooks and skills` in each project.

**Test checkpoint:** `python -c "import json,sys; json.load(open('.agents/hooks.json'))"` exits 0 in every listed project, and a listing of `.agents/skills/process-todo-section/SKILL.md` finds the file in each.

## 5. Design Contract Rule in Every Project

A skill is read when invoked; a rule under `.agents/rules/` is always on. Each project gets one short rule that states its own facts, so the planner and the executor never assume `design/SPEC.md`. Every fact is reread in the project: the survey found contracts at seven different paths, token sources that range from a JSON file to a table in the SPEC to another repository's theme, and a rendered check of the built app in only two projects.

**Phase:** 9
**Needs:** windows-host
**Surface:** no

**Build order:**

1. Write `.agents/rules/design-contract.md` in each project from its own files. Done when: every path and script the rule cites exists.
2. Mirror it to `.claude/rules/design-contract.md` where `.claude/rules/` exists. Done when: the two files are byte-equal.

- [ ] For each project, read its `AGENTS.md`, its design folder, `.conclave/design-lint.json` and its pre-commit hook, and record the contract files, token source, icon registry, lint command and rendered check. Done when: each fact names a tracked file (`git ls-files <path>` prints it) or says none exists.
- [ ] Write the rule with five parts: Contract, Tokens and icons, Never (raw `#RRGGBB` or `0xRRGGBB`, a hardcoded `rgb()` or `ColorF`, a literal spacing, radius or font size where a token exists, an inline unmanaged SVG or an emoji as an icon, an unapproved backdrop, plus the project's own bans), Static lint, Rendered check. Done when: the rule is under 40 lines and names only that project's paths. Cheaper substitute: one rule copied to every project, which cites a contract most do not have.
- [ ] Where no command renders the built app, say so in the rule and require each surface section to build or name its own rendered check, and file one section in that project (through its own `add-todo`) for a rendered check of the built app. Done when: the rule's Rendered check part is true of the project today and the filed section resolves.
- [ ] Mirror the rule to `.claude/rules/design-contract.md` wherever that folder exists. Done when: `git diff --no-index` of the two files prints nothing.
- [ ] Cite the contract and its lint in each project's `AGENTS.md` where it does not (three projects name no design lint; one calls a pointer file the contract; two cite a token path that does not exist and disagree with their SPEC). Done when: every design path `AGENTS.md` cites exists or is marked planned in the same line.
- [ ] Commit: `rules: the design contract, always on` in each project.

**Test checkpoint:** in each project, every backticked path in `.agents/rules/design-contract.md` exists (`python` over the file with `os.path.exists`), and the check fails when one cited path is renamed.

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
- [ ] Keep the two projects' own linters and the document checker as they are, and record in each rule of §5 which command is the lint. Done when: each still exits 0 on `HEAD`.
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
- [ ] Diff its `scripts/review-dispatch.py` and `scripts/review-prompt.py` against the kit's and install the kit's four reviewer scripts, keeping local edits the diff shows. Done when: `python3 scripts/review-dispatch.py --check-pin` prints `ok`.
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
- [ ] Add the Surface check to `validate` in each custom `scripts/todo-graph.py`, keeping its own section grammar and receipts folder. Done when: `python scripts/todo-graph.py self-test` passes with a case that refuses `Surface: yes` without a Fidelity. Cheaper substitute: a warning, which a run does not read.
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
- [ ] Mark as not applicable, with the reason, what a project is exempt from by the owner's decisions (Bosun's pin, the three custom graphs' stamp gate, the checkpoints of open surface sections). Done when: no exempt cell reads as a pass.
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

## Verification

- A fresh install carries both safety lenses and `design-plan`, and `python forge.py check-all` is green on CI for the stamped commits.
- The script of §16 is green for every applicable cell, and each exemption names the owner's decision behind it.
- Every finding and every piece of work this file did not build has a section in the project that owns it.
- `python scripts/todo-graph.py validate` and `python scripts/todo-graph.py plan --check` pass.
