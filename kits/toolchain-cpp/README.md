# C and C++ toolchain kit

Additive overlay for a C or C++ project: it pins the build tools the project wants, tells the operator which are missing or too old, and never installs a tool or chooses a build system. The project keeps its own Makefile, Ninja files or CMake; the kit checks what they need.

What it installs:

| File | What it is |
| --- | --- |
| `.conclave/toolchain-cpp.json` | The pin file: each tool, the commands that satisfy it, the least version |
| `scripts/toolchain-check.py` | Reads the pin file and reports each tool; installs and writes nothing |
| `scripts/tests/test_toolchain_check.py` | The check's own tests, with stub tools |
| `scripts/compdb-check.py` | Says whether the compile database can be trusted; runs and writes nothing |
| `scripts/tests/test_compdb_check.py` | The compile database check's own tests |
| `scripts/cc-cache.py` | Puts a compiler cache in front of the compilers a build names |
| `scripts/cache-stats.py` | Prints the cache's hit rate; fails a rebuild that did not use the cache |
| `scripts/tests/test_cc_cache.py` | The tests of both, with stub compilers and caches |
| `.clangd` | clangd's configuration, seeded once: the compile database folder and its defaults |
| `docs/toolchain-cpp.md` | The project's document: every command, and what is left to the project |
| `.claude/skills/cpp-toolchain/SKILL.md` | The `cpp-toolchain` skill, for Claude Code |
| `.agents/skills/cpp-toolchain/SKILL.md` | The same skill, for Antigravity |
| `.codex/skills/cpp-toolchain/SKILL.md` | The same skill, for Codex |
| `.codex/skills/cpp-toolchain/agents/openai.yaml` | Codex's interface file for the skill |

The pin file is the project's own from the first install: `forge.py` never overwrites it, and a project that already has one keeps it byte for byte.

The skill tells an agent to check before a build fails mysteriously, never to install or upgrade a tool or change a pin to get a build through, to regenerate the compile database after every change of the source set and read it back, and never to edit the database or `.clangd` to silence a diagnostic. Its three copies say the same; an install for one agent gets that agent's copy only.

## Install

```powershell
python forge.py kit /path/to/project toolchain-cpp [--dry-run]
python forge.py doctor /path/to/project toolchain-cpp [--strict]
```

`python forge.py init /path/to/project --kit toolchain-cpp` installs it with the base kit. The SDK does not install this kit in itself.

## The pins

The seed pins five tools. Three are `optional`, because a project may not use them: RasterFold builds with no compiler cache, Impossible OS with no Ninja.

| Tool | Commands, in order of preference | Least version | Optional |
| --- | --- | --- | --- |
| `ninja` | `ninja` | 1.10 | yes |
| `compiler-cache` | `ccache`, then `sccache` | 4.0, 0.5 | yes |
| `linker` | `mold`, then `ld.lld` | 1.0, 14 | yes |
| `clangd` | `clangd` | 14 | no |
| `compiler` | `clang`, then `gcc` | 14, 11 | no |

A tool is satisfied by the first of its commands found on `PATH`, and each command has its own version rule, because alternatives number their releases independently:

```json
{
  "name": "compiler-cache",
  "commands": [
    {"command": "ccache", "version_args": ["--version"],
     "version_pattern": "ccache version ([0-9]+(?:\\.[0-9]+)*)", "min_version": "4.0"},
    {"command": "sccache", "version_args": ["--version"],
     "version_pattern": "sccache ([0-9]+(?:\\.[0-9]+)*)", "min_version": "0.5"}
  ],
  "install": "apt install ccache (Windows: winget install Ccache.Ccache, or winget install Mozilla.sccache)",
  "optional": true
}
```

A pin file may also name where a project keeps tools of its own: `root`, the app's folder inside the project (`.` when left out), and `search`, a list of folders inside it. A command is looked for in those folders first, then on `PATH`, and never in the working directory. The seed names none, because C and C++ tools are installed for the machine; the PHP and Node kit's seed uses them for `vendor/bin` and `node_modules/.bin`.

To change a pin, edit `.conclave/toolchain-cpp.json`: raise a `min_version`, name the binary the project builds with (`clang-19` in place of `clang`), set `optional` to `false` for a tool the project cannot build without, or add a tool. `command` is a bare program name, never a path; `version_pattern` is a regular expression with exactly one group, which must capture dotted numbers; `install` is one line. The check refuses a pin file that breaks these rules, naming the file, the tool and the key.

```powershell
python scripts/toolchain-check.py --pins .conclave/toolchain-cpp.json          # one line per tool
python scripts/toolchain-check.py --pins .conclave/toolchain-cpp.json --json
python scripts/toolchain-check.py --pins .conclave/toolchain-cpp.json --root /path/to/project
```

Each line is the tool's name, one word and the detail: `ok`, `setup_required` for a required tool that is not ok, `optional` for a tool the pin marks optional that is not ok (`--json` keeps `status` and `optional` apart). It exits 3 when a tool that is not optional is not ok, 2 when the pin file does not load, 0 otherwise. Each tool is run with no shell, for at most 15 seconds and 64 KiB of output, and whatever it started is ended with it.

## The compile database

clangd is only as good as the `compile_commands.json` it reads: a stale one gives agents wrong diagnostics. `scripts/compdb-check.py` says whether the project's can be trusted.

```powershell
python scripts/compdb-check.py                                   # one line: the status and why
python scripts/compdb-check.py --json
python scripts/compdb-check.py --root /path/to/project --path build/compile_commands.json
python scripts/compdb-check.py --build-file CMakeLists.txt --build-file cmake/flags.cmake
python scripts/compdb-check.py --source src/new_file.c         # stale unless the database has an entry for it
```

| Status | Meaning |
| --- | --- |
| `current` | It parses, every source file it names exists, and no build file is newer than it |
| `stale` | A build file is newer, a source it names is gone, or a `--source` has no entry |
| `unknown` | A build file or a named source file cannot be read, or the database is too large |
| `invalid` | It cannot be read, is not a JSON list of entries, or an entry (named by number) is bad |
| `missing` | There is no file at its path |

It exits 0 for `current`, 1 for any other status, and 2 for bad usage or a pin file that does not load. `--json` prints one document (`path`, `status`, `detail`, `entries`, `newer`, `gone`, `unlisted`, `regenerate`) for every run that gets past its arguments, a refused one included (`status` is then `refused`). An entry needs a `directory`, a `file` and a compile command (`command`, or `arguments` starting with the compiler), as the format requires; a relative `file` is read from its `directory`, and a relative `directory` from the database's folder. At most 20 missing source files are named and the rest are counted. At most 256 MiB of a database is read: a larger one is `unknown` and is never loaded. A usual build file that is absent is passed over; one whose time the system will not give makes the status `unknown`, as does a source file the system will not let the check inspect (each is named with the system's reason). No fault of the file system ends the check as an error. What is certain sets the status and nothing is dropped: a `stale` database's detail also names each file that could not be read, with the reason.

The pin file says where the database is and what it must not be older than, under an optional `compdb` key (each key in it optional, each file read under the pin file's `root`):

```json
{"schema_version": 1, "tools": [],
 "compdb": {"path": "build/compile_commands.json",
            "build_files": ["CMakeLists.txt", "cmake/flags.cmake"],
            "regenerate": ["cmake", "-S", ".", "-B", "build"]}}
```

- `path`: the database, `compile_commands.json` when left out. `--path`, read from `--root`, overrides it.
- `build_files`: the files that change the compile flags. When left out, `build.ninja`, `Makefile` and `CMakeLists.txt` are compared where they exist, in the `root` and beside the database. A project with included makefiles or nested `CMakeLists.txt` files names them here, so the doctor sees them too. `--build-file` replaces the list for one run. A file named here that does not exist makes the status `unknown`, because freshness that cannot be told is not `current`.
- `regenerate`: the project's own command that writes the database again, as a list of arguments. The check prints it for a database that is not current, quoted for the shell of the system it runs on and saying which (`regenerate with (PowerShell): ...` on Windows, `regenerate with (sh): ...` elsewhere), and never runs it: a check that builds is not read-only. `--json` gives the arguments as the list they are.

## The compiler cache

A compiler cache (ccache or sccache) cuts the time and memory of a rebuild. `scripts/cc-cache.py` puts one in front of the compilers a build names, on Windows and on POSIX. A program cannot change its caller's `PATH`, so it writes the wrappers and prints the one statement that puts them first on `PATH`; the build script checks its exit and then evaluates that statement. In `sh`:

```sh
setup=$(python3 scripts/cc-cache.py cc c++) || exit 1
eval "$setup"
```

In PowerShell:

```powershell
$setup = python scripts/cc-cache.py --shell powershell clang
if ($LASTEXITCODE) { exit 1 }
$setup | Invoke-Expression
```

In a batch file:

```bat
set "CC_CACHE_SETUP=%TEMP%\cc-cache-setup-%RANDOM%.cmd"
python scripts\cc-cache.py --shell cmd clang > "%CC_CACHE_SETUP%" || exit /b 1
call "%CC_CACHE_SETUP%"
del "%CC_CACHE_SETUP%"
```

Checking the exit first matters: a plain `eval "$(...)"` would turn a setup that failed into a quiet success.

- **The wrappers.** For each compiler found on `PATH` it writes a wrapper of that name that runs the cache with the real compiler's full path and the arguments given (a `sh` script on POSIX, a `.cmd` on Windows), into a folder of the project's own under the user's cache folder: `$XDG_CACHE_HOME` or `~/.cache`, `%LOCALAPPDATA%` on Windows, then `conclave/cc-cache/<12 hex of the project's path>/`. The real compiler is looked for with that folder left out, so a wrapper never reaches itself. A wrapper is rewritten only when its content would change. A compiler is run by the path it was found at, never by what that path links to, so `clang++` that is a link to `clang` still runs as `clang++`. Two setups of one project started together take turns: the folder is written under a lock.
- **The cache.** `--cache ccache` or `--cache sccache`, else the first of the two on `PATH`. The folder records the choice, and `cache-stats.py` reads that cache.
- **Opting out.** With `BUILD_NO_CCACHE` set, or no cache installed, every wrapper is removed and the output is a comment, so evaluating it changes nothing. A shell that already has the folder on `PATH` reaches the real compilers again, and a wrapper also stands aside by itself when it runs with `BUILD_NO_CCACHE` set or with the cache's program gone. A compiler no longer named, or no longer installed, loses its wrapper on the next run.
- **Exit codes.** 0 also when there is nothing to wrap (a missing cache never breaks a build); 1 when a wrapper cannot be written, with nothing printed to evaluate; 1 as well when another setup holds the folder for more than 30 seconds; 2 for a compiler name that is not a bare name (on Windows, one given with its extension: name `clang`, not `clang.exe`, because the shell would find the real program before a wrapper), or a path a `.cmd` cannot quote (one holding `"` or `%`).

`scripts/cache-stats.py` says whether a rebuild used the cache:

```text
python scripts/cache-stats.py --zero                 # before the build: reset the statistics (read back to prove it)
python scripts/cache-stats.py --min-hit-rate 60      # after it: hits, misses and the rate; exit 3 when below
python scripts/cache-stats.py --cache sccache --json
```

It reads the form each cache prints for a program (`ccache --print-stats`, `sccache --show-stats --stats-format json`; confirmed against ccache 4.12.3 and sccache 0.13.0 and 0.19.0 on 2026-11-15), runs the cache with no shell for a bounded time and output, and exits 3 with `--min-hit-rate` when the rate is below it or when no compile went through the cache at all. Exit 2, with one line saying which, when no cache is installed or the cache could not be started, failed, ran over a limit, printed something else, or did not reset.

A build that finds its sources by itself (a wildcard in a Makefile, a glob in CMake) changes no build file when a source is added, so the database stays `current` without the new file. `--source <file>` (relative to `--root`, repeatable) asks whether that file has an entry, matched through each entry's `directory` with the system's rule for case; a file without one is listed under `unlisted` and the status is `stale`, and every such file is named, however many are asked for. After adding or moving a source: regenerate, then name the file. A `--source` outside the project is exit 2.

## clangd

The kit seeds a `.clangd` at the project root and puts clangd in the LSP kit's server table, so the three agents reach it (`kits/lsp/README.md`).

- **The seed.** `.clangd` holds what any C or C++ project needs and nothing of one project: `CompilationDatabase: .` (the folder that holds `compile_commands.json`), `Index: Background: Build`, and the two include diagnostics (`UnusedIncludes`, `MissingIncludes`) at clangd's own defaults, written out so a project sees where to set them. No target, no flag, no include path. It is the project's file from the first install: an existing `.clangd` is kept byte for byte.
- **Keep clangd and the freshness check on one database.** clangd reads a relative `CompilationDatabase` from the folder `.clangd` is in; `scripts/compdb-check.py` reads `compdb.path` under the pin file's `root`. clangd reads a database only from a file named `compile_commands.json`, looks in the folder it is given first and in a `build` folder of it when that has none. So the seed's `.` also serves `"compdb": {"path": "build/compile_commands.json"}`, as long as no older `compile_commands.json` is left at the root. When the database is anywhere else (`out/compile_commands.json`, or a `root` of `engine`), write that folder in `.clangd` too (`CompilationDatabase: out`, `CompilationDatabase: engine`). The doctor's `clangd-config` says when clangd would not find the database the check watches.
- **The server table.** With the `lsp` kit installed, the install adds the `cpp` preset's `clangd` to `.conclave/lsp.json`, rooted at the pin file's `root`, in whichever order the two kits are installed. A `clangd` entry the project already has is never changed; when it is not the preset's it is listed under `lsp_servers.differs`. Without the `lsp` kit nothing is written and the result names the command that installs it. Later, `python scripts/lsp-servers.py add cpp` (with `--root <folder>` for an app that is not at the project root) adds it by hand.

Confirmed with clangd itself (22.1.3 on Windows 11 and 19.1.7 on Ubuntu, 2026-11-15): a file that compiles only with a definition the database gives has no diagnostic with the seed, with the database at the root or in `build/`, and the compiler's error when `.clangd` names a folder without the database or the database is in another folder (`out/`) while `.clangd` still says `.`.

## Sources

The kit generalises what two C projects each built for themselves. The approach is theirs; the code is new, because each of theirs was tied to one build.

- RasterFold, at `b33493346141f96b6b304cd3e0c393595382f056`: `toolchain.json` (tools pinned by version, Ninja among them) and the preflight that checks them led to the pin file and `scripts/toolchain-check.py`; `scripts/gen-compdb.py` (`--check`, `--rebuild-stale`) led to `scripts/compdb-check.py`, which checks and leaves regenerating to the project; its `.clangd` gave the seed's `CompilationDatabase` and include diagnostics.
- Impossible OS, at `17a762d39ccd1958cbe711901f645fd9b042e939`: the `PATH` wrapper that puts ccache in front of the compiler in `scripts/build.sh` led to `scripts/cc-cache.py`, for any compiler, either cache and three shells; `scripts/ci/check-compile-cache.py` led to `scripts/cache-stats.py`; its `.clangd` gave the seed's `Index` setting. Its Bear step is why the check never assumes how a database is made.
- New in the kit: a version rule per command, tools looked for in the project's own folders, the `--source` question, the doctor's `clangd-server` and `clangd-config` checks, the document and the skill.

## Doctor

`python forge.py doctor <project> toolchain-cpp` reports:

- each file the kit installs, `ok` or `missing`;
- `tool-pins`: `ok` with the tools the project's pin file names, `missing` with the refusal when it does not load;
- `tool:<name>` for each pinned tool: `ok` with the path found and its version; `setup_required` when a required tool is not ok, with the reason (not installed and how to install it, both versions when it is too old, or what went wrong when it was run); `optional` for the same on a tool the pin marks optional.

- `compile-database`: `ok` with the database and its entry count when it is `current`; `setup_required` with the status and the reason for `missing`, `invalid`, `stale` and `unknown`, and the project's `regenerate` command when the pin file gives one. It reads the pin file's `compdb` and starts nothing.

- `clangd-server`: `ok` when `.conclave/lsp.json` has a `clangd` server; `setup_required`, naming the command, when the project has no table (`python forge.py kit <project> lsp`) or the table has no `clangd` (`python scripts/lsp-servers.py add cpp`, with `--root` for a pin file whose `root` is not the project); `unexpected` when the table does not load.
- `clangd-config`: `ok` when `.clangd` gives clangd the folder the compile database is in, or the folder above its `build` folder with no other `compile_commands.json` in it; `unexpected`, naming the folder to write, when it names another or `None`, when clangd would find another `compile_commands.json` first, when the database the check watches has another file name (clangd never reads it), or when `.clangd` cannot be read; `optional` when the file is in a form the doctor does not read (several documents, an `If:` condition, `CompileFlags` in flow style) or names no `CompilationDatabase`, saying which folder clangd must be given. Nothing is guessed from such a file, and it is never changed.

`optional` is shown and never counted: `--strict` exits 3 only for a required tool, a missing file or a pin file that does not load, so a project that uses no compiler cache passes.

The doctor reads the project's pin file, not the seed, and starts each pinned tool to ask its version. For that reason `python forge.py doctor <project>` with no kit named does not run these checks: name the kit.
