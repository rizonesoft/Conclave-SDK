# Agent Configuration Quality Criteria

Audit `AGENTS.md`, `GEMINI.md`, `CLAUDE.md`, `CODEX.md`, `SKILL.md`, and plugin directories against these checks:

## 1. Accuracy and Grounding

- Every file path, script path, CLI flag, and test command cited actually exists in the workspace or plugin.
- Architecture notes describe owning layers accurately instead of repeating generic programming advice.

## 2. Signal Density and Progressive Disclosure

- Always-on rule files (`AGENTS.md`, `GEMINI.md`, `rules/*.md`) contain high-signal constraints rather than exhaustive manuals.
- Detailed procedures and checklists live in on-demand `SKILL.md` files, and large reference specs live in `references/` or `scripts/`.
- Each rule file stays compact (hard platform cap is 24,000 bytes; prefer under 4,000 bytes for global always-on rules).

## 3. Agent and Plugin Isolation

- No Antigravity skill references Claude Code tool names (`Read`, `Edit`, `Write`, `Bash`, `AskUserQuestion`) unless translating them in a migration tool.
- Native Antigravity plugins place `hooks.json` at plugin root, omit `agents/*.md` wrappers in favor of native subagents and `run_workflow`, use valid `plugin.json` keys only, and reference UI settings with `[label](customization://<dir_name>)`.

## 4. Formatting and Hygiene

- Zero em dashes (`\u2014`) or en dashes (`\u2013`) in prose, code comments, or tables.
- Markdown paragraphs and list items stay on one line each.
- Markdown tables keep cells `<= 88` characters and rows `<= 120` characters so raw Markdown stays readable without wrapping.
- Zero hardcoded secrets, credentials, or AI attribution templates.
