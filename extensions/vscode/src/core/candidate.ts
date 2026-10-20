// Checking every edit's candidate text through the dispatcher (plan R7, R8; design spec section 1): debounced, newest
// edit wins, and Save on only while the newest candidate is valid and differs from disk. Pure over injected timers and
// an injected check, so the sequencing is unit-tested with fake timers.

import type { WorkspaceState } from "./checkPin";

export const DEBOUNCE_MS = 300;

export interface Timers {
  set: (fn: () => void, ms: number) => unknown;
  clear: (handle: unknown) => void;
}

export interface Checked {
  text: string;
  state: WorkspaceState;
}

// Save is on only when the newest candidate is valid and is not what is already on disk.
export function canSave(latest: Checked | undefined, current: string, disk: string): boolean {
  return latest !== undefined && latest.text === current && latest.state.state === "ready" && current !== disk;
}

export class CandidateFlow {
  private generation = 0;
  private timer: unknown;
  private latest: Checked | undefined;

  constructor(
    private readonly check: (text: string) => Promise<WorkspaceState>,
    private readonly onResult: (checked: Checked) => void,
    private readonly timers: Timers,
    private readonly delay = DEBOUNCE_MS,
  ) {}

  // A new edit: the pending check is replaced, and any result for an older edit is discarded when it arrives.
  edit(text: string): void {
    const mine = ++this.generation;
    if (this.timer !== undefined) {
      this.timers.clear(this.timer);
    }
    this.timer = this.timers.set(() => {
      this.timer = undefined;
      void this.check(text).then((state) => {
        if (mine === this.generation) {
          this.latest = { text, state };
          this.onResult(this.latest);
        }
      }, () => undefined);
    }, this.delay);
  }

  result(): Checked | undefined {
    return this.latest;
  }
}
