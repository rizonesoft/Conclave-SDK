#!/usr/bin/env node
// Enforce the delegation tier invariant on this project's agent definitions.
//
// The rule is in AGENTS.md: mechanical subtasks delegate to subagents, those
// subagents are Sonnet-tier only — never Haiku — and an elevated tier is
// reserved for work whose verdict quality demands it.
//
// A rule stated in prose is protected by discipline. This makes it protected by
// a check: an agent added with `model: haiku`, or with no `model:` line at all,
// fails here instead of passing every gate and being noticed later, or never.
//
// An absent `model:` is an error rather than a default, because an unpinned
// agent silently inherits the caller's model — mechanical work then runs on the
// expensive tier with no signal at all, which is the exact regression this
// exists to catch.
//
// No dependencies and no repository-specific paths, so a bootstrapped project
// can run it from day one. With no agents defined yet it passes with nothing
// checked, and starts enforcing the moment the first definition appears.
//
//   node scripts/verify-agent-tiers.mjs

import { existsSync, readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

/**
 * Tier vocabulary.
 *
 * Kept as substrings rather than exact model IDs so a version bump — sonnet-5
 * to a later sonnet — does not silently fail a project that is still obeying
 * the rule. The tier is the invariant; the exact pin is a routing decision that
 * belongs elsewhere.
 */
export const FORBIDDEN_AGENT_MODEL_TOKENS = ["haiku"];
export const BASE_AGENT_MODEL_TOKENS = ["sonnet"];
export const ELEVATED_AGENT_MODEL_TOKENS = ["opus", "fable"];

/** Where an elevated pin must record why it is elevated. */
export const ELEVATION_RATIONALE_FIELD = "model_rationale";

/**
 * Read the opening frontmatter as a strict, closed subset of YAML.
 *
 * Three review rounds on 2026-09-15 each found another way a regex over this
 * block reads a value that is not the value: a body line outside the
 * frontmatter, a trailing `# comment`, a comment inside quotes, an alias
 * (`model: *sonnet` resolving to a Haiku anchor), a `model:` line inside a
 * multi-line quoted scalar, a duplicate key read from the wrong end, and a
 * block scalar whose indentation indicator makes its only line empty. Chasing
 * them one at a time is how this file got to three rounds.
 *
 * So the reader models a deliberately small language and REFUSES everything
 * else. An agent definition's frontmatter is a handful of flat scalar keys; a
 * file using anchors, flow collections, tags or multi-line quoting is refused
 * as unreadable rather than guessed at. Failing closed on an exotic definition
 * costs whoever wrote it one plain rewrite. Failing open costs a run on the
 * wrong tier, silently, for as long as nobody looks.
 *
 * Returns `{ fields, error }`: `error` is set when the block cannot be read
 * under these rules, and `fields` maps key to `{ value, isQuoted }`.
 */
export function readAgentFrontmatter(text) {
  const match = /^---[ \t]*\r?\n([\s\S]*?)\r?\n---[ \t]*(?:\r?\n|$)/.exec(text);
  if (!match) return { fields: null, error: "has no opening frontmatter block; the tier pin must be a machine-read field, not prose" };

  const lines = match[1].split(/\r?\n/);
  const fields = new Map();
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];
    index += 1;
    if (line.trim() === "" || /^[ \t]*#/.test(line)) continue;

    // YAML needs whitespace after the colon in a block mapping: `model:sonnet`
    // is the plain scalar "model:sonnet", not a pin, and reading it as one let
    // a definition with no model field through.
    const entry = /^([A-Za-z_][A-Za-z0-9_-]*):(?:[ \t]+([^\r\n]*?))?[ \t]*$/.exec(line);
    if (!entry) {
      return { fields: null, error: `frontmatter line ${JSON.stringify(line)} is not a plain "key: value" pair; agent frontmatter is read as a closed subset of YAML and anything else is refused rather than guessed` };
    }

    const [, key, rest = ""] = entry;
    if (fields.has(key)) {
      // This reader takes the first, a YAML parser takes the last. Refuse the
      // ambiguity rather than pick a winner: `model: sonnet` above
      // `model: claude-haiku-4-5` read as Sonnet and ran as Haiku.
      return { fields: null, error: `declares "${key}:" more than once; a duplicate key is read from opposite ends by this check and by YAML` };
    }

    // A comment after the value is ordinary YAML, and rejecting it would fail
    // correct definitions. It is stripped here, outside the quoted region, so
    // `model: "sonnet # haiku"` still keeps its hash as content.
    const quotedWithComment = /^((["'])(?:[^\\]|\\.)*?\2)[ \t]+#[^\r\n]*$/.exec(rest);
    const scalarWithComment = /^([|>][-+0-9]*)[ \t]+#[^\r\n]*$/.exec(rest);
    const value = quotedWithComment?.[1] ?? scalarWithComment?.[1] ?? rest;

    if (/^[|>]$/.test(value)) {
      // A bare block scalar only. An indentation indicator (`|2`) changes what
      // counts as content, and this reader does not model that.
      const collected = [];
      while (index < lines.length && (lines[index].trim() === "" || /^[ \t]/.test(lines[index]))) {
        collected.push(lines[index].trim());
        index += 1;
      }
      fields.set(key, { value: collected.filter(Boolean).join(" "), isQuoted: true });
      continue;
    }

    if (/^[|>]/.test(value)) {
      return { fields: null, error: `"${key}:" uses a block scalar indicator (${JSON.stringify(value)}); write the value plainly so this check and YAML agree on where it ends` };
    }

    const quoted = /^(["'])((?:[^\\]|\\.)*?)\1[ \t]*$/.exec(value);
    if (quoted) {
      if (/\\/.test(quoted[2])) {
        return { fields: null, error: `"${key}:" contains a backslash escape; this check does not decode escapes, so write the value plainly` };
      }
      fields.set(key, { value: quoted[2].trim(), isQuoted: true });
      continue;
    }

    if (/^["']/.test(value)) {
      return { fields: null, error: `"${key}:" opens a quote that does not close on the same line; a multi-line quoted scalar can hide another key inside it` };
    }

    const plain = value.replace(/(?:^|[ \t])#.*$/, "").trim();
    if (/^[&*!]/.test(plain) || /^[[{]/.test(plain)) {
      return { fields: null, error: `"${key}:" uses YAML ${plain.startsWith("[") || plain.startsWith("{") ? "flow collection" : "anchor, alias or tag"} syntax (${JSON.stringify(plain)}); write the value plainly, because an alias resolves to something this check cannot see` };
    }
    fields.set(key, { value: plain, isQuoted: false });
  }

  return { fields, error: null };
}

/** A tier pin: one bare token, optionally quoted, and nothing else. */
export function tierPin(fields, field) {
  const entry = fields.get(field);
  if (!entry || entry.value === "") return null;
  return /^[A-Za-z0-9][A-Za-z0-9._-]*$/.test(entry.value) ? entry.value : null;
}

/**
 * A recorded justification: prose that survives unquoting and trimming.
 *
 * An unquoted `null` or `~` is YAML's way of writing nothing, so it records
 * nothing. Quoted, it is a word someone chose to write, and stays content.
 */
export function recordedProse(fields, field) {
  const entry = fields.get(field);
  if (!entry) return null;
  const value = entry.value.trim();
  if (value === "") return null;
  if (!entry.isQuoted && /^(?:null|Null|NULL|~)$/.test(value)) return null;
  return value;
}

export function verifyAgentTiers(repoRoot = process.cwd(), relativeRoot = join(".claude", "agents")) {
  const errors = [];
  const absoluteRoot = join(repoRoot, relativeRoot);
  if (!existsSync(absoluteRoot)) return { checked: 0, elevated: 0, errors };

  const files = readdirSync(absoluteRoot, { withFileTypes: true })
    .filter((entry) => entry.isFile() && entry.name.endsWith(".md"))
    .map((entry) => entry.name)
    .sort();

  let elevated = 0;
  for (const name of files) {
    const relative = join(relativeRoot, name);
    const text = readFileSync(join(absoluteRoot, name), "utf8");
    const { fields, error } = readAgentFrontmatter(text);

    if (error) {
      errors.push(`${relative} ${error}`);
      continue;
    }

    const model = tierPin(fields, "model")?.toLowerCase() ?? null;

    if (!model) {
      errors.push(
        `${relative} must declare an explicit "model:" field in its frontmatter carrying one bare tier token; an unpinned or unparseable pin inherits the caller's model`,
      );
      continue;
    }

    const forbidden = FORBIDDEN_AGENT_MODEL_TOKENS.find((token) => model.includes(token));
    if (forbidden) {
      errors.push(`${relative} pins "${model}": ${forbidden} is forbidden for every agent and subagent, for any task`);
      continue;
    }

    const isBase = BASE_AGENT_MODEL_TOKENS.some((token) => model.includes(token));
    const isElevated = ELEVATED_AGENT_MODEL_TOKENS.some((token) => model.includes(token));
    if (!isBase && !isElevated) {
      errors.push(`${relative} pins unrecognized tier "${model}"; use the base tier, or an elevated tier with a recorded rationale`);
      continue;
    }

    if (isElevated) {
      elevated += 1;
      // An elevated pin has to be argued for. Without this the expensive tier
      // becomes the path of least resistance and drifts upward silently.
      if (!recordedProse(fields, ELEVATION_RATIONALE_FIELD)) {
        errors.push(
          `${relative} pins the elevated tier "${model}" without a non-empty "${ELEVATION_RATIONALE_FIELD}:" field; `
          + "an elevated agent must be a deliberate decision, not a default that drifted",
        );
      }
    }
  }

  return { checked: files.length, elevated, errors };
}

if (process.argv[1]?.endsWith("verify-agent-tiers.mjs")) {
  const result = verifyAgentTiers();
  if (result.errors.length > 0) {
    process.stderr.write(`Agent tier invariant failed:\n${result.errors.map((line) => `  - ${line}`).join("\n")}\n`);
    process.exit(1);
  }
  process.stdout.write(
    `Agent tiers valid: ${result.checked} definition(s) checked, ${result.elevated} elevated with a recorded rationale.\n`,
  );
}
