# Base kit

Reusable starter overlay for adding Conclave and AgentForge agent instructions and skills to a project across Google Antigravity (`.agents/`), Claude Code (`.claude/`), and OpenAI Codex (`.codex/`). This is the generic agent layer; Laravel and WordPress stacks are sibling kits under `kits/`.

## Contents

```text
templates/
  AGENTS.md
  GEMINI.md
  CLAUDE.md
  CODEX.md
  .agents/skills/
  .claude/skills/
  .codex/skills/
  docs/
  scripts/
scripts/
  install.sh
  test-install.sh
```

The template uses real files, not symlinks. Antigravity, Claude, and Codex skills may start aligned, but each tool gets its own copy so wording and metadata can diverge when model or tool behavior requires it.

## Install

```powershell
python forge.py kit /path/to/new-project base
```

```bash
kits/base/scripts/install.sh /path/to/new-project
```

The installer is additive-only: it copies missing files and preserves every existing file byte-for-byte, including locally tuned `.agents`, `.claude`, and `.codex` skills and project instructions. Preview the exact additions with `--dry-run`:

```powershell
python forge.py kit /path/to/new-project base --dry-run
```

There is no force/overwrite mode on kits. Before copying any file, the installer preflights the complete destination set and refuses a symlink target or any missing destination whose parent inside the target is a symlink or non-directory.

After installing, adapt `AGENTS.md`, `GEMINI.md`, `CLAUDE.md`, `CODEX.md`, and skill descriptions to the target project.

The template `docs/` folder holds the skill/rule structure document, and `scripts/` holds `verify-agent-tiers.mjs`, which checks that every Claude agent definition pins an explicit non-Haiku model.

## Maintenance

When improving shared operating behavior, update:

1. The active project file under `.agents/skills/`, `.claude/skills/`, or `.codex/skills/`.
2. The other tool-specific copies if the same behavior should apply there.
3. This kit template if new projects should inherit the behavior.

Do not use symlinks between `.agents`, `.claude`, and `.codex`.
