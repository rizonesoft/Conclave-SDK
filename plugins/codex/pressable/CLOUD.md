# Pressable cloud connection

Verified 2026-10-06.

- Private ChatGPT plugin: https://chatgpt.com/plugins/plugin_asdk_app_6ac558887c308191b19fda963788c4f1
- Account: derick@rizonetech.com, verified in the ChatGPT account menu.
- Tunnel: tunnel_6ac557da3d1481918ca095c4dfc5a985
- Organization: org-VfkunBEjlO1475uR3boR16f5
- Workspace: 57d36c1b-3247-428d-b6ac-45bc8bea0511
- Ubuntu service: rizonetech-mcp@pressable on conclave-srv, enabled at boot with automatic restart.
- Host files: /opt/rizonetech-mcp/pressable; encrypted provider credential: /etc/rizonetech-mcp/pressable.provider.cred.
- Private loopback health endpoint: http://127.0.0.1:18784. The dedicated instance launcher uses the existing encrypted tunnel key. Other provider service configurations are unchanged.

## Verification

Source and installed Windows plugin initialize six tools and authenticate through DPAPI with 1Password execution blocked. The Ubuntu bundle passes the same harmless provider check with systemd encrypted credentials. Tunnel health, readiness and control-plane polling pass. Service restart was checked; a full host reboot/outage was not performed.

ChatGPT discovered four read tools and two write/preview tools, and the private listing displays Connected. The official Pressable icon and accurate integration description were added. Existing host approval settings were not weakened.

Model-driven test: https://chatgpt.com/c/6ac55914-1a34-83ea-b4eb-86136e23ebcc

Only connection_status was requested. Result: connected=true, provider=Pressable, operations=54, credentialMode=systemd-encrypted, runtime1Password=false. No account/site contents were listed and no previews or hosting changes were executed. Mocked safety tests cover write confirmation, immutable targets, expiration, replay prevention, schema drift and uncertain-write behavior; actual provider write semantics were not exercised.

Local source version: 0.2.1. ChatGPT's automatically created cloud wrapper displays its own version 1.0.0; it is not the Node adapter version. The workflow skill is included in the local package; cloud access uses the MCP tool descriptions and operation schemas, not an uploaded standalone skill.

The user explicitly approved tunnel creation and private ChatGPT access. Nothing was publicly published. See README.md for setup, credential replacement, host migration and verification commands.

## WP-CLI extension verification (2026-10-07)

The existing six tools now expose 57 operations (36 reads, 21 changes). Added run_site_wpcli_commands, get_site_wordpress_operation and list_site_wordpress_operations using current authenticated official MCP schemas. Fourteen tests pass, including immutable WP-CLI previews, single-use dispatch, job identifiers/pagination, uncertain submission, shell/target escape rejection and media/footer command examples. Source authentication and the read-only pending-job history route passed on staging site 1798697. Runtime still reports no 1Password access.

No media import, footer update or other WP-CLI command was submitted during development. Real command completion/side effects remain untested; use the documented preview and poll workflow for the first approved command. Provider success logs may truncate output to 500 characters. Upgrade uses candidate verification before replacing code and preserves existing encrypted credentials and the tunnel.

Deployment result: 0.2.1 is installed in the Codex plugin cache and deployed on conclave-srv. The installed Windows bundle passed the probe with 1Password blocked; Ubuntu candidate verification passed with systemd-encrypted credentials. The existing Pressable service is active and tunnel health/readiness/control-plane polling pass.

ChatGPT Cloud verification in the existing test conversation above returned connected=true, operations=57, credentialMode=systemd-encrypted and runtime1Password=false. Live discovery and descriptions exposed all three new operations and the one-command preview policy. This was metadata-only verification; no WP-CLI command was submitted. Screenshot evidence: pressable-wpcli-cloud.png in the Codex visualization workspace for this task.
