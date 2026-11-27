---
schema_version: 1
id: gemini-neon-writer
domain: 00-reviewer
status: active
title: "TODO-04 -- Gemini 4 Neon replaces Orchestrator (Carbon)"
---

# TODO-04 -- Gemini 4 Neon replaces Orchestrator (Carbon)

> **Goal:** Antigravity's writer in the SDK and in every kit it installs is Gemini 4 Neon (`gemini-4-neon-medium`, effort passed explicitly), replacing Orchestrator (Carbon) (`gemini-pro-orchestrator`) by the owner's decision of 2026-11-21. No kit rule, skill, pin check, unattended profile or document still steers an agent through Carbon planning and Hydrogen execution handoffs, and a project that still names an Orchestrator model keeps working.

> **Current state:** Measured 2026-11-21. The SDK's own launcher already starts Neon: `scripts/start-run.ps1` defaults the `agy` runner to `gemini-4-neon-medium` with `--effort=<effort>`, still starting an Orchestrator model without `--effort` when one is named, and `tests/test_start_run.py` covers both. Everything else still assumes Carbon: in `kits/base`, the `README.md` (its "Migrating existing installs to Orchestrator (Carbon)" section), `templates/AGENTS.md`, `templates/GEMINI.md`, `templates/CODEX.md`, `templates/.agents/rules/agy-output-and-safety.md`, `templates/docs/agent-skills-and-rules-structure.md` and five `templates/.claude/agents/*.md`; in `kits/todo`, the Antigravity copies of `process-plan`, `process-phase` and `process-todo-section` and their `skill-patches/agents/*.json`; in `kits/reviewer`, `README.md` and `templates/scripts/review_pin.py` (its refusal of an effort on an Orchestrator writer), with fixtures under `tests/fixtures/check-pin/pins/`; in `kits/unattended`, `README.md`, `templates/docs/unattended-run.md`, `templates/scripts/lib/unattended.py` and `templates/scripts/unattended-run.py` (an effort-free Orchestrator profile). The SDK's installed copies, `README.md`, `docs/agent-skills-and-rules-structure.md` and `assets/brand/README.md` follow the kits.

## Inputs

- The owner's decision of 2026-11-21: Gemini 4 Neon replaces Orchestrator (Carbon) as the Antigravity writer. Bosun made the same switch in its launcher on 2026-11-19 (`gemini-4-neon-medium`, `--effort` passed).
- `AGENTS.md` (kits as the only source, `python forge.py self-sync`, `python forge.py skill-copies`, the test cadence).
- -> XREF: D00 T02 §3 -- that section brought in Orchestrator (Carbon) as the Antigravity writer; this file replaces it with Gemini 4 Neon

## Outcome

- `git grep -nE "Carbon|Hydrogen|exit_plan_mode|gemini-pro-orchestrator" -- kits` prints only the compatibility notes that say an Orchestrator model is still accepted.
- The reviewer pin accepts `agy` with an effort under Neon, and still accepts an Orchestrator pin without one.
- An unattended profile on Neon carries its effort; an Orchestrator profile with `"effort": null` still loads.
- The SDK's installed copies match the kits, and CI is green.

**Adjacency:** all=not-applicable (agent and kit configuration: no product records or user data)

**Adjacency rationale:** This is a writer-model change in kit guidance and checks. The reverse path is the compatibility kept in each section: a project that names an Orchestrator model keeps working, so going back is a default and a text change.

## Implementation Order

| Order | Section | Deliverable | Depends On | Status |
| ----- | ------- | ----------- | ---------- | ------ |
| 1 | §1 | Base kit guidance names Gemini 4 Neon | -- | [x] |
| 2 | §2 | Antigravity TODO skills without Carbon handoffs | §1 | [x] |
| 3 | §3 | Reviewer pin accepts Neon with an effort | -- | [x] |
| 4 | §4 | Unattended profile runs Neon with its effort | -- | [x] |
| 5 | §5 | SDK copies, documents and tests follow the kits | §1, §2, §3, §4 | [ ] |

## 1. Base kit guidance names Gemini 4 Neon

> **Started:** 2026-11-26T06:22Z

The base kit tells every agent how Antigravity works. Today it describes Orchestrator's Carbon planning and Hydrogen execution and forbids `--effort`; under Neon, Antigravity is one model at an explicit effort, so that text is wrong for every project that installs the kit.

**Corrected 2026-11-26 (validation):** Verified all five `kits/base/templates/.claude/agents/*.md` files (`code-explorer.md`, `debug-evidence.md`, `git-runner.md`, `mutation-tester.md`, `test-runner.md`): none mentions Antigravity, Carbon, Hydrogen, or Gemini (each only says generic lowercase `so the orchestrator can request exactly that` for the parent Claude session), so item 4 confirms no Carbon/Antigravity drift and runs `node scripts/verify-agent-tiers.mjs`. Because `tests/test_forge.py` enforces `self-sync` parity between `kits/base/templates/` and the SDK's installed `.agents/` and `docs/agent-skills-and-rules-structure.md` (plus `tests/test_forge.py:1096` asserts `exit_plan_mode` in `.agents/rules/agy-output-and-safety.md` and `tests/test_agy_agents.py:1126` asserts the old README heading), §1 also runs `python forge.py self-sync` for the touched base-kit files and updates those two coupled assertions so `main` and CI stay green before §2-§5 land.

**Phase:** 10
**Needs:** none
**Surface:** no

**Build order:**

1. Rewrite the Antigravity guidance in the base kit's templates (`AGENTS.md`, `GEMINI.md`, `CODEX.md`, `.agents/rules/agy-output-and-safety.md`, `docs/agent-skills-and-rules-structure.md`). Done when: `git grep -nE "Carbon|Hydrogen|exit_plan_mode" -- kits/base/templates` prints nothing and each file positively names Gemini 4 Neon (`gemini-4-neon-medium`) with explicit `--effort` (or single-session plan-and-build workflow for the rule).
2. Update both "Subagents across the three writers" (active launch command `agy --model gemini-4-neon-medium --effort=medium`) and the migration section ("Moving Antigravity to Gemini 4 Neon") in `kits/base/README.md`, labeling the 2026-11-14 live proof as historical Orchestrator evidence, run `python forge.py self-sync`, and update the coupled tests (`tests/test_kit_install.py`, `tests/test_agy_agents.py:1124-1150`, `tests/test_forge.py:1095-1102`). Done when: `python -m unittest tests.test_kit_install tests.test_agy_agents` and `python -m unittest tests.test_forge -k micro_todo_and_complete_plan -k the_sdk_uses_the_agent_setup -k markdown_table` pass. **Corrected 2026-11-26 (plan review):** added active README launch paragraph, exact `-k` test selectors, positive fresh-install/rule assertions, and dropped redundant Claude-agent checklist item.

- [x] Rewrite the Antigravity lines in `kits/base/templates/AGENTS.md`, `GEMINI.md` and `CODEX.md` to say Antigravity runs `gemini-4-neon-medium` at an explicit `--effort`, with built-in subagents as before. Done when: none names Carbon or Hydrogen and each positively names `gemini-4-neon-medium` and explicit `--effort`. Cheaper substitute: appending a Neon note beside the Carbon text.
- [x] Rewrite `kits/base/templates/.agents/rules/agy-output-and-safety.md` so the same writer plans and builds one TODO section in one session without `exit_plan_mode` handoffs, checks the section's `stamp` and `ci_status.py` before taking the next ready row (whether `Surface` is `yes` or `no`), and revisits the plan when a needed design token or shared `Chrome:` control is missing, when the pinned reviewer returns `COMPLETION: gaps` or a `P1`/`P2` architectural or design-contract finding, or after two failed attempts on the same fix. Done when: the rule names no handoff, preserves the single-writer workflow and replan triggers, and keeps all other safety lines unchanged. **Corrected 2026-11-26 (plan review):** preserved section workflow and replan triggers.
- [x] Rewrite the Antigravity entry in `kits/base/templates/docs/agent-skills-and-rules-structure.md`. Done when: it names `gemini-4-neon-medium`, explicit `--effort`, and built-in subagents without Carbon/Hydrogen/`exit_plan_mode`.
- [x] Update `kits/base/README.md`: (a) rewrite "Subagents across the three writers" (`:68-72`) so active Antigravity guidance uses `agy --model gemini-4-neon-medium --effort=medium` with built-in subagents (`self`, `research`, `image-generator`); (b) replace "Migrating existing installs to Orchestrator (Carbon)" (`:74-91`) with "Moving Antigravity to Gemini 4 Neon" covering launch flags, explicit effort, reversible cleanup of retired `.agents/agents/` wrappers, and compatibility note that `gemini-pro-orchestrator` still runs without `--effort`; (c) label the 2026-11-14 live verification block (`:93-99`) clearly as historical Orchestrator (`agy` 1.5.8) evidence. Done when: active launch guidance shows `agy --model gemini-4-neon-medium --effort=medium` in its own section and Orchestrator appears only in compatibility and historical-evidence notes. **Corrected 2026-11-26 (plan review):** added active launch paragraph and historical-evidence labeling; removed duplicate Claude-agent tier-check item.
- [x] Run `python forge.py self-sync` and update the coupled tests: (a) extend a fresh-install test in `tests/test_kit_install.py` to read back `AGENTS.md`, `GEMINI.md`, `CODEX.md`, and `docs/agent-skills-and-rules-structure.md` and assert `gemini-4-neon-medium` and `--effort` (with no Carbon/Hydrogen/`exit_plan_mode`); (b) update `tests/test_agy_agents.py:1124-1150` to verify the active Neon launch command inside its own section and the new migration heading while keeping cleanup/wrapper/structure assertions; (c) update `tests/test_forge.py:1096` to assert the positive single-writer Neon workflow in `.agents/rules/agy-output-and-safety.md` (keeping lines 1100-1101 for TODO skills until §2). Done when: `python -m unittest tests.test_kit_install tests.test_agy_agents` and `python -m unittest tests.test_forge -k micro_todo_and_complete_plan -k the_sdk_uses_the_agent_setup -k markdown_table` pass. **Corrected 2026-11-26 (plan review):** exact `-k` selectors and positive Neon assertions.
- [x] Commit: `base: Antigravity guidance names Gemini 4 Neon at an explicit effort (D00 T04 §1)`

**Test checkpoint:** `git grep -nE "Carbon|Hydrogen|exit_plan_mode" -- kits/base/templates` prints nothing, and `python -m unittest tests.test_kit_install` ends `OK`.

> **Verified:** 2026-11-26 | §1 | 1e9d7f161c88bf19d33cde39a299a06883997aa3
> **Review:** `docs/reviews/d00-t04-s1.json`

## 2. Antigravity TODO skills without Carbon handoffs

> **Started:** 2026-11-26T23:32Z

The todo kit's Antigravity copies of `process-plan`, `process-phase` and `process-todo-section` tell the writer to plan on Carbon and hand to Hydrogen after each section. Under Neon the writer follows the same steps as the Claude source.

**Corrected 2026-11-26 (validation):** `tests/test_agy_agents.py` has no existing TODO-skill handoff assertions, and the `tests/test_forge.py` TODO-skill assertions are at lines `1101-1104` (shifted from `1100-1101` in §1). Item 3 therefore adds a dedicated test in `tests/test_agy_agents.py` covering both `kits/todo/skill-patches/agents/process-*/SKILL.md.json` and the generated `kits/todo/templates/.agents/skills/process-*/SKILL.md` (so restoring a Carbon handoff line in `process-plan/SKILL.md.json` fails `tests.test_agy_agents`) and updates `tests/test_forge.py:1101-1104` to assert their absence. Because `tests/test_forge.py` enforces `self-sync` parity between `kits/todo/templates/` and the SDK's installed `.agents/`, `.claude/`, and `.codex/` skills, §2 also runs `python forge.py self-sync` after `python forge.py skill-copies` so `main` and CI stay green before §5 lands.

**Phase:** 10
**Needs:** none
**Surface:** no

**Build order:**

1. Add the failing assertions in `tests/test_agy_agents.py` and `tests/test_forge.py:1101-1104` covering patch absence, positive Claude-source working passages (`--writer agy`, audit-to-phase transition, next-row instruction, validate-before-build), and the Step 4 `Commit:` exception across all three agents. Done when: the new assertions fail before the edits.
2. Delete the three handoff-only patch entries in `kits/todo/skill-patches/agents/{process-plan,process-phase,process-todo-section}/SKILL.md.json` and add the `Commit:` exception in Step 4 of `kits/todo/templates/.claude/skills/process-todo-section/SKILL.md`, then run `python forge.py skill-copies` once and `python forge.py self-sync` once. Done when: `python forge.py skill-copies --check` exits 0, `python -m unittest tests.test_agy_agents` and `python -m unittest tests.test_forge -k micro_todo_and_complete_plan -k the_sdk_uses_the_agent_setup -k markdown_table` pass. **Corrected 2026-11-26 (plan review):** ordered test-first, single `skill-copies`/`self-sync` pass, explicit patch-entry deletion, Step 4 placement for `Commit:` exception, and positive working-passage assertions.

- [x] Add failing tests: (a) in `tests/test_agy_agents.py`, assert that `kits/todo/skill-patches/agents/{process-plan,process-phase,process-todo-section}/SKILL.md.json` and `kits/todo/templates/.agents/skills/{process-plan,process-phase,process-todo-section}/SKILL.md` contain no `Carbon`, `Hydrogen`, `exit_plan_mode`, or `enter_plan_mode` (so restoring a handoff line in `process-plan/SKILL.md.json` fails `tests.test_agy_agents`); (b) in `tests/test_forge.py:1101-1104`, assert the absence of those four terms on installed `.agents/skills/{process-plan,process-phase,process-todo-section}/SKILL.md`, positively assert the working passages (audit-to-phase transition in `process-plan`, next-row instruction in `process-phase`, validate-before-build and `--writer agy` in `process-todo-section`), and positively assert the Step 4 `Commit:` exception across installed `.claude`, `.agents`, and `.codex` copies of `process-todo-section/SKILL.md`. Done when: both tests fail before the source edits and pass after. **Corrected 2026-11-26 (plan review):** test-first order, positive working-passage and `Commit:`-exception assertions, and clear separation of patch-only vs regenerated-install mutation detection.
- [x] Delete the handoff-only replace entries from `kits/todo/skill-patches/agents/process-plan/SKILL.md.json`, `process-phase/SKILL.md.json` and `process-todo-section/SKILL.md.json` (not empty replacements), keeping every other declared difference so the Claude source supplies the working passages. Done when: each patch still applies cleanly and none contains Carbon, Hydrogen, `exit_plan_mode`, or `enter_plan_mode`. Cheaper substitute: editing the generated copies by hand or replacing with empty strings. **Corrected 2026-11-26 (plan review):** delete entries rather than emptying them.
- [x] Clarify in Step 4 of `kits/todo/templates/.claude/skills/process-todo-section/SKILL.md` (filed non-blocking P3 from `D00 T03 §2` Completion review) that a section's `Commit:` checklist item stays `[ ]` until `todo-graph.py stamp` ticks it with the Implementation Order row. Done when: the exception sits in Step 4 beside the ticking instruction without conflicting with Step 7. **Corrected 2026-11-26 (plan review):** placed in Step 4.
- [x] Run `python forge.py skill-copies` once and `python forge.py self-sync` once, then run `python forge.py skill-copies --check`, `python -m unittest tests.test_agy_agents`, and `python -m unittest tests.test_forge -k micro_todo_and_complete_plan -k the_sdk_uses_the_agent_setup -k markdown_table`. Done when: `skill-copies --check` exits 0 and all named tests pass. **Corrected 2026-11-26 (plan review):** single generation and self-sync pass after both source edits.
- [x] Commit: `todo: Antigravity skills follow the Claude steps under Gemini 4 Neon (D00 T04 §2)`

**Test checkpoint:** `python -m unittest tests.test_agy_agents` ends `OK`, and fails when a Carbon handoff line is restored in `kits/todo/skill-patches/agents/process-plan/SKILL.md.json`.

> **Verified:** 2026-11-27 | §2 | eb30b67f374667ed94cf311f900349d0612d0c97
> **Review:** `docs/reviews/d00-t04-s2.json`

## 3. Reviewer pin accepts Neon with an effort

> **Started:** 2026-11-27T00:16Z

`review_pin.py` refuses an effort on an Orchestrator writer because Orchestrator rejects `--effort`. Neon takes an effort like the other writers, so the check keys on the model, not on `agy`.

**Corrected 2026-11-27 (validation):** In `kits/reviewer/templates/scripts/review_pin.py`, `check_agy_effort` (`:487`) already keys scheduled-effort refusal on `is_agy_orchestrator(model)`, whereas `check_reviewer_effort` (`:146-155`) still refuses `effort` on every `cli == "agy"` reviewer and `EFFORTS` (`:64`) omits `"agy"` (`agy --help` accepts `low|medium|high|xhigh|max`). Updating `check_reviewer_effort` to refuse `effort` only when `is_agy_orchestrator(model)` also affects `tests/fixtures/check-pin/pins/refused-agy-effort.toml` (which previously used `gemini-4-argon-high` to test the blanket `cli == "agy"` refusal) and `kits/reviewer/templates/scripts/tests/test_review_dispatch.py:459-460`, so both are updated to test the Orchestrator reviewer-level `effort` refusal. Because `tests/test_check_pin_contract.py` runs `tests/fixtures/check-pin/pins/` and `tests/test_forge.py` enforces `self-sync` parity (and `scripts.tests.test_review_pin` imports the synced `scripts/review_pin.py`), §3 runs `python forge.py self-sync` and verifies `scripts.tests.test_review_pin`, `scripts.tests.test_review_dispatch`, and `tests.test_check_pin_contract`.

**Phase:** 10
**Needs:** none
**Surface:** no

**Build order:**

1. Add `"agy": ("low", "medium", "high", "xhigh", "max")` to `EFFORTS`, update `check_reviewer_effort` (plus its `faults()` guard), `check_agy_effort`, and the module docstring in `kits/reviewer/templates/scripts/review_pin.py` so Orchestrator models (`gemini-pro-orchestrator` and `gemini-pro-orchestrator-*`) reject `effort` on both reviewer entries and schedule steps while non-Orchestrator Antigravity models (including Neon) accept explicit reviewer-level and mixed-effort scheduled passes. Done when: a Neon pin with reviewer-level `effort` and mixed-effort schedule steps validates, invalid efforts and Orchestrator efforts are refused, and `scripts.tests.test_review_pin` passes.
2. Update `kits/reviewer/templates/scripts/review-dispatch.py` (`command()`, `dispatch()`, `AGY_EFFORT_FLAG`, `agy_flags_missing(help_text, *, need_effort=False)`) and `forge.py` (`_doctor_reviewer` / `_agy_flags_check`) so non-Orchestrator `agy` invocations pass `--effort=<effort>` when an effort is active, record that effort in the result, omit `--effort` when no effort is active (including a scheduled step with no effort overriding a reviewer default) or for Orchestrator, and `forge.py doctor` requires `--effort` in `agy --help` when the pin uses explicit `agy` effort while keeping effort-free pins compatible. Done when: fake-CLI dispatch tests and doctor flag tests pass.
3. Add `tests/fixtures/check-pin/pins/valid-agy-neon-effort.toml`, update `tests/fixtures/check-pin/pins/refused-agy-effort.toml` and `expected.json` (keeping both `refused-agy-orchestrator-*` fixtures), update `kits/reviewer/README.md` (naming Neon and removing contradictory effort/Orchestrator text at lines 61 and 75), and run `python forge.py self-sync`. Done when: `python -m unittest scripts.tests.test_review_pin scripts.tests.test_review_dispatch scripts.tests.test_three_pass tests.test_check_pin_contract tests.test_reviewer_flags` and `python -m unittest tests.test_forge -k the_sdk_uses_the_agent_setup -k markdown_table` pass. **Corrected 2026-11-27 (plan review):** extended through dispatch, record read-back, mixed-effort schedules, doctor `--effort` capability check, and README consistency.

- [x] Add `"agy": ("low", "medium", "high", "xhigh", "max")` to `EFFORTS`, update `check_reviewer_effort` (plus its `faults()` guard), `check_agy_effort`, and the module docstring (`:41-46`) in `kits/reviewer/templates/scripts/review_pin.py` so `effort` on `cli == "agy"` is refused only when `is_agy_orchestrator(model)` (or outside `EFFORTS["agy"]`), allowing Neon pins with reviewer-level `effort` and mixed-effort three-pass or rotation schedules. Done when: `review_pin.py` accepts a Neon pin with `effort = "medium"` and mixed-effort schedule (`medium` plan, `low` completion), refuses invalid efforts, and refuses `effort` on `gemini-pro-orchestrator` and `gemini-pro-orchestrator-*` in both `load_pin` and `faults`. Cheaper substitute: dropping the check, which lets an Orchestrator pin fail at launch. **Corrected 2026-11-27 (plan review):** removed model-suffix coupling in `check_agy_effort` for non-Orchestrator models and updated module docstring.
- [x] Update `kits/reviewer/templates/scripts/review-dispatch.py` (`command()`, `dispatch()`, `AGY_EFFORT_FLAG = "--effort"`, `agy_flags_missing(help_text, *, need_effort=False)`) and `forge.py` (`_agy_flags_check` / `_doctor_reviewer`) so non-Orchestrator `agy` passes `--effort=<effort>` and records that effort (including when effort differs from the model name suffix, e.g. `gemini-4-neon-medium` with `effort = "high"`), sends no `--effort` when omitted (including a step with no effort overriding a reviewer default) or for Orchestrator, and `forge.py doctor` requires `--effort` in `agy --help` only when the pin configures explicit `agy` effort. Done when: fake-CLI tests in `test_review_dispatch.py` / `test_three_pass.py` prove `--effort=high` reaches `agy` and is recorded, omitted effort and Orchestrator send no `--effort`, and `tests/test_reviewer_flags.py` proves missing `--effort` fails doctor on an explicit-effort pin while an effort-free pin still passes. **Corrected 2026-11-27 (plan review):** folded P1 dispatch/record gap and P2 doctor `--effort` capability check.
- [x] Add `tests/fixtures/check-pin/pins/valid-agy-neon-effort.toml` (Neon with reviewer-level `effort` and mixed-effort three-pass schedule), update `tests/fixtures/check-pin/pins/refused-agy-effort.toml` to use `gemini-pro-orchestrator`, update `tests/fixtures/check-pin/pins/expected.json` (keeping both `refused-agy-orchestrator-*` fixtures), add unit tests in `kits/reviewer/templates/scripts/tests/test_review_pin.py`, and run `python forge.py self-sync`. Done when: `python -m unittest scripts.tests.test_review_pin scripts.tests.test_review_dispatch scripts.tests.test_three_pass tests.test_check_pin_contract tests.test_reviewer_flags` and `python -m unittest tests.test_forge -k the_sdk_uses_the_agent_setup -k markdown_table` pass. **Corrected 2026-11-27 (plan review):** removed redundant expected.json flip mutation in favor of the dispatch `--effort` regression.
- [x] Update `kits/reviewer/README.md` to name Gemini 4 Neon as the Antigravity writer (replacing `Carbon` writer shortcut references) and rewrite the effort rules (`:61`, `:75`) to accurately state reviewer-level `effort`, scheduled override and omission, mixed-effort schedules on Neon, and Orchestrator refusal on both three-pass and rotation. Done when: it names no Carbon handoff or Carbon writer shortcut and has no contradictory effort or Orchestrator rule. **Corrected 2026-11-27 (plan review):** added explicit requirement to fix contradictory `:61` and `:75` guidance.
- [x] Commit: `reviewer: the pin accepts Gemini 4 Neon with an effort (D00 T04 §3)`

**Test checkpoint:** `python -m unittest scripts.tests.test_review_pin scripts.tests.test_review_dispatch scripts.tests.test_three_pass tests.test_check_pin_contract tests.test_reviewer_flags` ends `OK`, and fails when `--effort=<effort>` is removed from the `agy` command in `kits/reviewer/templates/scripts/review-dispatch.py`. **Corrected 2026-11-27 (plan review):** checkpoint verifies real dispatch `--effort` delivery rather than flipping `expected.json`.

> **Verified:** 2026-11-27 | §3 | ba6f265ef247cc72a4f4a5423b58e43a5e0648c6
> **Review:** `docs/reviews/d00-t04-s3.json`

## 4. Unattended profile runs Neon with its effort

> **Started:** 2026-11-27T01:16Z

The unattended kit allows `"effort": null` for an Orchestrator profile and documents Carbon. A Neon profile carries an effort, and the run passes it.

**Corrected 2026-11-27 (validation):** Verified `kits/unattended/templates/scripts/lib/unattended.py` and `kits/unattended/templates/scripts/unattended-run.py`: the profile template (`.conclave/unattended.json`) intentionally leaves `name`, `model`, and `effort` as `null` with no hardcoded model defaults; `load_profile()` (`lib/unattended.py:72-84,102-119`) already requires a valid `effort` (`low|medium|high|xhigh|max`) for every non-Orchestrator `agy` model (refusing `"effort": null`) while accepting `"effort": null` only for `is_agy_orchestrator(model)`, and `unattended-run.py:230-240` already passes `["agy", f"--model={model}", f"--effort={effort}"]` for non-Orchestrator `agy` models and omits `--effort` for Orchestrator. What still names Carbon is `kits/unattended/templates/docs/unattended-run.md:10`, `kits/unattended/README.md` (which does not yet name `gemini-4-neon-medium`), and the test fixtures in `kits/unattended/templates/scripts/tests/{test_unattended.py,test_run.py,test_shortcut.py}`. Items 1 and 2 therefore verify the existing loader/launcher behavior against `gemini-4-neon-medium` (updating those test fixtures from `gemini-4-carbon-medium` to `gemini-4-neon-medium` and adding a positive Neon `--effort=medium` launch/resume assertion and `effort: null` refusal), without churning working loader/launcher code.

**Phase:** 10
**Needs:** none
**Surface:** no

**Build order:**

1. Update `kits/unattended/templates/scripts/tests/test_unattended.py`, `test_run.py`, and `test_shortcut.py` from `gemini-4-carbon-medium` to `gemini-4-neon-medium`, verifying `load_profile()` accepts Neon with explicit effort, refuses `"effort": null` on Neon in both top-level and `runners.agy` forms, and accepts `"effort": null` only on Orchestrator, and adding a portable fresh-start and `--conversation` resume test in `test_run.py` for `gemini-4-neon-medium` with `effort = "high"` (differing from the model suffix) asserting `--effort=high` on both. Done when: the focused loader and portable launcher tests pass on Windows.
2. Update `kits/unattended/README.md` and `kits/unattended/templates/docs/unattended-run.md` so each positively documents `gemini-4-neon-medium` with explicit effort and `gemini-pro-orchestrator` with `"effort": null`, then run `git grep -n -i "carbon\|hydrogen" -- kits/unattended/`, `python forge.py check-all --only kit-unattended` (once), `python -m unittest tests.test_forge -k markdown_table`, and the focused portable `--effort` drop mutation check. Done when: grep prints nothing, both docs pass positive read-back, the Windows suite passes, and the mutation fails on the portable Neon test (with CI covering `tests/test_unattended_installed.py` and shortcut shards at stamp). **Corrected 2026-11-27 (plan review):** added suffix-divergent `effort = "high"` portable fresh-start/resume test as Windows mutation witness, separated Step 1 focused tests from Step 2 kit-wide grep, required positive doc read-back, and cited installed-kit CI coverage.

- [x] Verify `kits/unattended/templates/scripts/lib/unattended.py` accepts `gemini-4-neon-medium` with explicit effort, refuses `"effort": null` on `gemini-4-neon-medium` in both top-level `agent: "agy"` and `runners.agy` forms, and keeps `"effort": null` accepted only for `is_agy_orchestrator(model)` (`gemini-pro-orchestrator`, `gemini-pro-orchestrator-*`), updating `kits/unattended/templates/scripts/tests/test_unattended.py` fixtures from `gemini-4-carbon-medium` to `gemini-4-neon-medium`. Done when: `test_unattended.py` passes covering top-level and `runners.agy` Neon and Orchestrator cases. Cheaper substitute: accepting `null` for every model. **Corrected 2026-11-27 (plan review):** explicitly required both top-level and `runners.agy` null-effort refusal assertions.
- [x] Verify `kits/unattended/templates/scripts/unattended-run.py` passes `--model=gemini-4-neon-medium --effort=<effort>` for Neon (and omits `--effort` for Orchestrator): update `kits/unattended/templates/scripts/tests/test_run.py` and `test_shortcut.py` fixtures from `gemini-4-carbon-medium` to `gemini-4-neon-medium` (renaming `carbon` at `test_shortcut.py:1951`), and add a portable fresh-start and `--conversation` resume case in `test_run.py` with `model = "gemini-4-neon-medium"` and `effort = "high"` asserting `--effort=high` on both. Done when: the portable Neon test passes on Windows and fails when `--effort={effort}` is dropped from `unattended-run.py:240`. **Corrected 2026-11-27 (plan review):** added suffix-divergent `effort = "high"` portable fresh-start/resume witness so Windows mutation exercises Neon directly.
- [x] Rewrite the Antigravity parts of `kits/unattended/README.md` and `kits/unattended/templates/docs/unattended-run.md` to name Gemini 4 Neon (`gemini-4-neon-medium`, `"effort": "medium"`) as the Antigravity writer while keeping the Orchestrator (`gemini-pro-orchestrator`, `"effort": null`) compatibility note. Done when: positive read-back of both files confirms both the Neon explicit-effort example and the Orchestrator `"effort": null` rule, and `git grep -n -i "carbon\|hydrogen" -- kits/unattended/` prints nothing. **Corrected 2026-11-27 (plan review):** added positive read-back requirement for both documents.
- [x] Run `python forge.py check-all --only kit-unattended` once on Windows, run the focused portable Neon `--effort` drop mutation check, and run `python -m unittest tests.test_forge -k markdown_table` (citing CI green for `tests/test_unattended_installed.py` and shortcut shards at stamp). Done when: the suite and format check pass and the mutation fails. **Corrected 2026-11-27 (plan review):** one Windows kit run, focused mutation witness, and installed-kit CI evidence.
- [x] Commit: `unattended: Antigravity profiles run Gemini 4 Neon with their effort (D00 T04 §4)`

**Test checkpoint:** `python forge.py check-all --only kit-unattended` passes on Windows, and the portable Neon fresh-start/resume test in `kits/unattended/templates/scripts/tests/test_run.py` fails when `--effort={effort}` is dropped from `kits/unattended/templates/scripts/unattended-run.py`. **Corrected 2026-11-27 (plan review):** named the portable Neon test as the Windows mutation witness.

> **Verified:** 2026-11-27 | §4 | 28c2eae4950db4b41c92dff1f8ab771e8ccbdff7
> **Review:** `docs/reviews/d00-t04-s4.json`

## 5. SDK copies, documents and tests follow the kits

The SDK runs its own installed copy of the base, todo and reviewer kits, so the change reaches its own agents only after `self-sync`, and its own documents still describe Carbon.

**Phase:** 10
**Needs:** none
**Surface:** no

**Build order:**

1. Refresh the installed copy and the SDK's documents. Done when: `python forge.py self-sync` reports no difference and `git grep -nE "Carbon|Hydrogen|gemini-pro-orchestrator" -- README.md docs/agent-skills-and-rules-structure.md assets/brand/README.md .agents scripts` prints only compatibility notes.

- [ ] Run `python forge.py self-sync`. Done when: the self-sync test passes.
- [ ] Update `README.md`, `docs/agent-skills-and-rules-structure.md` and `assets/brand/README.md` (the runner badge is Gemini's, not Carbon's) to name Neon. Done when: none names Carbon outside a compatibility note.
- [ ] Update `tests/test_forge.py`, `tests/test_kit_install.py`, `tests/test_reviewer_flags.py` and `tests/fixtures/agy-stop-payload.json` where they assert Carbon text or the Orchestrator default. Done when: each passes and still fails if the default reverts.
- [ ] Leave stamped sections, `docs/reviews/` and `docs/phase-runs/` as written. Done when: the decision is noted under this section.
- [ ] Commit: `sdk: own copies, documents and tests follow Gemini 4 Neon (D00 T04 §5)`

**Test checkpoint:** `python -m unittest tests.test_forge` ends `OK`, and CI is green on the commit.

## Verification

- `git grep -nE "Carbon|Hydrogen|exit_plan_mode|gemini-pro-orchestrator" -- kits .agents README.md docs/agent-skills-and-rules-structure.md` prints only compatibility notes.
- A Neon campaign started from "Conclave-SDK Gemini campaign" runs a section end to end under the new skills.
- `python scripts/todo-graph.py validate` and `python scripts/todo-graph.py plan --check` pass.
