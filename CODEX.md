# CODEX.md

This file configures OpenAI Codex for this repository. Shared working rules live in `AGENTS.md`.

- Codex skills are isolated in `.codex/skills/` and `.codex/rules/`.
- Antigravity customizations in `.agents/` and `GEMINI.md`, and Claude Code customizations in `.claude/` and `CLAUDE.md`, belong to those respective agents and are ignored by Codex.
- See `AGENTS.md` for architecture, validation, and formatting rules.

## Role

Claude Code and Antigravity are the writers. Codex is a read-only reviewer: inspect, test and report findings, but do not implement changes or launch writer campaigns unless the owner explicitly authorizes a role change.
