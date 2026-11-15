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

> **Started:** 2026-11-15T18:18:40Z

Agents reach the queue rule through the global rules but have nowhere to read the details: what counts as heavy, what the exit codes mean, how to read `bosun status`. One short page in this checkout gives that, written from Bosun's own README so the two do not drift silently.

**Phase:** 7
**Needs:** none
**Surface:** no

**Build order:**

1. Write the page from Bosun's README. Done when: every fact on it is in Bosun's `README.md` at the cited commit, or in the facts copied into Inputs.
2. Link it. Done when: the checkpoint passes.

- [x] Write `docs/bosun.md` with question-shaped headings: what Bosun is (a separate tool beside Conclave, never required); which commands to wrap (full builds and full test suites) and never wrap (quick commands, dev servers, watchers); `bosun run -- <command>`, `bosun status`, `bosun report --days 7`; how the queue decides (2 slots shared by Windows and WSL, the memory the second slot needs, the 15-minute wait); exit 74 as the write budget stopping the job, with its two limits: in WSL the budget is off until `sudo ~/.local/share/bosun/enable-write-budget.sh` and `wsl --shutdown` turn it on, and it counts writes to the Linux disk only, never writes through a Windows drive such as `/mnt/c` or `/mnt/d`; how a limit is changed, checked and put back (`bosun config set`, `bosun config get`, `bosun config unset <key>`, and that a flag wins over a variable, a variable over the saved file, the file over the default); where the logs are; the fallback of running the command normally when `bosun` is not on PATH. Done when: each statement matches Bosun's `README.md` at the commit named in the page's last line, the page states no threshold the README does not, and the test below finds every one of those topics.
- [x] Add `docs/bosun.md` to the table in `global/README.md` as the reference behind the section 11 queue bullets, with a link written relative to that file (`../docs/bosun.md`). Done when: the test below resolves the link from `global/README.md` to the page.
- [x] Add `BosunPageTests` to `tests/test_forge.py`: it finds on the page each topic of the first item (the commands, what not to wrap, the queue's slots, memory and wait, exit 74, the WSL budget's switch and its Linux-disk limit, `config set`, `config get`, `config unset` and the precedence, the logs' folder, the fallback, and the Bosun commit on the last line, a full 40-hex SHA), every figure on it among the README's (2 slots, 6 GB, 3 GB, 15 minutes, 100 GB, 74, 30 seconds, 14 days), and the link in `global/README.md` resolving to the page. Done when: it passes, and fails when any one topic is removed from the page or the link points elsewhere.
- [ ] Commit: `docs: Bosun reference page for the global queue rule`

**Corrected 2026-11-15 (validation):** Bosun's checkout (`D:\Bosun`) is now at `99fd0410083f083164dc332e22bc6067805db5c3`, not `1f36ed2`; its README there still states every fact copied into Inputs, word for word, and adds `bosun config set` for the limits (slots, the memory the second slot needs on Windows and in the VM, the wait before a job starts anyway) and the WSL step that turns the write budget on (`sudo ~/.local/share/bosun/enable-write-budget.sh`, then `wsl --shutdown`; until then the budget is off in WSL). The page is written from the README at `99fd041` and names it, and says how the limits are changed and when the budget is off rather than leaving them out. The checkpoint's Windows `Select-String` is run as a Python check, so it runs on both systems.

**Corrected 2026-11-15 (plan review):** three gaps, all taken. (1) The page must say that the WSL write budget counts writes to the Linux disk only, never through a Windows drive (`/mnt/c`, and `/mnt/d` where this checkout is). (2) Changing a limit without saying how to check it and put it back leaves a reader unable to see a variable overriding a saved value: `config get`, `config unset` and the order of precedence are on the page. (3) A check for four strings passes on a stub and a broken link: a test (`BosunPageTests` in `tests/test_forge.py`) holds each topic and resolves the link from `global/README.md`.

**Test checkpoint:** `python -m unittest tests.test_forge -k BosunPage` ends `OK`; removing the WSL budget's Linux-disk limit from the page makes it fail.

## 2. Queue rule parity test

> **Started:** 2026-11-15T18:36:28Z

The Codex rules lacked the queue bullets until 2026-11-12 while the Claude Code rules had them. A test keeps the shared bullets identical so a change to one file without the other fails.

**Phase:** 7
**Needs:** none
**Surface:** no

**Build order:**

1. Add the test. Done when: it passes on the current files and fails when one bullet is edited.

- [x] Add `test_queue_rules_match` to `global/tests/test_deploy.py`: read section 11 of `global/claude/rules/claude-code.md` and `global/codex/rules/codex.md`, extract the bullets starting `- **Heavy jobs queue.**` and `- **A child process never outlives its test.**`, and assert each is present once in both and byte-identical. Done when: `python -m unittest global.tests.test_deploy` passes.
- [x] Prove the test can fail by deleting the Codex "Heavy jobs queue" bullet in a scratch copy of the file the test reads. Done when: the test fails naming the missing bullet, and the file is restored byte for byte.
- [ ] Commit: `global: test that the Claude Code and Codex queue rules match`

**Corrected 2026-11-15 (build):** measured while building: both bullets are present once in section 11 of each file and byte for byte the same, so the test passes on the files as they are. `python -m unittest global.tests.test_deploy -k queue_rules` runs the two tests on Windows and in WSL (`global/tests` is read as a namespace package), and the whole folder is the `global-tests` suite of `check-all`. The failing case is proved twice: inside the test, on copies of the Codex file's text held in memory (a bullet missing, a bullet changed, a bullet repeated, section 11 renamed), each fault named; and once on the real file, each change restored byte for byte.

**Test checkpoint:** `python -m unittest global.tests.test_deploy -k queue_rules` passes; removing either bullet from `global/codex/rules/codex.md` makes it fail.

## Verification

- `docs/bosun.md` exists, is linked from `global/README.md`, and cites the Bosun commit it was checked against.
- `python -m unittest global.tests.test_deploy` passes.
- `python scripts/todo-graph.py validate` and `python scripts/todo-graph.py plan --check` pass.
