# Blog claims checked against Google guidance

Scope: every `[Check]` item raised by the nine reader agents across the 571 aioseo.com blog posts (323 raw flags), merged into one row per distinct claim and grouped by topic. Each row gives the vendor claim with an example post and its publish date (several posts usually repeat the same claim), why it is wrong or outdated against Google Search documentation, and what to do instead. Only corrections we are confident about are in the tables; claims that depend on 2026 announcements or details we could not confirm are in "Needs verification" at the end. Use this file when an AIOSEO post, a client or the plugin UI suggests one of these tactics. Dates are post publish dates (modified dates in brackets where they matter).

## Contents

- Keywords, on-page and content
- Ranking-factor claims
- Crawling, indexing and robots.txt
- Sitemaps and indexing pings
- Canonicals, duplicates, pagination and parameters
- Redirects, 404s and migrations
- Structured data and rich results
- Page experience, speed and mobile
- Links and link attributes
- Local SEO
- AI search and AI content
- Search Console, Analytics and tools
- Social, multilingual and miscellaneous
- Needs verification

## Keywords, on-page and content

| Vendor claim (example post, date) | Why it is wrong or outdated | Do instead |
|---|---|---|
| Keep keyword density at 1 to 1.5% (Rank Math figure quoted), "optimal about 5%" or "at least 0.5%" (https://aioseo.com/best-keyword-density-checkers/ 2025-05-29; https://aioseo.com/quick-seo-wins/ 2024-09-17; https://aioseo.com/content-optimization/ 2024-07-04) | Google has no density target and treats stuffing as spam; 5% is stuffing; 0.5% is a plugin heuristic; the Authority Hacker study cited is correlation | Write naturally; use TruSEO density only as an over-use alarm |
| Use "LSI keywords" (https://aioseo.com/what-are-related-keywords/ 2025-07-02; https://aioseo.com/keyword-research-tips/ 2026-02-10; Writing Assistant descriptions) | Latent semantic indexing is a retired information-retrieval method that Google does not use | Cover related terms, entities, subtopics and questions found in the SERP |
| Minimum 300 words, "ideal 2,100 to 2,400 words", "aim for 2,000 to 3,000 words" (https://aioseo.com/blog-post-seo-checklist/ 2022-07-14; https://aioseo.com/website-authority/ 2026-06-10) | Word count is not a ranking factor (Mueller); HubSpot's figure came from its own top 50 posts of 2019 | Match intent and completeness; compare with what ranks |
| Title must be 60 characters (or 50 to 60, 60 to 70); meta description 160; "pixel measurement is not necessary" (https://aioseo.com/how-to-use-a-serp-snippet-tool/ 2023-04-14; https://aioseo.com/seo-title-tags/ 2022-05-03) | Truncation is by pixel width (about 600 px for titles); Google generates title links and rewrites descriptions often; no length is documented | Use counters as guidance; make the first ~60 characters complete; write for the click |
| "Google has confirmed there can be SEO value" in long keyword-rich titles (https://aioseo.com/how-to-use-an-seo-title-tag-generator-in-wordpress/ 2023-08-29) | Google gives no length target; keyword-padded titles read as stuffing and may be rewritten | Descriptive, concise, unique titles |
| Meta tags and descriptions "help rank" (https://aioseo.com/how-to-write-meta-descriptions-for-seo/ 2023-03-27) | Meta descriptions are not a ranking factor (the same posts concede it) | Write them for CTR only |
| Search engines weight the first and last paragraphs and want the keyword in the first 100 to 150 words and in every heading (https://aioseo.com/blog-post-seo-checklist/ 2022-07-14; https://aioseo.com/diy-seo-projects-for-beginners/ 2023-05-04) | Unsourced plugin heuristics; Google has no placement requirement | Answer the query early in natural language; skip awkward placements |
| Multiple H1s "confuse search engines" (https://aioseo.com/homepage-seo-tips/ 2025-09-02) | Google says multiple H1s are not a problem (Mueller, quoted in https://aioseo.com/h1-tags-seo/ 2026-08-07) | One H1 for clarity; fix duplicates as a theme bug, not a ranking issue |
| Keep H1 under ~70 characters to avoid snippet truncation (https://aioseo.com/h1-tags-seo/ 2026-08-07) | The H1 is not the snippet title; no Google length rule | Keep H1 readable; set the SEO title separately |
| No more than 300 words between headings, paragraphs up to 300 words (https://aioseo.com/seo-checklist/ 2024-02-05) | Arbitrary readability heuristic, not a Google rule | Structure for the reader |
| Slugs are a ranking factor (https://aioseo.com/what-is-a-slug-in-seo/ 2024-04-30) | URL words are a very lightweight signal (Mueller: "overrated") | Short, readable slugs; never change live URLs just for keywords |
| Underscores are "treated as word joiners" and HTTPS gives a "ranking advantage" (https://aioseo.com/best-wordpress-permalink-structure/ 2025-01-08) | Simplified: Google recommends hyphens; HTTPS is a lightweight signal | Use hyphens; use HTTPS for users and trust |
| Domain with the primary keyword "works best"; exact-match domains help (https://aioseo.com/wordpress-seo-optimization/ 2024-12-03; https://aioseo.com/how-to-do-seo-for-a-new-website-pro-tips/ 2023-07-17) | Keyword domains carry no ranking boost; the 2012 EMD update reduced low-quality EMDs | Choose a brandable domain |
| .biz and .us are "viewed as spam"; brand classifier quote (https://aioseo.com/choosing-the-right-domain-name-for-seo/ 2017-09-12) | Generic TLDs are not a ranking signal; the Matt Cutts quote is from an old talk | Pick a TLD that suits the audience; ccTLDs only for geo-targeting |
| Emojis lift CTR; "emoji search is on the rise" (https://aioseo.com/are-emojis-good-for-seo/ 2022-10-17) | No evidence given; Google may drop emojis from snippets; not a ranking factor | Test in GSC; do not assume |
| Auto-update the year in titles with the Current Year tag (https://aioseo.com/seo-hacks-to-grow-your-traffic/ 2023-05-08) | A changed year without changed content is misleading; Google asks for honest dates | Use the tag only on pages you refresh yearly |
| Change the published or updated date to signal freshness; "search engines love fresh content"; "freshness is a confirmed ranking factor" (https://aioseo.com/how-to-stop-content-decay-and-regain-lost-traffic/ 2023-08-07 [2025-12-04]; https://aioseo.com/content-optimization/ 2024-07-04) | Freshness matters only for queries that need it; date manipulation is risky | Update dates only after substantive changes; keep the original publish date |
| Publish regularly because frequency helps ranking (https://aioseo.com/seo-checklist/ 2024-02-05; https://aioseo.com/comprehensive-seo-checklist-2016/ 2024-02-05) | Frequency is not a ranking factor | Publish when you have something useful; schedule refreshes |
| Image alt text under 125 characters (https://aioseo.com/how-to-write-alt-text-for-images-for-seo-3-easy-tips/ 2021-06-17) | Screen-reader heuristic, not a Google rule | Concise, descriptive alt text |
| Add keywords to the image title attribute to rank (https://aioseo.com/how-to-name-image-files-for-seo-in-wordpress/ 2021-07-01; https://aioseo.com/wordpress-image-seo/ 2024-05-06) | The title attribute has no known ranking effect | Descriptive file name and alt text |
| Use JPEG for photos, PNG for screenshots, "stick to one format" (https://aioseo.com/what-is-the-best-image-format-for-your-website/ 2021-07-23; https://aioseo.com/how-to-best-optimize-images-in-wordpress/ 2022-08-29) | Outdated: WebP and AVIF are smaller and supported by Google Images | WebP or AVIF with fallbacks |
| Native lazy loading arrived in WordPress 5.4 (https://aioseo.com/how-to-best-optimize-images-in-wordpress/ 2022-08-29) | It was WordPress 5.5 | Rely on core lazy loading; do not lazy-load the LCP image |
| Meta keywords field (step 4 of https://aioseo.com/how-to-set-up-seo-for-different-languages-and-countries/ 2022-07-25 [2026-06-18]) | Google ignores meta keywords | Leave it empty |
| A self-ranking "best X" comparison with the publisher at number one (https://aioseo.com/commercial-intent-keywords/ 2026-06-02) | Google's reviews guidance expects first-hand evidence; unsubstantiated self-ranking is thin | Show testing evidence and fair comparisons |
| Headline and content "grades" (EMV, A++ optimiser grades) predict ranking (https://aioseo.com/best-wordpress-headline-analyzer-tool/ 2021-12-17; https://aioseo.com/website-seo-tools/ 2024-05-16) | Tool scores are correlation heuristics, not Google signals (the second post admits it) | Use as editing prompts |

Sources: https://aioseo.com/keyword-density/, https://aioseo.com/word-count-for-seo/, https://aioseo.com/seo-title-tags/, https://aioseo.com/h1-tags-seo/, https://aioseo.com/what-are-related-keywords/, https://aioseo.com/how-to-stop-content-decay-and-regain-lost-traffic/, https://aioseo.com/blog-post-seo-checklist/, https://aioseo.com/website-authority/

## Ranking-factor claims

| Vendor claim (example post, date) | Why it is wrong or outdated | Do instead |
|---|---|---|
| Bounce rate, dwell time, time on page and pogo-sticking are signals; "leaked docs show user data impacts rankings"; "pages that keep users longer rank better" (https://aioseo.com/how-to-run-a-site-speed-test-in-wordpress/ 2025-06-03; https://aioseo.com/internal-links/ 2025-01-23; https://aioseo.com/user-behavior-analytics-in-seo/ 2022-04-01; https://aioseo.com/content-pruning-seo/ 2026-05-12) | Google says it does not use bounce rate or Analytics data; the 2024 leak lists attributes without showing how they are used (the vendor's own /is-bounce-rate-a-ranking-factor/ agrees) | Use engagement as a UX and intent diagnostic |
| Higher CTR makes you rank higher (https://aioseo.com/seo-title-tags/ 2022-05-03; https://aioseo.com/ways-to-increase-your-organic-clickthrough-rates/ 2022-08-22; https://aioseo.com/how-to-write-meta-descriptions-for-seo/ 2023-03-27) | Google aggregates interaction data in some systems (Navboost, 2023 DOJ testimony) but CTR is not a lever site owners can pull to rank | Optimise CTR for traffic |
| Set "reduce bounce rate by 15%" as an SEO goal (https://aioseo.com/how-to-set-seo-goals-that-boost-rankings/ 2023-08-15) | Bounce rate is page-dependent and not a ranking factor | Use conversion or engagement rate as the business KPI |
| Social likes, shares and +1s increase rankings; social metrics feed ranking (https://aioseo.com/how-social-media-impacts-seo/ 2017-05-15; https://aioseo.com/all-in-one-seo-social-meta-panel-optimizes-your-social-shares/ 2015-09-10) | Google says social signals are not ranking factors; Google+ no longer exists | Treat social as distribution |
| Page speed is a "top" or "confirmed significant" ranking factor; "Google penalises slow sites"; "shaving one second boosts rankings" (https://aioseo.com/elementor-seo-tips/ 2022-03-25; https://aioseo.com/homepage-seo-tips/ 2025-09-02; https://aioseo.com/ultimate-wordpress-seo-guide/ 2024-02-28) | Core Web Vitals are a light signal; relevance dominates; the vendor's own /how-to-do-seo-checks-wordpress-guide/ says content quality comes first | Fix speed when far behind competitors, mainly for conversions |
| HTTPS or security is a "key ranking factor" (https://aioseo.com/membership-site/ 2024-12-19; https://aioseo.com/seo-growth-hacks/ 2023-12-28) | Google calls HTTPS a lightweight signal (2014) | Use HTTPS everywhere for trust and browsers |
| UX or page experience is a "significant ranking factor" (https://aioseo.com/how-to-add-internal-links-in-wordpress/ 2023-11-13; https://aioseo.com/what-is-search-visibility/ 2024-05-20) | Page experience is not a single ranking system (Google, 2023) | Improve UX for users and conversions |
| Backlinks are "a top 3" or "top two" ranking factor (https://aioseo.com/link-building-statistics/ 2022-05-05; https://aioseo.com/video-seo-guide/ 2025-12-02) | Unsourced; the same vendor quotes Gary Illyes (2023) saying links are no longer in the top 3 | Earn relevant links; prioritise content and intent |
| "Content quality is the number one ranking factor" (https://aioseo.com/rank-math-vs-yoast/ 2026-07-10; https://aioseo.com/how-to-learn-seo/ 2024-01-01) | Google does not publish a single top factor | Treat as rhetoric |
| E-E-A-T is "proven to impact rankings" or "a set of criteria Google uses to assess content" (https://aioseo.com/rank-math-review/ 2025-04-01; https://aioseo.com/how-to-write-an-author-bio-that-boosts-your-google-e-e-a-t-signals/ 2024-03-06) | E-E-A-T comes from the rater guidelines; raters do not rank pages | Build real author, evidence and trust signals |
| The algorithm history table ("YMYL Update 2018", HCU "heavily weighted on E-A-T") (https://aioseo.com/eeat-and-ymyl/ 2024-02-08) | Mixes community nicknames with confirmed updates and implies a direct E-A-T weight | Use Google's update names and dates |
| Author schema and author boxes make you "rank higher"; author schema is "recommended by Google" (https://aioseo.com/aioseo-review/ 2025-04-10; https://aioseo.com/how-to-add-author-schema-in-wordpress/ 2023-01-24) | Author markup is optional guidance, not a ranking factor | Add it for attribution; credibility comes from real expertise |
| Uptime: "search engines penalise sites that are often unavailable" (https://aioseo.com/ultimate-wordpress-seo-guide/ 2024-02-28) | No uptime penalty; persistent 5xx slows crawling and can drop URLs | Monitor uptime and fix 5xx quickly |
| Quality comments show an active community and raise rankings (https://aioseo.com/abc-of-wordpress-site-maintenance/ 2022-05-31) | Unsupported | Moderate comments for users; mark links ugc |
| Readability lifts rankings through engagement (https://aioseo.com/how-to-improve-readability-score-on-wordpress-step-by-step/ 2025-01-06) | Readability is not a ranking factor and the engagement chain is speculation | Write readably for the audience |
| Header tags give time-on-page and Core Web Vitals benefits (https://aioseo.com/header-tags/ 2022-04-14) | Tenuous; headings aid structure and accessibility | Use a logical heading hierarchy |
| Increased traffic signals value and boosts ranking (https://aioseo.com/how-to-increase-blog-traffic/ 2024-05-27) | Traffic is an outcome, not an input | Measure it; do not buy or fake it |

Sources: https://aioseo.com/is-bounce-rate-a-ranking-factor/, https://aioseo.com/google-ranking-factors/, https://aioseo.com/seo-myths/, https://aioseo.com/google-search-algorithm-leak/, https://aioseo.com/how-social-media-impacts-seo/, https://aioseo.com/elementor-seo-tips/, https://aioseo.com/link-building-statistics/, https://aioseo.com/eeat-and-ymyl/

## Crawling, indexing and robots.txt

| Vendor claim (example post, date) | Why it is wrong or outdated | Do instead |
|---|---|---|
| Use robots.txt Disallow to "prevent crawling and indexing", hide pages or avoid duplicate content (https://aioseo.com/duplicate-content/ 2025-02-20; https://aioseo.com/how-to-hide-a-page-in-wordpress/ 2022-01-07; https://aioseo.com/what-is-robots-txt-in-wordpress/ 2023-09-04) | robots.txt controls crawling, not indexing; blocked URLs can be indexed from links; Google cannot see a noindex or canonical on a blocked page | noindex (page crawlable) or canonical; robots.txt only for crawl noise |
| Combine Disallow and noindex on internal search URLs (https://aioseo.com/internal-site-search/ 2025-03-25) | The Disallow stops Google reading the noindex | Choose one: noindex if URLs are already indexed, then Disallow later if wanted |
| Block an unfinished language folder in robots.txt (https://aioseo.com/international-seo-keyword-research/ 2026-03-31) | Blocked URLs can still be indexed; hreflang to blocked pages breaks | Keep it on staging, password-protect or noindex until ready |
| robots.txt "improves indexing", "protects privacy" (https://aioseo.com/ultimate-guide-to-wordpress-robots-txt-files/ 2023-09-27; https://aioseo.com/what-is-robots-txt-in-wordpress/ 2023-09-04) | It is public and voluntary; bad bots ignore it | Use authentication for private content; WAF for bad bots |
| Crawl-delay and Clean-param directives (AIOSEO Robots.txt Editor posts, e.g. https://aioseo.com/how-to-edit-a-robots-txt-file-in-wordpress/ 2023-08-28) | Google ignores Crawl-delay; Clean-param is Yandex only | Use them only for Bing or Yandex needs; manage Googlebot load at the server |
| Test with the GSC robots.txt tester (https://aioseo.com/best-robots-txt-generator/ 2025-06-05) | Retired December 2023 | Use the robots.txt report in GSC Settings and URL Inspection |
| "Add disavow rules that prevent crawling of internal site search URLs" (https://aioseo.com/technical-seo/ 2024-03-13) | Wrong term: disavow is for backlinks | Disallow in robots.txt or noindex |
| Nofollow on internal links makes Google remove pages from its index (https://aioseo.com/index-your-website-on-google/ 2023-09-18) | Nofollow is a hint and does not deindex | Keep internal links followed for other reasons |
| Noindex saves crawl budget and avoids duplicate-content penalties (https://aioseo.com/noindex-meta-tag/ 2024-05-29; https://aioseo.com/robots-meta-tags/ 2024-01-09) | Noindexed pages are still crawled; there is no duplicate penalty | Canonicalise duplicates; noindex pages that should not appear |
| noarchive protects time-sensitive pages (https://aioseo.com/robots-meta-tags/ 2024-01-09) | Google removed cached links in 2024; the directive is moot for Google | Ignore unless other engines matter |
| Privacy and legal pages "shouldn't be indexed" (https://aioseo.com/indexing-in-seo/ 2023-11-21) | Vendor opinion; Google has no such rule | Leave them indexable unless there is a reason |
| Crawl budget matters for typical sites; prune or Crawl Cleanup "to save crawl budget" (https://aioseo.com/crawl-budget/ 2024-04-08; https://aioseo.com/how-to-stop-content-decay-and-regain-lost-traffic/ 2023-08-07) | Google's guide targets about 1M+ URL sites or 10k+ URLs changing daily | Prune for quality; crawl tuning for large faceted sites |
| "Blocked by robots.txt means Google thinks the page lacks value"; "Soft 404 means thin or AI content" (https://aioseo.com/website-not-showing-up-on-google/ 2026-08-28) | Blocked is a directive; soft 404 means the page looks like an error page | Read GSC reasons literally and fix the cause |
| The GSC "Coverage" tab (https://aioseo.com/index-your-website-on-google/ 2023-09-18; https://aioseo.com/how-to-add-google-search-console-to-your-wordpress-website/ 2024-12-05) | Renamed to Indexing > Pages | Use the Pages report |
| "Delete URL parameters from Google Search Console" (https://aioseo.com/how-to-delete-url-parameters-from-google-search-console/ 2022-06-14) | The URL Parameters tool was removed in 2022 | Canonicals, clean internal links, block pure noise in robots.txt |
| Use the site to publish AI content "indexable at scale" (https://aioseo.com/index-your-website-on-google/ 2023-09-18) | Scaled content abuse policy (March 2024) | Publish only reviewed, useful pages |

Sources: https://aioseo.com/duplicate-content/, https://aioseo.com/internal-site-search/, https://aioseo.com/ultimate-guide-to-wordpress-robots-txt-files/, https://aioseo.com/noindex-meta-tag/, https://aioseo.com/crawl-budget/, https://aioseo.com/website-not-showing-up-on-google/, https://aioseo.com/how-to-delete-url-parameters-from-google-search-console/, https://aioseo.com/index-your-website-on-google/

## Sitemaps and indexing pings

| Vendor claim (example post, date) | Why it is wrong or outdated | Do instead |
|---|---|---|
| Set sitemap priority and change frequency; sitemaps "prioritise" pages and bots "focus on priority pages" (https://aioseo.com/what-is-an-xml-sitemap/ 2024-11-28; https://aioseo.com/best-sitemap-generators/ 2024-07-25; https://aioseo.com/what-is-crawling-and-indexing/ 2023-09-11; https://aioseo.com/create-a-wordpress-xml-sitemap-without-a-plugin/ 2020-12-29) | Google ignores priority and changefreq; it uses lastmod only when consistently accurate | Keep lastmod accurate; ignore the other fields |
| Ping Google at google.com/ping?sitemap= (https://aioseo.com/how-to-submit-a-sitemap-to-google-wordpress-tutorial/ 2023-08-10; https://aioseo.com/sitemap-best-practices/ 2024-05-22) | Deprecated in 2023 and no longer works | Submit in GSC (or AIOSEO's GSC connection) and list the sitemap in robots.txt |
| IndexNow notifies Google, or "all other search engines" (https://aioseo.com/how-to-create-a-sitemap-in-wordpress/ 2020-12-22 [2026-03-05]; https://aioseo.com/what-is-indexnow-for-seo/ 2022-03-10) | Google does not participate; only IndexNow engines (Bing, Yandex, Naver, Seznam and others) share pings | Use IndexNow for Bing; keep the sitemap in GSC |
| Google "recommends" both an XML and an RSS/Atom sitemap and crawls RSS more often (https://aioseo.com/html-sitemap-vs-xml-sitemap/ 2024-12-31; https://aioseo.com/sitemap-best-practices/ 2024-05-22) | Google accepts RSS/Atom as a format; it does not require two sitemaps | One accurate XML sitemap is the baseline; RSS optional |
| An XML sitemap improves rankings or solves duplicate content (https://aioseo.com/html-sitemap-vs-xml-sitemap/ 2024-12-31; https://aioseo.com/what-is-an-xml-sitemap/ 2024-11-28) | Sitemaps aid discovery only and are a weak canonical hint | Use canonicals and redirects for duplicates |
| Without a sitemap Google "will skip money pages" (https://aioseo.com/what-is-an-xml-sitemap/ 2024-11-28) | Overstated for small, well-linked sites | Keep a sitemap, but rely on internal links |
| `<link rel="canonical">` inside a sitemap `<url>` (https://aioseo.com/canonical-url/ 2024-07-11) | Not a valid sitemap field | List only canonical URLs in the sitemap |
| The sitemap is "the second file crawlers visit" (https://aioseo.com/html-sitemap-vs-xml-sitemap/ 2024-12-31) | Unsupported | No action |
| A News sitemap needs Google Publisher Center approval (https://aioseo.com/create-a-google-news-sitemap/ 2021-12-22; https://aioseo.com/sitemap-best-practices/ 2024-05-22) | Google News inclusion is automatic and policy-based; Publisher Center is optional | Meet News content policies; submit the News sitemap in GSC |
| A News sitemap holds "articles at least two days old" (https://aioseo.com/create-a-google-news-sitemap/ 2021-12-22) | Reversed: it should list articles published in the last 2 days | Let the plugin keep only recent articles |
| A Google News listing raises main-search rankings or domain authority (https://aioseo.com/submit-your-site-to-google-news/ 2020-12-15) | Unsupported | Treat News as a separate surface |

Sources: https://aioseo.com/sitemap-best-practices/, https://aioseo.com/what-is-an-xml-sitemap/, https://aioseo.com/how-to-submit-a-sitemap-to-google-wordpress-tutorial/, https://aioseo.com/html-sitemap-vs-xml-sitemap/, https://aioseo.com/what-is-indexnow-for-seo/, https://aioseo.com/how-to-create-a-sitemap-in-wordpress/, https://aioseo.com/create-a-google-news-sitemap/, https://aioseo.com/best-sitemap-generators/

## Canonicals, duplicates, pagination and parameters

| Vendor claim (example post, date) | Why it is wrong or outdated | Do instead |
|---|---|---|
| Canonicalise paginated pages to page 1 or a view-all page (https://aioseo.com/canonical-url/ 2024-07-11; https://aioseo.com/pagination-seo/ 2025-04-23) | Google recommends self-referencing canonicals on paginated pages; pointing all to page 1 hides deeper items; rel prev/next unused since 2019 | Self-canonical each page; unique titles via Paged Format |
| GSC lets you manually submit canonical URLs (https://aioseo.com/canonical-url/ 2024-07-11) | Not a GSC feature | Set rel=canonical; check Google's choice in URL Inspection |
| Google does not pass PageRank through canonicals (https://aioseo.com/canonical-url/ 2024-07-11) | Google consolidates signals to the chosen canonical | Use canonicals to consolidate near-duplicates |
| Duplicate content brings penalties, "in severe cases the entire site" (https://aioseo.com/duplicate-content/ 2025-02-20; https://aioseo.com/technical-seo/ 2024-03-13; https://aioseo.com/what-is-a-url-parameter/ 2024-04-03) | Duplication is filtered and consolidated, not penalised, except deceptive or scraped spam | Canonicalise or merge for clarity |
| Paraphrase or spin content to avoid "duplicate content penalties"; Spin Rewriter for guest posts and networks (https://aioseo.com/best-ai-paraphrasing-tools/ 2025-08-12) | No penalty for normal syndication; spinning for link networks is spam | Syndicate with a canonical or attribution; write original guest content |
| Non-canonical versions "may still be indexed" (https://aioseo.com/canonical-tags/ 2025-03-04) | Edge behaviour; usually folded under the canonical | Check Google-selected canonical in URL Inspection |
| Block parameter URLs in robots.txt to consolidate (https://aioseo.com/what-is-a-url-parameter/ 2024-04-03) | Blocked URLs cannot pass canonical signals | Canonical for content parameters; Disallow only pure junk (tracking, internal search) |

Sources: https://aioseo.com/canonical-url/, https://aioseo.com/canonical-tags/, https://aioseo.com/duplicate-content/, https://aioseo.com/pagination-seo/, https://aioseo.com/what-is-a-url-parameter/, https://aioseo.com/technical-seo/, https://aioseo.com/best-ai-paraphrasing-tools/

## Redirects, 404s and migrations

| Vendor claim (example post, date) | Why it is wrong or outdated | Do instead |
|---|---|---|
| A 302 or 307 "does not pass link equity" (https://aioseo.com/url-redirection-tips/ 2025-10-07; https://aioseo.com/wordpress-redirects/ 2026-06-19; https://aioseo.com/redirect-types/ 2024-03-07) | Google says redirects pass signals; a long-lived 302 can be treated as permanent | Pick the code that states your intent: 301 permanent, 302 temporary |
| "19 redirect types" including 418, 505 and other 4xx/5xx codes (https://aioseo.com/redirect-types/ 2024-03-07; https://aioseo.com/all-in-one-seo-vs-rank-math/ 2025-03-12) | 4xx and 5xx are not redirects and have no SEO use | Use 301, 302, 307, 308, and 410 for removals |
| Redirect all 404s, or deleted pages, to the homepage (https://aioseo.com/how-to-automatically-redirect-404-pages-to-the-homepage-in-wordpress/ 2022-09-08; https://aioseo.com/how-to-add-301-redirects-in-wordpress/ 2021-05-04) | Google treats irrelevant redirects as soft 404s | Redirect only to a relevant replacement; otherwise 404 or 410 |
| 404s are "harmful to SEO", "de-rank the page" and signal poor quality (https://aioseo.com/how-to-avoid-404-errors-when-updating-your-wordpress-site/ 2022-08-18) | 404s for removed pages are normal (the vendor's other posts agree) | Fix 404s that have traffic or backlinks; leave the rest |
| A 410 makes Google "de-index it immediately" (https://aioseo.com/wordpress-redirects/ 2026-06-19) | 410 is processed slightly faster than 404, not instantly | Use 410 for permanent removal and wait |
| Add a redirect for every 404 (https://aioseo.com/how-to-decode-http-status-codes/ 2025-05-13) | Only when a relevant target exists | Triage 404 logs |
| Domain move: Duplicator, Relocate Site, Change of Address, then done (https://aioseo.com/how-to-move-a-wordpress-site-to-a-new-domain/ 2022-01-19) | Incomplete | Keep 301s at least a year (ideally permanently), update internal links, canonicals, sitemaps, structured data and analytics |
| Switching SEO plugins never hurts rankings (https://aioseo.com/migrating-from-rank-math-to-all-in-one-seo/ 2021-04-01) | True only if titles, robots, canonicals, schema and sitemap URLs carry over | Spot-check pages and resubmit the new sitemap URL |
| Maintenance mode via a functions.php `wp_die()` snippet (https://aioseo.com/how-to-put-your-wordpress-site-in-maintenance-mode/ 2022-01-28) | Returns a 500-class error unless a 503 header is set | Return 503 with Retry-After; keep it short |

Sources: https://aioseo.com/url-redirection-tips/, https://aioseo.com/wordpress-redirects/, https://aioseo.com/redirect-types/, https://aioseo.com/how-to-avoid-404-errors-when-updating-your-wordpress-site/, https://aioseo.com/how-to-automatically-redirect-404-pages-to-the-homepage-in-wordpress/, https://aioseo.com/how-to-move-a-wordpress-site-to-a-new-domain/, https://aioseo.com/how-to-decode-http-status-codes/, https://aioseo.com/how-to-put-your-wordpress-site-in-maintenance-mode/

## Structured data and rich results

| Vendor claim (example post, date) | Why it is wrong or outdated | Do instead |
|---|---|---|
| FAQ schema earns rich snippets, more SERP space, PAA, "87% CTR" (https://aioseo.com/ways-to-increase-your-organic-clickthrough-rates/ 2022-08-22; https://aioseo.com/types-of-schema-markup/ 2025-06-18; https://aioseo.com/website-optimization-tips/ 2025-09-30; https://aioseo.com/how-to-add-faq-schema-in-wordpress/ 2026-07-08) | FAQ rich results were restricted in August 2023 to well-known government and health sites and stopped showing for all sites on 7 May 2026; PAA does not use FAQ markup | Keep visible FAQs only where they help users |
| HowTo schema for featured snippets and rich results (https://aioseo.com/how-to-get-featured-snippets-on-google/ 2023-01-23 [2026-02-12]; https://aioseo.com/how-to-get-cited-by-ai-search-tools/ 2026-06-25) | HowTo rich results were removed in 2023; schema does not select featured snippets | Write clear steps in HTML lists |
| Hide FAQs with the block's visibility toggle while keeping the schema (https://aioseo.com/best-wordpress-faq-plugins/ 2024-06-13; https://aioseo.com/how-to-use-a-wordpress-faq-block-to-boost-seo-and-get-more-traffic/ 2022-11-24) | Structured data must describe content visible to users | Show the FAQs or remove the markup |
| Mark up your own business's reviews for stars; "can I use product review schema for my own reviews? Yes"; embed Product Review in Local Business (https://aioseo.com/how-to-add-product-review-schema-in-wordpress/ 2022-12-26; https://aioseo.com/types-of-schema-markup/ 2025-06-18; https://aioseo.com/how-to-use-barnacle-seo/ 2024-08-06) | Self-serving reviews on LocalBusiness and Organization pages are not eligible for review snippets (since 2019); reviews must be of the item on the page | Review markup only for genuine reviews of a product or item the page is about |
| Test with Google's Structured Data Testing Tool (https://aioseo.com/how-to-add-product-review-schema-in-wordpress/ 2022-12-26; https://aioseo.com/how-to-add-rich-snippets-to-wordpress/ 2022-09-29) | Retired in 2021 | Rich Results Test and validator.schema.org |
| Schema "helps land featured snippets", gives "better indexing", helps voice search and AI Overviews (https://aioseo.com/how-to-use-schema-markup-to-boost-your-seo/ 2022-09-22; https://aioseo.com/what-is-answer-engine-optimization/ 2025-08-14) | Not documented; Google says AI features need no special markup | Use schema for eligible rich results and clarity |
| Schema improves rankings indirectly through CTR engagement (https://aioseo.com/schema-types-to-boost-ecommerce/ 2024-06-10; https://aioseo.com/what-is-structured-data-and-how-does-it-impact-seo/ 2023-03-01) | Schema is not a ranking factor; the engagement chain is speculation | Expect eligibility, not rank gains |
| "Google supports 31 rich result types" and the long supported-types list (https://aioseo.com/what-is-structured-data-and-how-does-it-impact-seo/ 2023-03-01; https://aioseo.com/how-to-run-a-rich-results-test-in-wordpress/ 2022-12-29) | Several types have been retired or narrowed since | Check Google's Search Gallery before promising a result |
| Sitelinks search box toggle (Search Appearance > Advanced) (https://aioseo.com/how-to-run-a-rich-results-test-in-wordpress/ 2022-12-29; https://aioseo.com/website-optimization-tips/ 2025-09-30) | Google retired the sitelinks search box in November 2024 | Leave it; it has no visible effect |
| FAQPage is "one of the most cited schema types in AI Overviews" (https://aioseo.com/restaurant-seo/ 2026-07-01) | Unsourced | Do not add markup for that reason |
| "Price Valid Until is required" to fix the offers error (https://aioseo.com/how-to-fix-missing-schema-properties-for-woocommerce-products/ 2021-11-23) | priceValidUntil is recommended, not required; the error is fixed by offers, review or aggregateRating | Fill offers correctly; add priceValidUntil for sale prices |
| Merchant listing and Product snippet treated as one thing (https://aioseo.com/schema-types-to-boost-ecommerce/ 2024-06-10) | They are distinct experiences with different required properties | Check Google's merchant listing docs; match markup to page and feed |
| LocalBusiness output on the homepage only "per Schema.org requirements" (https://aioseo.com/how-to-add-local-business-schema-in-wordpress/ 2023-01-30) | That is an AIOSEO design choice, not a schema.org or Google rule | Multi-location sites need markup on each location page; verify output |
| Paste breadcrumb PHP "after the `</head>` tag" in header.php (https://aioseo.com/breadcrumb-navigation-in-wordpress/ 2024-03-12) | Places markup outside body; edits are lost on theme update | Use the block, shortcode or a child-theme hook inside body |
| Web Stories rank higher because Google prioritises AMP; a theme "meets AMP standards" as an SEO plus (https://aioseo.com/how-to-optimize-your-google-web-story/ 2024-12-24; "21 Best WordPress Themes for SEO", 2021-12-30) | AMP is not a ranking factor and lost special treatment (Top Stories, 2021) | Judge Web Stories on audience value |
| AI Schema output can go live as generated (https://aioseo.com/seo-advice/ 2026-05-19) | Generated markup may describe content not on the page | Validate and compare with visible content |

Sources: https://aioseo.com/how-to-add-faq-schema-in-wordpress/, https://aioseo.com/rank-math-vs-yoast/, https://aioseo.com/how-to-add-product-review-schema-in-wordpress/, https://aioseo.com/how-to-run-a-rich-results-test-in-wordpress/, https://aioseo.com/how-to-use-a-wordpress-faq-block-to-boost-seo-and-get-more-traffic/, https://aioseo.com/types-of-schema-markup/, https://aioseo.com/how-to-add-local-business-schema-in-wordpress/, https://aioseo.com/how-to-create-custom-schema-markup-in-wordpress/

## Page experience, speed and mobile

| Vendor claim (example post, date) | Why it is wrong or outdated | Do instead |
|---|---|---|
| Core Web Vitals are LCP, FID and CLS (https://aioseo.com/elementor-seo-tips/ 2022-03-25; https://aioseo.com/page-speed-test-tools/ 2025-06-25; https://aioseo.com/seo-checkers/ 2024-04-17) | INP replaced FID on 12 March 2024 | Track LCP up to 2.5 s, INP up to 200 ms, CLS up to 0.1 (75th percentile) |
| TTFB, FCP and TTI are Core Web Vitals (https://aioseo.com/website-speed-optimization/ 2025-11-04) | They are diagnostics, not Core Web Vitals | Use them to debug LCP and INP |
| Use Google's Mobile-Friendly Test (https://aioseo.com/seo-best-practices/ 2023-12-06; https://aioseo.com/comprehensive-seo-checklist-2016/ 2024-02-05) | Retired in December 2023 with the Mobile Usability report | Lighthouse, PageSpeed Insights, real devices |
| Core Web Vitals sit under GSC Enhancements; page experience is one ranking system (https://aioseo.com/technical-seo-audit/ 2024-06-20) | GSC shows them under Experience; Google said in 2023 page experience is not a single system | Read the Core Web Vitals report under Experience |
| HTTPS makes pages faster (HTTP ~6 s vs HTTPS ~0.5 s demo) (https://aioseo.com/https-and-seo/ 2023-10-26) | The gain comes from HTTP/2 or HTTP/3, which browsers use over TLS | Enable HTTPS and HTTP/2 or HTTP/3 |
| "Starting May 2021 speed is part of Core Web Vitals" and "3 seconds is slow" as rules (https://aioseo.com/how-to-best-optimize-images-in-wordpress/ 2022-08-29; https://aioseo.com/optimizing-web-forms-for-seo/ 2024-04-18) | Dated framing; uncited thresholds | Use CWV field data |

Sources: https://aioseo.com/page-speed-test-tools/, https://aioseo.com/website-speed-optimization/, https://aioseo.com/mobile-seo-tools/, https://aioseo.com/seo-best-practices/, https://aioseo.com/https-and-seo/, https://aioseo.com/elementor-seo-tips/, https://aioseo.com/technical-seo-audit/

## Links and link attributes

| Vendor claim (example post, date) | Why it is wrong or outdated | Do instead |
|---|---|---|
| Disavow spammy or "toxic" links immediately; use toxic scores and in-tool disavow (https://aioseo.com/link-building-guide/ 2022-06-07 [2025-01-13]; https://aioseo.com/toxic-backlinks/ 2024-04-09; https://aioseo.com/website-seo-tools/ 2024-05-16; https://aioseo.com/negative-seo/ 2024-03-26) | Google ignores most spammy links; disavow is for manual actions or links you built in a scheme; toxic scores are third-party | Do nothing for random spam; disavow only with a manual action or a self-built scheme |
| Disavow "in GSC" (https://aioseo.com/best-link-building-tools/ 2025-06-26; https://aioseo.com/how-to-add-google-search-console-to-your-wordpress-website/ 2024-12-05) | The disavow tool is separate from the main GSC interface | Find it only when needed |
| DA, DR and Authority Score as quality measures (https://aioseo.com/website-authority/ 2026-06-10; https://aioseo.com/how-to-use-barnacle-seo/ 2024-08-06) | Third-party metrics Google does not use (Mueller quoted in /referring-domains-vs-backlinks-seo/) | Judge relevance and real traffic |
| Guest posting "in return for a dofollow link", at scale, with optimised anchors (https://aioseo.com/how-to-boost-your-small-business-seo/ 2022-11-03; https://aioseo.com/link-building-guide/ 2022-06-07) | Large-scale article campaigns with keyword anchors are link spam | Guest post for audience; mark paid or exchanged links sponsored |
| Reciprocal links and link exchanges with local businesses; "exchange a link for a link" (https://aioseo.com/best-link-building-tools/ 2025-06-26; https://aioseo.com/link-building-statistics/ 2022-05-05) | Excessive link exchanges are a link scheme | Link where it helps users; no quid pro quo at scale |
| Barnacle profiles "build domain authority" (https://aioseo.com/how-to-use-barnacle-seo/ 2024-08-06) | Profile links are mostly nofollow or ugc | Use third-party profiles for SERP presence and referral traffic |
| Nofollow means "don't crawl this link"; nofollow links pass no value at all; nofollow needed to avoid passing authority (https://aioseo.com/how-to-add-nofollow-links-in-wordpress/ 2020-12-08; https://aioseo.com/ultimate-wordpress-seo-guide/ 2024-02-28; https://aioseo.com/toxic-backlinks/ 2024-04-09) | Since March 2020 nofollow, sponsored and ugc are hints; linking out to good sources needs no nofollow | Use rel values as Google defines them |
| Affiliate links "must" be nofollow to avoid penalties (https://aioseo.com/nofollow-vs-dofollow-links/ 2022-02-24) | Google asks for sponsored (nofollow is acceptable) | rel="sponsored" on affiliate and paid links |
| "Nofollow a secondary source" (https://aioseo.com/link-building-guide/ 2022-06-07) | Non-standard use | Cite sources normally |
| Open outbound links in a new tab for dwell time and SEO (https://aioseo.com/link-building-guide/ 2022-06-07; https://aioseo.com/blog-post-seo-checklist/ 2022-07-14) | No search benefit; a UX choice | Decide on UX grounds |
| Pages linking to high-DR sites rank higher (https://aioseo.com/blog-post-seo-checklist/ 2022-07-14) | Correlation only | Link to the best source |
| Top players quietly buy links; buying expired domains and mass AI content are "gray hat" (https://aioseo.com/what-are-paid-links-in-seo/ 2023-06-01; https://aioseo.com/white-hat-vs-black-hat-seo/ 2026-03-24) | Paid links violate link spam policy; expired domain abuse and scaled content abuse are spam policies (March 2024) | Refuse these tactics |
| "Infographics: build them" vs "skip them" (https://aioseo.com/seo-hacks-to-grow-your-traffic/ 2023-05-08; https://aioseo.com/referring-domains-vs-backlinks-seo/ 2023-04-27) | Neither is a rule; embed-code links with keyword anchors are a known spam pattern | Low priority; original data earns links better |
| Link-equity sculpting and fixed internal:external ratios (80:20, 70:30) (https://aioseo.com/nonprofit-seo/ 2024-04-01; https://aioseo.com/topic-clusters/ 2023-10-05) | No Google basis; nofollow sculpting does not work | Link for users; no ratios |

Sources: https://aioseo.com/toxic-backlinks/, https://aioseo.com/link-building-guide/, https://aioseo.com/nofollow-vs-dofollow-links/, https://aioseo.com/how-to-use-barnacle-seo/, https://aioseo.com/what-are-paid-links-in-seo/, https://aioseo.com/white-hat-vs-black-hat-seo/, https://aioseo.com/negative-seo/, https://aioseo.com/website-seo-tools/

## Local SEO

| Vendor claim (example post, date) | Why it is wrong or outdated | Do instead |
|---|---|---|
| Offer giveaway entries in exchange for reviews (https://aioseo.com/a-complete-local-seo-checklist/ 2021-02-23) | Incentivised reviews violate Google's policy; Yelp prohibits soliciting reviews | Ask every customer without incentives |
| Responding to reviews is "a confirmed ranking signal"; reviews are a "direct ranking factor" (https://aioseo.com/restaurant-seo/ 2026-07-01; https://aioseo.com/seo-tips-small-businesses/ 2026-04-07) | Google lists review count and score within prominence; responding is not confirmed as a signal | Respond for customers and trust |
| GBP posts and activity are ranking signals; a local area code is a strong signal; conflicting hours are "penalised" (https://aioseo.com/how-to-use-a-google-business-profile-to-imrpove-local-seo/ 2023-03-23; https://aioseo.com/local-seo-tips/ 2026-04-21; https://aioseo.com/law-firm-seo/ 2026-07-31) | Unconfirmed beyond Google's relevance, distance, prominence statement | Keep data accurate; post for customers |
| Embedding a Google Map improves rankings (implied in https://aioseo.com/how-to-embed-google-maps-in-wordpress/ 2023-02-20) | The vendor's own /restaurant-seo/ says it does not | Embed for directions only |
| Mark up your own reviews on your site for GBP-style stars (https://aioseo.com/local-seo/ 2024-04-10) | Self-serving LocalBusiness review markup is not eligible | Collect reviews on GBP and third-party sites |
| Two near-identical sites for one business dominating page 1 as a tactic (local citations guide, probable source https://aioseo.com/how-to-get-local-seo-citations/ 2023-02-09) | Duplicate or doorway sites for one location can breach spam policies | One site, one location page per real location |
| NAP is a ranking factor (https://aioseo.com/what-is-nap-in-seo/ 2023-02-02) | Consistency helps Google match listings; impact is modest | Keep a master NAP and fix inconsistencies once |
| Voice and local statistics (Google Assistant +400%, 1 billion voice searches) (https://aioseo.com/a-complete-local-seo-checklist/ 2021-02-23; https://aioseo.com/guide-to-voice-search/ 2025-03-20) | Dated (2017 to 2021) and unsourced | Do not quote them |

Sources: https://aioseo.com/a-complete-local-seo-checklist/, https://aioseo.com/restaurant-seo/, https://aioseo.com/seo-tips-small-businesses/, https://aioseo.com/local-seo-tips/, https://aioseo.com/law-firm-seo/, https://aioseo.com/local-seo/, https://aioseo.com/what-is-nap-in-seo/, https://aioseo.com/how-to-manage-google-reviews-for-improved-seo/

## AI search and AI content

| Vendor claim (example post, date) | Why it is wrong or outdated | Do instead |
|---|---|---|
| llms.txt improves AI Overviews and citations, is a "VIP pass", "directly increases" citation likelihood (https://aioseo.com/what-is-llms-txt/ 2025-07-16; https://aioseo.com/restaurant-seo/ 2026-07-01) | A 2024 proposal, not a standard; Google has said it does not use it; no major AI search provider documents using it; the vendor's 2026-09-11 post says it has no ranking effect and no citation guarantee | Optional, low-effort hygiene; do not promise results |
| llms.txt can hold Allow rules to grant or restrict AI crawlers (https://aioseo.com/what-is-llms-full-txt/ 2025-12-09) | The format has no allow or deny semantics | Control crawlers in robots.txt by user agent |
| Allowing Google-Extended helps AI Overviews (https://aioseo.com/how-to-get-cited-by-ai-search-tools/ 2026-06-25) | Google-Extended governs Gemini training and grounding, not Search or AI Overviews | Googlebot access and snippet eligibility govern AI Overviews |
| Special schema, FAQ or HowTo markup helps AI Overviews, voice or AI citation; "3.2x more citations with structured data" (https://aioseo.com/how-to-get-cited-by-ai-search-tools/ 2026-06-25; https://aioseo.com/types-of-schema-markup/ 2025-06-18) | Google says AI features need no special markup; the figures are unnamed correlations | Standard SEO; schema only where it matches content |
| "Google SGE" and "SGE shows for 86.83% of results"; Bard (https://aioseo.com/generative-engine-optimization-geo/ 2025-02-13; https://aioseo.com/optimizing-for-google-sge/ 2025-03-06) | SGE became AI Overviews (2024); the figure is not credible as stated | Use current product names; measure your own queries |
| GEO engines "prioritise time on page", "penalise slow sites", "value external links" (https://aioseo.com/generative-engine-optimization-geo/ 2025-02-13) | Unsupported | Clear, accurate, well-structured content |
| Generate entire articles with AI as first drafts; "High-Volume AI Content Sites" as a use case (https://aioseo.com/generative-engine-optimization-geo/ 2025-02-13; Yoast vs Rank Math vs AIOSEO, 2024-12-26) | Scaled content abuse policy (March 2024) covers mass low-value content regardless of tool | Human review, original value, real byline |
| Auto-translate whole sites with AI (https://aioseo.com/how-to-set-up-seo-for-different-languages-and-countries/ 2022-07-25 [2026-06-18]; https://aioseo.com/multilingual-wordpress-site/ 2026-04-28) | Unreviewed machine translation at scale risks scaled content abuse | Native review before indexing |
| Content freshness is a ranking factor "revealed in the leaked documents" (https://aioseo.com/what-is-answer-engine-optimization/ 2025-08-14; https://aioseo.com/how-to-rank-in-googles-ai-overviews/ 2025-08-06) | The leak does not show how attributes are used | Refresh honestly when content changes |
| Block all AI crawlers as a default (robots.txt Block AI Crawlers posts, e.g. https://aioseo.com/how-to-block-an-unwanted-web-crawler/ 2025-03-27) | A business decision; blocking search and retrieval bots removes AI-search citations | Decide per user agent (training vs search vs user-initiated) |

Sources: https://aioseo.com/what-is-llms-txt/, https://aioseo.com/llms-txt-vs-robots-txt-vs-xml-sitemap/, https://aioseo.com/what-is-llms-full-txt/, https://aioseo.com/how-to-get-cited-by-ai-search-tools/, https://aioseo.com/generative-engine-optimization-geo/, https://aioseo.com/optimizing-for-google-sge/, https://aioseo.com/how-to-rank-in-googles-ai-overviews/, https://aioseo.com/how-to-block-an-unwanted-web-crawler/

## Search Console, Analytics and tools

| Vendor claim (example post, date) | Why it is wrong or outdated | Do instead |
|---|---|---|
| Universal Analytics paths ("Audience > Geo", Goals, Behavior menu) and GA verification for GSC (https://aioseo.com/how-to-set-up-seo-for-different-languages-and-countries/ 2022-07-25; https://aioseo.com/important-sections-of-google-analytics-explained/ 2017-05-24; Google Site Verification post 2016-02-19) | UA stopped processing in July 2023 | GA4 reports and key events; verify GSC by DNS or AIOSEO's connection |
| Google Optimize for testing (GSC vs GA post 2024-05-15; https://aioseo.com/best-woocommerce-seo-plugins/ 2025-01-09) | Sunset September 2023 | Use a current testing tool |
| GA4 bounce rate must be added manually, or does not exist (https://aioseo.com/is-bounce-rate-a-ranking-factor/ 2023-10-03) | GA4 has a native Bounce rate metric (sessions not engaged) since 2022 | Add it from the metric list if needed |
| GSC "set preferred domain" and Mobile Usability report (https://aioseo.com/how-to-add-google-search-console-to-your-wordpress-website/ 2024-12-05) | Both removed | Redirect to one host; use Lighthouse |
| Rank tracker "position" equals your SERP rank (https://aioseo.com/how-to-track-keyword-rankings-in-wordpress/ 2023-06-05) | GSC position is an average across queries, locations and devices | Call it average position |

Sources: https://aioseo.com/how-to-add-google-search-console-to-your-wordpress-website/, https://aioseo.com/is-bounce-rate-a-ranking-factor/, https://aioseo.com/how-to-set-up-seo-for-different-languages-and-countries/, https://aioseo.com/important-sections-of-google-analytics-explained/, https://aioseo.com/how-to-track-keyword-rankings-in-wordpress/, https://aioseo.com/best-woocommerce-seo-plugins/

## Social, multilingual and miscellaneous

| Vendor claim (example post, date) | Why it is wrong or outdated | Do instead |
|---|---|---|
| Hreflang example with a single href and no self-reference (https://aioseo.com/multilingual-seo-mistakes/ 2022-07-12 [2026-06-08]) | Hreflang needs reciprocal annotations including a self-reference, plus x-default where relevant | Let the translation plugin output full reciprocal sets; validate |
| Subdirectories are the "recommended" structure (https://aioseo.com/multilingual-wordpress-site/ 2026-04-28) | Google accepts ccTLDs, subdomains and subdirectories | Choose by business and maintenance needs |
| Programmatic page case studies as models (Transit, KrispCall, Flyhomes) (https://aioseo.com/seo-case-studies/ 2024-02-07) | Predate the March 2024 scaled content policy; survivorship bias | Only with unique value per page |
| Raw SQL DELETE examples for database cleanup (https://aioseo.com/how-to-clean-your-wordpress-database/ 2017-04-06 [2026-02-20]) | Risky, and the examples contain typos | Back up; use WP-CLI or a maintained plugin |
| "Optimising forms for SEO" (https://aioseo.com/optimizing-web-forms-for-seo/ 2024-04-18) | Forms are conversion work with no search effect | Treat as CRO |
| Wix links include # via JavaScript (https://aioseo.com/wix-vs-wordpress-for-seo/ 2024-06-04) | Dated | Evaluate platforms on current output |
| Twitter Cards raise engagement 43%; "social drives 31.24% of traffic" (https://aioseo.com/add-twitter-cards-in-wordpress/ 2020-12-31; https://aioseo.com/negative-seo/ 2024-03-26) | Old Twitter claims and undated figures | Do not quote |
| "Google Helpful Content Update" as a current, separate rule; HCU and Product Reviews update conflated (https://aioseo.com/technical-seo-audit/ 2024-06-20; https://aioseo.com/ecommerce-seo/ 2024-10-22) | Both were folded into core ranking systems | Apply people-first and reviews guidance generally |

Sources: https://aioseo.com/multilingual-seo-mistakes/, https://aioseo.com/multilingual-wordpress-site/, https://aioseo.com/seo-case-studies/, https://aioseo.com/how-to-clean-your-wordpress-database/, https://aioseo.com/optimizing-web-forms-for-seo/, https://aioseo.com/technical-seo-audit/

## Needs verification

Claims we could not confirm or refute with confidence. Check primary documentation before advising on them.

1. A Search Console toggle that removes a site from AI Overviews, AI Mode and Discover AI Overviews, site-wide only, with page-level controls due by March 2027 (https://aioseo.com/opt-out-of-ai-overviews/ 2026-07-15).
2. Search Console added AI Overview and AI Mode segments to the Search type filter in early June 2026 (https://aioseo.com/googles-ai-search-overhaul/ 2026-07-24). Google documented in 2025 that AI Mode data is counted in the Web search type; separate segments are unconfirmed here.
3. Google I/O on 19 May 2026 made AI Mode the default for 1B+ users; AI Overviews in about 48% of queries; position 1 CTR down from about 27% to 11% (https://aioseo.com/googles-ai-search-overhaul/ 2026-07-24).
4. A May 2026 Google spam policy on manipulating AI search results, and the June 2026 spam update window of 24 to 26 June (https://aioseo.com/google-june-2026-spam-update/ 2026-07-17).
5. Bing Webmaster Tools "AI Performance" dashboard (February 2026) showing Copilot citations (https://aioseo.com/how-to-get-cited-by-ai-search-tools/ 2026-06-25).
6. Resolved (2026-10-11): FAQ rich results stopped appearing in Google Search for all sites on 7 May 2026. Several independent reports quote Google's Search Central documentation; the FAQ report and Rich Results Test support were dropped in June 2026 and Search Console API support in August 2026. Stated by https://aioseo.com/rank-math-vs-yoast/ (2026-07-10).
7. Google "Ask Maps" weighting review language, and public Instagram content indexed from July 2025 (https://aioseo.com/restaurant-seo/ 2026-07-01).
8. Whether nosnippet or max-snippet on a page affects use in AI Overviews in exactly the way AIOSEO's help text implies (https://aioseo.com/robots-meta-tags/ 2024-01-09). Google documents that snippet controls apply to AI features; the AIOSEO toggle wording needs checking.
9. Which user agents AIOSEO's "Block AI Crawlers" and Unwanted Bots lists contain, and whether they separate training from search bots (https://aioseo.com/how-to-stop-bot-traffic/ 2025-03-18).
10. Web Stories visibility in Search and Discover after Google's later changes, and "higher CTR than blog posts" (https://aioseo.com/what-are-google-web-stories/ 2024-12-17).
11. GBP Q&A feature status and Local Services Ads Google Guaranteed lifetime cap of $2,000 (https://aioseo.com/what-is-the-google-guaranteed-badge-for-local-businesses/ 2023-03-16).
12. Whether AIOSEO emits LocalBusiness markup on individual Location posts in multi-location mode (https://aioseo.com/how-to-add-local-business-schema-in-wordpress/ 2023-01-30).
13. Whether the AIOSEO FAQ block outputs FAQPage JSON-LD by default and what the visibility toggle emits when content is hidden (https://aioseo.com/how-to-add-faq-schema-in-wordpress/ 2026-07-08).
14. "Merchant listing markup keeps out-of-stock items showing in results" (https://aioseo.com/ecommerce-seo/ 2024-10-22).
15. Vendor AI-citation statistics: 60% of AI-cited sources outside Google's top 10; FAQ schema 28% to 40% citation lift; 46.7% of Perplexity's top sources are communities; Grok share 2% to 18% (https://aioseo.com/how-to-get-cited-by-ai-search-tools/ 2026-06-25; https://aioseo.com/how-to-rank-in-googles-ai-overviews/ 2025-08-06).
16. Rich-result CTR figures from "Milestone Research" (FAQ 87%, rich snippets +17%) and "rich results get 58% of clicks vs 41%" (https://aioseo.com/what-is-structured-data-and-how-does-it-impact-seo/ 2023-03-01; https://aioseo.com/seo-statistics/ 2024-02-14).

Sources: https://aioseo.com/opt-out-of-ai-overviews/, https://aioseo.com/googles-ai-search-overhaul/, https://aioseo.com/google-june-2026-spam-update/, https://aioseo.com/how-to-get-cited-by-ai-search-tools/, https://aioseo.com/rank-math-vs-yoast/, https://aioseo.com/restaurant-seo/, https://aioseo.com/robots-meta-tags/, https://aioseo.com/what-is-structured-data-and-how-does-it-impact-seo/
