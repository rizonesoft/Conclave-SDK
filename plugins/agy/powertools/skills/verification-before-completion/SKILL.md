---
name: verification-before-completion
description: >-
  Use before claiming any bug is fixed, feature works, test passes, build succeeds, deploy landed, or task is complete. Enforces fresh command verification and output inspection in the current turn.
---

# Verification Before Completion

Evidence precedes claims. Never declare work passing, fixed, clean, or done from memory, prior runs, partial checks, or confidence alone.

## Five-step verification gate

Execute these steps before writing any completion claim:

1. **Identify the proving check**: choose the exact command, validator, or runtime probe that directly tests every requirement of your change.
2. **Run it freshly now**: execute the command in the current turn after your final edit (`bosun run -- <cmd>` for heavy full builds or full test suites when `bosun` is on `PATH`).
3. **Inspect full output and exit code**: verify 0 failures, no unexpected skipped tests, and zero silent warnings or fallback errors.
4. **Verify red-green and subagent diffs**: for bug fixes, confirm the new test failed before your fix and passes after it; after any subagent or workflow edit, run `git status --short` and read `git diff` yourself rather than trusting the subagent summary.
5. **Report facts only**: state exact commands run, exact counts/status observed, any remaining limits or unverified scopes, and end code-change reports with a `Layer:` line.

## Disallowed claims

- Saying "tests pass" when only a filtered subset ran, or before the final edit.
- Treating static linters or syntax checks as proof of runtime behavior.
- Claiming a deploy, service reload, or plugin install works without checking the live target or validator output.
- Shipping or calling work verified on an incomplete or failed cross-family review ("no review" is an explicit limit, never an approval).
