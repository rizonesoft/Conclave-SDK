## Round 1: none

- Writer: claude
- Run: 2026-11-18T13:15:14Z
- Candidate: a592d9758805e7166397e803ceec198160aee236
- Effort: medium
- Lenses: adversarial, integration, source-defect, consistency, quality, optimization
- Skipped: astra (incomplete: no final round verdict line)
- Lines: 13
- Digest: f731f4ecc1861ea0

**P2. The same unattended suite still has the failing 900-second limit.** `test_the_kits_own_tests_pass` runs the template copy with `subprocess.run`. A slow Windows runner can still time out there and leave `pwsh` children alive. The reviewer and WordPress suite calls also use `subprocess.run`. Both have time limits, but neither owns its descendants on timeout or interruption. Route all three through suite-level cleanup and apply the unattended budget to both copies. [Unattended call](D:/Conclave-SDK/tests/test_forge.py:3784) · [Reviewer call](D:/Conclave-SDK/tests/test_forge.py:779) · [WordPress call](D:/Conclave-SDK/tests/test_forge.py:611)

**P2. `_probe` can leave an actual fixture process alive.** On POSIX, `_probe` calls `_kill_tree(proc)` without a descendant tag, so cleanup reaches only the probe’s process group. The unattended suite deliberately starts a child in a new session that sleeps for 300 seconds. If the outer timeout or interrupt arrives while that fixture is active, the child can survive the test runner. The five-second drain bounds the wait for output but cannot terminate that child. The test harness owns this fix. Forge already has a suite runner with stronger cleanup and bounded output capture. [Probe cleanup](D:/Conclave-SDK/forge.py:1934) · [Detached fixture](D:/Conclave-SDK/kits/unattended/templates/scripts/tests/test_run.py:59) · [Suite runner](D:/Conclave-SDK/forge.py:3431)

**Failure reporting and budget.** On an ordinary nonzero exit, the assertion shows the last 2,000 characters of merged stdout and stderr, including unittest’s failure summary. On timeout, `_probe` discards partial output, including anything collected during the drain. The assertion still reports the timeout reason, which is enough to fail the test, but the last diagnostic is lost. The 2,400-second limit is reasonable as a hang watchdog given the 721.269-second focused pass recorded in the commit. I reviewed the code and recorded timing without rerunning the suite. [Assertion](D:/Conclave-SDK/tests/test_forge.py:3815) · [Timeout return](D:/Conclave-SDK/forge.py:1946)

LENS adversarial: findings  
LENS integration: findings  
LENS source-defect: findings  
LENS consistency: findings  
LENS quality: clean  
LENS optimization: clean  
HIGHEST: P2

## Writer note: round 1

Both findings checked against the code and found real; both fixed in 15b2d6e. Every kit suite in tests/test_forge.py now runs through run_kit_suite (its own process group, every process tagged, the whole tree and any tagged straggler ended), and both unattended kit copies get the 2400-second budget. `RunKitSuiteTest` holds it: a fake suite whose child sleeps 300 seconds in a session of its own is ended with that child at a 5-second limit, and the test fails when only the direct child is killed.

## Round 2: astra (`gpt-6.2-astra` via `codex`)

- Writer: claude
- Run: 2026-11-18T13:43:34Z
- Candidate: 66b6fdcc9f36b2f912c2702e2dbf9e27a6620e2f
- Effort: medium
- Lenses: adversarial, integration, source-defect, consistency, quality, optimization
- Lines: 16
- Digest: 7925b0804fa8a476

**P2. A Windows descendant can survive suite teardown.** `run_kit_suite` starts the suite without a Windows job object. If the suite exits after spawning a child with redirected output, `communicate()` returns and `_kill_tagged()` does nothing on Windows. If the child inherits the output pipe, `communicate()` can instead wait the full budget, after which `taskkill /T` targets a suite PID that has already exited. The regression test keeps the suite parent alive until timeout, so it misses both cases. Reuse `forge._run_suite`, which assigns the suspended process to a kill-on-close job before it can spawn children and waits for the suite independently of pipe EOF. [Test helper](D:/Conclave-SDK/tests/test_forge.py:59) · [Regression fixture](D:/Conclave-SDK/tests/test_forge.py:135) · [Shared suite runner](D:/Conclave-SDK/forge.py:3431)

**P2. On POSIX, cancelling the outer `check-all` suite can leave the nested kit suite running.** The helper creates a new process group and replaces the inherited `CONCLAVE_CHECK_ALL_TAG`. If `check-all` kills the outer test process, the nested suite is outside its group and carries a different tag. The outer cleanup misses it, and the killed test process cannot run `end_tree()`. Preserve outer ownership when creating a separately cancellable inner suite. A regression should terminate the outer runner while the inner fixture is active and verify that the fixture exits. [Nested launch](D:/Conclave-SDK/tests/test_forge.py:58) · [Group and tag cleanup](D:/Conclave-SDK/forge.py:1892)

**P3. The helper buffers the entire suite output and can discard it on timeout.** Ordinary failures still report the last 2,000 characters of merged stdout and stderr. If the five-second post-kill drain also times out, `end_tree()` returns `b""`, losing diagnostics already emitted. The shared runner keeps a bounded tail as output arrives, which addresses both issues. [Drain](D:/Conclave-SDK/tests/test_forge.py:65) · [Shared output capture](D:/Conclave-SDK/forge.py:3496)

The test harness owns the timeout change. All four kit-suite calls in `tests/test_forge.py` now use the helper, and both unattended copies get 2,400 seconds. That is reasonable watchdog headroom against the recorded 721.269-second focused pass. A wall-clock limit alone cannot distinguish a hang from a sufficiently slow run. I reviewed both commits and the writer’s recorded results without rerunning the suites.

LENS adversarial: findings
LENS integration: findings
LENS source-defect: findings
LENS consistency: findings
LENS quality: findings
LENS optimization: findings
HIGHEST: P2
OVERALL: needs-attention
