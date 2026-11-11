#!/usr/bin/env node
// Converts the article Markdown to WordPress block-editor (Gutenberg) markup for post_content.
// Usage: node to-gutenberg.mjs <article.md> [--media media-map.json] [--out post.html]
//
// - The H1 is the post title and is left out of the content.
// - --media maps local image paths to uploaded media: { "images/a.webp": { "id": 123, "url": "https://..." } }.
//   Unmapped images keep their path and must be uploaded before publishing.
// - Supports headings, paragraphs, flat and one-level nested lists, block quotes, images on their own line
//   (with an optional "title" used as the caption), tables, fenced code and horizontal rules.
//   Inline: links, bold, italic, code. Link rel values go in the title slot: [text](url "sponsored").
// - Anything unsupported (inline images, raw HTML links) stops the conversion with an error.
// After creating the post, open it in the editor once: the editor reports any block it cannot validate.

import { readFileSync, writeFileSync } from 'node:fs';

const args = process.argv.slice(2);
const opt = (n) => { const i = args.indexOf(`--${n}`); return i >= 0 ? args[i + 1] : undefined; };
const valued = new Set(['--media', '--out']);
let src;
for (let i = 0; i < args.length; i++) {
  if (valued.has(args[i])) { i++; continue; }
  if (!args[i].startsWith('--')) { src = args[i]; break; }
}
if (!src) {
  console.error('Usage: node to-gutenberg.mjs <article.md> [--media media-map.json] [--out post.html]');
  process.exit(2);
}
const media = opt('media') ? JSON.parse(readFileSync(opt('media'), 'utf8')) : {};

let md = readFileSync(src, 'utf8').replace(/\r\n/g, '\n');
if (md.startsWith('---')) { const end = md.indexOf('\n---', 3); if (end > 0) md = md.slice(end + 4); }

const errors = [];
const escHtml = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const escAttr = (s) => escHtml(s).replace(/"/g, '&quot;');
const emphasis = (s) => s
  .replace(/\*\*([^*]+)\*\*|__([^_]+)__/g, (_, a, b) => `<strong>${a || b}</strong>`)
  .replace(/(^|[^*\w])\*([^*\s][^*]*?)\*(?!\*)/g, '$1<em>$2</em>')
  .replace(/(^|[^_\w])_([^_\s][^_]*?)_(?!\w)/g, '$1<em>$2</em>');
// [text](url) and [text](url "sponsored nofollow"): the title slot carries rel values.
// URLs may contain one level of balanced parentheses, e.g. Wikipedia links.
const LINK = /\[([^\]]+)\]\(((?:[^()\s]|\([^()\s]*\))+)(?:\s+"([^"]*)")?\)/g;
const REL = /^(sponsored|nofollow|ugc|noopener|noreferrer)$/i;
const inline = (s) => {
  if (/!\[[^\]]*\]\(/.test(s)) errors.push(`Inline image is not supported; put each image on its own line: "${s.slice(0, 70)}"`);
  if (/<a\s/i.test(s)) errors.push(`Raw HTML link; write it as [text](url "rel") instead: "${s.slice(0, 70)}"`);
  const tokens = [];
  const hold = (html) => { tokens.push(html); return `\u0000${tokens.length - 1}\u0000`; };
  s = s.replace(/`([^`]+)`/g, (_, c) => hold(`<code>${escHtml(c)}</code>`));
  s = s.replace(LINK, (_, text, url, title) => {
    const words = (title || '').split(/\s+/).filter(Boolean);
    const rel = words.filter((w) => REL.test(w)).map((w) => w.toLowerCase());
    if (words.length !== rel.length) errors.push(`Link title "${title}" is not a rel value (use sponsored, nofollow or ugc): ${url}`);
    return hold(`<a href="${escAttr(url)}"${rel.length ? ` rel="${rel.join(' ')}"` : ''}>${emphasis(escHtml(text))}</a>`);
  });
  s = emphasis(escHtml(s));
  while (/\u0000\d+\u0000/.test(s)) s = s.replace(/\u0000(\d+)\u0000/g, (_, i) => tokens[+i]);
  return s;
};
const block = (name, attrs, html) => {
  const a = attrs && Object.keys(attrs).length ? ` ${JSON.stringify(attrs)}` : '';
  return `<!-- wp:${name}${a} -->\n${html}\n<!-- /wp:${name} -->`;
};
const paragraph = (text) => block('paragraph', null, `<p>${inline(text)}</p>`);

const imageBlock = (alt, path, caption) => {
  const m = media[path];
  const url = m?.url || path;
  const attrs = m?.id ? { id: m.id, sizeSlug: 'large', linkDestination: 'none' } : { sizeSlug: 'large', linkDestination: 'none' };
  const cls = m?.id ? ` class="wp-image-${m.id}"` : '';
  const cap = caption ? `<figcaption class="wp-element-caption">${inline(caption)}</figcaption>` : '';
  return block('image', attrs, `<figure class="wp-block-image size-large"><img src="${escAttr(url)}" alt="${escAttr(alt)}"${cls}/>${cap}</figure>`);
};

const listBlock = (items, ordered) => {
  const tag = ordered ? 'ol' : 'ul';
  const inner = items.map((it) => {
    const nested = it.children.length ? `\n${listBlock(it.children, it.childOrdered)}` : '';
    return `<!-- wp:list-item -->\n<li>${inline(it.text)}${nested}</li>\n<!-- /wp:list-item -->`;
  }).join('\n');
  return block('list', ordered ? { ordered: true } : null, `<${tag} class="wp-block-list">${inner}</${tag}>`);
};

const tableBlock = (rows) => {
  const cells = (r) => r.replace(/^\s*\|/, '').replace(/\|\s*$/, '').split('|').map((c) => c.trim());
  const head = cells(rows[0]);
  const body = rows.slice(2).map(cells);
  const thead = `<thead><tr>${head.map((c) => `<th>${inline(c)}</th>`).join('')}</tr></thead>`;
  const tbody = `<tbody>${body.map((r) => `<tr>${r.map((c) => `<td>${inline(c)}</td>`).join('')}</tr>`).join('')}</tbody>`;
  return block('table', null, `<figure class="wp-block-table"><table>${thead}${tbody}</table></figure>`);
};

const out = [];
const lines = md.split('\n');
let i = 0;
let titleSkipped = false;
while (i < lines.length) {
  const line = lines[i];
  if (/^\s*$/.test(line)) { i++; continue; }

  const fence = line.match(/^```(\w*)/);
  if (fence) {
    const code = [];
    i++;
    while (i < lines.length && !/^```/.test(lines[i])) code.push(lines[i++]);
    i++;
    out.push(block('code', null, `<pre class="wp-block-code"><code>${escHtml(code.join('\n'))}</code></pre>`));
    continue;
  }

  const h = line.match(/^(#{1,6})\s+(.*?)\s*#*\s*$/);
  if (h) {
    const level = h[1].length;
    if (level === 1 && !titleSkipped) { titleSkipped = true; i++; continue; }
    out.push(block('heading', level === 2 ? null : { level }, `<h${level} class="wp-block-heading">${inline(h[2])}</h${level}>`));
    i++;
    continue;
  }

  if (/^(\*\s*\*\s*\*|-{3,}|_{3,})\s*$/.test(line)) { out.push(block('separator', null, '<hr class="wp-block-separator has-alpha-channel-opacity"/>')); i++; continue; }

  const img = line.match(/^\s*!\[([^\]]*)\]\(([^)\s]+)(?:\s+"([^"]*)")?\)\s*$/);
  if (img) { out.push(imageBlock(img[1], img[2], img[3])); i++; continue; }

  if (/^\s*\|/.test(line)) {
    const rows = [];
    while (i < lines.length && /^\s*\|/.test(lines[i])) rows.push(lines[i++]);
    out.push(tableBlock(rows));
    continue;
  }

  if (/^\s*>/.test(line)) {
    const q = [];
    while (i < lines.length && /^\s*>/.test(lines[i])) q.push(lines[i++].replace(/^\s*>\s?/, ''));
    const paras = q.join('\n').split(/\n\s*\n/).map((p) => paragraph(p.replace(/\n/g, ' ')));
    out.push(block('quote', null, `<blockquote class="wp-block-quote">${paras.join('\n')}</blockquote>`));
    continue;
  }

  const li = line.match(/^(\s*)([-*+]|\d+[.)])\s+(.*)$/);
  if (li) {
    const ordered = /\d/.test(li[2]);
    const items = [];
    while (i < lines.length) {
      const m = lines[i].match(/^(\s*)([-*+]|\d+[.)])\s+(.*)$/);
      if (!m) {
        if (/^\s{2,}\S/.test(lines[i]) && items.length) { items[items.length - 1].text += ` ${lines[i].trim()}`; i++; continue; }
        break;
      }
      if (m[1].length >= 2 && items.length) {
        const parent = items[items.length - 1];
        parent.childOrdered = /\d/.test(m[2]);
        parent.children.push({ text: m[3], children: [] });
      } else {
        items.push({ text: m[3], children: [] });
      }
      i++;
    }
    out.push(listBlock(items, ordered));
    continue;
  }

  // Paragraph: the first line always belongs to it, so nothing is skipped silently.
  const para = [lines[i++].trim()];
  while (i < lines.length && !/^\s*$/.test(lines[i]) && !/^(#{1,6}\s|```|\s*>|\s*\||!\[|\s*([-*+]|\d+[.)])\s)/.test(lines[i])) para.push(lines[i++].trim());
  out.push(paragraph(para.join(' ')));
}

if (errors.length) {
  console.error(`Not converted. Fix these in the Markdown:\n- ${[...new Set(errors)].join('\n- ')}`);
  process.exit(1);
}

const html = `${out.join('\n\n')}\n`;
const unmapped = [...md.matchAll(/!\[[^\]]*\]\(([^)\s]+)/g)].map((m) => m[1]).filter((p) => !media[p] && !/^https?:\/\//.test(p));
if (opt('out')) {
  writeFileSync(opt('out'), html);
  console.log(`Wrote ${opt('out')} (${out.length} blocks).`);
} else {
  process.stdout.write(html);
}
if (unmapped.length) console.error(`Images still pointing at local files (upload them and pass --media): ${[...new Set(unmapped)].join(', ')}`);
