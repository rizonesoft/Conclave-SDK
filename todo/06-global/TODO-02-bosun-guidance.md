---
schema_version: 1
id: bosun-guidance
domain: 06-global
status: active
title: "TODO-02 -- Bosun guidance: reference page and rule parity"
---

# TODO-02 -- Bosun guidance: reference page and rule parity

> **Goal:** An agent in any repository on the owner's machine knows when and how to route a heavy job through Bosun, from one short reference page in this checkout, and the Claude Code and Codex global rules can never again disagree about it.

> **Current state:** Measured 2026-11-12. Bosun (`D:\Bosun`, commit `1f36ed2`) is a separate Windows and WSL tool that queues heavy jobs across both sides (`bosun run`, `status`, `report`) and logs memory per repo; it is installed at `%LOCALAPPDATA%\Bosun\bin` and `~/bin/bosun` in WSL. Its own rule (`D:\Bosun\AGENTS.md`, owner decision 2026-11-10) is that no other repository depends on Bosun and Bosun writes into no other repository, so guidance lives here and always falls back to running the command normally. The "Heavy jobs queue" and "A child process never outlives its test" rules were in `global/claude/rules/claude-code.md` (section 11) only; they were added to `global/codex/rules/codex.md` (section 11) on 2026-11-12 and deployed to `~/.codex/AGENTS.md` on Windows and in WSL. Nothing in this checkout explains Bosun beyond those bullets, and no test keeps the two rule files in step. Antigravity has no global rules in `global/`, so it gets neither rule.

> **Owner decision 2026-11-12:** this file was filed on the owner's request and is a commitment of the governing plan (`docs/plans/2026-11-11-sdk-audit-and-roadmap.md`, "Bosun guidance"). A run corrects a drifted claim in place and ships both sections; it never retires the file, merges it into another, moves it to phase 99, defers it or rewrites it out of scope without the owner. Bosun's own rule that no repository depends on it is met by the fallback below, so it is not a reason to drop this work.

## Inputs

- Bosun's `README.md` at commit `1f36ed2` (the checkout is `D:\Bosun` on Windows, `/mnt/d/Bosun` from WSL): commands, queue defaults, the 100 GB write budget and exit code 74, environment variables, log location. It is the source of truth; the page here summarises it and names the commit it was checked against. When that checkout cannot be read, the facts below, copied from it on 2026-11-12, are enough to write §1:
  - Put `bosun run --` in front of heavy commands on Windows or in WSL, for example `bosun run -- npm test`; `bosun status` shows slots in use and memory available; `bosun report --days 7` summarises the memory logs.
  - Only wrapped commands queue; sessions and editors stay open. Do not wrap dev servers or watchers, because they hold a slot for as long as they run.
  - 2 slots by default, shared by Windows and WSL; the second needs 6 GB available on Windows (and 3 GB inside the VM in WSL); a job waiting 15 minutes starts anyway with a warning; a crashed job frees its slot at once.
  - A job and everything it starts may write at most 100 GB; over that it is stopped, children and all, and `bosun run` exits 74 and says why (`--max-write-gb` or `BOSUN_MAX_WRITE_GB`, 0 turns it off).
  - Logs: `%LOCALAPPDATA%\Bosun\logs`, one CSV per side per day, every 30 seconds, kept 14 days.
- `global/claude/rules/claude-code.md` and `global/codex/rules/codex.md`, section 11: the two queue bullets.
- `global/README.md`: the table of what `global/` holds.
- `global/tests/test_deploy.py`: the existing tests for `global/`.

## Outcome

- `docs/bosun.md` answers what Bosun is, which commands to wrap and which never to wrap, what exit 74 means, and what to do when `bosun` is missing, and `global/README.md` links it.
- A test fails when the queue bullets in the Claude Code and Codex global rules differ.

**Adjacency:** all=not-applicable (documentation and a text parity test, with no records a user lists, exports, is notified of or reverses)

**Adjacency rationale:** Both sections only add a page and a test inside this checkout; reversing either is deleting the file.

## Implementation Order

| Order | Section | Deliverable | Depends On | Status |
| ----- | ------- | ----------- | ---------- | ------ |
| 1 | §1 | Bosun reference page | -- | [ ] |
| 2 | §2 | Queue rule parity test | -- | [ ] |

## 1. Bosun reference page

Agents reach the queue rule through the global rules but have nowhere to read the details: what counts as heavy, what the exit codes mean, how to read `bosun status`. One short page in this checkout gives that, written from Bosun's own README so the two do not drift silently.

**Phase:** 7
**Needs:** none
**Surface:** no

**Build order:**

1. Write the page from Bosun's README. Done when: every fact on it is in Bosun's `README.md` at the cited commit, or in the facts copied into Inputs.
2. Link it. Done when: the checkpoint passes.

- [ ] Write `docs/bosun.md` with question-shaped headings: what Bosun is (a separate tool beside Conclave, never required); which commands to wrap (full builds and full test suites) and never wrap (quick commands, dev servers, watchers); `bosun run -- <command>`, `bosun status`, `bosun report --days 7`; exit 74 as the write budget stopping the job; the fallback of running the command normally when `bosun` is not on PATH. Done when: each statement matches Bosun's `README.md` at the commit named in the page's last line (or the facts copied into Inputs), and the page states no queue threshold Bosun's README does not.
- [ ] Add `docs/bosun.md` to the table in `global/README.md` as the reference behind the section 11 queue bullets. Done when: the row is there and the link resolves.
- [ ] Commit: `docs: Bosun reference page for the global queue rule`

**Test checkpoint:** `python -c "import pathlib,sys; t=pathlib.Path('docs/bosun.md').read_text(encoding='utf-8'); sys.exit(0 if all(s in t for s in ('bosun run --','bosun status','74','not installed')) else 1)"` exits 0, and `Select-String -Path global/README.md -Pattern 'docs/bosun.md'` finds the link.

## 2. Queue rule parity test

The Codex rules lacked the queue bullets until 2026-11-12 while the Claude Code rules had them. A test keeps the shared bullets identical so a change to one file without the other fails.

**Phase:** 7
**Needs:** none
**Surface:** no

**Build order:**

1. Add the test. Done when: it passes on the current files and fails when one bullet is edited.

- [ ] Add `test_queue_rules_match` to `global/tests/test_deploy.py`: read section 11 of `global/claude/rules/claude-code.md` and `global/codex/rules/codex.md`, extract the bullets starting `- **Heavy jobs queue.**` and `- **A child process never outlives its test.**`, and assert each is present once in both and byte-identical. Done when: `python -m unittest global.tests.test_deploy` passes.
- [ ] Prove the test can fail by deleting the Codex "Heavy jobs queue" bullet in a scratch copy of the file the test reads. Done when: the test fails naming the missing bullet, and the file is restored byte for byte.
- [ ] Commit: `global: test that the Claude Code and Codex queue rules match`

**Test checkpoint:** `python -m unittest global.tests.test_deploy -k queue_rules` passes; removing either bullet from `global/codex/rules/codex.md` makes it fail.

## Verification

- `docs/bosun.md` exists, is linked from `global/README.md`, and cites the Bosun commit it was checked against.
- `python -m unittest global.tests.test_deploy` passes.
- `python scripts/todo-graph.py validate` and `python scripts/todo-graph.py plan --check` pass.
