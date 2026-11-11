# Website Router cloud access

Host: **conclave-srv**, managed privately over Tailscale SSH. Runtime Node.js: `/opt/rizonetech-mcp/node/bin/node`.

- Adapter: `/opt/rizonetech-mcp/website-router/server.mjs`
- Encrypted registry: `/etc/rizonetech-mcp/website-router.provider.cred` (root-only, systemd host encryption)
- Shared encrypted tunnel key: `/etc/rizonetech-mcp/tunnel-key.cred`
- Dedicated service: `rizonetech-mcp@website-router`
- Instance override: `/etc/systemd/system/rizonetech-mcp@website-router.service.d/override.conf`
- Loopback tunnel health port: `18785`
- Intended private ChatGPT account: **derick@rizonetech.com**

The encrypted registry and built adapter were deployed and all ten websites passed a harmless authenticated check from Ubuntu on 2026-10-07. The dedicated tunnel `tunnel_6ac577d42ce481918833ef0a5d67adb2` is created and its systemd service is enabled and active. The private ChatGPT plugin is connected: https://chatgpt.com/plugins/plugin_asdk_app_6ac57857bf008191a8c23ab9290c0aff . Tunnel live, ready and successful control-plane polling checks passed. Model-driven ChatGPT verification passed for all ten sites: [connection test results](https://chatgpt.com/c/6ac578bd-480c-83ea-85c8-efa0bacaab6e). The response reported systemd-encrypted credentials and runtime1Password false. No public endpoint or public plugin listing is created.

## Setup/update

On Windows, import/update the Conclave item(s), then run `scripts/sync-ubuntu.ps1`. It stages code over verified SSH, sends the registry through private stdin, validates it using a transient DynamicUser service, replaces the encrypted credential atomically and restarts only this service when enabled. `-Build` rebuilds first. The maintenance helper reads the existing Ubuntu sudo password from Conclave only during this explicit administration action.

Initial tunnel activation uses `scripts/activate-ubuntu.py <tunnel-id>` on the Ubuntu host after the dedicated private tunnel is approved and created. The script writes the per-instance runner and enables systemd startup/restart. Never run Windows and Ubuntu against the same tunnel simultaneously.

## Read-only verification

Run a transient systemd service with `LoadCredentialEncrypted=provider:/etc/rizonetech-mcp/website-router.provider.cred` to execute `probe.mjs server.mjs`. The probe discovers seven tools and checks every website. For an active tunnel:

```sh
/opt/rizonetech-mcp/bin/tunnel-client health --url http://127.0.0.1:18785 --require-control-plane-poll --json
```

The service has no runtime dependency on Windows or 1Password. A server outage stops calls without queuing changes or sending unsolicited notifications; ChatGPT can still display tool errors. Existing Atera, Domains.co.za, Bunny.net and Pressable services are not reconfigured.



ChatGPT's custom-MCP wrapper currently displays version 1.0.0 and generic listing fields; the source adapter is version 0.2.1. Its original router icon and capability descriptions were uploaded. The local package includes the website-management skill; the cloud connection receives the seven tools and their workflow descriptions.


## SSH/SFTP backup storage

The existing private tunnel carries SSH/SFTP operations through the same seven tools. Ubuntu stores encrypted backups under `/var/lib/rizonetech-website-router` (systemd private state directory, mode 0700). The backup key lives inside the encrypted provider registry. Windows uses `%LOCALAPPDATA%\Rizonetech\WebsiteRouter\state`. Preserve the backup key and encrypted backup files together when migrating; re-importing provider passwords alone does not restore old backup access.
