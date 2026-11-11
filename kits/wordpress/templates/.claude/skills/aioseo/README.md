# aioseo

A Claude Code skill that makes Claude an expert operator of All in One SEO (AIOSEO) with an Elite licence. It covers auditing, configuring, troubleshooting and extending AIOSEO on WordPress, and planning SEO work on those sites. It is project-independent: copy the folder into any repository.

## What it knows

The reference files come from a complete read, on 2026-10-11, of every page in aioseo.com's documentation (489 pages), the FAQ page and the blog (571 posts). The docs' 95 code examples were recovered from their WPCode embeds and reproduced verbatim. Each section names its source pages. Where the vendor's advice is dated or conflicts with Google's documentation, a bracketed note says so, and `references/google-alignment.md` collects those conflicts. Points the docs left unclear are in `references/open-questions.md`, to be checked on a live site.

| File | Content |
|---|---|
| `SKILL.md` | Routing, ways to act on a site, change discipline, credentials, workflows, easy-to-miss facts |
| `references/site-setup-audit.md` | Read-only audit procedure, recommended Elite configuration, recurring routine |
| `references/settings-search-appearance.md` | General Settings, Search Appearance, robots, canonicals, smart tags, Image SEO, Access Control |
| `references/content-optimization.md` | Per-post settings, TruSEO, Headline Analyzer, Writing Assistant, SEO Revisions, Author SEO, blocks |
| `references/schema-local-social.md` | Schema, Local SEO, breadcrumbs, social profiles, Open Graph, X |
| `references/sitemaps-robots-indexing.md` | Sitemaps, robots.txt, llms.txt, IndexNow, verification |
| `references/search-statistics-gsc.md` | Search Statistics, Index Status, rank tracking, decay, GSC status playbooks |
| `references/redirects-links.md` | Redirection Manager, 404s, full site redirect, Link Assistant, Broken Link Checker |
| `references/ai-mcp.md` | AI Copilot and AI features, AI credits, AI Insights, MCP server |
| `references/api-automation.md` | REST `aioseo_meta_data` write traps, Abilities, bulk routes, Composer, credentials |
| `references/tools-migration-multisite.md` | Import/export, backups, migration from other plugins, multilingual, multisite |
| `references/developer-hooks.md` | Every documented filter, with the vendor's code and its known bugs |
| `references/troubleshooting.md` | Generic procedure and symptom, cause and fix tables |
| `references/licensing-account.md` | Plans, activations, staging, AI credit billing, requirements |
| `references/playbook-*.md` | SEO playbooks by topic, distilled from the blog and corrected against Google |
| `references/blog-features-tiers.md`, `references/blog-google-checks.md` | Feature and tier map from the blog; every blog claim corrected |
| `references/google-alignment.md`, `references/docs-seo-guidance.md` | Where AIOSEO's advice and Google's guidance differ |
| `scripts/check-seo-output.mjs` | Read-only check of a live page's SEO output (and robots.txt, sitemap, llms.txt with `--site`) |
| `scripts/crawl-aioseo.mjs` | Polite re-crawl of aioseo.com docs, FAQ and blog to text, for refreshing the references |

## Install

Copy this folder to `<repo>/.claude/skills/aioseo/` (one project) or `~/.claude/skills/aioseo/` (all projects), then start a new Claude Code session. It triggers on AIOSEO and WordPress SEO tasks, or run `/aioseo`. It works alongside `seo-article-writer`, which writes articles and uses this skill for AIOSEO detail.

Requirements: Node 18 or later for the scripts (no dependencies). Write access to a site comes from the session: the AIOSEO MCP server, a WordPress REST connection that keeps the Application Password in a credential store, or wp-admin steps the user follows.

## Scripts

```
node scripts/check-seo-output.mjs <url> [--site] [--json]
node scripts/crawl-aioseo.mjs <empty-dir> [--only docs|blog|faq] [--since YYYY-MM-DD] [--concurrency 4]
```

## Refreshing

When AIOSEO ships a major version, run the crawler with `--since` set to the last refresh date, read the changed pages, update the affected reference sections, and move resolved items out of `open-questions.md`.
