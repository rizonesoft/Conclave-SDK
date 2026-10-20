# Automations kit

Date: 2026-10-20. Owner request the same day: align the SDK with Isotone's automation system and turn it into a kit.

## Goal

Every project that wants scheduled checks gets one place that lists them (`.conclave/automations/tasks.json`) and one runner that logs each run and emails the operator when one fails, the same way on Windows (Task Scheduler) and on Linux and WSL (systemd user timers). Isotone (Task Scheduler, data-driven `tasks.json`) and Rizonetech (hand-written systemd units with `OnFailure=`) each built their own; the kit is Isotone's design with the platform and project names taken out.

## Decisions

| Decision | Choice | Why |
| --- | --- | --- |
| Source | Isotone's `.conclave/automations/` | Newest, data-driven, already tested |
| Schema | Isotone's `tasks.json` schema 1, unchanged | Isotone's file loads as is |
| Project name | Read from `folder`; names must start `<folder>-` | No templating in `forge.py` |
| Fresh kit | `folder: null`, no tasks; installers refuse until set | As the WordPress pin's nulls |
| Linux and WSL | `install.sh` renders units from `tasks.json` | One list for both schedulers |
| Failure report | `run.py` on both platforms, no `OnFailure=` | One code path, one email format |
| Unit ownership | Only units marked with this repo's `tasks.json` | Never touches another unit |
| Ownership | Runner, alert, installers are kit scripts | `sync --include-scripts` refreshes them |
| Email | Rizonetech SMTP2GO sender and vault item, as Isotone | The one verified sender |

## The SDK's own copy

The SDK installs the kit like `base`, `todo` and `reviewer`. Its folder is `\Conclave-SDK\`, and its one task, `conclave-sdk-reviewers`, runs `forge.py doctor . reviewer --strict` on Monday at 07:00, so a pinned reviewer CLI that disappears or a pin that stops loading is reported before a review round needs it. It is the SDK's counterpart of Isotone's `isotone-delegate-probe`.

## Not in the kit

Isotone's own checks (`check-vulnerable-packages.py`, `check-sdk-ga.py`, the delegate probe) stay in Isotone: they read .NET and Isotone's panel. Isotone keeps its copy and never runs `forge.py sync` (its `AGENTS.md` says why); it can take the kit's files when it chooses, because its `tasks.json` already loads under the kit's runner.

## Reversal cost

Low: the kit is additive, and `install.ps1 -Uninstall` or `install.sh --uninstall` removes every scheduled task it registered.
