import { closeSync, lstatSync, mkdirSync, mkdtempSync, openSync, readdirSync, rmdirSync, rmSync, statSync, writeSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

// Candidate files (design spec section 1): <os.tmpdir()>/conclave/pin-<pid>-<counter>.toml, the folder private (0700),
// each file private (0600) and created exclusively (never reusing a name), deleted as soon as its check ends. In the
// Remote WSL host os.tmpdir() is the Linux side's, where the dispatcher runs too.
export const CANDIDATES = join(tmpdir(), "conclave");
const DAY_MS = 24 * 60 * 60 * 1000;
const NAME = /^pin-\d+-\d+\.toml$/;
const FALLBACK = /^conclave-[A-Za-z0-9]{6}$/;
let counter = 0;
let fallback: string | undefined;

// A folder that is this account's alone: a real directory (lstat, so a symlink planted in its place is not followed),
// owned by this account, closed to others. Windows' temporary folder is per account already.
function ownPrivateFolder(dir: string): boolean {
  if (process.platform === "win32") {
    return true;
  }
  try {
    const info = lstatSync(dir);
    return info.isDirectory() && !info.isSymbolicLink() && info.uid === process.getuid?.() && (info.mode & 0o077) === 0;
  } catch {
    return false;
  }
}

// The shared folder when it is safely ours; otherwise a fresh private folder for this process, so no other account can
// read or swap a candidate between its write and the dispatcher's read. The swept folders are named conclave-XXXXXX.
function folder(dir: string): string {
  try {
    mkdirSync(dir, { recursive: true, mode: 0o700 });
  } catch {
    // Something other than a folder holds the name: fall back below.
  }
  if (dir !== CANDIDATES || ownPrivateFolder(dir)) {
    return dir;
  }
  fallback ??= mkdtempSync(join(tmpdir(), "conclave-"));
  return fallback;
}

// Writes text to a new candidate file, gives its path to use, and deletes it whatever happens after it was created:
// a failed write, a failed close or a failed check.
export async function withCandidate<T>(text: string, use: (path: string) => Promise<T>, dir = CANDIDATES): Promise<T> {
  counter += 1;
  const path = join(folder(dir), `pin-${process.pid}-${counter}.toml`);
  let created = false;
  try {
    const fd = openSync(path, "wx", 0o600);
    created = true;
    try {
      writeSync(fd, text);
    } finally {
      closeSync(fd);
    }
    return await use(path);
  } finally {
    if (created) {
      rmSync(path, { force: true });
    }
  }
}

function sweepFolder(dir: string, now: number): number {
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

// At activation: candidate files older than a day were left by a crash between write and delete; remove them from the
// shared folder and from this account's fallback folders, and remove a fallback folder left empty.
export function sweepCandidates(dir = CANDIDATES, now = Date.now(), temp = tmpdir()): number {
  let removed = sweepFolder(dir, now);
  let names: string[];
  try {
    names = readdirSync(temp).filter((n) => FALLBACK.test(n));
  } catch {
    names = [];
  }
  for (const name of names) {
    const own = join(temp, name);
    if (own === fallback || !ownPrivateFolder(own)) {
      continue;
    }
    // The folder's age is read before sweeping it, since deleting a file inside refreshes the folder's mtime.
    let old: boolean;
    try {
      old = now - statSync(own).mtimeMs > DAY_MS;
    } catch {
      continue;
    }
    removed += sweepFolder(own, now);
    try {
      if (old && readdirSync(own).length === 0) {
        rmdirSync(own);
      }
    } catch {
      // In use or gone: left for the next sweep.
    }
  }
  return removed;
}
