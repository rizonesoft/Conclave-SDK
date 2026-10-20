# Automations kit

Additive overlay that gives a project scheduled jobs that report their own failures: one task list, one runner that logs every run and emails the operator when one fails, installers for Windows Task Scheduler and for systemd user timers on Linux and WSL, and a skill for Gemini (`.agents/`), Claude (`.claude/`) and Codex (`.codex/`). Generalized from Isotone's `.conclave/automations/` (2026-10-19), which was itself adapted from the Rizonetech systemd automations; Isotone's `tasks.json` loads unchanged.

## What lands

| Path | Role | `sync` |
| ---- | ---- | ---- |
| `.conclave/automations/tasks.json` | The project's task list (`folder: null` until set) | Never |
| `.conclave/automations/README.md` | What runs, when, and when it fails | Never |
| `.conclave/automations/run.py` | Runs a task, keeps its log, calls the alert on a failure | Scripts |
| `.conclave/automations/alert.py` | The failure email through SMTP2GO, key from the vault | Scripts |
| `.conclave/automations/install.ps1` | Registers every task in Task Scheduler, under the folder | Scripts |
| `.conclave/automations/install.sh` | The same as systemd user timers on Linux and WSL | Scripts |
| `scripts/tests/test_automations.py` | Manifest, runner, alert, units and installer tests | Scripts |
| `.{agents,claude,codex}/skills/scheduled-automations/` | When and how to add or fix a task | Always |

"Scripts" means `python forge.py sync <target> --include-scripts` refreshes the file; the task list and its README stay the project's.

## The task list

`folder` is the project's Task Scheduler folder (`"\\Isotone\\"`), and every task name starts with its name in lower case and a hyphen (`isotone-`), so two projects never share a folder or a unit name. A task has exactly `name`, a one-line `description`, `command` (`python` and a script in the repository), `trigger` and `timeout_minutes`.

| Trigger | Task Scheduler | systemd |
| --- | --- | --- |
| `{"weekly": "Monday", "at": "07:00"}` | Weekly, start when available, 5 min random delay | `OnCalendar`, `Persistent=true` |
| `{"at_logon_delay_minutes": 3, "every_minutes": 60}` | At logon plus the delay, then repeated | `OnStartupSec`, `OnUnitActiveSec` |

## Install

```powershell
python forge.py kit /path/to/project automations
python forge.py doctor /path/to/project automations
```

```bash
kits/automations/scripts/install.sh /path/to/project [--dry-run]
```

Then set `folder` in `tasks.json`, add the tasks, and run the project's installer (`pwsh .conclave/automations/install.ps1` or `bash .conclave/automations/install.sh`). The doctor loads the task list under the runner's own rules, reports an unset folder and any command script that does not exist, and checks the scheduler is reachable. Operator globals: Python 3 (`pythonw.exe` on Windows) and `conclave-op` in WSL for the alert's key.

## Failure email

Every failed run (non-zero exit, timeout, or a command that cannot start) emails `rizonetech@gmail.com` from `website@rizonetech.com` as "`<Folder>` automations", with the exit, the last 60 lines of the run's log, and how to run it again. The SMTP2GO key is read from the Conclave vault item "Rizonetech SMTP2GO (website mail)" at send time and never stored. An alert that cannot be sent makes the run exit 3 and is recorded at the end of its log.
