// D00 T01 §4 spike (owner's answer 5): which TOML library round-trips the fixture pins byte for byte and edits
// them in place? Results are in docs/specs/2026-10-20-vscode-extension-design.md section 2. To re-run, outside the
// repository: npm install --prefix <dir>/libs smol-toml @iarna/toml @ltd/j-toml toml-patch @decimalturn/toml-patch
// toml-eslint-parser, copy this file to <dir>, and run node <dir>/toml_libraries.mjs <path to the shipped pin>.
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const require = createRequire(join(here, "libs", "package.json"));
const shipped = readFileSync(process.argv[2], "utf8");

// Fixtures: the shipped pin; the same with inline and trailing comments; the inline-table layout load_pin accepts.
const comments = shipped
  .replace('effort = "medium"', 'effort = "medium" # astra reviews on medium')
  .replace('[routes]', '[routes] # who reviews whom')
  .replace('model = "claude-sonnet-5-5"', '# the newest Sonnet\nmodel = "claude-sonnet-5-5"');
const inline = "schema_version = 1\nreviewers = { astra = { cli = 'codex', model = 'gpt-6-astra', effort = 'medium' } }\n"
  + "routes = { claude = ['astra'] }\n";
const fixtures = { shipped, comments, inline };

// The two edits every editor must make, and the byte-for-byte expectation: only that line changes.
const edits = {
  effort: { apply: (o) => { o.reviewers.astra.effort = "high"; },
            expect: (t) => t.replace(/effort = (["'])medium\1/, (m, q) => `effort = ${q}high${q}`) },
  route: { apply: (o) => { o.routes.claude = ["gemini", "astra"]; },
           expect: (t) => t.includes('claude = ["astra", "gemini"]')
             ? t.replace('claude = ["astra", "gemini"]', 'claude = ["gemini", "astra"]')
             : t.replace("claude = ['astra']", "claude = ['gemini', 'astra']") },
};

const clone = (o) => JSON.parse(JSON.stringify(o));
const libs = {
  "smol-toml": () => { const m = require("smol-toml"); return { parse: m.parse, write: (o) => m.stringify(o) }; },
  "@iarna/toml": () => { const m = require("@iarna/toml"); return { parse: m.parse, write: (o) => m.stringify(o) }; },
  "@ltd/j-toml": () => {
    const m = require("@ltd/j-toml");
    return { parse: (t) => m.parse(t, { joiner: "\n", bigint: false, x: { comment: true } }),
             write: (o) => m.stringify(o, { newline: "\n", newlineAround: "section" }) };
  },
  "toml-patch": () => { const m = require("toml-patch"); return { parse: m.parse, write: (o, src) => m.patch(src, o) }; },
  "@decimalturn/toml-patch": () => {
    const m = require("@decimalturn/toml-patch");
    return { parse: m.parse, write: (o, src) => m.patch(src, o) };
  },
};

const results = [];
for (const [name, load] of Object.entries(libs)) {
  let lib;
  try { lib = load(); } catch (e) { results.push({ name, error: "load: " + e.message }); continue; }
  for (const [fx, text] of Object.entries(fixtures)) {
    const row = { name, fixture: fx };
    try {
      const obj = lib.parse(text);
      row.roundTrip = lib.write(clone(obj), text) === text;
      for (const [ename, edit] of Object.entries(edits)) {
        const o = clone(obj);
        edit.apply(o);
        const out = lib.write(o, text);
        const want = edit.expect(text);
        row[ename] = out === want ? "exact" : (out.includes("#") || !text.includes("#") ? "changed more" : "comments lost");
      }
    } catch (e) { row.error = e.message.split("\n")[0].slice(0, 90); }
    results.push(row);
  }
}
// toml-eslint-parser builds a syntax tree with comments but has no writer: report what it gives.
try {
  const p = require("toml-eslint-parser");
  const ast = p.parseTOML(shipped);
  results.push({ name: "toml-eslint-parser", fixture: "shipped", note: `parses with ${ast.comments.length} comments and token ranges; no writer` });
} catch (e) { results.push({ name: "toml-eslint-parser", error: e.message }); }
console.log(JSON.stringify(results, null, 1));
