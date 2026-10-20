import * as vscode from "vscode";
import type { WorkspaceState } from "./core/checkPin";
import type { SdkRefusal, SdkSource } from "./core/sdkSource";
import { sweepCandidates, withCandidate } from "./host/candidate";
import { DispatcherClient } from "./host/dispatcher";
import { log, output, recentLog } from "./host/output";
import { PythonService, type PythonResolution, type PythonResolved } from "./host/python";
import { PinSession, type SaveDeps } from "./host/save";
import { SdkSourceService } from "./host/sdkSource";

// The reviewer editor panel. This is the scaffold's placeholder (D02 T01 §1); D03 T01 builds the editor in it.
let panel: vscode.WebviewPanel | undefined;

// What activate returns: the integration tests read the output channel, the Python resolution and the workspace state
// through it, since VS Code cannot read a channel back.
export interface ConclaveApi {
  output: vscode.OutputChannel;
  python: (folder?: vscode.Uri) => Promise<PythonResolution>;
  onDidResolvePython: vscode.Event<PythonResolved>;
  checkWorkspace: (folder: vscode.Uri, pin?: string) => Promise<WorkspaceState>;
  recentLog: () => string[];
  sdkSource: (folder?: vscode.Uri) => Promise<SdkSource | SdkRefusal>;
  // The dispatcher's verdict on candidate text, written to a candidate file that is deleted after the check.
  checkCandidate: (folder: vscode.Uri, text: string) => Promise<WorkspaceState>;
  // A folder's pin as loaded, with atomic save, stale check, re-check, discard and reload; tests pass their hooks.
  openPin: (folder: vscode.Uri, hooks?: Pick<SaveDeps, "afterWrite" | "rename" | "delay">) => PinSession;
}

export function activate(context: vscode.ExtensionContext): ConclaveApi {
  context.subscriptions.push(output());
  const swept = sweepCandidates();
  if (swept) {
    log(`Removed ${swept} candidate file(s) left by an earlier session.`);
  }
  const python = new PythonService();
  context.subscriptions.push(python);
  const dispatcher = new DispatcherClient(python);
  context.subscriptions.push(dispatcher);
  const sdk = new SdkSourceService(python, {
    extensionPath: context.extensionPath,
    storage: context.globalStorageUri.fsPath,
    development: context.extensionMode !== vscode.ExtensionMode.Production,
  });
  context.subscriptions.push(
    vscode.commands.registerCommand("conclave.openReviewers", () => {
      if (panel) {
        panel.reveal();
        return panel;
      }
      panel = vscode.window.createWebviewPanel("conclave.reviewers", "Reviewers", vscode.ViewColumn.Active, {});
      panel.webview.html = "<!doctype html><html><body><p>Reviewers</p></body></html>";
      panel.onDidDispose(() => (panel = undefined), undefined, context.subscriptions);
      log("Opened the Reviewers panel.");
      return panel;
    }),
  );
  return {
    output: output(),
    python: (folder) => python.python(folder),
    onDidResolvePython: python.onDidResolve,
    checkWorkspace: (folder, pin) => dispatcher.check(folder, pin),
    recentLog,
    sdkSource: (folder) => sdk.resolve(folder),
    checkCandidate: (folder, text) => withCandidate(text, (path) => dispatcher.check(folder, path)),
    openPin: (folder, hooks) => {
      const session = new PinSession(folder, { check: (f) => dispatcher.check(f), log, ...hooks });
      context.subscriptions.push(session);
      return session;
    },
  };
}

export function deactivate(): void {}
