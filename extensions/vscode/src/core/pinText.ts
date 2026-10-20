// The reviewer pin as text: reading it for display and editing it in place, so every byte an edit does not touch
// (comments, blank lines, key order, quote style, line endings) stays as the operator wrote it (plan R12).
//
// This is the narrow hand-written editor the design spec chose (docs/specs/2026-10-20-vscode-extension-design.md
// section 2) after no TOML library edited every case in place. It edits one layout, the one the reviewer kit ships;
// isEditableLayout says whether a pin is in it, and a valid pin that is not opens the read-only pin-layout state.
// It never validates: the workspace dispatcher's --check-pin judges every result. Its behaviour is the reference
// design/spikes/pin_edits.py, whose outputs are the golden cases under test/fixtures/edits/.

// A comment runs to the end of the line, which TOML ends only at \n: [^\n] rather than ".", which in JavaScript also
// stops at U+2028 and U+2029 (Python's "." does not), so both editors read the same lines.
const HEADER = /^\[(reviewers\.[A-Za-z0-9_-]+|routes)\][ \t]*(#[^\n]*)?$/;
const KEY = /^([A-Za-z0-9_-]+)[ \t]*=[ \t]*("[^"\\\n]*"|'[^'\n]*'|[0-9]+)([ \t]*#[^\n]*)?$/d;
// Elements need the comma between them that TOML requires, so no two quantifiers compete for the same spaces and a
// long malformed array cannot backtrack exponentially.
const ROUTE =
  /^([A-Za-z0-9_-]+)[ \t]*=[ \t]*\[([ \t]*(?:"[A-Za-z0-9_-]+"(?:[ \t]*,[ \t]*"[A-Za-z0-9_-]+")*(?:[ \t]*,)?[ \t]*)?)\]([ \t]*#[^\n]*)?$/d;
const TOKEN = /"([A-Za-z0-9_-]+)"/g;

export interface Span {
  start: number;
  end: number;
}

export interface PinReviewer {
  name: string;
  cli?: string;
  model?: string;
  effort?: string;
  span: Span;
}

export interface PinRoute {
  writer: string;
  names: string[];
  span: Span;
}

export interface PinView {
  reviewers: PinReviewer[];
  routes: PinRoute[];
}

// Lines split on \n alone, each keeping its ending (a CRLF line keeps its \r\n): TOML ends a line with \n or \r\n and
// nothing else, so a U+2028 inside a comment is a character of that line.
// A line without TOML's whitespace (space, tab) and its ending. String.prototype.trim would also remove U+2028 and
// other characters that belong to a comment, and Python's str.strip removes a different set, so neither is used.
function bare(line: string): string {
  return line.replace(/^[ \t\r\n]+|[ \t\r\n]+$/g, "");
}

function linesOf(text: string): string[] {
  return text.match(/[^\n]*\n|[^\n]+$/g) ?? [];
}

function names(inner: string): string[] {
  return [...inner.matchAll(TOKEN)].map((n) => n[1]);
}

// The array's inside with these names, in its own style: the spacing after "[", between elements and before "]" are
// kept, so an edit changes only the names.
function rebuild(inner: string, updated: string[]): string {
  const tokens = [...inner.matchAll(TOKEN)];
  const lead = tokens.length ? inner.slice(0, tokens[0].index) : "";
  const last = tokens[tokens.length - 1];
  const trail = tokens.length ? inner.slice((last.index ?? 0) + last[0].length) : "";
  const sep = tokens.length >= 2 ? inner.slice((tokens[0].index ?? 0) + tokens[0][0].length, tokens[1].index) : ", ";
  return lead + updated.map((n) => `"${n}"`).join(sep) + trail;
}

function eol(text: string): string {
  return text.includes("\r\n") ? "\r\n" : "\n";
}

function header(line: string): string | undefined {
  return HEADER.exec(bare(line))?.[1];
}

function isComment(line: string): boolean {
  return bare(line).startsWith("#");
}

export function isEditableLayout(text: string): boolean {
  let table: string | undefined;
  for (const raw of text.split("\n")) {
    const line = bare(raw);
    if (line === "" || line.startsWith("#")) {
      continue;
    }
    const name = header(line);
    if (name) {
      table = name;
    } else if (table === "routes" ? !ROUTE.test(line) : !KEY.test(line)) {
      return false;
    }
  }
  return true;
}

// The header line's index and one past the table's last key line (trailing blank and comment lines excluded).
function tableSpan(lines: string[], name: string): [number, number] {
  const start = lines.findIndex((line) => header(line) === name);
  if (start < 0) {
    throw new Error(`the pin has no [${name}] table`);
  }
  let end = start + 1;
  while (end < lines.length && header(lines[end]) === undefined) {
    end += 1;
  }
  while (end > start + 1 && (bare(lines[end - 1]) === "" || isComment(lines[end - 1]))) {
    end -= 1;
  }
  return [start, end];
}

// The comment lines directly above a header, with no blank line between them and it.
function commentBlockAbove(lines: string[], start: number): number {
  let i = start;
  while (i > 0 && isComment(lines[i - 1])) {
    i -= 1;
  }
  return i;
}

// A line given its ending when it has none (the last line of a file without a final newline).
function ending(line: string, nl: string): string {
  return line.endsWith("\n") || line.endsWith("\r") ? line : line + nl;
}

// Removes a key or route line; a trailing comment on it stays behind, byte for byte, as a comment line in its place.
// match is the line's KEY or ROUTE match on bare(line), whose group 3 is the comment.
function removeLine(lines: string[], i: number, match: RegExpExecArray): void {
  const span = match.indices?.[3];
  if (!span) {
    lines.splice(i, 1);
    return;
  }
  const body = lines[i].replace(/[\r\n]+$/, "");
  const lead = body.length - body.replace(/^[ \t]+/, "").length;
  const comment = body.slice(lead + span[0]).replace(/^[ \t]+/, "");
  lines[i] = body.slice(0, lead) + comment + lines[i].slice(body.length);
}

function replaceFirst(line: string, found: string, replacement: string): string {
  return line.replace(found, () => replacement);
}

// Set, add (value given, key absent) or remove (value null) one key of one reviewer table.
export function setField(text: string, reviewer: string, key: string, value: string | null): string {
  const lines = linesOf(text);
  const nl = eol(text);
  const [start, end] = tableSpan(lines, `reviewers.${reviewer}`);
  for (let i = start + 1; i < end; i += 1) {
    const m = KEY.exec(bare(lines[i]));
    if (m && m[1] === key) {
      if (value === null) {
        removeLine(lines, i, m);
      } else {
        const quote = m[2][0];
        lines[i] = replaceFirst(lines[i], m[2], `${quote}${value}${quote}`);
      }
      return lines.join("");
    }
  }
  if (value !== null) {
    lines[end - 1] = ending(lines[end - 1], nl);
    lines.splice(end, 0, `${key} = "${value}"${nl}`);
  }
  return lines.join("");
}

// A new table after the last reviewer table, before the comment block above [routes], with a blank line before it.
export function addReviewer(text: string, name: string, entry: Record<string, string>): string {
  const lines = linesOf(text);
  const nl = eol(text);
  const last = lines.reduce((found, line, i) => (header(line)?.startsWith("reviewers.") ? i : found), -1);
  if (last < 0) {
    throw new Error("the pin has no reviewer table to add after");
  }
  const [, end] = tableSpan(lines, header(lines[last]) as string);
  lines[end - 1] = ending(lines[end - 1], nl);
  const block = [nl, `[reviewers.${name}]${nl}`, ...Object.entries(entry).map(([k, v]) => `${k} = "${v}"${nl}`)];
  lines.splice(end, 0, ...block);
  return lines.join("");
}

function same(a: string[], b: string[]): boolean {
  return a.length === b.length && a.every((n, k) => n === b[k]);
}

// Applies change(names) to every route; a route left empty is removed, never written as [].
function setRoutes(text: string, change: (names: string[]) => string[]): string {
  const lines = linesOf(text);
  const [start, end] = tableSpan(lines, "routes");
  for (let i = end - 1; i > start; i -= 1) {
    const m = ROUTE.exec(bare(lines[i]));
    if (!m) {
      continue;
    }
    const current = names(m[2]);
    const updated = change(current);
    if (same(updated, current)) {
      continue;
    }
    if (updated.length === 0) {
      removeLine(lines, i, m);
    } else {
      lines[i] = replaceFirst(lines[i], `[${m[2]}]`, `[${rebuild(m[2], updated)}]`);
    }
  }
  return lines.join("");
}

// The header and every route entry that names the reviewer change, nothing else.
export function renameReviewer(text: string, from: string, to: string): string {
  const lines = linesOf(text);
  const [start] = tableSpan(lines, `reviewers.${from}`);
  lines[start] = replaceFirst(lines[start], `[reviewers.${from}]`, `[reviewers.${to}]`);
  return setRoutes(lines.join(""), (names) => names.map((n) => (n === from ? to : n)));
}

// The table, the comment block directly above it and one blank line after it go; its name leaves every route.
export function deleteReviewer(text: string, name: string): string {
  const lines = linesOf(text);
  const [start, tableEnd] = tableSpan(lines, `reviewers.${name}`);
  const first = commentBlockAbove(lines, start);
  let end = tableEnd;
  if (end < lines.length && bare(lines[end]) === "") {
    end += 1;
  }
  lines.splice(first, end - first);
  return setRoutes(lines.join(""), (names) => names.filter((n) => n !== name));
}

// Rewrites one writer's array on its own line, or appends a line after the last route when it has none.
export function setRoute(text: string, writer: string, routeNames: string[]): string {
  const lines = linesOf(text);
  const nl = eol(text);
  const [start, end] = tableSpan(lines, "routes");
  const array = `[${routeNames.map((n) => `"${n}"`).join(", ")}]`;
  for (let i = start + 1; i < end; i += 1) {
    const m = ROUTE.exec(bare(lines[i]));
    if (m && m[1] === writer) {
      if (!same(names(m[2]), routeNames)) {
        lines[i] = replaceFirst(lines[i], `[${m[2]}]`, `[${rebuild(m[2], routeNames)}]`);
      }
      return lines.join("");
    }
  }
  lines[end - 1] = ending(lines[end - 1], nl);
  lines.splice(end, 0, `${writer} = ${array}${nl}`);
  return lines.join("");
}

export function removeRoute(text: string, writer: string): string {
  const lines = linesOf(text);
  const [start, end] = tableSpan(lines, "routes");
  for (let i = start + 1; i < end; i += 1) {
    const m = ROUTE.exec(bare(lines[i]));
    if (m && m[1] === writer) {
      removeLine(lines, i, m);
      break;
    }
  }
  return lines.join("");
}

// The pin's reviewers and routes with where each sits in the text, for display only; undefined for a layout the
// editor does not edit.
export function readPin(text: string): PinView | undefined {
  if (!isEditableLayout(text)) {
    return undefined;
  }
  const lines = linesOf(text);
  const offsets: number[] = [];
  lines.reduce((offset, line) => (offsets.push(offset), offset + line.length), 0);
  offsets.push(text.length);
  const view: PinView = { reviewers: [], routes: [] };
  lines.forEach((line) => {
    const name = header(line);
    if (name?.startsWith("reviewers.")) {
      const [start, end] = tableSpan(lines, name);
      const reviewer: PinReviewer = { name: name.slice("reviewers.".length), span: { start: offsets[start], end: offsets[end] } };
      for (let k = start + 1; k < end; k += 1) {
        const m = KEY.exec(bare(lines[k]));
        if (m && (m[1] === "cli" || m[1] === "model" || m[1] === "effort")) {
          reviewer[m[1]] = m[2].slice(1, -1);
        }
      }
      view.reviewers.push(reviewer);
    } else if (name === "routes") {
      const [start, end] = tableSpan(lines, name);
      for (let k = start + 1; k < end; k += 1) {
        const m = ROUTE.exec(bare(lines[k]));
        if (m) {
          const body = lines[k].replace(/[\r\n]+$/, "");
          view.routes.push({
            writer: m[1],
            names: names(m[2]),
            span: { start: offsets[k], end: offsets[k] + body.length },
          });
        }
      }
    }
  });
  return view;
}
