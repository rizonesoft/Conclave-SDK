# Bootstrap Project Prompt

Initialize or update this repository using `R:\GitHub\AgentForge`:

1. Run `python R:\GitHub\AgentForge\forge.py init . --mode hybrid` to install isolated `.agents/skills/`, `.claude/skills/`, `GEMINI.md`, `CLAUDE.md`, and `scripts/todo-graph.py`.
2. Verify the setup with `python R:\GitHub\AgentForge\forge.py check .`.
3. If `todo/` already has active TODO files, run `python scripts/todo-graph.py validate` and `python scripts/todo-graph.py plan --check`.
4. Commit the agent configuration on `main`.
