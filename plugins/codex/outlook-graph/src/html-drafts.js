import { randomUUID } from "node:crypto";
import { z } from "zod";
import { GraphError, key, messageView } from "./client.js";
import { htmlHash, htmlRegion, quoteFingerprint, renderParagraphs, verifyAuthored } from "./html-body.js";
import { attachmentDifferences, attachmentReferences } from "./attachment-references.js";

const id = z.string().min(1).max(2048).regex(/^[^\x00-\x20]+$/);
export const htmlDraftTarget = z.object({
  messageId: id,
  mailbox: z.string().email().max(254),
  subject: z.string().min(1).max(998).regex(/^[^\r\n]+$/),
  conversationId: id,
  internetMessageId: z.string().min(1).max(2048),
}).strict();
export const htmlDraftUpdate = htmlDraftTarget.extend({
  expectedChangeKey: id,
  expectedBodySha256: z.string().regex(/^[a-f0-9]{64}$/),
  paragraphs: z.array(z.string().min(1).max(20000)).min(1).max(100),
}).strict();
const equal = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const lower = (value) => typeof value === "string" ? value.toLowerCase() : "";
const stableKeys = ["id", "internetMessageId", "subject", "from", "sender", "receivedDateTime",
  "sentDateTime", "conversationId", "parentFolderId", "categories", "webLink", "isDraft",
  "isRead", "hasAttachments", "toRecipients", "ccRecipients", "bccRecipients", "replyTo"];
const stable = (message) => Object.fromEntries(stableKeys.map((k) => [k, message[k] ?? null]));
const snapshotHash = (state) => htmlHash(JSON.stringify(state));
const protectedReferences = (report) => report.references.filter((r) => r.roles.some((role) => role !== "authored"))
  .map(({ contentId, roles, attachmentIds, resolution }) => ({ contentId,
    roles: roles.filter((role) => role !== "authored"), attachmentIds, resolution }))
  .sort((a, b) => JSON.stringify(a).localeCompare(JSON.stringify(b)));

export class HtmlDrafts {
  constructor(client, { now = Date.now } = {}) {
    this.client = client;
    this.now = now;
    this.pending = new Map();
  }
  async state(target, account) {
    account ||= await this.client.me();
    if (!account?.id || ![account.mail, account.userPrincipalName].some((v) => lower(v) === lower(target.mailbox)))
      throw new GraphError("Signed-in mailbox does not match the explicitly expected mailbox.");
    const message = await this.client.message(target.messageId, { bodyType: "html" });
    if (message?.isDraft !== true) throw new GraphError("Only an existing unsent draft may be updated.");
    if (message.id !== target.messageId || message.subject !== target.subject ||
        message.conversationId !== target.conversationId || message.internetMessageId !== target.internetMessageId ||
        lower(message.from?.emailAddress?.address) !== lower(target.mailbox))
      throw new GraphError("Draft identity does not match the reviewed message, subject, thread and sender.");
    if (typeof message.changeKey !== "string" || !message.changeKey ||
        typeof message["@odata.etag"] !== "string" || !message["@odata.etag"] ||
        !message.webLink || !message.parentFolderId || typeof message.isRead !== "boolean" ||
        !Array.isArray(message.categories) || lower(message.body?.contentType) !== "html" ||
        typeof message.body?.content !== "string" || message.body.content.length > 1000000)
      throw new GraphError("Complete HTML draft metadata and a conditional-write ETag are required.");
    for (const field of ["toRecipients", "ccRecipients", "bccRecipients"])
      if (!Array.isArray(message[field]) || message[field].some((r) => !r.emailAddress?.address))
        throw new GraphError("Draft recipient metadata is incomplete.");
    if (!message.toRecipients.length) throw new GraphError("The existing draft has no To recipients.");
    const attachments = await this.client.attachments(target.messageId);
    return { account: { id: account.id, mail: account.mail ?? null, userPrincipalName: account.userPrincipalName ?? null },
      message, attachments };
  }
  async read(parameters) {
    const { bodyOffset = 0, bodyLimit = 30000, ...expected } = parameters;
    const parsed = htmlDraftTarget.safeParse(expected);
    if (!parsed.success || !Number.isSafeInteger(bodyOffset) || bodyOffset < 0 ||
        !Number.isSafeInteger(bodyLimit) || bodyLimit < 1000 || bodyLimit > 50000)
      throw new GraphError("Invalid HTML draft read parameters.");
    const current = await this.state(parsed.data), html = current.message.body.content;
    let editRegion;
    try {
      const region = htmlRegion(html);
      editRegion = { supported: true, authoredHtml: region.authoredHtml,
        quoteSha256: quoteFingerprint(region), attachmentReferences: attachmentReferences(region, current.attachments) };
    } catch (e) {
      editRegion = { supported: false, reason: e instanceof GraphError ? e.message : "HTML boundaries unavailable." };
    }
    return { message: messageView(current.message), changeKey: current.message.changeKey,
      body: { contentType: "html", content: html.slice(bodyOffset, bodyOffset + bodyLimit) },
      bodySha256: htmlHash(html), bodyOffset, bodyLength: html.length,
      nextBodyOffset: bodyOffset + bodyLimit < html.length ? bodyOffset + bodyLimit : null,
      attachments: current.attachments, attachmentVerification: "metadata-only", editRegion,
      minimumRequestIntervalMs: this.client.minimumRequestIntervalMs ?? 0 };
  }
  async prepare(parameters) {
    const parsed = htmlDraftUpdate.safeParse(parameters);
    if (!parsed.success) throw new GraphError("Invalid HTML draft update parameters.");
    const p = parsed.data, authoredHtml = renderParagraphs(p.paragraphs);
    for (const [id, item] of this.pending) if (item.expiresAt <= this.now()) this.pending.delete(id);
    if (this.pending.size >= 20) throw new GraphError("Too many pending HTML draft previews.");
    const before = await this.state(p);
    if (before.message.changeKey !== p.expectedChangeKey || htmlHash(before.message.body.content) !== p.expectedBodySha256)
      throw new GraphError("Draft changed since the reviewed read. Preserve it and read it again.");
    const region = htmlRegion(before.message.body.content), afterHtml = region.replace(authoredHtml);
    const afterRegion = htmlRegion(afterHtml);
    if (!verifyAuthored(afterRegion, p.paragraphs)) throw new GraphError("Generated HTML did not pass authored-content validation.");
    const baselineReferences = attachmentReferences(region, before.attachments);
    const proposedReferences = attachmentReferences(afterRegion, before.attachments);
    if (!baselineReferences.protectedReferencesComplete || !proposedReferences.protectedReferencesComplete)
      throw new GraphError("Quoted or document CID references do not uniquely resolve to inline attachment metadata. Preserve the draft and inspect its attachments.");
    const changeId = randomUUID(), expiresAt = this.now() + 600000;
    const target = before.account.id + ":" + p.messageId;
    this.pending.set(changeId, structuredClone({ p, before, beforeHash: snapshotHash(before), afterHtml,
      quoteHash: quoteFingerprint(region), baselineReferences, proposedReferences, target, expiresAt }));
    return { changeId, target, expiresAt, executed: false, approvalRequired: true,
      approvalMode: "task-scoped-agent", operation: "update_html_draft",
      mailbox: p.mailbox, message: messageView(before.message),
      beforeHtml: before.message.body.content, afterHtml, paragraphs: [...p.paragraphs],
      attachments: before.attachments, cost: "No paid operation initiated",
      attachmentReferences: { baseline: baselineReferences, proposed: proposedReferences },
      impact: "Replace only the authored section before the native quote in this existing draft. This removes any automatic authored signature. Preserve the quote, recipients, categories, read state and all attachments. Never create a replacement or send.",
      recovery: "Original HTML is included in this preview. If outcome is uncertain, inspect this same draft before any further action; no automatic retry, deletion or rollback.",
      verificationPlan: "One If-Match body-only PATCH, followed by a fresh HTML and attachment metadata read. Compare all preserved fields, authored paragraphs and quoted content/links/images. Exact CSS and attachment bytes are not certified." };
  }
  async execute(changeId, confirmedTarget) {
    const preview = this.pending.get(changeId);
    if (!preview || preview.expiresAt <= this.now()) {
      this.pending.delete(changeId);
      throw new GraphError("HTML draft preview missing or expired.");
    }
    if (preview.target !== confirmedTarget) throw new GraphError("Confirmed target does not match HTML draft preview.");
    this.pending.delete(changeId); // consume before the first await: concurrent replay cannot write
    const { p, before, afterHtml } = preview;
    const current = await this.state(p);
    if (snapshotHash(current) !== preview.beforeHash) throw new GraphError("Draft or attachment metadata changed. Prepare a fresh preview.");
    if (preview.expiresAt <= this.now()) throw new GraphError("HTML draft preview expired during validation.");
    let stage = "html-body-update-requested";
    const diagnostics = { attachmentReferences: { baseline: preview.baselineReferences, proposed: preview.proposedReferences } };
    try {
      await this.client.request("PATCH", "/me/messages/" + key(p.messageId), {
        body: { body: { contentType: "HTML", content: afterHtml } },
        headers: { "If-Match": current.message["@odata.etag"], Prefer: 'outlook.body-content-type="html"' },
      });
      stage = "html-body-readback";
      const actual = await this.state(p, current.account), region = htmlRegion(actual.message.body.content);
      const observedReferences = attachmentReferences(region, actual.attachments);
      diagnostics.attachmentReferences.observed = observedReferences;
      diagnostics.attachmentDifferences = attachmentDifferences(preview.baselineReferences, preview.proposedReferences, observedReferences);
      diagnostics.checks = { preservedMessageFields: equal(stable(actual.message), stable(before.message)),
        attachmentInventory: equal(actual.attachments, before.attachments), authoredParagraphs: verifyAuthored(region, p.paragraphs),
        quoteContentLinksAndImages: quoteFingerprint(region) === preview.quoteHash,
        protectedCidReferences: equal(protectedReferences(preview.proposedReferences), protectedReferences(observedReferences)),
        protectedCidCoverage: observedReferences.protectedReferencesComplete };
      if (Object.values(diagnostics.checks).some((ok) => !ok))
        throw new GraphError("Saved draft readback differs in authored content, quoted history, preserved metadata or attachment inventory.");
      return { status: "verified", operation: "update_html_draft", draftId: actual.message.id,
        webLink: actual.message.webLink, message: messageView(actual.message), sent: false,
        body: actual.message.body, bodySha256: htmlHash(actual.message.body.content),
        attachments: actual.attachments, diagnostics, verification: { html: true, authoredParagraphs: true,
          quoteContentLinksAndImages: true, preservedMessageFields: true, attachments: "metadata-only",
          exactHtml: actual.message.body.content === afterHtml, exactCss: false, attachmentBytes: false } };
    } catch (e) {
      return { status: "partial-or-uncertain", operation: "update_html_draft", stage,
        draftId: p.messageId, webLink: before.message.webLink, verified: false, sent: false, retry: false,
        error: e instanceof GraphError ? e.message : "HTML draft update could not be verified.", diagnostics,
        instruction: "Stop dependent actions. Re-read this same draft before any new decision. Never retry this preview or create a replacement." };
    }
  }
}
