# Plugin design direction

Accepted 2026-10-06. This is the default architecture for Rizonetech custom plugins; changes to hosting, access, credential handling or write authority require an explicit user decision.

## Ownership and packaging

- The authoritative source is <SDK>\plugins\codex. Each integration lives directly beneath the root. Do not restore a codex-plugins nesting layer or use Kami as the plugin source.
- Group local marketplace listings under Rizonetech (catalog ID rizonetech). This is our private catalog, not a promise of a separate public store category.
- Keep each provider's MCP server, skills, manifests, assets, tests and setup instructions together. Share deployment conventions without merging unrelated provider permissions.
- Preserve plugin identities and existing connections when changing hosts.

## Hosting and connectivity

- Run cloud MCP services on the always-on Ubuntu server conclave-srv, supervised by systemd with automatic startup and restart. Windows must not be required for ChatGPT cloud use.
- Use Tailscale SSH for private administration. Use the existing outbound OpenAI secure tunnels for ChatGPT access; do not expose an unauthenticated public MCP endpoint or assume ChatGPT joins the private tailnet.
- Keep a separate service and tunnel for each integration. GitHub stores source and release history; it is not the running MCP host.
- Keep local Windows Codex operation supported with DPAPI credentials. Windows cloud tunnels are disabled standby; never operate two hosts against the same tunnel concurrently.

## Credentials

- All AI/plugin 1Password entries and recovery credentials belong in Conclave.
- 1Password is used during explicit setup, import or recovery, not on every tool call.
- On Ubuntu use root-only systemd encrypted credentials and private service credential directories. On Windows use DPAPI CurrentUser storage outside Git.
- Every plugin must support secure initial setup, credential replacement, non-secret status, a harmless connection check and new-host recovery. Re-import on another host; do not treat host-bound ciphertext as portable.
- Keep keys, passwords and TOTP seeds out of source, command arguments, logs and chat. Generate changing TOTP codes from the encrypted seed where the provider requires them.

## Tool behavior and availability

- Start with the requested workflows and least necessary access. Atera remains read-only for devices, monitoring and alerts.
- Provider changes require a clear preview and task-scoped approval of the intended target and effect; the agent may approve within the explicit user task and must test and verify afterward. Domains uses expiring, single-use previews consumed before execution. Never automatically retry uncertain provider writes.
- Bound requests, pagination and read retries. Redact secrets and provider error bodies; accurately report incomplete coverage.
- Fail quietly at the service level when unavailable. Do not send unsolicited notifications or queue business changes for later execution. ChatGPT may still display a tool connection error; complete UI silence is not guaranteed.
- Preserve existing ChatGPT approval policies. Public publication, broader sharing and paid hosting need explicit authorization.

## Presentation and delivery

- Use the proper provider icon where available, with appropriate small-size legibility and contrast. Include Rizonetech attribution without implying provider endorsement.
- Finish display names, concise and full descriptions, accurate tool descriptions, useful example prompts, workflow skills, setup and troubleshooting. Descriptions must reflect the actual host and credential model.
- Build and test before delivery; verify MCP initialization, complete tool discovery and a harmless live provider check. Check the intended host as well as the local implementation.
- Distinguish verified behavior from remaining work. Cloud icon upload, cloud skill packaging, a model-driven ChatGPT account call and full outage/replay testing remain recorded follow-ups from the migration; accepting this direction does not mark them completed.

Operational details: [Ubuntu runtime](../cloud-access/linux/README.md), [cloud connections](../cloud-access/README.md), and [Windows credentials](WINDOWS_CREDENTIALS.md).

## Branding permission gate

The [provider permission register](BRAND_PERMISSIONS.md) is authoritative for pending logo approval. Obtain written permission for Atera, Bunny.net and Domains.co.za, satisfy their conditions, then upload all three approved icons together. Availability of an official asset or browser file permission is not branding authorization.

## Existing local backend adapters

The Conclave plugin connects Codex to the user-requested existing WSL checkout at `~/conclave` through local stdio. It preserves Conclave's canonical MCP launcher and backend credential ownership; the adapter stores only non-secret location settings and owns no API credential to duplicate into DPAPI. Normal startup never calls 1Password. Its setup, credential-update delegation, connection check and new-computer recovery are documented in [Conclave setup](../conclave/README.md). The user also requested and approved a dedicated private Conclave tunnel to the existing WSL backend for derick@rizonetech.com. Its separate Windows runner uses the existing DPAPI tunnel key and does not enable the retired provider standby task. This PC must remain on and signed in; the cloud hosting and encrypted credential defaults above remain in force for independent API integrations. See [Conclave cloud access](../conclave/CLOUD.md).


## Mandatory task-scoped approval and verification

All current and future plugins must follow [Change approvals](CHANGE_APPROVALS.md). The agent may approve changes within the explicit user task after showing the concrete preview and performing preflight checks. It must test and verify the actual outcome. Ask for unclear or additional scope; stop dependent actions on failed/inconclusive verification. Preserve runtime guards and host confirmations.
