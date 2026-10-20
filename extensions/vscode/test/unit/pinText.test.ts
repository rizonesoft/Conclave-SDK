import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import {
  addReviewer,
  deleteReviewer,
  isEditableLayout,
  readPin,
  removeRoute,
  renameReviewer,
  setField,
  setRoute,
} from "../../src/core/pinText";
import { findOnPath } from "../../src/core/which";

// Compiled to out/test/unit/, so the package root is three folders up and the SDK root five.
const root = join(__dirname, "..", "..", "..");
const fixtures = join(root, "test", "fixtures");
const dispatcher = join(root, "..", "..", "kits", "reviewer", "templates", "scripts", "review-dispatch.py");
const shipped = readFileSync(join(fixtures, "pins", "valid-shipped.toml"), "utf8");

type Edit = [string, ...unknown[]];
const EDITS: Record<string, (text: string, ...args: never[]) => string> = {
  set_field: setField,
  add_reviewer: addReviewer,
  rename_reviewer: renameReviewer,
  delete_reviewer: deleteReviewer,
  set_route: setRoute,
  remove_route: removeRoute,
};

function apply(text: string, edits: Edit[]): string {
  return edits.reduce((current, [name, ...args]) => {
    const edit = EDITS[name];
    assert.ok(edit, `unknown edit ${name}`);
    return edit(current, ...(args as never[]));
  }, text);
}

const cases = readdirSync(join(fixtures, "edits")).filter((d) => statSync(join(fixtures, "edits", d)).isDirectory());
const read = (name: string, file: string) => readFileSync(join(fixtures, "edits", name, file), "utf8");

// The interpreter for the dispatcher check, found on PATH only, as the extension finds it.
function python(): string[] {
  const isFile = (p: string) => {
    try {
      return statSync(p).isFile();
    } catch {
      return false;
    }
  };
  const env = { platform: process.platform, path: process.env.PATH ?? "", pathext: process.env.PATHEXT, isFile };
  const found = process.platform === "win32"
    ? (findOnPath("py", env) ? [findOnPath("py", env) as string, "-3"] : [findOnPath("python", env) as string])
    : [(findOnPath("python3", env) ?? findOnPath("python", env)) as string];
  assert.ok(found[0], "no Python on PATH to run the dispatcher");
  return found;
}

test("pinText: every golden edit gives the reference's bytes, LF and CRLF", () => {
  assert.equal(cases.length, 12, `expected 12 golden cases, found ${cases.join(", ")}`);
  for (const name of cases) {
    const input = read(name, "input.toml");
    const edits = JSON.parse(read(name, "edits.json")) as Edit[];
    const expected = read(name, "expected.toml");
    assert.equal(apply(input, edits), expected, `${name}: LF`);
    assert.equal(apply(input.replace(/\n/g, "\r\n"), edits), expected.replace(/\n/g, "\r\n"), `${name}: CRLF`);
  }
});

test("pinText: every golden output is a pin the dispatcher accepts", () => {
  const [command, ...prefix] = python();
  const folder = mkdtempSync(join(tmpdir(), "conclave-pintext-"));
  try {
    for (const name of cases) {
      const file = join(folder, `${name}.toml`);
      writeFileSync(file, read(name, "expected.toml"));
      const out = execFileSync(command, [...prefix, dispatcher, "--check-pin", "--json", "--pin", file], { encoding: "utf8" });
      assert.equal(JSON.parse(out).ok, true, `${name}: ${out}`);
    }
  } finally {
    rmSync(folder, { recursive: true, force: true });
  }
});

test("pinText: a deleted reviewer takes its comment block and leaves no orphan comment", () => {
  const out = deleteReviewer(shipped, "sonnet");
  assert.ok(!out.includes("# Sonnet 5.5 through Claude Code in plan mode."));
  assert.ok(out.includes("# Each writer is reviewed by the other two families"), "the [routes] comment went too");
});

test("pinText: the editable layout is the shipped one, LF or CRLF, and nothing else", () => {
  assert.ok(isEditableLayout(shipped));
  assert.ok(isEditableLayout(shipped.replace(/\n/g, "\r\n")));
  assert.ok(isEditableLayout(readFileSync(join(fixtures, "pins", "valid-comments.toml"), "utf8")));
  for (const [label, text] of [
    ["inline table", readFileSync(join(fixtures, "pins", "valid-inline-layout.toml"), "utf8")],
    ["quoted key", shipped.replace('cli = "codex"', '"cli" = "codex"')],
    ["dotted key", shipped.replace('cli = "codex"', 'reviewers.astra.cli = "codex"')],
    ["escape", shipped.replace('model = "gpt-6-astra"', 'model = "gpt-6\\u002dastra"')],
    ["two-line array", shipped.replace('claude = ["astra", "gemini"]', 'claude = [\n  "astra", "gemini"]')],
  ]) {
    assert.notEqual(text, shipped, `${label}: the fixture edit matched nothing`);
    assert.equal(isEditableLayout(text), false, label);
    assert.equal(readPin(text), undefined, label);
  }
});

test("pinText: readPin's spans slice back to the text, and an unchanged value leaves it byte for byte", () => {
  for (const file of ["valid-shipped.toml", "valid-comments.toml", "valid-no-codex-route.toml"]) {
    const text = readFileSync(join(fixtures, "pins", file), "utf8");
    const view = readPin(text);
    assert.ok(view, file);
    assert.deepEqual(view.reviewers.map((r) => r.name), ["astra", "gemini", "sonnet"], file);
    for (const r of view.reviewers) {
      assert.ok(text.slice(r.span.start, r.span.end).startsWith(`[reviewers.${r.name}]`), `${file}: ${r.name}`);
      if (r.model) {
        assert.equal(setField(text, r.name, "model", r.model), text, `${file}: ${r.name} rewritten unchanged`);
      }
    }
    for (const route of view.routes) {
      assert.ok(text.slice(route.span.start, route.span.end).startsWith(`${route.writer} = [`), `${file}: ${route.writer}`);
      assert.equal(setRoute(text, route.writer, route.names), text, `${file}: ${route.writer} rewritten unchanged`);
    }
  }
  const view = readPin(shipped);
  assert.deepEqual(view?.reviewers.find((r) => r.name === "gemini"), {
    name: "gemini", cli: "agy", model: "gemini-4-argon-high", span: view?.reviewers[1].span,
  });
  assert.deepEqual(view?.routes.map((r) => [r.writer, r.names]), [
    ["claude", ["astra", "gemini"]], ["codex", ["gemini", "sonnet"]], ["gemini", ["astra", "sonnet"]],
  ]);
});
