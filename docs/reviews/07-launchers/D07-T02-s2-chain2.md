## Plan review: astra (`gpt-6.2-astra` via `codex`)

- Writer: agy
- Run: 2026-11-21T11:23:27Z
- Candidate: 1c06436dd095b930a9923f28969db454ec5b0558
- Effort: medium
- Lenses: plan, simplest
- Lines: 17
- Digest: 96eb5a42343272c3

1. **P1, lines 115 and 122.** Three of the four browser repairs added by the re-plan can be omitted while the checkpoint stays green. Add regressions that make an I/O error in each lookup helper produce a refusal with zero launches, resolve `Work Apps-org.example.Browser.desktop` to the intended command, and refuse `Exec=browser %u %F` before launch. Keep the `ENAMETOOLONG` fallback and relative-root decoy as independent cases. Reverting each repair must fail its own test.

2. **P1, lines 106, 115 and 122.** The build order promises to open a browser on each supported system, but the checkpoint replaces both launch mechanisms with recorders. It cannot detect a Linux browser that starts but cannot read the redirect page, or a Windows URL association that fails to open it. §7 exercises HTTP redemption directly and does not cover this handoff. Add a WSL and Linux smoke check using a harmless loopback URL, with success measured by the destination receiving the browser request. A real ticket is unnecessary.

3. **P2, lines 115, 116 and 118.** Linux treats a successful `Popen` as launch success. A configured browser can start and immediately exit nonzero, for example in a shell without a graphical display. The opener then reports success and leaves the ticket live. Define how to detect an immediate startup failure without waiting for a long-running browser to close. Test with a child that actually exits nonzero and assert a fixed error, nonzero opener exit and removal of this run’s ticket.

4. **P2, lines 114 and 117.** `drop` distinguishes `dropped`, `absent`, `gone` and `not ours`, but `--check` prints that it removed the ticket for all four. Two overlapping runs can therefore produce a successful removal report when the second run replaced the first ticket. Require `dropped` for the claimed store-and-remove proof. Exercise replacement between store and drop through `main --check`, assert that the newer ticket survives, and check the diagnostic and exit status.

5. **P2, lines 95, 108 and 115.** The WSL argument-secrecy test stops at PowerShell. Passing the link on PowerShell’s stdin proves that its own arguments are clean, but `Start-Process -FilePath $u` hands the URL to the registered Windows handler. Test a cold browser launch with a disposable marker and inspect the receiving handler’s arguments. If the marker appears there, use a private redirect page for the Windows handoff too and pass only its path.

6. **P3, lines 95 and 103–106, simplest lens.** Line 95 still directs Linux to `xdg-open`, which line 115 explicitly replaced after it selected an HTML editor. Remove that obsolete instruction. The broad “tests that need no PHP pass” criterion also adds no evidence beyond the specific checks below it. Keep one Linux dispatch description and one checkpoint that names the observable outcomes.

LENS plan: findings  
LENS simplest: findings  
HIGHEST: P1  
PLAN: gaps  
OVERALL: needs-attention

- Planned: gap 1, dedicated regression tests for `EIO` in each lookup helper, `Work Apps-org.example.Browser.desktop`, `Exec=browser %u %F`, and separate `ENAMETOOLONG` and relative-root tests, in commit `todo: D07 T02 §2 plan review gaps planned`
- Planned: gap 2, Build order item 2 aligned to recorders plus real child-process exit check (tests never open a live desktop browser window), in commit `todo: D07 T02 §2 plan review gaps planned`
- Planned: gap 3, detect immediate non-zero Linux browser exit via `proc.wait(timeout=0.3)` and prove with a real failing child triggering `drop`, in commit `todo: D07 T02 §2 plan review gaps planned`
- Planned: gap 4, require `drop == "dropped"` for `--check` success and test replacement (`not ours`) exiting 1 with newer ticket preserved, in commit `todo: D07 T02 §2 plan review gaps planned`
- Planned: gap 5, documented that WSL keeps Inputs' PowerShell stdin -> `Start-Process` design (one-use ticket consumed before comparison on first request), in commit `todo: D07 T02 §2 plan review gaps planned`
- Planned: gap 6, removed obsolete `xdg-open` text from section header and tightened Build order item 1, in commit `todo: D07 T02 §2 plan review gaps planned`

## Round 1: astra (`gpt-6.2-astra` via `codex`)

- Writer: agy
- Run: 2026-11-21T11:33:10Z
- Candidate: 4e74a8db188a3f53f6277d605d665e3facb35e52
- Effort: medium
- Lenses: adversarial, integration, source-defect, consistency, quality, optimization
- Lines: 29
- Digest: ebab00d428461f5d

### adversarial: needs-attention

1. **P3** `kits/wordpress/templates/scripts/open-dashboard.py:190` accepts DEL (`U+007F`) and C1 control characters despite the section’s requirement to reject control characters. For example, `DESKTOP_ID.fullmatch("bad\u0085name.desktop")` succeeds. If lookup misses, the refusal copies that control character into stderr.

### integration: needs-attention

1. **P1** `kits/wordpress/templates/scripts/open-dashboard.py:238` and `:247` can launch the wrong browser after a filesystem error. On Python 3.14, `Path.is_file()` and `Path.is_dir()` suppress `OSError` and return `False`, so the new handlers never see `EACCES` or `EIO`. To reproduce on Linux, configure `browser.desktop` in both the user and system applications directories, then run the opener as an ordinary user without search permission on the user applications directory. Lookup falls through to the system entry and hands it the login page. Use `stat()` to distinguish a missing path from an indeterminate lookup. [Python 3.14 path query behavior](https://docs.python.org/3.14/library/pathlib.html#querying-file-type-and-status)

### source-defect: needs-attention

1. **P2** `kits/wordpress/templates/scripts/open-dashboard.py:368` strips significant leading spaces from the desktop-file ID. On Linux, a directory named ` Work Apps` containing `org.example.Browser.desktop` produces the ID ` Work Apps-org.example.Browser.desktop`. When `xdg-mime` returns that ID followed by a newline, `.strip()` also removes the initial space. Lookup then fails or selects a different entry under `Work Apps`. Remove only the command’s line terminator before validating the ID. [Desktop Entry Specification, desktop file ID](https://specifications.freedesktop.org/desktop-entry/latest/file-naming.html#desktop-file-id)

### consistency: approve

### quality: needs-attention

1. **P3** `kits/wordpress/templates/scripts/tests/test_open_dashboard.py:749` injects `EIO` by replacing the very `Path` predicates whose error handling matters. This makes the regression pass on Python 3.14 while the permission-denied reproduction above still launches the fallback. Exercise the filesystem error below the predicate or use an inaccessible higher-priority directory in an unprivileged Linux test.
2. **P3** `kits/wordpress/templates/scripts/tests/test_open_dashboard.py:345` cannot distinguish a child exiting nonzero from no child starting at all. Replace `sys.executable` in the fixture’s `Exec` line with a nonexistent executable and the same exit code, stderr, and ticket-removal assertions still pass. Assert that the real child started and that its exit status was observed.

### optimization: approve

LENS adversarial: findings  
LENS integration: findings  
LENS source-defect: findings  
LENS consistency: clean  
LENS quality: findings  
LENS optimization: clean  
HIGHEST: P1  
OVERALL: needs-attention

## Writer note: round 1 answered

- Fixed: integration P1 (use `os.stat` + `stat.S_ISREG`/`stat.S_ISDIR` in `_is_file_or_miss`/`_is_dir_or_miss` so `EIO`/`EACCES` never get swallowed by Python 3.14's `Path.is_file`/`Path.is_dir`), source-defect P2 (strip only `\r\n` from `xdg-mime` stdout so leading spaces in nested desktop IDs survive), adversarial P3 (reject DEL `U+007F` and C1 `U+0080..U+009F` in `DESKTOP_ID`), quality P3 #1 (inject `EIO`/`EACCES`/`ENAMETOOLONG` at `os.stat` below the predicates), and quality P3 #2 (prove the real failing child process actually ran via a marker file before exiting 1).

## Completion review: astra (`gpt-6.2-astra` via `codex`)

- Writer: agy
- Run: 2026-11-21T11:38:13Z
- Candidate: bacac1f25f94d61bcbf89be0daf2d7b34b0c2861
- Effort: low
- Lenses: plan-delivery, record
- Lines: 28
- Digest: 1172b873142ef75f

## Part 1. Completeness

1. **present**. The CLI entry point, scratch-project `--help`, fresh token and digest, URL validation, pinned-user selection, native Windows refusal and invalid-pin refusals have executable coverage in `test_open_dashboard.py:129`, `:135`, `:153`, `:159`, `:178`, `:194`, `:204` and `:835`.
2. **present**. Pinned SSH selects the site before `eval` and sends the digest on stdin. The PHP harness covers storage, site-clock expiry, read-back, missing plugin, failed reads and deletion that preserves a newer ticket. See `open-dashboard.py:125` and `test_open_dashboard.py:215`, `:244`, `:260`, `:270` and `:282`.
3. **present**. The default command and `--check` have distinct success criteria. The replacement test verifies that `--check` exits unsuccessfully when another run replaces its ticket. See `test_open_dashboard.py:296`, `:311` and `:320`.
4. **present**. WSL dispatch, Linux browser selection, private redirect pages, stale-page removal and host-specific refusals have recorder coverage. The immediate-exit test also verifies that a real child ran, exited unsuccessfully and triggered ticket removal. See `test_open_dashboard.py:337`, `:529`, `:544`, `:563`, `:683`, `:707`, `:729`, `:758`, `:783` and `:799`.
5. **present**. Browser failure, a lost SSH reply, interruption, unconfirmed cleanup and exceptions containing sensitive text have tests. Cross-language constant agreement belongs to `test_ticket_login.py`, as specified by the §2 checkpoint. See `test_open_dashboard.py:379`, `:391`, `:399`, `:420`, `:448` and `:464`. These are source-coverage findings. I did not rerun the suites.
6. **missing-in-scope, P1**. No cited run proves that a successful invocation reaches a browser destination on either supported host. The plan review requested that observation. Its disposition substituted recorders and a child that exits **unsuccessfully**. Section 7 exercises HTTP redemption directly and does not own the browser handoff. Record one harmless loopback request received through the configured browser on WSL and one on Linux. This can be an attended check without opening windows during automated tests. See `docs/reviews/07-launchers/D07-T02-s2.md:13` and `:30`.
7. **missing-in-scope, P2**. The WSL test establishes that the URL is absent from PowerShell’s arguments. It stops before the registered Windows handler receives the URL from `Start-Process`. The recorded disposition cites one-use redemption, which supplies no evidence about arguments before redemption. Verify a cold launch with a disposable marker and require zero occurrences in the receiving handler’s arguments. See `open-dashboard.py:441`, `test_open_dashboard.py:529` and `docs/reviews/07-launchers/D07-T02-s2.md:19` and `:33`.
8. **missing-in-scope, P2**. Failure recovery can tell the user “the ticket was removed from the site” when the remote operation returned `absent`, `gone` or `not ours`. This is reachable after a lost store reply or overlapping launches. `drop()` preserves the distinction, but `_clean_up()` discards it. Require a removal claim only for `dropped`, and exercise all four replies through cleanup. See `open-dashboard.py:148` and `:482`.

## Part 2. Excellence

The named alternative is the host’s one-click dashboard login, which opens the dashboard from the hosting account. The governing plan records the owner’s choice to retain the SSH-backed one-use ticket. It supplies no comparative timing or success measurements. See `docs/plans/2026-11-11-sdk-audit-and-roadmap.md:123`.

1. **in-scope, P1**. The comparison lacks a verified successful dashboard handoff for the candidate’s common action. The measurable target is one invocation and one observed browser request on each supported host, with no manual URL transfer. This is the same evidence gap as Part 1 item 6. No separate speed or accessibility finding follows from the two assigned lenses.

## Gap list

1. **missing-in-scope, P1**. Successful browser delivery lacks an observed destination request on WSL and Linux.
2. **missing-in-scope, P2**. WSL argument-secrecy evidence ends before the registered Windows handler.
3. **missing-in-scope, P2**. Failure cleanup reports a confirmed deletion for three outcomes that do not establish one.
4. **in-scope, P1**. The common-action comparison needs one observed browser request per host from a single invocation, the same proof as gap 1.

LENS plan-delivery: findings  
LENS record: findings  
HIGHEST: P1  
COMPLETION: gaps
