import { lstatSync, readdirSync, rmdirSync, unlinkSync } from "node:fs";
import { join } from "node:path";

const BUSY = new Set(["EBUSY", "EPERM", "ENOTEMPTY"]);
const RETRIES = 5;

function retried(remove: () => void): void {
  for (let attempt = 0; ; attempt++) {
    try {
      remove();
      return;
    } catch (error) {
      const code = (error as NodeJS.ErrnoException).code ?? "";
      if (code === "ENOENT") {
        return;
      }
      if (!BUSY.has(code) || attempt >= RETRIES) {
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
    if (!["EPERM", "EISDIR"].includes((error as NodeJS.ErrnoException).code ?? "")) {
      throw error;
    }
    rmdirSync(path);
  }
}

// Deletes path and everything under it without ever going through a link: each entry is read with lstat, a symlink or
// junction (Node reports a junction as a symbolic link) is removed as an entry, and only real folders are descended.
// A path that does not exist is not an error.
//
// WORKAROUND: VS Code 1.142's runtime (Electron 43.7.7, Node 24.21.0) follows a junction in
// fs.rmSync(path, {recursive: true}) and deletes its target's contents (measured 2026-10-20, D02 T01 §20); standalone
// Node 24.14.1 does not. Every recursive delete in the extension goes through here instead.
export function removeTree(path: string): void {
  let isFolder: boolean;
  let isLink: boolean;
  try {
    const stat = lstatSync(path);
    isFolder = stat.isDirectory();
    isLink = stat.isSymbolicLink();
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") {
      return;
    }
    throw error;
  }
  if (isLink) {
    retried(() => removeLink(path));
  } else if (isFolder) {
    for (const name of readdirSync(path)) {
      removeTree(join(path, name));
    }
    retried(() => rmdirSync(path));
  } else {
    retried(() => unlinkSync(path));
  }
}
