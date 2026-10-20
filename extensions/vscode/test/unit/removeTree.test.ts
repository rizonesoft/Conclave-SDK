import assert from "node:assert/strict";
import { chmodSync, existsSync, mkdirSync, mkdtempSync, readdirSync, renameSync, symlinkSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { removeTree } from "../../src/host/removeTree";

// The fs module object removeTree calls through, so a test can step in between its lstat and its readdir. (Following a
// junction in rmSync is the extension host's own behaviour, tested in test/integration/removeTree.test.ts.)
const fs = createRequire(__filename)("node:fs") as typeof import("node:fs");

function during<T>(folder: string, act: () => void, body: () => T): T {
  const original = fs.readdirSync;
  let done = false;
  (fs as { readdirSync: unknown }).readdirSync = ((path: string, ...rest: unknown[]) => {
    if (!done && path === folder) {
      done = true;
      act();
    }
    return (original as (...a: unknown[]) => unknown)(path, ...rest);
  }) as typeof fs.readdirSync;
  try {
    return body();
  } finally {
    (fs as { readdirSync: unknown }).readdirSync = original;
  }
}

test("removeTree: a folder swapped for a link while it is removed stops the delete before anything outside goes", () => {
  const base = mkdtempSync(join(tmpdir(), "conclave-swap-"));
  try {
    const outside = join(base, "outside");
    mkdirSync(outside);
    writeFileSync(join(outside, "keep.txt"), "keep");
    const tree = join(base, "tree");
    mkdirSync(join(tree, "inner"), { recursive: true });
    writeFileSync(join(tree, "inner", "file.txt"), "x");
    const inner = join(tree, "inner");
    // After removeTree has read inner as a real folder, inner becomes a junction to outside.
    assert.throws(() => during(inner, () => {
      renameSync(inner, join(base, "moved"));
      symlinkSync(outside, inner, "junction");
    }, () => removeTree(tree)), /changed while it was being removed/);
    assert.deepEqual(readdirSync(outside), ["keep.txt"], "the delete went through the swapped-in link");
  } finally {
    removeTree(base);
  }
});

test("removeTree: a folder another window removes first is not an error", () => {
  const base = mkdtempSync(join(tmpdir(), "conclave-gone-"));
  try {
    const tree = join(base, "tree");
    mkdirSync(join(tree, "inner"), { recursive: true });
    writeFileSync(join(tree, "inner", "file.txt"), "x");
    // Between removeTree's lstat and its readdir, the whole tree goes.
    during(tree, () => fs.rmSync(tree, { recursive: true, force: true }), () => removeTree(tree));
    assert.ok(!existsSync(tree));
  } finally {
    removeTree(base);
  }
});

test("removeTree: a read-only file is removed", () => {
  const tree = mkdtempSync(join(tmpdir(), "conclave-readonly-"));
  writeFileSync(join(tree, "locked.txt"), "x");
  // The read-only attribute on Windows.
  chmodSync(join(tree, "locked.txt"), 0o444);
  removeTree(tree);
  assert.ok(!existsSync(tree));
});
