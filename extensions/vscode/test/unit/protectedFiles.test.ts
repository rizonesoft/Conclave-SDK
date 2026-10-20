import assert from "node:assert/strict";
import { chmodSync, mkdirSync, mkdtempSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { protectedChanges } from "../../src/core/protectedFiles";
import { protectedSnapshot, Unreadable } from "../../src/host/protectedFiles";
import { removeTree } from "../../src/host/removeTree";

test("protectedFiles: a protected file changed or removed is reported unless forge said it wrote it", () => {
  const before = new Map([["AGENTS.md", "a"], ["todo/README.md", "b"], ["docs/x.md", "c"], [".claude/settings.json", "d"]]);
  const after = new Map([["AGENTS.md", "a2"], ["todo/README.md", "b"], [".claude/settings.json", "d2"], ["docs/new.md", "n"]]);
  // AGENTS.md changed and docs/x.md disappeared; .claude/settings.json changed but forge reported writing it; a new
  // file is not a change to an existing one.
  assert.deepEqual(protectedChanges(before, after, [".claude/settings.json"]), ["AGENTS.md", "docs/x.md"]);
  assert.deepEqual(protectedChanges(before, new Map(before), []), []);
  // forge may report a path with backslashes on Windows.
  assert.deepEqual(protectedChanges(new Map([["todo/a.md", "1"]]), new Map([["todo/a.md", "2"]]), ["todo\\a.md"]), []);
});

test("protectedFiles: a linked protected folder or ancestor is recorded as a link and never read through", () => {
  const base = mkdtempSync(join(tmpdir(), "conclave-protected-"));
  try {
    const outside = join(base, "outside");
    mkdirSync(outside);
    writeFileSync(join(outside, "a.md"), "outside");
    writeFileSync(join(outside, "settings.json"), "outside");
    const work = join(base, "work");
    mkdirSync(join(work, "todo"), { recursive: true });
    writeFileSync(join(work, "todo", "README.md"), "mine");
    // Junctions on Windows (no rights needed), directory symlinks elsewhere.
    symlinkSync(outside, join(work, "docs"), "junction");
    symlinkSync(outside, join(work, ".claude"), "junction");
    const snapshot = protectedSnapshot(work);
    assert.deepEqual([...snapshot.keys()].sort(), [".claude", "docs", "todo/README.md"]);
    assert.ok(snapshot.get("docs")?.startsWith("link:") && snapshot.get(".claude")?.startsWith("link:"));
    // A change outside the folder is not a change to the project; a retargeted link is.
    writeFileSync(join(outside, "a.md"), "changed outside");
    assert.deepEqual(protectedChanges(snapshot, protectedSnapshot(work), []), []);
    const elsewhere = join(base, "elsewhere");
    mkdirSync(elsewhere);
    removeTree(join(work, "docs"));
    symlinkSync(elsewhere, join(work, "docs"), "junction");
    assert.deepEqual(protectedChanges(snapshot, protectedSnapshot(work), []), ["docs"]);
  } finally {
    removeTree(base);
  }
});

test("protectedFiles: a protected file that exists but cannot be read is an error, not an absence", { skip: (process.platform === "win32" && "mode 000 does not stop the owner reading on Windows") || (process.getuid?.() === 0 && "root reads mode 000") }, () => {
  const work = mkdtempSync(join(tmpdir(), "conclave-protected-"));
  try {
    writeFileSync(join(work, "AGENTS.md"), "mine");
    mkdirSync(join(work, "docs"));
    chmodSync(join(work, "AGENTS.md"), 0o000);
    assert.throws(() => protectedSnapshot(work), (error: unknown) => error instanceof Unreadable && error.path === "AGENTS.md");
    chmodSync(join(work, "AGENTS.md"), 0o600);
    chmodSync(join(work, "docs"), 0o000);
    assert.throws(() => protectedSnapshot(work), (error: unknown) => error instanceof Unreadable && error.path === "docs");
    chmodSync(join(work, "docs"), 0o700);
  } finally {
    removeTree(work);
  }
});
