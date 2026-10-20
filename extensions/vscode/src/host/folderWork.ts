import type * as vscode from "vscode";

// Why a read gave no answer: the folder left (forget or dispose), or it kept changing under every attempt.
export type Unanswered = "left" | "unsettled";

const ATTEMPTS = 5;

// One folder computation at a time per folder, cached until invalidated, bound to the folder's lifetime as it was when
// the read was asked (D02 T01 §19). The kit state and the kit health both run on it, so their rules cannot drift.
//
// A read captures the folder's lifetime when it is asked: a forget ends that lifetime, so a read asked before the forget
// answers "left", even if it only runs after the folder was read again under a new lifetime. The computation is given
// alive(), which it checks before every process it starts, so a forgotten folder's computation starts nothing more.
// An invalidation bumps the generation: a computation that it superseded runs again, at most ATTEMPTS times, then
// answers "unsettled" rather than with a state from before the last change.
export class FolderWork<T> {
  private readonly cache = new Map<string, Promise<T>>();
  private readonly generations = new Map<string, number>();
  private readonly lifetimes = new Map<string, object>();
  private readonly queues = new Map<string, Promise<unknown>>();
  private disposed = false;

  constructor(
    private readonly compute: (folder: vscode.Uri, alive: () => boolean) => Promise<T>,
    private readonly unanswered: (why: Unanswered) => T,
  ) {}

  read(folder: vscode.Uri): Promise<T> {
    const key = folder.toString();
    let lifetime = this.lifetimes.get(key);
    if (!lifetime) {
      lifetime = {};
      this.lifetimes.set(key, lifetime);
    }
    let answer = this.cache.get(key);
    if (!answer) {
      const asked = lifetime;
      answer = this.serial(key, () => this.fresh(folder, asked));
      this.cache.set(key, answer);
    }
    return answer;
  }

  // Something the answer depends on changed: the cached answer is dropped and a computation in flight runs again.
  invalidate(folder: vscode.Uri): void {
    const key = folder.toString();
    this.generations.set(key, (this.generations.get(key) ?? 0) + 1);
    this.cache.delete(key);
  }

  // The folder left: its lifetime ends, so every read asked until now answers "left" and starts nothing more.
  forget(folder: vscode.Uri): void {
    const key = folder.toString();
    this.lifetimes.delete(key);
    this.cache.delete(key);
  }

  // Whether a computation for folder, asked in lifetime, may still act.
  alive(folder: vscode.Uri, lifetime: object): boolean {
    return !this.disposed && this.lifetimes.get(folder.toString()) === lifetime;
  }

  dispose(): void {
    this.disposed = true;
    this.lifetimes.clear();
    this.cache.clear();
  }

  private serial(key: string, fn: () => Promise<T>): Promise<T> {
    const next = (this.queues.get(key) ?? Promise.resolve()).then(fn, fn);
    this.queues.set(key, next.catch(() => undefined));
    return next;
  }

  private async fresh(folder: vscode.Uri, lifetime: object): Promise<T> {
    const key = folder.toString();
    const alive = () => this.alive(folder, lifetime);
    for (let attempt = 0; attempt < ATTEMPTS; attempt += 1) {
      if (!alive()) {
        return this.unanswered("left");
      }
      const generation = this.generations.get(key) ?? 0;
      const answer = await this.compute(folder, alive);
      if (!alive()) {
        return this.unanswered("left");
      }
      if ((this.generations.get(key) ?? 0) === generation) {
        return answer;
      }
    }
    return this.unanswered("unsettled");
  }
}
