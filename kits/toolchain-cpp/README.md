# C and C++ toolchain kit

Additive overlay for a C or C++ project: it pins the build tools the project wants, tells the operator which are missing or too old, and never installs a tool or chooses a build system. The project keeps its own Makefile, Ninja files or CMake; the kit checks what they need.

The kit is being built in sections (`todo/04-tooling/TODO-02-toolchain-kits.md`). What it installs today:

| File | What it is |
| --- | --- |
| `.conclave/toolchain-cpp.json` | The pin file: each tool, the commands that satisfy it, the least version |
| `scripts/toolchain-check.py` | Reads the pin file and reports each tool; installs and writes nothing |
| `scripts/tests/test_toolchain_check.py` | The check's own tests, with stub tools |

The pin file is the project's own from the first install: `forge.py` never overwrites it, and a project that already has one keeps it byte for byte.

Still to come: the compile database check (D04 T02 §3), the compiler cache wrapper (§4), the clangd seed and its entry in the LSP kit's server table (§5), and the `cpp-toolchain` skill and document (§7).

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

To change a pin, edit `.conclave/toolchain-cpp.json`: raise a `min_version`, name the binary the project builds with (`clang-19` in place of `clang`), set `optional` to `false` for a tool the project cannot build without, or add a tool. `command` is a bare program name, never a path; `version_pattern` is a regular expression with exactly one group, which must capture dotted numbers; `install` is one line. The check refuses a pin file that breaks these rules, naming the file, the tool and the key.

```powershell
python scripts/toolchain-check.py --pins .conclave/toolchain-cpp.json          # one line per tool
python scripts/toolchain-check.py --pins .conclave/toolchain-cpp.json --json
```

It exits 3 when a tool that is not optional is not ok, 2 when the pin file does not load, 0 otherwise. Each tool is run with no shell, for at most 15 seconds and 64 KiB of output, and whatever it started is ended with it.

## Doctor

`python forge.py doctor <project> toolchain-cpp` reports:

- each file the kit installs, `ok` or `missing`;
- `tool-pins`: `ok` with the tools the project's pin file names, `missing` with the refusal when it does not load;
- `tool:<name>` for each pinned tool: `ok` with the path found and its version; `setup_required` when a required tool is not ok, with the reason (not installed and how to install it, both versions when it is too old, or what went wrong when it was run); `optional` for the same on a tool the pin marks optional.

`optional` is shown and never counted: `--strict` exits 3 only for a required tool, a missing file or a pin file that does not load, so a project that uses no compiler cache passes.

The doctor reads the project's pin file, not the seed, and starts each pinned tool to ask its version. For that reason `python forge.py doctor <project>` with no kit named does not run these checks: name the kit.
