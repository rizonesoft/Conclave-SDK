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
| 1 | §1 | `forge.py check-all` over every suite | -- | [ ] |
| 2 | §2 | Test inventory that refuses a test no suite runs | §1 | [ ] |
| 3 | §3 | Install assertions moved from bash to the Python suite | §1 | [ ] |
| 4 | §4 | Bash installers and their tests retired | §3 | [ ] |
| 5 | §5 | Skill copy generator with per-agent patches | -- | [ ] |
| 6 | §6 | Committed skill copies equal to the generator's output | §5 | [ ] |
| 7 | §7 | Pre-commit hook enabled at install and checked by doctor | -- | [ ] |

## 1. `forge.py check-all` over every suite

> **Started:** 2026-11-13T19:51:07Z

One command runs the Python suites, the kit script tests and the install tests, and is what runs before a commit (recommendation 9). A gate outside it does not exist.

**Phase:** 5
**Needs:** none
**Surface:** no

**Build order:**

1. Add the suite table and the `check-all` subcommand to `forge.py`. Done when: it runs each suite and reports each result.
2. Name it in `AGENTS.md` and `README.md` as the command to run before a commit. Done when: the checkpoint passes.

- [ ] Add `SUITES` to `forge.py`: a table of name, command and working folder for `tests/`, each `kits/*/templates/scripts/tests/` folder (automations, reviewer, unattended, wordpress), `kits/wordpress/hosts/pressable/templates/scripts/tests/`, `scripts/tests/`, `node scripts/verify-agent-tiers.mjs` and `python scripts/agy-subagent.py --check`. Done when: a test asserts every suite's script or folder exists and every unittest folder holds at least one `test_*.py`. Cheaper substitute: one shell line that chains the commands must fail review, because a failure in the middle hides the rest.
- [ ] Add `check_all(full=False, only=(), skip=())` to `forge.py`: run each selected suite as a subprocess with no shell and a per-suite timeout, draining its output as it runs into a bounded tail (the last 40 lines and at most 64 KB, however much it prints), and return each suite's result, exit, duration and the count from its `Ran N tests` line. A suite that cannot be started is a `FAIL` naming the launch error, one that runs past its timeout is a `FAIL` naming the timeout, and a unittest suite that ran no test is a `FAIL` (`no tests ran`); each is followed by the remaining suites. Done when: tests with stub suites cover a pass, a failure whose last lines are kept, a noisy suite printing more than the limit (the tail kept, memory bounded), a launch failure followed by a passing suite, an empty unittest folder, and a failure and a timeout each followed by a suite that still runs.
- [ ] End a suite's whole process tree on timeout and on any interruption of `check_all`, Ctrl+C included (`taskkill /T` on Windows, its process group on POSIX), before the interruption passes on. Done when: a test with a stub suite that starts a child and sleeps finds both gone after its timeout, and a test that interrupts the wait finds both gone and the interrupt raised. Cheaper substitute: `subprocess.run(timeout=...)` alone must fail the child-process assertion, because it leaves grandchildren running.
- [ ] Set `CONCLAVE_FULL_TESTS=1` for the suites in `check_all` when `full` is true, and remove it from their environment otherwise, whatever the caller's own environment holds. Done when: a stub unittest suite holding one test gated on the variable reports one test run and one skipped without `--full` and two run with it, also when the caller's environment already has the variable set.
- [ ] Add the `check-all` subcommand to `main` and `_run` in `forge.py` with `--full`, `--only <name>` and `--skip <name>` (each repeatable), printing one `PASS` or `FAIL` line per suite with its duration and test count, then the kept tail of each failure, and exiting 1 when any failed. An unknown suite name exits 2 naming it, before any suite starts. Done when: a test runs the command line against a table holding a failing stub first and a passing stub second and asserts both lines in that order and exit 1; `--only` twice runs exactly those two and leaves a sentinel suite's marker file unwritten; `--skip` leaves its suite out; and an unknown name exits 2 with no marker written.
- [ ] Run the suites through `check-all` in `.github/workflows/tests.yml`, keeping its three jobs and their names (`scripts/ci_status.py` and past stamps name them): the Windows job runs `python forge.py check-all --only tests`, the Linux full job `python forge.py check-all --full --only tests`, and the kit job `python forge.py check-all --full --skip tests`, which also runs the Pressable overlay's tests and the two agent checks its shell loop never reached. Done when: the workflow's run on the section's candidate is green on all three jobs and its log lists every suite of `SUITES` as `PASS`.
- [ ] Name `python forge.py check-all --full` in `AGENTS.md` (Test cadence) and `README.md` (`:247`) as the one command that runs every suite with the gated tests, for the cases the cadence already gives the full suite (reproducing a red, or when `ci_status.py` exits 3), with `--only <name>` for one suite; the cadence itself stays (targeted tests while building, CI for the suites). Done when: both documents name the command with `--full` and `AGENTS.md` still says CI is the section's suite evidence.
- [ ] Commit: `forge: check-all runs every suite`

**Corrected 2026-11-13 (validation):** the owner's test cadence (`AGENTS.md`, 2026-11-13, later than this section) keeps the local loop to targeted tests and makes CI the suite evidence, so `check-all` is the one command for the whole set when the whole set is wanted, not a step before every commit: the documents say so, and the checkpoint proves the command on stub suites and one real small suite, with the full run left to CI. The kit test folders are four today (automations, reviewer, unattended, wordpress) plus the Pressable overlay, `tests/` holds 17 files, and `scripts/agy-subagent.py --check` (D00 T02 §3) joins `verify-agent-tiers.mjs`. `docs/todo-workflow.md` names no pre-commit suite. `forge._probe` (D00 T02 §2) already ends a process tree on timeout and is the base for the runner.

**Corrected 2026-11-13 (plan review):** CI itself runs `check-all` in its three jobs and that green run is the section's evidence that the real table works end to end; the documented command is `check-all --full`, proven on a really gated test; a suite that cannot start is a named `FAIL` and the rest still run; output is drained into a bounded tail; the tree is ended on interruption as well as timeout; and the tests prove discovery, continuation, exact selection and the unknown-name refusal.

**Test checkpoint:** `python -m unittest tests.test_check_all` ends `OK` and `python forge.py check-all --only agent-tiers --only agy-subagents` prints `PASS` for both and exits 0; a stub suite that exits 1 makes the command print `FAIL` for it and exit 1.

## 2. Test inventory that refuses a test no suite runs

A new test file that no suite picks up is a gate nobody runs. `check-all` compares the test files in the repository with what its suites cover and fails on one that is unowned.

**Phase:** 5
**Needs:** none
**Surface:** no

**Build order:**

1. Add `unowned_tests()` to `forge.py` and run it first in `check_all`. Done when: a stray test file fails the run by name.
2. Decide every `global/` and `plugins/` suite. Done when: each is run or excluded with a reason.

- [ ] Add `unowned_tests()` to `forge.py`: list tracked files named `test_*.py`, `*_test.py`, `*.test.mjs` and `test-*.sh` with `git ls-files`, and return those under no suite folder in `SUITES` and no entry in `EXCLUDED_TESTS`. Done when: a test adds `tests/extra/test_stray.py` to a scratch copy and finds it returned. Cheaper substitute: a hard-coded count of test files must fail, because it passes when one file replaces another.
- [ ] Add the `global/claude/hooks/`, `global/codex/hooks/` and `global/tests/` suites to `SUITES` in `forge.py`, after running each once and recording its command in the table. Done when: `python forge.py check-all --only global-claude-hooks` passes, or the suite's failure is filed in `todo/findings.md` with `file:line` and the suite still listed.
- [ ] Run each of the ten `plugins/*/*/tests/` suites and the two `global/*/skills/process-ticktick-task/scripts/` test files once with the network unplugged from the process (no credentials in the environment), then list each in `SUITES` when it passes offline or in `EXCLUDED_TESTS` in `forge.py` with its reason (needs an account, needs a live service). Done when: `unowned_tests()` returns nothing for the repository and every exclusion carries a reason string. Cheaper substitute: excluding the whole `plugins/` folder by prefix must fail review, because a new offline test there would never run.
- [ ] Fail `check_all` in `forge.py` before running anything when `unowned_tests()` is not empty, naming each file. Done when: a test asserts exit 1 and the file's path in the output.
- [ ] Commit: `forge: check-all refuses a test file no suite runs`

**Test checkpoint:** `python forge.py check-all` exits 0; adding an empty `tests/extra/test_stray.py` makes it exit 1 naming that file.

## 3. Install assertions moved from bash to the Python suite

The six `test-install.sh` files check a fresh install of each kit. They run in no suite. Their assertions move into `tests/` against `forge.py kit`, so they run on Windows and WSL alike.

**Phase:** 5
**Needs:** none
**Surface:** no

**Build order:**

1. List every assertion in the six `kits/*/scripts/test-install.sh` files. Done when: each maps to an existing or a new Python test.
2. Add `tests/test_kit_install.py`. Done when: the checkpoint passes.

- [ ] Write the assertion map as a table in the docstring of `tests/test_kit_install.py`: one row per assertion of each `kits/<kit>/scripts/test-install.sh` (file present, file mode, doctor output, `--help` exit, refusal), naming the Python test that covers it. Done when: every `grep -c "assert\|test \|\[ "` line of the six scripts has a row. Cheaper substitute: porting only the file-present checks must fail review against the map.
- [ ] Add the fresh-install tests to `tests/test_kit_install.py`: for each of the six kits, `forge.apply_kit` on an empty fixture (with an `artisan` file for Laravel and a `wp-load.php` for WordPress), then the mapped assertions. Done when: the tests pass and each fails when its template file is removed from a scratch copy of the kit.
- [ ] Port the doctor assertions of `kits/laravel/scripts/test-install.sh` and `kits/wordpress/scripts/test-install.sh` to `forge.doctor_repo` in `tests/test_kit_install.py`. Done when: the tests assert the same check names and statuses the scripts did.
- [ ] Add `tests/test_kit_install.py` to the suites `check-all` runs through the `tests/` folder and confirm it in the output. Done when: `python forge.py check-all --only tests` lists its test count as higher than before by the number of new tests.
- [ ] Commit: `tests: kit install assertions in the Python suite`

**Test checkpoint:** `python -m unittest discover -s tests -p test_kit_install.py` ends `OK`; removing `review_pin.py` from a scratch copy of the reviewer kit makes its install test fail.

## 4. Bash installers and their tests retired

With the assertions ported and `forge.py` writing the install record, the bash installers are a second installer that cannot write the record (roadmap finding 13, recommendation 8). They are removed. Reversing this costs restoring twelve files from git history.

**Phase:** 5
**Needs:** none
**Surface:** no

**Build order:**

1. Delete the installers and their tests. Done when: no `install.sh` or `test-install.sh` remains under `kits/*/scripts/`.
2. Update every document that names them. Done when: the checkpoint passes.

- [ ] Delete `kits/automations/scripts/install.sh`, `kits/base/scripts/install.sh`, `kits/laravel/scripts/install.sh`, `kits/reviewer/scripts/install.sh`, `kits/todo/scripts/install.sh` and `kits/wordpress/scripts/install.sh` with `git rm`. Done when: `git ls-files "kits/*/scripts/install.sh"` prints nothing. Cheaper substitute: leaving them with a deprecation comment must fail, because they would still install without a record.
- [ ] Delete the six `kits/*/scripts/test-install.sh` files with `git rm`. Done when: `git ls-files "kits/*/scripts/test-install.sh"` prints nothing and `python forge.py check-all` still passes.
- [ ] Check `kits/laravel/scripts/doctor.sh` and `kits/wordpress/scripts/doctor.sh` against `forge.doctor_repo`: where every check a script makes is also made by `forge.py doctor`, delete the script; where one is not, add the check to `forge.py` with a test first. Done when: each script is gone or `todo/findings.md` names the check that keeps it, with `file:line`.
- [ ] Rewrite the install and test sections of `kits/README.md` (lines 19 to 23, 45 to 46 and 64 to 68) and of each `kits/<kit>/README.md` to use `python forge.py kit` and `python forge.py check-all`. Done when: `grep -rn "install.sh" kits/*.md kits/*/README.md` shows only the automations kit's own `.conclave/automations/install.sh`, which is a scheduler installer and stays.
- [ ] Rewrite the sentences in stamped TODO history that name the installers only where a live document depends on them: none of `todo/00-reviewer/TODO-01-three-pass-review.md` is edited, because its checklist is the contract its stamps cover. Done when: `git diff --stat` for this section shows no change under `todo/00-reviewer/`.
- [ ] Commit: `kits: forge.py is the only installer`

**Test checkpoint:** `python forge.py check-all` exits 0 and `git ls-files "kits/*/scripts/*.sh"` prints nothing; restoring one `test-install.sh` makes `check-all` fail as an unowned test.

## 5. Skill copy generator with per-agent patches

The Antigravity and Codex copies of a skill are the Claude copy with a few declared differences (the agent's name, its `--writer` value, a block only one agent has). A generator builds them from the Claude file plus a patch file per agent, and refuses a patch that no longer applies (recommendation 8).

**Phase:** 5
**Needs:** none
**Surface:** no

**Build order:**

1. Add `skill_copies` and the `skill-copies` subcommand to `forge.py`. Done when: a fixture kit's two copies are generated from its Claude file and patches.
2. Cover the refusals. Done when: the checkpoint passes.

- [ ] Define the patch file in `forge.py`: `kits/<kit>/skill-patches/<agent>/<skill path>.json`, holding `{"schema_version": 1, "replace": [{"find": "<exact text>", "with": "<exact text>"}]}`, where `<agent>` is `agents` or `codex` and `<skill path>` is the file's path under `templates/.claude/skills/`. Done when: a test loads a patch and refuses an unknown key, a non-string `find` and an empty `find`, each naming the patch file.
- [ ] Add `generate_copy(source_text, patch)` to `forge.py`: apply each replacement in order, refusing one whose `find` occurs zero times or more than once, naming the patch file and the text. Done when: tests cover one replacement, a removed block (an empty `with`), a `find` that is missing and a `find` that occurs twice. Cheaper substitute: `str.replace` with no count check must fail the twice test, because a patch that silently hits two places is a wrong copy.
- [ ] Add `skill_copies(check=False)` to `forge.py`: for every file under each kit's `templates/.claude/skills/` (and each WordPress host overlay), produce the `.agents` and `.codex` file from the source and its patch, a file with no patch being copied unchanged. With `check` it writes nothing and returns the paths whose committed bytes differ. Done when: a test on a fixture kit generates both copies and `check` returns nothing afterwards.
- [ ] Leave hand-kept files alone in `skill_copies`: the `agents/openai.yaml` files that exist only under `.codex/` are never generated, deleted or reported. Done when: a test finds a fixture's `openai.yaml` untouched and not listed.
- [ ] Report a stray copy in `skill_copies`: a file under `.agents/skills/` or `.codex/skills/` (other than `agents/openai.yaml`) with no Claude source is listed and fails `--check`. Done when: a test adds one and finds it named.
- [ ] Add the `skill-copies` subcommand to `main` and `_run` in `forge.py` with `--check`, writing through `atomic_write` and exiting 1 when `--check` finds a difference. Done when: a test runs the command line on the fixture and asserts both exits.
- [ ] Commit: `forge: skill-copies generates the Antigravity and Codex skill files`

**Test checkpoint:** `python -m unittest discover -s tests -p test_forge.py` ends `OK`; removing the count check from `generate_copy` makes the twice test fail.

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
- [ ] Commit: `forge: the todo kit's pre-commit hook is enabled at install and checked by doctor`

**Test checkpoint:** `python -m unittest tests.test_forge` ends `OK`; leaving the install-time setting out makes the fresh-install doctor test fail.

## Verification

- `python forge.py check-all --full` passes on Windows and in WSL, and its output lists every suite named in `SUITES`.
- A fresh `python forge.py kit <scratch> reviewer` followed by the ported install tests passes with no bash installer in the repository.
- `python forge.py skill-copies --check` exits 0.
- `python scripts/todo-graph.py validate` and `python scripts/todo-graph.py plan --check` pass.
