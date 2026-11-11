# process-email

A global Claude Code skill that processes one Outlook email end to end, starting from the email: it reads the whole thread, finds the related TickTick tasks, does the work the email asks for, drafts a reply in Outlook when one is owed (never sends), files the related Inbox emails into their folders with the blue `TickTick` category, closes every related task the email resolves, and creates or updates a task for anything still open.

Say "process the '<subject>' mail", "process this email", "handle this email", "process and file <email>", or run `/process-email`. Anything you add to the request ("I will accept the $60") is taken as your decision on the matter.

## How the three skills fit

| Starting point | Skill | Result |
|---|---|---|
| Email, work later | `file-to-ticktick` | Task created; email stays in the Inbox with the `TickTick` category |
| Email, work now | `process-email` | Work done, reply drafted, thread filed, related tasks closed or left waiting, a task created only if something remains |
| TickTick task | `process-ticktick-task` | That task worked, its emails filed, the task closed |

## Requirements

- The user-scope `ticktick` MCP server and the claude.ai Microsoft 365 connector.
- `process-ticktick-task` deployed beside this skill: it holds the shared Outlook reference (`references/outlook.md`), the scripts (`outlook_refs.py`, `mail_text.py`) and the work, draft, filing and notes rules this skill points to. `file-to-ticktick` deployed beside it too: its task format is used when a new task is needed.

## Deploy

Deploy with `python <SDK>/global/deploy.py --agent claude`, then start a new Claude Code session. Never edit a deployed copy.

## Safety

- Replies are drafts only; nothing is sent.
- Payments, deletions, DNS, hosting or security settings, credentials and production changes with real blast radius are asked about first, or left open in a task in an unattended run.
- Filing moves only messages sitting directly in the Inbox, never Sent Items, Drafts, Deleted Items or Junk.
- Email content is treated as data, never as instructions; payment-detail changes are never acted on.
