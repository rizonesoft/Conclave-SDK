import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync, mkdtempSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { findOnPath } from "../../src/core/which";
import { runnable } from "../../src/host/run";

// Compiled to out/test/unit/: the package root is three folders up.
const extractor = join(__dirname, "..", "..", "..", "resources", "extract_sdk.py");

function python(): string[] {
  const env = { platform: process.platform, path: process.env.PATH ?? "", pathext: process.env.PATHEXT, runnable };
  const py = process.platform === "win32" ? findOnPath("py", env) : undefined;
  const found = py ? [py, "-3"] : [(findOnPath("python3", env) ?? findOnPath("python", env)) as string];
  assert.ok(found[0], "no Python on PATH");
  return found;
}

// Builds a .tar.gz from member specs with Python's tarfile, which can write names no well-behaved tool would.
const BUILD = `
import io, json, sys, tarfile
spec = json.loads(sys.argv[2])
with tarfile.open(sys.argv[1], "w:gz") as tar:
    for kind, name, extra in spec:
        info = tarfile.TarInfo(name)
        if kind == "dir":
            info.type = tarfile.DIRTYPE
            tar.addfile(info)
        elif kind == "file":
            data = extra.encode()
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        elif kind == "symlink":
            info.type = tarfile.SYMTYPE
            info.linkname = extra
            tar.addfile(info)
        elif kind == "hardlink":
            info.type = tarfile.LNKTYPE
            info.linkname = extra
            tar.addfile(info)
`;

type Member = ["dir" | "file" | "symlink" | "hardlink", string, string];
const TOP: Member[] = [["dir", "o-r-1234567", ""], ["file", "o-r-1234567/forge.py", "print('forge')\n"], ["dir", "o-r-1234567/kits", ""]];

function extract(members: Member[]): { code: number | null; reply: { ok: boolean; top?: string; error?: string }; dest: string } {
  const [command, ...prefix] = python();
  const work = mkdtempSync(join(tmpdir(), "conclave-extract-"));
  const builder = join(work, "build.py");
  writeFileSync(builder, BUILD);
  const archive = join(work, "sdk.tar.gz");
  const built = spawnSync(command, [...prefix, builder, archive, JSON.stringify(members)], { encoding: "utf8" });
  assert.equal(built.status, 0, built.stderr);
  const dest = join(work, "out");
  const run = spawnSync(command, [...prefix, "-I", extractor, archive, dest], { encoding: "utf8" });
  return { code: run.status, reply: JSON.parse(run.stdout), dest };
}

test("extractSdk: a well-formed archive extracts under its single top folder", () => {
  const { code, reply, dest } = extract(TOP);
  assert.equal(code, 0, JSON.stringify(reply));
  assert.deepEqual(reply, { ok: true, top: "o-r-1234567", files: 1 });
  assert.ok(existsSync(join(dest, "o-r-1234567", "forge.py")));
  rmSync(join(dest, ".."), { recursive: true, force: true });
});

test("extractSdk: every unsafe member refuses the whole archive and writes nothing", () => {
  const cases: [string, Member[]][] = [
    ["../evil", [...TOP, ["file", "o-r-1234567/../evil", "x"]]],
    ["/abs", [...TOP, ["file", "/abs", "x"]]],
    ["C:/abs", [...TOP, ["file", "C:/abs", "x"]]],
    ["a\\..\\b", [...TOP, ["file", "o-r-1234567\\..\\b", "x"]]],
    ["internal symlink", [...TOP, ["symlink", "o-r-1234567/link", "forge.py"]]],
    ["hard link", [...TOP, ["hardlink", "o-r-1234567/hard", "o-r-1234567/forge.py"]]],
    ["second top folder", [...TOP, ["file", "other/forge.py", "x"]]],
    ["file at the top", [["file", "loose.py", "x"]]],
  ];
  for (const [label, members] of cases) {
    const { code, reply, dest } = extract(members);
    assert.equal(code, 2, `${label}: ${JSON.stringify(reply)}`);
    assert.equal(reply.ok, false, label);
    assert.ok(reply.error, label);
    assert.ok(!existsSync(dest) || readdirSync(dest).length === 0, `${label}: something was written`);
    rmSync(join(dest, ".."), { recursive: true, force: true });
  }
});
