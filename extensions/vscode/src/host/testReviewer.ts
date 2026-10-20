import { readFile } from "node:fs/promises";
import { join } from "node:path";
import * as vscode from "vscode";
import { singleReviewerPin } from "../core/testPin";
import { parseTestRun, type TestOutcome } from "../core/testOutcome";
import { DISPATCHER, PIN } from "../core/workspaceState";
import { withCandidate } from "./candidate";
import { log } from "./output";
import type { PythonService } from "./python";
import { run, running } from "./run";

// The spec names no timeout for a test run. A reviewer gets the dispatcher's --timeout of 600 s (real reviews here
// finish in two to six minutes), and the process is killed 60 s after that if the dispatcher itself does not return.
export const REVIEW_TIMEOUT_S = 600;
export const PROCESS_TIMEOUT_MS = (REVIEW_TIMEOUT_S + 60) * 1000;
// How long processes a cancel could not end keep the temporary pin and the one-test guard: they are checked every
// 500 ms, for at most as long as a run may last.
const SURVIVOR_WAIT_MS = PROCESS_TIMEOUT_MS;

async function ended(pids: number[], alive: (pid: number) => boolean): Promise<void> {
  const deadline = Date.now() + SURVIVOR_WAIT_MS;
  while (pids.some(alive) && Date.now() < deadline) {
    await new Promise((r) => setTimeout(r, 500));
  }
}

export interface TestOptions {
  // The pin text to test from (the editor's candidate); the saved pin when absent.
  pinText?: string;
  // Asks before the run (plan R11): the default is a modal naming the model, the CLI and the writer.
  confirm?: (title: string, detail: string) => Promise<boolean>;
  // Cancels a run in progress: the dispatcher and every reviewer it started are killed.
  signal?: AbortSignal;
  run?: typeof run;
  // Whether a process still runs: running; tests pass their own to end a survivor on cue.
  alive?: (pid: number) => boolean;
}

async function modal(title: string, detail: string): Promise<boolean> {
  return (await vscode.window.showWarningMessage(title, { modal: true, detail }, "Run test")) === "Run test";
}

// The Test reviewer action (plan R11, design/SPEC.md section 5): one dispatch of the planted-bug prompt through a
// temporary pin that holds the chosen reviewer alone, asked for before every run. One test runs at a time.
export class ReviewerTester {
  private running = false;

  constructor(private readonly python: PythonService, private readonly prompt: string) {}

  async test(folder: vscode.Uri, name: string, options: TestOptions = {}): Promise<TestOutcome> {
    if (this.running) {
      return { kind: "refused", message: "Another test is running" };
    }
    this.running = true;
    // The outcome returns at once; the guard is released only when the run's processes have ended (cleanup).
    let cleanup: Promise<void> = Promise.resolve();
    try {
      const [outcome, done] = await this.testNow(folder, name, options);
      cleanup = done;
      return outcome;
    } catch (error) {
      // Anything unforeseen is a refusal the card can show, never a rejected promise.
      log(`Test reviewer ${name}: refused: ${String(error)}.`);
      return { kind: "refused", message: `The test could not run: ${String(error)}` };
    } finally {
      void cleanup.catch(() => undefined).finally(() => (this.running = false));
    }
  }

  // The outcome, and a promise that settles once nothing the run started is left (the temporary pin is deleted then).
  private async testNow(folder: vscode.Uri, name: string, options: TestOptions): Promise<[TestOutcome, Promise<void>]> {
    let pinText = options.pinText;
    if (pinText === undefined) {
      try {
        pinText = await readFile(join(folder.fsPath, PIN), "utf8");
      } catch (error) {
        return [{ kind: "refused", message: `${PIN} cannot be read: ${String(error)}` }, Promise.resolve()];
      }
    }
    const pin = singleReviewerPin(pinText, name);
    if (!pin) {
      return [{ kind: "refused", message: `${name} cannot be tested: it is not in the pin, its CLI is unknown, or the pin's layout is not one the editor edits` }, Promise.resolve()];
    }
    const { model, cli } = pin.reviewer;
    const confirmed = await (options.confirm ?? modal)(`Test ${name} on a planted bug?`,
      `Runs review-dispatch.py with a one-reviewer temporary pin: ${model} through ${cli}, as writer ${pin.writer}. This makes a real model call.`);
    if (!confirmed) {
      log(`Test reviewer ${name}: not run, the confirmation was declined.`);
      return [{ kind: "cancelled" }, Promise.resolve()];
    }
    const python = await this.python.python(folder);
    if (!python.ok) {
      return [{ kind: "refused", message: `No usable Python to run the dispatcher: ${python.message}` }, Promise.resolve()];
    }
    log(`Test reviewer ${name} (${model} through ${cli}, as writer ${pin.writer}) in ${folder.fsPath}: started.`);
    const started = Date.now();
    // The temporary pin is a candidate file: private, and deleted when the run ends, whatever its outcome; when a cancel
    // could not end every process, only once those have ended, since a reviewer may still be reading it.
    let reported: (result: Awaited<ReturnType<typeof run>>) => void = () => undefined;
    const reply = new Promise<Awaited<ReturnType<typeof run>>>((r) => (reported = r));
    const cleanup = withCandidate(pin.text, async (path) => {
      const result = await (options.run ?? run)(python.command, [
        ...python.prefix, join(folder.fsPath, DISPATCHER), "--writer", pin.writer, "--prompt", this.prompt, "--pin", path,
        "--timeout", String(REVIEW_TIMEOUT_S),
      ], PROCESS_TIMEOUT_MS, folder.fsPath, { signal: options.signal, tree: true });
      reported(result);
      if (result.survivors?.length) {
        await ended(result.survivors, options.alive ?? running);
        log(`Test reviewer ${name}: the processes a cancel could not end have ended or been given up on; the temporary pin is deleted.`);
      }
    });
    const result = await Promise.race([reply, cleanup.then(() => reply)]);
    const outcome = parseTestRun(result);
    const detail = outcome.kind === "review" ? `review from ${outcome.reviewer}`
      : outcome.kind === "failover" ? outcome.lines.join("; ")
      : outcome.kind === "refused" ? `refused: ${outcome.message}` : (outcome.note ?? "cancelled");
    log(`Test reviewer ${name}: ${detail} after ${Math.round((Date.now() - started) / 1000)} s.`);
    return [outcome, cleanup];
  }
}
