import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { findOnPath } from "../../src/core/which";
import { singleReviewerPin } from "../../src/core/testPin";
import { runnable } from "../../src/host/run";

// Compiled to out/test/unit/: the package root is three up, and the dispatcher is the reviewer kit's own.
const root = join(__dirname, "..", "..", "..");
const dispatcher = join(root, "..", "..", "kits", "reviewer", "templates", "scripts", "review-dispatch.py");
const shipped = readFileSync(join(root, "test", "fixtures", "workspaces", "shipped", ".conclave", "reviewers.toml"), "utf8");

function python(): string[] {
  const env = { platform: process.platform, path: process.env.PATH ?? "", pathext: process.env.PATHEXT, runnable };
  const found = process.platform === "win32"
    ? (findOnPath("py", env) ? [findOnPath("py", env) as string, "-3"] : [findOnPath("python", env) as string])
    : [(findOnPath("python3", env) ?? findOnPath("python", env)) as string];
  assert.ok(found[0], "no Python on PATH to run the dispatcher");
  return found;
}

test("testPin: each shipped reviewer alone, on one route of another family, is a pin the dispatcher accepts", () => {
  const [command, ...prefix] = python();
  const work = mkdtempSync(join(tmpdir(), "conclave-testpin-"));
  try {
    const want: Record<string, [string, string, string]> = {
      astra: ["claude", "codex", "gpt-6-astra"],
      gemini: ["claude", "agy", "gemini-4-argon-high"],
      sonnet: ["codex", "claude", "claude-sonnet-5-5"],
    };
    for (const [name, [writer, cli, model]] of Object.entries(want)) {
      const pin = singleReviewerPin(shipped, name);
      assert.ok(pin, name);
      assert.equal(pin.writer, writer, name);
      assert.deepEqual([pin.reviewer.cli, pin.reviewer.model], [cli, model], name);
      const file = join(work, `${name}.toml`);
      writeFileSync(file, pin.text);
      const report = JSON.parse(execFileSync(command, [...prefix, dispatcher, "--check-pin", "--json", "--pin", file], { encoding: "utf8" }));
      assert.equal(report.ok, true, `${name}: ${JSON.stringify(report)}`);
      assert.deepEqual(Object.keys(report.reviewers), [name]);
      assert.deepEqual(report.routes, { [writer]: [name] });
      // The reviewer's own table is kept as written, comment included.
      assert.ok(pin.text.includes(shipped.slice(pin.reviewer.span.start, pin.reviewer.span.end)), name);
    }
  } finally {
    rmSync(work, { recursive: true, force: true });
  }
});

test("testPin: an unknown reviewer, an unknown CLI or a layout the editor does not edit gives no pin", () => {
  assert.equal(singleReviewerPin(shipped, "nobody"), undefined);
  assert.equal(singleReviewerPin(shipped.replace('cli = "agy"', 'cli = "gemini-cli"'), "gemini"), undefined);
  assert.equal(singleReviewerPin("schema_version = 1\nreviewers = { astra = { cli = \"codex\" } }\n", "astra"), undefined);
  // A CLI named after an object property is unknown, not a lookup of Object's members.
  assert.equal(singleReviewerPin(shipped.replace('cli = "claude"', 'cli = "constructor"'), "sonnet"), undefined);
  // No [routes] table: the text model cannot add a route, so there is no pin (a refusal, not a throw).
  assert.equal(singleReviewerPin(shipped.slice(0, shipped.indexOf("# Each writer is reviewed")), "sonnet"), undefined);
});
