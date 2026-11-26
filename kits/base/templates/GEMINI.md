# GEMINI.md

Follow [AGENTS.md](./AGENTS.md). This file holds only what is specific to Google Antigravity (`agy`).

- Skills live in `.agents/skills/<name>/` and are mirrored as real files in `.claude/skills/<name>/` and `.codex/skills/<name>/`. Change all three together.
- Use `.agents/skills/local-tool-safety` before local tool, Windows/WSL, connector, mail, cloud, SQL, or outbound work.
- Rules live in `.agents/rules/` , the always-on location: a rule there applies without a skill being invoked. A repository with a UI surface keeps its design contract, token source, forbidden patterns and its lint and rendered-check commands in `.agents/rules/design-contract.md`.
- Model and subagents: Antigravity runs Gemini 4 Neon (`gemini-4-neon-medium`) at an explicit `--effort` (for example `agy --model gemini-4-neon-medium --effort=medium`), plans and builds each section in one session, and delegates to built-in subagents (`self`, `research`, `image-generator`) via `invoke_subagent` without custom `.agents/agents/` wrappers.
