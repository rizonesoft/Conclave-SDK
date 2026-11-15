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
| 1 | §1 | LSP kit known to `forge.py` | -- | [ ] |
| 2 | §2 | Server table `.conclave/lsp.json` with presets per stack | §1 | [ ] |
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

- [ ] Create `kits/lsp/README.md` and `kits/lsp/templates/.conclave/lsp.json` holding `{"schema_version": 1, "servers": []}`. Done when: `python forge.py kits` prints `lsp`, a test in a new `tests/test_lsp_kit.py` loads the template as that JSON object, and the list `tests/test_forge.py:291` expects of `forge.list_kits()` names `lsp`.
- [ ] Add `lsp` to `KIT_ORDER` in `forge.py` before `laravel`, and to the kit names in the usage docstring (the `doctor` line), the `--kit` help of `init`, the help of `kit` and the docstring of `apply_kit`. Done when: tests in `tests/test_lsp_kit.py` install through `init --kit lsp` and through `kit <project> lsp` on the command line and find `.conclave/lsp.json`, find the file recorded under `lsp` in `.conclave/kits.json`, find a second install changing nothing, and find a project's own `.conclave/lsp.json` kept byte for byte and listed under `preserved`. Cheaper substitute: a kit `forge.py` installs without recording must fail the record test, because `diff` and `update` would then not know the file.
- [ ] Detect the kit in `installed_kits` of `forge.py` by `.conclave/lsp.json`. Done when: a test in `tests/test_lsp_kit.py` finds `lsp` in `check_repo(...)["kits"]` after an install and not before, and not in a project that has only the Laravel kit.
- [ ] Add an `lsp` branch to `doctor_repo` in `forge.py` that checks each file the kit installs is present, read from the kit's `templates/` so a file added by a later section is checked without a second list (the per-server checks come in §2). Done when: tests in `tests/test_lsp_kit.py` find `ok` for each file on a fresh install through `forge.py doctor <project> lsp`, `missing` with `--strict` exit 3 once `.conclave/lsp.json` is deleted, and a check for a file added to a scratch copy of the kit.
- [ ] Check the kit when no kit is named, in `doctor_repo` of `forge.py`: `forge.py doctor <project>` selects Laravel, WordPress or base as it does today and, when `installed_kits` finds `lsp`, appends the `lsp` branch's checks and lists the kit under `also` in the report. Done when: tests in `tests/test_lsp_kit.py` run `forge.py doctor <project>` with no kit on a base project with the kit (the base checks and the `lsp` checks, `also` naming `lsp`), on one without it (no `also`, no `lsp` check) and with the table deleted after an install that also left a skill-free trace (`--strict` exit 3 names the missing file only while the kit is still detected), and the usage docstring's `doctor` line says what the bare form checks.
- [ ] List the kit in `README.md` (the kits sentence and table), `kits/README.md` (the install block and the Layout table) and `AGENTS.md` (Purpose, and the sentence naming the kits the SDK does not install in itself). Done when: the three name it with table rows within 120 characters, each saying what the kit holds so far (the server table; the client, plugin and bridge come in §2 to §7), and `python -m unittest tests.test_forge -k markdown_table` passes.
- [ ] Commit: `lsp: kit skeleton known to forge.py`

**Corrected 2026-11-15 (validation):** measured today. `forge.list_kits()` lists any folder under `kits/` with a `templates/` folder and `tests/test_forge.py:291` asserts the exact list, so that test changes with the kit. The items named no test file; they go in a new `tests/test_lsp_kit.py`, not `tests/test_forge.py` (over ten minutes to run), so the checkpoint names it; before: "`python -m unittest discover -s tests -p test_forge.py` ends `OK`". "The kit names in the usage docstring and the `--kit` help texts" are four places, now named. The install item proved only that the file lands: the install record, a second install and a project's own table are what the other kits' installs are held to (`tests/test_kit_install.py`), so they are in. The doctor item would have needed a hand-kept file list that §2 to §7 each extend: it reads the kit's `templates/`. `AGENTS.md` also names the kits the SDK does not install in itself, where `lsp` belongs. Removing `lsp` from `KIT_ORDER` does not make an install fail (`init --kit` appends a kit that is not in the order), so the checkpoint's failure case is the one that does: removing the detection.

**Corrected 2026-11-15 (plan review):** one gap, taken. `doctor_repo(project, None)` selects Laravel, WordPress or base (`forge.py:1886` to `:1892`), so `forge.py doctor <project>` would never have checked an installed LSP kit, and no later section owned that. The bare form now appends the `lsp` checks when the kit is installed. Decision (default, cheap to reverse: one loop): only `lsp` joins the bare form, because its checks read files and `PATH`; the `todo` and `reviewer` branches start other programs (Codex's app-server, the reviewer CLIs) and stay behind their kit name, which is noted in `todo/findings.md` as an open question for the bare form.

**Test checkpoint:** `python -m unittest tests.test_lsp_kit` ends `OK`; removing the `.conclave/lsp.json` detection from `installed_kits` makes the detection test fail.

## 2. Server table `.conclave/lsp.json` with presets per stack

One table names every language server the project uses: its command, the file extensions it serves and how to install it. Presets fill it for a stack so a project does not write entries by hand.

**Phase:** 6
**Needs:** none
**Surface:** no

**Build order:**

1. Write `load_servers` in `kits/lsp/templates/scripts/lib/lsp_table.py` and the presets file. Done when: a table with one preset loads.
2. Add `scripts/lsp-servers.py` and the doctor checks. Done when: the checkpoint passes.

- [ ] Add `load_servers(root)` to `lib/lsp_table.py`, reading `.conclave/lsp.json` entries of `{"name", "command", "extensions", "language", "install"}`: `name` matching `[a-z0-9][a-z0-9-]*` and unique, `command` a non-empty list of strings, `extensions` a non-empty list each starting with a dot, `install` a one-line hint. Done when: a test for each fault reads a refusal naming `.conclave/lsp.json`, the entry and the key. Cheaper substitute: accepting a `command` string and splitting it on spaces must fail, because a path with a space breaks.
- [ ] Create `kits/lsp/templates/scripts/lib/lsp_presets.json` with presets `cpp` (clangd), `python` (basedpyright-langserver), `php` (intelephense), `web` (typescript-language-server, tailwindcss-language-server) and `laravel` (laravel-lsp, plus `php` and the Tailwind server), each entry with the install hint the Laravel kit already gives (`forge.py:579`) or the server's own documented install command. Done when: a test loads every preset through the same entry checks as `load_servers`.
- [ ] Create `kits/lsp/templates/scripts/lsp-servers.py` with `list`, `add <preset>` and `remove <name>`: `add` merges a preset's entries into the table, leaving an entry the project already has by that name untouched, written through a temporary file and `os.replace`. Done when: tests cover adding to an empty table, adding a preset twice (no change the second time), keeping a project's edited entry and an unknown preset refused by name.
- [ ] Add per-server checks to the `lsp` branch of `doctor_repo` in `forge.py`: the table loads under `load_servers` (compiled from the kit's module as `_doctor_reviewer` does, `forge.py:454`), and each server's command resolves with `shutil.which`, `setup_required` with its `install` hint when it does not. Done when: tests cover a malformed table (`missing` with the refusal), an installed stub server and a missing one.
- [ ] Add `kits/lsp/templates/scripts/tests/test_lsp_table.py` and run it from `tests/test_forge.py` as the other kits' tests are. Done when: the quick suite runs it.
- [ ] Commit: `lsp: server table with presets per stack`

**Test checkpoint:** `python -m unittest discover -s kits/lsp/templates/scripts/tests` ends `OK`; making `add` replace an existing entry makes the edited-entry test fail.

## 3. Diagnostics client that reads the server table

The Laravel kit's client already speaks LSP over stdio with the standard library. Its server list moves out of the code into the table, and the client becomes the LSP kit's.

**Phase:** 6
**Needs:** none
**Surface:** no

**Build order:**

1. Copy `kits/laravel/templates/scripts/lsp-diagnostics.py` to `kits/lsp/templates/scripts/lsp-diagnostics.py` and replace `SERVERS` with the loaded table. Done when: `--all` runs every server in a fixture table.
2. Keep the exit rules and bound the server process. Done when: the checkpoint passes.

- [ ] Replace the `SERVERS` table (`lsp-diagnostics.py:325`) in the LSP kit's copy with `load_servers`, so `--server <name>` and `--all` accept the names in `.conclave/lsp.json`. Done when: a test with a stub server in a fixture table collects its `publishDiagnostics` for a file. Cheaper substitute: keeping the Laravel server names as a fallback in the code must fail review; the table is the only list.
- [ ] Send each file only to the servers whose `extensions` include its suffix in `lsp-diagnostics.py`. Done when: a test with two stub servers finds a `.py` file sent to one and not the other.
- [ ] Keep the client's exit rules: a server whose command is not installed prints `SKIPPED -- not installed. Install: <hint>` and the client exits 3 only when every requested server is missing (`:648`, `:670`). Done when: tests cover one missing among two (exit by diagnostics) and all missing (exit 3).
- [ ] End the server's whole process tree in `lsp-diagnostics.py` on the client's timeout and on exit, and cap what is read from a server at a fixed byte limit per run. Done when: a test with a stub server that starts a child and never answers finds both gone after the timeout, and one that floods its output finds the client stopping at the cap with a clear message. Cheaper substitute: killing only the direct child must fail the child-gone assertion.
- [ ] Refuse an empty table in `lsp-diagnostics.py` with one line naming `scripts/lsp-servers.py add`. Done when: a test with the shipped empty table finds that line and exit 2.
- [ ] Add `kits/lsp/templates/scripts/tests/test_lsp_diagnostics.py` covering the items above with stub servers. Done when: the quick suite runs it.
- [ ] Commit: `lsp: diagnostics client reads the server table`

**Test checkpoint:** `python -m unittest discover -s kits/lsp/templates/scripts/tests` ends `OK`; sending every file to every server makes the suffix test fail.

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
