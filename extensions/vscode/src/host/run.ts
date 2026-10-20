import { execFile } from "node:child_process";
import { accessSync, constants, statSync } from "node:fs";
import type { RunResult } from "../core/python";

// A file this platform would run: a regular file, and on POSIX one with execute permission.
export function runnable(path: string): boolean {
  try {
    if (!statSync(path).isFile()) {
      return false;
    }
    if (process.platform !== "win32") {
      accessSync(path, constants.X_OK);
    }
    return true;
  } catch {
    return false;
  }
}

// Runs an absolute path with an argument array: no shell, no console window on Windows, and a timeout that always
// settles. On timeout the process is killed with SIGKILL (which it cannot catch, unlike execFile's default SIGTERM) and
// the promise settles at once, even if a descendant still holds its output open.
export function run(file: string, args: string[], timeoutMs: number, cwd?: string): Promise<RunResult> {
  return new Promise((resolve) => {
    let settled = false;
    const settle = (result: RunResult) => {
      if (!settled) {
        settled = true;
        clearTimeout(timer);
        resolve(result);
      }
    };
    const child = execFile(file, args, { windowsHide: true, encoding: "utf8", cwd, maxBuffer: 4 * 1024 * 1024 },
      (error, stdout) => {
        if (error && typeof error.code !== "number") {
          settle({ code: undefined, stdout, error: String(error.code ?? error.message) });
        } else {
          settle({ code: error ? (error.code as number) : 0, stdout });
        }
      });
    const timer = setTimeout(() => {
      child.kill("SIGKILL");
      settle({ code: undefined, stdout: "", error: `timed out after ${timeoutMs / 1000} s` });
    }, timeoutMs);
  });
}
