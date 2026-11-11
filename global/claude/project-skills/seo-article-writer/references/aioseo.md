# All in One SEO (Elite) setup

Verified against the all-in-one-seo-pack 5.0.3 source (latest stable on 2026-10-07) and aioseo.com documentation. The Elite (Pro) code is not public: anything marked **unverified** must be checked on the live site after the first write. Recheck this file when AIOSEO's major version changes.

## 1. Per-article settings

The skill fills `seo.json` (template: `templates/seo.example.json`). `scripts/build-aioseo-payload.mjs` turns it into the REST payload. What each field becomes:

| seo.json | AIOSEO field | Rule |
|---|---|---|
| `aioseo.title` | SEO title (`title`) | About 400-600 px wide (roughly 50-60 characters; the checker estimates width). Keyphrase in it, at the start if it still reads well. Close to the H1, not identical if a sharper title fits. Smart tags allowed: `#post_title #separator_sa #site_title`. |
| `aioseo.description` | Meta description (`description`) | 120-155 characters (or the house limit), unique, keyphrase once (never more than twice), a concrete outcome or fact. Not a keyword list. Google rewrites many descriptions; write it anyway. |
| `aioseo.focus_keyphrase` | Focus keyphrase (`focus_keyword` + `keyphrases.focus`) | 1-4 content words, the query people type. |
| `aioseo.additional_keyphrases` | Additional keyphrases (`additional_keywords` + `keyphrases.additional`) | 2-5 close variants or sub-topics from the research. Elite allows several. |
| `aioseo.cornerstone` | Cornerstone content (`pillar_content`) | True only for a pillar page that many posts link to. |
| `aioseo.social.og_*` | Facebook tab | OG title can be more conversational than the SEO title. Image `featured` (default) or a custom URL; 1200x630. Object type `article`, section = primary category, tags. |
| `aioseo.social.twitter_*` | X tab | `twitter_use_og: true` and card `summary_large_image` unless X needs different copy. |
| `aioseo.robots` | Advanced tab robots | `"default"` (follow global settings) for normal posts. |
| `aioseo.canonical_url` | Canonical URL | Empty (self-canonical) unless the article is republished from elsewhere. |
| `aioseo.schema.faq` | Schema tab, custom FAQPage graph | Optional. Questions and answers copied exactly from the visible FAQ (the checker blocks mismatches). Google stopped showing FAQ rich results on 7 May 2026, so this mainly helps other engines. Never combine it with AIOSEO's FAQ block, which emits its own FAQPage schema. |
| `post.*` | WordPress post fields | Title (= the article H1), slug, excerpt, categories, tags, author, featured image with alt, title and caption. |

The default Article schema (BlogPosting for posts, with author, dates and featured image) comes from the global Search Appearance settings; no per-post schema write is needed for it. Microsoft says schema helps its LLMs; Google says no special schema is needed for AI features, and a controlled Ahrefs test (May 2026) found no citation lift from adding JSON-LD. Treat schema as accuracy, not a ranking lever.

## 2. Applying it: WordPress REST API

AIOSEO registers the `aioseo_meta_data` field on every public post type (free since 4.9.8, all plans).

- **Write:** `POST /wp-json/wp/v2/posts/<id>` with `{"aioseo_meta_data": {...}}`, authenticated with a WordPress Application Password for a user who can edit the post (administrators and editors can).
- **Read back:** `GET /wp-json/wp/v2/posts/<id>` returns `aioseo_meta_data` plus read-only `aioseo_head` (the rendered head HTML) and `aioseo_head_json`. Verify every write by reading these back.
- **Patch semantics:** keys you leave out keep their stored value. Unknown keys are silently ignored. Since 5.0.3 a forbidden or invalid payload returns 403 or 400 and nothing is saved.

Traps (all handled by the builder):

1. **Keyphrases must be written three ways:** `focus_keyword` (string), `additional_keywords` (`[{"word": "...", "score": 0}]`) and `keyphrases` (`{"focus": {"keyphrase": ...}, "additional": [...]}`). The 5.x editor reads only the first two; a write to `keyphrases` alone is invisible in the editor.
2. **Robots use short names on write:** `default`, `noindex`, `nofollow`, `noarchive`, `nosnippet`, `noimageindex`, `notranslate`, `noodp`, `maxSnippet`, `maxVideoPreview`, `maxImagePreview`. Reads return `robots_*` names; writing those does nothing. Overrides need `"default": false`.
3. **Schema is replaced whole.** The write is a shallow replace, so sending `schema` overwrites the post's entire schema object. To add the FAQ graph: GET the current `aioseo_meta_data.schema`, append the builder's `schema_custom_graphs` to `customGraphs` (replacing an item with the same `id`), and send the whole object back. Then confirm the FAQPage appears in `aioseo_head_json` (**unverified** that Elite outputs custom graphs unchanged).
4. **`_aioseo_*` post meta is write-only.** It exists for translation plugins; writing it directly changes nothing. Always use `aioseo_meta_data`.
5. **TruSEO scores are computed in the browser.** A REST write does not update `seo_score`. Open the post in the editor once to get the TruSEO and Headline Analyzer scores.
6. **New posts:** create the post with `aioseo_meta_data` in the same request so AIOSEO creates its row. (The separate Abilities API returns 404 for posts without a row.)

### Publishing order

1. Upload images: `POST /wp-json/wp/v2/media` (binary body, `Content-Disposition: attachment; filename=...`), then `POST /wp-json/wp/v2/media/<id>` with `alt_text`, `title`, `caption`. Build the media map for `to-gutenberg.mjs`.
2. Resolve category and tag names to IDs (`GET /wp/v2/categories?search=`, `/wp/v2/tags?search=`); create missing tags only with the user's approval.
3. Create the post as a **draft**: `POST /wp-json/wp/v2/posts` with `title`, `slug`, `excerpt`, `content` (Gutenberg markup), `status: "draft"`, `categories`, `tags`, `author`, `featured_media`, and `aioseo_meta_data`.
4. If FAQ schema is wanted, do the schema read-modify-write.
5. Read back and verify: title, description, keyphrases, OG and X fields, robots default, canonical, and the `aioseo_head` output.
6. Hand the user the draft link. Publishing (draft to publish) is a separate, explicit user decision.

Use whatever WordPress access the session has: a WordPress MCP connection with prepare/execute writes, or a WordPress REST connection that keeps the Application Password in a credential store. Never put the Application Password in chat, command arguments, logs or files in the repository. If no write access exists, give the user `wp-payload.json`, `post.html` and the manual steps below.

### Optional: AIOSEO Abilities (WordPress 6.9+)

AIOSEO also registers WordPress Abilities usable over REST or AIOSEO's MCP server: `aioseo-posts/seo-data-get`, `aioseo-posts/seo-data-update` (title, description, canonical, focus and additional keyphrases, cornerstone, robots, OG and X title/description; no schema), `aioseo-posts/list-missing-seo`, `aioseo-posts/list-truseo-score`, `aioseo-settings/get`, `aioseo-audit/site-get`. Route (WordPress core Abilities REST controller): `/wp-json/wp-abilities/v1/abilities/<namespace>/<ability>/run`. Read-only abilities run with `GET` (input as a query parameter); others with `POST` and `{"input": {...}}`. Check each ability's annotations with `GET /wp-json/wp-abilities/v1/abilities` before calling it. Useful for the read-only site audit below.

## 3. Done by hand in wp-admin (tell the user)

- Primary category in the AIOSEO sidebar, if the post has several categories (the REST shape of `primary_term` is unverified).
- Reviewer selection in the Author SEO panel, when an expert reviewed the article.
- Open the post once in the editor: check TruSEO and Headline Analyzer, and that no block shows a validation warning.
- Link Assistant suggestions (internal links from older posts to the new one) after publishing.
- Optional: AIOSEO Table of Contents block for long articles (its heading list is generated by the editor).

## 4. TruSEO 2.0 checks and how the skill treats them

The skill aims for green where it does not harm the writing, and never writes to the score. `lint-article.mjs` mirrors these checks.

| TruSEO check | Pass criterion | Skill stance |
|---|---|---|
| Keyphrase in SEO title | Present; start scores higher | Yes; start only if natural |
| Keyphrase in introduction | First paragraph | Yes |
| Keyphrase in meta description | Present, at most twice | Yes, once |
| Keyphrase in URL | In the slug | Yes |
| Keyphrase in subheadings | 30-75% of subheadings | One or two where natural; info only |
| Keyphrase in image alt | 30-75% of alt texts | Only where truthful |
| Keyphrase density | 0.5-3 per 100 words | Ceiling only; never pad |
| Keyphrase length | 1-4 content words (up to 8 acceptable) | Yes |
| Competing links | No internal link anchor uses the keyphrase | Yes |
| SEO title width | 400-600 px | Yes |
| Meta description length | 120-160 characters | Skill target 120-155 |
| Content length | 300+ words | Yes; length follows intent |
| Internal / external links | At least one of each | Yes, more where useful |
| Images | At least one image or video | Yes |
| Image alt text | Every image | Yes (empty alt only for decorative images) |
| Single H1 | One | Yes |
| Paragraph length | 150 words or fewer | Skill limit 120 |
| Sentence length | 25% or fewer over 20 words | Info; clarity first |
| Subheading distribution | 300 words or fewer per section | Yes |
| Transition words | 30%+ of sentences | Natural connectives (because, but, so, for example), never "Additionally/Furthermore" openers |
| Passive voice | 10% or less | Info |
| Consecutive sentence starts | No more than 2 in a row with the same word | Yes |

Headline Analyzer (English): scores 70+ as good; looks at word balance (common 20-30%, uncommon 10-20%, emotional 10-15%, at least one power word), headline type, length and the first and last three words. Use it as a nudge for the SEO title; do not add hype words that make the title less accurate.

## 5. One-time site setup (AIOSEO Elite)

Run once per site, and offer to audit it read-only (`aioseo-settings/get`, `aioseo-audit/site-get`, or the settings screens). Change settings only with the user's approval.

1. **Search Appearance > Global:** separator; home title `#site_title #separator_sa #tagline`; Knowledge Graph as Organization (name, logo, contact) or Person; alternate site name.
2. **Content Types > Posts:** title `#post_title #separator_sa #site_title`, description `#post_excerpt`, schema Article with subtype BlogPosting, show in search results, robots "use default settings".
3. **Advanced:** meta keywords off (Google ignores them); auto-generated descriptions on as a fallback; `max-image-preview: large`, snippet and video limits -1; Crawl Cleanup for feed and query-string bloat.
4. **Archives and taxonomies:** noindex thin tag, date and author archives (keep author archives indexable if they are real author pages with bios).
5. **Social Networks:** all profile URLs (they feed `sameAs`); Facebook default image 1200x630, default image source "featured image", app ID, article tags on; X username, default card `summary_large_image`, use Facebook data.
6. **Sitemaps:** XML sitemap with posts, pages and categories (exclude tags and attachments unless useful); RSS sitemap; News sitemap only for Google News publishers; Video sitemap if video is embedded. IndexNow on (Bing, Yandex and others; Google does not use IndexNow).
7. **Robots.txt:** keep the sitemap line. Do not block search and answer crawlers if AI citations are wanted: Googlebot, Bingbot, OAI-SearchBot (ChatGPT search), Claude-SearchBot and Claude-User, PerplexityBot. Training crawlers (GPTBot, ClaudeBot) are a separate policy choice for the owner. Google-Extended is not a crawler but a robots.txt token: it controls whether Google may use the site's content to train Gemini models and to ground answers in Gemini Apps and some Vertex AI features. It does not affect Google Search inclusion or ranking, including AI Overviews and AI Mode, which follow Googlebot.
8. **llms.txt:** optional. Google says it "will neither harm nor help" Search, and an Ahrefs study (June 2026) found 97% of llms.txt files received no requests. Enabling it is harmless; do not expect visibility from it.
9. **Breadcrumbs:** on, with the home link and category hierarchy (BreadcrumbList schema; Google shows breadcrumbs on desktop only since January 2025).
10. **Author SEO (E-E-A-T):** a complete profile for every author: photo, short and full bio, job title, employer, alumni of, knows about, awards, languages, social profiles. "Append author bio to posts" on. Never invent credentials or use AI headshots.
11. **Image SEO:** alt text format that never overwrites hand-written alt text; filename lower case with hyphens; strip punctuation.
12. **Webmaster Tools and Search Statistics (Elite):** verify Google Search Console and Bing Webmaster Tools; connect Search Statistics for keyword tracking, index status and content decay. Use content decay to pick articles to update (a real update beats a new post on the same topic).
13. **Redirects:** use the Redirection Manager whenever a slug changes.
14. **TruSEO:** enable TruSEO, Headline Analyzer and the spell checker.
15. **AI features:** AIOSEO's own AI title, description, FAQ and alt-text generators exist (Elite includes credits). This skill writes those itself; if anyone uses AIOSEO's generators, the output still goes through the fact-check (Google requires AI-written metadata to be checked).
