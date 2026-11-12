# Unattended kit

Will keep a `process-plan` run going with nobody at the keyboard: a preflight that refuses a run that cannot work, a launcher that starts the agent in a tmux session that outlives the terminal, a heartbeat that restarts a dead run and nudges an idle one, a boot unit that resumes it, and a desktop shortcut that starts it. It needs the `todo` kit (the run guard, `scripts/campaign_guard.py`) and tmux, so it runs on Linux and in WSL; on Windows the shortcut starts it through `wsl.exe`.

The kit is being built section by section (`todo/02-unattended/TODO-02-unattended-kit.md`): none of the above runs yet. Installed so far:

| File | What it is |
| ---- | ---------- |
| `.conclave/unattended.json` | The run profile: agent, model, effort, prompt, branch, thresholds, preflight checks |
| `docs/unattended-prompt.md` | The seed prompt the run starts with, naming no project |
| `scripts/unattended-run.py` | `start`, `status`, `attach [--watch]`, `stop`: the run in tmux session `<name>-run` |
| `scripts/unattended-preflight.py` | One PASS or FAIL line per precondition; exit 1 on any FAIL (Linux, WSL) |
| `scripts/lib/unattended.py` | `load_profile`; the launch lock and the claim (`build/unattended-launch.json`) |
| `scripts/tests/test_unattended.py` | The kit's own tests |

After installing, set `name`, `model` and `effort` in `.conclave/unattended.json` (the template leaves them `null` and the loader refuses it until they are set). Install it with `python forge.py kit <project> unattended` after the `todo` kit, and check the machine with `python forge.py doctor <project> unattended`. The SDK does not install this kit in itself (`SELF_KITS` in `forge.py`).
