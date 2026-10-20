import * as vscode from "vscode";
import { output } from "./host/output";

// The reviewer editor panel. This is the scaffold's placeholder (D02 T01 §1); D03 T01 builds the editor in it.
let panel: vscode.WebviewPanel | undefined;

// What activate returns: the integration tests read the output channel through it, since VS Code lists none.
export interface ConclaveApi {
  output: vscode.OutputChannel;
}

export function activate(context: vscode.ExtensionContext): ConclaveApi {
  context.subscriptions.push(output());
  context.subscriptions.push(
    vscode.commands.registerCommand("conclave.openReviewers", () => {
      if (panel) {
        panel.reveal();
        return panel;
      }
      panel = vscode.window.createWebviewPanel("conclave.reviewers", "Reviewers", vscode.ViewColumn.Active, {});
      panel.webview.html = "<!doctype html><html><body><p>Reviewers</p></body></html>";
      panel.onDidDispose(() => (panel = undefined), undefined, context.subscriptions);
      output().appendLine("Opened the Reviewers panel.");
      return panel;
    }),
  );
  return { output: output() };
}

export function deactivate(): void {}
