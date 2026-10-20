import assert from "node:assert/strict";
import { test } from "node:test";
import { findOnPath, fullyQualified } from "../../src/core/which";

const files = (...paths: string[]) => (p: string) => paths.map((x) => x.toLowerCase()).includes(p.toLowerCase());

test("a python.exe in the workspace folder is never found when it is not on PATH", () => {
  // The workspace is the working directory; only PATH directories are searched, so the stub is invisible.
  const runnable = files("R:\\repo\\python.exe");
  assert.equal(findOnPath("python", { platform: "win32", path: "C:\\Windows", pathext: ".EXE", runnable }), undefined);
  assert.equal(findOnPath("python", { platform: "win32", path: ".;C:\\Windows", pathext: ".EXE", runnable }), undefined);
});

test("relative, drive-relative and empty PATH entries are not searched", () => {
  for (const entry of [".", "bin", "\\repo", "C:repo", ""]) {
    assert.equal(fullyQualified(entry, "win32"), false, entry);
  }
  for (const entry of ["C:\\Python314", "c:/tools", "\\\\server\\share\\bin"]) {
    assert.equal(fullyQualified(entry, "win32"), true, entry);
  }
  assert.equal(fullyQualified("bin", "linux"), false);
  assert.equal(fullyQualified("/usr/bin", "linux"), true);
});

test("Windows finds a PATHEXT name before the bare name, and falls back to the defaults", () => {
  const runnable = files("C:\\npm\\codex", "C:\\npm\\codex.CMD", "C:\\Python314\\python.EXE");
  const env = { platform: "win32" as const, path: "C:\\npm;C:\\Python314", runnable };
  assert.equal(findOnPath("codex", { ...env, pathext: ".EXE;.CMD" }), "C:\\npm\\codex.CMD");
  assert.equal(findOnPath("python", { ...env, pathext: "" }), "C:\\Python314\\python.EXE");
  // A PATHEXT entry that is a path, not an extension, is dropped.
  assert.equal(findOnPath("python", { ...env, pathext: "\\..\\..\\evil.exe" }), "C:\\Python314\\python.EXE");
});

test("Linux searches the absolute PATH directories in order", () => {
  const runnable = files("/usr/local/bin/python3", "/usr/bin/python3");
  assert.equal(findOnPath("python3", { platform: "linux", path: "/usr/local/bin:/usr/bin", runnable }), "/usr/local/bin/python3");
  assert.equal(findOnPath("python3", { platform: "linux", path: "bin:./x", runnable: () => true }), undefined);
});
