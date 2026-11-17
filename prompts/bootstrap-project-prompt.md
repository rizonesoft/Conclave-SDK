# Bootstrap Project Prompt (Gemini, Claude, or Codex)

Use this prompt inside **Google Antigravity (Gemini)**, **Claude Code**, or **OpenAI Codex** to import Conclave-SDK into a **new** or **existing** repository (`<sdk>` is the folder of your Conclave-SDK checkout):

1. **Install only what this repository needs:**
   - For a **new** repository: run `python <sdk>/forge.py init .`. That installs the `base` kit only: `AGENTS.md`, `GEMINI.md`, `CLAUDE.md`, `CODEX.md`, the safety and authoring skills for `.agents/`, `.claude/` and `.codex/`, the Claude subagents, the rules and `scripts/verify-agent-tiers.mjs`.
   - Add `--kit reviewer` for independent review by a different model family (GPT-6.2 Astra for Claude work).
   - Add `--kit todo` only when the work is planned in TODO files (eight TODO skills, `scripts/todo-graph.py`, a starter `todo/` tree and `docs/todo-workflow.md`).
   - For an **existing** repository: add a missing kit with `forge.py kit . <kit>` (preview with `--dry-run`; pass `--agent gemini`, `--agent claude` or `--agent codex` for one agent). It copies only missing files and never overwrites one the repository has. To take a later SDK improvement into a repository that already has a kit, run `forge.py diff .` then `forge.py update .` (an install made before `.conclave/kits.json` existed runs `forge.py record .` first).
   - Conclave-SDK is a template: nothing it copies links back to it, and there is no update command. Adapt the copied skills, scripts and pins to this repository; they are its own from now on.
2. **Apply a stack kit when one applies (additive-only, never overwrites):**
   - If the repository contains `artisan` (at root, `platform/`, or a first-level child), run `python <sdk>/forge.py kit . laravel`.
   - For a WordPress site, run `python <sdk>/forge.py kit . wordpress --host pressable` (or `--host wpcom`), then follow the `wordpress-connect` skill.
3. **Verify health and TODO integrity:**
   - Run `python <sdk>/forge.py check .` and `python <sdk>/forge.py doctor .`.
   - If `todo/` has active TODO files, run `python scripts/todo-graph.py validate` and `python scripts/todo-graph.py plan --check` (or run the `groom-plan` skill if reconciling a brownfield repo or incomplete `todo/` tree).
4. **Commit on `main`:** Commit the isolated agent setup and any applied stack kit overlay.
