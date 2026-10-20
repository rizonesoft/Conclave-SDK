import { type BigIntStats, lstatSync, readdirSync, rmdirSync, unlinkSync } from "node:fs";
import { join } from "node:path";

const BUSY = new Set(["EBUSY", "ENOTEMPTY"]);
const RETRIES = 5;

function code(error: unknown): string {
  return (error as NodeJS.ErrnoException).code ?? "";
}

function retried(remove: () => void): void {
  for (let attempt = 0; ; attempt++) {
    try {
      remove();
      return;
    } catch (error) {
      if (code(error) === "ENOENT") {
        return;
      }
      if (!BUSY.has(code(error)) || attempt >= RETRIES) {
        throw error;
      }
      // A virus scanner or indexer can hold a file just written for a moment on Windows.
      Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 50 * (attempt + 1));
    }
  }
}

function removeLink(path: string): void {
  try {
    unlinkSync(path);
  } catch (error) {
    // A junction or a directory symlink on Windows is removed as a folder entry; rmdir never touches its target.
    if (!["EPERM", "EISDIR"].includes(code(error))) {
      throw error;
    }
    rmdirSync(path);
  }
}

function stat(path: string): BigIntStats | undefined {
  try {
    return lstatSync(path, { bigint: true });
  } catch (error) {
    if (code(error) === "ENOENT") {
      return undefined;
    }
    throw error;
  }
}

// Whether path is still the folder first read there: not gone, not a link, the same file system object.
function unchanged(path: string, first: BigIntStats): boolean {
  const now = stat(path);
  return now !== undefined && !now.isSymbolicLink() && now.isDirectory() && now.ino === first.ino && now.dev === first.dev;
}

// Deletes path and everything under it without going through a link: each entry is read with lstat, a symlink or
// junction (Node reports a junction as a symbolic link) is removed as an entry, and only real folders are descended. A
// folder is checked to be the same folder before each entry under it is removed, so one swapped for a link while it is
// being removed stops the delete with an error. What remains is the moment between that check and the removal: only a
// process of the same user can swap a folder there, and it could delete the files itself. A path that does not exist,
// or that disappears while it is removed (another window removing the same entry), is not an error.
//
// WORKAROUND: VS Code 1.142's runtime (Electron 43.7.7, Node 24.21.0) follows a junction in
// fs.rmSync(path, {recursive: true}) and deletes its target's contents (measured 2026-10-20, D02 T01 §20); standalone
// Node 24.14.1 does not. Every recursive delete in the extension goes through here instead.
export function removeTree(path: string): void {
  const first = stat(path);
  if (first === undefined) {
    return;
  }
  if (first.isSymbolicLink()) {
    retried(() => removeLink(path));
    return;
  }
  if (!first.isDirectory()) {
    // On Windows unlink clears a read-only attribute itself (libuv), as rmSync does.
    retried(() => unlinkSync(path));
    return;
  }
  let names: string[];
  try {
    names = readdirSync(path);
  } catch (error) {
    if (code(error) === "ENOENT") {
      return;
    }
    throw error;
  }
  for (const name of names) {
    if (!unchanged(path, first)) {
      if (stat(path) === undefined) {
        return;
      }
      throw new Error(`${path} changed while it was being removed (it is no longer the same folder), so the delete stopped`);
    }
    removeTree(join(path, name));
  }
  retried(() => rmdirSync(path));
}
