# AGENTS.md

Shared instructions for agents working in `Conclave-SDK`. Each agent loads this file alongside its own isolated entrypoint (`GEMINI.md`, `CLAUDE.md`, or `CODEX.md`).

## Purpose

`Conclave-SDK` holds the overlay kits (`kits/base`, `kits/todo`, `kits/reviewer`, `kits/automations`, `kits/laravel`, `kits/wordpress`) that carry every agent skill, rule, subagent, script and template, plus prompts and the stdlib-only CLI `forge.py`, used to bootstrap projects under `R:\GitHub`. The SDK is a template: a project takes a copy once and owns it, and nothing links it back to the SDK.

## Architecture and Working Rules

- **Zero external dependencies:** All Python scripts (`forge.py` and every script in the kits) use the Python 3 standard library only.
- **Atomic writes:** Every file write in tooling uses a temporary file in the destination directory followed by `os.replace`.
- **Strict agent isolation:** Each kit keeps Antigravity skills in `templates/.agents/`, Claude Code skills in `templates/.claude/` and OpenAI Codex skills in `templates/.codex/`, installed as the same folders in target repos. The kits are the only source. The SDK's own `.agents/`, `.claude/`, `.codex/` and `scripts/` are an installed copy of the `base`, `todo`, `reviewer` and `automations` kits, as are `.conclave/reviewers.toml`, `.conclave/automations/` and the kits' files under `docs/`, because the SDK plans, reviews and schedules its own work with them: change a kit file in the kit, then refresh the copy with `python forge.py self-sync` (a test fails until the two match). The `laravel` and `wordpress` kits are not installed in the SDK itself. Default provisioning mode is `isolated` so every target repository is 100% self-contained.
- **Prose and table formatting:** Write one line per paragraph and list item in Markdown. Never use em dashes or en dashes anywhere: prose, code, comments, commit messages and generated files. Keep every Markdown table row at or under 120 characters so table rows never wrap in raw `.md` view, and keep TODO `Deliverable` cells and `## N. <Title>` headings to a short noun phrase of at most 88 characters.
- **TODO contract:** All skills and templates enforce small, single-responsibility sections, short `Deliverable` and section titles (`<= 88` chars), granular five-part micro-steps (`Done when:` and backticked path/symbol per item, `Cheaper substitute:` on UI/write items), logical step commits within sections, and a 100% complete development plan with zero silent drops or unowned SPEC controls.
- **Imported material:** `global/` (the owner's machine-level rules, hooks and skills for Claude Code and Codex) and `plugins/` (account-bound MCP plugins) were imported byte for byte from two retired repositories. `forge.py` never installs either into a project, and only their two `README.md` files are held to the writing rules above; change an imported file only on purpose, never to satisfy a formatter. The findings files under `docs/reviews/` hold reviewers' replies byte for byte under a digest and are exempt too.
- **Output discipline:** Bound command output and run `python -m unittest discover -s tests -v` before committing changes.
