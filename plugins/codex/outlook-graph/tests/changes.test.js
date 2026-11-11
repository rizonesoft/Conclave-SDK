import test from "node:test";
import assert from "node:assert/strict";
import { Changes } from "../src/changes.js";
const mail = (overrides = {}) => ({
  id: "m",
  internetMessageId: "<permanent@example.test>",
  subject: "Request",
  receivedDateTime: "2026-10-13T08:00:00Z",
  conversationId: "thread",
  parentFolderId: "inbox-id",
  categories: ["Blue"],
  webLink: "https://outlook.office.com/m",
  changeKey: "v1",
  isDraft: false,
  from: { emailAddress: { address: "sender@example.test" } },
  body: { contentType: "text", content: "original" },
  "@odata.etag": 'W/"v1"',
  ...overrides,
});
class Fake {
  constructor() {
    this.source = mail();
    this.evidence = mail({
      id: "old",
      parentFolderId: "dest",
      receivedDateTime: "2026-10-10T08:00:00Z",
    });
    this.calls = [];
    this.cat = true;
    this.path = "Inbox/Processed/Customers/Example";
  }
  async me() {
    return { id: "account", mail: "owner@example.test" };
  }
  async message(id) {
    return structuredClone(
      id === "old" ? this.evidence : id === "draft" ? this.draft : this.source,
    );
  }
  async folder(id) {
    return {
      id: id === "inbox" ? "inbox-id" : id,
      displayName: id,
      parentFolderId: "root",
    };
  }
  async folderPath() {
    return this.path;
  }
  async categories() {
    return {
      items: this.cat ? [{ displayName: "TickTick" }] : [],
      nextCursor: null,
    };
  }
  async request(method, path, { body } = {}) {
    this.calls.push({ method, path, body: structuredClone(body) });
    if (this.fail?.(method, path)) throw Error("provider secret failure");
    if (path.endsWith("/move")) {
      this.source = {
        ...this.source,
        id: "new-id",
        parentFolderId: body.destinationId,
        webLink: "https://outlook.office.com/new",
      };
      return { id: "new-id" };
    }
    if (method === "POST") {
      this.draft = { ...mail({ id: "draft", isDraft: true }), ...(body || {}) };
      return { id: "draft" };
    }
    if (path.endsWith("/draft")) Object.assign(this.draft, body);
    else Object.assign(this.source, body);
    return {};
  }
}
const filing = {
  messageId: "m",
  destinationId: "dest",
  evidenceMessageId: "old",
};
test("missing account identity cannot create a preview", async () => {
  const f = new Fake();
  f.me = async () => ({});
  await assert.rejects(
    new Changes(f).prepare("tag_message", { messageId: "m" }),
    /account identity/,
  );
  assert.equal(f.calls.length, 0);
});
test("category lookup follows continuation before deciding it is missing", async () => {
  const f = new Fake();
  const seen = [];
  f.categories = async ({ cursor }) => {
    seen.push(cursor);
    return cursor
      ? { items: [{ displayName: "TickTick" }], nextCursor: null }
      : { items: [], nextCursor: "next" };
  };
  await new Changes(f).prepare("tag_message", { messageId: "m" });
  assert.deepEqual(seen, [undefined, "next"]);
  assert.equal(f.calls.length, 0);
});
test("preview does no writes, includes full body and is isolated from caller mutation", async () => {
  const f = new Fake(),
    c = new Changes(f);
  const p = await c.prepare("create_draft", {
    mode: "new",
    subject: "Re: hello",
    to: ["real@example.test"],
    body: "Body only",
  });
  assert.equal(p.parameters.body, "Body only");
  p.parameters.body = "tampered";
  assert.equal(f.calls.length, 0);
  const done = await c.execute(p.changeId, p.target);
  assert.equal(done.status, "verified");
  assert.equal(f.calls[0].body.body.content, "Body only");
});
test("filing preserves category set and verifies new permanent identity and link", async () => {
  const f = new Fake(),
    c = new Changes(f);
  const p = await c.prepare("file_message", filing);
  const r = await c.execute(p.changeId, p.target);
  assert.equal(r.status, "verified");
  assert.deepEqual(r.message.categories, ["Blue", "TickTick"]);
  assert.equal(r.message.internetMessageId, f.evidence.internetMessageId);
  assert.equal(r.message.id, "new-id");
  assert.equal(f.calls.length, 2);
  assert.equal(r.atomic, false);
});
test("top-level Noise accepts evidenced filing and verifies category preservation", async () => {
  const f = new Fake();
  f.path = "Noise";
  const c = new Changes(f);
  const p = await c.prepare("file_message", filing);
  assert.equal(p.before.folderPath, "Noise");
  assert.equal(f.calls.length, 0);
  const r = await c.execute(p.changeId, p.target);
  assert.equal(r.status, "verified");
  assert.equal(r.folderPath, "Noise");
  assert.equal(r.message.parentFolderId, filing.destinationId);
  assert.equal(r.message.internetMessageId, p.before.source.internetMessageId);
  assert.equal(r.message.webLink, "https://outlook.office.com/new");
  assert.deepEqual(r.message.categories, ["Blue", "TickTick"]);
  assert.deepEqual(f.calls.map(({ method }) => method), ["PATCH", "POST"]);
  assert.deepEqual(f.calls[1].body, { destinationId: filing.destinationId });
});
test("Noise still requires earlier mail from the same sender or conversation", async () => {
  const f = new Fake();
  f.path = "Noise";
  f.evidence.from.emailAddress.address = "other@example.test";
  f.evidence.conversationId = "other";
  await assert.rejects(new Changes(f).prepare("file_message", filing), /earlier/);
  assert.equal(f.calls.length, 0);
});
test("Noise destination is revalidated before execution", async () => {
  const f = new Fake();
  f.path = "Noise";
  const c = new Changes(f);
  const p = await c.prepare("file_message", filing);
  f.path = "Deleted Items/Noise";
  await assert.rejects(c.execute(p.changeId, p.target), /Filing destination/);
  assert.equal(f.calls.length, 0);
});
test("Noise allowance does not admit other roots, nested names or subfolders", async () => {
  for (const path of [
    "Noises", "Noise/Child", "Inbox/Noise", "Archive/Noise",
    "Deleted Items/Noise", "Junk Email", "Sent Items", "Drafts", "Inbox",
  ]) {
    const f = new Fake();
    f.path = path;
    await assert.rejects(new Changes(f).prepare("file_message", filing), /Filing destination/);
    assert.equal(f.calls.length, 0, path);
  }
});
test("tagging stays in Inbox and existing TickTick causes no duplicate update", async () => {
  const f = new Fake();
  f.source.categories.push("TickTick");
  const c = new Changes(f),
    p = await c.prepare("tag_message", { messageId: "m" });
  assert.equal((await c.execute(p.changeId, p.target)).status, "verified");
  assert.equal(f.calls.length, 0);
  assert.equal(f.source.parentFolderId, "inbox-id");
});
test("protected source folders and drafts are rejected", async () => {
  for (const folder of [
    "sentitems",
    "drafts",
    "deleteditems",
    "junkemail",
    "inbox-child",
  ]) {
    const f = new Fake();
    f.source.parentFolderId = folder;
    await assert.rejects(
      new Changes(f).prepare("file_message", filing),
      /directly in Inbox/,
    );
  }
  const f = new Fake();
  f.source.isDraft = true;
  await assert.rejects(
    new Changes(f).prepare("tag_message", { messageId: "m" }),
  );
});
test("missing category and wrong filing precedent block without writes", async () => {
  const f = new Fake();
  f.cat = false;
  await assert.rejects(
    new Changes(f).prepare("tag_message", { messageId: "m" }),
    /category/,
  );
  f.cat = true;
  f.evidence.parentFolderId = "elsewhere";
  await assert.rejects(
    new Changes(f).prepare("file_message", filing),
    /earlier/,
  );
  f.evidence.parentFolderId = "dest";
  f.path = "Sent Items/Customers";
  await assert.rejects(
    new Changes(f).prepare("file_message", filing),
    /Inbox\/Processed/,
  );
  assert.equal(f.calls.length, 0);
});
test("unrelated sender and conversation cannot supply filing evidence", async () => {
  const f = new Fake();
  f.evidence.from.emailAddress.address = "other@example.test";
  f.evidence.conversationId = "other";
  await assert.rejects(
    new Changes(f).prepare("file_message", filing),
    /earlier/,
  );
});
test("confirmation mismatch, changed state and replay are rejected", async () => {
  const f = new Fake(),
    c = new Changes(f),
    p = await c.prepare("tag_message", { messageId: "m" });
  await assert.rejects(c.execute(p.changeId, "wrong"), /match/);
  f.source.changeKey = "v2";
  await assert.rejects(c.execute(p.changeId, p.target), /changed/);
  await assert.rejects(c.execute(p.changeId, p.target), /missing/);
  assert.equal(f.calls.length, 0);
});
test("expiry before and during validation blocks writes", async () => {
  let now = 0;
  const f = new Fake(),
    c = new Changes(f, { now: () => now }),
    p = await c.prepare("tag_message", { messageId: "m" });
  now = 600001;
  await assert.rejects(c.execute(p.changeId, p.target), /expired/);
  now = 0;
  const q = await c.prepare("tag_message", { messageId: "m" });
  const original = f.me;
  f.me = async () => {
    now = 600001;
    return original();
  };
  await assert.rejects(c.execute(q.changeId, q.target), /during/);
  assert.equal(f.calls.length, 0);
});
test("concurrent execution consumes preview before awaiting validation", async () => {
  const f = new Fake(),
    c = new Changes(f),
    p = await c.prepare("tag_message", { messageId: "m" });
  const result = await Promise.allSettled([
    c.execute(p.changeId, p.target),
    c.execute(p.changeId, p.target),
  ]);
  assert.equal(result.filter((x) => x.status === "fulfilled").length, 1);
  assert.equal(f.calls.length, 1);
});
test("move failure reports partial result with tagged source and no retry", async () => {
  const f = new Fake();
  f.fail = (_m, p) => p.endsWith("/move");
  const c = new Changes(f),
    p = await c.prepare("file_message", filing),
    r = await c.execute(p.changeId, p.target);
  assert.equal(r.status, "partial-or-uncertain");
  assert.equal(r.stage, "move-requested");
  assert.equal(r.retry, false);
  assert.equal(f.calls.length, 2);
  assert.ok(!JSON.stringify(r).includes("provider secret"));
});
test("category readback failure prevents the move", async () => {
  const f = new Fake();
  f.request = async (...args) => {
    f.calls.push(args);
    return {};
  };
  const c = new Changes(f),
    p = await c.prepare("file_message", filing),
    r = await c.execute(p.changeId, p.target);
  assert.equal(r.verified, false);
  assert.equal(f.calls.length, 1);
});
test("incorrect moved identity is never reported verified", async () => {
  const f = new Fake(),
    orig = f.request.bind(f);
  f.request = async (...args) => {
    const r = await orig(...args);
    if (args[1].endsWith("/move")) f.source.internetMessageId = "<wrong>";
    return r;
  };
  const c = new Changes(f),
    p = await c.prepare("file_message", filing);
  assert.equal((await c.execute(p.changeId, p.target)).verified, false);
});
test("reply and reply-all replace generated content and verify exact recipients", async () => {
  for (const mode of ["reply", "reply_all"]) {
    const f = new Fake(),
      c = new Changes(f),
      p = await c.prepare("create_draft", {
        mode,
        messageId: "m",
        to: ["person@example.test"],
        cc: [],
        body: "Exact reply",
      });
    const r = await c.execute(p.changeId, p.target);
    assert.equal(r.status, "verified");
    assert.equal(r.sent, false);
    assert.match(
      f.calls[0].path,
      mode === "reply" ? /createReply$/ : /createReplyAll$/,
    );
    assert.equal(f.draft.body.content, "Exact reply");
    assert.deepEqual(f.draft.bccRecipients, []);
  }
});
test("partial draft body failure preserves draft ID for inspection", async () => {
  const f = new Fake();
  f.fail = (m) => m === "PATCH";
  const c = new Changes(f),
    p = await c.prepare("create_draft", {
      mode: "reply",
      messageId: "m",
      to: ["person@example.test"],
      body: "Reply",
    }),
    r = await c.execute(p.changeId, p.target);
  assert.equal(r.status, "partial-or-uncertain");
  assert.equal(r.draftId, "draft");
  assert.equal(f.calls.length, 2);
});
test("GitHub notification, empty body and unknown operations cannot create drafts", async () => {
  const f = new Fake();
  f.source.from.emailAddress.address = "notifications@github.com";
  const c = new Changes(f);
  await assert.rejects(
    c.prepare("create_draft", {
      mode: "reply",
      messageId: "m",
      to: ["a@example.test"],
      body: "test",
    }),
    /GitHub/,
  );
  await assert.rejects(
    c.prepare("create_draft", {
      mode: "new",
      subject: "x",
      to: ["a@example.test"],
      body: "",
    }),
  );
  await assert.rejects(c.prepare("send_mail", {}));
  assert.equal(f.calls.length, 0);
});
