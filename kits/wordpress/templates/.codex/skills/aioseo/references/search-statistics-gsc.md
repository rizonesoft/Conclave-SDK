# Search Statistics and Google Search Console

Search Statistics (Elite), Index Status, Keyword Rank Tracker, content decay, email reports, and GSC status playbooks.

Built from a full read of aioseo.com/docs, /faqs and /blog on 2026-10-11 (AIOSEO Pro 5.0.2 on aioseo.com). Each section lists its source pages. Text in [brackets] is a reviewer note where the vendor advice looks dated or conflicts with Google guidance. UI labels move between versions: confirm on the live site before giving click paths as fact. Unresolved points are in open-questions.md.

## Contents

- SEO Analysis tool and Site Audit
- Search Statistics features (Index Status, Keyword Rank Tracker, Email Reports)
- Search Statistics (Google Search Console integration)
- Google Search Console status troubleshooting playbooks
- Search Statistics / Index Status (mentions only)

## SEO Analysis tool and Site Audit
Sources: https://aioseo.com/docs/using-the-seo-analysis-tool/, https://aioseo.com/docs/how-to-perform-an-seo-audit-of-your-site-using-all-in-one-seo/ (PUBLISHED 2025-08-18, MODIFIED 2026-10-06), https://aioseo.com/docs/seo-analysis-unable-to-connect-to-your-site/

- **Dashboard**: an SEO Site Score card with issue and warning counts, and a **Complete Site Audit Checklist** link.
- **All in One SEO » SEO Analysis**: Your Homepage Score (out of 100) with a mobile screenshot, and the **Complete SEO Checklist** (Important Issues, Recommended Improvements, Good Results; tabs Issues, Warnings, Good).
  - **Refresh Results** re-runs the scan.
  - Expanding a result shows how to fix it.
  - Tabs: **Site Audit**, **Analyze Competitor Site** (enter any URL), **Headline Analyzer**.
- **Site Audit** (**Basic or higher**):
  - **Site Overview** with Passed, Issues and Warnings counts, which filter the report when clicked.
  - **Site Audit Report** per content item, with a Content Types filter and title search.
  - A **Focus Keyword** column, or an **Add Focus Keyword** link.
  - Expand an item to see its audit, with **Fix** and **Ignore** buttons.
  - **All Checks** tab (Issues, Warnings, Good).
  - **Settings** tab: Post Types, Taxonomies and Post Statuses to scan.

Homepage checklist checks and fixes:
- **SEO Title**: missing (set it in Search Appearance » Home Page), too short, too long, "No keywords were found in the page title" (the most common words on the page), "Both the page title and meta description are missing keywords". The keyword ones are safe to ignore if the title is representative.
- **Meta Description**: missing, too short, too long, no keywords.
- **Headings**: no H1 (some themes use the logo; add an H1 to the content anyway), "X H1 tags were found" (should be one), no H2.
- **Images**: some images lack an alt attribute (expand to see which).
- **Links**: no internal links, too few internal links, an uneven internal to external ratio (each can be ignored if justified).
- **Advanced**:
  - No canonical tag (a theme or plugin removed it).
  - A noindex header or meta tag (check Settings » Reading "Search engine visibility" and AIOSEO robots settings).
  - www and non-www not redirected to the same site (the doc says "a CNAME that redirects www" [a CNAME does not redirect; you also need a 301 at the server or host]).
  - robots.txt missing (use Tools » Robots.txt Editor).
  - robots.txt has disallow rules (keep the default `/wp-admin/` disallow).
  - Some Open Graph tags missing (Social Networks » Facebook).
  - Duplicate OG tags (a theme or another plugin).
  - No Schema.org data.
- **Performance** (advanced; safe to ignore if unsure):
  - No "expires" headers on images (Apache or NGINX config, or .htaccess).
  - Unminified JS or CSS.
  - More than **20 requests**.
  - HTML over **50 KB**.
  - Response time over **0.2 s** (use caching).
  - [These thresholds are dated heuristics. Use Core Web Vitals and PageSpeed Insights instead.]
- **Security**: plugins publicly visible, theme visible, directory listing enabled, the site on a Google malware list (clean it, then use the GSC Security Issues report), no HTTPS.

Troubleshooting (the scan runs from AIOSEO's servers, so the site must be reachable on the public internet; local or dev sites won't work):

| Symptom | Cause | Fix |
|---|---|---|
| "We were unable to parse the content for this site." | A firewall, security plugin or CDN (Cloudflare, Incapsula) is blocking or timing out | Whitelist **104.236.26.134** and **159.89.243.35**. Some services won't allow it |
| "We couldn't connect to the site, please try again later." | The homepage source took more than **60 s** | Add caching, optimise JS and CSS (for example Autoptimize; ask the host first), shrink homepage images |
| Results don't match the page source | Stale results, an error page, or a CAPTCHA served to the scanner | **Refresh Results**, whitelist the IPs. A Coming Soon or maintenance page (for example SeedProd) must be turned off before scanning |

## Search Statistics features (Index Status, Keyword Rank Tracker, Email Reports)
Sources: https://aioseo.com/docs/checking-the-index-status-of-content/, https://aioseo.com/docs/using-the-keyword-rank-tracker-feature-in-search-statistics/, https://aioseo.com/docs/how-to-generate-your-seo-email-reports/ (MODIFIED 2026-08-12)

All of these need Search Statistics connected to Google Search Console.

**Index Status** (**Elite**). Search Statistics » **Index Status** tab.
- A **Presence on Google** chart; click a status to filter.
- **Post Index Status** table with filters: All Post Types, Index Status, Robots.txt Allowed Status, Page Fetch Status, Crawled As (desktop or mobile).
- Hover a title for View Post, Edit Post and **Refresh Status** (forces a GSC re-check).
- Expand a row for the GSC detail: how Google found the URL (sitemaps or referring internal links) and any rich results. "No sitemaps listed" means Google did not find the URL via a sitemap; it does not mean the URL is absent from the sitemap.
- **Inspect in Google Search Console** opens URL Inspection.
- The Indexed column in the Dashboard's Content Performance table and the AIOSEO Details icon show a popover with: indexed or not, last crawl, user agent (mobile by default), crawl allowed, indexing allowed, fetch success, and user canonical versus Google canonical.

**Keyword Rank Tracker** (**Elite**). Search Statistics » **Keyword Rank Tracker** tab.
- **Add Keywords**: manually (one per line), from **Focus Keywords**, from a **CSV** (a sample file is provided), or from **Google Search Console** (Performance report keywords).
- **At most 100 keywords scanned at a time.**
- Stats: Total Keywords, Search Impressions, Clicks, Avg. CTR, plus position distribution graphs and a sortable table.
- Click a keyword to see **Related Keywords** (like "People also search for"; Add Keyword on hover) and **Keyword Ranking Pages**.
- **Groups** tab: Create Group (name plus a keyword picker); Add to Group from the Keywords tab (select, then Apply); Star icon creates the **Star group** (favourites). Group stats: Total Groups, Total Keywords, Impressions, Clicks, Avg. CTR.
- **All Keywords**: Keyword Positions graph (Total Keywords, Search Impressions, Avg. Position) and a **Keyword Performance** table (Top Losing and Top Winning tabs; click through to per-page stats).

**Email Reports.** General Settings » Advanced » **Email Summaries** toggle.
- Add recipients; each has its own frequency, **Monthly** or **Weekly**.
- No limit on recipients, but each address must be unique.
- The envelope button sends a test.
- Sections:
  - **SEO Report** (**Elite** and GSC): Top Winning and Losing Posts, Top Winning and Losing Keywords.
  - **Content Summary**: content created in the period, with TruSEO score, CTR and impressions.
  - **SEO Milestones**: CTR and impression changes.
  - **What's New** (vendor updates).

## Search Statistics (Google Search Console integration)

Sources: https://aioseo.com/docs/connecting-search-statistics-to-google-search-console/, https://aioseo.com/docs/using-the-search-statistics-in-all-in-one-seo/, https://aioseo.com/docs/viewing-detailed-search-statistics-for-your-content/

- Tier: **Elite plan**. Index Status is also Elite.
- Path: **All in One SEO > Search Statistics**. Tabs: Dashboard, SEO Statistics, Keyword Rankings (and the Keyword Rank Tracker), Content Rankings, Settings.
- **Connect:** Search Statistics > Settings > **Connect** > Choose an account (or "Use another account") > **Allow** > choose the GSC site from the dropdown > **Complete Connection**. Data then starts fetching, which takes a while.
  - Only data from the GSC Performance report is read.
  - **Disconnect** and **Reconnect** buttons; reconnect only if the connection failed.
  - Settings also chooses which post types are included.
- **Date range:** defaults to the previous 7 days ending yesterday. The current day is never shown because GSC is still recording it. The selector updates every report.

**Dashboard widgets**
- **SEO Statistics**: Search Impressions, Total Clicks, Average CTR and Average Position (based on the highest position whenever the site appeared).
- **Keyword Positions**: average keyword position by range buckets; clicking a legend item hides that range.
- **Keyword Rankings**: Top Keywords and Winning / Losing.
- **Post Optimizations**: the same as the AIOSEO Overview dashboard widget.
- **Content Performance**: tabs Top Pages (most clicks), Top Losing and Top Winning. Columns: Title, TruSEO Score, **Indexed**, Clicks, Impressions, Position, Difference (Diff).
- Each widget has an **Open Report** link.

**SEO Statistics tab**
- A larger graph with selectable metrics. A **Google icon** marks Google system or algorithm updates, with Read More linking to Google's changelog.
- Content Performance table: 10 rows per page, searchable.

**Content Rankings tab** (content decay)
- Columns: TruSEO Score, Indexed, Last Updated On, **Loss** (points lost in the last month against the all-time high, from a proprietary decay algorithm based on impressions, CTR and other factors), **Drop (%)**, and **Performance Score** (a 12-month graph).
- "Slowly Recovering" shows when Drop is under 25% and points have risen for 4 consecutive months.

**Per-post detail** (click a title in Content Performance, Keyword Performance or Content Rankings)
- SEO Scores: TruSEO and Headline Analysis.
- Speed Test: PageSpeed desktop and mobile.
- Suggested Changes: TruSEO recommendations.
- Link Assistant: inbound, outbound, external, affiliate links and suggestions.
- Focus Keyword Trends.
- Redirects: Manage Redirects, or Add Redirect.
- **Google Page Indexing**: indexed yes/no, last crawl, crawling user agent (mobile by default), whether robots.txt allows crawling, whether indexing is allowed, fetch success, and the user-declared canonical against Google's selected canonical.
- SEO Meta: title, description, schema graphs, canonical, robots, additional keywords.
- SEO Performance: graph with Google update icons, WordPress revision icons (View Revisions) and AIOSEO icons (SEO Revisions: user, date, Compare, view, delete).
- Keywords: Top Losing/Top Winning; click a keyword for itemized statistics.
- A link to the Google Search Status Dashboard.

**Index Status**
- The **Indexed** column in Content Performance and Content Rankings, plus the **AIOSEO Details** column on the All Posts and All Pages lists.
- Icons are colour-coded. Hover over an orange or red icon to see the GSC reason (Duplicate without user-selected canonical, Indexed though blocked by robots.txt, 5xx, noindex, Page with redirect, and so on).

---

## Google Search Console status troubleshooting playbooks

Sources: https://aioseo.com/docs/how-to-fix-the-duplicate-without-user-selected-canonical-error-in-google-search-console/, https://aioseo.com/docs/troubleshooting-duplicate-google-chose-different-canonical-than-user-errors/, https://aioseo.com/docs/understanding-the-alternate-page-with-proper-canonical-tag-status-in-google-search-console/, https://aioseo.com/docs/understanding-the-page-with-redirect-status-in-google-search-console/, https://aioseo.com/docs/understanding-and-fixing-the-excluded-by-noindex-tag-status-in-google-search-console/, https://aioseo.com/docs/resolving-indexed-though-blocked-by-robots-txt-in-google-search-console/, https://aioseo.com/docs/server-error-5xx-in-google-search-console/, https://aioseo.com/docs/how-to-identify-and-fix-soft-404-errors/ (all published 2025)

**Finding affected URLs (common to all):**
- GSC: Indexing > Pages > "Why pages aren't indexed" (or "Improve page appearance") > click the reason > Examples.
- In AIOSEO, use Index Status (Elite).
- After fixing, use URL Inspection > (TEST LIVE URL) > **Request Indexing**. For many URLs, use **Validate Fix** in the Page indexing report.
- Validation stops at the first remaining instance. Do not click Validate Fix again until validation passes or fails. It usually takes up to about 2 weeks, and Google emails the result.

| GSC status | Meaning | AIOSEO fix |
|---|---|---|
| Duplicate without user-selected canonical | Duplicates exist and none declares a canonical (URL variants, www/non-www, parameters, duplicate meta) | Edit the post > AIOSEO Settings > **Advanced** > **Canonical URL** (absolute URL). Or Redirects: 301 the duplicate to the canonical. Or noindex the duplicate (Advanced > Robots Settings > turn off Use Default Settings > No Index). Exclude duplicates from the sitemap. Then Request Indexing. Use Siteliner or Ahrefs Site Audit to find duplicates |
| Duplicate, Google chose different canonical than user | Google rejected the declared canonical (conflicts, http/https or www variants, duplicate content) | Set the correct Canonical URL; consolidate the content; 301 the non-canonical; keep only preferred URLs in the sitemap; Request Indexing. The doc says "always use HTTPS and non-www" [HTTPS yes; www versus non-www is a free choice as long as it is consistent] |
| Alternate page with proper canonical tag | Informational: Google honoured your canonical (e.g. `?filter=1`) | Usually no action needed. Optionally 301 with a **Query Parameters** option (see Redirects) |
| Page with redirect | The URL redirects; Google indexes the target | Usually fine. Check with httpstatus.io, where the **X-Redirect-By** response header shows the source (e.g. WordPress adding a trailing slash). Fix loops, chains and wrong targets in Redirection Manager |
| Excluded by 'noindex' tag | The page has noindex | Check per post (Advanced > Robots Settings); per content type (Search Appearance > Content Types > [type] > Advanced > Robots Meta > No Index); Search Appearance > Advanced > turn off Use Default Settings > **No Index Paginated**; WordPress Settings > Reading > "Discourage search engines from indexing this site" must be unchecked; robots.txt Disallow rules. RSS `/feed/` URLs are noindexed by default; AIOSEO recommends leaving them that way |
| Indexed, though blocked by robots.txt | Indexed from links but cannot be crawled | Remove or adjust the Disallow in Tools > Robots.txt Editor; check in URL Inspection > TEST LIVE URL > "Crawl allowed?" = Yes; for unwanted pages use noindex and allow crawling; 301 blocked pages that have external links |
| Server error (5xx) | Server failed (500, 501, 502, 503, 504, 505, 507) | Server error logs; resources (CPU, RAM, storage); disable plugins and themes to find conflicts; CDN; host support; then validate |
| Soft 404 | A 200 response on an empty or "not found" page | Gone for good: return **410** through Redirection Manager. Moved: **301**. Thin: add content. Keep but hide: noindex. Find them through GSC, URL Inspection, server logs and httpstatus.io |

- The 404/410 guidance contradicts itself. The "add redirect when deleting" doc says Google "may consider 410 URLs as Soft 404" and that this is normal. [Google treats 410 roughly like 404 and does not call it a soft 404; a redirect to an irrelevant page, such as the homepage, is what Google flags as soft 404.]

---

## Search Statistics / Index Status (mentions only)
Sources: https://aioseo.com/docs/checking-index-status-in-google-search-results/, https://aioseo.com/docs/how-to-self-assess-your-content-to-see-if-its-helpful-reliable-and-people-first/

- **Index Status (Elite):**
  - **All in One SEO » Search Statistics » Index Status** tab.
  - Also the Index Status icon (with a hover popup) in the **AIOSEO Details** column on All Posts.
- **Diagnosing traffic drops:**
  - Search Statistics shows GSC data in wp-admin.
  - Keyword Rank Tracker compares rankings.
  - **SEO Revisions** (Pro) shows SEO changes you made.
