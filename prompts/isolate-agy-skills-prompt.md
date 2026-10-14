# Isolate Antigravity Skills Prompt

Synchronize isolated Antigravity skills and rules from `R:\GitHub\AgentForge` into this repository without disturbing `.claude/skills/`:

1. Run `python R:\GitHub\AgentForge\forge.py sync . --agent agy --mode hybrid` to install `.agents/skills/`, `.agents/rules/`, `.agents/skills.json`, and `GEMINI.md`.
2. Update the repository path table in `AGENTS.md` if needed so `.agents/skills/` is listed alongside `.claude/skills/`.
3. Run `python R:\GitHub\AgentForge\forge.py check .` and `python scripts/todo-graph.py validate`.
4. Commit `.agents/`, `GEMINI.md`, and `AGENTS.md` on `main`.
