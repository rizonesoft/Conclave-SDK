## Round 1: astra (`gpt-6-astra` via `codex`)

- Writer: claude
- Run: 2026-11-12T07:01:09Z
- Candidate: eb8ba4f027bb65e413dca5e6bbdc3a7d13b52dfc
- Effort: medium
- Lenses: adversarial, integration, source-defect, consistency, quality, optimization
- Lines: 28
- Digest: 4eea6d3450e4906a

**adversarial: approve**

**integration: needs-attention**

1. **P2** `kits/reviewer/templates/scripts/review-dispatch.py:991` (also `scripts/review-dispatch.py:991`): On Linux/WSL, a dead dispatcher does not mean its review has stopped. `run()` starts the reviewer with `start_new_session=True`; its only process-tree cleanup runs in the dispatcher's `finally`, which SIGKILL bypasses. The new takeover therefore launches another review while the original reviewer can still run and consume paid requests.

   Reproduce: launch a section review in WSL, wait until its reviewer starts, send `kill -9` to the dispatcher PID, let the launching shell reap it, then rerun the same section pass. The lock is immediately reclaimed although the original reviewer remains alive. Recovery needs to account for the reviewer process tree before admitting another pass.

**source-defect: approve**

**consistency: approve**

**quality: needs-attention**

2. **P3** `kits/reviewer/templates/scripts/tests/test_three_pass.py:247`: The regression test named “owner was killed” starts Python with `pass`, waits for normal exit, then fabricates its lock. It never kills a dispatcher or starts a reviewer descendant, so it cannot exercise the cancellation lifecycle in finding 1. Reproduce by inspecting or running this test: no kill occurs. Add coverage that kills an actual dispatcher during a bounded review and checks descendant lifetime and subsequent admission.

**optimization: approve**

These findings are based on code inspection. Live WSL reproduction was unavailable because WSL enumeration returned `E_ACCESSDENIED`; I did not run tests that write files.

LENS adversarial: clean
LENS integration: findings
LENS source-defect: clean
LENS consistency: clean
LENS quality: findings
LENS optimization: clean
HIGHEST: P2
OVERALL: needs-attention

- Implemented: P2, on Linux and WSL the lock records the reviewer's process group once it starts, and a lock is free only when the dispatcher and that group are both gone (Windows needs no group: the kill-on-close job ends the reviewer with the dispatcher), in the commit after eb8ba4f
- Implemented: P3, two real-kill tests: SIGKILL of a dispatcher mid-review (POSIX: refused while the reviewer's group lives, admitted once it ends) and TerminateProcess of one (Windows: the job ends the reviewer's child, the lock is taken over), each failing without its part of the fix, in the commit after eb8ba4f

## Round 2: astra (`gpt-6-astra` via `codex`)

- Writer: claude
- Run: 2026-11-12T07:42:09Z
- Candidate: 9f1700b396e52a69c5cd128d92ffe5615365aed0
- Effort: medium
- Lenses: adversarial, integration, source-defect, consistency, quality, optimization
- Lines: 26
- Digest: 5be2cbe4c4e0d5fb

### adversarial: needs-attention

1. **P2** `kits/reviewer/templates/scripts/review-dispatch.py:377` and `:986` (also installed copy): The reviewer starts before its process group is recorded. SIGKILL between `Popen` and `os.replace` leaves a live reviewer behind a three-field lock, which `_lock_owner_dead()` immediately treats as reclaimable. A failed group-record write also logs and continues with this unsafe state. Reproduce on Linux/WSL by killing the dispatcher during that startup interval, then rerunning the same section. Both reviewers can run concurrently. Publication needs a launch handshake that prevents reviewer execution until ownership is safely recorded.

### integration: needs-attention

2. **P2** `kits/reviewer/templates/scripts/review-dispatch.py:1025` and `:1039` (also installed copy): Expiry bypasses the new reviewer-group check. After SIGKILL removes the dispatcher, nothing enforces its timeout on the surviving reviewer. Reproduce on Linux/WSL with a hanging reviewer: kill the dispatcher after group publication, wait past its timeout plus the 300-second grace period, then retry the section. A second reviewer starts while the first remains alive. A read-only mocked probe confirmed that expired-lock admission calls `_lock_owner_dead()` zero times. Known live groups must continue blocking admission after expiry.

### source-defect: approve

### consistency: approve

### quality: approve

### optimization: approve

Review based on candidate inspection and the in-memory probe. Full suites and live process-kill reproductions were not run under the read-only constraint.

LENS adversarial: findings
LENS integration: findings
LENS source-defect: clean
LENS consistency: clean
LENS quality: clean
LENS optimization: clean
HIGHEST: P2
OVERALL: needs-attention

- Implemented: P2 1, on Linux and WSL the reviewer starts behind a gate (a launcher waiting on a pipe) that opens only after its group is in the lock; a dispatcher killed first closes the pipe and the launcher exits without running it, a failed record runs no reviewer, and exec failures still read `could not start` through a close-on-exec status pipe, in the commit after 9f1700b
- Implemented: P2 2, a live recorded group keeps the lock past its expiry; once its dispatcher is dead and the deadline past, the next launch ends the group first, only when its leader's `/proc` start time matches the one recorded, in the commit after 9f1700b
