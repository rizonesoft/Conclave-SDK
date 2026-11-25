---
schema_version: 1
id: desktop-interface-tests
domain: 04-tooling
status: active
title: "TODO-04 -- Desktop interface tests that never take the operator's desk"
---

# TODO-04 -- Desktop interface tests that never take the operator's desk

> **Goal:** Any Windows desktop project the kits serve tests its interface in two kinds: a default kind that drives the UI through UI Automation and never moves the pointer, sends a key or brings a window to the front, and an opt-in kind that sends real input only at night on an idle, unlocked desktop and stops the moment a person touches it. Every visual run and window capture holds one machine-wide desktop lock, so two repositories or sessions never fight over the screen.

> **Current state:** Measured 2026-11-18. No kit carries either shape: `git grep -n -i "SendInput\|UI Automation\|desktop lock" kits/` finds nothing. Both exist as working references in one project the owner runs (Bosun, a neighbouring checkout whose own TODO sections are its D02 T02 §11 and §12): `scripts/smoke-input.ps1`, `tests/smoke_input_test.ps1`, `tests/Bosun.TestChild/InputWatch.cs`, `tests/Bosun.Panel.E2E/SmokeInput.cs` and `ForegroundKept.cs`, `src/Bosun.Panel/Shell/LaunchShow.cs`, `scripts/lib/DesktopLock.cs`, `scripts/capture-window.ps1` and `tests/Bosun.Panel.E2E/TestAssembly.cs`. Bosun imports nothing from the SDK, so the kit carries its own version, with every name and variable per project.

> **Owner request 2026-11-18:** relayed by the Bosun run: "implement, or just add to the todo system so we do not forget". Filed here so every repository the kits serve gets the shapes.

## Inputs

- The Bosun references named in Current state, read as working references only; nothing is copied with its names.
- `forge.py`: `KIT_ORDER`, kit detection and `SUITES`, where a new kit is made known (the model is `D07 T01 §1`).
- `kits/automations/`: the scheduled-task kit (`tasks.json`, `run.py`, `install.ps1`), which owns a nightly task.
- `AGENTS.md`: standard library only for Python; machine values in `.conclave/local.toml`, never in tracked files.
- -> XREF: D07 T01 §7 -- the lock-with-holder shape (an exclusive handle the system frees, a holder named by id and start time) the desktop lock reuses

## Outcome

- A project's default interface tests run in CI and locally without touching the pointer, the keyboard or the foreground, and a test that leaves an app it started in front fails.
- Real-input tests run only when opted in, on demand or from a nightly task between 03:00 and 06:00 on an unlocked desktop idle 15 minutes, stop for a person, a lock or the deadline, and leave a bounded history whose status names skipped and missed nights.
- One named desktop lock, per machine and per project prefix, is held for every visual run and capture; a second taker waits a bounded time, then refuses naming the holder.

**Adjacency:** list=not-applicable (test runs, no records a user lists); document=not-applicable (nothing is sent, printed or filed); settings=applicable @ D04 T04 §1; reporting=applicable @ D04 T04 §1; notifications=not-applicable (a run's result is its history and status, not a message); permissions=not-applicable (no user roles: the opt-in is the operator's own variable); audit=applicable @ D04 T04 §1; exchange=not-applicable (nothing is imported or exported); reverse=applicable @ D04 T04 §2

**Adjacency rationale:** The opt-in variable, the nightly window and the idle threshold are the settings, read by the smoke runner; its bounded history and `-Status` are the reporting and audit; releasing the desktop lock (by handle close, process end or timeout) is the reverse path.

## Implementation Order

| Order | Section | Deliverable | Depends On | Status |
| ----- | ------- | ----------- | ---------- | ------ |
| 1 | §1 | Interface tests split by whether they take the desk | -- | [ ] |
| 2 | §2 | One owner of the visual desktop at a time | -- | [ ] |

## 1. Interface tests split by whether they take the desk

> **Started:** 2026-11-25T01:53Z

A default run (and CI) drives the UI without real input; real input is opt-in, nightly or on demand, and stops for a person.

**Phase:** 9
**Needs:** windows-host
**Surface:** no

**Build order:**

1. The trait and the guard on real input. Done when: a default test that sends input fails.
2. The nightly runner and its history. Done when: the checkpoint passes.

- [ ] Add a `desktop-tests` kit to `forge.py` (`KIT_ORDER`, its detection, its `kit-desktop-tests` suite in `SUITES`), carrying the shapes below with every name and variable under the project's prefix, as `D07 T01 §1` added the launchers kit. Done when: `python forge.py kit <fixture> desktop-tests` installs it and `check-all --only kit-desktop-tests` runs its suite.
- [ ] Ship a test trait and skip helper (per project prefix, Bosun's `[Trait("Input","Real")]` and `RealInputFact` as reference) that skips a real-input test unless `<PREFIX>_SMOKE_INPUT=1`, and input helpers that refuse in any test without the trait. Done when: a fixture project's default test that calls an input helper fails with the refusal.
- [ ] Add an after-each-test hook that fails a default test leaving an app it started in front, and a no-activate start (STARTF_USESHOWWINDOW with SW_SHOWNOACTIVATE, read by the app itself since WPF ignores it otherwise). Done when: a fixture app started by a default test never takes the foreground, and one that does fails the hook.
- [ ] Add a smoke runner that runs the real-input tests on demand or from a nightly task (03:00 to 06:00, interactive, never waking the machine or running late, a 3 hour limit), admitting a run only on an unlocked desktop idle 15 minutes, with the task in `kits/automations/`. Done when: a test of the admission check refuses a locked desktop, a busy one and one outside the window.
- [ ] Stop a run mid-class for a person, a lock or the deadline: a low-level-hook watcher that ignores only the runner's own tagged input (`dwExtraInfo`), since the injected flag alone also passes remote-control input. Done when: a fixture sends untagged input mid-run and finds the run stopped, and tagged input does not stop it.
- [ ] Reconcile every discovered test each run (ran once, passed, every class exited 0) and keep a bounded history with a `-Status` that names skipped and missed nights. Done when: a test with one class missing finds the run failed and `-Status` naming it, and a night with no run named as missed.
- [ ] Commit: `tooling: interface tests split by whether they take the desk`

**Test checkpoint:** `python forge.py check-all --only kit-desktop-tests` passes on Windows: the fixture project's default interface tests pass without moving the pointer or the foreground, its real-input tests skip unless opted in, and a default test that sends input fails.

## 2. One owner of the visual desktop at a time

Every visual smoke run and window capture, in any repository or session, holds one machine-wide desktop lock.

**Phase:** 9
**Needs:** windows-host
**Surface:** no

**Build order:**

1. The lock and its holder record. Done when: a second taker refuses naming the holder.
2. Inheritance for children. Done when: the checkpoint passes.

- [ ] Ship a named mutex (`Local\<prefix>-desktop`, overridable by `<PREFIX>_DESKTOP_LOCK`) held for a whole visual smoke run and for each window capture, with a holder record naming the process by id and start time, so a reused id never passes for the holder. Done when: a test holds the lock in one process and finds a second wait, then refuse naming the holder's id and start time.
- [ ] Bound the wait (`<PREFIX>_DESKTOP_WAIT_S`) and release on handle close or process end. Done when: a test kills the holder and finds the next taker gets the lock at once.
- [ ] Let children inherit the hold through `<PREFIX>_DESKTOP_HELD`, checked against an ancestor's id and start time, so a runner holding the lock across test classes never deadlocks its own children. Done when: a child of the holder takes the lock at once and an unrelated process with the variable set does not.
- [ ] Commit: `tooling: one owner of the visual desktop at a time`

**Test checkpoint:** `python forge.py check-all --only kit-desktop-tests` passes on Windows; removing the start-time check makes the reused-id test fail.

## Verification

- A fixture desktop project runs its default interface tests with the pointer and the foreground untouched, and its opt-in real-input tests skip by default.
- Two processes taking the desktop lock at once: one holds it, the other waits and then refuses naming the holder.
- `python scripts/todo-graph.py validate` and `python scripts/todo-graph.py plan --check` pass.
