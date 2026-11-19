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

## Completion review: astra (`gpt-6.2-astra` via `codex`)

- Writer: claude
- Run: 2026-11-19T21:45:25Z
- Candidate: 713ca02da83ea15ad7368d31a64986986561bbff
- Effort: low
- Lenses: plan-delivery, record
- Lines: 27
- Digest: 8846af4600476090

## Part 1. Completeness

1. `present` One deploy from the new checkout updates the hooks and repairs eligible registrations. The instructions distinguish a literal checkout move, which needs that deploy, from later drift a running hook can repair. `plugins/README.md:52`, `global/deploy.py:302`.
2. `present` The helper checks the selected Claude profile, validates the Node command and bundle argument for their respective platforms, and explains how to recover an env-protected entry without printing its values. `plugins/claude/scripts/register_claude.py:54`, `:83`, `:108`. Regression coverage is in `plugins/claude/scripts/test_register_claude.py:154`, `:164`, `:174`, `:239`.
3. `present` The hook reads the repair opt-out, starts a detached worker, creates a fresh log when possible, and distinguishes starting a repair from observing its outcome. The helper reads the persisted registrations back for verification. `global/claude/hooks/session_drift_check.py:106`, `:161`, `:181`, `plugins/claude/scripts/register_claude.py:197`.
4. `present` A malformed config or CLI timeout during plugin repair is recorded as a deployment failure and returns control to the outer deploy. `global/deploy.py:318`.
5. `missing-in-scope` **Round 1 finding 1 remains open for an existing stale registration.** Repair rereads the entry, then issues separate `remove` and `add-json` commands. If the worker stops after removal, the registration is gone. An env edit saved after the reread can also be deleted. The tests cover an edit visible at reread and an entry already missing. Neither covers that final interval. `plugins/claude/scripts/register_claude.py:165`, `:174`, `:177`, `plugins/claude/scripts/test_register_claude.py:290`, `:295`, `:300`.
6. `missing-in-scope` **The three-second hook budget still excludes repair-log setup.** After the bounded survey returns, the prompt thread synchronously creates the log directory and file. A slow marker directory can therefore hold the prompt beyond the budget even though the registration worker itself is detached. `global/claude/hooks/session_drift_check.py:112`, `:115`, `:181`, `:185`.
7. `missing-in-scope` **The live proof exercises addition, while the move requires replacement.** The supplied WSL observation establishes that a removed `bunny-net` entry returned and both servers showed Connected. It does not exercise the existing-stale-entry branch in item 5. The checked-in round record documents fixture evidence and explicitly identifies its live-test limit. The cross-platform suite passes are reported by the submitter. `plugins/claude/scripts/register_claude.py:174`, `docs/reviews/06-global/2026-11-19-mcp-self-heal.md:25`.

## Part 2. Excellence

The comparison is the SDK’s existing manual `register_claude.py` command, which registers both servers through Claude’s user-scope CLI. It is the directly applicable alternative documented in `plugins/README.md:52`.

1. `in-scope` The detached path still charges repair setup to the first prompt. Manual registration incurs **zero repair-log filesystem operations on the prompt thread**. That is the target for automatic repair as well. A delayed log-directory operation should leave the hook within its stated budget. This is the same gap as Part 1 item 6.

## Gap list

1. `missing-in-scope` P1. An interrupted replacement can delete the existing registration, and a concurrent env edit can be lost after the final reread.
2. `missing-in-scope` P2. Synchronous log setup outside the deadline can hold the first prompt beyond three seconds.
3. `missing-in-scope` P2. The reported live run proves missing-entry repair. Closure of the checkout-move claim still needs a run replacing existing stale paths and verifying both connections afterward.
4. `in-scope` P2. Match manual registration’s zero prompt-thread repair-log operations. This shares the fix for gap 2.

LENS plan-delivery: findings  
LENS record: findings  
HIGHEST: P1  
COMPLETION: gaps
