---
schema_version: 1
id: imported-material
domain: 06-global
status: active
title: "TODO-01 -- Imported material: plugins and retired repositories"
---

# TODO-01 -- Imported material: plugins and retired repositories

> **Goal:** The owner's machine runs its plugins from this checkout's `plugins/` folder, the superseded copies under `R:/Bin` are gone, and the two retired GitHub repositories are deleted, so `Conclave-SDK` is the only home of the imported material.

> **Current state:** Measured 2026-11-11 from `docs/plans/2026-11-11-sdk-audit-and-roadmap.md` (lines 98 to 104). The retired `rizonetech/Claude` and `rizonetech/Codex` repositories were imported byte for byte into `global/` and `plugins/` (378 files) and pushed to `origin/main`; the live copies were compared with the import file by file. `global/deploy.py` deploys the rules, skills and hook wiring from this checkout to the home folder and was run on Windows and in WSL. Not done: the MCP plugin registrations were not moved, so a plugin registered from `R:/Bin` still runs from there; the copies in `R:/Bin/claude` and `R:/Bin/codex` are superseded and still on disk; both GitHub repositories still exist. `plugins/README.md` lists ten imported plugins (eight for Codex, two for Claude).

## Inputs

- `docs/plans/2026-11-11-sdk-audit-and-roadmap.md`: "The two retired repositories" and its end-of-day status.
- `plugins/README.md` and each plugin folder's own `README.md`: which agent loads each plugin and how.
- `global/README.md` and `global/deploy.py`: what is already deployed from this checkout.
- `AGENTS.md` (Imported material): `global/` and `plugins/` are changed only on purpose, never to satisfy a formatter. §1 to §3 edit no file under either folder; §4 changes `global/deploy.py` on purpose, because the hooks it deploys do not run.
- -> XREF: D02 T01 §3 -- Codex's hook trust through its own app-server, which §4 applies to the global hooks

## Outcome

- Every plugin the owner's Codex and Claude Code load is loaded from `<this checkout>/plugins/`, shown by each agent's own plugin or MCP listing.
- `R:/Bin/claude` and `R:/Bin/codex` no longer exist, and nothing on the machine refers to them.
- `rizonetech/Claude` and `rizonetech/Codex` no longer exist on GitHub.

**Adjacency:** all=not-applicable (machine setup for one owner: plugin registrations and the removal of superseded copies, with no records a user lists, exports, is notified of or reverses)

**Adjacency rationale:** The reverse of each step is stated in its own section: a registration can be pointed back, and the deletions are preceded by a comparison that proves the content is on `origin/main`.

## Implementation Order

| Order | Section | Deliverable | Depends On | Status |
| ----- | ------- | ----------- | ---------- | ------ |
| 1 | §1 | Plugins registered from `plugins/` | -- | [ ] |
| 2 | §2 | Superseded copies under `R:/Bin` removed | §1 | [ ] |
| 3 | §3 | Retired GitHub repositories deleted | §2 | [ ] |
| 4 | §4 | Codex approval of the global hooks `deploy.py` writes | D02 T01 §3 | [x] |

## 1. Plugins registered from `plugins/`

> **Started:** 2026-11-15T22:19:23Z

Each plugin's registration in the owner's Codex and Claude Code configuration is pointed at this checkout. The registrations are account-bound and live in the user's own configuration, so this is done with the owner present.

**Corrected 2026-11-16 (validation):** the registrations moved before this section ran: the two Claude servers on 2026-11-14 (`eee7599`, `plugins/claude/scripts/register_claude.py`) and the Codex marketplace with its seven MCP plugins in `dbf6373`. Measured 2026-11-15: no Codex or Claude Code configuration on Windows or in WSL names `R:/Bin` or `/mnt/r/Bin`; `register_claude.py --check` prints `ok` on both systems; Codex's `rizonetech` marketplace is `\\?\D:\Conclave-SDK\plugins\codex` on Windows and `/mnt/d/Conclave-SDK/plugins/codex` in WSL, and Codex runs each plugin from its own install cache (`~/.codex/plugins/cache/rizonetech/<name>/<version>`) copied from that marketplace. The ten plugins are nine registrations: `codex/cloud-access` is scripts with no MCP server, so it has nothing to register. In WSL only `outlook-graph@rizonetech` is installed for Codex; the other Codex plugins are Windows-side. So the first and third items are verified rather than built, the second compares what is still under `R:/Bin` (§2 owns the full comparison), and the fourth is the live proof.

**Phase:** 99
**Needs:** attended
**Surface:** no

**Build order:**

1. List every current registration that points under `R:/Bin`. Done when: each of the ten plugins has its current path recorded.
2. Point each at `plugins/` and prove it loads. Done when: the checkpoint passes.

- [ ] List, without printing any credential, every plugin and MCP registration in the Codex user configuration and the Claude Code plugin configuration on Windows and in WSL whose path is under `R:/Bin` or `/mnt/r/Bin`, as plugin name and path only. Done when: the list covers the ten plugins in `plugins/README.md` or says which are not registered on which side. Cheaper substitute: printing a configuration file whole must fail, because it may hold a token.
- [ ] Compare each registered plugin folder under `R:/Bin` with its folder under `plugins/` file by file, ignoring line endings. Done when: each pair is reported identical, or the differing files are named and the section stops for the owner to say which copy wins.
- [ ] Point each registration at the folder under this checkout's `plugins/`, using each agent's own command or the plugin's own install helper (`plugins/claude/scripts/` for the two Claude plugins), never by hand-editing a file that holds a secret. Done when: each agent's plugin or MCP listing shows the new path for every plugin. Cheaper substitute: copying `plugins/` back over `R:/Bin` must fail; the registration is what moves.
- [ ] Call one read-only tool of each re-registered plugin from its agent. Done when: each answers, or the failure is recorded with the plugin name and the owner decides before §2 starts.
- [ ] Record in `plugins/README.md` that the plugins are registered from this checkout and how to register them on a new machine, as a deliberate change to that README (one of the two files under the imported folders held to the writing rules). Done when: the README has the paragraph.
- [ ] Commit: `plugins: registered from this checkout`

**Test checkpoint:** `grep -rn "R:/Bin\|R:\\\\Bin\|/mnt/r/Bin" <each agent's plugin and MCP configuration, names and paths only>` prints nothing on Windows and in WSL, and one tool call per plugin succeeds; a registration left on the old path shows in that listing.

## 2. Superseded copies under `R:/Bin` removed

Once nothing loads from them, the old copies are a second source that can drift. They are deleted by the owner, after proof that their content is in this repository.

**Phase:** 99
**Needs:** operator
**Surface:** no

**Build order:**

1. Prove the content of `R:/Bin/claude` and `R:/Bin/codex` is in `global/` and `plugins/` at `origin/main`. Done when: the comparison lists no file that exists only under `R:/Bin`.
2. The owner deletes the two folders. Done when: the checkpoint passes.

- [ ] Compare `R:/Bin/claude` and `R:/Bin/codex` with `global/` and `plugins/` at `origin/main`, file by file, ignoring line endings and the old folder names, and list every file that is only under `R:/Bin` or differs. Done when: the list is empty, or each listed file is one the roadmap says was left out on purpose (the repositories' own glue, the deployment logs, the brand permission drafts, the client site list). Cheaper substitute: comparing folder sizes must fail review.
- [ ] Search the home folder's agent configuration, the scheduled tasks and the systemd user units on Windows and in WSL for any remaining path under `R:/Bin/claude` or `R:/Bin/codex`. Done when: none is found, or each is repointed first.
- [ ] The owner deletes `R:/Bin/claude` and `R:/Bin/codex`. Done when: neither folder exists. Cheaper substitute: an agent deleting them without the owner's go-ahead in that session must fail; this is a deletion outside the repository.
- [ ] Remove the sentence in `docs/plans/2026-11-11-sdk-audit-and-roadmap.md` (line 104) that says the copies are superseded and the registrations were not moved, replacing it with the date both were done. Done when: the roadmap's status matches the machine.
- [ ] Commit: `docs: R:/Bin copies removed`

**Test checkpoint:** `Test-Path R:\Bin\claude` and `Test-Path R:\Bin\codex` both print `False`, and `python global/deploy.py` still deploys from this checkout without error.

## 3. Retired GitHub repositories deleted

The roadmap's end-of-day status says both repositories can be deleted. Deleting a repository cannot be undone, so the owner does it.

**Phase:** 99
**Needs:** operator
**Surface:** no

**Build order:**

1. Confirm the import is on `origin/main` and nothing else points at the two repositories. Done when: both checks are recorded.
2. The owner deletes them. Done when: the checkpoint passes.

- [ ] Confirm `git log origin/main --oneline -- global plugins` shows the import commits (`f06262c` and `0b36764`) and `git status -sb` shows `main` level with `origin/main`. Done when: both are true on the day of the deletion.
- [ ] Search the owner's checkouts and the two agents' configuration for `rizonetech/Claude` and `rizonetech/Codex` as a git remote, a submodule or a marketplace source. Done when: none is found, or each is repointed first.
- [ ] The owner deletes `rizonetech/Claude` and `rizonetech/Codex` on GitHub. Done when: `gh repo view rizonetech/Claude` and `gh repo view rizonetech/Codex` both report that the repository does not exist. Cheaper substitute: archiving them in place must fail; the roadmap's status is "can be deleted", and an archive is a second copy.
- [ ] Update "The two retired repositories" in `docs/plans/2026-11-11-sdk-audit-and-roadmap.md` with the deletion date. Done when: the section says the repositories are deleted.
- [ ] Commit: `docs: retired repositories deleted`

**Test checkpoint:** `gh repo view rizonetech/Claude` and `gh repo view rizonetech/Codex` each exit non-zero with "Could not resolve to a Repository".

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
