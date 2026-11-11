# Outlook Graph by Rizonetech

Independent Microsoft Graph tools for the TickTick email workflow. Returns `internetMessageId`, `conversationId`, `parentFolderId`, categories and current Outlook links; reads message bodies and thread pages; creates unsent drafts; adds the existing TickTick category and files individual Inbox messages after preview and verification. No send, delete, category-creation or arbitrary HTTP tools exist. Microsoft does not endorse this integration.

Version 0.1.7 also updates **existing HTML reply drafts** with conditional,
body-only writes, preserving recipients, quoted history, categories, read state
and attachment inventory. See [HTML draft updates](docs/HTML_DRAFTS.md) for exact
identity inputs, readback, pacing and supported layouts.

Attachment baselines include raw content IDs and authored/quoted/document CID
reference coverage. Unknown IDs stay explicit; every inventory mismatch blocks
verification. Classification never permits automatic cleanup or write retries.

## Register the dedicated app

1. Sign in to the [Microsoft Entra admin center](https://entra.microsoft.com/) in the tenant that owns the mailbox. Go to Entra ID, App registrations, New registration. Name it **Codex Outlook Graph** and select accounts in this organisational directory only. Leave redirect URI empty for device-code authentication.
2. In Authentication, Advanced settings, enable **Allow public client flows**. Do not create a client secret or certificate.
3. In API permissions, add Microsoft Graph **delegated** permissions `User.Read`, `Mail.ReadWrite` and `MailboxSettings.Read`. Do not add `Mail.Send`, application permissions or shared-mailbox permissions. MSAL also requests standard OpenID/offline-access scopes to maintain the session. If tenant policy requires administrator consent, use its normal consent process; do not disable policy.
4. Copy the non-secret Application (client) ID and Directory (tenant) ID from Overview. In the Conclave vault's **Codex Outlook Graph** item, fill `clientId`, `tenantId` and `mailbox`. Use the expected mailbox address, not a client customer account. Tokens never go into this item or chat; recovery is a new sign-in.

App registration instructions are based on [Microsoft's registration guide](https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-register-app) and [device authorization flow](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-device-code). App registration and first sign-in remain interactive prerequisites. No registration or Microsoft permission grant is created by installing this package.

## Windows setup and WSL desktop use

Build once from this source directory:

```powershell
cd <SDK>\plugins\codex\outlook-graph
npm.cmd ci
npm.cmd run build
node dist/setup.mjs login
node dist/setup.mjs check
```

`login` asks for the non-secret tenant ID, client ID and mailbox, then prints Microsoft's device sign-in instructions in your terminal. Complete the sign-in yourself. The existing encrypted session is retained if authentication fails or the mailbox does not match. Use `node dist/setup.mjs import-config` instead to read those three setup fields once from Conclave before sign-in. Use `node dist/setup.mjs status` for presence only without decryption, Graph access or vault access.

Windows stores the session under `%LOCALAPPDATA%/Rizonetech/OutlookGraph/session.dpapi`, encrypted with DPAPI CurrentUser and current-user/SYSTEM directory access. The single encrypted record contains the MSAL cache and its binding configuration, replaced atomically. `config.json` is a non-secret status/configuration mirror; its unknown settings survive updates. Runtime authentication uses the complete encrypted record, so an interrupted mirror write cannot mismatch an old cache with new account settings. Secrets exist transiently in memory and private pipes only. Helpers are hidden and bounded. Normal tools never call 1Password.

Native WSL uses the same Windows user's DPAPI store through `powershell.exe` and `wslpath`, with a shared cross-process lock. No token is written to the WSL filesystem. Windows interop and the Windows profile must be available. After Windows sign-in:

```sh
cd <SDK>/plugins/codex/outlook-graph
. "$HOME/.nvm/nvm.sh"
nvm use 22
node dist/setup.mjs status
node dist/setup.mjs check
```

For another Windows account or computer, clone, build and run `login` again using the registration metadata from Conclave. Do not copy DPAPI ciphertext. To replace the current session, run `login` again; it verifies the intended mailbox before replacing the session. No plaintext refresh-token argument or hidden static-key prompt is appropriate for this delegated OAuth flow. Refresh is handled silently by MSAL when Microsoft allows it. Revoked/expired consent returns a clear sign-in requirement, without vault fallback or a rotation schedule. Each tool's token request reloads the encrypted cache, so a successful setup takes effect without a long-lived credential cache.

## Installation

From the repository root, register the marketplace if needed, then install on each host:

```powershell
codex plugin marketplace add <SDK>\plugins\codex
codex plugin add outlook-graph@rizonetech --json
wsl -d Ubuntu -- bash -lc 'codex plugin add outlook-graph@rizonetech --json'
```

The MCP launcher requires Node.js 22 or newer. If WSL starts with an older system Node, it selects a compatible installed nvm runtime without changing shell configuration.

Use a fresh Codex session for discovery. Build before installing because `dist/` is intentionally ignored by Git. The root `plugin.json` and `mcp.json` use the supported portable package format. Never edit installed cache files. Refresh/reinstall through the host after a source version update.

## Tool map

| Tool | Behaviour |
| --- | --- |
| `connection_status` | Harmless profile and Inbox check |
| `get_message` | Identity plus bounded body chunks; follow `nextBodyOffset` |
| `list_messages` | Search or structured sender/subject/date/conversation filter; folder may be `inbox` or `sentitems`; follow `nextCursor` |
| `list_folders`, `get_folder` | Paginated children and complete bounded ancestor path |
| `list_categories` | Existing categories only; follow `nextCursor` |
| `translate_message_id` | Documented Graph EWS/immutable-ID translation |
| `prepare_create_draft` | Preview new, reply or reply-all draft with exact to/cc and plain-text body |
| `prepare_tag_message` | Preview existing TickTick category addition, preserving other categories and Inbox placement |
| `prepare_file_message` | Preview category addition and individual Inbox move, with earlier-mail evidence |
| `execute_change` | Consume exact preview once, revalidate, execute and read back actual results |
| `get_html_draft` | Read an exact existing HTML draft and bounded attachment metadata |
| `prepare_update_html_draft` | Preview escaped authored paragraphs replacing only the section before a native quote |
| `execute_html_draft_update` | One conditional body-only update of the same draft, followed by readback |

Legacy `prepare_create_draft` bodies replace the generated reply body, including
quoted history, so only the supplied plain-text body is saved. Existing-HTML-draft
updates preserve quoted history and all recipient fields instead. Neither route
appends a signature or sign-off. Legacy creation requires explicit recipient lists;
identify the real person for contact forms and use notes for GitHub notifications.
No automatic draft deletion occurs after a partial failure.

Filing is one MCP tool execution containing separate Graph category and move operations. It is **not atomic**. Only messages directly in Inbox can be filed, only below Inbox/Processed or in the top-level Noise folder, and only when a supplied older message from the same sender or conversation already lives there. The existing TickTick category is required. The result is `verified` only when permanent identity, destination, categories and new link read back correctly. A partial/uncertain result includes the last stage and identifiers and stops dependent actions. Never repeat it automatically. Source records and preview contents are private mailbox data, kept in process memory and returned only to the requesting host; they are not application logs.

Previews expire after ten minutes, are immutable server-side and single-use, and vanish on server restart. State changes require a fresh preview. The agent may approve within the explicit user task after showing the preview. Host confirmation policies remain in force. This is not independent proof of human consent. Concurrent provider edits can still race a Graph operation; read-back failure is reported honestly rather than treated as transactional completion.

## Ubuntu cloud packaging

The separate `linux/` installer targets the existing conclave-srv runtime. It creates a random AES-GCM cache key, seals it with `systemd-creds` using the host key and installs a dedicated service. The systemd private credential directory supplies that key; the encrypted MSAL cache lives in the service's private state directory. No plaintext cache or runtime 1Password access is supported.

Stage the complete built plugin, then run `sudo python3 linux/install.py`. It installs files but starts nothing. Run `sudo /opt/rizonetech-mcp/outlook-graph/session.sh login` in your own interactive SSH terminal, then the same command with `check`. The device code stays in that terminal, not the service journal. Fresh-host recovery generates a new host key and requires fresh Microsoft sign-in.

Create a dedicated private OpenAI tunnel before activation. Put only its non-secret `OUTLOOK_GRAPH_TUNNEL_ID=tunnel_...` in `/etc/rizonetech-mcp/outlook-graph.conf`, retaining the existing encrypted `tunnel-key.cred`. Check port 18787 is unused, then `sudo systemctl enable --now rizonetech-outlook-graph`. Do not reuse another integration's tunnel or expose a public listener. Cloud deployment, tunnel registration and live authentication are separate from the local package installation and must be verified before claiming cloud readiness.

## Tests and troubleshooting

`npm test` runs mocked Graph/client, change-state, encrypted-store and MCP protocol tests. Native Windows also exercises real DPAPI in an isolated temporary profile. Native WSL runs Linux encrypted-cache tests and package discovery; use `setup status` to check its DPAPI bridge without sign-in. `node scripts/probe.mjs` checks the built MCP server and makes only read calls. Unit tests use synthetic email data and never mutate a live mailbox.

Missing sign-in: finish app registration and run `setup login`. Missing category: inspect category pagination; never create another TickTick category. HTTP 401/403: check consent/account policy, then reauthenticate if needed. HTTP 429: respect the bounded delay or retry the read later. Writes are never retried. Stale cursor: restart the bounded query and deduplicate by permanent identity. A stale lock after a crash is deliberately not stolen: confirm all setup/MCP processes using this store have stopped before removing the empty `session.lock` directory. Windows DPAPI errors require the owning account; other Linux environments require the documented systemd key and state configuration.

See [official API sources](docs/SOURCES.md) and the repository's [approval standard](../docs/CHANGE_APPROVALS.md).
