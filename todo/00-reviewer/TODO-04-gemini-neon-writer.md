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
| 1 | §1 | Base kit guidance names Gemini 4 Neon | -- | [ ] |
| 2 | §2 | Antigravity TODO skills without Carbon handoffs | §1 | [ ] |
| 3 | §3 | Reviewer pin accepts Neon with an effort | -- | [ ] |
| 4 | §4 | Unattended profile runs Neon with its effort | -- | [ ] |
| 5 | §5 | SDK copies, documents and tests follow the kits | §1, §2, §3, §4 | [ ] |

## 1. Base kit guidance names Gemini 4 Neon

The base kit tells every agent how Antigravity works. Today it describes Orchestrator's Carbon planning and Hydrogen execution and forbids `--effort`; under Neon, Antigravity is one model at an explicit effort, so that text is wrong for every project that installs the kit.

**Phase:** 10
**Needs:** none
**Surface:** no

**Build order:**

1. Rewrite the Antigravity guidance in the base kit's templates. Done when: `git grep -nE "Carbon|Hydrogen|exit_plan_mode" -- kits/base/templates` prints nothing.
2. Replace the README's migration section. Done when: `kits/base/README.md` documents moving to Neon and keeps one line on Orchestrator compatibility.

- [ ] Rewrite the Antigravity lines in `kits/base/templates/AGENTS.md`, `GEMINI.md` and `CODEX.md` to say Antigravity runs `gemini-4-neon-medium` at an explicit `--effort`, with built-in subagents as before. Done when: none names Carbon or Hydrogen. Cheaper substitute: appending a Neon note beside the Carbon text.
- [ ] Rewrite `kits/base/templates/.agents/rules/agy-output-and-safety.md` so a section is planned and built in one session without `exit_plan_mode` handoffs. Done when: the rule names no handoff and keeps its safety lines unchanged.
- [ ] Rewrite the Antigravity entry in `kits/base/templates/docs/agent-skills-and-rules-structure.md`. Done when: it names Neon and explicit effort.
- [ ] Update the Antigravity mentions in the five `kits/base/templates/.claude/agents/*.md` files. Done when: `node scripts/verify-agent-tiers.mjs` passes and none names Carbon.
- [ ] Replace "Migrating existing installs to Orchestrator (Carbon)" in `kits/base/README.md` with "Moving Antigravity to Gemini 4 Neon": the launch flags, the effort, and that an Orchestrator model still runs without `--effort`. Done when: the section reads so and its verification notes name a real Neon run.
- [ ] Commit: `base: Antigravity guidance names Gemini 4 Neon at an explicit effort (D00 T04 §1)`

**Test checkpoint:** `git grep -nE "Carbon|Hydrogen|exit_plan_mode" -- kits/base/templates` prints nothing, and `python -m unittest tests.test_kit_install` ends `OK`.

## 2. Antigravity TODO skills without Carbon handoffs

The todo kit's Antigravity copies of `process-plan`, `process-phase` and `process-todo-section` tell the writer to plan on Carbon and hand to Hydrogen after each section. Under Neon the writer follows the same steps as the Claude source.

**Phase:** 10
**Needs:** none
**Surface:** no

**Build order:**

1. Remove the Carbon handoff text from the skill patches and regenerate the copies. Done when: `python forge.py skill-copies` reports no difference and the regenerated Antigravity skills name no handoff.

- [ ] Remove the Carbon and Hydrogen handoff instructions from `kits/todo/skill-patches/agents/process-plan/SKILL.md.json`, `process-phase/SKILL.md.json` and `process-todo-section/SKILL.md.json`, keeping every other declared difference. Done when: each patch still applies. Cheaper substitute: editing the generated copies by hand, which the generator test refuses.
- [ ] Run `python forge.py skill-copies`. Done when: `kits/todo/templates/.agents/skills/process-*/SKILL.md` name no Carbon, Hydrogen or `exit_plan_mode`.
- [ ] Update `tests/test_agy_agents.py` assertions that expect the handoff text to assert its absence. Done when: the test passes and fails if a handoff line is put back in a patch.
- [ ] Clarify in `kits/todo/templates/.claude/skills/process-todo-section/SKILL.md` (filed non-blocking P3 from `D00 T03 §2` Completion review) that a section's `Commit:` checklist item stays `[ ]` until `todo-graph.py stamp` ticks it with the Implementation Order row, then run `python forge.py skill-copies`. Done when: the clause appears in the Claude source and generated Antigravity/Codex copies and `python forge.py skill-copies --check` exits 0.
- [ ] Commit: `todo: Antigravity skills follow the Claude steps under Gemini 4 Neon (D00 T04 §2)`

**Test checkpoint:** `python -m unittest tests.test_agy_agents` ends `OK`, and fails when a Carbon handoff line is restored in `kits/todo/skill-patches/agents/process-plan/SKILL.md.json`.

## 3. Reviewer pin accepts Neon with an effort

`review_pin.py` refuses an effort on an Orchestrator writer because Orchestrator rejects `--effort`. Neon takes an effort like the other writers, so the check keys on the model, not on `agy`.

**Phase:** 10
**Needs:** none
**Surface:** no

**Build order:**

1. Make the effort refusal apply only to an Orchestrator model. Done when: a Neon pin with an effort validates and an Orchestrator pin with one is still refused.

- [ ] Change the effort check in `kits/reviewer/templates/scripts/review_pin.py` to refuse an effort only when the `agy` writer's model is `gemini-pro-orchestrator` or a variant. Done when: the function accepts a Neon pin with `effort = "medium"`. Cheaper substitute: dropping the check, which lets an Orchestrator pin fail at launch.
- [ ] Add `tests/fixtures/check-pin/pins/valid-agy-neon-effort.toml` and its line in `tests/fixtures/check-pin/pins/expected.json`, keeping the two `refused-agy-orchestrator-*` fixtures. Done when: `python -m unittest scripts.tests.test_review_pin` passes.
- [ ] Update `kits/reviewer/README.md` to name Neon as the Antigravity writer. Done when: it names no Carbon handoff.
- [ ] Commit: `reviewer: the pin accepts Gemini 4 Neon with an effort (D00 T04 §3)`

**Test checkpoint:** `python -m unittest scripts.tests.test_review_pin` ends `OK`, and fails when the Neon fixture's expected result is set to refused.

## 4. Unattended profile runs Neon with its effort

The unattended kit allows `"effort": null` for an Orchestrator profile and documents Carbon. A Neon profile carries an effort, and the run passes it.

**Phase:** 10
**Needs:** none
**Surface:** no

**Build order:**

1. Default the `agy` profile to Neon with an effort. Done when: a Neon profile launches with `--effort` and an Orchestrator profile with `"effort": null` still loads.

- [ ] Change the `agy` defaults in `kits/unattended/templates/scripts/lib/unattended.py` to `gemini-4-neon-medium` with `"effort": "medium"`, keeping `null` accepted only for an Orchestrator model. Done when: the kit's tests cover both. Cheaper substitute: accepting `null` for every model.
- [ ] Pass the profile's effort in `kits/unattended/templates/scripts/unattended-run.py` for Neon. Done when: a test's recorded launch line holds `--effort=medium`.
- [ ] Rewrite the Antigravity parts of `kits/unattended/README.md` and `templates/docs/unattended-run.md`. Done when: neither names Carbon or Hydrogen outside the compatibility note.
- [ ] Run the unattended kit's suite on Windows. Done when: it passes.
- [ ] Commit: `unattended: Antigravity profiles run Gemini 4 Neon with their effort (D00 T04 §4)`

**Test checkpoint:** `python forge.py check-all --only kit-unattended` passes, and fails when the Neon profile's effort is dropped from the launch line.

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
