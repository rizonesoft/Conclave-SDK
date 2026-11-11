# Redirects and links

Redirection Manager, 404 handling, full site redirects, .htaccess, Link Assistant, Broken Link Checker.

Built from a full read of aioseo.com/docs, /faqs and /blog on 2026-10-11 (AIOSEO Pro 5.0.2 on aioseo.com). Each section lists its source pages. Text in [brackets] is a reviewer note where the vendor advice looks dated or conflicts with Google guidance. UI labels move between versions: confirm on the live site before giving click paths as fact. Unresolved points are in open-questions.md.

## Contents

- Redirection Manager: overview, tiers and adding redirects
- Redirection Manager: automatic redirects, deletion prompts and 404 handling
- Redirection Manager: settings, method, logging, caching, headers, full site, import/export
- .htaccess Editor
- Link Assistant
- Broken Link Checker (separate plugin)

## Redirection Manager: overview, tiers and adding redirects

Sources: https://aioseo.com/docs/how-to-redirect-a-post-or-page-in-all-in-one-seo/, https://aioseo.com/docs/how-to-redirect-multiple-urls-to-the-same-destination/, https://aioseo.com/docs/choosing-which-redirect-type-to-use/, https://aioseo.com/docs/creating-a-pass-through-redirect/, https://aioseo.com/docs/ignoring-case-sensitivity-in-redirects/, https://aioseo.com/docs/ignoring-the-trailing-slash-in-redirects/, https://aioseo.com/docs/using-query-parameters-with-redirects/, https://aioseo.com/docs/redirect-manager-regex/, https://aioseo.com/docs/how-to-schedule-a-redirect-in-all-in-one-seo/

- Tier: **Redirection Manager is Basic plan or above**; "some advanced features" need Pro or above. Pro or above is named for Full Site Redirect, Log Settings, Advanced 404 Settings and child-to-parent 404 redirects. (The GSC troubleshooting pages say "Pro plan or above" for the whole Redirection Manager, which conflicts.)
- Path: **All in One SEO > Redirects**. Tabs: Redirects, Logs (Redirect Hits / 404 Hits), Full Site Redirect, HTTP Headers, Import / Export, Settings.
- You can also add redirects from the **Redirects tab in AIOSEO Settings** on the Edit Post screen.

**Add New Redirect form**
- **Source URL**: must be relative (no domain). Use the **add extra source URL's** link to send several sources to one target; the button then reads **Add Redirects**.
- **Target URL**: relative or absolute. Typing a post title, slug or ID shows a dropdown of matches.
- **Comment**: optional note.
- **Redirect Type** dropdown.
- **Settings (gear) icon** inside the Source URL field opens three checkboxes: **Ignore Slash**, **Ignore Case**, **Regex**.
- **Advanced Settings** toggle reveals: Redirect Type, **Query Parameters**, and **Custom Rules** (the **Add Custom Rules** link).
- Click **Add Redirect**.

**Redirects table**
- **Enabled** toggle disables a redirect without deleting it; **Hits** column.
- Row hover actions: **Check Redirect**, **Edit**, **Delete**.
- **Groups** filter, e.g. "Modified Post" for automatic redirects.

**Redirect types**
- Common: **301 Moved Permanently** for deleted or moved content; **307 Temporary Redirect** for temporary moves.
- Advanced:
  - 302 Found (rare; AIOSEO prefers 301 or 307)
  - 303 See Other
  - 304 Not Modified
  - 308 Permanent Redirect (AIOSEO prefers 301)
  - **Pass through**: keeps the source URL in the address bar and loads the target's content. External targets are allowed.
- Client errors: 400, 401, 403, 404, **410 Gone**, 418, 451.
- Server errors: 500, 501, 502, 503, 504, 505.
- Default type: Redirects > Settings > **Redirect Defaults** > Redirect Type. Individual redirects can override it.

**Query Parameters** (per redirect in Advanced Settings; the default is set in Settings > Redirect Defaults > Query Parameters)

| Option | Behaviour |
|---|---|
| Ignore all parameters | Redirects whatever parameters are present |
| Exact match all parameters in any order | Matches only if the parameters given in the Source URL all match, in any order |
| Ignore & pass parameters to the target | Matches regardless of parameters and appends them to the target (keeps UTMs) |
| Ignore all parameters except UTM | Ignores everything except `utm_*` |

**Ignore Case / Ignore Slash**
- Per redirect: the gear icon checkboxes.
- Globally: Settings > Redirect Defaults > **Ignore Case** and **Ignore Slash** toggles, which apply to the source URL.

**Regex** (the Regex checkbox; applies to both Source and Target). Examples:
- `^/docs/developer/(.*)` > `https://newdomain.com/$1` (directory to a new domain)
- `^/(.*?).html$` > `/$1/` (strip .html and add a trailing slash)
- `^/live/news/[0-9]+-(.+)` > `/news/$1/` (drop a directory and a numeric prefix)
- `^/old/(.*)` > `/new/$1`
- `^/docs/(.*)` > `/knowledge-base/$1`

**Scheduling**
- Only possible when adding a new redirect.
- Add Custom Rules > **Select Rule** = **Schedule** > **Start Date** / **End Date** (date and time). A blank End Date means no end.
- Also available on the Edit Post screen's Redirects tab.

---

## Redirection Manager: automatic redirects, deletion prompts and 404 handling

Sources: https://aioseo.com/docs/automatic-redirects-when-urls-change-in-content/, https://aioseo.com/docs/automatic-redirects-when-you-delete-content/, https://aioseo.com/docs/automatic-redirects-when-changing-the-post-slug/, https://aioseo.com/docs/adding-a-redirect-when-you-delete-content/, https://aioseo.com/docs/redirecting-404-content-not-found-using-all-in-one-seo/, https://aioseo.com/docs/logging-404-errors-in-all-in-one-seo/

- **Settings > Automatic Redirects:**
  - **Include All Post Types** toggle, or tick individual types. When a published URL changes, AIOSEO creates a redirect automatically in group **Modified Post**.
  - **Monitor Trashed & Deleted Posts** toggle: when content is deleted, AIOSEO creates a redirect to the **homepage** that starts **disabled**. Edit its Target URL, then switch it on in the Enabled column. It also lands in group Modified Post.
- **Slug-change prompt:** changing a slug on the edit screen shows a notice with an **Add Redirect to Improve SEO** button. The popup is pre-filled with source and target; choose 301 or 307. Custom Rules are under Advanced Settings.
- **Trash prompt:** trashing content shows an **Add Redirect to improve SEO** link. Source is pre-filled; Target defaults to `/` (homepage). Types offered: 301, 307, 410. Optional Comment; Add Custom Rules link.
- **Advanced 404 Settings** (Pro+): Settings > Advanced 404 Settings toggle.
  - **Enable Default 404 Redirect**: send every 404 to the Home Page or a Custom URL (relative or full).
  - **Redirect 404 Errors from Child to Parent**: hierarchical types go to the parent page; posts go to their category.
  - **Redirect 404 Errors for WooCommerce Products & Categories**: a product goes to its category.
  - **Redirect 404 Errors Based on Slug**: looks the slug up in the database; useful after permalink changes or moving content between post types.
  - AIOSEO warns that redirecting 404s may harm SEO and recommends leaving these off and building a custom 404 page instead. [Google treats mass redirects to the homepage as soft 404s, so the warning is sound.]
- **404 logs** (Log Settings needs Pro+): Settings > Log Settings > **Log 404 Errors** plus a retention dropdown.
  - View under Logs > **404 Hits**: URL, Hits, Last Accessed; **Add Redirect** link; Additional info icon; Delete icon; Search.
  - **Clear 404 Logs** button is in Settings.

---

## Redirection Manager: settings, method, logging, caching, headers, full site, import/export

Sources: https://aioseo.com/docs/selecting-the-redirect-method-in-redirects/, https://aioseo.com/docs/redirect-manager-configuration-reload/, https://aioseo.com/docs/redirect-manager-unknown-web-server/, https://aioseo.com/docs/caching-of-redirects-in-the-browser/, https://aioseo.com/docs/logging-redirects-in-all-in-one-seo/, https://aioseo.com/docs/redirect-gdpr-privacy-information/, https://aioseo.com/docs/setting-the-http-site-and-redirect-headers-in-all-in-one-seo/ (published 2025-12-02), https://aioseo.com/docs/full-site-redirects/, https://aioseo.com/docs/exporting-and-importing-redirects/, https://aioseo.com/docs/importing-redirects-from-other-plugins/, https://aioseo.com/docs/redirection-manager-custom-rules/ (MODIFIED 2026-08-27)

**Redirect Method** (first item on the Settings tab)
- **PHP**: the default; needs no server configuration; recommended for most users.
- **Web Server**: faster. You export a server config file and include it in the Apache vhost, `nginx.conf` or LiteSpeed vhost, then restart the server.
- Web Server limits: no hit counting, and no Logs tab.
- When Web Server is selected, every add, edit or delete regenerates the redirects file and adds a `test-redirect-{$random-hash}` entry. A warning shows ("Your redirect settings have been updated. In order for them to work properly you may need to reload your server configuration.") until the server reloads its config and the test redirect resolves. Ask the host to reload Apache or NGINX.
- Warning "We cannot detect your web server": only Apache and NGINX are detected. Switch to **PHP** and Save Changes.

**HTTP Cache Header**
- Toggle plus a cache duration dropdown; caches redirects in the visitor's browser.
- Cuts server load but hides cached hits from the logs.
- AIOSEO recommends enabling it if redirects will not change.

**Log Settings** (Pro+)

| Setting | Notes |
|---|---|
| Log Redirect Hits | plus a retention dropdown; **Clear Redirect Logs** button |
| Log 404 Errors | plus a retention dropdown; **Clear 404 Logs** button |
| Log External Redirects | logs redirects not made by AIOSEO (other plugins, WordPress) |
| Log HTTP Header Information | off by default; adds browser type, version and language. Cookies are never logged |
| Log IP Addresses | off, **Full Logging**, or **Anonymize IP** (sets the last octet to 0) |

- By default, a log entry holds only the date and time and the visitor's IP.
- View under Logs > **Redirect Hits** (URL, Hits, Last Accessed, Additional info, Delete, Search).
- For GDPR, turn the toggles off or anonymize IPs.
- AIOSEO recommends removing unused old redirects to avoid conflicts and loops.

**Custom Rules** (Advanced Settings > Add Custom Rule). Multiple rules combine as **AND**.

| Rule | Match on |
|---|---|
| Login Status | Logged In / Logged Out |
| WordPress User Roles | one or more roles (OR among the roles) |
| Referrer | value, with a Regex toggle |
| User Agent | value or regex; presets **Mobile** (`iPad\|iPod\|iPhone\|Android\|BlackBerry\|SymbianOS\|SCH-Md+\|Opera Mini\|Windows CE\|Nokia\|SonyEricsson\|webOS\|PalmOS`), **Feeds** (`Bloglines\|feed\|rss`), **Libraries** (`cURL\|Java\|libwww-perl\|PHP\|urllib`) |
| Cookie | regex option |
| IP Address | regex option |
| Server | regex option |
| HTTP Header | regex option |
| WordPress Filter | named filter; returns false unless you hook it |
| Locale | regex option |
| Schedule | Start/End date (see Scheduling) |

WordPress Filter example. The doc names the filter `aioseo_custom_filter`; the filter name you enter in the rule is the one executed:
```php
add_filter( 'aioseo_custom_filter', function ( $match, $url, $redirect ) {
    if ( ! empty( $_GET['do-redirect'] ) ) { $match = true; }
    return $match;
}, 10, 3 );
```

**HTTP Headers tab**
- Location: **Site** (sitewide, including redirects) or **Redirect** (redirects only).
- **Header** dropdown (or **Custom Header**) plus **Value**; **Add Header**; trash icon to delete.
- **Add Security Presets** and **Add CORS Presets** buttons.

**Full Site Redirect tab** (Pro+)
- **Relocate Site** toggle plus "Your new site address" (no `https://`). wp-admin, wp-login, wp-json, wp-content and wp-includes are not redirected. Turning it on disables Site Aliases and Canonical Settings.
- **Site Aliases**: extra domains or subdomains redirected to this site, using Add Aliased Domain and the trash icon. Aliases redirect everything, including login and admin. DNS and the server must route those domains to this install.
- **Canonical Settings** toggle:
  - **Redirect from HTTP to HTTPS**: make sure HTTPS works first.
  - **Preferred domain**: Leave domain as-is / Add www to domain / Remove www from domain.
  - After either change, update Settings > General > Site Address (URL). Test SSL with sslshopper.com or ssllabs.com.

**Import / Export tab**
- **Export Redirects** checkboxes: Export All Redirects, Manual Redirects, Modified Posts (needs Automatic Redirects), 404 Redirects (needs 404 Logs).
- Export formats: **Complete Data (JSON)** to re-import on another site; **Apache Redirects (.htaccess)**; **NGINX Redirects (.nginx)**.
- Import from an AIOSEO JSON file, or from CSV (sample CSV via the "click here" link), using Choose a File > Import.
- **Export Redirect Logs** and **Export 404 Logs** buttons.
- **Import Redirects From Other Plugins**: pick the plugin and click Import. Ignore Case, Ignore Slash and Regex options carry over where possible. The supported list is not in the docs.

---

## .htaccess Editor

Source: https://aioseo.com/docs/editing-the-htaccess-file-using-all-in-one-seo/

- Path: **Tools > .htaccess Editor** tab; Save Changes.
- The tab is visible **only on Apache**.
- [A bad edit can take the site down with a 500 error. Back up the file first.]

---

## Link Assistant

Sources: https://aioseo.com/docs/link-assistant/, https://aioseo.com/docs/introduction-to-link-assistant/, https://aioseo.com/docs/link-assistant-settings/, https://aioseo.com/docs/internal-links-in-the-links-report-in-link-assistant/, https://aioseo.com/docs/external-links-in-the-links-report-in-link-assistant/, https://aioseo.com/docs/affiliate-links-in-the-links-report-in-link-assistant/, https://aioseo.com/docs/link-suggestions-in-the-links-report-in-link-assistant/, https://aioseo.com/docs/using-the-domains-report-in-link-assistant/, https://aioseo.com/docs/cornerstone-content/

- Tier: **Pro plan or above** (an addon included with Pro and Elite). Introduced in 4.1.6.
- Path: All in One SEO > **Link Assistant**. Tabs: Overview, Links Report, Domains Report, Settings.
- Limitation: works best with **English content and the Block Editor**; page builder and multi-language support is "future".
- **Overview:**
  - Posts Crawled, with a scan % indicator. The scan keeps running in the background even after you log out.
  - Orphaned Posts (no inbound internal links); External Links; Internal Links; Affiliate Links.
  - Internal vs External vs Affiliate Links chart.
  - Most Linked to Domains ("See a Full Domains Report").
  - Linking Opportunities ("See All Linking Opportunities").
- **Links Report:**
  - Columns: Post Title, Publish Date, Internal Links, Affiliate Links, External Links, Link Suggestions.
  - Filters: **Linking Opportunities**, **Orphaned Posts**, **All Post Types** (picking Post adds a category filter).
  - 10 rows per page. The expand arrow opens tabs for each post.
  - **Inbound Internal**: Post Title and Phrase; hover for View/Edit Post; a delete icon removes only the link, not the text; Delete All Inbound Internal Links; Refresh; Inbound Link Suggestions button.
  - **Outbound Internal**: the same, with Post Title / URL.
  - **External**: Phrase; delete icon; Delete All External Links; Refresh.
  - **Affiliate**: links matching Affiliate Link Prefix; delete icon; Delete All Affiliate Links.
  - More than 5 items shows a "See All ..." link.
- **Link Suggestions:**
  - Tabs: **Inbound Internal Suggestions** and **Outbound Internal Suggestions**.
  - **Add Link**, one at a time or with checkboxes > Bulk Actions > Add Link > Apply.
  - "more phrases" offers radio buttons to choose a different phrase.
  - **Edit**: pencil icon > edit panel (bold, italic, underline, link). Select different text, click the link button, Save Changes, then Add Link. The target cannot be changed, only which text carries the link.
  - **Dismiss**: hover > Dismiss Suggestion, or Bulk Actions > Dismiss, or Dismiss All Inbound/Outbound Internal Suggestions. Undismissing requires Support.
  - **Refresh** button; scans can take a long time on big sites.
  - **How it works:** a phrase in your content matches words in another post's title (word order does not matter), e.g. product "Apple iPhone 13 Pro". Words in Words to Ignore are skipped.
- **Domains Report:**
  - Columns: Domain, Posts, Links. Expand to see Post Title, Phrases with Links, Publish Date, and "more phrases".
  - Per-row delete; hover a domain > **Delete All Links** removes every link to that domain sitewide.
  - 5 per page.
- **Settings:**

| Setting | Notes |
|---|---|
| Post Types | Include All Post Types or a selection |
| Post Statuses | Include All Post Statuses or select (Draft, Scheduled, Pending, Published, ...) |
| Number of Sentences to Skip at Beginning | e.g. 2 means no suggestions in the first two sentences |
| Affiliate Link Prefix | multiple; path form `/refer/` or domain form `https://amazn.to` |
| Exclude Posts / Pages | by name, slug or ID; excluded from scanning and suggestions |
| Words to Ignore | one word per line; pre-filled list |

- **Cornerstone Content** (Pro+): Edit Post > AIOSEO Settings > **Advanced** tab > **Cornerstone Content** toggle > Update. Cornerstone targets show an icon in internal link suggestions and should be prioritised. Block Editor and Classic Editor only.
- The intro page makes marketing claims ("internal linking can boost traffic by 40%", "external links are the third most important ranking factor", "outbound links share your page ranking"). [Unsupported by Google. Treat them as marketing. Outbound links do not "leak" rank in any way worth managing; qualify paid and affiliate links with rel="sponsored".]

---

## Broken Link Checker (separate plugin)

Sources: https://aioseo.com/docs/using-broken-link-checker-to-find-and-fix-broken-links-and-images/, https://aioseo.com/docs/do-i-need-a-license-key-to-use-broken-link-checker/

- A standalone, free plugin, "Broken Link Checker by AIOSEO" (Plugins > Add New). It adds a **Broken Links** menu.
- It uses **no licence key**. It connects to an aioseo.com account; even Pro account holders must add a free or paid BLC plan.
- **Free plan:** 250 internal and external links scanned per month. Signing up asks for payment details. Sites with more than 250 links are **automatically upgraded to a paid monthly subscription**. Paid tiers: Starter, Plus, Premium, Elite (more links, external checking, support). Upgrade through the "upgrading to Pro" link.
- Scanning runs on AIOSEO's servers: daily per the "Checking" section, with a rescan every three days per the same page (inconsistent).
- **Broken Links tab:**
  - Columns: URL, Post Title / Anchor, Status; plus quota used.
  - URL hover actions: **Edit URL**, **Unlink**, **Recheck**, **Add Redirect** (needs AIOSEO with Redirects), **Dismiss**.
  - Post hover actions: Edit Post, View Post, Delete.
  - An Information icon gives details.
- **Settings > Link Tweaks:**
  - **Stop search engines from following broken links** (adds `rel="nofollow"`).
  - **Don't update the modified date for a page/post when a link is updated**.
  - **Highlight Broken Links** (a red wavy underline on the front end, visible to Editors and Admins only).
- **Advanced Settings:**
  - Post Types; Post Statuses; Exclude Posts (name or ID).
  - **Exclude Domains**: one per line, without https or www, e.g. `facebook.com`.
  - **Uninstall Broken Link Checker**: remove all data on delete.
- Limitation: detects links inside page builders but **cannot edit or unlink** them; works best in the Block Editor.

---
