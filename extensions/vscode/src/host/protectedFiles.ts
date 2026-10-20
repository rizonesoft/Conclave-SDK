import { createHash } from "node:crypto";
import { lstatSync, readdirSync, readFileSync, readlinkSync } from "node:fs";
import { join } from "node:path";
import { PROTECTED_FILES, PROTECTED_FOLDERS } from "../core/protectedFiles";

// A protected path that could not be read: the proof cannot be made, which is not the same as the file being absent.
export class Unreadable extends Error {
  constructor(readonly path: string, readonly code: string) {
    super(`${path} could not be read (${code})`);
  }
}

const ABSENT = new Set(["ENOENT", "ENOTDIR"]);

type Entry = { kind: "absent" } | { kind: "link"; digest: string } | { kind: "folder" } | { kind: "file" };

// What is at rel inside folder, by lstat, so a link is never followed: its target is not the project's file to vouch
// for, and reading through it could leave the folder.
function entry(folder: string, rel: string): Entry {
  const path = join(folder, rel);
  try {
    const stat = lstatSync(path);
    if (stat.isSymbolicLink()) {
      // The link itself is the protected thing: a retargeted link is a change, read without leaving the folder.
      return { kind: "link", digest: `link:${readlinkSync(path)}` };
    }
    return stat.isDirectory() ? { kind: "folder" } : { kind: "file" };
  } catch (error) {
    const code = (error as NodeJS.ErrnoException).code ?? "unknown";
    if (ABSENT.has(code)) {
      return { kind: "absent" };
    }
    throw new Unreadable(rel, code);
  }
}

function hashFile(folder: string, rel: string): string {
  try {
    return createHash("sha256").update(readFileSync(join(folder, rel))).digest("hex");
  } catch (error) {
    throw new Unreadable(rel, (error as NodeJS.ErrnoException).code ?? "unknown");
  }
}

// Records rel, walking down from folder one component at a time: a link on the way is recorded under its own path and
// not gone through, a folder under a protected folder is walked, and a file is hashed.
function record(folder: string, rel: string, into: Map<string, string>, walk: boolean): void {
  const parts = rel.split("/");
  for (let i = 1; i < parts.length; i++) {
    const ancestor = parts.slice(0, i).join("/");
    const found = entry(folder, ancestor);
    if (found.kind === "absent") {
      return;
    }
    if (found.kind === "link") {
      into.set(ancestor, found.digest);
      return;
    }
  }
  const found = entry(folder, rel);
  if (found.kind === "link") {
    into.set(rel, found.digest);
  } else if (found.kind === "file") {
    into.set(rel, hashFile(folder, rel));
  } else if (found.kind === "folder" && walk) {
    let names: string[];
    try {
      names = readdirSync(join(folder, rel));
    } catch (error) {
      throw new Unreadable(rel, (error as NodeJS.ErrnoException).code ?? "unknown");
    }
    for (const name of names) {
      record(folder, `${rel}/${name}`, into, true);
    }
  }
}

// The hash of every protected file that exists in folder (plan R32), by its relative path, with a link recorded by its
// target text instead of being followed. Throws Unreadable when a protected path exists but cannot be read.
export function protectedSnapshot(folder: string): Map<string, string> {
  const snapshot = new Map<string, string>();
  for (const rel of PROTECTED_FILES) {
    record(folder, rel, snapshot, false);
  }
  for (const dir of PROTECTED_FOLDERS) {
    record(folder, dir, snapshot, true);
  }
  return snapshot;
}
