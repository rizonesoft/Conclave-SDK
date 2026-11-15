# Atera by Rizonetech

Read-only Atera device inventory, monitoring, alerts, and patch visibility in Codex. Independently developed by Rizonetech; not affiliated with or endorsed by Atera.

## Tools

| Tool | Purpose |
| --- | --- |
| `connection_status` | Verify token and Agents read access without returning inventory |
| `list_agents` / `get_agent` | Endpoint inventory and reported online/monitoring state |
| `find_agents_by_machine` | Paginated Atera machine-name lookup |
| `list_monitors` / `get_monitor` | SNMP, TCP, HTTP, and generic monitors |
| `list_alerts` / `get_alert` | Open, Resolved, or Snoozed alerts and individual details |
| `list_agent_patches` | Available or installed patches by DeviceGuid |
| `monitoring_summary` | Endpoint and open-alert counts, with explicit scan coverage |

No write endpoints, remote commands, patch installation, alert resolution, or background schedules are included. Monitor readings are those returned by Atera, not a live telemetry stream. SNMP credentials, Windows/Office product keys, and URL query strings are omitted from returned data.

## Setup

Requires Node.js 22+ and Windows PowerShell for normal Windows use. The 1Password CLI (`op`) is optional and needed only when importing or refreshing from 1Password. Local install runs on this computer; it does not deploy a cloud service.

1. In Atera, use **Admin > Data management > API** to create a token with **Read** permission for **Agents, Devices, and Alerts**. Check expiration and allowed IP addresses.
2. Fill the **credential** field of the **Atera API** item in your **Conclave** 1Password vault. Do not paste the token in chat or commit it.
3. Import the token once into Windows account-encrypted storage:

   ```powershell
   ./scripts/import-windows-credential.ps1 -TokenReference 'op://Conclave/Atera API/credential'
   ```

   This creates `%LOCALAPPDATA%/Rizonetech/Atera/token.dpapi`, encrypted with Windows DPAPI for the current user, and a non-secret `config.json` selecting that mode. Both stay outside Git and the plugin cache. The directory grants access to the current account and SYSTEM. Normal plugin requests decrypt locally and never call 1Password or fall back to it. The plaintext token exists only in process memory and the private child-process pipe; it is not saved to a plaintext file or placed on the command line.

   Keep the original in 1Password. After rotating it, rerun the import command to refresh the encrypted copy. Moving to another Windows account or computer requires a fresh import. Start a fresh plugin process after rotation (or allow the five-minute in-memory cache to expire). Changing the token in 1Password alone does not update this local copy.

   Alternatively, run `./scripts/configure.ps1` to enter a token through a hidden local prompt. It uses the same Windows-encrypted store and needs no 1Password installation. `ATERA_API_TOKEN` is an advanced process-environment override; do not persist it in Git or plaintext settings.

4. Build and verify:

   ```powershell
   cd D:\Conclave-SDK\plugins\codex\atera
   npm ci
   npm run icons
   npm run build
   npm test
   codex plugin marketplace add D:\Conclave-SDK\plugins\codex
   codex plugin add atera@rizonetech
   node scripts/check-connection.mjs
   ```

5. Start a new Codex chat after installation; restart the app if necessary. Confirm the Atera tools are available and ask for an endpoint/alert summary. A CLI installation alone does not verify desktop tool discovery.

The compiled `dist/server.mjs` bundles runtime dependencies so the installed plugin needs only Node and Windows PowerShell for the default authentication mode. Rebuild before install/update. Edit source, never the installed cache. `npm ci` uses the checked-in lockfile.

## Pagination and failure handling

Lists return one page (default 20, maximum 50 records). Follow `nextPage` to finish a scan. No server-returned URL is followed. Summary scans default to two pages each and are capped at ten per collection; `complete: false` means partial results. Agent and alert pages are not an atomic snapshot. The summary excludes SNMP/TCP/HTTP/generic monitor inventory.

Requests use fixed HTTPS Atera endpoints, GET only, a 15-second timeout, at most three attempts, serialized requests, and a 250 ms minimum interval. `Retry-After` is respected; delays above 15 seconds return a retry-later error rather than blocking a chat or retrying early. 401/403 errors are not retried. Response bodies are bounded to 4 MiB, tool results to 200 KB; request smaller pages when necessary. Errors omit raw upstream bodies and credential values.

If authentication fails, check the Atera token's expiration, Read permissions, and IP restrictions. A Windows decryption failure requires re-import under the correct Windows account; it does not trigger 1Password. Use `node scripts/check-windows-credential.mjs` to verify a real Agents request while blocking all 1Password subprocesses. The connection checker checks Agents access only; Devices and Alerts must also be tested before claiming full connectivity.

## Source documentation

- [Atera API portal](https://api.atera.com/devportal#auth)
- [OpenAPI specification](https://api.atera.com/proxy/publicapi/v3/openapi), snapshot in `docs/openapi.json`, retrieved 2026-10-05.
- [Using the Atera API](https://support.atera.com/hc/en-us/articles/219083397-Using-the-Atera-API)

The current specification declares Bearer-token authentication and `/api/v3/` paths. This integration uses those definitions, not legacy API-key header examples. No historical telemetry or other undocumented endpoints are assumed.

## Set, update, or check credentials

Run from `D:\Conclave-SDK\plugins\codex\atera` (or the actual plugin directory):

```powershell
# Set a token on a new computer, or replace the current token. Input is hidden.
./scripts/configure.ps1

# Optional: one-time import or refresh from 1Password.
./scripts/configure.ps1 -TokenReference 'op://Conclave/Atera API/credential'

# Show mode and file presence only; no secret read and no 1Password prompt.
./scripts/configure.ps1 -Status

# Check the current token using a harmless API request.
node scripts/check-windows-credential.mjs
```

For local automation, `-Token` accepts a PowerShell `SecureString`, for example one obtained with `Read-Host -AsSecureString`. Do not pass plaintext tokens on the command line. Setup preserves unrelated configuration, rejects empty updates, and atomically replaces each encrypted/configuration file. Start a new plugin process after a change to bypass the five-minute memory cache immediately.

## Move to another computer

1. Clone `https://github.com/rizonetech/Conclave-SDK` to the desired directory and install Node.js 22+.
2. In `<checkout>/plugins/codex/atera`, run `npm ci` and `npm run build`.
3. Run `./scripts/configure.ps1` to enter the token locally, or install/authorize 1Password CLI and use `-TokenReference` once. Do not copy `token.dpapi` from the old machine.
4. Register the Codex catalogue with `codex plugin marketplace add <checkout>/plugins/codex` and install `codex plugin add atera@rizonetech`.
5. Run the connection check and start a new chat. Check Atera's token IP restrictions if the new computer uses another public IP.

Test credential setup with `./tests/windows-setup.ps1`. It uses synthetic values in an isolated temporary directory and does not change your live credentials. See the repository's [credential rule](../docs/WINDOWS_CREDENTIALS.md).

## Task-scoped approval and verification

The agent may approve changes within your explicit task after showing the concrete preview and checking preconditions/recovery. It must test and verify the actual result, stop dependent work on failed or uncertain verification, and ask before unclear or additional actions. Host confirmations remain in force. See the [shared standard](../docs/CHANGE_APPROVALS.md). Caller confirmation is an authorization assertion, not an independent human authentication gate.
