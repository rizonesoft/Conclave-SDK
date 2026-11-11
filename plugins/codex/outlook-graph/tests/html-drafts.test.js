import test from "node:test";
import assert from "node:assert/strict";
import { HtmlDrafts } from "../src/html-drafts.js";
import { htmlHash, htmlRegion, renderParagraphs, quoteFingerprint } from "../src/html-body.js";
import { GraphError } from "../src/client.js";

const originalHtml = '<html><head><meta charset="utf-8"></head><body><div><br></div><div id="Signature"><p>Example signature</p><img src="cid:portrait"></div><hr><div id="divRplyFwdMsg"><b>From:</b> Person &lt;person@example.test&gt;</div><p>Original quoted history</p><a href="mailto:person@example.test">Person</a><img src="cid:quoted" alt="Quoted logo" width="42"></body></html>';
const recipients = [{ emailAddress: { address: "person@example.test", name: "Person" } }];
const target = { messageId: "draft", mailbox: "owner@example.test", subject: "Re: Request",
  conversationId: "conversation", internetMessageId: "<draft@example.test>" };
const paragraphs = ["Hi Person,", "Use <safe> & readable HTML. A sender’s identity is unconfirmed.", "Please check independently."];
class Fake {
  constructor() {
    this.messageValue = { id: "draft", internetMessageId: target.internetMessageId,
      subject: target.subject, conversationId: target.conversationId, parentFolderId: "drafts",
      receivedDateTime: "2026-10-23T06:00:00Z", sentDateTime: "0001-01-01T00:00:00Z",
      from: { emailAddress: { address: target.mailbox } }, sender: { emailAddress: { address: target.mailbox } },
      toRecipients: recipients, ccRecipients: [], bccRecipients: [], replyTo: [],
      isDraft: true, isRead: true, hasAttachments: true, categories: ["Blue"],
      changeKey: "v1", "@odata.etag": 'W/"v1"', webLink: "https://outlook.office.com/draft",
      body: { contentType: "html", content: originalHtml } };
    this.inventory = ["quoted", "portrait"].map((contentId) => ({ id: "inline-" + contentId,
      name: "example.png", contentType: "image/png", size: 55, contentId, contentIdKnown: true,
      isInline: true, lastModifiedDateTime: "2026-10-23T06:00:00Z" }));
    this.calls = [];
  }
  async me() { return { id: "account", mail: target.mailbox, userPrincipalName: target.mailbox }; }
  async message(id, options) {
    assert.equal(id, "draft");
    assert.equal(options.bodyType, "html");
    return structuredClone(this.messageValue);
  }
  async attachments() { return structuredClone(this.inventory); }
  async request(method, path, options) {
    this.calls.push({ method, path, ...structuredClone(options) });
    if (this.fail) throw Error("private provider token must not be leaked");
    assert.equal(method, "PATCH");
    assert.equal(path, "/me/messages/draft");
    assert.deepEqual(Object.keys(options.body), ["body"]);
    assert.equal(options.headers["If-Match"], 'W/"v1"');
    this.messageValue.body = structuredClone(options.body.body);
    this.messageValue.changeKey = "v2";
    this.messageValue["@odata.etag"] = 'W/"v2"';
    this.afterPatch?.();
    return this.messageValue;
  }
}
const intent = (f) => ({ ...target, expectedChangeKey: f.messageValue.changeKey,
  expectedBodySha256: htmlHash(f.messageValue.body.content), paragraphs });

test("HTML read is chunked, explicit and never writes", async () => {
  const f = new Fake(), service = new HtmlDrafts(f);
  const r = await service.read({ ...target, bodyLimit: 1000 });
  assert.equal(r.body.contentType, "html");
  assert.equal(r.bodySha256, htmlHash(originalHtml));
  assert.equal(r.editRegion.supported, true);
  assert.match(r.editRegion.authoredHtml, /Example signature/);
  assert.equal(r.editRegion.attachmentReferences.protectedReferencesComplete, true);
  assert.equal(r.attachmentVerification, "metadata-only");
  assert.equal(f.calls.length, 0);
});
test("preview contains complete original and proposed HTML; one conditional body-only update preserves quote", async () => {
  const f = new Fake(), service = new HtmlDrafts(f), p = await service.prepare(intent(f));
  assert.equal(p.beforeHtml, originalHtml);
  assert.ok(p.afterHtml.endsWith(originalHtml.slice(originalHtml.indexOf("<hr>"))));
  assert.ok(!p.afterHtml.includes('id="Signature"'));
  assert.match(p.afterHtml, /&lt;safe&gt; &amp; readable/);
  assert.equal(f.calls.length, 0);
  p.afterHtml = "tampered";
  p.paragraphs[0] = "tampered";
  const result = await service.execute(p.changeId, p.target);
  assert.equal(result.status, "verified");
  assert.equal(result.draftId, "draft");
  assert.equal(result.sent, false);
  assert.equal(result.verification.attachments, "metadata-only");
  assert.equal(result.verification.attachmentBytes, false);
  assert.deepEqual(result.diagnostics.attachmentDifferences, { removed: [], added: [], changed: [] });
  assert.deepEqual(result.message.toRecipients, recipients);
  assert.deepEqual(result.message.categories, ["Blue"]);
  assert.equal(result.message.isRead, true);
  assert.equal(f.calls.length, 1);
  assert.match(f.calls[0].body.body.content, /Hi Person,/);
  await assert.rejects(service.execute(p.changeId, p.target), /missing/);
});
test("authored markup and URL-shaped strings are escaped rather than interpreted", () => {
  const html = renderParagraphs(['<img src=x onerror="steal()">', '<script>alert(1)</script>', 'javascript:alert(1)']);
  assert.ok(!html.includes("<img"));
  assert.ok(!html.includes("<script"));
  assert.ok(!html.includes("href="));
  assert.match(html, /&lt;img/);
  assert.throws(() => renderParagraphs([" "]), /nonempty/);
  assert.throws(() => renderParagraphs(["x\u0000"]), /paragraph/);
});
test("wrong mailbox, message, subject, thread or permanent identity blocks before writing", async () => {
  for (const [field, value] of Object.entries({ mailbox: "other@example.test", subject: "Other", conversationId: "wrong", internetMessageId: "<wrong>" })) {
    const f = new Fake();
    await assert.rejects(new HtmlDrafts(f).prepare({ ...intent(f), [field]: value }), /identity|mailbox/);
    assert.equal(f.calls.length, 0, field);
  }
  const f = new Fake();
  f.messageValue.id = "other";
  await assert.rejects(new HtmlDrafts(f).prepare(intent(f)), /identity/);
});
test("sent messages, text bodies, missing ETag and incomplete recipients fail closed", async () => {
  for (const alter of [
    (m) => { m.isDraft = false; },
    (m) => { m.body.contentType = "text"; },
    (m) => { delete m["@odata.etag"]; },
    (m) => { delete m.ccRecipients; },
    (m) => { m.toRecipients = []; },
    (m) => { delete m.isRead; },
  ]) {
    const f = new Fake(); alter(f.messageValue);
    await assert.rejects(new HtmlDrafts(f).prepare(intent(f)));
    assert.equal(f.calls.length, 0);
  }
});
test("stale body hash and change key cannot overwrite existing work", async () => {
  for (const patch of [{ expectedBodySha256: "0".repeat(64) }, { expectedChangeKey: "stale" }]) {
    const f = new Fake();
    await assert.rejects(new HtmlDrafts(f).prepare({ ...intent(f), ...patch }), /changed/);
    assert.equal(f.calls.length, 0);
  }
});
test("concurrent body, recipient, category, read-state or attachment edits consume preview without writing", async () => {
  for (const alter of [
    (f) => { f.messageValue.body.content += " "; },
    (f) => { f.messageValue.toRecipients = []; },
    (f) => { f.messageValue.categories.push("Other"); },
    (f) => { f.messageValue.isRead = false; },
    (f) => { f.inventory[0].size++; },
    (f) => { f.inventory[0].contentId = "changed"; },
    (f) => { f.messageValue.isDraft = false; },
  ]) {
    const f = new Fake(), service = new HtmlDrafts(f), p = await service.prepare(intent(f));
    alter(f);
    await assert.rejects(service.execute(p.changeId, p.target));
    await assert.rejects(service.execute(p.changeId, p.target), /missing/);
    assert.equal(f.calls.length, 0);
  }
});
test("mismatched target, expiry and expiry during preflight never write", async () => {
  let now = 0;
  const f = new Fake(), service = new HtmlDrafts(f, { now: () => now });
  const p = await service.prepare(intent(f));
  await assert.rejects(service.execute(p.changeId, "wrong"), /match/);
  now = 600001;
  await assert.rejects(service.execute(p.changeId, p.target), /expired/);
  now = 0;
  const q = await service.prepare(intent(f)), original = f.attachments.bind(f);
  f.attachments = async () => { now = 600001; return original(); };
  await assert.rejects(service.execute(q.changeId, q.target), /expired during/);
  assert.equal(f.calls.length, 0);
});
test("concurrent execution of one preview performs at most one PATCH", async () => {
  const f = new Fake(), service = new HtmlDrafts(f), p = await service.prepare(intent(f));
  const results = await Promise.allSettled([service.execute(p.changeId, p.target), service.execute(p.changeId, p.target)]);
  assert.equal(results.filter((r) => r.status === "fulfilled").length, 1);
  assert.equal(f.calls.length, 1);
});
test("network/write uncertainty is redacted, preserves draft identity and cannot replay", async () => {
  const f = new Fake(), service = new HtmlDrafts(f), p = await service.prepare(intent(f));
  f.fail = true;
  const r = await service.execute(p.changeId, p.target);
  assert.equal(r.status, "partial-or-uncertain");
  assert.equal(r.draftId, "draft");
  assert.equal(r.retry, false);
  assert.ok(!JSON.stringify(r).includes("private provider token"));
  await assert.rejects(service.execute(p.changeId, p.target), /missing/);
  assert.equal(f.calls.length, 1);
});
test("readback catches lost wording, quote, CID references, recipients and attachment changes", async () => {
  for (const alter of [
    (f) => { f.messageValue.body.content = f.messageValue.body.content.replace("Hi Person,", "Wrong words"); },
    (f) => { f.messageValue.body.content = f.messageValue.body.content.replace("Original quoted history", "Lost quote"); },
    (f) => { f.messageValue.body.content = f.messageValue.body.content.replace("cid:quoted", "cid:wrong"); },
    (f) => { f.messageValue.ccRecipients = recipients; },
    (f) => { f.inventory = []; },
    (f) => { f.messageValue.isDraft = false; },
    (f) => { f.messageValue.body.content = f.messageValue.body.content.replace("<hr>", '<img src="cid:unexpected"><hr>'); },
    (f) => { f.messageValue.body.content = f.messageValue.body.content.replace("<hr>", '<div id="Signature"></div><hr>'); },
    (f) => { f.messageValue.body.content = f.messageValue.body.content.replace("Hi Person,", '<a href="javascript:bad()">Hi Person,</a>'); },
  ]) {
    const f = new Fake(), service = new HtmlDrafts(f), p = await service.prepare(intent(f));
    f.afterPatch = () => alter(f);
    assert.equal((await service.execute(p.changeId, p.target)).status, "partial-or-uncertain");
    assert.equal(f.calls.length, 1);
  }
});

test("stale ETag rejection is never retried or reported verified", async () => {
  const f = new Fake(), service = new HtmlDrafts(f), p = await service.prepare(intent(f));
  f.request = async (...args) => { f.calls.push(args); throw new GraphError("Graph HTTP 412. Write not verified; do not automatically retry."); };
  const result = await service.execute(p.changeId, p.target);
  assert.equal(result.status, "partial-or-uncertain");
  assert.equal(result.retry, false);
  assert.equal(f.calls.length, 1);
  assert.equal(f.messageValue.body.content, originalHtml);
});
test("a write applied before response loss is reconciled by reading the same draft without another PATCH", async () => {
  const f = new Fake(), service = new HtmlDrafts(f), p = await service.prepare(intent(f));
  const write = f.request.bind(f);
  f.request = async (...args) => { await write(...args); throw new GraphError("Graph write outcome is uncertain. Do not retry; inspect mailbox state."); };
  assert.equal((await service.execute(p.changeId, p.target)).status, "partial-or-uncertain");
  const observed = await service.read(target);
  assert.equal(observed.message.id, "draft");
  assert.match(observed.body.content, /Hi Person,/);
  assert.equal(observed.bodySha256, htmlHash(f.messageValue.body.content));
  assert.equal(f.calls.length, 1);
});
test("provider CSS normalization is separated from logical content verification", async () => {
  const f = new Fake(), service = new HtmlDrafts(f), p = await service.prepare(intent(f));
  f.afterPatch = () => { f.messageValue.body.content = f.messageValue.body.content.replaceAll("margin:0 0 8pt", "margin-bottom:8pt"); };
  const r = await service.execute(p.changeId, p.target);
  assert.equal(r.status, "verified");
  assert.equal(r.verification.exactHtml, false);
  assert.equal(r.verification.exactCss, false);
});

test("43-to-2 inline inventory reduction is not hidden by successful HTML content checks", async () => {
  const f = new Fake();
  f.messageValue.body.content = originalHtml.replace("</body>", '<img src="cid:quoted-two"></body>');
  f.inventory = Array.from({ length: 43 }, (_, i) => ({ id: "inline-" + i,
    name: "synthetic-" + i + ".png", contentType: "image/png", size: 100 + i,
    isInline: true, contentIdKnown: true,
    contentId: ["quoted", "quoted-two", "portrait"][i] ?? "orphan-" + i,
    lastModifiedDateTime: "2026-10-23T06:00:00Z" }));
  const retained = structuredClone(f.inventory.slice(0, 2));
  const quoteBefore = quoteFingerprint(htmlRegion(f.messageValue.body.content));
  const service = new HtmlDrafts(f), p = await service.prepare(intent(f));
  f.afterPatch = () => { f.inventory = structuredClone(retained); };
  const result = await service.execute(p.changeId, p.target);
  assert.equal(result.status, "partial-or-uncertain");
  assert.equal(result.stage, "html-body-readback");
  assert.equal(result.retry, false);
  assert.equal(result.diagnostics.checks.attachmentInventory, false);
  assert.equal(result.diagnostics.checks.protectedCidCoverage, true);
  const removed = result.diagnostics.attachmentDifferences.removed;
  assert.equal(removed.length, 41);
  assert.deepEqual(removed[0].before.roles, ["authored"]);
  assert.equal(removed[0].before.contentId, "portrait");
  assert.equal(removed[0].proposed.classification, "unreferenced");
  assert.equal(removed[1].before.classification, "unreferenced");
  assert.equal(result.diagnostics.attachmentReferences.observed.references.length, 2);
  const observed = await service.read(target);
  assert.equal(observed.message.isDraft, true);
  assert.equal(observed.editRegion.quoteSha256, quoteBefore);
  assert.deepEqual(observed.attachments, retained);
  assert.match(observed.body.content, /Hi Person,/);
  assert.equal(f.calls.length, 1);
  await assert.rejects(service.execute(p.changeId, p.target), /missing/);
});

test("missing or duplicate protected CIDs fail before any PATCH", async () => {
  for (const alter of [
    (f) => { f.inventory = f.inventory.filter((a) => a.contentId !== "quoted"); },
    (f) => { f.inventory.push({ ...f.inventory[0], id: "duplicate" }); },
    (f) => { f.inventory[0].isInline = false; },
    (f) => { f.inventory[0].contentId = null; f.inventory[0].contentIdKnown = false; },
  ]) {
    const f = new Fake(); alter(f);
    const service = new HtmlDrafts(f), read = await service.read(target);
    assert.equal(read.editRegion.attachmentReferences.protectedReferencesComplete, false);
    await assert.rejects(service.prepare(intent(f)), /CID references/);
    assert.equal(f.calls.length, 0);
  }
});

test("CID metadata changes with identical attachment ID and size are diagnosed and never retried", async () => {
  const f = new Fake(), service = new HtmlDrafts(f), p = await service.prepare(intent(f));
  f.afterPatch = () => { f.inventory[0].contentId = "different"; };
  const result = await service.execute(p.changeId, p.target);
  assert.equal(result.status, "partial-or-uncertain");
  assert.equal(result.diagnostics.checks.attachmentInventory, false);
  assert.equal(result.diagnostics.checks.protectedCidCoverage, false);
  const [changed] = result.diagnostics.attachmentDifferences.changed;
  assert.equal(changed.before.contentId, "quoted");
  assert.equal(changed.observed.contentId, "different");
  assert.equal(result.retry, false);
  assert.equal(f.calls.length, 1);
});

test("switching protected CSS references between existing assets fails without an inventory mismatch", async () => {
  for (const mode of ["quoted", "document"]) {
    const f = new Fake();
    const css = '<style>.example { background:url("cid:quoted") }</style>';
    f.messageValue.body.content = originalHtml.replace(mode === "quoted" ? "</body>" : "</head>",
      css + (mode === "quoted" ? "</body>" : "</head>"));
    const service = new HtmlDrafts(f), p = await service.prepare(intent(f));
    f.afterPatch = () => { f.messageValue.body.content = f.messageValue.body.content.replace(css,
      css.replace("cid:quoted", "cid:portrait")); };
    const result = await service.execute(p.changeId, p.target);
    assert.equal(result.status, "partial-or-uncertain");
    assert.equal(result.diagnostics.checks.attachmentInventory, true);
    assert.equal(result.diagnostics.checks.protectedCidCoverage, true);
    assert.equal(result.diagnostics.checks.protectedCidReferences, false);
    assert.equal(f.calls.length, 1);
  }
});

test("removal of unreferenced or unknown-CID assets still fails strict inventory verification", async () => {
  for (const extra of [
    { contentId: "unused", contentIdKnown: true },
    { contentId: null, contentIdKnown: false },
  ]) {
    const f = new Fake();
    f.inventory.push({ ...f.inventory[0], ...extra, id: "extra" });
    const service = new HtmlDrafts(f), p = await service.prepare(intent(f));
    p.attachmentReferences.baseline.inventory[0].contentId = "public-preview-tampering";
    f.afterPatch = () => { f.inventory.pop(); };
    const result = await service.execute(p.changeId, p.target);
    assert.equal(result.status, "partial-or-uncertain");
    assert.equal(result.diagnostics.checks.protectedCidCoverage, true);
    assert.equal(result.diagnostics.attachmentDifferences.removed[0].before.classification,
      extra.contentIdKnown ? "unreferenced" : "unknown-content-id");
    assert.equal(result.diagnostics.attachmentReferences.baseline.inventory[0].contentId, "quoted");
    assert.equal(result.retry, false);
    assert.equal(f.calls.length, 1);
  }
});
test("missing, duplicate, nested and structurally excessive quote layouts fail without writes", async () => {
  for (const html of [
    "<html><body><p>No quote</p></body></html>",
    originalHtml.replace("</body>", '<div id="divRplyFwdMsg">Other</div></body>'),
    originalHtml.replace('<div id="divRplyFwdMsg">', '<table><tr><td><div id="divRplyFwdMsg">').replace("</body>", "</td></tr></table></body>"),
    '<html><body>' + '<div>'.repeat(300) + '<div id="divRplyFwdMsg">x</div>' + '</div>'.repeat(300) + '</body></html>',
  ]) {
    const f = new Fake(); f.messageValue.body.content = html;
    await assert.rejects(new HtmlDrafts(f).prepare(intent(f)));
    assert.equal(f.calls.length, 0);
  }
});
test("a single native wrapper is supported while preserving outer markup and quote bytes", () => {
  const html = originalHtml.replace("<body>", '<body><div dir="ltr">').replace("</body>", "</div></body>");
  const before = htmlRegion(html), afterHtml = before.replace(renderParagraphs(paragraphs));
  assert.ok(afterHtml.startsWith('<html><head><meta charset="utf-8"></head><body><div dir="ltr">'));
  assert.equal(quoteFingerprint(htmlRegion(afterHtml)), quoteFingerprint(before));
  assert.ok(afterHtml.endsWith(html.slice(html.indexOf("<hr>"))));
});
