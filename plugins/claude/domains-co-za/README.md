# Domains.co.za by Rizonetech

Local Windows MCP integration for Domains.co.za reseller domain management. Claude Code copy; source lives in `<SDK>\plugins\claude\domains-co-za`. Registered for Claude by `<SDK>/plugins/claude/scripts/register_claude.py`. It shares no code, build or credential store with the Codex plugin of the same name.

## Capabilities

Read domains and expiry fields, availability, DNS, registry locks, transfer status, DS/glue records, TLDs, account funds, reseller pricing, and existing contact/nameserver templates. Prepare and execute individual nameserver, auto-renew, lock, renewal, template-based registration and DNS record changes. Every write requires an exact local preview; previews expire after ten minutes or a restart and are consumed before sending. Writes are never retried automatically. Provider code 2 means queued.

Domain list pagination is deliberately conservative: the current documentation lists only the `tld` filter. The plugin slices the returned array locally and exposes provider totals and coverage. It does not invent server paging support. The API response limit is 5 MB, chat output 200 KB. GET transient failures retry once after at most five seconds; all calls have 30-second timeouts and refuse redirects.

Transfers, domain deletion, bulk DNS replacement, contact editing, DNSSEC changes and billing operations are not implemented in this release. DNS record writes require Premium DNS. Registration requires existing template IDs.

## Credentials and setup

Official documentation uses `POST /login` with **username and password**, returning a JWT. It does not document a permanent API key. The **Conclave** vault placeholder is **Domains.co.za Reseller API**. Fill its username and password, or its concealed **API token** field with an issued JWT. If both are populated, import chooses username/password.

Prerequisites: Windows, Node.js 22+, PowerShell; 1Password CLI is needed only for an explicit import. No runtime 1Password dependency exists.

```powershell
# Import once after completing the Conclave placeholder:
& <SDK>\plugins\claude\domains-co-za\scripts\configure.ps1 -ImportFrom1Password
# Or enter username/password locally with a hidden password prompt:
& <SDK>\plugins\claude\domains-co-za\scripts\configure.ps1
# Or store a provider-issued JWT using a hidden local prompt:
$credential = Read-Host 'API bearer token' -AsSecureString
& <SDK>\plugins\claude\domains-co-za\scripts\configure.ps1 -Token $credential
$credential.Dispose()
# Presence only, no decryption or 1Password:
& <SDK>\plugins\claude\domains-co-za\scripts\configure.ps1 -Status
# Harmless API check, no private account details returned:
node <SDK>\plugins\claude\domains-co-za\scripts\check-connection.mjs
```

Credentials are bundled into a Windows DPAPI CurrentUser-encrypted file under `%LOCALAPPDATA%\Rizonetech\Claude\DomainsCoZa\token.dpapi`. The directory ACL allows only the current account and SYSTEM. Non-secret `config.json` has a schema version; updates preserve unrelated fields. Empty/invalid imports do not overwrite working credentials. Secrets are never accepted as plaintext command arguments. A SecureString `-Credential` JSON bundle is also supported for local automation and isolated tests.

Every operation reloads encrypted credentials. Login JWTs are cached only in process memory for up to four minutes, shortened by the JWT expiration; changing the encrypted credentials invalidates that cache on the next operation. A bearer-only configuration requires manual refresh when it expires. For automatic two-factor login, add the existing authenticator setup secret (Base32 or otpauth TOTP URI) to the Conclave item as a one-time-password field or a concealed field named `Authenticator secret`, then explicitly reimport. It is encrypted together with the password and generates current TOTP codes locally. Keep the Windows clock synchronized. Alternatively run `scripts/login-with-code.ps1` to enter a current code in a hidden prompt and store the issued JWT; repeat when it expires. This plugin does not bypass or disable 2FA.

Updating the Conclave entry alone does not refresh the encrypted copy: rerun the explicit import. Normal operation never invokes `op`, prompts for 1Password, or falls back to it. On another computer, install the plugin and run setup again under that Windows account; do not copy DPAPI ciphertext. There are no arbitrary API host overrides.

## Claude Code (WSL)

Claude Code (user scope, all projects) runs `dist/server.mjs` through Windows Node, so DPAPI decryption works unchanged. Register or refresh every Claude connection plugin with `python <SDK>/plugins/claude/scripts/register_claude.py` on Windows and `bash <SDK>/plugins/claude/scripts/register-claude.sh` in WSL. `dist/server.mjs` is tracked in git, so a fresh checkout runs without a build. After a source change, rebuild with `python <SDK>/plugins/claude/scripts/build_claude.py domains-co-za` (it runs `npm run build` and records the sources' digest in `dist/source.sha256`) and commit the bundle; the session drift check warns while the bundle is stale. From WSL, refresh the encrypted credential straight from Conclave without a desktop prompt:

```bash
bash <SDK>/plugins/claude/scripts/import-domains-co-za.sh
```

## Build and verify

```powershell
cd <SDK>\plugins\claude\domains-co-za
npm ci
npm test
python ..\scripts\build_claude.py domains-co-za
pwsh -NoProfile -File tests/windows-setup.ps1
```

API references: https://docs.domains.co.za/ and its linked Postman collection. The HTML examples take precedence where the collection is stale (for example DS records). `POST` uses URL-encoded form bodies; GET/PUT/DELETE follow the documented PHP query encoding. Authentication always uses a POST body and is never placed in the URL.

Independently developed by Rizonetech. Not an official Domains.co.za product.
