import * as vscode from "vscode";

// The one "Conclave" output channel: every process the extension runs, and every check, is logged here. The last lines
// are also kept in memory, so the integration tests can read back what was logged (VS Code cannot read a channel).
let channel: vscode.OutputChannel | undefined;
const recent: string[] = [];
const KEEP = 200;

export function output(): vscode.OutputChannel {
  channel ??= vscode.window.createOutputChannel("Conclave");
  return channel;
}

export function log(line: string): void {
  output().appendLine(line);
  recent.push(line);
  if (recent.length > KEEP) {
    recent.splice(0, recent.length - KEEP);
  }
}

export function recentLog(): string[] {
  return [...recent];
}
