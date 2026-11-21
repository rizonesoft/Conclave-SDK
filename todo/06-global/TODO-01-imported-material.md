---
schema_version: 1
id: imported-material
domain: 06-global
status: done
title: "TODO-01 -- Imported material: plugins and retired repositories"
---

# TODO-01 -- Imported material: plugins and retired repositories

> **Goal:** The owner's machine runs its plugins from this checkout's `plugins/` folder, the superseded copies under `R:/Bin` are gone, and the two retired GitHub repositories are deleted, so `Conclave-SDK` is the only home of the imported material.

> **Current state:** Measured 2026-11-11 from `docs/plans/2026-11-11-sdk-audit-and-roadmap.md` (lines 98 to 104). The retired `rizonetech/Claude` and `rizonetech/Codex` repositories were imported byte for byte into `global/` and `plugins/` (378 files) and pushed to `origin/main`; the live copies were compared with the import file by file. `global/deploy.py` deploys the rules, skills and hook wiring from this checkout to the home folder and was run on Windows and in WSL. Not done: the MCP plugin registrations were not moved, so a plugin registered from `R:/Bin` still runs from there; the copies in `R:/Bin/claude` and `R:/Bin/codex` are superseded and still on disk; both GitHub repositories still exist. `plugins/README.md` lists ten imported plugins (eight for Codex, two for Claude).

## Inputs

- `docs/plans/2026-11-11-sdk-audit-and-roadmap.md`: "The two retired repositories" and its end-of-day status.
- `plugins/README.md` and each plugin folder's own `README.md`: which agent loads each plugin and how.
- `global/README.md` and `global/deploy.py`: what is already deployed from this checkout.
- `AGENTS.md` (Imported material): `global/` and `plugins/` are changed only on purpose, never to satisfy a formatter. §4 changes `global/deploy.py` on purpose, because the hooks it deploys do not run. **Corrected 2026-11-16 (D06 T01 §3 completion review):** this said §1 to §3 edit no file under either folder; they change these on purpose, each a defect or a stale statement the live work found: `global/codex/hooks/session_drift_check.py` and its test (§1, §3), `global/README.md` (§2), `plugins/README.md` (§1, §3), `plugins/codex/README.md` (§2, §3), `plugins/codex/outlook-graph/scripts/dpapi-store.ps1` and its test (§1), `plugins/codex/atera/README.md` and the seven Codex `plugin.json` files (§3).
- -> XREF: D02 T01 §3 -- Codex's hook trust through its own app-server, which §4 applies to the global hooks
- -> XREF: D06 T03 §6 -- moves the imported `global/` and `plugins/` from the public tree into the private overlay

## Outcome

- Every plugin the owner's Codex and Claude Code load is loaded from `<this checkout>/plugins/`, shown by each agent's own plugin or MCP listing.
- `R:/Bin/claude` and `R:/Bin/codex` no longer exist, and nothing on the machine refers to them.
- `rizonetech/Claude` and `rizonetech/Codex` no longer exist on GitHub.

**Adjacency:** all=not-applicable (machine setup for one owner: plugin registrations and the removal of superseded copies, with no records a user lists, exports, is notified of or reverses)

**Adjacency rationale:** The reverse of each step is stated in its own section: a registration can be pointed back, and the deletions are preceded by a comparison that proves the content is on `origin/main`.

## Implementation Order

| Order | Section | Deliverable | Depends On | Status |
| ----- | ------- | ----------- | ---------- | ------ |
| 1 | §1 | Plugins registered from `plugins/` | -- | [x] |
| 2 | §2 | Superseded copies under `R:/Bin` removed | §1 | [x] |
| 3 | §3 | Retired GitHub repositories deleted | §2 | [x] |
| 4 | §4 | Codex approval of the global hooks `deploy.py` writes | D02 T01 §3 | [x] |

## 1. Plugins registered from `plugins/`

> **Started:** 2026-11-15T22:19:23Z

Each plugin's registration in the owner's Codex and Claude Code configuration is pointed at this checkout. The registrations are account-bound and live in the user's own configuration, so this is done with the owner present.

**Corrected 2026-11-16 (validation):** the registrations moved before this section ran: the two Claude servers on 2026-11-14 (`eee7599`, `plugins/claude/scripts/register_claude.py`) and the Codex marketplace with its seven MCP plugins in `dbf6373`. Measured 2026-11-15: no Codex or Claude Code configuration on Windows or in WSL names `R:/Bin` or `/mnt/r/Bin`; `register_claude.py --check` prints `ok` on both systems; Codex's `rizonetech` marketplace is `\\?\D:\Conclave-SDK\plugins\codex` on Windows and `/mnt/d/Conclave-SDK/plugins/codex` in WSL, and Codex runs each plugin from its own install cache (`~/.codex/plugins/cache/rizonetech/<name>/<version>`) copied from that marketplace. The ten plugins are nine registrations: `codex/cloud-access` is scripts with no MCP server, so it has nothing to register. In WSL only `outlook-graph@rizonetech` is installed for Codex; the other Codex plugins are Windows-side. So the first and third items are verified rather than built, the second compares what is still under `R:/Bin` (§2 owns the full comparison), and the fourth is the live proof.

**Corrected 2026-11-16 (plan review, `docs/reviews/06-global/D06-T01-s1.md`):** a marketplace path and a tool call do not prove Codex runs this checkout's content, because Codex runs an installed copy; and the population was stated four ways. The items below now name one matrix (Codex on Windows: `atera`, `bunny-net`, `conclave`, `domains-co-za`, `outlook-graph`, `pressable`, `website-router`; Codex in WSL: `outlook-graph`; Claude Code on both: `bunny-net`, `domains-co-za`; `codex/cloud-access`: not applicable, no MCP server), inventory every registration whatever its path, prove each installed copy matches this checkout, and call a tool from a fresh session for every entry. The live proof found two defects, fixed here (the drift check missed a bundled plugin's `scripts/`, and `outlook-graph`'s credential helper failed from WSL), and three Codex plugins with no credential store on this Windows host, seeded from the vault.

**Phase:** 99
**Needs:** attended
**Surface:** no

**Build order:**

1. List every current registration, whatever its path. Done when: each matrix entry has its current path recorded (was: "points under `R:/Bin`", "each of the ten plugins"; corrected 2026-11-16, plan review).
2. Point each at `plugins/` and prove it loads from this checkout's content. Done when: the checkpoint passes.

- [x] List, without printing any credential, every plugin and MCP registration in the Codex user configuration and the Claude Code configuration on Windows and in WSL, whatever its path, as name and path only. Done when: the list covers the matrix above and names any registration outside it. Cheaper substitute: printing a configuration file whole must fail, because it may hold a token. Done 2026-11-15: no entry names `R:/Bin` or `/mnt/r/Bin`; Codex's `rizonetech` marketplace is `\\?\D:\Conclave-SDK\plugins\codex` (Windows) and `/mnt/d/Conclave-SDK/plugins/codex` (WSL); Claude's two servers run Windows Node on `D:\Conclave-SDK\plugins\claude\<name>\dist\server.mjs` on both systems, no `env` block; outside the matrix only a dead `rizonetech-local` marketplace (a WSL folder that no longer exists, holding no plugin).
- [x] Compare each registered plugin folder under `R:/Bin` with its folder under `plugins/` file by file, ignoring line endings. Done when: each pair is reported identical, or the differing files are named and the section stops for the owner to say which copy wins. Done 2026-11-16: every file under the two folders was hashed against every blob `origin/main` has held under `global/` and `plugins/`; the 36 code and README files that differ do so only in lines naming the old folders, and the rest are §2's left-out material. The owner chose this checkout ("please delete R:\Bin\claude and R:\Bin\codex", 2026-11-16).
- [x] Point each registration at the folder under this checkout's `plugins/`, using each agent's own command or the plugin's own install helper, never by hand-editing a file that holds a secret. Done when: each agent's listing shows this checkout for every matrix entry. Cheaper substitute: copying `plugins/` back over `R:/Bin` must fail; the registration is what moves. Done before this section (`eee7599`, `dbf6373`); verified by the first item and by `register_claude.py --check` printing `ok` on both systems.
- [x] Make `plugin_drift` in `global/codex/hooks/session_drift_check.py` compare every installed copy's `scripts/` with this checkout for bundled plugins too, not only `dist/*.mjs` and the manifest. Done when: `test_bundled_plugin_cached_scripts` in `global/codex/hooks/test_session_drift_check.py` passes, and fails (errors) with the old check, on Windows and in WSL. Cheaper substitute: refreshing the caches without changing the check must fail review; the check passed on a stale `outlook-graph` copy.
- [x] Make `plugins/codex/outlook-graph/scripts/dpapi-store.ps1` load its own engine's Security module (`$PSHOME`), so a WSL-started helper whose inherited module path lists PowerShell 7 first still decrypts the session. Done when: the test "the DPAPI helper works when PowerShell 7's modules come first on the inherited module path" in `tests/store.test.js` passes, fails on the old script, and the plugin's `npm test` passes (82). Cheaper substitute: dropping `PSModulePath` in the WSL shell must fail; it comes from the Windows process that started `wsl.exe`, which the bridge cannot change.
- [x] Refresh each stale installed copy with `codex plugin add <name>@rizonetech` and prove every copy matches this checkout. Done when: the drift check prints nothing on Windows and in WSL. Done 2026-11-16: `outlook-graph` refreshed on both systems; the WSL copy was the one the fixed check named.
- [x] Call one read-only tool of each matrix entry from a fresh session of its agent. Done when: each answers, or the failure is recorded with the plugin name and its cause and the owner decides before §2 starts (corrected 2026-11-16 after the round: the owner's decision had been dropped). Done 2026-11-16: Codex on Windows, `connection_status` ok for `atera`, `bunny-net`, `domains-co-za`, `pressable`, and `website-router` (10 of 13 sites connected; Rizonetech, Rizonetech Launch and Swiss Hotel School Staging did not, a site-side state), `memory_health` ok for `conclave`; Codex in WSL, `outlook-graph` ok; Claude Code on Windows and in WSL, `bunny-net` and `domains-co-za` connected. `atera`, `bunny-net` and `website-router` answered only after their stores were seeded from the Conclave vault with their own import scripts. Not answered: `outlook-graph` from Codex on Windows, which binds its 14 tools yet never exposes them to the model (filed in `todo/findings.md`); the same server answers `connection_status` when started from its Windows copy directly. Owner decision, 2026-11-16, asked after one more run with the `apps` feature off changed nothing: accept it as a recorded Codex issue and carry on with §2 and §3.
- [x] Record in `plugins/README.md` that the plugins are registered from this checkout and how to register them on a new machine, as a deliberate change to that README (one of the two files under the imported folders held to the writing rules). Done when: the README has the paragraph. Done: "Registered from this checkout".
- [x] Commit: `plugins: registered from this checkout`

**Test checkpoint:** on Windows and in WSL, `grep -rn "R:/Bin\|R:\\\\Bin\|/mnt/r/Bin"` over each agent's plugin and MCP configuration (names and paths only) prints nothing, `register_claude.py --check` prints `ok`, the drift hook run by hand prints nothing, and one tool call per matrix entry answers or its failure carries the owner's recorded decision; a registration left on the old path shows in the listing, and a stale installed copy makes the drift hook name it.

> **Verified:** 2026-11-16 | §1 | 8a3f67df0b750ce4b947c35e4cfd591590166569
> **Review:** `docs/reviews/d06-t01-s1.json`

## 2. Superseded copies under `R:/Bin` removed

> **Started:** 2026-11-15T22:59:21Z

Once nothing loads from them, the old copies are a second source that can drift. They are deleted by the owner, after proof that their content is in this repository.

**Corrected 2026-11-16 (validation):** the `operator` Need is answered. The owner said in the attended session of 2026-11-16, before this section started, "please delete R:\Bin\claude and R:\Bin\codex" and then "Then complete phase 99", so the agent deletes the folders on that go-ahead once the comparison and the search are clean; the Need is now `attended`. The comparison is done and committed: `docs/reviews/06-global/D06-T01-bin-comparison.md` names all 88 files with no identical blob in the repository (28 differ only in lines naming the old folders, 9 are the old repositories' glue and logs, 51 are derived, local or backup material). Two statements in the repository call the copies a rollback that will no longer exist (`global/README.md:54`, `plugins/codex/README.md:31`), and the roadmap sentence moved to line 106; both are added below. Two vendor notes beside the tunnel client (`configuration.md`, `onboarding.md`) exist nowhere else, so they are kept beside the extracted client in this checkout's git-ignored `plugins/codex/.local/tunnel-client/` before the delete.

**Phase:** 99
**Needs:** attended
**Surface:** no

**Build order:**

1. Prove the content of `R:/Bin/claude` and `R:/Bin/codex` is in `global/` and `plugins/` at `origin/main`. Done when: the comparison lists no file that exists only under `R:/Bin` unaccounted for.
2. Delete the two folders on the owner's go-ahead. Done when: the checkpoint passes.

- [x] Compare `R:/Bin/claude` and `R:/Bin/codex` with `global/` and `plugins/` at `origin/main`, file by file, ignoring line endings and the old folder names, and list every file that is only under `R:/Bin` or differs. Done when: the list is empty, or each listed file is one the roadmap says was left out on purpose (the repositories' own glue, the deployment logs, the brand permission drafts, the client site list) or is derived, local or backup material named in `docs/reviews/06-global/D06-T01-bin-comparison.md`. Cheaper substitute: comparing folder sizes must fail review. Done 2026-11-16: 466 files hashed against 683 blobs; 378 identical, and each of the other 88 is named by kind in the inventory (28 path-only, 9 glue and logs, 51 derived, local or backup).
- [x] Search the home folder's agent configuration, the scheduled tasks and the systemd user units on Windows and in WSL for any remaining path under `R:/Bin/claude` or `R:/Bin/codex`. Done when: none is found, or each is repointed first. Done 2026-11-16: 0 matches in the Codex and Claude Code configuration on both systems, no scheduled task, service or `PATH` entry on Windows, no systemd user unit or crontab line in WSL.
- [x] Search the persisted plugin state under `%LOCALAPPDATA%\Rizonetech` (and Codex's packaged copy of it), and every running process's executable and command line, for a path under `R:/Bin/claude` or `R:/Bin/codex`, reporting file names and counts only and skipping encrypted stores. Done when: none is found, or each is repointed first; the Conclave tunnel client is seen running from this checkout. **Added 2026-11-16 (plan review):** a scheduled task pointing here does not prove a running tunnel or a saved launch command has left `R:/Bin`. Done 2026-11-16: no file under either store names the old folders, no process executable or command line does, and `tunnel-client.exe` runs from `D:\Conclave-SDK\plugins\codex\.local\tunnel-client\v0.0.15`.
- [x] Copy `R:/Bin/codex/.local/tunnel-client/configuration.md` and `onboarding.md` into `plugins/codex/.local/tunnel-client/`. Done when: both are there byte for byte (SHA-256) and `git check-ignore` reports them ignored. Cheaper substitute: committing them must fail; `.local/` is local material. Done 2026-11-16: both SHA-256 equal, both ignored (`.gitignore:5`).
- [x] Delete `R:/Bin/claude` and `R:/Bin/codex` on the owner's go-ahead recorded above. Done when: neither folder exists. Cheaper substitute: an agent deleting them without the owner's go-ahead in that session must fail; this is a deletion outside the repository. Done 2026-11-16: 6,970 files (58.6 MB) and 350 files (104.5 MB) removed; both `Test-Path` print `False`; the rest of `R:\Bin` is untouched.
- [x] After the delete, call one read-only tool of each entry of §1's matrix from a fresh session of its agent, and read `plugins/codex/conclave/scripts/Manage-Cloud.ps1 -Action Status`, leaving the `Rizonetech Plugin Cloud Access` task disabled. Done when: every entry answers as it did in §1 (the owner-accepted Windows Codex `outlook-graph` exception aside, no new failure) and the Conclave status reads running. **Added 2026-11-16 (plan review):** `deploy.py` deploys rules, skills and hooks and exercises no plugin. Done 2026-11-16: Codex on Windows answered for `atera`, `bunny-net`, `conclave`, `domains-co-za`, `pressable` and `website-router` (10 of 13 sites, as in §1), `outlook-graph` as accepted; Codex in WSL `outlook-graph` ok; Claude Code on both systems `bunny-net` and `domains-co-za` ok; Conclave `running`, `healthy`, `ready`; the provider task `Disabled`.
- [x] Replace the rollback statements in `global/README.md` (line 54) and `plugins/codex/README.md` (line 31) with the date the copies were deleted. Done when: neither README calls `R:\Bin` a rollback copy. Done: both now say the copy was deleted on 2026-11-16 and cite the inventory.
- [x] Remove the sentence in `docs/plans/2026-11-11-sdk-audit-and-roadmap.md` (line 106) that says the copies are superseded and the registrations were not moved, replacing it with the date both were done. Done when: the roadmap's status matches the machine. Done: item 3 of "The two retired repositories" now dates both.
- [x] Commit: `docs: R:/Bin copies removed`

**Test checkpoint:** `Test-Path R:\Bin\claude` and `Test-Path R:\Bin\codex` both print `False`, and `python global/deploy.py` still deploys from this checkout without error on Windows and in WSL; after the delete, one read-only call per §1 matrix entry answers (the accepted Windows Codex `outlook-graph` exception aside) and the Conclave status reads running. A process or saved command still using `R:/Bin` shows in the search, and fails a call once the folders are gone.

> **Verified:** 2026-11-16 | §2 | 5517e96fa5ae06cea8f3ca25397ce02be3fdcbed
> **Review:** `docs/reviews/d06-t01-s2.json`

## 3. Retired GitHub repositories deleted

> **Started:** 2026-11-15T23:19:34Z

The roadmap's end-of-day status says both repositories can be deleted. Deleting a repository cannot be undone, so the owner does it.

**Corrected 2026-11-16 (validation):** the owner already deleted both before this run: `gh repo view rizonetech/Claude` and `gh repo view rizonetech/Codex` print "Could not resolve to a Repository" (first measured 2026-11-15T22:05Z, again at 23:19Z, with a token that can see the organisation's repositories), so the third item is verified, not done, and the `operator` Need is answered (the owner also asked in the session for Phase 99 to be completed); it is now `attended`. The search found no git remote or submodule for either repository in 156 checkouts on Windows and in WSL, but the retired `rizonetech/Codex` is still the author link in the seven Codex `plugin.json` files and the clone source in `plugins/codex/atera/README.md:92`, and Claude Code in WSL still lists a `rizonetech` marketplace whose source, `rizonetech/claude-plugins`, no longer exists either (nothing is installed from it). Those are added below. Claude Code's own `githubRepoPaths` record in the Windows `~/.claude.json` still maps `rizonetech/claude` to the vanished `R:\Claude`: it is a local cache the CLI owns, neither a remote nor a source, and is left to Claude Code.

**Phase:** 99
**Needs:** attended
**Surface:** no

**Build order:**

1. Confirm the import is on `origin/main` and nothing else points at the two repositories. Done when: both checks are recorded.
2. The owner deletes them. Done when: the checkpoint passes.

- [x] Confirm `git log origin/main --oneline -- global plugins` shows the import commits (`f06262c` and `0b36764`) and `git status -sb` shows `main` level with `origin/main`. Done when: both are true on the day of the deletion. Done 2026-11-16: both import commits are listed, and `main` is level with `origin/main` (`## main...origin/main`).
- [x] Search the owner's checkouts and the two agents' configuration for `rizonetech/Claude` and `rizonetech/Codex` as a git remote, a submodule or a marketplace source. Done when: none is found, or each is repointed first. Done 2026-11-16: no remote or submodule in 102 checkouts on Windows and 54 in WSL; no Codex or Claude Code marketplace source names either repository; the stale links found instead are the next four items.
- [x] Make `plugin_drift` in `global/codex/hooks/session_drift_check.py` compare each installed copy's `plugin.json` with this checkout's, beside the MCP manifest. Done when: a test in `global/codex/hooks/test_session_drift_check.py` with a stale cached `plugin.json` fails on the old check and passes on the new one, on Windows and in WSL. **Added 2026-11-16 (plan review):** the check compared only `mcp.json`, so a copy keeping the dead link passed. Done: `test_plugin_manifest` errors on the old check; 17 tests pass on Windows and in WSL.
- [x] Point the author link in each `plugins/codex/<name>/plugin.json` at `https://github.com/rizonetech/Conclave-SDK`, then refresh each installed Codex copy with `codex plugin add <name>@rizonetech`. Done when: `git grep -c "github.com/rizonetech/Codex" -- plugins/codex` exits 1 with no output (no match, not an error), and the drift check prints nothing on Windows and in WSL. Cheaper substitute: leaving the dead link because nothing calls it must fail review; Codex shows it as the developer's link. **Corrected 2026-11-16 (plan review):** the grep was not scoped, so it matched this file. Done 2026-11-16: seven links replaced, every `plugin.json` still parses; the drift check named all seven Windows copies and the WSL `outlook-graph` copy before the refresh and prints nothing on either system after it; the grep exits 1 with no output.
- [x] Rewrite the "Move to another computer" steps in `plugins/codex/atera/README.md` for this checkout: clone `https://github.com/rizonetech/Conclave-SDK`, build in `plugins/codex/atera`, register `<checkout>/plugins/codex`. Done when: the steps, run against a scratch `CODEX_HOME` (marketplace add, then `codex plugin add atera@rizonetech`), install `atera` into that home's cache and leave the real `~/.codex` unchanged. **Added 2026-11-16 (plan review):** only the clone URL was planned, and the build and registration paths named the old repository's layout. Done 2026-11-16: the scratch home received `atera` 0.1.5 with `dist/server.mjs` and the new author link; the real `~/.codex/config.toml` hash is unchanged.
- [x] Remove Claude Code's dead `rizonetech` marketplace in WSL with `claude plugin marketplace remove rizonetech`. Done when: neither `~/.claude/plugins/known_marketplaces.json` nor `~/.claude/settings.json` in WSL names `rizonetech/claude-plugins`, and every enabled plugin is still installed. Cheaper substitute: editing the two files by hand must fail; the CLI owns them. Done 2026-11-16: "Successfully removed marketplace: rizonetech"; neither file names it; no enabled plugin is missing.
- [x] The owner deletes `rizonetech/Claude` and `rizonetech/Codex` on GitHub. Done when: `gh repo view rizonetech/Claude` and `gh repo view rizonetech/Codex` both report that the repository does not exist. Cheaper substitute: archiving them in place must fail; the roadmap's status is "can be deleted", and an archive is a second copy. Verified 2026-11-16 (the owner deleted both before this section): each `gh repo view` prints "Could not resolve to a Repository".
- [x] Update "The two retired repositories" in `docs/plans/2026-11-11-sdk-audit-and-roadmap.md` with the deletion date. Done when: the section says the repositories are deleted. Done: its 2026-11-16 status says so.
- [x] Commit: `docs: retired repositories deleted`

**Test checkpoint:** `gh repo view rizonetech/Claude` and `gh repo view rizonetech/Codex` each exit non-zero with "Could not resolve to a Repository".

> **Verified:** 2026-11-16 | §3 | 900adae1b7b54e68714df3bedc6ebc319b05d022
> **Review:** `docs/reviews/d06-t01-s3.json`

## 4. Codex approval of the global hooks `deploy.py` writes

> **Started:** 2026-11-12T03:59:17Z

Filed 2026-11-12 from `D02 T01 §3`. Codex's `hooks/list` reports every hook in the owner's `~/.codex/hooks.json` (`layer_rules.py` and `article_rules.py` from `global/codex/hooks`) as `modified`: their approvals are for earlier versions, so Codex skips them and the layer and writing rules do not run in Codex sessions. `deploy.py` writes that file, so it also approves what it wrote, through the same Codex interface the todo kit's `codex-hook-trust.py` uses.

**Corrected 2026-11-12 (validation):** `codex-hook-trust.py` (D02 T01 §3) already holds the app-server client: its stdio JSON-RPC, the job object and suspended start on Windows, the process group elsewhere. `deploy.py` loads it by path from this checkout (`kits/todo/templates/scripts/codex-hook-trust.py`) rather than carrying a second copy, through two functions the script gains: `list_hooks(cwd, codex_home)` and `approve_hooks(cwd, hooks, codex_home)`. `--home DIR` deploys to `DIR/.codex`, so the app-server is started with `CODEX_HOME` set to that folder, and the approval lands in that home's `config.toml`, never the real one. User hooks need no project trust, only the hook approval.

**Phase:** 2
**Needs:** none
**Surface:** no

**Build order:**

1. Approve the deployed hooks from `deploy_codex` in `global/deploy.py`. Done when: `hooks/list` reports them `trusted`.
2. Cover it and document it. Done when: the checkpoint passes.

- [x] Add a `trust_codex_hooks(home)` step to `deploy_codex` in `global/deploy.py`: after `hooks.json` is written, call `list_hooks` of the todo kit's `codex-hook-trust.py` (with `CODEX_HOME` set from `--home`) and write `trusted_hash` through its `approve_hooks` for each `user`-source hook whose `sourcePath` is the deployed `hooks.json` and whose command names a script under `global/codex/hooks`; skipped with one line under `--dry-run`, when `codex` is not installed, or when the server does not answer in 30 seconds. A hook the operator disabled (`enabled` false) is left disabled, reported as such and never approved; the outcome lists each deployed hook as `approved`, `trusted`, `disabled` or `not approved` with the reason, a refused or timed-out approval leaves the rest reported as they stand, and a rerun approves only what is still not trusted. Done when: deploys on Windows and in WSL each end with every deployed hook `trusted` in a fresh `hooks/list` (each key accounted for) and no other hook's state changed. **Corrected 2026-11-12 (plan review):** disabled hooks, partial failures, the retry and the WSL side were unstated. Cheaper substitute: computing the hash must fail review; Codex computes it.
- [x] Test `trust_codex_hooks` in `global/tests` with a stub app-server answering recorded responses. Done when: the stub, starting from `modified` hooks, receives one `config/value/write` per deployed hook carrying exactly its key and the `currentHash` the listing gave, and a fresh listing after the writes (the stub applying them) reads `trusted`, so a skipped or corrupted write fails; none is sent for a plugin hook, another file's hook, a disabled hook or one already `trusted`; a listing with no deployed hook, a refused write, a server that stops answering after one approval, `--dry-run` and a missing `codex` each report truthfully; and a test with a relative `--home` and a different ambient `CODEX_HOME` finds every listing and write made against the deployment home and the ambient one untouched. **Corrected 2026-11-12 (plan review):** a recorded success proved no hash was persisted, and `--home` isolation was untested.
- [x] State the step in `global/README.md`. Done when: the README says that a deploy approves the hooks it wrote and how to check them (`hooks/list` through `codex app-server`, or a Codex session's hook list).
- [x] Commit: `global: deploy.py approves the Codex hooks it writes`

**Test checkpoint:** `python global/deploy.py --agent codex` ends with the deployed hooks `trusted` in Codex's `hooks/list`; making `trust_codex_hooks` skip the write leaves them `modified` and its test fails.

> **Verified:** 2026-11-12 | §4 | 0b65d86feaa6dc4f010c2475fd9d4b4f1d3dfac3
> **Review:** `docs/reviews/d06-t01-s4.json`
## Verification

- Each plugin in `plugins/README.md` loads from this checkout on Windows and in WSL.
- Neither `R:/Bin/claude` nor `R:/Bin/codex` exists, and neither retired repository exists on GitHub.
- `python scripts/todo-graph.py validate` and `python scripts/todo-graph.py plan --check` pass.
