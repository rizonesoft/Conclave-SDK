# bunny.net by Rizonetech

Local Windows MCP integration for bunny.net CDN, DNS and storage administration. Claude Code copy; source lives in `<SDK>\plugins\claude\bunny-net`. Registered for Claude by `<SDK>/plugins/claude/scripts/register_claude.py`. It is not a Codex plugin and has its own credential store.

## Capabilities

Read pull zones (list and full settings), DNS zones with records and record IDs, BIND zone exports, storage zones and traffic statistics. Prepare and execute individual DNS record additions, updates and deletions, DNS zone creation, full or cache-tag pull zone purges and URL or wildcard purges. Every write requires an exact local preview that reads current state first; previews expire after ten minutes or a restart and are consumed before sending. Record updates and deletions re-read the record before sending and send nothing if it changed since the preview. Script, PTR, SVCB and HTTPS records are read-only. Writes are never retried automatically.

The client accepts only the endpoints listed in `src/client.js`; anything else is refused before the credential is loaded. Pull zone reads always send `includeCertificate=false`. Responses drop credential-bearing fields before they reach the model: storage passwords, pull zone token-auth keys, S3 signing keys and secrets, log forwarding tokens, TLS certificates and private keys, the WordPress bypass cookie, DNS script environment variables, edge-rule action parameters (which can carry origin authorization headers) and edge-rule trigger patterns (which can hold shared secrets for header, query string or cookie gates). Origin URLs lose any userinfo and query string. The account API key is also redacted from any value. GET transient failures retry once after at most five seconds; all calls have 30-second timeouts and refuse redirects. Responses are capped at 5 MB, chat output at 200 KB.

Pull zone, storage zone and DNS zone deletion, hostname and certificate management, edge rules, security settings, key resets, Stream and Storage file APIs are not implemented in this release.

## Credentials and setup

bunny.net's API uses one account-level API key (`AccessKey` header) with full account access; the provider offers no scoped keys for the core API. This plugin limits exposure by implementing only the operations above. Find the key at https://dash.bunny.net/account/api-key. The **Conclave** vault placeholder is **Bunny.net Account API**; put the key in its `credential` field.

Prerequisites: Windows, Node.js 22+, PowerShell; 1Password CLI is needed only for an explicit import. No runtime 1Password dependency exists.

```powershell
# Import once after completing the Conclave placeholder:
& <SDK>\plugins\claude\bunny-net\scripts\configure.ps1 -ImportFrom1Password
# Or enter the key locally with a hidden prompt:
& <SDK>\plugins\claude\bunny-net\scripts\configure.ps1
# Presence only, no decryption or 1Password:
& <SDK>\plugins\claude\bunny-net\scripts\configure.ps1 -Status
# Harmless API check, no private account details returned:
node <SDK>\plugins\claude\bunny-net\scripts\check-connection.mjs
```

From WSL, where the Conclave service account works without a desktop prompt, `bash <SDK>/plugins/claude/scripts/import-bunny-net.sh` streams the item straight into the encrypted store. The key never appears in an argument or on screen.

The key is stored as a Windows DPAPI CurrentUser-encrypted file under `%LOCALAPPDATA%\Rizonetech\Claude\BunnyNet\token.dpapi`. The directory ACL allows only the current account and SYSTEM. Non-secret `config.json` has a schema version; updates preserve unrelated fields. Empty or malformed keys never overwrite a working credential. Every operation reloads the encrypted credential, so a rotation takes effect on the next call with no restart.

Rotation: reset the key in the bunny.net dashboard (the old key stops working immediately), update the Conclave item, then rerun one of the setup commands. Updating Conclave alone does not refresh the encrypted copy. On another computer, install the plugin and run setup again under that Windows account; do not copy DPAPI ciphertext. There are no API host overrides.

## Claude Code (WSL)

Claude Code (user scope, all projects) runs `dist/server.mjs` through Windows Node, so DPAPI decryption works unchanged. Register or refresh every Claude connection plugin with `python <SDK>/plugins/claude/scripts/register_claude.py` on Windows and `bash <SDK>/plugins/claude/scripts/register-claude.sh` in WSL. `dist/server.mjs` is tracked in git, so a fresh checkout runs without a build. After a source change, rebuild with `python <SDK>/plugins/claude/scripts/build_claude.py bunny-net` (it runs `npm run build` and records the sources' digest in `dist/source.sha256`) and commit the bundle; Claude picks it up on its next session, and the session drift check warns while the bundle is stale.

## Build and verify

```powershell
cd <SDK>\plugins\claude\bunny-net
npm ci
npm test
python ..\scripts\build_claude.py bunny-net
pwsh -NoProfile -File tests/windows-setup.ps1
node scripts/verify-installed.mjs .
```

API reference: https://bunny.net/docs/api-reference and the core OpenAPI document at https://bunny.net/docs/api-reference/core/openapi.json. DNS record types are sent as the provider enum index (A = 0 through HTTPS = 14).

## Troubleshooting

- `bunny.net is not configured`: run `configure.ps1` (any mode) under the Windows account that runs the plugin.
- `HTTP 401`: the key was reset or mistyped. Refresh it from Conclave with one of the setup commands.
- `Result too large for chat`: use `search`, a smaller `perPage`, or a single-zone read.
- `Request outcome is unknown`: the connection dropped during a change. Read current state before preparing the change again.

Independently developed by Rizonetech. Not an official bunny.net product.
