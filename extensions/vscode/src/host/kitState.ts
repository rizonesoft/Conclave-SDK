import * as vscode from "vscode";
import { parseKit, parseKits } from "../core/forgeJson";
import { kitState, type KitState, refusalReason } from "../core/kitState";
import type { Python } from "../core/python";
import type { ForgeSource } from "./forge";
import { runForge } from "./forge";

export type KitStates = { ok: true; kits: KitState[] } | { ok: false; message: string };

export interface KitStateDeps {
  // Where forge.py comes from for this folder (D02 T01 §7), or why there is none.
  source: (folder: vscode.Uri) => Promise<ForgeSource | { message: string }>;
  python: (folder: vscode.Uri) => Promise<Python | { message: string }>;
}

// What a folder's kit state depends on: the agents' folders, the pin, the kits' scripts, todo and docs (each kit
// installs there), and the agent documents at the root that the base kit writes.
const WATCHED = ["{.agents,.claude,.codex,.conclave,scripts,todo,docs}/**", "{AGENTS,CLAUDE,GEMINI,CODEX}.md"];
const SETTLE_MS = 300;

// Each folder's kit state (plan R27) from forge's dry runs, one at a time per folder, cached until a watched path
// changes or a kit operation calls invalidate. One onDidChangeKitState event follows a burst of changes (an install
// writes many files), so the Kits view and the reviewer editor read the state again once.
export class KitStateService implements vscode.Disposable {
  private readonly cache = new Map<string, Promise<KitStates>>();
  private readonly watchers = new Map<string, vscode.Disposable[]>();
  private readonly pending = new Map<string, NodeJS.Timeout>();
  private readonly changed = new vscode.EventEmitter<vscode.Uri>();
  readonly onDidChangeKitState = this.changed.event;

  private readonly folders: vscode.Disposable;

  constructor(private readonly deps: KitStateDeps) {
    this.folders = vscode.workspace.onDidChangeWorkspaceFolders((e) => e.removed.forEach((f) => this.forget(f.uri)));
  }

  // A folder that leaves the workspace: its watchers (which hold the folder open on Windows) and cache are dropped.
  forget(folder: vscode.Uri): void {
    const key = folder.toString();
    this.watchers.get(key)?.forEach((w) => w.dispose());
    this.watchers.delete(key);
    clearTimeout(this.pending.get(key));
    this.pending.delete(key);
    this.cache.delete(key);
  }

  states(folder: vscode.Uri): Promise<KitStates> {
    const key = folder.toString();
    this.watch(folder);
    let states = this.cache.get(key);
    if (!states) {
      states = this.compute(folder);
      this.cache.set(key, states);
    }
    return states;
  }

  // A kit operation finished, or a watched path changed: the cached state is dropped, and one event fires once the
  // changes have settled.
  invalidate(folder: vscode.Uri): void {
    const key = folder.toString();
    this.cache.delete(key);
    clearTimeout(this.pending.get(key));
    this.pending.set(key, setTimeout(() => {
      this.pending.delete(key);
      this.cache.delete(key);
      this.changed.fire(folder);
    }, SETTLE_MS));
  }

  private watch(folder: vscode.Uri): void {
    const key = folder.toString();
    if (this.watchers.has(key)) {
      return;
    }
    const watchers = WATCHED.map((glob) => vscode.workspace.createFileSystemWatcher(new vscode.RelativePattern(folder, glob)));
    const seen = () => this.invalidate(folder);
    watchers.forEach((w) => (w.onDidChange(seen), w.onDidCreate(seen), w.onDidDelete(seen)));
    this.watchers.set(key, watchers);
  }

  private async compute(folder: vscode.Uri): Promise<KitStates> {
    const source = await this.deps.source(folder);
    if (!("folder" in source)) {
      return { ok: false, message: source.message };
    }
    const python = await this.deps.python(folder);
    if (!("command" in python)) {
      return { ok: false, message: python.message };
    }
    const kits = await runForge(source, python, ["kits"], parseKits);
    if (kits.kind !== "ok") {
      return { ok: false, message: kits.kind === "failed" ? kits.message : "cancelled" };
    }
    const states: KitState[] = [];
    for (const kit of kits.value) {
      const dry = await runForge(source, python, ["kit", folder.fsPath, kit, "--dry-run", "--agent", "all"], parseKit);
      states.push(dry.kind === "ok"
        ? kitState(dry.value)
        : { kit, state: "unavailable", reason: dry.kind === "failed" ? refusalReason(dry.stderrTail, dry.message) : "cancelled" });
    }
    return { ok: true, kits: states };
  }

  dispose(): void {
    this.folders.dispose();
    this.pending.forEach((t) => clearTimeout(t));
    this.watchers.forEach((ws) => ws.forEach((w) => w.dispose()));
    this.changed.dispose();
  }
}
