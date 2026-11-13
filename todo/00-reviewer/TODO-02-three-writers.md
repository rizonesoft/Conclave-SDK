---
schema_version: 1
id: three-writers
domain: 00-reviewer
status: active
title: "TODO-02 -- Antigravity and Codex as first-class writers"
---

# TODO-02 -- Antigravity and Codex as first-class writers

> **Goal:** Work written by any of the three agents can be reviewed from a fresh install: the template pin routes `codex` as well as `claude` and `agy`, the Antigravity command line the dispatcher builds is proven against the installed CLI, and Antigravity has the subagents the base kit gives Claude Code, or the limit is written down.

> **Current state:** Measured 2026-11-11. `kits/reviewer/templates/scripts/review_pin.py` accepts the writers `claude`, `codex`, `agy` and `gemini` (`WRITERS`, `:47`). The template pin `kits/reviewer/templates/.conclave/reviewers.toml` defines one reviewer (`astra`, the Codex CLI) and routes `claude` and `agy` to it (`:31`, `:32`); it has no `codex` route, so a review of Codex work refuses (the pin's own comment, `:27`). Each agent's skill copies already name their own agent: `--writer agy` in `.agents`, `--writer codex` in `.codex` (roadmap finding 11 is closed). The dispatcher builds the Antigravity reviewer command as `agy --model <model> --mode plan --sandbox --print-timeout <n>s` (`kits/reviewer/templates/scripts/review-dispatch.py:210`); no test compares those flags with what the installed CLI accepts. The base kit ships five Claude subagents under `kits/base/templates/.claude/agents/` and nothing equivalent under `.agents/`.

## Inputs

- `docs/plans/2026-11-11-sdk-audit-and-roadmap.md`: findings 9, 10 and 11 and recommendation 7.
- `kits/reviewer/templates/.conclave/reviewers.toml`, `kits/reviewer/templates/scripts/review_pin.py` and `kits/reviewer/templates/scripts/review-dispatch.py`, with their tests in `kits/reviewer/templates/scripts/tests/`.
- The owner's rule that Claude writes and never reviews: the reviewer added for Codex work is therefore Antigravity, not Claude.
- The pin rule in `AGENTS.md` (Review): a section keeps the pin committed at its plan review's candidate, so §1's pin change is committed before the next section starts.
- -> XREF: D02 T01 §2 -- the run guard for Antigravity and Codex (the other half of recommendation 7) is wired there

## Outcome

- A fresh install's `python scripts/review-dispatch.py --check-pin` prints `ok` with routes for `claude`, `agy` and `codex`, and a review of Codex work reaches a reviewer of another family.
- `python forge.py doctor <project> reviewer` fails a check when the installed `agy` no longer accepts a flag the dispatcher passes.
- Antigravity sessions have read-only subagent definitions equal in purpose to the five Claude ones, or `kits/base/README.md` states that Antigravity has none and why.

**Adjacency:** all=not-applicable (developer tooling: a reviewer pin, a command-line check and agent definition files, with no records a user lists, exports, is notified of or reverses)

**Adjacency rationale:** The one setting this work adds is a route and a reviewer in the template pin, consumed by the pin loader and proven by the `--check-pin` contract tests.

## Implementation Order

| Order | Section | Deliverable | Depends On | Status |
| ----- | ------- | ----------- | ---------- | ------ |
| 1 | §1 | Codex route and an Antigravity reviewer in the template pin | -- | [ ] |
| 2 | §2 | Antigravity flags checked against the installed CLI | -- | [ ] |
| 3 | §3 | Antigravity counterparts of the base kit's subagents | §2 | [ ] |

## 1. Codex route and an Antigravity reviewer in the template pin

> **Started:** 2026-11-13T14:07:20Z

The template pin leaves Codex's work with no reviewer (roadmap finding 10). It gains a second reviewer of another family and a `codex` route to it.

**Phase:** 4
**Needs:** none
**Surface:** no

**Build order:**

1. Add the reviewer and the route to `kits/reviewer/templates/.conclave/reviewers.toml`. Done when: the pin loads with three routes.
2. Update the fixtures, the skill tables and the SDK's own pin. Done when: the checkpoint passes.

- [x] Add a reviewer run through the Antigravity CLI to `kits/reviewer/templates/.conclave/reviewers.toml`, with a model name the installed `agy` lists and, under the three-pass schedule, ending in the effort the schedule sets (the loader refuses one that disagrees, `review_pin.py:136`). Done when: `python kits/reviewer/templates/scripts/review_pin.py --check --pin kits/reviewer/templates/.conclave/reviewers.toml` prints `ok`. Cheaper substitute: a model name not checked against the CLI's own list must fail review.
- [x] Refuse in `review_pin.py` an Antigravity reviewer whose model is not one of Google's (a name beginning `gemini-`): `agy` also serves Anthropic and OpenAI models (`claude-opus-5-5-medium`, `gpt-oss-120b-medium` in `agy models` at 1.5.8), so the CLI alone does not say the family, and a Claude model routed for Claude's own work would pass the other-family rule. Done when: tests refuse `cli = "agy"` with a `claude-` and a `gpt-` model, naming the reviewer, and accept `gemini-4-hydrogen-medium`. Cheaper substitute: a comment in the pin asking for a Gemini model must fail review, because the loader is what holds the rule.
- [x] Add `codex = ["<that reviewer>"]` under `[routes]` in the template pin and rewrite the comment at `:27` to say all three writers are routed. Done when: a test loads the template pin and finds routes for `claude`, `agy` and `codex`, each to a reviewer of another family.
- [x] Add a dispatcher test in `tests/test_template_pin.py`, on the kit's own harness (`Harness` in `kits/reviewer/templates/scripts/tests/test_review_dispatch.py`): with the template pin and a stub `agy`, `--writer codex` reaches the stub and records its review. Done when: the test fails when the `codex` route is removed.
- [x] Add a `--check-pin` fixture for the three-route pin under `tests/fixtures/check-pin/` and extend `tests/test_check_pin_contract.py`. Done when: the contract test passes and the fixture's expected JSON names three routes.
- [x] Replace the "none yet" row for Codex in the route table of `independent-review` in the three agent folders (`kits/reviewer/templates/.claude/skills/independent-review/SKILL.md:14` and its two copies), and name the new reviewer, its model and the `codex` route in the reviewer inventory of `kits/reviewer/README.md` (`:15` to `:19`, which names only Astra). Done when: a test reads the template pin and finds, in the README inventory and in each of the three skill tables, every reviewer with its model and every route with its reviewer, so a deleted row fails it, and `grep -rn "none yet" kits/reviewer` prints nothing.
- [x] Dispatch one bounded live review through the installed `agy` with the template pin: `review-dispatch.py --kind round --writer codex` on a small prompt naming a real commit of this repository, recorded to a scratch findings file, with a time limit. Done when: the dispatcher records it as a returned review (its `LENS` lines, `HIGHEST:` and `OVERALL:` present), and the agy version, model, elapsed time and verdict lines are in `kits/reviewer/README.md`. Cheaper substitute: the stub dispatcher test alone must fail review, because it proves neither the prompt's delivery nor a reply the dispatcher accepts.
- [x] Commit the SDK's own `.conclave/reviewers.toml` with the same reviewer and route as its own commit, before any other section starts, and run `python forge.py self-sync`. Done when: `python scripts/review-dispatch.py --check-pin` prints `ok` and `git log -1 --format=%s -- .conclave/reviewers.toml` is that commit.
- [ ] Commit: `reviewer: route Codex work to an Antigravity reviewer`

**Corrected 2026-11-13 (validation):** read at `agy` 1.5.8. Its models carry their effort in the name and every three-pass step runs at `medium`, so the reviewer is `gemini-4-hydrogen-medium` (`agy models`; Hydrogen is the line that offers `xhigh`, the strongest Gemini 4 here). The dispatcher builds the Antigravity command at `review-dispatch.py:217`, not `:210`. `agy` serves Claude and GPT models too, so the other-family rule needs the model's family, not only the CLI's: a micro-step above adds it.

**Corrected 2026-11-13 (build):** the tests of the shipped pin live in the SDK's `tests/test_template_pin.py`, not in the kit's tests: those are installed into projects, which own their pin and may change its routes, so a test of the template beside a project's own pin would fail there for no fault. The `--check-pin` fixture `valid-three-routes.toml` is held byte for byte to the template, and a second fixture refuses an Antigravity reviewer with another family's model.

**Corrected 2026-11-13 (live dispatch):** the first live dispatch returned no review: headless `agy --mode plan` refuses every shell command (measured on 1.5.8 against allow-rules, a trusted workspace and a hook), so the dispatcher's Antigravity command, unproven since the reviewer kit was written, could never read a commit. It now runs `agy --sandbox --settings <deny write_file and mcp>` with no mode, proven read-only by probes and recorded in `kits/reviewer/README.md`; a reviewer that prints nothing has its own stderr line in the recorded reason; and the live review's own P1 (the family check crashing `--check --all` on a malformed model) is fixed with a test. `§2`'s flag list follows this command line.

**Corrected 2026-11-13 (plan review):** a bounded live dispatch through the installed `agy` proves the route returns a review the dispatcher accepts, and the documentation test reads the pin, so a deleted row fails it.

**Test checkpoint:** `python -m unittest discover -s kits/reviewer/templates/scripts/tests` and `python -m unittest discover -s tests` both end `OK`; removing the `codex` route makes the new dispatcher test fail.

## 2. Antigravity flags checked against the installed CLI

> **Started:** 2026-11-13T15:16:09Z

The roadmap says to check every `agy` flag against the current CLI before it ships. The dispatcher passes five; a CLI release that renames one would turn every Antigravity review into "no review" with nobody noticing.

**Phase:** 4
**Needs:** none
**Surface:** no

**Build order:**

1. Name the flags the dispatcher passes to `agy` in one tuple in `kits/reviewer/templates/scripts/review-dispatch.py`. Done when: the command is built from it.
2. Check them in `forge.py doctor`. Done when: the checkpoint passes.

- [ ] Move the Antigravity flags (`--model`, `--sandbox`, `--settings`, `--print-timeout` and `-p`, the command `§1` proved live; never `--mode`) into a module constant `AGY_FLAGS` in `review-dispatch.py` and build the command in `command` (`:217`) from it. Done when: the existing dispatcher tests pass unchanged and the command line is byte for byte what it was.
- [ ] Add `agy_flags_missing(help_text)` to `review-dispatch.py`, returning the flags of `AGY_FLAGS` that the CLI's `--help` output does not list as whole words. Done when: tests with a captured help text find none missing, and with `--print-timeout` removed from the text find that one.
- [ ] Add a `reviewer-flags:<name>` check to `_doctor_reviewer` in `forge.py` (`forge.py:452`) for each reviewer whose CLI is `agy` and installed: run `agy --help` with a 15 second limit and report `unexpected` naming the missing flags, or `ok` with the CLI's version. Done when: tests with a stub `agy` cover both results.
- [ ] Probe that the CLI accepts the dispatcher's settings, in the same check: write `AGY_REVIEW_SETTINGS` to a scratch file and run `agy --settings <file> agents` (15 seconds; it validates the settings and runs no model: `agy` 1.5.8 answers a bad key with `Error: --settings: unknown setting`), reporting `unexpected` with the CLI's own line when it exits non-zero or prints a `--settings:` error. Done when: a stub that advertises every flag but rejects `permissions` is reported `unexpected` naming that line, and the scratch file is gone afterwards.
- [ ] Never report `ok` from a probe that failed: a CLI that cannot be started is `setup_required` with the launch error, one that exits non-zero is `unexpected` with its exit code even when its output lists every flag, and one that runs past the limit is `setup_required`, with its whole process tree ended (a job object or `taskkill /T` on Windows, its process group elsewhere), since `agy` may be a `.cmd` wrapper whose child would outlive it. Done when: tests cover a launch failure, a non-zero exit with complete help text, and a stub that starts a child and hangs, after which neither the stub nor its child is alive.
- [ ] Run the check against the `agy` installed on this machine and record its version and the result in `kits/reviewer/README.md`. Done when: the README names the version, and any flag reported missing is fixed in `AGY_FLAGS` with the dispatcher test updated.
- [ ] Run `python forge.py self-sync`. Done when: `scripts/review-dispatch.py` equals the kit file.
- [ ] Commit: `reviewer: doctor checks the Antigravity flags the dispatcher passes`

**Corrected 2026-11-13 (plan review):** the check also probes that the CLI accepts the settings payload (`agy --settings <file> agents`, which validates and runs no model), a failed probe is never `ok` (launch failure, non-zero exit, timeout each have their result), and a timed-out probe's whole process tree is ended and proven so with a child-spawning stub.

**Corrected 2026-11-13 (`§1`):** the flags are the ones of the command `§1` proved against `agy` 1.5.8 (`--model`, `--sandbox`, `--settings`, `--print-timeout`, `-p`): `--mode plan` is gone, because headless plan mode refuses the reviewer every command, and `--settings` carries the session's deny rules. The check also covers that the settings key `permissions` is accepted, since `agy` refuses an unknown setting by name.

**Test checkpoint:** `python -m unittest discover -s tests -p test_forge.py` and `python -m unittest discover -s kits/reviewer/templates/scripts/tests` end `OK`; adding a flag to `AGY_FLAGS` that the captured help text lacks makes the missing-flag test fail.

## 3. Antigravity counterparts of the base kit's subagents

Claude Code gets five read-only subagents from the base kit (`code-explorer`, `debug-evidence`, `git-runner`, `mutation-tester`, `test-runner`). Antigravity gets none (roadmap finding 9). Whether it can is a fact about the installed CLI, so the section starts by establishing it.

**Phase:** 4
**Needs:** none
**Surface:** no

**Build order:**

1. Establish from the installed Antigravity CLI and its documentation whether a project can define subagents, and in what file format. Done when: the answer and its source are in `kits/base/README.md`.
2. Port the five agents, or record the limit. Done when: the checkpoint passes.

- [ ] Write in `kits/base/README.md` what the installed `agy` supports for project-defined subagents: the folder, the file format, how a tool list is restricted and how a model is chosen, with the CLI version and the help or documentation text it came from. Done when: the README section exists and quotes its source. Cheaper substitute: a format written from memory must fail review.
- [ ] When Antigravity supports them: create the five definitions under `kits/base/templates/.agents/` in that format, each read-only (no edit or write tool), with the same purpose text as its Claude counterpart. Done when: a fresh `--agent agy` install has all five and a test asserts none lists a write tool.
- [ ] When Antigravity supports them: extend `kits/base/templates/scripts/verify-agent-tiers.mjs` or add a Python test in `tests/test_forge.py` that checks the Antigravity definitions the way `verify-agent-tiers.mjs` checks the Claude ones. Done when: a definition with a write tool fails the check.
- [ ] When Antigravity does not support them: state in `kits/base/README.md` and in the Subagents section of `kits/base/templates/AGENTS.md` that Antigravity runs mechanical subtasks in the main session, and close this section with no template change. Done when: both documents carry the sentence and the README names the CLI version checked.
- [ ] Run `python forge.py self-sync`. Done when: `python -m unittest discover -s tests` passes with the SDK's installed copies equal to the kits.
- [ ] Commit: `base: Antigravity subagents, or the recorded limit`

**Test checkpoint:** `python -m unittest discover -s tests` ends `OK`; when the agents were ported, adding a write tool to one Antigravity definition makes the new check fail, and when they were not, `grep -c "main session" kits/base/README.md` is at least 1.

## Verification

- A fresh `python forge.py init <scratch> --kit reviewer` prints `ok` for `python scripts/review-dispatch.py --check-pin` and lists three routes.
- `python forge.py doctor . reviewer --strict` exits 0 on this machine with the `reviewer-flags` check shown.
- `python -m unittest discover -s tests` passes.
- `python scripts/todo-graph.py validate` and `python scripts/todo-graph.py plan --check` pass.
