# AI search playbook: AI Overviews, AI Mode, chat assistants, llms.txt and AI crawlers

Scope: how to make a WordPress site running AIOSEO Elite visible and citable in Google AI Overviews and AI Mode, ChatGPT search, Perplexity, Claude, Microsoft Copilot, Gemini and Grok; how to set AI crawler policy; what llms.txt does and does not do; how to use AIOSEO's AI features, AI Insights and MCP server safely; and how to measure AI visibility. It is merged from the aioseo.com blog notes (posts dated 2023 to October 2026) and checked against what Google, Bing, OpenAI, Anthropic and Perplexity document. Every statement is marked as documented (by the platform named) or as a vendor claim. Feature settings and click paths live in ai-mcp.md, api-automation.md and sitemaps-robots-indexing.md; this file names the feature and its menu path in one line and moves on. UI labels change between AIOSEO versions, so confirm a path on the live site before giving it as fact.

## Contents

- Ground rules: documented facts vs vendor claims
- Google AI Overviews and AI Mode: eligibility
- Getting cited by ChatGPT, Perplexity, Claude, Copilot, Gemini and Grok
- Writing for extraction (GEO and AEO practices)
- Entity consistency and off-site mentions
- Structured data in an AI-search context
- Freshness without faking it
- llms.txt and llms-full.txt
- AI crawlers and robots.txt policy
- Snippet controls, noindex and the reported AI Overviews opt-out
- AIOSEO AI writing features: safe use
- AI Insights (brand visibility research)
- AIOSEO MCP server (high level)
- Measuring AI visibility
- Vendor-reported 2026 Google changes (verify before use)
- Vendor statistics register
- Conflicts between posts

## Ground rules: documented facts vs vendor claims

Marker convention used below:
- **Documented (Google)**, **Documented (OpenAI)** and so on: stated in that platform's own documentation or by a named spokesperson.
- **(vendor claim)**: stated by an aioseo.com post with no primary source. The post and date are given.
- **Verify**: plausible but not confirmed; check the platform's current docs before advising a client.

Decision rules:
1. Classic SEO is the foundation for AI search. Documented (Google): AI Overviews and AI Mode draw on the same index and ranking systems as Search; a page must be indexed and eligible to show a snippet to be used as a supporting link. There is no separate "AI index" to submit to.
2. Documented (Google): no special markup, file, schema type or "AI optimisation" is required for AI features. Anything sold as an AI-specific lever (llms.txt, FAQ schema for citations, "AI-ready" scores) is at best general quality hygiene.
3. GEO (generative engine optimisation) and AEO (answer engine optimisation) are vendor and industry labels, not Google concepts. Treat them as "write clear, well-structured, authoritative pages that are easy to quote", which is also good SEO.
4. Correlation studies (schema pages cited more, brand mentions correlate with citations) do not show cause. Never promise a citation. The Sept 2026 AIOSEO llms.txt post and the 2026 keyword-mapping post both say no tactic guarantees a citation.
5. Engagement metrics are diagnostics. Do not tell a client that dwell time, bounce rate or CTR "signal" AI engines or Google to rank them higher.

Sources: https://aioseo.com/llms-txt-vs-robots-txt-vs-xml-sitemap/, https://aioseo.com/how-to-get-cited-by-ai-search-tools/, https://aioseo.com/how-to-rank-in-googles-ai-overviews/, https://aioseo.com/keyword-mapping/, https://aioseo.com/generative-engine-optimization-geo/, https://aioseo.com/what-is-answer-engine-optimization/

## Google AI Overviews and AI Mode: eligibility

Documented (Google):
- A page can appear as a link in AI Overviews or AI Mode only if it is indexed and eligible for a snippet. The usual crawl and index checks apply: not blocked in robots.txt for Googlebot, no `noindex`, returns 200, content renders without needing user interaction.
- AI Mode and AI Overviews may use "query fan-out": the system issues several related sub-queries and assembles an answer from many pages. A site where each subtopic has one clear page with descriptive internal links gives the system more good candidates (the 2026 keyword-mapping post makes the same point and states it does not guarantee citation).
- Structured data is used for understanding only when it matches visible content.
- Controls that apply: `noindex` (removes from Search, including AI features), `nosnippet`, `data-nosnippet` and `max-snippet` (limit what text Google may show or use). `Google-Extended` does not affect Search or AI Overviews (see the crawler section).

Checklist for a page you want considered:
1. Indexed: Search Statistics > Index Status shows "Indexed" (Elite), or GSC URL Inspection.
2. No accidental `nosnippet` or very small `max-snippet` on money pages (AIOSEO Settings > Advanced > Robots Setting on the page; global robots meta in Search Appearance > Advanced).
3. The question the page answers is answered in plain text near the top, not only in an image, accordion that needs a click, or PDF.
4. Author, date and sources are visible (see Author SEO in playbook-keywords-content.md).
5. The page ranks or is close to ranking organically for the core query. AIOSEO's own posts say traditional SEO comes first; vendor posts disagree on how often AI sources sit outside the top 10 (see the statistics register).

Vendor advice restated correctly:
- "Optimise for SGE" (2025-03 post) is outdated naming: SGE became AI Overviews (2024) and AI Mode launched in 2025. The 86.83% SGE coverage figure from that post is not credible as stated.
- "Grade 6-8 reading level, active voice, 1-3 sentence paragraphs" for AI Overviews (2025-08 post) is a readability habit, not a Google requirement.
- "Google prioritises time on page" and "penalises slow sites" (GEO post, 2025-02) are not supported. Page experience is a minor signal.
- Timelines such as "Google AIO picks up new pages in 4-8 weeks" (vendor claim, how-to-get-cited-by-ai-search-tools, 2026-06-25) are anecdotal. Indexing time varies.

Sources: https://aioseo.com/how-to-rank-in-googles-ai-overviews/, https://aioseo.com/optimizing-for-google-sge/, https://aioseo.com/generative-engine-optimization-geo/, https://aioseo.com/keyword-mapping/, https://aioseo.com/how-to-get-cited-by-ai-search-tools/, https://aioseo.com/googles-ai-search-overhaul/

## Getting cited by ChatGPT, Perplexity, Claude, Copilot, Gemini and Grok

Platform table. "Index source" is what the platform or vendor says it uses to find pages.

| Platform | Index source | What to do | Status of the claim |
|---|---|---|---|
| Google AI Overviews / AI Mode | Google Search index (Googlebot) | Normal Google SEO; keep pages snippet-eligible | Documented (Google) |
| Gemini app | Google index plus Gemini grounding | Normal Google SEO; Google-Extended governs Gemini training and grounding use, not Search | Documented (Google) for Google-Extended scope |
| ChatGPT search | OpenAI's own crawler (OAI-SearchBot) plus search partners | Allow OAI-SearchBot; be indexed in Bing as well | OAI-SearchBot documented (OpenAI); "ChatGPT uses the Bing index" is a vendor claim (how-to-get-cited-by-ai-search-tools, 2026-06-25), partly true, verify |
| Microsoft Copilot | Bing index (Bingbot) | Verify the site in Bing Webmaster Tools, submit the sitemap, use IndexNow | Bing dependency documented (Microsoft) |
| Perplexity | Its own crawler (PerplexityBot) | Allow PerplexityBot; it is said to crawl within days | Crawler documented (Perplexity); speed is a vendor claim |
| Claude (web search) | Anthropic's crawlers plus a search provider | Allow Claude-SearchBot and Claude-User if you want to be fetched and cited | Crawler names documented (Anthropic); verify current list |
| Grok | Live web plus X posts, weights freshness | Keep an X presence if the audience uses it | (vendor claim, how-to-get-cited-by-ai-search-tools, 2026-06-25) |

Five-step fix list (merged from the vendor's "5 fixes" and "12 tips" posts, restated):
1. **Access.** Make sure the search and user-fetch crawlers you want are not blocked (see the crawler table). Tools > Robots.txt Editor shows the live rules; server logs show whether GPTBot, OAI-SearchBot, PerplexityBot or ClaudeBot actually fetch pages.
2. **Index coverage outside Google.** Verify in Bing Webmaster Tools (import from GSC), submit `/sitemap.xml`, and keep IndexNow on (activate in Feature Manager > IndexNow; the API key is shown under General Settings > Webmaster Tools). IndexNow helps Bing, Yandex and other participants only; Google does not use it.
3. **Extractable pages.** Answer-first sections, question headings, self-contained passages (next section).
4. **Entity and off-site consensus.** Consistent facts about the brand across your site, profiles and third-party sites (section after next).
5. **Optional extras.** llms.txt (low cost, unproven) and accurate structured data (helps understanding, no citation guarantee).

Things the posts say that need restating:
- "No paid placement in ChatGPT, Perplexity or AI Overviews as of 2026" (vendor claim, 2026-06-25). Treat as a dated observation; ad products in AI answers are changing.
- "Backlinks are used by AI engines as a signal" (2025-08 post) is asserted, not shown. Links still matter for classic ranking, which feeds Google's AI features.
- Do not buy or fake citations, reviews or forum mentions. The vendor reports (unverified) a May 2026 Google spam policy on manipulating AI results; regardless of that report, fake reviews and paid undisclosed links already violate Google spam policies and platform rules.

Sources: https://aioseo.com/how-to-get-cited-by-ai-search-tools/, https://aioseo.com/how-to-rank-in-googles-ai-overviews/, https://aioseo.com/what-is-indexnow-for-seo/, https://aioseo.com/how-to-submit-a-sitemap-to-bing-wordpress-tutorial/, https://aioseo.com/google-june-2026-spam-update/, https://aioseo.com/ecommerce-seo-trends/

## Writing for extraction (GEO and AEO practices)

These practices recur across the GEO, AEO, AI Overviews, featured-snippet and content-audit posts. They are good writing for readers and for snippets. None is a documented AI ranking factor.

Page-level rules:
1. **Answer first.** Put the direct answer to the page's main question in the first 2-3 sentences. For each major H2, open with a short direct answer (the vendor uses 40-60 words; treat the number as a habit, not a rule), then detail, then context (inverted pyramid).
2. **Descriptive or question headings.** "How long does a deck stain last?" beats "Overview". Use People Also Ask, autocomplete, support emails and sales questions as heading sources.
3. **Self-contained sections.** Each section should make sense if quoted alone: name the subject instead of "it", define terms where used, keep one idea per section.
4. **Structure that survives extraction.** Numbered steps for processes, tables for comparisons and specifications, short paragraphs, bold key definitions sparingly. A summary or key points block at the top helps scanning readers.
5. **Specific, checkable facts.** Prices, dimensions, dates, named sources, first-hand results. Cite primary sources. Original data, photos and test results are what other sites and AI answers quote.
6. **Show who wrote it and why they know.** Visible byline, credentials, reviewer for YMYL topics, About and contact pages (AIOSEO Author SEO: All in One SEO > Users or Search Appearance > Author SEO, verify path).
7. **Long-tail and conversational queries.** Full-sentence questions from customers are good section topics. Do not create a thin page per question; group them under the page that owns the topic (keyword mapping).
8. **Topic clusters.** One owner page per subtopic, linked from a pillar (Cornerstone Content toggle in the post's AIOSEO settings; Link Assistant > Links Report for link suggestions).

Content-audit "AI readiness" check (from the October 2026 content-audit post, about 15 minutes per page, restated):
- Main answer in the first 2-3 sentences.
- Question-based or descriptive headings.
- Self-contained sections.
- Updated date accurate and matching real changes.
- Schema present and matching visible content (Article by default; FAQPage only if there is a real visible FAQ, and expect no rich result).
- Spot-check the target questions in ChatGPT, Perplexity and Google AI features; record who is cited and what they do that you do not.

Weak or wrong advice to drop:
- "Bucket brigade" phrases as chunk markers (2024 post): no evidence.
- "LSI keywords" or "semantic keywords" lists: use related subtopics, entities and questions found in the results and in real customer language.
- Word-count targets for AI visibility: none exist.
- "Use AI tools to generate entire articles" (GEO post, 2025-02): conflicts with the vendor's own later posts and with Google's scaled content abuse policy unless each page gets substantial human work.

Sources: https://aioseo.com/what-is-answer-engine-optimization/, https://aioseo.com/how-to-do-a-content-audit-for-seo/, https://aioseo.com/how-to-get-featured-snippets-on-google/, https://aioseo.com/generative-engine-optimization-geo/, https://aioseo.com/optimizing-for-google-sge/, https://aioseo.com/keyword-mapping/, https://aioseo.com/ai-in-seo/, https://aioseo.com/how-to-rank-in-googles-ai-overviews/

## Entity consistency and off-site mentions

Why: AI answers often summarise what many sources say about a brand. Consistent, verifiable facts make it easier for any system to describe you correctly. This is the documented basis of Knowledge Graph and local search; the link to AI citation is inferred.

Checklist:
1. **One set of facts.** Business name, address, phone, founding date, founders, product names, prices and service areas identical on the site, Google Business Profile, Bing Places, Apple Business Connect, LinkedIn, Crunchbase, industry directories and review sites.
2. **Site identity markup.** Organization or Person in Search Appearance > Global Settings > Knowledge Graph; social profile URLs in Social Networks > Social Profiles (output as `sameAs`). Local businesses: Local SEO > Locations.
3. **Author entities.** Every author has a full profile with verifiable external profiles (Author SEO). Do not invent credentials.
4. **Third-party presence.** The vendor recommends Reddit, Quora, niche forums, LinkedIn, industry publications and review sites (G2, Capterra, Product Hunt). Participate honestly and disclose affiliation. Never seed fake threads or reviews.
5. **Unlinked mentions count as context.** The vendor names an Ahrefs study (2025) finding brand mentions had the strongest correlation with AI Overview citations (vendor claim citing Ahrefs, how-to-rank-in-googles-ai-overviews and seo-for-startups, 2025). Correlational; useful as a reason to do digital PR, not proof of a mechanism.
6. **Monitor the brand.** Google Alerts for `"Brand" -site:yourdomain.com`; AI Insights Keyword Reports for how assistants describe the category (see below).

Sources: https://aioseo.com/how-to-rank-in-googles-ai-overviews/, https://aioseo.com/how-to-get-cited-by-ai-search-tools/, https://aioseo.com/seo-for-startups/, https://aioseo.com/what-is-google-knowledge-graph/, https://aioseo.com/seo-reputation-management/, https://aioseo.com/google-alerts-for-seo/

## Structured data in an AI-search context

Documented (Google):
- Structured data helps Google understand a page and makes it eligible for specific rich results. It is not required for AI features and does not guarantee inclusion.
- Markup must describe content visible on the page. Hidden content marked up (for example an FAQ block with its visibility toggled off) violates the structured data guidelines.
- HowTo rich results were removed in 2023. FAQ rich results were restricted in August 2023 to well-known government and health sites and stopped showing for all sites on 7 May 2026. FAQPage markup may still be parsed, but it produces no SERP feature.

Vendor claims to treat with care:
- "Pages with structured data are cited 3.2x more" and "FAQ schema correlates with 28-40% higher citation probability" (vendor claim, unnamed research, how-to-get-cited-by-ai-search-tools, 2026-06-25). Correlational.
- "FAQPage is one of the most frequently cited schema types in AI Overviews" (vendor claim, restaurant-seo, 2026-07-01). Unsourced.
- The 2026-06 cited-by-AI post recommends Article, FAQPage and HowTo. Restated: keep Article (AIOSEO default on posts), Product, Recipe, Event, LocalBusiness, Organization and Person where they match the page. Add FAQPage only where a genuine visible FAQ exists, for consistency of markup, expecting no rich result. Skip HowTo markup for SERP purposes.

AIOSEO: Schema Generator in the post's AIOSEO Settings > Schema tab; AI Schema tab inside Generate Schema proposes types (credits); always validate with the Rich Results Test or validator.schema.org before publishing. Details: schema-local-social.md.

Sources: https://aioseo.com/how-to-create-custom-schema-markup-in-wordpress/, https://aioseo.com/how-to-get-cited-by-ai-search-tools/, https://aioseo.com/restaurant-seo/, https://aioseo.com/rank-math-vs-yoast/, https://aioseo.com/seo-advice/, https://aioseo.com/types-of-schema-markup/

## Freshness without faking it

Rules:
1. Update when facts change (prices, specifications, laws, screenshots, statistics) and when the results show a newer, better answer. Freshness matters most for queries that need current information.
2. Change the visible "updated" date and `dateModified` only after a substantive edit. Keep dates consistent across the page, Article schema and the sitemap `lastmod` (AIOSEO handles schema and sitemap automatically from the post's modified date).
3. Use AIOSEO's Limit Modified Date option (post editor, also in supported page builders) for typo fixes so the date does not bump.
4. Avoid auto-updating years in titles (Current Year smart tag) unless the content is reviewed each year.
5. Review cadence: quarterly for fast-moving or AI-sensitive topics, 6-12 months for evergreen pages (vendor guidance, several posts).

Restated vendor claims: "content freshness is an important ranking factor revealed in the leaked documents" (AEO post, 2025-08; AIO post, 2025-08) and "even small updates help" are not confirmed. The 2024 leak shows attributes exist, not how they are weighted. Timestamp-only edits are a form of fake freshness; do not make them.

Sources: https://aioseo.com/what-is-answer-engine-optimization/, https://aioseo.com/how-to-rank-in-googles-ai-overviews/, https://aioseo.com/google-search-algorithm-leak/, https://aioseo.com/how-to-stop-content-decay-and-regain-lost-traffic/, https://aioseo.com/how-to-do-a-content-audit-for-seo/

## llms.txt and llms-full.txt

What it is:
- llms.txt is a 2024 proposal (Jeremy Howard) for a Markdown file at the site root that lists a site's key pages for language-model agents: `# Site name`, `> one-line summary`, `## Section`, `- [Title](url): note`. llms-full.txt is a companion that inlines page content as Markdown.
- It is not a web standard and has no allow or deny semantics. It cannot block or permit any crawler. Access control is robots.txt (and server rules).

What platforms say:
- Documented (Google): Google does not use llms.txt for Search or AI features (Gary Illyes, 2025). No major AI search provider has documented using it to select or rank citations. Verify for any specific vendor before claiming support.
- AIOSEO's own Sept 2026 comparison post states: no ranking effect, does not guarantee AI tools read or cite you, "curation, not a dump of every URL". Use that wording; it supersedes the 2025 posts that called it a "VIP pass", said it improves AI Overviews, or (llms-full.txt post, 2025-12) that it can hold Allow rules.

Decision rule:
- Cost is near zero with AIOSEO, risk is near zero if the file lists only public, indexable pages. Turn it on, curate it, and do not spend more time on it than that. Do not report it to a client as a visibility lever.
- Include: cornerstone pages, product and category pages, buying guides, documentation, About and contact. Exclude: utility pages (cart, account, thank-you), thin tag archives, noindexed or private content.
- Do not put anything in llms-full.txt that you would not publish on the page itself (it is public Markdown of your content and easy to scrape).

AIOSEO: All in One SEO > Sitemaps > LLMs.txt (toggle, per post type and taxonomy include/exclude, Open llms.txt button; one 2025 post gave the path as General Settings > llms.txt, verify). Per Sept 2026 posts llms-full.txt and the Markdown conversion options are Pro only; check on the live site. Hooks for developers: developer-hooks.md.

Conflict noted: the Dec 2025 post defines llms.txt as recent content and llms-full.txt as all content; the Sept 2026 post defines llms.txt as curated links and llms-full.txt as comprehensive. Inspect the generated files on the live site rather than relying on either description.

Sources: https://aioseo.com/llms-txt-vs-robots-txt-vs-xml-sitemap/, https://aioseo.com/what-is-llms-txt/, https://aioseo.com/what-is-llms-full-txt/, https://aioseo.com/best-llms-txt-generators/, https://aioseo.com/restaurant-seo/, https://aioseo.com/seo-reputation-management/, https://aioseo.com/how-to-get-cited-by-ai-search-tools/

## AI crawlers and robots.txt policy

Principle: AI companies run separate user agents for search indexing, user-initiated fetching and model training. Decide per purpose. Blocking a search or retrieval agent removes you from that assistant's citations; blocking a training agent does not affect Google Search.

| User agent / token | Owner | Purpose | Block it if | Notes |
|---|---|---|---|---|
| Googlebot | Google | Search crawling, including AI Overviews and AI Mode | Never, unless you want out of Google Search | Documented (Google) |
| Google-Extended | Google | robots.txt token (not a separate crawler) controlling use of content for Gemini model training and grounding | You do not want Gemini training or grounding use | Documented (Google): does not affect Search inclusion or AI Overviews |
| Bingbot | Microsoft | Bing search, which grounds Copilot | Never, unless you want out of Bing and Copilot | Bing also offers meta controls for chat use; verify current docs |
| OAI-SearchBot | OpenAI | Indexing for ChatGPT search results | You do not want ChatGPT search citations | Documented (OpenAI) |
| GPTBot | OpenAI | Collecting content for model training | You do not want training use | Documented (OpenAI); blocking it does not remove you from ChatGPT search |
| ChatGPT-User | OpenAI | Fetches a page when a user's request needs it | Rarely | OpenAI states robots.txt may not apply in the same way to user-initiated fetches; verify |
| ClaudeBot | Anthropic | Training data collection | You do not want training use | Documented (Anthropic) |
| Claude-SearchBot | Anthropic | Indexing for search quality in Claude | You do not want Claude search citations | Documented (Anthropic); verify current name list |
| Claude-User | Anthropic | Fetches a page for a user's request | Rarely | Documented (Anthropic) |
| PerplexityBot | Perplexity | Indexing for Perplexity answers (Perplexity says not for training) | You do not want Perplexity citations | Documented (Perplexity) |
| Perplexity-User | Perplexity | User-initiated fetches | Rarely | Perplexity states it generally ignores robots.txt; verify |
| Applebot-Extended | Apple | Token controlling use for Apple model training (Applebot itself crawls for Siri and Spotlight) | You do not want Apple training use | Documented (Apple) |
| CCBot | Common Crawl | Open web crawl used in many training datasets | You do not want inclusion in open training corpora | Documented (Common Crawl) |

Default policy for a business that wants AI visibility:
- Allow: Googlebot, Bingbot, OAI-SearchBot, ChatGPT-User, Claude-SearchBot, Claude-User, PerplexityBot, Perplexity-User.
- Business decision: GPTBot, ClaudeBot, Google-Extended, Applebot-Extended, CCBot. Blocking them limits training use; it has no documented effect on Google Search.
- Paywalled, licensed or sensitive content: block training agents, consider `nosnippet` on specific pages, and use authentication for anything truly private (robots.txt is public and only compliant bots obey it).

Steps:
1. Read the live file: Tools > Robots.txt Editor > Open Robots.txt, or `https://site/robots.txt`.
2. Check AIOSEO's bot blocking: Search Appearance > Advanced > Crawl Cleanup > Unwanted Bots (writes Disallow rules into robots.txt; options to block all unwanted bots or only AI crawlers), and the "Block AI Crawlers" section in the Robots.txt Editor. Verify exactly which user agents the AIOSEO list contains on the installed version; the posts never list them. A one-click "block AI crawlers" can remove the site from ChatGPT, Claude or Perplexity search citations if it includes their search agents.
3. Add explicit groups per user agent. `Allow: /` lines are redundant unless a broader Disallow applies to that agent.
4. Confirm with server logs that allowed agents fetch pages and blocked ones stop. Bad bots ignore robots.txt; use a WAF or server rules for those, and never block Googlebot or Bingbot by accident.
5. Remember robots.txt controls crawling, not indexing. A blocked URL can still be indexed from links, and a crawler cannot see a `noindex` on a page it may not fetch.

Vendor framing to restate: the 2026-06 cited-by-AI post lists Google-Extended among agents to "let in" for AI visibility. Allowing Google-Extended has no effect on AI Overviews or Google Search; it only affects Gemini training and grounding use.

Statistics: "32% of site owners allow AI platforms, 11% block" (vendor claim, seo-statistics, modified 2026-01).

Sources: https://aioseo.com/how-to-get-cited-by-ai-search-tools/, https://aioseo.com/how-to-block-an-unwanted-web-crawler/, https://aioseo.com/how-to-stop-bot-traffic/, https://aioseo.com/how-to-generate-robots-txt-files-in-wordpress/, https://aioseo.com/llms-txt-vs-robots-txt-vs-xml-sitemap/, https://aioseo.com/seopress-review/, https://aioseo.com/seo-statistics/

## Snippet controls, noindex and the reported AI Overviews opt-out

Documented (Google) controls, from most to least drastic:

| Control | Effect on classic results | Effect on AI Overviews / AI Mode | Use when |
|---|---|---|---|
| `noindex` | Page removed from Search | Removed | Page should not be in Google at all |
| `nosnippet` (page) | No text snippet, no featured snippet | Content not used as direct input | Page content must not be quoted |
| `data-nosnippet` (element) | That element excluded from snippets | Excluded | One section (prices for members, legal text) must not be quoted |
| `max-snippet:N` | Snippet limited to N characters | Applies to AI features too | Limit quoting while staying visible |
| Google-Extended Disallow | None | None | Only controls Gemini training and grounding |

AIOSEO: per page in AIOSEO Settings > Advanced > Robots Setting (turn off Use Default Settings; No Index, No Snippet, Max Snippet and related options); site-wide in Search Appearance > Advanced > Global Robots Meta. `data-nosnippet` is an HTML attribute added in content, not an AIOSEO setting.

Reported opt-out toggle (needs verification):
- The vendor reports (opt-out-of-ai-overviews, 2026-07-15) a Search Console setting that removes a whole site from AI Overviews, AI Mode and Discover AI summaries; site-wide only; in limited testing; not a ranking signal; not covering the Gemini app; with page-level controls reportedly required by March 2027.
- Verify in Google's own documentation and in the client's Search Console before advising. Until verified, the documented route is `nosnippet`, `data-nosnippet` or `max-snippet`.
- Vendor advice worth keeping: do not opt out unless content is paywalled, licensed or sensitive, because opting out (or `nosnippet`) also removes featured snippets and normal text snippets, which usually costs clicks.

Sources: https://aioseo.com/opt-out-of-ai-overviews/, https://aioseo.com/googles-ai-search-overhaul/, https://aioseo.com/robots-meta-tags/, https://aioseo.com/noindex-meta-tag/

## AIOSEO AI writing features: safe use

Feature map (one line each; settings in ai-mcp.md):
- **AI Copilot / AI Content tab:** post editor > AIOSEO Settings > AI Copilot (older posts: "AI Content"); SEO titles, meta descriptions, FAQs, key points, social posts, marketing email. Defaults in All in One SEO > AI Suite > AI Content.
- **Optimize with AI (AI Copilot Optimize, 2026-08):** Optimization tab > Content Optimization > Optimize with AI; rewrites title, description, headline and content in one pass, Block Editor only, does not save until you click Update, Revert per item.
- **AI Assistant block:** block "AIOSEO - AI Assistant"; prompt, Generate, Insert; drafts sections, tables, FAQs, translations.
- **AI Schema:** Schema tab > Generate Schema > AI Schema (Smart or prompt-based).
- **Bulk titles and descriptions:** All Posts > Bulk actions > Generate SEO Titles with AI / Generate Meta Descriptions with AI. **Bulk alt text:** Media Library (list view) > Bulk actions > Generate Alt Text for Images with AI.
- **AI Image Generator:** Image block > Generate with AI, Edit with AI, featured image button; model choice GPT Image 2 or Nano Banana 2 (Sept 2026).
- **Writing Assistant:** powered by SEOBoost, needs a separate SEOBoost account (see playbook-keywords-content.md).
- **Credits:** General Settings > License > AI Credits; about 10 credits per text action, image cost varies with quality. Allowances: Lite 100 free credits; paid plans "10,000" (2025 posts) vs Pro 50,000 and Elite 200,000 (Sept 2026 post). Use the figure shown in the live licence screen.

Policy baseline (Documented, Google): content is judged on quality and helpfulness, not on how it was produced. The scaled content abuse policy (March 2024) covers many pages generated mainly to manipulate rankings with little value, whatever the tool. AIOSEO's own posts agree: AI as a co-pilot, never unreviewed long-form publishing.

Safe-use rules:
1. A named human author reviews and edits every AI-assisted page before publishing; add first-hand experience, real examples and data the model cannot know.
2. Fact-check every statistic, date, name, price and quote. Remove anything you cannot source.
3. Never fabricate credentials, author photos, reviews, testimonials, screenshots of real software, infographic data or product images that differ from what customers receive (the vendor's Sept 2026 image post states the same limits).
4. Do not mass-generate near-identical pages (city pages sharing the same 200 words is the vendor's own example of scaled content abuse). Programmatic pages need unique value per page.
5. Bulk titles, descriptions and alt text: generate, then review a sample before applying site-wide; titles and descriptions must stay accurate to the page. Google may rewrite either.
6. Inserted FAQ blocks: keep only genuinely useful Q&As, visible on the page. Expect no FAQ rich result.
7. AI Schema output: validate, and delete any type that describes content not on the page.
8. Do not use paraphrasing or spinning tools to dodge "duplicate content penalties" or to produce guest-post variants (best-ai-paraphrasing-tools, 2025-08): there is no duplicate penalty for normal syndication, and spun link-network content violates spam policy.
9. The yoast-vs-rank-math post pitches "High-Volume AI Content Sites" as a use case. Do not follow.

Sources: https://aioseo.com/how-to-use-ai-blog-post-generator/, https://aioseo.com/how-to-use-wordpress-ai-assistant/, https://aioseo.com/how-to-use-an-ai-content-writer/, https://aioseo.com/gpt-image-2-vs-nano-banana-2/, https://aioseo.com/ai-generated-content/, https://aioseo.com/eeat-seo/, https://aioseo.com/best-ai-paraphrasing-tools/, https://aioseo.com/best-rank-math-alternative/

## AI Insights (brand visibility research)

What it is: a BETA feature in AIOSEO Pro (docs, 2025-12) that runs a query through several AI engines and reports which brands they mention. Path: All in One SEO > AI Suite > Keyword Reports (Brand Tracker tab marked "Coming Soon"). Engines covered per the docs: OpenAI, Claude, Gemini, DeepSeek and Perplexity. The blog notes do not cover it; details in ai-mcp.md.

How to use it:
1. Build a fixed list of 10-30 specific, long-tail category queries that buyers ask ("best dog food for puppies with sensitive stomachs", not "dog food").
2. Run each query; record, per engine, whether the brand appears, its position and which sources the engine cites.
3. Read the cited sources: they show which publications, review sites and forums to earn mentions on, and which competitor pages are being quoted.
4. Re-run the same list on a fixed cadence (monthly) to see change. One run is a sample, not a measurement: answers vary between runs and users.
5. Treat results as research input for content and PR, not as a KPI that maps to traffic.

Limits: results are snapshots of model output for one phrasing; they do not reflect personalisation, location or the consumer apps' exact behaviour. Report "free for a limited time" pricing is vendor wording; check before relying on it.

Sources: https://aioseo.com/how-to-get-cited-by-ai-search-tools/, https://aioseo.com/how-to-rank-in-googles-ai-overviews/

## AIOSEO MCP server (high level)

What it is: AIOSEO registers SEO "abilities" with the WordPress Abilities API; the free MCP Adapter plugin exposes them to AI clients over the Model Context Protocol, so an assistant can read and change SEO data. Path: All in One SEO > AI Suite > MCP (4-step wizard: registered abilities, Install MCP Adapter, Generate Application Password, Test connection). Setup and configuration detail: ai-mcp.md and api-automation.md.

Requirements and scope:
- AIOSEO 4.9.8+ and WordPress 6.9+.
- Abilities by plan (docs): Free 13 (posts, settings, notifications, robots.txt, audits); Pro roughly doubles this (terms, redirects, Search Statistics); Link Assistant adds four. Search Statistics abilities return data only on Elite.
- Clients with ready snippets (docs): Claude Desktop, Claude Code CLI, Gemini CLI, Cursor, VS Code.

Safety rules:
1. The Application Password carries the full capabilities of the WordPress user that created it, not just SEO. Create a dedicated user with the lowest role that can do the job.
2. Treat the password as a credential: not in Git, screenshots, tickets or chat; use environment interpolation in client config.
3. Start read-only: audits, lists of posts missing descriptions, low TruSEO scores, redirect lookups, Search Statistics summaries.
4. Put a human checkpoint before any write with a large blast radius: robots.txt, redirects, bulk metadata, noindex changes. Preview exactly what will change and confirm the target site.
5. An agent's explanation of a traffic drop is a hypothesis, not a diagnosis. Confirm in GSC and on the site.
6. Revoke from the WordPress profile > Application Passwords when a client or contractor no longer needs access.

Conflicts noted: ability count 28 (2026-06-25 post) vs 29 (2026-09-14 post); the docs count by plan instead. The Sept 2026 blog post lists a ChatGPT client tab, but the docs say ChatGPT is not supported directly; use a listed client. The July 2026 plugins post says MCP is free on all plans including Lite; true for the base abilities, while Pro and Elite abilities depend on plan.

Sources: https://aioseo.com/wordpress-mcp/, https://aioseo.com/how-to-get-cited-by-ai-search-tools/, https://aioseo.com/best-seo-plugins-for-wordpress/

## Measuring AI visibility

No platform gives complete AI citation data. Combine several partial sources and keep the method fixed so trends are comparable.

| Source | What it shows | Status |
|---|---|---|
| GSC Performance report | Clicks and impressions from AI Overviews and AI Mode are included in the "Web" search type totals | Documented (Google, 2025). A separate AI Overviews / AI Mode filter added in June 2026 is a vendor claim (googles-ai-search-overhaul, 2026-07-24): verify in the property |
| AIOSEO Search Statistics | GSC data inside WordPress (Elite) | Inherits GSC; whether it exposes any AI segment is not stated in any post, verify |
| GA4 referrals | Sessions from chatgpt.com, perplexity.ai, copilot.microsoft.com, gemini.google.com, claude.ai | Reliable for clicks that carry a referrer; some assistant traffic arrives as direct |
| `utm_source=chatgpt.com` | ChatGPT search appends this to outbound links | Documented (OpenAI); filter on it in GA4 |
| Bing Webmaster Tools | Bing and Copilot visibility; an "AI Performance" dashboard showing cited pages and queries (Feb 2026) | Dashboard is a vendor claim (how-to-get-cited-by-ai-search-tools, 2026-06-25): verify |
| Server logs | Which AI agents fetch which URLs, how often, with what status codes | First-party, reliable for crawl activity, not for citations |
| Prompt sampling | Whether the brand is named or cited for a fixed prompt set | Manual or via AI Insights; noisy, sample repeatedly |
| Third-party trackers | Citation share across engines (vendor names Profound and Amplitude AI Visibility; Ahrefs Brand Radar also exists) | Vendor methodologies differ; compare like with like |

Monthly routine:
1. GA4: AI referral sessions and conversions by landing page, month on month.
2. GSC: clicks, impressions and CTR for the pages and queries you target; watch for rising impressions with falling CTR (a typical AI Overview pattern on informational queries).
3. Logs: confirm allowed AI agents still fetch key pages; look for 4xx/5xx served to them.
4. Prompt set: run the fixed list (AI Insights or manual), record mentions, positions and cited URLs.
5. Act: improve pages that are cited for the wrong facts, refresh pages losing citations to newer sources, pursue mentions on the sites the engines cite most.

KPI rule: report conversions and qualified sessions first. Citations and mentions are leading indicators, not revenue.

Sources: https://aioseo.com/how-to-get-cited-by-ai-search-tools/, https://aioseo.com/googles-ai-search-overhaul/, https://aioseo.com/how-to-do-a-content-audit-for-seo/, https://aioseo.com/generative-engine-optimization-geo/, https://aioseo.com/how-to-rank-in-googles-ai-overviews/

## Vendor-reported 2026 Google changes (verify before use)

Every item below comes from AIOSEO posts dated June to October 2026 with no linked primary source. Check Google's announcements or documentation before repeating any of them to a client.

| Reported change | Post (date) |
|---|---|
| Google I/O on 19 May 2026 made AI Mode the default for over 1 billion monthly users | googles-ai-search-overhaul (2026-07-24) |
| AI Overviews show citations with "Highly Cited" badges; "Preferred Sources" in results | googles-ai-search-overhaul (2026-07-24) (Preferred Sources for Top Stories existed from 2025; the badge claim needs checking) |
| AI Overviews appear on about 48% of queries; position 1 CTR fell from about 27% to about 11%; zero-click above 50% of US searches | googles-ai-search-overhaul (2026-07-24) |
| Search Console added AI Overview and AI Mode segments to the Search Type filter in early June 2026 | googles-ai-search-overhaul (2026-07-24) |
| Search Console opt-out toggle for AI Overviews, AI Mode and Discover AI summaries; page-level controls required by March 2027 | opt-out-of-ai-overviews (2026-07-15) |
| New May 2026 spam policy against manipulating AI search results (buying or faking citations) | google-june-2026-spam-update (2026-07-17) |
| June 2026 spam update rolled out 24 June (noon ET) to 26 June (2 pm ET) | google-june-2026-spam-update (2026-07-17) |
| FAQ rich results fully retired on 7 May 2026 | rank-math-vs-yoast (2026-07-10). Consistent with this skill's baseline: treat as fact |
| Bing Webmaster Tools "AI Performance" dashboard (Feb 2026), the only first-party citation tracker | how-to-get-cited-by-ai-search-tools (2026-06-25) |
| Commercial and local queries still mostly show organic results | googles-ai-search-overhaul (2026-07-24) |
| "Ask Maps" weights review language; public Instagram content indexed from July 2025 | restaurant-seo (2026-07-01) |

Sources: https://aioseo.com/googles-ai-search-overhaul/, https://aioseo.com/opt-out-of-ai-overviews/, https://aioseo.com/google-june-2026-spam-update/, https://aioseo.com/rank-math-vs-yoast/, https://aioseo.com/how-to-get-cited-by-ai-search-tools/, https://aioseo.com/restaurant-seo/

## Vendor statistics register

All "(vendor claim)" unless a measuring party is named. Do not quote these as facts; if a client needs a figure, find the primary study.

| Claim | Who measured, per the post | Post (date) | Note |
|---|---|---|---|
| 60% of AI-cited sources are not in Google's top 10 for the same query | Not named | how-to-get-cited-by-ai-search-tools (2026-06-25) | Conflicts with the next row; platforms and methods differ |
| 52% of AI Overview sources rank in the top 10 | Not named | seo-statistics (modified 2026-01-23) | See above |
| Pages with structured data cited 3.2x more | Not named | how-to-get-cited-by-ai-search-tools (2026-06-25) | Correlational |
| FAQ schema linked to 28-40% higher citation probability | Not named | how-to-get-cited-by-ai-search-tools (2026-06-25) | Correlational; FAQ rich results no longer show |
| Only 11% of domains are cited by both ChatGPT and Perplexity | Not named | how-to-get-cited-by-ai-search-tools (2026-06-25) | Suggests checking engines separately |
| 46.7% of Perplexity's top-cited sources are communities such as Reddit and Quora | Not named | how-to-get-cited-by-ai-search-tools (2026-06-25) | |
| Grok grew from about 2% to about 18% of the US chatbot market (Jan 2025 to Jan 2026) | Not named | how-to-get-cited-by-ai-search-tools (2026-06-25) | |
| Brand mentions show the strongest correlation with AI Overview citations | Ahrefs (2025), named by vendor | how-to-rank-in-googles-ai-overviews (2025-08, modified 2026-04); seo-for-startups (2025-08-28) | Correlational |
| 63% of businesses report positive impact from AI Overviews since May 2024 | Not named | how-to-rank-in-googles-ai-overviews (2025-08, modified 2026-04) | |
| AI Overviews plus a featured snippet take over 75% of a mobile screen | Not named | how-to-rank-in-googles-ai-overviews (2025-08, modified 2026-04) | |
| 60% of searches end without a click because of AI Overviews; AI search traffic +527%; 17.3% of top-20 content is AI-generated | Not named | seo-statistics (modified 2026-01-23) | |
| Google showed SGE for 86.83% of results | Not named | optimizing-for-google-sge (2025-03-06) | Not credible as stated; outdated naming |
| AI Overviews on about 48% of queries; position 1 CTR about 27% to about 11% | Not named | googles-ai-search-overhaul (2026-07-24) | |
| 72% of people researching an attorney use Google and 42% also check an AI tool | Not named | law-firm-seo (2026-07-31) | |

Sources: https://aioseo.com/how-to-get-cited-by-ai-search-tools/, https://aioseo.com/how-to-rank-in-googles-ai-overviews/, https://aioseo.com/seo-statistics/, https://aioseo.com/optimizing-for-google-sge/, https://aioseo.com/googles-ai-search-overhaul/, https://aioseo.com/seo-for-startups/, https://aioseo.com/law-firm-seo/

## Conflicts between posts

One line each, with the answer to use.
- **llms.txt effect:** 2025 posts (what-is-llms-txt, restaurant-seo) say it increases AI citations; Sept 2026 post says no ranking effect and no guarantee. Use the Sept 2026 wording; Google says it does not use the file.
- **llms.txt vs llms-full.txt contents:** Dec 2025 (recent vs all content) vs Sept 2026 (curated links vs comprehensive). Inspect the live files.
- **llms.txt Allow rules:** llms-full.txt post (2025-12) says you can grant crawler permission in it; the format has no such semantics. Use robots.txt.
- **llms.txt path:** Sitemaps > LLMs.txt (most posts) vs General Settings > llms.txt (2025 blog-stats post). Verify on the installed version.
- **Google-Extended:** listed as an agent to allow for AI visibility (2026-06 post); it does not affect Search or AI Overviews.
- **FAQ and HowTo schema:** recommended for AI and snippets in 2025-2026 posts; HowTo rich results gone since 2023 and FAQ rich results gone since 7 May 2026. Keep only visible, useful FAQs.
- **AI-written articles:** GEO post (2025-02) says generate whole drafts; later posts say co-pilot only. Follow the later posts and Google's scaled content abuse policy.
- **MCP:** 28 vs 29 abilities; ChatGPT tab in the blog vs "not supported directly" in the docs. Use the docs.
- **AI credits:** "10,000 on paid plans" (2025) vs Pro 50,000 / Elite 200,000 (Sept 2026). Read the licence screen.
- **AI title generator:** OpenAI API key required (2023 posts) vs built-in credits (June 2025 onward). The OpenAI-key integration was replaced in v4.8.4.

Sources: https://aioseo.com/what-is-llms-txt/, https://aioseo.com/what-is-llms-full-txt/, https://aioseo.com/llms-txt-vs-robots-txt-vs-xml-sitemap/, https://aioseo.com/how-to-get-cited-by-ai-search-tools/, https://aioseo.com/wordpress-mcp/, https://aioseo.com/generative-engine-optimization-geo/, https://aioseo.com/how-to-check-blog-stats/, https://aioseo.com/how-to-use-a-meta-description-generator-in-wordpress/
