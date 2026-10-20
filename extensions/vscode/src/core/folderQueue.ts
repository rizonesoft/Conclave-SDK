// One dispatcher process per workspace folder at a time. A request identical to one still waiting shares that request's
// answer; once a request has started, an identical one queues a fresh run behind it, so an answer never predates the
// request (a pin saved while a check runs is read by the next check). A different request waits its turn. Pure
// scheduling, unit-tested with controlled promises.

export interface Queued<T> {
  promise: Promise<T>;
  // True when this call queued a new run; false when it joined one already waiting.
  created: boolean;
}

export class FolderQueue<T> {
  private readonly tails = new Map<string, Promise<unknown>>();
  private readonly waiting = new Map<string, Promise<T>>();

  run(folder: string, key: string, task: () => Promise<T>): Queued<T> {
    const id = `${folder}\n${key}`;
    const known = this.waiting.get(id);
    if (known) {
      return { promise: known, created: false };
    }
    const before = this.tails.get(folder) ?? Promise.resolve();
    const call: Promise<T> = before.catch(() => undefined).then(() => {
      if (this.waiting.get(id) === call) {
        this.waiting.delete(id);
      }
      return task();
    });
    const settled = call.catch(() => undefined).finally(() => {
      if (this.tails.get(folder) === settled) {
        this.tails.delete(folder);
      }
    });
    this.tails.set(folder, settled);
    this.waiting.set(id, call);
    return { promise: call, created: true };
  }
}
