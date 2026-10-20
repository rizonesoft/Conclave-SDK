import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { chmodSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { findOnPath } from "../../src/core/which";
import { endTree, killTree, run, runnable, running as isRunning, type TreeOps } from "../../src/host/run";

test("a process that ignores SIGTERM is killed at the timeout and the run settles", async () => {
  const started = Date.now();
  const result = await run(process.execPath, ["-e", "process.on('SIGTERM', () => {}); setInterval(() => {}, 1000)"], 500);
  assert.equal(result.code, undefined);
  assert.match(result.error ?? "", /timed out after 0\.5 s/);
  assert.ok(Date.now() - started < 5000, `settled after ${Date.now() - started} ms`);
});

test("an exit code and its output come back; a missing file cannot start", async () => {
  assert.deepEqual(await run(process.execPath, ["-e", "process.stdout.write('3.12.3'); process.exit(0)"], 5000),
    { code: 0, stdout: "3.12.3", stderr: "" });
  assert.deepEqual(await run(process.execPath, ["-e", "process.stderr.write('refused: no'); process.exit(2)"], 5000),
    { code: 2, stdout: "", stderr: "refused: no" });
  assert.equal((await run(process.execPath, ["-e", "process.exit(4)"], 5000)).code, 4);
  const missing = await run(process.execPath + ".missing", [], 5000);
  assert.equal(missing.code, undefined);
  assert.match(missing.error ?? "", /ENOENT/);
});

// Running, not merely present: on POSIX a killed process stays a zombie (state Z) until its parent reaps it, and
// process.kill(pid, 0) still succeeds on one, so ps decides there.
function alive(pid: number): boolean {
  if (process.platform !== "win32") {
    try {
      const state = execFileSync("ps", ["-o", "stat=", "-p", String(pid)], { encoding: "utf8" }).trim();
      return state !== "" && !state.startsWith("Z");
    } catch {
      return false;
    }
  }
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}

test("a run cancelled before it starts starts nothing", async () => {
  const controller = new AbortController();
  controller.abort();
  const result = await run(process.execPath, ["-e", "require('fs').writeFileSync('never', '')"], 5000, tmpdir(), { signal: controller.signal });
  assert.deepEqual(result, { code: undefined, stdout: "", stderr: "", error: "cancelled" });
});

test("cancelling a tree run kills the process and a descendant in its own session", async () => {
  const work = mkdtempSync(join(tmpdir(), "conclave-tree-"));
  const pids = join(work, "pids.json");
  // The child starts a detached grandchild (its own session on POSIX, as the dispatcher starts a reviewer), records
  // both process ids, then waits.
  const script = `
    const { spawn } = require("node:child_process");
    const grandchild = spawn(process.execPath, ["-e", "setInterval(() => {}, 1000)"], { detached: true, stdio: "ignore" });
    require("node:fs").writeFileSync(${JSON.stringify(pids)}, JSON.stringify([process.pid, grandchild.pid]));
    setInterval(() => {}, 1000);`;
  const controller = new AbortController();
  try {
    const running = run(process.execPath, ["-e", script], 60_000, work, { signal: controller.signal, tree: true });
    const started = Date.now();
    while (!existsSync(pids) && Date.now() - started < 10_000) {
      await new Promise((r) => setTimeout(r, 20));
    }
    await new Promise((r) => setTimeout(r, 100));
    const [child, grandchild] = JSON.parse(readFileSync(pids, "utf8")) as [number, number];
    assert.ok(alive(child) && alive(grandchild));
    controller.abort();
    const result = await running;
    assert.equal(result.error, "cancelled");
    const until = Date.now() + 5000;
    while ((alive(child) || alive(grandchild)) && Date.now() < until) {
      await new Promise((r) => setTimeout(r, 50));
    }
    assert.equal(alive(child), false, "the child is still running");
    assert.equal(alive(grandchild), false, "the grandchild in its own session is still running");
  } finally {
    rmSync(work, { recursive: true, force: true });
  }
});

test("cancelling a tree run kills a chain 25 processes deep, all gone when the run settles", async () => {
  const work = mkdtempSync(join(tmpdir(), "conclave-chain-"));
  const pids = join(work, "pids.txt");
  // Each process records its id and starts the next, 25 deep; the last one waits.
  const script = `
    const fs = require("node:fs");
    const depth = Number(process.env.CHAIN_DEPTH ?? "25");
    fs.appendFileSync(${JSON.stringify(pids)}, process.pid + "\\n");
    if (depth > 1) {
      // Under node -e the code is not in argv, so it is passed along as the first argument.
      require("node:child_process").spawn(process.execPath, ["-e", process.argv[1], process.argv[1]], {
        stdio: "ignore", env: { ...process.env, CHAIN_DEPTH: String(depth - 1) } });
    }
    setInterval(() => {}, 1000);`;
  const controller = new AbortController();
  try {
    const running = run(process.execPath, ["-e", script, script], 60_000, work, { signal: controller.signal, tree: true });
    const started = Date.now();
    const count = () => (existsSync(pids) ? readFileSync(pids, "utf8").trim().split("\n").length : 0);
    while (count() < 25 && Date.now() - started < 20_000) {
      await new Promise((r) => setTimeout(r, 50));
    }
    assert.equal(count(), 25);
    const chain = readFileSync(pids, "utf8").trim().split("\n").map(Number);
    controller.abort();
    assert.equal((await running).error, "cancelled");
    // Settled only once every process has ended: checked at that instant, synchronously, with no grace.
    assert.deepEqual(chain.filter(isRunning), [], "processes of the chain are still running");
  } finally {
    // A failed assertion above must not leave the chain running.
    controller.abort();
    rmSync(work, { recursive: true, force: true });
  }
});

test("a cancelled tree run has ended its process when it settles, 20 times over", async () => {
  for (let i = 0; i < 20; i += 1) {
    const pid: { value?: number } = {};
    const controller = new AbortController();
    const killer = async (target: number) => {
      pid.value = target;
      return killTree(target);
    };
    const running = run(process.execPath, ["-e", "setInterval(() => {}, 1000)"], 60_000, undefined, { signal: controller.signal, tree: true, killer });
    await new Promise((r) => setTimeout(r, 50));
    controller.abort();
    assert.equal((await running).error, "cancelled");
    assert.ok(pid.value !== undefined && !isRunning(pid.value), `run ${i}: process ${pid.value} still running when the run settled`);
  }
});

test("a cancelled tree run settles only when the tree kill is done, not when the process exits", async () => {
  let killDone = false;
  const killer = async (pid: number) => {
    process.kill(pid, "SIGKILL");
    await new Promise((r) => setTimeout(r, 300));
    killDone = true;
    return { survivors: [], verified: true };
  };
  const controller = new AbortController();
  const running = run(process.execPath, ["-e", "setInterval(() => {}, 1000)"], 60_000, undefined, { signal: controller.signal, tree: true, killer });
  await new Promise((r) => setTimeout(r, 300));
  controller.abort();
  const result = await running;
  assert.equal(result.error, "cancelled");
  assert.equal(killDone, true, "the run settled on the exit, before the tree kill was done");
});

// A made-up process table for endTree. posix: a killed parent's children are reparented to init (0), as on Linux, and
// processes can be stopped; otherwise (Windows) a dead parent keeps its id on its children and nothing is stopped.
// spawnOnKill and spawnOnStop: a process that starts a child just as it is killed, or just before it is stopped.
function fakeTree(options: { posix?: boolean; children?: [number, number[]][]; spawnOnKill?: [number, number[]][]; spawnOnStop?: [number, number[]][]; unkillable?: number[] } = {}) {
  const children = new Map<number, number[]>(options.children ?? []);
  const alive = new Set([1, ...[...children.values()].flat()]);
  const stopped = new Set<number>();
  const spawnOnKill = new Map(options.spawnOnKill ?? []);
  const spawnOnStop = new Map(options.spawnOnStop ?? []);
  const unkillable = new Set(options.unkillable ?? []);
  let clock = 0;
  const kills: number[][] = [];
  const spawn = (parent: number, kids: number[]) => {
    children.set(parent, [...(children.get(parent) ?? []), ...kids]);
    kids.forEach((k) => alive.add(k));
  };
  const ops: TreeOps = {
    table: async () => new Map([...children].map(([k, v]) => [k, [...v]])),
    kill: async (pids) => {
      kills.push(pids);
      for (const pid of pids) {
        if (!stopped.has(pid)) {
          spawn(pid, spawnOnKill.get(pid) ?? []);
        }
        if (!unkillable.has(pid)) {
          alive.delete(pid);
          if (options.posix) {
            spawn(0, children.get(pid) ?? []);
            children.delete(pid);
          }
        }
      }
    },
    running: (pid) => alive.has(pid),
    now: () => clock,
    sleep: async (ms) => void (clock += ms),
  };
  if (options.posix) {
    ops.stop = (pids) => pids.forEach((pid) => {
      if (!stopped.has(pid)) {
        spawn(pid, spawnOnStop.get(pid) ?? []);
        stopped.add(pid);
      }
    });
  }
  return { ops, kills, alive };
}

test("endTree: on Windows, a descendant started as its parent is killed is found by the next look and ended", async () => {
  const tree = fakeTree({ spawnOnKill: [[1, [2]], [2, [3]]] });
  assert.deepEqual(await endTree(1, tree.ops), { survivors: [], verified: true });
  assert.deepEqual(tree.kills, [[1], [2], [3]]);
  assert.deepEqual([...tree.alive], []);
});

test("endTree: on POSIX, a child born just before its parent is stopped is frozen and ended, though killing reparents it", async () => {
  // 1 has child 2; 2 starts 3 just before it is stopped. Killed before 3 was seen, 2 would hand 3 to init, out of reach.
  const tree = fakeTree({ posix: true, children: [[1, [2]]], spawnOnStop: [[2, [3]]] });
  assert.deepEqual(await endTree(1, tree.ops), { survivors: [], verified: true });
  assert.deepEqual([...tree.alive], [], "a process of the tree is still running");
  assert.deepEqual(tree.kills, [[1, 2, 3]], "the tree was killed before it was complete");
});

test("endTree: a look that never answers still ends in a kill, and the end is reported unverified", { timeout: 5000 }, async () => {
  // A child the stalled table would have shown: it cannot be found, so the end is not reported as confirmed.
  const tree = fakeTree({ children: [[1, [2]]] });
  tree.ops.table = () => new Promise(() => undefined);
  assert.deepEqual(await endTree(1, tree.ops, 100, 10), { survivors: [], verified: false });
  assert.deepEqual(tree.kills[0], [1]);
  assert.ok(tree.alive.has(2), "the fake child is unseen, so it is still running");
});

test("endTree: on POSIX, a table that reads again after a blind kill cannot confirm the end", async () => {
  // Root 1 with child 2; the first two reads fail, so 1 is frozen and killed without 2 being seen, and 2 is
  // reparented to init. The third read works, but no walk from 1 can find 2 any more.
  const tree = fakeTree({ posix: true, children: [[1, [2]]] });
  const table = tree.ops.table;
  let reads = 0;
  tree.ops.table = async () => (++reads <= 2 ? undefined : table());
  const end = await endTree(1, tree.ops, 1000);
  assert.deepEqual(end, { survivors: [], verified: false });
  assert.ok(tree.alive.has(2), "the fake child is unseen, so it still runs");
});

test("endTree: on Windows, a table that reads again finds what it missed, since dead parents keep their ids", async () => {
  const tree = fakeTree({ children: [[1, [2]]] });
  const table = tree.ops.table;
  let reads = 0;
  tree.ops.table = async () => (++reads <= 2 ? undefined : table());
  assert.deepEqual(await endTree(1, tree.ops, 1000), { survivors: [], verified: true });
  assert.deepEqual([...tree.alive], []);
});

test("endTree: a table that is always slow still leads to a kill before the deadline", async () => {
  const tree = fakeTree({ posix: true });
  tree.ops.table = async () => {
    await tree.ops.sleep(3000);
    return undefined;
  };
  const end = await endTree(1, tree.ops, 5000);
  assert.ok(tree.kills.length >= 1, "no kill was attempted");
  assert.deepEqual(end, { survivors: [], verified: false });
  assert.equal(tree.alive.has(1), false, "the root was left frozen");
});

test("endTree: on POSIX, discovery the deadline cuts short while it still finds processes cannot confirm the end", async () => {
  // Each stop starts a child (2 starts 3, 3 starts 4, ...), and each look takes 2.6 s: discovery is still finding
  // processes when the deadline ends it, so the last child born may be reparented unseen.
  const tree = fakeTree({ posix: true, children: [[1, [2]]], spawnOnStop: [[2, [3]], [3, [4]], [4, [5]], [5, [6]]] });
  const table = tree.ops.table;
  tree.ops.table = async () => {
    await tree.ops.sleep(2600);
    return table();
  };
  const end = await endTree(1, tree.ops, 5000);
  assert.equal(end.verified, false, JSON.stringify(end));
});

test("endTree: a process that cannot be ended is returned at the deadline", async () => {
  const tree = fakeTree({ unkillable: [1] });
  assert.deepEqual(await endTree(1, tree.ops, 100), { survivors: [1], verified: true });
  assert.ok(tree.kills.length > 1, "it tried more than once");
});

test("a cancelled run says which processes did not end, or that their end could not be confirmed", async () => {
  for (const [end, error, extra] of [
    [{ survivors: [4242], verified: true }, "cancelled, but 1 process did not end (4242)", { survivors: [4242] }],
    [{ survivors: [], verified: false }, "cancelled, but the process table could not be read to confirm that every process ended", { survivors: [], unverified: true }],
    [{ survivors: [7], verified: false }, "cancelled, but 1 process did not end (7), and the process table could not be read to confirm that every other process ended", { survivors: [7], unverified: true }],
  ] as const) {
    const controller = new AbortController();
    const running = run(process.execPath, ["-e", "setInterval(() => {}, 1000)"], 60_000, undefined, {
      signal: controller.signal, tree: true, killer: async (pid) => (process.kill(pid, "SIGKILL"), { survivors: [...end.survivors], verified: end.verified }),
    });
    await new Promise((r) => setTimeout(r, 300));
    controller.abort();
    assert.deepEqual(await running, { code: undefined, stdout: "", stderr: "", error, ...extra });
  }
});

test("an argument execFile cannot pass is a run that could not start, not a rejection", async () => {
  const result = await run(process.execPath + "\u0000", [], 5000);
  assert.equal(result.code, undefined);
  assert.match(result.error ?? "", /ERR_INVALID_ARG_VALUE|ERR_INVALID_ARG_TYPE/);
});

test("runnable skips a POSIX file without execute permission, so a later PATH entry is found", { skip: process.platform === "win32" && "execute permission is a POSIX rule" }, () => {
  const root = mkdtempSync(join(tmpdir(), "conclave-runnable-"));
  try {
    for (const [dir, mode] of [["first", 0o644], ["second", 0o755]] as const) {
      mkdirSync(join(root, dir));
      writeFileSync(join(root, dir, "python3"), "#!/bin/sh\n");
      chmodSync(join(root, dir, "python3"), mode);
    }
    assert.equal(runnable(join(root, "first", "python3")), false);
    const env = { platform: process.platform, path: `${join(root, "first")}:${join(root, "second")}`, runnable };
    assert.equal(findOnPath("python3", env), join(root, "second", "python3"));
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});
