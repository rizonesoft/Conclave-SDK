---
schema_version: 1
id: install-record-and-update
domain: 01-forge
status: done
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
| 4 | §4 | `forge.py update` for missing and kit-newer files | §3 | [x] |
| 5 | §5 | `forge.py record` for projects installed before the record | §3 | [x] |
| 6 | §6 | `.kit-new` copies for a hand merge | §4 | [x] |
| 7 | §7 | Weekly drift report across projects | §3 | [x] |
| 8 | §8 | `init` that writes nothing when a kit refuses | §1 | [x] |
| 9 | §9 | Backup of the entry docs `init --force` replaces | -- | [x] |

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

- [x] Add `update_project(target_root, kit_name=None, only=(), dry_run=False)` to `forge.py`, writing each `missing` and `kit-newer` file from `diff_project` through `_write_recorded` and listing every other non-identical file with its state under `left` (`unreadable` with its reason) and, for `project-changed`, `both-changed` and `differs`, its `patch` from `diff_project` (or `binary`), as recommendation 3 asks. **Corrected 2026-11-11 (plan review):** leftovers had no diff. **Corrected 2026-11-11 (validation):** said `atomic_write`, which leaves the record behind the file. Done when: a test on the six-state fixture finds the `missing` and `kit-newer` files equal to the kit and the `project-changed`, `both-changed`, `project-removed` and `project-only` files byte for byte as before. A test asserts the `project-changed` leftover's patch has the project's edit on a `-` line. Cheaper substitute: an `overwrite=True` copy of the kit must fail this test.
- [x] Never copy a generated entry in `update_project`, whatever its state: the Laravel `.mcp.json` goes under `left` with its state (`generated` or `missing`) and the hint that `forge.py kit <project> laravel` builds it. Done when: a Laravel test finds `.mcp.json` untouched when present and still absent when missing, with the hint in the result. **Corrected 2026-11-11 (plan review):** a missing generated entry has no source to copy.
- [x] Restrict `update_project` with `only`: each value is a file or a folder relative to the project, `..` and absolute paths refuse, a value that matches no kit file refuses naming it, and a `project-removed` file is written only when `only` names it or its folder. Done when: tests cover one file, one folder, a path outside the project, a path no kit ships and a restored removed file.
- [x] Update the record in `update_project` through `_write_recorded`: each written file's digest becomes the kit's and its kit's `sdk_commit` the current one, one file at a time, so a failure part way leaves the files before it written and recorded. For the failing file: a failed staging or record write leaves it unwritten and its entry as before; a failed rename leaves the new digest recorded with the staged file and journal, which the next `kit` or `update` settles through `_recover` (finished if the file is unchanged, rolled back if the project edited it meanwhile). Done when: tests inject each of the three failures on the second of three files and check the first file new and recorded, the second as stated, the third untouched, and after a rename failure a retry finishing the file, or keeping an edit made in between. **Corrected 2026-11-11 (validation, plan review):** said the record was written once after the files, then that the failing file is never recorded, which a failed rename contradicts.
- [x] Refuse an unsafe destination in `update_project` before any write, as `apply_kit` does: any `unsafe` path inside the selection (a link, a folder, or a parent that is a link or not a folder) refuses naming it. Done when: a test with a linked skill folder exits 2 and writes nothing, and the same project updated with `--only` a path outside that folder succeeds.
- [x] Order `update_project` so every refusal comes before any write: a read-only `diff_project`, then the `only` and unsafe refusals over it, then `_recover` (which settles the whole record, inside the selection or not), then a second `diff_project` that the writes use. Done when: tests on an interrupted project (a staged `.forge-new` and a journal left) with an `--only` that matches nothing, and with an unsafe selected destination, each exit 2 and leave every file under the target byte for byte as before. **Corrected 2026-11-11 (plan review):** recovery could write before a refusal.
- [x] Settle an interrupted run in `update_project` with `_recover` after the refusals, and re-read each file's digest just before its write, leaving it under `left` as `changed-since-diff` when it no longer matches what was classified. Done when: a test leaves a staged `.forge-new` file for a recorded, deleted file and finds it moved into place, and a test that edits a `kit-newer` file between the diff and the write finds the edit kept. Cheaper substitute: writing from the diff's classification alone must fail the edit test. **Corrected 2026-11-11 (validation):** added.
- [x] Record the agents in `update_project` that the diff compared for a kit with no record entry yet, not only one, by letting `_record_install` take a list of agents. Done when: a project with `.claude` and `.codex` folders and no record updates a missing file and the record names both. **Corrected 2026-11-11 (validation):** added; `_record_install` took one agent or `all`.
- [x] Leave out `scripts/` in `update_project` with `no_scripts=True` (`--no-scripts`), as `init --no-scripts` does. Done when: a test on an install made with `--no-scripts` updates with the flag and finds no `scripts/` file written. **Corrected 2026-11-11 (validation):** added; a project that opted out of scripts had no way to keep that through `update`.
- [x] Preview with `dry_run=True` in `update_project`: no `_recover`, no write and no record change, listing under `written` what a run would write. Done when: tests on an ordinary and an interrupted project find every file under the target byte for byte as before and `written` naming the `missing` and `kit-newer` files. **Corrected 2026-11-11 (plan review):** `_recover` writes, and the preview had no no-write test.
- [x] Update without a record in `update_project`: write `missing` files only, list `differs` files under `left`, and say in the result that `record` (§5) adopts the files identical to the kit as installed, and that a differing file is merged by hand, with `update --kit-new` (§6) to help. **Corrected 2026-11-11 (plan review):** the hint said `record` makes differing files updatable, which §5 does not. Done when: a test without `.conclave/kits.json` finds a differing file untouched and the hint present.
- [x] Add the `update` subcommand to `main` and `_run` in `forge.py` with `--only` (repeatable), `--no-scripts` and `--dry-run`, printing JSON with `written`, `left` and `record`. Done when: a test runs the command line on the six-state fixture, parses the first run's JSON naming the `missing` and `kit-newer` files under `written` with their new digests in the record, finds the second run's `written` empty and a following `diff` reporting both `identical`, and runs `--only` twice and `--no-scripts` through the command line. **Corrected 2026-11-11 (plan review):** a command that did nothing passed.
- [x] Add an `update` section to `README.md` beside `diff`, stating that it never writes over a changed file. Done when: the README names `--only` and `--dry-run` with one example each.
- [x] Commit: `forge: update writes only missing and kit-newer files`

**Test checkpoint:** `python -m unittest discover -s tests -p test_forge.py` ends `OK`; making `update_project` also write `project-changed` files makes the six-state test fail.

> **Verified:** 2026-11-11 | §4 | 884c2231d05db3fc58b4a4838f9234c93606eaa5
> **Review:** `docs/reviews/d01-t01-s4.json`

## 5. `forge.py record` for projects installed before the record

> **Started:** 2026-11-11T19:43:13Z

Every project installed so far has no record, so none of its files can be `kit-newer`. `forge.py record <project>` writes a record for the files that are byte-identical to the current kit, which is the only state where the installed bytes are known.

**Corrected 2026-11-11 (validation):** §3 reports more states than `differs` and `missing` (`unsafe`, `unreadable`, `generated`, `project-only`), and §2 leaves an interrupted run for the next writer to settle; the items below say what `record` does with each and that it settles first, as `kit` and `update` do. A kit the record already names keeps its `sdk_commit`, `agents` and `host`: adopting a file is not an install.

**Phase:** 1
**Needs:** none
**Surface:** no

**Build order:**

1. Add `record_project` and the `record` subcommand to `forge.py`. Done when: an old install gains entries for its identical files only.
2. Cover it and document it. Done when: the checkpoint passes.

- [x] Add `record_project(target_root, kit_name=None, dry_run=False)` to `forge.py`: for every kit the project has, add a record entry for each file whose digest equals the kit's, with the current SDK commit for a kit the record does not yet name (its agents the ones `diff_project` compared, its host the plan's), and the kit's own entry left as it is for one it does. Done when: a test on a project with one edited skill finds every other file recorded and the edited one absent, and a test with a recorded kit finds its `sdk_commit`, `agents` and `host` unchanged after `record`; read-back tests find a Claude-only legacy install recorded with `agents` `["claude"]` and the current commit, and a `wpcom` legacy install with `host` `wpcom`, and a following `diff_project` comparing only those. **Corrected 2026-11-11 (validation, plan review):** the kit entry rules were unstated, and only their preservation was tested. Cheaper substitute: recording every file the project has must fail, because a later `update` would overwrite the edit.
- [x] Keep existing entries in `record_project`: an entry already in the record is never replaced, so running it after an `update` changes nothing. Done when: a test records, edits a kit template in a scratch SDK copy, records again and finds the first digest still there and the file reported `kit-newer` by `diff_project`.
- [x] Write the record in `record_project` once, through `write_record`, after every entry is decided; a failed write raises, so the command exits non-zero and prints no `recorded` list. Done when: a test whose `write_record` fails finds the earlier record byte for byte as before and every project file unchanged, and the command line exits non-zero with no traceback. **Corrected 2026-11-11 (plan review):** a failed write had no stated result.
- [x] Settle an interrupted run in `record_project` with `_recover` after the read-only refusals (the target, the record, the kit named and its plan) and before it reads the states, except on `--dry-run`, which writes nothing at all. Done when: `record <project> nope` and a refusing plan on an interrupted project exit 2 and leave its files and staged file as they were, a test with a staged `.forge-new` for a recorded, deleted file finds it moved into place by `record`, and a dry run on the same fixture leaves every file under the target byte for byte as before while listing what it would record. **Corrected 2026-11-11 (validation, plan review):** added; the plan review put the refusals before recovery.
- [x] Add the `record` subcommand to `main` and `_run` in `forge.py` with `--dry-run`, printing `recorded` and `skipped` with the reason for each skipped file: its `diff` state (`differs`, `missing`, `unsafe`, `unreadable`, `generated`) or `recorded` for a file that already has an entry. Done when: a test parses the output of the command line and finds each of those reasons on a fixture holding it. **Corrected 2026-11-11 (validation):** the reasons were only `differs` and `missing`.
- [x] Describe `record` in `README.md` under the existing-project steps: run `record`, then `diff`, then `update`. Done when: the three commands appear in that order with the SDK's path spelled as the rest of the README spells it.
- [x] Commit: `forge: record adopts an install made before the record existed`

**Test checkpoint:** `python -m unittest discover -s tests -p test_forge.py` ends `OK`; making `record_project` record a differing file makes the edited-skill test fail.

> **Verified:** 2026-11-11 | §5 | f68484bc42d081b423296bde1f968cc3f69f3c82
> **Review:** `docs/reviews/d01-t01-s5.json`

## 6. `.kit-new` copies for a hand merge

> **Started:** 2026-11-11T19:54:30Z

A file both sides changed cannot be updated safely. `update --kit-new` writes the kit's version beside the project's as `<name>.kit-new`, never over it, so the project merges by hand (recommendation 3).

**Corrected 2026-11-11 (validation):** two drifts. A `project-changed` file has, by §3's definition, kit bytes equal to the recorded ones, so items 1 and 2 contradicted each other: siblings are for `both-changed` and `differs` only. And the merge's last step, `forge.py record`, never replaces an entry (§5), so a merged file would stay `both-changed` for ever: `record --merged <path>` is added to move its entry to the kit's digest, after which it reads `project-changed` (the project's own version of the current kit).

**Phase:** 1
**Needs:** none
**Surface:** no

**Build order:**

1. Add `kit_new` to `update_project` in `forge.py`. Done when: a `both-changed` file gains a sibling and is itself unchanged.
2. Cover the leftovers. Done when: the checkpoint passes.

- [x] Add `kit_new=False` to `update_project` and `--kit-new` to the `update` subcommand in `forge.py`: for each `both-changed` and `differs` file inside the `only` filter, write the kit's bytes to `<path>.kit-new` with `atomic_write`, list it under `kit_new`, and on `--dry-run` only list it. Done when: a command-line test finds siblings for a `both-changed` and a `differs` file equal to the kit and listed under `kit_new`, the project's files byte for byte as before and no record entry for either sibling; `--only` leaves a file outside it without a sibling; `--no-scripts` writes none under `scripts/`; and a dry run leaves every file and the record byte for byte as before. Cheaper substitute: writing the kit's bytes over the project's file must fail this test. **Corrected 2026-11-11 (validation):** named `project-changed`, which item 2 excludes.
- [x] Skip a `project-changed` file in `update_project`, whose kit bytes equal the recorded ones, since the kit has nothing new to merge. Done when: a test finds no sibling for it and a sibling for the `both-changed` one.
- [x] Never replace an existing sibling in `update_project`: a `<path>.kit-new` already there (the project may be merging from it) or one that is a link or a folder is left and listed under `left` as `merge-pending`. Done when: tests with an edited sibling, a sibling that is a folder and a dangling link each run `--kit-new` again and find the sibling as it was (the link's target never created), the path listed as `merge-pending` and the file's record entry unchanged. Cheaper substitute: checking `Path.exists()` alone must fail the dangling-link case. **Corrected 2026-11-11 (validation):** added.
- [x] Report leftover siblings in `diff_project`: a `<path>.kit-new` beside a kit file is listed under `merge_pending`. Done when: a test finds the sibling listed after `--kit-new` and gone from the list once the file is deleted.
- [x] Keep `.kit-new` files, and forge's own staged `.forge-new` and `.forge-replace` files, out of every kit plan in `kit_plan`, so one left in a kit by mistake is never installed. Done when: a test with each in a scratch kit's templates finds them absent from the plan. **Corrected 2026-11-11 (validation):** the staged suffixes are the same mistake.
- [x] Add `merged=()` to `record_project` and `--merged <path>` (repeatable, relative to the project as `--only` is) to `record` in `forge.py`: for each named kit file whose `<path>.kit-new` is a regular file still holding the kit's current bytes, set its entry to that digest under its kit (creating the kit and file entries for a file with no entry), write the record once, then remove the sibling. Every argument is checked before `_recover` and before any write, and one bad argument refuses the batch: no sibling, a sibling the project edited or one the kit has moved past (re-run `update --kit-new` after deleting it), a link or folder, or a path no kit ships. `--dry-run` lists what it would record and changes nothing. Done when: a test merges a `both-changed` file by hand and runs `record --merged` to find `diff` reporting it `project-changed` and the sibling gone; a merge that took the kit's version whole (`identical`) is accepted and a later kit change reads `kit-newer`; a `differs` file with no entry gains its kit and file entries; a test that changes the kit template between `update --kit-new` and `record --merged` gets exit 2 with the record unchanged; a batch of one good and one bad path changes nothing; an interrupted project refuses with its staged file untouched; and `--dry-run --merged` leaves every file and the record byte for byte as before. Cheaper substitute: recording the merged file's own digest must fail, since `update` would then take the next kit version over the merge. **Corrected 2026-11-11 (validation, plan review):** added; plain `record` never replaces an entry, and the plan review found that recording the current kit's digest after the SDK moved would hide the newer change.
- [x] Document the merge in `README.md`: compare, edit the project's file, then `python forge.py record <project> --merged <path relative to the project>`, which checks the sibling against the kit, records it and removes it. Done when: the README example names the project and a relative path, and a test runs that exact command line. **Corrected 2026-11-11 (validation, plan review, round 1):** said plain `record`, then omitted the project argument, then told the project to delete the copy that `--merged` checks. Done when: the steps are in the `update` section.
- [x] Commit: `forge: update --kit-new writes a changed file's kit version beside it`

**Test checkpoint:** `python -m unittest discover -s tests -p test_forge.py` ends `OK`; making `--kit-new` write to the project's own path makes the sibling test fail.

> **Verified:** 2026-11-11 | §6 | 53d5b0905d9834cbf93f3971ae79a8f4f2c5fc98
> **Review:** `docs/reviews/d01-t01-s6.json`

## 7. Weekly drift report across projects

> **Started:** 2026-11-11T20:09:28Z

A scheduled task runs `diff` over the owner's projects once a week and reports which have files that can be updated and which need a merge (recommendation 4). It proposes; nothing is written to a project. The report is run from the SDK, because a project holds no path back to it.

**Corrected 2026-11-11 (validation):** the task runs from Windows Task Scheduler on this machine, where a project listed by its WSL path alone is always `not on this machine`, so the weekly report would never report anything. Both projects are reachable from Windows as `\\wsl.localhost\Ubuntu\home\derickpayne\projects\<name>` (checked 2026-11-11), so each entry carries that `windows` path beside its `posix` one. §3 added states the counts must place: `project-only` is counted as retired, and a project `diff` refuses is reported with its error and fails the report.

**Phase:** 1
**Needs:** none
**Surface:** no

**Build order:**

1. Add `forge.py drift` reading `.conclave/projects.json`. Done when: it prints one line per project and exits 3 when any has drift.
2. Schedule it in the SDK's own `.conclave/automations/tasks.json`. Done when: `python forge.py doctor . automations --strict` passes.

- [x] Add `load_projects(path)` to `forge.py`, reading `{"schema_version": 1, "projects": [{"name": "<name>", "windows": "<path or null>", "posix": "<path or null>"}]}`. Done when: a valid file reads back equal to what was written, and tests refuse a missing `name`, a duplicate name, an entry with both paths null, an unknown key, another `schema_version`, and a `name` or path that is not a string, each naming the file and the entry. **Corrected 2026-11-11 (plan review):** the read-back, the schema and the field types were untested.
- [x] Add `drift_report(projects)` to `forge.py`: for each project, use the path for this operating system, call `diff_project`, and count the files in each state. A project with no path for this system, or a path that does not exist here, is listed as `not on this machine` and does not fail the report; one whose `diff` refuses (a malformed record, a pin conflict) is listed with the error and fails it, and the projects after it are still reported. Each state is counted exactly: `kit-newer` (can update), `missing`, `both-changed` (need a merge), `differs` (unrecorded: run `record`, then merge), `project-only` (retired), and `unsafe` and `unreadable` together as incomplete, with their reasons. Done when: a test with one drifted project holding a known count of each state, one current project, one absent path and one with a malformed record placed before the others reports all four with those exact counts; a test picks the `windows` path when `os.name` is `nt` and the `posix` one otherwise, with `~` expanded. **Corrected 2026-11-11 (validation, plan review):** a refused diff had no result, and `differs`, `unsafe` and `unreadable` were not counted, so a project holding only those read as current.
- [x] Add the `drift` subcommand to `main` and `_run` in `forge.py`, printing one line per project (`<name>: <n> can update, <n> need a merge, <n> unrecorded, <n> missing, <n> retired, <n> incomplete`) with the paths of at most 20 files under each count and a `... and <n> more` line past that, and exiting 3 when any project has a file in any of those states or its diff refused. Done when: tests assert exit 0 for current projects, exit 3 with the line for a drifted one, exit 3 for a project whose only state is `differs` and for one whose only state is `unreadable`, exit 3 for a malformed record, and a 25-file count printing 20 paths and `... and 5 more`. **Corrected 2026-11-11 (plan review):** `differs`, `unsafe`, `unreadable` and the 20-file limit were not covered. Cheaper substitute: exiting 0 always must fail, because the automations runner emails only on a non-zero exit.
- [x] Create `.conclave/projects.json` in the SDK listing RasterFold and Impossible OS, the two projects the roadmap names, each with its `posix` path (`~/projects/RasterFold`, `~/projects/impossible-os`, expanded by `os.path.expanduser`) and its `windows` path through `\\wsl.localhost\Ubuntu`. Done when: `python forge.py drift` on this Windows machine reports both projects with counts, not `not on this machine`. **Corrected 2026-11-11 (validation):** said both would be `not on this machine` on Windows, where the task runs.
- [x] Add the task `conclave-sdk-drift` to `.conclave/automations/tasks.json`: `["python", "forge.py", "drift"]`, weekly on Monday at 07:30, `timeout_minutes` 10. Done when: `python forge.py doctor . automations --strict` exits 0 and `python .conclave/automations/run.py --check` prints the folder.
- [x] Register the task on this machine with `pwsh .conclave/automations/install.ps1` and read it back. Done when: `Get-ScheduledTask -TaskPath '\Conclave-SDK\' -TaskName conclave-sdk-drift` shows an action running `run.py conclave-sdk-drift` and a weekly Monday 07:30 trigger, quoted in the run file. **Corrected 2026-11-11 (plan review):** editing `tasks.json` does not schedule anything.
- [x] Prove a run reaches the alert in `tests/test_forge.py`: in a scratch copy of the SDK (`forge.py`, `kits/`, the real `tasks.json` and a `projects.json` naming one drifted scratch project), `run.main(["conclave-sdk-drift"], root=..., alerter=...)` runs the real command and calls the alerter with the task, exit 3 and a log tail holding the project's line. Done when: the test passes and fails when `drift` exits 0 for that project. **Corrected 2026-11-11 (plan review):** added; no test sends a real email.
- [x] Describe the report in `README.md` and in `.conclave/automations/README.md`: what an exit of 3 means, that the email is the report, and how to add a project. Done when: both name `.conclave/projects.json`.
- [x] Commit: `forge: weekly drift report over the listed projects`

**Test checkpoint:** `python -m unittest discover -s tests -p test_forge.py` ends `OK` and `python forge.py doctor . automations --strict` exits 0; making `drift` exit 0 for a drifted project makes its test fail.

> **Verified:** 2026-11-11 | §7 | 9124bf3cf719bf153932d7bc0a0ceee311a8238b
> **Review:** `docs/reviews/d01-t01-s7.json`

## 8. `init` that writes nothing when a kit refuses

> **Started:** 2026-11-11T20:26:16Z

`provision` applies the chosen kits in order (`forge.py:653`), so `init --kit todo --kit laravel` on a folder with no `artisan` writes the base and todo kits and then refuses (roadmap finding 14). Every kit is planned before any file is written.

**Corrected 2026-11-11 (validation):** `provision` is now at `forge.py` `def provision` (line numbers moved with §2 to §7). Planning a target that does not exist yet needs the Laravel and WordPress root finders (`_find_laravel_app_root`, `_find_wordpress_root`) to read a missing folder as empty, since both call `iterdir` and would raise `FileNotFoundError`; the item for the absent path covers it.

**Phase:** 1
**Needs:** none
**Surface:** no

**Build order:**

1. Plan every chosen kit in `provision` before the first write. Done when: a refusing kit leaves the target empty.
2. Cover it in `tests/test_forge.py`. Done when: the checkpoint passes.

- [x] Call `kit_plan` for every selected kit in `provision` of `forge.py` before the first `apply_kit`, and run the unsafe-parent check over the combined plan. Done when: a test runs `init --kit todo --kit laravel` on an empty folder, gets exit 2 naming `artisan`, and finds the folder still empty; and a test with an obstruction only a later kit meets (`.claude/skills/add-todo` as a file, under `init --kit todo`) gets exit 2 and finds every existing file, the record included, byte for byte as before. Removing the combined check must fail the second test. **Corrected 2026-11-11 (plan review):** the `artisan` refusal comes from `kit_plan`, so it never tested the combined check. Cheaper substitute: deleting the written files after a refusal must fail review, since a file the project already had could be among them.
- [x] Refuse an unknown kit name in `provision` before any write, naming the available kits. Done when: a test with `--kit nope` finds exit 2 and an empty target.
- [x] Create the target folder in `provision` only after the plans succeed, so a refused `init` on a new path leaves no folder behind, with `_find_laravel_app_root` and `_find_wordpress_root` returning `None` for a folder that does not exist. Done when: a test with a path that does not exist and a refusing kit finds the path still absent, and `init --kit todo` and `init --kit wordpress` on new paths still install, the latter with the host's files and its record read back. **Corrected 2026-11-11 (validation, plan review):** the root finders raised on a missing folder, and no test reached the WordPress finder.
- [x] Apply `--no-scripts` to the combined plan in `provision` as `apply_kit` does, so the preflight checks only what will be written. Done when: a test with `scripts` as a file (an unsafe parent for every `scripts/` path) and `--no-scripts` installs, and without `--no-scripts` refuses with the target unchanged. **Corrected 2026-11-11 (validation):** added; the preflight over the combined plan must use the same filter.
- [x] Commit: `forge: init plans every kit before it writes one`

**Test checkpoint:** `python -m unittest discover -s tests -p test_forge.py` ends `OK`; moving the plan loop after the first `apply_kit` makes the empty-folder test fail.

> **Verified:** 2026-11-11 | §8 | 4267907b6fdddb30b260c000d7032f3123f6288a
> **Review:** `docs/reviews/d01-t01-s8.json`

## 9. Backup of the entry docs `init --force` replaces

> **Started:** 2026-11-11T20:39:51Z

`init --force` writes the kit's `AGENTS.md`, `GEMINI.md`, `CLAUDE.md` and `CODEX.md` over the project's (`forge.py:657`) and keeps no copy (roadmap finding 15). The replaced file is kept beside the new one.

**Corrected 2026-11-11 (validation):** `provision` moved (§2 to §8); the docs are now written through `_write_recorded`, which records each with the kit's digest. With the `todo` kit, `init` appends the TODO pointer to `AGENTS.md`, so a doc "equal to the kit's bytes" would never match on a second `--force` and the run would refuse on its own backup: a doc is skipped when it already holds what `init` would leave (the kit's bytes, plus the pointer for `AGENTS.md` when `todo` is chosen).

**Phase:** 1
**Needs:** none
**Surface:** no

**Build order:**

1. Keep each replaced doc as `<name>.replaced` in `provision`. Done when: the project's old bytes are readable after `--force`.
2. Cover the repeat and the no-op. Done when: the checkpoint passes.

- [x] Write the project's existing entry doc to `<name>.replaced` with `atomic_write` in `provision` of `forge.py` before the kit's version replaces it, and list the backups under `backups` in the result. Done when: a test with all four docs edited (and one run with `--agent claude`, which replaces only `AGENTS.md` and `CLAUDE.md`) finds each `<name>.replaced` holding the old bytes and each doc the kit's; a test whose backup write fails finds exit 1, the doc and its record entry unchanged; and a test whose replacement fails after the backup finds the old bytes in `<name>.replaced` and the doc still the old one. Cheaper substitute: printing the old content must fail, because the output is not kept. **Corrected 2026-11-11 (plan review):** writing the backup after the replacement passed the old-bytes test, and only `AGENTS.md` was covered.
- [x] Skip a doc in `provision` that already holds what `init` would leave (the kit's bytes, plus the TODO pointer for `AGENTS.md` when `todo` is chosen): no rewrite, no backup, no record change. Done when: tests running `init --force` twice, with and without `--with-todo`, find one backup per replaced doc, not two, the second run's `backups` empty, exit 0, no write to any entry doc (an `atomic_write` spy) and the record byte for byte as before. **Corrected 2026-11-11 (plan review):** an identical rewrite passed. **Corrected 2026-11-11 (validation):** compared with the kit's bytes alone, which a pointed `AGENTS.md` never equals.
- [x] Refuse `init --force` in `provision` when a `<name>.replaced` already exists for a doc that would be replaced, naming it, before any file is written, including the kits' own files, and a `.replaced` that is a link or a folder refuses the same way. A `<name>.replaced` whose bytes equal the doc's current bytes is already that doc's backup (a run that backed it up and then failed to replace it), so it is kept and the run goes on. Done when: tests with the collision on `CODEX.md` (a later doc) as a file holding other bytes, a folder and a dangling link, on a target missing the kits' files, each find exit 2 and every file under the target unchanged; and a retry after a failed replacement succeeds with the backup intact. **Corrected 2026-11-11 (plan review):** the collision kinds were unstated, an obstruction on the first doc could not catch an early write, and a retry after a failed replacement was blocked by its own backup. **Corrected 2026-11-11 (validation):** "before any file is written" now includes the kits' files, since §8 plans them first. Cheaper substitute: overwriting the earlier backup must fail, because it is the only copy of the first version.
- [x] State the backup in the `--force` help text in `main` of `forge.py` and in `README.md`, with the reverse: restore a doc by copying its `.replaced` back, and before a later `--force` that would replace it again, move the earlier backup aside (rename or delete it). Done when: `python forge.py init --help` names `.replaced`, and a test follows the README's steps: restore, then move the backup aside and run `--force` again, finding a new backup and the moved one intact. **Corrected 2026-11-11 (plan review):** the refusal had no reverse or retry path.
- [x] Commit: `forge: init --force keeps the entry docs it replaces`

**Test checkpoint:** `python -m unittest discover -s tests -p test_forge.py` ends `OK`; removing the backup write makes the old-bytes test fail.

> **Verified:** 2026-11-11 | §9 | 19473ebcaacff18e3e8bc0dd8ce9d5595b411b20
> **Review:** `docs/reviews/d01-t01-s9.json`

## Verification

- A scratch project is installed with `init --kit todo`, one skill is edited, a kit template is changed in a scratch copy of the SDK, and `diff`, `update` and `diff` again show the edited skill untouched, the changed template taken and no file left `kit-newer`.
- `python forge.py drift` over a list holding that project exits 3 before the update and 0 after it.
- `python -m unittest discover -s tests` passes.
- `python scripts/todo-graph.py validate` and `python scripts/todo-graph.py plan --check` pass.
