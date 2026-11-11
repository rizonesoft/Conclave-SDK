# Windows credentials and configuration rule

Applies to every current and future Rizonetech plugin in this repository. This is the user's chosen default, not an optional enhancement. Keep the implementation self-contained inside each plugin so an installed package works without the source checkout.

## Storage and normal operation

- Use Windows DPAPI CurrentUser encryption for API secrets. Store encrypted files under `%LOCALAPPDATA%/Rizonetech/<Plugin>/` and non-secret settings in `config.json` beside them. Include a configuration schema version.
- Restrict the storage directory to the current Windows user and SYSTEM. Set filesystem access rules without requiring administrator or ownership privileges.
- Never put secret values in source, manifests, Git, plugin caches, plaintext configuration, logs, tool responses, command-line arguments, or chat. Add encrypted-store extensions to `.gitignore` as defense in depth; real stores still belong outside the checkout.
- Normal use must decrypt locally without 1Password approval. Do not silently fall back to 1Password on missing, invalid, expired, or undecryptable credentials. Explain how to set or refresh them.
- A 1Password item may retain the recovery copy. Use 1Password only for explicitly requested initial import or refresh. Credentials entered directly need not depend on 1Password.
- Plaintext exists only in transient process memory and a private process pipe when needed. Launch helpers hidden with bounded timeouts. For Windows PowerShell helpers launched from PowerShell 7, remove the inherited `PSModulePath` to avoid loading incompatible modules.
- Keep providers' authentication and authorization requirements intact. Use documented least-privilege access for the implemented features. Do not promise a Windows-encrypted copy can migrate to another account or computer.

## Required configuration capabilities

Every plugin must ship a documented local setup entrypoint with these operations:

1. **Set or update:** an interactive hidden credential prompt, plus a `SecureString` input option for local scripted setup. Never require a plaintext token argument or a chat message.
2. **Import or refresh:** optionally accept a non-secret 1Password reference and perform a one-time read into Windows-encrypted storage.
3. **Status:** report mode and presence, without decrypting, displaying secrets, or triggering 1Password. Distinguish configuration presence from a successful API connection.
4. **Connection check:** use a harmless read-only API request and return a concise result without private response data. Support a verification that blocks 1Password subprocesses.
5. **Migration:** document clone/install, prerequisites, fresh credential setup on the new account/computer, required non-secret settings, restart/reload, and connection verification. Do not copy ciphertext as a recovery method.
6. **Rotation:** use the same setup entrypoint to replace an existing credential. Preserve unrelated configuration. Validate and encrypt before overwriting; use atomic per-file replacement. An empty value, failed import, or failed validation must not erase the working credential. Document that updating 1Password alone does not refresh the Windows copy.

Document any in-memory credential cache lifetime and how to make replacement effective immediately. Support a new process/restart or explicit reload; avoid long-lived stale credentials after rotation. Plugins requiring non-secret settings must validate them, document defaults, preserve unknown unrelated settings on updates, and expose their status without leaking secrets. Do not add arbitrary server URL overrides that could redirect credentials.

## Verification and reference implementation

Test fresh setup in an isolated directory, DPAPI round-trip, replacement, empty/invalid-input rejection, preservation of unrelated settings, non-secret status, and no 1Password runtime fallback. Never rotate the user's live credential just to test setup. Verify source and installed copies, not only a mock. Treat normal-operation API errors separately from credential-store errors.

Atera provides the initial implementation:

- `atera/scripts/configure.ps1`: hidden prompt, SecureString input, import, and status.
- `atera/scripts/credential-store.ps1`: storage, encryption, access rules, and atomic file replacement.
- `atera/scripts/import-windows-credential.ps1`: one-time 1Password import.
- `atera/src/credentials.js`: hidden, bounded runtime decryption and explicit failure behavior.
- `atera/tests/windows-setup.ps1`: isolated fresh-profile and rotation tests.
- `atera/scripts/check-windows-credential.mjs`: live connection verification with 1Password blocked.

Reuse this tested pattern, adapting only plugin identity, credential fields, required configuration, and provider authentication. Keep improvements consistent across plugins where applicable. Non-Windows implementations require an explicit supported alternative; do not silently use plaintext files.

## Persistent Windows service storage

When the packaged host redirects LocalAppData into its application cache, persistent services may use `%USERPROFILE%/.rizonetech/<Plugin>/` instead. Verify a fixed local disk and resolved placement, keep it outside synced folders and Git, and apply the same current-user/SYSTEM ACL and DPAPI rules. Service-issued credentials may be generated locally; retain secure replacement, optional explicit import, status, rotation and migration capabilities.

## Required 1Password vault and setup flow

- All AI-related 1Password entries MUST be created in the **Conclave vault**. Do not create entries in Personal or another vault.
- Create an empty, clearly named provider credential placeholder during plugin development. Derive its fields from the provider authentication documentation; do not assume every API uses a static key.
- Import completed credentials only on explicit setup or refresh into Windows DPAPI CurrentUser storage. Normal plugin operations MUST NOT call 1Password or fall back to it.
- Support secure setup, update and fresh setup on another computer. Updating the Conclave entry alone does not update the encrypted local copy.
