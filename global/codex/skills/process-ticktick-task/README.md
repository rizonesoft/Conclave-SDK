# process-ticktick-task

Global Codex skill by Rizonetech for processing one verified TickTick task. Invoke with `process TickTick task <title or link>`, `process task <title>` or `$process-ticktick-task`. Uses the official TickTick plugin and the independent Outlook Graph connector. Python 3.10+ helpers use only the standard library.

The independent source is this folder; installation never reads another agent's repository. [SKILL.md](SKILL.md) owns the workflow, [Outlook mapping](references/outlook.md) owns connector differences, and [TickTick setup](references/ticktick.md) records connection/recovery. The sibling `file-to-ticktick` shares these local helpers and references.

Follows Claude's processing order: confirm, read context, do the work, draft without sending, file, write notes, close and report. Codex adaptations cover tool discovery, plain-text drafts, verified Graph previews/execution, workspace paths and the global article rules. Routine authorised work does not require another approval. Waiting tasks retain their tags and gain `waiting`; messages without a supported filing destination retain Inbox placement and receive the existing TickTick category.

From the repository root, preview with `python skills/deploy.py process-ticktick-task`, then add `--apply` to install. Use `python3` in WSL. Run tests with `python -m unittest discover -s skills/global/process-ticktick-task/scripts`.

Check Outlook Graph authentication at runtime. Its filing scope is beneath Inbox/Processed or the top-level Noise folder, with earlier-message evidence; it cannot create folders or categories. The curated Outlook plugin alone lacks the required identity/thread metadata and combined filing action. If Graph is unavailable, record those blockers and keep dependent work open. See the Outlook reference for routing and exact tool arguments.
