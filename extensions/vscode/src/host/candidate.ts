import { closeSync, mkdirSync, mkdtempSync, openSync, readdirSync, rmSync, statSync, writeSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

// Candidate files (design spec section 1): <os.tmpdir()>/conclave/pin-<pid>-<counter>.toml, the folder private (0700),
// each file private (0600) and created exclusively (never reusing a name), deleted as soon as its check ends. In the
// Remote WSL host os.tmpdir() is the Linux side's, where the dispatcher runs too.
export const CANDIDATES = join(tmpdir(), "conclave");
const DAY_MS = 24 * 60 * 60 * 1000;
const NAME = /^pin-\d+-\d+\.toml$/;
let counter = 0;
let fallback: string | undefined;

// The shared folder, unless on POSIX it belongs to someone else or others may enter it; then a fresh private folder
// for this process, so no other account can read or swap a candidate between its write and the dispatcher's read.
function folder(dir: string): string {
  mkdirSync(dir, { recursive: true, mode: 0o700 });
  if (process.platform === "win32" || dir !== CANDIDATES) {
    return dir;
  }
  const info = statSync(dir);
  if (info.uid === process.getuid?.() && (info.mode & 0o077) === 0) {
    return dir;
  }
  fallback ??= mkdtempSync(join(tmpdir(), "conclave-"));
  return fallback;
}

// Writes text to a new candidate file, gives its path to use, and deletes it whatever use does.
export async function withCandidate<T>(text: string, use: (path: string) => Promise<T>, dir = CANDIDATES): Promise<T> {
  counter += 1;
  const path = join(folder(dir), `pin-${process.pid}-${counter}.toml`);
  const fd = openSync(path, "wx", 0o600);
  try {
    writeSync(fd, text);
  } finally {
    closeSync(fd);
  }
  try {
    return await use(path);
  } finally {
    rmSync(path, { force: true });
  }
}

// At activation: candidate files older than a day are left by a crash between write and delete; remove them.
export function sweepCandidates(dir = CANDIDATES, now = Date.now()): number {
  let removed = 0;
  let names: string[];
  try {
    names = readdirSync(dir);
  } catch {
    return 0;
  }
  for (const name of names.filter((n) => NAME.test(n))) {
    try {
      if (now - statSync(join(dir, name)).mtimeMs > DAY_MS) {
        rmSync(join(dir, name), { force: true });
        removed += 1;
      }
    } catch {
      // Gone already, or another process's file being deleted: nothing to sweep.
    }
  }
  return removed;
}
