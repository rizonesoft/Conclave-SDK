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

// Part 2: every edit the editor makes, through the two libraries that patch text in place, as a line diff of the
// shipped pin (and the inline-table pin where the edit applies). design/spikes/pin_edits.py has the expected diffs.
function lineDiff(a, b) {
  const x = a.split("\n"), y = b.split("\n");
  const lcs = Array.from({ length: x.length + 1 }, () => new Array(y.length + 1).fill(0));
  for (let i = x.length - 1; i >= 0; i--)
    for (let j = y.length - 1; j >= 0; j--)
      lcs[i][j] = x[i] === y[j] ? lcs[i + 1][j + 1] + 1 : Math.max(lcs[i + 1][j], lcs[i][j + 1]);
  const out = [];
  let i = 0, j = 0;
  while (i < x.length || j < y.length) {
    if (i < x.length && j < y.length && x[i] === y[j]) { i++; j++; }
    else if (j < y.length && (i === x.length || lcs[i][j + 1] >= lcs[i + 1][j])) { out.push(`+ new ${j + 1}: ${y[j]}`); j++; }
    else { out.push(`- old ${i + 1}: ${x[i]}`); i++; }
  }
  return out.length ? out.join("\n") : "(no change)";
}
const renameKey = (obj, from, to) => Object.fromEntries(Object.entries(obj).map(([k, v]) => [k === from ? to : k, v]));
const structural = {
  "set a field": (o) => { o.reviewers.astra.effort = "high"; },
  "add a reviewer": (o) => { o.reviewers.mini = { cli: "codex", model: "gpt-6-mini", effort: "low" }; },
  "rename a reviewer": (o) => {
    o.reviewers = renameKey(o.reviewers, "astra", "gpt6");
    for (const w of Object.keys(o.routes)) o.routes[w] = o.routes[w].map((n) => (n === "astra" ? "gpt6" : n));
  },
  "delete a reviewer": (o) => {
    delete o.reviewers.sonnet;
    for (const w of Object.keys(o.routes)) o.routes[w] = o.routes[w].filter((n) => n !== "sonnet");
  },
  "set a route": (o) => { o.routes.codex = ["sonnet", "gemini"]; },
  "remove a route": (o) => { delete o.routes.gemini; },
};
for (const name of ["toml-patch", "@decimalturn/toml-patch"]) {
  const lib = libs[name]();
  for (const [label, text] of Object.entries({ shipped, inline })) {
    for (const [edit, apply] of Object.entries(structural)) {
      const o = clone(lib.parse(text));
      try { apply(o); } catch { continue; }  // the inline pin has no sonnet or codex route to edit
      let out;
      try { out = lineDiff(text, lib.write(o, text)); } catch (e) { out = "ERROR " + e.message.split("\n")[0]; }
      console.log(`### ${name}, ${label}: ${edit}\n${out}`);
    }
  }
}
