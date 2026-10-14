# Bootstrap or Update Project Prompt (Gemini, Claude, or Codex)

Use this prompt inside **Google Antigravity (Gemini)**, **Claude Code**, or **OpenAI Codex** to import AgentForge into a **new** or **existing** repository:

1. **Provision or sync isolated agent skills and rules:**
   - For a **new** repository: run `python R:\GitHub\AgentForge\forge.py init . --with-todo` (or `/mnt/r/GitHub/AgentForge/forge.py` inside WSL) to install isolated `.agents/` (`GEMINI.md`), `.claude/` (`CLAUDE.md`, `.claude/agents/`), `.codex/` (`CODEX.md`), `scripts/todo-graph.py`, and `scripts/verify-agent-tiers.mjs`.
   - For an **existing** repository: run `python R:\GitHub\AgentForge\forge.py sync . --include-scripts` (pass `--agent gemini`, `--agent claude`, or `--agent codex` to update a single agent, or `--agent all` for all three). Existing `AGENTS.md`, `GEMINI.md`, `CLAUDE.md`, and `CODEX.md` files are preserved.
2. **Apply stack overlay kits when applicable (additive-only, never overwrites):**
   - If the repository contains `artisan` (at root, `platform/`, or a first-level child), run `python R:\GitHub\AgentForge\forge.py kit . laravel`.
   - If the repository contains `wp-load.php` or `wp-config.php` (at root, `website/`, `wordpress/`, or `wp/`), run `python R:\GitHub\AgentForge\forge.py kit . wordpress`.
3. **Verify health and TODO integrity:**
   - Run `python R:\GitHub\AgentForge\forge.py check .` and `python R:\GitHub\AgentForge\forge.py doctor .`.
   - If `todo/` has active TODO files, run `python scripts/todo-graph.py validate` and `python scripts/todo-graph.py plan --check` (or run the `groom-plan` skill if reconciling a brownfield repo or incomplete `todo/` tree).
4. **Commit on `main`:** Commit the isolated agent setup and any applied stack kit overlay.
