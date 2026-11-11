#!/usr/bin/env node
// Read-only check of what a live WordPress page outputs for SEO (AIOSEO or anything else).
// Usage: node check-seo-output.mjs <url> [--site] [--allow-noindex] [--json]
//   --site  also checks /robots.txt, /sitemap.xml, /llms.txt and the home page on the same origin
//   --allow-noindex  report noindex as info (for pages that should be noindexed)
//   --json  machine-readable output
// Fetches public URLs only, sends no credentials or cookies, and changes nothing.
// Exit code: 0 ok, 1 errors found (missing title, noindex, broken canonical, invalid JSON-LD...), 2 usage or fetch failure.

const args = process.argv.slice(2);
const target = args.find((a) => !a.startsWith('--'));
const asJson = args.includes('--json');
const withSite = args.includes('--site');
const allowNoindex = args.includes('--allow-noindex');
const HDRS = ['server', 'cf-cache-status', 'cache-control', 'age', 'x-cache', 'content-type', 'x-robots-tag', 'x-redirect-by'];
const pickHeaders = (h) => Object.fromEntries(HDRS.filter((k) => h[k]).map((k) => [k, h[k]]));
if (!target || !/^https?:\/\//i.test(target)) {
  console.error('Usage: node check-seo-output.mjs <https://example.com/page/> [--site] [--json]');
  process.exit(2);
}

const UA = 'Mozilla/5.0 (compatible; seo-output-check/1.0; read-only)';
async function get(url, { follow = true } = {}) {
  const res = await fetch(url, { redirect: follow ? 'follow' : 'manual', headers: { 'User-Agent': UA, Accept: 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8' }, signal: AbortSignal.timeout(30000) });
  const body = res.status >= 300 && res.status < 400 ? '' : await res.text();
  return { status: res.status, url: res.url || url, headers: Object.fromEntries(res.headers), body };
}

const dec = (s = '') => s.replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#0?39;|&apos;/g, "'")
  .replace(/&#(\d+);/g, (_, n) => String.fromCodePoint(+n)).replace(/&#x([0-9a-f]+);/gi, (_, n) => String.fromCodePoint(parseInt(n, 16)));
const attr = (tag, name) => dec(tag.match(new RegExp(`\\b${name}\\s*=\\s*("([^"]*)"|'([^']*)')`, 'i'))?.slice(2).find((v) => v !== undefined) ?? '');
const metas = (head) => [...head.matchAll(/<meta\b[^>]*>/gi)].map((m) => m[0]);
const metaBy = (head, key, val) => metas(head).filter((t) => attr(t, key).toLowerCase() === val.toLowerCase()).map((t) => attr(t, 'content'));
const links = (head, rel) => [...head.matchAll(/<link\b[^>]*>/gi)].map((m) => m[0]).filter((t) => attr(t, 'rel').toLowerCase().split(/\s+/).includes(rel)).map((t) => attr(t, 'href'));

const findings = [];
const add = (level, msg) => findings.push({ level, msg });

function analysePage(page) {
  const html = page.body;
  const head = html.split(/<\/head>/i)[0] || html;
  const titles = [...head.matchAll(/<title[^>]*>([\s\S]*?)<\/title>/gi)].map((m) => dec(m[1].trim()));
  const desc = metaBy(head, 'name', 'description');
  const robotsMeta = metaBy(head, 'name', 'robots');
  const xRobots = page.headers['x-robots-tag'] || '';
  const canon = links(head, 'canonical');
  const aioseoComment = html.match(/<!--\s*All in One SEO( Pro)?\s*([\d.]+)[^>]*-->/i);
  const og = Object.fromEntries(['og:title', 'og:description', 'og:image', 'og:type', 'og:url', 'og:site_name'].map((k) => [k, metaBy(head, 'property', k)[0] || '']));
  const tw = Object.fromEntries(['twitter:card', 'twitter:title', 'twitter:description', 'twitter:image'].map((k) => [k, metaBy(head, 'name', k)[0] || '']));
  const h1s = [...html.matchAll(/<h1\b[^>]*>([\s\S]*?)<\/h1>/gi)].map((m) => dec(m[1].replace(/<[^>]+>/g, '').trim()));
  const hreflang = [...head.matchAll(/<link\b[^>]*hreflang[^>]*>/gi)].length;

  const schemaTypes = [];
  let schemaErrors = 0;
  for (const m of html.matchAll(/<script\b[^>]*type=["']application\/ld\+json["'][^>]*>([\s\S]*?)<\/script>/gi)) {
    try {
      const data = JSON.parse(m[1]);
      const nodes = Array.isArray(data) ? data : data['@graph'] ? data['@graph'] : [data];
      for (const n of nodes) [].concat(n?.['@type'] || []).forEach((t) => schemaTypes.push(t));
    } catch { schemaErrors++; }
  }

  const r = {
    url: page.url, status: page.status, headers: pickHeaders(page.headers),
    aioseo: aioseoComment ? `${aioseoComment[1] ? 'Pro ' : ''}${aioseoComment[2]}` : 'not detected',
    title: titles[0] || '', titleCount: titles.length,
    description: desc[0] || '', descriptionCount: desc.length,
    robots: robotsMeta.join(', '), xRobotsTag: xRobots,
    canonical: canon[0] || '', canonicalCount: canon.length,
    h1: h1s, hreflangLinks: hreflang,
    openGraph: og, twitter: tw,
    schemaTypes: [...new Set(schemaTypes)], schemaParseErrors: schemaErrors,
  };

  if (page.status !== 200) add('error', `HTTP ${page.status} for ${page.url}`);
  if (!r.title) add('error', 'No <title>.');
  if (r.titleCount > 1) add('error', `${r.titleCount} <title> tags (theme or a second SEO plugin also outputs one).`);
  if (!r.description) add('warn', 'No meta description.');
  if (r.descriptionCount > 1) add('error', `${r.descriptionCount} meta descriptions (duplicate output; another plugin or the theme).`);
  if (/noindex/i.test(r.robots + ' ' + xRobots)) add(allowNoindex ? 'info' : 'error', `Page is noindex (robots: "${r.robots}", X-Robots-Tag: "${xRobots}").`);
  if (!r.canonical) add('warn', 'No canonical link.');
  if (r.canonicalCount > 1) add('error', `${r.canonicalCount} canonical links.`);
  if (r.canonical && r.canonical.replace(/\/$/, '') !== page.url.replace(/[?#].*$/, '').replace(/\/$/, '')) add('info', `Canonical points elsewhere: ${r.canonical}`);
  if (h1s.length !== 1) add('info', `${h1s.length} H1 elements in the HTML.`);
  if (!og['og:title'] || !og['og:image']) add('warn', 'Open Graph title or image missing.');
  if (!tw['twitter:card']) add('info', 'No twitter:card.');
  if (schemaErrors) add('error', `${schemaErrors} JSON-LD block(s) do not parse.`);
  if (!schemaTypes.length) add('warn', 'No JSON-LD structured data.');
  const dupOg = metas(head).filter((t) => attr(t, 'property') === 'og:title').length;
  if (dupOg > 1) add('error', `${dupOg} og:title tags (duplicate social output).`);
  if (r.aioseo === 'not detected') add('info', 'AIOSEO head comment not found (plugin inactive, comment filtered, or another SEO plugin).');
  return r;
}

async function siteChecks(origin) {
  const out = {};
  const robots = await get(`${origin}/robots.txt`).catch((e) => ({ status: 0, body: '', error: e.message }));
  out.robotsTxt = { status: robots.status, headers: pickHeaders(robots.headers || {}), sitemapLines: (robots.body.match(/^sitemap:.*$/gim) || []).map((s) => s.trim()), disallowAll: /^disallow:\s*\/\s*$/im.test(robots.body), aiBlocks: (robots.body.match(/^user-agent:\s*(GPTBot|ClaudeBot|Claude-SearchBot|Claude-User|OAI-SearchBot|PerplexityBot|Google-Extended|CCBot|Bytespider|Applebot-Extended)\s*$/gim) || []).map((s) => s.split(':')[1].trim()) };
  if (robots.status !== 200) add('error', `/robots.txt returned ${robots.status}.`);
  if (out.robotsTxt.disallowAll) add('error', 'robots.txt contains "Disallow: /" (check which user-agent group).');
  const sm = await get(`${origin}/sitemap.xml`).catch((e) => ({ status: 0, body: '' }));
  out.sitemap = { status: sm.status, headers: pickHeaders(sm.headers || {}), isIndex: /<sitemapindex/i.test(sm.body), entries: (sm.body.match(/<loc>/gi) || []).length, generator: sm.body.match(/generated on (.*?) by (All in One SEO[^-]*)/i)?.slice(1).join(' by ') || '' };
  if (sm.status !== 200) add('error', `/sitemap.xml returned ${sm.status}.`);
  const llms = await get(`${origin}/llms.txt`).catch(() => ({ status: 0, body: '' }));
  out.llmsTxt = { status: llms.status, bytes: llms.body.length };
  return out;
}

try {
  const page = await get(target);
  const result = { page: analysePage(page) };
  if (withSite) {
    const origin = new URL(page.url).origin;
    result.site = await siteChecks(origin);
  }
  result.findings = findings;
  if (asJson) console.log(JSON.stringify(result, null, 2));
  else {
    const p = result.page;
    console.log(`URL: ${p.url} (HTTP ${p.status})   AIOSEO: ${p.aioseo}`);
    console.log(`Headers: ${Object.entries(p.headers).map(([k, v]) => `${k}=${v}`).join('  ') || '(none of interest)'}`);
    console.log(`Title (${[...p.title].length} chars): ${p.title}`);
    console.log(`Description (${[...p.description].length} chars): ${p.description}`);
    console.log(`Robots: ${p.robots || '(none)'}${p.xRobotsTag ? `   X-Robots-Tag: ${p.xRobotsTag}` : ''}`);
    console.log(`Canonical: ${p.canonical || '(none)'}`);
    console.log(`H1: ${p.h1.map((h) => `"${h}"`).join(' | ') || '(none)'}   hreflang links: ${p.hreflangLinks}`);
    console.log(`OG: ${Object.entries(p.openGraph).map(([k, v]) => `${k}=${v ? 'set' : '-'}`).join(' ')}`);
    console.log(`X:  ${Object.entries(p.twitter).map(([k, v]) => `${k}=${k === 'twitter:card' ? v || '-' : v ? 'set' : '-'}`).join(' ')}`);
    console.log(`Schema types: ${p.schemaTypes.join(', ') || '(none)'}`);
    if (result.site) {
      const s = result.site;
      console.log(`robots.txt: HTTP ${s.robotsTxt.status}; sitemap lines: ${s.robotsTxt.sitemapLines.length}; AI user-agent groups: ${s.robotsTxt.aiBlocks.join(', ') || 'none'}`);
      console.log(`sitemap.xml headers: ${Object.entries(s.sitemap.headers).map(([k, v]) => `${k}=${v}`).join('  ')}`);
      console.log(`sitemap.xml: HTTP ${s.sitemap.status}; ${s.sitemap.isIndex ? 'index' : 'urlset'} with ${s.sitemap.entries} <loc>; ${s.sitemap.generator}`);
      console.log(`llms.txt: HTTP ${s.llmsTxt.status} (${s.llmsTxt.bytes} bytes)`);
    }
    for (const level of ['error', 'warn', 'info']) {
      const list = findings.filter((f) => f.level === level);
      if (list.length) { console.log(`\n${level.toUpperCase()}`); list.forEach((f) => console.log(`- ${f.msg}`)); }
    }
  }
  process.exit(findings.some((f) => f.level === 'error') ? 1 : 0);
} catch (e) {
  console.error(`Fetch failed: ${e.message}`);
  process.exit(2);
}
