import assert from "node:assert/strict";
import { chmodSync, existsSync, mkdirSync, mkdtempSync, readdirSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { removeTree } from "../../src/host/removeTree";

// Runs in the extension host on purpose: VS Code's own runtime is where fs.rmSync(path, {recursive: true}) follows a
// junction, so a test under standalone Node could not fail.
suite("removeTree", () => {
  let outside: string;

  suiteSetup(() => {
    outside = mkdtempSync(join(tmpdir(), "conclave-outside-"));
    writeFileSync(join(outside, "keep.txt"), "keep");
  });

  // The outside folder holds no link, and the test checked its contents before getting here.
  suiteTeardown(() => removeTree(outside));

  test("removeTree: a tree holding a junction is removed and the junction's target keeps its files", () => {
    const tree = mkdtempSync(join(tmpdir(), "conclave-tree-"));
    mkdirSync(join(tree, "real", "deeper"), { recursive: true });
    writeFileSync(join(tree, "real", "deeper", "file.txt"), "x");
    writeFileSync(join(tree, "top.txt"), "x");
    // The read-only attribute on Windows, which unlink in this runtime clears by itself.
    writeFileSync(join(tree, "real", "locked.txt"), "x");
    chmodSync(join(tree, "real", "locked.txt"), 0o444);
    // A junction on Windows (no rights needed), a directory symlink on POSIX.
    symlinkSync(outside, join(tree, "real", "link"), "junction");
    removeTree(tree);
    assert.ok(!existsSync(tree), "the tree was not removed");
    assert.deepEqual(readdirSync(outside), ["keep.txt"], "the delete went through the junction");
  });

  test("removeTree: a link passed directly is removed as a link", () => {
    const holder = mkdtempSync(join(tmpdir(), "conclave-tree-"));
    const link = join(holder, "link");
    symlinkSync(outside, link, "junction");
    removeTree(link);
    assert.ok(!existsSync(link));
    assert.deepEqual(readdirSync(outside), ["keep.txt"]);
    removeTree(holder);
  });

  test("removeTree: a path that does not exist is not an error", () => {
    assert.doesNotThrow(() => removeTree(join(tmpdir(), "conclave-never-made-0f3a")));
  });
});
