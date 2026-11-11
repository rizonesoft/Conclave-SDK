import { readdirSync, existsSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";

// Own runtime selection here because noninteractive WSL does not load nvm.
let runtime = process.execPath;
if (Number(process.versions.node.split(".")[0]) < 22) {
  const root = join(homedir(), ".nvm", "versions", "node");
  let versions = [];
  try {
    versions = readdirSync(root)
      .filter(
        (v) =>
          /^v\d+\.\d+\.\d+$/.test(v) && Number(v.slice(1).split(".")[0]) >= 22,
      )
      .sort((a, b) => b.localeCompare(a, undefined, { numeric: true }));
  } catch (e) {
    if (e.code !== "ENOENT") {
      process.stderr.write(
        "Cannot inspect the nvm runtime directory. Check its access permissions.\n",
      );
      process.exit(1);
    }
  }
  runtime = versions.map((v) => join(root, v, "bin", "node")).find(existsSync);
  if (!runtime) {
    process.stderr.write(
      "Outlook Graph requires Node.js 22 or newer on PATH or installed with nvm.\n",
    );
    process.exit(1);
  }
}
const child = spawn(
  runtime,
  [fileURLToPath(new URL("../dist/server.mjs", import.meta.url))],
  { stdio: "inherit", windowsHide: true },
);
child.on("error", () => {
  process.stderr.write("Outlook Graph runtime could not start.\n");
  process.exitCode = 1;
});
child.on("exit", (code) => {
  process.exitCode = code ?? 1;
});
for (const signal of ["SIGINT", "SIGTERM"])
  process.on(signal, () => child.kill(signal));
