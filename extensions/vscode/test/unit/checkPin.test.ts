import assert from "node:assert/strict";
import { execFileSync, spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { test } from "node:test";
import { parseCheckPin } from "../../src/core/checkPin";
import { findOnPath } from "../../src/core/which";
import { runnable } from "../../src/host/run";

// Compiled to out/test/unit/, so the package root is three folders up and the SDK root five.
const root = join(__dirname, "..", "..", "..");
const pins = join(root, "test", "fixtures", "pins");
const dispatcher = join(root, "..", "..", "kits", "reviewer", "templates", "scripts", "review-dispatch.py");
const old = join(root, "test", "fixtures", "dispatchers", "review-dispatch-b7c649b.py");

interface Expected {
  exit: number;
  ok: boolean;
  error?: string;
  error_prefix?: string;
}
const expected = JSON.parse(readFileSync(join(pins, "expected.json"), "utf8")) as Record<string, Expected>;

function python(): string[] {
  const env = { platform: process.platform, path: process.env.PATH ?? "", pathext: process.env.PATHEXT, runnable };
  const py = process.platform === "win32" ? findOnPath("py", env) : undefined;
  const found = py ? [py, "-3"] : [(findOnPath("python3", env) ?? findOnPath("python", env)) as string];
  assert.ok(found[0], "no Python on PATH to run the dispatcher");
  return found;
}

function checkPin(script: string, pin: string): { stdout: string; code: number | undefined } {
  const [command, ...prefix] = python();
  const run = spawnSync(command, [...prefix, script, "--check-pin", "--json", "--pin", pin], { encoding: "utf8" });
  return { stdout: run.stdout, code: run.status ?? undefined };
}

test("checkPin: every contract fixture gets its state and the dispatcher's exact error", () => {
  for (const [name, want] of Object.entries(expected)) {
    const pin = join(pins, name);
    const { stdout, code } = checkPin(dispatcher, pin);
    // The pin's text only matters for a valid pin (its layout); a refused one is the dispatcher's verdict alone.
    const state = parseCheckPin(stdout, code, readFileSync(pin, "utf8"));
    if (want.ok) {
      assert.equal(state.state, name === "valid-inline-layout.toml" ? "pin-layout" : "ready", name);
    } else if (want.error_prefix) {
      assert.equal(state.state, "refused", name);
      assert.ok(state.state === "refused" && state.error.startsWith(want.error_prefix), name);
    } else {
      assert.deepEqual(state, { state: "refused", error: want.error }, name);
    }
  }
});

test("checkPin: a missing pin is no-pin, from the dispatcher's own message", () => {
  const { stdout, code } = checkPin(dispatcher, join(pins, "no-such-pin.toml"));
  const state = parseCheckPin(stdout, code);
  assert.equal(state.state, "no-pin");
  assert.ok(state.state === "no-pin" && state.error.startsWith("no reviewer pin at"));
});

test("checkPin: a dispatcher from before --check-pin is old-dispatcher, though it exits 2 like a refusal", () => {
  const { stdout, code } = checkPin(old, join(pins, "valid-shipped.toml"));
  assert.equal(code, 2);
  const state = parseCheckPin(stdout, code);
  assert.equal(state.state, "old-dispatcher");
  for (const [out, exit] of [["", 1], ["Traceback (most recent call last):", 1], ["[1, 2]", 0], ['{"ok": true}', 2]] as const) {
    assert.equal(parseCheckPin(out, exit).state, "old-dispatcher", JSON.stringify([out, exit]));
  }
});

test("checkPin: a newer schema the dispatcher accepts is unsupported-schema, and the shipped pin is ready", () => {
  const { stdout, code } = checkPin(dispatcher, join(pins, "valid-shipped.toml"));
  assert.equal(parseCheckPin(stdout, code, readFileSync(join(pins, "valid-shipped.toml"), "utf8")).state, "ready");
  const newer = JSON.stringify({ ...JSON.parse(stdout), schema_version: 2 });
  assert.deepEqual(Object.keys(parseCheckPin(newer, 0)), ["state", "version", "report"]);
  assert.equal(parseCheckPin(newer, 0).state, "unsupported-schema");
});

test("checkPin: the real dispatcher is the one under test", () => {
  // Guards the fixture path: a moved dispatcher would make every case above an error, not a pass.
  const [command, ...prefix] = python();
  assert.match(execFileSync(command, [...prefix, dispatcher, "--help"], { encoding: "utf8" }), /--check-pin/);
});
