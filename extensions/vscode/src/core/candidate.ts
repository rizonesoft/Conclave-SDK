// Checking every edit's candidate text through the dispatcher (plan R7, R8; design spec section 1): debounced, newest
// edit wins, and Save on only while the newest edit's own check found it valid and it differs from disk. Pure over
// injected timers and an injected check, so the sequencing is unit-tested with fake timers.
//
// One check runs at a time and at most one waits: a newer edit replaces the waiting one, so obsolete checks never pile
// up behind a slow dispatcher, and the result of a check for an older edit is never applied. A running check is not
// killed (the dispatcher's 30 s timeout bounds it); its answer is simply discarded.

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

// Save is on only when the newest edit has its own check (settled), that check found the text valid, and the text is
// not what is already on disk.
export function canSave(latest: Checked | undefined, current: string, disk: string, settled: boolean): boolean {
  return settled && latest !== undefined && latest.text === current && latest.state.state === "ready" && current !== disk;
}

export class CandidateFlow {
  private generation = 0;
  private applied = 0;
  private timer: unknown;
  private latest: Checked | undefined;
  private running = false;
  private waiting: { generation: number; text: string } | undefined;

  constructor(
    private readonly check: (text: string) => Promise<WorkspaceState>,
    private readonly onResult: (checked: Checked) => void,
    private readonly timers: Timers,
    private readonly delay = DEBOUNCE_MS,
  ) {}

  // A new edit: the pending check is replaced, and any result for an older edit is discarded when it arrives.
  edit(text: string): void {
    const generation = ++this.generation;
    if (this.timer !== undefined) {
      this.timers.clear(this.timer);
    }
    this.timer = this.timers.set(() => {
      this.timer = undefined;
      this.waiting = { generation, text };
      this.next();
    }, this.delay);
  }

  private next(): void {
    if (this.running || !this.waiting) {
      return;
    }
    const { generation, text } = this.waiting;
    this.waiting = undefined;
    this.running = true;
    const done = () => {
      this.running = false;
      this.next();
    };
    void this.check(text).then((state) => {
      if (generation === this.generation) {
        this.latest = { text, state };
        this.applied = generation;
        this.onResult(this.latest);
      }
      done();
    }, done);
  }

  // The newest completed check, for showing its errors while later edits are checked.
  result(): Checked | undefined {
    return this.latest;
  }

  // True when the newest edit's own check has completed.
  settled(): boolean {
    return this.applied === this.generation && this.generation > 0;
  }
}
