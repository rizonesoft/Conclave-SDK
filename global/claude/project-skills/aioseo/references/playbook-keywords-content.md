# Playbook: keywords, on-page and content

Scope: how to choose keywords, match intent, map keywords to URLs, optimise titles, descriptions, headings, URLs and images, write for readers and snippets, build internal links with Link Assistant, show E-E-A-T with Author SEO, and audit, refresh, prune and consolidate content on a WordPress site running AIOSEO. It merges the content and on-page advice from 571 aioseo.com blog posts (2015 to October 2026) and restates it against Google Search documentation. Vendor rules of thumb are kept where they are useful and labelled as heuristics; where posts conflict, the Google-aligned answer is given with the conflict noted in one line. AIOSEO features are named with one menu path; settings screens are documented in content-optimization.md, settings-search-appearance.md and search-statistics-gsc.md. Seasonal pages are in playbook-monitoring-growth.md, local and product keywords in playbook-local-ecommerce.md, answer-engine work in playbook-ai-search.md.

## Contents

- Ground rules: what Google uses and what it does not
- Keyword research and difficulty bands
- Search intent and the funnel
- Keyword mapping and cannibalisation
- Content planning and topic clusters
- On-page: titles and meta descriptions
- On-page: headings, URLs and the homepage
- On-page: images and media
- TruSEO, focus keyphrases and keyword placement
- Writing for readers and snippets
- Internal linking with Link Assistant
- E-E-A-T and Author SEO
- Content audits
- Refresh, pruning and consolidation
- Content decay

## Ground rules: what Google uses and what it does not

Apply these before any rule below. Many AIOSEO posts state the opposite somewhere; the posts that cite Google directly agree with this list.

| Topic | Google position | How to treat vendor advice |
|---|---|---|
| Keyword density | No target exists; stuffing is spam | TruSEO's density check (passes at 0.5% or more) is a smoke test for under-use and stuffing only |
| Word count | Not a ranking factor (John Mueller: "Word count is not a ranking factor") | Length follows intent and what the topic needs |
| "LSI keywords" | Google does not use latent semantic indexing | Say "related terms, entities, subtopics and questions" |
| Bounce rate, dwell time, time on page | Google says it does not use Google Analytics data or bounce rate for ranking | Use as UX and intent-mismatch diagnostics |
| CTR | Not a lever to game. Google uses aggregated interaction data in some systems (DOJ trial testimony, 2023, on Navboost), but individual CTR changes do not move rankings on demand | CTR work is traffic work |
| Social signals | Not ranking factors (Mueller and Illyes quotes in /seo-myths/) | Social is a distribution channel |
| E-E-A-T | A Search Quality Rater Guidelines framework, not a ranking factor or score | Build the underlying signals: real authors, evidence, sources, trust pages |
| Meta descriptions | Not a ranking factor; Google often rewrites them | Write them for the click |
| Meta keywords | Ignored by Google | Leave empty |
| Readability scores | Not a ranking factor | Use for the reader |
| Freshness | Matters for queries that need it; dates must be honest | Update when content changes substantively |
| AI-assisted content | Allowed if helpful; mass-produced low-value content is spam (scaled content abuse policy, March 2024) | Human review, original value, real byline |
| Helpful Content Update | Folded into core ranking systems in March 2024 | The people-first principle stands; the update name does not |
| FAQ and HowTo rich results | HowTo removed in 2023; FAQ restricted in August 2023 to well-known government and health sites and stopped showing for all sites on 7 May 2026 | Keep FAQ sections only when they help readers |

Conflict noted: some posts call speed, HTTPS, UX, CTR, bounce rate and freshness "confirmed" or "top" ranking factors; others (/google-ranking-factors/, /is-bounce-rate-a-ranking-factor/, /seo-myths/, /word-count-for-seo/) quote Google saying they are not, or are minor. Follow the second group.

Sources: https://aioseo.com/google-ranking-factors/, https://aioseo.com/seo-myths/, https://aioseo.com/is-bounce-rate-a-ranking-factor/, https://aioseo.com/word-count-for-seo/, https://aioseo.com/keyword-density/, https://aioseo.com/helpful-content-update/, https://aioseo.com/google-search-algorithm-leak/, https://aioseo.com/rank-math-vs-yoast/

## Keyword research and difficulty bands

Order of decision: intent first, then difficulty, then volume. A 100-search commercial term can outearn a 2,000-search informational term (vendor opinion, consistent across posts).

Workflow:
1. Free SERP pass. Search the seed in a private window (personalisation and location still apply, so treat it as a read of format, not a rank check). Note the content types on page 1 (guides, listicles, product pages, video), ads, People Also Ask (clicking one loads more), and related searches at the bottom.
2. Tool pass. Semrush Keyword Magic Tool or Ahrefs Keywords Explorer: filter difficulty, read the intent label, compare volume. Free sources: Google Keyword Planner (needs a Google Ads account, no spend; shows ranges such as 1K to 10K when no ads run), Google Trends for seasonality, AnswerThePublic, AlsoAsked, autocomplete.
3. Check what ranks. Look at the traffic of the top 3 to 4 pages, not only the query's volume: a top page often ranks for hundreds of variants (one post's example: 350+ keywords), so single-query volume understates the opportunity.
4. Pick the target, then record it in the keyword map (next sections).

Difficulty bands (Semrush KD, as quoted in /keyword-difficulty-in-seo-what-is-it-and-how-to-use-it/). KD is a third-party estimate built mostly from the backlink profiles of ranking pages; Google has no such metric. The scale is logarithmic, so 50 is already hard.

| KD | Label | Who should target it |
|---|---|---|
| 0 to 14 | Very easy | New and low-authority sites |
| 15 to 29 | Easy | New and low-authority sites |
| 30 to 49 | Possible | Sites with some links and topical depth |
| 50 to 69 | Difficult | Established sites with relevant links |
| 70 to 84 | Hard | Strong domains, with a content and link plan |
| 85 to 100 | Very hard | Rarely worth it for small sites |

Worked ladders (Semrush figures quoted by the vendor, undated): flooring 90% (very hard), wood flooring 71%, exotic wood flooring 15% (easy), Brazilian teak hardwood flooring 11% (very easy). "local seo" 96% informational, "local seo for beginners" 72%, "local seo for wordpress" 31% possible and commercial. Rule: when a keyword is Hard, filter Keyword Magic Tool to easier long-tail variants.

Decision rules:
- New or small sites: Very easy to Possible terms, long-tail (3+ words), commercial or transactional where the business sells something, plus some informational content for links and email capture.
- Use SERP weak spots, not KD alone: low-authority domains, forums or UGC on page 1 signal an opening (LowFruits "Weak Spots" method; vendor tool, not independently validated).
- Do not skip zero-volume or N/A terms that match a buyer's exact problem: volumes are clickstream estimates and small exact-match queries can convert (vendor anecdotes).
- Of two equally easy terms with the same intent, take the higher volume.
- Authority rule of thumb (vendor, /website-authority/): very strong domains can target head terms; low-authority sites go long-tail. DA, DR and Authority Score are third-party proxies; Google does not use them.
- Document a maximum KD per site in the SEO SOP so writers do not chase unwinnable terms.

Idea sources, cheapest first: autocomplete, People Also Ask, People Also Search For, related searches, GSC Performance > Queries (most queries shown are long-tail), AIOSEO Keyword Rank Tracker related keywords (Search Statistics > Keyword Rank Tracker, expand a row), "Get Additional Keyphrases" in the editor (Semrush; free Semrush plans allow about 10 requests a day; country selector), customer emails, sales calls, reviews, Reddit, Quora, Facebook groups, YouTube autocomplete.

Competitor gap:
1. Semrush Keyword Gap (your domain plus 1 to 4 competitors) or Ahrefs Content Gap (can compare sub-folders, for example blog vs blog).
2. Filter intent to Commercial and Transactional, and KD to Easy and Very easy.
3. Use the Untapped tab (they rank, you do not) and sort by the competitor's position to find their top-3 terms.
4. If you already rank around positions 8 to 26, improve the existing page; if not, plan a new page.
5. Track the chosen terms in Search Statistics or GSC.

International markets: define the market as language plus country (fr-FR, fr-CA, fr-BE), brainstorm local terms with native speakers (cell phone, mobile, Handy; sweater, jumper), validate volume with the country selected, run an eye test of the local SERP (drop terms whose SERP means something else, such as "chips" in the US and UK), then study the top 3 local sites. Hreflang and URL structure are in playbook-technical.md.

Statistics in posts, all (vendor claim) with no primary source: "long-tail is 70% of search traffic", "54.31% of queries contain 3+ words", "94.74% of keywords get 10 or fewer searches a month". Treat as directional.

Sources: https://aioseo.com/keyword-research/, https://aioseo.com/keyword-difficulty-in-seo-what-is-it-and-how-to-use-it/, https://aioseo.com/keyword-research-tips/, https://aioseo.com/low-competition-keywords/, https://aioseo.com/keyword-gap-analysis/, https://aioseo.com/international-seo-keyword-research/, https://aioseo.com/how-to-find-long-tail-keywords-and-increase-organic-traffic/, https://aioseo.com/website-authority/

## Search intent and the funnel

Four intents (Semrush letters): I informational, N navigational, C commercial (comparing, deciding), T transactional (ready to act). One query can carry two. Keyword intent is not the whole of search intent: the SERP also tells you the expected format and depth.

Read intent from the SERP, not the label:
- If page 1 is all how-to guides, a listicle will lose; if it is product pages, a blog post will lose. Reshape the page to the winning format class.
- If every top result is weak, you may ignore their format, but name one concrete way you will beat the current number one (shorter intro, plain language, fact-checked sources, better images, a missing step).
- Pricing queries straddle commercial and transactional: answer with a pricing page, not a blog post.
- Navigational: make sure you rank for your own brand and product names.

Three free commercial-intent checks (about a minute, /commercial-intent-keywords/):
1. Results are roundups, comparisons or reviews.
2. Paid ads sit above organic (3 to 4 ads is a strong buyer signal; Keyword Planner CPC reinforces it).
3. People Also Ask shows "is X worth it", "A or B", "best X for Y".

Modifier to format map:

| Modifier | Format |
|---|---|
| best, top, recommended, for [use case] | Roundup with short, differentiated, hands-on reviews |
| vs, alternative(s), A or B | Head-to-head comparison, short table, honest pros and cons |
| review, worth it | Single review with first-hand evidence |
| price, cost, quote, rates | Pricing page |
| emergency, same day, 24 hour, near me | Service page with contact and hours (local) |
| buy, book, order | Product or booking page with a clear CTA |
| how to add, choose, create, find, fix | Tutorial with steps, product mentioned where it helps |

Funnel (See-Think-Do, mapped to TOFU, MOFU, BOFU):

| Stage | Intent | Content | Channels that suit it |
|---|---|---|---|
| See / TOFU | Informational | "What is X", general how-tos, statistics | SEO, social |
| Think / MOFU | Commercial | Comparisons, reviews, how-tos with the product, testimonials | SEO, YouTube, email, retargeting |
| Do / BOFU | Transactional | Product, pricing, booking, offers | SEO, email, PPC, Local Services Ads |

Decision rules:
- Revenue beats traffic. Vendor illustration: 500 visits a month at 2.4% conversion on a $500 product is $6,000; 10,000 visits at 0.02% is $1,000. Build MOFU and BOFU pages first for a business site; add TOFU for links, email capture and topical coverage.
- In a cluster, the pillar can be TOFU while spokes target MOFU and BOFU; the vendor builds the earning spokes first.
- Comparison pages that include your own product: be objective, show hands-on use, credit competitor strengths, keep tables to a few features. Google's reviews guidance expects first-hand evidence and comparison detail; a self-ranking "best" list with the publisher at number one is thin unless substantiated.
- Email can monetise informational content that does not convert from search.

Sources: https://aioseo.com/search-intent/, https://aioseo.com/commercial-intent-keywords/, https://aioseo.com/buyer-intent-keywords/, https://aioseo.com/tofu-mofu-bofu/, https://aioseo.com/what-is-serp-analysis/, https://aioseo.com/customer-centric-content-strategy/, https://aioseo.com/seo-secrets-to-grow-revenue/

## Keyword mapping and cannibalisation

Rule: each keyword cluster belongs to exactly one URL, and each URL serves one primary intent.

Steps (/keyword-mapping/, 2026-09-18):
1. Gather keywords from research, competitor gaps and GSC queries.
2. Cluster by intent, not by shared words. "keyword research" and "keyword research tools" need different pages.
3. Same-page test: would a searcher for each term be happy landing on the same page? If yes, same cluster.
4. Assign each cluster to an existing URL or mark "new page needed".
5. Build the map with these columns: URL, primary keyword, secondary keywords, intent, status (update, create, consolidate), internal link targets. Optional: owner, last updated, current position, priority.
6. Set the primary keyword as the Focus Keyphrase and close variants as Additional Keyphrases in the editor (AIOSEO Settings > General > Focus Keyphrase). Vendor rule of thumb: 1 primary plus 3 to 5 secondary terms per page.
7. Turn the map into links: Link Assistant shows pages that mention a topic but do not link to its owner page.
8. Review the map every few months and whenever GSC shows two URLs swapping for one query.

Cannibalisation:
- Symptom: two or more URLs target the same intent (example from the post: /how-to-do-keyword-research/, /keyword-research-guide/, /keyword-research-for-seo/), or GSC shows the ranking URL for a query alternating.
- Fix in this order: differentiate the intents; else consolidate into the strongest URL and 301 the others (AIOSEO > Redirects); else declare one primary and point internal links and anchors at it.
- Store specific: category pages target broad commercial terms, product pages target specific ones; do not let them compete.
- Multisite or multiple domains: assign a keyword to one site only.
- Unique SEO titles per page are the cheapest guard against accidental overlap.

Query fan-out note: AI answer systems split broad questions into sub-queries, which rewards a site where every subtopic has one clear home and descriptive internal links. The post itself says mapping does not guarantee citation in ChatGPT or AI Overviews.

Sources: https://aioseo.com/keyword-mapping/, https://aioseo.com/keyword-research-tips/, https://aioseo.com/category-page-seo-for-woocommerce/, https://aioseo.com/guide-to-wordpress-multisite-seo/, https://aioseo.com/content-pruning-seo/, https://aioseo.com/seo-title-tags/

## Content planning and topic clusters

Strategy:
- Start from 3 to 5 business objectives, each with a strategy, KPI and target; write the strategy down.
- Core topics sit where what you offer overlaps with what the audience cares about. Jobs-to-be-done beats demographic personas (Google research cited by the vendor: only 31% of mobile video-game searchers were men aged 18 to 35).
- Fewer, better pages. Vendor claims: 2 strong posts a month beat 8 mediocre ones; 20 focused posts beat 200 scattered ones. Publishing frequency is not a ranking factor; consistency matters for the team, not for Google.
- New blog: about 1 post a week, then scale. Put refreshes in the editorial calendar alongside new posts, including a January pass for any title that contains a year.

Topic clusters:
1. Pick 3 to 5 core topics, broad enough for a cluster but not so broad they need hundreds of pages.
2. One pillar (cornerstone) page per topic that summarises each subtopic and links down to it.
3. Spoke pages go deep on one subtopic each, link up to the pillar and across to siblings where relevant.
4. No fixed page count ("3 pages is probably too few"); aim to cover the topic better than competitors' clusters.
5. Mark pillars with Cornerstone Content (AIOSEO Settings > General > Cornerstone Content) so Link Assistant prioritises them, and group the cluster's keywords in the Keyword Rank Tracker.

Silos: a physical silo is a URL folder (/blog/seo/tools/), a virtual silo is links only. Both are organisational tools, not requirements. Click depth and internal links matter; folder depth does not. Use categories as chapters for pillars and tags as an index for subtopics.

Categories and tags:
- Categories: broad, hierarchical, one per post where possible, roughly 5 to a dozen in total, never leave "Uncategorized", name with the topic keyword.
- Tags: specific, flat, optional, up to about 5 per post, no single-use tags.
- They help through internal links and archive pages, not directly (Mueller). Noindex thin tag archives; keep useful category and topic hubs indexable (decide per taxonomy in Search Appearance > Taxonomies). Conflict: a 2021 post says noindex all categories and tags; the 2026 WooCommerce post says index useful categories. Follow the 2026 post.

Scaled and programmatic content:
- Only for repetitive, data-driven pages (listings, glossaries, area-code or location data) where each page carries unique, useful data, and edit it.
- Failing example from the vendor: 15 city pages sharing the same 200 words. That is scaled content abuse under Google's March 2024 policy.
- Case studies that gained from programmatic pages (/seo-case-studies/) predate that policy and show survivorship bias: do not copy them without unique value per page.

UGC: Google does not treat comments and forum posts differently, but large volumes of low-quality UGC can reduce crawling and quality perception. Moderate, paginate heavy comment threads, mark user links rel="ugc".

Repurposing: pick evergreen, high-traffic or well-linked posts (Search Statistics Content Performance), then derive FAQs, key points, social posts, email, video or infographics, and cross-link. AIOSEO AI Content can draft these from an existing post (AIOSEO Settings > AI Copilot or AI Content tab); human review is required.

Sources: https://aioseo.com/content-strategy/, https://aioseo.com/seo-content-strategy/, https://aioseo.com/topic-clusters/, https://aioseo.com/seo-silos/, https://aioseo.com/how-categories-and-tags-work/, https://aioseo.com/the-difference-between-tags-and-categories/, https://aioseo.com/content-repurposing-for-seo/, https://aioseo.com/seo-advice/

## On-page: titles and meta descriptions

SEO title (the `<title>` element):
- Put the primary term near the start. Users scan the first 2 to 3 words, and image-search captions truncate early.
- Keep the first ~60 characters a complete, sensible title. Google truncates by pixel width (roughly 580 to 600 px on desktop), not characters, and since August 2021 it often generates its own title link. Character targets in posts vary (50 to 60, 60 to 65, 60 to 70): use AIOSEO's counter as guidance only. Longer titles are not penalised, but anything after the cut-off is invisible and padding with keywords reads as stuffing.
- State the unique value (numbers, outcome, audience, free download). Differentiate from titles already ranking (format, step count, angle).
- Unique per page. The SEO title can differ from the H1, product name or post title.
- "How to" promises steps: do not use it if the page has none.
- Homepage pattern: `[Primary keyword] | [Brand]`. Local service pattern: `[Service] in [City] | [Brand]` (example: "Emergency Plumber in Chicago | SpeedyFix").
- Years: the Current Year smart tag updates the year on 1 January. Use it only on pages you actually refresh each year; bumping a year without updating the content is misleading (the vendor's own /on-page-seo/ warns against it).
- Emojis are allowed (emoji picker beside the title and description fields). They are not a ranking factor and Google may drop them; test in GSC rather than assume a CTR lift.
- Headline Analyzer scores (power, emotional and common word balance, sentiment, length) are copy heuristics, not Google signals.

Meta description:
- Not a ranking factor. It is the pitch for the click and Google rewrites it often, especially when the query is a related term.
- About 150 to 160 characters is a display guideline, not a rule; Google truncates by pixels.
- Describe the page, answer the query, include the primary term once (Google bolds matches), give a reason to click, and make each one unique. Replace the default Excerpt smart tag with a written description on pages that matter.
- Local service pattern: what you do + who for + one credibility signal.

AIOSEO, one line each:
- Per post: AIOSEO Settings > General (Appearance in newer builds) > Edit Snippet, with the snippet preview and smart tags.
- Site-wide templates: Search Appearance > Content Types and Taxonomies.
- Homepage: Search Appearance > Global Settings > Home Page.
- AI suggestions: the AI Generator button beside each field (5 options, credits). Review every suggestion: clicking Add replaces the field including smart tags.
- Bulk: Bulk CSV export and import of titles and descriptions, or the AI bulk actions on the All Posts list.
- Front-end check: admin bar > AIOSEO > SEO Preview.

Diagnostic: high impressions with low CTR at a stable position usually means the title or description does not match the intent. Rewrite, annotate the change in SEO Revisions, and read the result after a few weeks. Expect impression and click changes, not ranking jumps.

Vendor statistics, all (vendor claim) and inconsistent across posts: position 1 CTR quoted as 19% to 39.8%; "moving up one position raises CTR by 2.8%"; "Google is 57% more likely to rewrite too-long titles"; "25.02% of top pages lack a meta description". Use only as rough orientation.

Sources: https://aioseo.com/seo-title-tags/, https://aioseo.com/how-to-write-meta-descriptions-for-seo/, https://aioseo.com/how-to-use-a-serp-snippet-tool/, https://aioseo.com/how-to-use-google-snippet-preview-to-boost-seo/, https://aioseo.com/how-to-change-the-seo-title-in-wordpress/, https://aioseo.com/how-to-use-an-seo-title-tag-generator-in-wordpress/, https://aioseo.com/are-emojis-good-for-seo/, https://aioseo.com/homepage-seo-guide/

## On-page: headings, URLs and the homepage

Headings:
- One H1 per page, normally the post title. Google says multiple H1s cause no problem (Mueller), but a second H1 usually signals a theme or builder bug, so fix it. Conflict: one homepage post says multiple H1s "confuse search engines"; follow Google.
- H1 is not a ranking factor on its own. A 2026 Rankability study cited by the vendor found most top pages use a single H1 and no stronger ranking pattern for keyword-in-H1 (its 93.5% and 12.5% figures add to more than 100%, so treat the numbers loosely).
- Verify the H1 exists: right-click > Inspect > find `<h1>`. Divi, Elementor and older themes sometimes output the title as H2 or styled text; fix in the theme or builder heading settings.
- H2 for sections, H3 for subsections. Never choose a level for its size; bold large text is not a heading. Do not add a Heading 1 block inside post content.
- Descriptive headings, not "Overview". Question headings suit snippet and answer extraction.
- Subheading every ~300 words and paragraphs under ~120 words are AIOSEO readability heuristics, not Google rules.

URLs and slugs:
- Settings > Permalinks > Post name. Large stores may use /%category%/%postname%/, but renaming a category later breaks every URL under it.
- Short, readable, lowercase, hyphens (not underscores), drop stop words where clarity survives, no dates or years (so the page can be refreshed), no IDs or session parameters.
- Words in URLs are a very lightweight signal (Mueller: keywords in URLs are "overrated"). Do not change a live URL for SEO alone.
- Changing a published slug needs a 301. AIOSEO's URL Slug Monitor prompts "Add Redirect to Improve SEO"; Automatic Redirects can do it without the prompt (Redirects > Settings > Automatic Redirects).

Homepage:
- Choose static page or latest posts (Settings > Reading), then set the homepage title and description (Search Appearance > Global Settings > Home Page).
- One H1 that states the primary keyword and value proposition; one CTA above the fold; secondary keywords in subheadings; copy that answers the visitor's main problem.
- The homepage carries most authority: link to the top revenue pages, services, products and best posts, and keep important pages within about 3 clicks.
- Trust: reviews, testimonials, logos, certifications, contact details.
- Organization (or LocalBusiness) structured data comes from the Knowledge Graph and Local SEO settings. An on-page FAQ is fine for users; it will not earn FAQ rich results.
- Before rewriting, review the top 5 to 10 competitor homepages (headline, repeated phrases, layout, depth) and run AIOSEO > SEO Analysis on your own homepage.

Sources: https://aioseo.com/h1-tags-seo/, https://aioseo.com/header-tags/, https://aioseo.com/best-wordpress-permalink-structure/, https://aioseo.com/what-is-a-slug-in-seo/, https://aioseo.com/homepage-seo-guide/, https://aioseo.com/homepage-seo-tips/, https://aioseo.com/on-page-seo/, https://aioseo.com/elementor-seo-tips/

## On-page: images and media

Checklist:
1. File name: short, descriptive, lowercase, hyphenated, matching what the image shows (`marine-recruit-holding-plank.jpg`, not `man-exercising.jpg` or `324oiu98.jpg`). Rename before upload. Do not insert unrelated keywords. File names are a light signal alongside alt text, surrounding text and structured data.
2. Alt text: describe the image and its purpose as you would to someone who cannot see it. Include the keyword only when it describes the image. No "image of". About 125 characters is a screen-reader heuristic, not a Google rule.
3. Decorative images (dividers, CSS backgrounds): empty alt (`alt=""`) so screen readers skip them.
4. Captions only where useful (product galleries, event photos, charts); captions and alt may match.
5. Title attribute: optional, no known ranking effect.
6. Size and format: resize to the content width, compress before upload (a 2 to 4 MB stock photo is the most common speed problem in the posts), prefer WebP or AVIF with fallbacks. Google Images supports BMP, GIF, JPEG, PNG, WebP, SVG and AVIF. The 2021 "JPEG for photos, PNG for screenshots" advice is outdated.
7. Lazy loading is native in WordPress since 5.5 (one post says 5.4; it was 5.5). Do not lazy-load the main above-the-fold image.
8. Place images near the text they illustrate. Original images and screenshots beat widely used stock (Mueller: stock images have no web-search penalty but are harder to rank in image search).
9. Images are included in AIOSEO's XML sitemap by default (Sitemaps > General Sitemap > Advanced Settings). Do not block image folders in robots.txt.
10. Attachment pages are thin: keep Redirect Attachment URLs on (Search Appearance > Image SEO or Media; options Attachment, Attachment Parent, Disabled).
11. Licences: use your own, Creative Commons with attribution, or licensed stock. Posts cite US statutory damages of up to $150,000 per infringement (vendor claim).

At scale:
- Image SEO templates (Search Appearance > Image SEO) set alt, title, caption, description and file name formats from smart tags. Templated alt text is only better than nothing: write real alt text for important images.
- AI alt text: Media Library > select images > Bulk actions > Generate Alt Text for Images with AI (about 10 credits per image). Review the output; AI alt text can be wrong about what is shown.
- Never use AI images to fake software screenshots, invent data in infographics or show products that differ from what customers receive.

Video:
- Embed (YouTube or Vimeo) rather than uploading to WordPress. For Google video features, the video must be the main content of a dedicated, indexable watch page; a video in a sidebar or below long text is not treated as a watch page.
- Add a transcript or summary, chapters, a descriptive title (keyword near the start), and Video structured data. The video sitemap is a Pro module (Sitemaps > Video Sitemap).

Sources: https://aioseo.com/how-to-best-optimize-images-in-wordpress/, https://aioseo.com/wordpress-image-seo/, https://aioseo.com/how-to-write-alt-text-for-images-for-seo-3-easy-tips/, https://aioseo.com/image-filename-seo/, https://aioseo.com/decorative-images/, https://aioseo.com/what-is-the-best-image-format-for-your-website/, https://aioseo.com/how-to-lazy-load-images-in-wordpress/, https://aioseo.com/video-seo-guide/

## TruSEO, focus keyphrases and keyword placement

What TruSEO is: a plugin checklist and score out of 100 (Focus Keyphrase, Basic SEO, Title, Readability, plus spelling and headline checks in 2026 builds). Google has no focus-keyword concept.

Placement checklist TruSEO applies: keyphrase in the SEO title, meta description, URL, first paragraph, some subheadings and at least one image alt; plus density, internal and external link presence, title and description length. The vendor itself says "these are suggestions; Google doesn't require them".

Decision rules:
- Treat 70 to 80 as good. Do not chase 100: vendor anecdotes include posts at 60 outranking perfect scores. Posts disagree on targets (60+, 70+, 75 to 80); pick a house threshold, not a goal.
- Skip any recommendation that makes copy awkward: forcing the keyphrase into more subheadings, adding it to alt text of an unrelated image, repeating it to pass density.
- Density: passes at 0.5% or more; 2% or more may indicate stuffing (vendor guideline). Never edit to hit a percentage. One post's "optimal ~5%" is stuffing territory; ignore it.
- "First 100 to 150 words", "first and last paragraph", "keyword in every H-tag" are plugin heuristics. Answering the query early is good writing; repeating the exact phrase is not required.
- Use synonyms and related terms. AIOSEO's "Get Additional Keyphrases" (Semrush) and the SEOBoost Writing Assistant's term lists are coverage prompts, not requirements; the writing tools even suggest terms scraped from competitors' comments. Tool grades (Writing Assistant, Surfer, Clearscope) do not map to rankings; one vendor post notes an A++ grade did not correlate with quality and a low grade can win the snippet.
- Additional Keyphrases: add 1 to 3 close variants of the same intent instead of repeating the focus phrase. Free (Lite) allows one focus keyphrase; paid plans allow more.
- Workflow per post (5 to 15 minutes): AIOSEO Settings > General: Edit Snippet > Focus Keyphrase > Basic SEO > Readability > Schema > Advanced (robots, canonical) > Social. The TruSEO Highlighter (eye icon) jumps to the flagged sentence.
- Optimize with AI (Optimization tab or AI Copilot > Auto-Optimize) rewrites title, description, headline and content in one pass. It saves a revision first, does not save the post until you click Update, and costs credits per run. Read every change; it can remove nuance or facts.
- The dashboard "AIOSEO Overview" widget (posts rated Needs Improvement, Okay, Good, and posts without a focus keyphrase) works as a quick triage list.

Sources: https://aioseo.com/on-page-seo-checklist-wordpress/, https://aioseo.com/what-is-a-focus-keyword/, https://aioseo.com/keyword-density/, https://aioseo.com/best-keyword-density-checkers/, https://aioseo.com/best-seo-score-checkers/, https://aioseo.com/how-to-add-multiple-keywords-in-wordpress/, https://aioseo.com/how-to-use-a-writing-assistant-in-wordpress/, https://aioseo.com/best-rank-math-alternative/

## Writing for readers and snippets

People-first rules:
- Write for the reader, then check SEO. "Always edit with the reader in mind" is the vendor's own rule.
- Show first-hand experience: original photos, screenshots, video, data, named examples, first-person detail where honest. A Zyppy study cited by the vendor found first-person language among the biggest differences for sites that gained after the 2022 to 2023 helpful-content updates (vendor-reported, unverified).
- Be as long as the topic needs. Correlation studies are cited both ways: Ahrefs (900M+ pages) found backlink correlation rose to about 1,000 words then fell; HubSpot's "2,100 to 2,400 words" came from its own top 50 posts of 2019 (median 2,164, range 333 to 5,581); Backlinko found 3,000+ word pages earned most links. None is a target. Conflict: /website-authority/ (2026) says aim for 2,000 to 3,000 words; /word-count-for-seo/ and Google say no target. Follow Google.
- Cite primary sources. Link out to reputable, original sources with descriptive anchors; external links are not a ranking factor and need no nofollow when you vouch for them. On YMYL pages, linking to dubious sites reads as untrustworthy.
- Transparency for commercial pages: pricing, shipping, guarantees, refunds near the decision point.
- Quality conversation test (/topic-clusters/): knows the subject, understands the reader, gets to the point, avoids jargon, offers at least one useful fact the reader did not have.

Structure for scanning and extraction:
- Inverted pyramid: the answer or summary and the key link first, details next, background last. Not for narrative pieces.
- Under each question heading, answer in the first 1 to 3 sentences (40 to 60 words is the vendor's snippet range), then expand.
- 2 to 4 sentence paragraphs, one idea each; lists for steps ("Step 1", "Step 2"); tables for comparisons and data; sparing bold for key definitions; a short summary or Key Points block at the top of long pieces.
- Self-contained sections that make sense when quoted alone.
- CTA verb-first and visually distinct.

Readability heuristics (AIOSEO Readability tab, not Google rules):
- Flesch Reading Ease 60 to 70 for general audiences (bands: 90 to 100 very easy, 60 to 70 plain English, 30 to 50 difficult, 0 to 30 very difficult). Match the audience; technical readers tolerate lower scores.
- Sentences around 20 words or fewer, paragraphs up to 120 words, passive voice used sparingly, transition words, not starting consecutive sentences with the same word, media present.
- Worked example from the vendor: 51.5 to 76.6 after adding subheadings, switching passive to active and varying sentence starts.
- Stat: "54% of US adults read at or below a 6th-grade level" is attributed to Gallup via a secondary source (vendor claim).

Featured snippets and People Also Ask:
- Types: paragraph, list, table, video. You cannot buy or mark up your way in; Google selects.
- Recipe: question H2 matching the query, a concise 40 to 60 word answer directly below, then steps as a list or data as a table. Check who holds the snippet now and beat a vague or overlong answer with a tighter one.
- Mine PAA and PASF for headings and sections; copy the dominant answer format; keep answers non-promotional. PAA inclusion does not require FAQ markup.
- Table of Contents block (AIOSEO - Table of Contents) builds anchor links from headings; Google may show jump links, never guaranteed. Keep TOC labels short (the block lets the label differ from the heading). Use Synced plus Standalone TOCs for 3,000+ word guides.
- FAQ sections: keep them when real customer questions deserve answers. FAQ rich results no longer show for any site (from 7 May 2026). Never hide FAQ text while outputting FAQ markup (the FAQ block's visibility toggle): structured data must describe visible content.
- Voice and conversational queries: full-sentence questions from support emails and AnswerThePublic, answered directly. Voice-search statistics in posts (1 billion a month, 8 billion assistants) are unsourced (vendor claim).

Vendor statistics: "moving from position 2 to 1 gives about 74% more clicks", "featured snippets take ~8% of clicks", "featured snippet visibility can raise traffic 516%". All (vendor claim), unsourced.

Sources: https://aioseo.com/how-to-get-featured-snippets-on-google/, https://aioseo.com/how-to-optimize-for-googles-people-also-ask/, https://aioseo.com/how-to-use-googles-people-also-search-for/, https://aioseo.com/how-to-use-the-flesch-reading-ease-score-to-grow-traffic/, https://aioseo.com/how-to-use-the-inverted-pyramid-to-improve-web-content/, https://aioseo.com/scannability/, https://aioseo.com/wordpress-table-of-contents-seo/, https://aioseo.com/how-to-add-faq-schema-in-wordpress/

## Internal linking with Link Assistant

Why: internal links help discovery and crawling, pass PageRank and context, and tell Google which pages matter. A page in the sitemap but with no internal links is known but unimportant: "sitemaps say a page exists, internal links say it matters."

Rules:
1. Every page you care about gets at least one contextual internal link. At publish time, add links to the new post from 2 to 5 relevant older posts (posts quote 2 to 3, 3 to 4 and 3 to 5; about 10 minutes per post).
2. Prefer contextual body links over nav, footer or sidebar links.
3. Anchor text: descriptive, concise, varied across pages, not "click here" or whole sentences, no exact-match keyword in every link. For internal links, descriptive anchors are a strength; repeated exact-match money anchors are a spam pattern only in backlinks.
4. Point more links at the 1 to 3 money pages and at pillars. Link from "power pages" (most impressions or most backlinks in Search Statistics Content Performance or a backlink tool) to pages you want to lift.
5. Keep important pages within about 3 clicks of the homepage. Click depth matters; URL folder depth does not.
6. Internal links stay followed. Remove accidental rel="nofollow" on internal links (Link Assistant flags them). Never use nofollow to "sculpt" PageRank.
7. No fixed counts or ratios. "3 to 5 links per 1,000 words" and internal:external ratios of 80:20 or 70:30 are vendor rules of thumb with no Google basis. Avoid sitewide link stuffing ("50 internal links on every page muddies hierarchy").
8. Every link should help the reader on the page where it sits.
9. Automated keyword auto-linking plugins can create over-optimised anchors at scale: review before enabling.
10. After deleting, merging or moving a page, update internal links to the final URL rather than relying on redirects.
11. Multilingual sites: link to same-language pages.
12. Breadcrumbs add hierarchical links and BreadcrumbList markup (General Settings > Breadcrumbs).

Orphan pages:
- Find: Link Assistant > Orphaned Posts (crawl-based); also Ahrefs or Screaming Frog crawls cross-checked with the sitemap. New posts start as orphans.
- Intentional orphans (PPC and campaign landing pages) are fine; noindex them if not wanted in search.
- Unwanted orphans: test pages (delete, redirect if they have traffic), defunct products (redirect to the closest product or category), weak pages (merge, then redirect), good pages (link them in).

AIOSEO workflow, one line each:
- Site view: AIOSEO > Link Assistant > Links Report > Linking Opportunities > click a post > Add Link, or Bulk Actions > Add Links. Edit the suggested anchor first.
- Editor view: AIOSEO Settings > Link Assistant > Link Suggestions. The posts describe the Inbound and Outbound labels in opposite ways; check in the live UI which direction each list adds before bulk-applying.
- Cornerstone first: mark the pillar, open its Link Assistant tab, apply inbound suggestions from supporting posts.
- Domains Report: review every external domain you link to; fix broken or low-quality targets; set rel="sponsored" on affiliate links in bulk.
- Manual fallback: `site:example.com "topic"` to find pages that mention a topic without linking.
- Cadence: monthly Link Assistant review; 15 minutes a day or week for large backlogs.

Sources: https://aioseo.com/internal-linking-best-practices/, https://aioseo.com/internal-links/, https://aioseo.com/how-to-use-link-assistant-to-optimize-your-internal-linking-strategy/, https://aioseo.com/how-to-easily-find-and-fix-orphan-pages-in-wordpress/, https://aioseo.com/how-to-create-cornerstone-content-in-wordpress/, https://aioseo.com/what-is-anchor-text-and-how-does-it-impact-seo/, https://aioseo.com/ways-link-assistant-can-save-you-time-on-internal-and-external-link-building/, https://aioseo.com/how-to-find-internal-links/

## E-E-A-T and Author SEO

What it is: Experience, Expertise, Authoritativeness, Trust, from Google's Search Quality Rater Guidelines ("Experience" added December 2022). Trust is the most important part. Raters do not change rankings; their ratings help Google evaluate its systems. It is not a ranking factor, and author markup is not a guaranteed signal. Posts that say E-E-A-T is "proven to impact rankings" or that Author SEO makes you "rank higher" overstate it; the vendor's own /keyword-research/ post says Author SEO confers nothing if the author lacks real experience.

Signals to build, by group:

| Group | What to do |
|---|---|
| Author | Named human author on every article, bio with relevant credentials and hands-on experience, author archive page, links to verifiable profiles (LinkedIn, bar directory, professional register) |
| Site | Detailed About and Contact pages, Organization or Person identity (Search Appearance > Global Settings > Knowledge Graph), consistent social profiles |
| Content | Original photos, screenshots, data; first-person detail where true; cited primary sources; visible published and updated dates |
| Trust | HTTPS, privacy policy, affiliate and sponsor disclosures, editorial policy, real third-party reviews, transparent pricing and refunds |

Author SEO in AIOSEO (Plus and above per 2026 posts; verify tier), one line each:
- Enable at All in One SEO > Users (Author SEO), then fill each user's profile: bio and short excerpt, "Knows about" topics, job title, employer, education, awards, languages, social profiles, photo.
- Output: Person markup on the author, a hyperlinked "Written by" byline, Author Bio block (after the conclusion; compact or full), Reviewer block for a fact-checker byline (the reviewer needs a profile).
- Author archives: keep them indexable (Search Appearance > Taxonomies or Archives), give them a real title and description, show the bio there.

Decision rules:
- Never use a generic "admin" byline. Every author needs a complete profile.
- Never add credentials, photos or reviewers that are not real and verifiable. No AI-generated author photos or personas.
- Bios: 100 to 200 words, third person, relevant credentials and awards (not all of them), professional photo, a little personality. Keywords in bios do nothing for ranking.
- YMYL (health, finance, legal, safety): every informational page names a credentialed writer or reviewer; individual bio pages for each professional; link to an external register for verification. Healthcare: no dosage advice or diagnostic statements, plain language, structure as what it is, who it is for, what to expect, when to seek care; an SEO score is not an accuracy check. Legal: follow state bar advertising rules (no guarantees, superlatives or unverifiable results).
- Reviews and comparisons: show you used the product (photos, test results, video). Embedding your own YouTube review gives the content two chances to appear (vendor tip).
- Testimonials, media mentions, community involvement and a Google Business Profile support trust for local businesses.
- Author schema helps Google attribute content; Google accepts `sameAs` profile links. It is optional, not a ranking requirement.

Sources: https://aioseo.com/eeat-seo/, https://aioseo.com/eeat-and-ymyl/, https://aioseo.com/what-is-google-eat/, https://aioseo.com/how-to-boost-your-author-seo-in-wordpress/, https://aioseo.com/how-to-write-an-author-bio-that-boosts-your-google-e-e-a-t-signals/, https://aioseo.com/healthcare-seo/, https://aioseo.com/law-firm-seo/, https://aioseo.com/how-to-add-author-schema-in-wordpress/

## Content audits

A content audit gives each URL a verdict (keep, update, merge, remove). It differs from a content inventory (a list) and an SEO audit (crawl, index, speed; run after migrations, redesigns and traffic drops).

Seven steps (/how-to-do-a-content-audit-for-seo/, 2026-10-09):
1. Goal and scope: traffic, conversions, cleanup before a redesign, or AI-search readiness. Full, partial or sample. With hundreds of posts, start partial.
2. Inventory: export URLs from /sitemap.xml (AIOSEO has one sitemap per content type) or Posts > All Posts. Columns: URL, title, type, published, last updated, focus keyphrase, clicks (12 months), impressions (12 months), average position, answer-ready (yes or no), verdict.
3. Performance data: Search Statistics > Content Rankings with a 12-month range, sorted by drop, then Keyword Rankings (Elite). Without Elite: GSC Performance > Search results, 12 months, add average position, Pages tab, export; compare the last 6 months with the previous 6.
4. Triage:
   - Clear winners: top 20% by clicks with steady traffic. Keep, light check only.
   - Clear zeros: under 100 impressions in 12 months. Candidates to merge or remove (raise the cut-off on large sites). About a minute each.
   - Middle: everything else. Prioritise positions 4 to 20, declining pages and high impressions with low clicks. 10 to 15 minutes each.
   - Exclude anything published in the last 3 months.
   - Example from the post: a 300-post blog splits into about 60 winners, 90 zeros and 150 middle pages. Work in batches of 10 (about 2 hours); start with the top 30.
5. Quality review (up to about 30 minutes per page): outdated facts and screenshots, thin sections, intent mismatch against the current SERP, broken links, missing internal links, weak title or description (high impressions plus low clicks is a title problem). TruSEO gives a quick check; the SEOBoost Content Audit compares a page with top results (separate subscription).
6. Answer readiness (about 15 minutes per page): main answer in the first 2 to 3 sentences, question headings, self-contained sections, accurate updated date, valid Article markup. llms.txt and spot checks in AI tools are covered in playbook-ai-search.md.
7. Verdicts and priority: quick wins (positions 4 to 20 with impressions) first, then slipping top performers, then merges, then removals. Measure after 4 to 8 weeks in Content Rankings or GSC.

Throughput: Content Science estimates 6 to 12 pages reviewed per hour (vendor-cited). Cadence: full audit yearly, partial quarterly, more often for fast publishers or after a core update drop.

Sources: https://aioseo.com/how-to-do-a-content-audit-for-seo/, https://aioseo.com/content-pruning-seo/, https://aioseo.com/how-to-optimize-existing-content-for-seo/, https://aioseo.com/content-optimization-strategy/, https://aioseo.com/seo-audit/, https://aioseo.com/how-to-check-blog-stats/

## Refresh, pruning and consolidation

Decision table:

| Signals | Verdict | Action | AIOSEO feature |
|---|---|---|---|
| Steady traffic, links, accurate, answers the query | Keep | Light check | Search Statistics |
| Relevant but outdated, slipping or weak | Refresh | Update facts, structure, title, links | TruSEO, Link Assistant |
| Several pages on one intent | Consolidate | Merge into the strongest URL, 301 the rest, update internal links | Redirects |
| No traffic, no links, off-topic or obsolete | Remove | 301 to the closest relevant page; if none, 404 or 410 | Redirects |
| Needed by users but not in search (thank-you, campaign) | Noindex | Robots Setting > No Index | AIOSEO Settings > Advanced |

Thresholds and guards (/content-pruning-seo/, 2026-05-12, author rules):
- Under 100 clicks in 12 months means review, not automatic deletion.
- 15 or more referring domains: never hard-delete; refresh or merge and redirect.
- Only prune content older than 6 to 12 months.
- Check backlinks before removing anything; redirect rather than 404 when a relevant target exists. Do not redirect everything to the homepage (Google treats that as a soft 404).
- Prune in batches, log every decision, check the sitemap after, monitor 4 to 12 weeks.
- When unsure, refresh.
- Cadence: every 6 to 12 months, 3 to 6 for frequent publishers, and after core-update drops.

Why prune: quality and relevance. Large sections of unhelpful content (old forums, off-topic legacy posts) can weigh on how a site is perceived. "Prune to save crawl budget" applies only to very large sites (the post concedes 1,000+ pages; Google's crawl-budget guidance targets far larger sites). "40% bad pages drag the rest down" is a simplification. Google does not ask you to delete content for age alone.

Refresh checklist:
1. Re-read the current SERP: has intent or format changed? If the page now ranks for a different term than planned, consider retargeting.
2. Update facts, statistics, screenshots, prices, steps; remove anything stale.
3. Add what the page lacks: a direct answer up top, missing subtopics from PAA and GSC queries, a table, a FAQ section if users need it.
4. Rewrite the SEO title and meta description if CTR is weak; remove stale years from titles.
5. Fix broken links (Broken Link Checker, separate plugin) and add new internal links in both directions (Link Assistant).
6. Expand keyword coverage with "Get Additional Keyphrases" only where the intent fits.
7. Dates: keep the original publish date; change the modified date only for meaningful changes (several posts agree). Never bump dates without real edits; Google's guidance is to show dates honestly. "Updated date gives a rankings boost" and "freshness is a confirmed ranking factor" are overstated.
8. Promote the refreshed page (email, social, outreach to sites that link to outdated competitors).
9. Annotate the change in SEO Revisions and compare after 4 to 8 weeks.
IndexNow tells Bing and other participating engines about the update; it does nothing for Google, so rely on internal links and the sitemap there.

Consolidation steps: pick the URL with the most links and traffic, merge the best unique content from the others into it, 301 each old URL to it (AIOSEO > Redirects, or bulk CSV under Import/Export), update internal links, remove the old URLs from menus, and watch GSC for the merged queries. Vendor anecdote: three AIOSEO posts on "best WordPress SEO plugins" merged into one reached page 1 within 6 weeks (vendor claim).

Recovery after a site-wide quality drop (helpful-content style): audit, then remove or substantially improve thin, duplicate or search-first pages; fix UX; gather user feedback; diversify traffic; expect months, not weeks. Pruning 20% to 30% of posts improved rankings in one vendor anecdote (vendor claim).

Sources: https://aioseo.com/content-pruning-seo/, https://aioseo.com/how-to-stop-content-decay-and-regain-lost-traffic/, https://aioseo.com/duplicate-content/, https://aioseo.com/how-to-do-a-content-audit-for-seo/, https://aioseo.com/helpful-content-update/, https://aioseo.com/seo-tips/, https://aioseo.com/nonprofit-seo/, https://aioseo.com/seo-advice/

## Content decay

Definition: a gradual loss of impressions, clicks or position on a page that used to perform, usually over about 6 months, typically on posts 12+ months old that have not been updated while competitors published newer or deeper pages. A sudden cliff is not decay: check indexability, technical errors, manual actions and algorithm update dates first (playbook-monitoring-growth.md).

Causes: freshness expectations for the query, competitor velocity, changed intent or SERP layout (including AI Overviews taking clicks), lost links, relevance loss.

Signals and where to see them:

| Signal | Report |
|---|---|
| Impressions sliding over months | Search Statistics > SEO Statistics > Content Performance > Top Losing, Diff column |
| Proprietary decay score | Search Statistics > Content Rankings: Loss, Drop %, Performance Score, Last Updated On (Elite); sorted by largest loss by default |
| CTR falling at a steady position | Keyword Rankings, Average CTR (stale title or description, or a new SERP feature) |
| Losing one high-value keyword | Keyword Rankings > Top Losing |
| Not indexed any more | Search Statistics > Index Status, GSC URL Inspection |
| Without Elite | GSC Performance, compare the last 6 months with the previous 6, Pages tab, then the page's queries |

Fix order: refresh pages ranking 4 to 20 (some posts say 8 to 15 or 11 to 20) with real impressions first, then high-impression low-CTR pages (title and description), then slipping former top performers, then consolidation, then removal. Use the refresh checklist above.

Cadence: audit top content every 6 to 12 months, quarterly for fast-moving or AI-exposed topics, and refresh anything older than a year that still matters. Posts disagree (yearly, 6 to 12 months, 3 to 6 months); scale it to how fast the topic changes. Judge results after 4 to 8 weeks, and annotate each refresh in SEO Revisions.

"Content refresh is often the highest-ROI activity in SEO" is vendor opinion, though consistent across the posts.

Sources: https://aioseo.com/how-to-stop-content-decay-and-regain-lost-traffic/, https://aioseo.com/how-to-easily-monitor-seo-rankings-in-wordpress/, https://aioseo.com/how-to-check-blog-stats/, https://aioseo.com/content-pruning-seo/, https://aioseo.com/search-statistics-power-hacks-to-help-boost-your-rankings/, https://aioseo.com/how-to-use-seo-data-to-boost-search-rankings/, https://aioseo.com/website-authority/
