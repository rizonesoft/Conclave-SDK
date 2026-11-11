---
schema_version: 1
id: install-record-and-update
domain: 01-forge
status: active
title: "TODO-01 -- Install record, diff and update"
---

# TODO-01 -- Install record, diff and update

> **Goal:** A project can see what the SDK has that it lacks and take it deliberately: `forge.py` records what it installed, `diff` reports every kit file's state without writing, `update` writes only what is safe, and a weekly report says which projects have drifted. Nothing a project changed is ever overwritten.

> **Current state:** Measured 2026-11-11. `forge.py` (812 lines) has `init`, `kit`, `doctor`, `kits`, `check` and `self-sync`. `apply_kit` (`forge.py:188`) builds its file list inline and skips an existing file unread (`forge.py:286`), so same, changed and stale look alike. Nothing records what was installed: `tests/test_forge.py:183` asserts `.conclave/kits.json` does not exist and `tests/test_forge.py:185` asserts there is no `sync` command, and the docstring (`forge.py:11`) and `README.md` say nothing records the source. `provision` (`forge.py:653`) applies kits one by one, so a second kit that refuses leaves the first one written, and `init --force` (`forge.py:657`) rewrites the four entry docs with no backup. The SDK's own `.conclave/automations/tasks.json` has one task, `conclave-sdk-reviewers`.

## Inputs

- `docs/plans/2026-11-11-sdk-audit-and-roadmap.md`: findings 1 to 4, 14 and 15, and recommendations 1 to 4. Recommendation 1 is an owner decision of 2026-11-11 that reverses the 2026-10-25 decision that nothing records the source.
- `forge.py` and `tests/test_forge.py`: every section changes both.
- `kits/automations/templates/.conclave/automations/run.py`: a task's non-zero exit sends the failure email with the tail of its log, which §7 uses as the report channel.
- -> XREF: D01 T02 §4 -- the bash installers are retired there, after which `forge.py` is the only installer and the only writer of the record

## Outcome

- `python forge.py diff <project>` prints, for every kit file, one of `missing`, `identical`, `kit-newer`, `project-changed`, `both-changed`, `project-removed` or `project-only` (and, where no record entry or no readable file exists, `differs`, `unsafe`, `unreadable` or `generated`), and writes nothing.
- `python forge.py update <project>` writes only `missing` and `kit-newer` files and leaves every other file byte for byte as the project had it.
- A project installed before the record existed gains the upgrade path through `python forge.py record <project>`.
- `init` writes nothing when any chosen kit refuses, and `init --force` keeps the entry docs it replaces.

**Adjacency:** all=not-applicable (developer tooling: a command line that copies template files and reports on them, with no records a user lists, exports, is notified of or reverses)

**Adjacency rationale:** The one record this work adds, `.conclave/kits.json`, is a note the project may delete: every command works without it and says what it can no longer tell. The reverse of `update` is the project's own git history, which is why `update` never writes over a file whose bytes differ from what was installed.

## Implementation Order

| Order | Section | Deliverable | Depends On | Status |
| ----- | ------- | ----------- | ---------- | ------ |
| 1 | §1 | Kit file plan shared by install, diff and update | -- | [x] |
| 2 | §2 | Install record in `.conclave/kits.json` | §1 | [x] |
| 3 | §3 | Read-only `forge.py diff` | §2 | [x] |
| 4 | §4 | `forge.py update` for missing and kit-newer files | §3 | [ ] |
| 5 | §5 | `forge.py record` for projects installed before the record | §3 | [ ] |
| 6 | §6 | `.kit-new` copies for a hand merge | §4 | [ ] |
| 7 | §7 | Weekly drift report across projects | §3 | [ ] |
| 8 | §8 | `init` that writes nothing when a kit refuses | §1 | [ ] |
| 9 | §9 | Backup of the entry docs `init --force` replaces | -- | [ ] |

## 1. Kit file plan shared by install, diff and update

> **Started:** 2026-11-11T17:48:24Z

`apply_kit` decides which template file goes to which project path inside its own body (`forge.py:222` to `forge.py:277`), including the Laravel app root and the WordPress host overlay. `diff` and `update` need the same list, so it moves into one function they all call. Behaviour of `kit` and `init` must not change.

**Phase:** 1
**Needs:** none
**Surface:** no

**Build order:**

1. Extract `kit_plan(target_root, kit_name, agent, host)` from `apply_kit` in `forge.py`, returning the `(source, destination, relative path)` list and the `extra` fields. Done when: `apply_kit` calls it and builds no list of its own.
2. Cover it in `tests/test_forge.py`. Done when: the checkpoint passes.

- [x] Move the list building for the Laravel, WordPress and plain kits out of `apply_kit` into `kit_plan` in `forge.py`, keeping the refusals (no `artisan`, an unknown host, a pin for another host) raised from `kit_plan`. Done when: `apply_kit` contains no `rglob` call and `python -m unittest discover -s tests -p test_forge.py` passes with no assertion changed. Cheaper substitute: a second copy of the list logic written for `diff` must fail review.
- [x] Return from `kit_plan` whether each entry is a template copy or generated, so the Laravel `.mcp.json` (`forge.py:294`), which `apply_kit` builds itself, is named as generated and has no source file. Done when: a test asserts the Laravel plan lists `.mcp.json` as generated and every other entry has a source that exists.
- [x] Test `kit_plan` in `tests/test_forge.py` for each kit against paths the test derives itself, never from `apply_kit`: the expected set is built by walking `kits/<kit>/templates` (plus `kits/wordpress/hosts/<host>/templates` for each WordPress host, and the seven listed Laravel files with `boost.json` mapped to the app root) and keeping the paths outside the other agents' folders and entry docs by the test's own prefix rule, for `--agent all`, `claude`, `codex` and `agy`. Done when: the plan's relative paths equal that set for every kit and agent, no path under an excluded agent's folder is present, each destination is the expected file under the target (the nested Laravel `platform/boost.json` included), and the test fails when `kit_plan` drops the agent filter `_rel_allowed_for_agent` or omits one template. **Corrected 2026-11-11 (plan review):** said the plan's paths equal `apply_kit`'s `installed` list, which consumes the same plan and so cannot fail.
- [x] Assert in `tests/test_forge.py` that a fresh `apply_kit` on an empty fixture installs exactly the files `kit_plan` lists, each present at its destination with the template's bytes, as a consistency check beside the independent one. Done when: the test fails when `apply_kit` skips one planned file. **Corrected 2026-11-11 (plan review):** added; the comparison is kept as the second check.
- [x] Commit: `forge: one kit file plan for install, diff and update`

**Test checkpoint:** `python -m unittest discover -s tests -p test_forge.py` ends `OK`; removing the agent filter from `kit_plan` makes the new test fail, because its expected paths are derived by the test and not by `apply_kit`. **Corrected 2026-11-11 (plan review):** the reason was not stated and the earlier test could not fail.

> **Verified:** 2026-11-11 | §1 | 6721fcc8a5b28c69026ed8d4e4f135e9cefdb9ac
> **Review:** `docs/reviews/d01-t01-s1.json`

## 2. Install record in `.conclave/kits.json`

> **Started:** 2026-11-11T17:57:49Z

`kit` and `init` write a record of what they installed: the SDK commit and, for every file written, its kit and a digest of the bytes as installed (roadmap recommendation 1, owner decision 2026-11-11). The record is a note, not a link: the project owns every file and deleting the record breaks nothing.

**Phase:** 1
**Needs:** none
**Surface:** no

**Build order:**

1. Add `load_record`, `write_record` and `file_digest` to `forge.py`, and write the record from `apply_kit`. Done when: a fresh install has a record naming every file it wrote.
2. Replace the tests and prose that say nothing is recorded. Done when: the checkpoint passes.

- [x] Add `file_digest(data)` to `forge.py`: the SHA-256 of the bytes with CRLF read as LF, the comparison `self_sync` already makes (`forge.py:694`), so a checkout with converted line endings does not look changed. Done when: a test gives the same digest for a file and its CRLF twin and a different one for a changed byte. Cheaper substitute: a digest of raw bytes must fail the CRLF test.
- [x] Add `load_record(target_root)` to `forge.py`, reading `.conclave/kits.json` as `{"schema_version": 1, "kits": {"<kit>": {"sdk_commit": "<40 hex or null>", "agents": ["<agy|claude|codex>", ...], "host": "<host or null>"}}, "files": {"<relative path>": {"kit": "<kit>", "sha256": "<64 hex>"}}}`. Done when: tests show a missing file reads as no record and a valid record loads equal to what was written. Cheaper substitute: treating a malformed record as empty must fail, because `update` would then lose what it knew. **Corrected 2026-11-11 (plan review):** `agent` was one value, which cannot hold a Claude install followed by a Codex one; it is now the sorted list `agents`.
- [x] Refuse every malformed record in `load_record` with a `ValueError` naming `.conclave/kits.json` and the fault: bytes that are not UTF-8 JSON, a top level that is not an object, a missing or unknown key at any level, another `schema_version`, `kits` or `files` that is not an object, a kit name no kit has, an `sdk_commit` that is neither `null` nor 40 lowercase hex, `agents` that is not a non-empty sorted list of distinct names from `agy`, `claude` and `codex`, a `host` that is neither `null` nor a WordPress host, a file path that is absolute, has a backslash, a `..` or an empty segment, a `sha256` that is not 64 lowercase hex, and a file entry whose `kit` is not under `kits`. Done when: one test per fault reads the refusal, and a test runs `python forge.py kit <target> todo` against a target holding a malformed record and gets exit 2 with the one-line message. **Corrected 2026-11-11 (plan review):** added; the faults were four and the command line was not tested.
- [x] Add `write_record(target_root, record)` to `forge.py`, written with `atomic_write` and sorted keys so the file is stable across runs. Done when: a test reads the file back equal to what was passed and two identical installs produce byte-identical records.
- [x] Read the SDK commit in `forge.py` with `git -C <FORGE_ROOT> rev-parse HEAD` (a 15 second timeout, no shell), recording `null` when the SDK is not a git checkout, git is missing, the command fails or it times out. Done when: tests assert the record holds exactly the output of `git rev-parse HEAD` for this checkout, and JSON `null` (not the string) for a copy of the kits outside any repository, for a `git` that is not on `PATH` and for an injected `subprocess.TimeoutExpired`; none raises. **Corrected 2026-11-11 (plan review):** "none raises" passed for a reader that always returned `null`, and the timeout had no stated result.
- [x] Check the record and its folder in `apply_kit` of `forge.py` before the first template is written: `load_record` runs first, and `.conclave` or `.conclave/kits.json` being a symlink, or `.conclave` existing as a file, refuses through `_has_unsafe_parent`. Done when: tests with a malformed record, a `.conclave` that is a file and a symlinked `kits.json` each find the `ValueError` and no file written under the target. Cheaper substitute: validating the record after the copy loop must fail the nothing-written assertion. **Corrected 2026-11-11 (plan review):** added; a refusal after the copy left files with no record.
- [x] Record every file `apply_kit` writes in `forge.py`: after the copy loop, merge the written template files into the record under their kit with the digest of the template's bytes, leave preserved files and generated files (the Laravel `.mcp.json`) unrecorded, and write nothing on `--dry-run`. Done when: a test installs `todo`, edits one skill, deletes another, applies `todo` again and then `reviewer`, and finds the edited skill's digest still that of the bytes as installed, the restored skill recorded, the `reviewer` entries added, and a file the project had before any install (its own `scripts/todo-graph.py`) absent from the record. Cheaper substitute: rebuilding the record from the files on disk, or recording preserved files, must fail this test. **Corrected 2026-11-11 (plan review):** the earlier test reapplied only `reviewer`, which never touches the edited skill, and did not cover a file that was never installed.
- [x] Keep the record true when a copy fails part way in `apply_kit` of `forge.py`: the files already written are recorded before the error is raised again. Done when: a test injects a failing `atomic_write` on the third file and finds the first two files present and recorded, the third absent from disk and record, and the error raised. **Corrected 2026-11-11 (plan review):** added; §4 covers a failed update, not a failed install.
- [x] Record each kit's `agents` cumulatively in `apply_kit` of `forge.py`: `all` records `agy`, `claude` and `codex`; one agent is added to those already recorded for that kit and never removes one. Done when: tests cover `--agent claude` then `--agent codex` (both recorded, no `agy`), `all` then `--agent claude` (still all three) and a second kit installed for another agent keeping its own list. **Corrected 2026-11-11 (plan review):** added.
- [x] Record the entry docs in `provision` of `forge.py` with the digest of the kit's bytes, so the `TODO_POINTER` appended at `forge.py:667` reads as the project's change and `update` never replaces `AGENTS.md`. Done when: tests cover a fresh `init --with-todo` (the `AGENTS.md` digest equals the template's, not the file's), a second `init` (the entry keeps its digest and nothing is recorded for a doc the project already had before the first install), and `init --force` (a doc it replaces is recorded with the template's digest, and one it replaces that was never recorded gains an entry). **Corrected 2026-11-11 (plan review):** only the fresh install was tested.
- [x] Replace `test_init_and_kit_copy_once_and_never_overwrite_the_projects_copy` line 183 and `test_the_cli_has_no_sync_or_mode_that_links_a_project_to_the_sdk` in `tests/test_forge.py`: the first asserts the record exists and names only written files, the second keeps refusing `sync`, `digest` and `--mode inherit` and asserts the record holds no path to the SDK. Done when: both pass and the second fails when an absolute path is added to the record.
- [x] Rewrite the "nothing records" sentences in the `forge.py` docstring (`forge.py:11`), `README.md`, `AGENTS.md` and `kits/README.md` to say what the record holds and that a project may delete it. Done when: `grep -rn "nothing records\|nothing they write records" forge.py README.md AGENTS.md kits/README.md` prints nothing.
- [x] Commit: `forge: record what a project installed in .conclave/kits.json`

**Test checkpoint:** `python -m unittest discover -s tests -p test_forge.py` ends `OK`; making `apply_kit` record preserved files makes the edited-skill test fail, and moving `load_record` after the copy loop makes the nothing-written test fail. **Corrected 2026-11-11 (plan review):** the second mutation was added with the validate-first item.

> **Verified:** 2026-11-11 | §2 | 8d88711aef6a45c092adbc51b3ead67327c4457a
> **Review:** `docs/reviews/d01-t01-s2.json`

## 3. Read-only `forge.py diff`

> **Started:** 2026-11-11T19:14:00Z

`forge.py diff <project> [kit]` answers "what does the SDK have that I lack" (recommendation 2). It reads the project, the kits and the record, and writes nothing.

**Corrected 2026-11-11 (validation):** the six recorded states assumed every planned file has a record entry. Three cases had no state: a file the project had before any install (preserved, so never recorded), a kit installed before the record existed while a later kit is recorded, and a destination that is a link, a folder or under an unsafe parent (which `update` must refuse, §4). They are covered by the items marked below. The generated Laravel `.mcp.json` has no template to compare with, so it is reported as `generated`, not classified; `diff` never runs `_recover`, which writes.

**Phase:** 1
**Needs:** none
**Surface:** no

**Build order:**

1. Add `diff_project(target_root, kit_name=None)` and the `diff` subcommand to `forge.py`. Done when: every state below is reported for a fixture that holds it.
2. Document it in `README.md`. Done when: the checkpoint passes.

- [x] Add `diff_project` to `forge.py`, classifying every `kit_plan` entry with a record: `missing` (not in the project, not in the record), `project-removed` (in the record, not in the project), `identical` (project digest equals the kit's), `kit-newer` (project digest equals the recorded one and the kit's differs), `project-changed` (kit digest equals the recorded one and the project's differs) and `both-changed` (all three differ). Done when: one test builds a fixture holding all six and asserts each path's state. Cheaper substitute: comparing only project against kit must fail, because it cannot tell `kit-newer` from `project-changed`.
- [x] Report `project-only` in `diff_project` for a path the record names that the kit no longer ships. Done when: a test removes a template file from a scratch copy of a kit and the installed copy is reported `project-only`, not dropped from the output.
- [x] Classify without a record entry in `diff_project` as `missing`, `identical` or `differs`: for every file of a kit the record does not name (`"record": false` on that kit), and for a planned file with no entry under a recorded kit (one the project had before the install). Done when: a test deletes `.conclave/kits.json` from the six-state fixture and finds only those three states, and a test with a recorded `reviewer` and an unrecorded `todo` finds `todo` reported with `"record": false`. **Corrected 2026-11-11 (validation):** the no-entry cases had no state.
- [x] Choose the kits and the agents in `diff_project`: the kits the record names together with `installed_kits(target_root)`, narrowed to one by the optional `kit` argument; for each kit the agents the record holds, else every agent whose folder (`.agents`, `.claude`, `.codex`) exists in the project, else all three, planning each agent and taking the union. Done when: tests show a Claude-only project reports no `.agents/` or `.codex/` file as `missing`, and naming a kit the project does not have refuses with exit 2. **Corrected 2026-11-11 (validation):** the record alone hid a kit installed before the record existed.
- [x] Plan the WordPress kit in `diff_project` with the host the record holds, so a deleted pin still compares against the recorded host's overlay, and refuse with exit 2 when the pin names another host than the record. Done when: a `wpcom` install whose pin is deleted reports its `wpcom` overlay files and no `pressable` file, and a pin edited to `pressable` under a `wpcom` record refuses naming both. **Corrected 2026-11-11 (plan review):** added.
- [x] Refuse a target in `diff_project` that does not exist or is not a folder with exit 2, and report a folder with no kit as `"kits": {}` with exit 0. Done when: command-line tests cover a missing path, a file and an empty folder. **Corrected 2026-11-11 (plan review):** added.
- [x] Report a project or kit file that cannot be read in `diff_project` as `unreadable` with the error's reason, and go on with the rest. Done when: a test injecting a `PermissionError` on one file's read finds that path `unreadable`, every other path classified, exit 0, no traceback and nothing written. **Corrected 2026-11-11 (plan review):** added; `main` catches only `ValueError`.
- [x] Report an unsafe destination in `diff_project` as `unsafe` without reading it: a link, a folder, or a path under a parent that is a link or not a folder. Done when: a test with a symlinked skill file and a skill folder that is a link finds both `unsafe` and the link targets unread. Cheaper substitute: reading through the link must fail, since it compares bytes outside the project. **Corrected 2026-11-11 (validation):** added.
- [x] Report the generated Laravel `.mcp.json` in `diff_project` as `generated` when it is a file and `missing` when absent, with no digest comparison; `unsafe` takes precedence. Done when: a Laravel fixture test finds `.mcp.json` `generated`, `missing` after it is deleted, and `unsafe` as a folder, a link and a dangling link. **Corrected 2026-11-11 (validation, plan review):** added; the generated entry has no source to compare, and the plan review asked for the precedence.
- [x] Add the `diff` subcommand to `main` and `_run` in `forge.py`, printing JSON like the other commands (`target`, `record`, `sdk_commit`, and per kit a list of `{"path", "state"}`), with `--patch` adding a unified diff from `difflib` for each `project-changed`, `both-changed` and `differs` text file. Done when: a test runs the command line and parses the output; `--patch` on a `project-changed`, a `both-changed` and a `differs` file gives a unified diff headed `--- project/<path>` and `+++ kit/<path>` whose `-` line is the project's and `+` line the kit's; and on a binary or non-UTF-8 file it prints `binary` in place of a diff. **Corrected 2026-11-11 (plan review):** a stub returning no patch passed.
- [x] Prove `diff` writes nothing in `tests/test_forge.py`: digest every file under the fixture before and after, including `.conclave/kits.json`. Done when: the test fails if `diff_project` is made to write the record. Cheaper substitute: asserting only that the record's bytes are unchanged must fail review, since a created file elsewhere would pass it.
- [x] Add a `diff` section to `README.md` with every state and what each means for the project. Done when: every state name in `forge.py` (`DIFF_STATES`) appears in the README table, a test asserts it, and its rows are within 120 characters. **Corrected 2026-11-11 (validation):** the states are eleven, not seven.
- [x] Commit: `forge: diff reports each kit file's state without writing`

**Test checkpoint:** `python -m unittest discover -s tests -p test_forge.py` ends `OK`; making `diff_project` ignore the record makes the six-state test fail.

> **Verified:** 2026-11-11 | §3 | ea657586cfeb869daefa9ea35f7eb3a977ef9c59
> **Review:** `docs/reviews/d01-t01-s3.json`

## 4. `forge.py update` for missing and kit-newer files

> **Started:** 2026-11-11T19:25:59Z

`forge.py update <project> [kit] [--only <path>]` brings a project up to date without ever writing over its own work (recommendation 3): only `missing` and `kit-newer` files are written, and `--only` lets a project take one script or skill.

**Corrected 2026-11-11 (validation):** §2 shipped `_write_recorded`, which stages, records and renames one file at a time with a journal, so the record is kept true file by file rather than "written once after the files"; §3 shipped states this section did not name (`unsafe`, `unreadable`, `generated`, and `differs` for a file with no record entry). The items below say what `update` does with each, and that it settles an interrupted run (`_recover`) before writing, as `kit` does.

**Phase:** 1
**Needs:** none
**Surface:** no

**Build order:**

1. Add `update_project` and the `update` subcommand to `forge.py`. Done when: a fixture's `kit-newer` file is replaced and its `project-changed` file is not.
2. Cover the refusals and the record. Done when: the checkpoint passes.

- [ ] Add `update_project(target_root, kit_name=None, only=(), dry_run=False)` to `forge.py`, writing each `missing` and `kit-newer` file from `diff_project` through `_write_recorded` and listing every other non-identical file with its state under `left` (`unreadable` with its reason, and the generated `.mcp.json`, which only `kit` builds). **Corrected 2026-11-11 (validation):** said `atomic_write`, which leaves the record behind the file. Done when: a test on the six-state fixture finds the `missing` and `kit-newer` files equal to the kit and the `project-changed`, `both-changed`, `project-removed` and `project-only` files byte for byte as before. Cheaper substitute: an `overwrite=True` copy of the kit must fail this test.
- [ ] Restrict `update_project` with `only`: each value is a file or a folder relative to the project, `..` and absolute paths refuse, a value that matches no kit file refuses naming it, and a `project-removed` file is written only when `only` names it or its folder. Done when: tests cover one file, one folder, a path outside the project, a path no kit ships and a restored removed file.
- [ ] Update the record in `update_project` through `_write_recorded`: each written file's digest becomes the kit's and its kit's `sdk_commit` the current one, one file at a time, so when a write fails part way the files already replaced are recorded and the failing one is neither written nor recorded. **Corrected 2026-11-11 (validation):** said the record was written once after the files. Done when: a test injects a failing write on the second of three files and finds the first file new, the record naming the first file's new digest and the third file untouched.
- [ ] Refuse an unsafe destination in `update_project` before any write, as `apply_kit` does: any `unsafe` path inside the selection (a link, a folder, or a parent that is a link or not a folder) refuses naming it. Done when: a test with a linked skill folder exits 2 and writes nothing, and the same project updated with `--only` a path outside that folder succeeds.
- [ ] Settle an interrupted run in `update_project` with `_recover` before the diff, and re-read each file's digest just before its write, leaving it under `left` as `changed-since-diff` when it no longer matches what was classified. Done when: a test leaves a staged `.forge-new` file for a recorded, deleted file and finds it moved into place, and a test that edits a `kit-newer` file between the diff and the write finds the edit kept. Cheaper substitute: writing from the diff's classification alone must fail the edit test. **Corrected 2026-11-11 (validation):** added.
- [ ] Record the agents in `update_project` that the diff compared for a kit with no record entry yet, not only one, by letting `_record_install` take a list of agents. Done when: a project with `.claude` and `.codex` folders and no record updates a missing file and the record names both. **Corrected 2026-11-11 (validation):** added; `_record_install` took one agent or `all`.
- [ ] Leave out `scripts/` in `update_project` with `no_scripts=True` (`--no-scripts`), as `init --no-scripts` does. Done when: a test on an install made with `--no-scripts` updates with the flag and finds no `scripts/` file written. **Corrected 2026-11-11 (validation):** added; a project that opted out of scripts had no way to keep that through `update`.
- [ ] Update without a record in `update_project`: write `missing` files only, list `differs` files under `left`, and say in the result that `record` (§5) makes the rest updatable. Done when: a test without `.conclave/kits.json` finds a differing file untouched and the hint present.
- [ ] Add the `update` subcommand to `main` and `_run` in `forge.py` with `--only` (repeatable), `--no-scripts` and `--dry-run`, printing JSON with `written`, `left` and `record`. Done when: a test runs the command line twice and the second run writes nothing.
- [ ] Add an `update` section to `README.md` beside `diff`, stating that it never writes over a changed file. Done when: the README names `--only` and `--dry-run` with one example each.
- [ ] Commit: `forge: update writes only missing and kit-newer files`

**Test checkpoint:** `python -m unittest discover -s tests -p test_forge.py` ends `OK`; making `update_project` also write `project-changed` files makes the six-state test fail.

## 5. `forge.py record` for projects installed before the record

Every project installed so far has no record, so none of its files can be `kit-newer`. `forge.py record <project>` writes a record for the files that are byte-identical to the current kit, which is the only state where the installed bytes are known.

**Phase:** 1
**Needs:** none
**Surface:** no

**Build order:**

1. Add `record_project` and the `record` subcommand to `forge.py`. Done when: an old install gains entries for its identical files only.
2. Cover it and document it. Done when: the checkpoint passes.

- [ ] Add `record_project(target_root, kit_name=None, dry_run=False)` to `forge.py`: for every kit the project has, add a record entry for each file whose digest equals the kit's, with the current SDK commit. Done when: a test on a project with one edited skill finds every other file recorded and the edited one absent. Cheaper substitute: recording every file the project has must fail, because a later `update` would overwrite the edit.
- [ ] Keep existing entries in `record_project`: an entry already in the record is never replaced, so running it after an `update` changes nothing. Done when: a test records, edits a kit template in a scratch SDK copy, records again and finds the first digest still there and the file reported `kit-newer` by `diff_project`.
- [ ] Add the `record` subcommand to `main` and `_run` in `forge.py` with `--dry-run`, printing `recorded` and `skipped` with the reason for each skipped file (`differs` or `missing`). Done when: a test parses the output of the command line.
- [ ] Describe `record` in `README.md` under the existing-project steps: run `record`, then `diff`, then `update`. Done when: the three commands appear in that order with the SDK's path spelled as the rest of the README spells it.
- [ ] Commit: `forge: record adopts an install made before the record existed`

**Test checkpoint:** `python -m unittest discover -s tests -p test_forge.py` ends `OK`; making `record_project` record a differing file makes the edited-skill test fail.

## 6. `.kit-new` copies for a hand merge

A file both sides changed cannot be updated safely. `update --kit-new` writes the kit's version beside the project's as `<name>.kit-new`, never over it, so the project merges by hand (recommendation 3).

**Phase:** 1
**Needs:** none
**Surface:** no

**Build order:**

1. Add `kit_new` to `update_project` in `forge.py`. Done when: a `both-changed` file gains a sibling and is itself unchanged.
2. Cover the leftovers. Done when: the checkpoint passes.

- [ ] Add `kit_new=False` to `update_project` and `--kit-new` to the `update` subcommand in `forge.py`: for each `project-changed`, `both-changed` and `differs` file inside the `only` filter, write the kit's bytes to `<path>.kit-new`. Done when: a test finds the sibling equal to the kit, the project's file byte for byte as before and no record entry for the sibling.
- [ ] Skip a `project-changed` file whose kit bytes equal the recorded ones in `update_project`, since the kit has nothing new to merge. Done when: a test finds no sibling for it and a sibling for the `both-changed` one.
- [ ] Report leftover siblings in `diff_project`: a `<path>.kit-new` beside a kit file is listed under `merge_pending`. Done when: a test finds the sibling listed after `--kit-new` and gone from the list once the file is deleted.
- [ ] Keep `.kit-new` files out of every kit plan in `kit_plan`, so a sibling left in a kit by mistake is never installed. Done when: a test with a `.kit-new` file in a scratch kit's templates finds it absent from the plan.
- [ ] Document the merge in `README.md`: compare, edit the project's file, delete the sibling, then `forge.py record` to mark the merged file. Done when: the steps are in the `update` section.
- [ ] Commit: `forge: update --kit-new writes a changed file's kit version beside it`

**Test checkpoint:** `python -m unittest discover -s tests -p test_forge.py` ends `OK`; making `--kit-new` write to the project's own path makes the sibling test fail.

## 7. Weekly drift report across projects

A scheduled task runs `diff` over the owner's projects once a week and reports which have files that can be updated and which need a merge (recommendation 4). It proposes; nothing is written to a project. The report is run from the SDK, because a project holds no path back to it.

**Phase:** 1
**Needs:** none
**Surface:** no

**Build order:**

1. Add `forge.py drift` reading `.conclave/projects.json`. Done when: it prints one line per project and exits 3 when any has drift.
2. Schedule it in the SDK's own `.conclave/automations/tasks.json`. Done when: `python forge.py doctor . automations --strict` passes.

- [ ] Add `load_projects(path)` to `forge.py`, reading `{"schema_version": 1, "projects": [{"name": "<name>", "windows": "<path or null>", "posix": "<path or null>"}]}`. Done when: tests refuse a missing `name`, a duplicate name, an entry with both paths null and an unknown key, each naming the file and the entry.
- [ ] Add `drift_report(projects)` to `forge.py`: for each project, use the path for this operating system, call `diff_project`, and count the files in each state. A project with no path for this system, or a path that does not exist here, is listed as `not on this machine` and does not fail the report. Done when: a test with one drifted project, one current project and one absent path reports all three.
- [ ] Add the `drift` subcommand to `main` and `_run` in `forge.py`, printing one line per project (`<name>: <n> can update, <n> need a merge, <n> missing`) with the paths of at most 20 files each, and exiting 3 when any project has a `kit-newer`, `missing`, `both-changed` or `project-only` file. Done when: a test asserts exit 0 for current projects and exit 3 with the line for a drifted one. Cheaper substitute: exiting 0 always must fail, because the automations runner emails only on a non-zero exit.
- [ ] Create `.conclave/projects.json` in the SDK listing RasterFold (`~/projects/RasterFold` in WSL) and Impossible OS (`~/projects/impossible-os` in WSL), the two projects the roadmap names, with home-relative paths expanded by `os.path.expanduser`. Done when: `python forge.py drift` reads it on Windows, where both are `not on this machine`, without error.
- [ ] Add the task `conclave-sdk-drift` to `.conclave/automations/tasks.json`: `["python", "forge.py", "drift"]`, weekly on Monday at 07:30, `timeout_minutes` 10. Done when: `python forge.py doctor . automations --strict` exits 0 and `python .conclave/automations/run.py --check` prints the folder.
- [ ] Describe the report in `README.md` and in `.conclave/automations/README.md`: what an exit of 3 means, that the email is the report, and how to add a project. Done when: both name `.conclave/projects.json`.
- [ ] Commit: `forge: weekly drift report over the listed projects`

**Test checkpoint:** `python -m unittest discover -s tests -p test_forge.py` ends `OK` and `python forge.py doctor . automations --strict` exits 0; making `drift` exit 0 for a drifted project makes its test fail.

## 8. `init` that writes nothing when a kit refuses

`provision` applies the chosen kits in order (`forge.py:653`), so `init --kit todo --kit laravel` on a folder with no `artisan` writes the base and todo kits and then refuses (roadmap finding 14). Every kit is planned before any file is written.

**Phase:** 1
**Needs:** none
**Surface:** no

**Build order:**

1. Plan every chosen kit in `provision` before the first write. Done when: a refusing kit leaves the target empty.
2. Cover it in `tests/test_forge.py`. Done when: the checkpoint passes.

- [ ] Call `kit_plan` for every selected kit in `provision` of `forge.py` before the first `apply_kit`, and run the unsafe-parent check (`forge.py:280`) over the combined plan. Done when: a test runs `init --kit todo --kit laravel` on an empty folder, gets exit 2 naming `artisan`, and finds the folder still empty. Cheaper substitute: deleting the written files after a refusal must fail review, since a file the project already had could be among them.
- [ ] Refuse an unknown kit name in `provision` before any write, naming the available kits. Done when: a test with `--kit nope` finds exit 2 and an empty target.
- [ ] Create the target folder in `provision` only after the plans succeed, so a refused `init` on a new path leaves no folder behind. Done when: a test with a path that does not exist and a refusing kit finds the path still absent.
- [ ] Commit: `forge: init plans every kit before it writes one`

**Test checkpoint:** `python -m unittest discover -s tests -p test_forge.py` ends `OK`; moving the plan loop after the first `apply_kit` makes the empty-folder test fail.

## 9. Backup of the entry docs `init --force` replaces

`init --force` writes the kit's `AGENTS.md`, `GEMINI.md`, `CLAUDE.md` and `CODEX.md` over the project's (`forge.py:657`) and keeps no copy (roadmap finding 15). The replaced file is kept beside the new one.

**Phase:** 1
**Needs:** none
**Surface:** no

**Build order:**

1. Keep each replaced doc as `<name>.replaced` in `provision`. Done when: the project's old bytes are readable after `--force`.
2. Cover the repeat and the no-op. Done when: the checkpoint passes.

- [ ] Write the project's existing entry doc to `<name>.replaced` with `atomic_write` in `provision` of `forge.py` before the kit's version replaces it, and list the backups under `backups` in the result. Done when: a test finds `AGENTS.md.replaced` holding the old bytes and `AGENTS.md` holding the kit's. Cheaper substitute: printing the old content must fail, because the output is not kept.
- [ ] Skip a doc whose bytes already equal the kit's in `provision`: no rewrite and no backup. Done when: a test running `init --force` twice finds one backup, not two, and the second run's `backups` empty.
- [ ] Refuse `init --force` in `provision` when a `<name>.replaced` already exists for a doc that would be replaced, naming it, before any file is written. Done when: a test finds exit 2 and both the doc and the earlier backup unchanged. Cheaper substitute: overwriting the earlier backup must fail, because it is the only copy of the first version.
- [ ] State the backup in the `--force` help text in `main` of `forge.py` and in `README.md`. Done when: `python forge.py init --help` names `.replaced`.
- [ ] Commit: `forge: init --force keeps the entry docs it replaces`

**Test checkpoint:** `python -m unittest discover -s tests -p test_forge.py` ends `OK`; removing the backup write makes the old-bytes test fail.

## Verification

- A scratch project is installed with `init --kit todo`, one skill is edited, a kit template is changed in a scratch copy of the SDK, and `diff`, `update` and `diff` again show the edited skill untouched, the changed template taken and no file left `kit-newer`.
- `python forge.py drift` over a list holding that project exits 3 before the update and 0 after it.
- `python -m unittest discover -s tests` passes.
- `python scripts/todo-graph.py validate` and `python scripts/todo-graph.py plan --check` pass.
