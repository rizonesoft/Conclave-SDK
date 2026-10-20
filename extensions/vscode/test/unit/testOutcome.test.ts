import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { test } from "node:test";
import { parseTestRun } from "../../src/core/testOutcome";

// Saved dispatcher answers: a review, a round where every reviewer failed over (captured from the kit's dispatcher
// with a fake CLI that exits 3), and a refusal on stderr.
const fixtures = join(__dirname, "..", "..", "..", "test", "fixtures", "dispatch");
const read = (name: string) => readFileSync(join(fixtures, name), "utf8");

test("testOutcome: a review keeps the reviewer's text verbatim", () => {
  const summary = JSON.parse(read("review.json"));
  assert.deepEqual(parseTestRun({ code: 0, stdout: read("review.json"), stderr: "" }), {
    kind: "review", reviewer: "sonnet", model: "claude-sonnet-5-5", cli: "claude", review: summary.review,
  });
});

test("testOutcome: no review gives the dispatcher's failover lines", () => {
  assert.deepEqual(parseTestRun({ code: 1, stdout: read("failover.json"), stderr: "" }),
    { kind: "failover", lines: ["Skipped: sonnet (exited 3)"] });
});

test("testOutcome: a refusal gives the dispatcher's message", () => {
  assert.deepEqual(parseTestRun({ code: 2, stdout: "", stderr: read("refused.stderr") }),
    { kind: "refused", message: "the reviewer pin has no route for writer 'claude'" });
});

test("testOutcome: a cancelled, unfinished or unreadable run is never a review", () => {
  assert.deepEqual(parseTestRun({ code: undefined, stdout: "", stderr: "", error: "cancelled" }), { kind: "cancelled" });
  assert.deepEqual(parseTestRun({ code: undefined, stdout: "", stderr: "", error: "timed out after 660 s" }),
    { kind: "failover", lines: ["The dispatcher did not finish: timed out after 660 s"] });
  assert.deepEqual(parseTestRun({ code: 0, stdout: "not json", stderr: "" }),
    { kind: "failover", lines: ["The dispatcher exited 0 with no summary"] });
  // Exit 0 with no reviewer named is not a review, whatever the text says.
  assert.equal(parseTestRun({ code: 0, stdout: JSON.stringify({ reviewer: null, review: "looks fine", failover: [] }), stderr: "" }).kind, "failover");
});
