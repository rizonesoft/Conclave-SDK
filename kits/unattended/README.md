# Unattended kit

Keeps a `process-plan` run going with nobody at the keyboard: a preflight that refuses a run that cannot work, a launcher that starts the agent in a tmux session that outlives the terminal, a heartbeat that nudges an idle run, counts what it ships and records a dead one as ended (it never restarts it), and desktop shortcuts that start it. The operator's page is `docs/unattended-run.md`, installed with the kit; each agent's `unattended-run` skill points at it.

A run never restarts itself: it starts only when its operator starts it, and `stop`, a crash or a reboot ends it (owner decision 2026-11-12). Nothing in the kit resumes a run at boot, at logon or on a timer, the automations kit refuses a scheduled task that starts one, and `start` itself refuses to run under a scheduled task (`CONCLAVE_AUTOMATION`, which the automations kit sets for every process a task runs), because a run nobody started spends money and writes to the tree unseen: on 2026-11-12 a watchdog resumed a project's run headless after its window closed, and it kept committing with nobody watching. The heartbeat only nudges a live run and records a dead one as ended.

## What it needs and how to install it

It needs the `todo` kit (the run guard, `scripts/campaign_guard.py`, and the graph library the ship count reads, `scripts/lib/todo_graph.py`) and tmux, so the run lives on Linux and in WSL; on Windows the shortcuts start it through `wsl.exe`. It brings the `launchers` kit with it, whose `scripts/campaign-icon.py` draws each shortcut's icon, so installing this kit installs that one too (recorded under `launchers` in `.conclave/kits.json`). Install it after the todo kit with `python forge.py kit <project> unattended`, set `name`, `model` and `effort` in `.conclave/unattended.json` (the template leaves them `null`, and the loader refuses them until set, except Antigravity Orchestrator models `gemini-pro-orchestrator` and `gemini-pro-orchestrator-*`, which require `"effort": null`), and check the machine with `python forge.py doctor <project> unattended`. The SDK does not install this kit in itself (`SELF_KITS` in `forge.py`).

## What it installs

| File | What it is |
| ---- | ---------- |
| `.conclave/unattended.json` | The run profile: agent, model, effort, runners, prompt, thresholds, preflight checks |
| `docs/unattended-prompt.md` | The seed prompt the run starts with, naming no project |
| `docs/unattended-run.md` | The operator's page: start, watch, stop, shortcuts, the heartbeat, each message |
| `scripts/unattended-run.py` | `start`, `status`, `attach`, `stop`, `heartbeat`, `shortcut`: the run in tmux |
| `scripts/unattended-preflight.py` | A PASS or FAIL line per precondition, as it comes; exit 1 on a FAIL (Linux, WSL) |
| `scripts/unattended-shortcut.ps1` | Windows desktop shortcuts, one per runner, that start the run in WSL |
| `scripts/lib/unattended.py` | `load_profile`, `runner`, the launch lock and claim, `ships_between` |
| `scripts/tests/` | The kit's own tests |
| `.claude/skills/unattended-run/SKILL.md` | Claude Code's skill: start, stop, watch or debug a run |
| `.agents/skills/unattended-run/SKILL.md` | Antigravity's copy of the skill |
| `.codex/skills/unattended-run/SKILL.md` | Codex's copy of the skill |
| `.codex/skills/unattended-run/agents/openai.yaml` | Codex's interface entry for the skill |

## What was not lifted, and why

The kit is built from RasterFold's unattended runner and Impossible OS's overnight supervisor. Left out on purpose, each being specific to its project: Impossible OS's machinery revert (`supervisor.py:108`, which reverts commits and depends on that project's frozen-file list), its webhook alert (`notify.sh:35`), its skill-deny check and its phase guard; RasterFold's `--repair` compile database rebuild, its scout roster check and its seed prompt. Left out by the owner's decision: both projects' restart of a dead run (Impossible OS's `heartbeat.sh` restart half, RasterFold's boot resume), since a run never restarts itself.
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

Antigravity Orchestrator models (`gemini-pro-orchestrator` and `gemini-pro-orchestrator-*`) manage reasoning effort across phases internally and reject `--effort`: both top-level `agent: "agy"` profiles and `runners.agy` entries in `.conclave/unattended.json` must keep `"effort": null` for those models, and the launcher omits `--effort` on both fresh start and `--conversation` resume.

Claude Code: `--model`, `--effort`, `--session-id` (the run's tag), `--resume <id>`, `--disallowedTools AskUserQuestion,EnterPlanMode,ExitPlanMode`, `--dangerously-skip-permissions`, then `--` and the prompt (`--disallowedTools` takes a list, which would otherwise swallow the prompt).