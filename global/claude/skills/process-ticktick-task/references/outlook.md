# Outlook through the Microsoft 365 connector

Mailbox: derick@rizonetech.com. Mail sent to rizonetech@gmail.com also lands here. Checked against the live mailbox on 13 October 2026.

## Message ids

- Tasks store OWA links: `https://outlook.office365.com/owa/?ItemID=<EWS id, URL-encoded>&exvsurl=1&viewmodel=ReadMessageItem`. Graph wants the REST form: URL-decode, then `+` becomes `_` and `/` becomes `-`. `scripts/outlook_refs.py` does this; read the result with `read_resource` and `mail:///messages/<graphId>`.
- The connector does not use immutable ids. Moving a message to another folder gives it a new id, so an older link returns `NOT_FOUND` (seen with the SMTP2GO weekly summary, which had moved back to the Inbox). Recover by searching subject, sender and date, and confirm with the received time.
- `Outlook key AAkz...=` in older tasks is only the tail of an id. It cannot be read; search instead.
- Outlook search cannot find a message by its `internetMessageId` (tested 13 October 2026: no results). Find by subject, sender and date, then confirm with the `internetMessageId`.
- Large HTML emails overflow the tool output; Claude Code saves the result to a file. `scripts/mail_text.py <file>` prints the headers and a plain-text body.
- A message read gives `conversationId` (the thread), `internetMessageId` (stable across moves), `parentFolderId`, `webLink`, the recipients and the body.

## Search limits

- `outlook_email_search` rejects some combinations: `folderName` with a date plus `query` or `recipient`, and `order: "oldest"` with `query` or `recipient`. In the own mailbox, drop `folderName` and search every folder.
- Results are not reliably date-sorted when `query` is set; sort the dates yourself and check `nextOffset` pages.
- For "did Derick already reply": `recipient: <their address>` without `folderName`, keep hits whose sender is derick@rizonetech.com.

## Folders

Filing goes under `Inbox/Processed`. Its top level (October 2026): Atera, Customers (one subfolder per client, some with their own subfolders), Finance, Mooisig, Notifications (Automation Briefs, DMARC Reports, Facebook, GitHub, Google Alerts, Helpdesk Tickets, LinkedIn, Mail Tests, Monitoring & Backups and more), Personal, Promotions, RizonePress, Rizonesoft, SEO. `Inbox/Personal` (Home, School) and the top-level `Noise` folder also exist. The tree changes; treat this as orientation, not a lookup table.

`read_resource` on `mail:///folders/<id>` returns a folder's name, counts, `parentFolderId`, its messages and its child folders, but **at most ten children**: Customers has 31 and Processed 13, so a listing is never proof that a folder is missing. Well-known names work as ids: `mail:///folders/inbox`, `mail:///folders/msgfolderroot`.

### Choosing the folder

Go by precedent, not by name guessing:

1. Search earlier mail from the same sender address (`sender`, no `folderName`), then the same domain, then the same subject or project words.
2. Read the hits that are not in the Inbox (compare `parentFolderId` with the Inbox id from `mail:///folders/inbox`) and note their folders. The folder most of them share is the destination. Mail of one thread goes together.
3. Confirm the destination by reading the folder and walking `parentFolderId` up to the Inbox, so the report can name the full path (for example `Inbox/Processed/Customers/JMR Group`).
4. No precedent: walk the tree from `Inbox/Processed` by name, remembering the ten-child limit. Still nothing: leave the message in the Inbox and tell Derick which folder to create.

Different messages in one task can belong in different folders: a client thread goes to the client's folder, a Jetpack alert about that client's site goes where earlier Jetpack alerts went.

### Moving

`outlook_batch_modify_labels` with `messageIds` (at most five), `moveToFolderId` and `addCategories: ["TickTick"]` in the same call. The `TickTick` category (blue) was created in the mailbox on 13 October 2026; if it is ever missing, recreate it with `outlook_create_label` before filing. Categories are read-modify-written, so the ones already on a message stay. Trash and Junk destinations are refused. `outlook_modify_thread_labels` moves a whole conversation, including the copies in Sent Items, so do not use it for filing. The connector rate-limits writes: on a rate-limit error wait briefly and retry that call once; on any other error re-read the message state before deciding.

## Reply drafts

- `outlook_create_reply_draft` and `outlook_create_reply_all_draft` take the message id (read it before filing, the id changes on a move), thread the draft, quote the original and return the draft's id and `webLink`. `outlook_create_draft` starts a new message.
- HTML bodies may only use headings, paragraphs, links, lists, b, i, strong, em, strike, code, tables, br, hr, div and pre. Anything else (span, font, blockquote, images, comments) makes the call fail.
- Drafts made this way carry no Outlook signature and are stamped with the connector's `X-AI-Generated` header. Do not add a signature or sign-off name.
- Contact-form mail comes from `automailer@rizonesoft.com` or a site's `wordpress@` address. The real sender's address is in the body; draft to them.
- A reply goes out from derick@rizonetech.com. If the original reached rizonetech@gmail.com or another address, mention that in the notes.
