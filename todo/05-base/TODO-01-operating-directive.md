---
schema_version: 1
id: operating-directive
domain: 05-base
status: active
title: "TODO-01 -- Operating directive in the base kit"
---

# TODO-01 -- Operating directive in the base kit

> **Goal:** The paragraph the owner pastes into every repository (act autonomously, decide, fix forward, ask only what matters, keep git tidy) is installed once by the base kit as rules an agent can act on, and `init` fills in the project's own goal and acceptance bar.

> **Current state:** Measured 2026-11-11. `kits/base/templates/AGENTS.md` has four sections (Working rules, Safety, Skills, Subagents). Its Safety section says when to ask the operator, but nothing tells an agent to decide and carry on, to fix forward, or how to handle branches and worktrees. Its opening line asks the project to "name what the project is" by hand. `forge.py init` has no `--goal` or `--acceptance` option (`forge.py:731` to `:738`). The todo kit seeds `todo/plan.json` with `"acceptance": null` (`kits/todo/templates/todo/plan.json`), and the generated plan prints the bar when it is set. The owner's machine-level rules, imported byte for byte, are in `global/claude/rules/claude-code.md` (sections 3 "Act, then report", 5 "Proportional process" and 6 "Git") and `global/codex/rules/codex.md`; they apply only on the owner's machine and are not installed by any kit.

## Inputs

- `docs/plans/2026-11-11-sdk-audit-and-roadmap.md`: "The standing directive as kits", the two `base (extend)` rows, and the sentences on `forge.py init --goal` and the acceptance bar.
- `AGENTS.md` (Autonomy and ambition, added 2026-11-11 on the owner's word): the SDK's own statement of the directive, and the wording §1 carries into the base kit's template. **Corrected 2026-11-11:** added; the directive was not yet written down in this repository when the file was authored.
- `global/claude/rules/claude-code.md` sections 3, 5 and 6: the source of the directive's rules. `global/` is imported material and is read, never changed, by this file.
- `kits/base/templates/AGENTS.md` and the three rule files `kits/base/templates/.claude/rules/claude-output-and-safety.md`, `.agents/rules/agy-output-and-safety.md` and `.codex/rules/codex-output-and-safety.md`.
- -> XREF: D03 T01 §1 -- the other keys of `todo/plan.json` are defined there; §4 here writes only `acceptance`

## Outcome

- A fresh `init` writes an `AGENTS.md` whose rules tell an agent when to act without asking, when to ask, and how to leave git, and whose first section states the project's goal when `--goal` was given.
- `init --kit todo --acceptance "<bar>"` writes the bar into `todo/plan.json`, and the generated plan shows it.
- A project that already has an `AGENTS.md` is untouched, and `forge.py diff` shows it what the template now says.

**Adjacency:** all=not-applicable (developer tooling: template text and two `init` options, with no records a user lists, exports, is notified of or reverses)

**Adjacency rationale:** The two settings are `--goal` and `--acceptance`, each written once into a file the project then owns; the refusal tests in §3 and §4 cover what they will not write over.

## Implementation Order

| Order | Section | Deliverable | Depends On | Status |
| ----- | ------- | ----------- | ---------- | ------ |
| 1 | §1 | Operating directive in the base `AGENTS.md` | -- | [ ] |
| 2 | §2 | Git hygiene rules in the base kit | §1 | [ ] |
| 3 | §3 | `forge.py init --goal` | §1, D01 T01 §2 | [ ] |
| 4 | §4 | `forge.py init --acceptance` for the todo kit's plan | §3 | [ ] |

## 1. Operating directive in the base `AGENTS.md`

The directive becomes a section of the base `AGENTS.md`, written as rules with a test an agent can apply, not as ambition.

**Phase:** 7
**Needs:** none
**Surface:** no

**Build order:**

1. Add an "Operating directive" section to `kits/base/templates/AGENTS.md`. Done when: it holds the rules below.
2. Mirror the one-line form in the three rule files and test for it. Done when: the checkpoint passes.

- [ ] Add `## Operating directive` to `kits/base/templates/AGENTS.md` after Working rules, with one rule per line: a task assigned is a task authorised, so do it and then report; never end with a question when the next step is known and unblocked; finish the follow-ups this session can do safely; ask only when proceeding could destroy or expose something or needs business context the repository lacks; fix forward (a risk found later is filed as ordinary work and blocks nothing); build the simplest design that meets the request in full (source: `global/claude/rules/claude-code.md` sections 3 and 5). Done when: each of the six rules is one list item and the section is under 20 lines. Cheaper substitute: pasting the owner's paragraph as prose must fail review; each line must be a rule with an action.
- [ ] Reconcile the new section with the existing Safety section of `kits/base/templates/AGENTS.md` so the two do not contradict: Safety keeps the list of things that need the operator, and the directive points at it for "ask only when". Done when: the words "ask the operator" appear with one meaning in both sections.
- [ ] State the unattended case in the section: an unattended run never asks, takes the industry-standard option, records the decision and what reversing it would cost, and stops only through the run's own pause mechanism. Done when: the item names where the decision is recorded (the run file) in one line.
- [ ] Add one line to each of `kits/base/templates/.claude/rules/claude-output-and-safety.md`, `.agents/rules/agy-output-and-safety.md` and `.codex/rules/codex-output-and-safety.md` pointing at the directive in `AGENTS.md`. Done when: the three files carry the same sentence.
- [ ] Add a test to `tests/test_forge.py`: a fresh `init` has the section in `AGENTS.md` and the pointer in each agent's rule file. Done when: removing the section from the template makes it fail.
- [ ] Run `python forge.py self-sync` and add the same section to the SDK's own `AGENTS.md`, which `self-sync` does not write. Done when: `python -m unittest discover -s tests` passes and the SDK's `AGENTS.md` holds the section.
- [ ] Commit: `base: operating directive in AGENTS.md`

**Test checkpoint:** `python -m unittest discover -s tests -p test_forge.py` ends `OK`; deleting the section from `kits/base/templates/AGENTS.md` makes the new test fail.

## 2. Git hygiene rules in the base kit

The second `base` row: work on main, and clean up branches and worktrees when work is finished. Source: `global/claude/rules/claude-code.md` section 6.

**Phase:** 7
**Needs:** none
**Surface:** no

**Build order:**

1. Add a "Git" section to `kits/base/templates/AGENTS.md`. Done when: it holds the rules below.
2. Test for it. Done when: the checkpoint passes.

- [ ] Add `## Git` to `kits/base/templates/AGENTS.md` with one rule per line: develop on the main branch unless the operator asks for a branch in that task; read `git status --short` before staging and never write over another session's uncommitted changes; never discard changes with `reset`, `checkout`, `restore` or `clean` unless asked for that exact cleanup; after a commit, confirm it landed; remove worktrees you created, delete branches whose content is on main, and prune dead worktree records; never delete an unmerged branch without asking. Done when: each rule is one list item. Cheaper substitute: a link to the owner's machine-level rules must fail, because a project does not have them.
- [ ] Keep the rule a project can change: say in the section's first line that a project with a branch workflow replaces the first rule with its own. Done when: the line is there.
- [ ] Add the section to the test from §1 in `tests/test_forge.py`. Done when: removing the section from the template makes it fail.
- [ ] Run `python forge.py self-sync`. Done when: `python -m unittest discover -s tests` passes.
- [ ] Commit: `base: git hygiene rules in AGENTS.md`

**Test checkpoint:** `python -m unittest discover -s tests -p test_forge.py` ends `OK`; deleting the Git section from the template makes the test fail.

## 3. `forge.py init --goal`

The base `AGENTS.md` asks the project to name what it is. `init --goal "<text>"` writes that into the file it creates, so the directive has something to aim at from the first session.

**Phase:** 7
**Needs:** none
**Surface:** no

**Build order:**

1. Add a goal placeholder to `kits/base/templates/AGENTS.md` and `--goal` to `init` in `forge.py`. Done when: a fresh `init --goal` writes the goal.
2. Cover the cases where it must not write. Done when: the checkpoint passes.

- [ ] Add `## Goal` as the first section of `kits/base/templates/AGENTS.md` holding one placeholder line, and remove the "Adapt this file" sentence it replaces. Done when: a fresh `init` with no `--goal` writes the placeholder line unchanged.
- [ ] Add `--goal <text>` to the `init` parser and a `goal` argument to `provision` in `forge.py`: replace the placeholder with the text in the `AGENTS.md` this run created. Done when: a test with `--goal "Ship the importer"` finds that sentence under `## Goal` and no placeholder. Cheaper substitute: appending the goal to the end of the file must fail the under-the-heading assertion.
- [ ] Refuse a goal that is empty, longer than 600 characters, or contains a line break, an em dash or an en dash in `provision`, before any file is written. Done when: tests for each find exit 2 and an empty target.
- [ ] Leave an existing `AGENTS.md` alone in `provision`: when `init --goal` runs on a project that already has the file (and `--force` is not given), nothing is written to it and the result says the goal was not applied and why. Done when: a test finds the file byte for byte unchanged and `goal_applied` false in the output.
- [ ] Record the kit's digest, not the filled file's, for `AGENTS.md` in the install record (D01 T01 §2 records entry docs that way), so a filled goal reads as the project's change. Done when: a test finds `AGENTS.md` reported `project-changed` by `forge.diff_project` after `init --goal`, and `identical` after `init` with no goal.
- [ ] Document `--goal` in `README.md` (New Project) with one example. Done when: `python forge.py init --help` and the README both name it.
- [ ] Commit: `forge: init --goal writes the project's goal into AGENTS.md`

**Test checkpoint:** `python -m unittest discover -s tests -p test_forge.py` ends `OK`; writing the goal into an existing `AGENTS.md` makes the unchanged-file test fail.

## 4. `forge.py init --acceptance` for the todo kit's plan

The ambition ("finish 100 percent") belongs where the runner reads it: the acceptance bar in `todo/plan.json`. `init --acceptance "<bar>"` writes it when the todo kit is chosen.

**Phase:** 7
**Needs:** none
**Surface:** no

**Build order:**

1. Add `--acceptance` to `init` in `forge.py`. Done when: a fresh install's `todo/plan.json` holds the bar.
2. Cover the refusals. Done when: the checkpoint passes.

- [ ] Add `--acceptance <text>` to the `init` parser and an `acceptance` argument to `provision` in `forge.py`: set the `acceptance` key of the `todo/plan.json` this run created, written with `atomic_write` as JSON with the template's indentation. Done when: a test with `--kit todo --acceptance "Every screen in the SPEC works"` reads the key back and finds `title` and `phases` unchanged. Cheaper substitute: text substitution on the JSON file must fail the test whose bar contains a double quote.
- [ ] Refuse `--acceptance` without the todo kit in `provision`, before any file is written, naming `--kit todo`. Done when: a test finds exit 2 and an empty target.
- [ ] Leave an existing `todo/plan.json` alone in `provision`, saying in the result that the bar was not applied. Done when: a test finds the file byte for byte unchanged.
- [ ] Prove the generated plan shows the bar: after the install, `python scripts/todo-graph.py plan --sync` writes a `todo/implementation-plan.md` whose acceptance line holds the text. Done when: a test on the fresh install finds it.
- [ ] Document `--acceptance` in `README.md` and in `kits/todo/README.md`. Done when: both name it with one example.
- [ ] Commit: `forge: init --acceptance sets the plan's acceptance bar`

**Test checkpoint:** `python -m unittest discover -s tests -p test_forge.py` ends `OK`; accepting `--acceptance` without the todo kit makes its refusal test fail.

## Verification

- `python forge.py init <scratch> --kit todo --goal "<goal>" --acceptance "<bar>"` writes an `AGENTS.md` with the goal, the operating directive and the git rules, and a plan that shows the bar.
- The same command on a project that already has both files changes neither.
- `python -m unittest discover -s tests` passes.
- `python scripts/todo-graph.py validate` and `python scripts/todo-graph.py plan --check` pass.
