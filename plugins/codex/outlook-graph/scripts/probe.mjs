import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import { resolve } from "node:path";
const client = new Client({
  name: "outlook-graph-readonly-probe",
  version: "1.0",
});
try {
  await client.connect(
    new StdioClientTransport({
      command: process.execPath,
      args: [resolve(process.argv[2] || "scripts/launch.mjs")],
      stderr: "pipe",
    }),
  );
  const listing = await client.listTools();
  const names = listing.tools.map((t) => t.name);
  const check = await client.callTool({
    name: "connection_status",
    arguments: {},
  });
  console.log(
    JSON.stringify({
      toolCount: names.length,
      tools: names,
      connected: !check.isError,
      connectionStatus: check.content,
    }),
  );
} finally {
  await client.close();
}
