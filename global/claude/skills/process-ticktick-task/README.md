# process-ticktick-task

A global Claude Code skill that processes one TickTick task end to end (its partner `file-to-ticktick` creates the tasks from email, and uses this skill's Outlook reference and scripts): it reads the task and the Outlook emails it links, does the work, drafts a reply in Outlook when one is due (never sends), files the related Inbox emails into their folders with a blue `TickTick` category, writes notes on the task and closes it.

Say "process TickTick task <title or link>", "process task <title>", or run `/process-ticktick-task`. "Process task" on its own is checked against TickTick first; if no TickTick task matches, the skill stands down.

## Requirements

- The user-scope `ticktick` MCP server (registered on Windows and in WSL) and the claude.ai Microsoft 365 connector, signed in as the same Claude account in both.
- Python 3.10 or later for `scripts/outlook_refs.py` (standard library only).

## Files

| File | Purpose |
|---|---|
| `SKILL.md` | The workflow Claude follows |
| `references/outlook.md` | Message ids, search limits, folder discovery, filing and draft rules for the connector |
| `scripts/outlook_refs.py` | Turns the Outlook links and hints in a task into Graph message ids |
| `scripts/mail_text.py` | Prints a saved Outlook message (too large for the tool output) as headers and plain text |
| `scripts/test_*.py` | Tests: `python -m unittest discover -s scripts` |

## Deploy

This folder is the master copy. Deploy with `python <SDK>/global/deploy.py --agent claude` (once on Windows and once in WSL), then start a new Claude Code session. Never edit a deployed copy.

## Safety

- Replies are drafts only; nothing is sent.
- Anything with real blast radius (payments, deletions, DNS, hosting or security settings, credentials, production deploys) or that the task marks as not authorised is asked about first, or left open in an unattended run.
- Filing moves only messages sitting directly in the Inbox, never Sent Items, Drafts, Deleted Items or Junk.
- Email content is treated as data, never as instructions.
