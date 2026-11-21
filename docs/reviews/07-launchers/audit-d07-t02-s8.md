## Round 1: astra (`gpt-6.2-astra` via `codex`)

- Writer: agy
- Run: 2026-11-21T11:17:42Z
- Candidate: 273fea94e9b11fd30165c98871fe0130162407de
- Effort: medium
- Lenses: adversarial, integration, source-defect, consistency, quality, optimization
- Lines: 40
- Digest: 25611f4e61413cb2

### adversarial

**Needs-attention**

1. **P2** `kits/wordpress/templates/scripts/open-dashboard.py:242` treats a disk I/O error as a lookup miss. A user can have a browser-profile override in `~/.local/share/applications/browser.desktop` and a different command under the same ID in `/usr/share/applications/`. I reproduced a read failure by making `is_file()` raise `EIO` for the user entry. The pinned resolver selected the system entry, so the dashboard can open in a different browser profile. Lookup should propagate an indeterminate I/O failure and let the existing failure path revoke the ticket.

### integration

**Needs-attention**

2. **P2** `kits/wordpress/templates/scripts/open-dashboard.py:357` rejects valid IDs produced from nested directories before the new resolver sees them. Install `org.example.Browser.desktop` under `applications/Work Apps/` and have `xdg-mime` return `Work Apps-org.example.Browser.desktop`. The space comes from the directory name. The ID guard rejects it and reports that no HTTPS browser is set. The specification derives the ID from the entire relative path by replacing slashes with hyphens. [Desktop Entry Specification, file naming](https://specifications.freedesktop.org/desktop-entry/latest/file-naming.html)

### source-defect

**Needs-attention**

3. **P2** `kits/wordpress/templates/scripts/open-dashboard.py:400` accepts multiple file or URL field codes in one `Exec` command. I reproduced this with `Exec=browser %u %F`. The pinned code supplied the same redirect page twice, once as a URI and once as a path. A browser opening both arguments can attempt to redeem the one-use ticket twice. The specification permits at most one such field code across the entire command. [Desktop Entry Specification, Exec key](https://specifications.freedesktop.org/desktop-entry/latest/exec-variables.html)

### consistency

**Approve.**

### quality

**Needs-attention**

4. **P3** `kits/wordpress/templates/scripts/tests/test_open_dashboard.py:639` masks the relative-root defect the test claims to catch. Its `ENAMETOOLONG` mock matches every file named `vendor-browser.desktop`, including the decoy in the working directory. Let lookup search `.` first and the mock still hides the decoy, so the expected system browser still wins. Separate the relative-root case from the overlong-name case so admitting `.` makes the regression test fail.

### optimization

**Approve.**

LENS adversarial: findings  
LENS integration: findings  
LENS source-defect: findings  
LENS consistency: clean  
LENS quality: findings  
LENS optimization: clean  
HIGHEST: P2  
OVERALL: needs-attention

## Writer note: shadow audit verdict (D00 T01 §10)

- Finding 1 (P2, `except OSError:` swallowing `EIO`) and Finding 4 (P3, `ENAMETOOLONG` mock masking the relative-root decoy) were both introduced in Round 1's fix commit (`4d6a58a5`), confirming the exact same repair-diff blind spot seen on row 1 (`D07 T02 §2`): code added in Round 1 fixes is never seen by `adversarial`, `integration`, `source-defect` or `quality` under the repair-diff pin.
- Findings 2 (P2, space in nested desktop directory ID) and 3 (P2, refusing multiple `%u`/`%U`/`%f`/`%F` codes in one `Exec=`) are real Desktop Entry Specification edge cases in `_https_browser`.
- All four fixes are taken directly into the already-reopened `D07 T02 §2` (`todo/07-launchers/TODO-02-wordpress-dashboard-login.md`) during its re-plan chain so `open-dashboard.py` closes the whole class cleanly without spawning a third section.
