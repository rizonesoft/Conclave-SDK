import assert from "node:assert/strict";
import { mkdirSync, mkdtempSync, readdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import * as vscode from "vscode";
import type { ConclaveApi } from "../../src/extension";
import { KitStateService, watchedGlobs } from "../../src/host/kitState";
import { run } from "../../src/host/run";

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
    for (const name of ["repo", "explicit", "race", "config", "wordpress"]) {
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
  test("kitState: the watched paths are every kit's install surface, read from the SDK's templates", () => {
    const [top, inside, nestedTop, nested] = watchedGlobs(sdk);
    for (const name of [".agents", ".claude", ".codex", ".conclave", "scripts", "todo", "docs", "bin", "tools", "phpcs.xml.dist", "boost.json", "AGENTS.md", "artisan", ".mcp.json"]) {
      assert.ok(top.includes(name), `${name} is not watched`);
    }
    assert.deepEqual([inside, nestedTop, nested], [`${top}/**`, `*/${top}`, `*/${top}/**`]);
  });

  test("kitState: a computation an invalidation superseded runs again, and dry runs never overlap", async () => {
    const work = join(base, "race");
    mkdirSync(work);
    const folder = vscode.Uri.file(work);
    const source = { folder: sdk, label: "local Conclave-SDK (test)" };
    const python = await api.python(folder);
    assert.ok(python.ok);
    let active = 0;
    let most = 0;
    let release: (() => void) | undefined;
    let held = false;
    const service = new KitStateService({
      source: async () => source,
      python: async () => python,
      // The first dry run of the todo kit reads the folder, then holds its answer until the test releases it: that
      // answer describes the folder before the change.
      run: async (file, args, timeoutMs, cwd, options) => {
        active += 1;
        most = Math.max(most, active);
        try {
          const result = await run(file, args, timeoutMs, cwd, options);
          if (!held && args.includes("todo") && args.includes("--dry-run")) {
            held = true;
            await new Promise<void>((r) => (release = r));
          }
          return result;
        } finally {
          active -= 1;
        }
      },
    });
    try {
      const first = service.states(folder);
      while (!release) {
        await new Promise((r) => setTimeout(r, 20));
      }
      // The folder changes while the first computation is held, and the change is announced.
      assert.equal((await api.runForge(source, ["kit", work, "todo"])).kind, "ok");
      service.invalidate(folder);
      const second = service.states(folder);
      release();
      const [a, b] = await Promise.all([first, second]);
      const todo = (s: typeof a) => (s.ok ? s.kits.find((k) => k.kit === "todo")?.state : s.message);
      assert.equal(todo(a), "installed", "the superseded computation answered with the state before the change");
      assert.equal(todo(b), "installed");
      assert.equal(most, 1, "two dry runs of one folder ran at once");
    } finally {
      service.forget(folder);
      service.dispose();
    }
  });

  test("kitState: correcting a setting reads the state again", async () => {
    const work = join(base, "config");
    mkdirSync(work);
    const folder = vscode.Uri.file(work);
    const config = vscode.workspace.getConfiguration("conclave");
    await config.update("pythonPath", join(base, "no-python.exe"), vscode.ConfigurationTarget.Global);
    try {
      const broken = await api.kitStates(folder);
      assert.equal(broken.ok, false, JSON.stringify(broken));
    } finally {
      await config.update("pythonPath", undefined, vscode.ConfigurationTarget.Global);
    }
    const started = Date.now();
    let states = await api.kitStates(folder);
    while (!states.ok && Date.now() - started < 10_000) {
      await new Promise((r) => setTimeout(r, 200));
      states = await api.kitStates(folder);
    }
    assert.ok(states.ok, `the failure stayed cached after the setting was corrected: ${JSON.stringify(states)}`);
  });

  test("kitState: removing a file only the WordPress kit installs makes it partly installed", async () => {
    const work = join(base, "wordpress");
    mkdirSync(work);
    const folder = vscode.Uri.file(work);
    const source = { folder: sdk, label: "local Conclave-SDK (test)" };
    assert.equal((await api.runForge(source, ["init", work, "--kit", "wordpress"])).kind, "ok");
    const before = await api.kitStates(folder);
    assert.ok(before.ok && before.kits.find((k) => k.kit === "wordpress")?.state === "installed", JSON.stringify(before));
    await new Promise((r) => setTimeout(r, 1000));
    let events = 0;
    const listener = api.onDidChangeKitState((changed) => void (changed.fsPath === folder.fsPath && (events += 1)));
    try {
      const bin = join(work, "bin");
      rmSync(join(bin, readdirSync(bin)[0]));
      const started = Date.now();
      while (events === 0 && Date.now() - started < 10_000) {
        await new Promise((r) => setTimeout(r, 100));
      }
      assert.ok(events > 0, "deleting a bin/ file did not change the kit state");
    } finally {
      listener.dispose();
    }
    const after = await api.kitStates(folder);
    assert.ok(after.ok && after.kits.find((k) => k.kit === "wordpress")?.state === "partly", JSON.stringify(after));
  });
});
