# Audit: D00 T02 §2, an extra review by Antigravity

The operator asked (2026-11-13) for Antigravity to review `D00 T02 §2` as well. The section was built by Claude, reviewed by Astra under the pin's route for `claude` and stamped at `3bc3531`; this is one more review of the same candidate by the pin's Antigravity reviewer, `hydrogen` (`gemini-4-hydrogen-medium` through `agy` 1.5.8), run with the dispatcher's own Antigravity command (sandboxed, write and MCP tools denied) outside the pin's route, so it is recorded here and not in the section's findings file. It took 423 seconds and returned `OVERALL: approve` with four P3 findings.

## Operator-requested review: hydrogen (`gemini-4-hydrogen-medium` via `agy`)

- Candidate: 3bc3531a887afd8965373a2d981b8d953ffeaba5
- Run: 2026-11-13

#### adversarial
Verdict: `advisory`

1. `[P3]` [forge.py:1297](file:///D:/Conclave-SDK/forge.py#L1297): `end_tree()` calls `proc.communicate()` with no `timeout`. If a timed-out or interrupted probe spawns a grandchild that detaches from the process group/tree (for example via `setsid` on POSIX) while keeping the inherited `stdout`/`stderr` pipe open, `proc.communicate()` will block indefinitely instead of returning the timeout error or propagating the interrupt.
2. `[P3]` [forge.py:1331-1334](file:///D:/Conclave-SDK/forge.py#L1331-L1334): `_agy_flags_check` runs `agy --settings <file> agents` and, whenever `code != 0`, reports `<executable> refuses the dispatcher's settings (exit <code>)` unless `--settings:` appears in output. Observed with `agy` 1.5.8 in a restricted environment where `~/.gemini/antigravity-cli` is not writable: `agy --settings <file> agents` exits `1` with `Failed to start: open .../installation_id: Access is denied.` before listing agents, which `_agy_flags_check` misreports as a `--settings` refusal.

#### integration
Verdict: `advisory`

1. `[P3]` [forge.py:1364](file:///D:/Conclave-SDK/forge.py#L1364): `_doctor_reviewer` resolves `reviewer["cli"]` via `shutil.which`, whereas [review-dispatch.py:171](file:///D:/Conclave-SDK/kits/reviewer/templates/scripts/review-dispatch.py#L171) avoids `shutil.which` because on Windows it searches the current working directory before `PATH`. Running `forge.py doctor` from a directory containing an `agy.cmd`/`agy.exe` will probe that CWD file rather than the `PATH` executable that `review-dispatch.py` actually invokes.
2. `[P3]` [forge.py:1367-1368](file:///D:/Conclave-SDK/forge.py#L1367-L1368): `_doctor_reviewer` calls `_agy_flags_check(module, found)` for every reviewer with `cli == "agy"` without caching by `found`, so a pin with multiple Antigravity reviewers re-runs all three subprocess probes against the same binary.

#### source-defect
Verdict: `approve`

Verified against `agy` 1.5.8 on this machine: `agy --help` lists all five flags in `AGY_FLAGS` (`--model`, `--sandbox`, `--settings`, `--print-timeout`, `-p`), `agy --version` exits `0` with `1.5.8`, and `agy --settings <json> agents` rejects unknown top-level keys (`Error: --settings: unknown setting "bad_key"`) while accepting `{"permissions":{"deny":["write_file(*)","mcp(*)"]}}`. Matches `D00 T02 §2` and Recommendation 7 of `docs/plans/2026-11-11-sdk-audit-and-roadmap.md`.

#### consistency
Verdict: `approve`

#### quality
Verdict: `approve`

HIGHEST: P3
OVERALL: approve

## Writer note: what was done with each finding

Each was checked against the code and found real. All four are fixed in `forge.py` outside a section (the section is stamped and its checklist is not rewritten), with tests in `tests/test_reviewer_flags.py` that fail without the fix.

- Cleanup wait with no limit: the wait after the tree is ended is bounded at 5 seconds and the pipe closed (`test_cleanup_does_not_wait_forever_on_a_pipe_a_stray_process_holds`).
- A failed settings probe called a refusal: only a `--settings:` line is a refusal; any other non-zero exit is reported with its exit code and the CLI's own first line (`test_a_settings_probe_that_fails_for_another_reason_is_not_called_a_refusal`).
- `shutil.which` in doctor: doctor finds a reviewer CLI with the dispatcher's own `find_cli`, so it probes the executable a review would run (`test_doctor_probes_the_cli_on_path_not_one_in_the_working_directory`).
- Repeated probes: one set of probes per executable, however many reviewers use it (`test_two_antigravity_reviewers_on_one_cli_are_probed_once`).
