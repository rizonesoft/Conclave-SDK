import { existsSync, realpathSync } from "node:fs";
import { basename, dirname, isAbsolute, join, resolve, sep } from "node:path";
import * as vscode from "vscode";
import { type KitResult, parseProvision } from "../core/forgeJson";
import type { Python } from "../core/python";
import { protectedChanges } from "../core/protectedFiles";
import { ENTRY_DOCS, type InitChoice, initArgs, refuseTarget } from "../core/repoInit";
import type { ForgeSource } from "./forge";
import { runForge } from "./forge";
import { log } from "./output";
import { protectedSnapshot } from "./protectedFiles";
import type { run } from "./run";

export type OpenChoice = "window" | "workspace" | "none";

export interface RepoInitDeps {
  source: () => Promise<ForgeSource | { message: string }>;
  python: () => Promise<Python | { message: string }>;
  run?: typeof run;
  // How the folder is opened; tests pass their own instead of opening a new window.
  openFolder?: (folder: vscode.Uri) => Thenable<unknown>;
  addToWorkspace?: (folder: vscode.Uri) => boolean;
}

export type RepoInitResult =
  | { ok: true; folder: string; written: string[]; skipped: string[]; kits: KitResult[]; kept: string[] }
  | { ok: false; message: string };

// The entry docs a folder already has, which init keeps (it is never run with --force): what the dialog says before
// the operator confirms.
export function existingEntryDocs(folder: string): string[] {
  return ENTRY_DOCS.filter((doc) => existsSync(join(folder, doc)));
}

// A path as the file system will see it: the nearest existing ancestor with its links and junctions resolved (forge
// resolves the target the same way), followed by the parts that do not exist yet.
function canonical(path: string): string {
  const rest: string[] = [];
  let at = path;
  for (;;) {
    try {
      return join(realpathSync.native(at), ...rest.reverse());
    } catch {
      const parent = dirname(at);
      if (parent === at) {
        return path;
      }
      rest.push(basename(at));
      at = parent;
    }
  }
}

// Sets up a repository with `forge.py init` (plan R31), from the folder, agent, mode and kits chosen (base always comes
// with init), then opens it in a new window, adds it to the workspace, or leaves it, as chosen. forge creates the
// folder if it does not exist. The folder must be an absolute path (a relative one would depend on the extension
// host's working directory). A folder inside a .git folder or the SDK source folder itself is refused before anything
// runs, by its path as written and by its real path, so a link or junction cannot lead there. Afterwards the protected
// files (plan R32) are proved unchanged by hash unless forge reported writing them.
//
// Adding the folder to the workspace: when the window has one folder (or none), VS Code turns it into a multi-root
// workspace and restarts every extension host, this one included, so the result may not reach the caller then.
export async function setUpRepository(choice: InitChoice, open: OpenChoice, deps: RepoInitDeps): Promise<RepoInitResult> {
  if (!isAbsolute(choice.folder)) {
    return { ok: false, message: `The folder must be an absolute path, not ${JSON.stringify(choice.folder)}.` };
  }
  const folder = resolve(choice.folder);
  const source = await deps.source();
  if (!("folder" in source)) {
    return { ok: false, message: source.message };
  }
  const target = { resolve, sep, caseInsensitive: process.platform === "win32" };
  const refused = refuseTarget(folder, source.folder, target) ?? refuseTarget(canonical(folder), canonical(source.folder), target);
  if (refused) {
    return { ok: false, message: `${refused}, so it was not set up.` };
  }
  let args: string[];
  try {
    args = initArgs({ ...choice, folder });
  } catch (error) {
    return { ok: false, message: String((error as Error).message) };
  }
  const python = await deps.python();
  if (!("command" in python)) {
    return { ok: false, message: python.message };
  }
  const kept = existingEntryDocs(folder);
  const before = protectedSnapshot(folder);
  const outcome = await runForge(source, python, args, (raw) => parseProvision("init", raw), { run: deps.run });
  if (outcome.kind !== "ok") {
    return { ok: false, message: outcome.kind === "failed" ? [outcome.message, ...outcome.stderrTail].join("\n") : "cancelled" };
  }
  const changed = protectedChanges(before, protectedSnapshot(folder), outcome.value.written);
  if (changed.length) {
    log(`forge init changed protected files it did not report writing in ${folder}: ${changed.join(", ")}.`);
    return { ok: false, message: `forge init changed protected files it did not report writing: ${changed.join(", ")}. Check them with git.` };
  }
  const uri = vscode.Uri.file(folder);
  if (open === "window") {
    await (deps.openFolder ?? ((u) => vscode.commands.executeCommand("vscode.openFolder", u, { forceNewWindow: true })))(uri);
  } else if (open === "workspace") {
    const added = (deps.addToWorkspace ?? ((u) => vscode.workspace.updateWorkspaceFolders(vscode.workspace.workspaceFolders?.length ?? 0, 0, { uri: u })))(uri);
    if (!added) {
      log(`Set up ${folder}, but it could not be added to the workspace.`);
    }
  }
  log(`Set up ${folder} with forge init: ${outcome.value.written.length} written, ${outcome.value.skipped.length} kept (${source.label}).`);
  return { ok: true, folder, written: outcome.value.written, skipped: outcome.value.skipped, kits: outcome.value.kits, kept };
}
