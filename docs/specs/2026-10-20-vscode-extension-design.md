# Conclave VS Code extension: design spec

Date: 2026-10-20. Written by `D00 T01 §4` from the plan (`docs/plans/2026-10-16-vscode-extension.md`), the approved mockup and `design/SPEC.md`, and `design/decisions.md` (approval 2026-10-17, the reviewer route change 2026-10-20). Each decision below records the options weighed, the choice, and the cost of reversing it. Where the owner's answers left a choice open, the choice here is a default, said so.

## 1. Validation runs in the workspace dispatcher

Options: port `load_pin` to TypeScript; call the dispatcher on the saved file only; call it on every candidate (plan R7).

Choice: every candidate is checked by the workspace's own `scripts/review-dispatch.py --check-pin --json --pin <candidate>`, run with the resolved Python (section 5) from the workspace folder; the extension holds no copy of any rule. The candidate is the editor's current text, written to `<os.tmpdir()>/conclave/pin-<process id>-<counter>.toml`: the folder is created with mode `0700`, the file with `0600` and the `wx` flag (never reusing a name), and it is deleted in a `finally` as soon as the dispatcher exits, times out (30 seconds) or cannot start. At activation, files in that folder older than one day are removed, which covers a crash between write and delete. In the Remote WSL extension host `os.tmpdir()` is the Linux side's, which is also where the dispatcher runs. Checks are debounced (300 ms after the last edit) and a newer check cancels an older one, so a slow dispatcher never paints a stale result. The JSON shape is the contract `D01 T01 §2` freezes; output that is not one JSON object with an `ok` key means the dispatcher is too old (plan R18).

Reversal cost: high. A TypeScript port would duplicate every rule, including the 2026-10-20 family rule, and drift from the dispatcher the reviews actually run.

## 2. Comment-preserving edits with a narrow hand-written editor

Options: a TOML library that parses and re-serialises (`@iarna/toml`, `smol-toml`); a library with a concrete syntax tree; a narrow hand-written editor over the text (`design/decisions.md` answer 5 prefers it unless a maintained library round-trips the shipped pin byte for byte).

Choice: a narrow hand-written editor in `extensions/vscode/src/core/pinText.ts` (`D02 T01 §4`). The libraries above parse into plain values and write them back without the comments, which plan R12 forbids; none of the maintained ones offers an edit-in-place writer. The pin's grammar is small and fixed (`load_pin` refuses anything else), so the editor only needs: read the tables and their spans; set one key's value; add, rename and delete a `[reviewers.<name>]` table with the comment block above it; set or remove one route array. Every edit replaces the smallest span it touches and keeps everything else, including comments, blank lines, key order and line endings, byte for byte. This is a default: the library survey here is from the libraries' documented behaviour, and `D02 T01 §4`'s golden tests over the fixture pins are the proof; if a library later round-trips them byte for byte, it can replace the editor behind the same five functions.

Each edit on the shipped pin (`kits/reviewer/templates/.conclave/reviewers.toml`), with the comments kept:

Set a field: astra's effort from `medium` to `high` changes one line.

```toml
# GPT-6 Astra through the Codex CLI, read-only sandbox.
[reviewers.astra]
cli = "codex"
model = "gpt-6-astra"
effort = "high"
```

Add a reviewer: a new table goes after the last reviewer table and before the routes comment, with one blank line on each side.

```toml
# Sonnet 5.5 through Claude Code in plan mode.
[reviewers.sonnet]
cli = "claude"
model = "claude-sonnet-5-5"
effort = "high"

[reviewers.mini]
cli = "codex"
model = "gpt-6-mini"
effort = "low"

# Each writer is reviewed by the other two families: Astra first wherever it
# may review, and the third family as the one fallback.
[routes]
```

Rename a reviewer: the header and every route entry that names it change, nothing else; `astra` to `gpt6`:

```toml
# GPT-6 Astra through the Codex CLI, read-only sandbox.
[reviewers.gpt6]
...
claude = ["gpt6", "gemini"]
codex = ["gemini", "sonnet"]
gemini = ["gpt6", "sonnet"]
```

Delete a reviewer: its table and the comment block directly above it go, and its name leaves every route (a route left empty is removed, never written as `[]`); deleting `sonnet` from the shipped pin leaves `codex = ["gemini"]` and `gemini = ["astra"]`.

Set a route: one array on one line in the file's own style; reordering codex writes `codex = ["sonnet", "gemini"]`. Remove a route: its line goes.

Reversal cost: medium. The editor is one module behind five functions with golden tests; swapping it for a library changes that module only, but only a library that keeps comments can satisfy R12.

## 3. Atomic writes with a stale-disk check

Options: `vscode.workspace.fs.writeFile` over the pin; Node `fs` with a temporary file and a rename; a `WorkspaceEdit` on a text document.

Choice: saves are atomic, on the extension host, with Node's `fs.promises`, which work the same locally on Windows and in the Remote WSL host (the pin is on the host's file system in both cases). Save: (1) read the pin and compare its SHA-256 with the hash recorded at load; if it differs, refuse and offer `Reload from disk` (plan R13, `design/SPEC.md` §4); (2) open `.conclave/.reviewers.toml.<random>.tmp` with the `wx` flag in the pin's own folder, write the text, `sync`, close; (3) `fs.promises.rename` it over `.conclave/reviewers.toml` (on Windows Node uses `MoveFileExW` with replace; in WSL `rename(2)`); (4) on any failure, delete the temporary file and say what failed. On Windows a rename onto a file another program holds open can fail with `EPERM` or `EBUSY`: retry three times at 100 ms, then report it and keep the edits. The new text's hash becomes the loaded hash.

Reversal cost: low. One function, with the integration test that proves the stale refusal and the temporary-file cleanup.

## 4. Re-check after every save

Choice: after the rename, the re-check runs `--check-pin --json --pin .conclave/reviewers.toml` on the saved file (plan R14) and its result replaces the shown status. The toast reads `Saved .conclave/reviewers.toml through a temporary file and a rename. Re-checked with --check-pin: ok.` when it is accepted. If the saved pin is refused (the dispatcher changed between the candidate check and the save, or another program wrote the file), the editor shows the refusal at its field exactly as for a candidate, with Save off until it is fixed, and the toast says `Saved, but --check-pin now refuses the pin: {message}`. The file stays saved: the refusal is the dispatcher's verdict on the file, not a failed write.

Reversal cost: low.

## 5. Windows and WSL

The extension is a workspace extension (`"extensionKind": ["workspace"]`), so in a Remote WSL window it runs in the WSL extension host and calls that side's Python and forge (plan R20). It needs a trusted workspace (`capabilities.untrustedWorkspaces.supported: false`); in Restricted Mode it runs nothing and shows `design/SPEC.md` §7's state (plan R19).

Python is resolved once per session, and again when `conclave.pythonPath` changes (`design/decisions.md` answer 7). A candidate must print a version of 3.11 or later (`tomllib`); 3.11.4 or later is needed only to extract a GitHub source (section 8). A set but unusable `conclave.pythonPath` is an error, never a silent fallback.

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

Choice: `npx @vscode/vsce package` in `extensions/vscode/` builds `conclave-<version>.vsix`, with `publisher` `rizonetech`, the name `conclave`, and the bundled SDK under `sdk/` (section 8). The owner decided on 2026-10-17 that it is not listed on the Visual Studio Marketplace: each version's `.vsix` is attached to a GitHub release of `rizonetech/Conclave-SDK` and installed from there (`design/decisions.md`, plan R22). `D04 T01 §6` recorded that decision point; a later change to it is a new dated decision.

Reversal cost: low. Publishing is a release step, not a code change.

## 8. Where the SDK comes from

The extension runs `forge.py` for every kit operation (plan R24) from one source per run:

- Bundled (the default): `forge.py` and `kits/` copied into the `.vsix` under `sdk/` at build time, with `sdk/SDK_COMMIT` naming the commit. Labelled `bundled Conclave-SDK@<short sha>`.
- `conclave.sdkPath`: a local checkout; it must hold `forge.py` and `kits/`, else the refusal `conclave.sdkPath is not a Conclave-SDK checkout.` Labelled with the path.
- `conclave.sdkRef`: a ref of `conclave.sdkRepository` (default `rizonetech/Conclave-SDK`, internal) on GitHub.

For the GitHub source: the session comes from VS Code's GitHub authentication provider (`vscode.authentication.getSession("github", ["repo"], { createIfNone: true })`), so no token is stored. The ref is resolved to one commit SHA first (`GET /repos/{owner}/{repo}/commits/{ref}` with `Accept: application/vnd.github.sha`); everything after uses that SHA. The source is the REST tarball (`GET /repos/{owner}/{repo}/tarball/{sha}`), not `git clone`, so no Git is needed and nothing but the tree at that SHA arrives. It is cached at `globalStorageUri/sdk/<sha>/`, written to `<sha>.partial/` and renamed into place when complete. Extraction uses the resolved Python's `tarfile` with `filter="data"` (Python 3.11.4 or later), which refuses absolute paths, `..` segments, links and device files; an older Python refuses the GitHub source with that reason instead of extracting without the filter. Nothing downloaded runs until the operator confirms a dialog naming the repository and the SHA. Refusals, each with its actions (`design/SPEC.md` §8): sign-in cancelled, no access (HTTP 404), rate limit used up (HTTP 403 with no requests remaining, naming the reset time), offline, an unusable `sdkPath`, and an archive the extractor refuses. `Use the bundled SDK` is always offered.

Reversal cost: medium. The bundled source alone works offline; the GitHub source is additive, and dropping it removes the sign-in, cache and extraction code without touching the kit operations.

## Not decided here

The feature sections' data contracts are owned by their kits: `todo-graph.py query plan` (`D06 T01 §2`) and `review-dispatch.py --list-rounds --json` (`D06 T01 §3`, hardened by `§8`). Protected files for the hash check are the project-owned files in `design/SPEC.md` §10.
