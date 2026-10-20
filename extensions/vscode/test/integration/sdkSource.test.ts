import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, symlinkSync, writeFileSync } from "node:fs";
import { createServer, type Server } from "node:http";
import type { AddressInfo } from "node:net";
import { tmpdir } from "node:os";
import { join } from "node:path";
import * as vscode from "vscode";
import type { ConclaveApi } from "../../src/extension";
import { recentLog } from "../../src/host/output";
import { PythonService } from "../../src/host/python";
import { removeTree } from "../../src/host/removeTree";
import { SdkSourceService } from "../../src/host/sdkSource";

// Compiled to out/test/integration/: the package root is three folders up.
const root = join(__dirname, "..", "..", "..");
const TOKEN = "gho_test_token_never_logged";
const shas: Record<string, string> = {
  main: "1".repeat(40), v2: "2".repeat(40), v3: "3".repeat(40), v4: "4".repeat(40),
  // alias names main's commit; readme's archive holds no forge.py; cut's body is cut off after the headers.
  alias: "1".repeat(40), readme: "5".repeat(40), cut: "6".repeat(40),
  // marker's archive carries a .complete folder of its own, a name the cache reserves.
  marker: "7".repeat(40),
};

// A tarball like GitHub's: one top folder holding forge.py and kits/.
function tarball(work: string, python: string[], sha: string, variant: "sdk" | "readme" | "marker" = "sdk"): Buffer {
  const builder = join(work, "build.py");
  writeFileSync(builder, [
    "import io, sys, tarfile",
    "top = 'o-r-' + sys.argv[2][:7]",
    "with tarfile.open(sys.argv[1], 'w:gz') as tar:",
    "    for name in (top, top + '/kits') + ((top + '/.complete',) if sys.argv[3] == 'marker' else ()):",
    "        info = tarfile.TarInfo(name); info.type = tarfile.DIRTYPE; tar.addfile(info)",
    "    data = b'print(1)\\n'; info = tarfile.TarInfo(top + ('/README.md' if sys.argv[3] == 'readme' else '/forge.py'))",
    "    info.size = len(data)",
    "    tar.addfile(info, io.BytesIO(data))",
  ].join("\n"));
  const out = join(work, `${sha}.tar.gz`);
  const [command, ...prefix] = python;
  const built = spawnSync(command, [...prefix, builder, out, sha, variant], { encoding: "utf8" });
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
    for (const sha of new Set(Object.values(shas))) {
      const variant = sha === shas.readme ? "readme" : sha === shas.marker ? "marker" : "sdk";
      archives.set(sha, tarball(work, [resolved.command, ...resolved.prefix], sha, variant));
    }
    server = createServer((request, response) => {
      requests.push(`${request.method} ${request.url}`);
      assert.equal(request.headers.authorization, `Bearer ${TOKEN}`);
      const commit = /^\/repos\/o\/r\/commits\/([^/]+)$/.exec(request.url ?? "");
      const tar = /^\/repos\/o\/r\/tarball\/([0-9a-f]{40})$/.exec(request.url ?? "");
      if (tar && tar[1] === shas.cut) {
        // The headers go out, then the connection drops before the body.
        response.writeHead(200, { "content-length": "100000" });
        response.write(archives.get(shas.cut)?.subarray(0, 10));
        setTimeout(() => response.destroy(), 20);
      } else if (commit && shas[decodeURIComponent(commit[1])]) {
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
    removeTree(work);
  });

  function service(storage: string, getSession: () => Promise<{ accessToken: string } | undefined> = async () => ({ accessToken: TOKEN }),
    maxDownload?: number) {
    return new SdkSourceService(python, { extensionPath: root, storage, development: true, apiBase: base, getSession, maxDownload });
  }
  const ref = (name: string, repository = "o/r") => ({ sdkPath: "", sdkRepository: repository, sdkRef: name });

  test("an archive without forge.py and kits/ is refused, and nothing is cached", async () => {
    const storage = join(work, "r1");
    const result = await service(storage).resolveWith(ref("readme"));
    assert.ok("state" in result && result.state === "sdk-archive-refused", JSON.stringify(result));
    assert.deepEqual(readdirSync(join(storage, "sdk")), []);
  });

  test("a cache entry that is not complete is rebuilt, never trusted", async () => {
    const storage = join(work, "r2");
    const entry = join(storage, "sdk", shas.main);
    mkdirSync(entry, { recursive: true });
    writeFileSync(join(entry, ".complete"), shas.main);
    const result = await service(storage).resolveWith(ref("main"));
    assert.ok("ok" in result, JSON.stringify(result));
    assert.ok(existsSync(join(result.folder, "forge.py")));
  });

  // A junction needs no rights on Windows, so anything running as this user can plant one in the cache.
  function planted(): string {
    const target = mkdtempSync(join(work, "victim-"));
    writeFileSync(join(target, "keep.txt"), "keep");
    return target;
  }

  test("an incomplete cache entry holding a junction is rebuilt without deleting through it", async () => {
    const storage = join(work, "r8");
    const entry = join(storage, "sdk", shas.main);
    mkdirSync(entry, { recursive: true });
    const target = planted();
    symlinkSync(target, join(entry, "link"), "junction");
    const result = await service(storage).resolveWith(ref("main"));
    assert.ok("ok" in result && existsSync(join(result.folder, "forge.py")), JSON.stringify(result));
    assert.deepEqual(readdirSync(target), ["keep.txt"], "the rebuild deleted through the junction");
  });

  test("an evicted cache entry holding a junction is removed without deleting through it", async () => {
    const storage = join(work, "s5");
    const sdk = service(storage);
    const target = planted();
    for (const name of ["main", "v2", "v3", "v4"]) {
      const result = await sdk.resolveWith(ref(name));
      assert.ok("ok" in result, name);
      if (name === "main") {
        symlinkSync(target, join(result.folder, "link"), "junction");
      }
      await new Promise((r) => setTimeout(r, 5));
    }
    assert.ok(!existsSync(join(storage, "sdk", shas.main)), "main was not evicted");
    assert.deepEqual(readdirSync(target), ["keep.txt"], "the eviction deleted through the junction");
  });

  test("two windows and two refs naming one commit all get the same complete entry", async () => {
    const storage = join(work, "r3");
    const results = await Promise.all([
      service(storage).resolveWith(ref("main")),
      service(storage).resolveWith(ref("alias")),
      service(storage).resolveWith(ref("main")),
    ]);
    for (const result of results) {
      assert.ok("ok" in result, JSON.stringify(result));
      assert.equal(result.folder, join(storage, "sdk", shas.main));
    }
    assert.deepEqual(readdirSync(join(storage, "sdk")), [shas.main], "a temporary file or folder was left");
    assert.ok(existsSync(join(storage, "sdk", shas.main, "forge.py")));
  });

  test("an archive carrying the cache's own marker names is refused, not a rejection", async () => {
    const result = await service(join(work, "r6")).resolveWith(ref("marker"));
    assert.ok("state" in result && result.state === "sdk-archive-refused" && /reserves/.test(result.message), JSON.stringify(result));
  });

  test("one window resolving two refs that name one commit downloads it once", async () => {
    const sdk = service(join(work, "r7"));
    const before = requests.filter((r) => r.includes(`/tarball/${shas.main}`)).length;
    const [a, b] = await Promise.all([sdk.resolveWith(ref("main")), sdk.resolveWith(ref("alias"))]);
    assert.ok("ok" in a && "ok" in b && a.folder === b.folder);
    assert.equal(requests.filter((r) => r.includes(`/tarball/${shas.main}`)).length - before, 1);
  });

  test("a connection that drops after the headers is offline, not an error", async () => {
    const result = await service(join(work, "r4")).resolveWith(ref("cut"));
    assert.ok("state" in result && result.state === "github-offline", JSON.stringify(result));
  });

  test("an archive larger than the limit is refused while it streams", async () => {
    const result = await service(join(work, "r5"), undefined, 64).resolveWith(ref("main"));
    assert.ok("state" in result && result.state === "sdk-archive-refused" && /larger than/.test(result.message), JSON.stringify(result));
  });

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
