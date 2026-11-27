# Automations kit

Additive overlay that gives a project scheduled jobs that report their own failures: one task list, one runner that logs every run and emails the operator when one fails, installers for Windows Task Scheduler and for systemd user timers on Linux and WSL, and a skill for Gemini (`.agents/`), Claude (`.claude/`) and Codex (`.codex/`). Generalized from Demo's `.conclave/automations/` (2026-10-19), which was itself adapted from the Rizonetech systemd automations; Demo's `tasks.json` loads unchanged.

## What lands

All paths under `.conclave/automations/` unless they start with a dot folder or `scripts/`.

| Path | Role | Edited |
| ---- | ---- | ---- |
| `tasks.json` | The project's task list (`folder: null` until set) | Never |
| `README.md` | What runs, when, and when it fails | Never |
| `run.py` | Runs a task, keeps its log, calls the alert on a failure | Runner |
| `alert.py` | The failure email through SMTP2GO, key from the vault | Runner |
| `install.ps1` | Registers every task in Task Scheduler, under the folder | Runner |
| `install.sh` | The same as systemd user timers on Linux and WSL | Runner |
| `scripts/tests/test_automations.py` | Runner, alert, unit and installer tests | Runner |
| `.{agents,claude,codex}/skills/scheduled-automations/` | How to add or fix a task | Skill |

Every file is copied once and is the project's from then on. "Never" means the project edits it as a matter of course; "Runner" means the project changes it only to fix the runner itself, never to add a task.

## The task list

`folder` is the project's Task Scheduler folder (`"\\Demo\\"`), and every task name starts with its name in lower case and a hyphen (`demo-`), so two projects never share a folder or a unit name. A task has exactly `name`, a one-line `description`, `command` (`python` and a script in the repository), `trigger` and `timeout_minutes`.

| Trigger | Task Scheduler | systemd |
| --- | --- | --- |
| `weekly`, `at` | Weekly, start when available, 5 min delay | `OnCalendar`, `Persistent=true` |
| `every_minutes` and a logon delay | At logon, repeated | `OnStartupSec`, `OnUnitActiveSec` |

For example `{"weekly": "Monday", "at": "07:00"}` or `{"at_logon_delay_minutes": 3, "every_minutes": 60}`.

## Install

```powershell
python forge.py kit /path/to/project automations [--dry-run]
python forge.py doctor /path/to/project automations
```

Then set `folder` in `tasks.json`, add the tasks, and run the project's installer (`pwsh .conclave/automations/install.ps1` or `bash .conclave/automations/install.sh`). The doctor loads the task list under the runner's own rules, reports an unset folder and any command script that does not exist, and checks the scheduler is reachable. Operator globals: Python 3 (`pythonw.exe` on Windows) and `conclave-op` in WSL for the alert's key.

## Failure email

Every failed run (non-zero exit, timeout, or a command that cannot start) emails the operator as "`<Folder>` automations", with the exit, the last 60 lines of the run's log, and how to run it again. The sender, the recipient and the vault item that holds the SMTP2GO key are this owner's settings: `alert.sender`, `alert.to` and `alert.key_item` in `.conclave/local.toml` with `.private/local.toml` as the overlay fallback (both ignored by git; the base kit's `.conclave/local.example.toml` is its template), and the alert refuses to send while one is unset. The key is read at send time and never stored. An alert that cannot be sent makes the run exit 3 and is recorded at the end of its log.
