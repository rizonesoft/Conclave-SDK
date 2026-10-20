import { readdirSync } from "node:fs";
import { join } from "node:path";
import * as vscode from "vscode";
import { parseKit, parseKits } from "../core/forgeJson";
import { kitState, type KitState, refusalReason } from "../core/kitState";
import type { Python } from "../core/python";
import type { ForgeSource } from "./forge";
import { runForge } from "./forge";
import type { run } from "./run";

export type KitStates = { ok: true; kits: KitState[] } | { ok: false; message: string };

export interface KitStateDeps {
  // Where forge.py comes from for this folder (D02 T01 §7), or why there is none.
  source: (folder: vscode.Uri) => Promise<ForgeSource | { message: string }>;
  python: (folder: vscode.Uri) => Promise<Python | { message: string }>;
  // Fires when a folder's Python is resolved (undefined: every folder), with what it resolved to; the state is read
  // again only when that differs from the Python it was computed with (the first resolution is not a change).
  onDidResolvePython?: vscode.Event<{ folder: vscode.Uri | undefined; python: Python | { message: string } }>;
  // The process runner for forge; tests pass one that holds a dry run, to order it against an invalidation.
  run?: typeof run;
}

const SETTLE_MS = 300;

function identity(python: Python | { message: string }): string {
  return "command" in python ? `${python.command} ${python.prefix.join(" ")} ${python.version}` : `none: ${python.message}`;
}
// A computation that a later invalidation superseded runs again, at most this many times in a row, so a folder that
// never stops changing still gets an answer.
const ATTEMPTS = 5;

// What forge reads and writes when it answers for a kit: the top-level entries of every kit's templates (and of the
// WordPress host templates), the Laravel app's artisan and .mcp.json, and, since the Laravel kit installs under the
// app root (the folder itself, platform/, or a first-level child), the same one level down. Read from the SDK source
// itself, so a kit that adds a path is watched without a change here.
export function watchedGlobs(sdkFolder: string): string[] {
  const names = new Set(["artisan", ".mcp.json"]);
  const add = (dir: string) => {
    try {
      readdirSync(dir).forEach((n) => names.add(n));
    } catch {
      // A kit without that folder adds nothing.
    }
  };
  let kits: string[];
  try {
    kits = readdirSync(join(sdkFolder, "kits"));
  } catch {
    kits = [];
  }
  for (const kit of kits) {
    add(join(sdkFolder, "kits", kit, "templates"));
    let hosts: string[];
    try {
      hosts = readdirSync(join(sdkFolder, "kits", kit, "hosts"));
    } catch {
      hosts = [];
    }
    hosts.forEach((host) => add(join(sdkFolder, "kits", kit, "hosts", host, "templates")));
  }
  const set = `{${[...names].sort().join(",")}}`;
  return [set, `${set}/**`, `*/${set}`, `*/${set}/**`];
}

// Each folder's kit state (plan R27) from forge's dry runs, cached until something it depends on changes: a watched
// path, a conclave setting, the folder's Python, workspace trust, or a kit operation calling invalidate. A folder's dry
// runs never overlap: computations run one at a time per folder, and one that an invalidation superseded runs again
// before it answers, so no reader gets an answer older than the last change it could see. One onDidChangeKitState
// event follows a burst of changes (an install writes many files).
export class KitStateService implements vscode.Disposable {
  private readonly cache = new Map<string, Promise<KitStates>>();
  private readonly generations = new Map<string, number>();
  private readonly queues = new Map<string, Promise<unknown>>();
  private readonly watchers = new Map<string, { globs: string; disposables: vscode.Disposable[] }>();
  private readonly folders = new Map<string, vscode.Uri>();
  // The Python each folder's state was computed with, as a comparable string.
  private readonly pythons = new Map<string, string>();
  private readonly pending = new Map<string, NodeJS.Timeout>();
  // Each folder's lifetime: a new object when the folder is first read after a forget, so a computation that started
  // before a forget (or a dispose) can tell, and makes no watcher for a folder that has left.
  private readonly lifetimes = new Map<string, object>();
  // The SDK folder each folder's state was last computed from, and one watcher per SDK folder on what forge's answer
  // depends on there (its kits and forge.py itself): a local checkout can change under a cached state.
  private readonly sources = new Map<string, string>();
  private readonly sdkWatchers = new Map<string, vscode.Disposable[]>();
  private disposed = false;
  private readonly changed = new vscode.EventEmitter<vscode.Uri>();
  private readonly subscriptions: vscode.Disposable[] = [];
  readonly onDidChangeKitState = this.changed.event;

  constructor(private readonly deps: KitStateDeps) {
    const all = () => this.folders.forEach((folder) => this.invalidate(folder));
    this.subscriptions.push(
      vscode.workspace.onDidChangeWorkspaceFolders((e) => e.removed.forEach((f) => this.forget(f.uri))),
      vscode.workspace.onDidChangeConfiguration((e) => {
        if (e.affectsConfiguration("conclave")) {
          all();
        }
      }),
      vscode.workspace.onDidGrantWorkspaceTrust(all),
    );
    if (deps.onDidResolvePython) {
      this.subscriptions.push(deps.onDidResolvePython(({ folder, python }) => {
        const now = identity(python);
        for (const [key, known] of this.folders) {
          if ((!folder || folder.toString() === key) && this.pythons.has(key) && this.pythons.get(key) !== now) {
            this.invalidate(known);
          }
        }
      }));
    }
  }

  states(folder: vscode.Uri): Promise<KitStates> {
    const key = folder.toString();
    this.folders.set(key, folder);
    if (!this.lifetimes.has(key)) {
      this.lifetimes.set(key, {});
    }
    let states = this.cache.get(key);
    if (!states) {
      states = this.serial(key, () => this.fresh(folder));
      this.cache.set(key, states);
    }
    return states;
  }

  // A kit operation finished, or something the state depends on changed: the cached state is dropped (and a
  // computation in flight will run again), and one event fires once the changes have settled.
  invalidate(folder: vscode.Uri): void {
    const key = folder.toString();
    this.generations.set(key, (this.generations.get(key) ?? 0) + 1);
    this.cache.delete(key);
    clearTimeout(this.pending.get(key));
    this.pending.set(key, setTimeout(() => {
      this.pending.delete(key);
      this.changed.fire(folder);
    }, SETTLE_MS));
  }

  // A folder that leaves the workspace: its watchers (which hold the folder open on Windows) and cache are dropped.
  forget(folder: vscode.Uri): void {
    const key = folder.toString();
    this.watchers.get(key)?.disposables.forEach((w) => w.dispose());
    this.watchers.delete(key);
    clearTimeout(this.pending.get(key));
    this.pending.delete(key);
    this.cache.delete(key);
    this.folders.delete(key);
    this.pythons.delete(key);
    this.lifetimes.delete(key);
    this.useSdk(key, undefined);
  }

  // How many SDK folders are watched (for tests): one for each SDK folder some known folder was last computed from.
  watchedSdkFolders(): number {
    return this.sdkWatchers.size;
  }

  // Records that the folder (key) now uses sdkFolder (or none), releasing the watchers of the SDK folder it used before
  // when no other folder uses that one.
  private useSdk(key: string, sdkFolder: string | undefined): void {
    const before = this.sources.get(key);
    if (before === sdkFolder) {
      return;
    }
    if (sdkFolder === undefined) {
      this.sources.delete(key);
    } else {
      this.sources.set(key, sdkFolder);
      this.watchSdk(sdkFolder);
    }
    if (before !== undefined && ![...this.sources.values()].includes(before)) {
      this.sdkWatchers.get(before)?.forEach((w) => w.dispose());
      this.sdkWatchers.delete(before);
    }
  }

  private serial<T>(key: string, fn: () => Promise<T>): Promise<T> {
    const next = (this.queues.get(key) ?? Promise.resolve()).then(fn, fn);
    this.queues.set(key, next.catch(() => undefined));
    return next;
  }

  // A computation whose generation moved on while it ran is out of date: it runs again. A folder that changed under
  // every attempt gets no state (never a stale one); the invalidation that superseded the last attempt has an event
  // pending, so a reader is told to read again.
  private async fresh(folder: vscode.Uri): Promise<KitStates> {
    const key = folder.toString();
    const lifetime = this.lifetimes.get(key);
    for (let attempt = 0; attempt < ATTEMPTS; attempt += 1) {
      const generation = this.generations.get(key) ?? 0;
      const states = await this.compute(folder, lifetime);
      if ((this.generations.get(key) ?? 0) === generation) {
        return states;
      }
    }
    return { ok: false, message: "the folder kept changing while its kit state was read; it is read again when it settles" };
  }

  // Whether a computation that started with lifetime may still act for its folder.
  private live(folder: vscode.Uri, lifetime: object | undefined): boolean {
    return !this.disposed && lifetime !== undefined && this.lifetimes.get(folder.toString()) === lifetime;
  }

  private watchSdk(sdkFolder: string): void {
    if (this.sdkWatchers.has(sdkFolder)) {
      return;
    }
    const base = vscode.Uri.file(sdkFolder);
    const watchers = ["kits/**", "forge.py"].map((glob) => vscode.workspace.createFileSystemWatcher(new vscode.RelativePattern(base, glob)));
    const seen = () => {
      for (const [key, sdk] of this.sources) {
        const folder = this.folders.get(key);
        if (sdk === sdkFolder && folder) {
          this.invalidate(folder);
        }
      }
    };
    watchers.forEach((w) => (w.onDidChange(seen), w.onDidCreate(seen), w.onDidDelete(seen)));
    this.sdkWatchers.set(sdkFolder, watchers);
  }

  private watch(folder: vscode.Uri, sdkFolder: string): void {
    const key = folder.toString();
    const globs = watchedGlobs(sdkFolder);
    if (this.watchers.get(key)?.globs === globs.join("|")) {
      return;
    }
    this.watchers.get(key)?.disposables.forEach((w) => w.dispose());
    const disposables = globs.map((glob) => vscode.workspace.createFileSystemWatcher(new vscode.RelativePattern(folder, glob)));
    const seen = () => this.invalidate(folder);
    disposables.forEach((w) => (w.onDidChange(seen), w.onDidCreate(seen), w.onDidDelete(seen)));
    this.watchers.set(key, { globs: globs.join("|"), disposables });
  }

  private async compute(folder: vscode.Uri, lifetime: object | undefined): Promise<KitStates> {
    const left: KitStates = { ok: false, message: "the folder is no longer watched" };
    if (!this.live(folder, lifetime)) {
      return left;
    }
    const source = await this.deps.source(folder);
    if (!("folder" in source)) {
      return { ok: false, message: source.message };
    }
    // The folder may have left while the source was resolved: then nothing is watched for it.
    if (!this.live(folder, lifetime)) {
      return left;
    }
    this.watch(folder, source.folder);
    this.useSdk(folder.toString(), source.folder);
    const python = await this.deps.python(folder);
    this.pythons.set(folder.toString(), identity(python));
    if (!("command" in python)) {
      return { ok: false, message: python.message };
    }
    const options = { run: this.deps.run };
    const kits = await runForge(source, python, ["kits"], parseKits, options);
    if (kits.kind !== "ok") {
      return { ok: false, message: kits.kind === "failed" ? kits.message : "cancelled" };
    }
    const states: KitState[] = [];
    for (const kit of kits.value) {
      const dry = await runForge(source, python, ["kit", folder.fsPath, kit, "--dry-run", "--agent", "all"], parseKit, options);
      states.push(dry.kind === "ok"
        ? kitState(dry.value)
        : { kit, state: "unavailable", reason: dry.kind === "failed" ? refusalReason(dry.stderrTail, dry.message) : "cancelled" });
    }
    return { ok: true, kits: states };
  }

  dispose(): void {
    this.disposed = true;
    this.sdkWatchers.forEach((ws) => ws.forEach((w) => w.dispose()));
    this.subscriptions.forEach((s) => s.dispose());
    this.pending.forEach((t) => clearTimeout(t));
    this.watchers.forEach((w) => w.disposables.forEach((d) => d.dispose()));
    this.changed.dispose();
  }
}
