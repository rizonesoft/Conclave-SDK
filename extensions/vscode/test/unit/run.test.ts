import assert from "node:assert/strict";
import { chmodSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { findOnPath } from "../../src/core/which";
import { run, runnable } from "../../src/host/run";

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

function alive(pid: number): boolean {
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
