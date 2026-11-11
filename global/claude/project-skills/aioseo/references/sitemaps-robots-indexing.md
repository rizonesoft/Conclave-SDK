# Sitemaps, robots.txt, llms.txt, IndexNow and verification

XML, video, news, RSS and HTML sitemaps; robots.txt editor; llms.txt; IndexNow; webmaster tools verification; analytics.

Built from a full read of aioseo.com/docs, /faqs and /blog on 2026-10-11 (AIOSEO Pro 5.0.2 on aioseo.com). Each section lists its source pages. Text in [brackets] is a reviewer note where the vendor advice looks dated or conflicts with Google guidance. UI labels move between versions: confirm on the live site before giving click paths as fact. Unresolved points are in open-questions.md.

## Contents

- XML Sitemap
- LLMs.txt
- Sitemaps: general model and URLs
- XML Sitemap (General Sitemap tab)
- Video Sitemap
- Google News Sitemap
- RSS Sitemap
- HTML Sitemap
- Sitemap troubleshooting
- Robots.txt Editor
- Webmaster Tools verification
- IndexNow
- Google Analytics / Google Tag Manager (deprecated)

## XML Sitemap
Source: https://aioseo.com/docs/how-to-create-an-xml-sitemap/

- It is on by default. Location: All in One SEO » Sitemaps » General Sitemap » **Enable Sitemap**; **Open Sitemap** views it.
- Sitemaps are virtual and generated dynamically on each crawler request, with no physical file.
- AIOSEO pings Google on publish or update; Bing and others get **IndexNow**. [Google retired its sitemap ping endpoint in 2023, so the Google ping does nothing. Submit the sitemap in Search Console instead; connecting GSC in Webmaster Tools keeps it submitted.]
- Disabling it makes the sitemap URL return 404. Not recommended.
- **Enable Sitemap Indexes**: default Enabled. It can be Disabled for very small sites (under a few hundred URLs).
- **Links Per Sitemap**: default **1,000** URLs per page. Lower it if pages load slowly.
- **Post Types** and **Taxonomies**: Include All Post Types and Include All Taxonomies are checked by default. Uncheck them to choose. Types set to noindex or Show in Search Results = No are not listed.
- **Date Archives** and **Author Archives**: off by default because they have little search value.
- Next step: submit to Google, Bing and Yandex (separate docs).

## LLMs.txt
Source: https://aioseo.com/docs/how-to-create-an-llms-txt-using-all-in-one-seo/ (PUBLISHED 2025-06-26)

- **Enabled by default.** Location: All in One SEO » Sitemaps » **LLMs.txt** tab.
- **LLMs.txt** section:
  - Enable llms.txt, with an **Open llms.txt** button (`/llms.txt`).
  - Enable **llms-full.txt**, with an **Open llms-full.txt** button. After enabling, save and wait about a minute while it generates; the button stays greyed out until then.
  - **Convert Posts to Markdown**: serves clean Markdown versions of posts to AI crawlers.
- **LLMs.txt Settings** section:
  - **Title**: defaults to the Site Title.
  - **Description**: defaults to the Tagline.
  - **URLs per Post Type / Taxonomy**: the maximum per type.
  - **Post Types** and **Taxonomies**.
  - **Exclude Posts / Pages** and **Exclude Terms**: autocomplete.
- [llms.txt is a proposed convention. Major search engines do not document using it, so treat it as optional.]

## Sitemaps: general model and URLs

Sources: https://aioseo.com/docs/how-to-create-a-google-news-sitemap/, https://aioseo.com/docs/how-to-create-an-rss-sitemap/, https://aioseo.com/docs/how-to-create-a-video-sitemap/, https://aioseo.com/docs/how-to-disable-sitemaps-in-all-in-one-seo/, https://aioseo.com/docs/submitting-a-sitemap-to-google/, https://aioseo.com/docs/submitting-a-sitemap-to-bing/, https://aioseo.com/docs/submitting-a-sitemap-to-yandex/, https://aioseo.com/docs/xml-sitemap-rewrite-rules-for-nginx/, https://aioseo.com/docs/troubleshooting-the-couldnt-fetch-error-in-google-search-console/

- wp-admin: **All in One SEO > Sitemaps**. Tabs: **General Sitemap** (the XML sitemap), **Video Sitemap**, **News Sitemap**, **RSS Sitemap**, **HTML Sitemap**. Every tab has an **Enable Sitemap** toggle at the top and an **Open Sitemap** button.
- Sitemaps are virtual pages generated on each request. No physical file is written, so file permissions and accidental deletion are not a concern.
- A disabled sitemap's URL returns 404. AIOSEO recommends leaving sitemaps on. Disable one only when another plugin supplies that sitemap.
- Default URLs:

| Sitemap | URL | Tier |
|---|---|---|
| XML (index) | `/sitemap.xml` (also `/sitemap.xml.gz`) | Lite |
| XML child sitemaps | `/<type>-sitemap.xml`, paginated as `/<type>-sitemap2.xml` etc. (e.g. `post-sitemap1.xml`) | Lite |
| Video | `/video-sitemap.xml`, children `/<type>-video-sitemap.xml` | Pro+ |
| News | `/news-sitemap.xml` | Pro+ |
| RSS | `/sitemap.rss`; the NGINX rules also map `/sitemap.latest.rss` | Lite |
| HTML | a virtual page you name, or a shortcode, block, widget or PHP call | Lite |

- The XML sitemap includes images, so no separate image sitemap is needed.
- Yandex accepts XML sitemaps only, not RSS.
- **Automatic GSC submission:** when the site is connected under General Settings > Webmaster Tools > Google Search Console (the OAuth connect), AIOSEO submits the XML, RSS, Video and News sitemaps to GSC and keeps them synced for as long as the connection lasts. A notice on the Sitemaps page confirms this.
- **Manual submission.** GSC: Sitemaps > Add a new sitemap, enter only the path (e.g. `sitemap.xml`). Bing Webmaster Tools: Sitemaps > Submit sitemap, enter the full URL. Yandex: Indexing > Sitemap files > Add.
- Processing time is set by the search engine and cannot be sped up. You submit once; you do not resubmit after each publish.

### NGINX rewrite rules (legacy)
Rewrite rules should not be needed on AIOSEO 4.2.1 or later. Add them only if a sitemap returns 404 on NGINX, or if `/sitemap.xml` keeps redirecting to `/sitemap_index.xml` (another SEO plugin's slug; remove that plugin's rules too). The video rules must come before the XML rules.
```
rewrite ^/video-sitemap.xml$ /index.php?aiosp_video_sitemap_path=root last;
rewrite ^/video-sitemap.xml.gz$ /index.php?aiosp_video_sitemap_path=root last;
rewrite ^/(.+)-video-sitemap.xml$ /index.php?aiosp_video_sitemap_path=$1 last;
rewrite ^/(.+)-video-sitemap.xml.gz$ /index.php?aiosp_video_sitemap_path=$1 last;
rewrite ^/(.+)-video-sitemap(\d+).xml$ /index.php?aiosp_video_sitemap_path=$1&aiosp_sitemap_page=$2 last;
rewrite ^/(.+)-video-sitemap(\d+).xml.gz$ /index.php?aiosp_video_sitemap_path=$1&aiosp_sitemap_page=$2 last;
rewrite ^/sitemap.xml$ /index.php?aiosp_sitemap_path=root last;
rewrite ^/sitemap.xml.gz$ /index.php?aiosp_sitemap_path=root last;
rewrite ^/(.+)-sitemap.xml$ /index.php?aiosp_sitemap_path=$1 last;
rewrite ^/(.+)-sitemap.xml.gz$ /index.php?aiosp_sitemap_path=$1 last;
rewrite ^/(.+)-sitemap(\d+).xml$ /index.php?aiosp_sitemap_path=$1&aiosp_sitemap_page=$2 last;
rewrite ^/(.+)-sitemap(\d+).xml.gz$ /index.php?aiosp_sitemap_path=$1&aiosp_sitemap_page=$2 last;
rewrite ^/sitemap.rss$ /index.php?aiosp_sitemap_path=rss last;
rewrite ^/sitemap.latest.rss$ /index.php?aiosp_sitemap_path=rss_latest last;
```
The query vars are `aiosp_sitemap_path`, `aiosp_video_sitemap_path` and `aiosp_sitemap_page`. These rules work for "99%" of users; WordPress installed in a subdirectory needs adjustments.

---

## XML Sitemap (General Sitemap tab)

Sources: https://aioseo.com/docs/choosing-which-content-to-include-in-your-xml-sitemap/, https://aioseo.com/docs/how-to-exclude-content-from-your-xml-sitemap/, https://aioseo.com/docs/excluding-images-from-the-xml-sitemap/, https://aioseo.com/docs/including-date-and-author-archives-in-your-xml-sitemap/, https://aioseo.com/docs/using-sitemap-indexes-and-pagination/, https://aioseo.com/docs/setting-the-priority-and-frequency-for-content-in-the-xml-sitemap/, https://aioseo.com/docs/adding-non-wordpress-content-to-the-xml-sitemap/, https://aioseo.com/docs/importing-urls-into-the-xml-sitemap/

Tier: Lite. Path: All in One SEO > Sitemaps (opens on General Sitemap).

**Sitemap Settings section**

| Setting | Default | Values / notes |
|---|---|---|
| Enable Sitemap | On | Off makes /sitemap.xml return 404 |
| Enable Sitemap Indexes | Enabled | Enabled/Disabled. Disabling suits only small sites |
| Links Per Sitemap | 1000 | Shown only while indexes are enabled. AIOSEO advises lowering it, never raising it |
| Post Types | Include All Post Types checked | Uncheck to pick individual types |
| Taxonomies | Include All Taxonomies checked | Uncheck to pick individual taxonomies |
| Date Archive Sitemap | Disabled | Enabled/Disabled. Hidden when date archives are noindexed in Search Appearance |
| Author Sitemap | Disabled | Enabled/Disabled. Hidden when author archives are noindexed |

- Pagination: with 2,500 posts you get post-sitemap1 (1000), post-sitemap2 (1000) and post-sitemap3 (500). The newest content goes into the first page.
- Content set to noindex or "excluded from search results" under Search Appearance does not appear in the Post Types/Taxonomies lists and is left out of the sitemap.
- AIOSEO recommends leaving date and author archives out except on news sites (date) or multi-author sites with followings (author).

**Additional Pages (non-WordPress URLs)**
- Toggle **Additional Pages**, then fill **Page URL**, **Priority**, **Frequency** and **Last Modified** and click **Add Page**. Entries appear in a table: click the URL to edit, the trash icon to delete.
- **Import from CSV** button, with a "Download Sample CSV File" link in the popup. Choose a File, then Import.
- CSV fields: Page URL as a full URL; Priority 0.0-1.0 (0.5 if unsure); Frequency one of `always, hourly, daily, weekly, monthly, yearly, never`; Last Modified Date as `mm/dd/yyyy`.

**Advanced Settings (toggle)**
- **Exclude Posts / Pages**: type a title, pick from the dropdown, repeat for more.
- **Exclude Terms**: type a category, tag or term name. Excluding a term also excludes every post in that term (e.g. excluding Uncategorized drops all its posts). Term exclusions on this tab also apply to the RSS sitemap.
- **Exclude Images**: Yes/No, default No. Yes removes the image entries.
- **Priority Score** (homepage, archives including post type and date archives, author archive), **Post Type Priority Score** and **Taxonomy Priority Score**, each with **Priority** and **Frequency** dropdowns. A **Grouped** toggle sets values per individual post type or taxonomy. Individual posts can override these (separate article not in the docs).
- Priority ranges 0.0-1.0, default 0.5. AIOSEO calculates priority and frequency automatically, so most users never change them.

Gotchas:
- Leaving content out of the sitemap does not stop indexing. Use noindex for that, and noindex content is removed from the sitemap automatically.
- The docs say "most search engines ignore" priority. [Google ignores `priority` and `changefreq` entirely and uses `lastmod` only if it is consistently accurate. Do not spend effort tuning these.]

---

## Video Sitemap

Sources: https://aioseo.com/docs/how-to-create-a-video-sitemap/, https://aioseo.com/docs/choosing-which-content-to-include-in-your-video-sitemap/, https://aioseo.com/docs/how-to-exclude-content-from-your-video-sitemap/, https://aioseo.com/docs/including-videos-in-custom-fields-in-your-video-sitemap/, https://aioseo.com/docs/supported-videos/, https://aioseo.com/docs/support-for-videos-embedded-using-the-media-library/, https://aioseo.com/docs/adding-non-wordpress-content-to-the-video-sitemap/, https://aioseo.com/docs/setting-the-priority-and-frequency-for-content-in-the-video-sitemap/, https://aioseo.com/docs/using-sitemap-indexes-and-pagination/

- Tier: **Pro plan or above**. Enabled by default on Pro.
- Path: Sitemaps > **Video Sitemap** tab. Open Sitemap shows an index with one child sitemap per content type (Posts, Pages and so on).
- **Video Sitemap Settings:** Enable Sitemap Indexes, Links Per Sitemap (default 1000), **Post Types** (Include All Post Types) and **Taxonomies** (Include All Taxonomies).
- Categories and Tags never appear under Taxonomies because their Description field does not support videos.
- Noindexed content is not listed.
- **Advanced Settings:** Exclude Posts / Pages; Exclude Terms (excludes every video in that term); **Include Custom Fields** = Yes includes videos stored in custom fields, which covers page builders that save to custom fields.
- Priority and Change Frequency were removed from the video sitemap in v4.0 because they are no longer required.
- Non-WordPress (external) video URLs cannot be added. The docs say a "future release" will add this.
- **Supported embeds (Pro 4.x):** DailyMotion (oEmbed, iFrame), Flickr (oEmbed, JavaScript), TED (oEmbed, iFrame), VideoPress/WordPress.tv (oEmbed, iFrame), Vimeo (oEmbed, iFrame), YouTube (oEmbed, iFrame), "some" JavaScript embeds, and local videos added through the Media Library or a shortcode.
- Local videos use the site logo as the thumbnail, or a generic video image if no logo is set. [Google requires a representative thumbnail and the video must be the page's main content to get video indexing. A logo thumbnail is weak.]

---

## Google News Sitemap

Sources: https://aioseo.com/docs/how-to-create-a-google-news-sitemap/, https://aioseo.com/docs/how-to-exclude-content-from-your-google-news-sitemap/

- Tier: **Pro plan or above**. URL: `/news-sitemap.xml`.
- Path: Sitemaps > **News Sitemap** tab. Enable Sitemap.
- **News Sitemap Settings:**
  - **Publication Name**: defaults to the Site Title when empty.
  - **Post Types**: Include All Post Types is checked by default. Uncheck it and select only news post types. Do not include Pages or Products.
- **Advanced Settings:** Exclude Posts / Pages. There is no Exclude Terms on this tab.
- Contains only content published in the **last 48 hours**. With nothing that recent, the URL returns **404, which is normal**.
- AIOSEO recommends Google Publisher Center approval. It is not required. [Google retired Google Newsstand and changed Publisher Center in 2024. Inclusion in Google News is now automatic, and the "Newsstand eligibility" benefit the doc names is out of date.]
- Excluding content only stops the notification; Google can still find and index it. Use noindex to prevent indexing.

---

## RSS Sitemap

Sources: https://aioseo.com/docs/how-to-create-an-rss-sitemap/, https://aioseo.com/docs/how-to-exclude-content-from-your-rss-sitemap/

- Tier: Lite. Created by default alongside the XML sitemap. URL: `/sitemap.rss`.
- Path: Sitemaps > **RSS Sitemap** tab.
- **Posts Per Sitemap**: default **50**. It is meant to stay small and hold only the latest content.
- **Post Types**: Include All Post Types by default.
- Exclusions: the doc points to the **General Sitemap** tab's Advanced Settings (Exclude Posts / Pages, which has a "+" button that lists all content, and Exclude Terms). A term excluded there drops its posts from both the XML and RSS sitemaps.
- AIOSEO claims search engines check RSS sitemaps "much more frequently" than XML sitemaps. [Google does accept RSS/Atom feeds as sitemaps and suggests them for recent changes, but the frequency claim is not documented.]

---

## HTML Sitemap

Sources: https://aioseo.com/docs/html-sitemap/, https://aioseo.com/docs/shortcode-html-sitemap/, https://aioseo.com/docs/function-html-sitemap/, https://aioseo.com/docs/using-a-widget-to-display-your-html-sitemap/

- Tier: Lite. Path: Sitemaps > **HTML Sitemap** tab. Enable Sitemap is **on by default**.
- **Display HTML Sitemap**, five methods:
  1. **Dedicated Page** (the radio option reads "Dynamic Page"): a virtual page whose name you enter. Save Changes, then **Open HTML Sitemap**.
  2. **Shortcode**
  3. **Gutenberg Block** (separate article, not in the docs)
  4. **Widget**: "AIOSEO – HTML Sitemap" under Appearance > Widgets. Widget settings override the global HTML sitemap settings.
  5. **PHP Code**
- **HTML Sitemap Settings:**

| Setting | Values | Default |
|---|---|---|
| Post Types | Include All Post Types or a selection | All |
| Taxonomies | Include All Taxonomies or a selection | All |
| Sort Order | Publish Date, Last Updated Date, Alphabetical, Post / Term ID | Publish Date |
| Sort Direction | Ascending, Descending | Ascending |
| Publication Date | show/hide the publish date next to each item (post types only) | shown |
| Compact Archives | works with the **WPBeginner Compact Archives** plugin | n/a |

- **Advanced Settings:** Exclude Posts / Pages and Exclude Terms; match by ID, title or slug.
- **Shortcode:** `[aioseo_html_sitemap]`. The PHP function `aioseo_html_sitemap( array $args )` takes the same arguments:

| Attribute | Meaning | Default |
|---|---|---|
| `post_types` | comma-separated slugs, e.g. `post,page` | all selected |
| `taxonomies` | comma-separated slugs, e.g. `category,post_tag` | all selected |
| `label_tag` | HTML tag for section labels | `h4` |
| `show_label` | `true`/`false` | `true` |
| `publication_date` | `true`/`false` | `true` |
| `archives` | `true` shows a compact archive instead of the sitemap | `true` per docs (see Open questions) |
| `order` | `ASC`/`DESC` | `ASC` |
| `order_by` | `publish_date`, `last_updated`, `alphabetical`, `id` | `publish_date` |

```
[aioseo_html_sitemap post_types="post,page" taxonomies="category,post_tag" label_tag="h2" show_label="true" publication_date="true" archives="false" order="ASC" order_by="alphabetical"]
```
```php
<?php if( function_exists( 'aioseo_html_sitemap' ) ) aioseo_html_sitemap( array(
 'post_types' => 'post,page', 'taxonomies' => 'category', 'label_tag' => 'span',
 'show_label' => 'true', 'publication_date' => 'true', 'archives' => 'false',
 'order' => 'ASC', 'order_by' => 'alphabetical' ) ); ?>
```
- The shortcode works in the Classic Editor, the Block Editor and any page builder. The settings screen shows the generated shortcode and PHP code, with an **Advanced Settings** link that lists every argument.

---

## Sitemap troubleshooting

Sources: https://aioseo.com/docs/excluding-the-xml-sitemap-from-caching/, https://aioseo.com/docs/this-page-contains-the-following-errors/, https://aioseo.com/docs/troubleshooting-the-couldnt-fetch-error-in-google-search-console/ (published 2026-06-17), https://aioseo.com/docs/xml-sitemap-rewrite-rules-for-nginx/

**Exclude sitemaps from caching.** Never cache sitemaps. Clear all caches after you add the exclusions.

| Plugin | Where | Value |
|---|---|---|
| LiteSpeed Cache | LiteSpeed Cache > Cache > Excludes > Do Not Cache URIs | `/(.*)sitemap(.*).xml` and `/(.*)sitemap.xsl` |
| WP Fastest Cache | WP Fastest Cache > Exclude > Exclude Pages > Add New Rule | Contains `sitemap` |
| WP Rocket | Settings > WP Rocket > Advanced Rules > Never Cache URL(s) | `/(.*)sitemap(.*).xml` and `/(.*)sitemap.xsl` |
| WP Super Cache | Settings > WP Super Cache > Advanced > "Add here strings (not a filename) that forces a page not to be cached" | the three regexes below |
| W3 Total Cache | Performance > Page Cache > "Never cache the following pages". Add the same strings to Database Cache (if used), to Minify > "Never minify the following pages", and to Browser Cache > "404 error exception list" | the three regexes below |

```
sitemap(_index)?\.xml(\.gz)?
[a-z0-9_\-]*sitemap[a-z0-9_\-]*\.(xml|xsl|html)(\.gz)?
([a-z0-9_\-]*?)sitemap([a-z0-9_\-]*)?\.xml
```
For server-level caching, or any plugin not listed, contact the host or the plugin developer.

**Troubleshooting table**

| Symptom | Cause | Fix |
|---|---|---|
| "XML declaration allowed only at the start of the document" / "XML or text declaration not at start of entity" | Output was sent before the sitemap, usually a plugin or theme PHP file with a closing `?>` followed by blank lines | Deactivate plugins one at a time; switch to a default theme (Twenty Twenty etc.); remove the closing `?>` or the whitespace; never modify core. AIOSEO cannot fix this itself |
| Sitemap returns 404 | Enable Sitemap is off; NGINX rewrite missing (pre-4.2.1); News sitemap has no posts from the last 48 h | Turn on Enable Sitemap; add the NGINX rules; for News, this is normal |
| `/sitemap.xml` redirects to `/sitemap_index.xml` | Leftover rewrite rules from a competing SEO plugin | Remove that plugin's rules and add AIOSEO's NGINX rules |
| GSC shows "Couldn't fetch" | Usually a transient fetch failure; property mismatch (www/non-www, http/https); everything noindexed so the sitemap is empty; a cached sitemap | (1) Open `/sitemap.xml` in an incognito window. (2) Make sure the GSC property exactly matches Settings > General > Site Address (URL). (3) Check Search Appearance > Content Types > Show in Search Results = Yes. (4) Exclude the sitemap from caching and clear caches. (5) Run the sitemap URL through the Rich Results Test: an overall "Crawl failed" is expected, but Crawl allowed must be Yes, Page fetch must be Successful, and the response must be 200. (6) Resubmit in GSC Indexing > Sitemaps, submitting the same URL twice without refreshing. (7) Submit `https://yourdomain.com/sitemap.xml?test=1` to bypass Google's cached copy |

---

## Robots.txt Editor

Sources: https://aioseo.com/docs/using-the-robots-txt-tool-in-all-in-one-seo/, https://aioseo.com/docs/robots-txt-editor-for-multisite-networks/, https://aioseo.com/docs/nginx-rewrite-rules-for-robots-txt/, https://aioseo.com/docs/resolving-indexed-though-blocked-by-robots-txt-in-google-search-console/

- Tier: Lite. Path: **All in One SEO > Tools > Robots.txt Editor** (the first tab of Tools).
- AIOSEO does not generate its own robots.txt. It modifies WordPress's dynamic robots.txt through the WordPress **`robots_txt` filter**. No physical file exists; the rules are stored in the database. To remove the WordPress default rules (which disallow core WordPress files), use the `robots_txt` filter yourself.
- **Enable Custom Robots.txt** toggle. AIOSEO says it is not needed unless you have a specific rule to add, because the WordPress default suits "99%" of sites.
- **Custom Robots.txt Preview** at the bottom; **Open Robots.txt** button.
- **Rule builder:** Add Rule, then fill:
  - **User Agent**: `*` for all, or e.g. `Googlebot`.
  - **Directive**: **Allow**, **Block** (written as Disallow), **Clean-param** (Yandex only) or **Crawl-delay** (Bing, Yahoo and Yandex only; per the doc, Google's crawl rate is set in GSC [that GSC crawl-rate tool was retired in Jan 2024]).
  - **Value**: a directory or file path. The `*` wildcard is allowed, e.g. `/wp-content/backup-*`.
- Save Changes. Edit a rule in place; delete it with the trash icon; reorder by drag and drop (order matters).
- **Import** button opens an Import Robots.txt window: **Import from URL**, or **Paste Robots.txt** text.
- Advanced rules supported: `$` end anchor (`/search$`), path prefixes (`/search/`) and query parameters (`/?display=wide`).
- **Block AI Crawlers**: pick individual known crawlers (AI bots and Google AdsBot) or **All AI Crawlers**.
- **Block Crawling of Internal Site Search URLs**: adds rules that stop crawling of search result URLs.
- Size: Google's proposed maximum is 512 KB [Google's documented limit is 500 KiB]; keep the file small.
- **NGINX:** rewrite rules are normally unnecessary. If `/robots.txt` returns 404 on NGINX, ask the host to make sure this rule exists:
  `rewrite ^/robots.txt$ /index.php?aioseo_robots_path=root;`
- **Multisite:** Network Admin > All in One SEO > **Network Tools** has the same editor. Rules set at network level apply to every site and cannot be overridden per site. A **site selector** dropdown edits an individual subsite's rules (search by domain). The doc says the network editor works **only for subdomain networks, not subdirectory networks**.
- **Noindex vs robots.txt (AIOSEO recommends):** robots.txt controls crawling, not indexing. Do not Disallow a page that also carries noindex, because Google cannot crawl it to see the tag. Use robots.txt for files that cannot carry meta tags (PDFs, images, feeds). Use AIOSEO Settings > Advanced > Robots Settings > turn off Use Default Settings > tick **No Index** for pages.

---

## Webmaster Tools verification

Sources: https://aioseo.com/docs/how-to-verify-your-site-with-google-search-console/ (MODIFIED 2026-10-06), https://aioseo.com/docs/how-to-verify-your-site-with-bing-webmaster-tools/ (MODIFIED 2026-10-06), https://aioseo.com/docs/how-to-verify-your-site-with-yandex-webmaster-tools/, https://aioseo.com/docs/baidu-webmaster-tools-verification/, https://aioseo.com/docs/how-to-verify-your-site-with-microsoft-clarity/, https://aioseo.com/docs/miscellaneous-site-verification/, https://aioseo.com/docs/integrating-with-indexnow-to-instantly-re-index-your-content/

- Path: **All in One SEO > General Settings > Webmaster Tools** tab. Each service is a clickable block. Save Changes after editing.
- You only verify once per site.
- The property URL must match the site exactly (https or not, www or not).

| Block | Field | How |
|---|---|---|
| Google Search Console | **Connect to Google Search Console** button (OAuth) | Choose the Google account > "Sign in to All in One SEO" > Continue > tick **Select all** permissions > Continue > **Complete Connection**. This adds and verifies the site and auto-submits the AIOSEO sitemaps. **Disconnect** and **Reconnect** buttons are on the block |
| Bing Webmaster Tools | **Bing Verification Code** | In Bing: Add a Site > "Copy and paste a <meta> tag in your default webpage". Paste the code, Save, then click Verify in Bing. Alternatively, import the site from GSC into Bing with no verification |
| Yandex Webmaster Tools | **Yandex Verification Code** | Yandex: My sites > Add site > "Verify rights to" > copy the meta code > paste > Save > **Check** |
| Baidu Webmaster Tools | **Baidu Verification Code** | Needs a Chinese phone number for the Baidu account. Enter domain and protocol > Next (下一步) > pick an industry > copy the code under "HTML tag" (HTML 标签验证) > paste > back in Baidu click Complete Verification (完成验证) |
| Microsoft Clarity | **Clarity Project ID** | Clarity: create a project (name, URL, category) > Overview > copy the Project ID > paste. This adds the Clarity tracking, which AIOSEO calls "verification" |
| Pinterest | listed as supported (no detail in the docs) | |
| IndexNow | IndexNow API key (view, change or regenerate) | see IndexNow below |
| **Miscellaneous Verification** | free HTML field at the bottom of the screen | paste any third-party verification meta tag |

- An alternative GSC verification needs no AIOSEO change: if the GA or GTM tag is already on the site, use GSC's URL prefix > Verify ownership > Google Analytics (or Google Tag Manager) > Verify.
- The docs suggest using a separate business Google or Microsoft account rather than a personal one.

---

## IndexNow

Source: https://aioseo.com/docs/integrating-with-indexnow-to-instantly-re-index-your-content/

- Added in v4.1.7. Tier: **Basic plan or above**.
- Activate in **All in One SEO > Feature Manager > IndexNow**. It configures itself; nothing else needs setting.
- AIOSEO pings the IndexNow API whenever content is published or updated.
- The doc says only Bing and Yandex support it. [Seznam, Naver and Yep also participate. Google does not support IndexNow, so this does not speed up Google indexing.]
- **Verify it works:** General Settings > Webmaster Tools > IndexNow block, copy the API key, then open `https://yoursite.com/<key>.txt`. The key text should display.
- To change the key: the same block lets you update or regenerate it, then Save Changes.

---

## Google Analytics / Google Tag Manager (deprecated)

Sources: https://aioseo.com/docs/how-to-connect-your-site-with-google-analytics/, https://aioseo.com/docs/how-to-connect-your-site-with-google-tag-manager/

- The GA features were **deprecated in v4.5.1** because Google sunset GA v3 (Universal Analytics). The GTM features are also deprecated.
- AIOSEO points users to **MonsterInsights** (free and premium; supports GA4) through a **Get Started** button in the Google Analytics section. AIOSEO has no GA4 tag field of its own.

---
