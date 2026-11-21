# Public core and private overlay

**Status:** approved design, not built. **Owner decisions:** 2026-11-20 and 2026-11-21. **Plan:** `todo/06-global/TODO-03-private-overlay.md`.

## What changed and why

On 2026-11-20 Conclave-SDK went public with its full history and moved from `rizonetech/Conclave-SDK` to `rizonesoft/Conclave-SDK`. The owner decided that development happens on the public repository, and that a small private overlay, `rizonetech/Conclave-SDK-private`, holds only the owner's own material. One codebase means no private fork to drift and nothing ever waiting to be integrated.

Decisions:

- One overlay per repository. Bosun has its own (`rizonetech/Bosun-private`) and this repository never reads it.
- `global/` (the owner's machine-wide Claude Code and Codex rules, hooks and skills) and `plugins/` (account-bound connection plugins) move into the overlay whole (owner, 2026-11-21). They are the owner's machine and business tooling, `forge.py` never installs either into a project, and moving them leaves the public SDK as the kits, `forge.py`, `scripts/` and tests. A plugin can be published on its own later.
- `todo/`, `docs/plans/` and `docs/specs/` stay public, scrubbed of machine paths, vault items and client names. Findings files under `docs/reviews/` are digest-frozen history and stay as written.
- Fresh history is dropped: the history has been public since 2026-11-20.

## How does it sit on the machine?

```
D:\GitHub\Conclave-SDK\        clone of rizonesoft/Conclave-SDK (public)
  .gitignore                   ignores .private/
  .conclave\local.toml         optional per-machine override, ignored (as today)
  .private\                    clone of rizonetech/Conclave-SDK-private
    local.toml                 the owner's values, same keys as .conclave/local.example.toml
    AGENTS.md                  owner-only agent rules
    deny-list.txt              strings that must never reach the public repo
    global\                    moved from the public tree, deploy.py unchanged in shape
    plugins\                   moved from the public tree
```

`global/deploy.py` finds plugins at `GLOBAL.parent / "plugins"`, so keeping both folders side by side under `.private/` keeps that layout.

## How do the owner's values reach the code?

The repository already keeps owner values out of tracked files as keys in the ignored `.conclave/local.toml`. The overlay extends that rule instead of adding a second mechanism: every reader of local settings resolves `.conclave/local.toml` first (a per-machine override) and `.private/local.toml` second, and refuses naming the key when neither has it. The reader lives in the base kit, so every project that installs the kit gains the same overlay support, and the SDK's installed copy follows through `python forge.py self-sync`.

## How does it stay in sync?

- **Setup** clones the overlay into `.private/` when `gh repo view rizonetech/Conclave-SDK-private` succeeds, and skips it quietly otherwise.
- **Pull:** a `post-merge` hook pulls `.private/` after every pull of the public repository.
- **Status and push:** `python forge.py sync` pulls and pushes both repositories and prints one line each; `--check` only reports.
- **Leak guard:** a `pre-push` hook scans outgoing commits, messages included, with `gitleaks` and with `.private/deny-list.txt`, and refuses a hit without printing the matched text. GitHub push protection is the second line.
- **Agent rules:** the public `CLAUDE.md` and `AGENTS.md` point at `.private/AGENTS.md` when it exists.
- **Tests:** `check-all` runs the overlay's suites (the former `global-*` and `plugin-*` entries) when `.private/` is present and reports them skipped otherwise. Public CI never sees the overlay, adds a full-history `gitleaks` job, and proves a stranger's clone passes.

## Reversal cost

Moving `global/` and `plugins/` back is a copy and a commit. Deleting `.private/` and the hooks returns a plain public checkout. Anything already public stays public.
