## Round 1: astra (`gpt-6.2-astra` via `codex`)

- Writer: agy
- Run: 2026-11-21T10:25:52Z
- Candidate: 09646718f6b6ed05c27f4232dbaf006488a98f4c
- Effort: medium
- Lenses: adversarial, integration, source-defect, consistency, quality, optimization
- Lines: 30
- Digest: 54a13c286d950e0b

### Adversarial · needs-attention

1. **P1** `kits/wordpress/templates/scripts/open-dashboard.py:74` exposes the live login ticket in the Windows browser’s process arguments. PowerShell receives the URL on stdin, then passes it to `Start-Process` as an HTTPS URL. I verified that this host’s default HTTPS handler is `ChromeHTML` and its registered command is `chrome.exe --single-argument %1`. Windows substitutes the complete ticket URL for `%1`. To reproduce safely, use a dummy URL with the same PowerShell command and inspect the Chrome process-creation event. On a machine that records process arguments, the real opener puts a redeemable administrator login link in that record.

### Integration · needs-attention

2. **P2** `kits/wordpress/templates/scripts/open-dashboard.py:283` treats a desktop file ID as a literal filename. A browser installed at `applications/vendor/browser.desktop` has the valid ID `vendor-browser.desktop`. Select it as the HTTPS default and run the opener. `xdg-mime` returns the ID, but the opener searches only for `applications/vendor-browser.desktop`, reports that the entry is missing, and drops the ticket. [Desktop Entry Specification, desktop file IDs](https://specifications.freedesktop.org/desktop-entry/latest/file-naming.html#desktop-file-id)

### Source-defect · needs-attention

3. **P2** `kits/wordpress/templates/scripts/open-dashboard.py:288` parses `Exec` with shell quoting and skips the desktop-entry string-unescaping step. For example, a browser entry with `Exec=browser "--profile=Work\sProfile" %u` specifies one argument containing `--profile=Work Profile`. The candidate passes a literal `\s` to the browser, changing the requested profile. This can be reproduced with the existing argv recorder without opening a browser. [Desktop Entry Specification, `Exec` quoting and escaping](https://specifications.freedesktop.org/desktop-entry/latest/exec-variables.html)

### Consistency · needs-attention

4. **P3** `kits/wordpress/templates/scripts/open-dashboard.py:134` accepts `True` as a user ID, although `pinned_user` explicitly rejects booleans. Call `store(pin, valid_digest, True)` with the existing PHP stand-in and it stores user ID `1`. The normal CLI rejects this input earlier, so the defect is confined to the helper’s validation contract.

### Quality · needs-attention

5. **P3** `kits/wordpress/templates/scripts/tests/test_open_dashboard.py:218` measures ticket expiry against the Python caller’s clock. PHP runs on the same host, so the test would also pass if the opener calculated the expiry locally and sent it to a site whose clock differed. Reproduce the coverage gap by substituting a Python-computed expiry for PHP’s `time()` while keeping both processes on the test host. A distinct clock value for the site stand-in would distinguish the two behaviors.

### Optimization · approve

LENS adversarial: findings  
LENS integration: findings  
LENS source-defect: findings  
LENS consistency: findings  
LENS quality: findings  
LENS optimization: clean  
HIGHEST: P1  
OVERALL: needs-attention

## Writer note: shadow audit verdict (D00 T01 §10)

- Finding 1 (P1, `Start-Process` browser command line): already raised in Round 1 (`docs/reviews/07-launchers/D07-T02-s2.md:49`) and answered as accepted by the owner's design in Inputs (`docs/reviews/07-launchers/D07-T02-s2.md:83`); not missed by the chain.
- Findings 2 and 3 (P2, desktop file ID subdirectory lookup and desktop-entry `Exec` string unescaping): real P2 defects missed by the repair-diff chain because `_https_browser` was introduced in the Round 1 fix commit (`f5ae9111`), after Round 1, and neither completion (`plan-delivery`, `record`) nor reconciliations (`repair-adversarial`, `repair-integration` on only the newest repair diff) reviewed `f5ae9111` with `integration` or `source-defect`. Repair filed as `D07 T02 §8` (together with P3 findings 4 and 5) and `D07 T02 §2` reopened with `todo-graph.py unstamp` per `D00 T01 §10`.
