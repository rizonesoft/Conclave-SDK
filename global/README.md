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

- In `settings.json` only the quoted script path of a hook command that runs `article_rules.py`, `layer_rules.py` or `article_check.py` changes, to the absolute path under `claude/hooks/`. A missing file, or one with no such command, is reported and left alone. An invalid file is refused and nothing is written.
- `codex/rules/hooks.json` is a template with `{HOOKS}` (POSIX path of `codex/hooks`), `{HOOKS_WINDOWS}` (the same with a drive letter and forward slashes) and `{PYTHON_WINDOWS}` (the Windows interpreter). A checkout on `X:` maps to `/mnt/x/...` and back. A pure Linux checkout uses its own path for both.
- Antigravity bundles under `../plugins/agy/<name>/` mirror cleanly into `.gemini/config/plugins/<name>/`: `hooks.json` gets the OS Python command, `powertools_hook.py` stamps `DEPLOYED_FROM`, orphan files inside those plugin folders are backed up and pruned without touching unrelated plugins, and `powertools_hook.py` checks for checkout drift once per session.
- Every write is atomic. An identical file is reported `unchanged` and not rewritten. A differing file is first copied to `.conclave/global-backups/<UTC timestamp>/` under the home directory, keeping its relative path.
- `--dry-run` reports and writes nothing. `--check` verifies without writing and exits 1 on drift. `--home DIR` deploys to `DIR` instead (the tests use it). The exit code is non-zero only on a refusal, drift under `--check`, or error.
- Tests: `python -m unittest discover -s global/tests -v`.

Hook tests live beside the hooks: `python -m unittest discover -s global/claude/hooks -p "test_*.py"` and the same in `global/codex/hooks`.

The live copies in `R:\Bin` (themselves from the retired `R:\Claude` and `R:\Codex` repositories) are superseded once the owner has run `deploy.py` on both Windows and WSL.

## Account identifiers

Several files name the owner's mail identities, mailbox addresses or client names as examples or as fixtures: the two `process-ticktick-task` skills (`references/outlook.md` and the helper tests), `claude/rules/claude-code.md`, `codex/rules/codex.md`, `codex/skills/file-to-ticktick/README.md` and the hook tests. Treat this folder as private to the owner.
