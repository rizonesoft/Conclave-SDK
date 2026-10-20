// Reading the workspace dispatcher's `--check-pin --json` reply (the contract frozen by D01 T01 §3) into the one state
// the extension shows. The extension holds no copy of any pin rule: what the dispatcher says is the verdict.

import { isEditableLayout } from "./pinText";

export const SUPPORTED_SCHEMA = 1;

export interface Reviewer {
  cli: string;
  model: string;
  effort?: string;
}

export interface CheckPinReport {
  ok: true;
  schema_version: number;
  reviewers: Record<string, Reviewer>;
  routes: Record<string, string[]>;
  clis: Record<string, boolean>;
}

export type WorkspaceState =
  | { state: "ready"; report: CheckPinReport }
  // Valid, but written in a layout the editor does not edit in place: read-only (design spec section 2).
  | { state: "pin-layout"; report: CheckPinReport }
  // Valid by a dispatcher that knows a newer schema than this extension edits (plan R21).
  | { state: "unsupported-schema"; version: number; report: CheckPinReport }
  | { state: "refused"; error: string }
  | { state: "no-pin"; error: string }
  // No JSON object with an "ok" key: a dispatcher from before --check-pin (plan R18). The rule is the output, never the
  // exit code, since such a dispatcher exits 2 like a refusal. detail says what came back.
  | { state: "old-dispatcher"; detail: string }
  | { state: "no-dispatcher" }
  | { state: "no-python"; message: string }
  | { state: "untrusted" };

export type StateName = WorkspaceState["state"];

function contractObject(stdout: string): Record<string, unknown> | undefined {
  try {
    const value: unknown = JSON.parse(stdout);
    return value !== null && typeof value === "object" && !Array.isArray(value) && "ok" in value
      ? (value as Record<string, unknown>)
      : undefined;
  } catch {
    return undefined;
  }
}

// One state from the dispatcher's stdout and exit code, and the pin's text when it could be read (for the layout).
export function parseCheckPin(stdout: string, exitCode: number | undefined, pinText?: string): WorkspaceState {
  const reply = contractObject(stdout.trim());
  if (!reply) {
    const shown = stdout.trim().slice(0, 200);
    return { state: "old-dispatcher", detail: `exit ${exitCode ?? "none"}, ${shown ? `printed ${JSON.stringify(shown)}` : "printed nothing"}` };
  }
  if (reply.ok === true && exitCode === 0) {
    const report = reply as unknown as CheckPinReport;
    if (report.schema_version !== SUPPORTED_SCHEMA) {
      return { state: "unsupported-schema", version: report.schema_version, report };
    }
    if (pinText !== undefined && !isEditableLayout(pinText)) {
      return { state: "pin-layout", report };
    }
    return { state: "ready", report };
  }
  if (reply.ok === false && exitCode === 2 && typeof reply.error === "string") {
    return reply.error.startsWith("no reviewer pin at") ? { state: "no-pin", error: reply.error } : { state: "refused", error: reply.error };
  }
  // A contract object that disagrees with its own exit code is not the contract either.
  return { state: "old-dispatcher", detail: `exit ${exitCode ?? "none"} with ok ${JSON.stringify(reply.ok)}` };
}
