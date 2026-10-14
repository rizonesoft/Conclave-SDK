# Laravel agent tooling

Every Laravel project starts or adopts this overlay.

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

One client: `scripts/lsp-diagnostics.py`. Three servers:

| Server | Binary | Install | Gate |
| ------ | ------ | ------- | ---- |
| laravel | `laravel-lsp` | `composer global require laravel/lsp` | yes (routes/views/env) |
| tailwind | `tailwindcss-language-server` | `npm i -g @tailwindcss/language-server` | yes |
| php | `intelephense` | `npm i -g intelephense` | no (on demand) |

```bash
python3 scripts/lsp-diagnostics.py --server laravel --server tailwind --staged
python3 scripts/lsp-diagnostics.py --server php path/to/File.php
```

A missing binary is `SKIPPED` (exit 3 when every requested server is missing), never a silent pass.

## Doctor

```bash
kits/laravel/scripts/doctor.sh .
```

Reports `ok` or `setup_required` for Boost, the three language servers, `artisan`, and `scripts/lsp-diagnostics.py`. It never installs anything.
