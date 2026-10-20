import { createHash, randomBytes } from "node:crypto";
import { promises as fs } from "node:fs";
import { join } from "node:path";
import * as vscode from "vscode";
import type { WorkspaceState } from "../core/checkPin";
import { PIN } from "../core/workspaceState";

// What a save came to. saved carries the re-check's state (plan R14) and the toast design spec section 4 words; the
// refusals leave the pin exactly as it was and keep the edits.
export type SaveResult =
  | { kind: "saved"; state: WorkspaceState; message: string }
  | { kind: "stale"; message: string }
  | { kind: "read-only"; message: string }
  | { kind: "failed"; message: string };

export interface SaveDeps {
  // The dispatcher's check of the folder's own pin, which publishes the new state.
  check: (folder: vscode.Uri) => Promise<WorkspaceState>;
  log: (line: string) => void;
  // Test hooks: a step between the synced temporary file and the last hash check, the rename, the retry wait, the
  // removal of the temporary file, and every read of the pin.
  afterWrite?: () => Promise<void>;
  rename?: (from: string, to: string) => Promise<void>;
  delay?: (ms: number) => Promise<void>;
  remove?: (path: string) => Promise<void>;
  read?: (path: string) => Promise<Buffer>;
}

export type SaveHooks = Pick<SaveDeps, "afterWrite" | "rename" | "delay" | "remove" | "read">;

const RETRIES = 3;
const RETRY_MS = 100;
const ABSENT = "absent";

function sha256(bytes: Buffer): string {
  return createHash("sha256").update(bytes).digest("hex");
}

function code(error: unknown): string | undefined {
  return (error as NodeJS.ErrnoException | undefined)?.code;
}

type Refusal = Exclude<SaveResult, { kind: "saved" }>;

// One folder's pin as the editor loaded it (plan R13 to R15, design spec sections 3 and 4). A save goes through a
// temporary file in .conclave/ and a rename, and is refused when the file on disk no longer has the hash it had when
// loaded: checked as the last step before the rename and again before every retry. A watcher marks the session stale
// as soon as another program writes the pin, so most conflicts show before Save is pressed.
//
// Load, save and the watcher's disk check run one at a time, in the order asked: a reload waits for a save in flight
// (so it can never move the baseline a save is checking against), and a watcher read never straddles a save.
export class PinSession implements vscode.Disposable {
  private loadedText = "";
  private loadedHash = ABSENT;
  private isStale = false;
  private queue: Promise<unknown> = Promise.resolve();
  private readonly watcher: vscode.FileSystemWatcher;
  private readonly changed = new vscode.EventEmitter<boolean>();
  readonly onDidChangeStale = this.changed.event;
  readonly pin: string;

  constructor(readonly folder: vscode.Uri, private readonly deps: SaveDeps) {
    this.pin = join(folder.fsPath, PIN);
    this.watcher = vscode.workspace.createFileSystemWatcher(new vscode.RelativePattern(folder, PIN));
    const seen = () => void this.checkDisk();
    this.watcher.onDidChange(seen);
    this.watcher.onDidCreate(seen);
    this.watcher.onDidDelete(seen);
  }

  get text(): string {
    return this.loadedText;
  }

  get stale(): boolean {
    return this.isStale;
  }

  // Reads the pin and records its hash: the text Discard returns to and the hash Save compares against.
  load(): Promise<string> {
    return this.serial(async () => {
      const { text, hash } = await this.readPin();
      this.loadedText = text;
      this.loadedHash = hash;
      this.setStale(false);
      this.deps.log(`Loaded ${PIN} in ${this.folder.fsPath} (sha256 ${hash === ABSENT ? "absent" : hash.slice(0, 16)}).`);
      return text;
    });
  }

  // The editor's model returns to the text as loaded; disk is not read.
  discard(): string {
    return this.loadedText;
  }

  // After stale, or a change seen by the watcher: the editor takes what is on disk now.
  reload(): Promise<string> {
    return this.load();
  }

  // What the watcher runs on an event: stale when the disk no longer has the loaded hash (our own rename leaves them
  // equal, since a save updates the hash before the queue moves on).
  checkDisk(): Promise<void> {
    return this.serial(async () => {
      try {
        if ((await this.readPin()).hash !== this.loadedHash) {
          this.setStale(true);
        }
      } catch {
        this.setStale(true);
      }
    });
  }

  save(text: string): Promise<SaveResult> {
    return this.serial(() => this.saveNow(text));
  }

  private async saveNow(text: string): Promise<SaveResult> {
    const temp = join(this.folder.fsPath, ".conclave", `.reviewers.toml.${randomBytes(6).toString("hex")}.tmp`);
    const written = { created: false };
    let result: SaveResult;
    try {
      result = await this.write(text, temp, written);
    } catch (error) {
      result = { kind: "failed", message: `${PIN} was not saved: ${String(error)}. Your edits are kept.` };
    }
    // The temporary file is removed on every path that created it and did not rename it; a removal that fails is
    // part of the result, never a rejection that loses it.
    if (written.created) {
      try {
        await (this.deps.remove ?? ((path: string) => fs.rm(path, { force: true })))(temp);
      } catch (error) {
        result = { ...result, message: `${result.message} The temporary file ${temp} could not be deleted: ${String(error)}.` } as SaveResult;
      }
    }
    if (result.kind !== "saved") {
      this.deps.log(`Save refused (${result.kind}) in ${this.folder.fsPath}: ${result.message}`);
      return result;
    }
    this.deps.log(`${result.message} (${this.folder.fsPath})`);
    return result;
  }

  // Everything up to and including the re-check; written.created is true while a temporary file exists to remove.
  private async write(text: string, temp: string, written: { created: boolean }): Promise<SaveResult> {
    const rename = this.deps.rename ?? fs.rename;
    const delay = this.deps.delay ?? ((ms: number) => new Promise<void>((r) => setTimeout(r, ms)));
    const baseline = this.loadedHash;
    // A pin marked read-only is the operator's choice: refused before anything is written.
    const existing = await fs.stat(this.pin).catch(() => undefined);
    if (existing) {
      try {
        await fs.access(this.pin, fs.constants.W_OK);
      } catch {
        return refusal("read-only", `${PIN} is read-only, so it was not saved. Make it writable, then save again.`);
      }
    }
    let handle: fs.FileHandle;
    try {
      handle = await fs.open(temp, "wx", existing ? existing.mode & 0o777 : 0o644);
    } catch (error) {
      if (["EACCES", "EPERM", "EROFS"].includes(code(error) ?? "")) {
        return refusal("read-only", `.conclave/ is read-only, so ${PIN} was not saved: ${String(error)}.`);
      }
      throw error;
    }
    written.created = true;
    try {
      await handle.writeFile(text, "utf8");
      await handle.sync();
    } finally {
      await handle.close();
    }
    await this.deps.afterWrite?.();
    for (let attempt = 0; ; attempt += 1) {
      // The last step before the rename: another program's change since load refuses the save and is kept.
      if ((await this.readPin()).hash !== baseline) {
        this.setStale(true);
        return refusal("stale", `${PIN} changed on disk since it was loaded, so it was not saved. Reload from disk to see the change; your edits are kept until then.`);
      }
      try {
        await rename(temp, this.pin);
        written.created = false;
        break;
      } catch (error) {
        const held = ["EPERM", "EBUSY"].includes(code(error) ?? "");
        if (!held || attempt >= RETRIES) {
          return refusal("failed", held
            ? `${PIN} is held open by another program, so it was not saved after ${RETRIES} retries. Your edits are kept.`
            : `${PIN} was not saved: ${String(error)}. Your edits are kept.`);
        }
        await delay(RETRY_MS);
      }
    }
    this.loadedText = text;
    this.loadedHash = sha256(Buffer.from(text, "utf8"));
    this.setStale(false);
    const state = await this.deps.check(this.folder);
    const message = state.state === "refused"
      ? `Saved, but --check-pin now refuses the pin: ${state.error}`
      : `Saved ${PIN} through a temporary file and a rename. Re-checked with --check-pin: ${state.state === "ready" ? "ok" : state.state}.`;
    return { kind: "saved", state, message };
  }

  // The pin's bytes and their hash, or ABSENT when there is no pin.
  private async readPin(): Promise<{ text: string; hash: string }> {
    try {
      const bytes = await (this.deps.read ?? fs.readFile)(this.pin);
      return { text: bytes.toString("utf8"), hash: sha256(bytes) };
    } catch (error) {
      if (code(error) === "ENOENT") {
        return { text: "", hash: ABSENT };
      }
      throw error;
    }
  }

  // Runs fn after every load, save and disk check asked before it, whether those succeeded or not.
  private serial<T>(fn: () => Promise<T>): Promise<T> {
    const next = this.queue.then(fn, fn);
    this.queue = next.catch(() => undefined);
    return next;
  }

  private setStale(stale: boolean): void {
    if (stale !== this.isStale) {
      this.isStale = stale;
      this.changed.fire(stale);
    }
  }

  dispose(): void {
    this.watcher.dispose();
    this.changed.dispose();
  }
}

function refusal(kind: Refusal["kind"], message: string): Refusal {
  return { kind, message };
}
