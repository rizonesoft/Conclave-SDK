import assert from "node:assert/strict";
import { existsSync, mkdirSync, mkdtempSync, readdirSync, rmSync, utimesSync, writeFileSync } from "node:fs";
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
    // The old check answers after the new edit: its answer is dropped, and then the new check runs.
    answers.get("old")?.(READY);
    await new Promise((r) => setImmediate(r));
    assert.deepEqual(applied, []);
    answers.get("new")?.(REFUSED);
    await new Promise((r) => setImmediate(r));
    assert.deepEqual(applied, [{ text: "new", state: REFUSED }]);
    assert.deepEqual(flow.result(), { text: "new", state: REFUSED });
  } finally {
    mock.timers.reset();
  }
});

test("candidate: Save is on only for a valid, current candidate that differs from disk", () => {
  assert.equal(canSave(undefined, "x", "y", true), false, "no check yet");
  assert.equal(canSave({ text: "x", state: REFUSED }, "x", "y", true), false, "refused");
  assert.equal(canSave({ text: "x", state: READY }, "x", "x", true), false, "valid but unchanged");
  assert.equal(canSave({ text: "x", state: READY }, "x", "y", true), true, "valid and changed");
  assert.equal(canSave({ text: "x", state: READY }, "xy", "y", true), false, "the check is for an older edit");
  assert.equal(canSave({ text: "x", state: READY }, "x", "y", false), false, "the newest edit's check has not finished");
});

test("candidate: editing back to an earlier text keeps Save off until that edit's own check finishes", async () => {
  mock.timers.enable({ apis: ["setTimeout"] });
  try {
    const answers: Array<(state: WorkspaceState) => void> = [];
    const flow = new CandidateFlow(() => new Promise((resolve) => answers.push(resolve)), () => undefined,
      { set: (fn, ms) => setTimeout(fn, ms), clear: (h) => clearTimeout(h as NodeJS.Timeout) });
    flow.edit("A");
    mock.timers.tick(300);
    answers[0](READY);
    await new Promise((r) => setImmediate(r));
    assert.ok(canSave(flow.result(), "A", "disk", flow.settled()), "A was checked valid");
    flow.edit("B");
    flow.edit("A");
    assert.equal(canSave(flow.result(), "A", "disk", flow.settled()), false, "Save on while the newest A is unchecked");
    mock.timers.tick(300);
    answers[1](REFUSED);
    await new Promise((r) => setImmediate(r));
    assert.equal(canSave(flow.result(), "A", "disk", flow.settled()), false);
  } finally {
    mock.timers.reset();
  }
});

test("candidate: a slow dispatcher runs one check at a time and only the newest waits", async () => {
  mock.timers.enable({ apis: ["setTimeout"] });
  try {
    const started: string[] = [];
    const answers: Array<(state: WorkspaceState) => void> = [];
    const applied: string[] = [];
    const flow = new CandidateFlow((text) => (started.push(text), new Promise((resolve) => answers.push(resolve))),
      (c) => applied.push(c.text), { set: (fn, ms) => setTimeout(fn, ms), clear: (h) => clearTimeout(h as NodeJS.Timeout) });
    for (const text of ["one", "two", "three", "four"]) {
      flow.edit(text);
      mock.timers.tick(400);
    }
    assert.deepEqual(started, ["one"], "a check started while another was running");
    answers[0](READY);
    await new Promise((r) => setImmediate(r));
    assert.deepEqual(started, ["one", "four"], "an obsolete check ran instead of the newest");
    answers[1](READY);
    await new Promise((r) => setImmediate(r));
    assert.deepEqual(applied, ["four"]);
    assert.ok(flow.settled());
  } finally {
    mock.timers.reset();
  }
});

test("candidate: a failed write leaves no candidate file, and an existing name is never deleted", async () => {
  const dir = mkdtempSync(join(tmpdir(), "conclave-candidates-"));
  try {
    // writeSync throws after the file was created (here on a value that is not text, as a broken caller would pass).
    await assert.rejects(withCandidate(undefined as unknown as string, async () => "unreachable", dir));
    assert.deepEqual(readdirSync(dir), [], "the candidate created before the failed write was left");
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
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

test("candidate: the sweep also clears this account's fallback folders", { skip: process.platform === "win32" && "fallback folders are a POSIX rule" }, () => {
  const temp = mkdtempSync(join(tmpdir(), "conclave-temp-"));
  try {
    const own = join(temp, "conclave-AbC123");
    mkdirSync(own, { mode: 0o700 });
    writeFileSync(join(own, "pin-7-1.toml"), "x");
    const old = Date.now() / 1000 - 2 * 24 * 60 * 60;
    utimesSync(join(own, "pin-7-1.toml"), old, old);
    utimesSync(own, old, old);
    assert.equal(sweepCandidates(join(temp, "conclave"), Date.now(), temp), 1);
    assert.equal(existsSync(own), false, "the empty fallback folder was kept");
  } finally {
    rmSync(temp, { recursive: true, force: true });
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
