import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { test } from "node:test";
import { parseKit } from "../../src/core/forgeJson";
import { kitState, refusalReason } from "../../src/core/kitState";

// forge's own dry runs, recorded by scripts/record-forge-fixtures.py on four folders: empty, base only, every kit that
// applies outside a Laravel app, and provisioned for Claude alone.
const fixtures = join(__dirname, "..", "..", "..", "test", "fixtures", "forge");
const KITS = ["base", "todo", "reviewer", "automations", "wordpress"];

function state(folder: string, kit: string) {
  const parsed = parseKit(readFileSync(join(fixtures, `dry-${folder}-${kit}.json`), "utf8"));
  assert.ok(parsed.ok, `${folder} ${kit}`);
  return kitState(parsed.value);
}

test("kitState: each recorded folder gives the expected state for every kit", () => {
  const want: Record<string, Record<string, string>> = {
    empty: { base: "not-installed", todo: "not-installed", reviewer: "not-installed", automations: "not-installed", wordpress: "not-installed" },
    base: { base: "installed", todo: "not-installed", reviewer: "not-installed", automations: "not-installed", wordpress: "not-installed" },
    all: { base: "installed", todo: "installed", reviewer: "installed", automations: "installed", wordpress: "installed" },
    claude: { base: "partly", todo: "not-installed", reviewer: "not-installed", automations: "not-installed", wordpress: "not-installed" },
  };
  for (const [folder, kits] of Object.entries(want)) {
    for (const kit of KITS) {
      assert.equal(state(folder, kit).state, kits[kit], `${folder} ${kit}`);
    }
  }
  assert.deepEqual(state("base", "base"), { kit: "base", state: "installed", kept: 28 });
  assert.deepEqual(state("empty", "reviewer"), { kit: "reviewer", state: "not-installed", add: 8 });
});

test("kitState: partly installed says how many files are missing and names the first five", () => {
  const partly = state("claude", "base");
  assert.ok(partly.state === "partly");
  assert.equal(partly.add, 14);
  assert.equal(partly.kept, 14);
  // Both agent folders a Claude-only repository lacks are named, with how many files each is missing.
  assert.match(partly.reason, /^14 of 28 files are missing \(5 in \.agents\/, 7 in \.codex\/, CODEX\.md, GEMINI\.md\): /);
  assert.match(partly.reason, /, and 9 more$/);
  const named = partly.reason.replace(/^[^:]*: /, "").replace(/, and 9 more$/, "").split(", ");
  assert.equal(named.length, 5);
  // The Codex files a Claude-only folder lacks are among those forge would add.
  const raw = JSON.parse(readFileSync(join(fixtures, "dry-claude-base.json"), "utf8"));
  assert.ok(raw.installed.some((p: string) => p.startsWith(".codex/")));
  assert.ok(raw.installed.every((p: string) => !p.startsWith(".claude/")));
});

test("kitState: an empty preserved list with files to add is not installed, never partly", () => {
  const dry = { target: "<TARGET>", kit: "todo", agent: "all", dryRun: true, installed: ["a", "b"], updated: [], preserved: [], mergeNeeded: [] };
  assert.deepEqual(kitState(dry), { kit: "todo", state: "not-installed", add: 2 });
  // A file forge would update on a refresh is there too.
  assert.equal(kitState({ ...dry, updated: ["c"] }).state, "partly");
});

test("kitState: forge's refusal reason loses its prefix", () => {
  const refused = JSON.parse(readFileSync(join(fixtures, "dry-empty-laravel.stderr"), "utf8"));
  assert.equal(refusalReason(refused.stderr.split("\n"), "no reason"),
    "No artisan found under <TARGET> (looked at root, platform/, and first-level children).");
  assert.equal(refusalReason([], "no reason"), "no reason");
});
