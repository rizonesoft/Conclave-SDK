import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { test } from "node:test";
import { type DoctorResult, parseCheck, parseDoctor } from "../../src/core/forgeJson";
import { healthFrom, kitHealth } from "../../src/core/kitHealth";

// forge's own check and doctor answers on a folder with every kit, recorded by scripts/record-forge-fixtures.py with
// PATH set to stub CLIs: every reviewer CLI present, or the Gemini CLI missing.
const fixtures = join(__dirname, "..", "..", "..", "test", "fixtures", "forge");

function doctor(name: string): DoctorResult {
  const parsed = parseDoctor(readFileSync(join(fixtures, `${name}.json`), "utf8"));
  assert.ok(parsed.ok, name);
  return parsed.value;
}

test("kitHealth: the reviewer doctor with every CLI is healthy, with every check kept verbatim", () => {
  const recorded = doctor("doctor-reviewer");
  const health = kitHealth(recorded);
  assert.equal(health.state, "checked");
  assert.ok(health.state === "checked" && health.problems === 0);
  assert.deepEqual(health.state === "checked" && health.checks, recorded.checks);
});

test("kitHealth: a missing reviewer CLI is one setup_required check, named with its detail", () => {
  const health = kitHealth(doctor("doctor-reviewer-no-agy"));
  assert.ok(health.state === "checked" && health.problems === 1);
  const gemini = health.state === "checked" ? health.checks.filter((c) => c.status !== "ok") : [];
  assert.deepEqual(gemini, [{ name: "reviewer:gemini", status: "setup_required", detail: "agy CLI not installed; this reviewer is skipped" }]);
});

test("kitHealth: the WordPress doctor before the site is set up counts every check that needs setup", () => {
  const recorded = doctor("doctor-wordpress");
  const health = kitHealth(recorded);
  assert.ok(health.state === "checked" && health.problems === recorded.missingOrSetupRequired && health.problems === 8);
  assert.ok(health.state === "checked" && health.checks.some((c) => c.name === "site-identity" && c.status === "setup_required"));
});

test("kitHealth: any status but ok counts, unexpected and an unknown one included", () => {
  const base = doctor("doctor-base");
  const checks = [...base.checks, { name: "x", status: "unexpected", detail: "x" }, { name: "y", status: "stale", detail: "y" }];
  const health = kitHealth({ ...base, checks });
  assert.ok(health.state === "checked" && health.problems === 2);
  assert.ok(health.state === "checked" && health.checks.at(-1)?.status === "stale");
});

test("kitHealth: a folder's health has check's presence flags verbatim and every kit, in order", () => {
  const check = parseCheck(readFileSync(join(fixtures, "health-check.json"), "utf8"));
  assert.ok(check.ok);
  const folder = healthFrom(check.value, [doctor("doctor-base"), doctor("doctor-reviewer"), { kit: "laravel", reason: "No artisan found" }]);
  // The flags are presence, verbatim: an isolated folder has no .agents manifests on purpose, which is not a problem.
  assert.deepEqual(folder.presence, check.value.flags);
  assert.equal(folder.presence.has_agy_skills_json, false);
  assert.deepEqual(folder.kits.map((k) => [k.kit, k.state]), [["base", "checked"], ["reviewer", "checked"], ["laravel", "unavailable"]]);
});
