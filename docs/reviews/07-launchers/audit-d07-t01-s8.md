## Round 1: astra (`gpt-6.2-astra` via `codex`)

- Writer: agy
- Run: 2026-11-22T11:36:58Z
- Candidate: c9158e4ed64d780df2fd4c3282c31a358af24fcf
- Effort: medium
- Lenses: adversarial, integration, source-defect, consistency, quality, optimization
- Lines: 45
- Digest: 0db23e948213ec0a

## adversarial

**needs-attention**

1. **P2** `kits/launchers/templates/scripts/project-shortcuts.ps1:106` compares ownership marks with `-ceq`, which treats some distinct Unicode paths as equal. Inspection can report another project’s shortcuts, and removal uses the same comparison at line 125. **Path:** Two WSL project directories on the same distro have visually identical names, one with a composed `é` and one with `e` followed by a combining accent. They share a Windows shortcut directory. **Evidence:** ran `'café' -ceq 'café'` in PowerShell 7 and observed `True`. Lines 64 and 80 embed the Linux path in the ownership mark. With different shortcut titles, both projects’ links can coexist and pass either project’s ownership check. Use ordinal equality for these marks.

## integration

**needs-attention**

2. **P1** `kits/launchers/templates/scripts/project-shortcuts.ps1:124` suppresses shortcut enumeration errors during removal. It can leave all links in place, delete their icons, and exit successfully. **Path:** An operator runs the documented `-Remove` command against a redirected Desktop whose directory listing is denied, while the local icon directory remains accessible. **Evidence:** traced `Get-Owned` at lines 122–125 into the removal branch at lines 130–135. The ignored enumeration error yields an empty link list, icon deletion proceeds, and the branch exits 0. Inspection already distinguishes an unreadable directory from an empty one at lines 93–99.
3. **P2** `kits/launchers/templates/scripts/project-shortcuts.ps1:101` checks the C# reader using `-LiteralPath` but loads it using wildcard-aware `Add-Type -Path`. **Path:** A project is installed in a valid Windows directory such as `C:\work\[archive]\shop`. **Evidence:** traced lines 89–101. The literal existence check succeeds, then `Add-Type` interprets the brackets as a character class. Run the documented `-Inspect` from that project in a fresh `pwsh` process to reproduce the read-back failure. `Add-Type` supports `-LiteralPath`.

## source-defect

**needs-attention**

4. **P2** `kits/launchers/templates/docs/launchers.md:14` describes valid Windows filename characters as the title boundary but omits a known limitation of this candidate. A valid title can pass `show` and still fail when shortcuts are saved. **Path:** An operator on a Western Windows code page chooses a project title containing Japanese characters. **Evidence:** traced the documented title rule to `todo/07-launchers/TODO-01-project-launchers.md:329`, which records the observed save failure and the empty ownership description on read-back. The Unicode writer repair belongs to §9. The §8 operator page should disclose the limitation while that repair is pending.
5. **P3** `kits/launchers/templates/docs/launchers.md:88` gives incomplete diagnosis for label refusals. For example, `Claude!` satisfies the listed rules for a single declared link, but its icon slug collides with the reserved agent slug `claude`. A punctuation-only label also produces an empty slug. Both refusals are explicit in `kits/launchers/templates/scripts/lib/launchers.py:217–223`.

## consistency

**needs-attention**

6. **P2** `kits/launchers/templates/scripts/project-shortcuts.ps1:70` derives Windows ownership from the spelling returned by `Resolve-Path`. The sibling unattended launcher expands an existing path’s 8.3 spelling before deriving identity. **Path:** On an 8.3-enabled volume, automation creates shortcuts through the short project path and the operator later inspects them through the long path. **Evidence:** traced lines 67–80 and 106. A spelling difference changes the mark, so inspection exits successfully with no matching links. `kits/unattended/templates/scripts/unattended-shortcut.ps1:159–160` handles this exact case using the kit’s existing `ShellPath.Long` helper.
7. **P2** `tests/test_forge.py:4386` runs the documented shell command with a timeout that kills only the immediate process. **Path:** The Windows example starts Python under PowerShell. If Python hangs, the 30-second timeout can leave it running after the test exits. **Evidence:** traced the example at `kits/launchers/templates/docs/launchers.md:38` through `run_cmd` at `tests/test_forge.py:4382–4391`. The Windows branch uses `subprocess.run` directly, bypassing the tree cleanup implemented for the adjacent shortcut test.

## quality

**needs-attention**

8. **P2** `tests/test_forge.py:4471` drops continuation lines from PowerShell’s formatted output. A valid long `IconPath` can therefore fail the Windows acceptance test. **Path:** The test runs under a long user-profile or `TEMP` path and `Format-List` wraps the icon filename. **Evidence:** traced `Format-List` at `kits/launchers/templates/scripts/project-shortcuts.ps1:118` to the parser at `tests/test_forge.py:4461–4476`. The parser retains only lines beginning with a field name and colon. The assertion at lines 4537–4539 then checks the truncated path on disk. Reproduce by parsing a record with the icon filename on an indented continuation line.

## optimization

**approve**

LENS adversarial: findings  
LENS integration: findings  
LENS source-defect: findings  
LENS consistency: findings  
LENS quality: findings  
LENS optimization: clean  
HIGHEST: P1  
OVERALL: needs-attention

## Writer note: shadow audit verdict (D00 T01 §10)

- Run on 2026-11-22 as a new full-lens shadow audit of Row 5 (`D07 T01 §8`, base `7bf101fd`, candidate `c9158e4e`, stamped `15d3ee85`).
- Highest reported grade: `P1`; highest missed grade: `P1` at `c9158e4e` (1 real P1, 6 real P2s, and 1 P3 missed by the repair-diff chain at `c9158e4e`).
- Verified against HEAD: findings 2 (`Get-Owned` directory enumeration error suppression, P1), 3 (`Add-Type -Path` bracket wildcard, P2), and 4 (Unicode title save limitation, P2) were subsequently fixed by `D07 T01 §9` (`1a843490`/`7211c4c2`). Findings 1 (`-ceq` Unicode normalization on WSL marks, P2), 6 (`Resolve-Path` vs 8.3 `ShellPath.Long`, P2), 7 (`subprocess.run` timeout without tree kill in `tests/test_forge.py:4386`, P2), 8 (`Format-List` continuation lines in `tests/test_forge.py:4471`, P2), and 5 (`launchers.md:88` slug collision docs, P3) remain open on HEAD.
- Remaining open repairs filed as `D07 T01 §10` and `D07 T01 §8` reopened with `todo-graph.py unstamp` per `D00 T01 §10`.
