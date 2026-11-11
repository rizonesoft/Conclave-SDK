# Pressable by Rizonetech

Private hosting management through Pressable's official MCP server, wrapped with encrypted credential storage and explicit change previews. Source: `R:\Codex\pressable`. Independent integration, not endorsed by Pressable.

## Capabilities

Six MCP tools expose 57 reviewed operations: 36 reads and 21 prepared changes. Inspect sites, environments, domains attached to sites, backups/restores, PHP, WordPress, plugins/themes, logs, alerts and performance. Prepare creation/cloning, configuration, cache purges, backups/restores, plugin/theme updates and site/domain removal. Destructive operations require exact target review and explicit confirmation. Reviewed WP-CLI media/content commands and job-status reads are included. Arbitrary SSH/bash, PHP eval, SQL, credentials, collaborator access and DNS record editing are not exposed. Novamira is discontinued.

`discover_operations` lists supported operations; `describe_operation` supplies their schemas; `read_operation` handles reads. `prepare_change` captures exact immutable parameters and site details in a five-minute preview. `execute_change` consumes it before any provider execution. Restart invalidates previews; no automatic retry or offline queue. The caller must obtain human authorization and host approval settings remain in force. `confirmed: true` is not a separate human authentication mechanism. Provider schema drift fails closed; adding upstream operations requires review and a plugin update.

## Windows setup and rotation

Prerequisites: Node 22 or newer and PowerShell. Install the plugin from the Rizonetech marketplace. Run the source or installed package's `scripts/configure.ps1` for a hidden credential prompt, or pass a SecureString via `-Token`. For the existing Conclave recovery entry:

```powershell
& R:\Codex\pressable\scripts\configure.ps1 -TokenReference 'op://Conclave/ybrpgakuvfuuwc5srxjsrj7ff4/password'
& R:\Codex\pressable\scripts\configure.ps1 -Status
node R:\Codex\pressable\scripts\check-connection.mjs
```

Stores the token under `%LOCALAPPDATA%\Rizonetech\Pressable\token.dpapi`, encrypted for the current Windows account, with current-user/SYSTEM ACLs. Configuration is non-secret and unrelated settings survive updates. Normal operation never invokes 1Password; the live check explicitly blocks it. The process caches the credential until restart. After rotation restart/reload the plugin; changing the 1Password entry alone does not refresh the runtime copy.

On a new PC install prerequisites, clone/install the plugin, then run fresh import or hidden setup and the connection check. Do not copy DPAPI ciphertext across computers/accounts.

## Cloud runtime

Cloud adapter: conclave-srv through a dedicated outbound private OpenAI tunnel. Provider authentication terminates at `https://mcp.pressable.com`; credentials are never uploaded to ChatGPT. Ubuntu uses `/etc/rizonetech-mcp/pressable.provider.cred` with systemd LoadCredentialEncrypted. Service: `rizonetech-mcp@pressable`, loopback health port 18784. The adapter adds our preview controls; do not bypass it with an unrestricted direct connector while expecting those controls.

Deployment scripts install only Pressable and its systemd instance override. `deploy-ubuntu.py` consumes a provider token through stdin and refuses to overwrite an existing credential. `activate-ubuntu.py TUNNEL_ID` starts the tunnel only after the provider probe. `invoke-ubuntu.ps1` is an explicit maintenance helper: it uses the existing Conclave Ubuntu credential and sends secrets through an SSH pipe, never command arguments or temporary plaintext files. It is never called at runtime.

For rotation, copy/run `scripts/update-credential.py` on the server through interactive Tailscale SSH with sudo. It accepts hidden input, atomically replaces host-encrypted storage and restarts only Pressable. Re-import from Conclave on a replacement server; encrypted blobs are not portable.

Read-only host verification:

```sh
sudo systemd-run --quiet --wait --pipe --collect -p DynamicUser=yes -p LoadCredentialEncrypted=provider:/etc/rizonetech-mcp/pressable.provider.cred /opt/rizonetech-mcp/node/bin/node /opt/rizonetech-mcp/pressable/probe.mjs /opt/rizonetech-mcp/pressable/server.mjs
curl -fsS http://127.0.0.1:18784/readyz
```

An offline service returns a concise failure and never queues business changes. ChatGPT can still display a connection error. Inspect provider state after an uncertain write before considering a newly authorized attempt. No automatic write retries or background messages.

## Build and tests

```powershell
npm --prefix R:\Codex\pressable ci
npm --prefix R:\Codex\pressable test
& R:\Codex\pressable\tests\windows-setup.ps1
npm --prefix R:\Codex\pressable run build
```

`scripts/review-schemas.mjs` is explicit developer-only schema discovery, never automatic access expansion. The checked-in operation schemas are provider metadata, not account contents. Requests have deadlines, a 4 MiB response limit and bounded parameters. Pagination is explicit; one result is not a promise of full inventory. Provider failures omit raw error bodies; response credential fields and URL query strings are redacted.

## Icon and sources

Official 180px Pressable icon from https://pressable.com/wp-content/themes/pressable-com/assets/images/favicon/apple-touch-icon-2026.png, retrieved 2026-10-06 for private identification. This does not establish public redistribution permission or endorsement. Provider documentation: https://pressable.com/knowledgebase/get-started-with-pressable-mcp/ . No public submission is authorized.

See CLOUD.md for the verified tunnel, account connection and deployment status.
Verified delivery: nine safety tests and Windows setup/rotation tests pass; source, installed package, Ubuntu probe and ChatGPT connection_status succeed. No provider write was executed. See CLOUD.md for evidence and current connection IDs.

## WP-CLI extension

Version 0.2.1 adds reviewed WP-CLI submission plus operation status/history, bringing the total to 57 operations. Use the existing preview workflow. See [WP-CLI setup and workflow](WPCLI.md) for media import, footer updates, command restrictions and result verification. Credentials, host and tunnel identity are unchanged.


## Task-scoped approval and verification

The agent may approve changes within your explicit task after showing the concrete preview and checking preconditions/recovery. It must test and verify the actual result, stop dependent work on failed or uncertain verification, and ask before unclear or additional actions. Host confirmations remain in force. See the [shared standard](../docs/CHANGE_APPROVALS.md). Caller confirmation is an authorization assertion, not an independent human authentication gate.
