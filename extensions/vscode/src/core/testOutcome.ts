import type { RunResult } from "./python";

// What a Test reviewer run came to (plan R11, design/SPEC.md section 5): the reviewer's text verbatim, the failover
// lines when no reviewer returned a review, the dispatcher's refusal, or a run the operator cancelled.
export type TestOutcome =
  | { kind: "review"; reviewer: string; model: string; cli: string; review: string }
  | { kind: "failover"; lines: string[] }
  | { kind: "refused"; message: string }
  | { kind: "cancelled" };

interface Summary {
  reviewer?: unknown;
  model?: unknown;
  cli?: unknown;
  review?: unknown;
  failover?: unknown;
}

const REFUSED = /^review-dispatch refused: (.*)$/m;

function failoverLines(summary: Summary): string[] {
  const entries = Array.isArray(summary.failover) ? summary.failover : [];
  return entries
    .filter((e): e is { reviewer: string; reason: string } => typeof e?.reviewer === "string" && typeof e?.reason === "string")
    .map((e) => `Skipped: ${e.reviewer} (${e.reason})`);
}

// The dispatcher prints its summary as JSON and exits 0 with a review, 1 with none (every reviewer failed over), or 2
// with "review-dispatch refused: ..." on stderr. Anything else (no JSON, a run that never finished) is no review.
export function parseTestRun(result: RunResult): TestOutcome {
  if (result.error === "cancelled") {
    return { kind: "cancelled" };
  }
  if (result.code === undefined) {
    return { kind: "failover", lines: [`The dispatcher did not finish: ${result.error ?? "it could not start"}`] };
  }
  const refused = REFUSED.exec(result.stderr ?? "");
  if (result.code === 2 && refused) {
    return { kind: "refused", message: refused[1] };
  }
  let summary: Summary;
  try {
    summary = JSON.parse(result.stdout) as Summary;
  } catch {
    return { kind: "failover", lines: [`The dispatcher exited ${result.code} with no summary`] };
  }
  if (result.code === 0 && typeof summary.reviewer === "string" && typeof summary.review === "string") {
    return {
      kind: "review",
      reviewer: summary.reviewer,
      model: typeof summary.model === "string" ? summary.model : "",
      cli: typeof summary.cli === "string" ? summary.cli : "",
      review: summary.review,
    };
  }
  const lines = failoverLines(summary);
  return { kind: "failover", lines: lines.length ? lines : [`The dispatcher exited ${result.code} with no review`] };
}
