import { execFile } from "node:child_process";
import { accessSync, constants, statSync } from "node:fs";
import { join } from "node:path";
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

export interface RunOptions {
  // Cancels the run: the process (and with tree, everything it started) is killed and the promise settles.
  signal?: AbortSignal;
  // Kill the whole process tree on timeout or cancel: a dispatcher starts each reviewer CLI in its own session, which
  // killing the dispatcher alone would leave running.
  tree?: boolean;
  // How a tree is killed: killTree; tests pass one that reports done later, to prove the run waits for it.
  killer?: (pid: number) => Promise<void>;
}

// Runs an absolute path with an argument array: no shell, no console window on Windows, and a timeout that always
// settles. On timeout the process is killed with SIGKILL (which it cannot catch, unlike execFile's default SIGTERM) and
// the promise settles at once, even if a descendant still holds its output open. With tree, the kill reaches every
// descendant first, and the promise settles once they are gone.
export function run(file: string, args: string[], timeoutMs: number, cwd?: string, options: RunOptions = {}): Promise<RunResult> {
  return new Promise((resolve) => {
    if (options.signal?.aborted) {
      resolve({ code: undefined, stdout: "", stderr: "", error: "cancelled" });
      return;
    }
    let settled = false;
    // Set when a cancel or the timeout starts killing: the run then settles only once the kill is done (with that
    // reason), never on the exit the kill causes, so a caller cleaning up after a cancel never races the tree.
    let stopping: string | undefined;
    const settle = (result: RunResult) => {
      if (!settled) {
        settled = true;
        clearTimeout(timer);
        options.signal?.removeEventListener("abort", cancel);
        resolve(result);
      }
    };
    let child: ReturnType<typeof execFile>;
    try {
      child = execFile(file, args, { windowsHide: true, encoding: "utf8", cwd, maxBuffer: 4 * 1024 * 1024 },
        (error, stdout, stderr) => {
          if (stopping !== undefined) {
            return;
          }
          if (error && typeof error.code !== "number") {
            settle({ code: undefined, stdout, stderr, error: String(error.code ?? error.message) });
          } else {
            settle({ code: error ? (error.code as number) : 0, stdout, stderr });
          }
        });
    } catch (error) {
      // execFile throws at once for an argument it cannot pass (a path with a NUL byte): that is a process that
      // could not start, reported like any other, never a rejected promise.
      const code = (error as NodeJS.ErrnoException).code;
      resolve({ code: undefined, stdout: "", stderr: "", error: code ?? String(error) });
      return;
    }
    const stop = (error: string) => {
      if (settled || stopping !== undefined) {
        return;
      }
      stopping = error;
      const done = () => settle({ code: undefined, stdout: "", stderr: "", error });
      if (options.tree && child.pid !== undefined) {
        void (options.killer ?? killTree)(child.pid).then(done, done);
      } else {
        child.kill("SIGKILL");
        done();
      }
    };
    const cancel = () => stop("cancelled");
    options.signal?.addEventListener("abort", cancel);
    // Declared after the launch: settle reads it only from callbacks, which always run later.
    const timer = setTimeout(() => stop(`timed out after ${timeoutMs / 1000} s`), timeoutMs);
  });
}

function quiet(file: string, args: string[]): Promise<string> {
  return new Promise((resolve) => {
    try {
      execFile(file, args, { windowsHide: true, encoding: "utf8", maxBuffer: 16 * 1024 * 1024 }, (_error, stdout) => resolve(stdout ?? ""));
    } catch {
      resolve("");
    }
  });
}

function signal(pid: number, name: NodeJS.Signals): void {
  try {
    process.kill(pid, name);
  } catch {
    // Already gone.
  }
}

// Kills pid and every process it started. Windows: taskkill /T /F, which walks the tree while its root is alive.
// POSIX: the descendants are found from ps by parent id, not by process group, since a child that started its own
// session (as the dispatcher does for each reviewer) leaves the group. Each round takes one ps snapshot, follows it to
// the whole tree under pid however deep, and stops every process found, so none can start another; rounds repeat
// until one finds nothing new, and then all of them are killed.
export async function killTree(pid: number): Promise<void> {
  if (process.platform === "win32") {
    const taskkill = join(process.env.SystemRoot ?? "C:\\Windows", "System32", "taskkill.exe");
    await quiet(taskkill, ["/T", "/F", "/PID", String(pid)]);
    return;
  }
  const ps = ["/bin/ps", "/usr/bin/ps"].find(runnable) ?? "ps";
  const tree = new Set([pid]);
  signal(pid, "SIGSTOP");
  for (let round = 0; round < 20; round += 1) {
    const parents = new Map<number, number[]>();
    for (const line of (await quiet(ps, ["-A", "-o", "pid=,ppid="])).split("\n")) {
      const [child, parent] = line.trim().split(/\s+/).map(Number);
      if (Number.isInteger(child) && Number.isInteger(parent)) {
        parents.set(parent, [...(parents.get(parent) ?? []), child]);
      }
    }
    const before = tree.size;
    const queue = [...tree];
    while (queue.length) {
      for (const child of parents.get(queue.pop() as number) ?? []) {
        if (!tree.has(child)) {
          tree.add(child);
          queue.push(child);
          signal(child, "SIGSTOP");
        }
      }
    }
    if (tree.size === before) {
      break;
    }
  }
  for (const member of tree) {
    signal(member, "SIGKILL");
  }
}
