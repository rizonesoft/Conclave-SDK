// The reviewer pin as text: reading it for display and editing it in place, so every byte an edit does not touch
// (comments, blank lines, key order, quote style, line endings) stays as the operator wrote it (plan R12).
//
// This is the narrow hand-written editor the design spec chose (docs/specs/2026-10-20-vscode-extension-design.md
// section 2) after no TOML library edited every case in place. It edits one layout, the one the reviewer kit ships;
// isEditableLayout says whether a pin is in it, and a valid pin that is not opens the read-only pin-layout state.
// It never validates: the workspace dispatcher's --check-pin judges every result. Its behaviour is the reference
// design/spikes/pin_edits.py, whose outputs are the golden cases under test/fixtures/edits/.

const HEADER = /^\[(reviewers\.[A-Za-z0-9_-]+|routes)\][ \t]*(#.*)?$/;
const KEY = /^([A-Za-z0-9_-]+)[ \t]*=[ \t]*("[^"\\\n]*"|'[^'\n]*'|[0-9]+)([ \t]*#.*)?$/;
const ROUTE = /^([A-Za-z0-9_-]+)[ \t]*=[ \t]*\[((?:[ \t]*"[A-Za-z0-9_-]+"[ \t]*,?)*)\]([ \t]*#.*)?$/;
const NAME = /"([A-Za-z0-9_-]+)"/g;

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

// Lines with their endings kept, split as Python's str.splitlines(keepends=True) splits the line endings a pin uses.
function linesOf(text: string): string[] {
  return text.match(/[^\r\n]*(?:\r\n|\n|\r)|[^\r\n]+$/g) ?? [];
}

function eol(text: string): string {
  return text.includes("\r\n") ? "\r\n" : "\n";
}

function header(line: string): string | undefined {
  return HEADER.exec(line.trim())?.[1];
}

function isComment(line: string): boolean {
  return line.trimStart().startsWith("#");
}

export function isEditableLayout(text: string): boolean {
  let table: string | undefined;
  for (const raw of text.split(/\r\n|\n|\r/)) {
    const line = raw.trim();
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
  while (end > start + 1 && (lines[end - 1].trim() === "" || isComment(lines[end - 1]))) {
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

// Removes a key or route line; a trailing comment on it stays behind as a comment line in its place.
function removeLine(lines: string[], i: number, comment: string | undefined): void {
  if (!comment) {
    lines.splice(i, 1);
    return;
  }
  const body = lines[i].replace(/[\r\n]+$/, "");
  const indent = body.slice(0, body.length - body.trimStart().length);
  lines[i] = indent + comment.trim() + lines[i].slice(body.length);
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
    const m = KEY.exec(lines[i].trim());
    if (m && m[1] === key) {
      if (value === null) {
        removeLine(lines, i, m[3]);
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

// Applies change(names) to every route; a route left empty is removed, never written as [].
function setRoutes(text: string, change: (names: string[]) => string[]): string {
  const lines = linesOf(text);
  const [start, end] = tableSpan(lines, "routes");
  for (let i = end - 1; i > start; i -= 1) {
    const m = ROUTE.exec(lines[i].trim());
    if (!m) {
      continue;
    }
    const names = [...m[2].matchAll(NAME)].map((n) => n[1]);
    const updated = change(names);
    if (updated.length === names.length && updated.every((n, k) => n === names[k])) {
      continue;
    }
    if (updated.length === 0) {
      removeLine(lines, i, m[3]);
    } else {
      lines[i] = replaceFirst(lines[i], `[${m[2]}]`, `[${updated.map((n) => `"${n}"`).join(", ")}]`);
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
  if (end < lines.length && lines[end].trim() === "") {
    end += 1;
  }
  lines.splice(first, end - first);
  return setRoutes(lines.join(""), (names) => names.filter((n) => n !== name));
}

// Rewrites one writer's array on its own line, or appends a line after the last route when it has none.
export function setRoute(text: string, writer: string, names: string[]): string {
  const lines = linesOf(text);
  const nl = eol(text);
  const [start, end] = tableSpan(lines, "routes");
  const array = `[${names.map((n) => `"${n}"`).join(", ")}]`;
  for (let i = start + 1; i < end; i += 1) {
    const m = ROUTE.exec(lines[i].trim());
    if (m && m[1] === writer) {
      lines[i] = replaceFirst(lines[i], `[${m[2]}]`, array);
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
    const m = ROUTE.exec(lines[i].trim());
    if (m && m[1] === writer) {
      removeLine(lines, i, m[3]);
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
        const m = KEY.exec(lines[k].trim());
        if (m && (m[1] === "cli" || m[1] === "model" || m[1] === "effort")) {
          reviewer[m[1]] = m[2].slice(1, -1);
        }
      }
      view.reviewers.push(reviewer);
    } else if (name === "routes") {
      const [start, end] = tableSpan(lines, name);
      for (let k = start + 1; k < end; k += 1) {
        const m = ROUTE.exec(lines[k].trim());
        if (m) {
          const body = lines[k].replace(/[\r\n]+$/, "");
          view.routes.push({
            writer: m[1],
            names: [...m[2].matchAll(NAME)].map((n) => n[1]),
            span: { start: offsets[k], end: offsets[k] + body.length },
          });
        }
      }
    }
  });
  return view;
}
