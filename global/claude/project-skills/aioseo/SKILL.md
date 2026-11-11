---
name: aioseo
description: Expert operator for the All in One SEO (AIOSEO) WordPress plugin with an Elite licence. Use this skill to audit, configure, troubleshoot or extend AIOSEO on a WordPress site, and to plan SEO work there. It covers every AIOSEO area: Search Appearance, titles and smart tags, TruSEO and Headline Analyzer, schema and local SEO, sitemaps, robots.txt and llms.txt, redirects and 404s, Link Assistant, Search Statistics and Index Status, Author SEO, Image SEO, the AI Copilot and AI credits, the AIOSEO MCP server, PHP filters and the REST API, imports from Yoast, Rank Math and SEOPress, multisite and licensing. Use it whenever the user mentions AIOSEO, All in One SEO, TruSEO or a WordPress SEO setting, error or Search Console problem on an AIOSEO site, even without naming the plugin. For writing one full article, the seo-article-writer skill runs the pipeline and uses this skill for AIOSEO detail.
---

# AIOSEO (All in One SEO, Elite)

The user's WordPress sites run AIOSEO with an Elite licence, so every feature and addon is available. This skill gives you three things. First, the full AIOSEO feature set with exact menu paths, settings, tiers, limits and failure modes, drawn from a complete read of aioseo.com's docs, FAQs and blog in October 2026. Second, a safe way to change a live site. Third, a rule for when AIOSEO's own advice should give way to Google's documented guidance.

## How to use this skill

1. Work out the task type and open the matching reference file (table below). Read only what the task needs; the files are large.
2. Find out what the site actually has before advising. Use the AIOSEO version, the active addons, the theme, page builder, caching or CDN layer, and any other SEO plugin. `scripts/check-seo-output.mjs <url> --site` shows the public output without credentials.
3. Give exact click paths (for example **All in One SEO » Search Appearance » Content Types » Posts » Advanced**) and setting labels. Labels move between versions; if the live screen differs, trust the screen and note the difference.
4. When AIOSEO advice, a TruSEO check or an SEO Analysis item conflicts with Google's documentation, follow Google and say why. `references/google-alignment.md` lists the known conflicts.

## Reference files

| Task | Read |
|---|---|
| First setup, site audit, "configure AIOSEO properly" | `references/site-setup-audit.md`, then the area files |
| General Settings, Search Appearance, titles and descriptions, smart tags, robots meta, canonicals, Image SEO, Access Control, SEO Alerts | `references/settings-search-appearance.md` |
| Per-post AIOSEO Settings, TruSEO, Headline Analyzer, Writing Assistant, SEO Revisions, Author SEO (E-E-A-T), AIOSEO blocks | `references/content-optimization.md` |
| Schema (Knowledge Graph, generator, templates, every type), Local SEO, breadcrumbs, social profiles, Open Graph, X cards | `references/schema-local-social.md` |
| XML, video, news, RSS and HTML sitemaps, robots.txt, llms.txt, IndexNow, webmaster verification | `references/sitemaps-robots-indexing.md` |
| Search Statistics, Index Status, rank tracking, content decay, email reports, GSC statuses (noindex, canonical, soft 404, 5xx...) | `references/search-statistics-gsc.md` |
| Redirects, 404s, full site redirects, .htaccess, Link Assistant, Broken Link Checker | `references/redirects-links.md` |
| AI Copilot, AI Assistant, AI images, AI schema, AI credits, AI Insights, MCP server and Abilities | `references/ai-mcp.md` |
| REST API writes, automation, bulk edits | `references/api-automation.md` |
| Import/export, backups, reset, migrating from other SEO plugins, multilingual and hreflang, multisite | `references/tools-migration-multisite.md` |
| PHP filters, functions, Composer (with the docs' real code examples and their known bugs) | `references/developer-hooks.md` |
| Something is broken | `references/troubleshooting.md` (also the troubleshooting sections inside the area files) |
| Plans, licence, activations, staging, AI credit billing, requirements | `references/licensing-account.md` |
| Keyword research, intent, mapping and cannibalisation, on-page, internal links, E-E-A-T, content audits, refresh and pruning | `references/playbook-keywords-content.md` |
| Crawling, indexing, canonicals, redirects, migrations, Core Web Vitals, structured data workflow, international | `references/playbook-technical.md` |
| Local SEO and WooCommerce or ecommerce SEO | `references/playbook-local-ecommerce.md` |
| AI Overviews, AI Mode, ChatGPT, Perplexity and Claude citations, llms.txt, AI crawler policy | `references/playbook-ai-search.md` |
| Search Statistics and GSC workflows, reporting cadence, link building, migrating from Yoast or Rank Math | `references/playbook-monitoring-growth.md` |
| Which plan has which feature, and AIOSEO release history (from the blog) | `references/blog-features-tiers.md` (check aioseo.com/pricing for current plans) |
| Vendor advice versus Google | `references/google-alignment.md` first, then `references/blog-google-checks.md` (152 corrected claims) and `references/docs-seo-guidance.md` |
| Points the docs left unclear | `references/open-questions.md` |

## Ways to act on a site

Use the least powerful route that does the job.

1. **Public, read-only.** Page source, `/sitemap.xml`, `/robots.txt`, `/llms.txt`, response headers. `scripts/check-seo-output.mjs` reports title, description, robots, canonical, Open Graph, X, JSON-LD types, the AIOSEO version comment, sitemap and robots.txt status. Start every audit and every "it doesn't show" question here.
2. **AIOSEO MCP server** (WordPress 6.9+, AIOSEO 4.9.8+, MCP Adapter plugin). It exposes AIOSEO Abilities: posts, settings, notifications, robots.txt and audit in Lite; terms, redirects and Search Statistics in Pro (Search Statistics returns data on Elite only); four Link Assistant abilities with that addon. Check each ability's annotations (read-only or not) before calling it. Setup is in `references/ai-mcp.md`.
3. **WordPress REST API.** `aioseo_meta_data` on `/wp-json/wp/v2/<type>/<id>`, with read-back through `aioseo_head` and `aioseo_head_json`. The write has traps (keyphrase triple-write, short robots names, schema replaced whole); see `references/api-automation.md`.
4. **wp-admin by hand.** When no write access exists, or for settings that have no API, give the user numbered steps with the exact labels.

### Change discipline

AIOSEO settings change live output for every page at once. For any write:

- Read the current value first and show the user the exact change (before and after, the scope, and the pages affected).
- Get approval for that specific change. Approval of one change does not cover the next.
- Back up first. **Tools » Backup Settings** saves settings only, not per-post SEO data. **Tools » Import/Export » Export Content** (JSON or CSV) saves post and term SEO data. Bulk changes need both.
- Change one settings group at a time, then verify on the front end (page source or the checker). Clear the page cache and CDN before you verify.
- No automatic retries on a failed write. Read the state again, then decide.

Settings with a site-wide blast radius need explicit, separate approval and a stated rollback: **Show in Search Results**, **Global Robots Meta**, **No Index Paginated** and **No Index RSS Feeds**, **Crawl Cleanup** (feeds, Unwanted Bots, search cleanup), **Robots.txt Editor** rules and **Block AI Crawlers**, the **.htaccess Editor**, **Redirect Method: Web Server**, **Full Site Redirect** and **Canonical Settings**, **Advanced 404 Settings**, **Remove Category Base Prefix**, **Redirect Attachment URLs**, **Run Shortcodes**, schema type defaults, the Knowledge Graph type, and **Uninstall AIOSEO** (deletes all data when the plugin is deleted). Never change a post's publish status, and never send `status` in a REST write to a published post.

### Credentials and paid actions

- Application Passwords and licence keys never go into chat, command arguments, logs, tool output or repository files. The AIOSEO MCP wizard shows a one-time password and a client config snippet that contains it. Tell the user to paste it into the client configuration or credential store themselves. Do not ask them to send it to you.
- An Application Password carries its user's full capabilities. Recommend a dedicated user with the least role that does the job (AIOSEO's **SEO Manager** or **SEO Editor** roles, or Editor), and revoke it from the WordPress profile when it is no longer needed.
- AI features spend AI credits (about 10 per action; bulk titles, descriptions and alt text cost 10 per item). State the credit cost and get approval before any bulk AI action. AI output (titles, descriptions, FAQs, schema, alt text) is fact-checked like any other content before it is saved.

## Standard workflows

**Audit a site (read-only).** Follow `references/site-setup-audit.md`. Report findings ranked by impact, each with the evidence (URL, observed output) and the exact fix path. Change nothing during an audit.

**Configure a feature.** Read its section, check the tier, plan the change, get approval, apply, verify on the front end, and record what changed.

**Troubleshoot.** First compare the live output with the setting (checker, page source, headers). Rule out caching, CDN and security rules (Cloudflare often blocks `/wp-json/aioseo/` and caches or rewrites sitemaps; `check-seo-output.mjs` shows `server`, `cf-cache-status` and `cache-control`), a second SEO plugin and the theme. A change to a CDN or firewall rule is a site change too: same approval and rollback rules. Then work through `references/troubleshooting.md`. The vendor's procedure (Health Check troubleshooting mode, plugins off one by one, a default theme, WP_DEBUG, the browser console) is the fallback.

**Optimise one post.** Set the SEO title, meta description, focus and additional keyphrases (up to 10), the social tabs, the schema and the canonical in AIOSEO Settings. Use TruSEO and the Headline Analyzer as hints, never as targets (see `google-alignment.md`). Writing a new article runs through the seo-article-writer skill.

**Grow traffic on an existing site.** Pick work from data: Search Statistics **Content Rankings** (decay), Keyword Rank Tracker losers, Index Status problems, Link Assistant orphaned posts and linking opportunities. Then use the playbooks. A real update of a decaying post usually beats a new post on the same topic.

**Customise with code.** Use `references/developer-hooks.md`; several vendor examples have bugs (flagged there), so never paste one unread. Put snippets in WPCode (**Code Snippets » Add Snippet » Add Your Custom Code**; AIOSEO's **Tools » Code Snippets** tab only installs WPCode and offers its ready-made library), a must-use plugin or a child theme, never in a parent theme. A filter that adds noindex does not remove the URLs from the sitemap or llms.txt: pair `aioseo_robots_meta` with `aioseo_sitemap_exclude_posts` and `aioseo_llms_post_title` (return `''`), or use the per-post or per-type No Index setting, which excludes from the sitemap automatically. Robots settings on a category apply to the archive page, not to the posts in it. Test on staging, and remember that `aioseo_save_post` runs twice per Block Editor save.

## Facts that are easy to get wrong

- SEO data lives in AIOSEO's own tables (`aioseo_posts`, `aioseo_terms`), not in post meta. `get_post_meta()` and writes to `_aioseo_*` meta do nothing useful. Use the REST field, the Abilities or the plugin's own models.
- Show in Search Results = No does three things: it adds noindex, removes the content from the sitemaps and switches off all SEO features for that type.
- Sitemaps are virtual (no file). There are 1,000 URLs per sitemap page by default. The News sitemap lists only the last 48 hours and returns 404 when there is nothing. A cache or CDN that rewrites XML or XSL breaks them.
- Robots.txt rules (editor, Crawl Cleanup Unwanted Bots and its All AI Crawlers option, search-URL blocking) go into WordPress's dynamic robots.txt. A physical `robots.txt` file overrides all of it. Delete the physical file or edit it by hand.
- AIOSEO does not output hreflang; the multilingual plugin does (WPML or Universally are the integrated ones).
- TruSEO scores are computed in the browser editor. REST writes do not update them.
- Breadcrumb display settings do not change the BreadcrumbList schema.
- Google Analytics and Tag Manager support was removed in 4.5.1 (MonsterInsights replaces it). The OpenAI API-key generator was replaced by AI credits in 4.8.4.
- Google ignores sitemap `priority` and `changefreq`. IndexNow reaches Bing, Yandex, Seznam, Naver and Yep, not Google. FAQ rich results stopped showing in Google on 7 May 2026, and How-To rich results were removed in 2023.

## Keeping this current

The references reflect aioseo.com as of 2026-10-11 (aioseo.com itself ran AIOSEO Pro 5.0.2). Check https://aioseo.com/changelog/ when the site's version is newer, and confirm anything listed in `open-questions.md` on the live site. To refresh the knowledge base, run `scripts/crawl-aioseo.mjs` (sitemap-driven, polite) and re-read what changed.
