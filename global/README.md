# Global agent configuration

The owner's machine-level configuration for Claude Code and Codex: global rules, hooks, skills and helper scripts. It was imported from two retired personal repositories (`R:\Claude` and `R:\Codex`) so that both can be deleted. `forge.py` never installs anything from this folder into a project, and the kits do not read it.

## What is where

| Path | Holds |
| ---- | ----- |
| `claude/rules/claude-code.md` | Master copy of Claude Code's global rules |
| `claude/hooks/` | Claude hooks, their tests, `verify_install.py` and `verify-repos.txt` |
| `claude/skills/<name>/` | Skills: `file-to-ticktick`, `process-email`, `process-ticktick-task` |
| `claude/scripts/` | Shell helpers that deploy and register the Claude configuration |
| `claude/project-skills/` | `seo-article-writer` and `aioseo`: WordPress skills, not yet in a kit |
| `codex/rules/` | `codex.md` (master Codex rules), `deploy.py`, `hooks.json`, `test_deploy.py` |
| `codex/hooks/` | Codex hooks and their tests |
| `codex/skills/<name>/` | Global Codex skills: `file-to-ticktick`, `process-ticktick-task` |
| `codex/skills/deploy.py`, `tests/` | Skill deployer with its tests, and the skills README |
| `codex/marketplace.json` | Codex plugin marketplace definition |
| `codex/scripts/` | `check-approval-policy.mjs` |

The two agents are maintained independently. Nothing here is shared between `claude/` and `codex/`.

## Where the live copies run

The live copies currently run from `R:\Bin\claude` and `R:\Bin\codex`. They are plain copies with no git history. The live hook wiring in `~/.claude/settings.json` and `~/.codex/hooks.json` points at those folders. Nothing in this folder is wired live from the SDK checkout yet, so editing a file here changes nothing on the machine until it is deployed or the wiring is repointed.

## Hard-coded paths that need a decision

Every file below was imported byte for byte and still names one of `R:\Claude`, `R:/Codex`, `R:\Bin\...` or `C:/Python314`. The old repositories were deployed from those paths, so a deployer or a hook run from this checkout would still act on the old locations.

- `claude/hooks/verify_install.py`
- `claude/scripts/import-bunny-net.sh`
- `claude/scripts/import-domains-co-za.sh`
- `claude/scripts/register-claude.sh`
- `claude/skills/process-ticktick-task/SKILL.md`
- `codex/rules/codex.md`
- `codex/rules/deploy.py`
- `codex/rules/hooks.json`
- `codex/skills/README.md`
- `codex/skills/process-ticktick-task/SKILL.md`

The plugins under `../plugins/` carry the same kind of path in their READMEs and design notes, listed in `../plugins/README.md`.

`codex/skills/deploy.py` accepts only a folder directly beneath a `skills/global` directory. In this layout the skills sit directly under `codex/skills/`, so the deployer needs adjusting before it is used from here.

## Account identifiers

Several files name the owner's mail identities, mailbox addresses or client names as examples or as fixtures: the two `process-ticktick-task` skills (`references/outlook.md` and the helper tests), `claude/rules/claude-code.md`, `codex/rules/codex.md`, `codex/skills/file-to-ticktick/README.md` and the hook tests. Treat this folder as private to the owner.
