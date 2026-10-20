import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { test } from "node:test";
import { forgeOutcome, parseCheck, parseDoctor, parseKit, parseKits } from "../../src/core/forgeJson";

// forge.py's own answers, recorded by scripts/record-forge-fixtures.py with the temporary folder written as <TARGET>.
const fixtures = join(__dirname, "..", "..", "..", "test", "fixtures", "forge");
const read = (name: string) => readFileSync(join(fixtures, name), "utf8");

test("forgeJson: kits, kit and kit --dry-run keep every list verbatim", () => {
  const kits = parseKits(read("kits.json"));
  assert.ok(kits.ok);
  assert.deepEqual(kits.value, JSON.parse(read("kits.json")).kits);
  for (const [name, dryRun] of [["kit.json", false], ["kit-dry-run.json", true]] as const) {
    const raw = JSON.parse(read(name));
    const kit = parseKit(read(name));
    assert.ok(kit.ok, name);
    assert.deepEqual(kit.value, {
      target: "<TARGET>", kit: "reviewer", agent: "all", dryRun,
      installed: raw.installed, updated: raw.updated, preserved: raw.preserved, mergeNeeded: raw.merge_needed,
    });
    assert.ok(kit.value.installed.includes("scripts/review-dispatch.py"));
  }
});

test("forgeJson: check gives its flags and per-agent lists, doctor its checks", () => {
  const raw = JSON.parse(read("check.json"));
  const check = parseCheck(read("check.json"));
  assert.ok(check.ok);
  assert.equal(check.value.flags.has_agents_md, true);
  assert.equal(check.value.flags.has_agy_skills_json, false);
  assert.deepEqual(Object.keys(check.value.flags), Object.keys(raw).filter((k) => k.startsWith("has_")));
  assert.deepEqual([check.value.agySkills, check.value.claudeSkills, check.value.codexSkills, check.value.claudeAgents],
    [raw.agy_skills, raw.claude_skills, raw.codex_skills, raw.claude_agents]);
  const doctor = parseDoctor(read("doctor.json"));
  assert.ok(doctor.ok);
  assert.equal(doctor.value.missingOrSetupRequired, 0);
  assert.deepEqual(doctor.value.checks, JSON.parse(read("doctor.json")).checks);
});

test("forgeJson: a shape the parser does not know is refused with the raw text", () => {
  const raw = JSON.parse(read("kit.json"));
  delete raw.installed;
  const text = JSON.stringify(raw);
  assert.deepEqual(parseKit(text), { ok: false, message: 'forge kit: "installed" is missing or not a list of text', raw: text });
  const wrongType = JSON.stringify({ ...JSON.parse(read("kit.json")), dry_run: "no" });
  assert.equal(parseKit(wrongType).ok, false);
  const badKit = { ...JSON.parse(read("kit-dry-run.json")), merge_needed: [1] };
  assert.match((parseKit(JSON.stringify(badKit)) as { message: string }).message, /"merge_needed"/);
  assert.equal(parseDoctor(JSON.stringify({ ...JSON.parse(read("doctor.json")), checks: [{ name: "x" }] })).ok, false);
  assert.deepEqual(parseKits("[]"), { ok: false, message: "forge kits is not an object", raw: "[]" });
  // check: every flag check_repo always writes is required, one or all missing; a further has_* flag is kept.
  const check = JSON.parse(read("check.json"));
  delete check.has_agents_md;
  assert.deepEqual(parseCheck(JSON.stringify(check)), { ok: false, message: 'forge check: "has_agents_md" is missing or not true or false', raw: JSON.stringify(check) });
  const none = Object.fromEntries(Object.entries(JSON.parse(read("check.json"))).filter(([k]) => !k.startsWith("has_")));
  assert.equal(parseCheck(JSON.stringify(none)).ok, false);
  const extra = parseCheck(JSON.stringify({ ...JSON.parse(read("check.json")), has_new_thing: true }));
  assert.ok(extra.ok && extra.value.flags.has_new_thing === true);
  assert.equal(parseCheck(JSON.stringify({ ...JSON.parse(read("check.json")), has_todo_graph: "yes" })).ok, false);
});

test("forgeJson: exit 0 with JSON succeeds; any other run is a failure or a cancel", () => {
  assert.deepEqual(forgeOutcome("kits", { code: 0, stdout: read("kits.json"), stderr: "" }, parseKits),
    { kind: "ok", value: JSON.parse(read("kits.json")).kits });
  // Exit 0 without JSON is a failure naming the command, never a success.
  assert.deepEqual(forgeOutcome("kit", { code: 0, stdout: "done\n", stderr: "" }, parseKit),
    { kind: "failed", message: "forge kit printed no JSON", stderrTail: [], raw: "done\n" });
  const refused = JSON.parse(read("kit-refused.stderr"));
  assert.deepEqual(forgeOutcome("kit", { code: refused.exit, stdout: "", stderr: refused.stderr }, parseKit),
    { kind: "failed", message: "forge kit exited 2", stderrTail: ["forge.py: error: Target must be an existing non-symlink directory: <TARGET>"] });
  const long = Array.from({ length: 30 }, (_, i) => `line ${i + 1}`).join("\n") + "\n";
  const failed = forgeOutcome("doctor", { code: 1, stdout: "", stderr: long }, parseDoctor);
  assert.ok(failed.kind === "failed" && failed.stderrTail.length === 20 && failed.stderrTail[0] === "line 11" && failed.stderrTail[19] === "line 30");
  assert.deepEqual(forgeOutcome("kits", { code: undefined, stdout: "", stderr: "", error: "cancelled" }, parseKits), { kind: "cancelled" });
  assert.deepEqual(forgeOutcome("kits", { code: undefined, stdout: "", stderr: "", error: "timed out after 120 s" }, parseKits),
    { kind: "failed", message: "forge kits did not finish: timed out after 120 s", stderrTail: [] });
});
