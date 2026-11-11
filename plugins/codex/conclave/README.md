# Conclave by Rizonetech

A Windows Codex plugin for the existing [Conclave](https://github.com/rizonetech/Conclave) MCP server in WSL. The plugin source lives in `<SDK>\plugins\codex\conclave`; application source and data stay in `~/conclave` in Ubuntu.

## Capabilities

| Tool | Purpose |
| --- | --- |
| conclave_mcp_health | Connection, vault and policy readiness |
| search_memory / read_memory | Scoped retrieval of Conclave memory |
| resolve_project_context | Repository identity and recalled project context |
| get_current_plan | Bounded TODO plan lookup |
| get_tool_health | Existing Conclave integration diagnostics |
| create_approval_request | Persist a request without deciding or executing it |
| propose_memory_write | Policy-routed proposal; eligible factual additions may commit automatically |

The desktop connection is a local stdio bridge. A dedicated private OpenAI tunnel also supports ChatGPT access; see [cloud setup and status](CLOUD.md). Both serve the same existing Conclave checkout and preserve its approval policy.

## Setup and configuration

Requires Windows Node.js 22+, WSL with an Ubuntu distribution, the Conclave checkout, its installed dependencies and the exact Node version in its `.nvmrc`. The launcher automatically selects that version from `~/.nvm/versions/node`; it never runs a package manager or loads interactive shell profiles.

Defaults work with Ubuntu and `~/conclave`. Inspect or update only the non-secret settings:

```powershell
node <SDK>\plugins\codex\conclave\scripts\configure.mjs status
node <SDK>\plugins\codex\conclave\scripts\configure.mjs set --distribution Ubuntu --repo-root /home/derickpayne/conclave
node <SDK>\plugins\codex\conclave\scripts\check-connection.mjs
codex plugin add conclave@rizonetech --json
```

Optional `--node-path /absolute/Linux/path/to/node` selects an installed runtime explicitly. Set it to an empty string to return to automatic discovery. Settings live in `%LOCALAPPDATA%\Rizonetech\Conclave\config.json`, outside Git and the installed cache; updates preserve unrelated fields. `CONCLAVE_PLUGIN_CONFIG` selects another non-secret configuration file for isolated checks. Restart the plugin session after settings or backend changes.

The manifest runs `node src/launch.mjs`, which starts WSL with argument-separated paths, sets the `codex` client profile, and invokes the checkout's canonical `scripts/mcp-conclave.sh`. That script retains ownership of database credential projection and MCP policy.

## Credentials and moving computers

The bridge owns no API key and stores no credentials. It does not copy Conclave database credentials into Windows DPAPI. Conclave's existing WSL configuration launcher remains the credential owner, so normal use does not query 1Password. This narrow adapter exception preserves the existing backend's security model; new independent API plugins still use the repository's encrypted credential standard.

On a new PC, install WSL/Ubuntu and Windows Node, clone Conclave to a local WSL filesystem, and follow that checkout's setup instructions for its pinned Node, dependencies, database and explicit credential provisioning. Use Conclave's documented `pnpm secrets:sync` flow only during authorized setup/credential replacement, with recovery values in the Conclave 1Password vault. Do not copy secret files between machines or place credentials in plugin configuration.

Then install this plugin, set its distribution/root, and run the connection check. See Conclave's `docs/infrastructure/configuration-and-credential-storage.md` and `docs/infrastructure/conclave-mcp-launch-contract.md` for the authoritative backend contract.

## Verification and troubleshooting

```powershell
npm --prefix <SDK>\plugins\codex\conclave test
node <SDK>\plugins\codex\conclave\scripts\check-connection.mjs
```

The bounded check initializes MCP, verifies the exact eight tools, calls authenticated health and reads one plan result. It prints identities/counts and outcomes, never recalled memory, provider credentials or raw server error output. It performs no proposal or approval writes and requires clean shutdown on stdin close.

- Missing WSL/distro: confirm `wsl --list --quiet`, then update the distribution.
- Missing checkout or runtime: configure the correct WSL root and install Conclave's exact `.nvmrc` version through its normal setup. Startup never installs anything.
- Vault, database or policy not ready: resolve the reported state inside Conclave using its configuration guide, then rerun the check. Do not inject DATABASE_URL into the plugin.
- Installed but tools absent in an existing conversation: start a new Codex conversation so it loads the newly enabled plugin.
- Running from another Windows folder still serves the configured Conclave checkout. The PC and WSL backend must be available.

The local `codex` profile is a policy selector, not a network authenticator. Private cloud access relies on the dedicated OpenAI tunnel and its restricted organization/workspace association. Do not expose Conclave through a public HTTP listener.

## Assets

The icon is Conclave's existing `public/icons/conclave-icon-512.png`, copied from its repository without modification. The cloud icon uses the current public 192px asset with lossless PNG recompression (8,337 bytes); decoded pixels were verified identical, meeting ChatGPT's 10 KB upload limit.

Enable the two WSL startup-failure tests explicitly with `$env:CONCLAVE_TEST_WSL = '1'` before `npm test`. The live check allows up to 30 seconds for the existing backend to release idle database connections on stdin close.

Verified on 2026-10-06: seven tests passed, the installed package exposed all eight expected tools, authenticated health served `/home/derickpayne/conclave` with the `codex` profile, a bounded plan read succeeded, and shutdown completed on stdin close. No memory proposals or approval requests were created during validation.


## Task-scoped approval and verification

The agent may approve changes within your explicit task after showing the concrete preview and checking preconditions/recovery. It must test and verify the actual result, stop dependent work on failed or uncertain verification, and ask before unclear or additional actions. Host confirmations remain in force. See the [shared standard](../docs/CHANGE_APPROVALS.md). Caller confirmation is an authorization assertion, not an independent human authentication gate.
