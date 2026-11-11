## Round 1: astra (`gpt-6-astra` via `codex`)

- Writer: claude
- Run: 2026-11-11T18:55:31Z
- Candidate: d80d14e4b79a27a44c8d08f5cdf488f231c580de
- Effort: medium
- Lenses: adversarial, integration, source-defect, consistency, quality, optimization
- Lines: 36
- Digest: 32cb6fe713195610

### adversarial: needs-attention

1. **P1, `scripts/start-run.ps1:39`**: Unconditional takeover instructions defeat the guard during simultaneous launches. Reproduce by starting the launcher in two windows before either Claude session acquires its guard. Both pass the check at line 93 without prompting; once one acquires ownership, the other is explicitly instructed to use `--handover`. The guard permits that replacement without terminating the first writer. Restrict takeover authorization to an existing guard explicitly acknowledged by the operator, and refuse a newly acquired competing guard.

2. **P2, `scripts/start-run.ps1:45`**: `-DryRun` still writes when combined with `-InstallShortcut`. Reproduce with `pwsh scripts/start-run.ps1 -InstallShortcut -DryRun`: execution reaches `.Save()` and exits before checking `$DryRun`, creating or overwriting the desktop shortcut despite the documented no-change contract.

### integration: needs-attention

3. **P2, `scripts/start-run.ps1:94`**: The guard reader uses `.session`, but `scripts/campaign_guard.py:205` writes `session_id`. With a normally acquired guard, launching again prints `a run guard is held by session ` without identifying the owner whose activity the operator must assess. Reading a representative guard confirmed the empty result. Read `session_id` and handle missing identity explicitly.

### source-defect: approve

No additional findings.

### consistency: approve

No additional findings.

### quality: needs-attention

4. **P3, `tests/test_start_run.py:34`**: The argument-contract test examines a manually formatted dry-run string, never arguments received by a child process. Likewise, the sentinel assertion at line 32 returns before token handling executes. Reproduce the coverage gap by inspecting the early return at launcher line 65: these tests cannot detect broken invocation or token disclosure in the actual launch path. Use a harmless child stub to check received arguments and authentication-path output.

The four selected dry-run tests passed. Shortcut creation and live Claude execution were not run, preserving the read-only review.

### optimization: approve

No findings.

LENS adversarial: findings
LENS integration: findings
LENS source-defect: clean
LENS consistency: clean
LENS quality: findings
LENS optimization: clean
HIGHEST: P1
OVERALL: needs-attention

## Writer note: round 1 findings and gates

All four findings were verified against the code and fixed in the commit that follows this note.

1. P1, takeover during simultaneous launches: the handover instruction is no longer in the goal by default. The launcher reads the guard before starting. With no guard held, the session is told never to use `--handover` and to start nothing if it finds another session's guard. With a guard held, the session may take over that one named session only, after the operator presses Enter or passes `-TakeOver`. A guard file that names no valid session is never taken over.
2. P2, `-InstallShortcut -DryRun` wrote the shortcut: a dry run now prints the link and target and writes nothing.
3. P2, the guard's owner was read from `.session`: it is read from `session_id`, checked against a strict pattern before it is shown or put in the goal.
4. P3, tests never exercised the launch path: the tests now start a stand-in for claude through `-ClaudePath` and check the six arguments it received, the folder it ran in and that the token reached it, with the token read from a test registry key in a window that lacks it. The token never appears in the launcher's output.

Gates: `python -m unittest tests.test_start_run` ran 9 tests, OK. `python -m unittest discover -s tests` ran 342 tests in 100.158s, OK (skipped=95).
