import { join } from "node:path";
import { forgeOutcome, type ForgeOutcome, parseCheck, parseDoctor, parseKit, parseKits, parseProvision, type Parsed } from "../core/forgeJson";
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

// The parser for each command the extension runs; a command not listed here is refused before anything runs.
export const FORGE_PARSERS: Record<string, (raw: string) => Parsed<unknown>> = {
  kits: parseKits,
  kit: parseKit,
  init: (raw) => parseProvision("init", raw),
  sync: (raw) => parseProvision("sync", raw),
  check: parseCheck,
  doctor: parseDoctor,
};

function shown(arg: string): string {
  return /[\s"]/.test(arg) ? JSON.stringify(arg) : arg;
}

// The one way the extension runs forge.py: the resolved Python in isolated mode (-I: no PYTHON* variables and no
// working-directory module in front of forge's imports), an argument array with no shell, the SDK folder as the working
// directory, a timeout and a cancel that end the whole process tree. Every run is logged with its argv, folder, source
// label, exit and duration.
export async function runForge<T>(source: ForgeSource, python: Python, args: string[], parse: (raw: string) => Parsed<T>,
  options: ForgeOptions = {}): Promise<ForgeOutcome<T>> {
  const argv = [...python.prefix, "-I", join(source.folder, "forge.py"), ...args];
  const started = Date.now();
  const result = await (options.run ?? run)(python.command, argv, options.timeoutMs ?? FORGE_TIMEOUT_MS, source.folder,
    { signal: options.signal, tree: true });
  const ended = result.code !== undefined ? `exit ${result.code}` : (result.error ?? "did not start");
  log(`forge: ${[python.command, ...argv].map(shown).join(" ")} in ${source.folder} (${source.label}): ${ended} in ${Date.now() - started} ms`);
  return forgeOutcome(args[0] ?? "", result, parse);
}
