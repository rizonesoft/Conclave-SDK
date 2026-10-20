import { readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import * as vscode from "vscode";
import type { WorkspaceState } from "../core/checkPin";
import { checkWorkspace } from "../core/workspaceState";
import { log } from "./output";
import type { PythonService } from "./python";
import { run } from "./run";

export interface WorkspaceChecked {
  folder: vscode.Uri;
  state: WorkspaceState;
}

function isFile(path: string): boolean {
  try {
    return statSync(path).isFile();
  } catch {
    return false;
  }
}

function readText(path: string): string | undefined {
  try {
    return readFileSync(path, "utf8");
  } catch {
    return undefined;
  }
}

// Runs the workspace's own dispatcher (plan R7). One call per folder and pin is in flight at a time: a request while
// one runs gets that call's answer, so rapid requests start one process. Nothing runs in Restricted Mode, and every
// folder already checked is checked again when the workspace is trusted.
export class DispatcherClient implements vscode.Disposable {
  private readonly inFlight = new Map<string, Promise<WorkspaceState>>();
  private readonly checked = new Set<string>();
  private readonly changed = new vscode.EventEmitter<WorkspaceChecked>();
  private readonly trust: vscode.Disposable;
  readonly onDidCheck = this.changed.event;

  constructor(private readonly python: PythonService) {
    this.trust = vscode.workspace.onDidGrantWorkspaceTrust(() => {
      for (const key of this.checked) {
        void this.check(vscode.Uri.parse(key));
      }
    });
  }

  check(folder: vscode.Uri, pin?: string): Promise<WorkspaceState> {
    const key = `${folder.toString()}\n${pin ?? ""}`;
    const running = this.inFlight.get(key);
    if (running) {
      return running;
    }
    const call = checkWorkspace(folder.fsPath, {
      trusted: vscode.workspace.isTrusted,
      join,
      isFile,
      readText,
      python: () => this.python.python(folder),
      run,
      log,
      now: Date.now,
    }, pin).then((state) => {
      if (!pin) {
        this.checked.add(folder.toString());
      }
      this.changed.fire({ folder, state });
      return state;
    }).finally(() => this.inFlight.delete(key));
    this.inFlight.set(key, call);
    return call;
  }

  dispose(): void {
    this.trust.dispose();
    this.changed.dispose();
  }
}
