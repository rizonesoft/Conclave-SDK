import assert from "node:assert/strict";
import { mkdirSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import * as vscode from "vscode";
import type { ConclaveApi } from "../../src/extension";

// Kit state from the real forge.py of this SDK (conclave.sdkPath set to the repository root for the suite).
const root = join(__dirname, "..", "..", "..");
const sdk = join(root, "..", "..");

suite("kitState", () => {
  let base: string;
  let api: ConclaveApi;

  suiteSetup(async () => {
    base = mkdtempSync(join(tmpdir(), "conclave-kitstate-"));
    const extension = vscode.extensions.getExtension<ConclaveApi>("rizonetech.conclave");
    assert.ok(extension);
    api = await extension.activate();
    await vscode.workspace.getConfiguration("conclave").update("sdkPath", sdk, vscode.ConfigurationTarget.Global);
  });

  suiteTeardown(async () => {
    await vscode.workspace.getConfiguration("conclave").update("sdkPath", undefined, vscode.ConfigurationTarget.Global);
    // The folders leave: their watchers let go of them, so they can be removed.
    for (const name of ["repo", "explicit"]) {
      api.forgetKitState(vscode.Uri.file(join(base, name)));
    }
    await new Promise((r) => setTimeout(r, 500));
    rmSync(base, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
  });

  const forgeRuns = () => api.recentLog().filter((l) => l.startsWith("forge: ")).length;

  test("kitState: every kit's state, cached until the folder changes, with one event after an install", async () => {
    const work = join(base, "repo");
    mkdirSync(work);
    const folder = vscode.Uri.file(work);
    const source = { folder: sdk, label: "local Conclave-SDK (test)" };
    const init = await api.runForge(source, ["init", work]);
    assert.equal(init.kind, "ok", JSON.stringify(init));

    const first = await api.kitStates(folder);
    assert.ok(first.ok, JSON.stringify(first));
    const byKit = Object.fromEntries(first.kits.map((k) => [k.kit, k.state]));
    assert.equal(byKit.base, "installed");
    assert.equal(byKit.todo, "not-installed");
    assert.equal(byKit.reviewer, "not-installed");
    assert.equal(byKit.laravel, "unavailable");
    const laravel = first.kits.find((k) => k.kit === "laravel");
    assert.ok(laravel?.state === "unavailable" && /artisan/.test(laravel.reason), JSON.stringify(laravel));

    // A second read is the cache: no forge run.
    const runs = forgeRuns();
    assert.deepEqual(await api.kitStates(folder), first);
    assert.equal(forgeRuns(), runs, "the second read ran forge");

    // Installing a kit writes many files; the watcher gives one event once they settle.
    await new Promise((r) => setTimeout(r, 1000));
    let events = 0;
    const listener = api.onDidChangeKitState((changed) => {
      if (changed.fsPath === folder.fsPath) {
        events += 1;
      }
    });
    try {
      const install = await api.runForge(source, ["kit", work, "todo"]);
      assert.equal(install.kind, "ok", JSON.stringify(install));
      const started = Date.now();
      while (events === 0 && Date.now() - started < 10_000) {
        await new Promise((r) => setTimeout(r, 100));
      }
      await new Promise((r) => setTimeout(r, 1000));
      assert.equal(events, 1, `${events} events after one install`);
    } finally {
      listener.dispose();
    }
    const before = forgeRuns();
    const after = await api.kitStates(folder);
    assert.ok(after.ok && after.kits.find((k) => k.kit === "todo")?.state === "installed", JSON.stringify(after));
    assert.ok(forgeRuns() > before, "the state after the install came from the cache");
  });

  test("kitState: a kit operation's invalidate reads the state again", async () => {
    const work = join(base, "explicit");
    mkdirSync(work);
    const folder = vscode.Uri.file(work);
    await api.kitStates(folder);
    const runs = forgeRuns();
    let fired = false;
    const listener = api.onDidChangeKitState(() => (fired = true));
    try {
      api.invalidateKitState(folder);
      const started = Date.now();
      while (!fired && Date.now() - started < 5000) {
        await new Promise((r) => setTimeout(r, 50));
      }
      assert.ok(fired, "no event after invalidate");
    } finally {
      listener.dispose();
    }
    await api.kitStates(folder);
    assert.ok(forgeRuns() > runs, "invalidate did not drop the cache");
  });
});
