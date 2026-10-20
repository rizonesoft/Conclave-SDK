import { join } from "node:path";
import { forgeOutcome, type ForgeOutcome, parseCheck, parseDigest, parseDoctor, parseKit, parseKits, type Parsed } from "../core/forgeJson";
import type { Python } from "../core/python";
import { log } from "./output";
import { run } from "./run";

export const FORGE_TIMEOUT_MS = 120_000;

// Where forge.py comes from (D02 T01 §7): its folder, which is also the working directory, and the label every
// confirmation and log line names.
export interface ForgeSource {
  folder: string;
  label: string;
}

export interface ForgeOptions {
  signal?: AbortSignal;
  timeoutMs?: number;
  run?: typeof run;
}

// The parser for each command the extension runs; a command not listed here is refused before anything runs. A Map,
// so a name like "__proto__" or "toString" is not a command, never a lookup of Object's own members. Every one only
// reads: the extension never installs, updates or sets up a repository (design/decisions.md, read-only kit view).
export const FORGE_PARSERS = new Map<string, (raw: string) => Parsed<unknown>>([
  ["kits", parseKits],
  ["kit", parseKit],
  ["check", parseCheck],
  ["doctor", parseDoctor],
  ["digest", parseDigest],
]);

// Why args are not a read-only forge run, or undefined: a command outside FORGE_PARSERS, `kit` without --dry-run,
// which would install, or a `--`, after which argparse reads --dry-run as a folder name and installs into it.
export function notReadOnly(args: string[]): string | undefined {
  const command = args[0] ?? "";
  if (!FORGE_PARSERS.has(command)) {
    return `forge ${command} is not a command the extension runs`;
  }
  if (args.includes("--")) {
    return "forge arguments never include --: after it --dry-run would be read as a folder";
  }
  if (command === "kit" && !args.includes("--dry-run")) {
    return "forge kit runs only with --dry-run: the extension never installs a kit";
  }
  return undefined;
}

function shown(arg: string): string {
  return /[\s"]/.test(arg) ? JSON.stringify(arg) : arg;
}

// The one way the extension runs forge.py: the resolved Python in isolated mode (-I: no PYTHON* variables and no
// working-directory module in front of forge's imports), an argument array with no shell, the SDK folder as the working
// directory, a timeout and a cancel that end the whole process tree. Every run is logged with its argv, folder, source
// label, exit and duration.
export async function runForge<T>(source: ForgeSource, python: Python, args: string[], parse: (raw: string) => Parsed<T>,
  options: ForgeOptions = {}): Promise<ForgeOutcome<T>> {
  const refused = notReadOnly(args);
  if (refused) {
    log(`forge: refused ${args.map(shown).join(" ")}: ${refused}`);
    return { kind: "failed", message: refused, stderrTail: [] };
  }
  const argv = [...python.prefix, "-I", join(source.folder, "forge.py"), ...args];
  const started = Date.now();
  const result = await (options.run ?? run)(python.command, argv, options.timeoutMs ?? FORGE_TIMEOUT_MS, source.folder,
    { signal: options.signal, tree: true });
  const ended = result.code !== undefined ? `exit ${result.code}` : (result.error ?? "did not start");
  log(`forge: ${[python.command, ...argv].map(shown).join(" ")} in ${source.folder} (${source.label}): ${ended} in ${Date.now() - started} ms`);
  return forgeOutcome(args[0] ?? "", result, parse);
}
