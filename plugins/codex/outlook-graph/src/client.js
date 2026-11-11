import { randomUUID } from "node:crypto";

export class GraphError extends Error {}
export const BASE = "https://graph.microsoft.com/v1.0";
export const FIELDS =
  "id,internetMessageId,subject,from,sender,receivedDateTime,sentDateTime,conversationId,parentFolderId,categories,webLink,isDraft,changeKey,toRecipients,ccRecipients,bccRecipients,replyTo,isRead,hasAttachments";
export const key = (value) => {
  if (
    typeof value !== "string" ||
    !value ||
    value === "." ||
    value === ".." ||
    value.length > 2048 ||
    /[\x00-\x20]/.test(value)
  )
    throw new GraphError("Invalid identifier.");
  return encodeURIComponent(value);
};
const quote = (s) => "'" + s.replaceAll("'", "''") + "'";
const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

export class GraphClient {
  constructor(
    token,
    { fetchImpl = fetch, sleep = pause, now = Date.now, minimumRequestIntervalMs = 0 } = {},
  ) {
    this.token = token;
    this.fetch = fetchImpl;
    this.sleep = sleep;
    this.now = now;
    this.cursors = new Map();
    if (!Number.isSafeInteger(minimumRequestIntervalMs) || minimumRequestIntervalMs < 0 || minimumRequestIntervalMs > 60000)
      throw new GraphError("Minimum request interval must be an integer from 0 to 60000 milliseconds.");
    this.minimumRequestIntervalMs = minimumRequestIntervalMs;
    this.lastRequestAt = null;
    this.retryAfterUntil = 0;
    this.requestQueue = Promise.resolve();
  }
  async pace(action) {
    if (!this.minimumRequestIntervalMs && this.retryAfterUntil <= this.now()) return action();
    const previous = this.requestQueue;
    let release;
    this.requestQueue = new Promise((resolve) => { release = resolve; });
    await previous;
    try {
      const remaining = Math.max(this.retryAfterUntil,
        this.lastRequestAt === null ? 0 : this.lastRequestAt + this.minimumRequestIntervalMs) - this.now();
      if (remaining > 60000) throw new GraphError("Graph Retry-After cooldown exceeds one minute; wait before another request.");
      if (remaining > 0) await this.sleep(remaining);
      this.lastRequestAt = this.now();
      return action();
    } finally { release(); }
  }
  async request(method, path, { query = {}, body, headers = {} } = {}) {
    const url = new URL(path.startsWith("https:") ? path : BASE + path);
    if (
      url.origin !== "https://graph.microsoft.com" ||
      (!url.pathname.startsWith("/v1.0/me/") && url.pathname !== "/v1.0/me") ||
      url.username ||
      url.password ||
      url.hash
    )
      throw new GraphError("Unapproved Graph endpoint.");
    const route = url.pathname.slice("/v1.0".length);
    const approved =
      (method === "GET" &&
        /^\/me(?:\/messages(?:\/[^/]+(?:\/attachments)?)?|\/mailFolders(?:\/[^/]+(?:\/(?:messages|childFolders))?)?|\/outlook\/masterCategories)?$/.test(
          route,
        )) ||
      (method === "POST" &&
        /^\/me\/(?:translateExchangeIds|messages(?:\/[^/]+\/(?:move|createReply|createReplyAll))?)$/.test(
          route,
        )) ||
      (method === "PATCH" && /^\/me\/messages\/[^/]+$/.test(route));
    if (!approved)
      throw new GraphError("Operation is outside the reviewed Graph routes.");
    for (const [k, v] of Object.entries(query))
      if (v !== undefined) url.searchParams.set(k, String(v));
    const accessToken = await this.token();
    for (let attempt = 0; attempt < 3; attempt++) {
      let response;
      try {
        response = await this.pace(() => this.fetch(url, {
          method,
          redirect: "error",
          signal: AbortSignal.timeout(20000),
          headers: {
            Authorization: "Bearer " + accessToken,
            Accept: "application/json",
            "Content-Type": "application/json",
            Prefer: 'outlook.body-content-type="text"',
            ...headers,
          },
          ...(body === undefined ? {} : { body: JSON.stringify(body) }),
        }));
      } catch (e) {
        if (e instanceof GraphError) throw e;
        throw new GraphError(
          method === "GET"
            ? "Graph read failed or timed out."
            : "Graph write outcome is uncertain. Do not retry; inspect mailbox state.",
        );
      }
      const retryAfter = response.headers.get("retry-after");
      if (!response.ok && retryAfter) {
        const until = /^\d+$/.test(retryAfter)
          ? this.now() + Number(retryAfter) * 1000 : Date.parse(retryAfter);
        if (Number.isFinite(until)) this.retryAfterUntil = Math.max(this.retryAfterUntil, until);
      }
      if (
        method === "GET" &&
        [429, 502, 503, 504].includes(response.status) &&
        attempt < 2
      ) {
        const retry = response.headers.get("retry-after");
        const delay = retry
          ? /^\d+$/.test(retry)
            ? Number(retry) * 1000
            : Date.parse(retry) - this.now()
          : 500 * 2 ** attempt;
        await response.body?.cancel();
        if (!Number.isFinite(delay) || delay > 10000)
          throw new GraphError("Graph is throttled; retry later.");
        await this.sleep(Math.max(0, delay));
        continue;
      }
      if (!response.ok) {
        await response.body?.cancel();
        throw new GraphError(
          `Graph HTTP ${response.status}. ${method === "GET" ? "Read failed." : "Write not verified; do not automatically retry."}`,
        );
      }
      if (response.status === 204) return null;
      const reader = response.body?.getReader();
      if (!reader) throw new GraphError("Graph returned no body.");
      const chunks = [];
      let size = 0;
      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          size += value.length;
          if (size > 4 * 1024 * 1024) {
            await reader.cancel();
            throw new GraphError(
              "Graph response exceeds 4 MiB; narrow the request.",
            );
          }
          chunks.push(Buffer.from(value));
        }
      } catch (e) {
        if (e instanceof GraphError) throw e;
        throw new GraphError(
          "Graph response incomplete; write outcome may be uncertain.",
        );
      }
      try {
        return JSON.parse(Buffer.concat(chunks).toString("utf8"));
      } catch {
        throw new GraphError(
          "Graph returned invalid JSON; outcome not verified.",
        );
      }
    }
  }
  async page(path, query, cursor, kind) {
    let nextPath = path;
    if (cursor) {
      const entry = this.cursors.get(cursor);
      if (!entry || entry.kind !== kind || entry.expires < this.now())
        throw new GraphError(
          "Cursor missing, expired or for another read tool.",
        );
      nextPath = entry.url;
      query = {};
    }
    const data = await this.request("GET", nextPath, { query });
    if (!Array.isArray(data.value))
      throw new GraphError("Graph collection missing.");
    let nextCursor = null;
    if (data["@odata.nextLink"]) {
      const u = new URL(data["@odata.nextLink"]);
      if (
        u.origin !== "https://graph.microsoft.com" ||
        u.pathname !==
          new URL(nextPath.startsWith("https:") ? nextPath : BASE + nextPath)
            .pathname ||
        u.username ||
        u.password ||
        u.hash
      )
        throw new GraphError("Invalid Graph continuation link.");
      for (const [id, e] of this.cursors)
        if (e.expires < this.now()) this.cursors.delete(id);
      if (this.cursors.size >= 200)
        throw new GraphError("Too many active pagination cursors.");
      nextCursor = randomUUID();
      this.cursors.set(nextCursor, {
        url: u.href,
        kind,
        expires: this.now() + 600000,
      });
    }
    return { items: data.value, nextCursor, complete: nextCursor === null };
  }
  me() {
    return this.request("GET", "/me", {
      query: { $select: "id,mail,userPrincipalName" },
    });
  }
  message(id, { bodyType = "text" } = {}) {
    if (!["text", "html"].includes(bodyType)) throw new GraphError("Unsupported body read format.");
    return this.request("GET", "/me/messages/" + key(id), {
      query: { $select: FIELDS + ",body" },
      headers: { Prefer: 'outlook.body-content-type="' + bodyType + '"' },
    });
  }
  async attachments(id) {
    const inventory = [], seen = new Set();
    let cursor;
    for (let i = 0; i < 5; i++) {
      const page = await this.page("/me/messages/" + key(id) + "/attachments", {
        // contentId is declared on fileAttachment, not the base collection type.
        // Qualify only that property; retain item/reference attachments and paging.
        $top: 100, $select: "id,name,contentType,size,isInline,lastModifiedDateTime,microsoft.graph.fileAttachment/contentId",
      }, cursor, "attachments:" + id);
      for (const item of page.items) {
        if (typeof item.id !== "string" || !item.id || seen.has(item.id) ||
            typeof item.name !== "string" || !Number.isFinite(item.size) || item.size < 0 ||
            typeof item.isInline !== "boolean" || typeof item.contentType !== "string" ||
            (item["@odata.type"] != null && (typeof item["@odata.type"] !== "string" || item["@odata.type"].length > 200)) ||
            (item.contentId != null && (typeof item.contentId !== "string" ||
              item.contentId.length > 2048 || /[\x00-\x1f\x7f]/.test(item.contentId))))
          throw new GraphError("Attachment metadata is incomplete or duplicated.");
        seen.add(item.id);
        inventory.push({ ...Object.fromEntries(["id", "name", "contentType", "size", "isInline", "lastModifiedDateTime", "contentId"]
          .map((field) => [field, item[field] ?? null])),
          contentIdKnown: Object.hasOwn(item, "contentId"), attachmentType: item["@odata.type"] ?? null });
      }
      cursor = page.nextCursor;
      if (!cursor) return inventory.sort((a, b) => a.id.localeCompare(b.id));
    }
    throw new GraphError("Attachment inventory exceeds five pages; no draft update is permitted.");
  }
  folder(id) {
    return this.request("GET", "/me/mailFolders/" + key(id), {
      query: { $select: "id,displayName,parentFolderId,childFolderCount" },
    });
  }
  async folderPath(id) {
    const parts = [],
      seen = new Set();
    const root = await this.folder("msgfolderroot");
    for (let i = 0; i < 32; i++) {
      if (id === root.id) return parts.reverse().join("/");
      if (seen.has(id)) throw new GraphError("Folder ancestry cycle.");
      seen.add(id);
      const f = await this.folder(id);
      parts.push(f.displayName);
      id = f.parentFolderId;
      if (!id) throw new GraphError("Incomplete folder ancestry.");
    }
    throw new GraphError("Folder ancestry exceeds 32 levels.");
  }
  categories({ cursor } = {}) {
    return this.page(
      "/me/outlook/masterCategories",
      { $top: 100 },
      cursor,
      "categories",
    );
  }
  folders({ parentId, cursor, limit = 50 } = {}) {
    return this.page(
      parentId
        ? "/me/mailFolders/" + key(parentId) + "/childFolders"
        : "/me/mailFolders",
      {
        $top: limit,
        $select: "id,displayName,parentFolderId,childFolderCount",
      },
      cursor,
      "folders",
    );
  }
  messages({
    folderId,
    query,
    sender,
    subject,
    receivedAfter,
    receivedBefore,
    conversationId,
    cursor,
    limit = 25,
  } = {}) {
    const filters = [];
    if (receivedAfter) filters.push("receivedDateTime ge " + receivedAfter);
    if (receivedBefore) filters.push("receivedDateTime lt " + receivedBefore);
    if (sender) filters.push("from/emailAddress/address eq " + quote(sender));
    if (subject) filters.push("subject eq " + quote(subject));
    if (conversationId)
      filters.push("conversationId eq " + quote(conversationId));
    if (query && filters.length)
      throw new GraphError("Use search text or structured filters, not both.");
    return this.page(
      folderId
        ? "/me/mailFolders/" + key(folderId) + "/messages"
        : "/me/messages",
      {
        $top: limit,
        $select: FIELDS,
        ...(query
          ? { $search: JSON.stringify(query) }
          : filters.length
            ? { $filter: filters.join(" and ") }
            : { $orderby: "receivedDateTime desc" }),
      },
      cursor,
      "messages",
    );
  }
  async translate(id, sourceType = "ewsId") {
    const result = await this.request("POST", "/me/translateExchangeIds", {
      body: {
        inputIds: [id],
        sourceIdType: sourceType,
        targetIdType: "restId",
      },
    });
    const item = result.value?.[0];
    if (!item?.targetId)
      throw new GraphError("ID translation failed; search by source metadata.");
    return { id: item.targetId };
  }
}

export function identity(m) {
  const fields = [
    "id",
    "internetMessageId",
    "subject",
    "receivedDateTime",
    "conversationId",
    "parentFolderId",
    "webLink",
    "changeKey",
  ];
  if (
    fields.some((k) => typeof m[k] !== "string" || !m[k]) ||
    !Number.isFinite(Date.parse(m.receivedDateTime)) ||
    !Array.isArray(m.categories) ||
    m.categories.some((c) => typeof c !== "string") ||
    typeof m.isDraft !== "boolean" ||
    !m.from?.emailAddress?.address
  )
    throw new GraphError(
      "Message identity metadata is incomplete. Stop dependent changes.",
    );
  return messageView(m);
}
export const messageView = (m) =>
  Object.fromEntries(FIELDS.split(",").map((k) => [k, m[k] ?? null]));
