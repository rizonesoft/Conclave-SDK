import assert from "node:assert/strict";
import { test } from "node:test";
import { run } from "../../src/host/run";

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
