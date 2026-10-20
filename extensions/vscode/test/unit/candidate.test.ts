import assert from "node:assert/strict";
import { existsSync, mkdtempSync, readdirSync, rmSync, utimesSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { mock, test } from "node:test";
import { CandidateFlow, canSave, type Checked } from "../../src/core/candidate";
import type { WorkspaceState } from "../../src/core/checkPin";
import { sweepCandidates, withCandidate } from "../../src/host/candidate";

const READY: WorkspaceState = { state: "ready", report: { ok: true, schema_version: 1, reviewers: {}, routes: {}, clis: {} } };
const REFUSED: WorkspaceState = { state: "refused", error: "reviewer 'astra' has a malformed model" };

test("candidate: edits within 300 ms check once, the newest text", () => {
  mock.timers.enable({ apis: ["setTimeout"] });
  try {
    const checked: string[] = [];
    const flow = new CandidateFlow(async (text) => (checked.push(text), READY), () => undefined,
      { set: (fn, ms) => setTimeout(fn, ms), clear: (h) => clearTimeout(h as NodeJS.Timeout) });
    flow.edit("a");
    mock.timers.tick(100);
    flow.edit("ab");
    mock.timers.tick(299);
    assert.deepEqual(checked, []);
    mock.timers.tick(1);
    assert.deepEqual(checked, ["ab"]);
  } finally {
    mock.timers.reset();
  }
});

test("candidate: a result for an older edit that arrives late is discarded", async () => {
  mock.timers.enable({ apis: ["setTimeout"] });
  try {
    const answers = new Map<string, (state: WorkspaceState) => void>();
    const applied: Checked[] = [];
    const flow = new CandidateFlow((text) => new Promise((resolve) => answers.set(text, resolve)), (c) => applied.push(c),
      { set: (fn, ms) => setTimeout(fn, ms), clear: (h) => clearTimeout(h as NodeJS.Timeout) });
    flow.edit("old");
    mock.timers.tick(300);
    flow.edit("new");
    mock.timers.tick(300);
    answers.get("new")?.(REFUSED);
    await new Promise((r) => setImmediate(r));
    answers.get("old")?.(READY);
    await new Promise((r) => setImmediate(r));
    assert.deepEqual(applied, [{ text: "new", state: REFUSED }]);
    assert.deepEqual(flow.result(), { text: "new", state: REFUSED });
  } finally {
    mock.timers.reset();
  }
});

test("candidate: Save is on only for a valid, current candidate that differs from disk", () => {
  assert.equal(canSave(undefined, "x", "y"), false, "no check yet");
  assert.equal(canSave({ text: "x", state: REFUSED }, "x", "y"), false, "refused");
  assert.equal(canSave({ text: "x", state: READY }, "x", "x"), false, "valid but unchanged");
  assert.equal(canSave({ text: "x", state: READY }, "x", "y"), true, "valid and changed");
  assert.equal(canSave({ text: "x", state: READY }, "xy", "y"), false, "the check is for an older edit");
});

test("candidate: 50 checks leave no candidate file, even when a check throws", async () => {
  const dir = mkdtempSync(join(tmpdir(), "conclave-candidates-"));
  try {
    for (let i = 0; i < 50; i += 1) {
      const seen = await withCandidate(`schema_version = ${i}\n`, async (path) => existsSync(path), dir);
      assert.ok(seen);
    }
    await assert.rejects(withCandidate("x", async () => {
      throw new Error("check failed");
    }, dir));
    assert.deepEqual(readdirSync(dir), []);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("candidate: the activation sweep removes only candidate files older than a day", () => {
  const dir = mkdtempSync(join(tmpdir(), "conclave-sweep-"));
  try {
    const old = Date.now() / 1000 - 2 * 24 * 60 * 60;
    for (const name of ["pin-1-1.toml", "pin-2-9.toml", "notes.txt"]) {
      writeFileSync(join(dir, name), "x");
    }
    utimesSync(join(dir, "pin-1-1.toml"), old, old);
    utimesSync(join(dir, "notes.txt"), old, old);
    assert.equal(sweepCandidates(dir), 1);
    assert.deepEqual(readdirSync(dir).sort(), ["notes.txt", "pin-2-9.toml"]);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
