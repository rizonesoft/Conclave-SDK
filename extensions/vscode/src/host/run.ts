import { execFile } from "node:child_process";
import { accessSync, constants, readFileSync, statSync } from "node:fs";
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

// Running, not merely present: a killed process stays in the table until it is reaped (a zombie on POSIX), and on
// Linux /proc says which; elsewhere signal 0 does (Windows reports a terminated process as gone).
export function running(pid: number): boolean {
  if (process.platform === "linux") {
    try {
      const stat = readFileSync(`/proc/${pid}/stat`, "utf8");
      const state = stat.slice(stat.lastIndexOf(")") + 2, stat.lastIndexOf(")") + 3);
      return state !== "Z" && state !== "X";
    } catch {
      return false;
    }
  }
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}

// Every process under pid in one snapshot of the process table, however deep. POSIX: ps; Windows: the parent ids from
// CIM (taskkill's own report is localized, so it cannot be read back). An unreadable table gives pid alone.
async function descendants(pid: number): Promise<Set<number>> {
  const table = process.platform === "win32"
    ? await quiet(join(process.env.SystemRoot ?? "C:\\Windows", "System32", "WindowsPowerShell", "v1.0", "powershell.exe"),
      ["-NoProfile", "-NonInteractive", "-Command", "Get-CimInstance Win32_Process | ForEach-Object { \"$($_.ProcessId) $($_.ParentProcessId)\" }"])
    : await quiet(["/bin/ps", "/usr/bin/ps"].find(runnable) ?? "ps", ["-A", "-o", "pid=,ppid="]);
  const children = new Map<number, number[]>();
  for (const line of table.split("\n")) {
    const [child, parent] = line.trim().split(/\s+/).map(Number);
    if (Number.isInteger(child) && Number.isInteger(parent) && child !== parent) {
      children.set(parent, [...(children.get(parent) ?? []), child]);
    }
  }
  const tree = new Set([pid]);
  const queue = [pid];
  while (queue.length) {
    for (const child of children.get(queue.pop() as number) ?? []) {
      if (!tree.has(child)) {
        tree.add(child);
        queue.push(child);
      }
    }
  }
  return tree;
}

// Kills pid and every process it started, and returns once they have all ended (at most KILL_WAIT_MS): a signal or
// TerminateProcess only starts the end, and a caller that cleans up after a cancel must not race the tree.
// Windows: the tree is read first, then taskkill /T /F, which walks it while its root is alive. POSIX: the descendants
// are found by parent id, not by process group, since a child that started its own session (as the dispatcher does
// for each reviewer) leaves the group. Each round stops every process found, so none can start another, and rounds
// repeat until one finds nothing new; then all of them are killed.
export async function killTree(pid: number): Promise<void> {
  let tree: Set<number>;
  if (process.platform === "win32") {
    tree = await descendants(pid);
    await quiet(join(process.env.SystemRoot ?? "C:\\Windows", "System32", "taskkill.exe"), ["/T", "/F", "/PID", String(pid)]);
  } else {
    tree = new Set([pid]);
    signal(pid, "SIGSTOP");
    for (let round = 0; round < 20; round += 1) {
      const before = tree.size;
      for (const member of await descendants(pid)) {
        if (!tree.has(member)) {
          tree.add(member);
          signal(member, "SIGSTOP");
        }
      }
      // A stopped process cannot start another, but one may have started just before its stop: look again.
      if (tree.size === before) {
        break;
      }
    }
    for (const member of tree) {
      signal(member, "SIGKILL");
    }
  }
  const deadline = Date.now() + KILL_WAIT_MS;
  while ([...tree].some(running) && Date.now() < deadline) {
    await new Promise((r) => setTimeout(r, 10));
  }
}

const KILL_WAIT_MS = 5000;
