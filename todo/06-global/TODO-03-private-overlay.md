---
schema_version: 1
id: private-overlay
domain: 06-global
status: active
title: "TODO-03 -- Public core and private overlay"
---

# TODO-03 -- Public core and private overlay

> **Goal:** Conclave-SDK is developed in the public `rizonesoft/Conclave-SDK` repository, and the owner's own material (machine-wide rules and skills, account-bound plugins, vault items, client names, machine paths) lives only in the private overlay `rizonetech/Conclave-SDK-private`, cloned into the ignored `.private/` folder. A stranger's clone passes `check-all` and CI without the overlay; the owner works in one folder, one command syncs both repositories, and a push that would publish a secret or a private string is refused before it leaves the machine.

> **Current state:** Measured 2026-11-21. The repository went public with its full history and moved to `rizonesoft/Conclave-SDK` on 2026-11-20; secret scanning, push protection and private vulnerability reporting are on, with 0 open alerts. `rizonetech/Conclave-SDK-private` exists and is empty. Owner values already belong in the ignored `.conclave/local.toml` (`forge.py:1626` `LOCAL`, `.conclave/automations/alert.py:33`), but nothing reads a `.private/` folder and `.gitignore` does not ignore one. Tracked files outside `docs/reviews/` that name a vault item, TickTick, Outlook, the owner, an account or a machine path: 163 under `plugins/`, 29 under `global/`, and about 25 in the core (`kits/wordpress` 5, `kits/base` 4, `docs/phase-runs` 6, `kits/unattended`, `kits/toolchain-cpp`, `kits/automations` and `docs/plans` 2 each, and single files in `forge.py`, `README.md`, `todo/`, `tests/`, `scripts/tests`, `.github/ISSUE_TEMPLATE`, `.conclave/`, `.claude/skills` and `.codex/skills`). `forge.py` `SUITES` (around `forge.py:3338`) runs eleven `global-*` and `plugin-*` suites from the public tree, and `global/deploy.py` finds plugins at `GLOBAL.parent / "plugins"`. Commit messages since 2026-11-20 name client imports. `scripts/hooks/` holds only `pre-commit`; `gitleaks` is not installed and CI does not scan history.

## Inputs

- The approved design: `docs/specs/2026-11-21-public-core-private-overlay-design.md` (owner decisions of 2026-11-20 and 2026-11-21: one overlay per repository, `global/` and `plugins/` move into it whole, plans stay public and scrubbed, no fresh history).
- `AGENTS.md` rules this file extends: no machine or owner values in tracked files, stdlib-only Python, atomic writes, kits as the only source with `python forge.py self-sync`, the test cadence.
- `forge.py` (`LOCAL`, `load_projects`, the `SUITES` table, the hooks setup around `forge.py:985`), `.conclave/automations/alert.py`, `.conclave/automations/run.py`, `kits/base`, `global/deploy.py`, `.github/workflows/tests.yml`, `.gitignore`, `CLAUDE.md`, `AGENTS.md`.
- -> XREF: D06 T01 §1 -- that section imported `plugins/` and `global/` into the public tree; §6 and §7 here move them to the overlay

## Outcome

- `.private/` is ignored, and every reader of local settings resolves `.conclave/local.toml`, then `.private/local.toml`, then refuses naming the key, in the base kit and the SDK's installed copy alike.
- Setup clones the overlay, a `post-merge` hook keeps it current, and `python forge.py sync` reports and syncs both repositories.
- A `pre-push` hook refuses outgoing commits or messages holding a `gitleaks` finding or a deny-list string, and CI scans the full public history.
- `global/` and `plugins/` live only in the overlay, deploy and register from there, and their suites run from there when it is present.
- The public tree holds no owner-only rule, vault item, client name, owner name or machine path outside digest-frozen history.

**Adjacency:** all=not-applicable (repository and owner tooling: no product records, pages or user data)

**Adjacency rationale:** The overlay is how the owner's checkout is assembled, not a kit feature, except for the settings reader in §1, which every project gains as a fallback and which changes nothing for a project without `.private/`. Reverse paths are owned: deleting `.private/` and the hooks returns a plain public checkout, and moving `global/` or `plugins/` back is a copy and a commit.

## Implementation Order

| Order | Section | Deliverable | Depends On | Status |
| ----- | ------- | ----------- | ---------- | ------ |
| 1 | §1 | Overlay folder and the settings reader that falls back to it | -- | [ ] |
| 2 | §2 | Overlay clone in setup and pull after merge | §1 | [ ] |
| 3 | §3 | One sync command for both repositories | §2 | [ ] |
| 4 | §4 | Pre-push leak guard over commits and messages | §1 | [ ] |
| 5 | §5 | Full-history secret scan in CI | §4 | [ ] |
| 6 | §6 | Machine-wide rules and skills moved into the overlay | §2 | [ ] |
| 7 | §7 | Connection plugins moved into the overlay | §6 | [ ] |
| 8 | §8 | Agent rules split into public and overlay halves | §1 | [ ] |
| 9 | §9 | Owner values in the core moved into overlay settings | §1, §8 | [ ] |
| 10 | §10 | Live documents and plans scrubbed, deny list seeded | §4, §7, §9 | [ ] |

## 1. Overlay folder and the settings reader that falls back to it

The repository already keeps owner values in the ignored `.conclave/local.toml`. The overlay extends that rule rather than adding a second mechanism: one reader resolves the override first and the overlay second, and it lives in the base kit so the installed copy and every project stay in step.

**Phase:** 10
**Needs:** none
**Surface:** no

**Build order:**

1. Ignore `.private/` and admit the overlay in `AGENTS.md`. Done when: `git check-ignore -v .private/local.toml` names the `.gitignore` line and the "No machine or owner values" rule names `.private/local.toml`.
2. Add the shared reader in the base kit and route every reader through it. Done when: the new tests pass and fail with the order swapped.

- [ ] Add `.private/` to `.gitignore`. Done when: `git check-ignore -v .private/local.toml` names the line. Cheaper substitute: a `.git/info/exclude` entry a fresh clone lacks.
- [ ] Amend the "No machine or owner values in tracked files" rule in `AGENTS.md` to name `.private/local.toml` (from `rizonetech/Conclave-SDK-private`) as the owner's settings and `.conclave/local.toml` as a per-machine override, and state that the overlay never wraps or replaces a public script. Done when: the rule reads so and the Markdown format check passes.
- [ ] Add `read_local_settings(root)` to the base kit's library that loads `.conclave/local.toml` and `.private/local.toml`, merges per key with the override winning, and refuses a malformed file naming the file and reason. Done when: the function exists in the kit with atomic, stdlib-only code. Cheaper substitute: a second copy of the TOML loading in each caller.
- [ ] Route `forge.py` `load_projects` and `LOCAL` users through `read_local_settings`, keeping their refusal messages but naming both files. Done when: `python -m unittest tests.test_forge -k projects` passes.
- [ ] Route `.conclave/automations/alert.py` and `.conclave/automations/run.py` through the reader in the automations kit. Done when: their kit tests pass.
- [ ] Add `tests/test_local_settings.py` covering override only, overlay only, both with override winning per key, neither (refusal names the key), and a malformed overlay file. Done when: they pass and fail when the merge order is swapped.
- [ ] Run `python forge.py self-sync` and the base and automations kit suites. Done when: the installed copy matches and both suites pass.
- [ ] Commit: `overlay: settings fall back to .private/local.toml after the local override`

**Test checkpoint:** `python -m unittest tests.test_local_settings` ends `OK`, and fails with `.private/local.toml` read before `.conclave/local.toml`.

## 2. Overlay clone in setup and pull after merge

The owner should never have to remember the overlay: the setup step that turns on the hooks also clones it when the account can see it, and every pull of the public repository pulls it too. A stranger's setup sees neither step fail.

**Phase:** 10
**Needs:** none
**Surface:** no

**Build order:**

1. Extend the setup that enables `core.hooksPath` (`forge.py:985`) with the overlay clone. Done when: on the owner's account `.private/.git` exists afterwards, and with access refused setup exits 0 saying the overlay was skipped.
2. Add `scripts/hooks/post-merge`. Done when: a pull of the public repository fast-forwards a behind overlay.

- [ ] Add an overlay step that runs `gh repo view` on the overlay name and clones it into `.private/` when that succeeds and `.private/` is absent. Done when: a run on the owner's account reads back `.private`'s origin. Cheaper substitute: an unconditional clone that fails every stranger's setup.
- [ ] Take the overlay name from `[overlay] repo` in the settings reader or `CONCLAVE_OVERLAY_REPO`, defaulting to `rizonetech/Conclave-SDK-private`. Done when: a test changes the clone source through each.
- [ ] Skip with one plain line when `gh` is missing, signed out or refused, and never touch an existing `.private/` or follow a link there. Done when: tests cover each case and setup exits 0.
- [ ] Add `scripts/hooks/post-merge` running `git -C .private pull --ff-only` when `.private/.git` exists, printing one line and never failing the merge. Done when: a test with a behind overlay shows it fast-forwarded. Cheaper substitute: a hook that hides a failed pull.
- [ ] Record `scripts/hooks/post-merge` as executable in git. Done when: `git ls-files -s scripts/hooks/post-merge` starts with `100755`.
- [ ] Add `tests/test_overlay_setup.py` using a local bare repository as the overlay remote. Done when: they pass and fail when the existing-folder guard is removed.
- [ ] Commit: `overlay: setup clones the overlay and every pull keeps it current`

**Test checkpoint:** `python -m unittest tests.test_overlay_setup` ends `OK`, and fails when the existing-folder guard is removed.

## 3. One sync command for both repositories

One place shows whether anything is waiting in either repository, and one run brings both level, so nothing is left unsynced by accident.

**Phase:** 10
**Needs:** none
**Surface:** no

**Build order:**

1. Add `python forge.py sync --check`. Done when: it prints `public` and `overlay` lines with ahead, behind and dirty, and exits 1 when either needs attention.
2. Make a plain run pull and push both. Done when: a behind and ahead pair ends level in a test.

- [ ] Add the `sync` subcommand with `--check`, printing one line per repository and `overlay: not present` without `.private/`. Done when: output matches a fixture for each state. Cheaper substitute: forwarding raw `git status` text.
- [ ] Exit 1 under `--check` when either repository is dirty, ahead or behind. Done when: tests assert each exit code.
- [ ] Without `--check`, pull with `--ff-only` and push each repository that is ahead, overlay first, stopping with the reason on divergence or a refused push. Done when: a diverged test leaves both untouched and exits 1. Cheaper substitute: an unasked merge or rebase.
- [ ] Never stage or commit for the user. Done when: a dirty test repository is unchanged after a run.
- [ ] Add `tests/test_overlay_sync.py` and its file to `tests/shard-seconds.json`. Done when: `python forge.py check-all --only tests` runs them.
- [ ] Document `python forge.py sync` in `README.md`. Done when: the README names it under development setup.
- [ ] Commit: `overlay: one command shows and syncs the public repo and its overlay`

**Test checkpoint:** `python -m unittest tests.test_overlay_sync` ends `OK`, and fails when `--check` ignores a dirty overlay.

## 4. Pre-push leak guard over commits and messages

Every push to a public repository is a publish. The guard refuses one before it leaves the machine when added lines or commit messages hold a secret or a string the owner listed as private, without ever printing the match.

**Phase:** 10
**Needs:** none
**Surface:** no

**Build order:**

1. Add `scripts/leak_scan.py` over a commit range. Done when: it exits 1 naming commit, file and kind for a planted secret, a deny-list hit in a file and a deny-list hit in a message.
2. Call it from `scripts/hooks/pre-push`. Done when: a test push with a planted hit is refused and a clean push goes through.

- [ ] Install `gitleaks` per user (`winget install --id Gitleaks.Gitleaks -e`) and record the version in the README's setup list. Done when: `gitleaks version` prints it.
- [ ] Add `scripts/leak_scan.py --range <a..b>` running `gitleaks git --log-opts <range> --redact`, exit 1 on any finding with commit, file and rule only. Done when: a fake token pattern in a test commit is reported redacted.
- [ ] Add the deny-list pass over added lines and commit messages in the range, matching each non-comment line of `.private/deny-list.txt` case-insensitively and printing commit and file or `message`, never the line or the entry. Done when: a test with a listed string in a message is refused and the output lacks the string. Cheaper substitute: printing the entry, which leaks the list.
- [ ] Refuse, not pass, when `gitleaks` is missing, naming the install command. Done when: a test with it off the PATH exits 1.
- [ ] Add `scripts/hooks/pre-push` reading pushed ranges from standard input and scanning each, skipping pushes to the overlay's remote. Done when: tests cover both. Cheaper substitute: scanning only the last commit.
- [ ] Record `scripts/hooks/pre-push` as executable in git. Done when: `git ls-files -s` shows `100755`.
- [ ] Add `tests/test_leak_scan.py` for secret hit, file hit, message hit, redaction, missing tool, missing deny list and a clean range. Done when: they pass and fail if the message pass is removed.
- [ ] Commit: `overlay: refuse a push that would publish a secret or a private string`

**Test checkpoint:** `python -m unittest tests.test_leak_scan` ends `OK`, and fails when the commit message pass is removed.

## 5. Full-history secret scan in CI

The local guard covers pushes from the owner's machine; CI covers everything else, including history from before the guard. It never sees the overlay, so it scans for secrets only.

**Phase:** 10
**Needs:** none
**Surface:** no

**Build order:**

1. Add a `secrets` job to `.github/workflows/tests.yml`. Done when: it is green on `main` and red on a throwaway branch holding a planted fake token.

- [ ] Add the job on `ubuntu-latest` with `fetch-depth: 0`, running a `gitleaks` release pinned by version and SHA-256 over the whole history with `--redact`. Done when: it runs on the next push. Cheaper substitute: an unpinned download or a scan of the pushed commit only.
- [ ] Add `.gitleaksignore` entries only for proven false positives, each with a comment (the bundled ssh2 probe key in `plugins/codex/website-router/dist/server.mjs` history is the known one). Done when: the job is green on `main`.
- [ ] Prove the job fails with a throwaway branch holding a planted fake token, then delete the branch. Done when: that run is red on `secrets` and `git ls-remote` no longer lists the branch.
- [ ] Commit: `ci: scan the full public history for secrets on every push`

**Test checkpoint:** `python scripts/ci_status.py` reports the `secrets` job green on HEAD, and the recorded run of the planted-token branch is red.

## 6. Machine-wide rules and skills moved into the overlay

`global/` is the owner's machine-wide Claude Code and Codex setup, deployed by `global/deploy.py`. It moves into the overlay whole, deploys from there, and its suites run from there.

**Phase:** 10
**Needs:** none
**Surface:** no

**Build order:**

1. Copy `global/` into `.private/global/` and push the overlay. Done when: `rizonetech/Conclave-SDK-private` holds `global/` with the same files as the public tree's HEAD.
2. Redeploy from the overlay and remove `global/` from the public tree. Done when: `python .private/global/deploy.py` reports every target current and `git ls-files global` prints nothing.

- [ ] Copy `global/` byte for byte into `.private/global/`, excluding `__pycache__/`, and commit and push it in the overlay. Done when: a digest comparison of every file matches the public HEAD. Cheaper substitute: a partial copy that drops tests.
- [ ] Run `python .private/global/deploy.py` and read back that every hook, rule and skill target now points at `.private/global/`. Done when: its report shows no target still deployed from the public `global/`.
- [ ] Update the rule text in `.private/global/claude/` and `.private/global/codex/` that says the global hooks run "from the `global/claude/hooks` folder of the Conclave-SDK checkout" to name `.private/global/`, then redeploy. Done when: the deployed `~/.claude/CLAUDE.md` names the new folder.
- [ ] Move the five `global-*` entries in `forge.py` `SUITES` to `.private/global/...` paths, run when `.private/` exists and reported as skipped otherwise. Done when: `check-all` without the overlay prints them skipped and with it runs them green. Cheaper substitute: deleting the suites.
- [ ] Remove `global/` from the public tree with `git rm -r global`, and update `README.md` and the `AGENTS.md` "Imported material" rule to say it lives in the overlay. Done when: `git grep -n "global/" -- README.md AGENTS.md` names only the overlay location.
- [ ] Commit: `overlay: machine-wide rules and skills live in the private overlay`

**Test checkpoint:** `python forge.py check-all --only global-tests` passes with the overlay present and reports skipped without it.

## 7. Connection plugins moved into the overlay

`plugins/` holds account-bound connection plugins registered on the owner's machine from this checkout. They move into the overlay beside `global/`, keeping `deploy.py`'s `GLOBAL.parent / "plugins"` layout.

**Phase:** 10
**Needs:** none
**Surface:** no

**Build order:**

1. Copy `plugins/` into `.private/plugins/` and push the overlay. Done when: every file matches the public HEAD by digest.
2. Re-register from the overlay and remove `plugins/` from the public tree. Done when: `deploy.py` reports every plugin registered from `.private/plugins/` and `git ls-files plugins` prints nothing.

- [ ] Copy `plugins/` byte for byte into `.private/plugins/`, excluding `node_modules/` and build caches, and push the overlay. Done when: the digest comparison matches. Cheaper substitute: copying only the plugins in use.
- [ ] Run `python .private/global/deploy.py` and read back that `~/.claude.json` MCP entries, the Codex plugins and `~/.gemini/config/plugins/` run from `.private/plugins/`. Done when: no entry points at the public `plugins/` folder.
- [ ] Update every plugin's npm dependencies in `.private/plugins/*/package.json` and `package-lock.json` until `npm audit --omit=dev` reports no high or medium advisory (on 2026-11-21 Dependabot listed 122 open alerts, 17 high, all in the plugin lockfiles, among them `body-parser`, `zod`, `@azure/msal-node`, `hono` and others), then run each plugin's tests. Done when: `npm audit` is clean in each plugin folder and the plugin suites pass. Cheaper substitute: moving the folders so the public alerts disappear while the vulnerable versions keep running.
- [ ] Move the six `plugin-*` entries in `forge.py` `SUITES` and `tests/test_agy_plugins.py` to overlay paths, run when `.private/` exists and skipped otherwise. Done when: `check-all` without the overlay prints them skipped and with it runs them green.
- [ ] Remove `plugins/` from the public tree with `git rm -r plugins`, and update `README.md`, `.github/ISSUE_TEMPLATE/config.yml` and the "Imported material" rule. Done when: `git grep -n "plugins/" -- README.md AGENTS.md .github` names only the overlay location.
- [ ] Confirm the MCP servers still connect after re-registration (`claude mcp list` shows bunny-net and domains-co-za connected). Done when: both read connected.
- [ ] Commit: `overlay: connection plugins live in the private overlay`

**Test checkpoint:** `python forge.py check-all --only plugin-codex-atera` passes with the overlay present and reports skipped without it, and `claude mcp list` shows the plugins connected.

## 8. Agent rules split into public and overlay halves

Agents need the owner's rules on the owner's machine and nowhere else. The public files keep every rule a contributor needs and load the overlay's rules when present.

**Phase:** 10
**Needs:** none
**Surface:** no

**Build order:**

1. Prove how Claude Code handles a missing `@` import and wire the import or a fallback. Done when: the owner's session loads `.private/AGENTS.md` and a checkout without it starts cleanly.

- [ ] Test `@.private/AGENTS.md` in `CLAUDE.md` in a scratch checkout with and without the file, and record whether a missing import is silent with `claude --version`. Done when: the finding is recorded under this section.
- [ ] Add the import to `CLAUDE.md` if silent; otherwise have setup write an ignored `CLAUDE.local.md` holding it. Done when: the owner's session lists the overlay rules. Cheaper substitute: copying the owner's rules into `CLAUDE.md`.
- [ ] Add one line to `AGENTS.md` telling Codex and Antigravity to read `.private/AGENTS.md` when it exists. Done when: the line is present once and not repeated in `CODEX.md` or `GEMINI.md`.
- [ ] Add `tests/test_agent_rules_overlay.py` asserting `CLAUDE.md` and `AGENTS.md` carry the pointer and no `op://`, vault name or machine path. Done when: it passes and fails when an `op://` line is added to `AGENTS.md`.
- [ ] Commit: `overlay: agent rules load the overlay's half when present`

**Test checkpoint:** `python -m unittest tests.test_agent_rules_overlay` ends `OK`, and fails when an `op://` line is added to `AGENTS.md`.

## 9. Owner values in the core moved into overlay settings

With `global/` and `plugins/` gone, about 25 core files still carry owner values. Each becomes a key read through the §1 reader, with its default and meaning in `.conclave/local.example.toml` and its value in `.private/local.toml`.

**Phase:** 10
**Needs:** none
**Surface:** no

**Build order:**

1. Move the owner's `.conclave/local.toml` values into `.private/local.toml`. Done when: the overlay holds them and `.conclave/local.toml` holds only true per-machine overrides or is gone.
2. Replace each owner value in `kits/`, `forge.py`, `scripts/`, `tests/` and the installed skills with a setting or a neutral value. Done when: `git grep -nE "op://|TickTick|Outlook|rizonetech" -- kits forge.py scripts tests .claude .codex` prints only neutral samples.

- [ ] Move the owner's keys from `.conclave/local.toml` into `.private/local.toml` and push the overlay. Done when: the alert automation and the drift report still read their values.
- [ ] Replace vault items and account names in `kits/wordpress`, `kits/base`, `kits/unattended`, `kits/toolchain-cpp`, `kits/automations` and `kits/launchers` with settings documented in `.conclave/local.example.toml`, or neutral samples in tests. Done when: each touched kit's suite passes. Cheaper substitute: an empty default that fails later with a vague error.
- [ ] Replace owner values in `forge.py`, `scripts/tests`, `tests/test_agy_plugins.py` (if it remains) and `.conclave/local.example.toml` with neutral samples. Done when: `python -m unittest tests.test_forge` passes.
- [ ] Run `python forge.py self-sync` and `python forge.py skill-copies` so `.claude/skills`, `.codex/skills` and `.agents/skills` follow the kits. Done when: both report no difference.
- [ ] Move owner-only rules from `AGENTS.md` to `.private/AGENTS.md`, keeping a generic public rule where a contributor needs one. Done when: `AGENTS.md` names no vault or account.
- [ ] Commit: `overlay: owner values in the core read from overlay settings`

**Test checkpoint:** `git grep -nE "op://|TickTick|Outlook|rizonetech" -- kits forge.py scripts tests .claude .codex .agents` prints only neutral samples, and CI is green on the commit.

## 10. Live documents and plans scrubbed, deny list seeded

The last private details sit in live documents and open plan sections. Live text cites repository names and neutral samples; stamped sections, phase-run records and digest-frozen findings stay as written. The deny list then guards every future push.

**Phase:** 10
**Needs:** none
**Surface:** no

**Build order:**

1. Seed `.private/deny-list.txt` and scrub live documents. Done when: the deny-list pass over the live tree prints no hit outside frozen history.
2. Prove the full history with the guard. Done when: `scripts/leak_scan.py` over the full history reports no `gitleaks` finding beyond the recorded ignores.

- [ ] Seed `.private/deny-list.txt` with the owner's name, client and site names, vault and item names, and account names found in this file's current state, and push the overlay. Done when: the list is non-empty and a planted hit is refused by the `pre-push` hook.
- [ ] Replace client names, vault items and machine paths in `README.md`, `docs/plans/`, `docs/specs/` and open sections of `todo/` (including `todo/findings.md`) with neutral wording. Done when: `python scripts/todo-graph.py validate` passes and the deny-list pass over those paths is clean.
- [ ] Leave stamped sections, `docs/phase-runs/` and `docs/reviews/` as written, and record that decision under this section. Done when: the note is present.
- [ ] Word future commit messages for client work neutrally by adding the rule to `.private/AGENTS.md` (client names stay in the overlay). Done when: the rule is present.
- [ ] Run `scripts/leak_scan.py` over the full history. Done when: no finding remains beyond the recorded `.gitleaksignore` entries.
- [ ] Commit: `overlay: scrub live documents and plans, seed the deny list`

**Test checkpoint:** `python scripts/leak_scan.py --range <root>..HEAD` exits 0 on the owner's checkout with the overlay present.

## Verification

- With `.private/` removed, `python forge.py check-all` passes with the overlay suites reported skipped, and CI is green on HEAD including `secrets`.
- With `.private/` present, `python forge.py sync --check` exits 0 after `python forge.py sync`, every overlay suite passes, and a push holding a deny-list string is refused.
- `git ls-files global plugins` prints nothing, and `claude mcp list` shows the plugins connected from `.private/plugins/`.
- `python scripts/todo-graph.py validate` and `python scripts/todo-graph.py plan --check` pass.
