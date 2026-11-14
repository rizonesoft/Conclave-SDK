---
schema_version: 1
id: three-writers
domain: 00-reviewer
status: active
title: "TODO-02 -- Antigravity and Codex as first-class writers"
---

# TODO-02 -- Antigravity and Codex as first-class writers

> **Goal:** Work written by any of the three agents can be reviewed from a fresh install: the template pin routes `codex` as well as `claude` and `agy` to Gemini 4 Carbon, the Antigravity command line and settings the dispatcher passes are proven against the installed CLI, and the base kit adopts native Orchestrator (Carbon) instead of custom `.agents/agents/` wrappers.

> **Current state:** Measured 2026-11-13 (`agy` 1.5.8). The prior pass routed `codex` to `[reviewers.hydrogen]` (`gemini-4-hydrogen-medium`), omitted `edit_file(*)` from `AGY_REVIEW_SETTINGS`, required `-<effort>` suffixes in `review_pin.py:check_agy_effort` even though `gemini-pro-orchestrator` manages its own effort and rejects `--effort`, and shipped manual `.agents/agents/*.md` plus `scripts/agy-subagent.py` in `kits/base`. With `Orchestrator (Carbon)` enabled, Antigravity natively plans on Carbon (`<plan_execute_protocol>`), executes via Hydrogen (`exit_plan_mode`), and provides built-in subagents (`self`, `research`, `image-generator`) without `.agents/agents/` definitions, while Codex code reviews should run directly on Gemini 4 Carbon (`gemini-4-carbon-medium`).

## Inputs

- `docs/plans/2026-11-11-sdk-audit-and-roadmap.md`: findings 9, 10 and 11 and recommendation 7.
- `kits/reviewer/templates/.conclave/reviewers.toml`, `kits/reviewer/templates/scripts/review_pin.py` and `kits/reviewer/templates/scripts/review-dispatch.py`, with their tests in `kits/reviewer/templates/scripts/tests/`.
- The owner's rule that Claude writes and never reviews, and the 2026-11-14 architectural correction that Codex work routes to Gemini 4 Carbon and Antigravity uses native `Orchestrator (Carbon)` (`gemini-pro-orchestrator`) without manual `.agents/agents/` wrappers.
- The pin rule in `AGENTS.md` (Review): a section keeps the pin committed at its plan review's candidate, so §1's pin change is committed before the next section starts.
- -> XREF: D02 T01 §2 -- the run guard for Antigravity and Codex (the other half of recommendation 7) is wired there

## Outcome

- A fresh install's `python scripts/review-dispatch.py --check-pin` prints `ok` with routes for `claude`, `agy` and `codex` (routing `codex` to `carbon`), and a review of Codex work reaches Gemini 4 Carbon.
- `python forge.py doctor <project> reviewer --strict` checks every flag and session deny rule (`write_file(*)`, `edit_file(*)`, `mcp(*)`) against the installed `agy` and exits 3 on `unexpected` failures.
- Antigravity sessions use native `Orchestrator (Carbon)` (`gemini-pro-orchestrator`) with zero `.agents/agents/*.md` files or `scripts/agy-subagent.py` in `kits/base` or the SDK root, documented and proven against `agy` 1.5.8.
- `kits/unattended` accepts `"effort": null` for `gemini-pro-orchestrator` (`Orchestrator (Carbon)`) and `gemini-pro-orchestrator-*` on top-level `agy` profiles and `runners.agy`, omitting `--effort` on launch while refusing non-`null` effort on Orchestrator models and refusing `null` elsewhere.

**Adjacency:** all=not-applicable (developer tooling: a reviewer pin, a command-line check and agent configuration, with no records a user lists, exports, is notified of or reverses)

**Adjacency rationale:** The one setting this work adds is a route and a reviewer in the template pin, consumed by the pin loader and proven by the `--check-pin` contract tests.

## Implementation Order

| Order | Section | Deliverable | Depends On | Status |
| ----- | ------- | ----------- | ---------- | ------ |
| 1 | §1 | Codex route to Gemini 4 Carbon and Orchestrator effort rules | -- | [x] |
| 2 | §2 | Antigravity flags and deny settings checked against the CLI | §1 | [x] |
| 3 | §3 | Antigravity Orchestrator Carbon and subagent contract in the base kit | §2 | [x] |
| 4 | §4 | Orchestrator effort-free profiles in the unattended kit | §1 | [ ] |

## 1. Codex route to Gemini 4 Carbon and Orchestrator effort rules

> **Started:** 2026-11-13T22:54:00Z

The template pin previously routed Codex reviews to Gemini 4 Hydrogen (`hydrogen`). It switches to Gemini 4 Carbon (`carbon`), teaches `review_pin.py` that `Orchestrator (Carbon)` (`gemini-pro-orchestrator`) manages its own effort and rejects `--effort`, and denies `edit_file(*)` alongside `write_file(*)` and `mcp(*)` in Antigravity review sessions.

**Phase:** 4
**Needs:** none
**Surface:** no

**Build order:**

1. Update `[reviewers.carbon]`, `[routes]`, `check_agy_effort`, and `AGY_REVIEW_SETTINGS` in `kits/reviewer/templates/`. Done when: `review_pin.py --check` and kit unit tests pass.
2. Update fixtures, contract tests, skill tables, README, live dispatch proof, and SDK pin via `self-sync`. Done when: the checkpoint passes.

- [x] Replace `[reviewers.hydrogen]` with `[reviewers.carbon]` (`cli = "agy"`, `model = "gemini-4-carbon-medium"`) and set `codex = ["carbon"]` in `kits/reviewer/templates/.conclave/reviewers.toml`, explaining in the pin comments that Gemini 4 Carbon reviews Codex work directly at `medium` effort matching `[schedule]`. Done when: `python kits/reviewer/templates/scripts/review_pin.py --check --pin kits/reviewer/templates/.conclave/reviewers.toml` prints `ok` and `load_pin` resolves `codex` to `("carbon", "gemini-4-carbon-medium")`. Cheaper substitute: keeping Hydrogen in `codex` or omitting the `gemini-4-carbon-medium` model name must fail review.
- [x] Update `check_agy_effort`, `load_pin`, and `faults` in `kits/reviewer/templates/scripts/review_pin.py` (`:194-201`, `:271-288`, `:437`) so `gemini-pro-orchestrator` and `gemini-pro-orchestrator-*` load without error when no pass sets `effort` (on unscheduled, `three-pass`, or `rotation` pins) and raise `Refused` naming `"manages its own effort and rejects --effort"` whenever any pass (`plan`, `completion`, `rounds`, `reconciliation`, `rotation`, or `escalation`) sets `effort` in either `three-pass` or `rotation`, while keeping `-<effort>` suffix validation for non-orchestrator `agy` `three-pass` reviewers (`gemini-4-carbon-medium`), keeping `agy` `rotation` pins for non-orchestrator models valid, and keeping `gemini-` family enforcement. Done when: tests in `kits/reviewer/templates/scripts/tests/test_review_pin.py` cover `load_pin` and `faults` for orchestrator effort-free and effort-bearing pins across unscheduled, `three-pass`, and `rotation` shapes (including `rotation` and `escalation` steps) plus `gemini-4-carbon-medium` effort suffix checks. Cheaper substitute: checking only `three-pass` in `check_agy_effort` or skipping `faults` must fail review, because `rotation` pins and `--check --all` would accept conflicting Orchestrator effort settings.
- [x] Update `AGY_REVIEW_SETTINGS` in `kits/reviewer/templates/scripts/review-dispatch.py` (`:241`) to `{"permissions": {"deny": ["write_file(*)", "edit_file(*)", "mcp(*)"]}}` so `dispatch.review` writes all three deny patterns to `agy-settings.json` before invoking `agy --sandbox --settings`. Done when: `tests/test_reviewer_flags.py` exercises `dispatch.review` with a fake executable reading the `--settings` file on disk and asserts all three deny patterns, AND a bounded live `agy --model gemini-4-carbon-medium --sandbox --settings` probe attempts `edit_file` on a disposable file in `$env:TEMP` and fails with an explicit permission denial (leaving its bytes unchanged) while still reading the committed repository candidate. Cheaper substitute: checking only `AGY_REVIEW_SETTINGS` or `command` argv without proving `review` writes the file and `agy` enforces `edit_file(*)` must fail review.
- [x] Update `tests/test_template_pin.py`, `tests/test_reviewer_flags.py` (`AGY_REVIEW_SETTINGS` JSON assertions in `dispatch.review` tests and `carbon` reviewer references), and `tests/fixtures/check-pin/pins/` (`valid-three-routes.toml` equal to template, `expected.json`, plus `valid-agy-orchestrator-unscheduled.toml`, `refused-agy-orchestrator-effort.toml`, and `refused-agy-orchestrator-rotation-effort.toml` exercised in `tests/test_check_pin_contract.py`). Done when: `python -m unittest tests.test_template_pin tests.test_check_pin_contract tests.test_reviewer_flags` passes and removing `codex = ["carbon"]` fails `test_template_pin`. Cheaper substitute: updating `expected.json` without regenerating/checking `valid-three-routes.toml` against the shipped pin or without testing `--check-pin` refusal on effort-bearing orchestrator pins must fail review.
- [x] Update the reviewer tables in `kits/reviewer/README.md` (`:7-28`) and the three `independent-review` copies (`kits/reviewer/templates/.{agents,claude,codex}/skills/independent-review/SKILL.md`) to name `carbon` and `gemini-4-carbon-medium` for `codex`, and run `python forge.py self-sync` so `.conclave/reviewers.toml`, `scripts/`, `.agents/`, `.claude/`, `.codex/`, and `docs/` match the kits. Done when: `tests.test_check_pin_contract.ShippedPinDocumentation` passes and `python scripts/review-dispatch.py --check-pin` prints `ok`. Cheaper substitute: updating only `README.md` or one agent skill copy leaves the isolated `.agents`, `.claude`, or `.codex` instructions stale and fails `ShippedPinDocumentation`.
- [x] Dispatch one bounded live review through the installed `agy` with the template pin (`python scripts/review-dispatch.py --kind round --candidate f69e3edd55873cf0a293a8d5e0e9ba1f836fc304 --writer codex --prompt <scratch>/s1-live-codex-prompt.md --record <scratch>/live-codex-carbon.md`, using a non-section scratch record name) asking for a verifiable observation from that committed candidate (`§1`'s `Started:` timestamp, without naming it in the prompt), and record the `agy` version, date, reviewer (`carbon`), model (`gemini-4-carbon-medium`), elapsed time, candidate observation, `edit_file(*)` deny probe result, and verdict lines in `kits/reviewer/README.md`. Done when: the dispatcher exits `0`, records `reviewer == "carbon"` and `model == "gemini-4-carbon-medium"`, quotes `2026-11-13T22:54:00Z` from the candidate alongside `LENS` lines, `HIGHEST:`, and `OVERALL:`, and the results match `kits/reviewer/README.md`.
- [x] Commit: `reviewer: route Codex work to Gemini 4 Carbon`

**Corrected 2026-11-14 (reopen):** Prior `D00 T02 §1` started `2026-11-13T14:07:20Z` and routed `codex` to `hydrogen` (`gemini-4-hydrogen-medium`) without `edit_file(*)` in `AGY_REVIEW_SETTINGS` and without `gemini-pro-orchestrator` effort handling. Reopened 2026-11-14 to route `codex` to Gemini 4 Carbon (`gemini-4-carbon-medium`), deny `edit_file(*)`, and teach `review_pin.py` about Orchestrator models.

**Corrected 2026-11-14 (plan review):** Astra (`gpt-6-astra`) flagged four gaps folded above: `check_agy_effort` runs via both `load_pin` and `faults` on `rotation` as well as `three-pass` schedules (`rotation`/`escalation` steps included); `test_reviewer_flags.py` proves `dispatch.review` writes `--settings` to disk and a bounded live probe proves `edit_file(*)` denies edits while committed reads succeed; and the bounded live `codex -> carbon` dispatch passes `--prompt` and a non-section `--record` scratch path, requires a verifiable committed candidate observation (`Started:` timestamp), and asserts `reviewer`/`model`.

**Test checkpoint:** `python -m unittest discover -s kits/reviewer/templates/scripts/tests` and `python -m unittest tests.test_template_pin tests.test_check_pin_contract tests.test_reviewer_flags tests.test_forge` both end `OK`; removing `codex = ["carbon"]` fails `tests.test_template_pin`.

> **Unstamped:** 2026-11-14: Route Codex reviews to Gemini 4 Carbon instead of Hydrogen and handle Orchestrator (Carbon) effort rules in review_pin.py (revoked receipt `docs/reviews/d00-t02-s1.revoked-2026-11-14.json`)

> **Verified:** 2026-11-14 | §1 | 630d20f13a9778670fed77a1d6b487cf1dd0d33b
> **Review:** `docs/reviews/d00-t02-s1.json`

## 2. Antigravity flags and deny settings checked against the CLI

> **Started:** 2026-11-14T00:13:39Z

The roadmap says to check every `agy` flag against the current CLI before it ships. The dispatcher passes five flags and session settings; a CLI release that renames one or rejects the settings key would turn every Antigravity review into "no review" with nobody noticing.

**Phase:** 4
**Needs:** none
**Surface:** no

**Build order:**

1. Name the flags the dispatcher passes to `agy` in one tuple in `kits/reviewer/templates/scripts/review-dispatch.py`. Done when: the command is built from it.
2. Check them and `AGY_REVIEW_SETTINGS` in `forge.py doctor`, aligned to `[reviewers.carbon]`. Done when: the checkpoint passes.

- [x] Define `AGY_FLAGS` (`("--model", "--sandbox", "--settings", "--print-timeout", "-p")`) in `kits/reviewer/templates/scripts/review-dispatch.py` and build the Antigravity `argv` in `command` from `AGY_FLAGS` and `AGY_REVIEW_SETTINGS` (`write_file(*)`, `edit_file(*)`, `mcp(*)`). Done when: `tests/test_reviewer_flags.py` proves `command` emits `AGY_FLAGS` in exact order, verifies that substituting distinct flag names into `AGY_FLAGS` changes `command`'s output with matching values, and verifies `dispatch.review` writes all three deny patterns to `agy-settings.json` before invoking `agy`. Cheaper substitute: duplicating literal flag strings in `command` or comparing `command` only against unchanged `AGY_FLAGS` must fail review, because hardcoded flags pass equality checks on the unchanged tuple.
- [x] Implement `agy_flags_missing(help_text)` in `kits/reviewer/templates/scripts/review-dispatch.py` to return every flag from `AGY_FLAGS` absent as a whole word from `help_text`. Done when: `FlagList` tests in `tests/test_reviewer_flags.py` pass with zero missing flags on captured `agy --help` output and report missing flags when `--print-timeout` is replaced with `--print-timeout-extra` or when `-p` is removed while `--print` remains (proving plain `flag in help_text` substring checks fail). Cheaper substitute: plain `flag in help_text` substring checks pass `--print-timeout` vs `--print`, whereas `-p` in `--print` and `--print-timeout` in `--print-timeout-extra` both pass naive substring matching and must be caught.
- [x] Wire `reviewer-flags:<name>` in `_doctor_reviewer` and `_agy_flags_check` in `forge.py` for every `agy` reviewer (`carbon`) found via `module.find_cli`: probe `<cli> --help` under `PROBE_SECONDS` (`15s`) and report `unexpected` naming missing flags or `ok` with `<cli> --version`. Done when: `DoctorCheck` tests in `tests/test_reviewer_flags.py` cover missing flags, working-directory decoy `agy` exclusion, multi-reviewer caching, and `ok` output on `[reviewers.carbon]`. Cheaper substitute: calling `shutil.which` without `path` on Windows or reporting only the legacy `hydrogen` reviewer must fail review, because Windows cwd lookup finds decoys and installed projects route to `carbon`.
- [x] Probe `AGY_REVIEW_SETTINGS` (`write_file(*)`, `edit_file(*)`, `mcp(*)`) in `_agy_flags_check` in `forge.py` via `<cli> --settings <temp_file> agents` (deleting `<temp_file>` in `finally:`), reporting `unexpected` on non-zero exit or `--settings:` output. Done when: `DoctorCheck` tests verify the temp file holds all three deny rules, is cleaned up after success or refusal, distinguishes generic `agents` errors from settings refusal, and never leaks `forge-agy-settings-*` files. Cheaper substitute: asserting settings acceptance from `--help` alone or leaving temp settings files behind must fail review.
- [x] Enforce never-`ok` failure mapping in `_probe` and `_agy_flags_check` in `forge.py` and verify CLI `--strict` exit codes end to end: launch failure -> `setup_required`, non-zero exit -> `unexpected`, timeout -> `setup_required` after `_kill_tree` cleanup (`forge.main(["doctor", ..., "reviewer", "--strict"])` returns `3` on `unexpected` or `setup_required` and `0` when `reviewer-flags:carbon` and `reviewer:astra` pass). Done when: `DoctorCheck` tests in `tests/test_reviewer_flags.py` exercise `forge.main(["doctor", str(project), "reviewer", "--strict"])` directly via captured stdout JSON across `ok` (exit `0`), missing flag (`3`), rejected settings (`3`), `agents` failure (`3`), and `setup_required` (`3`, `0` without `--strict`) plus process-tree cleanup on timeout and interrupt. Cheaper substitute: inspecting only `doctor_repo()` return dicts without testing `forge.main(..., "--strict")` exit code `3` must fail review.
- [x] Run live `python forge.py doctor . reviewer --strict` against installed `agy` (`[reviewers.carbon]`) and record the date, `agy` version, `reviewer-flags:carbon` result (`ok`), all five `AGY_FLAGS`, and all three `AGY_REVIEW_SETTINGS` deny patterns in `kits/reviewer/README.md` (`:28`). Done when: `python forge.py doctor . reviewer --strict` exits `0` showing `reviewer-flags:carbon` `ok` and `kits/reviewer/README.md` records that verification. Cheaper substitute: keeping the stale `2026-11-13` `hydrogen` note without re-running `doctor . reviewer --strict` after `§1` switched to `carbon` and added `edit_file(*)` must fail review.
- [x] Run `python forge.py self-sync`. Done when: `scripts/review-dispatch.py` and `scripts/review_pin.py` match `kits/reviewer/templates/` and `tests.test_forge -k self_sync` passes. Cheaper substitute: editing `scripts/review-dispatch.py` directly or skipping `self-sync` breaks SDK parity tests.
- [x] Commit: `reviewer: verify Antigravity flags and deny settings for Carbon`

**Corrected 2026-11-14 (reopen):** Prior `D00 T02 §2` started `2026-11-13T15:16:09Z` and verified `reviewer-flags:hydrogen` without `edit_file(*)` in `AGY_REVIEW_SETTINGS`. Reopened 2026-11-14 to verify `AGY_FLAGS` and all three `AGY_REVIEW_SETTINGS` deny rules (`write_file(*)`, `edit_file(*)`, `mcp(*)`) against `[reviewers.carbon]` and add end-to-end `forge.main doctor --strict` exit-code tests.

**Corrected 2026-11-14 (plan review):** Astra (`gpt-6-astra`) flagged two P2 gaps folded above: `FlagList` now tests `--print-timeout-extra` (for `--print-timeout`) and removing `-p` while `--print` remains (where naive `flag in help_text` fails), and `test_the_command_is_built_from_the_flags` substitutes distinct names into `AGY_FLAGS` and checks `command` emits them with their associated values.

**Test checkpoint:** `python -m unittest discover -s tests -p test_reviewer_flags.py` and `python -m unittest discover -s kits/reviewer/templates/scripts/tests` end `OK`.

> **Unstamped:** 2026-11-14: Re-verify Antigravity reviewer flags and edit_file/write_file/mcp deny settings against the Carbon reviewer (revoked receipt `docs/reviews/d00-t02-s2.revoked-2026-11-14.json`)

> **Verified:** 2026-11-14 | §2 | 5147b0187fccf63c663c708a744653b7a7c77d31
> **Review:** `docs/reviews/d00-t02-s2.json`

## 3. Antigravity Orchestrator Carbon and subagent contract in the base kit

> **Started:** 2026-11-14T01:36:08Z

**Corrected 2026-11-14 (reopen):** Prior `D00 T02 §3` started `2026-11-13T16:17:11Z` and created custom `.agents/agents/*.md` files plus `scripts/agy-subagent.py`. Reopened because Antigravity `Orchestrator (Carbon)` (`gemini-pro-orchestrator`) handles Carbon planning, Hydrogen execution, and built-in subagents automatically without custom `.agents/agents/` definitions.

Claude Code gets five read-only subagents from the base kit under `.claude/agents/`. Antigravity with `Orchestrator (Carbon)` provides two-phase planning/execution and built-in subagents (`self`, `research`, `image-generator`) natively and should not ship custom `.agents/agents/*.md` files or `scripts/agy-subagent.py`.

**Phase:** 4
**Needs:** none
**Surface:** no

**Build order:**

1. Remove `.agents/agents/*.md` and `scripts/agy-subagent.py` from `kits/base` and SDK root and update `forge.py` and install scripts. Done when: fresh `--agent agy` installs ship zero `.agents/agents/` files or `agy-subagent.py`.
2. Rewrite `tests/test_agy_agents.py`, document native `Orchestrator (Carbon)` in `kits/base`, and run a live `CONCLAVE_LIVE_AGY=1` proof on `gemini-pro-orchestrator`. Done when: tests and live proof pass.

- [x] Remove all five `.agents/agents/*.md` definitions and `scripts/agy-subagent.py` from `kits/base/templates/` and the SDK root via `git rm`, and remove stale `.agents/agents/` / `agy-subagent.py` references from `forge.py` (`SELF_PREFIXES`, `check_repo`, `SUITES`), `kits/base/scripts/test-install.sh`, `tests/test_forge.py`, `tests/test_check_all.py`, and `todo/01-forge/TODO-02-gates-and-skill-source.md` (with a `Corrected` note). Done when: `git ls-files .agents/agents kits/base/templates/.agents/agents scripts/agy-subagent.py kits/base/templates/scripts/agy-subagent.py` is empty. Cheaper substitute: deleting only the SDK root copies while leaving `kits/base/templates/.agents/agents` or `agy-subagent.py` in `forge.py` `SUITES` or `test-install.sh` must fail review.
- [x] Document Antigravity's native `Orchestrator (Carbon)` (`gemini-pro-orchestrator`) behavior in `kits/base/README.md`, `kits/base/templates/AGENTS.md`, `kits/base/templates/GEMINI.md`, `kits/base/templates/CODEX.md`, and `kits/base/templates/docs/agent-skills-and-rules-structure.md`, explaining automatic Carbon planning, Hydrogen execution (`exit_plan_mode`), built-in subagents (`self`, `research`, `image-generator`), why custom `.agents/agents/` files and `agy-subagent.py` are omitted, AND a reversible migration guide for existing `forge.py update` installs (naming the five retired SDK definitions plus `scripts/agy-subagent.py` preserved as `project-only`, preserving project customizations, explaining `--model gemini-pro-orchestrator` selection and rollback, and verifying native operation after cleanup). Done when: those docs match the native architecture and `tests/test_agy_agents.py` exercises the migration steps on an old-install fixture containing customized and unmodified files. Cheaper substitute: leaving stale `.agents/agents` instructions or omitting existing-install migration from `kits/base/README.md` must fail review.
- [x] Rewrite `tests/test_agy_agents.py` to enforce the native `Orchestrator (Carbon)` contract: offline tests cover zero `.agents/agents/` or `agy-subagent.py` in `kits/base`/SDK root, `forge.update` migration on an old-install fixture (removing the 5 SDK definitions and wrapper while keeping a custom project agent), `review_pin` orchestrator effort rules, `parse_orchestrator_stream` + `parse_subagent_delegation_stream` rejecting listing-only output, missing `exit_plan_mode`, failed delegation, and incomplete execution, AND bounded process-tree cleanup (`taskkill /T` on Windows, `os.killpg` elsewhere) with a real child-process fixture proving no descendant survives timeout or teardown; `CONCLAVE_LIVE_AGY=1` live proof installs `--agent agy` into a scratch repo and proves built-in subagent listing (`self`, `research`, `image-generator`), actual `invoke_subagent` known-answer delegation to a built-in subagent with completion evidence and independently checked result, and two-phase `gemini-pro-orchestrator` `exit_plan_mode` execution fixing `calc.py`. Done when: `python -m unittest tests.test_agy_agents` passes offline and with `CONCLAVE_LIVE_AGY=1` on `agy` 1.5.8, and results are recorded in `kits/base/README.md`. Cheaper substitute: testing only subagent listing without proving live `invoke_subagent` delegation or omitting process-tree teardown proof must fail review.
- [x] Run `python forge.py self-sync`. Done when: `python -m unittest discover -s tests` passes with SDK root matching the kits. Cheaper substitute: editing SDK root copies directly instead of syncing from `kits/base/templates` must fail review.
- [x] Commit: `base: adopt native Orchestrator Carbon without agy-subagent wrappers`

**Corrected 2026-11-14 (plan review):** Astra (`gpt-6-astra`) flagged one P1 and two P2 gaps folded above: `CONCLAVE_LIVE_AGY=1` now requires actual `invoke_subagent` known-answer delegation and negative stream fixtures rejecting listing-only/failed delegation; `tests/test_agy_agents.py` keeps bounded execution with whole-tree cleanup proven on a child-process fixture; and `kits/base/README.md` documents a reversible migration for existing `forge.py update` installs tested against an old-install fixture.

**Test checkpoint:** `python -m unittest tests.test_agy_agents tests.test_check_all tests.test_forge` and `python forge.py check-all --only agent-tiers` end `OK`.

> **Unstamped:** 2026-11-14: Orchestrator (Carbon) handles Carbon planning, Hydrogen execution, and built-in subagents automatically without custom .agents/agents files (revoked receipt `docs/reviews/d00-t02-s3.revoked-2026-11-14.json`)

> **Verified:** 2026-11-14 | §3 | 0c884d06f501efd5e308cb83611633191dc609f4
> **Review:** `docs/reviews/d00-t02-s3.json`

## 4. Orchestrator effort-free profiles in the unattended kit

> **Started:** 2026-11-14T04:14:17Z

Unattended profiles previously required a string `effort` for every agent and always passed `--effort=<effort>` when launching `agy`. `Orchestrator (Carbon)` (`gemini-pro-orchestrator`) and `gemini-pro-orchestrator-*` manage effort internally and reject `--effort`, so both `.conclave/unattended.json` top-level `agy` profiles and `runners.agy` entries must require `"effort": null` on Orchestrator models and omit `--effort` at launch.

**Phase:** 4
**Needs:** none
**Surface:** no

**Build order:**

1. Add `is_agy_orchestrator` to `unattended.py` and omit `--effort` when `effort is None` in `unattended-run.py`. Done when: kit unit tests cover profile validation and argv emission.
2. Document `"effort": null` for Orchestrator models in `kits/unattended` docs. Done when: the checkpoint passes.

- [ ] Add `is_agy_orchestrator(model)` to `kits/unattended/templates/scripts/lib/unattended.py` (rejecting non-strings, whitespace, NUL, and bare `"gemini-pro-orchestrator-"` with an empty suffix) and update `load_profile` so `model` / `runners.<agent>.model` refuse whitespace and bare `"gemini-pro-orchestrator-"`, while top-level `agent == "agy"` profiles and `runners.agy` entries with `gemini-pro-orchestrator` or `gemini-pro-orchestrator-*` require `effort: null` (raising `ProfileError` naming `"manages its own effort and rejects --effort"` on any non-null effort), while keeping `effort` required and validated against `EFFORTS` for all non-orchestrator models and keeping the unchanged template refusal naming `name`, `model`, `effort`. Done when: `LoadProfileTest` and `RunnersTest` in `kits/unattended/templates/scripts/tests/test_unattended.py` cover effort-free orchestrator acceptance, non-null orchestrator refusal, malformed orchestrator model refusal, null non-orchestrator refusal, and `runner(profile, "agy")` returning `effort: None`. Cheaper substitute: allowing `effort: null` on non-orchestrator `agy` models, accepting bare `"gemini-pro-orchestrator-"`, or breaking the unchanged-template error message must fail review.
- [ ] Update `agent_command` in `kits/unattended/templates/scripts/unattended-run.py` so `agent == "agy"` omits `--effort` when `effort is None` on Orchestrator models (both fresh start and `--conversation` resume) and raises `RunError` if `effort is None` reaches `claude`, `codex`, or a non-orchestrator `agy` model, or if non-`None` effort reaches an Orchestrator `agy` model. Done when: `CommandTest` in `kits/unattended/templates/scripts/tests/test_run.py` proves `agy` omits `--effort` when `effort is None` across fresh/resume and `skip_permissions` `True`/`False`, keeps `--effort=<e>` for non-orchestrator `agy` models, and refuses `None` effort on `claude`/`codex`/non-orchestrator `agy` and non-`None` effort on Orchestrator `agy`, AND `RunTest` in `kits/unattended/templates/scripts/tests/test_run.py` proves persisted `"effort": null` Orchestrator profiles end-to-end through `start` and its separate preflight process (top-level `agent="agy"` fresh launch + operator-initiated resume keeping `--conversation`, `start --agent agy` runner selection, asserting `--model=...` and zero `--effort` args, plus an invalid effort-bearing Orchestrator profile refusing before launching a child). Cheaper substitute: passing `--effort=None`, skipping resume/refusal command assertions, or testing only `CommandTest` without persisted `RunTest` `start` + preflight integration must fail review.
- [ ] Update `kits/unattended/README.md` and `kits/unattended/templates/docs/unattended-run.md` to document `effort: null` for Antigravity Orchestrator models (`gemini-pro-orchestrator`, `gemini-pro-orchestrator-*`) in `.conclave/unattended.json` and `runners.agy`. Done when: both docs explain the Orchestrator `effort: null` rule and markdown formatting checks pass. Cheaper substitute: updating code without updating operator setup docs in `unattended-run.md` and `README.md` must fail review.
- [ ] Commit: `unattended: support effort-free Antigravity Orchestrator profiles`

**Corrected 2026-11-14 (plan review):** Astra (`gpt-6-astra`) flagged one P2 gap folded above: `RunTest` in `kits/unattended/templates/scripts/tests/test_run.py` is extended with end-to-end persisted `"effort": null` integration coverage through `start`, its separate preflight process, and the launched stub command across top-level `agy` (fresh + resume keeping `--conversation`), `start --agent agy`, and an invalid effort-bearing profile refusing before spawning a child.

**Test checkpoint:** `python -m unittest discover -s kits/unattended/templates/scripts/tests` and `python -m unittest tests.test_forge -k markdown_table -k dashes` both end `OK` (with Linux CI `kits-linux` executing the `RunTest` tmux integration cases); setting `effort: "medium"` with `model: "gemini-pro-orchestrator"` fails `LoadProfileTest`.

## Verification

- A fresh `python forge.py init <scratch> --kit reviewer` prints `ok` for `python scripts/review-dispatch.py --check-pin` and lists three routes.
- `python forge.py doctor . reviewer --strict` exits 0 on this machine with the `reviewer-flags` check shown.
- `python -m unittest discover -s tests` passes.
- `python -m unittest discover -s kits/unattended/templates/scripts/tests` passes.
- `python scripts/todo-graph.py validate` and `python scripts/todo-graph.py plan --check` pass.
