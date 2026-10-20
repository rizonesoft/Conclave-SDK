import { join } from "node:path";
import * as vscode from "vscode";
import type { WorkspaceState } from "./core/checkPin";
import type { SdkRefusal, SdkSource } from "./core/sdkSource";
import { sweepCandidates, withCandidate } from "./host/candidate";
import { DispatcherClient } from "./host/dispatcher";
import { log, output, recentLog } from "./host/output";
import { PythonService, type PythonResolution, type PythonResolved } from "./host/python";
import { PinSession, type SaveHooks } from "./host/save";
import { SdkSourceService } from "./host/sdkSource";
import { ReviewerTester, type TestOptions } from "./host/testReviewer";
import { FORGE_PARSERS, runForge, type ForgeOptions, type ForgeSource } from "./host/forge";
import type { ForgeOutcome } from "./core/forgeJson";
import { KitStateService, type KitStates } from "./host/kitState";
import type { TestOutcome } from "./core/testOutcome";

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
  openPin: (folder: vscode.Uri, hooks?: SaveHooks) => PinSession;
  // Test reviewer (plan R11): one dispatch of the planted-bug prompt through the named reviewer alone.
  testReviewer: (folder: vscode.Uri, name: string, options?: TestOptions) => Promise<TestOutcome>;
  // One forge.py run from an SDK source, with the Python resolved for folder, parsed by its command (D02 T01 §9).
  runForge: (source: ForgeSource, args: string[], options?: ForgeOptions & { folder?: vscode.Uri }) => Promise<ForgeOutcome<unknown>>;
  // Each kit's state in a folder from forge's dry runs (D02 T01 §10), cached until the folder changes.
  kitStates: (folder: vscode.Uri) => Promise<KitStates>;
  onDidChangeKitState: vscode.Event<vscode.Uri>;
  // A kit operation (D05 T01) finished: the folder's kit state is read again.
  invalidateKitState: (folder: vscode.Uri) => void;
  // A folder leaving the workspace: its kit state's watchers and cache are dropped.
  forgetKitState: (folder: vscode.Uri) => void;
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
  const tester = new ReviewerTester(python, join(context.extensionPath, "resources", "planted-bug-prompt.md"));
  const sdk = new SdkSourceService(python, {
    extensionPath: context.extensionPath,
    storage: context.globalStorageUri.fsPath,
    development: context.extensionMode !== vscode.ExtensionMode.Production,
  });
  const kitStates = new KitStateService({
    source: async (folder) => {
      const source = await sdk.resolve(folder);
      return "ok" in source ? source : { message: source.message };
    },
    python: async (folder) => {
      const resolved = await python.python(folder);
      return resolved.ok ? resolved : { message: resolved.message };
    },
  });
  context.subscriptions.push(kitStates);
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
    testReviewer: (folder, name, options) => tester.test(folder, name, options),
    kitStates: (folder) => kitStates.states(folder),
    onDidChangeKitState: kitStates.onDidChangeKitState,
    invalidateKitState: (folder) => kitStates.invalidate(folder),
    forgetKitState: (folder) => kitStates.forget(folder),
    runForge: async (source, args, options) => {
      const parse = FORGE_PARSERS.get(args[0] ?? "");
      if (!parse) {
        return { kind: "failed", message: `forge ${args[0] ?? ""} is not a command the extension runs`, stderrTail: [] };
      }
      const resolved = await python.python(options?.folder);
      if (!resolved.ok) {
        return { kind: "failed", message: `No usable Python to run forge.py: ${resolved.message}`, stderrTail: [] };
      }
      return runForge(source, resolved, args, parse, options);
    },
  };
}

export function deactivate(): void {}
