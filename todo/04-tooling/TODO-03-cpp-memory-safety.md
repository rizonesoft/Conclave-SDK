---
schema_version: 1
id: cpp-memory-safety
domain: 04-tooling
status: active
title: "TODO-03 -- Memory-safety checks in the C and C++ toolchain kit"
---

# TODO-03 -- Memory-safety checks in the C and C++ toolchain kit

> **Goal:** A C or C++ project that installs `toolchain-cpp` declares the memory-safety hardening it builds with, and one command says whether its compile commands and its built binaries really carry it, on Windows and Linux, so a project cannot ship an unhardened or sanitizer-instrumented binary without a check naming what is missing. The kit checks and documents; it never chooses a project's flags or edits its build.

> **Current state:** Measured 2026-11-16. `kits/toolchain-cpp/` pins tools, checks the compile database, wraps a compiler cache and seeds clangd, and says nothing about memory safety: `git grep -n -i -E "fsanitize|_LIBCPP_HARDENING|_MSVC_STL_HARDENING|guard:cf|mguard|stack-protector|AddressSanitizer" -- kits global` prints nothing. The owner reviewed every C++ repository on the machine that day and found the coverage uneven: Isotone has control-flow guard, shadow stack, `/analyze`, a sanitizer lane and fuzzing; CarbonCD and Crownroot had no memory-safety option at all; none switched on standard library hardening. Measured the same day on probe programs (an out-of-bounds `std::vector` read): MSVC 19.52 exits 0 plain and `0xC0000409` with `/D_MSVC_STL_HARDENING=1`; llvm-mingw clang 23.1.1 exits 0 plain and `0xC000001D` with `-D_LIBCPP_HARDENING_MODE=_LIBCPP_HARDENING_MODE_FAST`; g++ 15.2.0 exits 0 plain and 134 with `-D_GLIBCXX_ASSERTIONS`. On llvm-mingw `-mguard=cf` set the Control Flow Guard image flag and `-Wl,--cetcompat` was refused by lld while `-Wl,-Xlink=-cetcompat` set the shadow-stack flag. Each project then planned its own check script (Resolute-SDK `D00 T01 §10`, CarbonCD `D00 T01 §11`, Crownroot's build tooling section 10), which is the copy-per-project this kit exists to end. Two of them, Resolute-SDK and CarbonCD, already have this kit installed.

## Inputs

- `kits/toolchain-cpp/README.md` and `kits/toolchain-cpp/templates/`: the pin file, `scripts/toolchain-check.py` and `scripts/compdb-check.py`, whose shape (a pin file key, a read-only script, exit codes, `--json`, a doctor row) each section here follows.
- `forge.py` `doctor_repo`: where the kit's doctor rows are added.
- `AGENTS.md`: Python standard library only, so image headers are parsed by the script itself and never through `dumpbin`, `llvm-readobj` or `readelf`; and the Claude skill file is the source of the other two agents' copies.
- Decision recorded here (owner direction 2026-11-16): a shipped tool built with hardening needs a crash handler that says something useful, because hardening ends the process at once; the skill carries that rule, and the handler itself stays the project's.

## Outcome

- `python scripts/hardening-check.py` in a project reads the `hardening` key of `.conclave/toolchain-cpp.json` and prints one line per requirement: each definition or option on the compile commands of the project's own sources, and each image property of the binaries it names, `ok` or missing by name.
- `python forge.py doctor <project> toolchain-cpp` shows the same as `hardening` rows, and `optional` when the project declares no `hardening` key.
- The `cpp-toolchain` skill and `docs/toolchain-cpp.md` tell an agent which options each compiler family takes, how to prove one with a probe that must trap, that a sanitizer build is a test build, and that a hardened shipped tool needs a crash message.

**Adjacency:** all=not-applicable (developer tooling: a declared policy, a read-only check and guidance, with no records a user lists, exports, is notified of or reverses)

**Adjacency rationale:** The one setting is the `hardening` key of the project's own pin file, consumed by one script and the doctor, with a refusal test for each malformed entry in §1.

## Implementation Order

| Order | Section | Deliverable | Depends On | Status |
| ----- | ------- | ----------- | ---------- | ------ |
| 1 | §1 | Hardening policy in the pin file, checked on compile commands | -- | [ ] |
| 2 | §2 | Image properties read from built Windows and Linux binaries | §1 | [ ] |
| 3 | §3 | Doctor rows for the hardening checks | §2 | [ ] |
| 4 | §4 | Skill and document guidance, with the measured options | §2 | [ ] |

## 1. Hardening Policy in the Pin File

> **Started:** 2026-11-16T18:09:39Z

**Corrected 2026-11-16:** the plan put the `hardening` loader in `hardening-check.py`, but `load_pin_file` in `scripts/toolchain-check.py` owns the pin file's format and refuses an unknown top-level key (`TOP_OPTIONAL`), so `toolchain-check.py`, `compdb-check.py` and the doctor would all refuse a pin file that declares a policy. The loader is added there, as `compdb` was, and the web kit's byte-for-byte copy follows. `binaries` moves to §2 with `image` and `test_binaries`, so no key is loaded before something reads it. The matching rules the plan left open are stated in the items: which entries are definitions and which options, that the last occurrence on a command wins, response files, and how a `command` string is split. A policy that matches no first-party entry is `unknown`, never a pass.

A project states what it builds with, and the check holds its compile commands to that. Standard library hardening leaves no mark on a binary's headers, so the compile database is the only place a read-only check can see it. The check must not guess a policy: a project with no `hardening` key gets no finding.

**Phase:** 6
**Needs:** none
**Surface:** no

**Build order:**

1. Define the `hardening` key in the pin file's loader, `load_pin_file` in `kits/toolchain-cpp/templates/scripts/toolchain-check.py`. Done when: a malformed key is refused naming the file and the key.
2. Check the compile commands of the project's own sources in `kits/toolchain-cpp/templates/scripts/hardening-check.py`. Done when: a missing definition is named with the first source that lacks it.

- [x] Add `_load_hardening` to `load_pin_file` in `kits/toolchain-cpp/templates/scripts/toolchain-check.py` (`hardening` joins `TOP_OPTIONAL`), loading an optional object: `compile` (a non-empty list of definitions, `NAME` or `NAME=VALUE` such as `_MSVC_STL_HARDENING=1`, or options, which start with `-` or `/` such as `/guard:cf`), `sources` (folders under `root` that are the project's own, `["."]` when left out) and `exclude` (folders that are not, such as fetched dependencies); the loaded file gives `hardening: None` when the key is absent. Done when: `test_toolchain_check.py` cases load a valid policy and refuse, naming the file and the key, an unknown key, an empty `compile`, a list that holds a non-string or a blank entry, and a folder outside the project. Cheaper substitute: a fixed list of flags in the script, which chooses a project's build for it.
- [x] Copy the changed `toolchain-check.py` and `test_toolchain_check.py` to `kits/toolchain-web/templates/scripts/`, byte for byte. Done when: `SharedCheckTests` in `tests/test_toolchain_kits.py` passes.
- [x] Add `kits/toolchain-cpp/templates/scripts/hardening-check.py`, which loads the pin file through `toolchain-check.py` and prints `hardening: no policy declared` and exits 0 when it has no `hardening` key, and with `--json` prints the loaded policy and the result as one document. Done when: `--json` prints the loaded policy for a valid file, and the script exits 2 with the loader's refusal for a list that holds a non-string.
- [x] Read the compile database at the pin file's `compdb.path` through `scripts/compdb-check.py` (shared code, one implementation): a `read_database` function moved out of `check_database`, and the freshness check itself, so a database that is not `current` (stale, missing, invalid, unknown) is `unknown` here with compdb-check's own detail and its regenerate line, never checked for flags. Done when: `test_compdb_check.py` passes unchanged, `hardening-check.py` has no JSON or size handling of its own, and a database carrying every required flag but older than a build file exits 1 naming the build file and printing the regenerate line.
- [x] Match each required entry against each first-party entry's `arguments`, or its `command` split by Windows rules when the entry's `directory` is a Windows path (a drive letter or a backslash) and by POSIX rules otherwise. A definition is met by `-DNAME[=VALUE]`, `/DNAME[=VALUE]` or a separate `-D NAME[=VALUE]` or `/D NAME[=VALUE]` (a bare `NAME` in the policy is met by any value, `NAME=VALUE` only by that value, and `-DNAME` is `NAME=1`); an option is met by the same argument, an MSVC `/` option by its `-` spelling too. The last occurrence wins: a later `-UNAME`, `/UNAME`, `-U NAME` or `/U NAME`, another value, the `-fno-` form of an `-f` option, or `/option-` undoes it. Done when: a stored database with `/D_MSVC_STL_HARDENING=1` on every entry passes, one with it missing on a single first-party source exits 3 naming the requirement and that source, and each ordered pair `-D_GLIBCXX_ASSERTIONS -U_GLIBCXX_ASSERTIONS`, `/D_MSVC_STL_HARDENING=1 /U_MSVC_STL_HARDENING`, `/D _MSVC_STL_HARDENING=1 /U _MSVC_STL_HARDENING`, `/D_MSVC_STL_HARDENING=1 /D_MSVC_STL_HARDENING=0`, `-fstack-protector-strong -fno-stack-protector-strong` and `/guard:cf /guard:cf-` exits 3 while the reverse order passes. Cheaper substitute: a substring search over the file, which passes when one target has the option and the rest do not.
- [x] Read each `@file` response file (relative to the entry's `directory`) in place of its argument, split by the same rules as the command, and report `unknown` whenever it cannot be expanded faithfully: it is missing or unreadable, larger than 1 MiB, not UTF-8 or UTF-16 with a byte order mark, holds an unbalanced quote, or itself names a response file (nesting is refused, never followed or ignored). An unbalanced quote in a `command` is `unknown` too. Done when: an entry whose required definition sits only in a quoted response file passes; and a missing file, an oversized one, a file of invalid bytes, an unbalanced quote and a response file whose nested `@inner.rsp` holds `-U` of the requirement each exit 1 naming the file and the reason. Cheaper substitute: ignoring response files, which fails a project whose flags all sit in one.
- [x] Leave sources outside `sources` or under `exclude` unchecked, and count them in the output. Done when: a database whose only unhardened entry is under an excluded folder passes and prints the count excluded.
- [x] Report as `unknown` (exit 1, one line saying which), never as a pass: a compile database that is missing, invalid or larger than the 256 MiB the compile database check reads, and a policy that no first-party entry falls under. Done when: each case exits 1 with one line saying which.
- [x] Add `kits/toolchain-cpp/templates/scripts/tests/test_hardening_check.py` covering the cases above with stored databases, and add the script and its test to the kit's installed file list in `tests/test_toolchain_kits.py`. Done when: `python -m unittest discover -s kits/toolchain-cpp/templates/scripts/tests -p "test_*.py"` and `python -m unittest tests.test_toolchain_kits` pass, and `test_hardening_check.py`, run directly, fails when the per-source matching is replaced by a whole-file search.
- [ ] Commit: `toolchain-cpp: a declared hardening policy, checked on the compile commands`

**Test checkpoint:** `python -m unittest discover -s kits/toolchain-cpp/templates/scripts/tests -p "test_*.py"` (the kit's own suite, which runs `test_hardening_check.py`; `tests.test_toolchain_kits` runs the installed copies only under `CONCLAVE_FULL_TESTS`) and `python -m unittest tests.test_toolchain_kits` pass with the new cases, and the case with one unhardened first-party source fails when the matching is made a whole-file search.

**Corrected 2026-11-16 (plan review at `c803d34`):** the freshness check, the MSVC `/U` and separated `/D` and `/U` forms, the response-file refusals and a checkpoint that runs the new tests were added to the items above; before, the checkpoint named only `tests.test_toolchain_kits`.

## 2. Image Properties of Built Binaries

What the linker wrote is the only proof of control-flow guard, shadow-stack compatibility and address randomisation, and compile flags prove none of them: Isotone learned that and reads `dumpbin`, which only exists where Visual Studio does. This section reads the headers directly, so the same check runs on Windows, in WSL and on a CI runner with no toolchain installed.

**Phase:** 6
**Needs:** none
**Surface:** no

**Build order:**

1. Parse PE and ELF headers in `hardening-check.py` with the standard library. Done when: stored binaries of both kinds report their properties.
2. Hold each binary the policy names to the properties it requires. Done when: a missing property is named per binary, on a `hardening:image:` line beside the `hardening:compile:` one, and the exit is 3 when either has a missing requirement, else 1 when either is unknown, else 0.

- [ ] Add a PE reader to `kits/toolchain-cpp/templates/scripts/hardening-check.py`: DLL characteristics (`DYNAMIC_BASE`, `HIGH_ENTROPY_VA`, `NX_COMPAT`, `GUARD_CF`), the guard function count from the load configuration, `CET_COMPAT` from the extended DLL characteristics debug entry, and the import table's DLL names. Done when: a test over small stored executables (one linked with control-flow guard and shadow stack, one without) reports each property correctly. Cheaper substitute: running `dumpbin` or `llvm-readobj`, which the standard-library rule forbids and a Linux runner does not have.
- [ ] Add an ELF reader: position-independent executable, `GNU_RELRO` with `BIND_NOW`, a non-executable `GNU_STACK`, a reference to `__stack_chk_fail`, and the needed libraries. Done when: a test over two small stored executables (hardened and not) reports each property correctly.
- [ ] Add `binaries`, `image` and `test_binaries` to `_load_hardening` in `toolchain-check.py` (both kits' copies), each refused naming the key when malformed, and let `hardening.binaries` name each binary (a path under `root`, with `*` allowed in the file name) and `hardening.image` list the properties required of all of them, by the names above. Done when: a policy requiring `GUARD_CF` exits 3 naming the binary that lacks it, and a named binary that does not exist is `unknown` (exit 1), never a pass.
- [ ] Refuse a binary that imports or needs a sanitizer runtime (a name containing `asan`, `ubsan`, `tsan` or `msan`) unless the policy lists it under `hardening.test_binaries`. Done when: a stored executable importing `clang_rt.asan_dynamic-x86_64.dll` exits 3 naming the import. Cheaper substitute: trusting that nobody ships a sanitizer build tree.
- [ ] Store the fixtures as real linker output, never hand-made headers: `kits/toolchain-cpp/templates/scripts/tests/fixtures/` holds a probe program built hardened and plain by MSVC 19.52 (`cl` and `link`), with AddressSanitizer by clang-cl, and hardened, plain and with AddressSanitizer by GCC 15.2 in WSL, each named `*.bin` so nothing takes it for a program to run, beside a `README.md` giving each build command and what `dumpbin /headers /loadconfig` and `readelf -lWd` reported for it. Done when: every property the reader reports for a fixture is the one its README records from those tools. Cheaper substitute: headers written by the test itself, which prove the reader agrees with its own author.
- [ ] Report a property that does not belong to a binary's format (`GUARD_CF` on an ELF file) as not applicable, `HIGH_ENTROPY_VA` on a 32-bit image too, and `STACK_PROTECTOR` on an ELF file with no dynamic string table and no `__stack_chk_fail` symbol as `unknown`; a binary none of whose required properties applies is `unknown`, never a pass. Read the delay-loaded imports with the others. Done when: a policy requiring only `GUARD_CF` of an ELF binary exits 1 naming it, and a delay-loaded sanitizer runtime is refused like an imported one.
- [ ] Bound the reader: at most 64 MiB of a file is read, a truncated or malformed header is `invalid` naming the offset, and no input makes the script raise. Done when: a test feeds a truncated file, a file of zeros and a text file and each ends with one line and exit 1.
- [ ] Commit: `toolchain-cpp: image hardening read from PE and ELF headers`

**Test checkpoint:** `python -m unittest discover -s kits/toolchain-cpp/templates/scripts/tests -p "test_*.py"` (the kit's own suite, which runs `test_hardening_check.py`) and `python -m unittest tests.test_toolchain_kits` pass with the PE, ELF, sanitizer-import and malformed-file cases, and the control-flow guard case fails when the reader is made to skip the DLL characteristics.

## 3. Doctor Rows for the Hardening Checks

The doctor is where an operator sees a project's state in one screen, so a project that declared a policy sees whether it holds.

**Phase:** 6
**Needs:** none
**Surface:** no

**Build order:**

1. Add the rows in `forge.py` `doctor_repo` for `toolchain-cpp`. Done when: the three states print as below.

- [ ] Add a `hardening-policy` row: `optional` with one line saying how to declare one when the pin file has no `hardening` key, `ok` with the counts of compile entries and binaries it covers, `missing` with the refusal when the key does not load. Done when: `python forge.py doctor <project> toolchain-cpp` prints each for a fixture project in `tests/test_forge.py`.
- [ ] Add `hardening:compile` and `hardening:image` rows running the check read-only: `ok`, `setup_required` naming the first three findings and the count of the rest, or `unknown` when the database or a binary is not there. Done when: a fixture project with one unhardened source shows `setup_required` naming it, and `--strict` exits 3 for it.
- [ ] Keep `optional` uncounted by `--strict`, as the kit's other optional rows are. Done when: a project with no `hardening` key passes `--strict`.
- [ ] Commit: `forge: the doctor reports a project's hardening policy`

**Test checkpoint:** `python -m unittest tests.test_forge` passes with the three policy states and the `--strict` cases, and the unhardened-source case fails when the row is made to print `ok` unconditionally.

## 4. Skill and Document Guidance

A check says what is missing; the skill says what to do about it. The guidance carries what was measured, with the compiler versions, so an agent does not assert an option a toolchain refuses.

**Phase:** 6
**Needs:** none
**Surface:** no

**Build order:**

1. Write the section in `kits/toolchain-cpp/templates/docs/toolchain-cpp.md` and the rules in the Claude skill file. Done when: the generated copies match.

- [ ] Add "Memory safety" to `kits/toolchain-cpp/templates/docs/toolchain-cpp.md`: the `hardening` key with one worked example per compiler family, the command and its exit codes, and a table of options by family (MSVC: `_MSVC_STL_HARDENING=1`, `/guard:cf`, `/CETCOMPAT`, `/sdl`; Clang with libc++, llvm-mingw included: `_LIBCPP_HARDENING_MODE_FAST`, `-fstack-protector-strong`, `-ftrivial-auto-var-init=zero`, `-mguard=cf`, `-Wl,-Xlink=-cetcompat`; GCC with libstdc++: `_GLIBCXX_ASSERTIONS`, `-fstack-protector-strong`, `-D_FORTIFY_SOURCE`, full RELRO), each row giving the compiler version it was measured on from Current state and marking what was not measured. Done when: the document carries the table with a version or "not measured" in every row.
- [ ] State the limits in the same section: hardening covers bounds and control flow, not object lifetime; lifetime errors are found by a sanitizer test build and fuzzing, which never ship. Done when: the paragraph is there and names both.
- [ ] Add four rules to `kits/toolchain-cpp/templates/.claude/skills/cpp-toolchain/SKILL.md`: prove an option with a probe program that commits the error on purpose and must trap, never by reading the flag back; apply hardening to the project's own targets, and a sanitizer only in a test preset; run `python scripts/hardening-check.py` before calling a build shippable; and plan a crash message with any hardening that ships, because the process ends at once (a fast-fail reaches no handler inside the process, so the next start must be able to say the last run stopped). Done when: `python forge.py skill-copies` regenerates the Antigravity and Codex copies and the copy test passes.
- [ ] Describe `hardening-check.py`'s reading of a compile command in the same document as built in §1: its first line for each status (`hardening:compile: none: no policy declared: ...` when no key is declared), and that `-fno-stack-protector` undoes every stack protector level (§1's checklist named a `-fno-stack-protector-strong` pair, an option neither GCC nor Clang has; its findings file records the correction). Done when: the document names both and `tests/test_toolchain_kits.py` asserts the no-policy line against the script's own output.
- [ ] Add a "Memory safety" section to `kits/toolchain-cpp/README.md`, beside the file table rows for `scripts/hardening-check.py` and its test. Done when: the section names the `hardening` key and the command, and the table lists both files. **Corrected 2026-11-16:** the two file table rows were added in §1 (`f936823`), since `tests/test_toolchain_kits.py` fails while an installed file is missing from the table.
- [ ] Commit: `toolchain-cpp: memory-safety guidance with the measured options`

**Test checkpoint:** `python forge.py check-all` passes, and the skill-copies test fails when the Claude skill file is changed without regenerating the copies.

## Verification

- A fixture C++ project with the kit installed and a `hardening` key gets `ok` from `python scripts/hardening-check.py` when its compile commands and binary carry the policy, a named finding when either does not, and the same from `python forge.py doctor <project> toolchain-cpp`.
- `python forge.py check-all` passes.
- `python scripts/todo-graph.py validate` and `python scripts/todo-graph.py plan --check` pass.
