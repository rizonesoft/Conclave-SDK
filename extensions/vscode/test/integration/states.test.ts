import assert from "node:assert/strict";
import { copyFileSync, mkdirSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import * as vscode from "vscode";
import type { ConclaveApi } from "../../src/extension";
import { CandidateFlow, canSave, type Checked } from "../../src/core/candidate";
import { errorTarget } from "../../src/core/errorTarget";
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
    // A runner that runs the real dispatcher at once but holds its answer until the test releases it, so the first
    // check has finished reading the valid pin (its "ready" reply is in hand) before the pin is saved refused.
    const held: Array<{ done: Promise<unknown>; release: () => void }> = [];
    const runner: typeof run = (file, args, timeoutMs, cwd) => {
      const actual = run(file, args, timeoutMs, cwd);
      let release = () => undefined as void;
      const gate = new Promise<void>((r) => (release = r));
      held.push({ done: actual, release });
      return gate.then(() => actual);
    };
    const client = new DispatcherClient(python, runner);
    const published: string[] = [];
    const listener = client.onDidCheck(({ state }) => published.push(state.state));
    const until = async (count: number) => {
      while (held.length < count) {
        await new Promise((r) => setTimeout(r, 10));
      }
    };
    try {
      const before = client.check(folder);
      await until(1);
      await held[0].done;
      copyFileSync(join(fixtures, "pins", "refused-same-family.toml"), pinFile);
      const after = client.check(folder);
      assert.notEqual(before, after, "a check asked after the run started shared the older run");
      held[0].release();
      assert.equal((await before).state, "ready", "the first run did not read the valid pin");
      await until(2);
      held[1].release();
      assert.equal((await after).state, "refused");
      await new Promise((r) => setTimeout(r, 50));
      // Exactly the newer answer: the older run finished first, but a newer run was queued, so it is not published.
      assert.deepEqual(published, ["refused"]);
    } finally {
      listener.dispose();
      client.dispose();
      python.dispose();
    }
  });

  test("a bad candidate is refused within a second, and the fix is valid", async () => {
    const extension = vscode.extensions.getExtension<ConclaveApi>("rizonetech.conclave");
    assert.ok(extension);
    const folder = workspace(base, "candidate", dispatcher, "valid-shipped.toml");
    const shipped = readFileSync(join(fixtures, "pins", "valid-shipped.toml"), "utf8");
    const results: Checked[] = [];
    const flow = new CandidateFlow((text) => api.checkCandidate(folder, text), (c) => results.push(c),
      { set: (fn, ms) => setTimeout(fn, ms), clear: (h) => clearTimeout(h as NodeJS.Timeout) });
    const started = Date.now();
    flow.edit(shipped.replace('model = "gpt-6-astra"', 'model = "GPT 6"'));
    while (results.length < 1 && Date.now() - started < 5000) {
      await new Promise((r) => setTimeout(r, 20));
    }
    assert.ok(Date.now() - started < 1000, `the refusal took ${Date.now() - started} ms, not under a second`);
    assert.equal(results[0]?.state.state, "refused");
    assert.ok(results[0].state.state === "refused" && errorTarget(results[0].state.error).kind === "model");
    flow.edit(shipped);
    while (results.length < 2) {
      await new Promise((r) => setTimeout(r, 20));
    }
    assert.equal(results[1].state.state, "ready");
    assert.ok(flow.settled());
    assert.equal(canSave(flow.result(), shipped, shipped, flow.settled()), false, "valid but unchanged from disk");
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
