## Round 1: astra (`gpt-6.2-astra` via `codex`)

- Writer: agy
- Run: 2026-11-22T11:37:17Z
- Candidate: 7bf101fd0de03aedc4a781b307d6a490dc4deaec
- Effort: medium
- Lenses: adversarial, integration, source-defect, consistency, quality, optimization
- Lines: 32
- Digest: b48d742f43dc0d6f

## adversarial: needs-attention

1. **P1. `replan` can move a findings file outside the repository.** Path: a project checkout contains a linked domain directory beneath `docs/reviews`, and the writer runs `replan` for an open section in that domain. Evidence: traced. `kits/todo/templates/scripts/lib/todo_graph.py:1683` validates the configured receipts root. Line 2098 then appends the domain and filename, and line 2130 calls `os.replace` without checking those additional path components. If the linked directory contains the expected findings filename, the command renames that external file. The existing `linked` check at line 1643 covers both symlinks and Windows junctions.

2. **P2. Two retries can both acquire the same TODO lock.** Path: a killed re-plan leaves its lock behind, then two workers re-plan different sections in that TODO. Evidence: traced at `kits/todo/templates/scripts/lib/todo_graph.py:2115`. Both workers can observe the abandoned lock as free. Pause the second immediately after that check, let the first unlink and acquire the lock, then resume the second. Its `unlink()` removes the first worker's live lock. Both can now reach the whole-file write at line 2148, losing one correction while leaving its archive on disk. The dispatcher's takeover protocol at `kits/reviewer/templates/scripts/review-dispatch.py:1242` rechecks ownership under a separate exclusive lock.

## integration: needs-attention

3. **P2. A sibling `stamp` can erase a successful re-plan.** Path: two workers operate on different sections of the same TODO, one stamping and one re-planning. Evidence: traced. At `kits/todo/templates/scripts/lib/todo_graph.py:2280`, `stamp` reads the whole TODO without taking the lock used by `replan`. Pause the stamp after that read, let `replan` write its correction at line 2148, then resume the stamp. Line 2297 replaces the TODO with the older snapshot plus the stamp. Both commands can report success, but the re-planned section loses its new `Started:` and correction note.

## source-defect: needs-attention

4. **P2. The stamp can identify the wrong commit as the checklist correction.** Path: a fast or stub-backed review workflow re-plans a section twice within one UTC minute and commits each correction separately. Evidence: traced. `kits/todo/templates/scripts/todo-graph.py:124` produces minute-resolution `Started:` values. `kits/todo/templates/scripts/lib/todo_graph.py:605` searches history oldest first for that line, so both corrections resolve to the first matching commit. The equality check at line 668 then refuses a plan review of the actual second correction and can accept the earlier candidate. This violates the correction-commit requirement at `todo/00-reviewer/TODO-01-three-pass-review.md:344`.

## consistency: needs-attention

5. **P3. The plan-validation docstring omits the re-plan exception.** `kits/todo/templates/scripts/lib/todo_graph.py:635` tells callers that a plan candidate may precede the build-start commit. For a section with an archive, line 668 requires equality. Compare the docstring with the `kept_chain_files` branch immediately before the return.

## quality: needs-attention

6. **P2. The serialization regression passes with broken stale-lock takeover.** Path: the crash-recovery race in finding 2. Evidence: traced at `tests/test_todo_graph.py:2936`. The test installs a live lock owned by the test process, calls `replan` once, and expects refusal. Removing the stale-lock `unlink()` or allowing it to remove a new owner's lock leaves every assertion green. The missing case needs two contenders and an ownership change between the stale check and removal.

## optimization: approve

LENS adversarial: findings  
LENS integration: findings  
LENS source-defect: findings  
LENS consistency: findings  
LENS quality: findings  
LENS optimization: clean  
HIGHEST: P1  
OVERALL: needs-attention

## Writer note: shadow audit verdict (D00 T01 §10)

- Run on 2026-11-22 as a new full-lens shadow audit of Row 4 (`D00 T01 §9`, base `9015bf1c`, candidate `7bf101fd`, stamped `1a8d1bd0`).
- Highest reported grade: `P1`; highest missed grade: `P1` (1 real P1, 4 real P2s, and 1 P3 missed by the repair-diff chain, all verified still open on HEAD: `replan` can `os.replace` through a symlinked/junctioned domain folder beneath `docs/reviews`, TOCTOU race in stale `todo_lock` takeover, `stamp` writes TODO without taking `todo_lock`, minute-resolution `Started:` in `build_start` resolves same-minute double replan to earlier commit, serialization test misses stale-lock takeover contention, and `plan_record` docstring omits re-plan equality).
- Repair filed as `D00 T01 §13` and `D00 T01 §9` reopened with `todo-graph.py unstamp` per `D00 T01 §10`.
