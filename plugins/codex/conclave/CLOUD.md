# Conclave private cloud access

The cloud runner uses a dedicated OpenAI Secure MCP Tunnel and the existing Windows-to-WSL stdio launcher. It serves the same live `~/conclave` checkout as local Codex. Source stays in `<SDK>\plugins\codex\conclave`.

This PC must remain on, connected and signed in. WSL, Conclave's database and its configured vault must be available. The other integrations continue running on `conclave-srv`; this runner neither starts their Windows standby task nor changes their tunnel IDs.

## Current state (2026-10-06)

Dedicated tunnel: `tunnel_6ac540220efc819195db5fc2880226f3`. The Windows task is installed and running. Authenticated OpenAI polling, health and readiness checks passed; a stop/start cycle passed and the provider standby task remains disabled. The generated profile stores only an environment-variable credential reference. The private [Conclave by Rizonetech plugin](https://chatgpt.com/plugins/plugin_asdk_app_6ac5425e0434819189a8a56a765e6cba) is registered and connected to derick@rizonetech.com. ChatGPT discovered all eight existing tools, and the current Conclave icon is uploaded. A [read-only ChatGPT cloud health test](https://chatgpt.com/c/6ac54315-0318-83ea-9c5b-f4efa232bd45) succeeded: ChatGPT called Conclave MCP health, served /home/derickpayne/conclave as the codex profile, and reported executionAuthority=false. No proposal or approval writes were performed. ChatGPT currently groups all eight tools under Write; normal approval settings remain unchanged.

## Access and credentials

- Target account: `derick@rizonetech.com`, existing Rizonetech Platform organization and associated ChatGPT workspace.
- Keep the ChatGPT plugin private. Do not add other organizations/workspaces or publish it without the user's instruction.
- The official tunnel client makes outbound authenticated connections. Conclave's server remains stdio with no public or LAN listener.
- The existing Windows DPAPI CurrentUser tunnel key is decrypted only into the child tunnel process environment. Generated profiles contain an environment-variable reference, never a key value. Recovery remains in the Conclave 1Password vault; normal use makes no 1Password calls.
- Conclave's own configuration launcher continues to project its database credential. The tunnel key is filtered out of the Conclave launcher environment.
- The existing `codex` profile retains Conclave's policy. It is not an authentication mechanism; access depends on the private tunnel's organization/workspace permissions and ChatGPT account access.
- `propose_memory_write` may commit eligible additions. Creating an approval request never approves or executes it. Keep normal ChatGPT tool approvals, and never replay uncertain writes after an outage.

## Activation

First create a dedicated tunnel in [Platform tunnel settings](https://platform.openai.com/settings/organization/tunnels), using the existing organization/workspace association. Then, from the Windows user account that owns the DPAPI credential:

```powershell
node <SDK>\plugins\codex\conclave\scripts\check-connection.mjs
# Substitute the actual tunnel ID from Platform:
pwsh -NoProfile -File <SDK>\plugins\codex\conclave\scripts\Manage-Cloud.ps1 -Action Configure -TunnelId tunnel_REPLACE_WITH_ACTUAL_ID
pwsh -NoProfile -File <SDK>\plugins\codex\conclave\scripts\Manage-Cloud.ps1 -Action Install
pwsh -NoProfile -File <SDK>\plugins\codex\conclave\scripts\Manage-Cloud.ps1 -Action Start
pwsh -NoProfile -File <SDK>\plugins\codex\conclave\scripts\Manage-Cloud.ps1 -Action Status
```

`Install` registers the separate **Rizonetech Conclave Cloud Access** scheduled task. It runs with no window at this user's sign-in with limited privileges, without VBS, through `scripts/run-hidden.py`, so `pythonw` must be on `PATH`. Run `Install` again to apply a change to the task's definition. `Start` also re-enables a previously stopped task. It supervises only `rizonetech-conclave`, checks every 30 seconds and starts a stopped runtime; the official client handles network reconnection. No business writes are queued.

State lives in `%LOCALAPPDATA%\Rizonetech\Conclave\cloud.json`, `cloud-status.json` and `cloud-profiles`. The runner also resolves the existing packaged-Codex LocalAppData redirection. It reuses the approved tunnel-client installation at `<SDK>\plugins\codex\.local\tunnel-client\v0.0.15\tunnel-client.exe`; install/update the official client explicitly if that path is missing.

In ChatGPT's Plugins directory, choose **Add custom MCP server → Tunnel**, select the dedicated Conclave tunnel and create the private plugin with the Conclave icon and accurate description. Confirm discovery, then run a harmless health call from the intended account. A running local process alone does not prove the cloud account is connected.

## Stop, recovery and future tools

```powershell
pwsh -NoProfile -File <SDK>\plugins\codex\conclave\scripts\Manage-Cloud.ps1 -Action Stop
```

Stop disables the Conclave scheduled task and stops only its managed tunnel runtime. Local Codex access is unaffected. To resume, use Start. Stop before changing the configured tunnel ID.

For a new computer, follow [local setup](README.md), restore the tunnel key from the Conclave vault into that user's Windows-encrypted store using the approved credential import process, and configure the same tunnel only after stopping its old owner. Never run two computers against the same tunnel concurrently or copy host-bound encrypted blobs.

The server's tool list is discovered at connection time. After adding tools to Conclave, restart its tunnel runtime and refresh the ChatGPT plugin's tool list; update usage guidance and the check's expected tool inventory. Review new write effects before cloud use.

Reference: [OpenAI Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels).
