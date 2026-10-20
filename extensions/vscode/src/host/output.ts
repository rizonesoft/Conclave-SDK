import * as vscode from "vscode";

// The one "Conclave" output channel: every process the extension runs, and every check, is logged here.
let channel: vscode.OutputChannel | undefined;

export function output(): vscode.OutputChannel {
  channel ??= vscode.window.createOutputChannel("Conclave");
  return channel;
}
