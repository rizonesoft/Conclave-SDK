# LSP kit

Additive overlay that gives a project's three agents (Antigravity, Claude Code and Codex) the stack's language servers. One table, `.conclave/lsp.json`, names the servers; everything else in the kit reads it.

The kit is being built in sections (`todo/04-tooling/TODO-01-lsp-kit.md`). What it installs today:

| File | What it is |
| --- | --- |
| `.conclave/lsp.json` | The server table, seeded empty: `{"schema_version": 1, "servers": []}` |
| `scripts/lsp-servers.py` | `list`, `add <preset>` and `remove <name>` for the table |
| `scripts/lib/lsp_table.py` | The table's rules: `load_servers`, the presets, the write |
| `scripts/lib/lsp_presets.json` | The catalogue of servers and the presets per stack |
| `scripts/lsp-diagnostics.py` | Runs the table's servers over files and reports their diagnostics |
| `scripts/lib/lsp_client.py` | The LSP client: starts, contains and bounds one server, returns its result |
| `scripts/lib/lsp_plugin.py` | Generates the Claude Code plugin from the table |
| `scripts/tests/test_lsp_table.py` | The kit's own tests of the table |
| `scripts/tests/test_lsp_diagnostics.py` | The kit's own tests of the client, against a stub language server |
| `scripts/tests/test_lsp_plugin.py` | The kit's own tests of the generated plugin |

The table is the project's own file from the first install: `forge.py` never overwrites it, and a project that already has one keeps it byte for byte.

Still to come, each reading the same table: an MCP bridge for Codex and Antigravity (§6), and the `language-servers` skill and document (§7).

## Install

```powershell
python forge.py kit /path/to/project lsp [--dry-run]
python forge.py doctor /path/to/project lsp [--strict]
```

`python forge.py init /path/to/project --kit lsp` installs it with the base kit. The kit installs no language server: the operator installs those at user level, and the doctor names each one that is missing with its install command.

## The server table

```json
{
  "schema_version": 1,
  "servers": [
    {
      "name": "clangd",
      "command": ["clangd"],
      "extensions": {".c": "c", ".h": "c", ".cpp": "cpp"},
      "install": "apt install clangd"
    }
  ]
}
```

| Key | Required | What it is | Default |
| --- | --- | --- | --- |
| `name` | yes | Lowercase letters, digits and `-`; unique in the table | |
| `command` | yes | A list: the program, then its arguments. Never one string | |
| `extensions` | yes | An object from a file suffix to the LSP language id sent for it | |
| `install` | yes | A one-line hint the doctor prints when the program is missing | |
| `root` | no | The folder inside the project the server runs in | `.` |
| `requires` | no | A file under `root` that must exist for the server to be run | none |
| `init` | no | An object sent to the server as `initializationOptions` | `{}` |
| `settings` | no | An object answered to the server's `workspace/configuration` | none |
| `severity` | no | The least severity that fails a run: `error` or `warning` | `error` |
| `settle` | no | Seconds to wait for diagnostics, from 1 to 120 | `5` |
| `note` | no | One line on what the server is for | none |

A suffix is matched against the end of a file's name and the longest match wins, so `.blade.php` can name a different language from `.php`. `root` and `requires` are relative paths that stay inside the project (`.` and `./` are the project itself).

The program, the first item of `command`, is found the same way by every tool. A bare name (`clangd`) is looked for on `PATH` and nowhere else, never in the working directory. A name with a folder in it (`vendor/bin/laravel-lsp`) is read from the server's `root`; an absolute path is read as it is. Either way it must be a file the system will execute.

The value `${scratch}` in `init` or `settings` stands for a temporary folder outside the repository that the diagnostics client (§3) makes for the run and removes afterwards: the `laravel` preset gives it to Intelephense as its `storagePath`, so the server's index never lands in the project. `init` and `settings` may nest 32 levels of objects and lists, because every tool that reads them walks them. Anything else in the file (an unknown key, a `command` given as one string, a duplicate name) is refused by every tool that reads the table, with a message naming the file, the server and the key.

## Presets

A preset adds a stack's servers. Each server is described once in the catalogue (`scripts/lib/lsp_presets.json`) with settings that fit any project; a preset names the servers it wants and overrides only what its stack needs.

| Preset | Servers | Notes |
| --- | --- | --- |
| `cpp` | `clangd` | Reads `compile_commands.json` at the project root |
| `python` | `basedpyright` | `basedpyright-langserver --stdio` |
| `php` | `intelephense` | General PHP, no framework settings |
| `web` | `typescript`, `tailwindcss` | Tailwind with no framework prerequisites |
| `laravel` | `laravel-lsp`, `intelephense`, `tailwindcss` | Laravel settings; finds the app by `artisan` |

```powershell
python scripts/lsp-servers.py list                      # the table's servers and the presets on offer
python scripts/lsp-servers.py add laravel               # append a preset's servers
python scripts/lsp-servers.py add laravel --root api    # name the app's folder instead of looking for it
python scripts/lsp-servers.py remove tailwindcss        # delete one server
```

`add` never changes an entry the project already has by that name: it prints which servers it added and which it kept, so a project's own command or settings survive a second `add` and a later preset. The `laravel` preset looks for `artisan` at the project root, then in `platform/`, then in the other first-level folders in name order, and writes that folder as each server's `root`; with no `artisan` anywhere it refuses and asks for `--root`. The table is written through a temporary file and a replace, and only when it changes. Exit 0 on success, 1 when the table cannot be written (it is then as it was), 2 for a table that does not load or a preset or server name that is not known.

## Diagnostics

```text
python scripts/lsp-diagnostics.py --all --staged                  # every server, the staged files
python scripts/lsp-diagnostics.py --all --worktree                # the files changed in the working tree
python scripts/lsp-diagnostics.py --all --commit <sha>             # the files of a commit
python scripts/lsp-diagnostics.py --server clangd src/main.c      # named servers (repeatable), named files
```

The table is the only list of servers: `--server` takes its names and an empty table is refused with how to add one. Give one input (`--staged`, `--worktree`, `--commit <sha>` or paths from the project root). Git is read with `-z`, so a file name with a space or outside ASCII arrives whole, and a git command that fails (an unknown revision, a folder that is no repository) ends the run with git's reason, never as an empty input. A file goes only to the servers that serve it: its name ends with one of the server's `extensions` (the longest suffix gives the language id, so `.blade.php` is not `.php`) and it lies under the server's `root`. The client is read-only: it opens documents in the server's memory and writes nothing to the project.

`--severity <error|warning|information|hint>` and `--settle <seconds>` override each server's own `severity` and `settle`; `--timeout <seconds>` (default 240, or `LSP_DIAGNOSTICS_TIMEOUT`) is what a server gets for the whole run; `--json` prints one document (`servers`, `diagnostics`, `failing`, `exit`, `error`) for every run that gets past its arguments, a refused one included (exit 2, with the refusal as its `error`); `--verbose` shows the end of each server's standard error.

Each server ends with one result, and a check that did not finish is never a pass:

| Result | Meaning |
| --- | --- |
| `ok` | Every file it was sent was answered |
| `idle` | No file of its kind in the input: it is not started, installed or not |
| `missing` | Its program is not installed; the line carries the entry's `install` hint |
| `skipped` | The file its entry `requires` is absent |
| `failed` | Not contained, refused or never answered `initialize`, ended early, or hit a limit |
| `partial` | It ran, and some file was not answered or could not be read; each is named |

| Exit | When |
| --- | --- |
| 0 | Every server that ran finished, with no diagnostic at or above its threshold |
| 1 | A diagnostic at or above a server's threshold, or a server that is `failed` or `partial` |
| 2 | Bad usage, an unknown server, a git command that failed, or a table that does not load |
| 3 | No requested server could check anything: each is `missing`, `skipped` or `failed` |

The exit is the same with and without `--json`.

A server is started with no shell and no console window and is contained before it runs: in a job object on Windows (started suspended, resumed once it is in the job), in its own session on POSIX. Its whole process tree is ended on every way out, a clean run and an interrupt included, and a server that cannot be contained is not run. At most 64 MiB is read from a server in a run, standard output and standard error together, and no message may announce more than 32 MiB; either limit stops the server and the result says which. What is sent to a server is queued and written beside the run, so a server that stops reading cannot hold the run past its time limit, and a diagnostic that is not one (a server's reply is checked, never assumed) makes that server `failed` with the file named.

`${scratch}` in an entry's `init` or `settings`, in any string at any depth, is replaced with a temporary folder outside the repository that exists for the run and is removed after it, so a server's index or cache (Intelephense's `storagePath`) never lands in the project.

`scripts/lib/lsp_client.py` is the client itself (`run_server`, `Client`), for other tools that drive the table's servers.

## Claude Code plugin

Claude Code can run language servers itself while it edits, from a plugin. The kit generates that plugin from the table, so the table stays the only list of servers:

```text
python scripts/lsp-servers.py plugin        # writes .claude/lsp/conclave-lsp/ for the table's servers
claude --plugin-dir .claude/lsp/conclave-lsp
```

`.claude/lsp/conclave-lsp/` holds `.claude-plugin/plugin.json` and `.lsp.json`, which maps each server's name to its entry. It is generated output: rewritten whole on every run, never merged, and anything else left in the folder is removed. Once a project has it, `lsp-servers.py add` and `remove` and a stack kit's install keep it in step with the table; a project that never ran `plugin` gets none. If the table changed and the plugin could not be written, the table keeps its change, the command exits 1 and names `python scripts/lsp-servers.py plugin`, which brings the plugin in step. `python forge.py kit` and `init` exit 1 as well when a stack kit's install could not write the table or the plugin; the result names what was left and the command to retry.

What an entry becomes, using only the keys Claude Code documents (one unknown key makes it skip the whole file):

| Table | `.lsp.json` |
| --- | --- |
| `command` | `command`, `args`: a name or absolute path as is, a relative one under the project |
| `extensions` | `extensionToLanguage` |
| `root` | `workspaceFolder`, as `${CLAUDE_PROJECT_DIR}/<root>`, when it is not `.` |
| `init`, `settings` | `initializationOptions`, `settings`, when not empty |

A string in `init` or `settings` that holds `${scratch}` is left out with its key, because Claude Code resolves variables in `command`, `args` and `workspaceFolder` only. `requires`, `severity`, `settle`, `note` and `install` have no key there and are not written.

How Claude Code loads it, with the source of each statement:

- `claude --plugin-dir .claude/lsp/conclave-lsp` loads it for one session. `claude --help` of Claude Code 2.1.325 on the machine this was written on (2026-11-15): "`--plugin-dir <path>` Load a plugin from a directory or .zip for this session only; a folder of plugins loads each child (repeatable: `--plugin-dir A --plugin-dir B.zip`)".
- The environment variable `CLAUDE_CODE_PLUGIN_DIRS` names plugin folders for a run whose command line cannot be changed (`code.claude.com/docs/en/plugins/loading`).
- The plugin installs no server: "Your plugin configures the connection but doesn't install the server binary" (`code.claude.com/docs/en/plugins/components`). Each program must be on `PATH`; `python forge.py doctor <project> lsp` says which are missing.
- A server starts on the first edit of a file it serves, and Claude Code gives each extension to one server, the first registered (`code.claude.com/docs/en/plugins/components`). With the `laravel` preset `.php` goes to `laravel-lsp`, not to `intelephense` or `tailwindcss`. The generator writes what the table says and drops nothing; `plugin` names each shared extension and the server that gets it, and the order of the servers in the table decides.

Verified live on 2026-11-15 with Claude Code 2.1.325 on Windows 11: a headless session (`claude -p`) loaded the generated plugin, once by `--plugin-dir` and once by `CLAUDE_CODE_PLUGIN_DIRS`, started both stub servers of a two-server table (one under a `root` of its own: it was given that folder as its workspace root, and its process was started there), gave each the file it serves, and was given each server's diagnostic back. The SDK's `tests/test_lsp_kit.py` holds that run; it starts a real Claude Code session, so it runs only with `CONCLAVE_LIVE_CLAUDE=1`. Not verified: a `.zip` of the plugin, and `--plugin-url`.

The plugin gives Claude Code diagnostics while it edits. `scripts/lsp-diagnostics.py` remains the gate: it runs every server of the table on its files, whatever their extensions share, and has an exit code.

## Doctor

`python forge.py doctor <project> lsp` reports:

- each file the kit installs, `ok` or `missing`;
- `server-table`: `ok` with the servers it names (or that it holds none yet, and how to add one), `missing` with the refusal when the table does not load;
- `server:<name>` for each server: `ok` with the path its program was found at, `setup_required` with its `install` hint when it is not installed. A program given as a path is looked for in the server's `root`.

- `claude-plugin`: `ok` when `.claude/lsp/conclave-lsp/` is byte for byte what the table gives now; `unexpected`, naming `python scripts/lsp-servers.py plugin`, when it is not (the table was edited by hand since, or a file of the plugin is missing); and when no plugin was generated, `setup_required` naming that command for a project that has a `.claude` folder and a server in its table, `optional` otherwise. `optional` is shown and never counted.

`python forge.py doctor <project>` with no kit named checks the project's stack kit or the base kit as before and, when this kit is installed, adds these checks and lists the kit under `also`.

The SDK does not install this kit in itself.
