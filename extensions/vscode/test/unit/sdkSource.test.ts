import assert from "node:assert/strict";
import { posix } from "node:path";
import { test } from "node:test";
import { bundledSource, chooseSource } from "../../src/core/sdkSource";

const checkout = (path: string) => path === "R:\\GitHub\\Conclave-SDK";

test("sdkSource: a set sdkPath wins, and an unusable one is refused, never passed over", () => {
  assert.deepEqual(chooseSource({ sdkPath: "R:\\GitHub\\Conclave-SDK" }, checkout), { kind: "path", path: "R:\\GitHub\\Conclave-SDK" });
  const bad = chooseSource({ sdkPath: "R:\\elsewhere" }, checkout);
  assert.deepEqual(bad, { state: "sdk-path-invalid", message: "conclave.sdkPath is not a Conclave-SDK checkout." });
});

test("sdkSource: nothing set, or a blank sdkPath, is the bundle", () => {
  assert.deepEqual(chooseSource({ sdkPath: "" }, checkout), { kind: "bundled" });
  assert.deepEqual(chooseSource({ sdkPath: "   " }, checkout), { kind: "bundled" });
});

test("sdkSource: the bundle when packaged, the checkout in development, and a refusal when a packaged build has none", () => {
  const sha = "a".repeat(40);
  const probe = (folders: string[], commit?: string) => ({
    isSdkFolder: (p: string) => folders.includes(p),
    readCommit: () => commit,
    join: posix.join,
  });
  assert.deepEqual(bundledSource("/ext", false, probe(["/ext/sdk"], sha)),
    { ok: true, folder: "/ext/sdk", sha, label: `bundled Conclave-SDK@${sha.slice(0, 7)}` });
  const dev = bundledSource("/r/sdk/extensions/vscode", true, probe(["/r/sdk"]));
  assert.ok("ok" in dev && dev.label === "local Conclave-SDK (development)" && dev.sha === "local");
  const packaged = bundledSource("/r/sdk/extensions/vscode", false, probe(["/r/sdk"]));
  assert.ok("state" in packaged && packaged.state === "sdk-bundle-missing" && !/sdkRef|GitHub/.test(packaged.message),
    "a packaged build must not fall back to a checkout, and names no GitHub source");
  assert.equal((bundledSource("/ext", false, probe(["/ext/sdk"], "not-a-sha")) as { state: string }).state, "sdk-bundle-missing");
});
