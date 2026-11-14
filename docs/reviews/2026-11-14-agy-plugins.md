## Round 1: astra (`gpt-6-astra` via `codex`)

- Writer: agy
- Run: 2026-11-14T11:30:21Z
- Candidate: 268c8ea58216ad1f8004723a6cd1c3b425c6255a
- Effort: medium
- Lenses: adversarial, integration, source-defect, consistency, quality, optimization
- Lines: 38
- Digest: d805aaca079433cf

### adversarial: needs-attention

1. **P1** `plugins/agy/powertools/hooks/powertools_hook.py:363`: Quoting an option bypasses the catastrophic-command guard. Harmless parser probes confirmed that `git push "--force" origin main` returns `None`, although Git receives the same force option as the blocked unquoted command. `bash -lc "git push --force origin main"` also bypasses detection because shell wrappers are only inspected inside the WSL branch. Reproduce by passing these strings to `catastrophic_command`, or as `run_command.CommandLine`; the hook allows them without confirmation.

2. **P1** `plugins/agy/craft/skills/docx/scripts/office/helpers/__init__.py:79`: `safe_extract` checks paths and symlinks but imposes no member-count or expanded-byte limit. An externally supplied DOCX containing highly compressed, oversized XML or media is extracted completely before validation, potentially filling the temporary drive. Reproduce by passing such a document to `scripts/office/validate.py`. The PPTX and XLSX copies contain the same defect. Enforce extraction budgets before and during decompression.

### integration: needs-attention

3. **P2** `plugins/agy/craft/skills/xlsx/scripts/recalc.py:349`: Ordinary text containing an Excel error name is reported as a calculation error. Both scanner paths use substring matching on string cells. For example, a workbook instruction cell containing `Use IFERROR to handle #N/A` produces an error finding despite containing no failing formula. The read-only classifier probe confirmed this, including the false positive `No #REF! errors remain`. Reproduce by recalculating a workbook containing either instruction. Distinguish error-valued cells from explanatory text.

4. **P2** `plugins/agy/craft/skills/xlsx/scripts/recalc.py:217`: The Windows timeout kills only the immediate `soffice` process, not its `soffice.bin` child. A slow or hung workbook can therefore leave LibreOffice running after the command reports failure, retaining locks or subsequently modifying the workbook. Reproduce on Windows with a workbook whose recalculation exceeds the supplied timeout, then inspect the remaining LibreOffice processes. Terminate and await the entire owned process tree before returning or cleaning its profile.

### source-defect: approve

No additional findings.

### consistency: needs-attention

5. **P1** `plugins/agy/craft/skills/pdf/scripts/fill_fillable_fields.py:51`: PDF output violates the repository’s atomic-write requirement. Opening the destination with `"wb"` immediately truncates an existing file; a disk-full error or interrupted write then destroys the previous output and leaves a partial PDF. Reproduce by rerunning the documented form-filling command against an existing output on a volume without sufficient free space. Write to a temporary file beside the destination, then replace it only after successful completion.

### quality: approve

No additional findings.

### optimization: approve

No additional findings.

The review used static inspection and read-only probes. Filesystem-writing tests were not run in this read-only environment.

LENS adversarial: findings
LENS integration: findings
LENS source-defect: clean
LENS consistency: findings
LENS quality: clean
LENS optimization: clean
HIGHEST: P1
OVERALL: needs-attention

- Implemented: P1 (finding 1), catastrophic_command now checks quoted options after command/subcommand lookup (keeping env-assignment quote rules and -- end-of-options handling) and recursively unwraps sudo, env, wsl, bash/sh/zsh, pwsh/powershell, and cmd wrapper invocations with tests in tests/test_agy_plugins.py
- Implemented: P1 (finding 2), safe_extract in docx, pptx, and xlsx office/helpers/__init__.py enforces MAX_ARCHIVE_ENTRIES, MAX_ARCHIVE_BYTES, and MAX_MEMBER_BYTES before and during chunked extraction, cleaning up partial targets on overflow with tests in tests/test_agy_plugins.py
- Implemented: P2 (finding 3), xlsx/scripts/recalc.py restricts error detection to t="e" XML cells and openpyxl data_type=="e" cells with bounded archive reads instead of scanning shared or inline explanatory strings, with tests in tests/test_agy_plugins.py
- Implemented: P2 (finding 4), office/soffice.py across docx, pptx, and xlsx terminates and reaps the full LibreOffice process tree (taskkill /T /F on Windows, killpg SIGKILL on POSIX) before temporary profile cleanup on timeout, and xlsx/recalc.py plus docx/accept_changes.py now route through run_soffice with temp sibling output
- Implemented: P1 (finding 5), all four pdf/scripts/*.py writers and pptx/scripts/thumbnail.py create_grids now write to sibling temp files via mkstemp and atomically replace targets via os.replace, with atomic-failure tests in tests/test_agy_plugins.py

## Round 2: astra (`gpt-6-astra` via `codex`)

- Writer: agy
- Run: 2026-11-14T11:53:30Z
- Candidate: 4b4628adb529fee10ca67e26411ff2ac1a3ac1c0
- Effort: medium
- Lenses: adversarial, integration, source-defect, consistency, quality, optimization
- Lines: 32
- Digest: 7dfdee236be225a5

### adversarial: needs-attention

1. **P1** `plugins/agy/powertools/hooks/powertools_hook.py:491`: Force refspecs bypass confirmation when the remote uses `--repo`. The parser always skips the first positional argument as the remote, even after consuming `--repo`. In-memory reproduction: `catastrophic_command('git push --repo origin +HEAD:main')` and the `--repo=origin` variant both return `None`; the equivalent `git push origin +HEAD:main` is flagged. These commands can overwrite remote history without the promised `force_ask`.

### integration: needs-attention

2. **P2** `plugins/agy/powertools/hooks/powertools_hook.py:594`: Repository article checkers run without process-tree containment. On timeout, `subprocess.run` kills only the direct process, leaving its children running; inherited output handles can also delay timeout handling. Reproduce with an ordinary `scripts/article-check.py` that launches a slow external checker, then invoke `check_draft()` on a draft. After 30 seconds the descendant survives. Use the same process-tree cleanup contract already implemented in the craft LibreOffice wrapper.

### source-defect: approve

No additional findings.

### consistency: needs-attention

3. **P1** `plugins/agy/craft/skills/docx/scripts/merge_runs.py:60`: Directory-mode editing truncates `word/document.xml` before writing its replacement, violating the governing atomic-write requirement. Reproduce using the documented `python scripts/merge_runs.py unpacked/` workflow with a disk-full failure during the write: the existing document becomes empty or partial, and the exception handler cannot restore it. This can destroy edits present only in the unpacked directory. Similar direct overwrites occur in `comment.py:109` and `pptx/scripts/add_slide.py:386`. Write replacements beside their destinations and use `os.replace`.

### quality: approve

No additional findings.

### optimization: approve

No additional findings.

LENS adversarial: findings
LENS integration: findings
LENS source-defect: clean
LENS consistency: findings
LENS quality: clean
LENS optimization: clean
HIGHEST: P1
OVERALL: needs-attention

- Implemented: P1 (finding 1), _check_git_force_push now tracks --repo and --repo=<val> plus short-option clusters (-uo, -ofix) so refspecs after --repo and single-arg +src:dst force pushes trigger force_ask, with regression tests in tests/test_agy_plugins.py
- Implemented: P2 (finding 2), article_check.run_bounded_command (used by check_draft and fetch_post), office/soffice.run_process_tree (thumbnail.py pdftoppm and _ensure_shim), and validators/redlining.py now enforce bounded timeouts and full process-tree cleanup, with grandchild termination tests in tests/test_agy_plugins.py
- Implemented: P1 (finding 3), added atomic_write_bytes, atomic_write_text, and atomic_copy in office/helpers/__init__.py across docx, pptx, and xlsx, and converted merge_runs.py, comment.py, add_slide.py, clean.py, and auto-repair writes in validators/{base,docx}.py to sibling mkstemp + os.replace with preservation tests in tests/test_agy_plugins.py

## Round 3: astra (`gpt-6-astra` via `codex`)

- Writer: agy
- Run: 2026-11-14T12:08:28Z
- Candidate: 38014aac8b755cd9db418c1e1a803d293a2d65b4
- Effort: medium
- Lenses: adversarial, integration, source-defect, consistency, quality, optimization
- Lines: 36
- Digest: e99d2913a959845b

### adversarial: needs-attention

1. **P1: Exited parents prevent descendant cleanup.** `plugins/agy/powertools/hooks/article_check.py:93` and `plugins/agy/craft/skills/docx/scripts/office/soffice.py:40` return immediately when `proc.poll()` reports completion. A checker or launcher can spawn a child that inherits stdout, then exit; `communicate()` times out because the descendant still holds the pipe, but cleanup skips the surviving process. The same implementation exists in the PPTX/XLSX copies. Reproduce by running a wrapper that starts a sleeping descendant and exits through either runner with a short timeout. A read-only mock probe confirmed zero termination calls for an exited parent. On Windows, subsequently closing a pipe used by a blocked reader thread can also exceed the claimed cleanup bound.

2. **P1: Mirror pushes bypass the catastrophic-command guard.** `plugins/agy/powertools/hooks/powertools_hook.py:493` recognizes explicit force flags but omits `--mirror`, which force-updates remote refs and deletes remote refs absent locally. Reproduce with `catastrophic_command("git push --mirror origin")`: it returns `None`, confirmed against the candidate. Consequently, submitting that command through `run_command` receives `allow`, despite its destructive force-push semantics.

### integration: needs-attention

3. **P1: The documented editing workflows bypass archive limits.** `plugins/agy/craft/skills/pptx/SKILL.md:76` directs agents to unrestricted `ZipFile.extractall()`, while `plugins/agy/craft/skills/docx/SKILL.md:56` directs them to unrestricted `unzip`. Neither uses the newly supplied `safe_extract()` budgets. Reproduce by supplying an external PPTX or DOCX containing a highly compressed multi-gigabyte member and following the documented editing workflow: extraction consumes disk until completion or exhaustion, before validation runs. Route these instructions through the bounded extraction helper; protecting only the validator leaves the normal editing entry point exposed.

### source-defect: approve

No additional concrete findings.

### consistency: approve

No additional concrete findings.

### quality: approve

No additional concrete findings.

### optimization: approve

No additional concrete findings.

Verification was limited to source inspection and read-only probes; no files were modified and no full suite was run.

LENS adversarial: findings
LENS integration: findings
LENS source-defect: clean
LENS consistency: clean
LENS quality: clean
LENS optimization: clean
HIGHEST: P1
OVERALL: needs-attention

- Implemented: Finding 1 (P1): `article_check.py` (`run_bounded_command`) and `craft/skills/{docx,pptx,xlsx}/scripts/office/soffice.py` (`run_process_tree`) now attach Win32 Job Objects (`KILL_ON_JOB_CLOSE`) and call unconditional `os.killpg` without early `proc.poll()` return or blocking pipe closes so exited parents cannot leave pipe-inheriting descendants alive, verified by real exited-parent grandchild tests in `tests/test_agy_plugins.py`.
- Implemented: Finding 2 (P1): `powertools_hook.py` (`_check_git_force_push`) now gates `git push --mirror`, `-c remote.<name>.mirror=true`, `--delete`/`-d`, `--prune`, and `:refspec` deletions, while keeping `--no-mirror` allowed, verified in `tests/test_agy_plugins.py`.
- Implemented: Finding 3 (P1): added `craft/skills/{docx,pptx,xlsx}/scripts/office/unpack.py` (`safe_extract` + atomic staging) and `pack.py` (atomic `rezip`) and updated `docx/SKILL.md`, `pptx/SKILL.md`, and `merge_runs.py` to use them instead of unrestricted `unzip` / `ZipFile.extractall()`, verified by structure and CLI budget/atomicity tests in `tests/test_agy_plugins.py`.

## Round 4: astra (`gpt-6-astra` via `codex`)

- Writer: agy
- Run: 2026-11-14T12:23:12Z
- Candidate: 574bbe68ab0d26ba7a76b9f9154c1b166763c297
- Effort: medium
- Lenses: adversarial, integration, source-defect, consistency, quality, optimization
- Lines: 34
- Digest: 0b424181b878cf1a

### adversarial: needs-attention

1. **P1** `plugins/agy/powertools/hooks/powertools_hook.py:506`: Destructive push options bypass approval when abbreviated. Reproduction: pass `git push --mir origin` or `git push --del origin main` to `_handle_pre_tool_use`; both return `{"decision": "allow"}`. Git accepts these as `--mirror` and `--delete`, respectively. Verified Git’s parsing using nonexecuting option-error probes. Normalize accepted option abbreviations before classification.

2. **P1** `plugins/agy/craft/skills/pptx/scripts/thumbnail.py:112`: Thumbnail generation bypasses the archive size limits. Both relationship XML and presentation XML are decompressed completely and then parsed into DOMs. Reproduction: supply a `.pptx` containing a highly compressed, multi-gigabyte whitespace-filled `ppt/_rels/presentation.xml.rels`, then run the documented `python scripts/thumbnail.py hostile.pptx`. Memory exhaustion occurs before conversion or bounded extraction. Apply member and aggregate limits before reading, with bounded reads. This finding is source-verified; an exhaustion payload was not executed.

### integration: approve

No additional findings.

### source-defect: needs-attention

3. **P2** `plugins/agy/powertools/hooks/powertools_hook.py:84`: The injected “Owner writing rules” replace the governing requirement that Claude research, write and rewrite articles with permission to write and obtain cross-family review. Reproduction: trigger `PreInvocation` with “write an article”; the resulting instructions omit Claude ownership and direct the current agent to write. Preserve the writer restriction from section 10, also present in both existing global rule files.

### consistency: approve

No additional findings.

### quality: approve

No additional findings.

### optimization: approve

No additional findings.

LENS adversarial: findings
LENS integration: clean
LENS source-defect: findings
LENS consistency: clean
LENS quality: clean
LENS optimization: clean
HIGHEST: P1
OVERALL: needs-attention

- Implemented: Finding 1 (P1): `powertools_hook.py` (`_resolve_push_long_opt`, `_check_git_force_push`) now normalizes `git push` long option abbreviations against Git's canonical option set (catching `--m`, `--mir`, `--del`, `--pru`, `--force-w`, `--force-i`, `--rep`, `--no-mir`, etc.), `-c remote.<name>.mirror` booleans, and `--config-env`, verified in `tests/test_agy_plugins.py`.
- Implemented: Finding 2 (P1): added `validate_archive`, `open_zip_member`, and `read_zip_member` with `_BoundedZipStream` to shared `craft/skills/{docx,pptx,xlsx}/scripts/office/helpers/__init__.py` enforcing entry count, symlink, per-member, and cumulative unpacked byte limits, and wired `pptx/scripts/thumbnail.py`, `office/validators/docx.py`, `xlsx/scripts/recalc.py`, and `pptx/scripts/slide_text.py`, verified by valid, spoofed-header member overflow, and cumulative aggregate limit tests in `tests/test_agy_plugins.py`.
- Implemented: Finding 3 (P2): restored Section 10's `"Claude researches, writes and rewrites"` authorship rule in `powertools_hook.py` (`ARTICLE_RULES`) and added `## 7. Creative writing and articles` to `plugins/agy/powertools/rules/AGENTS.md`, verified in `tests/test_agy_plugins.py`.

## Round 5: astra (`gpt-6-astra` via `codex`)

- Writer: agy
- Run: 2026-11-14T12:41:09Z
- Candidate: 6a8c39a5d16ae2f422f99980bedc82f545668a57
- Effort: medium
- Lenses: adversarial, integration, source-defect, consistency, quality, optimization
- Lines: 36
- Digest: d74e2ec78605d97e

### adversarial: needs-attention

1. **P1** `plugins/agy/powertools/hooks/powertools_hook.py:659`: The root-deletion guard recognizes only the exact PowerShell parameter `-Recurse`. PowerShell accepts unambiguous abbreviations such as `-Recur`. Reproduce safely by passing `Remove-Item C:\ -Recur -Force` to `catastrophic_command()` without executing the command: the recursive flag remains false, so the hook allows it. Normalize PowerShell parameters before classifying destructive commands.

2. **P1** `plugins/agy/craft/skills/xlsx/scripts/recalc.py:92`: Archive validation failures become `[]`, meaning “no external links at risk.” Consequently, `recalc()` proceeds to LibreOffice instead of refusing the rejected workbook. Reproduce with a workbook containing external formulas with missing cached values and enough additional ZIP entries to exceed 10,000. The guard skips its link inspection, permitting the destructive recalculation it explicitly promises to prevent. An in-memory probe confirmed that validation raises for 10,001 entries while `external_links_at_risk()` returns `[]`. Propagate validation failures to the existing inspection-error handler.

### integration: needs-attention

3. **P2** `plugins/agy/craft/skills/pdf/scripts/convert_pdf_to_images.py:21`: The documented conversion command cannot create its output directory. On a fresh workspace, run `python scripts/convert_pdf_to_images.py input.pdf images/` with a valid one-page PDF and no existing `images` directory. The first `image.save()` raises `FileNotFoundError`. This affects the workflows documented in `FORMS.md`, including the final verification conversion. Create the destination before saving.

### source-defect: approve

No additional findings.

### consistency: approve

No additional findings.

### quality: approve

No additional findings.

### optimization: needs-attention

4. **P2** `plugins/agy/craft/skills/pdf/scripts/convert_pdf_to_images.py:10`: Conversion materializes every page at 200 DPI before resizing any page to `max_dim=1000`. A supplied 1,000-page A4 PDF requires roughly 11 GB for RGB pixel buffers alone, despite producing small thumbnails. Reproduce through the documented conversion command with an existing output directory and a long PDF. This can exhaust memory on ordinary workstations. Render bounded batches and apply the size limit during rasterization.

No files were modified. Findings combine source inspection with the archive-validation probe; full application workflows were not executed.

LENS adversarial: findings
LENS integration: findings
LENS source-defect: clean
LENS consistency: clean
LENS quality: clean
LENS optimization: findings
HIGHEST: P1
OVERALL: needs-attention

- Implemented: Finding 1 (P1): `powertools_hook.py` (`_resolve_pwsh_param`, `_check_root_delete`, `_resolve_pwsh_cli_opt`, `catastrophic_command`) now normalizes PowerShell `Remove-Item` parameters and aliases by unambiguous prefix (`-r`..`-recurse`, `-Recurse:$true` vs `$false`, `-Path`/`-LiteralPath`/`-LP`, value options), GNU `rm` long prefixes (`--rec`, `--no-preserve`), `pwsh` wrapper prefixes and `-EncodedCommand` UTF-16LE payloads, and `gh -R`, verified in `tests/test_agy_plugins.py`.
- Implemented: Finding 2 (P1): `craft/skills/xlsx/scripts/recalc.py` (`external_links_at_risk` and `recalc`) now lets `ValueError` from `validate_archive` propagate to `recalc()`'s inspection-error handler instead of returning `[]`, and validates zip workbooks when `force=True`, verified in `tests/test_agy_plugins.py`.
- Implemented: Findings 3 & 4 (P2): `craft/skills/pdf/scripts/convert_pdf_to_images.py` and `create_validation_image.py` now create missing output directories, render PDFs in bounded `BATCH_SIZE=10` page ranges with `size=max_dim` at rasterization time, write PNGs atomically, and close images immediately, verified in `tests/test_agy_plugins.py`.

## Round 6: astra (`gpt-6-astra` via `codex`)

- Writer: agy
- Run: 2026-11-14T12:55:04Z
- Candidate: 3ffe446bddb45a416cc7626b8123434b92afef4a
- Effort: medium
- Lenses: adversarial, integration, source-defect, consistency, quality, optimization
- Lines: 34
- Digest: e754b504391d69db

### adversarial: needs-attention

1. **P1** `plugins/agy/powertools/hooks/powertools_hook.py:671`: Root-delete detection does not normalize dot segments. Parser-only reproduction: `catastrophic_command('rm -rf /./*')` returns `None`, whereas `rm -rf /*` triggers protection. Likewise, `Remove-Item -Recurse -Force C:\.\*` bypasses the guard. These commands target root contents through valid OS paths, so destructive automation avoids `force_ask`.

2. **P1** `plugins/agy/craft/skills/xlsx/scripts/recalc.py:101`: Archive byte limits do not bound openpyxl’s merged-cell expansion. An incoming workbook containing `xl/externalLinks/unused.xml` and a worksheet merge `A1:XFD1048576` passes archive validation and enters two normal-mode `load_workbook` calls before LibreOffice’s timeout applies. Each load attempts to materialize billions of cells. A bounded, in-memory reproduction with `A1:CV100` produced a 1,202-byte archive and allocated 10,000 cells in each load. The full-range variant can exhaust memory from a tiny accepted file.

### integration: needs-attention

3. **P2** `plugins/agy/craft/skills/pdf/scripts/extract_form_field_info.py:40`: Choice options containing ordinary strings are interpreted as two-element arrays. For `/_States_: ['Yes', 'No']`, the extractor returns values `Y` and `N`, with labels `e` and `o`; one-character options raise `IndexError`. Reproduce through the documented extraction workflow with a PDF dropdown whose `/Opt` contains those strings. The subsequent filling script rejects the correct values because it uses this corrupted option list. Confirmed with a direct function probe; [pypdf’s implementation](https://pypdf.readthedocs.io/en/6.1.2/_modules/pypdf/_doc_common.html) copies `/Opt` directly into `/_States_`.

### source-defect: approve

No additional findings.

### consistency: approve

No additional findings.

### quality: approve

No additional findings.

### optimization: approve

No additional findings beyond the resource-exhaustion defect recorded under adversarial.

LENS adversarial: findings
LENS integration: findings
LENS source-defect: clean
LENS consistency: clean
LENS quality: clean
LENS optimization: clean
HIGHEST: P1
OVERALL: needs-attention

- Implemented: Finding 1 (P1): `powertools_hook.py` (`_is_root_target`) now normalizes dot segments (`.` and `..`), repeated separators, PowerShell `FileSystem::` / Windows device prefixes, and optional trailing wildcards for POSIX and drive-rooted paths without resolving relative paths, verified in `tests/test_agy_plugins.py`.
- Implemented: Finding 2 (P1): `craft/skills/xlsx/scripts/recalc.py` (`external_links_at_risk`, `_merged_ranges`, `_validate_workbook_archive`, `_scan_xml`, `_scan_with_openpyxl`, and `_report`) now inspects external-link formulas in pure bounded XML with a stdlib Expat DTD guard fallback, enforces `MAX_MERGED_CELLS = 1_000_000` before `openpyxl` runs, and propagates `ValueError` instead of falling back to unbounded loads, verified in `tests/test_agy_plugins.py`.
- Implemented: Finding 3 (P2): `craft/skills/pdf/scripts/extract_form_field_info.py` (`make_field_dict`) and `fill_fillable_fields.py` (`monkeypatch_pydpf_method`) now handle plain strings and single-element or two-element arrays in `/_States_` and `/Opt`, verified in `tests/test_agy_plugins.py`.

## Round 7: astra (`gpt-6-astra` via `codex`)

- Writer: agy
- Run: 2026-11-14T13:13:17Z
- Candidate: 1cab2fb7f8734b8383d51d8472f1b97be1c67cab
- Effort: medium
- Lenses: adversarial, integration, source-defect, consistency, quality, optimization
- Lines: 34
- Digest: 1e8c5327b2f2d209

### adversarial: needs-attention

1. **P1** `plugins/agy/craft/skills/xlsx/scripts/recalc.py:205`: The merged-cell budget scans raw bytes with an ASCII regex, so UTF-16 worksheet XML bypasses it. Reproduce with an incoming `.xlsx` containing UTF-16 `xl/worksheets/sheet1.xml` and `<mergeCell ref="A1:XFD1048576"/>`, without external links. The default precheck returns `[]`; `_validate_workbook_archive` also accepts it. The equivalent UTF-8 input raises the budget error. Both normal and `--force` recalculation therefore pass the oversized merge to LibreOffice. Parse merge elements with an encoding-aware XML parser and enforce the cumulative budget before conversion.

### integration: needs-attention

2. **P1** `plugins/agy/craft/skills/xlsx/scripts/recalc.py:234`: Defined-name matching is case-sensitive, but Excel defined names are case-insensitive. Reproduce with `ExternalValue` defined as `[1]Sheet1!$A$1`, an external-link part, and an uncached cell formula `externalvalue`. The read-only probe returned `[]`; changing only the formula to `ExternalValue` returned `['Sheet1!A1']`. This bypasses the refusal intended to prevent destructive recalculation of uncached external references. Apply case-insensitive matching throughout name dependency propagation and formula inspection.

### source-defect: approve

No additional findings.

### consistency: approve

No additional findings.

### quality: approve

No additional findings.

### optimization: approve

No additional findings.

The reproductions used in-memory ZIP archives. No files were modified, and LibreOffice conversion was not run.

LENS adversarial: findings
LENS integration: findings
LENS source-defect: clean
LENS consistency: clean
LENS quality: clean
LENS optimization: clean
HIGHEST: P1
OVERALL: needs-attention

- Implemented: Finding 1 (P1): `craft/skills/xlsx/scripts/recalc.py` (`_merged_ranges`, `_validate_workbook_archive`, `_worksheet_parts`, `external_links_at_risk`, and `_scan_xml`) now streams `<mergeCell>` elements through encoding-aware `_safe_iterparse` instead of scanning raw bytes with an ASCII regex, enforcing `MAX_MERGED_CELLS = 1_000_000` on UTF-16 and UTF-8 worksheets with or without external links, verified in `tests/test_agy_plugins.py`.
- Implemented: Finding 2 (P1): `craft/skills/xlsx/scripts/recalc.py` (`_names_pattern` and `external_links_at_risk`) now normalizes Excel defined names case-insensitively during dependency propagation and compiles `_names_pattern` with `re.IGNORECASE`, verified in `tests/test_agy_plugins.py`.

## Round 8: astra (`gpt-6-astra` via `codex`)

- Writer: agy
- Run: 2026-11-14T13:22:39Z
- Candidate: 0051c58117c537c6c742253aeab6fcbafdf8ccfb
- Effort: medium
- Lenses: adversarial, integration, source-defect, consistency, quality, optimization
- Lines: 34
- Digest: cd9761ee002af29e

### adversarial: needs-attention

1. **P1** `plugins/agy/craft/skills/xlsx/scripts/recalc.py:223`: Streaming validation retains cleared elements in their parent until the parent closes. A hostile worksheet containing millions of sibling `<c/>` elements therefore consumes memory proportional to element count despite the byte budget. Reproduction: ZIP `xl/worksheets/sheet1.xml` containing `<worksheet><sheetData><row>` followed by 400,000 `<c/>` elements and closing tags; call `external_links_at_risk()`. The 1,765-byte archive passed with `[]` while allocating 32,589,014 peak bytes. Scaling within the accepted 128 MiB XML limit permits gigabytes of allocations before rejection, risking memory exhaustion. Detach processed elements or enforce an element budget.

### integration: needs-attention

2. **P2** `plugins/agy/craft/skills/xlsx/scripts/recalc.py:417`: Defined-name matching searches string literals as though they were references. Reproduction: a workbook containing external defined name `ExternalValue`, an external-link part, and uncached formula `="ExternalValue"` or `=IF(1,"ExternalValue","ok")`. Both returned `['Sheet1!A1']` in the in-memory reproduction, causing `recalc()` to refuse formulas that do not reference another workbook. Formula tokenization must distinguish names from quoted text.

3. **P2** `plugins/agy/craft/skills/xlsx/scripts/recalc.py:334`: Name propagation discards `localSheetId`, conflating workbook names with sheet-local names. Reproduction: define workbook-level `ExternalValue` as `[1]Sheet1!$A$1`, define sheet-local `ExternalValue` with `localSheetId="0"` as `42`, and use `=ExternalValue` on the first sheet. The guard returned `['Sheet1!A1']` even though the local name shadows the external name. Preserve scope when resolving names and dependencies.

### source-defect: approve

No additional findings.

### consistency: approve

No additional findings.

### quality: approve

No additional findings.

### optimization: needs-attention

Finding 1 also defeats the streaming implementation’s memory bound. Measured parser peaks increased from approximately 8.3 MB to 16.3 MB to 32.4 MB for 100,000, 200,000 and 400,000 sibling elements respectively.

LENS adversarial: findings
LENS integration: findings
LENS source-defect: clean
LENS consistency: clean
LENS quality: clean
LENS optimization: findings
HIGHEST: P1
OVERALL: needs-attention

- Implemented: Finding 1 (P1 & optimization): `craft/skills/xlsx/scripts/recalc.py` (`_safe_iterparse`, `_merged_ranges`, `external_links_at_risk`, and `_scan_xml`) now parses XML using `events=("start", "end")`, tracks an explicit parent stack with depth (`<= 256`) and subtree (`<= 10_000`) bounds, and detaches finished sibling elements from their parent (`del stack[-1][:]` + `node.clear()`), holding streaming memory O(1) across large sibling `<c/>` floods, verified via `tracemalloc` in `tests/test_agy_plugins.py`.
- Implemented: Finding 2 (P2): `craft/skills/xlsx/scripts/recalc.py` (`_scan_formula_tokens` and `_expr_reaches_external`) now tokenizes Excel formulas while skipping double-quoted string constants (`"..."`) and structured brackets rather than matching raw regexes against formula text, verified in `tests/test_agy_plugins.py`.
- Implemented: Finding 3 (P2): `craft/skills/xlsx/scripts/recalc.py` (`_resolve_def_key`, `_expr_reaches_external`, and `external_links_at_risk`) now preserves `(name.casefold(), localSheetId)` scoping across dependency propagation, sheet-qualified names (`Sheet2!Name`), and sheet-local shadowing of workbook-global names, verified in `tests/test_agy_plugins.py`.

## Round 9: astra (`gpt-6-astra` via `codex`)

- Writer: agy
- Run: 2026-11-14T13:35:40Z
- Candidate: ecf94f46c19a5b80f97892ae1638b2c74e063063
- Effort: medium
- Lenses: adversarial, integration, source-defect, consistency, quality, optimization
- Lines: 34
- Digest: 003be631ed15e75d

### adversarial: needs-attention

1. **P1: Saved LAMBDA functions bypass the external-link guard.** `plugins/agy/craft/skills/xlsx/scripts/recalc.py:493` recognizes only `lambda`, but Excel-compatible files store `_xlfn.LAMBDA`. Reproduce with a defined name `LinkedFn = _xlfn.LAMBDA(_xlpm.x,[1]Sheet1!A1+_xlpm.x)` and an uncached cell containing `LinkedFn(1)`. The verified result from `external_links_at_risk()` is `[]`; removing `_xlfn.` produces `['Sheet1!A1']`. Consequently, line 419 skips the real function call and recalculation proceeds without the required refusal. The prefixed representation is documented in [XlsxWriter’s LAMBDA example](https://xlsxwriter.readthedocs.io/example_lambda.html).

### integration: needs-attention

2. **P1: Absolute worksheet targets containing dot segments silently skip the worksheet.** `plugins/agy/craft/skills/xlsx/scripts/recalc.py:98` strips the leading slash without normalizing the remaining path. Reproduce with relationship target `/xl/worksheets/./sheet1.xml`, archive member `xl/worksheets/sheet1.xml`, and an uncached external formula in A1. Verified: the guard returns `[]` and `_scan_xml()` counts zero formulas. Removing `/./` returns `['Sheet1!A1']` and one formula. Lines 542 and 753 silently continue on the unresolved target, bypassing protection and producing an incomplete report.

### source-defect: needs-attention

Finding 1: `plugins/agy/craft/skills/xlsx/scripts/recalc.py:493` does not recognize the documented serialized LAMBDA representation. Recognition must operate on stored OOXML formulas, including their function prefixes.

### consistency: needs-attention

Finding 2: `plugins/agy/craft/skills/xlsx/scripts/recalc.py:98` duplicates relationship resolution instead of using the bundled `office.helpers.opc_target()`. In the same reproduction, that shared helper correctly resolves the target to `xl/worksheets/sheet1.xml`.

### quality: approve

No additional actionable finding under this lens.

### optimization: needs-attention

3. **P2: Defined-name dependency propagation takes quadratic time outside the timeout.** `plugins/agy/craft/skills/xlsx/scripts/recalc.py:513` repeatedly tokenizes every unresolved definition, discovering only one additional dependency per iteration for a chain. Reproduce with `Name_0 = Name_1`, continuing through `Name_4000 = [1]Sheet1!A1`, and an uncached cell referencing `Name_0`. In-memory archive measurements were 0.130 seconds for 500 links, 0.516 seconds for 1,000, and 8.811 seconds for 4,000, whose archive was only 211 KB. Larger externally supplied workbooks remain well below the byte limits but monopolize execution; the recalculation timeout applies only afterward. Parse dependencies once and propagate reachability through a work queue.

Verification used read-only inspection and in-memory reproductions. No files were modified; the full suite was not run.

LENS adversarial: findings
LENS integration: findings
LENS source-defect: findings
LENS consistency: findings
LENS quality: clean
LENS optimization: findings
HIGHEST: P1
OVERALL: needs-attention

- Implemented: Finding 1 (P1 adversarial and source-defect): `craft/skills/xlsx/scripts/recalc.py` (`_is_lambda_func_name`, `external_links_at_risk`) now strips OOXML future/worksheet function prefixes (`_xlfn.`, `_xlws.`, `xlws.`) when seeding LAMBDA definitions so `_xlfn.LAMBDA` and `_xlfn._xlws.LAMBDA` calls trigger the external-link guard, verified in `tests/test_agy_plugins.py`.
- Implemented: Finding 2 (P1 integration and consistency): `craft/skills/xlsx/scripts/recalc.py` (`_workbook_opc_context`, `_worksheet_parts`, `external_links_at_risk`, `_scan_xml`) now delegates relationship resolution to bundled `office.helpers.opc_target` instead of duplicating path joins, normalizing dot segments and percent-encoded targets while rejecting package escapes, verified in `tests/test_agy_plugins.py`.
- Implemented: Finding 3 (P2 optimization): `craft/skills/xlsx/scripts/recalc.py` (`external_links_at_risk`, `_expr_reaches_external`) now tokenizes defined names once into reverse dependency graphs and propagates LAMBDA and external-link reachability via O(V + E) deque work queues, resolving a 4,001-name chain in under 1 second, verified by timing test in `tests/test_agy_plugins.py`.

## Round 10: astra (`gpt-6-astra` via `codex`)

- Writer: agy
- Run: 2026-11-14T13:50:03Z
- Candidate: 335cd448146749fa02c96cce9c28444cb4661335
- Effort: medium
- Lenses: adversarial, integration, source-defect, consistency, quality, optimization
- Lines: 32
- Digest: f84ff72d9191327b

### adversarial: needs-attention

1. **P1: Unbounded column conversion permits CPU exhaustion.** `plugins/agy/craft/skills/xlsx/scripts/recalc.py:241` converts arbitrarily long column names into increasingly large integers before checking merge bounds. Reproduce by supplying an XLSX whose `xl/worksheets/sheet1.xml` contains a `mergeCell` with `ref` equal to 160,000 `A` characters followed by `1`, then invoking `recalc.py`. The single-cell range consumes only one unit of the merge budget. Read-only probes measured 0.049 seconds for 10,000 characters, 0.694 seconds for 40,000, and 11.048 seconds for 160,000. Larger inputs remain below the XML size limit and run before the LibreOffice timeout applies. Reject invalid coordinate lengths and worksheet bounds before integer conversion.

### integration: needs-attention

2. **P2: Formula-local names incorrectly trigger the external-link refusal.** `plugins/agy/craft/skills/xlsx/scripts/recalc.py:439` resolves every name token against worksheet/workbook definitions without tracking `LET` bindings. Reproduce with a workbook-level name `Rate` referring to `[1]Sheet1!$A$1`, its external-link part, and an uncached `Sheet1!A1` formula `LET(Rate,1,Rate+1)`. The in-memory workbook probe returned `['Sheet1!A1']`, causing normal recalculation to refuse despite this formula using only its local constant. Track local bindings in both formula scanning and defined-name dependency analysis.

### source-defect: needs-attention

Finding 2 contradicts Excel’s documented function-local scope for `LET` names. The scanner needs to distinguish those bindings from workbook defined names. [Microsoft LET documentation](https://support.microsoft.com/en-us/excel/functions/let-function)

### consistency: approve

No additional findings.

### quality: approve

No additional findings.

### optimization: needs-attention

Finding 1 demonstrates approximately quadratic conversion cost: increasing input length fourfold increased runtime roughly sixteenfold. The archive and merge budgets do not bound this computational work.

LENS adversarial: findings
LENS integration: findings
LENS source-defect: findings
LENS consistency: clean
LENS quality: clean
LENS optimization: findings
HIGHEST: P1
OVERALL: needs-attention

- Implemented: Finding 1 (P1 adversarial and optimization): `craft/skills/xlsx/scripts/recalc.py` (`_row_major`, `_parse_merge_ref`, `external_links_at_risk`, `_scan_xml`) now validates cell coordinate lengths (`<= 12` chars, `<mergeCell ref>` `<= 64` chars), bounded numeric fields (`localSheetId`, shared-string index), and Excel grid limits (`<= 1,048,576` rows, `<= 16,384` `XFD` columns) before integer conversion, rejecting 160,000-char column bombs in O(1) time, verified by `test_recalc_coordinate_bounds_and_let_lambda_local_scopes` in `tests/test_agy_plugins.py`.
- Implemented: Finding 2 (P2 integration and source-defect): `craft/skills/xlsx/scripts/recalc.py` (`_lex_formula_tokens`, `_scan_formula_tokens`, `_binding_func_kind`, `_local_name_variants`) now tracks formula-local `LET`/`_xlfn.LET` and `LAMBDA`/`_xlfn.LAMBDA` parameter scopes (including `_xlpm.` normalization and array-brace comma isolation) so shadowed local variables do not falsely match workbook/worksheet defined names while pre-binding initializers, post-scope refs, and sheet-qualified refs remain checked, verified in `tests/test_agy_plugins.py`.

## Round 11: astra (`gpt-6-astra` via `codex`)

- Writer: agy
- Run: 2026-11-14T14:02:36Z
- Candidate: 5a739bbc8883646bab910bec58d2ecf1fbcd69df
- Effort: medium
- Lenses: adversarial, integration, source-defect, consistency, quality, optimization
- Lines: 34
- Digest: 84c73c9805738198

## adversarial: needs-attention

1. **P1** `plugins/agy/craft/skills/xlsx/scripts/recalc.py:490`: Formula inspection materializes an unbounded token list before checking dependencies. The archive permits worksheet XML up to 128 MiB, while subtree limits count elements, not formula text. An externally supplied XLSX containing external-link metadata and a single large `<f>` containing repeated `Rate+` terms reaches this allocation through `external_links_at_risk()`. A measured 500,001-byte expression consumed 14,124,448 bytes during token scanning alone. Larger accepted inputs can therefore consume gigabytes before LibreOffice runs; its timeout does not protect this inspection. Reproduce by placing that repeated expression in an uncached formula cell and calling `recalc.py`. Enforce a formula/token budget before materialization.

## integration: needs-attention

2. **P1** `plugins/agy/craft/skills/pptx/scripts/add_slide.py:333`: Slide registration silently fails for namespace-prefixed relationship XML. For example, a valid `presentation.xml.rels` serialized by ElementTree uses `<ns0:Relationships>`, so replacing `</Relationships>` changes nothing. The function nevertheless returns the new relationship ID, which is inserted into `presentation.xml`; the default CLI operation then overwrites the deck with a dangling slide reference. Reproduce with such a deck using `python add_slide.py deck.pptx slide1.xml`. An isolated execution returned `rId2` while leaving the relationship XML unchanged. The content-type insertion at line 315 has the same defect. Use namespace-aware XML insertion for both.

## source-defect: approve

No additional findings.

## consistency: approve

No additional findings.

## quality: approve

No additional findings.

## optimization: needs-attention

Finding 1 also exposes excessive memory amplification on the document-inspection path.

Verification was limited to read-only inspection and in-memory probes. Full document-tool execution was not performed.

LENS adversarial: findings
LENS integration: findings
LENS source-defect: clean
LENS consistency: clean
LENS quality: clean
LENS optimization: findings
HIGHEST: P1
OVERALL: needs-attention

- Implemented: Finding 1 (P1 adversarial and optimization): `craft/skills/xlsx/scripts/recalc.py` (`_make_dtd_guard`, `_safe_fromstring`, `_safe_iterparse`, `_lex_formula_tokens`, `external_links_at_risk`, `_scan_xml`, `_merged_ranges`) now enforces streaming XML element text and formula budgets (`MAX_FORMULA_CHARS = 32,768`, `MAX_FORMULA_TOKENS = 16,384`, `MAX_ELEMENT_TEXT_CHARS = 1,048,576`) before token materialization, verified by `test_recalc_formula_and_token_budgets_prevent_memory_amplification` in `tests/test_agy_plugins.py`.
- Implemented: Finding 2 (P1 integration): `craft/skills/{docx,pptx,xlsx}/scripts/office/helpers/__init__.py`, `craft/skills/pptx/scripts/{add_slide.py,clean.py,thumbnail.py}`, and `craft/skills/docx/scripts/comment.py` now use namespace-aware DOM inspection and insertion (preserving default and prefixed namespaces such as ElementTree `ns0:`/`ns1:`) instead of literal closing-tag string replacements or unprefixed tag lookups, verified by `test_pptx_and_docx_scripts_handle_namespace_prefixed_opc_xml` in `tests/test_agy_plugins.py`.

## Round 12: astra (`gpt-6-astra` via `codex`)

- Writer: agy
- Run: 2026-11-14T14:29:30Z
- Candidate: 569610c281744a8326af40f45cc10d4951b98569
- Effort: medium
- Lenses: adversarial, integration, source-defect, consistency, quality, optimization
- Lines: 32
- Digest: 986088495a012c4c

### adversarial: needs-attention

1. **P1** `plugins/agy/craft/skills/pptx/scripts/clean.py:100`: Missing presentation metadata causes destructive cleanup instead of refusal. Reproduce with an unpacked PPTX containing `_rels/.rels` targeting `ppt/presentation.xml` and `ppt/slides/slide1.xml`, but missing `ppt/presentation.xml`. Run `python clean.py unpacked`. The initial relationship check passes, both slide-reference helpers return empty collections, and line 112 deletes the slide. A damaged input therefore loses recoverable content. Confirmed with filesystem operations mocked, without modifying files.

### integration: needs-attention

2. **P2** `plugins/agy/craft/skills/pptx/scripts/clean.py:257`: Content-type cleanup fails on Windows. Removal functions record native paths such as `ppt\slides\slide2.xml`, while OPC `PartName` values use `ppt/slides/slide2.xml`. The comparison never matches. Reproduce on Windows by cleaning a deck with an orphaned slide and its content-type override: the slide disappears but the override remains, leaving inconsistent package metadata. An in-memory reproduction retained the override and made zero write calls. Normalize removal records to POSIX package paths.

### source-defect: approve

No additional findings.

### consistency: needs-attention

Finding 2 violates the package-path convention already used by the relationship resolver.

### quality: approve

No additional findings.

### optimization: approve

No findings established.

LENS adversarial: findings
LENS integration: findings
LENS source-defect: clean
LENS consistency: findings
LENS quality: clean
LENS optimization: clean
HIGHEST: P1
OVERALL: needs-attention

- Implemented: Finding 1 (P1 adversarial): `plugins/agy/craft/skills/pptx/scripts/clean.py` (`_validate_presentation_package`, `remove_orphaned_slides`, `clean_unused_files`) now refuses with `RefusedToClean` before deleting any files when `ppt/presentation.xml` or `ppt/_rels/presentation.xml.rels` is missing, malformed, or lacks presentation structure, verified by `test_pptx_clean_refuses_missing_presentation_and_prunes_content_types_posix` in `tests/test_agy_plugins.py`.
- Implemented: Finding 2 (P2 integration and consistency): `plugins/agy/craft/skills/pptx/scripts/clean.py` now uses canonical POSIX relative paths (`.as_posix()`) across all removal helpers and `_referenced_by`, uses `.removesuffix(".rels")`, handles nested `[trash]` subdirectories, and normalizes package paths in `update_content_types` so Windows runs prune `[Content_Types].xml` overrides consistently.

## Round 13: astra (`gpt-6-astra` via `codex`)

- Writer: agy
- Run: 2026-11-14T14:52:42Z
- Candidate: 832c9f4ef02d0dc04d5c5c6d2b85a4601cd8d737
- Effort: medium
- Lenses: adversarial, integration, source-defect, consistency, quality, optimization
- Lines: 36
- Digest: 294d16679dd86da8

### adversarial: needs-attention

1. **P1** `plugins/agy/craft/skills/pptx/scripts/clean.py:139`: Missing slide IDs bypass the destructive-cleanup refusal. `_referenced_slide_rids()` silently drops entries without `r:id`, so a damaged, nonempty slide list looks empty. Reproduce: unpack a deck whose `<p:sldIdLst>` contains `<p:sldId id="256"/>`, retaining its slide relationship and slide file, then run `clean.py unpacked/`. All slides are deleted instead of refusing. Confirmed using the actual cleanup functions with an in-memory filesystem.

2. **P2** `plugins/agy/craft/skills/pptx/scripts/clean.py:350`: Content types are parsed only after files and relationships have been deleted or rewritten. Reproduce: use a deck with one retained slide, one orphan slide, and malformed `[Content_Types].xml`; run `clean.py unpacked/`. Cleanup deletes the orphan, then raises `ExpatError`; the CLI falsely reports “Nothing was deleted.” Confirmed with an in-memory filesystem. Validate content types before any mutation.

### integration: needs-attention

3. **P2** `plugins/agy/craft/skills/pptx/scripts/apply_theme.js:32`: Dependency resolution breaks the documented project-local installation workflow. Reproduce: install `pptxgenjs` in a project, then follow the skill’s example requiring the globally deployed `apply_theme.js`. The project’s `require("pptxgenjs")` succeeds, but the helper resolves it from its own plugin directory and fails. The error suggests setting `NODE_PATH`, but the documented creation workflow neither sets it nor passes the dependency into the helper.

### source-defect: approve

No additional findings.

### consistency: needs-attention

4. **P1** `plugins/agy/craft/skills/pptx/scripts/apply_theme.js:85`: The theme writer violates the governing atomic-write requirement and can destroy the input deck. Its default output is the input path, and `fs.writeFileSync` truncates that file before writing the replacement ZIP. Reproduce: run the documented `node scripts/apply_theme.js deck.pptx theme.json` on a filesystem with insufficient remaining space for the replacement. A partial write leaves the original deck truncated. Write to a sibling temporary file and replace only after success.

### quality: approve

No additional findings.

### optimization: approve

No additional findings.

Validation was read-only; the cleanup reproductions used mocked filesystem operations, with no files modified.

LENS adversarial: findings
LENS integration: findings
LENS source-defect: clean
LENS consistency: findings
LENS quality: clean
LENS optimization: clean
HIGHEST: P1
OVERALL: needs-attention

- Implemented: Finding 1 (P1 adversarial): `plugins/agy/craft/skills/pptx/scripts/clean.py` (`_validate_slide_id_list` called from `_validate_presentation_package`) now validates every child of `<p:sldIdLst>` and every `<p:sldId>` entry, refusing with `RefusedToClean` before deleting anything if any `<p:sldId>` lacks `r:id`, references an unknown slide relationship id, escapes `unpacked_dir`, or targets a missing slide file, verified by `test_pptx_clean_refuses_missing_rid_and_malformed_content_types_before_deletion` in `tests/test_agy_plugins.py`.
- Implemented: Finding 2 (P2 adversarial): `plugins/agy/craft/skills/pptx/scripts/clean.py` (`_validate_presentation_package`, `clean_unused_files`) now requires `[Content_Types].xml` to exist and parses it via `parse_xml_file` (verifying root `<Types>`) before any deletion or `.rels` edit, and refuses when `.rels` or resolved references are empty, verified by `test_pptx_clean_refuses_missing_rid_and_malformed_content_types_before_deletion` in `tests/test_agy_plugins.py`.
- Implemented: Finding 3 (P2 integration): `plugins/agy/craft/skills/pptx/scripts/apply_theme.js` (`loadJSZip`, `collectSearchPaths`) now resolves `pptxgenjs` and `jszip` across `extraPaths`, the `module.parent` caller chain, `require.main`, `process.argv[1]`, `require.cache`, `NODE_PATH`, `process.cwd()`, and `__dirname` (without searching beside `deckPath`), verified programmatically and via CLI without `NODE_PATH` in `test_pptx_apply_theme_resolves_project_local_deps_and_writes_atomically`.
- Implemented: Finding 4 (P1 consistency): `plugins/agy/craft/skills/pptx/scripts/apply_theme.js` (`atomicWriteBuffer`, `readXmlBounded`, `applyTheme`) now writes via a sibling temporary file (`O_CREAT | O_EXCL | O_WRONLY`, full `writeSync` loop, `fsyncSync`, mode preservation, `renameSync`, and rollback cleanup) and enforces `10000`-entry, `128 MiB` member, and `512 MiB` archive budgets, verified by `ENOSPC` rollback and entry-limit assertions in `test_pptx_apply_theme_resolves_project_local_deps_and_writes_atomically`.

## Round 14: astra (`gpt-6-astra` via `codex`)

- Writer: agy
- Run: 2026-11-14T15:06:12Z
- Candidate: c85f0b6c96fe2fec4a6843d066798e36532e804b
- Effort: medium
- Lenses: adversarial, integration, source-defect, consistency, quality, optimization
- Lines: 26
- Digest: 4e29878d3c99851e

### adversarial: needs-attention

1. **P1** `plugins/agy/craft/skills/pptx/scripts/clean.py:169`: Duplicate relationship IDs pass validation. `_slide_rids()` silently keeps the last target, so cleaning can delete a slide referenced by the first relationship. Reproduce with one `p:sldId` referencing `rId1`, two slide relationships named `rId1` targeting existing `slide1.xml` and `slide2.xml`, respectively. Run `clean.py unpacked/`: `slide1.xml` is deleted instead of refusing the ambiguous package. Confirmed with in-memory XML and mocked filesystem mutations.

2. **P1** `plugins/agy/craft/skills/pptx/scripts/apply_theme.js:311`: The entry-count limit runs after JSZip has parsed and allocated the entire archive. A hostile ZIP below the 512 MiB input limit can contain millions of empty, uniquely named entries, exhausting memory before the 10,000-entry check executes. Reproduce through `node apply_theme.js many-entries.pptx theme.json` with such an archive. Check central-directory entry counts before loading it into JSZip. This finding is based on code inspection; real JSZip was unavailable locally.

### integration: approve

### source-defect: needs-attention

3. **P2** `plugins/agy/craft/skills/pptx/scripts/clean.py:140`: Content-type “validation” checks only the root’s local name. `<Types xmlns="urn:wrong"><Garbage/></Types>` passes, allowing destructive cleanup of an invalid package. The bundled `opc-contentTypes.xsd` requires the OPC namespace and permits only `Default` and `Override` children with required attributes. Reproduce by substituting that XML into an otherwise valid unpacked deck containing an orphan slide, then running `clean.py`. The invalid content-type document is accepted and deletion proceeds. Acceptance was confirmed using mocked filesystem reads.

### consistency: approve

### quality: approve

### optimization: approve

LENS adversarial: findings
LENS integration: clean
LENS source-defect: findings
LENS consistency: clean
LENS quality: clean
LENS optimization: clean
HIGHEST: P1
OVERALL: needs-attention

- Implemented: Finding 1 (P1 adversarial): `plugins/agy/craft/skills/pptx/scripts/clean.py` (`_validate_rels_dom`, `_slide_rids`, `_validate_presentation_package`) now rejects duplicate relationship `Id` attributes, missing/invalid `Id`/`Type`/`Target`/`TargetMode`, wrong namespace, and unexpected children or attributes across all `.rels` files before deleting anything, verified by Case 5 of `test_pptx_clean_refuses_missing_rid_and_malformed_content_types_before_deletion` in `tests/test_agy_plugins.py`.
- Implemented: Finding 2 (P1 adversarial): `plugins/agy/craft/skills/pptx/scripts/apply_theme.js` (`inspectZipBuffer` called in `applyTheme`) now inspects the ZIP/ZIP64 central directory and declared entry sizes/symlinks before calling `JSZip.loadAsync`, verified programmatically and via CLI with `many_entries.pptx` (10001 entries) in `test_pptx_apply_theme_resolves_project_local_deps_and_writes_atomically`.
- Implemented: Finding 3 (P2 source-defect): `plugins/agy/craft/skills/pptx/scripts/clean.py` (`_validate_content_types_dom` called from `_validate_presentation_package`) now enforces the OPC content-types namespace, allowed `<Default>`/`<Override>` child elements and attributes, regex/path rules matching `opc-contentTypes.xsd`, and uniqueness of extensions and part names before any deletion, verified by Case 6 of `test_pptx_clean_refuses_missing_rid_and_malformed_content_types_before_deletion`.

## Round 15: astra (`gpt-6-astra` via `codex`)

- Writer: agy
- Run: 2026-11-14T15:19:55Z
- Candidate: d2de0a48ee0eb1542ec8a74e312c569c7895cf6f
- Effort: medium
- Lenses: adversarial, integration, source-defect, consistency, quality, optimization
- Lines: 34
- Digest: f9e2f2524e38331b

### adversarial: needs-attention

1. **P1**, `plugins/agy/craft/skills/pptx/scripts/apply_theme.js:392`: The guard can inspect a different central directory from JSZip. It permits a gap between the declared directory end and EOCD, while JSZip shifts its reader origin by that gap. Reproduction: supply `crafted.pptx` with 31 padding bytes, a benign 47-byte directory entry, a 31-byte local header, a hostile 47-byte directory entry, then EOCD declaring offset 31, size 47 and one entry. The guard accepts the benign entry; JSZip resolves the directory to offset 109, where the unchecked entry can declare a symlink or oversized member. I reproduced guard acceptance with a 200 MiB symlink entry. The downstream offset follows [JSZip’s parser implementation](https://raw.githubusercontent.com/Stuk/jszip/v3.10.1/lib/zipEntries.js); JSZip was unavailable locally. Require the validated directory to be exactly the directory JSZip consumes.

### integration: approve

No separate findings.

### source-defect: needs-attention

2. **P2**, `plugins/agy/craft/skills/pptx/scripts/clean.py:51`: `_XML_ID_RE` restricts relationship IDs to ASCII, although `opc-relationships.xsd` declares `xsd:ID`, which permits Unicode NCNames. Reproduction: clean an unpacked presentation containing a relationship with `Id="rIdé"` and its matching reference. The new validation refuses a valid package. I verified that the bundled schema accepts this ID and `_validate_rels_dom` rejects it.

3. **P2**, `plugins/agy/craft/skills/pptx/scripts/clean.py:47`: `_CONTENT_TYPE_RE` omits the schema’s escaped-character alternative within quoted parameter values. Reproduction: put `ContentType="application/xml;p=&quot;a\&quot;b&quot;"` on a `Default` entry in an unpacked presentation’s `[Content_Types].xml`, then run the cleaner. I verified that the bundled `opc-contentTypes.xsd` accepts this value while `_validate_content_types_dom` refuses it. Valid input now prevents cleanup.

### consistency: approve

No separate findings.

### quality: approve

No separate findings.

### optimization: approve

No separate findings.

LENS adversarial: findings
LENS integration: clean
LENS source-defect: findings
LENS consistency: clean
LENS quality: clean
LENS optimization: clean
HIGHEST: P1
OVERALL: needs-attention

- Implemented: Finding 1 (P1 adversarial): `plugins/agy/craft/skills/pptx/scripts/apply_theme.js` (`inspectZipBuffer`, `parseZip64Extra`, and `applyTheme`) now requires EOF-aligned last EOCD selection, zero gap between Central Directory and EOCD (and between ZIP64 EOCD and locator), valid local header offsets, and post-load POSIX symlink checks, verified programmatically and via CLI with `gap_crafted.pptx` in `test_pptx_apply_theme_resolves_project_local_deps_and_writes_atomically`.
- Implemented: Finding 2 (P2 source-defect): `plugins/agy/craft/skills/pptx/scripts/clean.py` (`_XML_ID_RE`, `_slide_rids`, `_referenced_slide_rids`, `_validate_slide_id_list`, `_validate_rels_dom`) now accepts full Unicode XML 1.0 `NCName` values with `xs:ID` whitespace normalization, verified by Case 7 (`Id="rId\u00e9"`) of `test_pptx_clean_refuses_missing_rid_and_malformed_content_types_before_deletion`.
- Implemented: Finding 3 (P2 source-defect): `plugins/agy/craft/skills/pptx/scripts/clean.py` (`_is_valid_content_type` called in `_validate_content_types_dom`) replaces `_CONTENT_TYPE_RE` with an 8-state linear-time NFA matching `opc-contentTypes.xsd` `ST_ContentType` (including BasicLatin escapes and Latin-1 Supplement in quoted parameter values) and permits spaces in `Override/@PartName`, verified by Case 7 of `test_pptx_clean_refuses_missing_rid_and_malformed_content_types_before_deletion`.

## Round 16: astra (`gpt-6-astra` via `codex`)

- Writer: agy
- Run: 2026-11-14T15:38:57Z
- Candidate: fa2e0d18729a5f97102565a22c809de77a71dd85
- Effort: medium
- Lenses: adversarial, integration, source-defect, consistency, quality, optimization
- Lines: 32
- Digest: 77d55bc2f003cbee

### adversarial: needs-attention

1. **P1** `plugins/agy/craft/skills/pptx/scripts/clean.py:384`: Validation normalizes `Target` only in a temporary variable. `_referenced_by()` subsequently resolves the original attribute, allowing cleanup to delete referenced media. Reproduce with an otherwise valid unpacked deck containing `ppt/media/image1.png` and a slide relationship with `Target="../media/image1.png "`, then run `clean.py deck`. Validation accepts it, but the reference set contains `'ppt/media/image1.png '`, so line 592 selects the actual image for deletion. An in-memory probe with mocked filesystem deletion reproduced one `unlink` call.

### integration: needs-attention

Finding 1: validation and reference collection interpret the same relationship differently. Normalize at the shared relationship-reading layer before validation and consumption.

### source-defect: needs-attention

Finding 1: the bundled relationship schema declares `Target` as `xs:anyURI`, whose whitespace handling is `collapse`. Keeping trailing whitespace during path resolution violates that interpretation. [XML Schema whitespace rules](https://www.w3.org/TR/xmlschema-2/#rf-whiteSpace)

### consistency: needs-attention

Finding 1: normalized relationship IDs reach consumers, but normalized targets remain local to validation.

### quality: needs-attention

2. **P3** `tests/test_agy_plugins.py:2368`: The claimed PartName-spaces integration case declares `/ppt/slides/slide 1.xml`, but creates and references `slide1.xml`. It passes with a dangling override and never exercises cleanup of an actual space-containing part. Reproduce by running this case and inspecting its fixture paths and assertions.

### optimization: approve

No additional finding.

LENS adversarial: findings
LENS integration: findings
LENS source-defect: findings
LENS consistency: findings
LENS quality: findings
LENS optimization: clean
HIGHEST: P1
OVERALL: needs-attention

- Implemented: Finding 1 (P1 adversarial/integration/source-defect/consistency): `plugins/agy/craft/skills/{docx,pptx,xlsx}/scripts/office/helpers/__init__.py` (`collapse_xml_space`, `read_relationship`, `opc_target`, `get_rel_id_attr`), `plugins/agy/craft/skills/pptx/scripts/clean.py`, and `plugins/agy/craft/skills/pptx/scripts/thumbnail.py` now normalize OPC `xs:anyURI` and `xs:ID` attributes via XML Schema `whiteSpace="collapse"` at the shared helper layer so validation and relationship resolution interpret the exact same target and ID values (plus `clean.py` validates every `.rels` file resides in `_rels/` and resolves safely via `opc_target`), verified by `test_office_helpers_identical_and_safe_extract_bounded` and Case 7 (`Target="../media/image1.png "`) of `test_pptx_clean_refuses_missing_rid_and_malformed_content_types_before_deletion`.
- Implemented: Finding 2 (P3 quality): Case 7 in `tests/test_agy_plugins.py` (`test_pptx_clean_refuses_missing_rid_and_malformed_content_types_before_deletion`) now builds an end-to-end unpacked presentation containing actual `ppt/slides/slide 1.xml`, `ppt/slides/slide 2.xml`, `ppt/media/image1.png`, and `ppt/media/orphan.png` with zero dangling overrides, asserting `slide 1.xml` and `image1.png` survive while `slide 2.xml`, `orphan.png`, and the `slide 2.xml` Content-Type override are cleaned.

## Round 17: astra (`gpt-6-astra` via `codex`)

- Writer: agy
- Run: 2026-11-14T15:52:28Z
- Candidate: a254498a3b89025d28da91fbb1a3d5e1f356c13c
- Effort: medium
- Lenses: adversarial, integration, source-defect, consistency, quality, optimization
- Lines: 36
- Digest: 8567c491e653c2be

### adversarial: approve

No additional findings.

### integration: needs-attention

1. **P2: Normalized IDs break `add_slide.py --after`.** `plugins/agy/craft/skills/pptx/scripts/add_slide.py:284` compares the newly normalized `get_rel_id_attr()` against the raw ID returned at line 376. Reproduce with an unpacked deck whose presentation relationship and matching `p:sldId/@r:id` both contain `" rId1 "`, then run `python add_slide.py deck slide1.xml --after slide1.xml`. The existing slide is rejected as unlisted. An in-memory probe confirmed the mismatch and refusal. Normalize the relationship lookup through `read_relationship()` too.

2. **P2: Office validators still reject the whitespace-bearing relationships this change accepts.** `plugins/agy/craft/skills/pptx/scripts/office/validators/base.py:456` indexes raw IDs, and line 373 resolves raw Targets without the shared helper. Reproduce by running office validation on the new Case 7 deck: its padded relationship ID does not match the unpadded presentation reference, and padded Targets resolve to incorrect filesystem paths. An in-memory probe confirmed `validate_all_relationship_ids()` returns `False` for the equivalent relationship. The sibling docx/xlsx validator copies retain the same logic. Route these consumers through the shared normalization and target resolution.

### source-defect: approve

No additional findings.

### consistency: needs-attention

Finding 2: validation and cleanup still interpret the same stored relationship differently.

### quality: approve

No additional findings.

### optimization: approve

No findings supported by a measured performance failure.

Verification used read-only inspection and in-memory probes with mocked file access. No files were modified.

LENS adversarial: clean
LENS integration: findings
LENS source-defect: clean
LENS consistency: findings
LENS quality: clean
LENS optimization: clean
HIGHEST: P2
OVERALL: needs-attention

- Implemented: Finding 1 (P2 integration): `plugins/agy/craft/skills/pptx/scripts/add_slide.py` now routes `<Relationship>` reads (`Id`, `Type`, `Target`, `TargetMode`), `[Content_Types].xml` `Override/@PartName` checks (`normalize_part_name`), and `presentation.xml` `r:id` scans through the shared whitespace-collapsing helpers in `office.helpers`, preventing ID collisions and `--after` mismatches on padded IDs/targets, verified by `test_pptx_and_docx_scripts_handle_namespace_prefixed_opc_xml` and Case 7 of `test_pptx_clean_refuses_missing_rid_and_malformed_content_types_before_deletion`.
- Implemented: Finding 2 (P2 integration/consistency): `plugins/agy/craft/skills/{docx,pptx,xlsx}/scripts/office/validators/{base.py,pptx.py}`, `plugins/agy/craft/skills/{docx,pptx,xlsx}/scripts/office/helpers/{__init__.py,pptx_theme.py}`, `plugins/agy/craft/skills/pptx/scripts/clean.py`, `plugins/agy/craft/skills/docx/scripts/comment.py`, and `plugins/agy/craft/skills/xlsx/scripts/recalc.py` now share `normalize_part_name`, `read_relationship`, `opc_target`, and `collapse_xml_space` across validation and authoring scripts, verified with `PPTXSchemaValidator.validate()` on the Case 7 deck plus padded-OPC tests in `tests/test_agy_plugins.py`.

## Round 18: astra (`gpt-6-astra` via `codex`)

- Writer: agy
- Run: 2026-11-14T16:13:28Z
- Candidate: 220bafc8da8a2fe8c79fa169cd1c274d41969a93
- Effort: medium
- Lenses: adversarial, integration, source-defect, consistency, quality, optimization
- Lines: 38
- Digest: 4d137f165a66e0f8

### adversarial: needs-attention

1. **P1**: `plugins/agy/craft/skills/pptx/scripts/office/validators/base.py:418` silently skips invalid internal relationships when `opc_target()` returns `None`. That helper also returns `None` for scheme-prefixed targets, not only external relationships.

   Reproduce by adding an image relationship with `Target="ftp://example.com/missing.png"` and `TargetMode="Internal"` to a valid presentation’s `.rels` file, then running `office/validate.py`. The relationship passes the bundled XSD, and reference validation skips checking its nonexistent internal destination. An in-memory probe confirmed both checks return `True`. Reject unresolved internal targets instead of treating them as external. The same defect exists in the docx and xlsx copies.

### integration: needs-attention

Finding 1 affects the shared validators: migrating to `opc_target()` introduced a sentinel whose callers interpret too broadly. A missing internal destination can now pass reference validation.

### source-defect: needs-attention

2. **P1**: `plugins/agy/craft/skills/pptx/scripts/office/helpers/__init__.py:97` treats an Override part name as a relationship target. Relationship resolution removes path segments, but part-name validation must reject empty segments and trailing slashes. These are explicit OPC constraints. [ECMA-376, Part Name Syntax](https://web.mit.edu/~stevenj/www/ECMA-376.pdf)

   Reproduce by replacing a slide’s Override `PartName` with `/ppt//slides/slide1.xml` or `/ppt/slides/slide1.xml/`. Both normalize to `ppt/slides/slide1.xml`; direct probes confirmed `clean._validate_content_types_dom()` accepts both. The new consumers consequently recognize malformed declarations as valid declarations for another name. Validate part-name syntax before normalization. All three helper copies are affected.

### consistency: approve

No additional finding.

### quality: approve

No additional finding.

### optimization: approve

No substantiated finding.

Verification used read-only inspection and in-memory probes. No files were modified; the full suite was not run.

LENS adversarial: findings
LENS integration: findings
LENS source-defect: findings
LENS consistency: clean
LENS quality: clean
LENS optimization: clean
HIGHEST: P1
OVERALL: needs-attention

- Implemented: Finding 1 (P1 adversarial/integration): `opc_target()` in `plugins/agy/craft/skills/{docx,pptx,xlsx}/scripts/office/helpers/__init__.py` now returns `None` only when `TargetMode == "External"`, rejects invalid `TargetMode`, empty targets, URI schemes, authorities, queries, percent-encoded slashes, empty segments, trailing directory segments, and invalid OPC segment syntax with `ValueError`, and `BaseSchemaValidator.validate_file_references()` in `office/validators/base.py` records any failed or `None` internal target in `broken_refs` instead of silently skipping it, verified by `test_office_helpers_identical_and_safe_extract_bounded` and `test_pptx_clean_refuses_missing_rid_and_malformed_content_types_before_deletion`.
- Implemented: Finding 2 (P1 source-defect): `normalize_part_name()` in `plugins/agy/craft/skills/{docx,pptx,xlsx}/scripts/office/helpers/__init__.py` now validates ECMA-376 Part 2 section 9.1.1 PartName syntax (leading `/`, no trailing `/`, no empty segments, no `.`/`..`/trailing-dot segments, no `?`/`#`/`\`/`%2F`/`%5C`, no control chars) before normalizing, `BaseSchemaValidator.validate_content_types()` compares case-insensitive `<Override>` PartNames and flags duplicates, and `clean._validate_content_types_dom()` delegates to `normalize_part_name()`, verified in `test_office_helpers_identical_and_safe_extract_bounded` and `test_pptx_clean_refuses_missing_rid_and_malformed_content_types_before_deletion`.

## Round 19: astra (`gpt-6-astra` via `codex`)

- Writer: agy
- Run: 2026-11-14T16:30:16Z
- Candidate: 07691e339c36cebf7c582127448584df35a154b8
- Effort: medium
- Lenses: adversarial, integration, source-defect, consistency, quality, optimization
- Lines: 32
- Digest: a481c1aa177eb20c

### adversarial: needs-attention

1. **P1** `plugins/agy/craft/skills/pptx/scripts/office/helpers/__init__.py:92`: Internal targets are resolved before their complete URI syntax is validated. Reproduce with `Target="slides/slide1.xml#bad%GG"` in `ppt/_rels/presentation.xml.rels`: `opc_target()` returns `ppt/slides/slide1.xml`, and the cleaner’s `_validate_rels_dom()` accepts it, verified in memory. An existing slide therefore lets a malformed internal URI pass the refusal check. Invalid escapes in paths, such as `slide%GG.xml`, also survive `unquote()`. Validate escape syntax and permitted characters before splitting or decoding. [RFC 3986](https://www.rfc-editor.org/rfc/rfc3986.html#section-2.1)

### integration: approve

No additional findings.

### source-defect: needs-attention

2. **P1** `plugins/agy/craft/skills/pptx/scripts/office/helpers/__init__.py:156`: `normalize_part_name()` decodes percent-encoded unreserved characters instead of rejecting them. ECMA-376 Part 2, §9.1.1, constraint M1.8 prohibits these in PartNames. Reproduce by changing an existing slide’s Override to `PartName="/ppt/slides/%73lide1.xml"` in `[Content_Types].xml`. The helper returns `ppt/slides/slide1.xml`, and `_validate_content_types_dom()` accepts the Override, verified in memory. Consequently, both content-type validation and cleaner admission accept a declaration they must refuse. All three helper copies contain this defect. [ECMA-376 Part 2](https://cdn.ooxml.dev/ecma-376/part2.pdf)

### consistency: approve

No additional findings.

### quality: approve

No additional findings.

### optimization: approve

No findings.

LENS adversarial: findings
LENS integration: clean
LENS source-defect: findings
LENS consistency: clean
LENS quality: clean
LENS optimization: clean
HIGHEST: P1
OVERALL: needs-attention

- Implemented: Finding 1 (P1 adversarial): `opc_target()` in `plugins/agy/craft/skills/{docx,pptx,xlsx}/scripts/office/helpers/__init__.py` now validates percent-escape hex syntax (`%(?![0-9A-Fa-f]{2})`), strict UTF-8 decoding, control/surrogate/noncharacter bounds, RFC 3986 path/fragment characters, and External `xs:anyURI` syntax (`is_valid_any_uri()`, also enforced for `<Relationship Type>` in `pptx/scripts/clean.py` and External targets in `office/validators/base.py`) before splitting or resolving fragments, verified by `test_office_helpers_identical_and_safe_extract_bounded` and `test_pptx_clean_refuses_missing_rid_and_malformed_content_types_before_deletion`.
- Implemented: Finding 2 (P1 source-defect): `normalize_part_name()` in `plugins/agy/craft/skills/{docx,pptx,xlsx}/scripts/office/helpers/__init__.py` now enforces ECMA-376 Part 2 section 9.1.1 constraint M1.8 by rejecting percent-encoded RFC 3986 unreserved characters (e.g. `%73`, `%31`, `%2d`, `%2e`, `%5f`, `%7e`) alongside invalid hex escapes, invalid UTF-8 sequences, control octets, and disallowed URI characters before normalizing, verified in `test_office_helpers_identical_and_safe_extract_bounded` and `test_pptx_clean_refuses_missing_rid_and_malformed_content_types_before_deletion`.

## Round 20: astra (`gpt-6-astra` via `codex`)

- Writer: agy
- Run: 2026-11-14T16:49:16Z
- Candidate: 4d36a9ba34b8b5c11f92c2a9ed47fa75f2ff9513
- Effort: medium
- Lenses: adversarial, integration, source-defect, consistency, quality, optimization
- Lines: 32
- Digest: 303af71bb9765009

### adversarial: needs-attention

1. **P1** `plugins/agy/craft/skills/pptx/scripts/office/helpers/__init__.py:128`: `is_valid_any_uri()` accepts malformed URI structure, including `http://host:abc/a` and `1bad:type`. Reproduce by placing the former in an External relationship’s `Target`, or the latter in `Type`, in `ppt/_rels/presentation.xml.rels`. Calling `clean._validate_rels_dom()` accepts both; validation against the bundled `opc-relationships.xsd` rejects both. Consequently, cleanup’s pre-deletion validation passes damaged packages it promises to refuse. The same defect exists in all three helper copies.

### integration: needs-attention

Finding 1 creates inconsistent consumer behavior: cleanup accepts these relationships while the schema validator rejects them. Reproduced directly against both consumers without writing files.

### source-defect: needs-attention

2. **P3** `plugins/agy/craft/skills/pptx/scripts/office/helpers/__init__.py:137`: The bracketed-host regex excludes RFC 3986’s `IPvFuture` syntax. An External relationship with `Target="http://[v1.a]/a"` passes the bundled OPC schema but raises `RefusedToClean`. Reproduced through `_validate_rels_dom()`. This is an uncommon input, but contradicts the claimed RFC 3986 validation. [RFC 3986, section 3.2.2](https://www.rfc-editor.org/rfc/rfc3986#section-3.2.2).

### consistency: needs-attention

Finding 1 also affects the shared validation contract: `is_valid_any_uri()` is not equivalent to the bundled schema’s `xs:anyURI` validation. All three copies reproduce the same acceptance gap.

### quality: approve

No additional findings.

### optimization: approve

No demonstrated performance defect or missed measured target.

LENS adversarial: findings
LENS integration: findings
LENS source-defect: findings
LENS consistency: findings
LENS quality: clean
LENS optimization: clean
HIGHEST: P1
OVERALL: needs-attention

- Implemented: Finding 1 (P1 adversarial/integration/consistency): `is_valid_any_uri()` in `plugins/agy/craft/skills/{docx,pptx,xlsx}/scripts/office/helpers/__init__.py` now enforces RFC 3986 scheme-less first-segment colon rejection (`1bad:type`), single-`@` userinfo, and strict numeric `:port` (`http://host:abc/a`), and `BaseSchemaValidator.validate_file_references()` in `office/validators/base.py` checks `is_valid_any_uri(rel_type)` consistently with `clean._validate_rels_dom()` and `opc-relationships.xsd`, verified in `test_office_helpers_identical_and_safe_extract_bounded` and `test_pptx_clean_refuses_missing_rid_and_malformed_content_types_before_deletion`.
- Implemented: Finding 2 (P3 source-defect): `is_valid_any_uri()` bracketed-host validation in `plugins/agy/craft/skills/{docx,pptx,xlsx}/scripts/office/helpers/__init__.py` now supports RFC 3986 IPv6 literals via `ipaddress.IPv6Address` and RFC 3986 `IPvFuture` literals (`http://[v1.a]/a`), verified against `opc-relationships.xsd` in `test_office_helpers_identical_and_safe_extract_bounded` and `test_pptx_clean_refuses_missing_rid_and_malformed_content_types_before_deletion`.

## Round 21: astra (`gpt-6-astra` via `codex`)

- Writer: agy
- Run: 2026-11-14T17:01:46Z
- Candidate: 146c87cd9d45fdf167561f2cd0714cfd9066d382
- Effort: medium
- Lenses: adversarial, integration, source-defect, consistency, quality, optimization
- Lines: 36
- Digest: 299c44670452c18c

### adversarial: approve

No additional findings.

### integration: approve

No additional findings.

### source-defect: needs-attention

1. **P2: Valid empty ports are rejected.** `plugins/agy/craft/skills/docx/scripts/office/helpers/__init__.py:29` defines `_PORT_RE` with `+`, requiring at least one digit. Both authority branches enforce this, and the defect exists in the `pptx` and `xlsx` copies. RFC 3986 defines `port = *DIGIT` and explicitly identifies `http://example.com:/` as equivalent to `http://example.com/`. [RFC 3986](https://www.rfc-editor.org/rfc/rfc3986.html#section-3.2.3)

   **Reproduction:** An unpacked presentation containing an external hyperlink with `Target="http://example.com:/"` in `ppt/slides/_rels/slide1.xml.rels` is refused by `clean.py`. Calling its `_validate_rels_dom()` with that relationship reproduced `RefusedToClean`; `http://[::1]:/` also failed, while `http://example.com:80/` passed.

   `tests/test_agy_plugins.py:723` entrenches the error by classifying an empty port as malformed. Allow zero digits and test both hostname and bracketed-host cases. The installed lxml schema validator also rejects these inputs, so its behavior conflicts with RFC 3986 here; matching it does not establish RFC conformity.

### consistency: approve

No additional findings.

### quality: approve

No additional findings beyond finding 1’s incorrect test expectation.

### optimization: approve

No substantiated findings.

LENS adversarial: clean
LENS integration: clean
LENS source-defect: findings
LENS consistency: clean
LENS quality: clean
LENS optimization: clean
HIGHEST: P2
OVERALL: needs-attention

- Implemented: Finding 1 (P2 source-defect): `_PORT_RE` in `plugins/agy/craft/skills/{docx,pptx,xlsx}/scripts/office/helpers/__init__.py` now uses `^[0-9]*\Z` so RFC 3986 empty ports (`port = *DIGIT`, e.g. `http://example.com:/` and `http://[::1]:/`) are accepted by `is_valid_any_uri()`, `opc_target()`, `clean._validate_rels_dom()`, and `BaseSchemaValidator.validate_file_references()`, with both hostname and bracketed IPv6 empty-port unit and end-to-end tests added in `tests/test_agy_plugins.py`.

## Round 22: astra (`gpt-6-astra` via `codex`)

- Writer: agy
- Run: 2026-11-14T17:08:29Z
- Candidate: 4c658e0485ee119c1e2777131cfee32808f22e92
- Effort: medium
- Lenses: adversarial, integration, source-defect, consistency, quality, optimization
- Lines: 32
- Digest: afbae89b93863ce6

### adversarial: needs-attention

1. **P1** `plugins/agy/craft/skills/pptx/scripts/clean.py:602`: Cleaning can delete a referenced image because resolved relationship targets and filesystem paths are compared as case-sensitive strings. On Windows, unpack a normal deck containing `ppt/media/image1.png`, set its image relationship target to `../media/IMAGE1.PNG`, then run `clean.py <unpacked_dir>`. Validation accepts the package, but cleaning deletes the image and leaves its relationship dangling. Reproduced through `clean_unused_files()` using an in-memory Windows filesystem, without modifying files. Apply consistent OPC part-name comparison to resource references and deletion candidates; the theme and notes comparisons have the same defect.

### integration: needs-attention

2. **P2** `plugins/agy/craft/skills/docx/scripts/office/helpers/__init__.py:572`: `rezip()` includes an existing output package when that output is inside the input directory. Run `python plugins/agy/craft/skills/docx/scripts/office/pack.py unpacked unpacked/result.docx` twice. The second package contains the entire previous `result.docx`; subsequent runs accumulate nested copies, potentially retaining content removed from the current document. Neither the caller nor this helper rejects that destination or excludes it. This is statically verified and affects all three identical helper copies.

### source-defect: approve

No finding against the empty-port grammar in [RFC 3986 §3.2.3](https://www.rfc-editor.org/rfc/rfc3986.html#section-3.2.3).

### consistency: approve

No additional findings.

### quality: approve

No additional findings.

### optimization: approve

No independent finding beyond finding 2.

LENS adversarial: findings
LENS integration: findings
LENS source-defect: clean
LENS consistency: clean
LENS quality: clean
LENS optimization: clean
HIGHEST: P1
OVERALL: needs-attention

- Implemented: Finding 1 (P1 adversarial): Added ECMA-376 Part 2 section 9.1.1.4 ASCII case-folding helper `opc_part_key()` across `plugins/agy/craft/skills/{docx,pptx,xlsx}/scripts/office/helpers/__init__.py` and switched `clean.py` (`_package_files_by_key()`, `_validate_slide_id_list()`, `_validate_presentation_package()`, `remove_orphaned_slides()`, `remove_orphaned_rels_files()`, `remove_orphaned_files()`, `update_content_types()`), `BaseSchemaValidator` (`validate_file_references()`, `validate_all_relationship_ids()`, `validate_content_types()`), `add_slide.py`, `comment.py`, `thumbnail.py`, and `recalc.py` to compare OPC part names and `.rels` lookups case-insensitively across both Windows and Linux, with regression tests in `tests/test_agy_plugins.py`.
- Implemented: Finding 2 (P2 integration): Added `reject_output_inside_source()` in `plugins/agy/craft/skills/{docx,pptx,xlsx}/scripts/office/helpers/__init__.py` and enforced it at the top of `rezip()` and `pack.pack_package()` before directory creation or temp-file creation, with unit and CLI regression tests in `tests/test_agy_plugins.py`.
