# Technical SEO playbook (WordPress with AIOSEO)

Scope: task-ordered rules for crawling, indexing, sitemaps, canonicals, redirects, migrations, HTTPS, speed, structured data, page builders, multilingual sites, multisite and the security problems that show up in search. It is merged from about 570 aioseo.com blog posts (2015 to October 2026) and corrected against Google Search Central documentation where the posts are dated or overstated. AIOSEO features are named with their menu path in one line; the settings screens themselves are documented in sitemaps-robots-indexing.md, redirects-links.md, settings-search-appearance.md, schema-local-social.md and tools-migration-multisite.md. Menu labels drift between plugin versions, so confirm on the live site before giving a click path as fact. Vendor statistics are marked "(vendor claim)".

## Contents

- Diagnose "my page is not on Google"
- Choose the right index control: robots.txt, noindex, canonical, password
- Crawl cleanup: parameters, internal search, feeds, bots and crawl budget
- Sitemaps
- Submitting to search engines and IndexNow
- Canonicals, duplicates and pagination
- Archives, taxonomies and attachment pages
- URLs, permalinks and slugs
- Redirects, 404s and status codes
- Migrations: domain, HTTPS, permalink, SEO plugin and theme changes
- HTTPS and security problems that affect search
- Core Web Vitals and speed
- Structured data workflow
- Page builders, JavaScript and headless WordPress
- International and multilingual sites
- Multisite
- Technical audit cadence and checklist

## Diagnose "my page is not on Google"

Model: discovery (links, sitemaps) leads to crawl, crawl leads to index, index makes ranking possible. Crawled does not mean indexed and indexed does not mean ranking. If `site:example.com/page/` returns nothing it is an indexing problem; if the page is there but nowhere for its query it is a ranking problem with a different fix path.

Check in this order (most common causes first):
1. WordPress Settings > Reading > "Discourage search engines from indexing this site" must be unchecked. This is the top cause after a launch or a staging push. Clear the page cache afterwards.
2. Noindex at section level and page level. AIOSEO: Search Appearance > Content Types / Taxonomies ("Show in Search Results") and the post's AIOSEO Settings > Advanced > Robots Setting. The Posts list shows a noindex indicator per entry, which is the fastest scan.
3. robots.txt: look for `Disallow: /` or blocks on key paths (AIOSEO: Tools > Robots.txt Editor). Confirm per URL with GSC URL Inspection, which is more reliable than reading the file.
4. Sitemap: submitted, status Success, and the URL actually present (excluded post types and noindexed items are left out on purpose).
5. GSC Indexing > Pages report: open each "Not indexed" reason to list URLs. (Older posts call it "Coverage"; the current name is Page indexing.)
6. URL Inspection > Test Live URL (live data can differ from the stored index) > Request Indexing. This adds the URL to a priority queue; it cannot force indexing. A refused request means the URL is not available to Google (noindex, block, error): fix it, wait about a day, retest.
7. Only some pages missing: look at internal links, thin or near-duplicate content, and a canonical pointing elsewhere.
8. Manual actions: GSC > Security & Manual Actions.
9. Server errors: persistent 5xx and timeouts reduce crawling and can drop pages; there is no separate "uptime penalty".

AIOSEO shortcut (Elite): Search Statistics > Index Status groups URLs as Indexed, Crawled not indexed, Discovered not indexed, Other not indexed, No results yet, and shows per-URL robots, fetch, crawled-as, Google-selected canonical and last crawl, with a link to URL Inspection.

GSC status decision table:

| Status | Meaning | Likely cause | Action |
|---|---|---|---|
| Discovered, currently not indexed | Known, not yet crawled | Weak internal links, low priority, scheduling | Add internal links from strong pages, keep in sitemap, wait |
| Crawled, currently not indexed | Fetched, not stored | Thin or duplicate content, no internal links, or queue delay | Improve or merge content, add links; request indexing only after fixing |
| Excluded by noindex tag | Directive found | Robots meta or the WordPress Reading setting | Remove noindex if the page should rank |
| Blocked by robots.txt | Crawl disallowed | A rule matches | Edit the rule. This is a crawl directive, not a quality judgment (one post muddles the two) |
| Alternate page with proper canonical | Google chose another URL | Canonical points elsewhere | Correct only if the canonical is wrong |
| Duplicate, Google chose different canonical | Google overrode your hint | Near-duplicate content or conflicting signals | Align canonical, internal links, sitemap and redirects |
| Soft 404 | Page looks empty or "not found" with a 200 status | Thin page, empty category, redirect to an unrelated page | Add content, return a real 404/410, or redirect to a true equivalent |

Timelines (vendor claim, 2026 post): homepage 1 to 4 weeks after sitemap submission on a new domain, inner pages 2 to 8 weeks, recrawl after removing noindex 1 to 2 weeks. Repeated sitemap resubmission or repeated Request Indexing does not speed anything up.

Sources: https://aioseo.com/website-not-showing-up-on-google/, https://aioseo.com/why-wont-google-index-my-content/, https://aioseo.com/crawled-currently-not-indexed/, https://aioseo.com/indexing-in-seo/, https://aioseo.com/what-is-crawling-and-indexing/, https://aioseo.com/how-to-check-your-google-index-status-in-wordpress/, https://aioseo.com/best-google-index-checker/, https://aioseo.com/organic-search-traffic/

## Choose the right index control: robots.txt, noindex, canonical, password

Decision rules:
- Keep a page out of search results: `noindex` robots meta (or `X-Robots-Tag` header for PDFs and files). The page must stay crawlable, because a URL blocked in robots.txt cannot be fetched and its noindex is never seen. AIOSEO: post > AIOSEO Settings > Advanced > Robots Setting (turn off "Use Default Settings", tick No Index); whole post types or taxonomies in Search Appearance.
- Stop crawling of junk that should never be fetched (internal search results, cart and checkout actions, endless calendars, facet combinations you do not want in search): robots.txt Disallow. A disallowed URL can still be indexed, without a snippet, if other sites link to it.
- Consolidate duplicates while keeping both URLs live for users: rel=canonical.
- Move a page for good: 301 redirect.
- Keep something private: password or login protection (WordPress Visibility: Private or Password Protected) or HTTP authentication. robots.txt is public and not a security control; bad bots ignore it.
- Do not combine Disallow and noindex on the same URL: choose one. To deindex something already blocked, lift the block, let Google see the noindex, then decide whether to block again.
- `noindex` in robots.txt has been unsupported by Google since September 2019 (one post states this correctly).
- Sections commonly noindexed: thank-you and confirmation pages, login and account pages, internal search results, PPC-only landing pages, staging and test pages, expired event pages with no replacement, thin tag archives. Privacy and legal pages do not need noindex; one post says they should not be indexed, which is the author's opinion, not a Google rule.
- Noindexed pages are still crawled (less often), so noindex is not a crawl-budget tool, and there is no "duplicate content penalty" for noindex to avoid.

Other robots meta values (AIOSEO offers No Follow, No Archive, No Translate, No Image Index, No Snippet, max-snippet and related): use nofollow meta sparingly; noarchive is moot for Google since cached links were removed in 2024; noimageindex site-wide gives up image traffic; nosnippet removes all text snippets, including featured snippets and use in AI Overviews, so do not set it on pages you want to earn clicks from. Verify AIOSEO's help text against Google's robots meta documentation before using the less common values on money pages.

robots.txt rules:
- WordPress serves a virtual robots.txt; AIOSEO edits it without a physical file (Tools > Robots.txt Editor > Enable Custom Robots.txt). If a physical robots.txt exists in the web root it overrides the virtual one.
- Always keep the Sitemap lines (AIOSEO adds XML, RSS and, when enabled, video and news sitemap URLs).
- Wildcards `*` and `$` work for Google (`Disallow: /*.pdf$`). Comments start with `#`. Other crawlers vary in wildcard support.
- Google ignores `Crawl-delay`; `Clean-param` is a Yandex directive. AIOSEO exposes both, so expect them to affect only other engines.
- The whole-site block (`User-agent: *` + `Disallow: /`) is the classic catastrophic error; one vendor author lost weeks of traffic to it (anecdote).
- Test with the GSC robots.txt report (Settings > robots.txt) and URL Inspection. The legacy robots.txt Tester was retired in December 2023.
- AI crawler rules (GPTBot, ClaudeBot, Google-Extended and others) are a business decision; see playbook-ai-search.md. Never block Googlebot or Bingbot by accident when using "block unwanted bots" presets.

Sources: https://aioseo.com/noindex-meta-tag/, https://aioseo.com/robots-meta-tags/, https://aioseo.com/ultimate-guide-to-wordpress-robots-txt-files/, https://aioseo.com/how-to-generate-robots-txt-files-in-wordpress/, https://aioseo.com/how-to-edit-a-robots-txt-file-in-wordpress/, https://aioseo.com/how-to-hide-a-page-in-wordpress/, https://aioseo.com/what-is-robots-txt-in-wordpress/, https://aioseo.com/duplicate-content/

## Crawl cleanup: parameters, internal search, feeds, bots and crawl budget

Crawl budget first: Google's crawl-budget guide targets sites with roughly 1 million or more unique URLs, or 10,000 or more URLs that change daily. Google staff have said sites under a few thousand pages need not worry. For a normal WordPress site, crawl cleanup is hygiene that reduces junk URLs and duplicate signals, not a ranking lever. Treat vendor "save crawl budget" framing accordingly; it matters most for large WooCommerce stores with filters.

AIOSEO: Search Appearance > Advanced > Crawl Cleanup (sub-settings Query Arg Monitoring, Internal Site Search Cleanup, RSS Feeds, Unwanted Bots).

Query parameters:
- Sources: UTM and tracking tags, sort and filter options, session IDs, pagination parameters, spam query strings.
- Content-changing parameters you want consolidated (sort order, colour filter on the same products): canonical to the clean URL and link internally only to the clean URL.
- Pure noise (tracking, session, spam): block. Query Arg Monitor logs arguments; choose Block Key or Block Key & Value, singly or in bulk. Blocking writes robots.txt rules behind the scenes, so the same robots.txt caveats apply (a blocked URL cannot pass its canonical hint). Expect "1 week to a couple of months" before GSC reflects the cleanup (vendor estimate).
- GSC's URL Parameters tool was retired in 2022. A post titled "delete URL parameters from Google Search Console" actually describes blocking parameters on your own site.

Internal site search:
- Risks: thin `?s=` URLs indexed, spam queries (casino or pharma strings) creating indexable pages, crawl waste.
- Choose one: noindex the search results template (links followed, page not indexed) or Disallow search URLs (`?s=`, `/search/`, `/page/*/?s=`) via the Crawl Cleanup or robots.txt toggle. Do not apply both to the same URLs.
- Internal Site Search Cleanup adds a maximum query length, strips emojis and special characters and blocks common spam patterns.

Feeds:
- Disable unused WordPress feeds (comments, taxonomy, search, author) in Crawl Cleanup > RSS Feeds; keep the main content feed. AIOSEO sets feeds to noindex.
- Add attribution to feed items (General Settings > RSS Content, Before/After Content with Post Link and Site Link tags) so scrapers that republish the feed link back to the original.

Bots:
- Bot traffic skews analytics and uses server resources. Bad bots (scrapers, credential stuffing, click fraud, inventory hoarding) usually ignore robots.txt; use a WAF, a security plugin or server rules. Editing `.htaccess` by hand can lock the site out; test on staging.
- Crawl Cleanup > Unwanted Bots writes Disallow rules for listed bots. Check exactly which user agents the list contains before enabling "block all".

Sources: https://aioseo.com/crawl-budget/, https://aioseo.com/what-is-a-url-parameter/, https://aioseo.com/query-arg-crawling-in-wordpress/, https://aioseo.com/how-to-delete-url-parameters-from-google-search-console/, https://aioseo.com/internal-site-search/, https://aioseo.com/how-to-stop-bot-traffic/, https://aioseo.com/how-to-block-an-unwanted-web-crawler/, https://aioseo.com/disable-rss-feeds-in-wordpress/

## Sitemaps

Facts (Google):
- Sitemaps help discovery and recrawl; they do not improve rankings and do not force indexing. Most valuable for new sites, large sites, media-heavy sites and poorly linked pages. A small, well-linked site can do without one, though there is no reason to skip it on WordPress.
- Google ignores `<priority>` and `<changefreq>` (Gary Illyes called them "a bag of noise", 2017). Do not tune them; several posts still sell "page priority". Google uses `<lastmod>` only when it is consistently and verifiably accurate, so never bump dates without real changes.
- Protocol limits: 50,000 URLs or 50 MB uncompressed per file; split with a sitemap index (AIOSEO does this automatically).
- Google accepts XML, RSS 2.0, Atom and text sitemaps. It does not require or specifically recommend having both XML and RSS. About eight posts repeat "Google recommends both"; treat the RSS sitemap (`/sitemap.rss`, recent posts only) as an optional freshness aid.
- Sitemaps do not fix duplicate content and are only a weak canonical signal.

Rules:
1. Include only canonical, indexable URLs that return 200. Exclude redirected, canonicalised-away and noindexed URLs (AIOSEO excludes noindexed content automatically). Keep URL format consistent (https, www choice, trailing slash).
2. One XML sitemap source only. AIOSEO disables the WordPress core `wp-sitemap.xml` (since AIOSEO 3.6.2). After switching SEO plugins, remove the old sitemap URL from GSC (Yoast `sitemap_index.xml`, core `wp-sitemap.xml`) and submit `/sitemap.xml`. Removing a sitemap in GSC does not hurt rankings.
3. List sitemap URLs in robots.txt (AIOSEO adds them).
4. Leave date archives and author archives out unless they are genuinely useful (single-author blogs rarely need author archives).
5. Non-WordPress URLs on the same host (a landing page built elsewhere) can be added as Additional Pages via CSV.
6. Images are included in the XML sitemap by default; video sitemap (Pro) auto-detects YouTube, Vimeo and self-hosted embeds; pair with VideoObject schema.
7. Google News sitemap: for news publishers only, holds articles published in the last 2 days, posts only (not pages or products). Publisher Center approval is not required for inclusion in Google News; content must meet News policies. One 2021 post says "only articles at least two days old", which is wrong.
8. HTML sitemap is for visitors; its only search value is internal links.
9. Audit: confirm `/sitemap.xml` (and `/sitemap.rss` if used) load; if 404, check caching rules, NGINX rewrites, or another plugin; check GSC Sitemaps for errors; spot-check that key URLs appear.
10. Do not paste `<link rel="canonical">` into a sitemap `<url>` entry; one post shows this and it is not a valid sitemap field.

AIOSEO: Sitemaps > General Sitemap (dynamic, regenerated on request), plus RSS, Video, News and HTML tabs; details in sitemaps-robots-indexing.md.

Sources: https://aioseo.com/sitemap-best-practices/, https://aioseo.com/what-is-an-xml-sitemap/, https://aioseo.com/dynamic-sitemap/, https://aioseo.com/how-to-create-an-rss-sitemap-in-wordpress/, https://aioseo.com/html-sitemap-vs-xml-sitemap/, https://aioseo.com/wordpress-xml-sitemaps-vs-all-in-one-seo-sitemaps/, https://aioseo.com/create-a-google-news-sitemap/, https://aioseo.com/how-to-add-multiple-urls-to-your-sitemap-the-easy-way/

## Submitting to search engines and IndexNow

- "Submitting a site" means: create a free webmaster account, verify, submit the sitemap.
- Google: GSC property. Domain property via DNS TXT is the most robust verification. AIOSEO's one-click connect (General Settings > Webmaster Tools > Connect to Google Search Console) verifies without pasting a code and syncs sitemaps. A URL-prefix property must match https and www exactly.
- The Google sitemap ping endpoint (`google.com/ping?sitemap=`) was deprecated in 2023 and no longer works. Two posts still call it "the quickest way". Use GSC and the robots.txt Sitemap line.
- Bing Webmaster Tools: "Import from GSC" skips verification and imports sitemaps. Bing also powers DuckDuckGo, Yahoo and Ecosia results.
- Yandex (Russian audiences) and Baidu (needs a Chinese phone number) have their own tools; paste verification codes in Webmaster Tools. Brave has no webmaster tools; it reads robots.txt sitemaps.
- IndexNow: pings Bing, Yandex, Seznam, Naver and other participants when content is published, updated or deleted. Google does not participate, so IndexNow does nothing for Google indexing. One 2026 post says it "notifies Google and Bing" and that you need not resubmit to Google; that is wrong. Keep the sitemap in GSC. Run only one IndexNow implementation (AIOSEO's feature or Microsoft's plugin, not both). AIOSEO: Feature Manager > IndexNow, key managed in Webmaster Tools.
- Google Analytics verification via Universal Analytics (2016 post) is obsolete; UA stopped processing in July 2023.

Sources: https://aioseo.com/how-to-submit-your-website-to-search-engines-2024/, https://aioseo.com/how-to-submit-a-sitemap-to-google-wordpress-tutorial/, https://aioseo.com/how-to-submit-a-sitemap-to-bing-wordpress-tutorial/, https://aioseo.com/how-to-submit-a-sitemap-to-yandex-wordpress-tutorial/, https://aioseo.com/what-is-indexnow-for-seo/, https://aioseo.com/how-to-add-indexnow-in-wordpress/, https://aioseo.com/how-to-connect-site-to-google-without-google-search-console-verification-code/, https://aioseo.com/how-to-add-google-search-console-to-your-wordpress-website/

## Canonicals, duplicates and pagination

Facts:
- Duplicate content is a filtering problem, not a penalty: Google picks one canonical URL and folds signals into it. The exceptions are deceptive scraping and spam. Posts that threaten "site-wide penalties" for duplicates overstate it.
- rel=canonical is a strong hint, not a directive. Redirects are also strong signals; sitemap inclusion is weak. Internal links, hreflang and HTTPS preference also feed the choice. Consolidation passes signals to the canonical (one post claims canonicals do not transfer PageRank; Google says they consolidate signals).
- Google says most sites "will likely do just fine without specifying a canonical preference", but self-referencing canonicals (AIOSEO outputs them by default) remove ambiguity.
- GSC has no feature to "submit canonical URLs" (one post claims it does).

Rules:
1. One canonical per page, absolute https URL, consistent case and trailing slash. Link internally to the canonical version.
2. Use canonical for: same post reachable under several category paths, product variants and sort or filter parameters, tracking parameters, syndicated copies (ask the partner to canonicalise to your original), print versions.
3. Use 301 instead of canonical when the duplicate URL has no reason to exist for users (http to https, www to non-www, old slugs).
4. Use noindex only when neither applies and the page must exist for users.
5. Fix order for a duplicate-content report: pick the preferred URL, canonicalise or redirect the others, keep only preferred URLs in the sitemap, clean internal links, then prune or consolidate weak overlaps (see playbook-keywords-content.md).
6. Verify Google's choice in URL Inspection (user-declared vs Google-selected canonical). AIOSEO's Index Status hover panel shows both.
7. Scraped or hijacked copies: DMCA notice for scrapers; a canonical injected by malware into your own pages means the site is hacked (see security section).

Pagination:
- Paginated pages (`/page/2/`) should self-canonicalise and stay indexable when they list items not linked elsewhere. Do not canonicalise page 2+ to page 1 or to a view-all page unless the view-all page really exists and loads acceptably; canonicalising to page 1 hides deeper items. One canonical post recommends canonicalising to page 1; Google's documentation says otherwise.
- Google stopped using rel=prev/next in 2019; it is harmless but not a signal.
- Give each paginated page a unique title and description: AIOSEO Search Appearance > Advanced > Paged Format appends "Page N".
- "No Index Paginated" (Global Robots Meta) is rarely the right choice for product categories, because it can stop Google reaching products on deeper pages; use it only where items are reachable another way.

AIOSEO: per-page canonical at AIOSEO Settings > Advanced > Canonical URL (one WooCommerce post mis-cites it under Search Appearance).

Sources: https://aioseo.com/canonical-tags/, https://aioseo.com/canonical-url/, https://aioseo.com/duplicate-content/, https://aioseo.com/pagination-seo/, https://aioseo.com/technical-seo/, https://aioseo.com/category-page-seo-for-woocommerce/, https://aioseo.com/technical-seo-audit/

## Archives, taxonomies and attachment pages

Decision rules per archive type:
- Categories that act as topic hubs or product categories with real search demand: index, write a unique description, keep in the sitemap.
- Thin tag archives (single-use tags, dozens of near-identical tags): noindex via Search Appearance > Taxonomies, or better, stop creating them. Guideline from posts: tags optional, about 5 or fewer per post, no single-use tags; categories broad and few, never leave posts in "Uncategorized".
- Author archives: index on multi-author sites where the archive supports Author SEO and E-E-A-T; noindex or disable on single-author sites where they duplicate the blog index.
- Date archives: usually noindex and out of the sitemap.
- A 2021 post advises turning off "Show in Search Results" for all categories and tags; a 2026 WooCommerce post says keep valuable categories indexable. Follow the 2026 per-taxonomy rule.
- Attachment pages: redirect them (they are thin). AIOSEO: Search Appearance > Image SEO (or Media) > Redirect Attachment URLs: "Attachment" sends to the file, "Attachment Parent" sends to the post (unattached uploads still show a page), "Disabled" leaves them indexable. On by default after activation.
- Strip Category Base (Search Appearance > Taxonomies > Categories > Advanced) shortens URLs; on a live site redirect the old `/category/` URLs and check for slug collisions between pages and categories.
- Product attribute archives (WooCommerce): decide index or noindex per attribute; see playbook-local-ecommerce.md.

Sources: https://aioseo.com/the-difference-between-tags-and-categories/, https://aioseo.com/how-categories-and-tags-work/, https://aioseo.com/disable-image-attachment-pages-in-wordpress/, https://aioseo.com/how-to-best-optimize-images-in-wordpress/, https://aioseo.com/new-dashboard-widgets-and-strip-category-base-feature/, https://aioseo.com/category-page-seo-for-woocommerce/

## URLs, permalinks and slugs

Rules:
- Settings > Permalinks > Post name (`/%postname%/`). Avoid `?p=123` and date-based structures for evergreen content (dates age the URL and force redirects when refreshing). News sites may keep dates; large sites can use `/%category%/%postname%/` but category renames then break URLs.
- Slugs: lowercase, hyphens (not underscores), short, descriptive; drop stop words where clarity survives; include the main term only when natural; no year or month in the slug (`best-smartphones-of-march-2024` is the bad example). Words in URLs are a very light signal (John Mueller called slug keywords "very lightweight" and "overrated"); treat this as clarity and UX.
- "Permalinks mean permanent": never change structure or slugs on a live site without 301s. AIOSEO URL Slug Monitor prompts "Add Redirect" when a published slug changes; Automatic Redirects (Redirects > Settings) do it without the prompt.
- Choose www or non-www once (Settings > General, WordPress Address and Site Address) and redirect the other. Which one does not matter.
- Multilingual: translate slugs per language (Universally keeps the original slug with a language prefix and does not translate it; decide whether that is acceptable).

Sources: https://aioseo.com/best-wordpress-permalink-structure/, https://aioseo.com/what-is-a-slug-in-seo/, https://aioseo.com/ultimate-wordpress-seo-guide/, https://aioseo.com/how-to-avoid-404-errors-when-updating-your-wordpress-site/, https://aioseo.com/on-page-seo/

## Redirects, 404s and status codes

When to redirect: deleted post with traffic or backlinks, slug change, merged content, section restructure (`/blog/` to `/articles/`), http to https, domain move, duplicate consolidation, expired campaign with a successor page.

Status code decision table:

| Code | Use |
|---|---|
| 301 | Permanent move. The default for almost every case |
| 308 | Permanent and method-preserving (rarely needed on WordPress) |
| 302 | Temporary: maintenance of one page, short tests, content that will return |
| 307 | Temporary and method-preserving (forms, checkout POSTs) |
| 303, 304 | Listed in AIOSEO; no SEO use for content moves |
| 410 | Gone for good with no replacement; processed slightly faster than 404 |
| 404 | Gone with no relevant target. Normal; Google says leave real 404s alone |
| 503 | Planned maintenance; tells crawlers to come back later |

Corrections to the posts:
- Several posts say a 302 "does not pass link equity". Google says all 3xx redirects pass signals and a long-lived 302 is eventually treated like a 301. Pick the code that matches intent so Google chooses the intended canonical.
- 404s do not hurt rankings by themselves. What hurts is losing pages that had traffic or backlinks without redirecting them, and mass breakage after a migration (vendor anecdote: URLs changed without 301s, 48% organic decline). One 2022 post claims 404s are harmful and "de-rank" pages; another by the same vendor says the opposite.
- A 410 does not de-index "immediately"; it is slightly faster than a 404.
- "19 redirect types" marketing includes 4xx and 5xx codes that are not redirects.
- Redirecting every 404 to the homepage (AIOSEO 404 Settings offers it) creates soft 404s and poor UX. Redirect only to a genuinely equivalent page (parent category is acceptable for a discontinued product only when it serves the same need); otherwise let it 404 or 410.

Steps (AIOSEO: Redirects, Pro and up; settings in redirects-links.md):
1. Source as a relative path (`/old-page/`), target relative or absolute (type-ahead by title or slug), type 301 unless temporary.
2. For a single post, the post's AIOSEO Settings > Redirects tab works too.
3. Verify every redirect: Check Redirect, incognito test, hit counts and logs. If an old URL still 404s, clear the cache.
4. Bulk moves: keep a master CSV (Source, Target, Type, Ignore Slash, Ignore Case, Regex); import; spot-test a sample.
5. Regex: start small, anchor with `^` and `$`, document each rule, check logs after deploy.
6. Scheduled redirects for campaigns: start and end dates; temporary redirects revert at expiry.
7. Enable 404 logging, keep at least 30 days, review weekly; redirect only 404s with a relevant target, real traffic or backlinks.
8. Avoid chains (A to B to C: point A straight to C) and loops; recheck after every migration. Prune redirects that have had no hits for a long time only if the old URLs have no backlinks.
9. Redirects cannot fix a typo in someone else's backlink; add a redirect on your side or ask the site to correct it.
10. Broken links: fix internal links at the source (edit the URL) rather than relying on redirects; for external dead links edit, replace or unlink. AIOSEO's Broken Link Checker (separate plugin, scans on AIOSEO servers about every 3 days) offers Edit URL, Unlink, Add Redirect, Recheck, Dismiss.

Server error basics: 403 is usually permissions or a security plugin (ask the host), 500 check error logs, plugin updates and PHP memory, 502/504 timeouts or server configuration. Test plugin and theme updates on staging.

Sources: https://aioseo.com/wordpress-redirects/, https://aioseo.com/redirect-types/, https://aioseo.com/url-redirection-tips/, https://aioseo.com/how-to-redirect-a-page-or-post-in-wordpress/, https://aioseo.com/how-to-set-up-automatic-redirects-in-wordpress/, https://aioseo.com/how-to-redirect-links-in-bulk-using-a-csv-file/, https://aioseo.com/how-to-easily-find-and-fix-404-errors-in-wordpress/, https://aioseo.com/how-to-decode-http-status-codes/

## Migrations: domain, HTTPS, permalink, SEO plugin and theme changes

Domain move checklist (expands the thin 2022 post):
1. Crawl and export every old URL (Screaming Frog free tier covers 500 URLs) plus GSC top pages and pages with backlinks.
2. Back up (files plus database) and copy the site to the new domain (Duplicator or host tools).
3. Map old to new URLs one-to-one. Use the domain-wide redirect only when paths are identical: AIOSEO Redirects > Full Site Redirect > Relocate Site (excludes login and admin).
4. Update internal links, canonicals, hreflang, schema URLs (Organization logo, sameAs), Open Graph URLs and the sitemap to the new domain. Do not leave canonicals pointing at the old domain.
5. Verify both domains in GSC, then old property > Settings > Change of Address > select new property.
6. Submit the new sitemap; keep the old domain registered and the 301s live for at least one year (longer if old links persist).
7. Update GA4, Bing Webmaster Tools, Google Business Profile, social profiles and major backlinks where you can.
8. Watch GSC Pages and Performance for both properties for several weeks; fix 404 spikes from the logs.

HTTPS move:
1. Install the certificate (Let's Encrypt is free and auto-renews on a 90-day cycle; most hosts automate it).
2. 301 all http URLs to https. AIOSEO: Redirects > Full Site Redirect > Canonical Settings > "Force a redirect from HTTP to HTTPS", optional www preference. Check whether the host already redirects, so you do not create a chain.
3. Fix mixed content (images, scripts, CSS on http).
4. Update canonicals, sitemap, internal links and hardcoded URLs; update GSC (a Domain property covers both protocols) and GA4.
5. HTTPS itself is not faster; speed gains come from HTTP/2 or HTTP/3, which browsers only use over TLS. A post demo showing "6 s vs 0.5 s" exaggerates.

Permalink structure change: generate the redirect map first, bulk import, then switch, then test a sample and crawl for chains.

SEO plugin switch (Yoast, Rank Math, SEOPress to AIOSEO):
1. Back up; export redirects from the old plugin (Yoast: SEO > Redirects; Rank Math: Status and Tools > Import and Export).
2. Install AIOSEO with the old plugin still active so the importer can read its data (Setup Wizard detects it, or Tools > Import/Export > Import Settings From Other Plugins). Imports overwrite AIOSEO settings; post meta imports run in the background on big sites.
3. Import redirects separately. Rank Math imports titles, descriptions, focus keywords, redirects and schema but not rank history.
4. Deactivate the old plugin (keep it installed about a week); never run two SEO plugins long-term (duplicate meta tags, duplicate schema, competing sitemaps). Remove old plugin filters from functions.php.
5. Spot-check 5 to 10 pages: title, meta description, canonical, robots meta, schema in the Rich Results Test, redirects.
6. Swap sitemaps in GSC (remove `sitemap_index.xml` or `wp-sitemap.xml`, submit `/sitemap.xml`).
7. Multiple sites: smallest first, staging for money sites, one or two per day, log each, watch GSC Pages for two weeks.
Switching plugins does not hurt rankings when the metadata carries over; verify rather than assume.

Theme change: document templates, widgets, menus, shortcodes, header and footer code, custom CSS and functions first; check that the new theme renders the post title as the only H1, keeps breadcrumbs and schema single-sourced, and does not add its own meta or Open Graph output; test speed, forms, search and RSS; compare GSC before and after. AIOSEO settings are theme-independent.

Maintenance mode: serve 503 with a Retry-After header (SeedProd and WP Maintenance Mode do this; check with a header checker, because a `wp_die()` snippet returns a 500-class code unless the header is set). Keep it short; a 503 for days can lead to deindexing. Never use 404 or a noindex for maintenance. Do not leave "Discourage search engines" on after a staging push; SEO Alerts (Tools > SEO Alerts) checks hourly for homepage noindex, robots.txt failure and sitemap failure.

Sources: https://aioseo.com/how-to-move-a-wordpress-site-to-a-new-domain/, https://aioseo.com/how-to-redirect-a-wordpress-site/, https://aioseo.com/https-and-seo/, https://aioseo.com/migrating-from-yoast-seo-to-all-in-one-seo/, https://aioseo.com/migrating-from-rank-math-to-all-in-one-seo/, https://aioseo.com/yoast-seo-alternative/, https://aioseo.com/to-do-list-changing-wordpress-themes/, https://aioseo.com/how-to-put-your-wordpress-site-in-maintenance-mode/

## HTTPS and security problems that affect search

- HTTPS is a lightweight ranking signal (announced 2014) and table stakes for trust; Chrome has labelled http pages "Not secure" since 2018. Posts that call security a "key ranking factor" overstate it.
- HTTPS does not secure WordPress itself. Baseline: prompt updates (core, then themes, then plugins, one at a time, tested), strong unique admin credentials with 2FA and login limits, no "admin" username, off-site automated backups with tested restores, a WAF (DNS-level or application-level), least-privilege user roles, file permissions 755 folders and 644 files.
- Search-visible hack symptoms: injected spam links or pages (SEO spam is a large share of WordPress malware; Sucuri figure 55.4%, via vendor), canonicals pointing to foreign domains, cloaked redirects for mobile or search-referred users, sudden indexed pages in other languages, GSC Security Issues alerts. Response: clean the site, close the hole, then request review in GSC Security Issues.
- Nulled, "GPL" or cracked premium plugins (including fake AIOSEO Pro) carry backdoors, card skimmers and spam links. Install Lite only from wordpress.org and Pro only from aioseo.com.
- Negative SEO patterns: spam links (Google mostly ignores them automatically; disavow only for a manual action or a link scheme you or a previous owner built), scraping (DMCA, RSS attribution), fake reviews (report them), fake DMCA removal requests, heavy crawling or hotlinking (WAF, hotlink protection).
- robots.txt is not a security control; never list sensitive paths in it.
- Keep the Google Maps API key and any API keys restricted; never expose them in public files.

Sources: https://aioseo.com/does-https-keep-wordpress-secure/, https://aioseo.com/website-security/, https://aioseo.com/negative-seo/, https://aioseo.com/aioseo-pro-nulled-security-warning/, https://aioseo.com/toxic-backlinks/, https://aioseo.com/how-to-stop-bot-traffic/, https://aioseo.com/technical-seo-audit/

## Core Web Vitals and speed

Facts:
- Core Web Vitals are LCP, INP and CLS. INP replaced FID on 12 March 2024. Good thresholds, measured at the 75th percentile of real-user page loads: LCP at most 2.5 s, INP at most 200 ms, CLS at most 0.1. Several 2025 posts still list FID, and one lists TTFB, FCP and TTI as Core Web Vitals; they are diagnostics, not CWV.
- Speed and CWV are a light signal used by ranking systems; Google said in 2023 that page experience is not a single ranking system. Relevance and content quality dominate. Practical rule from one post (sound): if competitors load in about 3 s and you take about 8 s, fix it; if you are comparable, extra speed will not move rankings but can still lift conversions.
- Field data (CrUX in PageSpeed Insights and the GSC Core Web Vitals report under Experience) is what Google uses; lab scores (Lighthouse 0 to 100) are for debugging. Do not chase 100.
- Intrusive interstitials on mobile remain a page-experience concern.

Fix order for WordPress:
1. Measure key templates (home, top posts, product, category) on mobile and desktop: PageSpeed Insights, the GSC CWV report, AIOSEO SEO Analysis > Performance or the Search Statistics per-page speed test, WebPageTest for waterfalls.
2. Images: the most common cause (multi-megabyte stock photos). Resize to display width, compress, serve WebP or AVIF, lazy-load below-the-fold images (native in WordPress since 5.5) but not the LCP image.
3. Caching plugin (page cache, minify and defer CSS and JS) and a CDN.
4. Theme and builder weight: lightweight themes are faster; heavy builders and many plugins add CSS, JS and DOM size. Remove plugins that duplicate features.
5. Hosting: server response under about 300 ms (vendor hosting test benchmark), HTTP/2 or HTTP/3, PHP version current.
6. Fonts locally hosted, third-party scripts trimmed (chat widgets, multiple analytics tags).
7. Retest monthly and after theme or plugin changes.

Statistics in posts (third-party, via vendor, no links): Akamai 2017 "1 s delay = 7% fewer conversions"; Deloitte 2019 "0.1 s change influences the journey"; Unbounce 2019 "70% say speed affects willingness to buy". Use only as context.

Mobile: Google uses mobile-first indexing, so content, links, structured data and meta must be present on the mobile render. The Mobile-Friendly Test and Mobile Usability report were retired in December 2023; use Lighthouse, PageSpeed Insights and real devices.

Sources: https://aioseo.com/website-speed-optimization/, https://aioseo.com/page-speed-test-tools/, https://aioseo.com/best-site-speed-test-tools/, https://aioseo.com/how-to-run-a-site-speed-test-in-wordpress/, https://aioseo.com/mobile-seo/, https://aioseo.com/mobile-seo-tools/, https://aioseo.com/how-to-lazy-load-images-in-wordpress/, https://aioseo.com/on-page-seo/

## Structured data workflow

Facts:
- Structured data is not a direct ranking factor. It makes pages eligible for rich results and helps machines understand entities. Rich results are never guaranteed.
- Use JSON-LD (Google's preference; AIOSEO outputs it). Several types may coexist on one page (Article plus Video plus BreadcrumbList) if each describes visible content.
- Current status of types the posts promote: HowTo rich results removed in 2023. FAQ rich results were restricted in August 2023 to well-known authoritative government and health sites and stopped showing for all sites on 7 May 2026. Sitelinks search box retired November 2024 (AIOSEO's toggle no longer has a visible effect). Google has also retired or narrowed several other types listed in older posts (for example Special Announcement and some education types); a 2023 post's "Google supports 31 types" is out of date. Check the current Google Search Gallery before promising any rich result.
- Still widely used: Product and merchant listings, Review snippets (for genuine reviews of a product, recipe, etc.), Recipe, Event, JobPosting, VideoObject, BreadcrumbList, Article, Organization, LocalBusiness, Dataset.
- Structured data is not required for AI Overviews or featured snippets and does not control their selection.

Rules:
1. One schema source. Do not let a theme, an old SEO plugin, a review plugin and AIOSEO all output Product or Organization markup; duplicates and conflicts follow. Check View Source (search `@type`) or the AIOSEO Analyzer Schema tab.
2. Markup must match visible page content. Do not hide FAQ content while outputting FAQPage markup (the AIOSEO FAQ block's Visibility toggle and "appears only in source code" methods conflict with Google's guidelines). Information entered only in a schema form and shown nowhere on the page is a policy risk.
3. Review markup only for real reviews of the thing the page is about. Self-serving reviews of your own LocalBusiness or Organization are not eligible for review snippets; do not paste reviews copied from Google or Yelp into markup. AggregateRating needs first-party reviews collected on your site.
4. Fill required and recommended properties; remove default smart-tag chips (Post Title, Post Excerpt) where they produce wrong text (for example Dataset descriptions must be 50 to 5,000 characters).
5. Event: one event per page, unique URL each, keep status (Scheduled, Cancelled, Postponed, Moved Online) current. JobPosting: datePosted and validThrough, remove or update when filled.
6. Validate: Rich Results Test (AIOSEO's Validate Schema button opens it with the code loaded) and validator.schema.org. The Structured Data Testing Tool was retired in 2021; two posts still recommend it.
7. Monitor GSC enhancement reports after deploy; fix "missing field" warnings on templates, not page by page.
8. Measure impact by comparing GSC search appearance and CTR before and after, not by assuming a CTR lift. Vendor CTR figures (Milestone Research "FAQ 87%", "rich snippets 17% higher CTR", "58% vs 41% of clicks") are unsourced and partly describe features that no longer exist.
9. AI-generated schema (AIOSEO AI Schema / Smart Schema, uses credits) still needs validation and a visible-content check.

AIOSEO: post > AIOSEO Settings > Schema > Generate Schema (catalog, Custom Schema for pasted JSON-LD, templates); site defaults in Search Appearance > Content Types; Organization or Person in Search Appearance > Global Settings > Knowledge Graph. Field-level detail is in schema-local-social.md.

Sources: https://aioseo.com/how-to-create-custom-schema-markup-in-wordpress/, https://aioseo.com/how-to-run-a-rich-results-test-in-wordpress/, https://aioseo.com/how-to-implement-structured-data-in-wordpress/, https://aioseo.com/what-is-structured-data-and-how-does-it-impact-seo/, https://aioseo.com/types-of-schema-markup/, https://aioseo.com/how-to-use-a-wordpress-faq-block-to-boost-seo-and-get-more-traffic/, https://aioseo.com/how-to-add-product-review-schema-in-wordpress/, https://aioseo.com/rank-math-vs-yoast/

## Page builders, JavaScript and headless WordPress

- A page builder does not influence SEO except through speed, mobile layout and markup quality. Content and structure matter more.
- AIOSEO integrates with Divi, Elementor (AIOSEO 4.1.7+), WPBakery, Avada, SiteOrigin, Thrive Architect and SeedProd: title, description, focus keyphrase, TruSEO, schema, social, redirects, robots, canonical, Cornerstone and Limit Modified Date are editable inside the builder. Use that panel instead of the builder's own SEO fields so there is one source of meta.
- H1 check on builder sites: right-click > Inspect, search `<h1>`. Builders and older themes sometimes output the title as H2 or styled text, or add a second H1 in a hero module. Aim for one H1 (the page title); a second H1 usually signals a template bug. Google says multiple H1s are not a problem for its systems (John Mueller), so this is structure and accessibility hygiene, not a ranking fix. A homepage post saying "multiple H1s confuse search engines" contradicts that.
- Heading levels by structure, never by font size.
- JavaScript: content, links and meta that only appear after client-side rendering may be delayed or missed. Check the rendered HTML in URL Inspection; links must be real `<a href>` elements; avoid `#` fragment routing for content URLs.
- Headless WordPress: AIOSEO's REST API (Feature Manager > REST API) returns per-post and per-term title, description, robots, canonical, JSON-LD and Open Graph so the front end can print them. Make sure the front end, not WordPress, serves the canonical domain, and that the WordPress origin is not indexable as a duplicate (noindex it or restrict access).
- Limit Modified Date stops the modified date changing on trivial edits; use it so `dateModified` and sitemap `lastmod` stay honest.

Sources: https://aioseo.com/divi-seo/, https://aioseo.com/elementor-seo-tips/, https://aioseo.com/how-to-boost-your-wpbakery-seo/, https://aioseo.com/how-to-optimize-a-site-built-with-the-avada-website-builder/, https://aioseo.com/how-to-optimize-site-built-using-siteorigin-page-builder/, https://aioseo.com/how-to-optimize-site-with-thrive-architect-page-builder-using-aioseo-integration/, https://aioseo.com/h1-tags-seo/, https://aioseo.com/wordpress-rest-api-and-seo/

## International and multilingual sites

Decision rules:
1. Define each market as language plus country (fr-FR, fr-CA, fr-BE): this is the pairing hreflang uses.
2. URL structure: ccTLD, subdomain or subdirectory are all acceptable to Google; subdirectories (`/es/`) are simplest to run on one WordPress install. The posts' "recommended structure" is vendor opinion. Choose deliberately and do not change it later without redirects.
3. Give each language its own crawlable URL. Do not swap language on one URL by cookie or browser setting, and do not rely on Chrome's auto-translate (not indexed).
4. hreflang: every version lists every other version and itself (reciprocal plus self-reference), with exact codes, and an `x-default` for the fallback or selector page. Point hreflang only at indexable, canonical, 200-status URLs; hreflang to a robots-blocked or noindexed page breaks the set. One post's sample snippet is malformed (no self-reference).
5. Each language version canonicalises to itself, never to the original-language page.
6. Translate title, meta description, slugs, alt text, breadcrumbs, structured data and Open Graph, then recheck lengths. Internal links point to same-language pages; the 404 page is translated too.
7. Unfinished language folder: keep it on staging, password-protected or noindexed. One post suggests blocking `/de/` in robots.txt, which can leave URLs indexed without content and breaks hreflang.
8. Machine translation at scale without native review risks the scaled content abuse policy and poor quality. Have a native speaker review at least the money pages before indexing.
9. Local engines: Baidu (China) and Yandex (Russia) shares quoted in posts differ (Yandex 49%, 52%, 62% or 64% depending on post and date; Statcounter cited once). Verify current share before investing; verify in their webmaster tools via AIOSEO Webmaster Tools.
10. Sitemaps must include all language URLs; most translation plugins add them, or use AIOSEO Additional Pages.
11. Track by country in GSC (Performance > filter Country) and GA4 (Demographics); the "Audience > Geo" path in one post is Universal Analytics.

AIOSEO: the Translations API lets WPML and similar plugins translate AIOSEO fields (titles, descriptions, social, slugs); AIOSEO itself does not create hreflang in these posts, the translation plugin does (WPML, TranslatePress, Polylang, or Universally, a sister SaaS that translates rendered output and adds hreflang).

Sources: https://aioseo.com/how-to-set-up-seo-for-different-languages-and-countries/, https://aioseo.com/international-seo-keyword-research/, https://aioseo.com/multilingual-seo-mistakes/, https://aioseo.com/the-beginners-guide-to-wordpress-multilingual-seo/, https://aioseo.com/multilingual-wordpress-site/, https://aioseo.com/the-beginners-guide-to-wordpress-multilingual-seo/, https://aioseo.com/best-wordpress-multilingual-plugins/

## Multisite

- Structure: subdirectories consolidate signals under one host; subdomains and mapped domains are treated more like separate sites. Google has said there is no inherent ranking difference; pick for management and brand reasons. The network type is hard to change later (a post claims networks older than a month are forced to subdomains; verify on the install).
- Each site needs its own sitemap submitted (a separate GSC property for subdomains and mapped domains), unique titles and descriptions, its own schema identity, and its own robots.txt rules.
- Avoid cross-site duplicates and cannibalisation: assign each keyword cluster to one site; canonical or 301 where content must be shared.
- AIOSEO: Network Admin > AIOSEO > Network Tools (robots.txt per site or network-wide via "Network Admin (No Site)", Import/Export to copy settings or import another plugin's data to a new subsite); Network Settings > Domains Activation for licences. Multisite is an Elite feature per the 2026 plan list. Details in tools-migration-multisite.md.
- Host heavy subsites separately if they slow the network.

Sources: https://aioseo.com/guide-to-wordpress-multisite-seo/, https://aioseo.com/what-is-wordpress-multisite/, https://aioseo.com/best-seo-management-tools/, https://aioseo.com/best-seo-agency-software/, https://aioseo.com/ultimate-wordpress-seo-guide/

## Technical audit cadence and checklist

Cadence: a light monthly check; a full audit after a redesign, theme change, migration, plugin switch or sudden traffic drop; quarterly for active sites. Prepare access (GSC, GA4, WordPress admin, registrar, host), known issues and a staging copy. Vendor time estimates: small site (under 1,000 pages) 1 to 2 days basic, 3 to 5 days comprehensive.

First response to a sudden drop: check SEO Alerts and GSC for noindex, robots.txt or sitemap failures; then server errors and manual actions; then whether the date matches a confirmed Google update (a sharp cliff matches an update, a gradual slide does not); only then content-level causes. Do not change everything at once while an update is rolling out.

Checklist:
1. Indexability: WordPress Reading setting, noindex scan (Posts list indicator), GSC Pages report, Index Status.
2. robots.txt reachable, not blocking key pages or CSS/JS/images, Sitemap lines present.
3. Sitemaps load, contain only indexable 200 URLs, submitted, no errors; old plugin sitemaps removed.
4. Canonicals: self-referencing on indexable pages, no cross-domain canonicals you did not intend; compare declared vs Google-selected in URL Inspection (Screaming Frog Canonicals tab for bulk).
5. Redirects and 404s: no chains or loops, no homepage catch-all, 404 log reviewed, broken internal links fixed at source.
6. Internal links: orphan count (Link Assistant > Orphaned Posts), click depth of key pages (within about 3 clicks), breadcrumbs present.
7. Duplicates: parameters, internal search, attachment pages, thin tag archives, pagination titles.
8. Core Web Vitals field data on key templates; image weight; caching.
9. Mobile render parity and intrusive interstitials.
10. HTTPS everywhere, no mixed content, single host version.
11. Structured data: one source, types match page, Rich Results Test passes, GSC enhancement reports clean, no hidden FAQ markup.
12. Security: GSC Security Issues, unexpected outbound links or pages, plugin update status, no nulled plugins.
13. International: hreflang reciprocity and x-default; JavaScript rendering and log files for large or complex sites.
14. On-page sample: titles and descriptions present and unique, one H1, alt text on informative images.

AIOSEO: SEO Analysis > Site Audit (All URLs and All Checks views, Issues/Warnings/Good, Fix and Ignore) for page-level checks; the free AIOSEO Analyzer Chrome extension for any URL, including competitors. Use one or two crawlers (Screaming Frog, Semrush, Ahrefs Site Audit, Sitebulb) for anything the plugin cannot see, such as chains and orphan detection across the whole crawl.

Sources: https://aioseo.com/technical-seo-audit/, https://aioseo.com/technical-seo/, https://aioseo.com/seo-audit-checklist/, https://aioseo.com/seo-audit/, https://aioseo.com/best-technical-seo-tools/, https://aioseo.com/how-to-perform-website-seo-analysis-on-wordpress/, https://aioseo.com/google-june-2026-spam-update/, https://aioseo.com/seo-sensor/
