# SEO guidance from the AIOSEO docs

General SEO advice the docs give, with bracketed checks where it is dated. Prefer google-alignment.md where they differ.

Built from a full read of aioseo.com/docs, /faqs and /blog on 2026-10-11 (AIOSEO Pro 5.0.2 on aioseo.com). Each section lists its source pages. Text in [brackets] is a reviewer note where the vendor advice looks dated or conflicts with Google guidance. UI labels move between versions: confirm on the live site before giving click paths as fact. Unresolved points are in open-questions.md.

## Contents

- Titles and meta descriptions
- On-page basics (Top Tips page; first published 2014)
- Content quality, word count, helpful content
- Indexing, crawling, status codes, noindex vs robots.txt
- Images in search
- Reviews and review schema
- Meta keywords
- HTTPS
- SERP features you can't force

## Titles and meta descriptions
Sources: https://aioseo.com/docs/quality-guidelines-for-seo-titles-and-descriptions/, https://aioseo.com/docs/meta-descriptions/, https://aioseo.com/docs/why-doesnt-the-title-and-description-i-set-appear-in-search-results/, https://aioseo.com/docs/why-does-the-character-counter-for-seo-titles-show-a-different-count/, https://aioseo.com/docs/top-tips-for-good-on-page-seo/, https://aioseo.com/docs/how-to-use-all-in-one-seo-to-share-your-brand-story-with-shoppers/, https://aioseo.com/docs/how-to-optimize-seasonal-offers-with-all-in-one-seo/

**What to write**
- Every page needs a title and description. AIOSEO fills them from the formats under **Search Appearance**.
- Make each one **unique** (no duplicates) and descriptive, with no keyword stuffing.
- **Brand the title.** By default AIOSEO appends the Site Title after a separator. The default format is content title + separator + Site Title, e.g. "Heating Repair Services, Durham NC | ABC Plumbing and Heating".

**Length**
- Titles: **under 60 characters**.
- Descriptions: **155–160 characters**, from the brand-story doc.
- Limits differ by engine, device and query. Check `site:` results for truncation.

**Effect and display**
- The meta description **doesn't affect ranking** but drives CTR.
- Google may rewrite either one, and no plugin can force display.
- AIOSEO still says setting them on every page is a fundamental part of SEO.

**Seasonal campaigns**
- Put seasonal keywords plus the offer in the title ("Black Friday", "50% Off").
- Target specific long-tail phrases.
- Run SEO Analysis **4–6 weeks before** major seasonal events.

[Google's current guidance has no fixed character limit; truncation is pixel-based. Treat 60/160 as rough heuristics.]

## On-page basics (Top Tips page; first published 2014)
Sources: https://aioseo.com/docs/top-tips-for-good-on-page-seo/

**URLs**
- AIOSEO recommends the permalink structure `/%postname%/`.
- Use lowercase, hyphens and no special characters; reflect hierarchy (`/services/heating-repair/`).
- The page claims a keyword in the domain helps ("abcplumbingandheating.com"). [Dated: exact-match domains carry little weight now.]

**Page title and headings**
- The page title is the H1 and should be the **only H1**; the theme should output it.
- Use H2 for headings and H3 for sub-headings, without skipping levels.

**Content**
- Write for humans; the first paragraph should summarise.
- Stay on point and succinct. "Don't go overboard" contradicts the word-count doc.
- Prefer bullets over comma lists; use bold sparingly.

**Images**
- Rename files descriptively before upload.
- Set alt text, plus a caption or title where useful.
- Keep files **under 100 KB** if possible.

**Links**
- The nav should match the site structure; in-content links should build a path through the site; links should look distinct from body text.
- Use buttons for actions.
- Open external links in a new tab. [This is a UX opinion, not an SEO factor.]
- Link to higher-ranking sites, and "use NOFOLLOW when links are to sites with a lower ranking". [Questionable: Google's guidance is to use nofollow/sponsored/ugc for paid, untrusted or user-generated links, not according to the target's rank.]

**Design:** responsive, large clean fonts, uncluttered pages.

## Content quality, word count, helpful content
Sources: https://aioseo.com/docs/does-a-minimum-or-maximum-word-count-improve-my-seo/, https://aioseo.com/docs/the-importance-of-quality-content-for-seo/, https://aioseo.com/docs/how-to-self-assess-your-content-to-see-if-its-helpful-reliable-and-people-first/, https://aioseo.com/docs/how-does-google-ranking-work/

**Word count**
- There is **no magic word count**.
- The page cites Neil Patel's 2,000–3,000 words as an observation, not a rule. [Treat it as unsupported.]
- Cover the topic thoroughly, use keywords naturally (in headings, body and image alt), break up text, and refresh content.

**Quality**
- Keyword stuffing no longer works; the page shows a "best running shoes" stuffing example.
- Example of good depth: a dentist turning a 300-word page into a 1,500-word guide with an FAQ schema.

**Self-assessment questions**
- Original value? Comprehensive? Honest, non-clickbait title? Well formatted and error-free? Worth bookmarking or sharing?
- Expertise shown through credible sources, author bio and About page? Factually accurate?

**Traffic drop audit**
1. Find the affected pages and queries in Search Statistics.
2. Analyse the pages now outranking you; compare with the Keyword Rank Tracker.
3. Self-assess honestly against Google's helpful-content questions, and review SEO Revisions.

**How Google works**
- Crawl, then index, then rank. Ranking weighs relevance, authority (reviews, links) and UX (mobile, speed).

## Indexing, crawling, status codes, noindex vs robots.txt
Sources: https://aioseo.com/docs/how-to-ensure-google-indexes-your-website-for-better-visibility/, https://aioseo.com/docs/checking-index-status-in-google-search-results/, https://aioseo.com/docs/how-long-does-it-take-for-my-content-to-appear-on-google/, https://aioseo.com/docs/understanding-status-codes-and-how-they-affect-crawling-and-indexing/, https://aioseo.com/docs/when-to-use-noindex-or-the-robots-txt/, https://aioseo.com/docs/what-is-a-dynamically-generated-sitemap-and-why-is-it-better-to-use/, https://aioseo.com/docs/how-to-get-search-engines-to-help-people-discover-your-content/

**Getting indexed**
- Check with `site:yourdomain.com`.
- Make sure robots.txt isn't blocking Google, submit the sitemap in GSC, and use URL Inspection for crawl errors.
- Sharing on social media and refreshing old content are said to help discovery. [Social links are nofollow; their effect on discovery is weak.]

**Status codes**

| Code | Effect per AIOSEO |
|---|---|
| 200 | Crawlable; indexing not guaranteed |
| 201/202 | Googlebot waits briefly, then may treat the page as empty or an error |
| 204 | Nothing to index; often reported as a soft 404 |
| 301 | Permanent; the new URL becomes canonical |
| 302/other 3xx | Followed, but the target may not become canonical; Googlebot follows **up to 10 redirect hops** |
| 404/4xx | Not indexed; already-indexed URLs are dropped over time |
| 429 | Treated like a server error, so crawling slows; check the server logs |
| 500/503/5xx | Persistent errors reduce crawling and eventually remove pages |

Monitor the GSC **Indexing** report.

**NOINDEX vs robots.txt**
- `<meta name="robots" content="noindex" />` keeps a page out of results and drops it if already indexed. The page **must stay crawlable** so the tag can be seen.
- robots.txt `Disallow` controls crawling only. It doesn't prevent indexing, and blocked URLs that are linked can still be listed.
- Use Disallow for directories with nothing of value (e.g. `/cgi-bin/`).
- Default WordPress robots.txt:
  ```
  User-agent: *
  Disallow: /wp-admin/
  Allow: /wp-admin/admin-ajax.php
  ```

**Dynamic sitemaps**
- AIOSEO says dynamic sitemaps are always current, fast, can't be deleted or corrupted, and avoid file-permission problems.

## Images in search
Sources: https://aioseo.com/docs/how-to-get-your-images-to-appear-in-search-results/

- You can't force images into results; they appear mostly in mobile results (mobile-first).
- Use responsive, high-quality but compressed images.
- Use descriptive filenames **with hyphens, not underscores** (`black-cat.png`), alt text and captions, with no stuffing.
- Put the most important image **first or high on the page**; engines usually use the first image.
- Optimise the surrounding SEO title, description and schema.
- Use unique images rather than stock.
- Keep the page public (not behind a login or paywall).
- Confirm images are listed: **All in One SEO » Sitemaps » General Sitemap » Open Sitemap**, where the **Images** column shows the count per URL.
- Submit the sitemap to Google and Bing.

## Reviews and review schema
Sources: https://aioseo.com/docs/how-to-write-high-quality-reviews-that-inform-and-influence/

**Writing reviews**
- Be honest: cover pros and cons.
- Show proof: photos, video, first-hand detail.
- Focus on decision factors and compare with competitors.
- Structure: intro, headings, summary and recommendation.
- Add context and story, mention version improvements, link to resources, and **disclose affiliate links**.

**Self-serving reviews**
- Reviews of your **own LocalBusiness/Organization** on your own site are "self-serving" and get no stars.
- Reviews of specific products or services you sell are acceptable.

**Schema Generator review types:** Product, Product Review, Recipe, Movie, Software Application, Course.

**Rating scale:** set any scale with `bestRating` / `worstRating`, e.g. 1–10.

## Meta keywords
Sources: https://aioseo.com/docs/should-i-use-meta-keywords/

- **Don't bother.** Google dropped them in 2009.
- Yandex may still use them, so AIOSEO keeps a Meta Keywords feature for Russian-market sites. It is irrelevant for Google and Bing.

## HTTPS
Sources: https://aioseo.com/docs/setting-up-https-ssl/

- HTTPS has been a Google ranking signal since August 2014.
- **New site:** set the WordPress Address and Site Address to `https://` under Settings » General.
- **Existing site, Apache `.htaccess`:**
  ```
  <IfModule mod_rewrite.c>
  RewriteEngine On
  RewriteCond %{SERVER_PORT} 80
  RewriteRule ^(.*)$ https://yoursite.com/$1 [R,L]
  </IfModule>
  ```
  [`[R,L]` issues a **302**. Use `[R=301,L]` for a permanent move.]
- **NGINX:**
  ```
  server { listen 80; server_name yoursite.com www.yoursite.com; return 301 https://yoursite.com$request_uri; }
  ```
- **Admin over HTTPS:** add `define('FORCE_SSL_ADMIN', true);` to `wp-config.php`.
- Get the SSL certificate from your host (e.g. Let's Encrypt).
- Test for mixed content with Chrome DevTools or Why No Padlock.

## SERP features you can't force
- Sitelinks, favicon, dates, images, rich results and the chosen title/description are all Google's decision. See the table in Part 2.

---
