import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, readFile, writeFile, rm, mkdir } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { randomBytes } from "node:crypto";
import { existsSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import {
  LinuxStore,
  WindowsStore,
  validateRecord,
  locked,
  createStore,
} from "../src/store.js";
const record = {
  schemaVersion: 1,
  config: {
    clientId: "11111111-1111-4111-8111-111111111111",
    tenantId: "22222222-2222-4222-8222-222222222222",
    mailbox: "test@example.test",
    homeAccountId: "home",
    graphUserId: "graph",
  },
  cache: JSON.stringify({ test: "synthetic-cache-value" }),
};
test("WSL detection survives the minimal MCP environment without a plaintext fallback",()=>{
  const store=createStore({}, {platform:"linux",kernelRelease:"6.6.87.2-microsoft-standard-WSL2"});
  assert.ok(store instanceof WindowsStore);assert.equal(store.bridge,true);
  assert.throws(()=>createStore({}, {platform:"linux",kernelRelease:"6.8.0-generic"}),/systemd/);
});
test("encrypted Linux cache roundtrip, replacement and tamper detection", async (t) => {
  const dir = await mkdtemp(join(tmpdir(), "graph-store-"));
  t.after(() => rm(dir, { recursive: true, force: true }));
  await writeFile(join(dir, "cache-key"), randomBytes(32));
  const s = new LinuxStore({
    CREDENTIALS_DIRECTORY: dir,
    STATE_DIRECTORY: dir,
  });
  assert.equal((await s.status()).credentialPresent, false);
  assert.equal(await s.read(), null);
  await s.withLock(() => s.save(record));
  assert.deepEqual(await s.read(), record);
  const bytes = await readFile(join(dir, "session.enc"));
  assert.ok(!bytes.includes(Buffer.from("synthetic-cache-value")));
  const replacement = { ...record, cache: '{"replacement":true}' };
  await s.save(replacement);
  assert.deepEqual(await s.read(), replacement);
  const corrupted = await readFile(join(dir, "session.enc"));
  corrupted[30] ^= 1;
  await writeFile(join(dir, "session.enc"), corrupted);
  await assert.rejects(s.read(), /authentication failed/);
});
test("invalid replacement leaves encrypted session unchanged", async (t) => {
  const dir = await mkdtemp(join(tmpdir(), "graph-invalid-"));
  t.after(() => rm(dir, { recursive: true, force: true }));
  await writeFile(join(dir, "cache-key"), randomBytes(32));
  const s = new LinuxStore({
    CREDENTIALS_DIRECTORY: dir,
    STATE_DIRECTORY: dir,
  });
  await s.save(record);
  const before = await readFile(join(dir, "session.enc"));
  await assert.rejects(s.save({ ...record, cache: "" }), /Invalid/);
  assert.deepEqual(await readFile(join(dir, "session.enc")), before);
});
test("locking serializes changes and refuses a lock still held by another process", async (t) => {
  const dir = await mkdtemp(join(tmpdir(), "graph-lock-"));
  t.after(() => rm(dir, { recursive: true, force: true }));
  let n = 0;
  await Promise.all(
    [1, 2, 3].map(() =>
      locked(dir, async () => {
        const current = n;
        await new Promise((r) => setTimeout(r, 20));
        n = current + 1;
      }),
    ),
  );
  assert.equal(n, 3);
  await mkdir(join(dir, "session.lock"));
  await assert.rejects(
    locked(dir, () => assert.fail(), { timeout: 10 }),
    /busy/,
  );
});
test("missing systemd configuration has no plaintext or vault fallback", () => {
  assert.throws(() => new LinuxStore({}), /systemd/);
  assert.throws(() => validateRecord({}), /Invalid/);
});
const pwsh7Modules = join(
  process.env.ProgramFiles || "C:\\Program Files",
  "PowerShell",
  "7",
  "Modules",
);
test(
  "the DPAPI helper works when PowerShell 7's modules come first on the inherited module path",
  {
    skip:
      process.platform !== "win32" ||
      !existsSync(join(pwsh7Modules, "Microsoft.PowerShell.Security")),
  },
  async (t) => {
    // A Windows process started from WSL inherits the module path of whatever started wsl.exe, and
    // the bridge cannot remove it, so the helper is run here with that path as the bridge passes it.
    const root = await mkdtemp(join(tmpdir(), "graph-dpapi-path-"));
    t.after(() => rm(root, { recursive: true, force: true }));
    const env = {
      ...process.env,
      LOCALAPPDATA: root,
      PSModulePath: `${pwsh7Modules};${join(process.env.SystemRoot || "C:\\Windows", "System32\\WindowsPowerShell\\v1.0\\Modules")}`,
    };
    const run = (action, input) =>
      spawnSync(
        join(
          process.env.SystemRoot || "C:\\Windows",
          "System32/WindowsPowerShell/v1.0/powershell.exe",
        ),
        [
          "-NoLogo",
          "-NoProfile",
          "-NonInteractive",
          "-File",
          fileURLToPath(new URL("../scripts/dpapi-store.ps1", import.meta.url)),
          "-Action",
          action,
        ],
        { env, input: input ?? "", encoding: "utf8", windowsHide: true, timeout: 60000 },
      );
    const saved = run("save", JSON.stringify(record));
    assert.equal(saved.status, 0, saved.stderr);
    const loaded = run("load");
    assert.equal(loaded.status, 0, loaded.stderr);
    assert.deepEqual(JSON.parse(loaded.stdout.replace(/^\uFEFF/, "")), record);
  },
);
test(
  "Windows DPAPI roundtrip, status and preserved non-secret settings",
  { skip: process.platform !== "win32" },
  async (t) => {
    const root = await mkdtemp(join(tmpdir(), "graph-dpapi-"));
    t.after(() => rm(root, { recursive: true, force: true }));
    const s = new WindowsStore({ env: { ...process.env, LOCALAPPDATA: root } });
    assert.equal((await s.status()).credentialPresent, false);
    assert.equal(await s.read(), null);
    await s.withLock(() => s.save(record));
    assert.deepEqual(await s.read(), record);
    const folder = join(root, "Rizonetech/OutlookGraph");
    assert.ok(
      !(await readFile(join(folder, "session.dpapi"), "utf8")).includes(
        "synthetic-cache-value",
      ),
    );
    const config = JSON.parse(
      await readFile(join(folder, "config.json"), "utf8"),
    );
    config.unrelated = "preserved";
    await writeFile(join(folder, "config.json"), JSON.stringify(config));
    await s.save({ ...record, cache: '{"updated":true}' });
    assert.equal(
      JSON.parse(await readFile(join(folder, "config.json"), "utf8")).unrelated,
      "preserved",
    );
    const before = await readFile(join(folder, "session.dpapi"));
    await assert.rejects(s.save({ ...record, cache: "" }));
    assert.deepEqual(await readFile(join(folder, "session.dpapi")), before);
    assert.equal((await s.status()).configurationPresent, true);
  },
);
