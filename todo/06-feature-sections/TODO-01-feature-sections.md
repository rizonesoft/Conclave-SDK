---
schema_version: 1
id: feature-sections
domain: 06-feature-sections
status: active
title: "TODO-01 -- Feature Sections"
---

# TODO-01 -- Feature Sections

> **Goal:** The Conclave side bar holds one section per feature under the Kits tree: Reviewers, Plan, Review rounds and WordPress site. Each section shows only while its kit is in the current folder, reads its data from that kit's own script (never by parsing kit files in the extension) and has its own commands under `conclave.<feature>.*`, so a later feature is a new section and a new module, not an edit to the others.

> **Current state:** Measured 2026-10-16 at Conclave-SDK `ff17f29`. No extension code exists. The owner chose one section per feature on 2026-10-16 and asked for room for Plan, Review rounds and WordPress site; the mockup draws all four sections (`sidebar` = `sections`). `scripts/todo-graph.py query ready|blocked|stats` prints JSON, but no query returns every section with its status or the phase names from `todo/plan.json` (only `plan --sync` renders them). `scripts/review-dispatch.py` appends rounds to `--record` files (`docs/reviews/<topic>.md` by the independent-review skill) as `## Round N: <who>` with Writer, Run, Effort and Skipped lines, and has no way to list them. `forge.py doctor <folder> wordpress` already reports `site-pin`, `site-identity` and `site-ssh`.

## Inputs

- `docs/plans/2026-10-16-vscode-extension.md`: requirements R33 to R37.
- `design/mockup/project/Main.dc.html` `featurePanes` and `design/mockup/open-questions.md` §13: the drawn sections and where Review rounds data comes from.
- `kits/todo/templates/scripts/todo-graph.py` and `kits/todo/templates/scripts/lib/todo_graph.py` (`plan_config`, `disposition`, `query`): the Plan section's source.
- `kits/reviewer/templates/scripts/review-dispatch.py` (`record`, `main`): the Review rounds section's source.
- `forge.py` `_doctor_wordpress`: the WordPress site section's source.
- Every `npm`, `npx` and `node` command in this file runs in `extensions/vscode/`; SDK changes go to the kit first, then `python forge.py sync . --include-scripts` refreshes the SDK's installed copy.
- -> XREF: D00 T01 §2 -- no code before the owner approves the mockup
- -> XREF: D02 T01 §3 -- the Reviewers section shows the dispatcher client's state
- -> XREF: D02 T01 §10 -- the per-kit state decides which sections show
- -> XREF: D05 T01 §5 -- the Kits view owns the container, the current folder and the container badge this file adds to
- -> XREF: D05 T01 §8 -- the WordPress site section reuses the doctor runner
- -> XREF: D02 T01 §11 -- the parity fixtures and `expectParity` every surface section here asserts

## Outcome

- With the reviewer and todo kits installed, the Conclave side bar shows Kits, Reviewers, Plan and Review rounds; with the WordPress kit, also WordPress site; a folder without a kit shows no section for it.
- The Plan section lists the ready sections and every phase with its verified count from `todo-graph.py query plan`, with the phase names `todo/plan.json` gives.
- The Review rounds section lists every round record and round from `review-dispatch.py --list-rounds --json`, marking a round with no reviewer as not an approval.
- Adding a section is one module registered in `extensions/vscode/src/host/sections/registry.ts`, proved by a test section registered only in the test.

**Adjacency:** list=applicable @ D06 T01 §1; document=not-applicable (the sections read records the kits write; nothing is printed or sent); settings=not-applicable (no setting of their own); reporting=applicable @ D06 T01 §5; notifications=not-applicable (single local user; states show in the sections and the badge); permissions=applicable @ D06 T01 §1; audit=not-applicable (read-only queries, logged by the shared runner in D02 T01 §9); exchange=not-applicable (data comes only from the folder's own kit scripts); reverse=not-applicable (no section writes anything)

**Adjacency rationale:** Every section is read-only: it runs a kit script's query and renders the JSON. Writes stay in their owners: the reviewer editor writes the pin, the agents write plans and round records, and the wordpress-connect skill fills the site pin. Workspace trust is enforced once in the registry, which runs no section's query in Restricted Mode.

## Implementation Order

| Order | Section | Deliverable | Depends On | Status |
| ----- | ------- | ----------- | ---------- | ------ |
| 1 | §1 | Feature section registry | D02 T01 §10, D05 T01 §5 | [ ] |
| 2 | §2 | Plan query in todo-graph | D00 T01 §2 | [x] |
| 3 | §3 | Round listing in the dispatcher | D00 T01 §2 | [x] |
| 4 | §4 | Reviewers section | §1, D02 T01 §3 | [ ] |
| 5 | §5 | Plan section | §1, §2 | [ ] |
| 6 | §6 | Review rounds section | §1, §3, §8 | [ ] |
| 7 | §7 | WordPress site section | §1, D05 T01 §8 | [ ] |
| 8 | §8 | Round record hardening | §3 | [ ] |

## 1. Feature section registry

Features must be addable without editing each other (plan R33). This section adds a registry that contributes one view per feature to the `conclave` container, shows each only while its kit is in the current folder, runs no query in Restricted Mode, and adds each section's attention count to the container badge from D05 T01 §5.

**Phase:** 2
**Needs:** none
**Surface:** no

**Build order:**

1. Write `extensions/vscode/src/host/sections/registry.ts` and its `FeatureSection` interface. Done when: a section registered in a test appears and disappears with its kit.
2. Wire the badge and trust. Done when: the badge sums the sections' counts and an untrusted window runs no query.

- [ ] Define `FeatureSection` in `extensions/vscode/src/host/sections/registry.ts`: `id`, `kit`, `title`, `load(folder)` returning rows and an attention count, and `commands`. Done when: the type compiles and the four sections in this file implement it. Cheaper substitute: one tree provider with a switch per feature.
- [ ] Contribute `views.conclave` entries `conclave.reviewers`, `conclave.plan`, `conclave.rounds` and `conclave.site` in `extensions/vscode/package.json`, after `conclave.kits`, each with `when` `conclave.kit.<kit>`. Done when: the views appear in that order. Cheaper substitute: every view always visible.
- [ ] Set `conclave.kit.<kit>` context keys in `extensions/vscode/src/host/sections/registry.ts` from D02 T01 §10's state for D05 T01 §5's current folder (true unless the kit is not installed). Done when: installing the todo kit shows the Plan section without a reload. Cheaper substitute: checking the kit only at activation.
- [ ] Skip every `load` while the workspace is untrusted and show one "Restricted Mode" row per section. Done when: an integration test in an untrusted window runs no process. Cheaper substitute: running the read-only queries anyway.
- [ ] Add the sections' attention counts to the container badge in `extensions/vscode/src/host/kitsView.ts`, counting a problem once when the Kits health already reports it. Done when: a missing reviewer CLI makes the badge 1, not 2. Cheaper substitute: a badge per section summed blindly.
- [ ] Write `extensions/vscode/test/integration/sections.test.ts` with a test-only section. Done when: it passes and fails when the registry hard-codes the four sections. Cheaper substitute: testing only the shipped sections.
- [ ] Commit: `ui: feature section registry in the Conclave side bar`

**Test checkpoint:** `cd extensions/vscode && npm run test:integration -- --grep sections` passes, and fails when a section shows for a folder without its kit.

## 2. Plan query in todo-graph

> **Started:** 2026-10-20T08:14:17Z

The Plan section must not read `todo/` itself (plan R34): `todo_graph.py` owns the section rules and `plan_config` owns `todo/plan.json`. This section adds `todo-graph.py query plan`, printing the plan title, acceptance bar, phase names and every section with its status, to the todo kit.

**Phase:** 0
**Needs:** none
**Surface:** no

**Build order:**

1. Write the failing tests in `tests/test_todo_graph.py`. Done when: they fail because `plan` is not a query kind.
2. Implement the query in `kits/todo/templates/scripts/todo-graph.py` and refresh the SDK's copy. Done when: the tests pass and `scripts/todo-graph.py` matches the kit.

- [x] Add `test_query_plan_reports_config_and_every_section` to `tests/test_todo_graph.py`: a fixture plan with a verified, a ready and a blocked section, expecting `{"title", "acceptance", "phases": {"0": ...}, "sections": [{"ref", "path", "title", "phase", "status", "depends"}]}` with status `verified`, `ready`, `blocked` or `deferred`. Done when: it fails on the unchanged script. Cheaper substitute: asserting only the key names.
- [x] Add `plan` to the `query` choices in `kits/todo/templates/scripts/todo-graph.py`, building the sections from `graph` and `disposition` and the names from `plan_config`. Done when: the new test passes. Cheaper substitute: re-reading `todo/plan.json` with a second loader.
- [x] Add a refusal test for an unreadable `todo/plan.json` expecting the existing `Refused` message and exit code. Done when: it passes. Cheaper substitute: printing default phase names over a broken file.
- [x] Document `query plan` in `kits/todo/README.md` and refresh the SDK's copy with `python forge.py sync . --include-scripts`. Done when: `cmp scripts/todo-graph.py kits/todo/templates/scripts/todo-graph.py` reports no difference. Cheaper substitute: hand-editing `scripts/todo-graph.py`.
- [x] Commit: `todo kit: query plan reports the config and every section`, then push `main`

**Test checkpoint:** `python -m unittest tests.test_todo_graph -v` passes, and `test_query_plan_reports_config_and_every_section` fails when the `plan` choice is removed.

> **Verified:** 2026-10-20 | §2 | ab4e53ba5b35229dd8f734088a28c5104e668097
> **Review:** `docs/reviews/d06-t01-s2.json`

## 3. Round listing in the dispatcher

> **Started:** 2026-10-20T08:20:00Z (recorded at 08:31; work began about 08:20)

The Review rounds section must not parse the dispatcher's Markdown (plan R35, open question 13): `record` owns that format. This section adds `review-dispatch.py --list-rounds [--json] [--records <dir>]` to the reviewer kit, listing each record file under `docs/reviews/` with its rounds, read back from the headings and lines `record` writes.

**Phase:** 0
**Needs:** none
**Surface:** no

**Build order:**

1. Write the failing tests in `kits/reviewer/templates/scripts/tests/test_review_dispatch.py`. Done when: they fail because `--list-rounds` is an unknown argument.
2. Implement the listing next to `record` in `kits/reviewer/templates/scripts/review-dispatch.py` and refresh the SDK's copy. Done when: the tests pass and the root copy matches the kit.

- [x] Add `test_list_rounds_reads_back_what_record_wrote`: write two rounds with `record` (one reviewed, one with every reviewer skipped), then expect `--list-rounds --json` to print `{"records": [{"path", "rounds": [{"number", "reviewer", "model", "cli", "writer", "run", "effort", "skipped": [{"reviewer", "reason"}]}]}]}` with `reviewer` null for the skipped round. Done when: it fails on the unchanged script. Cheaper substitute: a fixture typed by hand instead of written by `record`.
- [x] Implement `list_rounds(records_dir)` beside `record` in `kits/reviewer/templates/scripts/review-dispatch.py`, so the writer and the reader of the format sit together, and make `--writer` and `--prompt` optional only with `--list-rounds`. Done when: the new test and every existing test pass. Cheaper substitute: a second parser in the extension.
- [x] Add a test that a missing `docs/reviews/` prints `{"records": []}` and exit 0, and a malformed heading is reported in `"unreadable": [path]`, never dropped. Done when: both pass. Cheaper substitute: skipping bad files silently.
- [x] Document the flag in `kits/reviewer/README.md` and refresh the SDK's copy with `python forge.py sync . --include-scripts`. Done when: `cmp scripts/review-dispatch.py kits/reviewer/templates/scripts/review-dispatch.py` reports no difference. Cheaper substitute: hand-editing `scripts/review-dispatch.py`.
- [x] Commit: `reviewer: list recorded review rounds as JSON`, then push `main`

**Test checkpoint:** `python -m unittest discover -s scripts/tests -p test_review_dispatch.py -v` passes, and `test_list_rounds_reads_back_what_record_wrote` fails when `record`'s heading format changes without the reader.

> **Verified:** 2026-10-20 | §3 | a7c73881df1b8ed48b370dde081e19ac11365d90
> **Review:** `docs/reviews/d06-t01-s3.json`

## 4. Reviewers section

**Corrected 2026-10-20:** review of `D00 T01 §4` found that `load_pin` accepts TOML layouts the editor cannot edit in place (inline tables, quoted keys, arrays over several lines); a valid pin in one is the read-only `pin-layout` state (`design/decisions.md`, 2026-10-20; design spec section 2), added below.

The pin's state belongs in the side bar, not only in the editor tab (plan R37). This section shows the pin state from D02 T01 §3, each reviewer with its CLI status and each route, and moves Open Reviewer Settings from the Kits title bar to this section's.

**Phase:** 2
**Needs:** none
**Surface:** yes
**Fidelity:** `design/SPEC.md` §12 Feature sections; `design/screens/12-dark.png` and `design/screens/12-light.png`.
**Job:** Tell the operator whether reviews will run, and which reviewer is skipped, without opening the editor.
**Treatment:** A native `TreeView`: a state row, one row per reviewer (model via CLI, warning codicon when the CLI is missing), a Routes group with one row per writer.
**Chrome:** Title actions Open Reviewer Settings and Refresh; inline Install on the no-pin and no-dispatcher rows; inline Open on a reviewer row, opening the editor at its card.

**Build order:**

1. Write `extensions/vscode/src/host/sections/reviewersSection.ts`. Done when: the shipped pin shows three reviewers and three routes.
2. Wire the states and actions. Done when: every D02 T01 §3 state has its row and action.

- [ ] Implement `reviewersSection` in `extensions/vscode/src/host/sections/reviewersSection.ts` from the `--check-pin --json` result: `reviewers`, `routes` and `clis`. Done when: a unit test over the shipped fixture lists the rows in pin order. Cheaper substitute: reading `.conclave/reviewers.toml` directly.
- [ ] Show one state row for `refused`, `unsupported-schema`, `no-pin`, `no-dispatcher`, `old-dispatcher`, `no-python` and `untrusted`, and no reviewer rows while the pin is refused. Done when: a unit test per state checks the row and that a refused pin lists no reviewer. Cheaper substitute: one generic error row.
- [ ] Show the `pin-layout` state row `reviewers.toml` `valid; a layout the editor does not edit` (warning icon), then the reviewer rows and the Routes group from `--check-pin`, each reviewer's action `Open reviewers.toml` (`design/SPEC.md` §12). **Corrected 2026-10-20:** was the state row alone; `D00 T01 §6` lists the reviewers, since the pin is valid and reviews run. Done when: a unit test with `valid-inline-layout.toml` shows the state row, two reviewers and one route, and the open-file action. Cheaper substitute: showing `valid (--check-pin)`.
- [ ] Move "Open Reviewer Settings" from D05 T01 §5's view title to `conclave.reviewers` and add inline Install (opening D05 T01 §6 preset to `reviewer`) on the no-pin and no-dispatcher rows. Done when: each action runs from the section. Cheaper substitute: keeping the command only in the Kits title.
- [ ] Write `extensions/vscode/test/integration/reviewersSection.test.ts`. Done when: it passes and fails when a missing CLI is shown as ready. Cheaper substitute: a label snapshot.
- [ ] Assert mockup parity for every scenario this section draws in `extensions/vscode/test/parity/reviewers-section.parity.test.ts` with `expectParity` from D02 T01 §11. Done when: the test passes and fails when one label, description, icon, badge, order or action differs from the mockup's fixture. Cheaper substitute: comparing by eye against the mockup.
- [ ] Commit: `ui: Reviewers section in the Conclave side bar`

**Test checkpoint:** `cd extensions/vscode && npm run test:integration -- --grep reviewersSection` passes, and fails when the section reads the pin file instead of `--check-pin`.

## 5. Plan section

The operator wants to see the plan's progress and what is ready next (plan R34). This section renders §2's `query plan`: a Ready now group, one group per phase with its verified count, and a row for each section that opens its TODO file at the section.

**Phase:** 2
**Needs:** none
**Surface:** yes
**Fidelity:** `design/SPEC.md` §12 Feature sections; `design/screens/12-dark.png` and `design/screens/12-light.png`.
**Job:** Show how far the plan is and which sections can start now.
**Treatment:** A native `TreeView` with the description "N of M verified", a Ready now group open by default and collapsed phase groups named from `todo/plan.json`.
**Chrome:** Title actions Validate the plan, Open the plan and Refresh; inline Open on a section row; inline Install on the "No todo/plan.json" row.

**Build order:**

1. Write `extensions/vscode/src/host/sections/planSection.ts`. Done when: the SDK's own plan shows its 43 sections in their phases.
2. Wire the actions. Done when: Validate, Open and Install each run.

- [ ] Implement `planSection` in `extensions/vscode/src/host/sections/planSection.ts` from `todo-graph.py query plan`, grouping by phase in the order of `phases`. Done when: a unit test over a fixture shows Ready now, then each phase with its count. Cheaper substitute: reading `todo/*.md` in the extension.
- [ ] Show "No todo/plan.json" with inline Install (D05 T01 §6 preset to `todo`) when the kit's `todo/plan.json` is missing, keeping todo-graph's bare phase numbers. Done when: the fixture without the file shows the row and "Phase 1". Cheaper substitute: inventing phase names.
- [ ] Open a section row's `path` at its `## N.` heading, and run `todo-graph.py validate` from the title with its output in the Conclave channel. Done when: an integration test opens the right line. Cheaper substitute: opening the file at the top.
- [ ] Write `extensions/vscode/test/integration/planSection.test.ts`. Done when: it passes and fails when a blocked section is listed under Ready now. Cheaper substitute: counting rows only.
- [ ] Assert mockup parity for every scenario this section draws in `extensions/vscode/test/parity/plan-section.parity.test.ts` with `expectParity` from D02 T01 §11. Done when: the test passes and fails when one label, description, icon, badge, order or action differs from the mockup's fixture. Cheaper substitute: comparing by eye against the mockup.
- [ ] Commit: `ui: Plan section in the Conclave side bar`

**Test checkpoint:** `cd extensions/vscode && npm run test:integration -- --grep planSection` passes, and fails when the verified count is computed in the extension instead of read from the query.

## 6. Review rounds section

Past review rounds should be one click away (plan R35). This section renders §3's `--list-rounds --json`: one group per record file, one row per round with its reviewer, writer and time, and a round with no reviewer marked as not an approval.

**Phase:** 2
**Needs:** none
**Surface:** yes
**Fidelity:** `design/SPEC.md` §12 Feature sections; `design/screens/12-dark.png` and `design/screens/12-light.png`.
**Job:** Let the operator find any recorded review and see at once which rounds produced no review.
**Treatment:** A native `TreeView` with record files as groups (newest round first) and an error codicon on a round with no reviewer.
**Chrome:** Title actions Open docs/reviews and Refresh; inline Open on a round row, opening the record at its heading.

**Build order:**

1. Write `extensions/vscode/src/host/sections/roundsSection.ts`. Done when: a fixture with two records shows three rounds.
2. Wire opening a round. Done when: Open lands on the round's heading.

- [ ] Implement `roundsSection` in `extensions/vscode/src/host/sections/roundsSection.ts` from `review-dispatch.py --list-rounds --json`. Done when: a unit test shows "no review, not an approval" for a round whose `reviewer` is null. Cheaper substitute: parsing `docs/reviews/*.md` in the extension.
- [ ] Show "No rounds recorded yet" for `{"records": []}` and list `unreadable` paths as warning rows. Done when: unit tests cover both. Cheaper substitute: an empty tree.
- [ ] Open a round row at its `## Round N` line. Done when: an integration test opens the right line. Cheaper substitute: opening the file at the top.
- [ ] Write `extensions/vscode/test/integration/roundsSection.test.ts`. Done when: it passes and fails when a skipped round is shown as reviewed. Cheaper substitute: a label snapshot.
- [ ] Assert mockup parity for every scenario this section draws in `extensions/vscode/test/parity/review-rounds-section.parity.test.ts` with `expectParity` from D02 T01 §11. Done when: the test passes and fails when one label, description, icon, badge, order or action differs from the mockup's fixture. Cheaper substitute: comparing by eye against the mockup.
- [ ] Commit: `ui: Review rounds section in the Conclave side bar`

**Test checkpoint:** `cd extensions/vscode && npm run test:integration -- --grep roundsSection` passes, and fails when the section reads the Markdown records itself.

## 7. WordPress site section

A WordPress folder needs its live site's connection state in view (plan R36). This section shows the `site-pin`, `site-identity` and `site-ssh` rows of `forge.py doctor <folder> wordpress` through D05 T01 §8's runner, with the host in the description; the wordpress-connect skill, run by the agent, stays the only writer of the site pin.

**Phase:** 2
**Needs:** none
**Surface:** yes
**Fidelity:** `design/SPEC.md` §12 Feature sections; `design/screens/12-dark.png` and `design/screens/12-light.png`.
**Job:** Show whether the site is connected and which wordpress-connect step is left.
**Treatment:** A native `TreeView` with one row per site check, verbatim from doctor, and the description "<host>" or "<host>, not connected yet".
**Chrome:** Title actions Open the site pin and Refresh; inline "How to finish this step" on a `setup_required` row, explaining that the agent runs wordpress-connect.

**Build order:**

1. Write `extensions/vscode/src/host/sections/siteSection.ts`. Done when: a fresh install shows two `setup_required` rows.
2. Wire the actions. Done when: Open and the explanation each run.

- [ ] Implement `siteSection` in `extensions/vscode/src/host/sections/siteSection.ts` from the doctor checks whose name starts with `site-`. Done when: a unit test over a fresh Pressable pin shows `site-identity` and `site-ssh` as `setup_required` with forge's details. Cheaper substitute: reading `.conclave/wordpress-site.json` in the extension.
- [ ] Never write the site pin: Open the site pin opens it in the text editor, and the setup row explains the wordpress-connect skill. Done when: a test asserts the section registers no write command. Cheaper substitute: a form that fills the pin.
- [ ] Write `extensions/vscode/test/integration/siteSection.test.ts`. Done when: it passes and fails when a `setup_required` row is shown as ok. Cheaper substitute: a label snapshot.
- [ ] Assert mockup parity for every scenario this section draws in `extensions/vscode/test/parity/wordpress-site-section.parity.test.ts` with `expectParity` from D02 T01 §11. Done when: the test passes and fails when one label, description, icon, badge, order or action differs from the mockup's fixture. Cheaper substitute: comparing by eye against the mockup.
- [ ] Commit: `ui: WordPress site section in the Conclave side bar`

**Test checkpoint:** `cd extensions/vscode && npm run test:integration -- --grep siteSection` passes, and fails when the section shows a check that doctor did not return.

## 8. Round record hardening

> **Started:** 2026-10-20T11:57:26Z

Review round 3 of §3 (`docs/reviews/06-feature-sections/D06-T01-s3.md`, the last round the review loop allows) left five defects in the round record that `record` writes and `--list-rounds` reads. They were filed here rather than patched a fourth time, and the envelope is re-thought, not patched: (1) a `- Lines:` value such as `²` passes `str.isdigit` and `int` raises, aborting the listing; (2) the count alone cannot tell an edit inside a review, and the README overclaims that it can; (3) the review is not stored byte for byte: `text_lines` drops a `\r`, and `record` reads the existing file with universal newlines, so an append turns a lone `\r` into a line break and breaks an earlier round's count; (4) `load_pin`'s `MODEL` and `NAME` patterns end in `$`, which accepts a trailing newline, and such a model breaks the round heading; (5) when the existing file is unreadable, `record` numbers by counting `## Round` lines, which counts quoted headings. §6 renders this listing, so it waits for this section.

**Phase:** 0
**Needs:** none
**Surface:** no

**Build order:**

1. Write the failing tests in `kits/reviewer/templates/scripts/tests/test_review_dispatch.py`, one per defect. Done when: each fails on the dispatcher at the end of §3.
2. Re-think the envelope in `kits/reviewer/templates/scripts/review-dispatch.py` and refresh the SDK's copy. Done when: the tests pass on Windows and WSL and `scripts/review-dispatch.py` matches the kit.

- [x] Accept a `- Lines:` value only as 1 to 6 ASCII digits (`re.fullmatch(r"[0-9]{1,6}", value)`) in `read_rounds`, and catch `ValueError` beside `OSError` in `list_rounds`. Done when: a record with `- Lines: ²` or a 5,000-digit count is named in `unreadable` and the other records are listed. Cheaper substitute: catching the exception and dropping the file.
- [x] Add `- Digest:` (the first 16 hex digits of the SHA-256 of the review's canonical lines, joined with `\n`) to what `record` writes, and verify it in `read_rounds`. Done when: an edit inside a review that keeps its line count is refused, and the README says that text after a round's review belongs to no round (as the `## Response to round N` notes do). Cheaper substitute: the count alone, which misses same-length edits.
- [x] Store the review byte for byte: split it on `\n` alone without dropping `\r`, and read and write the existing file in `record` with `newline=""`; canonicalise only for parsing and the digest (a line's trailing `\r` dropped, for CRLF checkouts). Done when: a review containing `A\r\nB` and a lone `\r` is stored unchanged, and appending a second round leaves the first one readable. Cheaper substitute: normalising every line ending, which changes the stored review.
- [x] Match `MODEL` and `NAME` in `load_pin` with `fullmatch` (or `\Z`) so a trailing newline is refused. Done when: a pin with `model = "gpt-6-astra\n"` is refused with `has a malformed model` and no reviewer runs. Cheaper substitute: stripping the value, which edits the pin's meaning.
- [x] Refuse in `record` to append to a findings file `read_rounds` cannot read, printing the round's JSON summary and saying why, with exit 2. Done when: the review text is still on stdout and the file is unchanged. Cheaper substitute: numbering by counting headings, which counts quoted ones.
- [x] Refresh the SDK's copy with `python forge.py sync . --include-scripts` and update `kits/reviewer/README.md`. Done when: `cmp scripts/review-dispatch.py kits/reviewer/templates/scripts/review-dispatch.py` reports no difference. Cheaper substitute: hand-editing `scripts/review-dispatch.py`.
- [ ] Commit: `reviewer: round records with a digest, stored byte for byte`, then push `main`

**Test checkpoint:** `python -m unittest discover -s scripts/tests -p test_review_dispatch.py -v` passes on Windows and in WSL, and each new test fails against the dispatcher at the end of §3 (`a7c7388`).

## Verification

- In the mockup's `sections` state and in the built extension, a folder with the reviewer, todo and WordPress kits shows the Kits tree and all four sections with the same rows, and a folder without them shows only the Kits tree.
- `python scripts/todo-graph.py validate` and `python scripts/todo-graph.py plan --check` pass.
