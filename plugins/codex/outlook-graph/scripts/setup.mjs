import { createInterface } from "node:readline/promises";
import { stdin, stdout } from "node:process";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { createStore } from "../src/store.js";
import { login, tokenProvider } from "../src/auth.js";
import { GraphClient, GraphError } from "../src/client.js";
const exec = promisify(execFile);
const guid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const command = process.argv[2] || "status";
try {
  const store = createStore();
  if (command === "status") console.log(JSON.stringify(await store.status()));
  else if (command === "check") {
    const client = new GraphClient(tokenProvider(store));
    await client.me();
    await client.folder("inbox");
    const c = await client.categories();
    console.log(
      JSON.stringify({
        connected: true,
        inboxReadable: true,
        tickTickCategoryFound: c.items.some(
          (x) => x.displayName === "TickTick",
        ),
        onePasswordRuntimeAccess: false,
      }),
    );
  } else if (command === "login" || command === "import-config") {
    if (!stdin.isTTY)
      throw new GraphError(
        "Run interactive setup in your own terminal. Tokens and sign-in codes must not be passed in arguments.",
      );
    let config = {};
    if (command === "import-config") {
      // Explicit setup only. Never called by the MCP server or token provider.
      const binary =
        process.platform === "win32"
          ? "op"
          : process.env.WSL_DISTRO_NAME
            ? "/home/derickpayne/.local/bin/conclave-op"
            : "op";
      let result;
      try {
        result = await exec(
          binary,
          [
            "item",
            "get",
            "Codex Outlook Graph",
            "--vault",
            "Conclave",
            "--format=json",
          ],
          { windowsHide: true, timeout: 45000, maxBuffer: 262144 },
        );
      } catch {
        throw new GraphError(
          "Cannot import Codex Outlook Graph from Conclave. Existing session unchanged.",
        );
      }
      const item = JSON.parse(result.stdout);
      for (const name of ["clientId", "tenantId", "mailbox"])
        config[name] = item.fields?.find(
          (f) => f.label === name || f.id === name,
        )?.value;
    }
    const rl = createInterface({ input: stdin, output: stdout });
    try {
      for (const name of ["tenantId", "clientId", "mailbox"])
        if (!config[name])
          config[name] = (await rl.question(name + " (non-secret): ")).trim();
    } finally {
      rl.close();
    }
    if (
      !guid.test(config.clientId) ||
      !guid.test(config.tenantId) ||
      !/^\S+@\S+\.\S+$/.test(config.mailbox)
    )
      throw new GraphError(
        "Use the dedicated application and directory GUIDs and your mailbox address.",
      );
    console.log(
      "Requested delegated access: User.Read, Mail.ReadWrite, MailboxSettings.Read. No Mail.Send.",
    );
    console.log(
      JSON.stringify(
        await login(store, config, (code) => console.log(code.message)),
      ),
    );
  } else throw new GraphError("Use status, check, login or import-config.");
} catch (e) {
  console.error(
    e instanceof GraphError
      ? e.message
      : "Setup failed. No credential values were printed.",
  );
  process.exitCode = 1;
}
