import { readFileSync, statSync } from "node:fs";
import { join, resolve } from "node:path";
import * as vscode from "vscode";
import type { WorkspaceState } from "../core/checkPin";
import { FolderQueue } from "../core/folderQueue";
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

// Runs the workspace's own dispatcher (plan R7). One dispatcher process runs per folder at a time; an identical request
// already waiting or running shares its answer. Nothing runs in Restricted Mode, and every folder already checked is
// checked again when the workspace is trusted.
//
// onDidCheck carries the folder's own pin only, and only its newest check: a candidate (§5) gets its verdict from the
// promise it asked for, so a candidate result is never mistaken for the saved pin's state, and an older check that
// finishes late is not published over a newer one.
export class DispatcherClient implements vscode.Disposable {
  private readonly queue = new FolderQueue<WorkspaceState>();
  private readonly generations = new Map<string, number>();
  private readonly checked = new Set<string>();
  private readonly changed = new vscode.EventEmitter<WorkspaceChecked>();
  private readonly trust: vscode.Disposable;
  readonly onDidCheck = this.changed.event;

  // runner is the process runner; tests pass one they hold open to order a check against a save.
  constructor(private readonly python: PythonService, private readonly runner: typeof run = run) {
    this.trust = vscode.workspace.onDidGrantWorkspaceTrust(() => {
      for (const key of this.checked) {
        void this.check(vscode.Uri.parse(key));
      }
    });
  }

  check(folder: vscode.Uri, pin?: string): Promise<WorkspaceState> {
    const key = folder.toString();
    const queued = this.queue.run(key, pin ?? "", () => checkWorkspace(folder.fsPath, {
      trusted: vscode.workspace.isTrusted,
      join,
      resolve,
      isFile,
      readText,
      python: () => this.python.python(folder),
      run: this.runner,
      log,
      now: Date.now,
    }, pin));
    // Each new run of the folder's own pin is published once, and only if no newer run was queued after it; a call that
    // joined a waiting run adds nothing, since that run publishes for both.
    if (!pin && queued.created) {
      const generation = (this.generations.get(key) ?? 0) + 1;
      this.generations.set(key, generation);
      void queued.promise.then((state) => {
        this.checked.add(key);
        if (this.generations.get(key) === generation) {
          this.changed.fire({ folder, state });
        }
      }, () => undefined);
    }
    return queued.promise;
  }

  dispose(): void {
    this.trust.dispose();
    this.changed.dispose();
  }
}
