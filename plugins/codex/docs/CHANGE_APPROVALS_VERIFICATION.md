# Approval safeguard verification

Verified 2026-10-07. Final user choice: the agent may approve all changes within the explicit user task and must test and verify afterward. The earlier ask-before-every-change draft was superseded before deployment.

## Installed and cloud versions

| Plugin | Installed version | Cloud runtime |
| --- | --- | --- |
| Atera | 0.1.5 | conclave-srv |
| Bunny.net | 0.1.1 | conclave-srv |
| Domains.co.za | 0.1.2 | conclave-srv |
| Pressable | 0.2.2 | conclave-srv |
| Website Router | 0.2.2 | conclave-srv |
| Conclave | 0.1.3 adapter | Existing Windows/WSL tunnel; backend remains 0.1.0 |

## Changes and evidence

- Shared task-scope, preview, preflight, recovery and post-change verification instructions are supplied through skills and MCP initialization. Write tool descriptions reinforce the workflow.
- Provider preview responses declare task-scoped agent approval and required verification. Execute responses mark the outcome not-yet-verified; the caller must perform appropriate read-back/tests.
- Domains previews now clone stored/returned parameters. Bunny nested record previews no longer share mutable data. Pressable and Website Router clone input before asynchronous validation.
- Bunny, Pressable and Website Router recheck expiry after asynchronous preflight validation, before dispatch.
- Conclave metadata guidance preserves backend policy and marks known mutation tools and unreviewed additions as writes. It does not independently approve or execute backend actions.
- 96 tests passed across the six plugins, including both opt-in WSL failure-path tests. New regressions cover preview mutation and expiry during validation. Existing tests cover target checks, read/write routing, schema drift, one-use previews, uncertain writes, SSH pinning and file recovery.
- All five Ubuntu candidates passed metadata and authenticated read-only connection checks using existing systemd-encrypted provider credentials before code replacement. All services are active; health, readiness and control-plane polling passed on ports 18781-18785.
- Conclave adapter initialization, discovery and live health passed, and the existing private tunnel is healthy/ready after restart.
- No provider/customer mutations were executed for live verification. Mutation behavior was tested with controlled fixtures. Host approval settings and existing credentials/tunnel identities were preserved.

## Limits

This is the selected agent-approval mode, not a separate authenticated human gate. Instructions and confirmation fields cannot independently prove task authorization or that the agent ran tests. Read-back and functional verification remain required for each real task; a provider's successful response alone is insufficient. Existing chats may retain cached tool descriptions until their connection refreshes.

Website Router's SSH route currently exposes fixed WP-CLI diagnostics and cache flushing. Broader reviewed media/content WP-CLI commands use the Pressable integration; this safeguard update did not widen SSH command scope.

Final desktop verification: all six installed packages passed MCP initialization/approval-guidance checks and harmless authenticated reads with runtime 1Password access blocked. Website Router's connection_status completed successfully across its registered sites. No live mutation or write-approval dialog was exercised. The tests and probes verify runtime controls and published instructions; they do not guarantee that every future model follows those instructions.
