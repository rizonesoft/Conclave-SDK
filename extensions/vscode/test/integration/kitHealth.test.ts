import assert from "node:assert/strict";
import { chmodSync, mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { delimiter, join } from "node:path";
import * as vscode from "vscode";
import type { ConclaveApi } from "../../src/extension";
import { KitHealthService } from "../../src/host/kitHealth";
import { KitStateService } from "../../src/host/kitState";
import { run, running } from "../../src/host/run";
import { removeTree } from "../../src/host/removeTree";
import { forgeFixture } from "./forgeFixture";

// Kit health from this SDK's own forge.py (conclave.sdkPath set to the repository root), with stub reviewer CLIs first
// on PATH so the reviewer doctor's answer does not depend on what this machine has installed.
const root = join(__dirname, "..", "..", "..");
const sdk = join(root, "..", "..");
const checkFixture = join(root, "test", "fixtures", "forge", "health-check.json");

// A fake SDK whose doctor for the "slow" kit never answers.
const FAKE_FORGE = `
import json, os, sys, time
a = sys.argv[1:]
if a[0] == "kits":
    print(json.dumps({"kits": ["base", "reviewer", "slow"]}))
elif a[0] == "kit":
    print(json.dumps({"target": a[1], "kit": a[2], "agent": "all", "dry_run": True, "installed": [], "updated": [], "preserved": ["x"], "merge_needed": []}))
elif a[0] == "check":
    print(open(${JSON.stringify(checkFixture)}, encoding="utf-8").read())
elif a[0] == "doctor":
    if a[2] == "slow":
        open(os.environ["CONCLAVE_SLOW_PID"], "w").write(str(os.getpid()))
        time.sleep(600)
    print(json.dumps({"target": a[1], "kit": a[2], "missing_or_setup_required": 0, "checks": [{"name": "x", "status": "ok", "detail": "x"}]}))
`;

suite("kitHealth", () => {
  let base: string;
  let api: ConclaveApi;
  let path: string | undefined;

  suiteSetup(async () => {
    base = mkdtempSync(join(tmpdir(), "conclave-kithealth-"));
    const extension = vscode.extensions.getExtension<ConclaveApi>("rizonetech.conclave");
    assert.ok(extension);
    api = await extension.activate();
    await vscode.workspace.getConfiguration("conclave").update("sdkPath", sdk, vscode.ConfigurationTarget.Global);
    const bin = join(base, "bin");
    mkdirSync(bin);
    for (const cli of ["codex", "agy", "claude"]) {
      const stub = join(bin, process.platform === "win32" ? `${cli}.cmd` : cli);
      writeFileSync(stub, process.platform === "win32" ? "@exit /b 0\r\n" : "#!/bin/sh\nexit 0\n");
      chmodSync(stub, 0o755);
    }
    path = process.env.PATH;
    process.env.PATH = `${bin}${delimiter}${path ?? ""}`;
  });

  suiteTeardown(async () => {
    process.env.PATH = path;
    await vscode.workspace.getConfiguration("conclave").update("sdkPath", undefined, vscode.ConfigurationTarget.Global);
    for (const name of ["reviewer", "slow", "away"]) {
      api.forgetKitState(vscode.Uri.file(join(base, name)));
    }
    await new Promise((r) => setTimeout(r, 500));
    removeTree(base);
  });

  test("kitHealth: an installed reviewer kit with its CLIs is healthy, and health is read again after an install", async () => {
    const work = join(base, "reviewer");
    mkdirSync(work);
    const folder = vscode.Uri.file(work);
    await forgeFixture(api, sdk, ["init", work, "--kit", "reviewer"]);
    const health = await api.kitHealth(folder);
    assert.ok(health.ok, JSON.stringify(health));
    const reviewer = health.kits.find((k) => k.kit === "reviewer");
    assert.ok(reviewer?.state === "checked" && reviewer.problems === 0, JSON.stringify(reviewer));
    assert.ok(reviewer.state === "checked" && reviewer.checks.some((c) => c.name === "reviewer:gemini" && c.status === "ok"));
    assert.equal(health.kits.some((k) => k.kit === "todo"), false, "doctor ran for a kit that is not installed");

    await new Promise((r) => setTimeout(r, 1000));
    let refreshed = false;
    const listener = api.onDidChangeKitHealth((changed) => void (changed.fsPath === folder.fsPath && (refreshed = true)));
    try {
      await forgeFixture(api, sdk, ["kit", work, "todo"]);
      const started = Date.now();
      while (!refreshed && Date.now() - started < 10_000) {
        await new Promise((r) => setTimeout(r, 100));
      }
      assert.ok(refreshed, "health was not refreshed after an install");
    } finally {
      listener.dispose();
    }
    const after = await api.kitHealth(folder);
    assert.ok(after.ok && after.kits.some((k) => k.kit === "todo" && k.state === "checked"), JSON.stringify(after));
  });

  test("kitHealth: a doctor past its timeout makes that kit unavailable, and the others are still reported", async () => {
    const fakeSdk = join(base, "fake-sdk");
    mkdirSync(join(fakeSdk, "kits"), { recursive: true });
    writeFileSync(join(fakeSdk, "forge.py"), FAKE_FORGE);
    const work = join(base, "slow");
    mkdirSync(work);
    const folder = vscode.Uri.file(work);
    const python = await api.python(folder);
    assert.ok(python.ok);
    const source = { folder: fakeSdk, label: "fake SDK" };
    const pidFile = join(base, "slow.pid");
    process.env.CONCLAVE_SLOW_PID = pidFile;
    const states = new KitStateService({ source: async () => source, python: async () => python });
    const health = new KitHealthService({
      kitStates: (f) => states.states(f), onDidChangeKitState: states.onDidChangeKitState,
      source: async () => source, python: async () => python, doctorTimeoutMs: 3000,
    });
    try {
      const result = await health.health(folder);
      assert.ok(result.ok, JSON.stringify(result));
      assert.deepEqual(result.kits.map((k) => [k.kit, k.state]), [["base", "checked"], ["reviewer", "checked"], ["slow", "unavailable"]]);
      const slow = result.kits.find((k) => k.kit === "slow");
      assert.ok(slow?.state === "unavailable" && /timed out after 3 s/.test(slow.reason), JSON.stringify(slow));
      const { readFileSync } = await import("node:fs");
      assert.equal(running(Number(readFileSync(pidFile, "utf8"))), false, "the slow doctor is still running");
    } finally {
      delete process.env.CONCLAVE_SLOW_PID;
      states.forget(folder);
      health.dispose();
      states.dispose();
    }
  });
  test("kitHealth: a folder that left and came back gets fresh health, not what was cached before it left", async () => {
    const work = join(base, "away");
    mkdirSync(work);
    const folder = vscode.Uri.file(work);
    await forgeFixture(api, sdk, ["init", work, "--kit", "reviewer"]);
    const before = await api.kitHealth(folder);
    assert.ok(before.ok && !before.kits.some((k) => k.kit === "todo"), JSON.stringify(before));
    // The folder leaves (its watchers go with it), changes while it is away, and comes back.
    api.forgetKitState(folder);
    await forgeFixture(api, sdk, ["kit", work, "todo"]);
    const after = await api.kitHealth(folder);
    assert.ok(after.ok && after.kits.some((k) => k.kit === "todo"), `the health from before the folder left came back: ${JSON.stringify(after)}`);
  });
  test("kitHealth: a computation for a folder that left stops, and never reads the folder again", async () => {
    const work = join(base, "away");
    const folder = vscode.Uri.file(work);
    const python = await api.python();
    assert.ok(python.ok);
    let reads = 0;
    let doctors = 0;
    let release: (() => void) | undefined;
    const forgetting = new vscode.EventEmitter<vscode.Uri>();
    const health = new KitHealthService({
      // Two installed kits, so a computation that went on after the forget would start their doctors.
      kitStates: async () => (reads += 1, { ok: true, kits: [{ kit: "base", state: "installed", kept: 1, stamp: "none" }, { kit: "todo", state: "installed", kept: 1, stamp: "none" }] }),
      onDidChangeKitState: new vscode.EventEmitter<vscode.Uri>().event,
      onDidForget: forgetting.event,
      source: async () => ({ folder: sdk, label: "local Conclave-SDK (test)" }),
      python: async () => python,
      // forge check is held until the folder has left.
      run: async (file, args, timeoutMs, cwd, options) => {
        if (args.includes("doctor")) {
          doctors += 1;
        }
        const result = await run(file, args, timeoutMs, cwd, options);
        if (args.includes("check")) {
          await new Promise<void>((r) => (release = r));
        }
        return result;
      },
    });
    try {
      const reading = health.health(folder);
      while (!release) {
        await new Promise((r) => setTimeout(r, 20));
      }
      forgetting.fire(folder);
      const doctorsAtForget = doctors;
      release();
      assert.deepEqual(await reading, { ok: false, message: "the folder is no longer watched" });
      assert.equal(reads, 1, "the computation read the folder again after it left");
      assert.equal(doctors, doctorsAtForget, "a doctor started for a folder that had left");
    } finally {
      health.dispose();
      forgetting.dispose();
    }
  });
  test("kitHealth: a read asked before the forget answers for the forgotten lifetime, and one asked after for the new one", async () => {
    const work = join(base, "away");
    const folder = vscode.Uri.file(work);
    const python = await api.python();
    assert.ok(python.ok);
    let checks = 0;
    let release: (() => void) | undefined;
    const forgetting = new vscode.EventEmitter<vscode.Uri>();
    const health = new KitHealthService({
      kitStates: async () => ({ ok: true, kits: [{ kit: "base", state: "installed", kept: 1, stamp: "none" }] }),
      onDidChangeKitState: new vscode.EventEmitter<vscode.Uri>().event,
      onDidForget: forgetting.event,
      source: async () => ({ folder: sdk, label: "local Conclave-SDK (test)" }),
      python: async () => python,
      // Only the first forge check is held, until the test releases it.
      run: async (file, args, timeoutMs, cwd, options) => {
        const result = await run(file, args, timeoutMs, cwd, options);
        if (args.includes("check") && ++checks === 1) {
          await new Promise<void>((r) => (release = r));
        }
        return result;
      },
    });
    try {
      const first = health.health(folder);
      while (!release) {
        await new Promise((r) => setTimeout(r, 20));
      }
      // Queued behind the held computation, then the folder leaves and is asked about again under a new lifetime.
      health.refresh(folder);
      const queued = health.health(folder);
      forgetting.fire(folder);
      const again = health.health(folder);
      release();
      const left = { ok: false, message: "the folder is no longer watched" };
      assert.deepEqual(await first, left);
      assert.deepEqual(await queued, left, "a read asked before the forget answered for the new lifetime");
      const after = await again;
      assert.ok(after.ok, JSON.stringify(after));
      // The held computation and the new lifetime's: the queued read started no computation of its own.
      assert.equal(checks, 2);
    } finally {
      health.dispose();
      forgetting.dispose();
    }
  });
});
