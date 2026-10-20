import assert from "node:assert/strict";
import { copyFileSync, mkdirSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import * as vscode from "vscode";
import type { ConclaveApi } from "../../src/extension";
import { DispatcherClient } from "../../src/host/dispatcher";
import { PythonService } from "../../src/host/python";
import { run } from "../../src/host/run";

// Workspaces are built for each run from the reviewer kit's own dispatcher and the contract's fixture pins, so no copy
// of the dispatcher is committed to drift from the kit. Compiled to out/test/integration/: the package root is three up.
const root = join(__dirname, "..", "..", "..");
const fixtures = join(root, "test", "fixtures");
const dispatcher = join(root, "..", "..", "kits", "reviewer", "templates", "scripts", "review-dispatch.py");
const oldDispatcher = join(fixtures, "dispatchers", "review-dispatch-b7c649b.py");

function workspace(base: string, name: string, script: string | undefined, pin: string | undefined): vscode.Uri {
  const folder = join(base, name);
  mkdirSync(join(folder, "scripts"), { recursive: true });
  mkdirSync(join(folder, ".conclave"), { recursive: true });
  if (script) {
    copyFileSync(script, join(folder, "scripts", "review-dispatch.py"));
  }
  if (pin) {
    copyFileSync(join(fixtures, "pins", pin), join(folder, ".conclave", "reviewers.toml"));
  }
  return vscode.Uri.file(folder);
}

suite("Workspace states", () => {
  let base: string;
  let api: ConclaveApi;

  suiteSetup(async () => {
    base = mkdtempSync(join(tmpdir(), "conclave-states-"));
    const extension = vscode.extensions.getExtension<ConclaveApi>("rizonetech.conclave");
    assert.ok(extension);
    api = await extension.activate();
  });

  suiteTeardown(() => rmSync(base, { recursive: true, force: true }));

  test("each workspace gets its state from its own dispatcher", async () => {
    const cases: [string, string | undefined, string | undefined, string][] = [
      ["shipped", dispatcher, "valid-shipped.toml", "ready"],
      ["layout", dispatcher, "valid-inline-layout.toml", "pin-layout"],
      ["refused", dispatcher, "refused-same-family.toml", "refused"],
      ["no-pin", dispatcher, undefined, "no-pin"],
      ["no-dispatcher", undefined, "valid-shipped.toml", "no-dispatcher"],
      ["old-dispatcher", oldDispatcher, "valid-shipped.toml", "old-dispatcher"],
    ];
    for (const [name, script, pin, want] of cases) {
      const state = await api.checkWorkspace(workspace(base, name, script, pin));
      assert.equal(state.state, want, `${name}: ${JSON.stringify(state).slice(0, 300)}`);
    }
    const refused = await api.checkWorkspace(vscode.Uri.file(join(base, "refused")));
    assert.ok(refused.state === "refused" && /of the writer's own family/.test(refused.error));
  });

  test("a pin saved while a check runs is read by the next check, and the older answer is not published", async () => {
    const folder = workspace(base, "saved-during-check", dispatcher, "valid-shipped.toml");
    const pinFile = join(folder.fsPath, ".conclave", "reviewers.toml");
    const python = new PythonService();
    // A runner the test holds open: each call waits until the test releases it, so the order is exact.
    const held: Array<{ args: string[]; release: () => void }> = [];
    const runner: typeof run = (file, args, timeoutMs, cwd) =>
      new Promise((resolve) => held.push({ args, release: () => void run(file, args, timeoutMs, cwd).then(resolve) }));
    const client = new DispatcherClient(python, runner);
    const published: string[] = [];
    const listener = client.onDidCheck(({ state }) => published.push(state.state));
    try {
      const before = client.check(folder);
      while (held.length < 1) {
        await new Promise((r) => setTimeout(r, 10));
      }
      // The first check has started (its dispatcher would read the pin now); then the pin is saved and checked again.
      held[0].release();
      const first = await before;
      assert.equal(first.state, "ready");
      copyFileSync(join(fixtures, "pins", "refused-same-family.toml"), pinFile);
      const running = client.check(folder);
      const joined = client.check(folder);
      assert.equal(running, joined, "an identical waiting request did not share the run");
      while (held.length < 2) {
        await new Promise((r) => setTimeout(r, 10));
      }
      held[1].release();
      assert.equal((await running).state, "refused");
      assert.deepEqual(published, ["ready", "refused"]);

      // The overlap itself: a check asked while another is running gets its own run, not the running one's answer.
      copyFileSync(join(fixtures, "pins", "valid-shipped.toml"), pinFile);
      const old = client.check(folder);
      while (held.length < 3) {
        await new Promise((r) => setTimeout(r, 10));
      }
      copyFileSync(join(fixtures, "pins", "refused-same-family.toml"), pinFile);
      const fresh = client.check(folder);
      assert.notEqual(old, fresh, "a check asked after the run started shared the older run");
      held[2].release();
      while (held.length < 4) {
        await new Promise((r) => setTimeout(r, 10));
      }
      held[3].release();
      assert.equal((await fresh).state, "refused");
      await old;
      assert.equal(published[published.length - 1], "refused", "an older answer was published last");
      assert.ok(!published.slice(2).includes("ready"), `the superseded run was published: ${published.join(", ")}`);
    } finally {
      listener.dispose();
      client.dispose();
      python.dispose();
    }
  });

  test("two rapid checks of one folder start one dispatcher, and each call is logged", async () => {
    const folder = workspace(base, "coalesced", dispatcher, "valid-shipped.toml");
    const before = api.recentLog().filter((l) => l.startsWith("check-pin:") && l.includes("coalesced")).length;
    const [a, b] = await Promise.all([api.checkWorkspace(folder), api.checkWorkspace(folder)]);
    assert.equal(a, b, "the second request did not share the first call");
    const after = api.recentLog().filter((l) => l.startsWith("check-pin:") && l.includes("coalesced"));
    assert.equal(after.length - before, 1, after.join("\n"));
    assert.match(after[after.length - 1], /--check-pin --json in .*coalesced: exit 0 in \d+ ms -> ready$/);
  });
});
