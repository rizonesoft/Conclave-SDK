import assert from "node:assert/strict";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, realpathSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import * as vscode from "vscode";
import type { ConclaveApi } from "../../src/extension";
import { running } from "../../src/host/run";
import { removeTree } from "../../src/host/removeTree";

// A fake SDK whose forge.py does what CONCLAVE_FAKE_FORGE says: answer, answer with its working directory, print no
// JSON, fail with 30 lines of stderr, or hang with a child of its own.
const FAKE = `
import json, os, subprocess, sys, time
mode = os.environ.get("CONCLAVE_FAKE_FORGE", "answer")
if mode == "answer":
    print(json.dumps({"kits": ["base", "reviewer"]}))
elif mode == "cwd":
    print(json.dumps({"kits": [os.getcwd()]}))
elif mode == "nojson":
    print("done")
elif mode == "fail":
    sys.stderr.write("".join(f"line {i}\\n" for i in range(1, 31)))
    sys.exit(2)
else:
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(600)"])
    open(os.environ["CONCLAVE_FORGE_PIDS"], "w").write(json.dumps([os.getpid(), child.pid]))
    time.sleep(600)
`;

suite("forgeRunner", () => {
  let base: string;
  let api: ConclaveApi;
  let sdk: string;
  const label = "local Conclave-SDK (fake)";

  suiteSetup(async () => {
    base = mkdtempSync(join(tmpdir(), "conclave-forge-"));
    sdk = join(base, "sdk");
    mkdirSync(join(sdk, "kits"), { recursive: true });
    writeFileSync(join(sdk, "forge.py"), FAKE);
    const extension = vscode.extensions.getExtension<ConclaveApi>("rizonetech.conclave");
    assert.ok(extension);
    api = await extension.activate();
  });

  suiteTeardown(() => {
    delete process.env.CONCLAVE_FAKE_FORGE;
    delete process.env.CONCLAVE_FORGE_PIDS;
    removeTree(base);
  });

  async function hung(): Promise<{ pids: () => Promise<[number, number]> }> {
    const file = join(base, `pids-${Date.now()}.json`);
    process.env.CONCLAVE_FAKE_FORGE = "hang";
    process.env.CONCLAVE_FORGE_PIDS = file;
    return {
      pids: async () => {
        const started = Date.now();
        while (!existsSync(file) && Date.now() - started < 15_000) {
          await new Promise((r) => setTimeout(r, 50));
        }
        await new Promise((r) => setTimeout(r, 100));
        return JSON.parse(readFileSync(file, "utf8")) as [number, number];
      },
    };
  }

  test("forgeRunner: an answer is parsed, run from the SDK folder, and logged with argv, folder, label, exit and time", async () => {
    process.env.CONCLAVE_FAKE_FORGE = "answer";
    assert.deepEqual(await api.runForge({ folder: sdk, label }, ["kits"]), { kind: "ok", value: ["base", "reviewer"] });
    const line = api.recentLog().filter((l) => l.startsWith("forge: ")).at(-1) ?? "";
    assert.ok(line.includes(join(sdk, "forge.py")) && line.includes(" -I ") && line.includes(" kits in "), line);
    assert.match(line, new RegExp(`in .* \\(${label.replace(/[()]/g, "\\$&")}\\): exit 0 in \\d+ ms$`));
    process.env.CONCLAVE_FAKE_FORGE = "cwd";
    const where = await api.runForge({ folder: sdk, label }, ["kits"]);
    assert.ok(where.kind === "ok" && realpathSync((where.value as string[])[0]) === realpathSync(sdk), JSON.stringify(where));
  });

  test("forgeRunner: no JSON, a non-zero exit and an unknown command are failures", async () => {
    process.env.CONCLAVE_FAKE_FORGE = "nojson";
    const nojson = await api.runForge({ folder: sdk, label }, ["kits"]);
    // raw is forge's stdout verbatim, so its line ending is the platform's.
    assert.ok(nojson.kind === "failed" && nojson.message === "forge kits printed no JSON" && nojson.raw?.trim() === "done", JSON.stringify(nojson));
    process.env.CONCLAVE_FAKE_FORGE = "fail";
    const failed = await api.runForge({ folder: sdk, label }, ["kits"]);
    assert.ok(failed.kind === "failed" && failed.message === "forge kits exited 2", JSON.stringify(failed));
    assert.deepEqual(failed.stderrTail, Array.from({ length: 20 }, (_, i) => `line ${i + 11}`));
    // A name that is not a command the extension runs (inherited object names included) starts nothing.
    // The newest forge line, not a count, for the reason given in the read-only kit view test below.
    const lastForge = () => api.recentLog().filter((l) => l.startsWith("forge: ")).at(-1);
    const runs = lastForge();
    for (const command of ["rm", "__proto__", "toString", "constructor"]) {
      const refused = await api.runForge({ folder: sdk, label }, [command]);
      assert.deepEqual(refused, { kind: "failed", message: `forge ${command} is not a command the extension runs`, stderrTail: [] }, command);
    }
    assert.equal(lastForge(), runs, "a refused command was run");
  });

  test("forgeRunner: a command that writes is refused before anything runs (read-only kit view)", async () => {
    const target = join(base, "never-written");
    // The newest finished run, not a count: the recent log keeps its last 200 lines, so the refusals' own lines can
    // push older runs out of it and a count drops though nothing ran.
    const lastRun = () => api.recentLog().filter((l) => / in .* ms$/.test(l)).at(-1);
    const started = lastRun();
    // After "--", argparse reads "--dry-run" as the target folder, so the install would go there.
    for (const args of [["init", target], ["sync", target], ["kit", target, "todo"], ["kit", target, "todo", "--agent", "all"],
      ["kit", "--", "--dry-run", "todo"], ["kit", target, "todo", "--dry-run", "--", "x"]]) {
      const refused = await api.runForge({ folder: sdk, label }, args);
      assert.ok(refused.kind === "failed" && /not a command the extension runs|only with --dry-run|never include --/.test(refused.message), JSON.stringify(refused));
    }
    assert.equal(lastRun(), started, "a writing command was run");
    assert.equal(existsSync(target), false);
    // The read-only form still runs.
    process.env.CONCLAVE_FAKE_FORGE = "answer";
    const dry = await api.runForge({ folder: sdk, label }, ["kits"]);
    assert.equal(dry.kind, "ok");
  });

  test("forgeRunner: a run past its timeout fails, and its process tree is gone", async () => {
    const fake = await hung();
    const outcome = api.runForge({ folder: sdk, label }, ["kits"], { timeoutMs: 4000 });
    const pids = await fake.pids();
    assert.ok(pids.every(running));
    assert.deepEqual(await outcome, { kind: "failed", message: "forge kits did not finish: timed out after 4 s", stderrTail: [] });
    assert.deepEqual(pids.filter(running), [], "a process of the timed-out forge is still running");
  });

  test("forgeRunner: a cancelled run is cancelled, and its process tree is gone", async () => {
    const fake = await hung();
    const controller = new AbortController();
    const outcome = api.runForge({ folder: sdk, label }, ["kits"], { signal: controller.signal });
    const pids = await fake.pids();
    controller.abort();
    assert.deepEqual(await outcome, { kind: "cancelled" });
    assert.deepEqual(pids.filter(running), [], "a process of the cancelled forge is still running");
  });
});
