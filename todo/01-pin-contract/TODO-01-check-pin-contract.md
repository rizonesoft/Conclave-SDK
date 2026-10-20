---
schema_version: 1
id: check-pin-contract
domain: 01-pin-contract
status: active
title: "TODO-01 -- Check Pin Contract"
---

# TODO-01 -- Check Pin Contract

> **Goal:** The reviewer kit's dispatcher answers `review-dispatch.py --check-pin [--json]`, loading the pin with `load_pin` (still the only home of the rules) and never running a reviewer; `load_pin` refuses a non-integer `schema_version`; the SDK's own installed copy at `scripts/review-dispatch.py` matches the kit; and a contract test over fixture pins freezes the JSON shape the VS Code extension relies on.

> **Current state:** Measured 2026-10-16 at Conclave-SDK `97cca1d` (the reviewer kit is unchanged since `b7c649b`). `kits/reviewer/templates/scripts/review-dispatch.py` has no `--check-pin`: `main()` requires `--writer` and `--prompt`, so `--check-pin` alone exits 2 with an argparse usage error and no JSON. `load_pin` accepts `schema_version = true` (Python `True == 1`), reproduced on the shipped pin. The kit's tests are `kits/reviewer/templates/scripts/tests/test_review_dispatch.py` (17, one skipped on Windows), run from `tests/test_forge.py` `test_reviewer_kit_dispatcher_tests_pass`. Since 2026-10-16 the SDK carries an installed copy of the reviewer kit at its root (`scripts/review-dispatch.py`, `.conclave/reviewers.toml`), guarded against drift by `tests/test_forge.py` `test_the_sdk_uses_the_agent_setup_its_kits_ship`.

## Inputs

- `docs/plans/2026-10-16-vscode-extension.md`: the `--check-pin` contract and requirements R7, R9, R10, R18, R21.
- `kits/reviewer/templates/scripts/review-dispatch.py`: `load_pin`, `Refused`, `CLIS`, `main()` and the hidden `--pin` argument.
- `kits/reviewer/README.md`: where the new flag is documented.
- `kits/reviewer/scripts/test-install.sh` and `python -m unittest discover -s tests -v`: the SDK gates.
- `AGENTS.md`: stdlib only, atomic writes, no dashes, one line per paragraph, kit first then the SDK's installed copy.
- -> XREF: D00 T01 §2 -- no code before the owner approves the mockup
- -> XREF: D02 T01 §3 -- the dispatcher client consumes this contract and the fixtures from §3

## Outcome

- `python scripts/review-dispatch.py --check-pin --json` on the shipped pin prints `{"ok": true, "schema_version": 1, "reviewers": {...}, "routes": {...}, "clis": {...}}` and exits 0; a refused pin prints `{"ok": false, "error": "<Refused message>"}` and exits 2; no reviewer CLI is ever started. Read back by the kit's unit tests and by `kits/reviewer/scripts/test-install.sh`.
- `schema_version = true` and `schema_version = 1.0` are refused with the existing schema message.
- `tests/test_check_pin_contract.py` pins the JSON shape over `extensions/vscode/test/fixtures/pins/`, and the SDK's root copy of the dispatcher is byte-identical to the kit template.

**Adjacency:** all=not-applicable (a read-only validation flag on an existing CLI: no records, settings, notices, permissions or undo of its own)

**Adjacency rationale:** `--check-pin` only reads the pin and reports. The extension's settings, permissions (workspace trust), audit trail (output channel) and reverse paths that act on its answer are declared in `D02 T01`, which owns them.

## Implementation Order

| Order | Section | Deliverable | Depends On | Status |
| ----- | ------- | ----------- | ---------- | ------ |
| 1 | §1 | Strict schema_version type in load_pin | D00 T01 §2 | [x] |
| 2 | §2 | Dispatcher check-pin flag | §1 | [x] |
| 3 | §3 | Check-pin contract fixtures and test | §2 | [ ] |

## 1. Strict schema_version type in load_pin

> **Started:** 2026-10-20T08:06:45Z

**Corrected 2026-10-20:** the owner's CRLF-only changes the first step guarded against are gone (`git status --short` lists only this run's untracked findings file), so that step records the clean tree; and the staging step listed four files, but ticking this checklist changes this TODO file too, so it is staged with them.

`load_pin` compares `pin["schema_version"] != 1`, which a TOML boolean `true` or float `1.0` passes, so a malformed pin loads and `--check-pin` would echo `"schema_version": true`. This section fixes the rule in the reviewer kit, proves it with a regression test that fails first, and refreshes the SDK's installed copy. It must not change any other rule or message.

**Phase:** 0
**Needs:** none
**Surface:** no

**Build order:**

1. Add the failing test in `kits/reviewer/templates/scripts/tests/test_review_dispatch.py`. Done when: it fails on the unchanged `load_pin` because `schema_version = true` loads.
2. Fix `load_pin` in `kits/reviewer/templates/scripts/review-dispatch.py` and refresh the root copy with `python forge.py sync . --include-scripts`. Done when: the new test passes, every other test passes, and `scripts/review-dispatch.py` matches the kit.

- [x] Read `git status --short` and note the owner's CRLF-only changes under `.agents/`, `.claude/`, `.codex/` and `AGENTS.md`. Done when: the list is recorded in the section's working notes and none of those paths is ever staged. Cheaper substitute: `git add -A`.
- [x] Add `test_a_non_integer_schema_version_is_refused` to `kits/reviewer/templates/scripts/tests/test_review_dispatch.py`, writing the shipped pin with `schema_version = true` and then `schema_version = 1.0` and expecting exit 2 and no reviewer call. Done when: the test fails against the unchanged `load_pin`. Cheaper substitute: a test that only checks `schema_version = 2`.
- [x] Change the schema check in `load_pin` to require `type(pin["schema_version"]) is int and pin["schema_version"] == 1`, keeping the message `the reviewer pin needs exactly schema_version = 1, [reviewers.*] and [routes]`. Done when: the new test passes. Cheaper substitute: `isinstance(..., int)`, which still accepts `True`.
- [x] Refresh the SDK's installed copy with `python forge.py sync . --include-scripts`. Done when: `cmp scripts/review-dispatch.py kits/reviewer/templates/scripts/review-dispatch.py` reports no difference. Cheaper substitute: hand-editing `scripts/review-dispatch.py`.
- [x] Run `python -m unittest discover -s tests -v` and `bash kits/reviewer/scripts/test-install.sh`. Done when: both pass, with the one Windows skip unchanged. Cheaper substitute: running only the new test.
- [x] Stage only the kit's dispatcher and test, their two root copies and this TODO file. Done when: `git diff --cached --stat` lists exactly those five files. Cheaper substitute: staging the owner's CRLF changes.
- [x] Commit: `reviewer: refuse a non-integer schema_version`, then push `main`

**Test checkpoint:** `python -m unittest discover -s scripts/tests -p test_review_dispatch.py -v` passes including `test_a_non_integer_schema_version_is_refused`, and that test fails when the `type(...) is int` check is reverted.

> **Verified:** 2026-10-20 | §1 | dabab8332703e4f55b38577838cfb97beadb2ccc
> **Review:** `docs/reviews/d01-t01-s1.json`

## 2. Dispatcher check-pin flag

> **Started:** 2026-10-20T09:00:04Z

**Corrected 2026-10-20:** `--json` and the suppressed `--pin` already exist (from `D06 T01 §3`'s `--list-rounds`), and `--writer` and `--prompt` are already checked by `main()` rather than argparse, so `--check-pin` reuses them; the staging step also stages this TODO file, which ticking changes.

The extension must never reimplement validation (plan R7), so the dispatcher grows a read-only mode that reports what `load_pin` decides. This section adds `--check-pin [--json]` to the reviewer kit with tests, documents it in the kit README, refreshes the SDK's installed copy and runs the SDK gates. It must not start any reviewer CLI and must not change the meaning of the existing exit codes for a review run.

**Phase:** 0
**Needs:** none
**Surface:** no

**Build order:**

1. Write the failing tests in `kits/reviewer/templates/scripts/tests/test_review_dispatch.py`. Done when: they fail because `--check-pin` is an unknown argument.
2. Implement `--check-pin` and `--json` in `kits/reviewer/templates/scripts/review-dispatch.py` `main()`. Done when: the new tests and every existing test pass.
3. Document the flag, refresh the root copy, run the gates and push. Done when: `scripts/review-dispatch.py --check-pin --json` prints `"ok": true` for `.conclave/reviewers.toml` and `main` is pushed.

- [x] Add `test_check_pin_reports_a_valid_pin` running `--check-pin --json` on the shipped pin and asserting exit 0, `ok` true, `schema_version` 1, the three reviewers and routes exactly as loaded, a `clis` key per entry of `CLIS` with a boolean value, and no reviewer call. Done when: it fails before the flag exists. Cheaper substitute: asserting only `ok`.
- [x] Add `test_check_pin_reports_a_refused_pin` over the bad pins already listed in `test_a_bad_pin_refuses_before_any_reviewer_runs`, asserting exit 2, `ok` false and `error` equal to the `Refused` message `load_pin` raises for that pin. Done when: it fails before the flag exists. Cheaper substitute: asserting a non-empty error string.
- [x] Add `test_check_pin_reports_a_missing_pin` asserting exit 2 and an `error` starting `no reviewer pin at`. Done when: it fails before the flag exists. Cheaper substitute: none, a missing pin is a separate path.
- [x] Add `test_check_pin_without_json_prints_one_line` asserting `ok` or `refused: <message>` on stdout with the same exit codes. Done when: it fails before the flag exists. Cheaper substitute: making `--json` the only mode without a test for the plain mode.
- [x] Add `test_check_pin_needs_no_writer_or_prompt` asserting `--check-pin` runs without `--writer` and `--prompt`, and that `--writer` without `--prompt` still fails as before. Done when: it fails before the flag exists. Cheaper substitute: dropping `required=True` on `--writer` with no replacement check.
- [x] Implement `--check-pin` and `--json` in `main()` of `kits/reviewer/templates/scripts/review-dispatch.py`: load with `load_pin(args.pin)`, compute `clis` with `shutil.which` per entry of `CLIS`, print one JSON object or one line, exit 0 or 2, and keep `--writer` and `--prompt` required for a review run. Done when: every dispatcher test passes. Cheaper substitute: a second copy of the rules in a `check_pin()` function.
- [x] Document `--check-pin [--json]` in `kits/reviewer/README.md` under "Running a round" with both JSON shapes and exit codes. Done when: the README shows the command and both outputs, with table rows at or under 100 characters. Cheaper substitute: a docstring change only.
- [x] Add the flag to the module docstring of `kits/reviewer/templates/scripts/review-dispatch.py`. Done when: `--help` shows `--check-pin` and `--json`. Cheaper substitute: an undocumented flag.
- [x] Refresh the SDK's installed copy with `python forge.py sync . --include-scripts`. Done when: `cmp scripts/review-dispatch.py kits/reviewer/templates/scripts/review-dispatch.py` reports no difference. Cheaper substitute: copying the file by hand.
- [x] Run `python -m unittest discover -s tests -v` and `bash kits/reviewer/scripts/test-install.sh`. Done when: both pass. Cheaper substitute: running only the dispatcher tests.
- [x] Stage only the kit's dispatcher, test and README, the root copies and this TODO file. Done when: `git diff --cached --stat` lists only those files. Cheaper substitute: staging the owner's CRLF changes.
- [x] Commit: `reviewer: add review-dispatch.py --check-pin`, then push `main`

**Test checkpoint:** `python scripts/review-dispatch.py --check-pin --json` exits 0 with `"ok": true`, and `python scripts/review-dispatch.py --check-pin --json --pin docs/plans/2026-10-16-vscode-extension.md` exits 2 with `"ok": false`.

> **Verified:** 2026-10-20 | §2 | 2d23e7eb300dad93f6db0a833c04ceba54bd9a07
> **Review:** `docs/reviews/d01-t01-s2.json`

## 3. Check-pin contract fixtures and test

> **Started:** 2026-10-20T11:41:04Z

**Corrected 2026-10-20:** `D01 T01 §2`'s review made a pin that cannot be read a refusal (non-UTF-8 bytes, an integer past Python's digit limit, nesting past the parser's recursion), so the contract gains `refused-not-utf8.toml`, `refused-integer-too-long.toml` and `refused-nested-deep.toml`; and the `pin-layout` state (`D00 T01 §4`) needs a valid pin in a layout the editor does not edit, `valid-inline-layout.toml`, which `D02 T01 §3` and `§4` use as their inline-table pin.

The extension relies on the exact JSON shape of `--check-pin`. This section freezes that shape: fixture pins under `extensions/vscode/test/fixtures/pins/`, one per rule in plan R9 plus valid, missing-route and comment-heavy pins, and a stdlib test in the SDK's own suite that runs the kit's dispatcher over them. The extension's TypeScript tests reuse the same fixtures, so a dispatcher change that breaks the contract fails the SDK suite first.

**Phase:** 0
**Needs:** none
**Surface:** no

**Build order:**

1. Write the fixtures in `extensions/vscode/test/fixtures/pins/` with `extensions/vscode/test/fixtures/pins/expected.json` mapping each file to its exit code and `error`. Done when: there is one fixture per rule in plan R9.
2. Write `tests/test_check_pin_contract.py`. Done when: it passes and fails when one expected message is altered.

- [x] Copy the shipped pin to `extensions/vscode/test/fixtures/pins/valid-shipped.toml` and add `valid-no-codex-route.toml` (route removed) `valid-comments.toml` (comments on every line, inline and trailing) and `valid-inline-layout.toml` (inline tables, a quoted key and a route array over several lines). Done when: each loads with `ok` true. Cheaper substitute: a single valid fixture.
- [x] Write one refused fixture per rule in plan R9 in `extensions/vscode/test/fixtures/pins/` (`refused-schema-2.toml`, `refused-schema-bool.toml`, `refused-extra-table.toml`, `refused-no-reviewers.toml`, `refused-bad-name.toml`, `refused-unknown-key.toml`, `refused-bad-cli.toml`, `refused-bad-model.toml`, `refused-agy-effort.toml`, `refused-bad-effort.toml`, `refused-route-writer.toml`, `refused-empty-route.toml`, `refused-route-too-long.toml`, `refused-same-family.toml`, `refused-fallback-family.toml`, `refused-undefined-reviewer.toml`, `refused-duplicate-reviewer.toml`, `refused-unparsable.toml`, `refused-not-utf8.toml`, `refused-integer-too-long.toml`, `refused-nested-deep.toml`). Done when: each is refused by the rule it is named for. **Corrected 2026-10-20:** gained the three route fixtures for the owner's family route rule (`design/decisions.md`, Reviewer routes, 2026-10-20); `refused-empty-route.toml` now gets `must list one reviewer and at most one fallback`, the message `refused-route-too-long.toml` gets too, as `refused-undefined-reviewer.toml` and `refused-duplicate-reviewer.toml` already share theirs, so the Done when no longer asks for distinct messages. Cheaper substitute: fixtures that all fail on the first rule.
- [x] Record each fixture's expected exit code and exact `error` text in `extensions/vscode/test/fixtures/pins/expected.json`, written from a real `--check-pin --json` run and checked by hand against `load_pin`. **Corrected 2026-10-20:** `refused-unparsable.toml` and `refused-integer-too-long.toml` record `error_prefix` `unreadable reviewer pin: ` with a `why`, because the rest of those messages is Python's own text, which differs between the 3.11 and later versions the SDK supports. Done when: every fixture has an entry and every entry has a fixture. Cheaper substitute: expectations copied from memory.
- [x] Write `tests/test_check_pin_contract.py` (stdlib `unittest`) running `kits/reviewer/templates/scripts/review-dispatch.py --check-pin --json --pin <fixture>` for every entry and asserting the exit code, the `ok` value, the exact `error` text and, for valid pins, the keys `schema_version`, `reviewers`, `routes`, `clis`. Done when: it passes inside `python -m unittest discover -s tests -v`. Cheaper substitute: asserting only exit codes.
- [x] Save the `b7c649b` dispatcher with `git show b7c649b:kits/reviewer/templates/scripts/review-dispatch.py` as `extensions/vscode/test/fixtures/dispatchers/review-dispatch-b7c649b.py` and add a test that it prints no JSON object with an `ok` key for `--check-pin --json` (plan R18). Done when: the test passes and documents the detection rule. Cheaper substitute: detecting old dispatchers by exit code, which collides with refusal's exit 2.
- [x] Add `extensions/vscode/test/fixtures/` and `tests/test_check_pin_contract.py` to the layout table in `README.md`. Done when: the README names both. Cheaper substitute: an undocumented fixture folder.
- [ ] Commit: `test: freeze the check-pin contract over fixture pins`

**Test checkpoint:** `python -m unittest tests.test_check_pin_contract -v` passes, and fails naming the fixture when one `error` string in `extensions/vscode/test/fixtures/pins/expected.json` is edited.

## Verification

- `python -m unittest discover -s tests -v` and `bash kits/reviewer/scripts/test-install.sh` pass at the pushed `main`.
- `cmp scripts/review-dispatch.py kits/reviewer/templates/scripts/review-dispatch.py` reports no difference, and `python -m unittest tests.test_check_pin_contract -v` passes.
- `python scripts/todo-graph.py validate` and `python scripts/todo-graph.py plan --check` pass.
