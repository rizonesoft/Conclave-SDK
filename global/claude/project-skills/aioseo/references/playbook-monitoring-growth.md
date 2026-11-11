# Playbook: monitoring, reporting and growth

Scope: how to read and act on performance data for a WordPress site running AIOSEO Elite, and how to grow it safely. It covers Search Statistics workflows (dashboard, Content Performance, Keyword Rankings, Content Rankings decay, position playbooks, Keyword Rank Tracker, Index Status, SEO Revisions and Google update markers), Google Search Console and GA4 routines, SEO Alerts and email reports, traffic-drop and algorithm-update diagnosis, off-site monitoring with Google Alerts, white-hat link building and digital PR, reporting cadence and KPIs, seasonal pages such as Black Friday, and the AIOSEO comparison with Yoast, Rank Math and SEOPress plus migration steps. It is distilled from aioseo.com blog posts (vendor content, 2015 to October 2026) and corrected against Google's documentation. Settings screens and click-by-click UI are in search-statistics-gsc.md, redirects-links.md and tools-migration-multisite.md; this file names the feature and its menu path in one line and focuses on decisions. Vendor statistics are labelled "(vendor claim)".

## Contents

- Reading Search Statistics
- Position playbooks (what to do at each ranking band)
- Keyword Rank Tracker
- Content decay workflow
- Index Status checks
- Measuring the effect of a change (SEO Revisions and update markers)
- Google Search Console routines
- GA4 and behaviour data
- SEO Alerts, email reports and automatic monitoring
- Traffic-drop diagnosis
- Responding to a Google update
- Off-site monitoring with Google Alerts
- Link building and digital PR (white hat)
- Links and offers to refuse, disavow and negative SEO
- Reporting cadence, KPIs and goals
- Seasonal pages (Black Friday and other annual events)
- AIOSEO compared with Yoast, Rank Math and SEOPress
- Migrating from Yoast or Rank Math to AIOSEO

## Reading Search Statistics

Search Statistics (All in One SEO > Search Statistics, Elite) is Google Search Console data shown inside WordPress. It is not a separate rank scraper: positions are GSC average positions, clicks and impressions are GSC numbers, and it inherits GSC's limits (about a 2 to 3 day lag, 16 months of history, query anonymisation for rare queries). Connect it once through All in One SEO > General Settings > Webmaster Tools > Connect to Google Search Console (no verification tag needed; sitemaps sync automatically).

What each report answers:

| Report (path) | Question it answers | Columns to read |
|---|---|---|
| Dashboard | Is overall visibility rising or falling? | Search Impressions, Total Clicks, Average CTR, Average Position, Keyword Positions buckets, Post Optimizations |
| SEO Statistics tab (timeline) | When did a change happen, and does it line up with a Google update or one of my edits? | Impressions/clicks graph, Google update markers (hover for name, Read More), SEO Revisions markers (AIOSEO logo) |
| SEO Statistics > Content Performance | Which pages are winning or losing? | Top Pages, Top Winning, Top Losing; Clicks, Impressions, Position, Diff. Click a page for its SEO Performance timeline and a Speed Test |
| Keyword Rankings / Keyword Performance | Which queries are winning or losing? | Total Keywords, Top Winning, Top Losing, Clicks, Avg CTR, Impressions, Position, Diff |
| Content Rankings | Which posts are decaying over 12 months? | Last Updated On, Loss, Drop %, Performance Score, TruSEO score, index status |
| Keyword Rank Tracker | How are my chosen keywords moving? | Clicks, Avg CTR, Impressions, Position, Position History |
| Index Status | Is each URL indexed, and if not, why? | Status bucket, reason, robots.txt, page fetch, crawled as, last crawl |

Reading rules:
- Impressions are the visibility metric; clicks are the outcome. Rising impressions with flat clicks usually means new low positions or a SERP feature absorbing clicks, not a problem by itself.
- Average position is an impression-weighted average across every query, device and location a page appears for. A page can "drop" in average position because it started appearing for many new long-tail queries at low positions. Always check position at the query level before acting.
- Diff in Content Performance and Loss in Content Rankings are AIOSEO's own scores (the blog calls Diff a "proprietary point system" and Loss a decay score built from impressions and CTR). Use them to sort, then read the underlying clicks and impressions before deciding.
- Ignore pages younger than about 3 months when judging performance; they are still settling.
- Use the per-page Speed Test only as a spot check; field data in GSC's Core Web Vitals report is what Google uses.

Sources: https://aioseo.com/how-to-check-blog-stats/, https://aioseo.com/how-to-use-seo-data-to-boost-search-rankings/, https://aioseo.com/how-to-easily-monitor-seo-rankings-in-wordpress/, https://aioseo.com/how-to-stop-content-decay-and-regain-lost-traffic/, https://aioseo.com/what-is-search-visibility/, https://aioseo.com/simple-guide-to-seo-analytics/, https://aioseo.com/how-to-track-keyword-rankings-in-wordpress/

## Position playbooks (what to do at each ranking band)

Work from the query level (Keyword Rankings, or GSC Performance filtered to the page). The vendor's 2023 position playbook is useful as a triage order; it is restated here with Google-aligned actions.

| Band (average position for the main query) | Likely constraint | Action |
|---|---|---|
| 1 | Holding | Protect: keep facts current, watch Top Losing, do not change the URL or rewrite heavily without reason |
| 2-4 | Click share | Rewrite the title link and meta description for the dominant intent; add structured data only where Google still shows a rich result for that type (Product, Review snippet, Recipe, Event, Video, Breadcrumb). Do not rely on FAQ or HowTo markup: HowTo rich results were removed in 2023 and FAQ rich results stopped showing for all sites on 7 May 2026 |
| 4-7 | Visibility on the page | Answer the query in the first lines under a descriptive heading, add a table of contents (jump links may appear but Google decides), improve images and examples; check who holds any featured snippet and how their answer is shaped |
| 7-10 | Content fit | Content audit: does the page match the intent and format of the current top results, is it complete, accurate and current, does it have internal links from relevant pages (Link Assistant suggestions to the page)? |
| 11-20 (page 2) | Strength and depth | Fastest wins per the vendor and consistent with experience: refresh, merge overlapping posts into this one, add internal links from your strongest pages, earn a few relevant links |
| 10-15 (if content is already strong) | Technical | Check indexing, canonical, speed and Core Web Vitals field data, redirect chains, crawl errors |
| 15-20 and beyond | Competition | Compare with ranking pages (AIOSEO SEO Analysis > Analyze Competitor Site, or a crawler); decide whether the keyword is realistic or whether a longer-tail variant should be the target |

Quick-win selection rules (merged from several posts):
1. Filter for positions 4-20 with meaningful impressions; these move most with the least work.
2. High impressions plus low CTR on an otherwise stable position: fix the title and description first (Google may rewrite either, so write for the query and test again after recrawl).
3. Refresh priority after that: positions 8-15, outdated statistics or screenshots, no direct answer near the top, a SERP format mismatch (a story where lists rank).
4. Exclude pages under 3 months old.
5. Work in batches (the content-audit post suggests 10 pages per batch, starting with the top 30 candidates) and re-check after 4-8 weeks.

Vendor numbers often quoted for these bands, all (vendor claim) without a named primary source: moving from position 2 to 1 gives about 74% more clicks; each position up adds about 2.8% CTR; a post sliding from 4 to 11 loses more than 70% of clicks; #1 gets 27.6% to 39.8% of clicks. They disagree with each other and vary with SERP features and AI Overviews; use them only to explain why page 2 matters.

Conflict: several posts say "higher CTR makes Google rank you higher". Google says it does not use GA data or bounce rate, and does not document CTR as a direct ranking factor; 2023 US DOJ trial testimony described Navboost using aggregated click data. Treat click data as something Google may use in aggregate, not a lever to pull. CTR work is traffic work.

Sources: https://aioseo.com/search-statistics-power-hacks-to-help-boost-your-rankings/, https://aioseo.com/how-to-do-a-content-audit-for-seo/, https://aioseo.com/restaurant-seo/, https://aioseo.com/seo-for-bloggers/, https://aioseo.com/keyword-gap-analysis/, https://aioseo.com/ways-to-increase-your-organic-clickthrough-rates/, https://aioseo.com/aioseo-vs-seopress/, https://aioseo.com/how-to-get-featured-snippets-on-google/

## Keyword Rank Tracker

Path: All in One SEO > Search Statistics > Keyword Rank Tracker (Elite). Data comes from GSC (average position), so it shows only queries your site already gets impressions for; keywords past position 100 show no data.

Adding keywords (four methods, merged across posts):
1. Import from Google Search Console (picker of queries you already rank for; added January 2025).
2. Import focus keyphrases already set in posts.
3. CSV upload.
4. Manual entry.

Limits and organisation:
- Cap stated as 100 tracked keywords (January 2025 post; may be plan dependent, confirm in the UI).
- Use groups for topic clusters, campaigns or clients; favourites for the handful that matter commercially.
- Pick tracked keywords by business value: money terms, priority clusters, branded terms, seasonal terms ahead of the season.

Related keywords: expand a tracked keyword's row to see related queries; select > Bulk Actions > Add to track them. A related query with impressions but no page targeting it is a content idea; one that matches an existing page is a section or heading to add. Check difficulty before assuming a related term is easy.

Five uses the posts describe:
1. Diagnose losers: Top Losing tab, Diff shows positions lost; update the page or test a new title.
2. Learn from winners: Top Winning; replicate the format, depth and internal-link pattern.
3. Ideation: related keywords into clusters.
4. Intent check: read the live SERP for losing terms; intent may have shifted.
5. Competitor work: pair with keyword gap tools (Semrush Keyword Gap, Ahrefs Content Gap) for terms you do not rank for at all, which this tracker cannot see.

For local businesses use a proximity grid tool (BrightLocal, Semrush local heatmaps) for local pack rank; GSC average position does not show map-pack position by neighbourhood. Manual checks in an incognito window are approximate because location still personalises results.

Sources: https://aioseo.com/how-to-import-google-search-console-keywords-to-wordpress/, https://aioseo.com/how-to-check-google-rankings/, https://aioseo.com/how-to-improve-keyword-rankings/, https://aioseo.com/how-to-use-a-keyword-ranking-tool/, https://aioseo.com/how-to-use-googles-people-also-search-for/, https://aioseo.com/what-are-related-keywords/, https://aioseo.com/what-keywords-is-my-site-ranking-for/, https://aioseo.com/how-to-check-seo-rankings/

## Content decay workflow

Decay is a gradual loss (the vendor's rule of thumb: over about 6 months, on posts 12+ months old, often not updated in a year, with newer or better competitors). A sudden drop is not decay; use Traffic-drop diagnosis instead.

Find decaying pages:
1. Content Rankings (Search Statistics > Content Rankings): default sort is biggest Loss first; read Drop % and Performance Score (12-month); check Last Updated On to see if a past edit coincided.
2. Content Performance > Top Losing, then Diff.
3. Keyword Rankings > Top Losing for the specific high-value query that is slipping.
4. Average CTR falling while position holds: usually a stale title/description or a new SERP feature.
5. Without Search Statistics: GSC Performance > Pages, compare last 6 months with previous 6 months (or last 3 months year on year for seasonal sites), sort by click difference.

Decide per page:

| Signal | Action |
|---|---|
| Still relevant, slipping, has impressions | Refresh: update facts, examples, screenshots; answer the query earlier; new title and description if CTR fell; add internal links |
| Intent changed (SERP now shows a different format) | Re-shape to the format that ranks, or re-target the page at the query it actually ranks for |
| Several posts competing for the same query | Consolidate into the strongest URL, 301 the others (Redirection Manager) |
| No traffic, no links, no business value | Remove: 301 to the closest relevant page, else 404/410; check backlinks first |
| Unsure | Refresh rather than delete |

Vendor thresholds worth keeping as starting points: under 100 clicks (or impressions) in 12 months means review, not automatic deletion; never hard-delete a page with 15+ referring domains; only prune content older than 6-12 months; prune in batches and log every decision; monitor 4-12 weeks after.

Dates: change the visible "updated" date only when the update is substantive. Google asks for accurate dates and warns against faking freshness. Keeping the original publish date and showing a real updated date is the safe pattern. Freshness matters for queries that need it, not universally (several posts call freshness a "confirmed ranking factor"; that is overstated).

Cadence: top content every 6-12 months, quarterly in fast-moving niches, plus after any core-update drop.

Sources: https://aioseo.com/how-to-stop-content-decay-and-regain-lost-traffic/, https://aioseo.com/content-pruning-seo/, https://aioseo.com/how-to-do-a-content-audit-for-seo/, https://aioseo.com/how-to-easily-monitor-seo-rankings-in-wordpress/, https://aioseo.com/how-to-optimize-existing-content-for-seo/, https://aioseo.com/seo-tips/

## Index Status checks

Path: All in One SEO > Search Statistics > Index Status (Elite), plus the Index Status icon in the AIOSEO Details column of the Posts list. Buckets: Indexed; Crawled, not indexed; Discovered, not indexed; Other, not indexed; No results yet. Each row shows the reason, robots.txt, page fetch, crawled as (mobile or desktop), rich results, last crawl, and Google-selected vs declared canonical, with a link to GSC URL Inspection.

Monitoring rules:
- Review monthly, and after publishing a batch, a migration, or a theme change.
- "Discovered, not indexed": strengthen internal links (Link Assistant orphan report), keep the URL in the sitemap.
- "Crawled, not indexed": improve or merge the content, add internal links; request indexing only after fixing.
- Google-selected canonical differs from yours: fix duplicates and internal links to the preferred URL.
- Repeated Request Indexing or sitemap resubmission does not speed anything up.

Fix procedures (noindex, robots.txt, canonical, soft 404) are in playbook-technical.md and search-statistics-gsc.md.

Sources: https://aioseo.com/how-to-check-your-google-index-status-in-wordpress/, https://aioseo.com/why-wont-google-index-my-content/, https://aioseo.com/website-not-showing-up-on-google/, https://aioseo.com/crawled-currently-not-indexed/, https://aioseo.com/best-google-index-checker/, https://aioseo.com/organic-search-traffic/

## Measuring the effect of a change (SEO Revisions and update markers)

SEO Revisions logs SEO edits from the post editor and lets you annotate what changed and why; the edits appear as AIOSEO-logo markers on the Search Statistics timeline (SEO Statistics > Content Performance > click post > SEO Performance), next to Google update markers. Details in content-optimization.md.

Before/after procedure:
1. Annotate the change with what and why (for example "rewrote title for 'X vs Y' intent").
2. Change one thing per page at a time where you can; several edits at once cannot be attributed.
3. Confirm Google recrawled the page (Index Status last crawl, or URL Inspection). The vendor says wait "a few days"; for most pages allow 2-4 weeks of data.
4. Compare equal windows (for example 28 days before vs 28 days after, same weekdays) and check the timeline for a Google update or seasonal swing inside the window.
5. Read impressions first (did visibility change?), then position at query level, then CTR, then clicks.
6. Record the outcome in the annotation so winning changes can be repeated.

Algorithm-update markers: hover for the update name; use them to separate "my edit" from "Google changed something". The vendor says no other WordPress SEO plugin overlays updates (vendor claim).

Timelines: the posts give no fixed timeframe ("weeks or months"); vendor anecdotes put local results at 3-6 months and competitive niches at 6-12. Treat all as anecdotes.

Sources: https://aioseo.com/how-to-track-seo-changes/, https://aioseo.com/how-long-does-seo-take-to-show-results-rank-faster/, https://aioseo.com/how-to-monitor-seo-performance-in-wordpress/, https://aioseo.com/how-to-monitor-the-impact-of-google-algorithm-updates-in-wordpress/, https://aioseo.com/helpful-content-update/, https://aioseo.com/keyword-difficulty-in-seo-what-is-it-and-how-to-use-it/

## Google Search Console routines

Search Statistics covers most day-to-day reading; use GSC directly for filters, exports, indexing tools and anything Search Statistics does not show.

Performance report:
- Weekly glance: clicks, impressions, CTR, average position (enable all four).
- Page then queries: Pages tab > click a URL > Queries tab, last 3 months, sort by clicks or impressions. Rewrite the page to cover the queries it actually earns, and find unplanned queries worth their own page.
- Decay: Date > Compare, last 6 months vs previous 6 months (or year on year), export.
- Country: filter Country for international sites; pair with language-specific pages.
- Device and search appearance filters to separate mobile issues and rich-result changes.
- Data retention is 16 months; export monthly if you need longer history.
- Position is an average; use query plus page filters before drawing conclusions.
- AI Mode traffic is counted in the Web search type (Google, 2025). The vendor reports separate AI Overview and AI Mode segments added in June 2026; verify in your property before relying on it. AI visibility measurement is in playbook-ai-search.md.

Indexing and health:
- Indexing > Pages (formerly Coverage): click each "not indexed" reason to list URLs.
- URL Inspection: Test Live URL, then Request Indexing after a fix. It queues a crawl; it does not force indexing.
- Sitemaps: confirm status Success; removing an old sitemap does not hurt.
- Core Web Vitals report (Experience section): field data, INP not FID.
- Security & Manual Actions > Manual Actions: check after any sharp drop. Fix, then Request Review.
- robots.txt report (Settings) replaced the old robots.txt tester in 2023.
- Settings > Change of Address for domain moves (see playbook-technical.md); keep 301s at least a year.

Retired items still mentioned in older posts: Index Coverage name, Mobile Usability report, preferred domain setting, URL Parameters tool, robots.txt tester, Structured Data Testing Tool. Disavow is a separate legacy tool, not part of routine GSC work.

Property setup: a Domain property (DNS verification) covers all protocols and subdomains; a URL-prefix property must match https and www exactly. After an HTTPS or domain change, make sure the new property exists and Search Statistics points at it.

Sources: https://aioseo.com/how-to-add-google-search-console-to-your-wordpress-website/, https://aioseo.com/how-to-set-up-google-search-console/, https://aioseo.com/how-to-connect-site-to-google-without-google-search-console-verification-code/, https://aioseo.com/google-search-console-vs-google-analytics/, https://aioseo.com/seo-tips/, https://aioseo.com/international-seo-keyword-research/, https://aioseo.com/googles-ai-search-overhaul/, https://aioseo.com/https-and-seo/

## GA4 and behaviour data

GSC is Google organic only (impressions, clicks, positions, indexing); GA4 is all channels and on-site behaviour (sessions, engagement, key events, revenue). Start with GSC on a new site and add GA4. Universal Analytics stopped processing in July 2023, so paths like "Audience > Geo" or "Goals" in older posts no longer exist; Google Optimize was sunset in September 2023.

Routines:
- Organic landing pages: Reports > Acquisition > Traffic acquisition, filter Session default channel group = Organic Search; then Engagement > Landing page.
- Intent mismatch smoke test (vendor heuristic): pages with healthy organic sessions but very short engagement time (under about 30 seconds) deserve a SERP check and a look at the first screen of content.
- Measure outcomes with key events (GA4's name for conversions since 2024) and ecommerce revenue, not traffic alone. The vendor's own revenue examples make the point: fewer, higher-intent visits can out-earn large informational traffic.
- Country and language: Reports > User attributes > Demographic details.
- AI assistant referrals (chatgpt.com, perplexity.ai and similar) show as referral traffic; see playbook-ai-search.md.

Bounce rate: GA4 does report it (it was re-added in 2022 as the share of sessions that were not engaged). It is a UX diagnostic, not a Google ranking factor; Google has said it does not use GA data for ranking. Several posts claim bounce, dwell time or time on page are ranking signals; others (including the vendor's own bounce-rate post) say they are not. Use the Google position. A high bounce rate on a contact or answer page can be fine.

Microsoft Clarity (heatmaps, recordings, rage and dead clicks) connects at General Settings > Webmaster Tools > Microsoft Clarity (paste the project ID). It helps diagnose UX; it does not affect SEO directly.

Sources: https://aioseo.com/google-search-console-vs-google-analytics/, https://aioseo.com/best-seo-tools-for-beginners/, https://aioseo.com/is-bounce-rate-a-ranking-factor/, https://aioseo.com/how-to-add-microsoft-clarity-to-wordpress/, https://aioseo.com/user-behavior-analytics-in-seo/, https://aioseo.com/simple-guide-to-seo-analytics/, https://aioseo.com/important-sections-of-google-analytics-explained/

## SEO Alerts, email reports and automatic monitoring

SEO Alerts (All in One SEO > Tools > SEO Alerts > Enable SEO Alerts; announced in 2026, available on every plan including Lite):
- Checks hourly for three failures: homepage set to noindex, robots.txt fails to load, XML sitemap fails to load. All three are on by default.
- Sends at most one alert per issue per day, by email (multiple addresses) and/or a Slack incoming webhook (Slack member IDs for @mentions); Test buttons confirm delivery.
- It does not check rankings, traffic, broken links, 404s, noindex on pages other than the homepage, canonicals, or Search Console errors.
- Typical causes it catches: a plugin or theme update, a staging push that left "Discourage search engines" ticked (Settings > Reading), a caching or server rule that breaks the sitemap.

Cover the gaps with:
- 404s: Redirection Manager 404 Logs (Redirects > Settings > enable 404 logs, review weekly); see redirects-links.md.
- Broken links: Broken Link Checker (separate AIOSEO plugin, scans every 3 days on AIOSEO servers).
- Performance: Search Statistics and GSC email notifications (manual actions, security issues, indexing spikes).
- Site Health: AIOSEO adds SEO checks to Tools > Site Health; the setup wizard's Smart Recommendations email flags critical issues.

Email reports: General Settings > Advanced > Email Summaries (some posts and versions call it Email Reports). Add several recipients, set weekly or monthly per recipient, use the envelope icon to send a test. Content: top winning and losing posts and keywords, content summary, posts to optimise, milestones. One post states it is Elite. Use it for client and team reporting; it does not replace reading the reports when something moves.

SERP volatility trackers (Semrush Sensor scores 0-10: 0-2 low, 2-5 normal, 5-8 high, 8-10 very high) show whether Google results are moving in general. They are context only and do not tell you whether your site was affected.

Sources: https://aioseo.com/best-seo-monitoring-tools/, https://aioseo.com/google-alerts-for-seo/, https://aioseo.com/seo-sensor/, https://aioseo.com/automated-seo-reports/, https://aioseo.com/best-seo-reporting-tools/, https://aioseo.com/seo-report-generator/, https://aioseo.com/how-to-check-site-health/

## Traffic-drop diagnosis

Run in this order; the early steps are cheap and catch the catastrophic causes.

1. Indexability first. Check SEO Alerts history, then: homepage and key templates not noindexed (Posts list noindex indicator, page source), robots.txt not disallowing key paths, sitemap loads, Settings > Reading visibility box unticked. A stray noindex blocking a whole site for months is a recurring vendor anecdote.
2. Real drop or tracking problem? Confirm the drop in GSC as well as GA4. A GA-only drop is usually a tag, consent or filter change.
3. Shape and timing. A sharp cliff on specific days points to a technical change, a manual action or a Google update; a gradual slide over months points to decay or competition. Overlay the Search Statistics update markers and Google's Search Status Dashboard; use volatility tools only as context.
4. Manual actions and security issues in GSC.
5. Scope it. Which pages (Content Performance > Top Losing), which queries (Keyword Rankings > Top Losing), which devices, countries, branded vs non-branded? Compare year on year to rule out seasonality.
6. Read what changed in the SERP. Impressions stable but clicks down: a new SERP feature or AI Overview, or a snippet change. Impressions down: ranking or indexing loss.
7. Recent site changes: SEO Revisions log, plugin/theme updates, redirects, URL changes, migration.
8. If it is gradual and page-level, use the Content decay workflow.

The vendor's suggested order for a sudden 20% drop (alerts, then volatility, then Search Statistics page and keyword level, then decay) matches this.

Sources: https://aioseo.com/seo-sensor/, https://aioseo.com/google-june-2026-spam-update/, https://aioseo.com/website-not-showing-up-on-google/, https://aioseo.com/how-to-stop-content-decay-and-regain-lost-traffic/, https://aioseo.com/organic-search-traffic/, https://aioseo.com/how-to-monitor-the-impact-of-google-algorithm-updates-in-wordpress/, https://aioseo.com/best-seo-monitoring-tools/, https://aioseo.com/seo-checkers/

## Responding to a Google update

Rules:
1. Wait until the rollout is finished (Google Search Status Dashboard) before judging. The vendor reported the June 2026 spam update as running 24 June to 26 June 2026 (vendor-reported; confirm on the dashboard).
2. Do not change everything at once. Mass edits during a rollout make recovery impossible to attribute.
3. Compare a window after the rollout with the same-length window before, at page and query level.
4. Identify the type. Core update: review affected pages against Google's helpful, people-first content questions (experience, originality, accuracy, intent fit). Spam update: check against Google's spam policies (scaled content abuse, site reputation abuse, expired domain abuse, link spam). Manual action: fix and request review.
5. Recovery from a core update usually takes months and often shows at a later core update; the vendor says 2-4 months minimum (vendor claim). Small timestamp edits or keyword tweaks do not help.
6. Log what you change in SEO Revisions so the next update can be read against it.

Older posts describe the Helpful Content Update as a separate system; Google folded it into core ranking in March 2024. The people-first principle still applies. Claims drawn from the 2024 leaked API documents (Navboost, siteAuthority, sandbox, freshness) are hypotheses: an attribute existing in the documents does not show how, or whether, it is used.

Sources: https://aioseo.com/google-june-2026-spam-update/, https://aioseo.com/how-to-monitor-the-impact-of-google-algorithm-updates-in-wordpress/, https://aioseo.com/helpful-content-update/, https://aioseo.com/google-search-algorithm-leak/, https://aioseo.com/google-ranking-factors/, https://aioseo.com/eeat-and-ymyl/

## Off-site monitoring with Google Alerts

Set alerts at google.com/alerts from a shared team account; Show options for frequency, sources, language, region, how many, and email or RSS delivery. Test each query in Google Search first.

Useful queries:

| Goal | Query pattern | Action |
|---|---|---|
| Unlinked brand mentions | `"Brand" -site:yourdomain.com` | Ask the author to add a link where it helps their readers |
| Link-target pages | `intitle:"best" "topic" tools` | Pitch your resource if it genuinely fits the list |
| Competitor activity | `site:competitor.com`, `"Competitor" -site:competitor.com` | See what they publish and where they are mentioned |
| Guest-post openings | `"write for us" "niche"` | Vet the site for relevance and editorial standards first |
| Plagiarism | a unique sentence from each of your top 5-10 pages, in quotes | Ask for removal or credit; DMCA if needed |
| Industry news | `"Google core update"` and topic terms | Context for timeline changes |

Scraped feeds: All in One SEO > General Settings > RSS Content adds a link back to the original before or after each feed item, so scraped copies credit you.

Sources: https://aioseo.com/google-alerts-for-seo/, https://aioseo.com/how-to-customize-the-rss-feed-in-wordpress/, https://aioseo.com/negative-seo/, https://aioseo.com/seo-reputation-management/

## Link building and digital PR (white hat)

Google's position: links help it discover pages and understand importance; links you place, buy or exchange to manipulate rankings are link spam. Earn links by being worth citing. Google's Gary Illyes said in 2023 that links are not among the top three ranking factors (as reported in a vendor post); older vendor posts still call them a top-two or top-three factor. Content quality first, links second.

Tactics worth doing, in rough order of effort to value:
1. Fix your own site first: content worth linking to, internal links to the pages you want to grow.
2. Unlinked mentions: Google Alerts query above; polite request.
3. Linkable assets: original research or data, statistics pages with sources, case studies, calculators and free tools, templates and cheat sheets. Keep them evergreen and updated.
4. Broken link building: find dead pages on relevant sites that others linked to, offer your replacement; also offer updated content to sites linking to an outdated competitor page.
5. Digital PR: data stories for industry or local press, expert commentary, podcasts, speaking, local news op-eds.
6. Relationship links: partners, suppliers, manufacturers, industry associations, chambers of commerce, sponsorships and events, local schools and resource pages. The value is relevance and referral traffic.
7. Guest posting done right: relevant sites with real readers, written for that audience, one link at most where it helps, no casino/drug-type destinations. Paid or fee-based placements must carry `rel="sponsored"`. Large-scale guest posting with keyword-rich anchors is a link scheme under Google's spam policy.
8. Barnacle SEO: complete profiles on directories, review sites, marketplaces and platforms that already rank for your terms (Google Business Profile, Yelp, industry directories, G2, LinkedIn). These links are mostly nofollow or UGC; the value is SERP real estate and referrals, not "authority".
9. Expert roundups: participate where relevant.

Link attributes (WordPress link popover, with AIOSEO toggles): `rel="sponsored"` for paid, affiliate and advertorial links; `rel="ugc"` for comments and forums; `rel="nofollow"` when you do not vouch for a link. Google treats all three as hints (since March 2020). Normal editorial links out to good sources need no attribute. Check an inbound link's attributes with View Page Source and a search for the anchor text.

Measuring: GSC Links report (top linking sites); Ahrefs or Semrush for referring domains, new and lost links. Referring domains matter more than raw backlink count. Domain Authority, Domain Rating and Authority Score are third-party estimates that Google does not use; use them only as rough benchmarks.

Vendor statistics from the 2022 link-building statistics post are unsourced in the text and dated; at most, cite them as (vendor claim), for example "#1 results have 3.8x more backlinks than positions 2-10" (vendor claim, correlation only).

Sources: https://aioseo.com/link-building-guide/, https://aioseo.com/how-to-use-barnacle-seo/, https://aioseo.com/referring-domains-vs-backlinks-seo/, https://aioseo.com/seo-guide-nofollow-sponsored-ugc-links/, https://aioseo.com/sponsored-links-what-are-they-and-do-they-impact-seo/, https://aioseo.com/nofollow-vs-dofollow-links/, https://aioseo.com/local-seo/, https://aioseo.com/keyword-research/

## Links and offers to refuse, disavow and negative SEO

Refuse:
- Buying links that pass ranking credit (no `rel="sponsored"`), link packages, "high DA link lists".
- PBNs and splogs (odd topic mix, expired domains with inflated metrics).
- Link exchanges and reciprocal linking at scale.
- Expired-domain abuse (buying an aged domain to rank unrelated content) and scaled AI content; some posts call these "gray hat", but both are named spam policies since March 2024.
- Article spinning or paraphrasing tools to produce many versions for guest posts or networks.
- Agencies promising guaranteed page-1 rankings, fake Lighthouse or PageSpeed reports (check the real score in PageSpeed Insights), free guest content with hidden links, fake traffic, cold calls claiming to be Google about your listing, monthly "citation management" fees, copy-paste "detailed audits".

The vendor's own paid-links post reports an Isotropic test that bought 90,000 Fiverr links, received about 12,000, mostly nofollow and low quality, with no benefit (vendor-reported experiment).

Disavow: Google says most sites never need it and that it ignores most spammy links automatically. Use the disavow tool only when there is a manual action for unnatural links, or when you (or a previous owner) knowingly built or bought links and cannot get them removed. Do not run routine "toxic score" clean-ups from third-party tools; several vendor posts recommend disavowing "immediately", which is outdated. Low-authority links from real small sites are normal, not toxic.

Manual action recovery: GSC > Security & Manual Actions > Manual Actions; remove or nofollow the offending links, document the work, disavow what you cannot remove, then Request Review. There is no guarantee of a quick reversal.

Negative SEO (spam links, scraping, hacking, fake reviews, fake DMCA requests, aggressive crawling): monitor, harden security (updates, 2FA, backups, WAF), report fake reviews, file DMCA for scraped copies. Spam links pointed at you are usually ignored by Google; disavow only if a manual action appears.

Sources: https://aioseo.com/what-are-paid-links-in-seo/, https://aioseo.com/toxic-backlinks/, https://aioseo.com/negative-seo/, https://aioseo.com/small-business-seo-scams-how-to-detect-and-avoid-them/, https://aioseo.com/white-hat-vs-black-hat-seo/, https://aioseo.com/website-authority/, https://aioseo.com/best-ai-paraphrasing-tools/, https://aioseo.com/link-building-statistics/

## Reporting cadence, KPIs and goals

Cadence:

| Frequency | What | Where |
|---|---|---|
| Hourly (automatic) | Homepage noindex, robots.txt, sitemap availability | SEO Alerts |
| Weekly | Clicks, impressions, CTR, position for high-traffic sites; 404 log; manual actions/security emails | GSC, Search Statistics dashboard, Redirects 404 Logs |
| Monthly | Top Winning/Losing pages and keywords, Content Rankings decay, tracked keywords, Index Status, Site Audit issues, orphan pages, broken links, KPI report | Search Statistics, SEO Analysis, Link Assistant, Broken Link Checker, Email Summaries |
| Quarterly | Partial content audit, keyword map review, competitor review, local grid ranks, Core Web Vitals field data | Content audit sheet, GSC, third-party tools |
| Annually | Full content audit, seasonal calendar, plugin and licence review | All of the above |
| Event-triggered | After migration, redesign, theme or plugin change, sharp drop, core update | Traffic-drop diagnosis |

Small sites can report monthly; high-traffic sites weekly. The vendor suggests a weekly maintenance hour and competitor audits every quarter (or every 6 months with SEO Analysis > Analyze Competitor Site).

KPIs (pick the few that map to the business):
- Organic clicks and impressions (GSC).
- Organic key events and revenue (GA4).
- Positions of priority keywords (Keyword Rank Tracker), read as average positions.
- Pages losing traffic (Content Rankings).
- Indexed vs submitted important URLs (Index Status, Page indexing).
- Core Web Vitals pass rate (field data: LCP 2.5 s, INP 200 ms, CLS 0.1 at the 75th percentile).
- Referring domains (third-party, trend only).
- Local: Business Profile calls, direction requests, website clicks.

Goals: write them SMART (specific, measurable, achievable, relevant, time-bound), starting from a business outcome and breaking it into process goals (content, internal links, links). Illustrative examples from the posts, not benchmarks: +20% organic traffic in 4 months; +5% organic CTR in 3 months; first page for a named keyword in 12 months; 1-3 articles in the top 10; 200 qualified leads in 6 months for a startup. The vendor also suggests "reduce bounce rate by 15%"; replace that with an engagement-rate or conversion goal, since bounce rate is page-dependent and not a ranking factor.

Client and team reporting: Email Summaries for recurring summaries; Access Control (General Settings > Access Control) for SEO roles; Looker Studio or an agency dashboard for multi-source reports. Write an SEO SOP that fixes the monthly metrics, the content-decay procedure, the broken-link procedure and who owns each.

Sources: https://aioseo.com/seo-reporting/, https://aioseo.com/automated-seo-reports/, https://aioseo.com/how-to-set-seo-goals-that-boost-rankings/, https://aioseo.com/simple-guide-to-seo-analytics/, https://aioseo.com/how-to-create-seo-sops/, https://aioseo.com/seo-marketing-plan/, https://aioseo.com/seo-for-startups/, https://aioseo.com/best-seo-reporting-tools/

## Seasonal pages (Black Friday and other annual events)

Decision rules:
1. One permanent URL per recurring event, reused every year (for example `/black-friday/`, not `/black-friday-2026/`). It keeps the links and history the page earned. Put the year in the title and H1, not the slug.
2. Start about 45 days before the event (some posts say October for Black Friday). Refresh the title, H1, year, offers and copy, and confirm the page is indexable and in the sitemap.
3. Add internal links from the homepage, blog and relevant product or category pages ahead of the push; more internal links to a seasonal page signal its current importance.
4. Track the event keywords in Keyword Rank Tracker (add them before the season) and the page in Content Performance.
5. After the event, keep the page live with a 200 status: update it to say the sale has ended, link to current offers, and keep evergreen content (what to expect next year, sign-up). Remove temporary site-wide links (header, footer, banners) but keep a few contextual links.

Conflict: the vendor's Black Friday post recommends a 302 redirect from the page after the sale. Google's guidance for recurring seasonal pages is to keep the same URL live year-round; a long-lived 302 is eventually treated like a 301, and redirecting to an unrelated page can be treated as a soft 404, so the page may lose what it built. Keep the page live instead.

Year-in-title automation: AIOSEO's Current Year smart tag updates the year on 1 January. Use it only on pages you actually review each year; a bumped year without updated content is misleading (one vendor post warns against exactly this). Plan the January update of year-in-title posts in the editorial calendar.

Sources: https://aioseo.com/black-friday-seo/, https://aioseo.com/content-strategy/, https://aioseo.com/on-page-seo/, https://aioseo.com/seo-hacks-to-grow-your-traffic/, https://aioseo.com/how-to-check-google-rankings/

## AIOSEO compared with Yoast, Rank Math and SEOPress

Everything below is vendor-authored (AIOSEO publishes these comparisons about its competitors). Treat feature gaps as claims to verify and all prices as dated.

Facts that are not in dispute:
- AIOSEO (formerly All in One SEO Pack) has been owned by Awesome Motive since February 2020.
- Yoast has been owned by Newfold Digital since August 2021.
- Rank Math: the vendor says it has been owned by Group One since 2023 (verify).
- Running two SEO plugins at once produces duplicate titles, meta, canonicals, schema and competing sitemaps. Pick one.

AIOSEO pricing as stated by the vendor (annual plans, first-year price, sites):

| Plan | Sept/Oct 2026 posts | Renewal (2026 post) | 2025 posts | Sites |
|---|---|---|---|---|
| Basic | $49.50 | $99 | $49.60 | 1 |
| Plus | $99.50 | $199 | $99.60 | 3 |
| Pro | $199.50 | $399 | $199.60 | 10 |
| Elite | $299.50 | $599 | $299.60 | 100 |

14-day money-back; unlimited users on every plan; no white label. Tier boundaries (for example Search Statistics on Elite, Local SEO from Plus, Link Assistant from Pro) are covered in blog-features-tiers.md and licensing-account.md.

Vendor comparison claims (verify before quoting):

| Topic | AIOSEO (vendor claim) | Competitor (vendor claim about them) |
|---|---|---|
| Redirect types | 19 (the list includes 4xx/5xx status codes that are not redirects) | Rank Math 3, Yoast 5, SEOPress 5 |
| Redirects tier | Pro and up | Free in Rank Math; Yoast Premium only |
| Focus keywords on free plan | 1 | Rank Math free 5 |
| Social profiles | 13 (another post says 11) | Yoast 8 |
| Setup wizard | 4 steps (another post says 5 or 7) | Yoast 5 (older posts 12) |
| Search Console data in WordPress, content decay, SEO Revisions with update timeline | Yes (Elite for Search Statistics) | SEOPress lacks Author SEO and content decay |
| Multi-site cost example | AIOSEO Pro 10 sites $199.50 first year, $399 renewal; 3-year 10-site total $997.50 | Yoast Premium $118.80 per site per year, WooCommerce SEO $178.80 per store; 3-year 10-site total $3,564; Rank Math Pro about $95.88 first year, $107.88 renewal, client sites need Business or Agency, Content AI extra |
| SEOPress | | Pro $49 (1 site), $59 (5), $149 (unlimited); white label; 12 schema types; periodic audit |
| Other alternatives named | | The SEO Framework (minimal, fast), SureRank (free tier, Pro $99 for 10 sites), Squirrly (AI-guided writing, from $9.99/month, no redirect manager) |

When a user asks which to choose: decide on features they will actually use (Search Console data inside WordPress, Link Assistant, Local SEO, WooCommerce depth, redirect manager), site count over three years, white-label needs (SEOPress), and the cost of migrating. Rankings do not change because of the plugin brand; they change if the migration drops metadata or redirects.

Sources: https://aioseo.com/aioseo-vs-seopress/, https://aioseo.com/best-rank-math-alternative/, https://aioseo.com/yoast-seo-alternative/, https://aioseo.com/rank-math-vs-yoast/, https://aioseo.com/all-in-one-seo-vs-rank-math/, https://aioseo.com/yoast-seo-vs-all-in-one-seo-which-is-the-best-seo-plugin/, https://aioseo.com/rank-math-review/, https://aioseo.com/seopress-review/

## Migrating from Yoast or Rank Math to AIOSEO

AIOSEO paths: setup wizard auto-detects the old plugin ("Import Data and Continue"), or All in One SEO > Tools > Import/Export > Import Settings From Other Plugins. Screen details are in tools-migration-multisite.md; redirect import is in redirects-links.md.

Steps:
1. Back up the full site (files and database), and use Tools > Import/Export > Create Backup in AIOSEO if it already has settings.
2. Export redirects from the old plugin (Yoast: SEO > Redirects export; Rank Math: Status and Tools > Import and Export) and keep the file.
3. Install AIOSEO with the old plugin still active, so the importer can read its data.
4. Import via the wizard or Tools > Import/Export, choosing which settings to bring. Imports overwrite existing AIOSEO settings; they do not merge.
5. On large sites, post meta imports run in the background; wait for them to finish before checking.
6. Import redirects into Redirects > Import/Export (CSV or JSON; other redirect plugins supported).
7. Deactivate the old plugin (Notification Center "Conflicting Plugins Detected" > Fix Now). Keep it installed but inactive for about a week in case you need to re-import, then delete it. Remove any of its filters from functions.php or snippets.
8. Spot-check 5-10 representative pages (home, a post, a page, a product, a category): title, meta description, canonical (AIOSEO Settings > Advanced), robots, Open Graph, schema (Rich Results Test), and that each redirect resolves in one hop.
9. Sitemap URL changes: AIOSEO serves `/sitemap.xml`; Yoast used `/sitemap_index.xml`, WordPress core `/wp-sitemap.xml`. Submit the new sitemap in GSC (Search Statistics' GSC connection can sync it) and remove the old one there; removing a sitemap does not hurt.
10. Watch GSC Page indexing and Search Statistics for two weeks.

What does not transfer: the vendor says a Rank Math import brings titles, descriptions, focus keywords, redirects and schema but not analytics or rank history. Re-add tracked keywords in Keyword Rank Tracker (import from GSC or focus keyphrases).

Many sites (agency rollout): migrate the smallest sites first, test money sites on staging, do 1-2 sites a day, keep a log per site, and watch each site's GSC Page indexing report for two weeks.

The vendor states that switching plugins does not hurt rankings if metadata is imported. That holds only if titles, descriptions, canonicals, robots settings, schema, redirects and the sitemap are verified as above.

Sources: https://aioseo.com/migrating-from-yoast-seo-to-all-in-one-seo/, https://aioseo.com/migrating-from-rank-math-to-all-in-one-seo/, https://aioseo.com/yoast-seo-alternative/, https://aioseo.com/best-rank-math-alternative/, https://aioseo.com/wordpress-seo-setup-guide/, https://aioseo.com/aioseo-vs-seopress/
