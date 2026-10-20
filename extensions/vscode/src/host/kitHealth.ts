import * as vscode from "vscode";
import { type DoctorResult, parseCheck, parseDoctor } from "../core/forgeJson";
import { type FolderHealth, healthFrom } from "../core/kitHealth";
import { refusalReason } from "../core/kitState";
import type { Python } from "../core/python";
import type { ForgeSource } from "./forge";
import { runForge } from "./forge";
import type { KitStates } from "./kitState";
import { FolderWork } from "./folderWork";
import type { run } from "./run";

export type KitHealthResult = ({ ok: true } & FolderHealth) | { ok: false; message: string };

export interface KitHealthDeps {
  // Each kit's state (D02 T01 §10): health is read for the kits installed or partly installed.
  kitStates: (folder: vscode.Uri) => Promise<KitStates>;
  onDidChangeKitState: vscode.Event<vscode.Uri>;
  // The kit state's folder lifetime: a folder it forgets is forgotten here too.
  onDidForget?: vscode.Event<vscode.Uri>;
  source: (folder: vscode.Uri) => Promise<ForgeSource | { message: string }>;
  python: (folder: vscode.Uri) => Promise<Python | { message: string }>;
  run?: typeof run;
  // Each doctor's timeout: 30 s; tests pass a short one.
  doctorTimeoutMs?: number;
}

const DOCTOR_TIMEOUT_MS = 30_000;
const LEFT = "the folder is no longer watched";
const UNSETTLED = "the folder kept changing while its kit health was read; it is read again when it settles";

// Each folder's kit health (plan R30), only from forge: `forge.py check` once, then `forge.py doctor <folder> <kit>`
// for each kit installed or partly installed, one process at a time per folder, each with a timeout (a doctor that
// does not answer makes that kit unavailable, not the folder). Cached until the folder's kit state changes (an install
// or update, D05 T01 §1 and §2, changes it) or refresh is asked; a computation that a change superseded runs again.
export class KitHealthService implements vscode.Disposable {
  private readonly work = new FolderWork<KitHealthResult>((folder, alive) => this.compute(folder, alive),
    (why) => ({ ok: false, message: why === "left" ? LEFT : UNSETTLED }));
  private readonly changed = new vscode.EventEmitter<vscode.Uri>();
  private readonly subscriptions: vscode.Disposable[] = [];
  readonly onDidChangeKitHealth = this.changed.event;

  constructor(private readonly deps: KitHealthDeps) {
    this.subscriptions.push(deps.onDidChangeKitState((folder) => this.refresh(folder)));
    if (deps.onDidForget) {
      this.subscriptions.push(deps.onDidForget((folder) => this.forget(folder)));
    }
  }

  health(folder: vscode.Uri): Promise<KitHealthResult> {
    return this.work.read(folder);
  }

  // On demand, and after every change to the folder's kit state: the cached health is dropped and readers are told.
  refresh(folder: vscode.Uri): void {
    this.work.invalidate(folder);
    this.changed.fire(folder);
  }

  // A folder that left: its cached health is dropped, and its computations start nothing more (FolderWork).
  forget(folder: vscode.Uri): void {
    this.work.forget(folder);
  }

  // alive() is checked before every forge process: a folder that left starts nothing more.
  private async compute(folder: vscode.Uri, alive: () => boolean): Promise<KitHealthResult> {
    const left: KitHealthResult = { ok: false, message: LEFT };
    const states = await this.deps.kitStates(folder);
    if (!states.ok) {
      return { ok: false, message: states.message };
    }
    const source = await this.deps.source(folder);
    if (!("folder" in source)) {
      return { ok: false, message: source.message };
    }
    const python = await this.deps.python(folder);
    if (!("command" in python)) {
      return { ok: false, message: python.message };
    }
    if (!alive()) {
      return left;
    }
    const check = await runForge(source, python, ["check", folder.fsPath], parseCheck, { run: this.deps.run });
    if (check.kind !== "ok") {
      return { ok: false, message: check.kind === "failed" ? check.message : "cancelled" };
    }
    const doctors: (DoctorResult | { kit: string; reason: string })[] = [];
    for (const state of states.kits.filter((k) => k.state === "installed" || k.state === "partly")) {
      if (!alive()) {
        return left;
      }
      const doctor = await runForge(source, python, ["doctor", folder.fsPath, state.kit], parseDoctor,
        { run: this.deps.run, timeoutMs: this.deps.doctorTimeoutMs ?? DOCTOR_TIMEOUT_MS });
      doctors.push(doctor.kind === "ok"
        ? doctor.value
        : { kit: state.kit, reason: doctor.kind === "failed" ? refusalReason(doctor.stderrTail, doctor.message) : "cancelled" });
    }
    return { ok: true, ...healthFrom(check.value, doctors) };
  }

  dispose(): void {
    this.work.dispose();
    this.subscriptions.forEach((s) => s.dispose());
    this.changed.dispose();
  }
}
