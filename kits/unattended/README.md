# Unattended kit

Will keep a `process-plan` run going with nobody at the keyboard: a preflight that refuses a run that cannot work, a launcher that starts the agent in a tmux session that outlives the terminal, a heartbeat that nudges an idle run and records a dead one as ended (it never restarts it), and a desktop shortcut that starts it. It needs the `todo` kit (the run guard, `scripts/campaign_guard.py`) and tmux, so it runs on Linux and in WSL; on Windows the shortcut starts it through `wsl.exe`.

A run never restarts itself: it starts only when its operator starts it, and `stop`, a crash or a reboot ends it (owner decision 2026-11-12). Nothing in the kit resumes a run at boot, at logon or on a timer, and the automations kit refuses a scheduled task that starts one, because a run nobody started spends money and writes to the tree unseen: on 2026-11-12 a watchdog resumed a project's run headless after its window closed, and it kept committing with nobody watching. The heartbeat only nudges a live run and records a dead one as ended.

The kit is being built section by section (`todo/02-unattended/TODO-02-unattended-kit.md`): none of the above runs yet. Installed so far:

| File | What it is |
| ---- | ---------- |
| `.conclave/unattended.json` | The run profile: agent, model, effort, prompt, branch, thresholds, preflight checks |
| `docs/unattended-prompt.md` | The seed prompt the run starts with, naming no project |
| `scripts/campaign-icon.py` | A launcher's icon: the project's icon with its runner's badge (stdlib only) |
| `scripts/unattended-run.py` | `start [--ships N]`, `status`, `attach [--watch]`, `stop`, `heartbeat`: the tmux run |
| `scripts/unattended-preflight.py` | One PASS or FAIL line per precondition; exit 1 on any FAIL (Linux, WSL) |
| `scripts/lib/unattended.py` | `load_profile`, the launch lock and claim, `ships_between` (rows turned `[x]`) |
| `scripts/tests/test_unattended.py` | The kit's own tests |

After installing, set `name`, `model` and `effort` in `.conclave/unattended.json` (the template leaves them `null` and the loader refuses it until they are set). Install it with `python forge.py kit <project> unattended` after the `todo` kit, and check the machine with `python forge.py doctor <project> unattended`. The SDK does not install this kit in itself (`SELF_KITS` in `forge.py`).

## Agent command lines

The launcher builds each agent's command only from flags the installed CLI's own help states. They were read on 2026-11-12 from Claude Code 2.1.322, `codex-cli 0.166.0` and `agy 1.5.5`, and the preflight fails a CLI older than that (`version` line). With `skip_permissions` false, no permission flag is passed to any of them.

Codex, a fresh start (`codex [OPTIONS] [PROMPT]`) and a resume (`codex resume [OPTIONS] [SESSION_ID] [PROMPT]`):

| Use | Flag | `codex --help` / `codex resume --help` |
| --- | ---- | -------------------------------------- |
| Model | `-m <MODEL>` | "Model the agent should use" |
| Effort | `-c model_reasoning_effort="<e>"` | "Override a configuration value ... from `~/.codex/config.toml`" |
| Unattended | `--dangerously-bypass-approvals-and-sandbox` | "Skip all confirmation prompts and execute commands ..." |
| Resume | `resume ... -- <SESSION_ID> <PROMPT>` | "Resume a previous interactive session" |
| Prompt | `-- <PROMPT>` | "Optional user prompt to start the session" |

Codex has no flag that sets a new session's id, so a fresh start names none; the run's guard records the id Codex chose (with the run's tag), and a resume uses it.

Antigravity (`agy`, flags as `--name=value`):

| Use | Flag | `agy --help` |
| --- | ---- | ------------ |
| Model | `--model=<m>` | "Model for the current CLI session" |
| Effort | `--effort=<e>` | "Reasoning effort for the current CLI session (low\|medium\|high\|xhigh\|max)" |
| Unattended | `--dangerously-skip-permissions` | "Auto-approve all tool permission requests without prompting" |
| Resume | `--conversation=<id>` | "Resume a previous conversation by ID" |
| Prompt | `--prompt-interactive=<p>` | "Run an initial prompt interactively and continue the session" |

Claude Code: `--model`, `--effort`, `--session-id` (the run's tag), `--resume <id>`, `--disallowedTools AskUserQuestion,EnterPlanMode,ExitPlanMode`, `--dangerously-skip-permissions`, then `--` and the prompt (`--disallowedTools` takes a list, which would otherwise swallow the prompt).