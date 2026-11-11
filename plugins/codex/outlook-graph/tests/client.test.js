import test from "node:test";
import assert from "node:assert/strict";
import { GraphClient, identity, key } from "../src/client.js";
const response = (value, status = 200, headers = {}) =>
  new Response(JSON.stringify(value), { status, headers });
const make = (fn, opts = {}) =>
  new GraphClient(async () => "test-token", { fetchImpl: fn, ...opts });
test("metadata projection includes all durable identity fields and body", async () => {
  const c = make(async (u, o) => {
    for (const k of [
      "internetMessageId",
      "conversationId",
      "parentFolderId",
      "categories",
      "webLink",
      "bccRecipients",
      "body",
    ])
      assert.ok(u.searchParams.get("$select").split(",").includes(k));
    assert.equal(o.redirect, "error");
    return response({ id: "m" });
  });
  await c.message("m");
});
test("read retries respect Retry-After; writes run only once", async () => {
  let n = 0;
  let clock = 0;
  const delays = [];
  const c = make(
    async () =>
      ++n < 3
        ? response({}, 429, { "retry-after": "1" })
        : response({ ok: true }),
    { now: () => clock, sleep: async (ms) => { delays.push(ms); clock += ms; } },
  );
  await c.me();
  assert.equal(n, 3);
  assert.deepEqual(delays, [1000, 1000]);
  n = 0;
  await assert.rejects(
    c.request("PATCH", "/me/messages/m", { body: { categories: [] } }),
    /429/,
  );
  assert.equal(n, 1);
});
test("long throttling delays stop instead of sleeping indefinitely", async () => {
  const c = make(async () => response({}, 429, { "retry-after": "60" }), {
    sleep: () => assert.fail(),
  });
  await assert.rejects(c.me(), /throttled/);
});
test("redirect or network error never leaks token/error body or retries a write", async () => {
  let n = 0;
  const c = make(async () => {
    n++;
    throw Error("test-token secret redirect");
  });
  await assert.rejects(
    c.request("POST", "/me/messages"),
    (e) => /uncertain/.test(e.message) && !e.message.includes("test-token"),
  );
  assert.equal(n, 1);
});
test("arbitrary endpoint and dot identifiers are refused before auth", async () => {
  const c = new GraphClient(() => assert.fail());
  for (const p of [
    "https://evil.example/v1.0/me/messages",
    "https://graph.microsoft.com.evil.example/v1.0/me/messages",
    "/users/victim/messages",
    "/me/../users/x",
  ])
    await assert.rejects(c.request("GET", p));
  for (const id of [".", "..", "a\nb"]) assert.throws(() => key(id));
});
test("opaque continuation retains provider URL and query, refuses other tool and expiry", async () => {
  const urls = [];
  let clock = 0;
  const c = make(
    async (u) => {
      urls.push(u.href);
      return response(
        urls.length === 1
          ? {
              value: [{ id: 1 }],
              "@odata.nextLink":
                "https://graph.microsoft.com/v1.0/me/messages?$skip=17&$top=25",
            }
          : { value: [{ id: 2 }] },
      );
    },
    { now: () => clock },
  );
  const first = await c.messages();
  assert.equal(first.complete, false);
  await assert.rejects(c.folders({ cursor: first.nextCursor }), /another/);
  const last = await c.messages({ cursor: first.nextCursor });
  assert.equal(last.complete, true);
  assert.match(urls[1], /skip=17/);
  clock = 600001;
  await assert.rejects(c.messages({ cursor: first.nextCursor }), /expired/);
});
test("malicious continuation host and path cannot redirect credentials", async () => {
  for (const next of [
    "https://evil.test/v1.0/me/messages",
    "https://graph.microsoft.com/v1.0/me/sendMail",
  ]) {
    const c = make(async () =>
      response({ value: [], "@odata.nextLink": next }),
    );
    await assert.rejects(c.messages(), /continuation/);
  }
});
test("structured queries quote values; search cannot combine with filter", async () => {
  const c = make(async (u) => {
    assert.equal(u.searchParams.get("$filter"), "subject eq 'Owner''s quote'");
    return response({ value: [] });
  });
  await c.messages({ subject: "Owner's quote" });
  assert.throws(
    () => c.messages({ query: "foo", sender: "a@x.test" }),
    /not both/,
  );
});
test("oversized and malformed provider data fail safely", async () => {
  await assert.rejects(
    make(async () => new Response("x".repeat(4 * 1024 * 1024 + 1))).me(),
    /4 MiB/,
  );
  await assert.rejects(
    make(async () => new Response("{bad")).me(),
    /invalid JSON/,
  );
  await assert.rejects(make(async () => response({})).messages(), /collection/);
  assert.throws(() => identity({}), /incomplete/);
});
test("folder ancestor cycles are bounded", async () => {
  const c = make(async (u) =>
    response(
      u.pathname.endsWith("msgfolderroot")
        ? { id: "root" }
        : { id: "x", displayName: "x", parentFolderId: "x" },
    ),
  );
  await assert.rejects(c.folderPath("x"), /cycle/);
});
test("EWS translation uses documented Graph operation", async () => {
  const c = make(async (u, o) => {
    assert.match(u.pathname, /translateExchangeIds$/);
    assert.equal(JSON.parse(o.body).targetIdType, "restId");
    return response({ value: [{ targetId: "rest" }] });
  });
  assert.deepEqual(await c.translate("ews"), { id: "rest" });
});
test("send, delete, arbitrary mailbox settings and write-through-read routes are blocked", async () => {
  const c = new GraphClient(() => assert.fail());
  for (const [method, path] of [
    ["POST", "/me/sendMail"],
    ["DELETE", "/me/messages/m"],
    ["POST", "/me/messages/m/send"],
    ["PATCH", "/me/mailboxSettings"],
    ["GET", "/me/messages/m/send"],
  ])
    await assert.rejects(c.request(method, path), /reviewed/);
});

test("HTML reads use the HTML preference without changing existing text reads", async () => {
  const seen = [], c = make(async (_url, options) => {
    seen.push(options.headers.Prefer);
    return response({ id: "m" });
  });
  await c.message("m", { bodyType: "html" });
  await c.message("m");
  assert.deepEqual(seen, ['outlook.body-content-type="html"', 'outlook.body-content-type="text"']);
  assert.throws(() => c.message("m", { bodyType: "unsafe" }));
});
test("attachment inventory is complete, metadata-only and sorted across pages", async () => {
  let count = 0;
  const c = make(async (url) => {
    assert.match(url.pathname, /\/messages\/m\/attachments$/);
    if (!count) {
      assert.ok(!url.searchParams.get("$select").includes("contentBytes"));
      assert.ok(url.searchParams.get("$select").split(",").includes("microsoft.graph.fileAttachment/contentId"));
    }
    return response({ value: [{ id: ++count === 1 ? "b" : "a", name: "logo.png", size: 12,
      isInline: true, contentType: "image/png", contentId: "example-cid", contentBytes: "must-not-return" }],
      ...(count === 1 ? { "@odata.nextLink": "https://graph.microsoft.com/v1.0/me/messages/m/attachments?$skip=1" } : {}) });
  });
  const result = await c.attachments("m");
  assert.deepEqual(result.map((x) => x.id), ["a", "b"]);
  assert.ok(result.every((x) => x.contentIdKnown && x.contentId === "example-cid"));
  assert.ok(!JSON.stringify(result).includes("must-not-return"));
});
test("attachment content IDs distinguish omitted, null and raw values and reject invalid metadata", async () => {
  const item = { id: "a", name: "example.png", size: 12, isInline: true, contentType: "image/png" };
  for (const [extra, known, expected] of [[{}, false, null], [{ contentId: null }, true, null], [{ contentId: "<raw@test>" }, true, "<raw@test>"]]) {
    const [a] = await make(async () => response({ value: [{ ...item, ...extra }] })).attachments("m");
    assert.equal(a.contentIdKnown, known);
    assert.equal(a.contentId, expected);
  }
  for (const contentId of [4, "x".repeat(2049), "line\nfeed"])
    await assert.rejects(make(async () => response({ value: [{ ...item, contentId }] })).attachments("m"), /metadata/);
});
test("attachment pagination is bounded and missing metadata is rejected", async () => {
  const c = make(async () => response({ value: [],
    "@odata.nextLink": "https://graph.microsoft.com/v1.0/me/messages/m/attachments?$skip=1" }));
  await assert.rejects(c.attachments("m"), /five pages/);
  await assert.rejects(make(async () => response({ value: [{ id: "incomplete" }] })).attachments("m"), /metadata/);
});

test("derived CID selection avoids base-schema HTTP 400 and retains all attachment types across pages", async () => {
  const select = "id,name,contentType,size,isInline,lastModifiedDateTime,microsoft.graph.fileAttachment/contentId";
  const common = { name: "synthetic", size: 12, isInline: false, contentType: "application/octet-stream" };
  const items = [
    { ...common, id: "file", "@odata.type": "#microsoft.graph.fileAttachment", contentId: "example-image", isInline: true },
    { ...common, id: "item", "@odata.type": "#microsoft.graph.itemAttachment" },
    { ...common, id: "reference", "@odata.type": "#microsoft.graph.referenceAttachment" },
  ];
  const seen = [];
  const c = make(async (url) => {
    seen.push(url.href);
    const fields = (url.searchParams.get("$select") || "").split(",");
    if (fields.includes("contentId")) return response({ error: { code: "Request_BadRequest" } }, 400);
    assert.deepEqual(fields, select.split(","));
    assert.ok(!url.pathname.includes("microsoft.graph.fileAttachment")); // no collection filter dropping other types
    assert.ok(!url.pathname.endsWith("/$value"));
    const next = new URL(url);
    next.searchParams.set("$skip", "1");
    return response(url.searchParams.has("$skip") ? { value: items.slice(1) } :
      { value: items.slice(0, 1), "@odata.nextLink": next.href });
  });
  await assert.rejects(c.request("GET", "/me/messages/m/attachments", { query: { $select: "id,contentId" } }), /HTTP 400/);
  seen.length = 0;
  const result = await c.attachments("m");
  assert.equal(seen.length, 2);
  assert.deepEqual(result.map((a) => a.id), ["file", "item", "reference"]);
  assert.equal(result[0].contentId, "example-image");
  assert.equal(result[0].attachmentType, "#microsoft.graph.fileAttachment");
  assert.equal(result[1].attachmentType, "#microsoft.graph.itemAttachment");
  assert.equal(result[2].attachmentType, "#microsoft.graph.referenceAttachment");
  assert.equal(result[1].contentIdKnown, false);
  assert.equal(result[2].contentIdKnown, false);
});

test("typed attachment projection errors are surfaced without unprojected fallback or HTTP 400 retry", async () => {
  let calls = 0;
  const c = make(async (url) => {
    calls++;
    assert.ok(url.searchParams.get("$select").includes("microsoft.graph.fileAttachment/contentId"));
    assert.ok(!url.searchParams.get("$select").includes("contentBytes"));
    return response({}, 400);
  });
  await assert.rejects(c.attachments("m"), /HTTP 400/);
  assert.equal(calls, 1);
});
test("minimum interval applies to concurrent calls and retry attempts", async () => {
  let clock = 0, attempts = 0;
  const started = [], c = make(async () => {
    started.push(clock);
    return ++attempts === 1 ? response({}, 503) : response({ id: "x" });
  }, { minimumRequestIntervalMs: 25000, now: () => clock, sleep: async (ms) => { clock += ms; } });
  await Promise.all([c.me(), c.me()]);
  assert.equal(started.length, 3);
  for (let i = 1; i < started.length; i++) assert.ok(started[i] - started[i - 1] >= 25000);
  assert.throws(() => make(() => {}, { minimumRequestIntervalMs: -1 }));
});

test("longer Retry-After survives a failed call and governs the next request", async () => {
  let clock = 0, attempt = 0;
  const starts = [], c = make(async () => {
    starts.push(clock);
    return ++attempt === 1 ? response({}, 429, { "retry-after": "45" }) : response({ id: "x" });
  }, { minimumRequestIntervalMs: 25000, now: () => clock, sleep: async (ms) => { clock += ms; } });
  await assert.rejects(c.me(), /throttled/);
  await c.me();
  assert.deepEqual(starts, [0, 45000]);
});
test("Retry-After on a refused PATCH never retries the write and also pauses later reads", async () => {
  let clock = 0, attempt = 0;
  const starts = [], c = make(async () => {
    starts.push(clock);
    return ++attempt === 1 ? response({}, 429, { "retry-after": "30" }) : response({ id: "x" });
  }, { now: () => clock, sleep: async (ms) => { clock += ms; } });
  await assert.rejects(c.request("PATCH", "/me/messages/m", { body: { body: {} } }), /429/);
  assert.equal(attempt, 1);
  await c.me();
  assert.deepEqual(starts, [0, 30000]);
});
