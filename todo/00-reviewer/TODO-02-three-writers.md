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

**Adjacency:** all=not-applicable (developer tooling: a reviewer pin, a command-line check and agent configuration, with no records a user lists, exports, is notified of or reverses)

**Adjacency rationale:** The one setting this work adds is a route and a reviewer in the template pin, consumed by the pin loader and proven by the `--check-pin` contract tests.

## Implementation Order

| Order | Section | Deliverable | Depends On | Status |
| ----- | ------- | ----------- | ---------- | ------ |
| 1 | §1 | Codex route to Gemini 4 Carbon and Orchestrator effort rules | -- | [ ] |
| 2 | §2 | Antigravity flags and deny settings checked against the CLI | -- | [ ] |
| 3 | §3 | Antigravity Orchestrator Carbon and subagent contract in the base kit | §2 | [ ] |

## 1. Codex route to Gemini 4 Carbon and Orchestrator effort rules

> **Started:** 2026-11-13T22:54:00Z

The template pin previously routed Codex reviews to Gemini 4 Hydrogen (`hydrogen`). It switches to Gemini 4 Carbon (`carbon`), teaches `review_pin.py` that `Orchestrator (Carbon)` (`gemini-pro-orchestrator`) manages its own effort and rejects `--effort`, and denies `edit_file(*)` alongside `write_file(*)` and `mcp(*)` in Antigravity review sessions.

**Phase:** 4
**Needs:** none
**Surface:** no

**Build order:**

1. Update `[reviewers.carbon]`, `[routes]`, `check_agy_effort`, and `AGY_REVIEW_SETTINGS` in `kits/reviewer/templates/`. Done when: `review_pin.py --check` and kit unit tests pass.
2. Update fixtures, contract tests, skill tables, README, live dispatch proof, and SDK pin via `self-sync`. Done when: the checkpoint passes.

- [ ] Replace `[reviewers.hydrogen]` with `[reviewers.carbon]` (`cli = "agy"`, `model = "gemini-4-carbon-medium"`) and set `codex = ["carbon"]` in `kits/reviewer/templates/.conclave/reviewers.toml`, explaining in the pin comments that Gemini 4 Carbon reviews Codex work directly at `medium` effort matching `[schedule]`. Done when: `python kits/reviewer/templates/scripts/review_pin.py --check --pin kits/reviewer/templates/.conclave/reviewers.toml` prints `ok` and `load_pin` resolves `codex` to `("carbon", "gemini-4-carbon-medium")`. Cheaper substitute: keeping Hydrogen in `codex` or omitting the `gemini-4-carbon-medium` model name must fail review.
- [ ] Update `check_agy_effort` in `kits/reviewer/templates/scripts/review_pin.py` (`:437`) so `gemini-pro-orchestrator` (and `gemini-pro-orchestrator-*`) load without error when no `[schedule]` pass sets `effort` (or `[schedule]` is absent), and raise `Refused` naming `"manages its own effort and rejects --effort"` whenever a `[schedule]` pass specifies `effort`, while keeping `-<effort>` suffix validation for non-orchestrator `agy` models and keeping the `gemini-` family check in `check_reviewer_family`. Done when: tests in `kits/reviewer/templates/scripts/tests/test_review_pin.py` prove orchestrator models load with effort-free schedules, refuse when any step sets `effort`, and check `gemini-4-carbon-medium` against scheduled efforts.
- [ ] Update `AGY_REVIEW_SETTINGS` in `kits/reviewer/templates/scripts/review-dispatch.py` (`:241`) to `{"permissions": {"deny": ["write_file(*)", "edit_file(*)", "mcp(*)"]}}` and keep `command` passing `--sandbox --settings <file>`. Done when: unit tests verify `edit_file(*)` is in `AGY_REVIEW_SETTINGS` and in the `agy-settings.json` written by `command`. Cheaper substitute: omitting `edit_file(*)` leaves Antigravity's edit tool allowed when sandbox permits or when tools are checked, so tests without all three patterns must fail.
- [ ] Update `tests/test_template_pin.py`, `tests/test_reviewer_flags.py` (`AGY_REVIEW_SETTINGS` JSON assertions and `carbon` reviewer references), and `tests/fixtures/check-pin/pins/` (`valid-three-routes.toml`, `expected.json`, plus a new `valid-agy-orchestrator-unscheduled.toml` fixture exercised in `tests/test_check_pin_contract.py`). Done when: `python -m unittest tests.test_template_pin tests.test_check_pin_contract tests.test_reviewer_flags` passes and removing `codex = ["carbon"]` fails `test_template_pin`.
- [ ] Update the reviewer tables in `kits/reviewer/README.md` (`:7-28`) and the three `independent-review` copies (`kits/reviewer/templates/.{agents,claude,codex}/skills/independent-review/SKILL.md`) to name `carbon` and `gemini-4-carbon-medium` for `codex`, and run `python forge.py self-sync` so `.conclave/reviewers.toml`, `scripts/`, `.agents/`, `.claude/`, `.codex/`, and `docs/` match the kits. Done when: `tests.test_check_pin_contract.ShippedPinDocumentation` passes and `python scripts/review-dispatch.py --check-pin` prints `ok`.
- [ ] Dispatch one bounded live review through the installed `agy` with the template pin (`python scripts/review-dispatch.py --kind round --candidate <HEAD> --writer codex` -> `carbon`, `gemini-4-carbon-medium`) against a real commit, writing the record to a scratch findings file, and record the `agy` version, date, model, elapsed time, and verdict lines in `kits/reviewer/README.md`. Done when: the dispatcher exits 0 with `LENS` lines, `HIGHEST:`, and `OVERALL:` recorded in the scratch file and documented in `kits/reviewer/README.md`.
- [ ] Commit: `reviewer: route Codex work to Gemini 4 Carbon`

**Corrected 2026-11-14 (reopen):** Prior `D00 T02 §1` started `2026-11-13T14:07:20Z` and routed `codex` to `hydrogen` (`gemini-4-hydrogen-medium`) without `edit_file(*)` in `AGY_REVIEW_SETTINGS` and without `gemini-pro-orchestrator` effort handling. Reopened 2026-11-14 to route `codex` to Gemini 4 Carbon (`gemini-4-carbon-medium`), deny `edit_file(*)`, and teach `review_pin.py` about Orchestrator models.

**Test checkpoint:** `python -m unittest discover -s kits/reviewer/templates/scripts/tests` and `python -m unittest tests.test_template_pin tests.test_check_pin_contract tests.test_reviewer_flags tests.test_forge` both end `OK`; removing `codex = ["carbon"]` fails `tests.test_template_pin`.

> **Unstamped:** 2026-11-14: Route Codex reviews to Gemini 4 Carbon instead of Hydrogen and handle Orchestrator (Carbon) effort rules in review_pin.py (revoked receipt `docs/reviews/d00-t02-s1.revoked-2026-11-14.json`)

## 2. Antigravity flags and deny settings checked against the CLI

The roadmap says to check every `agy` flag against the current CLI before it ships. The dispatcher passes five flags and session settings; a CLI release that renames one or rejects the settings key would turn every Antigravity review into "no review" with nobody noticing.

**Phase:** 4
**Needs:** none
**Surface:** no

**Build order:**

1. Name the flags the dispatcher passes to `agy` in one tuple in `kits/reviewer/templates/scripts/review-dispatch.py`. Done when: the command is built from it.
2. Check them and `AGY_REVIEW_SETTINGS` in `forge.py doctor`, aligned to `[reviewers.carbon]`. Done when: the checkpoint passes.

- [ ] Move the Antigravity flags (`--model`, `--sandbox`, `--settings`, `--print-timeout` and `-p`) into a module constant `AGY_FLAGS` in `review-dispatch.py` and build the command in `command` from it. Done when: the existing dispatcher tests pass unchanged.
- [ ] Add `agy_flags_missing(help_text)` to `review-dispatch.py`, returning the flags of `AGY_FLAGS` that the CLI's `--help` output does not list as whole words. Done when: tests with a captured help text find none missing, and with `--print-timeout` removed find that one.
- [ ] Add a `reviewer-flags:<name>` check to `_doctor_reviewer` in `forge.py` for each reviewer whose CLI is `agy` and installed: run `agy --help` with a 15 second limit and report `unexpected` naming the missing flags, or `ok` with the CLI's version. Done when: tests with a stub `agy` cover both results.
- [ ] Probe that the CLI accepts `AGY_REVIEW_SETTINGS` (`write_file(*)`, `edit_file(*)`, `mcp(*)`) in the same check via `agy --settings <file> agents`, reporting `unexpected` when it exits non-zero or prints `--settings:`. Done when: tests verify rejection is reported `unexpected` and exit code with `--strict` is `3`.
- [ ] Never report `ok` from a probe that failed: launch failure -> `setup_required`, non-zero exit -> `unexpected`, timeout -> `setup_required` with whole process tree ended. Done when: tests cover all three failures and `doctor ... --strict` exits `3` on `unexpected`.
- [ ] Run `python forge.py doctor . reviewer --strict` against installed `agy` (`[reviewers.carbon]`) and record its version, date, and result in `kits/reviewer/README.md`. Done when: README shows `reviewer-flags:carbon` verified on `agy` 1.5.8 and `--strict` exits `0`.
- [ ] Run `python forge.py self-sync`. Done when: `scripts/review-dispatch.py` equals the kit file.
- [ ] Commit: `reviewer: verify Antigravity flags and deny settings for Carbon`

**Test checkpoint:** `python -m unittest discover -s tests -p test_reviewer_flags.py` and `python -m unittest discover -s kits/reviewer/templates/scripts/tests` end `OK`.

> **Unstamped:** 2026-11-14: Re-verify Antigravity reviewer flags and edit_file/write_file/mcp deny settings against the Carbon reviewer (revoked receipt `docs/reviews/d00-t02-s2.revoked-2026-11-14.json`)

## 3. Antigravity Orchestrator Carbon and subagent contract in the base kit

**Corrected 2026-11-14 (reopen):** Prior `D00 T02 §3` started `2026-11-13T16:17:11Z` and created custom `.agents/agents/*.md` files plus `scripts/agy-subagent.py`. Reopened because Antigravity `Orchestrator (Carbon)` (`gemini-pro-orchestrator`) handles Carbon planning, Hydrogen execution, and built-in subagents automatically without custom `.agents/agents/` definitions.

Claude Code gets five read-only subagents from the base kit under `.claude/agents/`. Antigravity with `Orchestrator (Carbon)` provides two-phase planning/execution and built-in subagents (`self`, `research`, `image-generator`) natively and should not ship custom `.agents/agents/*.md` files or `scripts/agy-subagent.py`.

**Phase:** 4
**Needs:** none
**Surface:** no

**Build order:**

1. Remove `.agents/agents/*.md` and `scripts/agy-subagent.py` from `kits/base` and SDK root and update `forge.py` and install scripts. Done when: fresh `--agent agy` installs ship zero `.agents/agents/` files or `agy-subagent.py`.
2. Rewrite `tests/test_agy_agents.py`, document native `Orchestrator (Carbon)` in `kits/base`, and run a live `CONCLAVE_LIVE_AGY=1` proof on `gemini-pro-orchestrator`. Done when: tests and live proof pass.

- [ ] Remove all five `.agents/agents/*.md` definitions and `scripts/agy-subagent.py` from `kits/base/templates/` and the SDK root via `git rm`, and remove stale `.agents/agents/` / `agy-subagent.py` references from `forge.py` (`SELF_PREFIXES`, `check_repo`, `SUITES`), `kits/base/scripts/test-install.sh`, `tests/test_forge.py`, `tests/test_check_all.py`, and `todo/01-forge/TODO-02-gates-and-skill-source.md` (with a `Corrected` note). Done when: `git ls-files .agents/agents kits/base/templates/.agents/agents scripts/agy-subagent.py kits/base/templates/scripts/agy-subagent.py` is empty.
- [ ] Document Antigravity's native `Orchestrator (Carbon)` (`gemini-pro-orchestrator`) behavior in `kits/base/README.md`, `kits/base/templates/AGENTS.md`, `kits/base/templates/GEMINI.md`, `kits/base/templates/CODEX.md`, and `kits/base/templates/docs/agent-skills-and-rules-structure.md`, explaining automatic Carbon planning, Hydrogen execution (`exit_plan_mode`), built-in subagents, and why custom `.agents/agents/` files and `agy-subagent.py` are omitted. Done when: those docs reflect the native architecture with no stale wrapper claims.
- [ ] Rewrite `tests/test_agy_agents.py` to enforce the native `Orchestrator (Carbon)` contract (asserting zero `.agents/agents/` definitions and no `agy-subagent.py` in `kits/base` or SDK root, verifying `review_pin` orchestrator effort rules, and keeping a `CONCLAVE_LIVE_AGY=1` live proof installing `--agent agy` into a scratch repo and running `agy --model gemini-pro-orchestrator` to observe Carbon planning + `exit_plan_mode` Hydrogen execution + built-in subagents). Done when: `python -m unittest tests.test_agy_agents` passes offline and with `CONCLAVE_LIVE_AGY=1` on `agy` 1.5.8, and results are recorded in `kits/base/README.md`.
- [ ] Run `python forge.py self-sync`. Done when: `python -m unittest discover -s tests` passes with SDK root matching the kits.
- [ ] Commit: `base: adopt native Orchestrator Carbon without agy-subagent wrappers`

**Test checkpoint:** `python -m unittest tests.test_agy_agents tests.test_check_all tests.test_forge` and `python forge.py check-all --only agent-tiers` end `OK`.

> **Unstamped:** 2026-11-14: Orchestrator (Carbon) handles Carbon planning, Hydrogen execution, and built-in subagents automatically without custom .agents/agents files (revoked receipt `docs/reviews/d00-t02-s3.revoked-2026-11-14.json`)

## Verification

- A fresh `python forge.py init <scratch> --kit reviewer` prints `ok` for `python scripts/review-dispatch.py --check-pin` and lists three routes.
- `python forge.py doctor . reviewer --strict` exits 0 on this machine with the `reviewer-flags` check shown.
- `python -m unittest discover -s tests` passes.
- `python scripts/todo-graph.py validate` and `python scripts/todo-graph.py plan --check` pass.
