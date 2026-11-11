# Ubuntu cloud runtime

Production host: conclave-srv, Ubuntu 24.04, Tailscale 100.83.89.28. Source remains <SDK>\plugins\codex.

Services: rizonetech-mcp@atera and rizonetech-mcp@domains-co-za. Both are enabled at boot and automatically restart. Existing private OpenAI tunnel IDs and ChatGPT connections are retained. No public inbound MCP listener is exposed; Tailscale is for administration, outbound OpenAI tunnels carry cloud calls. Health endpoints bind to 127.0.0.1 ports 18781 and 18782.

Runtime: /opt/rizonetech-mcp, official Node v22.23.3 and tunnel-client v0.0.15. Installer verifies both release archives. Run install.py as root, passing JSON with atera, domains and tunnel strings through stdin, never command arguments or files. domains is the existing credential JSON string. Build both bundles and stage them as atera.mjs and domains-co-za.mjs alongside the Linux scripts. Installer does not start services until provider checks pass and Windows has stopped.

## Credentials and rotation

Encrypted files are root-only under /etc/rizonetech-mcp. systemd LoadCredentialEncrypted decrypts credentials into a private service credential directory. No runtime 1Password access. Recovery entries always belong in Conclave. Host encryption protects credentials at rest; it does not protect against a compromised root account. Do not copy these encrypted blobs to a different machine: re-import from Conclave there.

Update a credential over an interactive Tailscale SSH session:

1. Run sudo -v to authenticate before supplying any credential.
2. Run sudo python3 /opt/rizonetech-mcp/update-credential.py atera (or domains-co-za or tunnel-key).
3. Paste the replacement at the hidden prompt. Domains accepts the complete login JSON including totpSecret, or a bearer JSON object.
4. The updater validates shape, encrypts atomically and restarts the affected service(s). Run the harmless provider probe afterwards. Update the recovery entry in Conclave as well.

Do not put passwords, keys or authenticator secrets into chat, shell history, Git, service units, logs or plaintext files.

## Operations

    sudo systemctl status rizonetech-mcp@atera rizonetech-mcp@domains-co-za
    curl -fsS http://127.0.0.1:18781/readyz
    curl -fsS http://127.0.0.1:18782/readyz

Read-only MCP/provider probe (change plugin and count to domains-co-za and 23 for Domains):

    sudo systemd-run --quiet --wait --pipe --collect -p DynamicUser=yes -p LoadCredentialEncrypted=provider:/etc/rizonetech-mcp/atera.provider.cred /opt/rizonetech-mcp/node/bin/node /opt/rizonetech-mcp/probe.mjs /opt/rizonetech-mcp/atera/server.mjs 10

Windows scheduled task Rizonetech Plugin Cloud Access is disabled and its managed tunnel aliases are stopped. Local Codex DPAPI credentials are retained. Rollback: stop and disable BOTH Ubuntu services first, then enable/start the Windows scheduled task. Never run both hosts on the same tunnel simultaneously.

Domains writes retain single-use previews and no automatic provider-write retries. Service restart invalidates outstanding previews. An offline Ubuntu server makes cloud tools unavailable; ChatGPT may display a connection error. End-to-end outage/replay behavior and a model-driven cloud account call have not yet been verified. Full host reboot was not performed; service restart was tested.
Verified on 2026-10-05: both live provider probes passed; 32 plugin tests passed; both services enabled and active after restart; ChatGPT refreshed all 10 Atera and 23 Domains tools through the Ubuntu processes, with zero polling failures. Cloud app descriptions updated. Temporary migration sudo credential removed after completion.


Invoke-Ubuntu.ps1 is a migration-only helper. It requires a temporary DPAPI sudo credential that was removed after migration, so it is not the normal administration entrypoint. Use interactive Tailscale SSH for ongoing maintenance. The installer never starts tunnel services; start them explicitly only after successful checks and stopping the previous host.

## Bunny.net

Bunny.net uses rizonetech-mcp@bunny-net, port 18783 and 18 tools. Its dedicated tunnel is tunnel_6ac48be40bf0819186a83bbc42dcd6bb. Rotate with update-credential.py bunny-net; tunnel-key rotation restarts all three services. For the provider probe substitute bunny-net and 18 in the command above. Windows has no Bunny cloud standby entry; Ubuntu is its cloud runtime. Initial deployment uses bunny-net/scripts/deploy-ubuntu.py with a credential through stdin; repeat code deployments copy the built bundle without replacing the encrypted provider credential.

## Pressable

Pressable uses rizonetech-mcp@pressable on port 18784 with dedicated tunnel tunnel_6ac557da3d1481918ca095c4dfc5a985. Its six MCP tools expose 34 reviewed reads and 20 preview/confirmation-gated changes through Pressable's official MCP server. The instance uses /opt/rizonetech-mcp/pressable/run-tunnel.sh via its own systemd override; the shared provider launcher is unchanged.

Recovery is the existing Pressable MCP item in Conclave. Rotate through `sudo python3 /opt/rizonetech-mcp/pressable/update-credential.py` in interactive SSH. When rotating the shared tunnel key, restart Pressable as well as the original services; the legacy shared updater lists only the original three. See ../../pressable/CLOUD.md for the private ChatGPT connection and verified read-only test, and ../../pressable/README.md for build/setup and host migration.

## Website Router

The separate Website Router instance uses port 18785 and its own encrypted registry. See [deployment and connection state](../../website-router/CLOUD.md). Adding a website reuses this integration's tunnel.
