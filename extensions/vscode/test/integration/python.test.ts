import assert from "node:assert/strict";
import * as vscode from "vscode";
import type { ConclaveApi } from "../../src/extension";
import type { PythonResolution } from "../../src/host/python";

function next(api: ConclaveApi): Promise<PythonResolution> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("no Python resolution within 15 s")), 15_000);
    const listener = api.onDidResolvePython((result) => {
      clearTimeout(timer);
      listener.dispose();
      resolve(result);
    });
  });
}

suite("Python resolution", () => {
  test("resolves Python 3.11 or later on this host, and again when conclave.pythonPath changes", async () => {
    const extension = vscode.extensions.getExtension<ConclaveApi>("rizonetech.conclave");
    assert.ok(extension);
    const api = await extension.activate();
    const first = await api.python();
    assert.ok(first.ok, first.ok ? "" : first.message);
    const [major, minor] = first.version.split(".").map(Number);
    assert.ok(major > 3 || (major === 3 && minor >= 11), first.version);

    const config = vscode.workspace.getConfiguration("conclave");
    const bad = process.platform === "win32" ? "C:\\no\\such\\python.exe" : "/no/such/python3";
    try {
      const refused = next(api);
      await config.update("pythonPath", bad, vscode.ConfigurationTarget.Global);
      const result = await refused;
      assert.ok(!result.ok, "a bad conclave.pythonPath resolved");
      assert.equal(result.fromSetting, true);
      assert.match(result.message, /conclave\.pythonPath is set but cannot be used/);
    } finally {
      const restored = next(api);
      await config.update("pythonPath", undefined, vscode.ConfigurationTarget.Global);
      assert.ok((await restored).ok, "clearing the setting did not resolve a Python again");
    }
  });
});
