---
schema_version: 1
id: gates-and-skill-source
domain: 01-forge
status: active
title: "TODO-02 -- One gate and one skill source"
---

# TODO-02 -- One gate and one skill source

> **Goal:** One command runs every test the repository holds, `forge.py` is the only installer, and the Antigravity and Codex copies of each skill are generated from the Claude copy plus a small declared patch, so no gate goes unrun and no skill copy drifts by hand.

> **Current state:** Measured 2026-11-11. The quick suite `python -m unittest discover -s tests` runs the nine files in `tests/` and, from inside them, the automations and WordPress kit tests; the reviewer kit's four test files run only with `CONCLAVE_FULL_TESTS=1` (`tests/test_forge.py:529`). The six `kits/*/scripts/test-install.sh` files (61 to 127 lines) are in no suite, which is how a red reviewer install test went unseen (roadmap findings 16 and 17). Test files under `global/` (eight) and `plugins/` (35) are run by nothing in this repository. The six `kits/*/scripts/install.sh` files (103 to 191 lines) repeat what `forge.py kit` does. Each kit keeps three copies of every skill under `templates/.claude/`, `templates/.agents/` and `templates/.codex/`: of 18 skill files, 9 differ between the Claude and Antigravity copies (80 changed lines) and 9 between the Claude and Codex copies (78 changed lines), and 15 `agents/openai.yaml` files exist only under `.codex/`. No generator exists.

## Inputs

- `docs/plans/2026-11-11-sdk-audit-and-roadmap.md`: findings 12, 13, 16 and 17, and recommendations 8 and 9.
- `tests/test_forge.py`: the suite that already runs kit tests from inside it (`tests/test_forge.py:444`, `:530`, `:582`).
- `kits/*/scripts/install.sh` and `kits/*/scripts/test-install.sh`: the assertions §3 ports and the files §4 retires.
- `kits/*/templates/.claude/skills/`, `.agents/skills/` and `.codex/skills/`: the copies §5 and §6 bring under one source.
- -> XREF: D01 T01 §2 -- the install record is written only by `forge.py`, which is why the bash installers are retired here and not taught to write it

## Outcome

- `python forge.py check-all` runs every suite and exits non-zero when any fails, and a test file no suite runs makes it fail.
- No `install.sh` or `test-install.sh` remains under `kits/`, and every assertion they made is in the Python suite.
- `python forge.py skill-copies --check` exits 0 only when the committed `.agents` and `.codex` skill files equal what the generator produces from the `.claude` files and the patches.

**Adjacency:** all=not-applicable (developer tooling: a test runner, an installer cleanup and a file generator, with no records a user lists, exports, is notified of or reverses)

**Adjacency rationale:** The settings this work adds are the suite list in `forge.py` and the per-agent patch files, each consumed by one command and proven by a test that fails when the list or a patch is wrong.

## Implementation Order

| Order | Section | Deliverable | Depends On | Status |
| ----- | ------- | ----------- | ---------- | ------ |
| 1 | §1 | `forge.py check-all` over every suite | -- | [x] |
| 2 | §2 | Test inventory that refuses a test no suite runs | §1 | [x] |
| 3 | §3 | Install assertions moved from bash to the Python suite | §1 | [x] |
| 4 | §4 | Bash installers and their tests retired | §3 | [x] |
| 5 | §5 | Skill copy generator with per-agent patches | -- | [ ] |
| 6 | §6 | Committed skill copies equal to the generator's output | §5 | [ ] |
| 7 | §7 | Pre-commit hook enabled at install and checked by doctor | -- | [ ] |

## 1. `forge.py check-all` over every suite

> **Started:** 2026-11-14T06:27:30Z

One command runs the Python suites, the kit script tests and the install tests, and is what runs before a commit (recommendation 9). A gate outside it does not exist.

**Phase:** 5
**Needs:** none
**Surface:** no

**Build order:**

1. Add the suite table and the `check-all` subcommand to `forge.py`. Done when: it runs each suite and reports each result.
2. Name it in `AGENTS.md` and `README.md` as the command to run before a commit. Done when: the checkpoint passes.

- [x] Add `SUITES` to `forge.py`: a table of name, command and working folder for `tests/`, each `kits/*/templates/scripts/tests/` folder (automations, reviewer, unattended, wordpress), `kits/wordpress/hosts/pressable/templates/scripts/tests/`, `scripts/tests/`, `node scripts/verify-agent-tiers.mjs`. Done when: a test asserts every suite's script or folder exists and every unittest folder holds at least one `test_*.py`. Cheaper substitute: one shell line that chains the commands must fail review, because a failure in the middle hides the rest.
- [x] Add `check_all(full=False, only=(), skip=())` to `forge.py`: run each selected suite as a subprocess with no shell and a per-suite timeout, draining its output as it runs into a bounded tail (the last 40 lines and at most 64 KB, however much it prints), and return each suite's result, exit, duration and the count from its `Ran N tests` line. A suite that cannot be started is a `FAIL` naming the launch error, one that runs past its timeout is a `FAIL` naming the timeout, and a unittest suite that ran no test is a `FAIL` (`no tests ran`); each is followed by the remaining suites. Done when: tests with stub suites cover a pass, a failure whose last lines are kept, a noisy suite printing more than the limit (the tail kept, memory bounded including a 16 MB stream without newlines whose peak traced memory stays below 2 MB), a launch failure followed by a passing suite, an empty unittest folder, and a failure and a timeout each followed by a suite that still runs.
- [x] End a suite's whole process tree on timeout, on normal suite exit and on any interruption of `check_all`, Ctrl+C included (a Win32 job object on Windows, its session/process group on POSIX), before the interruption passes on. Done when: a test with a stub suite that starts a child and sleeps finds both gone after its timeout, a test with a child that outlives an exiting suite finds both gone on Windows and POSIX, and a test that interrupts the wait finds both gone and the interrupt raised. Cheaper substitute: `subprocess.run(timeout=...)` alone must fail the child-process assertion, because it leaves grandchildren running.
- [x] Set `CONCLAVE_FULL_TESTS=1` for the suites in `check_all` when `full` is true, and remove it from their environment otherwise, whatever the caller's own environment holds. Done when: a stub unittest suite holding one plain test and one gated on the variable reports two discovered tests in both modes, skips the gated test (`skipped=1` and no marker file) without `--full` (also when the caller's environment already has the variable set) and runs both (`full-ran` written, no skipped count) with `--full`.
- [x] Add the `check-all` subcommand to `main` and `_run` in `forge.py` with `--full`, `--only <name>` and `--skip <name>` (each repeatable), printing one `PASS` or `FAIL` line per suite with its duration and test count, then the kept tail of each failure, and exiting 1 when any failed. An unknown suite name exits 2 naming it, before any suite starts. Done when: a test runs the command line against a table holding a failing stub first and a passing stub second and asserts both lines in that order and exit 1; `--only` twice runs exactly those two and leaves a sentinel suite's marker file unwritten; `--skip` leaves its suite out; and an unknown name exits 2 with no marker written.
- [x] Run the suites through `check-all` in `.github/workflows/tests.yml`, keeping its three jobs and their names (`scripts/ci_status.py` and past stamps name them): the Windows job runs `python forge.py check-all --only tests`, the Linux full job `python forge.py check-all --full --only tests`, and the kit job `python forge.py check-all --full --skip tests`, which also runs the Pressable overlay's tests and the agent check its shell loop never reached. Done when: the workflow's run on the section's candidate is green on all three jobs and its log lists every suite of `SUITES` as `PASS`.
- [x] Name `python forge.py check-all --full` in `AGENTS.md` (Test cadence) and `README.md` (`:247`) as the one command that runs every suite with the gated tests, for the cases the cadence already gives the full suite (reproducing a red, or when `ci_status.py` exits 3), with `--only <name>` for one suite; the cadence itself stays (targeted tests while building, CI for the suites). Done when: both documents name the command with `--full` and `AGENTS.md` still says CI is the section's suite evidence.
- [x] Commit: `forge: check-all runs every suite`

**Corrected 2026-11-13 (validation):** the owner's test cadence (`AGENTS.md`, 2026-11-13, later than this section) keeps the local loop to targeted tests and makes CI the suite evidence, so `check-all` is the one command for the whole set when the whole set is wanted, not a step before every commit: the documents say so, and the checkpoint proves the command on stub suites and one real small suite, with the full run left to CI. The kit test folders are four today (automations, reviewer, unattended, wordpress) plus the Pressable overlay, `tests/` holds 17 files, and `scripts/agy-subagent.py --check` (D00 T02 §3) joins `verify-agent-tiers.mjs`. `docs/todo-workflow.md` names no pre-commit suite. `forge._probe` (D00 T02 §2) already ends a process tree on timeout and is the base for the runner.

**Corrected 2026-11-13 (plan review):** CI itself runs `check-all` in its three jobs and that green run is the section's evidence that the real table works end to end; the documented command is `check-all --full`, proven on a really gated test; a suite that cannot start is a named `FAIL` and the rest still run; output is drained into a bounded tail; the tree is ended on interruption as well as timeout; and the tests prove discovery, continuation, exact selection and the unknown-name refusal.

**Corrected 2026-11-13 (round 1):** the six `kits/*/scripts/test-install.sh` install tests, which the opening line of this section names and its table left out, are suites too (`install-<kit>`, run with bash on POSIX and shown as `SKIP` on Windows) until §3 moves their assertions into the Python suite and §4 retires them.

**Corrected 2026-11-14 (D00 T02 §3):** D00 T02 §3 retired `scripts/agy-subagent.py` and the `agy-subagents` suite when the base kit adopted native Antigravity `Orchestrator (Carbon)`, leaving `agent-tiers` (`node scripts/verify-agent-tiers.mjs`) as the subagent check suite.

**Corrected 2026-11-14 (re-plan after D00 T02 §3):** because D00 T02 §3 (2709112) changed lines 60, 65 and 77 after the 2026-11-13 completion review (f06cb17a), the pre-D00-T02-s3 findings are preserved in docs/reviews/01-forge/D01-T02-s1-before-d00-t02-s3.md and the three-pass review cycle restarts on this post-D00-T02-s3 contract.

**Corrected 2026-11-14 (plan review 2):** normal suite teardown now ends surviving descendants through a Win32 job object on Windows and session kill on POSIX (`test_a_child_that_outlives_its_suite_does_not_hold_the_run` asserts both PIDs gone), streaming tail storage is proven via peak traced memory (< 2 MB) over a 16 MB output stream without newlines, and the gated-test check reflects unittest's `Ran 2 tests` count in both modes alongside explicit skip/execution assertions.

**Test checkpoint:** `python -m unittest tests.test_check_all` ends `OK` and `python forge.py check-all --only agent-tiers` prints `PASS` and exits 0; a stub suite that exits 1 makes the command print `FAIL` for it and exit 1.

> **Verified:** 2026-11-14 | §1 | 6e1571e440cfd3cf68572ab3c5a0574800897e7a
> **Review:** `docs/reviews/d01-t02-s1.json`

## 2. Test inventory that refuses a test no suite runs

> **Started:** 2026-11-14T07:56:00Z

A new test file that no suite picks up is a gate nobody runs. `check-all` compares the test files in the repository with what its suites cover and fails on one that is unowned.

**Phase:** 5
**Needs:** none
**Surface:** no

**Build order:**

1. Add `unowned_tests()` to `forge.py` and run it first in `check_all`. Done when: a stray test file fails the run by name.
2. Decide every `global/` and `plugins/` suite. Done when: each is run or excluded with a reason.

- [x] Add `unowned_tests()` to `forge.py`: list tracked files named `test_*.py`, `*_test.py`, `*.test.mjs` and `test-*.sh` with `git ls-files`, and return those under no suite folder in `SUITES` and no entry in `EXCLUDED_TESTS`. Done when: a test adds `tests/extra/test_stray.py` to a scratch copy and finds it returned. Cheaper substitute: a hard-coded count of test files must fail, because it passes when one file replaces another.
- [x] Add the `global/claude/hooks/`, `global/codex/hooks/` and `global/tests/` suites to `SUITES` in `forge.py`, after running each once and recording its command in the table. Done when: `python forge.py check-all --only global-claude-hooks` passes, or the suite's failure is filed in `todo/findings.md` with `file:line` and the suite still listed.
- [x] Run each of the ten `plugins/*/*/tests/` suites and the two `global/*/skills/process-ticktick-task/scripts/` test files once with the network unplugged from the process (no credentials in the environment), then list each in `SUITES` when it passes offline or in `EXCLUDED_TESTS` in `forge.py` with its reason (needs an account, needs a live service). Done when: `unowned_tests()` returns nothing for the repository and every exclusion carries a reason string. Cheaper substitute: excluding the whole `plugins/` folder by prefix must fail review, because a new offline test there would never run.
- [x] Fail `check_all` in `forge.py` before running anything when `unowned_tests()` is not empty, naming each file. Done when: a test asserts exit 1 and the file's path in the output.
- [x] Commit: `forge: check-all refuses a test file no suite runs`

**Corrected 2026-11-14 (validation):** repository test discovery matches `test_*.py`, `*_test.py`, `*.test.mjs`, `*.test.js` (31 of the 35 files under `plugins/`) and `test-*.sh` via `git ls-files --cached --others --exclude-standard` so both tracked and untracked stray files are caught, checking true suite execution ownership (`unittest` owns `test_*.py` directly in `suite["path"]` or inside importable subpackages where every intermediate folder contains `__init__.py`; `command` owns test files explicitly named in `suite["argv"]`) rather than bare folder prefixes. All 5 `global/` suites (`global/claude/hooks`, `global/codex/hooks`, `global/tests`, `global/claude/skills/process-ticktick-task/scripts`, `global/codex/skills/process-ticktick-task/scripts`) and 6 offline `plugin-*` Node suites across 15 files (passed via explicit file paths in `node --test <files...>`) pass offline on Windows and WSL Linux and join `SUITES` (25 suites total); `plugins/codex/cloud-access` has no `tests/` folder (9 test directories across 10 plugin directories), and the remaining 20 `plugins/*/*/tests/*.test.js` files fail offline strictly with `ERR_MODULE_NOT_FOUND` for uninstalled npm packages (`@modelcontextprotocol/sdk`, `parse5`, `@azure/msal-node`, `zod`, `ajv`, `ssh2`, `ipaddr.js`) not checked into this zero-dependency repository, so each is listed individually in `EXCLUDED_TESTS` with its exact package reason and `check_all` also refuses stale or already-owned exclusions or empty reasons. Note: CI's three jobs remain as decided in §1 (`quick-windows`, `full-linux`, `kits-linux` with `--skip tests` running all non-`tests` suites including `global-*` and `plugin-*`), while `python forge.py check-all` on Windows prints `SKIP` for the 6 POSIX-only `install-*` bash suites and exits 0.

**Test checkpoint:** `python forge.py check-all` exits 0; adding an empty `tests/extra/test_stray.py` makes it exit 1 naming that file.

> **Verified:** 2026-11-14 | §2 | 82c7a1172e9a4566faa53263f7ed22a84a50cb81
> **Review:** `docs/reviews/d01-t02-s2.json`

## 3. Install assertions moved from bash to the Python suite

> **Started:** 2026-11-14T09:21:04Z

The six `test-install.sh` files check a fresh install of each kit through the bash installers, and run only on POSIX. Their assertions move into `tests/` against `forge.py kit`, so they run on Windows and WSL alike.

**Phase:** 5
**Needs:** none
**Surface:** no

**Build order:**

1. List every assertion in the six `kits/*/scripts/test-install.sh` files. Done when: each maps to an existing or a new Python test.
2. Add `tests/test_kit_install.py`. Done when: the checkpoint passes.

- [x] Write the assertion map as a table in the docstring of `tests/test_kit_install.py`: every line of each `kits/<kit>/scripts/test-install.sh` in exactly one row, the row stating what its lines require and the outcome they expect (file present, file mode, tool run and its exit, doctor output, refusal; a loop written out as its cases) and naming the Python test that requires the same, or `none` for lines that assert nothing. Done when: `AssertionMapTests` in the file reads each script while it exists and fails on a line in no row or in two, on a `none` row holding a line that can fail the script (a `[ ]` test, a `grep`, an `exit 1`, a `sys.exit`, an `assert`, a run of the installer, the doctor or `python3`), and on a row naming a test the file does not define; and its own test proves the check catches an appended assertion and one filed under `none`. Cheaper substitute: porting only the file-present checks must fail review against the map.
- [x] Add the fresh-install tests to `tests/test_kit_install.py`: for each of the six kits, `forge.apply_kit` on a fixture holding what the script's fixture held (an `artisan` file for Laravel, a `wp-load.php` for WordPress, the project's own file the kit must keep), then the mapped file, mode, content and installed-tool assertions, each installed tool run with `sys.executable -B`, no shell and a timeout. Done when: the tests pass and `KitTemplateRemovalTests` in the same file removes one mapped template file per kit from a scratch copy of `kits/` (`forge.FORGE_ROOT` patched to it) and finds that kit's install test failing.
- [x] Port what every script asserts of the installer itself to `forge.apply_kit` and `forge.main` in `tests/test_kit_install.py`: a second install leaves every file's bytes unchanged, `--dry-run` writes nothing, `kit <target> <kit> --force` exits 2 and changes nothing, and a destination folder that is a link (a junction on Windows) refuses with the folder it leads to unchanged. Done when: each of the six kits has those four assertions and the link test fails when `_has_unsafe_parent` is patched to return `False`. Cheaper substitute: asserting only the raised error must fail, because the sentinel outside the project is what the script checked.
- [x] Port the doctor assertions of `kits/laravel/scripts/test-install.sh` and `kits/wordpress/scripts/test-install.sh` to `forge.doctor_repo` and `forge.main(["doctor", ...])` in `tests/test_kit_install.py`. Done when: the tests assert the same check names and statuses the scripts did (`artisan` and `lsp-diagnostics.py` reported; `wordpress-root` reported, `site-identity` `setup_required`, `--strict` exit 3, `no-ddev` `ok` for a WordPress.com site, `wordpress-root` `ok` ending `/site` for a first-level child).
- [x] Add `tests/test_kit_install.py` to the suites `check-all` runs through the `tests/` folder and confirm it in the output. Done when: `forge.unowned_tests()` returns nothing and `python forge.py check-all --only tests` lists a test count higher than the 715 of CI run `43576278972` by the number of new tests.
- [x] Commit: `tests: kit install assertions in the Python suite`

**Corrected 2026-11-14 (validation):** the opening said the scripts "run in no suite"; since §1 (round 1) they run as the six POSIX-only `install-<kit>` suites of `forge.SUITES`, which stay until §4 retires the scripts with the installers. The scripts assert more than a fresh install, so the port is spelled out: the project's own file kept, a second install changing nothing, `--dry-run` writing nothing, the removed `--force` refused (`forge.py kit` has no such flag, so argparse exits 2) and a linked destination folder refused with the outside folder untouched, plus the tools run from the installed copy (`run.py --check`, `review_pin.py --check`, `--caps` and `--lenses`, `review-dispatch.py --check-pin`, the `--help` exits). The map's `Done when:` was a shell `grep -c` nobody would rerun and is now a test over the same pattern (100 lines measured today), which reads the scripts only while they exist so §4 can delete them. The template-removal proof was a manual step and is now `KitTemplateRemovalTests`. The todo kit's install asks Codex's app-server to approve its Stop hook, so the file sets `CODEX_HOOK_TRUST_SERVER` to `tests/fixtures/codex_app_server_stub.py` as `tests/test_forge.py:22` does. A seventh kit, `unattended`, has no bash installer and keeps its install tests in `tests/test_forge.py` (`UnattendedKitTests`). `kits/laravel/scripts/doctor.sh` also reports a `laravel/boost` composer check `forge.doctor_repo` lacks; no script test asserts it, and §4 decides it when it checks the two `doctor.sh` files. Decision (default, cheap to reverse: one constant): the WordPress bytecode assertion plants its stray `.pyc` in the scratch copy of `kits/`, never in the checkout as the script did.

**Corrected 2026-11-14 (plan review):** two gaps, both built. The port is of what the scripts mean today, not of their text: `kits/reviewer/scripts/test-install.sh` forbade a `codex` route on a line starting `!`, which `set -e` never fails on, while the reviewer pin has routed Codex to Carbon since D00 T02 §1. The Python test asserts `codex = ["carbon"]`, no `gemini` route and no Claude reviewer, and the script, a CI suite until §4, now asserts the same with an `if` that can fail. The map's check matched `assert|test |\[ ` and so missed assertions written as `grep`, a command's exit, `if ...; then exit 1` and `sys.exit`: the map now holds every line of every script, and its test refuses any line that can fail a script in a row naming no test (before: "finds every line matching `assert|test |\[ ` (100 lines) named by its line number in a row").

**Test checkpoint:** `python -m unittest discover -s tests -p test_kit_install.py` ends `OK`; removing `review_pin.py` from a scratch copy of the reviewer kit makes its install test fail, which `KitTemplateRemovalTests` runs on every pass and which fails itself when the removal is skipped.

> **Verified:** 2026-11-14 | §3 | d3886551efa817bb8152bed35b6b829643f6adc2
> **Review:** `docs/reviews/d01-t02-s3.json`

## 4. Bash installers and their tests retired

> **Started:** 2026-11-14T21:36:07Z

With the assertions ported and `forge.py` writing the install record, the bash installers are a second installer that cannot write the record (roadmap finding 13, recommendation 8). They are removed. Reversing this costs restoring twelve files from git history.

**Phase:** 5
**Needs:** none
**Surface:** no

**Build order:**

1. Give `forge.py doctor` the two checks only `kits/laravel/scripts/doctor.sh` makes. Done when: their tests pass.
2. Delete the installers, their tests and the two doctor scripts, with the suites and tests that read them. Done when: no `.sh` file remains under `kits/*/scripts/`.
3. Update every live document that names them. Done when: the checkpoint passes.

- [x] Add the `laravel/boost` check to the Laravel branch of `forge.doctor_repo` in `forge.py`: `ok` when `vendor/composer/installed.json` under the app root lists the package `laravel/boost`, otherwise `setup_required` with the hint `composer require --dev laravel/boost (dependency approval)`. Done when: a new test in `tests/test_kit_install.py` fails before the change and passes after it for a listed package, a listed package in an app under `platform/`, a valid file that lists other packages only, an absent file, a file that is not JSON, a file whose read raises `PermissionError` and a project with no `artisan`; every case but the first two reports `setup_required` with the hint, and the report's other checks are still all present. Cheaper substitute: reading `composer.json` must fail the test, because a required package that was never installed is not present.
- [x] Make `python forge.py doctor <target>` refuse a target that is not a directory in `forge.main`: exit 2 with `doctor: not a directory: <target>` on stderr and no report on stdout, as both scripts did (`kits/laravel/scripts/doctor.sh:16`). Done when: a new test in `tests/test_kit_install.py` fails before the change and passes after it, for a missing path and for a file.
- [x] Delete `kits/laravel/scripts/doctor.sh` and `kits/wordpress/scripts/doctor.sh` with `git rm`. Done when: `git ls-files ":(glob)kits/*/scripts/doctor.sh"` prints nothing and the check names and statuses of `python forge.py doctor <target> laravel` cover every `report` line of the deleted Laravel script (`artisan`, `lsp-diagnostics.py`, `boost.json`, `laravel/boost`, `laravel-lsp`, `tailwindcss-language-server`, `intelephense`, `skill:.agents`, `skill:.claude`, `skill:.codex`), which one test asserts as a set.
- [x] Delete `kits/automations/scripts/install.sh`, `kits/base/scripts/install.sh`, `kits/laravel/scripts/install.sh`, `kits/reviewer/scripts/install.sh`, `kits/todo/scripts/install.sh` and `kits/wordpress/scripts/install.sh` with `git rm`. Done when: `git ls-files ":(glob)kits/*/scripts/install.sh"` prints nothing. Cheaper substitute: leaving them with a deprecation comment must fail, because they would still install without a record.
- [x] Delete the six `kits/*/scripts/test-install.sh` files with `git rm` and remove their six `install-<kit>` entries, with the comment above them, from `SUITES` in `forge.py`. Done when: `git ls-files ":(glob)kits/*/scripts/test-install.sh"` prints nothing and no suite in `forge.SUITES` has a path ending `.sh`; the `"os": "posix"` suite key and `forge._runs_here` stay, because a host limit is a suite property that `tests/test_check_all.py` proves with stub suites.
- [x] Replace `test_every_install_test_in_the_repository_is_a_suite` and `test_every_kit_shell_script_is_committed_executable` in `tests/test_check_all.py` with one test that no file matching `kits/<kit>/scripts/*.sh` is tracked. Done when: the test fails with one `test-install.sh` restored and staged, and `forge._inventory_problems` names that restored file as an unowned test in the same test. Cheaper substitute: deleting the two tests without a replacement must fail review, because nothing would then stop a bash installer coming back.
- [x] Remove the script-reading half of `AssertionMapTests` in `tests/test_kit_install.py` (`script_problems`, `ASSERTION_LINE` and the two tests that use them) and reword the module docstring: the map stays as the record of what was ported, naming the last commit that holds the scripts its line numbers refer to (the parent of this section's deleting commit). Done when: `test_the_map_has_rows_for_all_six_kits`, `test_every_row_names_a_test_this_file_defines` and `test_no_line_is_in_two_rows` still pass and no code in the file opens a path under `kits/<kit>/scripts/`.
- [x] Rewrite the install, layout and test passages of `kits/README.md` (the bash installer block at lines 18 to 25, the layout block and the doctor sentence at lines 45 to 55, the test blocks at lines 59 to 72) to use `python forge.py kit`, `python forge.py doctor` and `python forge.py check-all`. Done when: `git grep -n -E "install\.sh|doctor\.sh" -- kits/README.md` prints nothing.
- [x] Rewrite the install passages of `kits/automations/README.md` (line 41), `kits/base/README.md` (lines 18 to 22 and 34), `kits/laravel/README.md` (lines 30 to 32), `kits/reviewer/README.md` (line 129), `kits/todo/README.md` (line 56) and `kits/wordpress/README.md` (lines 46 to 47) the same way. Done when: `git grep -n -E "scripts/(install|test-install|doctor)\.sh" -- "kits/*/README.md"` prints nothing, which leaves the automations kit's own `.conclave/automations/install.sh`, a scheduler installer that stays.
- [x] Rewrite the sentences that name the scripts in the installed templates: `kits/base/templates/docs/agent-skills-and-rules-structure.md` (line 52), `kits/laravel/templates/docs/laravel-agent-tooling.md` (lines 44 to 46) and the three `kits/wordpress/templates/<agent>/skills/wordpress-connect/SKILL.md` copies (line 17), then run `python forge.py self-sync`. Done when: `git grep -n -E "scripts/(install|test-install|doctor)\.sh" -- kits docs/agent-skills-and-rules-structure.md .agents .claude .codex` prints nothing and `python -m unittest tests.test_forge -k self_sync` passes.
- [x] Rewrite the sentences in stamped TODO history that name the installers only where a live document depends on them: none of `todo/00-reviewer/TODO-01-three-pass-review.md` is edited, because its checklist is the contract its stamps cover. Done when: `git diff --stat` for this section shows no change under `todo/00-reviewer/`.
- [x] Commit: `kits: forge.py is the only installer`

**Corrected 2026-11-14 (validation):** seven drifted claims, each measured today. (1) The `Done when:` lines and the checkpoint used `git ls-files "kits/*/scripts/*.sh"`, whose `*` crosses folders and so also lists `kits/laravel/templates/scripts/hooks/laravel-lsp-pre-push.sh` and `kits/wordpress/templates/scripts/hooks/wordpress-phpcs-pre-push.sh`, two installed hooks that stay: every pattern is now a `:(glob)` pathspec. (2) Since §1 the six scripts are the `install-<kit>` suites of `forge.SUITES` and two tests in `tests/test_check_all.py` count them (6 install tests, 14 kit shell scripts), so deleting only the files turns `check-all` red: the suites go with the files and one test now refuses a shell script under `kits/<kit>/scripts/`. (3) `AssertionMapTests` reads each script "while it exists" (§3); with none left that half can never run, so it is removed and the map stays as a record. (4) The doctor item left the outcome open; it is decided here. `kits/wordpress/scripts/doctor.sh` only formats `forge.py doctor`'s own report, and `kits/laravel/scripts/doctor.sh` makes two checks `forge.py` lacks: the `laravel/boost` package (the note in §3) and the exit 2 for a target that is not a directory. Both are added to `forge.py` with tests first, then both scripts are deleted. Decision (default, cheap to reverse: one function): the package check reads `vendor/composer/installed.json`, the file `composer show` itself reads, so it needs no `composer` on `PATH`, starts no process and works on Windows; the script ran `composer show laravel/boost`. (5) The README lines moved: `kits/README.md` named "lines 19 to 23, 45 to 46 and 64 to 68" and "each `kits/<kit>/README.md`" without lines. (6) Five live files outside the READMEs name the scripts and were in no item: the base kit's structure document and its installed copy in `docs/`, the Laravel tooling document and the three `wordpress-connect` skill copies. (7) The opening says "twelve files"; fourteen are deleted (six installers, six tests, two doctor scripts). `docs/specs/2026-10-16-wordpress-kit-connect-design.md:32` names `install.sh` as the design of its date and is left as history, like the stamped TODO files. The file's Outcome line "No `install.sh` or `test-install.sh` remains under `kits/`" means the kit installers under `kits/<kit>/scripts/`: `kits/automations/templates/.conclave/automations/install.sh` installs systemd timers in a project and stays.

**Corrected 2026-11-14 (plan review):** two gaps in the `laravel/boost` item, both taken. Its test cases were "a listed package, an absent file, a file that is not JSON and a project with no `artisan`", which a check answering `ok` for any file that parses would pass, and which never proved the app root under `platform/` is the one read; and no case covered a file that cannot be read, where the script's failed `composer show` gave `setup_required` and the report went on.

**Test checkpoint:** `python forge.py check-all` exits 0 and `git ls-files ":(glob)kits/*/scripts/*.sh"` prints nothing; restoring one `test-install.sh` makes `check-all` fail as an unowned test, which the replacement test in `tests/test_check_all.py` proves on every run.

> **Verified:** 2026-11-15 | §4 | 4c6346f61acfb02f39bd2c2e4e342b3e0b33e697
> **Review:** `docs/reviews/d01-t02-s4.json`

## 5. Skill copy generator with per-agent patches

> **Started:** 2026-11-14T21:54:21Z

The Antigravity and Codex copies of a skill are the Claude copy with a few declared differences (the agent's name, its `--writer` value, a block only one agent has). A generator builds them from the Claude file plus a patch file per agent, and refuses a patch that no longer applies (recommendation 8).

**Phase:** 5
**Needs:** none
**Surface:** no

**Build order:**

1. Add `skill_copies` and the `skill-copies` subcommand to `forge.py`. Done when: a fixture kit's two copies are generated from its Claude file and patches.
2. Cover the refusals. Done when: the checkpoint passes.

- [x] Define the patch file in `forge.py`: `<overlay>/skill-patches/<agent>/<skill path>.json` beside the overlay's `templates/` folder (`kits/<kit>/` or `kits/wordpress/hosts/<host>/`), holding `{"schema_version": 1, "replace": [{"find": "<exact text>", "with": "<exact text>"}]}`, where `<agent>` is `agents` or `codex` and `<skill path>` is the file's path under `templates/.claude/skills/`. Done when: tests in `tests/test_skill_copies.py` load a patch and refuse a file that is not JSON, a wrong `schema_version`, an unknown key at either level, a `replace` that is not a list, a non-string `find` or `with` and an empty `find`, each naming the patch file.
- [x] Add `generate_copy(source_text, patch)` to `forge.py`: apply each replacement in order, refusing one whose `find` occurs zero times or more than once, naming the patch file and the text. Done when: tests in `tests/test_skill_copies.py` cover one replacement, a removed block (an empty `with`), two chained replacements where the second `find` exists only in the first's `with`, a `find` that is missing and a `find` that occurs twice. Cheaper substitute: `str.replace` with no count check must fail the twice test, because a patch that silently hits two places is a wrong copy.
- [x] Add `skill_copies(check=False)` to `forge.py`: for every file under each kit's `templates/.claude/skills/` (and each WordPress host overlay), produce the `.agents` and `.codex` file from the source and its patch, a file with no patch being copied unchanged, the text read and written as UTF-8 with its line endings kept. With `check` it writes nothing and returns the paths whose bytes on disk differ from the generated ones, a missing copy among them. Done when: a test on a fixture kit compares each generated file with expected bytes written out in the test, never with the generator's own output (an Antigravity and a Codex copy patched differently, an unpatched `SKILL.md`, a nested `references/` file, and a source with CRLF line endings and non-ASCII text whose copies keep both byte for byte); `check` returns nothing afterwards; and a deleted copy and a copy with one changed byte are each returned by `check` and restored by a run without it.
- [x] Make `skill_copies` all or nothing: every patch is loaded and every copy generated in memory before the first write, and `check` never writes. Done when: one test puts a valid skill before a skill whose patch has a `find` that is missing and finds every destination's bytes unchanged after the refusal, and another takes a digest of every file in the fixture before and after `check` over a changed, a missing and a stray copy and finds them equal, the missing file still absent.
- [x] Refuse a stale patch in `skill_copies`: a patch file whose Claude source does not exist, or a folder under `skill-patches/` that is not `agents` or `codex`, raises naming the path. Done when: a test covers each and finds no file written. Cheaper substitute: skipping a patch with no source must fail the test, because a renamed skill would silently lose its declared differences.
- [x] Leave hand-kept files alone in `skill_copies`: a `.codex/skills/<skill>/agents/openai.yaml` file is never generated, deleted or reported. Done when: a test finds a fixture's `openai.yaml` untouched and not listed.
- [x] Report a stray copy in `skill_copies`: a file under `.agents/skills/` or `.codex/skills/` with no Claude source (other than Codex's `<skill>/agents/openai.yaml`) is listed and fails `--check`, and a run without `check` leaves it in place and reports it, because deleting a file nobody declared is the owner's call. Done when: a test adds one under each agent, an `agents/openai.yaml` under `.agents/skills/` among them, and finds each named.
- [x] Add the `skill-copies` subcommand to `main` and `_run` in `forge.py` with `--check`, writing through `atomic_write` and exiting 1 when `--check` finds a difference. Done when: a test runs the command line on the fixture and asserts both exits.
- [ ] Commit: `forge: skill-copies generates the Antigravity and Codex skill files`

**Corrected 2026-11-14 (validation):** measured today, each agent holds 19 files under its kits' `skills/` folders (16 `SKILL.md`, two `references/` files and `todo-template.md`), all with LF line endings, and `.codex` holds 16 `agents/openai.yaml` files besides; 10 files differ between the Claude and Antigravity copies and 9 between the Claude and Codex copies (the file's Current state says 9 and 9 of 18, from 2026-11-11, before the unattended kit's skill). No WordPress host overlay holds a skill today, so the overlay walk is proven on a fixture. Four gaps in the items, all taken: the patch path did not say where a host overlay's patches live (beside its `templates/`, like a kit's); the loader's refusals named three faults and left a wrong `schema_version`, a non-list `replace` and a non-string `with` open; `check` did not say a missing copy counts as a difference; and nothing refused a patch whose source is gone. The tests go in a new `tests/test_skill_copies.py`, not `tests/test_forge.py` (4,000 lines whose run takes over ten minutes), so the checkpoint named `test_forge.py` and now names the new file, which the `tests` suite of `check-all` picks up.

**Corrected 2026-11-14 (plan review):** five gaps, all taken. The generation test compared the generator with its own checker (before: "generates both copies, `check` returns nothing afterwards"), so a generator that ignored the patches passed: it now compares with bytes the test writes out. Nothing proved `check` writes nothing, or that a refusal part way leaves earlier copies alone: `skill_copies` is all or nothing, with a test for each. Ordered replacements and kept line endings had no test that told them from independent replacements or normalised newlines. The `agents/openai.yaml` exception covered both agent trees and is Codex's only (before: "other than `agents/openai.yaml`"). Decision (default, cheap to reverse: one branch): a stray copy is reported and never deleted by the generator.

**Test checkpoint:** `python -m unittest tests.test_skill_copies` ends `OK`; removing the count check from `generate_copy` makes the twice test fail.

## 6. Committed skill copies equal to the generator's output

The generator means nothing until the committed copies are its output. The differences that exist today are written down as patches, any difference that is an accident is removed, and a test keeps the three in step.

**Phase:** 5
**Needs:** none
**Surface:** no

**Build order:**

1. Write a patch for each of the nine skill files whose copies differ. Done when: `python forge.py skill-copies --check` exits 0 with no committed copy changed by accident.
2. Add the check to the suite and `self-sync` the SDK's copies. Done when: the checkpoint passes.

- [ ] List every differing line between the Claude copy and each other copy of the nine skill files that differ (measured 2026-11-11: 80 changed lines for `.agents`, 78 for `.codex`) and sort each into intended (the agent's name, the `--writer` value, a tool only one agent has) or accidental (wording that drifted). Done when: the list is in the commit message body with a count per skill and the two counts sum to the measured totals or the difference is explained.
- [ ] Write the patch files under each `kits/<kit>/skill-patches/` for the intended differences. Done when: `python forge.py skill-copies --check` reports only the files holding accidental differences.
- [ ] Resolve each accidental difference by changing the Claude source or the copy, whichever holds the better text, then run `python forge.py skill-copies`. Done when: `python forge.py skill-copies --check` exits 0 and `git diff --stat` shows no skill copy changed beyond the listed accidental lines. Cheaper substitute: writing a patch for every differing line without reading it must fail review, because it freezes the drift in place.
- [ ] Add a test to `tests/test_forge.py` that `forge.skill_copies(check=True)` returns nothing for the repository. Done when: editing one line of a `.codex` skill copy makes it fail naming the file.
- [ ] Run `python forge.py self-sync` and state the rule in `AGENTS.md` (Strict agent isolation) and `kits/base/templates/docs/agent-skills-and-rules-structure.md`: edit the Claude copy or a patch, then run `skill-copies`. Done when: `python -m unittest discover -s tests` passes with the SDK's installed copies equal to the kits.
- [ ] Refuse an empty folder under `skill-patches/` that is not `agents` or `codex` in `_skill_copy_plan` of `forge.py`, which today sees only files and so accepts `skill-patches/gemini/` until a patch is put in it. Done when: a test in `tests/test_skill_copies.py` creates the empty folder, finds `forge.SkillCopyError` naming it and every file's digest unchanged, and fails with the folder check removed. Source: the completion review of §5 (`docs/reviews/01-forge/D01-T02-s5.md`, part 1 item 5, P3).
- [ ] Commit: `kits: skill copies are the generator's output`

**Test checkpoint:** `python forge.py skill-copies --check` exits 0 and `python -m unittest discover -s tests` ends `OK`; editing one `.agents` skill file by hand makes both fail.

## 7. Pre-commit hook enabled at install and checked by doctor

The todo kit's `scripts/hooks/pre-commit` refuses a commit that would turn the plan gates red, but only once `core.hooksPath` points at `scripts/hooks`, and nothing sets it or says it is unset. The SDK's own clone ran without it until 2026-11-13, when a commit whose tree `validate` refused went through (`7060da9`, repaired in the next commit).

**Phase:** 5
**Needs:** none
**Surface:** no

**Build order:**

1. Report the setting in `forge.py doctor` for the todo kit. Done when: an unset `core.hooksPath` reads `setup_required` naming the command.
2. Set it at install when nothing else owns the repository's hooks. Done when: the checkpoint passes.

- [ ] Add a todo kit check to `doctor` in `forge.py`: `core.hooksPath` equal to `scripts/hooks` is `ok`; unset, or another path, is `setup_required` naming `git config core.hooksPath scripts/hooks`. Done when: a test in `tests/test_forge.py` reads both states.
- [ ] Set `core.hooksPath` to `scripts/hooks` when `forge.py` installs the todo kit into a git repository whose `core.hooksPath` is unset and whose `.git/hooks` holds only samples, and leave it, saying why, otherwise. Done when: tests cover a fresh repository (set), one with a `.git/hooks/pre-commit` of its own (left and reported) and one with another `core.hooksPath` (left and reported).
- [ ] Keep the fresh-install doctor test all `ok` in `tests/test_forge.py`. Done when: its fresh install reports the hook check `ok`.
- [ ] Document the setting and the doctor check in `kits/todo/templates/todo/README.md` beside the hook, copy it over `todo/README.md` and run `python forge.py self-sync`. Done when: the two READMEs are identical.
- [ ] Remove the sentence "The bash installers write no record." from the install record paragraph of `kits/README.md` (line 20), which describes installers §4 deleted as if they still ran. Done when: `git grep -n -i "bash installer" -- kits/README.md` prints nothing. Source: the completion review of §4 (`docs/reviews/01-forge/D01-T02-s4.md`, part 1 item 6, P3).
- [ ] Commit: `forge: the todo kit's pre-commit hook is enabled at install and checked by doctor`

**Test checkpoint:** `python -m unittest tests.test_forge` ends `OK`; leaving the install-time setting out makes the fresh-install doctor test fail.

## Verification

- `python forge.py check-all --full` passes on Windows and in WSL, and its output lists every suite named in `SUITES`.
- A fresh `python forge.py kit <scratch> reviewer` followed by the ported install tests passes with no bash installer in the repository.
- `python forge.py skill-copies --check` exits 0.
- `python scripts/todo-graph.py validate` and `python scripts/todo-graph.py plan --check` pass.
