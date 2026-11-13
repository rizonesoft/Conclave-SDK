# What stops RasterFold and Impossible OS adopting the todo graph

Measured 2026-11-13 by `scripts/adoption-dry-run.py` (D03 T01 §5), with the kit's every-fault validation (`validate --all`, D03 T01 §8) at SDK `807a23711533c3aad91702efa9811f397618ece2` (Impossible OS) and `7fe94ddf57446de6a7fe21987e4721f018863dc3` (RasterFold), each validator committed and clean. Each project was cloned with its history into scratch, its working tree's `todo/` and receipts folder were copied over the clone (both trees carried another session's uncommitted work, so that work is measured too), and a `todo/plan.json` written for it became the snapshot's own. Neither source was written: every git call against it took `--no-optional-locks`, and both copies held still (one copy each, no file moved).

| Project | Commit | Files copied | Sections | Stamped | Faults | Classes |
| ------- | ------ | -----------: | -------: | ------: | -----: | ------: |
| RasterFold | `41bc4662e90a` | 326 | 259 | 126 | 1,215 | 22 |
| Impossible OS | `d73ad210525d` | 5,217 | 2,596 | 915 | 19,711 | 32 |

The inputs are kept beside the output in the session scratch folder: `manifest.json` (every copied file's SHA-256, the effective `plan.json`, both commits) and `classes.json` (the classes, then every fault) for each run.

## The configuration each run used

- RasterFold: `phase_list` of its 60 milestone phases (0 to 59, as its generated plan's `### Phase N` headings number them) and 99 for `todo/99-manual`, each phase named as its plan names it, and `needs` holding its seven Needs as slugs (`windows-host`, `ffmpeg-jxl`, `network`, `idle-machine`, `gpu`, `arm64-device`, `fpga-board`, from `NEEDS_ALLOWED`, `scripts/todo-graph.py:236`). Default caps and receipts folder.
- Impossible OS: `phase_list` of its 18 phases (0 to 16 and 18, from its plan's headings), each named, `layout.receipts` set to `.claude/overnight/reviews`, default Needs and caps.

## RasterFold

Every class the run reported, with its decision. `places` is the sections (or files) that carry it. The first run, at `bf30b3804d23` with SDK `e6d21ca`, reported the same 22 classes and counts.

| # | Class | Places | Example | Decision |
| - | ----- | -----: | ------- | -------- |
| R1 | No Build order | 259 | `D00 T01 §1` | Project: open sections; stamped ones by D03 T01 §9 |
| R2 | No Phase field | 259 | `D00 T01 §1` | Project: write each section's plan phase |
| R3 | No Surface field | 259 | `D00 T01 §1` | Project: `no`, `yes` on the 11 with Fidelity |
| R4 | No Needs field | 175 | `D00 T01 §1` | Project: `**Needs:** none` |
| R5 | Needs phrase, not a slug | 84 | `D01 T02 §1` | Project: phrases to slugs, map below |
| R6 | Findings file with no returned review | 46 | `D00 T01 §11` | Kit: D03 T01 §9 freezes pre-adoption stamps |
| R7 | No Current state | 35 | `TODO-01-dev-automation.md` | Project: one measured line per file |
| R8 | Freeze check outside a frozen file | 15 | `D01 T04 §1` | Project: `frozen: true` or drop the line |
| R9 | Test checkpoint not runnable | 12 | `D01 T03 §3` | Project: a backticked command |
| R10 | Three-pass fields on a receipt | 11 | `D00 T05 §9` | Kit: D03 T01 §9 |
| R11 | Pin with an unknown writer | 6 | `D00 T05 §7` | Kit: D03 T01 §9 |
| R12 | Pin reviewer with an unknown CLI | 6 | `D01 T03 §2` | Kit: D03 T01 §9 |
| R13 | Plan review not as the kit records it | 4 | `D00 T01 §10` | Kit: D03 T01 §9 |
| R14 | Implementation Order unreadable | 3 | `TODO-05-lsp-subagents-...` | Project: kit table shape |
| R15 | Checklist size or Commit not last | 2 | `D01 T03 §2` | Project: split or reorder |
| R16 | Completion review not as recorded | 1 | `D01 T03 §1` | Kit: D03 T01 §9 |
| R17 | Deliverable over 88 characters | 1 | `D00 T05 §7` | Project: shorten the row |
| R18 | Stamp line malformed | 1 | `D00 T01 §7` | Kit: D03 T01 §9 |
| R19 | No Test checkpoint | 1 | `D01 T05 §4` | Project: write one |
| R20 | Files left out of the root index | 1 (33) | `TODO-00-INDEX.md` | Kit: D03 T01 §11 |
| R21 | Reconciliation not last | 1 | `D09 T01 §2` | Kit: D03 T01 §9 |
| R22 | Receipt pin commit differs | 1 | `D01 T05 §1` | Kit: D03 T01 §9 |
| R23 | Host `Requires` gate (not a fault) | 32 | `REQUIRES_ALLOWED`, `:264` | Kit: D03 T01 §10; values into Needs |

The classes as the script printed them:

- R1 `executable Build order required: <ref>`; R2 `missing Phase field`; R3 `missing Surface field`; R4 `missing Needs field`.
- R5 `unknown/duplicate Needs (<value>): <ref>`: `Idle machine (timing)` 44, `ffmpeg with libjxl (benchmarks)` 34, `Network (downloads)` 2, `Windows host (build/test)` 1, `GPU (compute)` 1, `ARM64 device` 1, `FPGA board` 1. The slug for each is the value `NEEDS_ALLOWED` maps it to.
- R6 `<path> holds no returned review: <ref>`; R7 `missing Current state field`; R8 `Freeze check must match frozen frontmatter: <ref>`; R9 `runnable Test checkpoint required: <ref>`.
- R10 `a three-pass receipt records passes_spent and pass_cap, and only a three-pass receipt: <ref>`.
- R11 `the reviewer pin at <sha> does not load: [routes] may only name the writers claude, codex, agy, gemini: <ref>`.
- R12 `the reviewer pin at <sha> does not load: reviewer 'spark' needs cli = one of codex, agy, claude: <ref>`.
- R13 `<path> must hold exactly one plan review returned by another model family and ending PLAN: complete or gaps, then OVERALL: approve or needs-attention, not N: <ref>`.
- R14 `invalid implementation order: <path>`; R15 `N-N items (at least one work item, Commit last) required: <ref>`.
- R16 `<path> must hold exactly one completion review returned by another model family and ending COMPLETION: complete or COMPLETION: gaps, not N: <ref>`.
- R17 `deliverable/title over N chars (wraps raw md table): <ref>`; R18 `invalid stamp: <ref>`; R19 `missing Test checkpoint field`; R20 `missing from root index: <path>` (33 files).
- R21 `only the last reconciliation in <path> may end RECONCILIATION: complete: <ref>`; R22 `receipt schedule_sha is not <sha>, the commit whose pin the section ran under: <ref>`.

R23 is RasterFold's `**Requires:**` line (32 sections: `windows-runtime` 14, `display-session` 7, `linux-display` 2 and others, each with its reason), checked against the host by `detect_context` (`scripts/todo-graph.py:296`). The kit reads no such field, so it raised nothing, and a runner on the kit could start a row whose host is absent. Its values become Needs (`display-session` and `operator` are kit defaults; `windows-runtime`, `linux-runtime` and `linux-display` join `needs` in `plan.json`), and D03 T01 §10 gives the kit the host check `Requires` does today.

## Impossible OS

Every class the run at `d73ad210525d` reported, one row each. The first run (at `9ece40d6c000`, SDK `e6d21ca`) stopped at the tables: the validator skipped a section whose Implementation Order row it could not read, and a repeated `Verified:` line raised out of `validate --all`. Both were gaps in D03 T01 §8, fixed in this section (`7fe94dd`, `807a237`), so this run checks every readable section body. Of the 2,596 sections, 2,554 were checked one by one; the other 42 are the sections of the two files whose frontmatter does not parse (I28: `TODO-10-documentation-site.md` 33, `TODO-09-repository-transfer-rizonetech.md` 9), which the validator reads no further.

| # | Class | Places | Example | Decision |
| - | ----- | -----: | ------- | -------- |
| I1 | No Build order | 2,554 | `D00 T01 §1` | Project: open sections; stamped by D03 T01 §9 |
| I2 | No Phase field | 2,554 | `D00 T01 §1` | Project: phase equals domain number |
| I3 | No Surface field | 2,554 | `D00 T01 §1` | Project: per section |
| I4 | No Needs field | 2,544 | `D00 T01 §1` | Project: `**Needs:** none` |
| I5 | No Test checkpoint | 1,166 | `D00 T04 §47` | Project: open sections; stamped by D03 T01 §9 |
| I6 | Stamp line not the kit's | 865 | `D00 T01 §1` | Kit: D03 T01 §9 |
| I7 | Checklist size or Commit not last | 534 | `D00 T01 §13` | Project: open sections; stamped by D03 T01 §9 |
| I8 | Checklist item in another spelling | 519 (2,217) | `D00 T01 §13` | Project: one item per `- [ ]` line |
| I9 | Deferred names no owner section | 302 (417) | `D00 T01 §4` | Project: an XREF to a section, or Resolved |
| I10 | No Adjacency line in Outcome | 225 | `TODO-01-developer-tooling-stack` | Project: an Adjacency line per file |
| I11 | Implementation Order invalid | 225 | the same file | Project: kit table shape |
| I12 | Implementation row malformed | 225 (2,520) | the same file | Project: kit table shape |
| I13 | Row and body sections differ | 225 | the same file | Project: kit table shape |
| I14 | Level-two headings out of order | 223 | the same file | Project: kit heading order |
| I15 | Test checkpoint not runnable | 200 | `D00 T01 §2` | Project: a backticked command |
| I16 | No Current state | 158 | the same file | Project: one measured line per file |
| I17 | XREF names no single section | 133 | the same file | Project: one reference per XREF |
| I18 | Stamped with open items | 89 | `D00 T07 §19` | Kit: D03 T01 §9 |
| I19 | Verification not last | 17 | `TODO-30-system-health-...` | Project: move Verification last |
| I20 | No Verification | 17 | the same file | Project: write one |
| I21 | Deliverable over 88 characters | 14 | `D00 T06 §4` | Project: shorten the row |
| I22 | Needs value not configured | 10 | `D01 T02 §18` | Key: `bare-metal` in `needs` |
| I23 | Resolved names no owner section | 7 (8) | `D00 T04 §23` | Project: an XREF to a section |
| I24 | TODO filename outside the pattern | 5 | `TODO-A-SSDT-Master-Table.md` | Project: renumber the file |
| I25 | Repeated Verified line | 4 | `D00 T08 §12` | Project: one stamp per section |
| I26 | No Inputs | 3 | `TODO-05-serial-analyze.md` | Project: write one |
| I27 | Files left out of a domain index | 3 | `02-kernel-core/INDEX.md` | Project: add the rows |
| I28 | Frontmatter malformed | 2 | `TODO-09-repository-transfer-...` | Project: fix the file |
| I29 | No TODO heading | 2 | `TODO-28-bsod-ux-enhancements.md` | Project: add the heading |
| I30 | Frontmatter field missing | 1 | `TODO-29-boot-perf-health-...` | Project: fix the file |
| I31 | No Goal | 1 | `TODO-11-warm-kernel-update-...` | Project: write one |
| I32 | Files left out of the root index | 1 (221) | `TODO-00-INDEX.md` | Kit: D03 T01 §11 |

The classes as the script printed them (counts in brackets are faults where a place carries several):

- I1 `executable Build order required: <ref>`; I2 `missing Phase field`; I3 `missing Surface field`; I4 `missing Needs field`; I5 `missing Test checkpoint field`.
- I6 `invalid stamp: <ref>`: the project's stamp is `> **Verified:** 2026-04-17 | commit `ad4d3fa4` | 5/5 items | build OK | ...`, an abbreviated commit and evidence fields, where the kit's is `<date> | §N | <40-character commit>`.
- I7 `N-N items (at least one work item, Commit last) required: <ref>`; I8 `malformed checklist item: <ref>` (indented sub-items such as `  - [x] ...` under an item).
- I9 `Deferred without a resolving owner: <ref>`: deferrals that name a question, a file or a commit instead of a section (`> **Deferred:** awaiting-answer Q42 ...`).
- I10 `exactly one Adjacency line inside Outcome required: <path>`; I11 `invalid implementation order: <path>`.
- I12 `malformed implementation row: <path>`: the table is `| ⭐ | Order | Deliverable | Depends On | Status |`, a priority column first and no `Section` column, with ranges in dependency cells (`§1-§6`).
- I13 `row/body mismatch: <path>`; I14 `level-two headings must be Inputs, Outcome, Implementation Order, the sections and Verification, once each and in that order: <path>`.
- I15 `runnable Test checkpoint required: <ref>`; I16 `missing Current state field`.
- I17 `XREF must name exactly one well-formed section: <line>`: lists of sections (`§2,§3`), ranges, file links with anchors, and blockquote notes (`Deferred:`, `Accepted:`) whose XREF names a file with no section.
- I18 `unfinished stamped checklist: <ref>`; I19 `Verification must follow numbered sections: <path>`; I20 `missing Verification: <path>`.
- I21 `deliverable/title over N chars (wraps raw md table): <ref>`; I22 `unknown/duplicate Needs (<value>): <ref>`, every one `bare-metal`; I23 `Resolved without a resolving owner: <ref>`.
- I24 `invalid TODO filename: <path>`; I25 `duplicate Verified field`; I26 `missing Inputs: <path>`; I27 `missing from domain index: <path>`.
- I28 `invalid or duplicate frontmatter: <path>`; I29 `missing TODO heading: <path>`; I30 `frontmatter fields: <path>`; I31 `missing Goal field`; I32 `missing from root index: <path>` (221 files).

Impossible OS's stamps (I6, I18) point at review transcripts in `.claude/overnight/reviews` (`*.out`), not the kit's JSON receipts, so they take the same path as RasterFold's 126 through D03 T01 §9.

## Kit changes, each with its section

- D03 T01 §9, pre-adoption stamps frozen at adoption: 126 RasterFold and 915 Impossible OS stamps were written by each project's own stamp and reviewer, so their stamps and receipts (R6, R10 to R13, R16, R18, R21, R22, I6) and their stamped bodies (R1, I1, I5, I7, I18) cannot meet the kit's current receipt format. The kit's rule is that a stamped section is never rewritten (`todo/README.md`, Brownfield code), and `legacy-receipts.json` already freezes old receipts by digest, but nothing writes that file for a project. The section adds the command that does, once, at adoption.
- D03 T01 §10, ready rows filtered by the hosts this session reaches: RasterFold's `Requires` gate (R23) skips a row whose host is absent; the kit's `query ready` lists it (`process-plan` says so and leaves the check to the agent).
- D03 T01 §11, a root index that lists domains: both projects keep the root index at domain altitude, as the kit's own `todo/README.md` describes it ("root index: domain order + active work"), and the validator demands every file in it (R20: 33 files, I32: 221).
- D03 T01 §13, section checks run when its table row cannot be read: a gap in `validate --all` itself, which hid every section-level class of Impossible OS behind its tables. This section built it (`7fe94dd`, with the repeated-stamp crash fixed in `807a237`) because its measurement needed it; D03 T01 §13 verifies and stamps it.
- D03 T01 §12, validation git calls cached per run: not a refusal, a cost the runs measured. `validate` on the SDK's 77 sections takes 61 seconds on Windows, 441 git processes (`cat-file`, `merge-base`, `show`) and `plan_config` read 220 times; the cost grows with every stamp, and Impossible OS carries 915 to the SDK's 42, on every pre-commit.

## Guidance against each project's caps

Both `plan.json` files keep the default caps (55 sections per file, 30 items, 88-character Deliverables, 120-character plan rows): no file in either project passed 55 sections and 15 Deliverables passed 88 (R17, I21), which the decision is to shorten, so neither needs a cap of its own. Read against those caps, `add-todo`, `create-todo` and `groom-plan` state each limit with its `caps` key and default, and no line misleads an agent working either project. One figure is tied to no cap at all: "raw Markdown table rows stay under 140 characters" (`create-todo/SKILL.md:25`, `groom-plan/SKILL.md:48`, `todo/README.md:56`) beside the 120-character `table_row` cap and AGENTS.md's 120; it is filed in `todo/findings.md`.

## Decisions taken without the owner

- Project-side changes are the projects' own work, done in their repositories when each adopts the kit; nothing here edits them. Reversing that (the kit accepting each project's shape) costs a configuration key per difference and a validator that reads two formats.
- Phase from the plan headings, Needs as slugs, and `Requires` values as Needs: the kit's shape already expresses each, so no key was added for them. Reversing one costs a key in `plan_config` and its tests.
- Impossible OS's `bare-metal` Need (I22) becomes a `needs` key in its `plan.json`, the one class a key answers. Reversing it costs one value.
- A section under an unreadable table row is checked from its body alone and is never a node of the graph: guessing its row would report dependency faults the tree does not have. Reversing that costs a second row parser.
