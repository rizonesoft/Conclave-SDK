# Language servers

The project's language servers are listed in one table, `.conclave/lsp.json` (`python scripts/lsp-servers.py list`). Three things read it:

- `python scripts/lsp-diagnostics.py` runs the servers over files and has an exit code. It is the gate.
- `python scripts/lsp-servers.py plugin` generates a Claude Code plugin, so Claude Code runs the servers while it edits.
- `scripts/lsp-mcp-bridge.py` is an MCP server that gives any agent the servers, read-only. Codex and Antigravity have no language server plugin, so this is how they reach them.

## The MCP bridge

The bridge offers four tools, each read-only. `file` is a path from the project root; `line` and `column` count from 1, a column in characters, in what is asked and in what is answered, so a place the bridge returns can be given back to it.

| Tool | Arguments | Answer |
| --- | --- | --- |
| `diagnostics` | `file` | What every server that serves the file reports, with each server's outcome |
| `definition` | `file`, `line`, `column` | Where the symbol is defined, as `file:line:column` |
| `references` | `file`, `line`, `column` | Where the symbol is used, one `file:line:column` a line |
| `hover` | `file`, `line`, `column` | What the server says of the symbol |

It starts a server on the first call that needs it and keeps it running, sends a file again when it has changed, and ends every server when the agent ends the bridge. A call the agent cancels stops waiting at once. It cannot rename, format or apply an edit: the only requests it sends a server are `initialize`, `shutdown`, `textDocument/hover`, `textDocument/definition` and `textDocument/references`. It installs no server: `python forge.py doctor <project> lsp` says which are missing.

## Registering the bridge

Each entry below runs `python scripts/lsp-mcp-bridge.py`. The path is relative, so it is read from the folder the agent is started in: start the agent at the project root, or give the script's full path. Where `python` is not Python 3 on the machine, name `python3`.

Each registration was confirmed on 2026-11-15 on Windows 11 by a real session of that agent, which found the tools, called `diagnostics` and got a stub server's diagnostic back (the SDK's `tests/test_lsp_kit.py`, run with `CONCLAVE_LIVE_AGENTS=1`).

### Codex

Confirmed with Codex 0.169.0. From `codex mcp add --help`: `codex mcp add [OPTIONS] <NAME> (--url <URL> | -- <COMMAND>...)`.

```text
codex mcp add conclave-lsp -- python scripts/lsp-mcp-bridge.py
```

It writes this table to `~/.codex/config.toml`, the user's configuration (seen by running the command against a scratch `CODEX_HOME`):

```toml
[mcp_servers.conclave-lsp]
command = "python"
args = ["scripts/lsp-mcp-bridge.py"]
```

In an interactive session Codex asks before the first call of a tool. A run with no one to ask (`codex exec`) refuses the call ("MCP tool call requires approval, but approval policy is never") unless the server's tools are approved in the configuration. The tools are read-only, so approving them is safe:

```toml
[mcp_servers.conclave-lsp]
command = "python"
args = ["scripts/lsp-mcp-bridge.py"]
default_tools_approval_mode = "approve"
```

`codex mcp get conclave-lsp` shows the entry and `codex mcp remove conclave-lsp` removes it.

### Antigravity

Confirmed with Antigravity 1.5.9 (`agy`). From `agy mcp add --help`: `agy mcp add [flags] <name> <commandOrUrl> [args...]`, with flags before the name.

```text
agy mcp add conclave-lsp python scripts/lsp-mcp-bridge.py
```

The entry goes to the user's configuration (`~/.gemini/config/mcp_config.json` on the machine this was confirmed on). `agy mcp list` shows it and `agy mcp remove conclave-lsp` removes it. Its session-only `--settings` option does not take MCP servers (`unknown setting "mcpServers"`), so there is no registration for one run.

### Claude Code

Claude Code has the plugin (`python scripts/lsp-servers.py plugin`), which gives it the servers natively, and needs the bridge only where the plugin is not used. Confirmed with Claude Code 2.1.325, from a project `.mcp.json` or a file given with `--mcp-config`:

```json
{
  "mcpServers": {
    "conclave-lsp": {
      "command": "python",
      "args": ["scripts/lsp-mcp-bridge.py"]
    }
  }
}
```

A project that already has an `.mcp.json` adds the `conclave-lsp` entry to its `mcpServers`. `python forge.py doctor <project> lsp` reports `mcp-bridge` as `ok` when it finds one there.
