# AIOSEO advice versus Google's guidance

AIOSEO's docs, blog, TruSEO checks and SEO Analysis sometimes recommend things Google's documentation does not support, or describe Google features that have since been retired. When they conflict, follow Google and tell the user why in one sentence. This file holds the rules to apply. `blog-google-checks.md` has the full table of 152 corrected blog claims with example posts, and the bracketed notes in each area file cover the docs.

## Contents

- Scores and heuristics
- Crawling and indexing
- Sitemaps and indexing pings
- Structured data and rich results
- Links
- AI search
- Measurement and tools
- Settings where the AIOSEO default or advice should be overridden

## Scores and heuristics

- **TruSEO, the Headline Analyzer, the SEO Analysis score, the Site Audit score and the Writing Assistant grade are plugin heuristics.** None is a Google signal. Use them to find pages worth reading, and stop as soon as a change would make the content worse. Never chase 100: AIOSEO's own blog reports a 60/100 page outranking a 100/100 one.
- **Keyword density** has no target. TruSEO's 0.5 to 3 per 100 words band is useful only as an alarm for stuffing.
- **Keyphrase placement quotas** (in 30 to 75% of subheadings and alt texts, in every heading, in the first 100 words) are not Google requirements. Put the phrase where it reads naturally.
- **Word count** is not a ranking factor. Match the intent and cover what the reader needs.
- **"LSI keywords"** is not something Google uses. Cover the related entities, subtopics and questions instead.
- **Title and description lengths:** Google truncates by pixel width (titles about 600 px) and rewrites both often. 50 to 60 characters and 120 to 155 characters are guides, not rules. Meta descriptions do not affect ranking.
- **Bounce rate, dwell time, CTR and social signals** are not documented ranking levers. Treat them as diagnostics.
- **Multiple H1s** are not a Google problem. One H1 is still the clean choice.
- **The SEO Analysis performance thresholds** (HTML under 50 KB, under 20 requests, 0.2 s response) are dated. Use Core Web Vitals (LCP, INP, CLS; INP replaced FID in March 2024) in PageSpeed Insights and Search Console.

## Crawling and indexing

- **robots.txt controls crawling, not indexing.** A disallowed URL can still be indexed from links, and Google cannot see a noindex on a page it may not crawl. To remove a page, use noindex (and keep it crawlable), a 404 or 410, or a redirect. Never Disallow and noindex the same URLs.
- **Crawl-delay and Clean-param** (offered in AIOSEO's robots.txt editor) are ignored by Google. Clean-param is Yandex only.
- **No Index Paginated:** Google advises leaving paginated pages indexable with self-referencing canonicals. Do not canonicalise page 2 and later to page 1.
- **Mass redirects to the home page** (Advanced 404 Settings, deleted-post redirects left pointing at `/`) are treated as soft 404s. Redirect to the closest relevant page, or return 410 when nothing replaces it. A 410 is not a soft 404.
- **302, 307 and 308 redirects pass signals.** For a permanent move use 301 or 308, because the type tells Google which URL to keep. The vendor claim that a 302 "passes no link equity" is outdated.
- **www versus non-www** is a free choice. HTTPS is the requirement; consistency is what matters.
- **The noarchive directive** no longer has an effect in Google, which removed cached pages in 2024. **noodp** has been obsolete since DMOZ closed in 2017.
- **rel=next/prev** has not been used by Google for indexing since 2019. Bing may still read it.

## Sitemaps and indexing pings

- **priority and changefreq are ignored by Google.** Only an accurate `lastmod` is used. Leave AIOSEO's Priority and Frequency on Default and spend no time on them.
- **The Google sitemap ping endpoint** was retired in 2023. Submit the sitemap in Search Console (AIOSEO's Webmaster Tools connection can sync it) and keep the Sitemap line in robots.txt.
- **IndexNow does not reach Google.** It notifies Bing, Yandex, Seznam, Naver and Yep. It is worth turning on, but it does not speed up Google indexing.
- **A sitemap does not "solve duplicate content".** Canonicals, redirects and consistent internal links do.
- **Google News:** inclusion is automatic for eligible sites. Publisher Center and Newsstand changed in 2024, so the "Newsstand eligibility" benefit the docs mention is out of date. The News sitemap lists articles from the last 2 days.

## Structured data and rich results

- **FAQ rich results stopped appearing for all sites on 7 May 2026** (restricted to government and health sites from August 2023). FAQPage markup is harmless and other engines may read it, but it brings no Google feature. Keep a visible FAQ only when it helps readers.
- **HowTo rich results** were removed in September 2023. HowTo schema brings no Google feature.
- **The sitelinks search box** was removed in November 2024, so the WebSite SearchAction markup does nothing in Google.
- **In June 2025 Google announced it was phasing out several rich result types,** including Book Actions, Course Info, ClaimReview (fact check), Estimated Salary, Learning Video, Special Announcement and Vehicle Listing. The markup stays valid schema.org, but expect no Google feature from it.
- **Markup must describe visible content.** The AIOSEO FAQ block's "Display Block" off setting (content hidden, schema kept) breaks Google's structured data guidelines. Never use it.
- **Self-serving reviews** (a LocalBusiness or Organization reviewing itself, or reviews the owner writes in the Product or Recipe blocks) are not eligible for review snippets and can lead to a manual action. Use only genuine third-party reviews.
- **Schema is not a ranking factor and is not needed for AI Overviews** (Google's guidance on AI features). Use it for accuracy and eligibility.
- **Testing tools:** the Structured Data Testing Tool is retired. Use the Rich Results Test and validator.schema.org.

## Links

- **Linking out does not "leak" ranking value** in any way worth managing. Use `rel="sponsored"` for paid and affiliate links, `rel="ugc"` for user content, and `nofollow` for links you do not vouch for, not according to the target's rank. Since 2019 Google treats all three as hints.
- **Disavow** is for real manual actions or clear link schemes you built, not routine "toxic link" cleanup.
- **Internal link ratios** (80/20 and similar) are not Google rules. Link where it helps the reader, with descriptive anchors.

## AI search

- **Optimising for AI Overviews and AI Mode is ordinary SEO** (Google, 2025 and 2026 guidance): crawlable, indexable, helpful, people-first content. No special markup, file or format is required.
- **llms.txt** is optional. Google has said it does not use it, and no major AI search provider documents relying on it. AIOSEO's llms.txt is harmless; it does not control AI Overviews or citations.
- **Google-Extended** controls the use of content for Gemini training and grounding. It does not affect Google Search, AI Overviews or AI Mode, which follow Googlebot.
- **"All AI Crawlers" also blocks citation bots.** Crawl Cleanup » Unwanted Bots offers individual crawlers and an **All AI Crawlers** option; the docs do not list which user agents it writes. Ticking All AI Crawlers can block the search and retrieval bots that produce citations (OAI-SearchBot, Claude-SearchBot and Claude-User, PerplexityBot) along with the training crawlers. Decide per user agent with the owner, tick only the training crawlers (GPTBot, ClaudeBot, CCBot) or write explicit rules in the Robots.txt Editor, and read `/robots.txt` afterwards to confirm what was written. Turning Crawl Cleanup on also disables most RSS feeds by default (see settings-search-appearance.md), so review the RSS tab in the same change. On Cloudflare, check its own AI bot blocking too: it can block crawlers regardless of robots.txt.
- **The snippet controls** (nosnippet, max-snippet, data-nosnippet) also limit how Google shows content in AI features. Use them knowing that.
- **Vendor AI-citation statistics** (citation lift from FAQ schema, share of citations outside the top 10, and similar) are uncited. Do not repeat them as fact.
- **AI-written content** is acceptable to Google when it is helpful and accurate. Scaled, unedited AI content is spam ("scaled content abuse"). AIOSEO's AI outputs (titles, descriptions, FAQs, schema, alt text) need the same fact-check as the body.

## Measurement and tools

- These Search Console and Google tools have been retired: the URL Parameters tool, the robots.txt Tester (replaced by the robots.txt report), the Mobile-Friendly Test and Mobile Usability report, the preferred-domain setting, Google Optimize, and Universal Analytics (AIOSEO removed its GA integration in 4.5.1).
- Google Search Console is the source of truth for impressions, clicks and indexing. AIOSEO's Search Statistics is a view of the same Performance data with extra decay and rank-tracking analysis.

## Settings where the AIOSEO default or advice should be overridden

| Setting | AIOSEO default or advice | Do instead |
|---|---|---|
| Search Appearance » Advanced » No Index Paginated | Offered as a cleanup | Leave it off |
| Sitemap Priority and Frequency | Tunable per post and type | Leave on Default |
| Redirects » Advanced 404 Settings | Available, with AIOSEO's own warning | Leave off; build a helpful 404 page |
| Monitor Trashed & Deleted Posts | Creates a disabled redirect to `/` | Point each one at the closest relevant page, or use 410, before enabling it |
| FAQ block » Display Block off | "Hide from visitors, keep schema" | Never hide marked-up content |
| Robots.txt Editor Crawl-delay and Clean-param | Offered | Not for Google; skip unless a non-Google engine needs them |
| Crawl Cleanup » Unwanted Bots » All AI Crawlers | One option that covers every AI bot | Tick only the bots the owner's policy blocks (usually training crawlers), then read `/robots.txt` |
| Image SEO alt text format (for example `%image_title% | %site_title%`) | Template-generated alt | Write real descriptions; never overwrite hand-written alt text |
| Title format with `#current_year` | Suggested for freshness | Only on pages that really change every year |
| SEO Analysis "No keywords found in title" | Flags the title | Ignore it if the title describes the page |
