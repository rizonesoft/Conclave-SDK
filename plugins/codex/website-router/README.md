# Website Router by Rizonetech

One private plugin for registered WordPress websites. Every operation selects an explicit site ID; production, staging and regional copies stay separate. Cloud execution belongs on **conclave-srv**, with its own outbound private OpenAI tunnel. Windows supports local Codex use independently.

## Included

Version 0.2.1 adds six reads and five previewed changes for SSH/SFTP, including actual uploads, file edits, encrypted recovery and object-cache flushing.

Seven router tools: `list_sites`, `connection_status`, `discover_operations`, `describe_operation`, `read_operation`, `prepare_change`, `execute_change`.

The WordPress policy covers 55 read operations and 35 changes across WordPress core, Elementor, AIOSEO, Jetpack Forms, WPForms, WooCommerce and email diagnostics/management where installed. Availability varies by site. Unknown abilities and changed schemas remain visible for discovery but cannot execute until reviewed. Credential-creating `suremails/add-connection` is intentionally not exposed through chat.

Changes require an exact site-bound, five-minute, single-use preview and explicit user authorization. Previews are consumed before dispatch. There is no automatic write retry, queue, production fallback or bulk cross-site execution. The `confirmed` argument is a caller assertion; this is not an independently authenticated human approval system.

See [connections](CONNECTIONS.md), [cloud deployment](CLOUD.md) and [design](DESIGN.md).

## Add or update a website

Create/update an item in **1Password > Conclave** named `<Website> WordPress MCP`. Use a dedicated WordPress application password with only the required permissions. Fields:

| Field | Value |
| --- | --- |
| username | WordPress username |
| password | WordPress application password |
| site_url | Canonical HTTPS origin, e.g. `https://example.com` |
| endpoint | Exact HTTPS MCP endpoint on the same origin |
| environment | `production`, `staging` or `development` |

Import one item (keeps its existing site ID when updating):

```powershell
pwsh -File D:\Conclave-SDK\plugins\codex\website-router\scripts\configure.ps1 -ItemId '<item-id>'
pwsh -File D:\Conclave-SDK\plugins\codex\website-router\scripts\sync-ubuntu.ps1
```

Or import every eligible WordPress item with `-ImportAllWordPress`. Entries without the required MCP fields are reported as skipped. Novamira is excluded. Imports merge; deleting a vault entry does not silently delete a runtime connection. Remove a connection explicitly with `-RemoveId '<site-id>'`, then sync. Removal affects the router registry only.

Restart the local Codex plugin after import. The sync command replaces the host-encrypted registry and restarts only Website Router if enabled. No code change or new tunnel is needed when the new site uses reviewed schemas. New provider abilities/schema variants need a reviewed plugin update.

Manual setup is also supported:

```powershell
pwsh -File D:\Conclave-SDK\plugins\codex\website-router\scripts\configure.ps1 -Id example -Name 'Example' -SiteUrl https://example.com -Endpoint https://example.com/wp-json/mcp/mcp-adapter-default-server -Environment staging -Username agent
```

The password prompt is hidden. Do not put passwords in command arguments. `-Status` reports non-secret store presence. All connections, endpoint metadata and credentials are kept together inside `%LOCALAPPDATA%\Rizonetech\WebsiteRouter\token.dpapi`; configuration contains no secrets. Normal plugin calls never access 1Password.

## Build and verify

```powershell
Set-Location D:\Conclave-SDK\plugins\codex\website-router
npm ci --ignore-scripts
npm test
npm run build
node scripts/probe.mjs dist/server.mjs
codex plugin add website-router@rizonetech --json
```

The probe discovers all seven tools and checks WordPress, PHP over SSH and SFTP directory access on each configured site. Unit tests cover site isolation, preview expiry, schema drift, rotation, uncertain-write replay, private IP blocking and redaction. No live changes are used as tests.

## New computer or credential replacement

Install from source, import the same Conclave items on the new Windows account, build/install and run the probe. DPAPI ciphertext is bound to its Windows user/host and is not portable. Rotate an application password in WordPress and its Conclave recovery item, re-import and sync. For a replacement Ubuntu host, re-import and encrypt on that host; do not copy host-bound ciphertext. Preserve the existing tunnel identity and stop its old runner before activating its replacement.

## Troubleshooting and boundaries

Authentication or endpoint failures appear per site. Verify the application password, MCP adapter and canonical HTTPS URL. Redirects, query-string credentials, local/private destinations and arbitrary URLs are rejected. Requests have time/body limits and DNS destinations are checked on the actual TLS socket. Pages with provider schema changes show review-required until reviewed. A quiet service outage does not enqueue business changes; ChatGPT may still show a connection error.

Admin-only logins and local DDEV/database entries are not MCP endpoints. SSH/SFTP use separately imported, pinned credentials on the same site ID. See [file access](FILES.md) for setup, operations and limitations.

Official protocol reference: [WordPress MCP Adapter default server](https://github.com/WordPress/mcp-adapter/blob/trunk/docs/guides/default-server.md). Original router artwork is owned by Rizonetech; no provider logo is used.


## Task-scoped approval and verification

The agent may approve changes within your explicit task after showing the concrete preview and checking preconditions/recovery. It must test and verify the actual result, stop dependent work on failed or uncertain verification, and ask before unclear or additional actions. Host confirmations remain in force. See the [shared standard](../docs/CHANGE_APPROVALS.md). Caller confirmation is an authorization assertion, not an independent human authentication gate.
