# Unattended kit

Will keep a `process-plan` run going with nobody at the keyboard: a preflight that refuses a run that cannot work, a launcher that starts the agent in a tmux session that outlives the terminal, a heartbeat that restarts a dead run and nudges an idle one, a boot unit that resumes it, and a desktop shortcut that starts it. It needs the `todo` kit (the run guard, `scripts/campaign_guard.py`) and tmux, so it runs on Linux and in WSL; on Windows the shortcut starts it through `wsl.exe`.

The kit is being built section by section (`todo/02-unattended/TODO-02-unattended-kit.md`): none of the above runs yet. Installed so far:

| File | What it is |
| ---- | ---------- |
| `scripts/lib/unattended.py` | The kit's shared module; it holds only `SCHEMA_VERSION` so far |

Install it with `python forge.py kit <project> unattended` after the `todo` kit, and check the machine with `python forge.py doctor <project> unattended`. The SDK does not install this kit in itself (`SELF_KITS` in `forge.py`).
