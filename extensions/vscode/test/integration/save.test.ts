import assert from "node:assert/strict";
import { chmodSync, copyFileSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import * as vscode from "vscode";
import type { ConclaveApi } from "../../src/extension";

// Each test saves into its own copy of the shipped fixture workspace, with the reviewer kit's own dispatcher so the
// re-check is the real --check-pin. Compiled to out/test/integration/: the package root is three up.
const root = join(__dirname, "..", "..", "..");
const fixtures = join(root, "test", "fixtures");
const dispatcher = join(root, "..", "..", "kits", "reviewer", "templates", "scripts", "review-dispatch.py");
const OTHER = "# written by another program\n";

suite("save", () => {
  let base: string;
  let api: ConclaveApi;
  let count = 0;
  const sessions: vscode.Disposable[] = [];

  suiteSetup(async () => {
    base = mkdtempSync(join(tmpdir(), "conclave-save-"));
    const extension = vscode.extensions.getExtension<ConclaveApi>("rizonetech.conclave");
    assert.ok(extension);
    api = await extension.activate();
  });

  // Each session's watcher holds its folder open on Windows: disposed before the folders are removed.
  teardown(() => sessions.splice(0).forEach((s) => s.dispose()));
  suiteTeardown(() => rmSync(base, { recursive: true, force: true }));

  function open(folder: vscode.Uri, hooks?: Parameters<ConclaveApi["openPin"]>[1]): ReturnType<ConclaveApi["openPin"]> {
    const session = api.openPin(folder, hooks);
    sessions.push(session);
    return session;
  }

  function copy(): { folder: vscode.Uri; pin: string; shipped: string } {
    count += 1;
    const folder = join(base, `w${count}`);
    mkdirSync(join(folder, "scripts"), { recursive: true });
    mkdirSync(join(folder, ".conclave"), { recursive: true });
    copyFileSync(dispatcher, join(folder, "scripts", "review-dispatch.py"));
    const pin = join(folder, ".conclave", "reviewers.toml");
    copyFileSync(join(fixtures, "workspaces", "shipped", ".conclave", "reviewers.toml"), pin);
    return { folder: vscode.Uri.file(folder), pin, shipped: readFileSync(pin, "utf8") };
  }

  function temps(pin: string): string[] {
    return readdirSync(join(pin, "..")).filter((n) => n.endsWith(".tmp"));
  }

  test("save: an edit is written through a temporary file, read back byte for byte, and re-checked", async () => {
    const { folder, pin, shipped } = copy();
    const session = open(folder);
    assert.equal(await session.load(), shipped);
    assert.ok(api.recentLog().some((l) => l.startsWith("Loaded .conclave/reviewers.toml") && /sha256 [0-9a-f]{16}/.test(l)));
    const edited = `${shipped}# edited in the editor, ünïcode kept\n`;
    const checksBefore = api.recentLog().filter((l) => l.startsWith("check-pin:") && l.includes(folder.fsPath)).length;
    const result = await session.save(edited);
    assert.equal(result.kind, "saved", JSON.stringify(result));
    assert.ok(result.kind === "saved" && result.state.state === "ready");
    assert.equal(result.message, "Saved .conclave/reviewers.toml through a temporary file and a rename. Re-checked with --check-pin: ok.");
    assert.deepEqual(readFileSync(pin), Buffer.from(edited, "utf8"));
    assert.deepEqual(temps(pin), []);
    const checksAfter = api.recentLog().filter((l) => l.startsWith("check-pin:") && l.includes(folder.fsPath)).length;
    assert.equal(checksAfter - checksBefore, 1, "no check was logged after the save");
    // The saved text is now the loaded text: a second save needs no reload.
    assert.equal((await session.save(shipped)).kind, "saved");
    assert.equal(session.discard(), shipped);
  });

  test("save: a pin changed on disk since load is stale, and the other program's text is kept", async () => {
    const { folder, pin, shipped } = copy();
    const session = open(folder);
    await session.load();
    writeFileSync(pin, OTHER);
    const result = await session.save(`${shipped}# mine\n`);
    assert.equal(result.kind, "stale", JSON.stringify(result));
    assert.equal(readFileSync(pin, "utf8"), OTHER);
    assert.deepEqual(temps(pin), []);
    assert.ok(session.stale);
  });

  test("save: a pin changed while the temporary file was written is stale", async () => {
    const { folder, pin, shipped } = copy();
    const session = open(folder, { afterWrite: async () => writeFileSync(pin, OTHER) });
    await session.load();
    const result = await session.save(`${shipped}# mine\n`);
    assert.equal(result.kind, "stale", JSON.stringify(result));
    assert.equal(readFileSync(pin, "utf8"), OTHER);
    assert.deepEqual(temps(pin), []);
  });

  test("save: a pin changed during a retry wait is stale, and a held pin is retried three times", async () => {
    const { folder, pin, shipped } = copy();
    const busy = () => Promise.reject(Object.assign(new Error("EBUSY: resource busy"), { code: "EBUSY" }));
    const session = open(folder, { rename: busy, delay: async () => writeFileSync(pin, OTHER) });
    await session.load();
    const result = await session.save(`${shipped}# mine\n`);
    assert.equal(result.kind, "stale", JSON.stringify(result));
    assert.equal(readFileSync(pin, "utf8"), OTHER);
    assert.deepEqual(temps(pin), []);

    const held = copy();
    let waits = 0;
    const always = open(held.folder, { rename: busy, delay: async () => void (waits += 1) });
    await always.load();
    const failed = await always.save(`${held.shipped}# mine\n`);
    assert.equal(failed.kind, "failed", JSON.stringify(failed));
    assert.match(failed.message, /held open by another program, so it was not saved after 3 retries/);
    assert.equal(waits, 3);
    assert.equal(readFileSync(held.pin, "utf8"), held.shipped);
    assert.deepEqual(temps(held.pin), []);
  });

  test("save: a read-only pin is refused and left untouched", async () => {
    const { folder, pin, shipped } = copy();
    const session = open(folder);
    await session.load();
    chmodSync(pin, 0o444);
    try {
      const result = await session.save(`${shipped}# mine\n`);
      assert.equal(result.kind, "read-only", JSON.stringify(result));
      assert.match(result.message, /is read-only, so it was not saved/);
      assert.equal(readFileSync(pin, "utf8"), shipped);
      assert.deepEqual(temps(pin), []);
    } finally {
      chmodSync(pin, 0o644);
    }
  });

  test("save: a saved pin the dispatcher refuses stays saved, with the refusal as the new state", async () => {
    const { folder, pin } = copy();
    const session = open(folder);
    await session.load();
    const refused = readFileSync(join(fixtures, "pins", "refused-same-family.toml"), "utf8");
    const result = await session.save(refused);
    assert.equal(result.kind, "saved", JSON.stringify(result));
    assert.ok(result.kind === "saved" && result.state.state === "refused");
    assert.match(result.message, /^Saved, but --check-pin now refuses the pin: /);
    assert.equal(readFileSync(pin, "utf8"), refused);
  });

  test("save: discard returns to the loaded text, and reload takes an outside change the watcher saw", async () => {
    const { folder, pin, shipped } = copy();
    const session = open(folder);
    await session.load();
    assert.equal(session.discard(), shipped);
    const seen = new Promise<boolean>((resolve) => {
      const listener = session.onDidChangeStale((stale) => {
        listener.dispose();
        resolve(stale);
      });
    });
    // VS Code starts a watcher asynchronously, and a write before it runs is not reported: the outside program writes
    // every 250 ms until the watcher sees one, as a real outside edit comes long after the editor opened. Only the
    // watcher sets stale here (nothing is saved), so stale proves it saw the change.
    let seenStale: boolean | undefined;
    void seen.then((stale) => (seenStale = stale));
    for (let waited = 0; seenStale === undefined && waited < 5000; waited += 250) {
      writeFileSync(pin, OTHER);
      await new Promise((r) => setTimeout(r, 250));
    }
    assert.equal(seenStale, true, "no watcher event in 5 s");
    assert.ok(session.stale);
    assert.equal(session.discard(), shipped, "discard read the disk");
    assert.equal(await session.reload(), OTHER);
    assert.equal(session.stale, false);
    assert.equal(session.discard(), OTHER);
  });
});
