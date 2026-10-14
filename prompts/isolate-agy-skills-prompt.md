# Isolate Agent Skills Prompt

Synchronize isolated Antigravity (`.agents/`) and OpenAI Codex (`.codex/`) skills and rules from `R:\GitHub\AgentForge` into this repository without disturbing `.claude/`:

1. Run `python R:\GitHub\AgentForge\forge.py sync . --agent agy` and `python R:\GitHub\AgentForge\forge.py sync . --agent codex` to install isolated `.agents/skills/`, `.agents/rules/`, `GEMINI.md`, `.codex/skills/`, `.codex/rules/`, and `CODEX.md`.
2. Update `AGENTS.md` and `CLAUDE.md` so each agent is directed to its own isolated directory (`.agents/skills/` for Antigravity, `.claude/skills/` for Claude Code, and `.codex/skills/` for Codex).
3. Run `python R:\GitHub\AgentForge\forge.py check .`, `python scripts/todo-graph.py validate`, and `python scripts/todo-graph.py plan --check`.
4. Commit `.agents/`, `.codex/`, `GEMINI.md`, `CODEX.md`, `CLAUDE.md`, and `AGENTS.md` on `main`.
