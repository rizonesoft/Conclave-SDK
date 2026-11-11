# file-to-ticktick

Global Codex skill by Rizonetech for turning actionable Outlook mail into one TickTick task per matter, preserving source identity and leaving emails in Inbox with the existing `TickTick` category. Invoke with `file to TickTick`, `TickTick this email`, `file my inbox to TickTick` or `$file-to-ticktick`.

Deploy `process-ticktick-task` beside it first for shared local helpers and references. From the repository root use `python skills/deploy.py file-to-ticktick` to preview and add `--apply` to install; WSL uses `python3`.

The current Outlook plugin omits required source identity and thread metadata. The skill performs read-only triage and reports that blocker instead of creating incomplete tasks or tagging messages without verification. It sends, moves and deletes nothing.

The user authorised the independent `outlook-graph@rizonetech` connector on 13 October 2026. It supplies the missing metadata and verified filing tools after its dedicated Microsoft registration and sign-in are complete. The curated-plugin limitations above remain relevant when that connection is unavailable. See the updated Outlook reference for routing and exact tool arguments.
