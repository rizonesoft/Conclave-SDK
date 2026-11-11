#!/usr/bin/env node
// Refuses a post the project protects (for example a sponsor-approved article).
// Usage: node guard-post.mjs --project <seo-article-writer.json> --post <id> [--post <id> ...]
// Run before fetching a post for a refresh and before any write that targets an existing post.
// Exit code: 0 allowed, 3 protected, 2 usage or unreadable project file (fails closed).

import { readFileSync } from 'node:fs';

const args = process.argv.slice(2);
const ids = [];
let projectFile;
for (let i = 0; i < args.length; i++) {
  if (args[i] === '--post') ids.push(args[++i]);
  else if (args[i] === '--project') projectFile = args[++i];
}
if (!projectFile || !ids.length || ids.some((id) => !/^\d+$/.test(id || ''))) {
  console.error('Usage: node guard-post.mjs --project <seo-article-writer.json> --post <id> [--post <id> ...]');
  process.exit(2);
}
let project;
try {
  project = JSON.parse(readFileSync(projectFile, 'utf8'));
} catch (e) {
  console.error(`Cannot read the project file ${projectFile} (${e.message}), so protected posts cannot be confirmed.`);
  process.exit(2);
}
const reasons = new Map((project.protected_posts || []).map((p) => [String(p.id), p.reason || 'protected']));
let hits = 0;
for (const id of ids) {
  if (reasons.has(id)) {
    hits++;
    console.error(`Post ${id} is protected: ${reasons.get(id)}. Do not edit, refresh, unpublish or draft it.`);
  } else {
    console.log(`Post ${id}: not protected.`);
  }
}
process.exit(hits ? 3 : 0);
