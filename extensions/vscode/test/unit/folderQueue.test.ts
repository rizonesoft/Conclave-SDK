import assert from "node:assert/strict";
import { test } from "node:test";
import { FolderQueue } from "../../src/core/folderQueue";

// A task the test finishes by hand, recording how many tasks of each folder run at once.
function harness() {
  const running = new Map<string, number>();
  const most = new Map<string, number>();
  const started: string[] = [];
  const finishers: Array<() => void> = [];
  const task = (folder: string, name: string, fail = false) => () => {
    started.push(name);
    running.set(folder, (running.get(folder) ?? 0) + 1);
    most.set(folder, Math.max(most.get(folder) ?? 0, running.get(folder) ?? 0));
    return new Promise<string>((resolve, reject) => finishers.push(() => {
      running.set(folder, (running.get(folder) ?? 0) - 1);
      if (fail) {
        reject(new Error(name));
      } else {
        resolve(name);
      }
    }));
  };
  const tick = () => new Promise((r) => setImmediate(r));
  return { most, started, finishers, task, tick };
}

test("different requests for one folder run one at a time, in order", async () => {
  const h = harness();
  const q = new FolderQueue<string>();
  const a = q.run("/w", "a", h.task("/w", "a")).promise;
  const b = q.run("/w", "b", h.task("/w", "b")).promise;
  await h.tick();
  assert.deepEqual(h.started, ["a"], "b started while a was running");
  h.finishers[0]();
  await h.tick();
  assert.deepEqual(h.started, ["a", "b"]);
  h.finishers[1]();
  assert.deepEqual(await Promise.all([a, b]), ["a", "b"]);
  assert.equal(h.most.get("/w"), 1);
});

test("an identical request still waiting shares its answer and starts nothing", async () => {
  const h = harness();
  const q = new FolderQueue<string>();
  const first = q.run("/w", "pin", h.task("/w", "first"));
  const second = q.run("/w", "pin", h.task("/w", "second"));
  assert.equal(first.promise, second.promise);
  assert.deepEqual([first.created, second.created], [true, false]);
  await h.tick();
  h.finishers[0]();
  assert.equal(await second.promise, "first");
  assert.deepEqual(h.started, ["first"]);
});

test("an identical request after the run started gets a fresh run behind it, never the older answer", async () => {
  const h = harness();
  const q = new FolderQueue<string>();
  const before = q.run("/w", "pin", h.task("/w", "before-save"));
  await h.tick();
  assert.deepEqual(h.started, ["before-save"]);
  const after = q.run("/w", "pin", h.task("/w", "after-save"));
  const joined = q.run("/w", "pin", h.task("/w", "unused"));
  assert.ok(after.created && !joined.created && after.promise === joined.promise);
  h.finishers[0]();
  await h.tick();
  assert.deepEqual(h.started, ["before-save", "after-save"]);
  h.finishers[1]();
  assert.deepEqual([await before.promise, await after.promise], ["before-save", "after-save"]);
  assert.equal(h.most.get("/w"), 1);
});

test("folders do not wait for each other, and a failed request does not block the next", async () => {
  const h = harness();
  const q = new FolderQueue<string>();
  const failed = q.run("/a", "x", h.task("/a", "a-fails", true)).promise;
  const other = q.run("/b", "x", h.task("/b", "b")).promise;
  const after = q.run("/a", "y", h.task("/a", "a-next")).promise;
  await h.tick();
  assert.deepEqual(h.started, ["a-fails", "b"]);
  h.finishers[0]();
  await assert.rejects(failed, /a-fails/);
  await h.tick();
  assert.deepEqual(h.started, ["a-fails", "b", "a-next"]);
  h.finishers[1]();
  h.finishers[2]();
  assert.deepEqual(await Promise.all([other, after]), ["b", "a-next"]);
});
