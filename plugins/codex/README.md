# Rizonetech Codex plugins

The source and local marketplace live in `D:\Conclave-SDK\plugins\codex` on Windows and `/mnt/d/Conclave-SDK/plugins/codex` in WSL. The seven plugins retain their existing identities, credentials and tunnels. The SDK's [design direction](DESIGN.md) remains authoritative.

The catalog is `.agents/plugins/marketplace.json`. Each plugin owns its manifests, source, tests, skills and assets. Nine bundled `dist/*.mjs` files are tracked so installation needs no build step. Conclave runs its dependency-free `src/launch.mjs` directly. Development dependencies, local inventories, tunnel executables and migration backups are not tracked.

## Build and verify

For each plugin with a lockfile, run `npm ci --no-audit --no-fund`, `npm test` and `npm run build` in its directory, through `bosun run --` for full suites and builds where Bosun is installed. Conclave needs only `npm test`. Outlook builds both `server.mjs` and `setup.mjs`; Pressable and Website Router each build `server.mjs` and `probe.mjs`. Rebuild after changing source or build scripts, then refresh the installed cache.

Global rules, hooks and skills belong to `global/codex`, deployed with `python global/deploy.py --agent codex` from the SDK root on Windows and `python3 global/deploy.py --agent codex` in WSL. Deployment hash-approves its hook definitions through Codex. `--check` verifies the deployed files without changing them.

The `UserPromptSubmit` drift hook runs once per session and platform. Its hashed session markers live in `R:\scratch\codex-drift` or `/mnt/r/scratch/codex-drift`. Within three seconds it checks global deployment, marketplace source, enabled caches, bundle hashes, MCP manifests and bundle freshness against `src/` inputs, plus source files for unbundled plugins. It is silent when clean and warns without blocking when drift or an incomplete check is found. It never prints configuration values or provider errors. Freshness uses the requested strict filesystem timestamp comparison: a checkout that writes source after bundles requires a rebuild even if their committed contents are unchanged.

## Windows cloud access

The Conclave task uses `conclave/scripts/run-hidden.py` and `conclave/scripts/Manage-Cloud.ps1` under this root. Its approved local tunnel runtime is in `.local/tunnel-client/v0.0.15`, outside Git. Provision that runtime before installing the task on another machine. Credentials remain in their existing DPAPI stores. Inspect status with:

```powershell
pwsh -NoProfile -File D:\Conclave-SDK\plugins\codex\conclave\scripts\Manage-Cloud.ps1 -Action Status
```

The `Rizonetech Plugin Cloud Access` task remains disabled standby. Provider services run on Ubuntu; do not enable duplicate tunnels. Restarting the active Conclave tunnel can interrupt cloud sessions and needs the operator's confirmation.

## Reconciliation and rollback

The 2026-11-14 audit compared SHA-256, timestamps and sizes for every file except `node_modules`, Git metadata and Python bytecode. It found 207 identical files, 30 byte differences, 108 old-only files and one SDK-only `DESIGN.md`, which was preserved. The listed code and test differences were line endings; substantive shared differences were documentation. Missing bundles, upstream specs and operational documentation were imported. Old config backups, local inventories, release archives and duplicate global deployment machinery stay outside the source tree.

Legacy article/layer hook code and skill helper code match `global/codex`. Its task skill differs only in the already-updated SDK source reference; global rules additionally contain newer main-branch, Bosun and child-process safeguards. Legacy rule/skill deployers and their tests are superseded by `global/deploy.py` and `global/tests/test_deploy.py`; the global READMEs describe that deployment. They must not be reinstalled from the rollback tree.

`R:\Bin\codex` is untouched rollback material. To reverse this relocation, restore only the rizonetech marketplace source and corresponding project trust table, copy its plugin distributions back to their matching version caches, and point the two existing task actions back there. Keep the provider standby disabled and obtain confirmation before restarting an active tunnel. Do not restore whole configuration files over unrelated newer settings. Audit and local verification logs for this cutover are in `R:\scratch\codex-cutover`.

## Local verification, 2026-11-14

All seven plugin suites passed on Windows and WSL, all nine bundles rebuilt, and 25 global deploy tests passed on each platform. All 56 Codex hook tests, including 15 new drift tests, passed on both. Platform-specific and opt-in tests retain their existing skips. All seven Windows caches and WSL's enabled Outlook cache initialized and listed tools. Six packages also initialized directly under Linux; Conclave remains a Windows-to-WSL adapter, not a native Linux launcher.

Both native Codex installations listed seven enabled, trusted global hooks. Live drift checks were clean in 0.059 seconds on Windows and 0.699 seconds in WSL; repeated session prompts skipped them. The explicitly approved Conclave restart returned running, healthy and ready with its launcher, manager and tunnel executable under the SDK. The provider task stayed disabled. Provider business operations and the Ubuntu cloud services were not changed.

The imported approval-policy probe now stops its entire child process tree on teardown and timeout. Its eleven regression tests pass on Windows and WSL. Live metadata checks pass for the six plugins covered by this shared approval policy; Outlook uses its own mail policy. Read-only inventories report no write-verification claim, and local previews are distinguished from provider execution. Its real descendant regression failed against the old Linux probe and passed with the SDK probe on Windows and WSL. Run it with `node --test scripts/check-approval-policy.test.mjs` from this directory.
