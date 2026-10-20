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
  // How a tree is killed: killTree, which returns the processes still running at its deadline; tests pass one that
  // reports done later, to prove the run waits for it.
  killer?: (pid: number) => Promise<number[] | void>;
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
      // Processes the kill could not end are part of the result: a caller keeps what they may still use.
      const done = (survivors?: number[] | void) => settle(survivors && survivors.length
        ? { code: undefined, stdout: "", stderr: "", error: `${error}, but ${survivors.length} process${survivors.length === 1 ? "" : "es"} did not end (${survivors.join(", ")})`, survivors }
        : { code: undefined, stdout: "", stderr: "", error });
      if (options.tree && child.pid !== undefined) {
        void (options.killer ?? killTree)(child.pid).then(done, () => done());
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

// A helper's stdout, or "" when it fails, cannot start or runs past timeoutMs (it is then killed): the kill must go on
// whatever a helper does.
function quiet(file: string, args: string[], timeoutMs = HELPER_MS): Promise<string> {
  return new Promise((resolve) => {
    try {
      execFile(file, args, { windowsHide: true, encoding: "utf8", maxBuffer: 16 * 1024 * 1024, timeout: timeoutMs, killSignal: "SIGKILL" },
        (_error, stdout) => resolve(stdout ?? ""));
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

// What endTree needs from the system, so its loop can be tested with a made-up process table.
export interface TreeOps {
  // The process table as parent id to child ids; an empty map when it cannot be read.
  table(): Promise<Map<number, number[]>>;
  kill(pids: number[]): Promise<void>;
  running(pid: number): boolean;
  now(): number;
  sleep(ms: number): Promise<void>;
}

const HELPER_MS = 3000;
const KILL_WAIT_MS = 5000;

// work, or fallback once ms pass; the timer is cleared either way, so it never holds the process open.
function bounded<T>(work: Promise<T>, ms: number, fallback: T): Promise<T> {
  let timer: NodeJS.Timeout | undefined;
  const late = new Promise<T>((r) => (timer = setTimeout(() => r(fallback), ms)));
  return Promise.race([work, late]).finally(() => clearTimeout(timer));
}

// Ends root and every process under it, and returns the ones still running at the deadline (none, normally). Each
// round reads the process table, walks it from every process known so far (a dead parent keeps its id on its children
// on Windows, and on POSIX a child is found before its parent dies), kills whatever is still running, and looks again:
// a process started between a look and a kill is found by the next look. A table read that stalls counts as empty, so
// the kill still happens.
export async function endTree(root: number, ops: TreeOps, deadlineMs = KILL_WAIT_MS, helperMs = HELPER_MS): Promise<number[]> {
  const known = new Set([root]);
  const deadline = ops.now() + deadlineMs;
  for (;;) {
    const table = await bounded(ops.table(), helperMs, new Map<number, number[]>());
    const queue = [...known];
    while (queue.length) {
      for (const child of table.get(queue.pop() as number) ?? []) {
        if (!known.has(child)) {
          known.add(child);
          queue.push(child);
        }
      }
    }
    const alive = [...known].filter((pid) => ops.running(pid));
    if (alive.length === 0) {
      return [];
    }
    if (ops.now() >= deadline) {
      return alive;
    }
    await bounded(ops.kill(alive), helperMs, undefined);
    await ops.sleep(20);
  }
}

async function processTable(): Promise<Map<number, number[]>> {
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
  return children;
}

async function killAll(pids: number[]): Promise<void> {
  if (process.platform === "win32") {
    const taskkill = join(process.env.SystemRoot ?? "C:\\Windows", "System32", "taskkill.exe");
    for (let i = 0; i < pids.length; i += 50) {
      await quiet(taskkill, ["/F", ...pids.slice(i, i + 50).flatMap((pid) => ["/PID", String(pid)])]);
    }
    return;
  }
  // Stopped first, all of them, so none can start another process between two kills.
  pids.forEach((pid) => signal(pid, "SIGSTOP"));
  pids.forEach((pid) => signal(pid, "SIGKILL"));
}

// Kills pid and every process it started, returning once they have all ended, or with the ones still running after
// KILL_WAIT_MS. Descendants are found by parent id (CIM on Windows, ps on POSIX), not by process group: a child that
// started its own session (as the dispatcher does for each reviewer) leaves the group.
export function killTree(pid: number): Promise<number[]> {
  return endTree(pid, {
    table: processTable,
    kill: killAll,
    running,
    now: Date.now,
    sleep: (ms) => new Promise((r) => setTimeout(r, ms)),
  });
}
