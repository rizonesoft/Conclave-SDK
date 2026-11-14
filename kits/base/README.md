# Base kit

Reusable starter overlay for adding Conclave-SDK agent instructions, skills and subagent configuration to a project across Google Antigravity (`.agents/`), Claude Code (`.claude/`), and OpenAI Codex (`.codex/`). This is the generic agent layer; Laravel and WordPress stacks are sibling kits under `kits/`.

## Contents

```text
templates/
  AGENTS.md
  GEMINI.md
  CLAUDE.md
  CODEX.md
  .agents/skills/
  .claude/agents/
  .claude/skills/
  .codex/skills/
  docs/
  scripts/
    verify-agent-tiers.mjs
```

The template uses real files, not symlinks. Antigravity, Claude, and Codex skills may start aligned, but each tool gets its own copy so wording and metadata can diverge when model or tool behavior requires it.

## Install

```powershell
python forge.py kit /path/to/new-project base
```

The installer is additive-only: it copies missing files and preserves every existing file byte-for-byte, including locally tuned `.agents`, `.claude`, and `.codex` skills, subagents and project instructions. Preview the exact additions with `--dry-run`:

```powershell
python forge.py kit /path/to/new-project base --dry-run
```

There is no force/overwrite mode on kits. Before copying any file, the installer preflights the complete destination set and refuses a symlink target or any missing destination whose parent inside the target is a symlink or non-directory.

After installing, adapt `AGENTS.md`, `GEMINI.md`, `CLAUDE.md`, `CODEX.md`, and skill descriptions to the target project.

The template `docs/` folder holds the skill/rule structure document. Under `scripts/`, `verify-agent-tiers.mjs` checks that every Claude agent definition in `.claude/agents/` pins an explicit model, that no agent can edit files (an explicit `tools:` list with no edit tools), that an elevated tier records why, and that a Haiku agent meets every condition of the near-mechanical allowance in `AGENTS.md` (reading frontmatter as a closed subset of YAML: flat `key: value` pairs plus one skipped `hooks:` block, refusing everything else).

## Subagents across the three writers

Claude Code receives five read-only subagent definitions under `.claude/agents/` (`code-explorer`, `debug-evidence`, `git-runner`, `mutation-tester`, `test-runner`). Codex has no project subagent definitions (the base kit ships no `.codex/agents/` folder) and runs mechanical subtasks in the main session.

Google Antigravity (`agy` 1.5.8) uses native `Orchestrator (Carbon)` (`gemini-pro-orchestrator`) instead of custom `.agents/agents/*.md` files or wrapper scripts:

- **Two-phase orchestration:** `gemini-pro-orchestrator` automatically plans on Carbon (`<plan_execute_protocol>`), hands concrete execution plans to Hydrogen through `exit_plan_mode`, and can hand back to Carbon via `enter_plan_mode` when verification or design assumptions diverge.
- **Built-in subagents (`<subagents>`):** Every session natively includes built-in `self`, `research`, and `image-generator` subagents invoked via `invoke_subagent`. Shipping custom `.agents/agents/*.md` wrappers is redundant and can override native model routing, so fresh `--agent agy` installs ship zero `.agents/agents/` files and no `scripts/agy-subagent.py`.
- **Effort and model selection:** `gemini-pro-orchestrator` and `gemini-pro-orchestrator-*` manage reasoning effort internally across planning and execution turns and reject `--effort`; start interactive or campaign sessions with `agy --model gemini-pro-orchestrator` and omit `--effort`.

### Migrating existing installs to Orchestrator (Carbon)

Because `forge.py update <project> base` is additive-only and preserves deleted kit files as `project-only` (so local edits are never lost), existing projects updated from older `base` kit releases retain the retired Antigravity wrappers and remain discoverable by `agy` until cleaned up:

- `.agents/agents/code-explorer.md`
- `.agents/agents/debug-evidence.md`
- `.agents/agents/git-runner.md`
- `.agents/agents/mutation-tester.md`
- `.agents/agents/test-runner.md`
- `scripts/agy-subagent.py`

Follow this reversible cleanup after `python forge.py update <project> base`:

1. Inspect retired files with `python forge.py diff <project> base` (each retired file reports `project-only`). Compare against `.conclave/kits.json` or `git diff`: copy any local customizations you still need from a retired file into a retained project-custom file (for example `.agents/agents/preserved-code-explorer.md`), and leave existing project-custom `.agents/agents/<custom>.md` files untouched.
2. Commit your pre-cleanup repository state, anchor a durable recovery ref (`git branch pre-orchestrator-migration`, or record `git rev-parse HEAD`), and save a raw byte-preserving archive before deleting anything (`python -c "import pathlib, zipfile; z = zipfile.ZipFile('.git/pre-orchestrator-migration.zip', 'w'); [z.write(f) for p in ('.agents/agents', 'scripts/agy-subagent.py', '.conclave/kits.json') for f in ([pathlib.Path(p)] if pathlib.Path(p).is_file() else sorted(x for x in pathlib.Path(p).rglob('*') if x.is_file()) if pathlib.Path(p).is_dir() else [])]; z.close()"`). Because a committed deletion removes those paths from later `HEAD` commits and Windows Git `core.autocrlf=true` alters LF or CRLF bytes during `git add` and `git checkout`, rollback after committed cleanup runs `git -c core.autocrlf=false checkout pre-orchestrator-migration -- .agents/agents scripts/agy-subagent.py .conclave/kits.json` followed by `python -m zipfile -e .git/pre-orchestrator-migration.zip .` to restore Git tracking plus exact pre-cleanup bytes across all six retired paths, `.conclave/kits.json`, and prior customizations if you ever revert to `gemini-4-carbon-medium` without `Orchestrator (Carbon)`.
3. Remove only the six retired SDK paths (and `.agents/agents` only if it is now empty; keep migrated `.agents/agents/preserved-*.md` and custom `.agents/agents/<custom>.md` files), remove their retired entries from `.conclave/kits.json` if desired, and commit the cleanup.
4. Switch interactive and CLI Antigravity launches to `--model gemini-pro-orchestrator` with no `--effort` flag; if the project also installs `kits/unattended`, update `kits/unattended` to a release with Orchestrator effort-free profile support before setting `"effort": null` in `.conclave/unattended.json` (older unattended releases require a non-null string effort such as `gemini-4-carbon-high` with `"effort": "high"`).
5. Verify native operation: confirm none of the five SDK wrappers remain in `.agents/agents/`, confirm `agy --model gemini-pro-orchestrator` lists built-in `self`, `research`, and `image-generator` in `<subagents>`, and confirm two-phase `exit_plan_mode` execution runs cleanly.

### Live verification (`agy` 1.5.8, 2026-11-14)

Verified on 2026-11-14 against installed `agy` `1.5.8` with `CONCLAVE_LIVE_AGY=1 python -m unittest -v tests.test_agy_agents` (`Ran 14 tests in 381.924s OK`):

- **Built-in `<subagents>` listing:** Initiated `gemini-pro-orchestrator` in a fresh `--kit base --agent agy` workspace with zero `.agents/agents` directory and confirmed native `self`, `research`, and `image-generator` subagents are available.
- **Real `invoke_subagent` delegation:** Delegated a known-answer lookup (`def halve` in `calc.py`) to `TypeName='research'` with parent direct-inspection tools forbidden, observed `step_type: "subagent"` (`invoke_subagent`) launch plus post-launch `system_message` wakeup in `stream-json`, matched subagent `send_message` and parent `SYSTEM_MESSAGE` (`sender=<subagent_conversation_id>`) transcript attribution, and independently confirmed the reported answer (line `5`, returning `n / 2`) in both `delegated_replies` and `assistant_text`.
- **Two-phase `exit_plan_mode` execution:** Invoked `gemini-pro-orchestrator` to fix buggy `add(a, b)` in `calc.py`, observed planning, `exit_plan_mode` (`Plan mode is off.`), `edit_file`, and `python -m unittest tests.test_calc` (`Ran 2 tests ... OK`) exit `0`.

## Maintenance

This kit is the only source of these files. When improving shared operating behavior:

1. Change the file in this kit's `templates/` for each agent it applies to (`.agents/`, `.claude/`, `.codex/`).
2. Run `python forge.py self-sync` to refresh the SDK's own `.agents/`, `.claude/`, `.codex/` and `scripts/`; `tests/test_forge.py` fails until they match.
3. Projects are not updated: each owns the copy it took. Port the change into a project by hand only when that project wants it.

Do not use symlinks between `.agents`, `.claude`, and `.codex`.
