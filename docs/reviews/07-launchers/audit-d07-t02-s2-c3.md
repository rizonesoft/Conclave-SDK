## Round 1: astra (`gpt-6.2-astra` via `codex`)

- Writer: agy
- Run: 2026-11-22T11:41:31Z
- Candidate: d86bc31a3853071a576539bfdc4c3e4f0d1c7f46
- Effort: medium
- Lenses: adversarial, integration, source-defect, consistency, quality, optimization
- Lines: 32
- Digest: af5808d87a6dc475

### Adversarial: needs-attention

1. **P2** `kits/wordpress/templates/scripts/tests/test_open_dashboard.py:726` skips browser cleanup once the original process exits, even if its children are still running. **Path:** A Linux browser launcher can fork a child in its process group and exit before test teardown. **Evidence:** traced. Line 795 calls `_kill_browser_tree`, but line 726 checks the leader’s `poll()` before reaching `killpg` at line 733. A launcher that starts a sleeping child and exits reproduces the orphan. The test at line 723 exercises the exited-leader case without checking for surviving children.
2. **P3** `kits/wordpress/templates/scripts/open-dashboard.py:84` prunes only `open-*.html`. If PowerShell stops between `WriteAllText` and `Move` at line 89, the `.open-*.tmp` file survives every subsequent launch. Linux has the same gap between lines 211 and 216. The ticket expires, but the file containing the login URL remains on disk.

### Integration: needs-attention

1. **P2** `kits/wordpress/templates/scripts/open-dashboard.py:53` can store a ticket that its own plugin rejects on type alone. **Path:** The user-edited pin accepts any positive Python integer as `wordpress_user_id`. **Evidence:** traced. Set it to `9223372036854775808` on a 64-bit PHP site. `scripts/lib/wp_site.py:77` accepts it, and `open-dashboard.py:171` inserts it as a PHP numeric literal. PHP represents it as a float. The read-back at line 57 compares equal to the same float, so `--check` can report success. The plugin requires an integer at `kits/wordpress/templates/tools/ticket-login/conclave-ticket-login.php:85` and returns 403 on redemption.
2. **P2** `kits/wordpress/templates/scripts/open-dashboard.py:92` treats a per-user `UserChoice` entry as the only way Windows can have a default HTTPS browser. **Path:** A Windows profile can use a machine-default HTTPS handler without a per-user override. **Evidence:** traced. Run the WSL opener on such a profile. The registry read uses `-ErrorAction Stop`, so execution reaches the failure handler at line 107 before starting the browser. The headless test substitutes a literal command for this lookup at `kits/wordpress/templates/scripts/tests/test_open_dashboard.py:839`. Windows distinguishes the effective default from the per-user association. [Microsoft’s association lookup contract](https://learn.microsoft.com/en-us/windows/win32/api/shobjidl_core/nf-shobjidl_core-iapplicationassociationregistration-querycurrentdefault)

### Source-defect: needs-attention

1. **P2** `kits/wordpress/templates/scripts/open-dashboard.py:424` copies child-process output into stderr despite the fixed-message requirement at `todo/07-launchers/TODO-02-wordpress-dashboard-login.md:120`. **Path:** `xdg-mime` returns a stale desktop ID after a browser is removed. **Evidence:** ran a read-only `python -B -` probe against the pinned Git blob, with `xdg-mime` returning `sample-diagnostic.desktop` and desktop lookup returning no match. `_failed()` produced `the browser's desktop entry sample-diagnostic.desktop is in no applications folder`. Line 518 passes that text through verbatim. This demonstrates disclosure of the child-provided ID, not a ticket disclosure.

### Consistency: needs-attention

1. **P2** `kits/wordpress/templates/scripts/tests/test_open_dashboard.py:688` identifies processes to terminate with PowerShell wildcard matching, while the repository requires cleanup of the test-owned process tree. **Path:** A Windows temp directory can legally contain square brackets, for example `C:\Temp\[work]`. **Evidence:** traced. `_windows_temp_profile` builds the profile under that directory at line 740. Line 685 escapes apostrophes only. Both the kill query at line 688 and the survivor check at line 691 interpret `[work]` as a wildcard character class. Both can miss the literal profile path, so cleanup reports success with the test browser still running.

### Quality: needs-attention

1. **P2** `kits/wordpress/templates/scripts/tests/test_open_dashboard.py:675` uses a single-threaded HTTP server with no accepted-socket timeout, making the headless smoke test’s 15-second deadline ineffective during teardown. **Path:** A browser opens a speculative loopback connection and leaves it idle. **Evidence:** traced. The server can block reading that connection before servicing the redirect request. The assertion at line 792 times out, but the cleanup registered at line 680 then waits in `server.shutdown()` for the blocked handler. Reproduce with an idle loopback connection held open while requesting shutdown.

### Optimization: approve

LENS adversarial: findings  
LENS integration: findings  
LENS source-defect: findings  
LENS consistency: findings  
LENS quality: findings  
LENS optimization: clean  
HIGHEST: P2  
OVERALL: needs-attention

## Writer note: shadow audit verdict (D00 T01 §10)

- Run on 2026-11-22 as a new full-lens shadow audit of Row 3 (`D07 T02 §2` chain 3, base `bacac1f2`, candidate `d86bc31a`, stamped `9015bf1c`).
- Highest reported grade: `P2`; highest missed grade: `P2` (6 real P2 defects and 1 P3 missed by the repair-diff chain: `_kill_browser_tree` skips `killpg` after leader exits, 64-bit `wordpress_user_id` float coercion in PHP, Windows machine-default HTTPS lookup without `UserChoice`, `xdg-mime` desktop ID echoed in stderr, PowerShell wildcard bracket matching in browser cleanup, single-threaded HTTP server shutdown hang, and unpruned `.open-*.tmp` files).
- Repair filed as `D07 T02 §9` and `D07 T02 §2` reopened with `todo-graph.py unstamp` per `D00 T01 §10`.
