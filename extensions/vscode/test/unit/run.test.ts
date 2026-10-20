import assert from "node:assert/strict";
import { chmodSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
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
    { code: 0, stdout: "3.12.3" });
  assert.equal((await run(process.execPath, ["-e", "process.exit(4)"], 5000)).code, 4);
  const missing = await run(process.execPath + ".missing", [], 5000);
  assert.equal(missing.code, undefined);
  assert.match(missing.error ?? "", /ENOENT/);
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
