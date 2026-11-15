# Laravel agent tooling

Every Laravel project starts or adopts this overlay across Gemini (`.agents/`), Claude (`.claude/`), and Codex (`.codex/`).

## Boost

Laravel Boost is a **dev-only** project package plus an MCP server over the running app. It is not a global plugin.

1. From the directory that contains `artisan`: `composer require --dev laravel/boost` after dependency approval.
2. `php artisan boost:install` from that same directory. Never from a parent whose `CLAUDE.md` is hand-written. Boost writes inside `<laravel-boost-guidelines>` delimiters; keep hand-written instructions outside them.
3. Register the MCP server at the directory a session actually starts in:

```json
"laravel-boost": {
  "command": "php",
  "args": ["artisan", "boost:mcp"]
}
```

For a monorepo whose app lives in `platform/`, the args are `["platform/artisan", "boost:mcp"]` from the repo root. Point `.env` at a **development** database. Boost's `database-query` tool executes SQL against whatever that connection resolves.

## Language servers

The client and the server table are the LSP kit's, which this kit brings with it: `scripts/lsp-diagnostics.py` runs the servers that `.conclave/lsp.json` names, and the table is the only list of them. The Laravel kit adds three, each rooted at the folder that holds `artisan`:

| Server | Binary | Install | Gate? |
| ------ | ------ | ------- | ----- |
| `laravel-lsp` | `laravel-lsp` | `composer global require laravel/lsp` | yes (routes, config, views) |
| `tailwindcss` | `tailwindcss-language-server` | `npm i -g @tailwindcss/language-server` | yes |
| `intelephense` | `intelephense` | `npm install -g intelephense` | no (on demand; PHPStan, Pint gate) |

```bash
python3 scripts/lsp-diagnostics.py --server laravel-lsp --server tailwindcss --staged
python3 scripts/lsp-diagnostics.py --server intelephense path/to/File.php
python3 scripts/lsp-servers.py list
```

A server that is not installed is `SKIPPED` (exit 3 when no requested server could check anything), never a silent pass, and a server that could not finish its check fails the run. To change what a server is started with, edit its entry in `.conclave/lsp.json`; `scripts/hooks/laravel-lsp-pre-push.sh` runs the first two servers on the staged files.

## Doctor

```powershell
python forge.py doctor . laravel
```

Reports `ok` or `setup_required` for Boost, `artisan`, the LSP kit's files, the server table (`server-table`) and each server it names (`server:laravel-lsp`, `server:tailwindcss`, `server:intelephense`). It never installs anything.
