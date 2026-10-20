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

// A name as Python's repr prints it: 'x', or "x" when the name holds a single quote.
const QUOTED = String.raw`'([^']*)'|"([^"]*)"`;
const name = (m: RegExpExecArray) => m[1] ?? m[2];

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
  [new RegExp(`^route (?:${QUOTED})(?: must list | names |: the fallback must be of a third family)`),
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
