# Conclave VS Code extension: design spec

Date: 2026-10-20. Written by `D00 T01 §4` from the plan (`docs/plans/2026-10-16-vscode-extension.md`), the approved mockup and `design/SPEC.md`, and `design/decisions.md` (approval 2026-10-17, the reviewer route change 2026-10-20). Each decision below records the options weighed, the choice, and the cost of reversing it. Where the owner's answers left a choice open, the choice here is a default, said so.

## 1. Validation runs in the workspace dispatcher

Options: port `load_pin` to TypeScript; call the dispatcher on the saved file only; call it on every candidate (plan R7).

Choice: every candidate is checked by the workspace's own `scripts/review-dispatch.py --check-pin --json --pin <candidate>`, run with the resolved Python (section 5) from the workspace folder; the extension holds no copy of any rule. The candidate is the editor's current text, written to `<os.tmpdir()>/conclave/pin-<process id>-<counter>.toml`: the folder is created with mode `0700`, the file with `0600` and the `wx` flag (never reusing a name), and it is deleted in a `finally` as soon as the dispatcher exits, times out (30 seconds) or cannot start. At activation, files in that folder older than one day are removed, which covers a crash between write and delete. In the Remote WSL extension host `os.tmpdir()` is the Linux side's, which is also where the dispatcher runs. Checks are debounced (300 ms after the last edit) and a newer check cancels an older one, so a slow dispatcher never paints a stale result. The JSON shape is the contract `D01 T01 §2` freezes; output that is not one JSON object with an `ok` key means the dispatcher is too old (plan R18).

Reversal cost: high. A TypeScript port would duplicate every rule, including the 2026-10-20 family rule, and drift from the dispatcher the reviews actually run.

## 2. Comment-preserving edits with a narrow hand-written editor

Options: a TOML library that parses and re-serialises; a library that patches the text in place; a narrow hand-written editor over the text (`design/decisions.md` answer 5 prefers it unless a maintained library round-trips the shipped pin byte for byte).

The spike answer 5 asked for, run on 2026-10-20 with Node 24.14.1 over the shipped pin, a copy with inline and trailing comments, and the inline-table layout `load_pin` also accepts, then every edit through the two libraries that patch in place (`design/spikes/toml_libraries.mjs`, its output in `design/spikes/toml_libraries.out.txt`):

| Library | Round trip | One-line edits | Other edits |
| --- | --- | --- | --- |
| `smol-toml` 1.9.1 | comments lost | comments lost | not tried |
| `@iarna/toml` 2.2.5 | comments lost | comments lost | not tried |
| `@ltd/j-toml` 1.38.0 | comments lost | comments lost | not tried |
| `toml-patch` 0.2.3 (last release 2022) | exact | exact | fails on inline tables |
| `@decimalturn/toml-patch` 3.3.1 | exact | exact | add and delete damage |
| `toml-eslint-parser` 1.0.3 | parser only | no writer | no writer |

`@decimalturn/toml-patch`, the maintained fork, comes closest: setting a field, renaming a reviewer and setting or removing a route change only the lines they should. But adding a reviewer writes `reviewers.mini = {cli = "codex", ...}` as a dotted inline key between astra's comment and astra's table, deleting `sonnet` also deletes the `[routes]` comment block, and renaming a reviewer in an inline table fails. So no library meets R12 for every edit.

Choice: a narrow hand-written editor in `extensions/vscode/src/core/pinText.ts` (`D02 T01 §4`). It edits a pin written in one layout, the one the kit ships: blank lines; comment lines; `schema_version = <integer>`; `[reviewers.<name>]` and `[routes]` headers; inside a reviewer table one `key = "value"` (or `'value'`) per line with no escapes; inside `[routes]` one `writer = ["a", "b"]` array per line; any line may end in a comment. `load_pin` accepts other layouts too (inline tables, quoted keys, dotted keys, arrays over several lines, escapes), and the editor never rewrites one: a valid pin in another layout opens the read-only `This pin uses a layout the editor does not edit` state (`design/decisions.md`, 2026-10-20), with `Open file` and `Retry`, and reviews still run. Every edit replaces the smallest span it touches and keeps everything else (comments, blank lines, key order, quote style, line endings) byte for byte. A deleted reviewer takes the comment block directly above its header, and the lines of its table, with it; any other comment stays. Removing a key or route line keeps the line's trailing comment as a comment line in its place, and an inserted line after a last line with no final newline first gives that line its ending.

Each edit on the shipped pin (`kits/reviewer/templates/.conclave/reviewers.toml`), as a unified diff of the whole file, so the lines shown are the only ones that change. `remove-field` and `add-field` start from `add-reviewer`'s result, and `add-route` from `remove-route`'s. `design/spikes/pin_edits.py` is the reference: it makes every edit, checks the file before and after with `load_pin`, and checks that a CRLF copy gives the same edit with CRLF kept; `D02 T01 §4`'s golden tests reproduce these outputs in TypeScript.

`set-field`: astra's effort from medium to high.

```diff
@@ -19,3 +19,3 @@
 model = "gpt-6-astra"
-effort = "medium"
+effort = "high"
```

`add-reviewer`: add mini (codex, gpt-6-mini, low).

```diff
@@ -33,2 +33,7 @@
 
+[reviewers.mini]
+cli = "codex"
+model = "gpt-6-mini"
+effort = "low"
+
 # Each writer is reviewed by the other two families: Astra first wherever it
```

`remove-field`: mini moved to Antigravity: cli, model, and its effort line removed.

```diff
@@ -34,5 +34,4 @@
 [reviewers.mini]
-cli = "codex"
-model = "gpt-6-mini"
-effort = "low"
+cli = "agy"
+model = "gemini-4-argon-low"
```

`add-field`: the reverse: mini back to Codex, its effort line added.

```diff
@@ -34,4 +34,5 @@
 [reviewers.mini]
-cli = "agy"
-model = "gemini-4-argon-low"
+cli = "codex"
+model = "gpt-6-mini"
+effort = "low"
```

`rename-reviewer`: astra renamed gpt6.

```diff
@@ -16,3 +16,3 @@
 # GPT-6 Astra through the Codex CLI, read-only sandbox.
-[reviewers.astra]
+[reviewers.gpt6]
 cli = "codex"
@@ -36,4 +36,4 @@
 [routes]
-claude = ["astra", "gemini"]
+claude = ["gpt6", "gemini"]
 codex = ["gemini", "sonnet"]
-gemini = ["astra", "sonnet"]
+gemini = ["gpt6", "sonnet"]
```

`delete-reviewer`: sonnet deleted.

```diff
@@ -27,8 +27,2 @@
 
-# Sonnet 5.5 through Claude Code in plan mode.
-[reviewers.sonnet]
-cli = "claude"
-model = "claude-sonnet-5-5"
-effort = "high"
-
 # Each writer is reviewed by the other two families: Astra first wherever it
@@ -37,3 +31,3 @@
 claude = ["astra", "gemini"]
-codex = ["gemini", "sonnet"]
-gemini = ["astra", "sonnet"]
+codex = ["gemini"]
+gemini = ["astra"]
```

`set-route`: codex reviewed by sonnet, then gemini.

```diff
@@ -37,3 +37,3 @@
 claude = ["astra", "gemini"]
-codex = ["gemini", "sonnet"]
+codex = ["sonnet", "gemini"]
 gemini = ["astra", "sonnet"]
```

`remove-route`: gemini's route removed.

```diff
@@ -38,2 +38 @@
 codex = ["gemini", "sonnet"]
-gemini = ["astra", "sonnet"]
```

`add-route`: a route for a writer with none, appended.

```diff
@@ -38 +38,2 @@
 codex = ["gemini", "sonnet"]
+gemini = ["sonnet", "astra"]
```

Reversal cost: medium. The editor is one module behind its edit functions with golden tests; swapping it for a library changes that module only, but only a library that passes every edit above can satisfy R12. Widening the layout it edits is additive: a new line form, its golden tests, and fewer pins in the read-only state.

## 3. Atomic writes with a stale-disk check

Options: `vscode.workspace.fs.writeFile` over the pin; Node `fs` with a temporary file and a rename; a `WorkspaceEdit` on a text document.

Choice: saves are atomic, on the extension host, with Node's `fs.promises`, which work the same locally on Windows and in the Remote WSL host (the pin is on the host's file system in both cases). Save: (1) open `.conclave/.reviewers.toml.<random>.tmp` with the `wx` flag in the pin's own folder, write the text, `sync`, close; (2) read the pin and compare its SHA-256 with the hash recorded at load, as the last step before the rename, and again before every retry; if it differs, delete the temporary file, refuse, and offer `Reload from disk` (plan R13, `design/SPEC.md` §4); (3) `fs.promises.rename` the temporary file over `.conclave/reviewers.toml` (on Windows Node uses `MoveFileExW` with replace; in WSL `rename(2)`); (4) on any failure, delete the temporary file and say what failed. On Windows a rename onto a file another program holds open can fail with `EPERM` or `EBUSY`: wait 100 ms, re-check the hash, and retry, three times, then report it and keep the edits. The new text's hash becomes the loaded hash. A file watcher on the pin marks the editor stale as soon as another program writes it, so most conflicts are caught before Save is pressed.

What remains: another program that writes the pin in the moment between the last hash check and the rename is overwritten. Neither Windows nor Linux gives a lock that other editors honour, and VS Code's own save has the same window; it is microseconds wide, it needs a second writer at that instant, and closing it would mean a lock no other tool takes. The check at the replacement boundary keeps it to that instant.

Reversal cost: low. One function, with the integration test that proves the stale refusal and the temporary-file cleanup.

## 4. Re-check after every save

Choice: after the rename, the re-check runs `--check-pin --json --pin .conclave/reviewers.toml` on the saved file (plan R14) and its result replaces the shown status. The toast reads `Saved .conclave/reviewers.toml through a temporary file and a rename. Re-checked with --check-pin: ok.` when it is accepted. If the saved pin is refused (the dispatcher changed between the candidate check and the save, or another program wrote the file), the editor shows the refusal at its field exactly as for a candidate, with Save off until it is fixed, and the toast says `Saved, but --check-pin now refuses the pin: {message}`. The file stays saved: the refusal is the dispatcher's verdict on the file, not a failed write.

Reversal cost: low.

## 5. Windows and WSL

The extension is a workspace extension (`"extensionKind": ["workspace"]`), so in a Remote WSL window it runs in the WSL extension host and calls that side's Python (plan R20). It declares limited support for untrusted workspaces (`capabilities.untrustedWorkspaces`: `supported` `"limited"`, with `conclave.pythonPath` as its one `restrictedConfigurations` entry; **corrected 2026-10-21 (reviewer-only extension, `design/decisions.md`, review round 1 of `D02 T01 §24`):** it also called forge and restricted `conclave.sdkPath`, both removed by `D02 T01 §24`; **corrected 2026-10-20:** `conclave.sdkRef` and `conclave.sdkRepository` went with the GitHub source, section 8), because `supported: false` would keep it from activating at all and the Restricted Mode state could never show. In Restricted Mode it activates, starts no process, and every command and view shows `design/SPEC.md` §7's state with `Manage Workspace Trust` (plan R19); one check, `vscode.workspace.isTrusted`, guards the single function that spawns processes, and `onDidGrantWorkspaceTrust` re-runs the workspace detection.

Python is resolved once per session, and again when `conclave.pythonPath` changes (`design/decisions.md` answer 7). A candidate must print a version of 3.11 or later (`tomllib`) (**Corrected 2026-10-20:** 3.11.4 was needed only to extract the GitHub source, dropped in section 8). A set but unusable `conclave.pythonPath` is an error, never a silent fallback.

| Host | Python tried, in order | Paths the extension passes |
| --- | --- | --- |
| Windows, local | `conclave.pythonPath`, `py -3`, `python` | Windows paths (`R:\GitHub\...`) |
| Remote WSL | `conclave.pythonPath`, `python3`, `python` | Linux paths (`/mnt/r/...`) |
| Linux or macOS, local | `conclave.pythonPath`, `python3`, `python` | POSIX paths |

Every process is started with `child_process.spawn` with an argument array (never a shell), the workspace folder as its working directory, `PYTHONIOENCODING=utf-8`, and a timeout; on Windows with `windowsHide: true`.

Reversal cost: medium. A UI extension that shells into WSL would need path translation everywhere.

## 6. Supported `schema_version` range

Choice: the editor edits `schema_version = 1` only (plan R21). When the workspace dispatcher refuses the pin's version, that is the pin-refused screen with the dispatcher's message. When the dispatcher accepts a version other than 1 (a newer dispatcher), the extension shows `This pin is newer than the editor` and opens nothing for editing: reviews still run, and the operator updates the extension or edits by hand. The `--check-pin` output's `schema_version` decides; the extension never parses the pin to find it.

Reversal cost: low. Supporting a version 2 is a new text-model branch and its golden tests, when the dispatcher defines one.

## 7. Packaging

Choice: `npx @vscode/vsce package` in `extensions/vscode/` builds `conclave-<version>.vsix`, with `publisher` `rizonetech`, the name `conclave`, and the bundled SDK under `sdk/` (section 8), whose digest must match `extensions/vscode/sdk-digest.json` (`D05 T02 §2`). **Corrected 2026-10-21 (reviewer-only extension, `design/decisions.md`):** nothing is bundled and the digest record is removed (`D02 T01 §24`). The owner decided on 2026-10-17 that it is not listed on the Visual Studio Marketplace: each version's `.vsix` is attached to a GitHub release of `rizonetech/Conclave-SDK` and installed from there (`design/decisions.md`, plan R22). `D04 T01 §6` recorded that decision point; a later change to it is a new dated decision.

Reversal cost: low. Publishing is a release step, not a code change.

## 8. Where the SDK comes from

**Deferred 2026-10-21 (reviewer-only extension, `design/decisions.md`):** the extension runs no `forge.py`, so this section waits with the kit features; `D02 T01 §24` removed the SDK source, `conclave.sdkPath`, the digest record and its drift test. **Corrected 2026-10-20** (owner, `design/decisions.md`, Read-only kit view and agent import): the extension never installs, updates or sets up a repository, and no kit source is configured. It runs `forge.py` only to read (`kits`, `kit --dry-run`, `check`, `doctor`, `digest`), from one source per run (plan R24):

- Bundled (the default): `forge.py` and `kits/` copied into the `.vsix` under `sdk/` at build time, with `sdk/SDK_COMMIT` naming the commit and `sdk/SDK_DATE` its date. Labelled `bundled Conclave-SDK@<short sha>`.
- `conclave.sdkPath`, a developer override for working on Conclave-SDK itself: a local checkout; it must hold `forge.py` and `kits/`, else the refusal `conclave.sdkPath is not a Conclave-SDK checkout.` Labelled with the path.

The GitHub source this section chose earlier (`conclave.sdkRef`, `conclave.sdkRepository`, the sign-in, tarball download, cache and extraction script) is dropped and its code removed (`D02 T01 §21`); its earlier text is `git show fb5e468:docs/specs/2026-10-20-vscode-extension-design.md`.

The two stay in step through two checks (plan R38 to R40). `forge.py digest` prints the SDK's commit and date and each kit's digest (every template and host overlay file, CRLF read as LF); `extensions/vscode/sdk-digest.json` records it with the extension's version, and a test in Conclave-SDK fails when the kits change without a new version (`D05 T02 §2`). Each project carries a kit stamp, `.conclave/kits.json`, written by forge when every SDK-managed file of a kit in the folder matches the SDK that ran (`D05 T02 §1`); the extension compares each kit's stamp with its own digest and date and shows `newer kits than this extension` or `older kits than this extension` instead of calling the kit partly installed (`D05 T02 §3`).

Reversal cost: high. Restoring the GitHub source means restoring `D02 T01 §7` and `§12` to `§15` from git and their settings; restoring installs means the dropped `D05 T01` flows.

## Not decided here

The feature sections' data contracts are owned by their kits: `todo-graph.py query plan` (`D06 T01 §2`) and `review-dispatch.py --list-rounds --json` (`D06 T01 §3`, hardened by `§8`). The protected-file hash check of the dropped install flows is gone with them (`design/SPEC.md` §10); the `adopt-conclave` skill checks the protected files with git (plan R41).
