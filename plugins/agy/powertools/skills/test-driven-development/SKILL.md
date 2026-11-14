---
name: test-driven-development
description: >-
  Use when implementing new features, fixing bugs, or changing behavioral contracts in code or hooks. Drives small, behavior-focused tests first so regressions fail before the fix and pass after it.
---

# Test-Driven Development

Write a failing behavior test first so you prove the test measures what you intend before implementing or changing behavior.

## Red-Green-Refactor loop

1. **Red**: write the smallest test expressing the desired behavior or reproducing the reported bug using real temporary files or real module contracts rather than mocked internals.
2. **Confirm failure**: run the test and verify it fails for the right reason (missing feature or exact bug), not a typo or import error.
3. **Green**: write the minimal owning-layer change to pass the test without lowering assertions or bypassing hooks.
4. **Confirm green**: run the new test and impacted suite and verify all cases pass cleanly.
5. **Refactor**: remove duplication and clarify naming while keeping all tests green.

## Conclave test hygiene

- Keep test files inside an existing test runner suite (`forge.py` `SUITES` in Conclave SDK repositories) rather than stranding unowned test files.
- Prefer real `tempfile.TemporaryDirectory` fixtures and end-to-end subprocess checks over heavy mocking that tests mock wiring instead of real code.
- Always clean up child processes and process trees on timeout or teardown (`taskkill /T` or job objects on Windows, process groups on Linux).
- In launcher tests on Windows, pass `creationflags=subprocess.CREATE_NO_WINDOW` in Python and `-NoNewWindow` in PowerShell `Start-Process` for console children.
- Keep unit tests fast and avoid flaky wall-clock sleeps; synchronize on files, exit status, or explicit events.
