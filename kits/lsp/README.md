# LSP kit

Additive overlay that gives a project's three agents (Antigravity, Claude Code and Codex) the stack's language servers. One table, `.conclave/lsp.json`, names the servers; everything else in the kit reads it.

The kit is being built in sections (`todo/04-tooling/TODO-01-lsp-kit.md`). What it installs today:

| File | What it is |
| --- | --- |
| `.conclave/lsp.json` | The server table, seeded empty: `{"schema_version": 1, "servers": []}` |

The table is the project's own file from the first install: `forge.py` never overwrites it, and a project that already has one keeps it byte for byte.

Still to come, each reading the same table: presets per stack and `scripts/lsp-servers.py` (D04 T01 §2), the diagnostics client `scripts/lsp-diagnostics.py` (§3), a Claude Code plugin generated from the table (§5), an MCP bridge for Codex and Antigravity (§6), and the `language-servers` skill and document (§7).

## Install

```powershell
python forge.py kit /path/to/project lsp [--dry-run]
python forge.py doctor /path/to/project lsp [--strict]
```

`python forge.py init /path/to/project --kit lsp` installs it with the base kit. The kit installs no language server: the operator installs those at user level, and the doctor will name each one that is missing once the table holds entries.

## Doctor

`python forge.py doctor <project> lsp` reports each file the kit installs as `ok` or `missing`. `python forge.py doctor <project>` with no kit named checks the project's stack kit or the base kit as before and, when this kit is installed, adds these checks and lists the kit under `also`.

The SDK does not install this kit in itself.
