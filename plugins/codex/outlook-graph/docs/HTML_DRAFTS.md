# Update an existing HTML reply draft

Added in 0.1.4, with CID baselines and diagnostics in 0.1.6. This route reuses
delegated Graph authentication. It adds no
credentials, consent, Mail.Send permission, browser-token access or COM route.
It updates an existing draft only; it cannot send or create a replacement.

## Workflow

1. Obtain exclusive mailbox ownership and respect task-specific start times and
   operation spacing. Even connection checks wait for ownership release.
2. Call `get_html_draft` with exact expected `messageId`, `mailbox`, `subject`,
   `conversationId` and `internetMessageId`. Follow every HTML chunk. Inspect the
   current authored content, native recipient fields, quote and attachments.
   `bodySha256` covers the complete HTML, not just the returned chunk.
3. Call `prepare_update_html_draft` with the same identity, returned
   `expectedChangeKey` and `expectedBodySha256`, plus plain-text `paragraphs`.
   New authored text is escaped into simple 12pt Segoe UI/Arial paragraphs;
   arbitrary authored HTML, CSS, links and executable markup are not accepted.
4. Show the full original/proposed HTML preview, exact target, recipient fields,
   effects, attachment inventory and recovery. Approve within the explicit task,
   then call `execute_html_draft_update` with the exact `changeId` and
   `confirmedTarget` on the **same running MCP server**.
5. Execution consumes the preview before awaiting preflight, rechecks the full
   snapshot and `isDraft === true`, then performs one body-only PATCH with a
   mandatory `If-Match` ETag. It reads the actual saved HTML and attachment
   inventory. A mismatch, timeout or uncertain result stops dependent work.
   Inspect the same draft before any new decision; never retry automatically or
   create/delete a replacement.
6. After verification, independently read that same draft through another
   already-authorized connector when available. Confirm HTML type, full wording,
   paragraph boundaries, recipients, quote, categories, read state and inventory.

The editable region precedes one native `divRplyFwdMsg` quote. Replacing it
removes any automatic authored signature and adds no closing or sign-off. The
entire old authored region is included in the preview: preserve existing user
work outside the explicit task. Only a direct quote or an unambiguous chain of
single `div` wrappers is supported. Ambiguous boundaries fail closed.

The HTML parser supplies source offsets; it does not execute or fetch content.
The proposed body retains the original outer document and quoted HTML verbatim,
including quoted signatures, links and CID references. Existing quoted HTML is
not sanitized or serialized again. Structural/size limits bound parsing.

Readback checks authored wording, semantic quote structure, links/images/CIDs
and preserved message fields. Microsoft may normalize formatting. Exact HTML
equality is reported separately in `verification.exactHtml`; success does not
certify exact CSS. Attachment verification compares complete, bounded metadata
inventories, including inline items; it does not download/certify original
bytes. No attachment write/deletion route is added. A body-only Graph save was
observed to reduce the inline inventory even though the plugin made no attachment
deletion call. The inventory-preservation guard remains strict and reports any
such reduction as unverified. Inspect the retained baseline and every quoted CID
reference; do not assume missing entries were unreferenced or harmless. A baseline
without content IDs cannot conclusively classify each removed attachment.

## Attachment baselines and diagnostics

Version 0.1.7 uses `$select=microsoft.graph.fileAttachment/contentId` alongside
the base attachment fields. The qualified property path handles the derived
schema without filtering the collection down to file attachments: item/reference
metadata, raw `@odata.type` (returned as `attachmentType`) and all continuation
pages remain covered. The unqualified base `contentId` selector was rejected by
Graph with HTTP 400. Errors are surfaced; there is no unprojected/byte-download
fallback and no automatic HTTP 400 retry.

The bounded attachment projection includes the raw `contentId` and
`contentIdKnown`; an omitted field is unknown, distinct from an explicit null.
No attachment bytes are requested or returned. The pre-update baseline and
proposed classification are included in the preview and retained in its private
snapshot. The exact raw metadata, including content IDs, is rechecked before
PATCH and compared after it.

`attachmentReferences` classifies each asset as referenced, unreferenced,
non-inline, unknown/invalid content ID or ambiguous duplicate content ID. Roles
are authored, quoted or preserved document markup (such as head CSS and wrapper
attributes). Coverage inspects CID URLs in HTML URL attributes, srcset and CSS
`url()` tokens; it is not a rendered-image or attachment-byte certification.
URL escapes and angle brackets are normalized only for matching; raw content
IDs remain in strict comparison. Case is preserved. Quoted or document CID URLs
must uniquely resolve to inline attachment metadata before a preview can proceed.

Readback reports separate content, message-field, inventory and protected-CID
checks. Attachment diagnostics retain the baseline, proposed and observed
classifications plus added, removed and metadata-changed entries. Every inventory
mismatch remains `partial-or-uncertain` with `retry:false`, even if all surviving
quoted references resolve or a removed entry was only in the authored signature
or unreferenced. These roles are evidence for a human decision, never permission
to delete, restore, clean up, retry or weaken the guard. Unknown IDs cannot prove
that missing entries were harmless. If a write or readback fails before an
observed inventory is obtained, diagnostics retain the baseline/proposal and the
same draft must be inspected before another decision.

## Pacing and timeouts

For a task requiring at least 24.5 seconds between Outlook operations, set
`OUTLOOK_GRAPH_MIN_REQUEST_INTERVAL_MS=25000` on its dedicated MCP process.
This non-secret, process-local option accepts 0–60000 ms (default 0). It paces
every Graph request start, including concurrent calls and read retry attempts.
The caller still owns spacing/exclusivity across processes and must wait the
required interval after the previous owner's last operation before starting.

Read/preview performs profile, HTML and bounded attachment reads. Execution
repeats preflight, conditionally updates, then reads actual HTML and attachments.
At 25-second spacing this exceeds an ordinary SDK timeout. Configure a caller
timeout of at least 300000 ms, longer for multi-page inventories; keep the same
server alive between preview/execute and issue progress while awaiting results.
Ten-minute preview expiry is rechecked after preflight.

## Supported authentication and installation

Use `node dist/setup.mjs status` under the Windows account owning the DPAPI
store. It reports presence without decryption or Graph access. A managed sandbox
can block its hidden Windows helper; authorized execution under the owning
account is supported. Do not copy ciphertext, extract tokens, change ACLs or
account settings, bypass DPAPI, or add registration/consent to make checks pass.
Presence is separate from live authentication/consent verification.

Build/test the owning source and refresh the private local plugin through the
installed Codex host's supported commands. Verify credential-free initialization
and all 14 tool schemas. Source changes alone do not update a version cache;
never edit that cache directly. A harmless live check is a separate authorized
step after mailbox ownership release.
