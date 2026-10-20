// Mockup check: renders Main.dc.html's Component for every combination of its data-props options
// (plus the control bar's scenario list and SDK source select), reports exceptions, top-level
// {{bindings}} that never resolve, exceptions thrown by handlers found in the render output, and
// a context menu left open on a target the view no longer shows (the pin file in the Explorer, a
// kit row in the Kits view), also after the scenario control switches under an open overlay.
// Usage: node design/spikes/mockup-check.js design/mockup/project/Main.dc.html [--handlers]
'use strict';
const fs = require('fs');
const vm = require('vm');

const file = process.argv[2];
const doHandlers = process.argv.indexOf('--handlers') >= 0;
const html = fs.readFileSync(file, 'utf8');
const m = html.match(/<script type="text\/x-dc" data-dc-script data-props='([^']*)'>([\s\S]*?)<\/script>/);
if (!m) { console.error('no data-dc-script block'); process.exit(2); }
const props = JSON.parse(m[1]);
const code = m[2];
const markup = html.slice(0, m.index);

const ctx = {
  console: console, JSON: JSON, Math: Math, Object: Object, Array: Array, String: String, Set: Set, RegExp: RegExp,
  setTimeout: function () { return 1; }, clearTimeout: function () {}
};
vm.createContext(ctx);
vm.runInContext('class DCLogic { constructor(props) { this.props = props; this.state = {}; } setState(s) { this.state = Object.assign({}, this.state, typeof s === "function" ? s(this.state) : s); } }\n' +
  code + '\n;globalThis.__C = Component; globalThis.__SCEN = typeof SCENARIOS !== "undefined" ? SCENARIOS.map(function (s) { return s[0]; }) : [];', ctx);
const Component = ctx.__C;

// Options: data-props enums, plus the control bar's scenario list and the SDK source select.
const opt = function (k) { return (props[k] && props[k].options) || []; };
const scen = Array.from(new Set(opt('scenario').concat(ctx.__SCEN)));
const srcSel = markup.match(/<select id="mk-src"[\s\S]*?<\/select>/);
const sources = srcSel ? Array.from(srcSel[0].matchAll(/<option value="([^"]+)"/g)).map(function (x) { return x[1]; }) : [null];
const dims = { theme: opt('theme'), scenario: scen, sidebar: opt('sidebar'), workspace: opt('workspace'), overlay: opt('overlay') };

// Top-level binding names in the markup, minus sc-for loop variables and literals.
const loopVars = new Set(Array.from(markup.matchAll(/<sc-for[^>]*\bas="([^"]+)"/g)).map(function (x) { return x[1]; }));
const bindings = new Set();
Array.from(markup.matchAll(/\{\{\s*([A-Za-z_$][\w$]*)/g)).forEach(function (x) {
  const n = x[1];
  if (!loopVars.has(n) && n !== 'true' && n !== 'false') bindings.add(n);
});

const seenKeys = new Set();
let combos = 0, renderErr = 0, handlerCalls = 0, handlerErr = 0;
const errSamples = [];
const handlerSamples = new Map();
function collectFns(v, path, out, depth) {
  if (depth > 6 || v == null) return;
  if (typeof v === 'function') { out.push(path); return; }
  if (Array.isArray(v)) { v.forEach(function (x, i) { collectFns(x, path.concat([i]), out, depth + 1); }); return; }
  if (typeof v === 'object') Object.keys(v).forEach(function (k) { collectFns(v[k], path.concat([k]), out, depth + 1); });
}
function at(v, path) { return path.reduce(function (o, k) { return o == null ? o : o[k]; }, v); }
const ev = { target: { value: '' }, key: 'Enter', preventDefault: function () {}, dataTransfer: null };

function make(p, src) {
  const c = new Component(p);
  if (src) c.state = Object.assign({}, c.state, { src: src });
  return c;
}

// A context menu open on a target the view does not show: the Explorer menu belongs to reviewers.toml in the tree,
// a kit menu to its kit's row.
const orphans = [];
function checkMenus(out, where) {
  const cm = out && out.cm;
  if (!cm || !cm.open) return;
  let shown = true;
  if (cm.label === 'Explorer context menu') shown = (out.tree || []).some(function (t) { return t.label === 'reviewers.toml'; });
  else if (/ kit context menu$/.test(cm.label)) {
    const kit = cm.label.replace(/ kit context menu$/, '');
    shown = (out.kitRows || []).some(function (r) { return r.kit === kit; });
  }
  if (!shown && orphans.length < 10) orphans.push(where + ': ' + cm.label);
  else if (!shown) orphans.push(where);
}
for (const theme of dims.theme) for (const scenario of dims.scenario) for (const sidebar of dims.sidebar)
for (const workspace of dims.workspace) for (const overlay of dims.overlay) for (const src of sources) {
  combos++;
  const p = { theme: theme, scenario: scenario, sidebar: sidebar, workspace: workspace, overlay: overlay };
  let out;
  try { out = make(p, src).renderVals(); Object.keys(out).forEach(function (k) { seenKeys.add(k); }); }
  catch (err) { renderErr++; if (errSamples.length < 10) errSamples.push(JSON.stringify(p) + ' src=' + src + ': ' + err.stack.split('\n').slice(0, 3).join(' | ')); continue; }
  checkMenus(out, JSON.stringify(p) + ' src=' + src);
  // Under an open overlay, the scenario control switched to each scenario.
  if (doHandlers && overlay !== 'none' && theme === dims.theme[0] && src === sources[0]) {
    for (const s of dims.scenario) {
      const c = make(p, src);
      const v = c.renderVals();
      if (typeof v.setScenario !== 'function') break;
      try { v.setScenario({ target: { value: s } }); checkMenus(c.renderVals(), JSON.stringify(p) + ' then scenario ' + s); }
      catch (err) { handlerErr++; }
    }
  }
  // Handlers: first theme and source, every scenario, sidebar and workspace with no overlay, and every overlay on ready.
  if (!doHandlers || theme !== dims.theme[0] || src !== sources[0] || (overlay !== 'none' && scenario !== 'ready')) continue;
  const fns = [];
  collectFns(out, [], fns, 0);
  for (const path of fns) {
    const c = make(p, src);
    const cur = c.renderVals();
    const fn = at(cur, path);
    if (typeof fn !== 'function') continue;
    handlerCalls++;
    try { fn(ev); checkMenus(c.renderVals(), JSON.stringify(p) + ' after ' + path.join('.')); }
    catch (err) {
      handlerErr++;
      const key = path.filter(function (x) { return typeof x === 'string'; }).join('.') + ': ' + err.message;
      if (!handlerSamples.has(key)) handlerSamples.set(key, JSON.stringify(p) + ' src=' + src + ' path=' + path.join('.') + ': ' + err.stack.split('\n').slice(0, 2).join(' | '));
    }
  }
}
const unresolved = Array.from(bindings).filter(function (b) { return !seenKeys.has(b); }).sort();
console.log('file: ' + file);
console.log('dims: theme ' + dims.theme.length + ', scenario ' + dims.scenario.length + ', sidebar ' + dims.sidebar.length + ', workspace ' + dims.workspace.length + ', overlay ' + dims.overlay.length + ', source ' + sources.length + ' (' + sources.join(',') + ')');
console.log('combinations: ' + combos + ', render exceptions: ' + renderErr);
errSamples.forEach(function (s) { console.log('  ' + s); });
console.log('top-level bindings: ' + bindings.size + ', never resolved: ' + (unresolved.length ? unresolved.join(', ') : 'none'));
if (doHandlers) {
  console.log('handler calls: ' + handlerCalls + ', handler exceptions: ' + handlerErr + ' (' + handlerSamples.size + ' distinct)');
  Array.from(handlerSamples.values()).slice(0, 20).forEach(function (s) { console.log('  ' + s); });
}
console.log('menus open on a missing target: ' + orphans.length);
orphans.slice(0, 10).forEach(function (s) { console.log('  ' + s); });
process.exit(renderErr || unresolved.length || orphans.length ? 1 : 0);
