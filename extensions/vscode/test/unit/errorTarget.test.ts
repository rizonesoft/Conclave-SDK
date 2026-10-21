import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { test } from "node:test";
import { errorTarget, type ErrorTarget } from "../../src/core/errorTarget";

// Compiled to out/test/unit/: the package root is three folders up.
const expected = JSON.parse(readFileSync(join(__dirname, "..", "..", "..", "test", "fixtures", "pins", "expected.json"), "utf8")) as
  Record<string, { ok: boolean; error?: string; error_prefix?: string }>;

// Where design/SPEC.md §4 attaches each refused fixture's message.
const WANT: Record<string, { kind: ErrorTarget["kind"]; reviewer?: string; writer?: string }> = {
  "refused-bad-name.toml": { kind: "name", reviewer: "Astra" },
  "refused-unknown-key.toml": { kind: "unknown-keys", reviewer: "astra" },
  "refused-bad-cli.toml": { kind: "cli", reviewer: "astra" },
  "refused-bad-model.toml": { kind: "model", reviewer: "astra" },
  "refused-agy-effort.toml": { kind: "stray-effort", reviewer: "gemini" },
  "refused-bad-effort.toml": { kind: "effort", reviewer: "astra" },
  "refused-no-reviewers.toml": { kind: "cards" },
  "refused-route-writer.toml": { kind: "unknown-writer" },
  "refused-empty-route.toml": { kind: "route", writer: "codex" },
  "refused-route-too-long.toml": { kind: "route", writer: "claude" },
  "refused-same-family.toml": { kind: "route", writer: "claude" },
  "refused-undefined-reviewer.toml": { kind: "route", writer: "codex" },
  "refused-schema-2.toml": { kind: "screen" },
  "refused-schema-bool.toml": { kind: "screen" },
  "refused-extra-table.toml": { kind: "screen" },
  "refused-unparsable.toml": { kind: "screen" },
  "refused-not-utf8.toml": { kind: "screen" },
  "refused-integer-too-long.toml": { kind: "screen" },
  "refused-nested-deep.toml": { kind: "screen" },
};

test("errorTarget: every refused fixture's message attaches where the SPEC says, verbatim", () => {
  const refused = Object.entries(expected).filter(([, e]) => !e.ok);
  assert.deepEqual(refused.map(([name]) => name).sort(), Object.keys(WANT).sort(), "a refused fixture has no expected target");
  for (const [name, e] of refused) {
    // A message whose tail is Python's own wording is tested with a tail of its shape.
    const message = e.error ?? `${e.error_prefix}Illegal character (at line 1, column 2)`;
    assert.deepEqual(errorTarget(message), { ...WANT[name], message }, name);
  }
});

test("errorTarget: an older dispatcher's route refusals still attach to the route row", () => {
  // Messages of a workspace dispatcher from before one reviewer per route (2026-10-21).
  for (const message of [
    "route 'claude' must list one reviewer and at most one fallback",
    "route 'codex' must list defined reviewers, each once",
    "route 'claude': the fallback must be of a third family, not the reviewer's own",
  ]) {
    assert.deepEqual(errorTarget(message), { kind: "route", writer: message.split("'")[1], message }, message);
  }
});

test("errorTarget: an unknown message attaches to the file with its text unchanged", () => {
  const message = "route 'claude' is something load_pin does not say yet";
  assert.deepEqual(errorTarget("a message no rule knows"), { kind: "file", message: "a message no rule knows" });
  assert.deepEqual(errorTarget(message), { kind: "file", message });
});

test("errorTarget: a name Python prints in double quotes is read too", () => {
  assert.deepEqual(errorTarget(`invalid reviewer "it's"`), { kind: "name", reviewer: "it's", message: `invalid reviewer "it's"` });
});

test("errorTarget: a name Python printed with escapes is decoded to the card's name", () => {
  // repr of a name holding a backslash doubles it; one holding both quotes uses '...' with \' inside.
  assert.deepEqual(errorTarget("invalid reviewer 'a\\\\b'"), { kind: "name", reviewer: "a\\b", message: "invalid reviewer 'a\\\\b'" });
  const both = `invalid reviewer 'it\\'s "x"'`;
  assert.deepEqual(errorTarget(both), { kind: "name", reviewer: `it's "x"`, message: both });
  assert.equal((errorTarget("invalid reviewer 'caf\\xe9'") as { reviewer: string }).reviewer, "caf\u00e9");
});
