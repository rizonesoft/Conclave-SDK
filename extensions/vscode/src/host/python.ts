import { execFile } from "node:child_process";
import { statSync } from "node:fs";
import * as vscode from "vscode";
import { resolvePython, type NoPython, type Python, type RunResult } from "../core/python";
import { findOnPath } from "../core/which";
import { output } from "./output";

export type PythonResolution = Python | NoPython;

const TIMEOUT_MS = 10_000;

function isFile(path: string): boolean {
  try {
    return statSync(path).isFile();
  } catch {
    return false;
  }
}

// Runs an absolute path with an argument array: no shell, a timeout, no console window on Windows.
function run(file: string, args: string[]): Promise<RunResult> {
  return new Promise((resolve) => {
    execFile(file, args, { timeout: TIMEOUT_MS, windowsHide: true, encoding: "utf8" }, (error, stdout) => {
      if (error && typeof error.code !== "number") {
        resolve({ code: undefined, stdout, error: error.killed ? `timed out after ${TIMEOUT_MS / 1000} s` : String(error.code ?? error.message) });
        return;
      }
      resolve({ code: error ? (error.code as number) : 0, stdout });
    });
  });
}

function describe(result: PythonResolution): string {
  return result.ok
    ? `Python ${result.version} from ${result.source}: ${[result.command, ...result.prefix].join(" ")}`
    : `No usable Python: ${result.message}`;
}

// The workspace's Python, resolved once per session and again whenever conclave.pythonPath changes.
export class PythonService implements vscode.Disposable {
  private current: Promise<PythonResolution>;
  private readonly changed = new vscode.EventEmitter<PythonResolution>();
  private readonly listener: vscode.Disposable;
  readonly onDidResolve = this.changed.event;

  constructor() {
    this.current = this.resolve();
    this.listener = vscode.workspace.onDidChangeConfiguration((event) => {
      if (event.affectsConfiguration("conclave.pythonPath")) {
        this.current = this.resolve();
      }
    });
  }

  python(): Promise<PythonResolution> {
    return this.current;
  }

  private generation = 0;

  private async resolve(): Promise<PythonResolution> {
    // A setting changed twice quickly starts two resolutions; only the newer one is logged and announced.
    const mine = ++this.generation;
    const setting = vscode.workspace.getConfiguration("conclave").get<string>("pythonPath", "");
    const platform = process.platform;
    const result = await resolvePython(setting, {
      platform,
      find: (name) => findOnPath(name, { platform, path: process.env.PATH ?? "", pathext: process.env.PATHEXT, isFile }),
      run,
    });
    if (mine === this.generation) {
      output().appendLine(describe(result));
      this.changed.fire(result);
    }
    return result;
  }

  dispose(): void {
    this.listener.dispose();
    this.changed.dispose();
  }
}
