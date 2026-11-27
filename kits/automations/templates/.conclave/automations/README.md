# Automations

Every scheduled job for this project lives here: the task list in `tasks.json`, the runner, the failure alert, and the installers for Windows Task Scheduler (`install.ps1`) and systemd user timers on Linux and WSL (`install.sh`). The Conclave-SDK `automations` kit installed this folder; `tasks.json` and this README are the project's own, and the runner, alert and installers are refreshed from the kit.

## What runs

| Task | When (local time) | Runs | Fails when |
| --- | --- | --- | --- |

`tasks.json` starts with `"folder": null` and no tasks. Set `folder` to the project's Task Scheduler folder (for example `"\\Demo\\"`) before adding the first task: every task name then starts with that folder's name in lower case and a hyphen (`demo-`), so two projects never share a folder or a unit name.

A weekly task starts when available: a run missed while this PC was off fires at the next chance (Task Scheduler's start-when-available, systemd's `Persistent=true`), with a five-minute random delay. A logon task fires its delay after logon and then on its interval. A start while the task still runs is ignored, and a run is stopped five minutes past its timeout. On Windows, tasks run only while the operator is logged on, so no password is stored.

## When a run fails

The scheduler starts `.conclave/automations/run.py <name>` (`pythonw.exe` on Windows, so no console opens). The runner writes the run's output to `build/automations/<name>/<UTC>.log` (the newest 20 kept) and its outcome to `build/automations/<name>/last.json`. On a non-zero exit or a timeout it calls `alert.py`, which emails the operator the task, its exit, the tail of that run's log, and how to run it again.

- It sends through SMTP2GO as "`<Folder>` automations", from `alert.sender` to `alert.to` in `.conclave/local.toml` or `.private/local.toml` (both ignored by git; copy `.conclave/local.example.toml` to `.conclave/local.toml` to override on one machine). The alert refuses to send while a setting is missing.
- The key is read at send time from the vault item `alert.key_item` names, through the vault tool `vault.cli` names (`conclave-op` by default, in WSL when the run is on Windows). Nothing is stored here, and there is no `.env`.
- SMTP2GO answers a refused send with HTTP 200 and `succeeded: 0`; the alert treats that as a failure.
- The runner exits with the command's code (124 on a timeout, 126 when it cannot start), or 3 when the alert could not be sent, with the reason appended to the run's log, so Task Scheduler's Last Run Result and `systemctl --user status` show every failure.

## Install and inspect

Windows:

```powershell
pwsh .conclave/automations/install.ps1              # idempotent; re-run after editing tasks.json
pwsh .conclave/automations/install.ps1 -Uninstall   # remove every task in the project's folder
Get-ScheduledTask -TaskPath '\<Folder>\' | Get-ScheduledTaskInfo | Format-Table TaskName, NextRunTime, LastTaskResult
Start-ScheduledTask -TaskPath '\<Folder>\' -TaskName <name>   # run one now
python .conclave/automations/run.py <name>                    # or run it in this console
python .conclave/automations/alert.py <name> --dry-run        # preview the alert for its last run
```

Linux and WSL:

```bash
bash .conclave/automations/install.sh               # idempotent; re-run after editing tasks.json
bash .conclave/automations/install.sh --uninstall   # remove this repository's units
systemctl --user list-timers '<folder>-*'
systemctl --user start <name>.service               # run one now
python3 .conclave/automations/alert.py <name> --dry-run
```

Tests: `python scripts/tests/test_automations.py`. The installers read `tasks.json` and register every task it lists; a task this project registered that the file no longer lists is removed.

## Adding an automation

1. Add an entry to `tasks.json`: a `<folder>-` name, a one-line description, the command (`python` and a script in this repository), a trigger (`{"weekly": "<Day>", "at": "HH:MM"}` or `{"at_logon_delay_minutes": N, "every_minutes": N}`), and `timeout_minutes`.
2. Add its row to the table above; `scripts/tests/test_automations.py` fails until the table and the file agree.
3. Run the tests, then the installer.

## Example: merging dependency pull requests

The `todo` kit ships `scripts/merge_prs.py`, which merges green dependency pull requests one at a time when it is safe: the working tree is clean, `HEAD` is `origin/main`, no TODO section is in progress, and (with `--scheduled`) no campaign run guard (`build/claude-campaign-guard.json`) is held. It holds the campaign guard's lock for its whole window, so no campaign starts mid-merge. Its policy (required checks, labels, extra producers such as a pins workflow, excluded branches) is the optional `merge` object in `.conclave/ci.json`; without it only Dependabot pull requests that change nothing outside `.github/` qualify, and a pull request with no checks never merges. `python scripts/merge_prs.py --dry-run` says why each one is waiting.

To schedule it, add this entry to `tasks.json` (with your own folder prefix) and its row to the table above:

```json
{
  "name": "<folder>-pr-merge",
  "description": "Merge green dependency pull requests while no campaign runs; email when a merge fails",
  "command": ["python", "scripts/merge_prs.py", "--scheduled"],
  "trigger": {"at_logon_delay_minutes": 15, "every_minutes": 360},
  "timeout_minutes": 20
}
```

The task fails, and emails, only when a merge fails (the pull request stays open) or the `git pull --ff-only` or `todo-graph.py validate` after one fails (that pull request is merged; the rest wait). Either leaves `build/merge-prs-stopped.json`, and every later run refuses until you have checked `main` and deleted it.
