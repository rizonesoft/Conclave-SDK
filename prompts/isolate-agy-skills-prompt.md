# Isolate Agent Skills Prompt

Copy isolated Antigravity (`.agents/`) and OpenAI Codex (`.codex/`) skills and rules from your Conclave-SDK checkout (`<sdk>` below) into this repository without disturbing `.claude/`:

1. For each kit the repository uses (`base` always, plus `todo`, `reviewer` or `automations` when present), run `python <sdk>/forge.py kit . <kit> --agent agy` and `python <sdk>/forge.py kit . <kit> --agent codex` to copy in the missing isolated `.agents/skills/`, `.agents/rules/`, `GEMINI.md`, `.codex/skills/`, `.codex/rules/`, and `CODEX.md`.
2. Update `AGENTS.md` and `CLAUDE.md` so each agent is directed to its own isolated directory (`.agents/skills/` for Antigravity, `.claude/skills/` for Claude Code, and `.codex/skills/` for Codex).
3. Run `python <sdk>/forge.py check .`, `python scripts/todo-graph.py validate`, and `python scripts/todo-graph.py plan --check`.
4. Commit `.agents/`, `.codex/`, `GEMINI.md`, `CODEX.md`, `CLAUDE.md`, and `AGENTS.md` on `main`.
