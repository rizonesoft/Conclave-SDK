# Laravel kit

Additive overlay for a Laravel application so every project gets the same agent toolchain across Gemini (`.agents/`), Claude (`.claude/`), and Codex (`.codex/`): Laravel Boost, Laravel LSP, Tailwind LSP, and the PHP LSP (Intelephense).

This kit does not scaffold a Laravel app. It does not install global binaries. It copies the overlay into an existing tree that already has `artisan`, and it tells you what is still `setup_required`.

Install `kits/base` (or `python forge.py init`) first when the repo should speak the full agent contract.

## What lands

| Path | Role |
| ---- | ---- |
| `boost.json` | Boost skill list placed at the Laravel app root |
| `scripts/hooks/laravel-lsp-pre-push.sh` | Pre-push check (missing servers skip, never pass) |
| `docs/laravel-agent-tooling.md` | How to wire Boost MCP and the three language servers |
| `.agents/skills/laravel-boost/SKILL.md` | Gemini / Antigravity (`agy`) skill copy |
| `.claude/skills/laravel-boost/SKILL.md` | Claude Code (`claude`) skill copy |
| `.codex/skills/laravel-boost/SKILL.md` | Codex skill copy plus `agents/openai.yaml` |
| `.mcp.json` | Created when missing; prints `laravel-boost` fragment if present |

The kit brings the `lsp` kit with it (`kits/lsp/README.md`). The diagnostics client `scripts/lsp-diagnostics.py`, its library under `scripts/lib/` and the server table `.conclave/lsp.json` are that kit's files, recorded under `lsp` in `.conclave/kits.json`, so `forge.py diff` and `forge.py update` treat them as the LSP kit's. The table is the only list of servers: the client holds none.

The install adds the `laravel` preset's servers to the table, each rooted at the folder that holds `artisan`: `laravel-lsp`, `intelephense` and `tailwindcss` (with Blade files and the Laravel settings). The result names them under `lsp_servers`:

- `added`: a server the table lacked.
- `replaced`: an entry that was still exactly what another preset writes for that name (the `web` preset's `tailwindcss`, which `toolchain-web` adds and which has no Blade). The project chose nothing in it, so the Laravel preset's entry takes its place.
- `kept`: an entry left as it was. An entry the project changed is never changed.
- `differs`: a kept entry that is not the Laravel preset's, so the operator knows what it lacks.

The order of the kits does not matter: `lsp`, `toolchain-web` and `laravel` in any order end with the same table. A table that does not load or cannot be written is left as it was and reported under `lsp_servers` and `merge_needed`.

## Install

```powershell
python forge.py kit /path/to/laravel-project laravel [--agent all|gemini|claude|codex] [--dry-run]
python forge.py doctor /path/to/laravel-project laravel
```

The target may be the Laravel app itself (`artisan` at the root) or a monorepo whose `platform/` (or another first-level child) contains `artisan`.

## A project from before the LSP kit

A Laravel project installed before the LSP kit has its own `scripts/lsp-diagnostics.py`, with its three servers in the code (`laravel`, `tailwind`, `php`), and a hook that passes those names. It moves to the shared client with the commands it already has, and its client and hook work together at every step:

1. `python forge.py kit <project> laravel` brings the LSP kit (the table, the client's library) and keeps the project's client and hook as they are. `python forge.py diff <project> laravel` then reports the old client as `project-only`: the Laravel kit no longer ships it.
2. `python forge.py update <project>` replaces a client the project never changed with the LSP kit's (`kit-newer` under `lsp`) and a hook it never changed with the new one.
3. A client the project changed is left for a merge (`python forge.py update <project> --kit-new` writes the kit's beside it). The new hook works with either client: it passes the table's names to the LSP kit's client and the old names to a client that does not use `lsp_client`.
4. A hook the project changed is left for a merge too, and while it still passes the old names the client is not replaced under it: `update` lists the client under `left` with the reason. Merge the hook, then update again.

## Operator globals

The `toolchain-web` kit checks the tools this kit relies on (PHP, Composer, Node, a package manager, and PHPStan, Pint and PHP_CodeSniffer in the app's `vendor/bin`) against pins the project owns, and compares the pins with `composer.json`'s own PHP constraint: `python forge.py kit <project> toolchain-web`, then `python forge.py doctor <project> toolchain-web`.

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
