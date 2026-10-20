import type { RunResult } from "./python";

// forge.py's JSON answers, typed, with every list kept verbatim (the shapes recorded in test/fixtures/forge/ by
// scripts/record-forge-fixtures.py). A shape the parser does not know is refused with the raw text, never guessed.

export interface KitResult {
  target: string;
  kit: string;
  agent: string;
  dryRun: boolean;
  installed: string[];
  updated: string[];
  preserved: string[];
  mergeNeeded: string[];
}

export interface ProvisionResult {
  target: string;
  mode: string;
  agent: string;
  written: string[];
  skipped: string[];
  kits: KitResult[];
}

export interface CheckResult {
  target: string;
  // Every has_* flag forge reports, by its own name.
  flags: Record<string, boolean>;
  agySkills: string[];
  claudeSkills: string[];
  codexSkills: string[];
  claudeAgents: string[];
}

export interface DoctorCheck {
  name: string;
  status: string;
  detail: string;
}

export interface DoctorResult {
  target: string;
  kit: string;
  missingOrSetupRequired: number;
  checks: DoctorCheck[];
}

export type Parsed<T> = { ok: true; value: T } | { ok: false; message: string; raw: string };

class Shape extends Error {}

type Json = Record<string, unknown>;

function object(value: unknown, where: string): Json {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Shape(`${where} is not an object`);
  }
  return value as Json;
}

function text(o: Json, key: string, where: string): string {
  if (typeof o[key] !== "string") {
    throw new Shape(`${where}: "${key}" is missing or not text`);
  }
  return o[key] as string;
}

function flag(o: Json, key: string, where: string): boolean {
  if (typeof o[key] !== "boolean") {
    throw new Shape(`${where}: "${key}" is missing or not true or false`);
  }
  return o[key] as boolean;
}

function count(o: Json, key: string, where: string): number {
  if (!Number.isInteger(o[key])) {
    throw new Shape(`${where}: "${key}" is missing or not a whole number`);
  }
  return o[key] as number;
}

function texts(o: Json, key: string, where: string): string[] {
  const value = o[key];
  if (!Array.isArray(value) || !value.every((v) => typeof v === "string")) {
    throw new Shape(`${where}: "${key}" is missing or not a list of text`);
  }
  return [...value] as string[];
}

function parse<T>(command: string, raw: string, read: (o: Json) => T): Parsed<T> {
  let json: unknown;
  try {
    json = JSON.parse(raw);
  } catch {
    return { ok: false, message: `forge ${command} printed no JSON`, raw };
  }
  try {
    return { ok: true, value: read(object(json, `forge ${command}`)) };
  } catch (error) {
    if (error instanceof Shape) {
      return { ok: false, message: error.message, raw };
    }
    throw error;
  }
}

function kitResult(o: Json, where: string): KitResult {
  return {
    target: text(o, "target", where),
    kit: text(o, "kit", where),
    agent: text(o, "agent", where),
    dryRun: flag(o, "dry_run", where),
    installed: texts(o, "installed", where),
    updated: texts(o, "updated", where),
    preserved: texts(o, "preserved", where),
    mergeNeeded: texts(o, "merge_needed", where),
  };
}

export function parseKits(raw: string): Parsed<string[]> {
  return parse("kits", raw, (o) => texts(o, "kits", "forge kits"));
}

export function parseKit(raw: string): Parsed<KitResult> {
  return parse("kit", raw, (o) => kitResult(o, "forge kit"));
}

// init and sync answer alike: the files written and skipped, and one kit result per kit applied.
export function parseProvision(command: "init" | "sync", raw: string): Parsed<ProvisionResult> {
  return parse(command, raw, (o) => {
    const where = `forge ${command}`;
    const kits = o.kits;
    if (!Array.isArray(kits)) {
      throw new Shape(`${where}: "kits" is missing or not a list`);
    }
    return {
      target: text(o, "target", where),
      mode: text(o, "mode", where),
      agent: text(o, "agent", where),
      written: texts(o, "written", where),
      skipped: texts(o, "skipped", where),
      kits: kits.map((k, i) => kitResult(object(k, `${where}: kits[${i}]`), `${where}: kits[${i}]`)),
    };
  });
}

// forge.py's check_repo writes these every time.
export const CHECK_FLAGS = ["has_agents_md", "has_gemini_md", "has_claude_md", "has_codex_md", "has_agy_skills_json",
  "has_agy_plugins_json", "has_todo_graph", "has_verify_agent_tiers"] as const;

export function parseCheck(raw: string): Parsed<CheckResult> {
  return parse("check", raw, (o) => {
    const where = "forge check";
    const flags: Record<string, boolean> = {};
    // The flags check_repo always writes are required; any further has_* flag a newer forge adds is kept too.
    for (const key of new Set([...CHECK_FLAGS, ...Object.keys(o).filter((k) => k.startsWith("has_"))])) {
      flags[key] = flag(o, key, where);
    }
    return {
      target: text(o, "target", where),
      flags,
      agySkills: texts(o, "agy_skills", where),
      claudeSkills: texts(o, "claude_skills", where),
      codexSkills: texts(o, "codex_skills", where),
      claudeAgents: texts(o, "claude_agents", where),
    };
  });
}

export function parseDoctor(raw: string): Parsed<DoctorResult> {
  return parse("doctor", raw, (o) => {
    const where = "forge doctor";
    const checks = o.checks;
    if (!Array.isArray(checks)) {
      throw new Shape(`${where}: "checks" is missing or not a list`);
    }
    return {
      target: text(o, "target", where),
      kit: text(o, "kit", where),
      missingOrSetupRequired: count(o, "missing_or_setup_required", where),
      checks: checks.map((c, i) => {
        const check = object(c, `${where}: checks[${i}]`);
        const at = `${where}: checks[${i}]`;
        return { name: text(check, "name", at), status: text(check, "status", at), detail: text(check, "detail", at) };
      }),
    };
  });
}

// What one forge run came to: its parsed answer, a failure (with the last 20 lines of stderr), or a cancel.
export type ForgeOutcome<T> =
  | { kind: "ok"; value: T }
  | { kind: "failed"; message: string; stderrTail: string[]; raw?: string }
  | { kind: "cancelled"; note?: string };

const TAIL = 20;

function tail(stderr: string | undefined): string[] {
  return (stderr ?? "").replace(/\s+$/, "").split(/\r?\n/).filter((l, i, all) => l !== "" || i < all.length - 1).slice(-TAIL);
}

// Exit 0 with forge's JSON is success; a non-zero exit is a failure with stderr's tail; exit 0 without JSON (or with a
// shape the parser refuses) is a failure naming the command; a cancel is its own outcome.
export function forgeOutcome<T>(command: string, result: RunResult, parse: (raw: string) => Parsed<T>): ForgeOutcome<T> {
  if (result.error?.startsWith("cancelled")) {
    return result.survivors?.length ? { kind: "cancelled", note: result.error } : { kind: "cancelled" };
  }
  if (result.code === undefined) {
    return { kind: "failed", message: `forge ${command} did not finish: ${result.error ?? "it could not start"}`, stderrTail: tail(result.stderr) };
  }
  if (result.code !== 0) {
    return { kind: "failed", message: `forge ${command} exited ${result.code}`, stderrTail: tail(result.stderr) };
  }
  const parsed = parse(result.stdout);
  return parsed.ok
    ? { kind: "ok", value: parsed.value }
    : { kind: "failed", message: parsed.message, stderrTail: tail(result.stderr), raw: parsed.raw };
}
