#!/usr/bin/env node
// Turns the skill's seo.json into the WordPress REST payload for a post with AIOSEO 5.x data.
// Usage: node build-aioseo-payload.mjs <seo.json> [--out wp-payload.json]
//
// Output shape:
// {
//   "post":  { title, slug, excerpt, status, categories (names), tags (names), author, featured_image },
//   "aioseo_meta_data": { ... }           -> send inside POST /wp-json/wp/v2/posts/<id>
//   "schema_custom_graphs": [ ... ]       -> merge into the post's CURRENT aioseo_meta_data.schema.customGraphs
//   "manual": { ... }                     -> steps that need wp-admin
// }
//
// Facts this encodes (verified against all-in-one-seo-pack 5.0.3 source, see references/aioseo.md):
// - The focus keyphrase must be written to focus_keyword, additional_keywords AND keyphrases,
//   because the 5.x editor reads only the dedicated columns.
// - Robots writes use short names (noindex, nofollow, ...) plus "default": false; robots_* names are ignored on write.
// - The REST write is a shallow array_replace: sending "schema" replaces the whole schema object, so schema
//   changes must be read-modify-write. This script never sends "schema" itself.

import { readFileSync, writeFileSync } from 'node:fs';

const args = process.argv.slice(2);
const src = args.find((a) => !a.startsWith('--'));
const outIdx = args.indexOf('--out');
const out = outIdx >= 0 ? args[outIdx + 1] : undefined;
if (!src) {
  console.error('Usage: node build-aioseo-payload.mjs <seo.json> [--out wp-payload.json]');
  process.exit(2);
}
const seo = JSON.parse(readFileSync(src, 'utf8'));
const a = seo.aioseo || {};
const s = a.social || {};
const problems = [];

if (!seo.post?.title) problems.push('post.title is required');
if (!seo.post?.slug || /[^a-z0-9-]/.test(seo.post.slug)) problems.push('post.slug must be lowercase ASCII words joined by hyphens');
if (!a.title) problems.push('aioseo.title is required');
if (!a.description) problems.push('aioseo.description is required');
if (!a.focus_keyphrase) problems.push('aioseo.focus_keyphrase is required');
// This workflow only ever creates drafts. Publishing is a separate, explicit user action in WordPress.
if (seo.post?.status && seo.post.status !== 'draft') problems.push(`post.status is "${seo.post.status}"; this workflow only creates drafts. Remove it or set "draft"`);
if (problems.length) {
  console.error(`seo.json is incomplete:\n- ${problems.join('\n- ')}`);
  process.exit(1);
}

const additional = (a.additional_keyphrases || []).filter(Boolean);
const tags = (list) => (list || []).map((t) => ({ label: t, value: t }));
const isUrl = (v) => typeof v === 'string' && /^https?:\/\//.test(v);

const meta = {
  title: a.title,
  description: a.description,
  // keyphrase triple-write
  focus_keyword: a.focus_keyphrase,
  additional_keywords: additional.map((word) => ({ word, score: 0 })),
  keyphrases: {
    focus: { keyphrase: a.focus_keyphrase, score: 0, analysis: {} },
    additional: additional.map((keyphrase) => ({ keyphrase, score: 0, analysis: {} })),
  },
  pillar_content: !!a.cornerstone,
  // Open Graph
  og_title: s.og_title || '',
  og_description: s.og_description || '',
  og_object_type: s.og_object_type || 'article',
  og_article_section: s.article_section || seo.post.primary_category || '',
  og_article_tags: tags(s.article_tags || seo.post.tags),
  // X / Twitter
  twitter_use_og: s.twitter_use_og !== false,
  twitter_card: s.twitter_card || 'summary_large_image',
  canonical_url: a.canonical_url || '',
};

if (isUrl(s.og_image)) {
  meta.og_image_type = 'custom_image';
  meta.og_image_custom_url = s.og_image;
} else {
  meta.og_image_type = s.og_image || 'featured';
}
if (s.twitter_use_og === false) {
  meta.twitter_title = s.twitter_title || '';
  meta.twitter_description = s.twitter_description || '';
  if (isUrl(s.twitter_image)) {
    meta.twitter_image_type = 'custom_image';
    meta.twitter_image_custom_url = s.twitter_image;
  } else if (s.twitter_image) {
    meta.twitter_image_type = s.twitter_image;
  } else {
    // Fall back to the Facebook image, including its custom URL.
    meta.twitter_image_type = meta.og_image_type;
    if (meta.og_image_custom_url) meta.twitter_image_custom_url = meta.og_image_custom_url;
  }
}

// Robots: "default" follows the global Search Appearance settings.
if (!a.robots || a.robots === 'default') {
  meta.default = true;
} else {
  meta.default = false;
  for (const k of ['noindex', 'nofollow', 'noarchive', 'nosnippet', 'noimageindex', 'notranslate', 'noodp']) meta[k] = !!a.robots[k];
  if (a.robots.maxSnippet !== undefined) meta.maxSnippet = a.robots.maxSnippet;
  if (a.robots.maxVideoPreview !== undefined) meta.maxVideoPreview = a.robots.maxVideoPreview;
  if (a.robots.maxImagePreview) meta.maxImagePreview = a.robots.maxImagePreview;
}

// Optional FAQPage graph. Only for questions that are visible on the page.
const customGraphs = [];
const faq = a.schema?.faq || [];
if (faq.length) {
  const jsonld = {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: faq.map((f) => ({ '@type': 'Question', name: f.question, acceptedAnswer: { '@type': 'Answer', text: f.answer } })),
  };
  customGraphs.push({ id: `#aioseo-custom-faq-${seo.post.slug}`, custom: true, graphName: 'FAQPage', schema: JSON.stringify(jsonld) });
}

const payload = {
  post: {
    title: seo.post.title,
    slug: seo.post.slug,
    excerpt: seo.post.excerpt || '',
    status: 'draft',
    categories: seo.post.categories || [],
    primary_category: seo.post.primary_category || '',
    tags: seo.post.tags || [],
    author: seo.post.author || '',
    featured_image: seo.post.featured_image || null,
  },
  aioseo_meta_data: meta,
  schema_custom_graphs: customGraphs,
  manual: {
    ...(seo.manual || {}),
    checks: [
      'Open the post in the editor once so TruSEO computes its scores (REST writes do not recalculate seo_score).',
      ...(seo.post.primary_category ? [`Confirm primary category "${seo.post.primary_category}" in the AIOSEO sidebar.`] : []),
      ...(seo.manual?.reviewer ? [`Select reviewer "${seo.manual.reviewer}" in the AIOSEO Author SEO panel.`] : []),
    ],
  },
};

const json = JSON.stringify(payload, null, 2);
if (out) {
  writeFileSync(out, `${json}\n`);
  console.log(`Wrote ${out}`);
} else {
  console.log(json);
}
