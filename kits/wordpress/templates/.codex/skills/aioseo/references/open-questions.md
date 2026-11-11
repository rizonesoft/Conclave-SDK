# Open questions and unverified points

Check these on a live Elite site before relying on them. Resolve an item by testing, then move the answer into the relevant reference file.

### From A-settings-onpage
1. **Writing Assistant location.** One page says General Settings » **Writing Assistant** tab (published 2024-10). The other (2026-08-12) shows a Writing Assistant card on General Settings » **Content Optimization**. The second is probably the v5.0 layout; check on a live site.
2. **Media versus Image SEO tab.** Redirect Attachment URLs and the Media Title format are said to be on Search Appearance » **Image SEO** tab in some pages and on the **Media** tab in others, and one page uses both. The tab list also differs: "Content Types, Taxonomies, Image SEO, Archives" versus "Content Types, Taxonomies, Media, Archives". There is also an Author SEO tab. The current tab set is unconfirmed.
3. **Social per-post location.** The newer X page says a separate **Social Appearance** meta box with Facebook and X (Twitter) tabs; the older homepage page says AIOSEO Settings » **Social** tab » Twitter. The tab list in the builder screenshots (Appearance, Optimization, Schema, AI Copilot, Redirects, SEO Revisions, Advanced) has no Social tab, which supports the separate meta box.
4. **Per-term SEO tier.** Category, tag and custom-taxonomy pages say "Pro only" (meaning any paid licence?); the Product Attributes page says Basic or higher. Probably both mean any paid plan.
5. **Block Editor UGC toggle.** The Block Editor link settings list only nofollow and sponsored; the Classic Editor also has UGC. It is unclear whether UGC exists in the Block Editor.
6. **Author blocks.** "Show 'See Full Bio' link" is listed for the Author Name and Reviewer Name blocks on one page and missing on the other. Author Bio (excerpt) is Plus, but full Bio, Author Name and Reviewer Name are Pro, even though the feature itself is Plus.
7. **SEO Revisions caps.** Only Plus = 15 is stated; the Pro and Elite caps are not given.
8. **Pro plugin folder name.** `all-in-one-seo-pack-pro` (delete step) versus `all-in-one-seo-pro` (upload step).
9. **Sitemap priority default.** "The default is 0.5", but AIOSEO also "calculates" priority and frequency. What does "Default" output?
10. **Quick Edit buttons.** "Save Changes / Discard Changes" on one page and "Save / Cancel" on another (UI version difference).
11. **Additional keyword limit.** The Semrush page says at most 10 keywords in Additional Keywords; the newer TruSEO page shows one keyword table and does not state a cap. Is the cap 10 additional keywords or 10 in total?
12. **Readability score scale.** The 60-80 target suggests Flesch Reading Ease, but the doc does not name the formula.
13. **Headline character target.** Character Count aims for "about 55". The Basics tab's Page title width uses pixels, and the Details column uses 600 px. These two title-length measures are separate.
14. **Shortcode filters.** The signatures of `aioseo_disable_shortcode_parsing` and `aioseo_conflicting_shortcodes` live on separate pages that were not in the docs.
15. **Crawl Cleanup bot list.** The Unwanted Bots page does not name the individual AI crawlers.
16. **Query Arg Monitoring Log Retention.** The dropdown values are not listed.
17. **Optimize UTM Parameters.** It "replaces UTM parameters with the # equivalent via 301". It is unclear whether this affects GA attribution; GA4 does read fragments only if configured.

### From B-schema-local-social
- `aioseo_breadcrumbs()` timing: "must run inside the WordPress loop" (Displaying Breadcrumbs) vs "must run after the queried object is loaded" (function page, whose own example sits in header.php outside the loop). The second looks correct.
- `aioseo_schema_breadcrumbs_home` filter: named but no signature or example in the docs (probably in a filters doc elsewhere).
- Where Local Business schema is output with Multiple Locations on: single-location doc says homepage only; the multi-location docs are silent (presumably each Location post).
- Local SEO tab names differ: function docs say "Local Seo -> Business Info" / "Opening Hours"; newer docs say "Local SEO » Locations" holds Business Info and the Map section. Map pin field is called both "Enter a query" and "Enter a search query".
- Per-user social URLs: Knowledge Panel doc says Users > edit > Social Profiles tab; Facebook/Twitter author docs say an "All in One SEO" section on Edit User with Facebook/Twitter fields. Probably the older UI; current UI likely the Social Profiles tab.
- Per-content social settings called the "Social Appearance meta box" in one doc and "AIOSEO Settings > Social tab" elsewhere.
- Image specs conflict: Twitter min 144 x 144 (Summary) in one page vs min 300 x 157 in troubleshooting; Facebook 1200 x 630 preferred vs 1.91:1 with 1640 x 856 example. Logo formats: Organization accepts SVG/WEBP, Person only jpg/png/gif.
- PHP examples in local function docs are buggy (label keys set to 'true'; missing quote in `'showWednesday`); `aioseo_local_map` PHP arg list omits `label` but example uses it. Booleans are passed as strings ('true'/'false'); whether real booleans work is not stated.
- Lists of allowed values not given: Article Type options beyond Article/Blog Post/News Article; Web Page Type options; Event Type/Status; Software Category; Employment Type; Price Indicator values; Local Business Type list; Facebook Object Type list.
- Content-type defaults are not documented for Book, Event, Fact Check, How-To, Job Posting, Music, Video; unclear whether the Schema Type dropdown offers them.
- Whether the Facebook "Default Post Facebook Image" falls back to the theme logo only if empty (doc says "automatically use it as" default).
- Several schema types Google has retired or restricted (Sitelinks Search Box Nov 2024; How-To Sept 2023; FAQ restricted Aug 2023; June 2025 phase-out of Book Actions, Course Info, ClaimReview, Estimated Salary, Vehicle Listing etc.). The AIOSEO docs still present them as rich-result opportunities. [Note, verify against current Google Search Central before advising.]
- Pinterest Rich Pins page in the local copy is a short stub; no AIOSEO-specific steps beyond "set homepage social meta first".
- "Google offers a $200 monthly credit" for Maps is likely out of date (Google changed Maps Platform pricing in March 2025).

### From C-technical-tools

1. **llms.txt is not covered.** No page in the docs documents llms.txt (no menu path, URL, settings or tier). Check other batches or the plugin UI. The topic list expected it.
2. **Redirection Manager tier conflict.** The redirect pages say "Basic plan or above". Five 2025 GSC troubleshooting pages say "Pro plan or above". Which advanced redirect features need Pro is only partly stated (Full Site Redirect, Log Settings and Advanced 404 are named). It is unclear whether Custom Rules, Regex, Query Parameters, HTTP Headers and Scheduling are Basic or Pro.
3. **HTML sitemap `archives` default.** The doc gives `archives` (compact archive instead of the sitemap) a default of `true`, which would replace the sitemap by default. This is likely a doc error; verify in code.
4. **HTML sitemap label.** The display option is called "Dedicated Page" in the text but "Dynamic Page" is the radio selected.
5. **RSS sitemap exclusions.** The RSS exclusion doc sends users to the General Sitemap tab's Advanced Settings. It is unclear whether the RSS Sitemap tab has its own Exclude Posts / Pages field or whether the XML exclusions are shared.
6. **Broken Link Checker scan cadence.** "Automatically scans ... each day" and "rescan ... every three days" appear on the same page.
7. **AI Suite menu name.** "AI Suite" in most pages, "AI Suites" in the credits page. AI Insights calls the screen "AI Insights" with tabs Keyword Reports / Brand Tracker / AI Content. The MCP doc adds an **MCP** tab to the AI Suite page. The full tab list in current versions is unclear.
8. **MCP ability counts.** "13 free, Pro doubles that" implies about 26, plus 4 for Link Assistant. The exact names of the abilities (e.g. `aioseo/...` identifiers) are not listed. Whether abilities respect the Application Password user's capabilities is not stated.
9. **Multisite robots.txt.** The page says the network editor works only for subdomain networks, yet it also describes a per-subsite site selector. It is unclear what subdirectory networks get.
10. **Domain Activations on multisite** is Elite-only, but plain network activation of the main site is not tier-gated in the doc.
11. **Soft 404 and 410 messaging is inconsistent.** The deletion doc says Google may treat 410 as a soft 404; the soft-404 doc recommends 410 for gone pages. The GSC section placement is also inconsistent: the 5xx and "Indexed though blocked" docs both point to an "Improve page appearance" section. [5xx sits under "Why pages aren't indexed". "Indexed, though blocked by robots.txt" is a warning in the indexed group.]
12. **Image Generator editor support.** The note says Block, Classic and page builders, but every step uses Image blocks and the Block Editor featured image panel.
13. **Search Statistics Settings.** The doc says the Settings tab chooses post types, but the linked detail article is not in the docs. The Keyword Rank Tracker and Index Status articles are referenced but absent.
14. **IndexNow engine list** is out of date (only Bing and Yandex named). It is unclear whether AIOSEO also pings on delete.
15. **Pinterest verification** is listed under Webmaster Tools, but no Pinterest page is in the docs. The field name is unknown.
16. **Import Redirects From Other Plugins.** The list of supported source plugins (e.g. Redirection, Yoast Premium, Rank Math) is not given.
17. **Web Server redirect method.** One page names LiteSpeed alongside Apache and NGINX, while the unknown-server page says only Apache and NGINX are supported or detected.

### From D-developer

Resolved by the recovered code (kept for the record): flyout hook name (`aioseo_flyout_menu_enable`); robots attribute keys; crumb/`reference` shape; breadcrumb template is an array with `template`; additional-pages entry keys; sitemap translation keys `language`/`languages[language, location]`; sitemap image entries are URL strings; RSS `pubDate`; Local Business `showPhone`/`showSunday`, `labels->closed`, nested `locations->business->name`, address tags list with `id`; conflicting shortcodes `'Label' => '[tag]'`; redirect log `$data['http_code']`/`$data['url']`; access-control roles are slugs; public post type items are arrays with `name`; `aioseo_meta_views` accepts `[]`.

Still open:
1. Exact structure of `$views` in `aioseo_meta_views` (list of names vs keyed) when only some views are removed; the example only returns `[]`.
2. `aioseo_social_image_ignore_cover_block`: prose says default `true` (ignore) yet the "use Cover block image" example returns `true`. Which value enables Cover block images? Test.
3. `aioseo_user_profile_tab_disable` "defaults to true" contradicts the example (returning `true` to hide). Probably defaults to `false`.
4. `aioseo_sitemap_post`/`_term`: prose lists 3 params, code registers 2. The 3rd is likely passed, unconfirmed.
5. Whether `$type` in `aioseo_sitemap_exclude_*` has values other than `'general'` (e.g. for video/news/RSS sitemaps).
6. REST API page says Lite and Pro, but Composer lists an `aioseo/rest-api` addon. Is the addon still required, and for which tier?
7. LLMS description filters say only "llms.txt"; title filters say llms.txt and llms-full.txt. Does llms-full.txt use the description filters? Why is the object optional (`= null`) in the vendor code?
8. `aioseo_page_builder_integration_disable` does not list valid `$pagebuilder` name strings.
9. `aioseo_report_summary_enable` does not name its argument.
10. The Facebook tags key list and the Twitter tags key list were not recoverable (Twitter embed empty; no Facebook list embed).
11. The two Local Business SQL embeds are empty in the source.
12. No action hooks, WP-CLI commands or JS API are documented in the docs; whether AIOSEO documents any elsewhere is unknown from these pages.
13. "Localizing AIOSEO options" (default title/description formats) is listed as a Translations API use case, but no hook for options is named.

### From E-faq-troubleshooting

1. **Chat support:** the "Do you offer phone support?" doc (MODIFIED 2026-08-14) says 24×7 chat on the Contact page. /faqs/ (MODIFIED 2026-05-20) says no phone or chat. The doc is probably current.
2. **Refund route:** the doc says https://aioseo.com/refund-survey/; /faqs/ says the contact form route ("I'd like a refund").
3. **Multilingual:** /faqs/ names only WPML. The docs name Universally and WPML. Compatibility with Polylang, TranslatePress and Weglot is not stated anywhere here.
4. **Minimum WordPress version:** the requirements page says 5.7 (with a footnote dropping everything below 6.0 at the start of 2026). The Update page says 5.9 and below are dropped and recommends "at least 7.x". The real enforced minimum version in current releases is unclear.
5. **Pro plugin folder name:** `all-in-one-seo-pack-pro` (Action Scheduler doc) vs `all-in-one-seo-pro` (manual-install doc).
6. **Keyword limit:** "a maximum of ten keywords" vs "up to 10 additional keywords alongside its focus keyword" (10 or 11 in total?).
7. **TruSEO in page builders:** TruSEO itself "works with supported page builders", but the Highlighter does not. The list of supported builders isn't in the docs.
8. **TruSEO disabled pages:** BuddyPress pages appear only in the FAQ answer, not in the main list.
9. **SEO Alerts licence tier:** not stated; the wording suggests Lite. How the hourly check is scheduled (WP-Cron vs Action Scheduler) is not stated.
10. **Redirect Attachment URLs location:** this doc says Search Appearance » Image SEO tab. Other AIOSEO docs and versions place it under the Media/Attachments content type. Verify in the current UI.
11. **AI credits:** the number included per Pro tier is not given; only "about 10 credits per AI feature use".
12. **Plan contents:** no page in the docs lists Basic/Plus/Pro/Elite features or site counts. The pricing page is the only stated source.
13. **Usage tracking:** the opt-in/opt-out setting location is not stated.
14. **Translated languages:** "50+" vs "54+".
15. **Temporary admin email for support:** obfuscated in the source text (Cloudflare email protection), so the actual address is unknown.

### From the blog (conflicts with the docs or between posts)

1. **MCP and ChatGPT.** The MCP doc (modified 2026-10-01) says ChatGPT is not supported directly. A 2026 blog post lists ChatGPT among the clients with a ready snippet. Check the MCP tab on the site.
2. **Ability count.** The docs say 13 in Lite and "about double" in Pro (plus 4 for Link Assistant). The blog says 28 or 29. Run `GET /wp-json/wp-abilities/v1/abilities` on the site.
3. **Search Statistics tier.** Most sources say Elite only; one post says "Pro unlocks Link Assistant and Search Statistics". Elite has it either way; this matters only when advising on lower plans.
4. **Plan contents and prices** change often and differ between posts (see blog-features-tiers.md). Check https://aioseo.com/pricing/ before stating what a plan includes.
5. **llms.txt location.** Most sources say Sitemaps » LLMs.txt; one post says General Settings. Check the site.
6. **Local SEO tier.** "Plus and above" in the docs and most posts; "Pro" in one 2026 post.
7. **Job Posting schema** is said to be on all paid plans since 4.9.9 (previously Elite).
8. **2026 AI search claims made only by the vendor blog** (AI Overviews opt-out toggle in Search Console, separate AI Overview and AI Mode filters, AI Mode as default, a May 2026 AI-manipulation spam policy, the June 2026 spam update window, Bing's "AI Performance" report). See "Needs verification" in blog-google-checks.md. Confirm against Google or Bing before advising.
