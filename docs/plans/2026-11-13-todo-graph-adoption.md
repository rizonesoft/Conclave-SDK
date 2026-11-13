# What stops RasterFold and Impossible OS adopting the todo graph

Measured 2026-11-13 by `scripts/adoption-dry-run.py` (D03 T01 §5), with the kit's every-fault validation (`validate --all`, D03 T01 §8) at SDK `e6d21ca661f809b27893bd174037d8c68bfeca18`, its validator clean. Each project was cloned with its history into scratch, its working tree's `todo/` and receipts folder were copied over the clone (both trees carried another session's uncommitted work, so that work is measured too), and a `todo/plan.json` written for it became the snapshot's own. Neither source was written: every git call against it took `--no-optional-locks`, and both copies held still (one copy each, no file moved).

| Project | Commit | Files copied | Sections | Stamped | Faults | Classes |
| ------- | ------ | -----------: | -------: | ------: | -----: | ------: |
| RasterFold | `bf30b3804d23` | 326 | 259 | 126 | 1,215 | 22 |
| Impossible OS | `9ece40d6c000` | 5,211 | 2,596 | 915 | 3,981 | 17 |

The inputs are kept beside the output in the session scratch folder: `manifest.json` (every copied file's SHA-256, the effective `plan.json`, both commits) and `classes.json` (the classes, then every fault) for each run.

## The configuration each run used

- RasterFold: `phase_list` of its 60 milestone phases (0 to 59, as its generated plan's `### Phase N` headings number them) and 99 for `todo/99-manual`, each phase named as its plan names it, and `needs` holding its seven Needs as slugs (`windows-host`, `ffmpeg-jxl`, `network`, `idle-machine`, `gpu`, `arm64-device`, `fpga-board`, from `NEEDS_ALLOWED`, `scripts/todo-graph.py:236`). Default caps and receipts folder.
- Impossible OS: `phase_list` of its 18 phases (0 to 16 and 18, from its plan's headings), each named, `layout.receipts` set to `.claude/overnight/reviews`, default Needs and caps.

## RasterFold

Every class the run reported, with its decision. `places` is the sections (or files) that carry it.

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

The kit's validator reads a file's Implementation Order before its sections, and every file failed there, so the run's classes are file-level. The section-level fields were counted directly on the snapshot: of 2,596 sections, `**Phase:**` 0, `**Needs:**` 12, `**Surface:**` 0, `**Build order:**` 0, `**Test checkpoint:**` 1,462, and 915 carry a `Verified:` stamp. The validator skips a section whose table row it cannot read (`todo_graph.py:1074`), so these are counted, not measured: D03 T01 §13 makes it check them and re-runs this measure, and until then they have rows here (I12 to I16) beside the measured ones.

| # | Class | Places | Example | Decision |
| - | ----- | -----: | ------- | -------- |
| I1 | Implementation row malformed | 225 (2,520) | `TODO-01-developer-tooling-stack` | Project: kit table shape |
| I2 | Implementation Order invalid | 225 | the same file | Project: as I1 |
| I3 | Row and body sections differ | 225 | the same file | Project: as I1 |
| I4 | No Adjacency line in Outcome | 225 | the same file | Project: an Adjacency line per file |
| I5 | Level-two headings out of order | 223 | the same file | Project: kit heading order |
| I6 | No Current state | 158 | the same file | Project: one measured line per file |
| I7 | XREF names no single section | 133 | `TODO-01-vmm-memory-protection` | Project: one reference per XREF |
| I8 | Verification not last | 17 | `TODO-30-system-health-recovery-...` | Project: move Verification last |
| I9 | No Verification | 17 | the same file | Project: write one |
| I10 | TODO filename outside the pattern | 5 | `TODO-A-SSDT-Master-Table.md` | Project: renumber the file |
| I11 | Inputs, heading, Goal or frontmatter | 9 | `TODO-05-serial-analyze.md` | Project: fix each file |
| I12 | No Phase field (counted) | 2,596 | every section | Project: phase equals domain number |
| I13 | No Needs field (counted) | 2,584 | all but 12 | Project: `**Needs:** none` |
| I14 | No Surface field (counted) | 2,596 | every section | Project: per section |
| I15 | No Build order (counted) | 2,596 | every section | Project: open sections; stamped by D03 T01 §9 |
| I16 | No Test checkpoint (counted) | 1,134 | 2,596 less 1,462 | Project: open sections; stamped by D03 T01 §9 |
| I17 | Files left out of an index | 1 (221), 3 | `TODO-00-INDEX.md` | Kit: D03 T01 §11 (root); project: 3 domain rows |

The classes as the script printed them:

- I1 `malformed implementation row: <path>` (2,520 rows in 225 files): the table is `| ⭐ | Order | Deliverable | Depends On | Status |`, a priority column first and no `Section` column, and dependency cells use ranges (`§1-§6`).
- I2 `invalid implementation order: <path>`; I3 `row/body mismatch: <path>`; I4 `exactly one Adjacency line inside Outcome required: <path>`.
- I5 `level-two headings must be Inputs, Outcome, Implementation Order, the sections and Verification, once each and in that order: <path>`; I6 `missing Current state field`.
- I7 `XREF must name exactly one well-formed section: <line>`: lists of sections (`§2,§3`), ranges, file links with anchors, and blockquote notes (`Deferred:`, `Accepted:`) that carry an XREF to a file with no section.
- I8 `Verification must follow numbered sections: <path>`; I9 `missing Verification: <path>`; I10 `invalid TODO filename: <path>`.
- I11 `missing Inputs: <path>` 3, `missing TODO heading: <path>` 2, `invalid or duplicate frontmatter: <path>` 2, `frontmatter fields: <path>` 1, `missing Goal field` 1.
- I17 `missing from root index: <path>` (221 files) and `missing from domain index: <path>` (3 files).

Impossible OS's receipts (`.claude/overnight/reviews`, `*.out` review transcripts, not the kit's JSON receipts) were not reached either: its 915 stamps take the same path as RasterFold's 126 through D03 T01 §9.

## Kit changes, each with its section

- D03 T01 §9, pre-adoption stamps frozen at adoption: 126 RasterFold and 915 Impossible OS stamps were written by each project's own stamp and reviewer, so their receipts (R6, R10 to R13, R16, R18, R21, R22) and their stamped bodies (R1, I15, I16) cannot meet the kit's current receipt format. The kit's rule is that a stamped section is never rewritten (`todo/README.md`, Brownfield code), and `legacy-receipts.json` already freezes old receipts by digest, but nothing writes that file for a project. The section adds the command that does, once, at adoption.
- D03 T01 §10, ready rows filtered by the hosts this session reaches: RasterFold's `Requires` gate (R23) skips a row whose host is absent; the kit's `query ready` lists it (`process-plan` says so and leaves the check to the agent).
- D03 T01 §11, a root index that lists domains: both projects keep the root index at domain altitude, as the kit's own `todo/README.md` describes it ("root index: domain order + active work"), and the validator demands every file in it (R20: 33 files, I17: 221).
- D03 T01 §13, section checks run when its table row cannot be read: a gap in `validate --all` itself, which hid every section-level class of Impossible OS behind its tables (I12 to I16 are counted until it ships).
- D03 T01 §12, validation git calls cached per run: not a refusal, a cost the runs measured. `validate` on the SDK's 77 sections takes 61 seconds on Windows, 441 git processes (`cat-file`, `merge-base`, `show`) and `plan_config` read 220 times; the cost grows with every stamp, and Impossible OS carries 915 to the SDK's 42, on every pre-commit.

## Guidance against each project's caps

Both `plan.json` files keep the default caps (55 sections per file, 30 items, 88-character Deliverables, 120-character plan rows): no file in either project passed 55 sections and only one Deliverable passed 88 (R17), so neither needs a cap of its own. Read against those caps, `add-todo`, `create-todo` and `groom-plan` state each limit with its `caps` key and default, and no line misleads an agent working either project. One figure is tied to no cap at all: "raw Markdown table rows stay under 140 characters" (`create-todo/SKILL.md:25`, `groom-plan/SKILL.md:48`, `todo/README.md:56`) beside the 120-character `table_row` cap and AGENTS.md's 120; it is filed in `todo/findings.md`.

## Decisions taken without the owner

- Project-side changes are the projects' own work, done in their repositories when each adopts the kit; nothing here edits them. Reversing that (the kit accepting each project's shape) costs a configuration key per difference and a validator that reads two formats.
- Phase from the plan headings, Needs as slugs, and `Requires` values as Needs: the kit's shape already expresses each, so no key was added for them. Reversing one costs a key in `plan_config` and its tests.
- Impossible OS's section-level classes are counted, not validated, until its tables read: a validator that guessed sections past an unreadable table would report faults the tree does not have.
