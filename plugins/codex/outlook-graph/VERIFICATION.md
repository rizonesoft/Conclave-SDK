# Verification, 23 October 2026

Version 0.1.7 adds guarded updates of existing HTML reply drafts and CID-aware
attachment baselines/diagnostics. Windows staging and owning-source builds pass;
all 81 JavaScript tests pass with no skips, including an isolated temporary-profile
DPAPI roundtrip. Sandbox-only encrypted-store failures are resolved by running the
same synthetic tests through supported execution under the owning Windows account.
No mailbox call is part of this test suite.

The existing private local plugin was refreshed using
`codex plugin add outlook-graph@rizonetech --json`, which reports version 0.1.7.
Credential-free SDK initialization/discovery returns the same server version and
14 tools. Package, lockfile, plugin and server versions are checked together by
the built-package test. No installation/cache files are edited directly.

New tests cover exact mailbox/message/thread identity, sent-item rejection,
missing/stale ETags, body-hash/change-key guards, concurrent user edits, preview
expiry/replay/concurrency, body-only PATCH, quote/CID/recipient preservation,
complete bounded attachment metadata, injected markup, readback normalization,
uncertain-write reconciliation, process pacing and longer Retry-After cooldowns.
CID regressions cover raw/omitted/null IDs, URL normalization, authored/quoted/
document roles, CSS and srcset references, missing/duplicate protected images,
same-ID/same-size CID changes, preview tampering and a synthetic inventory
reduction that remains a strict failure despite intact quoted images. Unused or
unknown assets are never silently exempted from inventory preservation.
The pinned parse5 parser was added from the official npm registry with install
scripts disabled. Existing authentication scopes/storage are unchanged.

The documented presence-only status command succeeds under the owning Windows
account and reports an existing encrypted session/configuration without Graph
access or credential disclosure. Presence is not proof of valid Microsoft consent.
Version 0.1.7 corrects the derived-type CID projection after an unqualified
collection selector returned HTTP 400. The regression models that schema failure,
requires the qualified fileAttachment property path, retains mixed attachment
types/pagination and proves HTTP errors cannot trigger an unprojected fallback.
Live compatibility is checked separately under explicit read-only authorization;
its result stays outside source to exclude real correspondence/customer data.
Neither a read-only check nor these tests certifies rendered-image coverage or
an actual update's preservation outcome.

Readback certifies authored content, semantic quoted structure/links/images,
preserved message fields and attachment metadata. It does not certify exact CSS
or original attachment bytes. See [HTML workflow](docs/HTML_DRAFTS.md).

## Historical verification, 13 October 2026

Version 0.1.2 is installed and enabled from the local Rizonetech marketplace on Windows and WSL Ubuntu. Source and runtime helpers are independent of other agents. Installed packages use portable root manifests.

## Tests

- Windows: 43 JavaScript tests passed, including real DPAPI roundtrip and replacement in an isolated temporary profile.
- WSL: 42 JavaScript tests passed; the native-Windows DPAPI test is explicitly skipped. Linux AES-GCM authentication, replacement, locking and package startup run on both platforms. WSL additionally exercises its DPAPI bridge through the installed package.
- Both platforms: 31 Python mail-helper tests, 7 skill-deployment tests, 41 hook tests and 6 rule-deployment tests passed.
- Ubuntu packaging: shell syntax and Python compilation passed. The cloud installer and service were not deployed or exercised on conclave-srv.
- Dependency audit reported zero vulnerabilities. The 256-pixel icon was rendered and visually checked.

Graph tests use synthetic mailbox fixtures. Coverage includes bounded pagination and bodies, redirects and endpoint restrictions, throttling, missing metadata, protected folders, preview expiry/replay/concurrency, changed source state, category preservation, draft recipients/body, partial writes and permanent identity after moves. Authentication tests cover failed or wrong-mailbox login preserving the old session, refreshed-cache persistence and provider-error redaction. A regression test covers WSL kernel detection when the MCP environment omits WSL_DISTRO_NAME.

## Installed packages and host checks

Installed MCP probes on both platforms discover exactly 11 tools and call only `connection_status`. Both return `Not signed in. Run outlook-graph setup login.` Windows app-server discovery separately reports those tools, no tools error and the correct plugin identity. This proves discovery and credential-store routing, not Microsoft mailbox access.

Both global skills were redeployed with per-file hash verification. Fresh `codex exec --skip-git-repo-check` sessions on Windows and WSL name `process-ticktick-task`, `file-to-ticktick` and `outlook-graph-mail`. Their event streams contain only agent messages, with no tool calls. A separate WSL model-driven session calls only connection_status and confirms the missing login.

Windows model-driven CLI checks, with and without the shared daemon, reported that the tool was not exposed to the model and made no call. The enabled plugin, successful app-server tool discovery and installed protocol probe do not resolve that host exposure discrepancy. Recheck a refreshed desktop session after login; Windows model-driven readiness remains unverified. Do not claim a daemon restart is a proven fix.

Both global AGENTS.md copies remain byte-identical to `rules/codex.md`, SHA256 `ffc1b434d196f0602f26257f37573e12534149484caafb12f6bc1a1d61dd2dd22`. No rules redeployment was needed. Existing global hook configuration remains in place and its tests pass.

## Authentication and remaining verification

The user confirmed no dedicated Microsoft app registration exists and requested a new setup. A Conclave placeholder named `Codex Outlook Graph` holds fields for non-secret tenant ID, client ID and mailbox. The README documents single-tenant public-client registration, delegated permissions, interactive login, import, update and recovery. No client secret is required. These checks created no Microsoft registration, permission grant or authenticated session.

After user login, run the harmless connection check, re-read a known open TickTick task, extract its Outlook references and confirm a linked message's internetMessageId. That live identity check remains pending. Official TickTick is unchanged; earlier authenticated read evidence is in `../skills/VERIFICATION.md`.

No live task or email was created, drafted, moved, categorised, completed, sent or deleted during verification. Cloud activation remains pending its own login and dedicated private tunnel. Local diagnostic event logs remain under ignored `.local/`.
