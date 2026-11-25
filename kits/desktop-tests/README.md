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
- Install or remove the nightly 03:00 task (updates `.conclave/automations/tasks.json` when the `automations` kit is installed, or registers directly standalone): `pwsh -NoProfile -File scripts/smoke-input.ps1 -Install` / `-Uninstall`
- Read nightly and on-demand history: `pwsh -NoProfile -File scripts/smoke-input.ps1 -Status`

## Files

| Path | Purpose |
| --- | --- |
| `.conclave/desktop-tests.json` | Project prefix, nightly window, idle threshold, and retention settings |
| `scripts/lib/desktop_tests.py` | Stdlib config loader and validator |
| `scripts/lib/DesktopTestGuard.cs` | Trait guard, no-activate launch helper, and continuous desk observer |
| `scripts/lib/InputWatch.cs` | Low-level keyboard and mouse hook watcher with per-run tag |
| `scripts/smoke-input.ps1` | Admitted real-input runner, Job Object teardown, reconciliation, and `-Status` |
| `scripts/tests/test_desktop_tests.py` | Default UIA fixture, negative desk-violation fixtures, and runner tests |
