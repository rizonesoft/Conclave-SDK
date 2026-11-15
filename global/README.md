# Global agent configuration

The owner's machine-level configuration for Claude Code, Codex, and Antigravity: global rules, hooks, skills and helper scripts. It was imported from two retired personal repositories so that both can be deleted. `forge.py` never installs anything from this folder into a project, and the kits do not read it.

## What is where

| Path | Holds |
| ---- | ----- |
| `claude/rules/claude-code.md` | Master copy of Claude Code's global rules |
| `claude/hooks/` | Claude hooks, their tests, `verify_install.py` and `verify-repos.txt` |
| `claude/skills/<name>/` | Skills: `file-to-ticktick`, `process-email`, `process-ticktick-task` |
| `claude/project-skills/` | `seo-article-writer` and `aioseo`: WordPress skills, not yet in a kit |
| `codex/rules/` | `codex.md` (master Codex rules) and `hooks.json` (the template `deploy.py` fills in) |
| `codex/hooks/` | Codex hooks and their tests |
| `codex/skills/<name>/` | Global Codex skills: `file-to-ticktick`, `process-ticktick-task` |
| `../plugins/agy/<name>/` | Antigravity global plugins deployed to `.gemini/config/plugins/` |
| `deploy.py`, `tests/` | The one deploy script and its tests |
| `codex/scripts/` | `check-approval-policy.mjs` |
| [`../docs/bosun.md`](../docs/bosun.md) | The Bosun queue behind section 11's "Heavy jobs queue" bullet |

The three agents are maintained independently. Nothing here is shared across `claude/`, `codex/`, and `plugins/agy/`.

## Deploying

`deploy.py` is the one place the live configuration is deployed from, wherever the SDK is checked out. It locates everything relative to its own file and deploys to the home directory of whoever runs it. Run it once on Windows and once in WSL:

```text
python <SDK>/global/deploy.py [--agent claude|codex|agy|all] [--home DIR] [--dry-run] [--check]
```

| Source | Target in the home directory |
| ------ | ---------------------------- |
| `claude/rules/claude-code.md` | `.claude/CLAUDE.md` |
| `claude/skills/<name>/` | `.claude/skills/<name>/`, files copied, destination-only files kept |
| `claude/hooks/` | not copied: the hook commands in `.claude/settings.json` are pointed at it |
| `codex/rules/codex.md` | `.codex/AGENTS.md` |
| `codex/rules/hooks.json` | `.codex/hooks.json`, generated from the template |
| `codex/skills/<name>/` | `.agents/skills/<name>/`, folders that hold a `SKILL.md` |
| `../plugins/agy/<name>/` | `.gemini/config/plugins/<name>/`, mirrored per OS |

Codex runs a hook only once its current hash is approved (`hooks.state` in the home's `config.toml`), and a changed `hooks.json` reads `modified`, so after writing `.codex/hooks.json` the deploy approves the hooks it wrote: the user hooks from that file whose command runs a script under `global/codex/hooks`. It does so through Codex's own app-server (`hooks/list`, then `config/value/write`), with the todo kit's `scripts/codex-hook-trust.py`, against the deploy's home (`--home` sets `CODEX_HOME`). A hook disabled in Codex stays disabled, and each hook is reported `approved`, `unchanged` (already trusted) or `skipped` with the reason; a dry run or a machine without `codex` skips the step, and a rerun approves what is still not trusted. To check: run the deploy again (every hook `unchanged`), or list the hooks in a Codex session.

- In `settings.json` the quoted script path of a hook command that runs `article_rules.py`, `layer_rules.py`, `article_check.py` or `session_drift_check.py` changes to the absolute path under `claude/hooks/`, and a `UserPromptSubmit` entry for `session_drift_check.py` is added when there is none, with the interpreter the other hook commands use. Nothing else changes. A missing file, or one with no such command, is reported and left alone. An invalid file is refused and nothing is written.
- `claude/hooks/session_drift_check.py` runs on the first prompt of each Claude Code session, inside a three second budget, and stays silent unless something drifted: it runs `deploy.py --agent claude --check`, and checks that `~/.claude.json` registers the `bunny-net` and `domains-co-za` servers from `plugins/claude` of this checkout (never `R:\Bin\claude`) with a `dist/server.mjs` built from the current sources (`plugins/claude/scripts/register_claude.py --check` holds those rules). On drift it adds a short warning to the prompt's context and to stderr, and never blocks the prompt. The session is remembered by an empty marker file in `R:\scratch\claude-drift` (`/mnt/r/scratch/claude-drift` in WSL), or the temporary folder where `R:` is absent.
- `codex/rules/hooks.json` is a template with `{HOOKS}` (POSIX path of `codex/hooks`), `{HOOKS_WINDOWS}` (the same with a drive letter and forward slashes) and `{PYTHON_WINDOWS}` (the Windows interpreter). A checkout on `X:` maps to `/mnt/x/...` and back. A pure Linux checkout uses its own path for both.
- `codex/hooks/session_drift_check.py` checks the global Codex deployment, SDK marketplace source, cached bundles and bundle freshness once per session and platform, within three seconds. It reuses the deployer's read-only check without starting a child process. Markers live in `R:\scratch\codex-drift` or `/mnt/r/scratch/codex-drift`; clean sessions produce no output. See [Codex plugin operations](../plugins/codex/README.md) for repair and verification.
- Antigravity bundles under `../plugins/agy/<name>/` mirror cleanly into `.gemini/config/plugins/<name>/`: `hooks.json` gets the OS Python command, `powertools_hook.py` stamps `DEPLOYED_FROM`, orphan files inside those plugin folders are backed up and pruned without touching unrelated plugins, and `powertools_hook.py` checks for checkout drift once per session.
- Every write is atomic. An identical file is reported `unchanged` and not rewritten. A differing file is first copied to `.conclave/global-backups/<UTC timestamp>/` under the home directory, keeping its relative path.
- `--dry-run` reports and writes nothing. `--check` verifies without writing and exits 1 on drift. `--home DIR` deploys to `DIR` instead (the tests use it). The exit code is non-zero only on a refusal, drift under `--check`, or error.
- Tests: `python -m unittest discover -s global/tests -v`.

Hook tests live beside the hooks: `python -m unittest discover -s global/claude/hooks -p "test_*.py"` and the same in `global/codex/hooks`.

The copies in `R:\Bin` (themselves from the retired `R:\Claude` and `R:\Codex` repositories) were deleted on 2026-11-16, after a file-by-file comparison showed their content is here or is derived, local or backup material (`docs/reviews/06-global/D06-T01-bin-comparison.md`). Rules, skills and hooks deploy from here, and the plugins are registered from `plugins/` on Windows and in WSL (`plugins/README.md`, "Registered from this checkout").

## Account identifiers

Several files name the owner's mail identities, mailbox addresses or client names as examples or as fixtures: the two `process-ticktick-task` skills (`references/outlook.md` and the helper tests), `claude/rules/claude-code.md`, `codex/rules/codex.md`, `codex/skills/file-to-ticktick/README.md` and the hook tests. Treat this folder as private to the owner.
