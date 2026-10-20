// One dispatcher process per workspace folder at a time. A request identical to one already waiting or running gets
// that request's answer; a different one waits its turn. Pure scheduling, unit-tested with controlled promises.

export class FolderQueue<T> {
  private readonly tails = new Map<string, Promise<unknown>>();
  private readonly pending = new Map<string, Promise<T>>();

  run(folder: string, key: string, task: () => Promise<T>): Promise<T> {
    const id = `${folder}\n${key}`;
    const known = this.pending.get(id);
    if (known) {
      return known;
    }
    const before = this.tails.get(folder) ?? Promise.resolve();
    const call = before.catch(() => undefined).then(task);
    const settled = call.catch(() => undefined).finally(() => {
      if (this.pending.get(id) === call) {
        this.pending.delete(id);
      }
      if (this.tails.get(folder) === settled) {
        this.tails.delete(folder);
      }
    });
    this.tails.set(folder, settled);
    this.pending.set(id, call);
    return call;
  }
}
