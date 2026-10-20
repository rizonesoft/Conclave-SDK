import { deleteReviewer, type PinReviewer, readPin, removeRoute, setRoute } from "./pinText";

// The CLI each family runs through, and the writer a test run names (plan R11, design/SPEC.md section 5): codex for a
// claude reviewer and claude otherwise, so the reviewer is never of the writer's own family.
const WRITER_FOR_CLI: Record<string, string> = { codex: "claude", agy: "claude", claude: "codex" };

export interface TestPin {
  // The pin text with only the chosen reviewer and one route naming it alone.
  text: string;
  writer: string;
  reviewer: PinReviewer;
}

// A one-reviewer pin for a Test reviewer run: the chosen reviewer's table kept as written, every other reviewer and
// route removed, and one route for a writer of another family. undefined when the pin's layout is not one the editor
// edits, the reviewer is not in it, or its CLI is unknown (the Test reviewer button is off in each case).
export function singleReviewerPin(pinText: string, name: string): TestPin | undefined {
  const view = readPin(pinText);
  const reviewer = view?.reviewers.find((r) => r.name === name);
  const writer = reviewer?.cli ? WRITER_FOR_CLI[reviewer.cli] : undefined;
  if (!view || !reviewer || !writer) {
    return undefined;
  }
  let text = pinText;
  for (const other of view.reviewers) {
    if (other.name !== name) {
      text = deleteReviewer(text, other.name);
    }
  }
  for (const route of view.routes) {
    if (route.writer !== writer) {
      text = removeRoute(text, route.writer);
    }
  }
  return { text: setRoute(text, writer, [name]), writer, reviewer };
}
