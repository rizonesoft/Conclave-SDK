## Round 1: none

- Writer: claude
- Run: 2026-11-19T21:37:48Z
- Effort: medium
- Lenses: adversarial, integration, source-defect, consistency, quality, optimization
- Skipped: astra (incomplete: no final round verdict line)
- Lines: 25
- Digest: 642a31d503ab889c

**P1 findings**

1. **An interrupted repair can delete a registration, including a concurrent user edit.** [plugins/claude/scripts/register_claude.py:136](/mnt/d/GitHub/Conclave-SDK/plugins/claude/scripts/register_claude.py:136) removes the entry unconditionally, even when the earlier read found it missing. Session A can finish repairing `bunny-net`, then session B can remove A’s working entry and die or time out before adding it back. The same stale read lets a repair delete an `env` block added after line 126. The CLI payload contains only the generated entry with an empty `env`, so the failure here is loss of the stored values. Detaching the worker does not make the two writes atomic.
2. **The guard can inspect one Claude profile while the CLI modifies another.** [plugins/claude/scripts/register_claude.py:151](/mnt/d/GitHub/Conclave-SDK/plugins/claude/scripts/register_claude.py:151) always selects `Path.home() / ".claude.json"`, while the child inherits `CLAUDE_CONFIG_DIR`. If the default registration is missing and the selected profile has a working registration with an `env` block, the default file passes the guard and the CLI removes the selected profile’s entry. Resolve the CLI’s actual configuration target before inspecting or mutating it, or skip automatic repair when the targets differ. [Claude Code settings locations](https://code.claude.com/docs/en/settings)
3. **Opening the repair log can truncate an unrelated file.** [global/claude/hooks/session_drift_check.py:97](/mnt/d/GitHub/Conclave-SDK/global/claude/hooks/session_drift_check.py:97) opens a predictable `repair.log` with `"w"` in a marker directory that can live under shared temporary storage. If that path is a symlink, the first drifting session truncates its target with the user’s permissions before the repair even starts. Concurrent legitimate workers also truncate each other’s diagnostics. An exclusively created per-run log avoids both failures.

**P2 findings**

4. **A literal checkout move disables the hook that promises to repair it.** [plugins/README.md:52](/mnt/d/GitHub/Conclave-SDK/plugins/README.md:52) says the hook re-registers the servers by itself after a move. The deployed hook command also contains an absolute path into the old checkout. Rename that checkout and Claude cannot start the hook. Keep the one-deploy recovery path explicit, or give the hook a stable entry point if unattended recovery from a rename is required.
5. **The hook exceeds its three-second prompt budget.** [global/claude/hooks/session_drift_check.py:168](/mnt/d/GitHub/Conclave-SDK/global/claude/hooks/session_drift_check.py:168) calls `repairable()` synchronously after `bounded_check()` returns, including after a timeout and with `CLAUDE_DRIFT_REPAIR=0`. This rereads the config and can hash bundle sources on the slow drive that caused the timeout. With injected slow reads, `main()` took **4.00 seconds** against its **3.00-second** budget. Return repair eligibility from the bounded check or do that work in the child.
6. **The hook promises success as soon as Python starts.** [global/claude/hooks/session_drift_check.py:149](/mnt/d/GitHub/Conclave-SDK/global/claude/hooks/session_drift_check.py:149) says “no action needed” and promises connection next session. A current bundle in a WSL-native checkout passes `fixable()`, but `expected_entry()` rejects its lack of a Windows drive path. Missing Windows Node or a missing `claude` CLI produces the same misleading message every session. Report that repair was started and where its outcome is recorded.
7. **The manual instruction cannot fix an env-protected entry.** [global/claude/hooks/session_drift_check.py:152](/mnt/d/GitHub/Conclave-SDK/global/claude/hooks/session_drift_check.py:152) directs the user to deploy. For a moved entry with a nonempty `env`, deploy calls the same `fixable()` that excluded it, prints the path mismatch, and leaves it untouched. The hook should identify the protected entry and explain the manual action without printing keys or values. The new test at [global/claude/hooks/test_session_drift_check.py:165](/mnt/d/GitHub/Conclave-SDK/global/claude/hooks/test_session_drift_check.py:165) accepts any `Repair: python` text, including this ineffective instruction.
8. **A plugin error can abort deployment of the other agents.** [global/deploy.py:313](/mnt/d/GitHub/Conclave-SDK/global/deploy.py:313) calls `fixable()` outside the handler, and the handler catches only `SystemExit`. A malformed `.claude.json` raises `JSONDecodeError`, and a hung CLI raises `TimeoutExpired`. Either terminates the default `--agent all` run after Claude files may have changed and before Codex or Antigravity deploys. Record the plugin failure, preserve its failure status, and finish the independent agents.
9. **The registration check accepts paths the launching platform cannot use.** [plugins/claude/scripts/register_claude.py:84](/mnt/d/GitHub/Conclave-SDK/plugins/claude/scripts/register_claude.py:84) treats `C:\Program Files\nodejs\node.exe` and `/mnt/c/Program Files/nodejs/node.exe` as interchangeable commands. A Windows-form command copied into WSL therefore passes the check even though WSL needs the `/mnt/c` executable path. The bundle argument has the converse requirement because Windows Node consumes it. The new repair selector inherits this behavior and leaves the broken entry “clean.” Compare each field against the form required by its consumer.

**Test evidence.** With fixture I/O isolated in memory, the new named-registration assertion failed against `HEAD` and passed against the working tree. It verifies name filtering and timeout arguments. The repair-hook test mocks `Popen`, so it proves launch flags and warning text only. I did not run the full fixture suites or a live Windows or WSL registration.

LENS adversarial: findings  
LENS integration: findings  
LENS source-defect: findings  
LENS consistency: findings  
LENS quality: findings  
LENS optimization: findings  
HIGHEST: P1  
OVERALL: changes requested
