---
name: systematic-debugging
description: >-
  Use whenever investigating any bug, test failure, flaky behavior, build error, or unexpected output before proposing or writing a fix. Enforces four-phase root-cause analysis so fixes land at the owning layer instead of patching symptoms.
---

# Systematic Debugging

Never guess at fixes or stack patches over symptoms. Find the root cause in the layer that owns the invariant before editing production code.

## Phase 1: Root cause investigation

Complete all checks before forming a fix hypothesis:

1. Read the full error message, stack trace, and failing assertion output without truncating line numbers or paths.
2. Reproduce the failure deterministically and record the minimal command or test case that triggers it.
3. Inspect recent changes (`git status --short`, `git diff`, `git log -n 10 --oneline`) for what shifted.
4. For multi-layer pipelines, trace backward along the call chain using [root-cause-tracing.md](./references/root-cause-tracing.md) or add single-pass boundary logging at each handoff to isolate where valid data becomes invalid.

## Phase 2: Owning-layer and pattern analysis

Compare the failing path against working paths in the same codebase:

- Identify a working sibling implementation and diff every assumption, configuration key, encoding, path separator, and lifecycle timing.
- Name the owning layer before touching any code: settings belong in settings, stored data in the producer or importer, page output in the component that builds it, never in a post-render filter or swallowed error.
- Read dependencies and called helpers completely instead of assuming their return values or error behavior.

## Phase 3: Single-variable hypothesis testing

Test one crisp hypothesis at a time:

1. State aloud what cause produces the symptom and what observation would disprove it.
2. Make the smallest reversible read or temporary probe needed to confirm or falsify the hypothesis.
3. Undo failed probes cleanly before trying the next hypothesis.

## Phase 4: Owning-layer fix and three-strike stop

Implement cleanly once root cause is proven:

1. Write a minimal failing regression test (or deterministic repro check) first and observe it fail for the expected reason.
2. Apply one focused fix in the owning layer (no unrelated cleanup or masking `except: pass` / `!important` / `@ts-ignore` bypasses).
3. Run the regression test plus impacted suites freshly and inspect full output before claiming the bug is fixed.
4. If three fix attempts fail in a row, stop editing and re-examine the architecture or ownership boundary, and discuss structural options with the user before making a fourth attempt.
