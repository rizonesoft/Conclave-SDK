# GEMINI.md

Follow [AGENTS.md](./AGENTS.md). This file holds only what is specific to Google Antigravity (`agy`).

- Skills live in `.agents/skills/<name>/` and are mirrored as real files in `.claude/skills/<name>/` and `.codex/skills/<name>/`. Change all three together.
- Use `.agents/skills/local-tool-safety` before local tool, Windows/WSL, connector, mail, cloud, SQL, or outbound work.
- Rules live in `.agents/rules/`.
- Subagents live in `.agents/agents/<name>.md`, pinned to `gemini-4-hydrogen-medium` while the main writer runs on Gemini 4 Carbon. Run `python scripts/agy-subagent.py <agent> -p="<task>"` to delegate on Hydrogen medium, and `python scripts/agy-subagent.py --check` after changing a definition. The main loop reviews what they return.
