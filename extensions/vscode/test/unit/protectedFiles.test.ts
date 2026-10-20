import assert from "node:assert/strict";
import { test } from "node:test";
import { protectedChanges } from "../../src/core/protectedFiles";

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
