// Checking one workspace folder: trust, the dispatcher's presence, Python, then the dispatcher's own verdict. Pure
// over injected effects, so every branch is unit-tested; src/host/dispatcher.ts wires VS Code and Node into it.

import { parseCheckPin, type WorkspaceState } from "./checkPin";
import type { NoPython, Python, RunResult } from "./python";

export const DISPATCHER = "scripts/review-dispatch.py";
export const PIN = ".conclave/reviewers.toml";
export const TIMEOUT_MS = 30_000;

export interface CheckDeps {
  trusted: boolean;
  // Joins the folder and a relative path with the platform's separator.
  join: (folder: string, relative: string) => string;
  // A candidate pin path made absolute against the folder (an absolute one is kept), so the dispatcher and the layout
  // read see the same file whatever the extension host's working directory is.
  resolve: (folder: string, path: string) => string;
  isFile: (path: string) => boolean;
  readText: (path: string) => string | undefined;
  python: () => Promise<Python | NoPython>;
  run: (file: string, args: string[], timeoutMs: number, cwd: string) => Promise<RunResult>;
  // One line per dispatcher call for the output channel.
  log: (line: string) => void;
  now: () => number;
}

// The folder's state; pin is the file --check-pin judges (the folder's own pin unless a candidate is given).
export async function checkWorkspace(folder: string, deps: CheckDeps, pin?: string): Promise<WorkspaceState> {
  if (!deps.trusted) {
    return { state: "untrusted" };
  }
  const dispatcher = deps.join(folder, DISPATCHER);
  if (!deps.isFile(dispatcher)) {
    return { state: "no-dispatcher" };
  }
  const python = await deps.python();
  if (!python.ok) {
    return python.untrusted ? { state: "untrusted" } : { state: "no-python", message: python.message };
  }
  const pinPath = pin ? deps.resolve(folder, pin) : deps.join(folder, PIN);
  const args = [...python.prefix, dispatcher, "--check-pin", "--json", ...(pin ? ["--pin", pinPath] : [])];
  const started = deps.now();
  const result = await deps.run(python.command, args, TIMEOUT_MS, folder);
  const state = parseCheckPin(result.stdout, result.code, deps.readText(pinPath));
  const why = result.code === undefined ? ` (${result.error ?? "did not run"})` : "";
  deps.log(`check-pin: ${[python.command, ...args].join(" ")} in ${folder}: exit ${result.code ?? "none"}${why} in ` +
    `${deps.now() - started} ms -> ${state.state}`);
  return state;
}
