// Where a refusal attaches in the editor (design/SPEC.md §4): the dispatcher's Refused message, verbatim, under the
// field it names. Keyed on the message forms load_pin raises; an unknown form attaches to the file, text unchanged.

export type ErrorTarget =
  | { kind: "name" | "unknown-keys" | "cli" | "model" | "stray-effort" | "effort"; reviewer: string; message: string }
  | { kind: "cards"; message: string }
  | { kind: "unknown-writer"; message: string }
  | { kind: "route"; writer: string; message: string }
  // The pin-refused screen (§7): the editor opens only a pin whose TOML parses with the pin's shape.
  | { kind: "screen"; message: string }
  | { kind: "file"; message: string };

// A name as Python's repr prints it: 'x', or "x" when the name holds a single quote but no double one, with
// backslash escapes inside (\\, \', \n, \xhh, \uhhhh, \Uhhhhhhhh), decoded back to the name the card shows.
const QUOTED = String.raw`'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)"`;
const ESCAPES: Record<string, string> = { "\\": "\\", "'": "'", '"': '"', n: "\n", r: "\r", t: "\t", a: "\x07", b: "\b", f: "\f", v: "\v", "0": "\0" };

function decode(literal: string): string {
  return literal.replace(/\\(x[0-9a-fA-F]{2}|u[0-9a-fA-F]{4}|U[0-9a-fA-F]{8}|.)/g, (whole, code: string) =>
    code.length > 1 ? String.fromCodePoint(parseInt(code.slice(1), 16)) : (ESCAPES[code] ?? whole));
}

const name = (m: RegExpExecArray) => decode(m[1] ?? m[2]);

const FORMS: [RegExp, (m: RegExpExecArray, message: string) => ErrorTarget][] = [
  [new RegExp(`^invalid reviewer (?:${QUOTED})$`), (m, message) => ({ kind: "name", reviewer: name(m), message })],
  [new RegExp(`^reviewer (?:${QUOTED}) has unknown keys: `), (m, message) => ({ kind: "unknown-keys", reviewer: name(m), message })],
  [new RegExp(`^reviewer (?:${QUOTED}) needs cli = one of `), (m, message) => ({ kind: "cli", reviewer: name(m), message })],
  [new RegExp(`^reviewer (?:${QUOTED}) has a malformed model$`), (m, message) => ({ kind: "model", reviewer: name(m), message })],
  [new RegExp(`^reviewer (?:${QUOTED}): Antigravity carries the effort in the model name, so set no effort$`),
    (m, message) => ({ kind: "stray-effort", reviewer: name(m), message })],
  [new RegExp(`^reviewer (?:${QUOTED}) needs effort = one of `), (m, message) => ({ kind: "effort", reviewer: name(m), message })],
  [/^the reviewer pin defines no reviewers$/, (_m, message) => ({ kind: "cards", message })],
  [/^\[routes\] may only name the writers /, (_m, message) => ({ kind: "unknown-writer", message })],
  [new RegExp(`^route (?:${QUOTED})(?: must list | names )`),
    (m, message) => ({ kind: "route", writer: name(m), message })],
  [/^the reviewer pin needs exactly schema_version = 1, \[reviewers\.\*\] and \[routes\]$/, (_m, message) => ({ kind: "screen", message })],
  [/^unreadable reviewer pin: /, (_m, message) => ({ kind: "screen", message })],
];

export function errorTarget(message: string): ErrorTarget {
  for (const [form, target] of FORMS) {
    const m = form.exec(message);
    if (m) {
      return target(m, message);
    }
  }
  return { kind: "file", message };
}
