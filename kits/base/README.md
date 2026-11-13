# Base kit

Reusable starter overlay for adding Conclave-SDK agent instructions, skills and read-only subagents to a project across Google Antigravity (`.agents/`), Claude Code (`.claude/`), and OpenAI Codex (`.codex/`). This is the generic agent layer; Laravel and WordPress stacks are sibling kits under `kits/`.

## Contents

```text
templates/
  AGENTS.md
  GEMINI.md
  CLAUDE.md
  CODEX.md
  .agents/agents/
  .agents/skills/
  .claude/agents/
  .claude/skills/
  .codex/skills/
  docs/
  scripts/
    agy-subagent.py
    verify-agent-tiers.mjs
scripts/
  install.sh
  test-install.sh
```

The template uses real files, not symlinks. Antigravity, Claude, and Codex skills and agent definitions may start aligned, but each tool gets its own copy so wording and metadata can diverge when model or tool behavior requires it.

## Install

```powershell
python forge.py kit /path/to/new-project base
```

```bash
kits/base/scripts/install.sh /path/to/new-project
```

The installer is additive-only: it copies missing files and preserves every existing file byte-for-byte, including locally tuned `.agents`, `.claude`, and `.codex` skills, subagents and project instructions. Preview the exact additions with `--dry-run`:

```powershell
python forge.py kit /path/to/new-project base --dry-run
```

There is no force/overwrite mode on kits. Before copying any file, the installer preflights the complete destination set and refuses a symlink target or any missing destination whose parent inside the target is a symlink or non-directory.

After installing, adapt `AGENTS.md`, `GEMINI.md`, `CLAUDE.md`, `CODEX.md`, and skill descriptions to the target project.

The template `docs/` folder holds the skill/rule structure document. Under `scripts/`, `verify-agent-tiers.mjs` checks that every Claude agent definition pins an explicit model, that no agent can edit files (an explicit `tools:` list with no edit tools), that an elevated tier records why, and that a Haiku agent meets every condition of the near-mechanical allowance in `AGENTS.md` (reading frontmatter as a closed subset of YAML: flat `key: value` pairs plus one skipped `hooks:` block, refusing everything else). Alongside it, `agy-subagent.py` enforces the Antigravity subagent frontmatter contract (`python scripts/agy-subagent.py --check`) and runs a named subagent on `gemini-4-hydrogen-medium` (`python scripts/agy-subagent.py <agent> -p="<task>"`).

## Subagents across the three writers

Claude Code and Google Antigravity both receive the five read-only subagent counterparts (`code-explorer`, `debug-evidence`, `git-runner`, `mutation-tester`, `test-runner`). Codex has no project subagent definitions (the base kit ships no `.codex/agents/` folder, matching Antigravity's built-in `migrate-agent-settings` discovery table, which lists no subagent path for Codex) and runs mechanical subtasks in the main session.

### Antigravity (`agy` 1.5.8) format, tool restriction and model selection

Measured on `agy` `1.5.8` (`2026-11-13`) from `~/.gemini/antigravity-cli/builtin/skills/agy-customizations/SKILL.md`, `~/.gemini/antigravity-cli/builtin/skills/migrate-agent-settings/SKILL.md`, `agy plugin validate --strict` and headless sessions:

- **Folder and discovery:** `agy-customizations/SKILL.md` states `"Path: .agents/ (or .agent/, _agents/, _agent/) at the root of your project"`, and `agy` `1.5.8` discovers workspace agent definitions at `.agents/agents/<name>.md` (as well as `agents/<name>.md` inside a plugin).
- **Frontmatter and tool restriction:** `migrate-agent-settings/SKILL.md` specifies `"agents/<name>.md (Claude Code subagents): keep the body as the system prompt"` with `name`, `description`, `subagent`, `mainAgent` and `tools`, noting `"tools: always write it, since an omitted tools gets only a small read-only default set"` and `"map each grant to the native tool names: Read/Glob/Grep to read_file, Edit/MultiEdit to edit_file, Write to write_file, Bash to run_command and manage_task, WebSearch/WebFetch to search_web"`. Each of the five base subagents sets `tools: [read_file, run_command, manage_task]` and `inheritMcp: false`, with neither `edit_file` nor `write_file`.
- **Model selection (`gemini-4-hydrogen-medium`):** `migrate-agent-settings/SKILL.md` says `"Drop model and color"` for imported definitions because `agy` `1.5.8`'s agent loader accepts only the four tier tokens `inherit`, `flash_lite`, `flash` and `pro` in `model:`; writing `model: gemini-4-hydrogen-medium` in `.agents/agents/<name>.md` fails `agy plugin validate` with `"Invalid model tier gemini-4-hydrogen-medium. The loader skips this agent"` and omits the file from `<subagents>`. At runtime, `invoke_subagent` maps `flash` and `pro` to `gemini-3.8-flash-tiered`, `flash_lite` to `gemini-3.5-flash-lite`, and `inherit` to the caller's Gemini 4 Carbon model. To run Antigravity subagents on Gemini 4 Hydrogen at medium effort (`gemini-4-hydrogen-medium`) while the main writer stays Gemini 4 Carbon, each `.agents/agents/<name>.md` sets `model: flash` (passing `agy plugin validate --strict`, appearing in `<subagents>`, and never inheriting Carbon), `conclave_model: gemini-4-hydrogen-medium`, `subagent: true`, `mainAgent: true` and `inheritMcp: false`, and `scripts/agy-subagent.py` invokes `agy --model gemini-4-hydrogen-medium --agent <name> --settings <deny write_file, edit_file, mcp> --input-format text --output-format stream-json` with the prompt piped on `stdin`, verifying `init.model == "gemini-4-hydrogen-medium"` and `init.agent == <name>` on every call.

### Live verification (`agy` 1.5.8, 2026-11-13)

Verified with `CONCLAVE_LIVE_AGY=1 python -m unittest tests.test_agy_agents` in a fresh `python forge.py init <scratch> --kit base --agent agy` repository (`agy` `1.5.8` on `2026-11-13`): `agy plugin validate --strict` passed with 0 errors and 0 warnings, a headless session in that install named all five custom subagents in `<subagents>`, and each subagent completed its known-answer fixture task on `gemini-4-hydrogen-medium` with the working tree left clean:

| Subagent | Model (`init.model`) | Elapsed | Live result (`2026-11-13`, `agy` `1.5.8`) |
| -------- | -------------------- | ------- | ----------------------------------------- |
| `code-explorer` | `gemini-4-hydrogen-medium` | `20.2s` | Located `halve` at `calc.py:5` |
| `git-runner` | `gemini-4-hydrogen-medium` | `17.1s` | Reported subject `calc: the known-answer fixture` |
| `test-runner` | `gemini-4-hydrogen-medium` | `16.7s` | Ran unittest and named `test_halve_keeps_whole_numbers` |
| `debug-evidence` | `gemini-4-hydrogen-medium` | `26.6s` | Quoted `'halve must floor odd numbers'` and `3.5` vs `3` |
| `mutation-tester` | `gemini-4-hydrogen-medium` | `40.3s` | Killed `test_add_sums` in a worktree; restored `calc.py` |

## Maintenance

This kit is the only source of these files. When improving shared operating behavior:

1. Change the file in this kit's `templates/` for each agent it applies to (`.agents/`, `.claude/`, `.codex/`).
2. Run `python forge.py self-sync` to refresh the SDK's own `.agents/`, `.claude/`, `.codex/` and `scripts/`; `tests/test_forge.py` fails until they match.
3. Projects are not updated: each owns the copy it took. Port the change into a project by hand only when that project wants it.

Do not use symlinks between `.agents`, `.claude`, and `.codex`.
