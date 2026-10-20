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
  // How a tree is killed: killTree, which says what it could not end; tests pass one that reports done later, to
  // prove the run waits for it.
  killer?: (pid: number) => Promise<TreeEnd | void>;
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
      // What the kill could not end, or could not confirm, is part of the result: a caller keeps what they may still use.
      const done = (end?: TreeEnd | void) => {
        if (end && end.survivors.length) {
          const n = end.survivors.length;
          const unseen = end.verified ? "" : ", and the process table could not be read to confirm that every other process ended";
          settle({
            code: undefined, stdout: "", stderr: "", error: `${error}, but ${n} process${n === 1 ? "" : "es"} did not end (${end.survivors.join(", ")})${unseen}`,
            survivors: end.survivors, ...(end.verified ? {} : { unverified: true }),
          });
        } else if (end && !end.verified) {
          settle({ code: undefined, stdout: "", stderr: "", error: `${error}, but the process table could not be read to confirm that every process ended`, survivors: [], unverified: true });
        } else {
          settle({ code: undefined, stdout: "", stderr: "", error });
        }
      };
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

// A helper's stdout, or undefined when it fails, cannot start or runs past timeoutMs (it is then killed): the kill must
// go on whatever a helper does, and a caller can tell a failed read from an empty one.
function quiet(file: string, args: string[], timeoutMs = HELPER_MS): Promise<string | undefined> {
  return new Promise((resolve) => {
    try {
      execFile(file, args, { windowsHide: true, encoding: "utf8", maxBuffer: 16 * 1024 * 1024, timeout: timeoutMs, killSignal: "SIGKILL" },
        (error, stdout) => resolve(error ? undefined : stdout));
    } catch {
      resolve(undefined);
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
  // The process table as parent id to child ids; undefined when it cannot be read, which is never taken for empty.
  table(): Promise<Map<number, number[]> | undefined>;
  // Freezes processes so none can start another while the tree is read (SIGSTOP); absent where the platform cannot.
  stop?(pids: number[]): void;
  kill(pids: number[]): Promise<void>;
  running(pid: number): boolean;
  now(): number;
  sleep(ms: number): Promise<void>;
}

// How a tree kill ended: the processes still running at the deadline, and whether the last look at the process table
// could be read (false: the tree may hold processes nobody could see).
export interface TreeEnd {
  survivors: number[];
  verified: boolean;
}

const HELPER_MS = 3000;
// taskkill is given less than the helper bound, so it has been killed before endTree's next round starts another.
const KILL_HELPER_MS = 2500;
const KILL_WAIT_MS = 5000;

// work, or fallback once ms pass; the timer is cleared either way, so it never holds the process open.
function bounded<T>(work: Promise<T>, ms: number, fallback: T): Promise<T> {
  let timer: NodeJS.Timeout | undefined;
  const late = new Promise<T>((r) => (timer = setTimeout(() => r(fallback), ms)));
  return Promise.race([work, late]).finally(() => clearTimeout(timer));
}

// Ends root and every process under it.
//
// Where processes can be frozen (POSIX), the whole tree is frozen before anything dies: the root is stopped, and each
// look at the process table stops every new process it finds, until a look finds nothing new or cannot be read.
// Killing first would lose a child born between a look and its parent's stop, since a POSIX child of a dead parent is
// reparented away from the walk. Then every round kills what is known to run, before it looks again, so a slow table
// never keeps the kill from happening; on Windows, which keeps a dead parent's id on its children, the next look finds
// a process born between a look and a kill.
//
// The end is confirmed (verified) only by a look that was read and shows nothing running and, on POSIX, only if no look
// failed before the first kill: a child reparented while its ancestry could not be read cannot be found by any later
// look. A table that cannot be read is never taken as empty.
export async function endTree(root: number, ops: TreeOps, deadlineMs = KILL_WAIT_MS, helperMs = HELPER_MS): Promise<TreeEnd> {
  const known = new Set([root]);
  const deadline = ops.now() + deadlineMs;
  const reparents = ops.stop !== undefined;
  let blind = false;
  let killed = false;
  const look = async (): Promise<boolean> => {
    const table = await bounded(ops.table(), helperMs, undefined);
    if (!table) {
      if (reparents && !killed) {
        blind = true;
      }
      return false;
    }
    const queue = [...known];
    while (queue.length) {
      for (const child of table.get(queue.pop() as number) ?? []) {
        if (!known.has(child)) {
          known.add(child);
          ops.stop?.([child]);
          queue.push(child);
        }
      }
    }
    return true;
  };
  if (ops.stop) {
    ops.stop([root]);
    // Complete only when a look finds nothing new: discovery that the deadline or a failed read ends early may have
    // missed a child that the kill then reparents, so the end cannot be confirmed.
    let complete = false;
    while (!complete && ops.now() < deadline) {
      const before = known.size;
      if (!(await look())) {
        break;
      }
      complete = known.size === before;
    }
    blind ||= !complete;
  }
  for (;;) {
    const alive = [...known].filter((pid) => ops.running(pid));
    if (alive.length) {
      await bounded(ops.kill(alive), helperMs, undefined);
      killed = true;
    }
    const read = await look();
    const left = [...known].filter((pid) => ops.running(pid));
    if (read && left.length === 0) {
      return { survivors: [], verified: !blind };
    }
    if (ops.now() >= deadline) {
      return { survivors: left, verified: read && !blind };
    }
    await ops.sleep(20);
  }
}

async function processTable(): Promise<Map<number, number[]> | undefined> {
  const table = process.platform === "win32"
    ? await quiet(join(process.env.SystemRoot ?? "C:\\Windows", "System32", "WindowsPowerShell", "v1.0", "powershell.exe"),
      ["-NoProfile", "-NonInteractive", "-Command", "Get-CimInstance Win32_Process | ForEach-Object { \"$($_.ProcessId) $($_.ParentProcessId)\" }"])
    : await quiet(["/bin/ps", "/usr/bin/ps"].find(runnable) ?? "ps", ["-A", "-o", "pid=,ppid="]);
  if (table === undefined || table.trim() === "") {
    return undefined;
  }
  const children = new Map<number, number[]>();
  for (const line of table.split("\n")) {
    const [child, parent] = line.trim().split(/\s+/).map(Number);
    if (Number.isInteger(child) && Number.isInteger(parent) && child !== parent) {
      children.set(parent, [...(children.get(parent) ?? []), child]);
    }
  }
  return children;
}

// Windows: one taskkill per round, /T so it also walks each tree itself, at most 500 ids (the rest go next round),
// bounded so it has ended before the next round. POSIX: the tree is already stopped; each process is killed.
async function killAll(pids: number[]): Promise<void> {
  if (process.platform === "win32") {
    const taskkill = join(process.env.SystemRoot ?? "C:\\Windows", "System32", "taskkill.exe");
    await quiet(taskkill, ["/T", "/F", ...pids.slice(0, 500).flatMap((pid) => ["/PID", String(pid)])], KILL_HELPER_MS);
    return;
  }
  pids.forEach((pid) => signal(pid, "SIGSTOP"));
  pids.forEach((pid) => signal(pid, "SIGKILL"));
}

// Kills pid and every process it started, returning once they have all ended, or with what it could not end or
// confirm after KILL_WAIT_MS. Descendants are found by parent id (CIM on Windows, ps on POSIX), not by process group:
// a child that started its own session (as the dispatcher does for each reviewer) leaves the group.
export function killTree(pid: number): Promise<TreeEnd> {
  return endTree(pid, {
    table: processTable,
    stop: process.platform === "win32" ? undefined : (pids) => pids.forEach((p) => signal(p, "SIGSTOP")),
    kill: killAll,
    running,
    now: Date.now,
    sleep: (ms) => new Promise((r) => setTimeout(r, ms)),
  });
}
