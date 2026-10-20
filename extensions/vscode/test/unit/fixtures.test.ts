import assert from "node:assert/strict";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { test } from "node:test";

// Compiled to out/test/unit/, so the package root is three folders up.
const pins = join(__dirname, "..", "..", "..", "test", "fixtures", "pins");

test("every fixture pin expected.json names exists, and every fixture pin is named", () => {
  const expected = JSON.parse(readFileSync(join(pins, "expected.json"), "utf8")) as Record<string, unknown>;
  const named = Object.keys(expected).sort();
  assert.ok(named.length > 0, "expected.json names no fixture");
  for (const name of named) {
    assert.ok(existsSync(join(pins, name)), `${name} is in expected.json but not in test/fixtures/pins/`);
  }
  assert.deepEqual(readdirSync(pins).filter((f) => f.endsWith(".toml")).sort(), named);
});
