## Round 1: none

- Writer: codex
- Run: 2026-11-14T19:30:32Z
- Effort: medium
- Lenses: adversarial, integration, source-defect, consistency, quality, optimization
- Skipped: carbon (timed out)
- Lines: 1
- Digest: 0555d87060386853

No reviewer returned a review. This round is not an approval.

## Round 2: none

- Writer: codex
- Run: 2026-11-14T19:36:19Z
- Effort: medium
- Lenses: adversarial, integration, source-defect, consistency, quality, optimization
- Skipped: carbon (incomplete: no final round verdict line)
- Lines: 38
- Digest: e9d00dd8ee0c091f

### Findings

#### `integration`

- **[P1] Git-tracked bundle vs. input mtime check triggers false drift after `git clone`, `git checkout`, or `git pull`** in [session_drift_check.py](file:///D:/Conclave-SDK/global/codex/hooks/session_drift_check.py#L73-L77): `plugin_drift` flags `SDK bundles older than inputs` whenever `any(p.stat().st_mtime_ns < newest for p in bundles)`. Because `dist/*.mjs`, `scripts/*`, and `src/*` are all tracked in Git and `dist/` sorts lexically before `scripts/` and `src/` in `.git/index`, Git checkouts and pulls write `dist/*.mjs` before `scripts/*` and `src/*`, stamping inputs with a newer `st_mtime_ns` than freshly checked-out bundles across all nine bundled plugins (and also counting non-bundle files such as tests under `scripts/` or `src/`).
- **[P1] Deployed hook `SDK` path assumes repo directory depth unless `{HOOKS}` points directly into the SDK** in [session_drift_check.py](file:///D:/Conclave-SDK/global/codex/hooks/session_drift_check.py#L19-L41) and [test_session_drift_check.py](file:///D:/Conclave-SDK/global/codex/hooks/test_session_drift_check.py#L92-L93): `SDK = Path(__file__).resolve().parents[3]` only resolves to the repository root when executed from `<SDK>/global/codex/hooks/session_drift_check.py` (or a symlink to it). If [deploy.py](file:///D:/Conclave-SDK/global/deploy.py) copies hook files into `<home>/.codex/hooks/` (matching `Deployer`'s `created`/`updated` copy model), `parents[3]` resolves to `<home>.parent` (`C:\Users` or `/home`), `sdk / 'global/deploy.py'` raises `FileNotFoundError`, and every new session emits `check could not read the deployment; run the checks manually`. [test_session_drift_check.py](file:///D:/Conclave-SDK/global/codex/hooks/test_session_drift_check.py#L92-L93) imports from the repo tree and never executes the deployed hook command written into `self.home / '.codex/hooks.json'`.
- **[P2] Source-launcher plugins skip cached code drift checks** in [session_drift_check.py](file:///D:/Conclave-SDK/global/codex/hooks/session_drift_check.py#L68-L93): for dependency-free plugins with no `dist/*.mjs` (such as `conclave`, noted at line 69), `bundles` is `[]`, so `actual == expected == {}` trivially passes and edits to SDK `src/` or `scripts/` never flag stale cached launcher files under `cache / name / <version>`.

#### `adversarial`

- **[P1] Early MCP child exit hangs the approval probe for 180 seconds or crashes with unhandled `EPIPE`** in [check-approval-policy.mjs](file:///D:/Conclave-SDK/plugins/codex/scripts/check-approval-policy.mjs#L8-L11): `pending` promises are never rejected on `child` `'exit'`/`'error'` or `lines` `'close'`, `child.stdin` has no `'error'` listener, and the ref'd 180-second `setTimeout` keeps the Node event loop alive after `child.stdout` closes (exceeding the 30-second suite timeout in [forge.py](file:///D:/Conclave-SDK/forge.py#L1964-L1965) and bypassing the `catch` block via `process.exit(1)`). In addition, [check-approval-policy.mjs](file:///D:/Conclave-SDK/plugins/codex/scripts/check-approval-policy.mjs#L2-L7) spawns a detached child process group on POSIX (`detached: process.platform !== 'win32'`) without `SIGINT`/`SIGTERM` handlers, so killing the probe with a termination signal leaks the child's separate process group.
- **[P2] Vacuous `Array.prototype.every` truth marks empty `sites: []` as `connected: true` under `--live`** in [check-approval-policy.mjs](file:///D:/Conclave-SDK/plugins/codex/scripts/check-approval-policy.mjs#L20): `d.sites?.every(s => s.connected)` evaluates to `true` when `d.sites` is `[]`, passing `--live` readiness when zero sites are returned.

#### `source-defect`

- **[P2] Approval-policy probe ignores non-read-only tools outside a hardcoded three-name list and passes when zero write tools exist** in [check-approval-policy.mjs](file:///D:/Conclave-SDK/plugins/codex/scripts/check-approval-policy.mjs#L17-L21): filtering `tools` down to only `execute_change`, `propose_memory_write`, and `create_approval_request` allows any other mutating tool (`annotations?.readOnlyHint !== true`) or a renamed write gateway (`writes.length === 0`, as in [check-approval-policy.test.mjs](file:///D:/Conclave-SDK/plugins/codex/scripts/check-approval-policy.test.mjs#L21)) to report `taskScopedApprovalAndVerification: true` without verifying write-approval metadata.

#### `consistency`

- **[P2] Missing temp-directory fallback in `first_prompt()` breaks environments without `R:\scratch` or `/mnt/r/scratch`** in [session_drift_check.py](file:///D:/Conclave-SDK/global/codex/hooks/session_drift_check.py#L23-L28) and [session_drift_check.py](file:///D:/Conclave-SDK/global/codex/hooks/session_drift_check.py#L119-L132): unlike [test_session_drift_check.py](file:///D:/Conclave-SDK/global/codex/hooks/test_session_drift_check.py#L18-L19) and [check-approval-policy.test.mjs](file:///D:/Conclave-SDK/plugins/codex/scripts/check-approval-policy.test.mjs#L10-L11), `first_prompt(session, folder=None)` does not fall back to `tempfile.gettempdir()` when `R:\scratch` or `/mnt/r/scratch` is absent. On hosts or CI runners without `R:` or a writable `/mnt/r`, `folder.mkdir(parents=True, exist_ok=True)` raises `OSError` before writing the marker, causing `main()` to inject `Codex setup drift: session drift check unavailable.` on every prompt of every session.

#### `quality`

- **[P2] Single-shot `/proc/<pid>/stat` check races asynchronous `SIGKILL` delivery on Linux** in [check-approval-policy.test.mjs](file:///D:/Conclave-SDK/plugins/codex/scripts/check-approval-policy.test.mjs#L34-L38): `process.kill(-child.pid, 'SIGKILL')` in [check-approval-policy.mjs](file:///D:/Conclave-SDK/plugins/codex/scripts/check-approval-policy.mjs#L6) returns before the kernel finishes transitioning target threads into `Z` or reaped state, so reading `/proc/<descendant>/stat` once immediately on parent exit can still observe `S`/`R` under CI load (and `.split(') ')[1]` misparses process names containing `) ` compared with `lastIndexOf(') ')`).
- **[P3] Inner `break` on manifest drift and dense single-line minification** in [session_drift_check.py](file:///D:/Conclave-SDK/global/codex/hooks/session_drift_check.py#L89-L93) and [check-approval-policy.mjs](file:///D:/Conclave-SDK/plugins/codex/scripts/check-approval-policy.mjs#L1-L22): line 93 breaks out of `for manifest in ('mcp.json', '.mcp.json'):` rather than `for version in versions:` (emitting duplicate problem entries from `plugin_drift()` when multiple cached version directories exist), [test_session_drift_check.py](file:///D:/Conclave-SDK/global/codex/hooks/test_session_drift_check.py#L68-L89) never covers `first_prompt()` with `folder=None`, and [check-approval-policy.mjs](file:///D:/Conclave-SDK/plugins/codex/scripts/check-approval-policy.mjs#L20) packs multi-step protocol logic onto a 427-character minified line.

#### `optimization`

- **[P3] Unconditional SDK bundle reads and SHA-256 hashing when a plugin has no cached versions** in [session_drift_check.py](file:///D:/Conclave-SDK/global/codex/hooks/session_drift_check.py#L78-L85): `expected = {p.name: hashlib.sha256(p.read_bytes()).digest() for p in bundles}` reads and hashes every plugin's `dist/*.mjs` bundles before checking whether `versions` is non-empty, performing unnecessary multi-megabyte reads across WSL's `/mnt/d` 9P mount for the seven or eight disabled plugins that have no WSL cache directories.

LENS adversarial: findings
LENS integration: findings
LENS source-defect: findings
LENS consistency: findings
LENS quality: findings
LENS optimization: findings
HIGHEST: P1
OVERALL: findings

- Reconciliation of malformed Round 2: fixed early MCP exit, descendant cleanup, empty live inventory, unknown mutating-tool validation, source-launcher cache comparison and unnecessary uncached bundle hashing. Added focused regressions and bounded descendant polling.
- Verified non-findings: global/deploy.py renders hooks directly against SDK/global/codex/hooks, so SDK path derivation is correct; scratch-only markers and strict source mtimes are explicit user requirements. Duplicate warning text is deduplicated before output. Tests now limit freshness inputs to src as requested. Checkout timestamps can require a rebuild, documented in plugins/codex/README.md.

## Round 3: none

- Writer: codex
- Run: 2026-11-14T20:27:48Z
- Lenses: adversarial, integration, source-defect, consistency, quality, optimization
- Skipped: carbon (timed out)
- Lines: 1
- Digest: 0555d87060386853

No reviewer returned a review. This round is not an approval.

- Session permissions proof, 2026-11-14: native Windows and WSL agy 1.5.9 with Orchestrator read HEAD 3bb79f029904a181be8c8c16ef603762c49e28cb through a command, then edit_file was denied and each scratch sentinel remained unchanged. Settings explicitly use auto mode and proceed-in-sandbox, retaining write/edit/MCP denies. No user preference was changed.
- Cadence correction: initial plan/round reviews retain medium effort and completion/reconciliation use low for Astra. Orchestrator receives and records no fixed effort. Dispatch and receipt replay share effective_effort against the committed route. The old loader rejects this mixed pin; the new loader, template dispatch and end-to-end receipt regressions pass.
- Prior broad review attempts timed out; the bounded retry under the old permission settings was cancelled when superseded by the corrected settings. None was counted as approval.

## Round 4: carbon (`gemini-pro-orchestrator` via `agy`)

- Writer: codex
- Run: 2026-11-14T20:44:17Z
- Lenses: adversarial, integration, source-defect, consistency, quality, optimization
- Lines: 17
- Digest: 5bc052d4309f8819

### Findings

- **[P2] (`adversarial`) Relative or empty marketplace `source` resolves against `os.getcwd()`, and source/manifest cache checks are one-way** in [session_drift_check.py](file:///D:/Conclave-SDK/global/codex/hooks/session_drift_check.py#L65-L119): `source = config.get('marketplaces', {}).get('rizonetech', {}).get('source', '')` defaults to `''` and passes straight into `normalized(source)` (`os.path.realpath(...)`) without requiring a non-empty absolute path (`Path(source.removeprefix('\\\\?\\')).is_absolute()`), so `os.path.realpath('')` matches `root` whenever Codex starts in `plugins/codex` and a broken relative `source = "plugins/codex"` in global `.codex/config.toml` passes silently whenever Codex starts in the SDK root; in addition, lines 101-119 only check SDK `src`/`scripts` files and `mcp.json`/`.mcp.json` one-way (unlike `actual != expected` for `bundles`), missing stale files left behind in cached plugin directories after an SDK deletion.
- **[P2] (`adversarial`) Non-object JSON stdout lines (`null`) and missing CLI path bypass `try/finally` and leak the spawned server tree** in [check-approval-policy.mjs](file:///D:/Conclave-SDK/plugins/codex/scripts/check-approval-policy.mjs#L172-L266): in `lines.on('line', ...)`, `JSON.parse("null")` returns `null` and `pending.get(message.id)` throws an uncaught `TypeError` inside the EventEmitter callback outside the top-level `try / catch / finally`, printing raw stack output and skipping `stopTree()` so the spawned MCP server and its descendants survive; `spawn(process.execPath, [process.argv[2]])` at line 172 is also outside `try` when `process.argv[2]` is omitted. Guard `if (!message || typeof message !== 'object') return;` before reading `message.id`, validate `process.argv[2]` inside `try`, and add `process.once('exit', stopTree)` as a last-resort teardown hook.
- **[P3] (`consistency`) Locale-dependent `read_text()` on JSON manifests and inner-loop `break` mismatch** in [session_drift_check.py](file:///D:/Conclave-SDK/global/codex/hooks/session_drift_check.py#L71-L119): line 71 specifies `encoding='utf-8-sig'` for `config.toml`, whereas lines 77 and 85 call `.read_text()` without `encoding='utf-8'` on `marketplace.json` and `package.json` (defaulting to the Windows ANSI codepage when UTF-8 mode is unset), and `break` on line 119 exits only `for manifest in ('mcp.json', '.mcp.json'):` rather than `for version in versions:` (unlike lines 109 and 114), returning duplicate entries from `check()` when multiple cached version directories exist.
- **[P3] (`integration`) Unguarded `None` from `committed_pin` in `schedule_ok`** in [todo_graph.py](file:///D:/Conclave-SDK/kits/todo/templates/scripts/lib/todo_graph.py#L712-L718): `committed_pin` can return `None` when `.conclave/reviewers.toml` is absent at the target SHA (as guarded by `if own is None` at line 742), so `check()` should guard `if chosen:` before calling `dispatch.review_pin.route_for(chosen, ...)` and indexing `chosen["reviewers"]` so tampered or unpinned SHAs do not raise an unhandled `AttributeError`/`TypeError`.
- **[P3] (`source-defect`) Unchecked `nextCursor` pagination on MCP `tools/list`** in [check-approval-policy.mjs](file:///D:/Conclave-SDK/plugins/codex/scripts/check-approval-policy.mjs#L231-L245): under MCP `2024-11-05`, `tools/list` responses may return `nextCursor`; either follow `nextCursor` or fail closed when `nextCursor` is present so a paginated server cannot pass `taskScopedApprovalAndVerification: true` with unaudited second-page tools.
- **[P3] (`quality`) Misnamed empty-inventory test and untested `prepare_change` gateway requirement** in [check-approval-policy.test.mjs](file:///D:/Conclave-SDK/plugins/codex/scripts/check-approval-policy.test.mjs#L356-L362): `test('no write tools cannot pass approval verification', ...)` passes `server([])`, which fails the empty-inventory check (`!tools.length` at [check-approval-policy.mjs](file:///D:/Conclave-SDK/plugins/codex/scripts/check-approval-policy.mjs#L232)) even though a read-only server with no write tools passes on line 361, while the `prepare_change`-without-`execute_change` rejection at [check-approval-policy.mjs](file:///D:/Conclave-SDK/plugins/codex/scripts/check-approval-policy.mjs#L240) has no test case.

LENS adversarial: findings
LENS integration: findings
LENS source-defect: findings
LENS consistency: findings
LENS quality: findings
LENS optimization: clean
HIGHEST: P2
OVERALL: needs-attention

## Round 5: carbon (`gemini-pro-orchestrator` via `agy`)

- Writer: codex
- Run: 2026-11-14T20:52:34Z
- Lenses: adversarial, integration, source-defect, consistency, quality, optimization
- Lines: 14
- Digest: e21e2d7ecd3ae6a8

All Round 4 findings are resolved at their owning layers across the supplied files and kit diff, and no new defects were found.

- `global/codex/hooks/session_drift_check.py`: `plugin_drift` validates `marketplaces.rizonetech.source` as a non-empty absolute path before normalization, decodes JSON as UTF-8, detects added, removed, and modified files in both source and `dist/*.mjs` caches via full hash-map equality, and avoids duplicate warnings across cached versions while keeping bounded daemon-thread execution and scratch-only session markers intact.
- `plugins/codex/scripts/check-approval-policy.mjs`: rejects missing or flag-first server arguments before spawning, guards non-object JSON values on stdout, fails closed on paginated or empty `tools/list` inventories and on `prepare_change` without `execute_change`, and cleans up the child process tree through `finally`, signal handlers, timeout, and `process.once('exit', stopTree)` without leaking provider data.
- `kits/reviewer` and `kits/todo` diff: `agy_review_settings` scopes transient `read_file(...)` permission strictly to the resolved external prompt path alongside `agentMode: "auto"`, `toolPermission: "proceed-in-sandbox"`, and existing write/edit/MCP denies, while `review_pin.effective_effort` keeps dispatch, prompt headers, and `todo_graph.schedule_ok` receipt replay (including per-candidate plan attempts) consistent for Orchestrator and direct models.

LENS adversarial: clean
LENS integration: clean
LENS source-defect: clean
LENS consistency: clean
LENS quality: clean
LENS optimization: clean
HIGHEST: none
OVERALL: approve

## Owner direction: two writers, Codex reviewer only

The owner cancelled Antigravity reviewer work after round 5 returned a nonblocking review. Restore the Claude and Antigravity writer routes with Astra as their only reviewer, medium initial reviews and low follow-ups. Revert the uncommitted Orchestrator dispatch and receipt-replay experiments. The SDK launcher and Desktop shortcuts expose only Claude and Carbon writers. No unattended campaign was launched. The plugin relocation and its verified fixes are retained.

Verification of the restored defaults: 39 template routing, launcher and CLI tests passed; three targeted kit install checks and the Markdown check passed. Windows and WSL pin validation passed. The two live Desktop links were read back and point to this checkout with Claude and agy runners. The latest WSL app-server trust recheck timed out at initialize; the preceding deploy and hash-approval checks passed, and the drift check remained clean. No campaign or additional model review was started.
