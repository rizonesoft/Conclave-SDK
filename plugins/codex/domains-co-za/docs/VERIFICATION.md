# Verification — 2026-10-05

- Fourteen automated tests passed: official MCP stdio initialization and 23-tool discovery; strict write schemas; exact-domain preview confirmation; preview expiry and single use; no write retries; provider return codes; URL/form encoding; response secret redaction; Windows-only credential loading; no 1Password fallback; RFC 6238 reference TOTP vectors.
- Isolated Windows setup checks passed: DPAPI round-trip, protected ACL, credential rotation, rejected invalid replacement, preservation of unrelated settings, and Node runtime decryption.
- Installed domains-co-za@rizonetech 0.1.0 through the supported Codex CLI. Tested the installed bundle through the official MCP client.
- Live authentication with password plus locally generated TOTP succeeded. Account-funds read and domain inventory read succeeded. Provider reported 96 domains and returned 96; only coverage counts were printed during verification.
- Installed verification passed with 1Password subprocess execution blocked. Ordinary operation requires no 1Password approval.
- Authenticator recovery copy is stored in the existing Domains.co.za Reseller API item in Conclave. Runtime credentials are protected by Windows DPAPI. No secret is stored in this repository.
- Icon rendered at 512x512 and visually inspected; official wordmark provenance recorded in assets/SOURCES.md.
- No live domain writes, registrations, renewals, DNS changes, or account charges were executed. Write behavior is verified with mocks; provider-specific write permissions remain unverified until a user-authorized change.

Commands: npm run build; npm test; pwsh -NoProfile -File tests/windows-setup.ps1; node scripts/verify-installed.mjs <installed-plugin-directory>.

## Icon correction, version 0.1.1

Replaced the composite globe icon with the official homepage favicon. Extracted the original 128 x 128 PNG frame losslessly, visually checked it, rebuilt the versioned bundle and refreshed the installed plugin.
