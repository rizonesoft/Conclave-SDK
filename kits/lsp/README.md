# LSP kit

Additive overlay that gives a project's three agents (Antigravity, Claude Code and Codex) the stack's language servers. One table, `.conclave/lsp.json`, names the servers; everything else in the kit reads it.

The kit is being built in sections (`todo/04-tooling/TODO-01-lsp-kit.md`). What it installs today:

| File | What it is |
| --- | --- |
| `.conclave/lsp.json` | The server table, seeded empty: `{"schema_version": 1, "servers": []}` |
| `scripts/lsp-servers.py` | `list`, `add <preset>` and `remove <name>` for the table |
| `scripts/lib/lsp_table.py` | The table's rules: `load_servers`, the presets, the write |
| `scripts/lib/lsp_presets.json` | The catalogue of servers and the presets per stack |
| `scripts/tests/test_lsp_table.py` | The kit's own tests |

The table is the project's own file from the first install: `forge.py` never overwrites it, and a project that already has one keeps it byte for byte.

Still to come, each reading the same table: the diagnostics client `scripts/lsp-diagnostics.py` (D04 T01 §3), a Claude Code plugin generated from the table (§5), an MCP bridge for Codex and Antigravity (§6), and the `language-servers` skill and document (§7).

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

The value `${scratch}` in `init` or `settings` stands for a temporary folder outside the repository that the diagnostics client (§3) makes for the run and removes afterwards: the `laravel` preset gives it to Intelephense as its `storagePath`, so the server's index never lands in the project. Anything else in the file (an unknown key, a `command` given as one string, a duplicate name) is refused by every tool that reads the table, with a message naming the file, the server and the key.

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

## Doctor

`python forge.py doctor <project> lsp` reports:

- each file the kit installs, `ok` or `missing`;
- `server-table`: `ok` with the servers it names (or that it holds none yet, and how to add one), `missing` with the refusal when the table does not load;
- `server:<name>` for each server: `ok` with the path its program was found at, `setup_required` with its `install` hint when it is not installed. A program given as a path is looked for in the server's `root`.

`python forge.py doctor <project>` with no kit named checks the project's stack kit or the base kit as before and, when this kit is installed, adds these checks and lists the kit under `also`.

The SDK does not install this kit in itself.
