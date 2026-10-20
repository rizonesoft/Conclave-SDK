import type { KitResult } from "./forgeJson";

// A kit's state in one folder (plan R27), read from forge's own dry run (`forge.py kit <folder> <kit> --dry-run --agent
// all`): a file forge would add is missing, a file it would keep (or update on a refresh) is there. The state is
// relative to all three agents' folders, so a repository provisioned for one agent is partly installed and says why.
export type KitState =
  | { kit: string; state: "installed"; kept: number }
  | { kit: string; state: "partly"; add: number; kept: number; reason: string }
  | { kit: string; state: "not-installed"; add: number }
  // forge refused the dry run (the laravel kit outside a Laravel app): its own reason.
  | { kit: string; state: "unavailable"; reason: string };

const SHOWN = 5;

export function kitState(dry: KitResult): KitState {
  const kept = dry.preserved.length + dry.updated.length;
  const add = dry.installed.length;
  if (add === 0) {
    return { kit: dry.kit, state: "installed", kept };
  }
  if (kept === 0) {
    return { kit: dry.kit, state: "not-installed", add };
  }
  // Where the missing files are, by top folder (a repository set up for one agent lacks the others' folders), then the
  // first few by name.
  const folders = new Map<string, number>();
  for (const path of dry.installed) {
    const top = path.includes("/") ? `${path.slice(0, path.indexOf("/"))}/` : path;
    folders.set(top, (folders.get(top) ?? 0) + 1);
  }
  // A file at the root is named as it is; a folder says how many of its files are missing.
  const where = [...folders].map(([top, n]) => (top.endsWith("/") ? `${n} in ${top}` : top)).join(", ");
  const first = dry.installed.slice(0, SHOWN).join(", ");
  const more = add > SHOWN ? `, and ${add - SHOWN} more` : "";
  return {
    kit: dry.kit,
    state: "partly",
    add,
    kept,
    reason: `${add} of ${add + kept} files are missing (${where}): ${first}${more}`,
  };
}

// forge's refusal line without its "forge.py: error: " prefix, from the end of its stderr.
export function refusalReason(stderrTail: string[], fallback: string): string {
  const line = [...stderrTail].reverse().find((l) => l.trim() !== "");
  return line ? line.replace(/^forge\.py: error: /, "") : fallback;
}
