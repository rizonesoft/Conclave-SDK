# Site setup and audit (AIOSEO Elite)

Two jobs: a read-only audit of an existing site, and the recommended configuration for a new or messy one. The recommended values follow Google's documentation where it differs from AIOSEO's defaults or advice (see google-alignment.md). Change nothing without the approval steps in SKILL.md.

## Contents

- Part 1: Read-only audit
- Part 2: Recommended configuration, by settings screen
- Part 3: After launch, the recurring routine

## Part 1: Read-only audit

Work from outside in, so that no finding depends on the admin's view of the settings.

### 1. Public output (no login)

Run `node scripts/check-seo-output.mjs <home URL> --site`, then run it on one post, one page, one category archive, one product (if WooCommerce) and one URL that should not be indexed (search results, an attachment, a tag archive). For each, record the HTTP status, title, description, robots, canonical, Open Graph and X tags, JSON-LD types, and the AIOSEO version comment.

Red flags:

- Two titles, two descriptions, two canonicals or duplicate `og:` tags. Another SEO plugin, the theme or a page builder is also printing them.
- `noindex` on the home page or on posts. Check WordPress Settings » Reading » "Discourage search engines" first.
- A canonical pointing to another URL, to http, or to the other www variant.
- No JSON-LD, or JSON-LD that does not parse.
- `/robots.txt` with `Disallow: /`, missing Sitemap lines, or a physical file (AIOSEO's dynamic rules not showing).
- `/sitemap.xml` returning 404, an HTML page or a cached old copy. The XSL stylesheet failing behind a CDN.
- AI search crawlers (OAI-SearchBot, Claude-SearchBot, Claude-User, PerplexityBot) blocked when the owner wants AI citations.

### 2. Search Console and Search Statistics

- Search Statistics connected (Elite) and showing data. If it is not connected, ask the user to connect it (Search Statistics » Settings » Connect); it needs their Google login.
- Index Status: count indexed against excluded against error, then read the reasons (see search-statistics-gsc.md for each GSC status).
- Content Rankings: posts with the largest Loss and Drop are refresh candidates.
- Keyword Rank Tracker: tracked keywords and the top losers.
- GSC directly: Page indexing, Core Web Vitals, manual actions, security issues, sitemaps submitted and read.

### 3. Settings review (wp-admin or the `aioseo-settings/get` ability)

Compare each screen with Part 2 and record every difference with its likely impact. In particular check Show in Search Results per content type and taxonomy, Global Robots Meta, the Knowledge Graph (Person or Organization, logo), the sitemap post types and taxonomies, Redirect Attachment URLs, Crawl Cleanup, robots.txt rules, the Redirect Method, and Full Site Redirect.

### 4. Content sample

From the AIOSEO Details column and the **AIOSEO Overview** widget: posts with no focus keyphrase, missing or default descriptions, title width over 600 px, and low TruSEO scores. Treat TruSEO as a pointer to posts worth reading, not a grade. Use **Link Assistant » Links Report » Orphaned Posts** for posts with no internal links pointing in. The **Site Audit** (SEO Analysis » Site Audit) gives a per-post checklist.

### 5. Report

Rank findings: indexing and crawl blockers first, then duplicate or conflicting output, then structured data errors, then content and linking work. For each finding give the evidence (URL plus what was observed), the exact fix path, the risk of the fix, and whether it needs approval. List anything you could not check, and why.

## Part 2: Recommended configuration

Elite has every feature. Activate the addons in **Feature Manager**: Author SEO, Image SEO, IndexNow, Link Assistant, Local SEO (only for real local businesses), News Sitemap (only for news publishers), Video Sitemap (only if the site embeds video).

### General Settings

- **License**: key active. On multisite, network-activate and use Domain Activations.
- **Webmaster Tools**: verify Google Search Console and Bing Webmaster Tools (and Microsoft Clarity if wanted). Connecting GSC also submits the sitemaps.
- **Content Optimization**: TruSEO, Headline Analyzer and Spell Checker on. They are writing aids and have no effect on rankings.
- **Access Control**: give writers the least access. SEO Manager (General Settings, Redirections, per-post) and SEO Editor (per-post only) exist for SEO staff.
- **Advanced**: Automatic Updates "Minor Only" or "All" with a backup routine. Email Summaries on, weekly or monthly to the owner. Uninstall AIOSEO off.
- **Tools » SEO Alerts** (2026): leave all three alerts on (home page noindexed, robots.txt failing, sitemaps failing), sent by email or Slack.

### Search Appearance

- **Global Settings**: separator; home page title `#site_title #separator_sa #tagline` or a written title; a written home page description. **Knowledge Graph**: Organization (name, logo at least 112x112, contact) for businesses, Person for personal brands. Alternate site name if the brand has one.
- **Content Types**: Posts title `#post_title #separator_sa #site_title`, description `#post_excerpt` as the fallback only (write descriptions per post). Schema: Article with BlogPosting for posts, WebPage for pages, Product for WooCommerce products. Show in Search Results: Yes for posts, pages and products; No for thin utility types.
- **Taxonomies**: categories indexable when they are real hub pages with intro text; tags usually Show in Search Results = No unless curated. Remove Category Base Prefix only on a new site, and check for post and category slug collisions first.
- **Archives**: author archives indexable only for real multi-author sites with bios; date archives No. The search page stays No (the default).
- **Image SEO / Media**: Redirect Attachment URLs = Attachment (the default). Alt text format must never overwrite hand-written alt text; filenames lower case with hyphens; strip punctuation.
- **Advanced**:
  - Global Robots Meta on defaults, plus `max-image-preview: large`, max snippet and video preview -1.
  - **No Index Paginated off** (Google advises leaving paginated pages indexable with self-canonicals). No Index RSS Feeds may stay on (the default).
  - Meta keywords off.
  - Run Shortcodes off unless a builder needs it, and test after enabling it.
  - Crawl Cleanup only for large sites: keep the global and static posts page feeds; disable comment, search, attachment and Atom/RDF feeds; leave author and category feeds on if people use them.
  - Query Arg Monitoring: watch the log table size (`_aioseo_crawl_cleanup_logs`).
- **Author SEO**: a complete profile for every real author (photo, short and full bio, job title, employer, Knows About topics from the global list, awards, languages, social profiles). Append Author Bio to Posts on, unless the theme already shows a bio or the Author Bio block is placed by hand. Never invent credentials, and never use AI headshots for real people.

### Social Networks

- Social Profiles: every official profile URL (they feed `sameAs`).
- Facebook: Open Graph on; default image 1200x630; image source "Featured Image" with the default as fallback; article tags from post tags.
- X: cards on; default `summary_large_image`; "Use Data from Facebook Tab" unless X needs different copy.

### Schema

- The Knowledge Graph and content-type defaults produce Organization or Person, WebSite, WebPage, BreadcrumbList and Article graphs automatically.
- Add per-post schema only for content that is visible on the page (Product, Recipe, Event, JobPosting, LocalBusiness, Review of a third-party item, VideoObject). Validate with the Rich Results Test.
- Do not expect a Google rich result from FAQPage (retired for all sites, 7 May 2026), HowTo (removed 2023), the sitelinks search box (removed November 2024), or the types Google phased out in 2025 (Book Actions, Course Info, ClaimReview, Vehicle Listing and others). The markup is harmless and other engines may read it.
- Never mark up self-serving reviews of your own business, and never hide content that the schema describes.

### Sitemaps

- General Sitemap on with indexes, 1,000 links per page; posts, pages, products and indexable taxonomies only; date and author archives off unless indexable; images included.
- Leave priority and frequency on Default (Google ignores both).
- Video Sitemap if video is embedded; News Sitemap only for publishers who meet Google News policies; RSS sitemap on (useful for recent changes); HTML sitemap optional for users.
- Exclude XML and XSL sitemap URLs from page caching and CDN rewriting.
- **llms.txt**: on by default; harmless. Google says it neither helps nor harms Search. Exclude private or thin sections.
- **IndexNow** on: it reaches Bing, Yandex, Seznam, Naver and Yep. Google does not use it.

### Robots.txt (Tools » Robots.txt Editor)

- Keep the sitemap line and WordPress's default `/wp-admin/` rules. Delete any physical robots.txt so AIOSEO's rules apply.
- AI policy is the owner's decision. To be cited in AI answers, allow Googlebot, Bingbot, OAI-SearchBot (ChatGPT search), Claude-SearchBot and Claude-User, and PerplexityBot. Training crawlers (GPTBot, ClaudeBot, CCBot, Google-Extended as a control token) are a separate choice. Google-Extended does not affect Google Search, AI Overviews or AI Mode. "Block AI Crawlers" in Crawl Cleanup blocks them in bulk; review the list it writes before enabling it.
- Never disallow URLs you want removed from the index; noindex them and leave them crawlable.

### Redirects

- Redirect Method: PHP (the default) unless the host can include the server config; the Web Server method loses hit logs.
- Automatic Redirects: on for all post types; Monitor Trashed & Deleted Posts on (it creates disabled redirects to review).
- 404 logging on with a retention period; Advanced 404 Settings off (mass redirects to the home page are soft 404s).
- Log IP Addresses anonymised for GDPR.
- Canonical Settings (HTTP to HTTPS, preferred www or non-www) only if the host does not already do it, and after HTTPS works.

### Link Assistant (Elite includes it)

Scan all public post types and published posts. Add affiliate prefixes so affiliate links are reported. Mark pillar pages as Cornerstone Content.

### Local SEO (real local businesses only)

Business Info with a NAP that matches the Google Business Profile exactly, opening hours, Maps API keys (Maps JavaScript API and Geocoding API, restricted by HTTP referrer), and Multiple Locations for chains. Details are in schema-local-social.md.

### WooCommerce

Product schema from the WooCommerce data (price, availability, SKU, GTIN, brand, reviews from real customers). Shipping and return policy schema needs a filter snippet (schema-local-social.md). Product attributes in titles use the Taxonomy Name smart tag with the `pa_` slug.

## Part 3: After launch, the recurring routine

- **Weekly**: SEO Alerts and email summary; new 404s (add redirects for URLs that have links or traffic); Index Status errors.
- **Monthly**: Content Rankings decay list; refresh one or two decaying posts with real updates; Link Assistant orphaned posts and suggestions; Keyword Rank Tracker losers; Broken Link Checker.
- **After any theme, plugin or AIOSEO major update**: rerun the public output checks on the sample URLs.
- **Before and after any site-wide setting change**: back up settings and export content.
