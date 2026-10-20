import { createHash } from "node:crypto";
import { lstatSync, readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { PROTECTED_FILES, PROTECTED_FOLDERS } from "../core/protectedFiles";

function hash(path: string): string | undefined {
  try {
    // A link is not followed: its target is not the project's file to vouch for, and reading through it could leave
    // the folder.
    if (!lstatSync(path).isFile()) {
      return undefined;
    }
    return createHash("sha256").update(readFileSync(path)).digest("hex");
  } catch {
    return undefined;
  }
}

function walk(folder: string, prefix: string, into: Map<string, string>): void {
  let names: string[];
  try {
    names = readdirSync(folder);
  } catch {
    return;
  }
  for (const name of names) {
    const path = join(folder, name);
    const rel = `${prefix}/${name}`;
    let isDir: boolean;
    try {
      isDir = lstatSync(path).isDirectory();
    } catch {
      continue;
    }
    if (isDir) {
      walk(path, rel, into);
    } else {
      const digest = hash(path);
      if (digest) {
        into.set(rel, digest);
      }
    }
  }
}

// The hash of every protected file that exists in folder (plan R32), by its relative path.
export function protectedSnapshot(folder: string): Map<string, string> {
  const snapshot = new Map<string, string>();
  for (const rel of PROTECTED_FILES) {
    const digest = hash(join(folder, rel));
    if (digest) {
      snapshot.set(rel, digest);
    }
  }
  for (const dir of PROTECTED_FOLDERS) {
    walk(join(folder, dir), dir, snapshot);
  }
  return snapshot;
}
