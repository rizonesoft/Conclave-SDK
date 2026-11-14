# Bunny.net by Rizonetech

Private CDN, DNS and Storage management for Codex and ChatGPT.

[Open the connected ChatGPT plugin](https://chatgpt.com/plugins/plugin_asdk_app_6ac48ced876c8191bdee42d5aaa0d42c) under derick@rizonetech.com. The source lives in D:\Conclave-SDK\plugins\codex\bunny-net and the private catalog is Rizonetech. This integration is independently maintained; Bunny.net does not endorse it.

## Capabilities

18 MCP tools provide zone inventory/details, CDN statistics, Storage browsing and small UTF-8 file reads. Preview tools cover URL/full-zone cache purges, standard DNS record creation/update/deletion, text file uploads and individual file deletion. Only execute_change mutates Bunny resources. Changes require user confirmation, an expiring single-use preview and matching target. Advanced DNS records (acceleration, monitoring, smart routing or script/pull-zone integration) must be updated in the Bunny dashboard; standard updates preserve omitted priority, weight, flags, port, disabled state and comment fields. No automatic write retries; no recursive deletion, binary upload, zone lifecycle or Stream administration.

Examples:
- List my CDN, DNS and Storage zones and report pagination coverage.
- Show CDN bandwidth and errors for a specified zone over the last seven days.
- Inspect the DNS records for example.com.
- Preview a TXT record change and wait for my confirmation.
- Browse a Storage folder and read its README file.

## Windows setup or key replacement

Requirements: Node.js 22+, PowerShell and the local plugin installed from this repository's rizonetech catalog.

    npm ci
    npm run build
    powershell -NoProfile -File .\scripts\configure.ps1

The credential prompt is hidden and replaces an existing key safely. Alternatively, import once from the Conclave recovery item (1Password may request approval):

    .\scripts\configure.ps1 -TokenReference 'op://Conclave/Bunny.net Account API/credential'
    .\scripts\configure.ps1 -Status
    node .\scripts\check-connection.mjs

Storage is %LOCALAPPDATA%\Rizonetech\BunnyNet\token.dpapi with a non-secret config.json; DPAPI is bound to the Windows user and machine. Existing unrelated configuration is preserved. Runtime never invokes 1Password. On a new computer reinstall/build the plugin, then run setup or re-import from Conclave. Do not copy DPAPI ciphertext between computers. Restart the plugin process after changing credentials. Keep the recovery item updated separately.

Install with codex plugin add bunny-net@rizonetech. Source changes require a rebuild and supported plugin refresh; do not edit the installed cache.

## Ubuntu cloud service

Authoritative cloud host: conclave-srv. Service: rizonetech-mcp@bunny-net. Dedicated private tunnel: tunnel_6ac48be40bf0819186a83bbc42dcd6bb. Local health port: 18783. The runtime bundle is /opt/rizonetech-mcp/bunny-net/server.mjs. Credentials live encrypted at /etc/rizonetech-mcp/bunny-net.provider.cred; systemd supplies them privately at runtime. The account key stays on the host. Read results requested by ChatGPT travel through the private tunnel.

See [Ubuntu operations](../cloud-access/linux/README.md). Over an interactive SSH connection, authenticate sudo, then run:

    sudo python3 /opt/rizonetech-mcp/update-credential.py bunny-net

Paste the replacement at the hidden prompt, then run the harmless provider probe with bunny-net and tool count 18. New hosts require re-import from Conclave because encrypted credentials are host-bound. The deployment helper is a one-time migration utility, not a persistent 1Password dependency.

## Limits and troubleshooting

Bunny's account key authenticates the core API; Storage requires a separate zone password, fetched in process memory from the authenticated core API. Read-only storage passwords are preferred for reads. Neither password is returned by tools. HTTP destinations are fixed/allowlisted, redirects rejected, responses bounded and provider error bodies suppressed.

Some zone-list endpoints return arrays despite the documented paged shape. The plugin reports local slicing versus provider pagination explicitly; no completeness claim is invented. Requests time out after 30 seconds. GETs have one bounded retry; long Retry-After delays are honored on subsequent calls. Large listings may exceed the response limit and require a narrower request. UTF-8 file reads/uploads are limited to 64 KiB.

Preflight state checking is not a transactional lock. Other actors can change a resource between check and write. Review important DNS changes carefully. After an uncertain write, inspect state before preparing again. Service restarts discard pending previews. Offline cloud calls may show an error in ChatGPT; no business changes are queued and no unsolicited alerts are sent.

## Verification and sources

Run npm test and tests/windows-setup.ps1. The connection check blocks runtime 1Password execution and checks discovery plus harmless authentication. Provider reads were tested on Windows and Ubuntu; production writes are not used as test fixtures.

Official source snapshots and observed compatibility notes: [API sources](docs/SOURCES.md). The bundled icon is Bunny.net's official site favicon, used to identify the integration; it remains Bunny.net's mark.

Verified 2026-10-06: 16 safety tests passed; synthetic Windows setup/rotation tests passed; the installed Windows bundle matched source and discovered all 18 tools; Windows and Ubuntu read-only provider probes passed without runtime 1Password. ChatGPT connected and displayed all 18 tools (17 reads/previews, one execution tool). Production writes and a model-driven conversation call were not performed. The local official icon is installed; ChatGPT icon upload remains blocked by the browser extension file-URL permission.
Final Ubuntu cloud refresh verified: initialized=true, tools=18, discoveryComplete=true, control-plane polling failures=0. Service enabled and active after restart.


## Task-scoped approval and verification

The agent may approve changes within your explicit task after showing the concrete preview and checking preconditions/recovery. It must test and verify the actual result, stop dependent work on failed or uncertain verification, and ask before unclear or additional actions. Host confirmations remain in force. See the [shared standard](../docs/CHANGE_APPROVALS.md). Caller confirmation is an authorization assertion, not an independent human authentication gate.
