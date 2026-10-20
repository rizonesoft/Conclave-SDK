import * as vscode from "vscode";
import { resolvePython, type NoPython, type Python } from "../core/python";
import { findOnPath } from "../core/which";
import { output } from "./output";
import { run, runnable } from "./run";

export type PythonResolution = Python | NoPython;

export interface PythonResolved {
  folder: vscode.Uri | undefined;
  result: PythonResolution;
}

const TIMEOUT_MS = 10_000;

function describe(folder: vscode.Uri | undefined, result: PythonResolution): string {
  const where = folder ? ` for ${folder.fsPath}` : "";
  return result.ok
    ? `Python ${result.version}${where} from ${result.source}: ${[result.command, ...result.prefix].join(" ")}`
    : `No usable Python${where}: ${result.message}`;
}

// The Python for each workspace folder (conclave.pythonPath is machine-overridable, so a folder may set its own),
// resolved on first use, again when that folder's setting changes, and again when the workspace is trusted. In
// Restricted Mode the resolver starts no process.
export class PythonService implements vscode.Disposable {
  private readonly results = new Map<string, Promise<PythonResolution>>();
  private readonly generations = new Map<string, number>();
  private readonly changed = new vscode.EventEmitter<PythonResolved>();
  private readonly listeners: vscode.Disposable[];
  readonly onDidResolve = this.changed.event;

  constructor() {
    this.listeners = [
      vscode.workspace.onDidChangeConfiguration((event) => {
        for (const key of [...this.results.keys()]) {
          const folder = key ? vscode.Uri.parse(key) : undefined;
          if (event.affectsConfiguration("conclave.pythonPath", folder)) {
            this.results.set(key, this.resolve(folder));
          }
        }
      }),
      vscode.workspace.onDidGrantWorkspaceTrust(() => {
        for (const key of [...this.results.keys()]) {
          this.results.set(key, this.resolve(key ? vscode.Uri.parse(key) : undefined));
        }
      }),
    ];
  }

  // The resolution for a workspace folder (or the window, with none), started on first use.
  python(folder?: vscode.Uri): Promise<PythonResolution> {
    const key = folder?.toString() ?? "";
    let result = this.results.get(key);
    if (!result) {
      result = this.resolve(folder);
      this.results.set(key, result);
    }
    return result;
  }

  private async resolve(folder: vscode.Uri | undefined): Promise<PythonResolution> {
    // A setting changed twice quickly starts two resolutions; only the newer one is logged and announced.
    const key = folder?.toString() ?? "";
    const mine = (this.generations.get(key) ?? 0) + 1;
    this.generations.set(key, mine);
    const setting = vscode.workspace.getConfiguration("conclave", folder).get<string>("pythonPath", "");
    const platform = process.platform;
    const result = await resolvePython(setting, {
      platform,
      trusted: vscode.workspace.isTrusted,
      find: (name) => findOnPath(name, { platform, path: process.env.PATH ?? "", pathext: process.env.PATHEXT, runnable }),
      run: (file, args) => run(file, args, TIMEOUT_MS),
    });
    if (mine === this.generations.get(key)) {
      output().appendLine(describe(folder, result));
      this.changed.fire({ folder, result });
    }
    return result;
  }

  dispose(): void {
    this.listeners.forEach((listener) => listener.dispose());
    this.changed.dispose();
  }
}
