# Desktop Tests Kit

Splits Windows desktop UI tests into two kinds: a default UI Automation kind that runs locally and in CI without touching the operator's pointer, keyboard, or foreground window, and an opt-in real-input kind that runs only through `scripts/smoke-input.ps1` (on demand or nightly between 03:00 and 06:00 on an unlocked desktop idle 15 minutes) and stops the moment a person touches the desk.

## Host prerequisites

- Windows 10 or Windows 11 with PowerShell 7 (`pwsh`) and Python 3 on `PATH`.
- .NET Framework 4.x C# compiler (`%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe`) and `UIAutomationClient.dll` (present by default on Windows and GitHub Actions `windows-latest` runners).

## Configuration

Every project setting lives in `.conclave/desktop-tests.json` (validated by `python scripts/lib/desktop_tests.py show`, exit 2 on invalid values):

- `prefix`: lower-case project prefix (`[a-z][a-z0-9-]{0,31}`); derives environment variable prefix `<PREFIX>_SMOKE_*`.
- `window_opens` / `window_closes`: local `HH:MM` nightly window (default `"03:00"` to `"06:00"`).
- `idle_minutes`: minimum idle minutes before a scheduled run is admitted (default `15`).
- `history_limit`: maximum records kept in `input-history.jsonl` (default `60`).
- `log_limit`: maximum per-run log files kept in the state folder (default `30`).
- `test_command`: optional default runner command list used by `scripts/smoke-input.ps1`.

## Local and CI commands

- Validate config: `python scripts/lib/desktop_tests.py show`
- Run default UI Automation tests (local and Windows CI): `python -m unittest discover -s scripts/tests -p "test_desktop_tests.py"`
- Run real-input tests on demand: `pwsh -NoProfile -File scripts/smoke-input.ps1`
- Capture a window or run a desktop capture command under the machine-wide lock: `pwsh -NoProfile -File scripts/capture-window.ps1 -WindowPid <pid> -Out <path.png>` (or `-Command <exe> [args...]`)
- Install or remove the nightly 03:00 task (updates `.conclave/automations/tasks.json` when the `automations` kit is installed, or registers directly standalone): `pwsh -NoProfile -File scripts/smoke-input.ps1 -Install` / `-Uninstall`
- Read nightly and on-demand history: `pwsh -NoProfile -File scripts/smoke-input.ps1 -Status`

## Machine-wide desktop lock

Every `scripts/smoke-input.ps1` run, `scripts/capture-window.ps1` capture, and live-desk fixture acquires one machine-wide named mutex (`Global\conclave-desktop-lock` by default, shared across repositories and Windows sessions) paired with a manual-reset lease event (`Global\conclave-desktop-lease-<lease_id>`), a named desktop Job Object (`Global\conclave-desktop-job-<lease_id>`), and a shared holder record in `%ProgramData%\Conclave\desktop-locks\<sha256(lock-name)>.json`:

- `<ENV_PREFIX>_DESKTOP_LOCK`: optional override (unqualified names canonicalize to `Global\<name>`; `Local\` and other namespaces are rejected).
- `<ENV_PREFIX>_DESKTOP_WAIT_S`: bounded wait in seconds (default `120`, valid range `0` to `86400`; invalid values fail closed).
- `<ENV_PREFIX>_DESKTOP_HELD`: inheritance token (`<pid>:<start_ticks>:<lease_id>:<lock_name>`) exported to job-member child processes so runners never deadlock their own children while unrelated processes and reused PIDs are refused.

## Files

| Path | Purpose |
| --- | --- |
| `.conclave/desktop-tests.json` | Project prefix, nightly window, idle threshold, and retention settings |
| `scripts/lib/desktop_tests.py` | Stdlib config loader and validator |
| `scripts/lib/DesktopTestGuard.cs` | Trait guard, no-activate launch helper, and continuous desk observer |
| `scripts/lib/DesktopLock.cs` | Machine-wide desktop mutex, lease event, named desktop job, and inheritance |
| `scripts/lib/InputWatch.cs` | Low-level keyboard and mouse hook watcher with per-run tag |
| `scripts/smoke-input.ps1` | Admitted real-input runner, Job Object teardown, reconciliation, and `-Status` |
| `scripts/capture-window.ps1` | Lock-guarded window capture and desktop capture command wrapper |
| `scripts/tests/test_desktop_tests.py` | Default UIA, negative desk-violation, lock, and runner tests |
