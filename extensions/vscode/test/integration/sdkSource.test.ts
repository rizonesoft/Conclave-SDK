import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { createServer, type Server } from "node:http";
import type { AddressInfo } from "node:net";
import { tmpdir } from "node:os";
import { join } from "node:path";
import * as vscode from "vscode";
import type { ConclaveApi } from "../../src/extension";
import { recentLog } from "../../src/host/output";
import { PythonService } from "../../src/host/python";
import { SdkSourceService } from "../../src/host/sdkSource";

// Compiled to out/test/integration/: the package root is three folders up.
const root = join(__dirname, "..", "..", "..");
const TOKEN = "gho_test_token_never_logged";
const shas: Record<string, string> = { main: "1".repeat(40), v2: "2".repeat(40), v3: "3".repeat(40), v4: "4".repeat(40) };

// A tarball like GitHub's: one top folder holding forge.py and kits/.
function tarball(work: string, python: string[], sha: string): Buffer {
  const builder = join(work, "build.py");
  writeFileSync(builder, [
    "import io, sys, tarfile",
    "top = 'o-r-' + sys.argv[2][:7]",
    "with tarfile.open(sys.argv[1], 'w:gz') as tar:",
    "    for name in (top, top + '/kits'):",
    "        info = tarfile.TarInfo(name); info.type = tarfile.DIRTYPE; tar.addfile(info)",
    "    data = b'print(1)\\n'; info = tarfile.TarInfo(top + '/forge.py'); info.size = len(data)",
    "    tar.addfile(info, io.BytesIO(data))",
  ].join("\n"));
  const out = join(work, `${sha}.tar.gz`);
  const [command, ...prefix] = python;
  const built = spawnSync(command, [...prefix, builder, out, sha], { encoding: "utf8" });
  assert.equal(built.status, 0, built.stderr);
  return readFileSync(out);
}

suite("SDK source", () => {
  let server: Server;
  let base: string;
  let work: string;
  const requests: string[] = [];
  const archives = new Map<string, Buffer>();
  let python: PythonService;

  suiteSetup(async () => {
    const extension = vscode.extensions.getExtension<ConclaveApi>("rizonetech.conclave");
    assert.ok(extension);
    await extension.activate();
    python = new PythonService();
    const resolved = await python.python();
    assert.ok(resolved.ok, "no Python on this host");
    work = mkdtempSync(join(tmpdir(), "conclave-sdk-"));
    for (const sha of Object.values(shas)) {
      archives.set(sha, tarball(work, [resolved.command, ...resolved.prefix], sha));
    }
    server = createServer((request, response) => {
      requests.push(`${request.method} ${request.url}`);
      assert.equal(request.headers.authorization, `Bearer ${TOKEN}`);
      const commit = /^\/repos\/o\/r\/commits\/([^/]+)$/.exec(request.url ?? "");
      const tar = /^\/repos\/o\/r\/tarball\/([0-9a-f]{40})$/.exec(request.url ?? "");
      if (commit && shas[decodeURIComponent(commit[1])]) {
        response.end(shas[decodeURIComponent(commit[1])]);
      } else if (tar && archives.has(tar[1])) {
        response.end(archives.get(tar[1]));
      } else if (request.url?.startsWith("/repos/limited/")) {
        response.writeHead(403, { "x-ratelimit-remaining": "0", "x-ratelimit-reset": "1792500000" }).end();
      } else {
        response.writeHead(404).end();
      }
    });
    await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
    base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
  });

  suiteTeardown(() => {
    server.close();
    python.dispose();
    rmSync(work, { recursive: true, force: true });
  });

  function service(storage: string, getSession: () => Promise<{ accessToken: string } | undefined> = async () => ({ accessToken: TOKEN })) {
    return new SdkSourceService(python, { extensionPath: root, storage, development: true, apiBase: base, getSession });
  }

  test("a cancelled sign-in is github-signin and makes no request", async () => {
    const before = requests.length;
    const result = await service(join(work, "s0"), async () => undefined).resolveWith({ sdkPath: "", sdkRepository: "o/r", sdkRef: "main" });
    assert.ok("state" in result && result.state === "github-signin");
    assert.equal(requests.length, before);
  });

  test("a ref resolves to one SHA, downloads once, extracts, and is reused from the cache", async () => {
    const storage = join(work, "s1");
    const sdk = service(storage);
    const first = await sdk.resolveWith({ sdkPath: "", sdkRepository: "o/r", sdkRef: "main" });
    assert.ok("ok" in first, JSON.stringify(first));
    assert.equal(first.sha, shas.main);
    assert.equal(first.label, `o/r@${shas.main.slice(0, 7)}`);
    assert.ok(existsSync(join(first.folder, "forge.py")) && existsSync(join(first.folder, ".complete")));
    const downloads = () => requests.filter((r) => r.includes("/tarball/")).length;
    const before = downloads();
    const again = await sdk.resolveWith({ sdkPath: "", sdkRepository: "o/r", sdkRef: "main" });
    assert.ok("ok" in again && again.folder === first.folder);
    assert.equal(downloads(), before, "the cached SHA was downloaded again");
    assert.ok(!recentLog().some((line) => line.includes(TOKEN)), "the token reached the output channel");
    assert.deepEqual(readdirSync(join(storage, "sdk")).filter((n) => n.includes("partial")), [], "a partial download was left");
  });

  test("a fourth SHA evicts the least recently used", async () => {
    const storage = join(work, "s2");
    const sdk = service(storage);
    for (const ref of ["main", "v2", "v3", "v4"]) {
      const result = await sdk.resolveWith({ sdkPath: "", sdkRepository: "o/r", sdkRef: ref });
      assert.ok("ok" in result, ref);
      await new Promise((r) => setTimeout(r, 5));
    }
    const kept = readdirSync(join(storage, "sdk")).sort();
    assert.deepEqual(kept, [shas.v2, shas.v3, shas.v4].sort());
  });

  test("no access and a used-up rate limit are their own refusals", async () => {
    const sdk = service(join(work, "s3"));
    const missing = await sdk.resolveWith({ sdkPath: "", sdkRepository: "o/r", sdkRef: "nope" });
    assert.ok("state" in missing && missing.state === "github-no-access");
    const limited = await sdk.resolveWith({ sdkPath: "", sdkRepository: "limited/r", sdkRef: "main" });
    assert.ok("state" in limited && limited.state === "github-rate-limited");
  });

  test("with nothing set, the development host uses the SDK checkout it runs from", async () => {
    const result = await service(join(work, "s4")).resolveWith({ sdkPath: "", sdkRepository: "", sdkRef: "" });
    assert.ok("ok" in result && result.label === "local Conclave-SDK (development)" && existsSync(join(result.folder, "forge.py")));
  });
});
