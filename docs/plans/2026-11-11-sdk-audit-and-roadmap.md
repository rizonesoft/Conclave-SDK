# Conclave-SDK audit and roadmap

Date: 2026-11-11. Asked for by the owner. Evidence: a read of `forge.py`, every kit, the tests, RasterFold, Impossible OS, and the retired `rizonetech/Claude` and `rizonetech/Codex` repositories.

## What the SDK is for

One place that holds the best current version of how the owner's projects are planned, built, reviewed and run unattended by Claude Code, Codex and Antigravity. A project takes what fits it and keeps its own shape. The SDK improves, and each project can see what improved and take it deliberately. Nothing is ever forced on a project and nothing a project built is ever overwritten.

## Verdict

The SDK is safe and behind. It never overwrites a project's file, and that part is well tested. But it has no way to upgrade a project, it does not know what a project installed, and the projects have moved ahead of it: the best tooling lives in RasterFold and Impossible OS, not here. Work has been flowing downstream by hand copy and almost never back upstream. That is the drift.

## Findings

| # | Finding | Evidence |
| - | ------- | -------- |
| 1 | No upgrade path: no `sync`, no `diff`, no change report | `forge.py:752`, `README.md:33` |
| 2 | Nothing records what a project installed, or from which commit | `tests/test_forge.py:167` |
| 3 | An existing file is skipped unread: same, changed and stale look alike | `forge.py:286` |
| 4 | A kit is all or nothing: one script or skill cannot be taken alone | `forge.py:188` |
| 5 | The todo graph hard-codes one layout, phase list and stamp | `lib/todo_graph.py:18,64` |
| 6 | Neither project's `todo/` passes the kit validator; both are ahead of it | drift survey |
| 7 | RasterFold's graph is 12,802 lines against the kit's 1,300 | `scripts/todo-graph.py` |
| 8 | Unattended running exists only in the projects | `campaign_guard.py:19` |
| 9 | Antigravity has skills and rules, no run guard or subagents | `kits/todo/README.md:33` |
| 10 | The template pin routes only `claude`; a Gemini writer is refused | `reviewers.toml:27` |
| 11 | Every skill example says `--writer claude`, for all agents | `independent-review` |
| 12 | Three hand-kept copies of each skill and no generator | `tests/test_forge.py:582` |
| 13 | Five near-identical bash installers beside `forge.py` | `kits/*/scripts/install.sh` |
| 14 | `init` writes kit 1 before kit 2 can fail; no rollback or list | `forge.py:653` |
| 15 | `init --force` rewrites the four entry docs with no backup | `forge.py:657` |
| 16 | The reviewer install test was red (old pin name) and nobody saw | fixed 2026-11-11 |
| 17 | The installed dispatcher test crashed at a shallow checkout path | fixed 2026-11-11 |
| 18 | A reviewer reply in the Windows code page lost its curly quotes | D00 T01 §2 |

Findings 16 and 17 are why it feels flaky: gates that are not run cannot be trusted. The bash install tests are in no suite that runs before a commit.

## Recommendations

In order. Each is small on its own, and none forces a shape.

### 1. Version what a project imported (owner decision 2026-11-11)

`forge.py` writes `.conclave/kits.json` in the project: the SDK commit, and for every file it installed, the kit, the path and a digest of the bytes as installed. This reverses the 2026-10-25 decision that nothing records the source. The record is a note, not a link: the project still owns every file, and deleting the record breaks nothing.

### 2. `forge.py diff <project> [kit]`, read-only

Per file: `missing`, `identical`, `kit-newer` (the project's bytes still match what was installed, so an update is safe), `project-changed` (show the diff, never write), `both-changed`, `project-only`. Without a record it still reports `missing`, `identical` and `differs`. This is the command that answers "what does the SDK have that I lack".

### 3. `forge.py update <project> [kit] [--only <path>]`

Writes only `missing` and `kit-newer` files. Everything else is listed with its diff and left alone. `--only` takes one file or folder, so a project adopts one script or skill. A changed file can be written beside the project's own as `<name>.kit-new` for a hand merge, never over it.

### 4. A scheduled drift report per project

A task for the automations kit that runs `forge.py diff` weekly and reports what can be updated automatically and what needs a merge. It proposes; the project decides. This is the automation: nobody types into each repository, and nothing lands unseen.

### 5. Upstream first, then down

For each project in turn: read what it built, lift the generic parts into the SDK, then let the project take the SDK's version of only those parts. Order: RasterFold's review flow (in progress, `todo/00-reviewer/`), then its campaign guard and unattended runner, then Impossible OS's overnight supervisor.

### 6. Make the todo graph take a project's shape

Move the layout and the closed lists (`todo/` path, receipts folder, phase list, Needs values, caps) into `todo/plan.json` with today's values as defaults, so a project with its own phases and Needs can adopt the graph without rewriting 256 sections. Until that exists, Impossible OS and RasterFold must not take the kit's graph.

### 7. Antigravity as a first-class writer and runner

Accept `agy` as a writer name beside `gemini`, ship routes for all three writers in the template pin, say `--writer <your agent>` in every skill, and give Antigravity and Codex the run guard through their own hook files, as RasterFold already does (`.agents/hooks.json`, `.codex/hooks.json`). Check every `agy` flag against the current CLI before it ships.

### 8. One source for the three skill copies

Generate `.agents` and `.codex` skills from the `.claude` source plus a small per-agent patch, or test that they differ only in an allowed list. Retire the bash installers in favour of `forge.py`, or generate them and test they install the same files.

### 9. Run every gate

One command, `python forge.py check-all`, runs the Python suites, the kit script tests and the install tests, and is what runs before a commit. A gate outside it does not exist.

## The standing directive as kits

The paragraph pasted into every repository ("act autonomously, self-heal, implement LSP servers, optimise the tool stack, make the unattended run really run, a desktop shortcut for Antigravity") is five capabilities. As kits a project installs them once and they stay current through `forge.py diff`.

| Kit | What it carries |
| --- | --------------- |
| `base` (extend) | The operating directive: decide, fix forward, ask only what matters |
| `base` (extend) | Git hygiene: work on main, prune merged branches and dead worktrees |
| `unattended` (new) | Preflight, launcher, heartbeat and stop hooks for all three agents |
| `unattended` (new) | Desktop shortcut and systemd unit that start the run |
| `lsp` (new) | Language server setup per stack for the three agents, with a doctor check |
| `toolchain-cpp` (new) | Ninja, ccache or sccache, a fast linker, clangd, a compile database |
| `toolchain-web` (new) | The PHP and Node equivalents for the Laravel and WordPress kits |

The directive itself belongs in `AGENTS.md` through the base kit, written as rules an agent can act on, with the project's own goal filled in by `forge.py init --goal`. The ambition ("best in its class, finish 100 percent") becomes the acceptance bar in `todo/plan.json`, where the runner already reads it.

On Ninja and similar tools: yes for the C and C++ projects (RasterFold, Impossible OS), where Ninja, a compiler cache and a faster linker cut build time and memory. They are stack tools, so they belong in a toolchain kit a project chooses, not in `base`. The SDK itself is standard library Python and needs none of them.

## The two retired repositories

Imported on 2026-11-11 into `global/` (rules, hooks, personal skills) and `plugins/` (ten plugin folders: eight for Codex, two for Claude), 378 files, byte for byte. Left out: each repository's own glue, verification and deployment logs, the brand permission drafts and the client site list.

Status on 2026-11-11, end of day: both GitHub repositories can be deleted.

1. The import is pushed to `origin/main`, and the live copies were compared with it file by file: the same content once line endings and the old folder names are set aside.
2. The client site list and the brand permission drafts were dropped on the owner's decision; they were not imported.
3. `global/deploy.py` now deploys the rules, skills and hook wiring from this checkout to the home folder, with no hard-coded path, and was run on Windows and in WSL: both run from `global/`. The copies in `R:/Bin/claude` and `R:/Bin/codex` are superseded. The MCP plugin registrations were not moved: a plugin registered from `R:/Bin` keeps running from there until it is registered again from `plugins/`.
