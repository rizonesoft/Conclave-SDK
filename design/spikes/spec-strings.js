// SPEC string inventory for the feature panes (D00 T01 §10): renders the mockup's `sections` side bar for every
// scenario, workspace and theme, calls every pane action and the actions of the rows first shown, and lists every
// distinct pane title, description and
// tooltip, action label, row tooltip, action label and message (the toast an action shows). With --spec it checks each
// against design/SPEC.md: a string is covered when a backticked span there matches it verbatim, or as a template whose
// {placeholders} stand for any text and which has at least one fixed character. A row tooltip that repeats the row's own
// description, or is the full path of its label, is that data shown again and not listed. Exits 1 on a missing string.
//
// What it is not: a proof that every string is specified. It reads pane titles, descriptions and their tooltips, action
// labels, the tooltips of the rows first shown, and messages; it does not read row labels and descriptions, which are
// mostly the example data, or rows inside collapsed groups, and a template matches any text with the same fixed parts.
// String-for-string parity with the mockup is the parity fixtures' job (D02 T01 §11), exported from the mockup's own
// view model and compared with what the extension renders.
// Usage: node design/spikes/spec-strings.js design/mockup/project/Main.dc.html [--spec design/SPEC.md]
'use strict';
const fs = require('fs');
const vm = require('vm');

const file = process.argv[2];
const specAt = process.argv.indexOf('--spec');
const spec = specAt > 0 ? process.argv[specAt + 1] : null;
const html = fs.readFileSync(file, 'utf8');
const m = html.match(/<script type="text\/x-dc" data-dc-script data-props='([^']*)'>([\s\S]*?)<\/script>/);
if (!m) { console.error('no data-dc-script block'); process.exit(2); }
const props = JSON.parse(m[1]);
const ctx = { console: console, JSON: JSON, Math: Math, Object: Object, Array: Array, String: String, Set: Set, RegExp: RegExp,
  setTimeout: function () { return 1; }, clearTimeout: function () {} };
vm.createContext(ctx);
vm.runInContext('class DCLogic { constructor(props) { this.props = props; this.state = {}; } setState(s) { this.state = Object.assign({}, this.state, typeof s === "function" ? s(this.state) : s); } }\n' +
  m[2] + '\n;globalThis.__C = Component;', ctx);
const Component = ctx.__C;
const opt = function (k) { return (props[k] && props[k].options) || []; };

const strings = new Map();
function add(kind, text) {
  if (typeof text !== 'string' || !text.trim()) return;
  // The mockup narrates what VS Code does for an Open or Reveal action; the extension shows no such message.
  if (kind === 'message' && /^(Opens|Reveals) /.test(text)) return;
  const key = kind + '\u0000' + text;
  if (!strings.has(key)) strings.set(key, { kind: kind, text: text });
}
// The toast an action shows: the component's flash state after the call.
function toast(c) { return c.e().toast || null; }

for (const theme of opt('theme')) for (const scenario of opt('scenario')) for (const workspace of opt('workspace')) {
  const p = { theme: theme, scenario: scenario, sidebar: 'sections', workspace: workspace, overlay: 'none' };
  const out = new Component(p).renderVals();
  (out.fpanes || []).forEach(function (pane, pi) {
    add('pane title', pane.title);
    add('pane description', pane.desc);
    add('pane description tooltip', pane.descTitle);
    (pane.actions || []).forEach(function (a, ai) {
      add('pane action', a.label);
      add('pane action tooltip', a.title);
      const c = new Component(p);
      const fresh = c.renderVals().fpanes[pi].actions[ai];
      if (fresh && typeof fresh.run === 'function') { fresh.run(); add('message', toast(c)); }
      else if (fresh && typeof fresh.onClick === 'function') { fresh.onClick(); add('message', toast(c)); }
    });
    (pane.rows || []).forEach(function (r, ri) {
      // A tooltip that repeats the row's own description, or is the full path of its label, is that data shown again.
      const derived = r.title && ((r.desc && r.desc.indexOf(r.title) >= 0) || r.title === r.label || (r.label && r.title.endsWith('/' + r.label)));
      if (!derived) add('row tooltip', r.title);
      add('row action', r.actLabel);
      const c = new Component(p);
      const row = c.renderVals().fpanes[pi].rows[ri];
      if (row && typeof row.act === 'function') { row.act(); add('message', toast(c)); }
    });
  });
}

const list = Array.from(strings.values()).sort(function (a, b) { return (a.kind + a.text).localeCompare(b.kind + b.text); });
if (!spec) {
  list.forEach(function (s) { console.log(s.kind + ': ' + s.text); });
  process.exit(0);
}
const specText = fs.readFileSync(spec, 'utf8');
const spans = Array.from(specText.matchAll(/`([^`]+)`/g)).map(function (x) { return x[1]; });
const escape = function (t) { return t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); };
const templates = spans.filter(function (t) { return t.replace(/\{[^}]*\}/g, '').replace(/\s/g, '').length >= 1; })
  .map(function (t) { return new RegExp('^' + t.split(/\{[^}]*\}/).map(escape).join('[\\s\\S]+?') + '$'); });
const verbatim = new Set(spans);
const missing = list.filter(function (s) { return !verbatim.has(s.text) && !templates.some(function (re) { return re.test(s.text); }); });
console.log('strings: ' + list.length + ', in the SPEC: ' + (list.length - missing.length) + ', missing: ' + missing.length);
missing.forEach(function (s) { console.log('  missing ' + s.kind + ': ' + s.text); });
process.exit(missing.length ? 1 : 0);
