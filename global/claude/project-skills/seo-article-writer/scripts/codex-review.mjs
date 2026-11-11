#!/usr/bin/env node
// Independent review of an article by OpenAI Codex CLI (read-only sandbox, live web search).
// Usage: node codex-review.mjs --article <draft.md> --brief <00-brief.md> [--ledger <claims.md>]
//        [--out <03-codex-review.json>] [--model <name>] [--effort high] [--project seo-article-writer.json]
// The reviewer model is pinned. With "reviewer_pins" in the project file, the TOML pin file is the only source
// of model and effort; otherwise "codex.model"/"codex.effort" or --model. Without a pin the script refuses to
// run when a project file is given (reviews must be reproducible), and warns otherwise.
// Writes the structured review JSON to --out (default: codex-review.json next to the article)
// and prints a short summary. Exit code: 0 pass, 3 revise, 4 block, 1 error.

import { spawn } from 'node:child_process';
import { readFileSync, existsSync, mkdtempSync, rmSync } from 'node:fs';
import { dirname, join, resolve, basename, delimiter } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
const opt = (name, fallback) => {
  const i = args.indexOf(`--${name}`);
  return i >= 0 ? args[i + 1] : fallback;
};

const article = opt('article');
const brief = opt('brief');
const ledger = opt('ledger');
if (!article || !brief || !existsSync(article) || !existsSync(brief)) {
  console.error('Usage: node codex-review.mjs --article <draft.md> --brief <brief.md> [--ledger <claims.md>] [--out <file.json>]');
  process.exit(1);
}
const out = resolve(opt('out', join(dirname(article), 'codex-review.json')));
const project = opt('project') ? JSON.parse(readFileSync(opt('project'), 'utf8')) : null;
// Reviewer pin. When the project file names "reviewer_pins" (a TOML file with a [reviewers.codex] section,
// such as .conclave/reviewers.toml), that file is the only source of the model and effort: a different --model
// or --effort, or a "codex" block in the project file that disagrees with it, is refused, so the skill cannot
// drift from the repository's reviewer. Without reviewer_pins, "codex": {"model", "effort"} or --model is used.
function readPin() {
  if (!project?.reviewer_pins) return null;
  const file = resolve(dirname(resolve(opt('project'))), project.reviewer_pins);
  if (!existsSync(file)) { console.error(`reviewer_pins file not found: ${file}`); process.exit(1); }
  const section = project.reviewer_pins_section || 'reviewers.codex';
  const toml = readFileSync(file, 'utf8').replace(/\r\n/g, '\n');
  const esc = section.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const body = toml.match(new RegExp(`^\\[${esc}\\][ \\t]*(?:#.*)?$([\\s\\S]*?)(?=^\\[|(?![\\s\\S]))`, 'm'))?.[1];
  const field = (name) => body?.match(new RegExp(`^[ \\t]*${name}[ \\t]*=[ \\t]*"([^"]+)"`, 'm'))?.[1];
  const pin = { file, model: field('model'), effort: field('effort') };
  if (!pin.model || !pin.effort) { console.error(`${file} has no [${section}] model and effort.`); process.exit(1); }
  for (const [flag, value] of [['model', pin.model], ['effort', pin.effort]]) {
    if (opt(flag) && opt(flag) !== value) { console.error(`--${flag} ${opt(flag)} differs from the pinned ${value} (${file}).`); process.exit(1); }
    if (project.codex?.[flag] && project.codex[flag] !== value) { console.error(`Project file codex.${flag} "${project.codex[flag]}" differs from the pinned ${value} (${file}). Remove it; the pin file is the only source.`); process.exit(1); }
  }
  return pin;
}
const pin = readPin();
const effort = pin?.effort || opt('effort', project?.codex?.effort || 'high');
const model = pin?.model || opt('model', project?.codex?.model);
if (!model) {
  if (project) {
    console.error('No reviewer model pinned. Set "reviewer_pins" (a TOML pin file) or "codex": {"model": "..."} in the project file, or pass --model.');
    process.exit(1);
  }
  console.error('Warning: no --model given; Codex will use its configured default, so reviews are not reproducible.');
}
if (!['minimal', 'low', 'medium', 'high', 'xhigh'].includes(effort)) {
  console.error(`--effort must be minimal, low, medium, high or xhigh (got "${effort}").`);
  process.exit(1);
}
if (model && !/^[\w.:-]+$/.test(model)) {
  console.error(`--model contains unexpected characters: "${model}".`);
  process.exit(1);
}

// Find the Codex executable without going through a shell. On Windows, npm installs a codex.cmd
// launcher next to node_modules/@openai/codex/bin/codex.js; run that file with this Node instead.
function resolveCodex() {
  const dirs = (process.env.PATH || '').split(delimiter).filter(Boolean);
  if (process.platform === 'win32') {
    for (const d of dirs) {
      const entry = join(d, 'node_modules', '@openai', 'codex', 'bin', 'codex.js');
      if (existsSync(join(d, 'codex.cmd')) && existsSync(entry)) return { cmd: process.execPath, pre: [entry] };
      if (existsSync(join(d, 'codex.exe'))) return { cmd: join(d, 'codex.exe'), pre: [] };
    }
    return null;
  }
  for (const d of dirs) if (existsSync(join(d, 'codex'))) return { cmd: join(d, 'codex'), pre: [] };
  return null;
}
const codex = resolveCodex();
if (!codex) {
  console.error('Codex CLI not found on PATH. Install it and run "codex login".');
  process.exit(1);
}

const prompt = readFileSync(join(here, '..', 'references', 'codex-review-prompt.md'), 'utf8');
const section = (label, path) => `\n===== ${label}: ${basename(path)} =====\n${readFileSync(path, 'utf8')}\n`;
const material = section('BRIEF', brief) + section('ARTICLE', article) + (ledger && existsSync(ledger) ? section('CLAIMS LEDGER', ledger) : '');

// Codex reads the prompt from stdin when the prompt argument is "-".
// Read-only sandbox: the reviewer can search the web and read files but cannot change anything.
const work = mkdtempSync(join(tmpdir(), 'codex-review-'));
const codexArgs = [
  '--search', 'exec',
  '-s', 'read-only',
  '--skip-git-repo-check',
  '--ephemeral',
  '-C', work,
  '--output-schema', join(here, 'codex-review.schema.json'),
  '-o', out,
  '-c', `model_reasoning_effort=${effort}`,
  ...(model ? ['-m', model] : []),
  '-',
];

console.error(`Running Codex review (model ${model || "default"}, effort ${effort}) on ${article} ...`);
const child = spawn(codex.cmd, [...codex.pre, ...codexArgs], { shell: false, stdio: ['pipe', 'ignore', 'pipe'] });
let stderr = '';
child.stderr.on('data', (d) => { stderr += d; });
child.stdin.end(`${prompt}\n<stdin>\n${material}\n</stdin>\n`);
child.on('close', (code) => {
  rmSync(work, { recursive: true, force: true });
  if (code !== 0 || !existsSync(out)) {
    console.error(`Codex exited with code ${code}.`);
    console.error(stderr.split('\n').slice(-15).join('\n'));
    process.exit(1);
  }
  let review;
  try {
    review = JSON.parse(readFileSync(out, 'utf8'));
  } catch {
    console.error(`Codex output in ${out} is not valid JSON.`);
    process.exit(1);
  }
  const count = (s) => review.findings.filter((f) => f.severity === s).length;
  console.log(`Verdict: ${review.verdict}  (critical ${count('critical')}, major ${count('major')}, minor ${count('minor')}; claims checked ${review.claims_checked})`);
  console.log(review.summary);
  console.log(`Full review: ${out}`);
  process.exit(review.verdict === 'pass' ? 0 : review.verdict === 'revise' ? 3 : 4);
});
