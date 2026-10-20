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

// Builds a .tar.gz from member specs with Python's tarfile, which can write names no well-behaved tool would. The raw
// kinds write header blocks directly (tarfile's own extended-header encoder, at the writer's offset), to build the
// archives a hostile server would send.
const BUILD = `
import io, json, sys, tarfile

def extended(headers, kind=tarfile.XHDTYPE):
    return tarfile.TarInfo._create_pax_generic_header(headers, kind, "utf-8")

def plain(name, data):
    info = tarfile.TarInfo(name)
    info.size = len(data)
    pad = (512 - len(data) % 512) % 512
    return info.tobuf(tarfile.USTAR_FORMAT, "utf-8", "strict") + data + bytes(pad)

def raw(tar, data):
    tar.fileobj.write(data)
    tar.offset += len(data)

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
        elif kind == "pax":
            info.pax_headers = {"comment": "x" * int(extra)}
            info.size = 1
            tar.addfile(info, io.BytesIO(b"x"))
        elif kind == "paxsize":
            # A PAX size of 512 on a header that says 0: tarfile skips the next 512 bytes as that file's data, where a
            # walker reading the raw headers sees two zero blocks' worth of end. Behind it, a large extended header.
            hidden = extended({"size": "512"}) + plain(name, b"")[:512] + bytes(512)
            raw(tar, hidden + extended({"comment": "x" * int(extra)}) + plain(name + ".after", b"x"))
        elif kind == "solaris":
            raw(tar, extended({"comment": "x" * int(extra)}, tarfile.SOLARIS_XHDTYPE) + plain(name, b"x"))
        elif kind == "chain":
            raw(tar, b"".join(extended({"comment": str(i)}) for i in range(int(extra))) + plain(name, b"x"))
        elif kind == "flood":
            # Members whose extended headers each stay under the 1 MB cap and whose files are empty: only the
            # decompressed stream as a whole is too large.
            for i in range(int(extra)):
                raw(tar, extended({"comment": "x" * 1_000_000}) + plain(f"{name}/{i}", b""))
        elif kind == "paxsparse":
            # A small PAX header selecting a GNU sparse 1.0 map, and a map of int(extra) regions in the file's data.
            headers = {"GNU.sparse.major": "1", "GNU.sparse.minor": "0", "GNU.sparse.realsize": extra, "GNU.sparse.name": name}
            raw(tar, extended(headers) + plain(name, (extra + "\\n" + "0\\n1\\n" * int(extra)).encode()))
        elif kind == "globalkeys":
            # One global PAX header with int(extra) keys, which tarfile copies into every later member, then 300 members.
            raw(tar, extended({f"k{i}": "v" for i in range(int(extra))}, tarfile.XGLTYPE)
                + b"".join(plain(f"{name}/f{i}", b"") for i in range(300)))
        elif kind == "globalpath":
            # One global PAX path (int(extra) characters, ending in "/"), which every later member takes as its name,
            # then more members than the member limit: checked as read, the second member is refused as a repeat;
            # checked only after reading, the member limit is what refuses it.
            raw(tar, extended({"path": name + "/" + "a" * int(extra) + "/"}, tarfile.XGLTYPE)
                + b"".join(plain(f"{name}/f{i}", b"") for i in range(20_001)))
        elif kind == "paxkey":
            raw(tar, extended({"mtime": "9" * 1000}) + plain(name, b"x"))
        elif kind == "longpath":
            raw(tar, extended({"path": name + "/" + "a" * int(extra)}) + plain(name, b"x"))
        elif kind == "sparse":
            info.type = tarfile.GNUTYPE_SPARSE
            tar.addfile(info)
        elif kind == "hardlink":
            info.type = tarfile.LNKTYPE
            info.linkname = extra
            tar.addfile(info)
`;

type Member = ["dir" | "file" | "symlink" | "hardlink" | "pax" | "paxsize" | "solaris" | "chain" | "flood" | "sparse" | "paxsparse" | "globalkeys" | "globalpath" | "paxkey" | "longpath", string, string];
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

// Each case names the reason it must be refused for, so a check that is removed cannot hide behind another.
test("extractSdk: every unsafe member refuses the whole archive and writes nothing", () => {
  const cases: [string, RegExp, Member[]][] = [
    ["../evil", /leaves the archive's folder/, [...TOP, ["file", "o-r-1234567/../evil", "x"]]],
    ["/abs", /absolute name/, [...TOP, ["file", "/abs", "x"]]],
    ["C:/abs", /absolute name/, [...TOP, ["file", "C:/abs", "x"]]],
    ["a\\..\\b", /leaves the archive's folder/, [...TOP, ["file", "o-r-1234567\\..\\b", "x"]]],
    ["internal symlink", /not a regular file or a folder/, [...TOP, ["symlink", "o-r-1234567/link", "forge.py"]]],
    ["hard link", /not a regular file or a folder/, [...TOP, ["hardlink", "o-r-1234567/hard", "o-r-1234567/forge.py"]]],
    ["second top folder", /2 top folders/, [...TOP, ["file", "other/forge.py", "x"]]],
    ["file at the top", /outside the archive's top folder/, [["file", "loose.py", "x"]]],
    ["a metadata header over 1 MB", /metadata header of \d+ bytes/, [...TOP, ["pax", "o-r-1234567/big.txt", String(2 * 1024 * 1024)]]],
    ["a large header behind a PAX size", /holds 'size'/, [...TOP, ["paxsize", "o-r-1234567/hidden.txt", String(2 * 1024 * 1024)]]],
    ["a large Solaris extended header", /metadata header of \d+ bytes/, [...TOP, ["solaris", "o-r-1234567/sun.txt", String(2 * 1024 * 1024)]]],
    ["a chain of extended headers", /extended headers in a row/, [...TOP, ["chain", "o-r-1234567/chain.txt", "2000"]]],
    ["a sparse member", /sparse/, [...TOP, ["sparse", "o-r-1234567/sparse.bin", ""]]],
    ["a PAX sparse map", /refused before it is read/, [...TOP, ["paxsparse", "o-r-1234567/map.bin", "300000"]]],
    ["a global PAX header with many keys", /PAX header with 10000 keys/, [...TOP, ["globalkeys", "o-r-1234567/kits", "10000"]]],
    ["a global PAX path every member takes", /appears twice/, [...TOP, ["globalpath", "o-r-1234567", "3000"]]],
    ["a PAX key git does not write", /holds 'mtime'/, [...TOP, ["paxkey", "o-r-1234567/old.txt", ""]]],
    ["a PAX path over 4096 characters", /PAX path of \d+ characters/, [...TOP, ["longpath", "o-r-1234567", "5000"]]],
    ["a stream past the decompressed limit", /decompresses to more than/, [...TOP, ["flood", "o-r-1234567/kits", "280"]]],
    ["names differing in case", /repeats/, [...TOP, ["file", "o-r-1234567/FORGE.PY", "print('other')"]]],
    ["a name twice", /appears twice/, [...TOP, ["file", "o-r-1234567/forge.py", "print('other')"]]],
    ["a trailing period Windows drops", /Windows cannot hold/, [...TOP, ["file", "o-r-1234567/forge.py.", "print('other')"]]],
    ["a trailing space", /Windows cannot hold/, [...TOP, ["file", "o-r-1234567/forge.py ", "print('other')"]]],
    ["an alternate data stream", /Windows cannot hold/, [...TOP, ["file", "o-r-1234567/forge.py:evil", "x"]]],
    ["a device name", /Windows cannot hold/, [...TOP, ["file", "o-r-1234567/kits/NUL.txt", "x"]]],
  ];
  for (const [label, reason, members] of cases) {
    const { code, reply, dest } = extract(members);
    assert.equal(code, 2, `${label}: ${JSON.stringify(reply)}`);
    assert.equal(reply.ok, false, label);
    assert.match(reply.error ?? "", reason, label);
    assert.ok((reply.error ?? "").length < 600, `${label}: a reply of ${reply.error?.length} characters`);
    assert.ok(!existsSync(dest) || readdirSync(dest).length === 0, `${label}: something was written`);
    rmSync(join(dest, ".."), { recursive: true, force: true });
  }
});
