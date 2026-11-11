#!/usr/bin/env node
// Deterministic checks for an article written in Markdown.
// Usage: node lint-article.mjs <article.md> [--keyphrase "focus keyphrase"] [--seo seo.json]
//        [--site example.com] [--project seo-article-writer.json] [--json]
// --project applies the project's house rules (opening length, description length, image formats,
// FAQ count); house rules fail as errors, the skill's own defaults only warn.
// Exit code 1 when any error (hard fail) is found, otherwise 0.
// Plain Node, no dependencies, so the skill works in any repository.

import { readFileSync } from 'node:fs';

// ---------- arguments ----------
const args = process.argv.slice(2);
const opt = (name) => {
  const i = args.indexOf(`--${name}`);
  return i >= 0 ? args[i + 1] : undefined;
};
const valued = new Set(['--keyphrase', '--seo', '--site', '--project']);
let file;
for (let i = 0; i < args.length; i++) {
  if (valued.has(args[i])) { i++; continue; }
  if (!args[i].startsWith('--')) { file = args[i]; break; }
}
if (!file) {
  console.error('Usage: node lint-article.mjs <article.md> [--keyphrase "..."] [--seo seo.json] [--site example.com] [--project project.json] [--json]');
  process.exit(2);
}
const asJson = args.includes('--json');
const site = (opt('site') || '').replace(/^https?:\/\//, '').replace(/\/.*$/, '').toLowerCase();
let seo;
if (opt('seo')) seo = JSON.parse(readFileSync(opt('seo'), 'utf8'));
const keyphrase = (opt('keyphrase') || seo?.aioseo?.focus_keyphrase || '').trim();
const project = opt('project') ? JSON.parse(readFileSync(opt('project'), 'utf8')) : null;
const house = project?.rules || {};

// ---------- thresholds (tuned to the references; change here, not inline) ----------
const T = {
  aiVocabDistinctPer1000: 3,
  boldPerSection: 1,
  paragraphWordsMax: 120,     // TruSEO flags paragraphs over 150 words; stay under
  sectionWordsMax: 300,       // TruSEO subheading distribution
  longSentenceWords: 20,
  longSentenceShareMax: 0.25, // TruSEO sentence length
  passiveShareMax: 0.10,      // TruSEO passive voice
  fleschMin: 60,              // general readability target (TruSEO 2.0 has no Flesch check)
  transitionShareMin: 0.3,    // TruSEO transition words, texts over 200 words
  uniformRun: 5,              // consecutive sentences within +-3 words of each other
  sameStartRun: 3,            // TruSEO consecutive sentences starting with the same word
  densityMin: 0.5,            // TruSEO: keyphrase occurrences per 100 words
  densityMax: 3,
  titleMinPx: 400,            // TruSEO title width band
  titleMaxPx: 600,
  descMinChars: house.meta_description_min ?? 120,
  descMaxChars: house.meta_description_max ?? 155, // Google truncates by pixel width, around 155-160 characters
  openingWords: house.opening_words ?? [40, 60],    // the direct answer under the H1
  imageFormats: house.image_formats ?? ['webp', 'avif', 'jpg', 'jpeg', 'png'],
  faqQuestions: house.faq_questions ?? null,        // e.g. [3, 6] when the house standard requires an FAQ
  minWords: 300,
};
// House rules are hard requirements; the skill's own defaults are advice.
const houseLevel = (key) => (house[key] !== undefined ? 'error' : 'warn');

// ---------- read and parse ----------
let raw = readFileSync(file, 'utf8');
const findings = [];
const add = (level, rule, message, where) => findings.push({ level, rule, message, ...(where ? { where } : {}) });

// strip YAML front matter
let frontMatter = '';
if (raw.startsWith('---')) {
  const end = raw.indexOf('\n---', 3);
  if (end > 0) { frontMatter = raw.slice(0, end + 4); raw = raw.slice(end + 4); }
}
// drop fenced code and HTML comments from prose analysis
const noCode = raw.replace(/```[\s\S]*?```/g, '').replace(/<!--[\s\S]*?-->/g, '');
const lines = noCode.split(/\r?\n/);

const headings = []; // {level, text, line}
const blocks = [];   // {type: p|li|quote|table, text, section}
let section = 0;
let para = [];
const flushPara = () => { if (para.length) { blocks.push({ type: 'p', text: para.join(' '), section }); para = []; } };
lines.forEach((line, idx) => {
  const h = line.match(/^(#{1,6})\s+(.*?)\s*#*\s*$/);
  if (h) { flushPara(); section++; headings.push({ level: h[1].length, text: h[2], line: idx + 1, section }); return; }
  if (/^\s*$/.test(line)) { flushPara(); return; }
  if (/^\s*\|/.test(line)) { flushPara(); blocks.push({ type: 'table', text: line, section }); return; }
  if (/^\s*([-*+]|\d+[.)])\s+/.test(line)) { flushPara(); blocks.push({ type: 'li', text: line.replace(/^\s*([-*+]|\d+[.)])\s+/, ''), section }); return; }
  if (/^\s*>/.test(line)) { flushPara(); blocks.push({ type: 'quote', text: line.replace(/^\s*>\s?/, ''), section }); return; }
  para.push(line.trim());
});
flushPara();

// plain text helpers
const stripMd = (s) => s
  .replace(/!\[([^\]]*)\]\([^)]*\)/g, '')
  .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
  .replace(/<[^>]+>/g, '')
  .replace(/[*_`~]/g, '');
const prose = blocks.filter((b) => b.type !== 'table').map((b) => stripMd(b.text));
const bodyText = prose.join('\n');
const words = (s) => (s.match(/[A-Za-z0-9À-ɏ'’-]+/g) || []);
const allWords = words(bodyText);
const wc = allWords.length || 1;
const per1000 = (n) => (n * 1000) / wc;
const splitSentences = (s) => s
  .replace(/\b(e\.g|i\.e|etc|vs|Mr|Mrs|Ms|Dr|St|No|Inc|Ltd)\./g, '$1')
  .split(/(?<=[.!?])\s+(?=[A-Z0-9"“'‘(])/)
  .map((x) => x.trim())
  .filter((x) => words(x).length > 0);
const sentences = prose.flatMap(splitSentences);
const lineOf = (needle) => {
  const i = raw.indexOf(needle);
  return i < 0 ? undefined : `line ${raw.slice(0, i).split('\n').length + (frontMatter ? frontMatter.split('\n').length - 1 : 0)}`;
};

// ---------- 1. hard fails ----------
// No dashes as punctuation anywhere: em dash, en dash, horizontal bar, figure dash, "--", or a spaced hyphen used as a dash.
// Hyphens inside words and ranges written with a plain hyphen (120-160) are fine.
const DASH = /[—–―‒]|(?<=\S) ?-- ?(?=\S)|(?<=\S) - (?=\S)/;
const hardPatterns = [
  ['tool-artefact', /contentReference|oaicite|turn\d+search\d+|attributableIndex|\[cite:\s*\d+\]|grok_card|ppl-ai-file|utm_source=(chatgpt|openai|perplexity|copilot|gemini|claude)/i],
  ['placeholder', /\[CHECK\]|INSERT_|\bTODO\b|\bTBD\b|(?<!!)\[(Describe|Add|Insert|Your|Link|Source)\b[^\]]*\](?!\()|\b(19|20)\d\d-XX-XX\b|\(add (url|link|source) here\)|lorem ipsum/i],
  ['assistant-residue', /\bAs an AI\b|my (last )?knowledge (update|cutoff)|\bI hope this helps\b|^\s*(Certainly|Sure|Absolutely)[!,.]|\bHere(?:'|’)s (a|an|the) (revised|updated|draft|rewritten)/im],
];
// Reader calls to action ("let me know in the comments") are legitimate in blogs; flag them for a look only.
const residueSoft = raw.match(/\b(let me know|would you like)\b/i);
if (residueSoft) add('info', 'assistant-residue-soft', `Found "${residueSoft[0]}". Fine as a reader call to action; delete if it addresses the person who requested the article.`);
for (const [rule, re] of hardPatterns) {
  const m = raw.match(re);
  if (m) add('error', rule, `Found "${m[0]}". Remove before any review.`, lineOf(m[0]));
}
// Publishable metadata (SEO title, description, social text, alt text, captions, FAQ schema) gets the same scan.
if (seo) {
  const strings = [];
  const walk = (v, path) => {
    if (typeof v === 'string') strings.push([path, v]);
    else if (v && typeof v === 'object') for (const [k, x] of Object.entries(v)) walk(x, path ? `${path}.${k}` : k);
  };
  walk({ post: seo.post, aioseo: seo.aioseo }, '');
  for (const [path, value] of strings) {
    for (const [rule, re] of hardPatterns) {
      const m = value.match(re);
      if (m) add('error', `${rule}-metadata`, `seo.json ${path} contains "${m[0]}".`);
    }
    if (/[​-‏⁠-⁤﻿­]|[\u{E0000}-\u{E007F}]/u.test(value)) add('error', 'invisible-characters-metadata', `seo.json ${path} contains invisible characters.`);
    const d = value.match(DASH);
    if (d) add('error', 'dash-metadata', `seo.json ${path} contains a dash ("${d[0].trim()}"). Use a comma, colon, full stop or parentheses; use a hyphen or "to" for ranges.`);
  }
}
const invisible = raw.match(/[​-‏⁠-⁤﻿­]|[\u{E0000}-\u{E007F}]/gu);
if (invisible) add('error', 'invisible-characters', `${invisible.length} invisible or zero-width character(s). Remove them.`);
const homoglyph = raw.match(/\b(?=[A-Za-z]*[Ѐ-ӿͰ-Ͽ])(?=[Ѐ-ӿͰ-Ͽ]*[A-Za-z])[A-Za-zЀ-ӿͰ-Ͽ]+\b/u);
if (homoglyph) add('error', 'homoglyph', `Word mixes Latin with Cyrillic or Greek letters: "${homoglyph[0]}".`, lineOf(homoglyph[0]));
if (raw.normalize('NFKC') !== raw) {
  const diff = [...raw].filter((c) => c.normalize('NFKC') !== c && !/[’‘“”…–—]/.test(c));
  if (diff.length) add('warn', 'unicode-compat', `${diff.length} compatibility character(s) change under NFKC normalisation (e.g. "${diff[0]}"). Use plain characters.`);
}

// ---------- 2. AI-writing patterns ----------
const aiVocab = ['additionally', 'align with', 'aligns with', 'bolster', 'bolstered', 'crucial', 'deep dive', 'delve', 'delves', 'delving', 'enduring', 'enhance', 'enhances', 'enhancing', 'foster', 'fosters', 'fostering', 'garner', 'garnered', 'highlights', 'highlighting', 'interplay', 'intricate', 'intricacies', 'landscape', 'meticulous', 'meticulously', 'navigate', 'navigating', 'pivotal', 'realm', 'robust', 'seamless', 'seamlessly', 'showcase', 'showcases', 'showcasing', 'tapestry', 'testament', 'underscore', 'underscores', 'underscoring', 'unlock', 'unleash', 'elevate', 'empower', 'leverage', 'leveraging', 'valuable', 'vibrant', 'game-changer', 'game changer', 'cutting-edge', 'ever-evolving', "in today's", 'embark', 'commendable', 'notably', 'paramount', 'multifaceted', 'nuanced', 'holistic', 'synergy', 'transformative'];
const lowerBody = bodyText.toLowerCase();
const vocabHits = {};
for (const w of aiVocab) {
  const re = new RegExp(`(?<![a-z])${w.replace(/[-’']/g, '[-’\' ]?')}(?![a-z])`, 'g');
  const n = (lowerBody.match(re) || []).length;
  if (n) vocabHits[w] = n;
}
const distinct = Object.keys(vocabHits).length;
if (per1000(distinct) > T.aiVocabDistinctPer1000) {
  add('warn', 'ai-vocabulary', `${distinct} distinct AI-associated words (${per1000(distinct).toFixed(1)} per 1,000 words; limit ${T.aiVocabDistinctPer1000}): ${Object.entries(vocabHits).map(([w, n]) => `${w}×${n}`).join(', ')}. Replace with plain words or specific facts.`);
} else if (distinct) {
  add('info', 'ai-vocabulary', `AI-associated words present (under the cluster limit): ${Object.entries(vocabHits).map(([w, n]) => `${w}×${n}`).join(', ')}.`);
}

const patternChecks = [
  ['significance-inflation', /\b(stands as|serves as|is a testament|a testament to|plays? an? (crucial|pivotal|vital|key|significant) role|underscores? (its|the) importance|reflects broader|setting the stage|evolving landscape|indelible mark|deeply rooted|cannot be overstated)\b/gi, 'State the concrete consequence instead.'],
  ['ing-tail', /,\s(highlighting|underscoring|emphasizing|emphasising|ensuring|reflecting|symbolizing|symbolising|contributing to|fostering|cultivating|showcasing|enhancing|paving the way)\b/gi, 'Cut the trailing clause or make it a sentence with evidence.'],
  ['vague-attribution', /\b(experts (say|argue|agree|believe|suggest)|studies (show|suggest|have shown)|research (shows|suggests|has shown)|observers (note|say)|critics (say|argue)|industry reports|many (people|experts) (say|believe)|it is (widely|generally) (believed|accepted))\b/gi, 'Name the source with date and link, or delete.'],
  ['negative-parallelism', /\b(not only\b.{1,80}?\bbut( also)?|it(?:'|’)s not (just )?[^.]{1,40}?, it(?:'|’)s|isn(?:'|’)t (just )?about [^.]{1,40}?, it(?:'|’)s)\b/gi, 'State the positive claim directly.'],
  ['hedge-disclaimer', /\b(it(?:'|’)s (important|worth|crucial) to (note|remember|consider|mention)|it is (important|worth|crucial) to (note|remember|consider)|worth noting|results may vary|while specific details|based on (the )?available information|not widely documented)\b/gi, 'Delete, or state the caveat specifically.'],
  ['formula-conclusion', /(^|\n)\s*(In conclusion|In summary|To sum up|Overall|Ultimately|All in all)[,:]|\bDespite (these|its|the) challenges\b/gi, 'End on the last useful point instead of a summary.'],
  ['promotional', /\b(boasts|nestled|in the heart of|groundbreaking|renowned|world-class|state-of-the-art|unparalleled|breathtaking|must-have|second to none|best-in-class)\b/gi, 'Replace with a checkable fact.'],
  ['copula-avoidance', /\b(serves as|stands as|functions as)\b/gi, 'Use "is" or "has".'],
  ['scaffolding', /\b(in this (article|post|guide),? (we|you)(?:'|’)?(ll| will)|let(?:'|’)s (dive|delve|explore|take a (closer )?look)|without further ado|buckle up|read on to (find out|learn))\b/gi, 'Cut the signposting and start with the substance.'],
];
for (const [rule, re, fix] of patternChecks) {
  const hits = bodyText.match(re);
  if (hits) add(hits.length > 1 ? 'warn' : 'info', rule, `${hits.length}× (${[...new Set(hits.map((h) => h.trim()))].slice(0, 5).map((h) => `"${h}"`).join(', ')}). ${fix}`);
}

// Dashes: zero allowed in headings, body, lists, tables, quotes and alt text (code excluded).
const dashText = noCode.replace(/`[^`\n]*`/g, '').replace(/\]\([^)]*\)/g, ']');
const dashHits = dashText.split(/\r?\n/).filter((l) => DASH.test(l));
const emDashes = dashHits.reduce((n, l) => n + (l.match(new RegExp(DASH.source, 'g')) || []).length, 0);
if (emDashes) add('error', 'dash', `${emDashes} dash(es) used as punctuation (none allowed). Rewrite with a comma, colon, full stop or parentheses; use a hyphen or "to" for ranges. First: "${dashHits[0].trim().slice(0, 80)}"`, lineOf(dashHits[0].trim().slice(0, 40)));

const triplets = (bodyText.match(/\b\w+(?: \w+)?, \w+(?: \w+)?,? and \w+(?: \w+)?\b/g) || []).length;
if (per1000(triplets) > 4) add('warn', 'rule-of-three', `${triplets} "X, Y and Z" lists (${per1000(triplets).toFixed(1)} per 1,000 words). Keep only the items that are true and develop them.`);

const openers = blocks.filter((b) => b.type === 'p' && /^(Additionally|Furthermore|Moreover|In addition|Notably|Importantly)\b/.test(stripMd(b.text).trim()));
if (openers.length) add('warn', 'paragraph-opener', `${openers.length} paragraph(s) open with Additionally/Furthermore/Moreover/Notably. Start with the subject.`);

// uniform sentence lengths
let run = 1; let worstRun = 1;
for (let i = 1; i < sentences.length; i++) {
  if (Math.abs(words(sentences[i]).length - words(sentences[i - 1]).length) <= 3) { run++; worstRun = Math.max(worstRun, run); } else run = 1;
}
if (worstRun >= T.uniformRun) add('warn', 'uniform-rhythm', `${worstRun} consecutive sentences of near-equal length. Let rhythm follow the content.`);
const lens = sentences.map((s) => words(s).length);
const mean = lens.reduce((a, b) => a + b, 0) / (lens.length || 1);
const sd = Math.sqrt(lens.reduce((a, b) => a + (b - mean) ** 2, 0) / (lens.length || 1));

// ---------- 3. structure ----------
const h1s = headings.filter((h) => h.level === 1);
if (h1s.length !== 1) add('error', 'h1', `Expected exactly one H1 (the post title); found ${h1s.length}.`);
let prevLevel = 1;
for (const h of headings) {
  if (h.level > prevLevel + 1) add('error', 'heading-skip', `"${h.text}" jumps from H${prevLevel} to H${h.level}.`, `line ${h.line}`);
  prevLevel = h.level;
  if (/\p{Extended_Pictographic}/u.test(h.text)) add('warn', 'heading-emoji', `Emoji in heading "${h.text}".`, `line ${h.line}`);
  const ws = h.text.split(/\s+/).filter((w) => /^[A-Za-z]/.test(w));
  const minor = /^(a|an|and|as|at|but|by|for|in|of|on|or|the|to|vs|with|via|from|into)$/i;
  const capsAfterFirst = ws.slice(1).filter((w) => !minor.test(w));
  if (h.level > 1 && capsAfterFirst.length >= 3 && capsAfterFirst.every((w) => /^[A-Z]/.test(w))) add('info', 'title-case-heading', `"${h.text}" looks like Title Case; use sentence case unless the site style requires it.`, `line ${h.line}`);
  if (/^(conclusion|key takeaways|final thoughts|wrapping up|challenges and (the )?future( outlook)?)$/i.test(h.text.trim())) add('warn', 'formula-heading', `Heading "${h.text}" is a template section. Use a heading that says what the section delivers, or cut it.`, `line ${h.line}`);
}
const sectionWords = {};
blocks.forEach((b) => { sectionWords[b.section] = (sectionWords[b.section] || 0) + words(stripMd(b.text)).length; });
for (const h of headings) {
  if ((sectionWords[h.section] || 0) > T.sectionWordsMax) add('warn', 'section-length', `Section "${h.text}" runs ${sectionWords[h.section]} words without a subheading (limit ${T.sectionWordsMax}).`, `line ${h.line}`);
}
blocks.filter((b) => b.type === 'p').forEach((b) => {
  const n = words(stripMd(b.text)).length;
  if (n > T.paragraphWordsMax) add('warn', 'paragraph-length', `Paragraph of ${n} words (limit ${T.paragraphWordsMax}): "${stripMd(b.text).slice(0, 60)}..."`);
});
const boldBySection = {};
blocks.filter((b) => b.type === 'p').forEach((b) => { boldBySection[b.section] = (boldBySection[b.section] || 0) + (b.text.match(/\*\*[^*]+\*\*|__[^_]+__/g) || []).length; });
const boldHeavy = Object.entries(boldBySection).filter(([, n]) => n > T.boldPerSection).length;
if (boldHeavy) add('warn', 'bold-overuse', `${boldHeavy} section(s) use bold more than ${T.boldPerSection}× in body paragraphs.`);
const inlineHeaderBullets = blocks.filter((b) => b.type === 'li' && /^\*\*[^*]+:?\*\*:?\s/.test(b.text)).length;
if (inlineHeaderBullets >= 4) add('warn', 'inline-header-bullets', `${inlineHeaderBullets} bullets start with a bold label. Prefer prose or a table.`);
const liWords = blocks.filter((b) => b.type === 'li').reduce((a, b) => a + words(stripMd(b.text)).length, 0);
if (liWords / wc > 0.4) add('warn', 'list-heavy', `${Math.round((liWords / wc) * 100)}% of the words are in bullet lists. Keep lists for parallel items.`);
const emojiBody = bodyText.match(/\p{Extended_Pictographic}/gu);
if (emojiBody) add('warn', 'emoji', `${emojiBody.length} emoji in body text.`);

// links and images
const links = [...raw.matchAll(/(?<!!)\[([^\]]+)\]\(((?:[^()\s]|\([^()\s]*\))+)(?:\s+"[^"]*")?\)/g)].map((m) => ({ text: m[1], url: m[2] }));
const isInternal = (u) => u.startsWith('/') || u.startsWith('#') || (site && new RegExp(`^https?://([a-z0-9-]+\\.)*${site.replace(/\./g, '\\.')}`, 'i').test(u));
const internal = links.filter((l) => isInternal(l.url));
const external = links.filter((l) => /^https?:/i.test(l.url) && !isInternal(l.url));
if (!internal.length) add('warn', 'internal-links', 'No internal links. Link to related posts with descriptive anchors.');
if (!external.length) add('warn', 'external-links', 'No external links. Cite primary sources for key claims.');
const badAnchors = links.filter((l) => /^(click here|here|read more|this|this link|learn more|more|link)$/i.test(l.text.trim()));
if (badAnchors.length) add('warn', 'anchor-text', `${badAnchors.length} non-descriptive anchor(s): ${badAnchors.map((l) => `"${l.text}"`).join(', ')}.`);
const images = [...raw.matchAll(/!\[([^\]]*)\]\(([^)\s]+)/g)].map((m) => ({ alt: m[1], src: m[2] }));
const noAlt = images.filter((i) => !i.alt.trim());
if (noAlt.length) add('warn', 'image-alt', `${noAlt.length} image(s) without alt text (decorative images may be intentional).`);
images.filter((i) => i.alt.length > 125).forEach((i) => add('info', 'image-alt-length', `Alt text over 125 characters: "${i.alt.slice(0, 50)}..."`));

// opening: the direct answer right under the H1. Like common article checkers, skip short lines such as a
// byline or date (under 15 words) and count whitespace-separated words, so the linter and a house checker agree.
const countWords = (s) => (s.trim() ? s.trim().split(/\s+/).length : 0);
const opening = blocks.find((b) => b.type === 'p' && b.section === (h1s[0]?.section ?? 1) && countWords(stripMd(b.text)) >= 15);
if (!opening) add('warn', 'opening', 'No paragraph of 15+ words directly under the H1. Open with the direct answer.');
else {
  const n = countWords(stripMd(opening.text));
  const [lo, hi] = T.openingWords;
  if (n < lo || n > hi) add(houseLevel('opening_words'), 'opening-length', `Opening paragraph is ${n} words; the direct answer should be ${lo}-${hi} words.`);
}

// image formats (body images and the featured image)
const extOf = (src) => (src.split(/[?#]/)[0].match(/\.([a-z0-9]+)$/i)?.[1] || '').toLowerCase();
const imageFiles = [...images.map((i) => i.src), ...(seo?.post?.featured_image?.file ? [seo.post.featured_image.file] : [])];
const badFormat = imageFiles.filter((f) => extOf(f) && !T.imageFormats.includes(extOf(f)));
if (badFormat.length) add(houseLevel('image_formats'), 'image-format', `Image format not allowed (${T.imageFormats.join(', ')}): ${badFormat.join(', ')}`);

// FAQ section: count H3 questions under an H2 named FAQ / Frequently asked questions
const faqH2 = headings.find((h) => h.level === 2 && /^(faqs?|frequently asked questions)\b/i.test(h.text.trim()));
const faqQs = faqH2 ? headings.filter((h) => h.line > faqH2.line && h.level === 3 && !headings.some((x) => x.level <= 2 && x.line > faqH2.line && x.line < h.line)) : [];
if (T.faqQuestions) {
  const [lo, hi] = T.faqQuestions;
  if (faqQs.length < lo || faqQs.length > hi) add('error', 'faq-count', `${faqH2 ? `FAQ has ${faqQs.length} question(s)` : 'No FAQ section'}; the house standard asks for ${lo}-${hi} real questions.`);
}
faqQs.filter((h) => !/\?\s*$/.test(h.text)).forEach((h) => add('info', 'faq-question-form', `FAQ heading is not phrased as a question: "${h.text}"`, `line ${h.line}`));

// no AI-assistance disclosure lines (house rule)
const aiLine = bodyText.match(/\b(this (article|post|guide) (was|has been) (written|created|generated|drafted|produced) (with|using|by|with the help of)[^.]{0,40}\b(AI|artificial intelligence|ChatGPT|Claude|Codex|an? (AI|language model)))|\bAI[- ]assisted\b|\bwritten with (the )?(help|assistance) of (AI|artificial intelligence)\b/i);
if (aiLine) add('error', 'ai-disclosure', `Found an AI-assistance line ("${aiLine[0]}"). The house style does not use these; remove it.`);

// ---------- 4. readability ----------
const syllables = (w) => {
  w = w.toLowerCase().replace(/[^a-z]/g, '');
  if (w.length <= 3) return 1;
  w = w.replace(/(?:[^laeiouy]es|ed|[^laeiouy]e)$/, '').replace(/^y/, '');
  return Math.max(1, (w.match(/[aeiouy]{1,2}/g) || []).length);
};
const syl = allWords.reduce((a, w) => a + syllables(w), 0);
const flesch = 206.835 - 1.015 * (wc / (sentences.length || 1)) - 84.6 * (syl / wc);
if (flesch < T.fleschMin) add('info', 'flesch', `Flesch reading ease ${flesch.toFixed(0)} (general target ${T.fleschMin}+; not an AIOSEO check). Shorter sentences and plainer words raise it; do not dumb down technical terms.`);
const longShare = lens.filter((n) => n > T.longSentenceWords).length / (lens.length || 1);
if (longShare > T.longSentenceShareMax) add('info', 'long-sentences', `${Math.round(longShare * 100)}% of sentences exceed ${T.longSentenceWords} words (AIOSEO target ${Math.round(T.longSentenceShareMax * 100)}% or less).`);
const irregular = 'been|born|built|bought|brought|caught|chosen|done|drawn|driven|found|given|gone|grown|held|hidden|kept|known|laid|led|left|lost|made|meant|met|paid|put|read|run|said|seen|sent|set|shown|sold|spent|taken|taught|told|thought|understood|won|written';
const passiveRe = new RegExp(`\\b(am|is|are|was|were|be|been|being|get|gets|got)\\s+(\\w+ly\\s+)?(\\w+ed|${irregular})\\b`, 'i');
const passiveShare = sentences.filter((s) => passiveRe.test(s)).length / (sentences.length || 1);
if (passiveShare > T.passiveShareMax) add('info', 'passive-voice', `About ${Math.round(passiveShare * 100)}% of sentences look passive (AIOSEO target ${Math.round(T.passiveShareMax * 100)}% or less).`);
let same = 1;
for (let i = 1; i < sentences.length; i++) {
  const a = sentences[i - 1].split(/\s+/)[0].toLowerCase(); const b = sentences[i].split(/\s+/)[0].toLowerCase();
  same = a === b ? same + 1 : 1;
  if (same === T.sameStartRun) add('info', 'same-start', `${T.sameStartRun}+ consecutive sentences start with "${b}".`);
}
const transitionRe = /\b(because|so|but|however|therefore|thus|for example|for instance|such as|also|then|first|second|third|finally|next|instead|still|yet|although|though|while|unlike|similarly|as a result|in contrast|on the other hand|that is|in fact|otherwise|meanwhile|afterwards|later|since|until|once|even so|even though|in short|overall)\b/i;
const transitionShare = sentences.filter((s) => transitionRe.test(s)).length / (sentences.length || 1);
if (wc > 200 && transitionShare < T.transitionShareMin) add('info', 'transition-words', `${Math.round(transitionShare * 100)}% of sentences use a transition word (TruSEO wants 30%+). Use natural connectives (because, but, so, for example), not "Additionally" or "Furthermore".`);
if (wc < T.minWords) add('warn', 'word-count', `Only ${wc} words. Thin content rarely satisfies a query; check the brief's scope.`);

// ---------- 5. keyphrase (mirrors AIOSEO TruSEO 2.0 keyword checks) ----------
const norm = (s) => stripMd(s).toLowerCase().replace(/[^\p{L}\p{N}\s]/gu, ' ').replace(/\s+/g, ' ').trim();
const kp = norm(keyphrase);
const kpStats = {};
const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const countIn = (text, phrase) => (norm(text).match(new RegExp(`(?<!\\S)${esc(phrase)}(?!\\S)`, 'g')) || []).length;
if (kp) {
  const count = countIn(bodyText, kp);
  const per100 = (count * 100) / wc; // TruSEO: occurrences per 100 words, good 0.5-3
  const firstPara = blocks.find((b) => b.type === 'p');
  const inIntro = firstPara ? norm(firstPara.text).includes(kp) : false;
  const subs = headings.filter((h) => h.level >= 2);
  const subShare = subs.length ? subs.filter((h) => norm(h.text).includes(kp)).length / subs.length : 0;
  const altShare = images.length ? images.filter((i) => norm(i.alt).includes(kp)).length / images.length : 0;
  const inTitle = h1s[0] ? norm(h1s[0].text).includes(kp) : false;
  const competing = internal.filter((l) => norm(l.text).includes(kp));
  const kpWords = kp.split(' ').length;
  Object.assign(kpStats, { keyphrase, count, per100Words: +per100.toFixed(2), inTitleH1: inTitle, inIntro, subheadingShare: Math.round(subShare * 100), altShare: Math.round(altShare * 100) });
  if (kpWords > 8) add('warn', 'keyphrase-length', `Keyphrase has ${kpWords} words; TruSEO prefers 1-4 (acceptable up to 8).`);
  if (!inIntro) add('warn', 'keyphrase-intro', 'Focus keyphrase is not in the first paragraph (TruSEO introductionKeyword).');
  if (!inTitle) add('warn', 'keyphrase-title', 'Focus keyphrase is not in the H1.');
  if (subs.length && subShare === 0) add('info', 'keyphrase-subheading', 'Keyphrase is in no H2/H3 (TruSEO wants 30-75% of subheadings). Add it where it reads naturally; never force it.');
  else if (subShare > 0.75) add('warn', 'keyphrase-subheading', `Keyphrase is in ${Math.round(subShare * 100)}% of subheadings; over 75% reads as stuffing.`);
  if (images.length && altShare < 0.3) add('info', 'keyphrase-alt', `Keyphrase is in ${Math.round(altShare * 100)}% of image alt texts (TruSEO 30-75%). Add it only where it truthfully describes the image.`);
  if (per100 > T.densityMax) add('warn', 'keyphrase-density', `Keyphrase appears ${per100.toFixed(2)} times per 100 words (TruSEO good band ${T.densityMin}-${T.densityMax}). Reads as stuffing; use variants.`);
  else if (per100 < T.densityMin) add('info', 'keyphrase-density', `Keyphrase appears ${per100.toFixed(2)} times per 100 words (TruSEO band ${T.densityMin}-${T.densityMax}). Fine if the topic is clear; never force it.`);
  if (competing.length) add('warn', 'competing-links', `${competing.length} internal link anchor(s) contain the focus keyphrase, which tells search engines another page targets it: ${competing.map((l) => `"${l.text}"`).join(', ')}.`);
}
if (!images.length) add('warn', 'images', 'No images in the body. Add at least one informative image (TruSEO images check); the featured image is set separately.');

// ---------- 6. seo.json (SEO title, description, slug, social, FAQ) ----------
// Approximate pixel width of a title in Google's desktop font (Arial 20px). Good band per TruSEO: 400-600 px.
const pxWidth = (s) => [...s].reduce((w, c) => w + (/[ilj.,:;'|!]/.test(c) ? 5.5 : /[ftrI()[\] ]/.test(c) ? 6.5 : /[mwMW]/.test(c) ? 16.5 : /[A-Z]/.test(c) ? 13 : /[0-9]/.test(c) ? 11 : 10.5), 0);
if (seo) {
  const a = seo.aioseo || {};
  const sep = seo.separator || '-';
  const resolve = (s) => (s || '').replace(/#post_title/g, seo.post?.title || h1s[0]?.text || '').replace(/#separator_sa/g, sep).replace(/#site_title/g, seo.site_title || 'Site').replace(/\s+/g, ' ').trim();
  const title = resolve(a.title);
  const desc = resolve(a.description);
  const slug = seo.post?.slug || '';
  if (!title) add('error', 'seo-title', 'aioseo.title is empty.');
  else {
    const px = pxWidth(title);
    if (px > T.titleMaxPx) add('warn', 'seo-title-width', `SEO title is about ${Math.round(px)} px (${title.length} chars); TruSEO band is ${T.titleMinPx}-${T.titleMaxPx} px, and Google truncates near 600 px: "${title}"`);
    else if (px < T.titleMinPx) add('info', 'seo-title-width', `SEO title is about ${Math.round(px)} px; under ${T.titleMinPx} px leaves room for a more descriptive title.`);
  }
  if (!desc) add('error', 'meta-description', 'aioseo.description is empty.');
  else if (desc.length < T.descMinChars || desc.length > T.descMaxChars) add(houseLevel(desc.length > T.descMaxChars ? 'meta_description_max' : 'meta_description_min'), 'meta-description-length', `Meta description is ${desc.length} characters (target ${T.descMinChars}-${T.descMaxChars}).`);
  if (kp) {
    if (title && !norm(title).includes(kp)) add('warn', 'keyphrase-seo-title', 'Focus keyphrase is not in the SEO title.');
    else if (title && !norm(title).startsWith(kp)) add('info', 'keyphrase-seo-title-position', 'Keyphrase is in the SEO title but not at the start (TruSEO scores the start higher). Move it only if the title still reads well.');
    if (desc && !norm(desc).includes(kp)) add('warn', 'keyphrase-meta', 'Focus keyphrase is not in the meta description.');
    if (desc && countIn(desc, kp) > 2) add('warn', 'keyphrase-meta-repeat', 'Keyphrase appears more than twice in the meta description.');
    if (slug && !norm(slug.replace(/-/g, ' ')).includes(kp)) add('info', 'keyphrase-slug', `Slug "${slug}" does not contain the keyphrase.`);
  }
  if (!slug) add('error', 'slug', 'post.slug is empty.');
  else if (slug.length > 75 || /[^a-z0-9-]/.test(slug)) add('warn', 'slug', `Slug "${slug}" should be short, lowercase, hyphenated ASCII.`);
  if (h1s[0] && seo.post?.title && norm(h1s[0].text) !== norm(seo.post.title)) add('warn', 'title-mismatch', 'The article H1 and post.title differ; the H1 is the WordPress post title.');
  const social = a.social || {};
  if (!social.og_title || !social.og_description) add('info', 'social', 'Open Graph title or description is empty; shares will fall back to the SEO title and description.');
  if (!seo.post?.featured_image?.alt) add('warn', 'featured-image', 'No featured image (or no alt text). It is the default social and Discover image.');
  // FAQ schema must repeat the visible FAQ exactly: question as a heading or text, answer as visible text.
  const visible = norm(bodyText + ' ' + headings.map((h) => h.text).join(' '));
  for (const f of a.schema?.faq || []) {
    if (!visible.includes(norm(f.question || ''))) add('error', 'faq-not-visible', `FAQ schema question is not visible in the article: "${f.question}". Schema must match visible content.`);
    if (!visible.includes(norm(f.answer || ''))) add('error', 'faq-answer-mismatch', `FAQ schema answer does not match visible text for "${f.question}". Copy the visible answer exactly.`);
  }
}

// ---------- report ----------
const stats = {
  words: wc, sentences: sentences.length, meanSentenceWords: +mean.toFixed(1), sentenceLengthSD: +sd.toFixed(1),
  fleschReadingEase: +flesch.toFixed(0), passivePercent: Math.round(passiveShare * 100), transitionPercent: Math.round(transitionShare * 100), dashes: emDashes,
  internalLinks: internal.length, externalLinks: external.length, images: images.length, headings: headings.length, ...kpStats,
};
const errors = findings.filter((f) => f.level === 'error').length;
const warns = findings.filter((f) => f.level === 'warn').length;
if (asJson) {
  console.log(JSON.stringify({ file, stats, errors, warnings: warns, findings }, null, 2));
} else {
  console.log(`Article: ${file}`);
  console.log(Object.entries(stats).map(([k, v]) => `${k}=${v}`).join('  '));
  for (const level of ['error', 'warn', 'info']) {
    const list = findings.filter((f) => f.level === level);
    if (!list.length) continue;
    console.log(`\n${level.toUpperCase()} (${list.length})`);
    for (const f of list) console.log(`- [${f.rule}]${f.where ? ` ${f.where}:` : ''} ${f.message}`);
  }
  console.log(`\n${errors} error(s), ${warns} warning(s).`);
}
process.exit(errors ? 1 : 0);
