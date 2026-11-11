import { createHash, randomUUID } from "node:crypto";
import { GraphError, identity, key, messageView } from "./client.js";
import { z } from "zod";
const id = z
  .string()
  .min(1)
  .max(2048)
  .regex(/^[^\x00-\x20]+$/);
const email = z.string().email().max(254);
const recipients = z.array(email).min(1).max(30);
export const changeSchemas = {
  tag_message: z.object({ messageId: id }).strict(),
  file_message: z
    .object({ messageId: id, destinationId: id, evidenceMessageId: id })
    .strict(),
  create_draft: z
    .object({
      mode: z.enum(["new", "reply", "reply_all"]),
      messageId: id.optional(),
      subject: z
        .string()
        .min(1)
        .max(998)
        .regex(/^[^\r\n]+$/)
        .optional(),
      to: recipients,
      cc: z.array(email).max(30).default([]),
      body: z.string().min(1).max(100000),
    })
    .strict(),
};
const digest = (v) =>
  createHash("sha256").update(JSON.stringify(v)).digest("hex");
const address = (m) => (m.from?.emailAddress?.address || "").toLowerCase();
const emails = (rs) =>
  (rs || []).map((r) => r.emailAddress.address.toLowerCase()).sort();
const same = (a, b) =>
  JSON.stringify([...a].sort()) === JSON.stringify([...b].sort());
const recipientObjects = (rs) =>
  rs.map((address) => ({ emailAddress: { address } }));

export class Changes {
  constructor(client, { now = Date.now } = {}) {
    this.client = client;
    this.now = now;
    this.pending = new Map();
  }
  async snapshot(operation, p) {
    const account = await this.client.me();
    if (typeof account?.id !== "string" || !account.id) {
      throw new GraphError(
        "Mailbox account identity is incomplete. No preview created.",
      );
    }
    const source = p.messageId ? await this.client.message(p.messageId) : null;
    if (source) identity(source);
    if (operation === "create_draft") {
      if (
        (p.mode === "new" && (!p.subject || p.messageId)) ||
        (p.mode !== "new" && (!source || p.subject))
      )
        throw new GraphError(
          "New drafts need a subject and no message ID; replies need a source message and no subject override.",
        );
      if (source?.isDraft) throw new GraphError("Cannot reply to a draft.");
      if (
        source &&
        ["notifications@github.com", "noreply@github.com"].includes(
          address(source),
        )
      )
        throw new GraphError(
          "GitHub notification mail gets a proposed comment in task notes, not a mail draft.",
        );
      return { account, source: source ? identity(source) : null };
    }
    const inbox = await this.client.folder("inbox");
    if (source.isDraft || source.parentFolderId !== inbox.id)
      throw new GraphError(
        "Only messages directly in Inbox may be tagged or filed.",
      );
    let categoryFound = false,
      cursor;
    for (let page = 0; page < 5; page++) {
      const cats = await this.client.categories({ cursor });
      if (cats.items.some((c) => c.displayName === "TickTick")) {
        categoryFound = true;
        break;
      }
      cursor = cats.nextCursor;
      if (!cursor) break;
    }
    if (!categoryFound)
      throw new GraphError(
        "Existing TickTick category not found within five pages; no category will be created.",
      );
    const result = { account, source: identity(source), inboxId: inbox.id };
    if (operation === "file_message") {
      const destination = await this.client.folder(p.destinationId);
      const evidence = await this.client.message(p.evidenceMessageId);
      identity(evidence);
      if (
        evidence.id === source.id ||
        evidence.parentFolderId !== destination.id ||
        evidence.isDraft ||
        Date.parse(evidence.receivedDateTime) >=
          Date.parse(source.receivedDateTime) ||
        !(
          address(source) === address(evidence) ||
          source.conversationId === evidence.conversationId
        )
      )
        throw new GraphError(
          "Destination must contain earlier mail from the same sender or conversation.",
        );
      const folderPath = await this.client.folderPath(destination.id);
      if (folderPath !== "Noise" && !folderPath.startsWith("Inbox/Processed/"))
        throw new GraphError(
          "Filing destination must be below Inbox/Processed or the top-level Noise folder.",
        );
      Object.assign(result, {
        destination,
        evidence: identity(evidence),
        folderPath,
      });
    }
    return result;
  }
  async prepare(operation, parameters) {
    const schema = changeSchemas[operation];
    if (!schema) throw new GraphError("Unsupported change.");
    const parsed = schema.safeParse(parameters);
    if (!parsed.success) throw new GraphError("Invalid change parameters.");
    const p = parsed.data;
    for (const [id, x] of this.pending)
      if (x.expiresAt <= this.now()) this.pending.delete(id);
    if (this.pending.size >= 50)
      throw new GraphError("Too many pending previews.");
    const before = await this.snapshot(operation, p),
      target = before.account.id + ":" + (p.messageId || "drafts");
    const changeId = randomUUID(),
      expiresAt = this.now() + 600000;
    this.pending.set(changeId, {
      operation,
      parameters: structuredClone(p),
      before: structuredClone(before),
      beforeHash: digest(before),
      target,
      expiresAt,
    });
    return {
      changeId,
      operation,
      target,
      parameters: structuredClone(p),
      before,
      expiresAt,
      executed: false,
      approvalRequired: true,
      approvalMode: "task-scoped-agent",
      cost: "No paid operation initiated",
      impact:
        operation === "file_message"
          ? "Add existing TickTick category, then move this Inbox message. Two separate writes, not an atomic transaction."
          : operation === "tag_message"
            ? "Add existing TickTick category, preserving other categories and Inbox location."
            : "Create a draft only with the exact reviewed recipients and plain-text body. Never send.",
      recovery:
        operation === "create_draft"
          ? "If uncertain, inspect Drafts before any retry. Do not automatically delete a partial draft."
          : "If partial or uncertain, re-read by permanent identity before any further action. No automatic reversal.",
    };
  }
  async execute(changeId, confirmedTarget) {
    const preview = this.pending.get(changeId);
    if (!preview || preview.expiresAt <= this.now()) {
      this.pending.delete(changeId);
      throw new GraphError("Preview missing or expired.");
    }
    if (preview.target !== confirmedTarget)
      throw new GraphError("Confirmed target does not match preview.");
    this.pending.delete(changeId);
    const { operation, parameters: p, before } = preview;
    if (digest(await this.snapshot(operation, p)) !== preview.beforeHash)
      throw new GraphError("Mailbox state changed. Prepare a new preview.");
    if (preview.expiresAt <= this.now())
      throw new GraphError("Preview expired during preflight.");
    let stage = "not-started",
      messageId = p.messageId,
      partialDraftId = null;
    try {
      if (operation === "create_draft") {
        const route =
          p.mode === "new"
            ? "/me/messages"
            : "/me/messages/" +
              key(p.messageId) +
              (p.mode === "reply" ? "/createReply" : "/createReplyAll");
        const desired = {
          toRecipients: recipientObjects(p.to),
          ccRecipients: recipientObjects(p.cc),
          bccRecipients: [],
          body: { contentType: "Text", content: p.body },
        };
        stage = "draft-create-requested";
        const draft = await this.client.request("POST", route, {
          body: p.mode === "new" ? { ...desired, subject: p.subject } : {},
        });
        if (!draft?.id)
          throw new GraphError("Draft response omitted its identifier.");
        partialDraftId = draft.id;
        if (p.mode !== "new") {
          const current = await this.client.message(draft.id);
          if (current.isDraft !== true)
            throw new GraphError("Created message is not a draft.");
          stage = "draft-body-update-requested";
          await this.client.request("PATCH", "/me/messages/" + key(draft.id), {
            body: desired,
            headers: current["@odata.etag"]
              ? { "If-Match": current["@odata.etag"] }
              : {},
          });
        }
        const actual = await this.client.message(draft.id);
        if (
          actual.isDraft !== true ||
          !same(
            emails(actual.toRecipients),
            p.to.map((s) => s.toLowerCase()),
          ) ||
          !same(
            emails(actual.ccRecipients),
            p.cc.map((s) => s.toLowerCase()),
          ) ||
          !same(emails(actual.bccRecipients), []) ||
          actual.body?.content?.replace(/\r\n/g, "\n") !==
            p.body.replace(/\r\n/g, "\n") ||
          (p.mode === "new" && actual.subject !== p.subject) ||
          !actual.webLink
        )
          throw new GraphError(
            "Draft read-back did not match body, recipients or draft state.",
          );
        return {
          status: "verified",
          operation,
          draftId: actual.id,
          webLink: actual.webLink,
          message: messageView(actual),
          sent: false,
          recipients: { to: p.to, cc: p.cc },
        };
      }
      const original = await this.client.message(messageId);
      if (
        original.changeKey !== before.source.changeKey ||
        original.parentFolderId !== before.inboxId
      )
        throw new GraphError("Source changed before category update.");
      const expected = [...new Set([...original.categories, "TickTick"])];
      if (!original.categories.includes("TickTick")) {
        stage = "category-update-requested";
        await this.client.request("PATCH", "/me/messages/" + key(messageId), {
          body: { categories: expected },
          headers: original["@odata.etag"]
            ? { "If-Match": original["@odata.etag"] }
            : {},
        });
      }
      const tagged = await this.client.message(messageId);
      if (
        tagged.internetMessageId !== before.source.internetMessageId ||
        tagged.parentFolderId !== before.inboxId ||
        !same(tagged.categories, expected)
      )
        throw new GraphError("Category read-back failed.");
      stage = "category-verified";
      if (operation === "tag_message")
        return { status: "verified", operation, message: identity(tagged) };
      stage = "move-requested";
      const moved = await this.client.request(
        "POST",
        "/me/messages/" + key(messageId) + "/move",
        { body: { destinationId: p.destinationId } },
      );
      if (!moved?.id)
        throw new GraphError("Move response omitted its new identifier.");
      messageId = moved.id;
      const actual = await this.client.message(messageId);
      if (
        actual.internetMessageId !== before.source.internetMessageId ||
        actual.parentFolderId !== p.destinationId ||
        !same(actual.categories, expected)
      )
        throw new GraphError("Move read-back failed.");
      return {
        status: "verified",
        operation,
        message: identity(actual),
        folderPath: before.folderPath,
        atomic: false,
      };
    } catch (e) {
      return {
        status:
          stage === "not-started" ? "not-executed" : "partial-or-uncertain",
        operation,
        stage,
        messageId: messageId ?? null,
        draftId: partialDraftId,
        source: before.source,
        folderPath: before.folderPath ?? null,
        verified: false,
        retry: false,
        error:
          e instanceof GraphError
            ? e.message
            : "Operation could not be verified.",
        instruction:
          "Stop dependent actions. Inspect current mailbox state by permanent identity and draft/source metadata. Never reuse this preview.",
      };
    }
  }
}
