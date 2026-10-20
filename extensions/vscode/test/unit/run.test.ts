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
      await killTree(target);
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
  };
  const controller = new AbortController();
  const running = run(process.execPath, ["-e", "setInterval(() => {}, 1000)"], 60_000, undefined, { signal: controller.signal, tree: true, killer });
  await new Promise((r) => setTimeout(r, 300));
  controller.abort();
  const result = await running;
  assert.equal(result.error, "cancelled");
  assert.equal(killDone, true, "the run settled on the exit, before the tree kill was done");
});

// A made-up process table for endTree: parent to children, which processes run, and what a kill does.
function fakeTree(spawnOnKill: Map<number, number[]> = new Map(), unkillable = new Set<number>()) {
  const children = new Map<number, number[]>();
  const alive = new Set([1]);
  let clock = 0;
  const kills: number[][] = [];
  const ops: TreeOps = {
    table: async () => new Map([...children].map(([k, v]) => [k, [...v]])),
    kill: async (pids) => {
      kills.push(pids);
      for (const pid of pids) {
        // A process that starts a child as it is being killed: the child appears after this round's look.
        for (const child of spawnOnKill.get(pid) ?? []) {
          children.set(pid, [...(children.get(pid) ?? []), child]);
          alive.add(child);
        }
        if (!unkillable.has(pid)) {
          alive.delete(pid);
        }
      }
    },
    running: (pid) => alive.has(pid),
    now: () => clock,
    sleep: async (ms) => void (clock += ms),
  };
  return { ops, kills, alive };
}

test("endTree: a descendant started after a look is found by the next look and ended", async () => {
  const tree = fakeTree(new Map([[1, [2]], [2, [3]]]));
  assert.deepEqual(await endTree(1, tree.ops), []);
  assert.deepEqual(tree.kills, [[1], [2], [3]]);
  assert.deepEqual([...tree.alive], []);
});

test("endTree: a look that never answers still ends in a kill", { timeout: 5000 }, async () => {
  const tree = fakeTree();
  tree.ops.table = () => new Promise(() => undefined);
  assert.deepEqual(await endTree(1, tree.ops, 5000, 20), []);
  assert.deepEqual(tree.kills, [[1]]);
});

test("endTree: a process that cannot be ended is returned at the deadline", async () => {
  const tree = fakeTree(new Map(), new Set([1]));
  assert.deepEqual(await endTree(1, tree.ops, 100), [1]);
  assert.ok(tree.kills.length > 1, "it tried more than once");
});

test("a cancelled run says which processes did not end", async () => {
  const controller = new AbortController();
  const running = run(process.execPath, ["-e", "setInterval(() => {}, 1000)"], 60_000, undefined, {
    signal: controller.signal, tree: true, killer: async (pid) => (process.kill(pid, "SIGKILL"), [4242]),
  });
  await new Promise((r) => setTimeout(r, 300));
  controller.abort();
  assert.deepEqual(await running, { code: undefined, stdout: "", stderr: "", error: "cancelled, but 1 process did not end (4242)", survivors: [4242] });
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
