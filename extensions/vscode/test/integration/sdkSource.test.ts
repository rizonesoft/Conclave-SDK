import assert from "node:assert/strict";
import { existsSync, mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import * as vscode from "vscode";
import type { ConclaveApi } from "../../src/extension";
import { recentLog } from "../../src/host/output";
import { removeTree } from "../../src/host/removeTree";
import { SdkSourceService } from "../../src/host/sdkSource";

// Compiled to out/test/integration/: the package root is three folders up.
const root = join(__dirname, "..", "..", "..");

suite("SDK source", () => {
  let work: string;

  suiteSetup(async () => {
    const extension = vscode.extensions.getExtension<ConclaveApi>("rizonetech.conclave");
    assert.ok(extension);
    await extension.activate();
    work = mkdtempSync(join(tmpdir(), "conclave-sdk-"));
  });

  suiteTeardown(() => removeTree(work));

  const service = (development = true) => new SdkSourceService({ extensionPath: root, development });

  test("with nothing set, the development host uses the SDK checkout it runs from", async () => {
    const result = await service().resolveWith({ sdkPath: "" });
    assert.ok("ok" in result && result.label === "local Conclave-SDK (development)" && existsSync(join(result.folder, "forge.py")));
  });

  test("a packaged build with no bundle is refused, never falling back to a checkout", async () => {
    const result = await service(false).resolveWith({ sdkPath: "" });
    assert.ok("state" in result && result.state === "sdk-bundle-missing", JSON.stringify(result));
  });

  test("a set sdkPath is used when it is a checkout and refused when it is not", async () => {
    const checkout = join(work, "checkout");
    mkdirSync(join(checkout, "kits"), { recursive: true });
    writeFileSync(join(checkout, "forge.py"), "print(1)\n");
    const used = await service().resolveWith({ sdkPath: checkout });
    assert.ok("ok" in used && used.folder === checkout && used.sha === "local", JSON.stringify(used));
    const refused = await service().resolveWith({ sdkPath: join(work, "nothing-here") });
    assert.ok("state" in refused && refused.state === "sdk-path-invalid", JSON.stringify(refused));
    assert.ok(recentLog().some((line) => line.startsWith("SDK source refused: conclave.sdkPath")));
  });

  test("the extension contributes no GitHub source settings", () => {
    const contributes = vscode.extensions.getExtension("rizonetech.conclave")?.packageJSON.contributes;
    const properties = Object.keys(contributes.configuration.properties).sort();
    assert.deepEqual(properties, ["conclave.pythonPath", "conclave.sdkPath"]);
  });
});
