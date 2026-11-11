import test from "node:test";
import assert from "node:assert/strict";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import { InMemoryTransport } from "@modelcontextprotocol/sdk/inMemory.js";
import { readFile } from "node:fs/promises";
process.env.OUTLOOK_GRAPH_TEST_IMPORT = "1";
const { createServer } = await import("../src/server.js");
test("MCP discovery contains reviewed tools only; reads cannot perform business writes", async () => {
  let writes = 0;
  const fake = {
    me: async () => ({ id: "x" }),
    folder: async () => ({ id: "inbox" }),
    request: () => {
      writes++;
      throw Error();
    },
  };
  const server = createServer(fake),
    client = new Client({ name: "test", version: "1" });
  const [a, b] = InMemoryTransport.createLinkedPair();
  await server.connect(a);
  await client.connect(b);
  try {
    const { tools } = await client.listTools();
    assert.equal(tools.length, 14);
    assert.ok(!tools.some((t) => /send|delete|http/.test(t.name)));
    for (const t of tools)
      assert.equal(t.annotations.readOnlyHint, !["execute_change", "execute_html_draft_update"].includes(t.name));
    const result = await client.callTool({
      name: "connection_status",
      arguments: {},
    });
    assert.ok(!result.isError);
    assert.equal(writes, 0);
    const invalid = await client.callTool({
      name: "prepare_create_draft",
      arguments: { mode: "send", body: "x", to: ["a@example.test"] },
    });
    assert.equal(invalid.isError, true);
  } finally {
    await client.close();
    await server.close();
  }
});
test("built package initializes without credentials and lists all tools", async () => {
  const client = new Client({ name: "package-probe", version: "1" });
  const env = { ...process.env, OUTLOOK_GRAPH_TEST_IMPORT: "0" };
  const transport = new StdioClientTransport({
    command: process.execPath,
    args: ["scripts/launch.mjs"],
    env,
    stderr: "pipe",
  });
  try {
    await client.connect(transport);
    assert.equal((await client.listTools()).tools.length, 14);
    const packageJson = JSON.parse(await readFile(new URL("../package.json", import.meta.url)));
    const pluginJson = JSON.parse(await readFile(new URL("../plugin.json", import.meta.url)));
    const lock = JSON.parse(await readFile(new URL("../package-lock.json", import.meta.url)));
    assert.equal(client.getServerVersion().version, packageJson.version);
    assert.equal(pluginJson.version, packageJson.version);
    assert.equal(lock.version, packageJson.version);
    assert.equal(lock.packages[""].version, packageJson.version);
  } finally {
    await client.close();
  }
});
test("message reads preserve missing identity and paginate the entire body", async () => {
  const server = createServer({
    message: async () => ({
      id: "draft",
      isDraft: true,
      body: { contentType: "text", content: "x".repeat(31000) },
    }),
  });
  const client = new Client({ name: "body-test", version: "1" });
  const [a, b] = InMemoryTransport.createLinkedPair();
  await server.connect(a);
  await client.connect(b);
  try {
    const read = async (bodyOffset) =>
      JSON.parse(
        (
          await client.callTool({
            name: "get_message",
            arguments: { messageId: "draft", bodyOffset },
          })
        ).content[0].text,
      );
    const first = await read(0);
    assert.equal(first.internetMessageId, null);
    assert.equal(first.identityComplete, false);
    assert.equal(first.body.content.length, 30000);
    assert.equal(first.nextBodyOffset, 30000);
    const last = await read(first.nextBodyOffset);
    assert.equal(last.body.content.length, 1000);
    assert.equal(last.nextBodyOffset, null);
  } finally {
    await client.close();
    await server.close();
  }
});
