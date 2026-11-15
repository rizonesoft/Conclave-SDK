---
schema_version: 1
id: lsp-kit
domain: 04-tooling
status: active
title: "TODO-01 -- LSP kit"
---

# TODO-01 -- LSP kit

> **Goal:** A project installs one kit and its three agents can ask the stack's language servers for diagnostics: one table names the servers, one client runs them on demand, Claude Code gets them as a live plugin, Codex and Antigravity get them through an MCP bridge, and a doctor check says which server is not installed.

> **Current state:** Measured 2026-11-11. No `kits/lsp/` exists. The only language server tooling in the SDK is in the Laravel kit: `kits/laravel/templates/scripts/lsp-diagnostics.py` (677 lines), a stdlib-only stdio LSP client whose servers are a table in the code (`SERVERS`, `:325`: laravel-lsp, tailwind, intelephense), with a pre-push hook and doctor checks (`forge.py:579`). Agents are pointed at it by skill text only. RasterFold (`~/projects/RasterFold` in WSL, `b33493346141f96b6b304cd3e0c393595382f056`) wires clangd and basedpyright into Claude Code as a local plugin, `.claude/lsp/rasterfold-lsp/.lsp.json` with `.claude-plugin/plugin.json`, loaded with `--plugin-dir`; it has nothing for Codex or Antigravity. Impossible OS (`~/projects/impossible-os` in WSL, `17a762d39ccd1958cbe711901f645fd9b042e939`) runs an MCP bridge, `scripts/lsp-mcp/bridge.py` with `lsp_client.py` and five server modules, registered in `.mcp.json:7` and in the Codex user configuration.

## Inputs

- `docs/plans/2026-11-11-sdk-audit-and-roadmap.md`: the `lsp` row of the kits table (language server setup per stack for the three agents, with a doctor check).
- `kits/laravel/templates/scripts/lsp-diagnostics.py`, `kits/laravel/templates/scripts/hooks/laravel-lsp-pre-push.sh` and `kits/laravel/templates/docs/laravel-agent-tooling.md`: the client §3 generalises and the kit §4 moves onto it.
- RasterFold `.claude/lsp/rasterfold-lsp/.lsp.json` (`:2` to `:11`) and Impossible OS `scripts/lsp-mcp/` at the commits above: the sources of §5 and §6.
- -> XREF: D04 T02 §5 -- the C and C++ toolchain kit adds the clangd entry to the server table defined here

## Outcome

- `python forge.py kit <project> lsp` installs the kit; `python scripts/lsp-servers.py add <preset>` adds a stack's servers to `.conclave/lsp.json`.
- `python scripts/lsp-diagnostics.py --all <files>` reports diagnostics from every installed server in the table and says `SKIPPED` for one that is not installed.
- Claude Code, Codex and Antigravity each have a documented, tested way to reach the same servers, and `python forge.py doctor <project> lsp` reports each server and each wiring.

**Adjacency:** all=not-applicable (developer tooling: a server table, a diagnostics client and agent wiring files, with no records a user lists, exports, is notified of or reverses)

**Adjacency rationale:** The one setting is the server table, consumed by the client, the plugin generator, the bridge and the doctor, with a refusal test for each malformed entry in §2.

## Implementation Order

| Order | Section | Deliverable | Depends On | Status |
| ----- | ------- | ----------- | ---------- | ------ |
| 1 | §1 | LSP kit known to `forge.py` | -- | [x] |
| 2 | §2 | Server table `.conclave/lsp.json` with presets per stack | §1 | [x] |
| 3 | §3 | Diagnostics client that reads the server table | §2 | [ ] |
| 4 | §4 | Laravel kit moved onto the shared client | §3 | [ ] |
| 5 | §5 | Claude Code plugin generated from the server table | §2 | [ ] |
| 6 | §6 | MCP bridge for Codex and Antigravity | §3 | [ ] |
| 7 | §7 | Language server skill and document for the three agents | §5, §6 | [ ] |

## 1. LSP kit known to `forge.py`

> **Started:** 2026-11-15T00:00:09Z

The kit folder, its detection and its doctor branch.

**Phase:** 6
**Needs:** none
**Surface:** no

**Build order:**

1. Create `kits/lsp/` with `README.md` and `templates/.conclave/lsp.json`. Done when: `python forge.py kits` lists `lsp`.
2. Teach `forge.py` the kit. Done when: the checkpoint passes.

- [x] Create `kits/lsp/README.md` and `kits/lsp/templates/.conclave/lsp.json` holding `{"schema_version": 1, "servers": []}`. Done when: `python forge.py kits` prints `lsp`, a test in a new `tests/test_lsp_kit.py` loads the template as that JSON object, and the list `tests/test_forge.py:291` expects of `forge.list_kits()` names `lsp`.
- [x] Add `lsp` to `KIT_ORDER` in `forge.py` before `laravel`, and to the kit names in the usage docstring (the `doctor` line), the `--kit` help of `init`, the help of `kit` and the docstring of `apply_kit`. Done when: tests in `tests/test_lsp_kit.py` install through `init --kit lsp` and through `kit <project> lsp` on the command line and find `.conclave/lsp.json`, find the file recorded under `lsp` in `.conclave/kits.json`, find a second install changing nothing, and find a project's own `.conclave/lsp.json` kept byte for byte and listed under `preserved`. Cheaper substitute: a kit `forge.py` installs without recording must fail the record test, because `diff` and `update` would then not know the file.
- [x] Detect the kit in `installed_kits` of `forge.py` by `.conclave/lsp.json`. Done when: a test in `tests/test_lsp_kit.py` finds `lsp` in `check_repo(...)["kits"]` after an install and not before, and not in a project that has only the Laravel kit.
- [x] Add an `lsp` branch to `doctor_repo` in `forge.py` that checks each file the kit installs is present, read from the kit's `templates/` so a file added by a later section is checked without a second list (the per-server checks come in §2). Done when: tests in `tests/test_lsp_kit.py` find `ok` for each file on a fresh install through `forge.py doctor <project> lsp`, `missing` with `--strict` exit 3 once `.conclave/lsp.json` is deleted, and a check for a file added to a scratch copy of the kit.
- [x] Check the kit when no kit is named, in `doctor_repo` of `forge.py`: `forge.py doctor <project>` selects Laravel, WordPress or base as it does today and, when `installed_kits` finds `lsp`, appends the `lsp` branch's checks and lists the kit under `also` in the report. Done when: tests in `tests/test_lsp_kit.py` run `forge.py doctor <project>` with no kit on a base project with the kit (the base checks and the `lsp` checks, `also` naming `lsp`), on one without it (no `also`, no `lsp` check) and on a Laravel project with it (the Laravel checks, then the `lsp` checks), and the usage docstring's `doctor` line says what the bare form checks.
- [x] List the kit in `README.md` (the kits sentence and table), `kits/README.md` (the install block and the Layout table) and `AGENTS.md` (Purpose, and the sentence naming the kits the SDK does not install in itself). Done when: the three name it with table rows within 120 characters, each saying what the kit holds so far (the server table; the client, plugin and bridge come in §2 to §7), and `python -m unittest tests.test_forge -k markdown_table` passes.
- [x] Commit: `lsp: kit skeleton known to forge.py`

**Corrected 2026-11-15 (validation):** measured today. `forge.list_kits()` lists any folder under `kits/` with a `templates/` folder and `tests/test_forge.py:291` asserts the exact list, so that test changes with the kit. The items named no test file; they go in a new `tests/test_lsp_kit.py`, not `tests/test_forge.py` (over ten minutes to run), so the checkpoint names it; before: "`python -m unittest discover -s tests -p test_forge.py` ends `OK`". "The kit names in the usage docstring and the `--kit` help texts" are four places, now named. The install item proved only that the file lands: the install record, a second install and a project's own table are what the other kits' installs are held to (`tests/test_kit_install.py`), so they are in. The doctor item would have needed a hand-kept file list that §2 to §7 each extend: it reads the kit's `templates/`. `AGENTS.md` also names the kits the SDK does not install in itself, where `lsp` belongs. Removing `lsp` from `KIT_ORDER` does not make an install fail (`init --kit` appends a kit that is not in the order), so the checkpoint's failure case is the one that does: removing the detection.

**Corrected 2026-11-15 (plan review):** one gap, taken. `doctor_repo(project, None)` selects Laravel, WordPress or base (`forge.py:1886` to `:1892`), so `forge.py doctor <project>` would never have checked an installed LSP kit, and no later section owned that. The bare form now appends the `lsp` checks when the kit is installed. Decision (default, cheap to reverse: one loop): only `lsp` joins the bare form, because its checks read files and `PATH`; the `todo` and `reviewer` branches start other programs (Codex's app-server, the reviewer CLIs) and stay behind their kit name, which is noted in `todo/findings.md` as an open question for the bare form.

**Test checkpoint:** `python -m unittest tests.test_lsp_kit` ends `OK`; removing the `.conclave/lsp.json` detection from `installed_kits` makes the detection test fail.

> **Verified:** 2026-11-15 | §1 | 8a75c584c044defd9015a2cbd99fd796464824da
> **Review:** `docs/reviews/d04-t01-s1.json`

## 2. Server table `.conclave/lsp.json` with presets per stack

> **Started:** 2026-11-15T00:54:10Z

One table names every language server the project uses: its command, the file extensions it serves and how to install it. Presets fill it for a stack so a project does not write entries by hand.

**Phase:** 6
**Needs:** none
**Surface:** no

**Build order:**

1. Write `load_servers` in `kits/lsp/templates/scripts/lib/lsp_table.py` and the presets file. Done when: a table with one preset loads.
2. Add `scripts/lsp-servers.py` and the doctor checks. Done when: the checkpoint passes.

- [x] Add `load_servers(root)` to `kits/lsp/templates/scripts/lib/lsp_table.py`, reading `.conclave/lsp.json` (`{"schema_version": 1, "servers": [...]}`) into checked entries. Required keys: `name` matching `[a-z0-9][a-z0-9-]*` and unique; `command`, a non-empty list of non-empty strings (the program, then its arguments); `extensions`, a non-empty object from a file suffix starting with a dot to the LSP language id the server is told for it (`{".c": "c", ".h": "c"}`); `install`, a one-line hint. Optional keys, each with the default the client uses: `root` (a folder inside the project, `.`), `requires` (a file inside the project that must exist for the server to be run, none), `init` (an object sent as `initializationOptions`, `{}`), `settings` (an object answered to `workspace/configuration`, none), `severity` (`error` or `warning`, the least severity that fails a run, `error`), `settle` (seconds to wait for diagnostics, a number from 1 to 120, 5) and `note` (one line). Done when: a test for each fault reads a `TableError` naming `.conclave/lsp.json`, the entry and the key: a file that is missing, unreadable, not UTF-8 or not JSON; a document that is not an object; a wrong `schema_version`; an unknown key at either level; a missing required key; `servers` that is not a list; an entry that is not an object; a duplicate or malformed `name`; a `command` that is a string, is empty or holds an empty string; `extensions` that is a list, is empty, or holds a suffix with no dot or a language that is not a non-empty string; an `install` of more than one line; a `root` or `requires` that is absolute or leaves the project with `..`; a `severity` outside the two; a `settle` that is not a number or is out of range; an `init` or `settings` that is not an object. Cheaper substitute: accepting a `command` string and splitting it on spaces must fail, because a path with a space breaks.
- [x] Create `kits/lsp/templates/scripts/lib/lsp_presets.json`: `{"schema_version": 1, "servers": {<name>: <entry without name>}, "presets": {<preset>: {"servers": [...], "root_marker": <file>}}}`. The catalogue holds each server once with settings that fit any project: `clangd`, `basedpyright` (`basedpyright-langserver --stdio`), `intelephense` (`--stdio`), `typescript` (`typescript-language-server --stdio`), `tailwindcss` (`tailwindcss-language-server --stdio`) and `laravel-lsp`, each with the server's own documented install command and no `requires`, `init` or `settings` that belongs to one framework. A preset's `servers` are names, or objects `{"server": <name>, <keys that override the catalogue entry>}` for what only that stack wants. Presets: `cpp` (`clangd`), `python` (`basedpyright`), `php` (`intelephense`), `web` (`typescript`, `tailwindcss`) and `laravel` (`laravel-lsp`, `intelephense`, `tailwindcss`), the `laravel` preset carrying as overrides the `init`, `settings`, `severity`, `settle` and `requires` the Laravel kit's client holds for its three servers today (`kits/laravel/templates/scripts/lsp-diagnostics.py:325`) and `"root_marker": "artisan"`. Done when: `load_presets()` in `lib/lsp_table.py` holds every catalogue entry and every resolved preset entry to the same checks as `load_servers`; tests refuse a preset that names a server the catalogue lacks, an override of `name`, and an unknown key at any level; and tests assert the resolved entries, key by key, for `web` (Tailwind with no `requires` and no Laravel `init`, Intelephense untouched by Laravel settings in `php`) and for `laravel` (each override present). Cheaper substitute: asserting only the server names of a preset must fail review, because the `web` preset would pass while carrying Laravel's prerequisites.
- [x] Resolve a preset's root when it is added, in `resolve_preset(root, preset, app_root=None)` of `lib/lsp_table.py`: a preset with a `root_marker` finds the folder holding that file at the project root, then in `platform/`, then in the first other immediate child folder in name order (the order `forge._find_laravel_app_root` uses), and writes that folder as each server's `root`, with `requires` read relative to `root`; `--root <folder>` on `add` names it outright; no folder holding the marker is a refusal naming the marker and `--root`. Done when: tests add `laravel` to a project with `artisan` at the root, under `platform/` and under another child folder, reload the written table with `load_servers` and find `root` and `requires` naming files that exist; a project with no `artisan` is refused with nothing written; and `--root` wins over discovery.
- [x] Create `kits/lsp/templates/scripts/lsp-servers.py` with `list`, `add <preset> [--root <folder>]` and `remove <name>`: `list` prints one line per server in the table (name, program, suffixes) and the presets on offer with their servers, and writes nothing; `add` appends a preset's resolved servers to the table, leaving an entry the project already has by that name untouched and printing which were added and which kept; `remove` deletes the entry of that name and prints it. Exit 2 with one line for an unknown preset, an unknown server name and a table that does not load. Done when: tests run the script as a program and assert its output and exit for `list` on the shipped empty table (no server, the five presets) and on a populated one, with the table's bytes unchanged after `list`; adding to the empty table (the added names printed); adding a preset twice (every name printed as kept, the file's bytes and modification time unchanged); a project's edited entry kept as it is and printed as kept; `laravel` after `php` adding only what is new; removing a server; and an unknown preset, an unknown name and a malformed table each refused by name with nothing written. Cheaper substitute: an `add` that replaces an existing entry must fail the edited-entry test.
- [x] Write the table safely in `write_servers(root, servers)` of `lib/lsp_table.py`: a temporary file in the table's folder, flushed, then `os.replace`, as indented JSON ending in a newline, and only when the content changes; a failure at either step is one line naming `.conclave/lsp.json` and the system's reason, exit 1, with the table as it was and no temporary file left. Done when: tests make the temporary write fail and make `os.replace` fail, and each finds the table's bytes unchanged, the folder holding no other file, and the command line printing that line with exit 1.
- [x] Add per-server checks to `_doctor_lsp` in `forge.py`, after its file checks: the table loads under `load_servers` (the kit's module compiled from the SDK, as `_doctor_reviewer` does at `forge.py:1692`), reported as `server-table`; and each server is a check named `server:<name>`, `ok` with the path `shutil.which` finds for its program, `setup_required` with its `install` hint when none is found. Done when: tests in `tests/test_lsp_kit.py` cover a malformed table (`server-table` `missing` with the refusal, and no `server:` check), the empty table (`ok`, saying it holds no server and naming `lsp-servers.py add`), an installed stub server and a missing one, and the bare `forge.py doctor <project>` showing the same checks.
- [x] Add `kits/lsp/templates/scripts/tests/test_lsp_table.py` and the suite `kit-lsp` to `SUITES` in `forge.py`. Done when: `python forge.py check-all --only kit-lsp` passes on Windows and in WSL and `tests.test_check_all` passes, which holds every test folder to a suite.
- [x] Bring `kits/lsp/README.md` up to date: the table's keys with their defaults, the presets, the three `lsp-servers.py` commands and the doctor's new checks. Done when: a test in `tests/test_lsp_kit.py` finds every key `load_servers` accepts and every preset name in the README, and the README lists every file under `kits/lsp/templates/`.
- [x] Commit: `lsp: server table with presets per stack`

**Corrected 2026-11-15 (validation):** measured today against the client the table must serve (`kits/laravel/templates/scripts/lsp-diagnostics.py:325`) and RasterFold's plugin file (`.claude/lsp/rasterfold-lsp/.lsp.json` at `b33493346141`). The entry was `{"name", "command", "extensions", "language", "install"}` with `extensions` a list: one `language` cannot serve clangd (`.c` is `c`, `.cpp` is `cpp`) and both consumers need the language per suffix (`textDocument/didOpen` in §3, `extensionToLanguage` in §5), so `extensions` is that map and `language` is gone. The Laravel client holds six more settings per server (`root`, `requires`, `init`, `configuration`, `severity`, `settle`) that §3 and §4 must keep or the Laravel servers change behaviour; the table has them as optional keys with defaults, decided here once so the format does not change under §3. The presets repeated entries (the `laravel` preset is "`laravel-lsp`, plus `php` and the Tailwind server"): they are names over one catalogue. The fault list named four faults; a file that cannot be read, structural faults and paths that leave the project are added, as the tool pin file's review found for the same shape (`D04 T02 §1`). `lsp-servers.py` had no outcome for an unknown server name or a table that does not load. "Run it from `tests/test_forge.py`" is a suite in `forge.SUITES` since `D01 T02 §1`. The doctor's line reference moved (`forge.py:454` is `:1692`). The README the kit ships described only §1.

**Corrected 2026-11-15 (plan review):** four gaps, all taken. (1) The catalogue gave Tailwind and Intelephense the Laravel client's prerequisites and settings (`resources/css/app.css`, `composer.json`, Laravel's diagnostic settings), so the `web` and `php` presets would have skipped or misconfigured them elsewhere: the catalogue holds general entries, a preset overrides what its stack wants, and tests assert the resolved entries. (2) The Laravel client finds its app at the root, in `platform/` or in another child folder (`discover_app_root`), and the table's `root` defaulted to `.` with nothing to set it: `add` resolves the root from the preset's `root_marker` and writes it, with `--root` to name it. (3) A failed write of the table had no outcome: it is its own item, with the two failures injected. (4) No test ran `list` or read what `add` and `remove` print: the command line tests assert output as well as exit and file state.

**Corrected 2026-11-15 (round 1):** four findings, all fixed. A `root` of `./` crashed the loader, and a `requires` of `.` crashed it in place of a refusal: `.` and `./` are the project itself for `root` and a refusal for `requires`. The doctor looked a server's program up with `shutil.which`, which on Windows tries the working directory first, and fell back to any regular file: a program in an unrelated working directory, or a file with no execute permission, read `ok`. `find_program` in `lib/lsp_table.py` is now the one lookup (a bare name on `PATH` only; a name with a folder in it from the server's `root`; a file the system will execute), used by the doctor and, from §3, by the client. The `laravel` preset left out the storage folder the Laravel client gives Intelephense at run time: the preset carries it as the placeholder `${scratch}`, which §3 replaces with a temporary folder outside the repository.

**Test checkpoint:** `python -m unittest discover -s kits/lsp/templates/scripts/tests` ends `OK`; making `add` replace an existing entry makes the edited-entry test fail.

> **Verified:** 2026-11-15 | §2 | 30de93eebd6e7ea27abfb09ba5d843e4bfd25a3a
> **Review:** `docs/reviews/d04-t01-s2.json`

## 3. Diagnostics client that reads the server table

> **Started:** 2026-11-15T03:16:46Z

The Laravel kit's client already speaks LSP over stdio with the standard library. Its server list moves out of the code into the table, and the client becomes the LSP kit's.

**Phase:** 6
**Needs:** none
**Surface:** no

**Build order:**

1. Lift the Laravel kit's LSP client into `kits/lsp/templates/scripts/lib/lsp_client.py` and its command line into `kits/lsp/templates/scripts/lsp-diagnostics.py`, reading the server table. Done when: `--all` runs every server in a fixture table.
2. Keep the exit rules and bound the server process. Done when: the checkpoint passes.

- [x] Create `kits/lsp/templates/scripts/lib/lsp_client.py` from the `Client` class of `kits/laravel/templates/scripts/lsp-diagnostics.py` (`:74` to `:272`): a stdio LSP client that starts one server from a table entry (`find_program` for its program, its `root` as the working directory and workspace, its `init` as `initializationOptions`, its `settings` answered to `workspace/configuration` and sent with `workspace/didChangeConfiguration`), opens documents with the language id the entry's `extensions` give them, and collects `textDocument/publishDiagnostics`. It is a module of its own because the MCP bridge of §6 drives servers through the same code. Done when: tests in a new `kits/lsp/templates/scripts/tests/test_lsp_diagnostics.py`, with a stub language server written for them that logs what it receives, find the stub's working directory and workspace folder to be the entry's `root`, its `initializationOptions` the entry's `init`, a `workspace/didChangeConfiguration` carrying `settings`, each `workspace/configuration` request answered by section from `settings`, each document opened with its language id, and the diagnostics the stub publishes for a file read back.
- [x] Give every server of a run one of six results in `lib/lsp_client.py` and `lsp-diagnostics.py`, none of which can pass for another: `ok` (every file it was sent was answered), `idle` (no file of its kind in the input), `missing` (its program is not installed), `skipped` (its `requires` file is absent), `failed` (it could not be contained, answered `initialize` with an error or not at all, ended before answering, or was ended at a limit) and `partial` (it ran, and some file was not answered or could not be read: each is named). A `failed` or `partial` result carries its reason. Done when: tests with stub servers cover an `initialize` error response, no `initialize` answer, a server that exits after `initialize`, one that answers one file of two, a file that cannot be read (named, never opened as an empty document), a containment refusal and an output-limit stop, each with its result and reason and none reported `ok`. Cheaper substitute: treating any response to `initialize` as success must fail the error-response test.
- [x] Replace the `SERVERS` table (`lsp-diagnostics.py:325`) with `load_servers` in `kits/lsp/templates/scripts/lsp-diagnostics.py`, so `--server <name>` (repeatable) and `--all` accept the names in `.conclave/lsp.json`, with the Laravel client's `--severity`, `--settle`, `--timeout`, `--json` and `--verbose`. Done when: a test with a stub server in a fixture table collects its diagnostics for a file through the command line, as text and as JSON, and `--server` with a name the table lacks is refused by name with exit 2. Cheaper substitute: keeping the Laravel server names as a fallback in the code must fail review; the table is the only list.
- [x] Take the input from git or from paths in `lsp-diagnostics.py`: `--staged`, `--worktree`, `--commit <sha>`, or paths. The git forms read names with `-z` (NUL-separated, never quoted or escaped) and check git's exit: a failed git command, an unknown revision among them, is one line with git's reason and exit 2, never an empty input. Done when: tests in a fixture repository cover each of the three forms, a file whose name is not ASCII and one with a space in each, a deleted file left out, an unknown revision refused with exit 2, and a folder that is not a repository refused with exit 2.
- [x] Send each file only to the servers that serve it, in `lsp-diagnostics.py`: a file goes to a server when its name ends with one of the server's `extensions` suffixes (the longest matching suffix gives the language id, so `.blade.php` is not `.php`) and it lies under the server's `root`. Done when: tests with two stub servers find a `.py` file sent to one and not the other, a `.blade.php` file opened as `blade` by a server that also lists `.php`, and a file outside a server's `root` not sent to it.
- [x] Honour each entry's run settings in `lsp-diagnostics.py`: `requires` (a file under `root` that must exist, else the server is `SKIPPED -- requires <file>`, which is not the same as not installed), `severity` (the least severity that makes the run fail, overridden by `--severity`), `settle` (how long after the last file is answered the client keeps listening, overridden by `--settle`) and `note` (printed beside the server's summary). Done when: tests cover a server skipped for a missing `requires` file; a warning that fails a `warning` server and passes an `error` one, and `--severity` overriding both; a stub that publishes a second, later set of diagnostics that a long `settle` collects and a short one does not, from the entry and from `--settle`; and the `note` in the text output.
- [x] Replace `${scratch}` in an entry's `init` and `settings` (any string value, at any depth) with a temporary folder outside the repository that the client makes for the run and removes afterwards, as `D04 T01 §2` decided for Intelephense's `storagePath`. Done when: a test finds the stub receiving a folder that exists during the run, lies outside the project and is gone after it, also when the server is ended at a limit.
- [x] Set the exit code from the results, the same with and without `--json`: 0 when every server that ran is `ok` or `idle` and no diagnostic is at or above its server's threshold; 1 when a diagnostic is, or a server is `failed` or `partial` (a check that did not finish is not a pass); 2 for bad usage, an unknown server name, a failed git command or a table that does not load; 3 when no requested server could check anything (every one `missing`, `skipped` or `failed`). The text form prints `SKIPPED -- not installed. Install: <hint>`, `SKIPPED -- requires <file>`, `FAILED -- <reason>` and `PARTIAL -- <reason>` lines (`:648` to `:670`); with `--json` every run that gets past its arguments prints one JSON document on standard output (`servers` with each result and reason, `diagnostics`, `failing`, `exit`), an empty input and an all-missing run included. Done when: tests run each of these through the command line in both forms and find the same exit: clean, a failing diagnostic, one missing among two, all missing (3), an unresponsive server alone (3), a partial server beside a clean one (1), a failed server beside a clean one (1), and no file of any server's kind (0, saying so), with the JSON parsed in every case.
- [x] Contain and bound the server in `lib/lsp_client.py`, in the shape `D04 T02 §1` settled for `toolchain-check.py`: started with no shell and no console window, in a job object on Windows (started suspended, resumed only once it is in the job) and its own session on POSIX; its whole process tree ended in one `finally` on every way out (a clean run, the time limit, a byte limit, an error, an interrupt); a server that cannot be contained is not run. At most 64 MiB is read from a server per run and no single message may exceed 32 MiB, standard error is read and counted too (kept to its last 64 KiB, shown with `--verbose`), and either limit ends the server with a message naming it. Done when: tests with stub servers find the child of a server that completed normally gone; both processes gone after a server that starts a child and never answers; a stopped run and both processes gone for one that floods standard output, one that floods standard error, and one that announces a message over the limit; a server whose launcher exits while its child holds the pipe ended with its child; a server that cannot be contained (the job refused) never run and reported `failed`; and an interrupt during a run leaving no process. Every flooding stub stops by itself after a fixed number of bytes. Cheaper substitute: killing only the direct child must fail the child-gone assertions.
- [x] Refuse an empty table in `lsp-diagnostics.py` with one line naming `python scripts/lsp-servers.py add <preset>` and exit 2. Done when: a test with the shipped empty table finds that line and the exit.
- [x] Detect the Laravel kit by a file only it installs, in `installed_kits` of `forge.py`: `scripts/lsp-diagnostics.py` is now a file of this kit too, and a project with the LSP kit alone would read as a Laravel project (`forge.py:226`). Done when: a test in `tests/test_lsp_kit.py` finds `laravel` absent from `check_repo(...)["kits"]` for a project with only the LSP kit and present for a Laravel install.
- [x] Add `test_lsp_diagnostics.py` to the kit's tests (the `kit-lsp` suite) and list the new files, the client's commands, results, exit codes, limits and the `${scratch}` behaviour in `kits/lsp/README.md`. Done when: `python forge.py check-all --only kit-lsp` passes on Windows and in WSL and the README test of `tests/test_lsp_kit.py` passes.
- [ ] Commit: `lsp: diagnostics client reads the server table`

**Corrected 2026-11-15 (validation):** measured today against the Laravel client (`kits/laravel/templates/scripts/lsp-diagnostics.py`, 677 lines) and what §2 decided. (1) The client was one file; §6's bridge is to drive servers "through the client code of §3", so the protocol client is a module, `lib/lsp_client.py`, and `lsp-diagnostics.py` is its command line. (2) §2 gave the table `root`, `requires`, `init`, `settings`, `severity`, `settle`, `note`, the `${scratch}` placeholder and `find_program`; the items here named only the server list and the suffix match, so the rest had no owner. (3) The suffix item said "whose `extensions` include its suffix": `extensions` is a map to language ids since §2, the longest suffix wins, and a file must also lie under the server's `root`. (4) The Laravel client reports a server whose `requires` file is missing as not installed (`:488`), which sends the reader to an install command for a server that is installed: it is its own outcome. (5) The containment item is written in the shape three reconciliations of `D04 T02 §1` settled (a child made before containment, a launcher that exits first, containment that fails, an interrupt). (6) `installed_kits` reads `scripts/lsp-diagnostics.py` as the Laravel kit (`forge.py:226`); from this section it is the LSP kit's file, so the detection moves to a file only the Laravel kit installs. The Laravel kit keeps its own copy of the client until §4 moves it onto this one: a project with both kits keeps whichever was installed first until then. (7) The test file was its own item with "the quick suite runs it": the kit's tests are the `kit-lsp` suite since §2.

**Corrected 2026-11-15 (plan review):** six gaps, all taken, each a place where the Laravel client being lifted reports a check that did not happen as a pass. (1) It takes any response to `initialize` as success and reports `ok` after a server dies or leaves files unanswered: a server now has six results, and `failed` and `partial` cannot read as `ok`. (2) Its `--json` branch returns 0 when every server is missing and its empty-input branch prints text: the exit is set once from the results and every run prints JSON when asked. (3) Its git helper ignores git's exit and splits names on newlines, so an unknown revision is an empty input and a quoted non-ASCII name is dropped: git is checked and read with `-z`. (4) Its `open` swallows a read error and returns a URI: an unread file is named and makes its server `partial`. (5) Nothing proved `workspace/didChangeConfiguration`, the working directory, `settle` or the `note`: each has an assertion. (6) The containment proof lacked a normal completion, a containment refusal, the single-message limit and standard error, which the Laravel client lets through unbounded with `--verbose`. Decision (default, cheap to reverse: one line of the exit rule): a `failed` or `partial` server makes the run exit 1 even beside clean servers, because a pre-push check that could not finish must not let the push through.

**Test checkpoint:** `python -m unittest discover -s kits/lsp/templates/scripts/tests` ends `OK`; sending every file to every server makes the suffix test fail. Killing only the direct child makes the child-gone tests fail.

## 4. Laravel kit moved onto the shared client

Two kits would otherwise install two different files at `scripts/lsp-diagnostics.py`. The Laravel kit keeps its hook and its skill, takes the client from the LSP kit and adds its servers to the table.

**Phase:** 6
**Needs:** none
**Surface:** no

**Build order:**

1. Remove the client from the Laravel kit and have the kit bring the LSP kit's. Done when: a fresh Laravel install has the shared client and a table with the `laravel` preset.
2. Update the hook, the doctor and the document. Done when: the checkpoint passes.

- [ ] Delete `kits/laravel/templates/scripts/lsp-diagnostics.py` and drop it from the Laravel list in `kit_plan` of `forge.py` (`forge.py:234`). Done when: `git ls-files kits/laravel/templates/scripts/lsp-diagnostics.py` prints nothing.
- [ ] Make `apply_kit` in `forge.py` install the `lsp` kit's files with the Laravel kit and add the `laravel` preset to a table it created, leaving a table the project already has untouched and reported under `merge_needed`. Done when: a test on a fresh Laravel fixture finds `scripts/lsp-diagnostics.py`, a table holding `laravel-lsp`, `intelephense` and the Tailwind server, and `lsp` in `installed_kits`. Cheaper substitute: writing the preset into an existing table must fail the untouched-table test.
- [ ] Change `kits/laravel/templates/scripts/hooks/laravel-lsp-pre-push.sh` (`:13` to `:19`) to name the servers as the table names them, keeping its rule that exit 3 prints SKIPPED and exits 0. Done when: `tests/test_forge.py`'s Laravel test runs the hook against stub servers and passes.
- [ ] Replace the three server checks in the Laravel branch of `doctor_repo` (`forge.py:579`) with the `lsp` branch's table checks. Done when: `python forge.py doctor <fixture> laravel` lists the three servers with the same statuses as before.
- [ ] Update `kits/laravel/templates/docs/laravel-agent-tooling.md` (`:22` to `:37`), `kits/laravel/README.md` and the `laravel-boost` skill in the three agent folders to name the table. Done when: none of them describes a server list in the client's code.
- [ ] State in `kits/laravel/README.md` what an existing Laravel project does: it keeps its own client until it runs `forge.py update`, which reports the file as `project-only`. Done when: the README carries that paragraph.
- [ ] Commit: `laravel: language servers through the LSP kit's client and table`

**Test checkpoint:** `python -m unittest discover -s tests -p test_forge.py` ends `OK`; restoring the old client's built-in server list makes the Laravel table test fail.

## 5. Claude Code plugin generated from the server table

Claude Code can run language servers live through a local plugin. RasterFold wrote its plugin by hand; the kit generates one from the table, so the table stays the only list.

**Phase:** 6
**Needs:** none
**Surface:** no

**Build order:**

1. Add `plugin` to `kits/lsp/templates/scripts/lsp-servers.py`. Done when: it writes the plugin folder for a table.
2. Record how Claude Code loads it and check it in the doctor. Done when: the checkpoint passes.

- [ ] Add `plugin` to `lsp-servers.py`: write `.claude/lsp/<project>-lsp/.lsp.json` (one entry per server with its command, arguments and an `extensionToLanguage` map, paths under `${CLAUDE_PROJECT_DIR}`) and `.claude/lsp/<project>-lsp/.claude-plugin/plugin.json`, both through a temporary file and `os.replace` (RasterFold `.lsp.json:2` to `:11`). Done when: a test on a two-server table reads both files back and finds each server and each extension. Cheaper substitute: a hand-written plugin committed to the template must fail review, because it is a second server list.
- [ ] Regenerate, never merge, in `plugin`: the plugin folder is generated output, rewritten whole on every run, and `lsp-servers.py add` and `remove` run `plugin` after changing the table. Done when: a test removes a server and finds it gone from `.lsp.json`.
- [ ] Record in `kits/lsp/README.md` how Claude Code loads a local LSP plugin for an interactive session and for an unattended one (RasterFold passes `--plugin-dir .claude/lsp/rasterfold-lsp`, `scripts/unattended-run.sh:70`), checked against the Claude Code documentation and `claude --help` on this machine, with the version. Done when: the README quotes the flag or setting from its source.
- [ ] Add a `claude-plugin` check to the `lsp` branch of `doctor_repo` in `forge.py`: the plugin's `.lsp.json` exists and names exactly the servers in the table. Done when: tests find `ok` after `plugin`, `setup_required` naming `lsp-servers.py plugin` before it, and `unexpected` when the two lists differ.
- [ ] Commit: `lsp: Claude Code plugin generated from the server table`

**Test checkpoint:** `python -m unittest discover -s kits/lsp/templates/scripts/tests` ends `OK`; leaving a removed server in the generated `.lsp.json` makes its test fail.

## 6. MCP bridge for Codex and Antigravity

Codex and Antigravity have no LSP plugin. Impossible OS reaches its servers from Codex through an MCP server that fronts them. The bridge is lifted, reading the same table.

**Phase:** 6
**Needs:** none
**Surface:** no

**Build order:**

1. Measure Impossible OS's `scripts/lsp-mcp/` and decide what is generic. Done when: the file list and sizes are in `kits/lsp/README.md`.
2. Lift the bridge onto the table and document its registration. Done when: the checkpoint passes.

- [ ] List in `kits/lsp/README.md` each file under Impossible OS `scripts/lsp-mcp/` at `17a762d39ccd1958cbe711901f645fd9b042e939` with its line count, what it does and whether it is generic or names that project (its five `servers/*_server.py` modules, `lsp_client.py`, `bridge.py`). Done when: every file has a row.
- [ ] Create `kits/lsp/templates/scripts/lsp-mcp-bridge.py`: an MCP server over stdio, standard library only, offering read-only tools (diagnostics for a file, definition, references, hover) that it answers by driving the table's servers through the client code of §3. Done when: a test speaks MCP to it with a stub language server and reads diagnostics back. Cheaper substitute: a bridge that shells out to `lsp-diagnostics.py` per call must fail review if it restarts the server every call; the bridge keeps each server running.
- [ ] Keep the bridge read-only: refuse any LSP method that edits (rename, code action apply, formatting, workspace edit), as Impossible OS's `_FORBIDDEN_LSP_METHODS` does in `lsp_client.py`. Done when: a test asking for a rename gets an MCP error and the stub server never receives the request.
- [ ] End every server process when the bridge exits or its stdin closes, whole tree, and bound each server's unread output. Done when: a test closes the bridge's stdin and finds the stub server and its child gone within 10 seconds.
- [ ] Document the registration for each agent in `kits/lsp/templates/docs/language-servers.md`: the project `.mcp.json` entry, the Codex configuration entry and the Antigravity one, each checked against that CLI's documentation on this machine with its version. Done when: the document has the three snippets and names where each was confirmed. Cheaper substitute: an entry format written from memory must fail review.
- [ ] Add an `mcp-bridge` check to the `lsp` branch of `doctor_repo` in `forge.py`: `scripts/lsp-mcp-bridge.py` is present and, when the project has an `.mcp.json`, it registers the bridge. Done when: tests cover registered, not registered (`setup_required` with the snippet's location) and no `.mcp.json`.
- [ ] Commit: `lsp: MCP bridge that serves the table's servers to Codex and Antigravity`

**Test checkpoint:** `python -m unittest discover -s kits/lsp/templates/scripts/tests` ends `OK`; letting a rename through makes the read-only test fail.

## 7. Language server skill and document for the three agents

The wiring is no use if an agent does not know it is there. A skill in each agent folder says when to ask the servers and how.

**Phase:** 6
**Needs:** none
**Surface:** no

**Build order:**

1. Write `kits/lsp/templates/docs/language-servers.md`. Done when: every command in it exists.
2. Add the `language-servers` skill in the three agent folders. Done when: the checkpoint passes.

- [ ] Write `docs/language-servers.md` in the kit: add a preset, generate the plugin, register the bridge, run diagnostics on changed files, and what SKIPPED means. Done when: a test extracts every `lsp-servers.py` and `lsp-diagnostics.py` command in it and finds each in that script's argument parser.
- [ ] Create `kits/lsp/templates/.claude/skills/language-servers/SKILL.md`: run diagnostics on the files a change touched before calling it done, treat an error diagnostic as a failed check and never edit a file to silence one. Done when: the frontmatter has `name` and `description` and the body names `scripts/lsp-diagnostics.py`.
- [ ] Create the Antigravity and Codex copies under `.agents/skills/language-servers/` and `.codex/skills/language-servers/` (with `agents/openai.yaml` for Codex), each naming how that agent reaches the servers (the bridge). Done when: `python forge.py doctor <fresh install> lsp` reports the skill `ok` in all three folders.
- [ ] Fill `kits/lsp/README.md` with what the kit installs and what each agent gets. Done when: it lists every file under `kits/lsp/templates/`.
- [ ] Add a fresh-install test to `tests/test_forge.py`: `init --kit lsp`, `lsp-servers.py add python` with a stub server on `PATH`, then the doctor and the kit's own tests in the installed copy. Done when: it passes and fails when a template file is removed from a scratch copy of the kit.
- [ ] Commit: `lsp: skill and document for the three agents`

**Test checkpoint:** `python -m unittest discover -s tests -p test_forge.py` ends `OK`; naming a command in `docs/language-servers.md` that the scripts lack makes the document test fail.

## Verification

- A scratch project with `init --kit lsp`, the `python` preset and basedpyright installed reports a planted type error through `python scripts/lsp-diagnostics.py --all <file>` and through the MCP bridge.
- A fresh Laravel install passes `python forge.py doctor <project> laravel` with the shared client.
- `python -m unittest discover -s tests` passes.
- `python scripts/todo-graph.py validate` and `python scripts/todo-graph.py plan --check` pass.
