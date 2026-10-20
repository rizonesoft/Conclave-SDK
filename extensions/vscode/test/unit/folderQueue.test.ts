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
  const a = q.run("/w", "a", h.task("/w", "a"));
  const b = q.run("/w", "b", h.task("/w", "b"));
  await h.tick();
  assert.deepEqual(h.started, ["a"], "b started while a was running");
  h.finishers[0]();
  await h.tick();
  assert.deepEqual(h.started, ["a", "b"]);
  h.finishers[1]();
  assert.deepEqual(await Promise.all([a, b]), ["a", "b"]);
  assert.equal(h.most.get("/w"), 1);
});

test("an identical request waiting or running shares its answer and starts nothing", async () => {
  const h = harness();
  const q = new FolderQueue<string>();
  const first = q.run("/w", "pin", h.task("/w", "first"));
  const second = q.run("/w", "pin", h.task("/w", "second"));
  assert.equal(first, second);
  await h.tick();
  h.finishers[0]();
  assert.equal(await second, "first");
  assert.deepEqual(h.started, ["first"]);
});

test("folders do not wait for each other, and a failed request does not block the next", async () => {
  const h = harness();
  const q = new FolderQueue<string>();
  const failed = q.run("/a", "x", h.task("/a", "a-fails", true));
  const other = q.run("/b", "x", h.task("/b", "b"));
  const after = q.run("/a", "y", h.task("/a", "a-next"));
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
