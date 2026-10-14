---
name: laravel-boost
description: "Use Laravel Boost MCP and Boost's own skills on a Laravel app. Prefer Boost tools over guessing framework APIs. Use when working in a Laravel tree with Boost installed."
---

# Laravel Boost

Boost is the MCP server registered as `laravel-boost` (`php <artisan> boost:mcp`) plus the skills `boost:install` wrote under the app. Do not write a second catalog of those tools.

1. Confirm `.env` points at a development database. Stop before calling `database-query` if it might be production.
2. Prefer Boost tools (`search-docs`, `database-schema`, `last-error`, `application-info`) over guessing a framework API.
3. Load Boost's `laravel-best-practices`, `pest-testing`, or `tailwindcss-development` when editing those surfaces.
4. Gates still win: Pest, Pint, PHPStan, `scripts/lsp-diagnostics.py`.
5. Run `boost:install` only from the directory that contains `artisan`.
