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

// A folder that is this account's alone: a real directory (lstat, so a symlink or Windows junction planted in its place
// is not followed; Node reports a junction as a symbolic link), owned by this account and closed to others on POSIX.
// Windows' temporary folder is per account already, so ownership and mode are POSIX-only.
function ownPrivateFolder(dir: string): boolean {
  try {
    const info = lstatSync(dir);
    if (!info.isDirectory() || info.isSymbolicLink()) {
      return false;
    }
    return process.platform === "win32" || (info.uid === process.getuid?.() && (info.mode & 0o077) === 0);
  } catch {
    return false;
  }
}

// The folder asked for when it is safely ours; otherwise a private folder for this process, so no other account can
// read or swap a candidate between its write and the dispatcher's read. The fallback is checked on every use, since
// another window's activation sweep removes an old empty one; it is then made again. Fallbacks are named conclave-XXXXXX.
function folder(dir: string): string {
  try {
    mkdirSync(dir, { recursive: true, mode: 0o700 });
  } catch {
    // Something other than a folder holds the name: fall back below.
  }
  if (ownPrivateFolder(dir)) {
    return dir;
  }
  if (fallback === undefined || !ownPrivateFolder(fallback)) {
    fallback = mkdtempSync(join(tmpdir(), "conclave-"));
  }
  return fallback;
}

// Writes all of text to a new candidate file, gives its path to use, and deletes it whatever happens after it was
// created: a failed or short write, a failed close or a failed check. write is writeSync; tests pass a short one.
export async function withCandidate<T>(text: string, use: (path: string) => Promise<T>, dir = CANDIDATES,
  write: typeof writeSync = writeSync): Promise<T> {
  counter += 1;
  const path = join(folder(dir), `pin-${process.pid}-${counter}.toml`);
  let created = false;
  try {
    const fd = openSync(path, "wx", 0o600);
    created = true;
    try {
      // writeSync may write fewer bytes than asked; the dispatcher must judge the whole candidate, never a prefix.
      const bytes = Buffer.from(text, "utf8");
      let offset = 0;
      while (offset < bytes.length) {
        const written = write(fd, bytes, offset, bytes.length - offset);
        if (written <= 0) {
          throw new Error(`the candidate file took ${offset} of ${bytes.length} bytes`);
        }
        offset += written;
      }
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
  // The shared folder is swept only when it is this account's own real folder: never through a symlink planted there.
  let removed = ownPrivateFolder(dir) ? sweepFolder(dir, now) : 0;
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
