# Laravel kit

Additive overlay for a Laravel application so every project gets the same agent toolchain across Gemini (`.agents/`), Claude (`.claude/`), and Codex (`.codex/`): Laravel Boost, Laravel LSP, Tailwind LSP, and the PHP LSP (Intelephense).

This kit does not scaffold a Laravel app. It does not install global binaries. It copies the overlay into an existing tree that already has `artisan`, and it tells you what is still `setup_required`.

Install `kits/base` (or `python forge.py init`) first when the repo should speak the full agent contract.

## What lands

| Path | Role |
| ---- | ---- |
| `boost.json` | Boost skill list placed at the Laravel app root |
| `scripts/lsp-diagnostics.py` | One stdio LSP client for Laravel, Tailwind, and Intelephense |
| `scripts/hooks/laravel-lsp-pre-push.sh` | Pre-push check (missing servers skip, never pass) |
| `docs/laravel-agent-tooling.md` | How to wire Boost MCP and the three language servers |
| `.agents/skills/laravel-boost/SKILL.md` | Gemini / Antigravity (`agy`) skill copy |
| `.claude/skills/laravel-boost/SKILL.md` | Claude Code (`claude`) skill copy |
| `.codex/skills/laravel-boost/SKILL.md` | Codex skill copy plus `agents/openai.yaml` |
| `.mcp.json` | Created when missing; prints `laravel-boost` fragment if present |

## Install

```powershell
python forge.py kit /path/to/laravel-project laravel [--agent all|gemini|claude|codex] [--dry-run]
python forge.py doctor /path/to/laravel-project laravel
```

```bash
kits/laravel/scripts/install.sh /path/to/laravel-project
kits/laravel/scripts/install.sh /path/to/laravel-project --dry-run
kits/laravel/scripts/doctor.sh /path/to/laravel-project
```

The target may be the Laravel app itself (`artisan` at the root) or a monorepo whose `platform/` (or another first-level child) contains `artisan`.

## Operator globals

```bash
composer global require laravel/lsp
npm install -g @tailwindcss/language-server intelephense
```

Then, in the Laravel app, after dependency approval:

```bash
composer require --dev laravel/boost
php artisan boost:install
```

Run `boost:install` from the directory that contains `artisan`, never from a parent that already has a hand-written `CLAUDE.md`.
