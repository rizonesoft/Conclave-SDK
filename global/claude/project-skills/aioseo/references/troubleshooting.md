# Troubleshooting

Generic procedure and symptom -> cause -> fix tables.

Built from a full read of aioseo.com/docs, /faqs and /blog on 2026-10-11 (AIOSEO Pro 5.0.2 on aioseo.com). Each section lists its source pages. Text in [brackets] is a reviewer note where the vendor advice looks dated or conflicts with Google guidance. UI labels move between versions: confirm on the live site before giving click paths as fact. Unresolved points are in open-questions.md.

## Contents

- Generic troubleshooting procedure
- Troubleshooting table

## Generic troubleshooting procedure
Sources: https://aioseo.com/docs/how-to-troubleshoot-issues-with-all-in-one-seo-pack/, https://aioseo.com/docs/how-to-fix-javascript-errors/, https://aioseo.com/docs/how-to-enable-debugging-in-wordpress/, https://aioseo.com/docs/how-to-open-the-browser-error-console/, https://aioseo.com/docs/browser-support-policy/

**Standard steps, in AIOSEO's order**
1. Clear all caches and deactivate caching/performance plugins, including server caches (Varnish) and CDNs (Cloudflare). Clear the browser cache after every later step.
2. Take a full backup of files and database.
3. Deactivate and reactivate AIOSEO.
4. Deactivate every plugin except AIOSEO. If the problem goes away, reactivate them one at a time until it returns.
5. If it persists, switch to a default theme (Twenty Twenty / Twenty Twenty-One).
6. Enable WP_DEBUG and read the log.
7. Check the browser console for red errors.
8. As a last resort, export your settings, reset to defaults and test.

**Health Check & Troubleshooting plugin** (wordpress.org/plugins/health-check)
- Click **Troubleshoot** under All in One SEO in the plugin list. This disables the other plugins and switches to a default theme **for your user only**, so visitors are unaffected.
- Reproduce the problem, re-enable the theme, then re-enable plugins one at a time.
- Deactivate and delete the Health Check plugin when finished.

**JavaScript errors checklist**
- Update AIOSEO and all addons.
- Use a supported browser.
- Clear the browser cache and every site, server and CDN cache, then hard-reload.
- **Disable JS caching and minification** (performance plugins).
- Test in an Incognito/Private window.
- Deactivate and reactivate AIOSEO and its addons.
- Run the Health Check plugin.

**Debug logging** (in `wp-config.php`, before `/* That's all, stop editing! */`):
```php
define( 'WP_DEBUG', true );
define( 'WP_DEBUG_LOG', true );        // writes /wp-content/debug.log
define( 'WP_DEBUG_DISPLAY', false );
@ini_set( 'display_errors', 0 );
define( 'SCRIPT_DEBUG', true );        // only if modifying core JS/CSS
```
Reproduce the issue, then read `/wp-content/debug.log`.

**Browser console:** Ctrl+Shift+I (Windows), Cmd+Option+I (Mac), F12, or right-click » Inspect, then open the Console tab. Hard-reload with Ctrl/Cmd+Shift+R; errors show in red.

**Supported admin browsers:** the latest 2 versions of Chrome, Firefox, Safari, Edge and Opera; Android Chrome (latest 2); iOS Safari and Chrome (latest 2); plus any desktop browser with more than 1% usage on caniuse.

## Troubleshooting table

### Admin UI, saving settings, REST API
| Symptom | Cause | Fix |
|---|---|---|
| Red notice at the top of AIOSEO screens saying the REST API is blocked; settings won't save | A security plugin or CDN blocks the WP REST API, or allows it only for some users. AIOSEO uses the REST API only when you change settings in wp-admin. | Deactivate plugins one at a time until the notice clears. If none is responsible, switch to Twenty Twenty. If on Cloudflare, see the next row. |
| Can't save settings or enter the Pro licence key; site is on Cloudflare | A Cloudflare WAF, managed rules or rate limiting blocks `/wp-json/aioseo/` | Cloudflare dashboard » Domains » Overview » the domain » **Security » Security rules** » Create » **Custom rules**. Condition: Field **URI Path**, Operator **starts with**, Value `/wp-json/aioseo/` (optionally AND **Hostname equals** `mydomain.com`). Action **Skip**: tick All remaining custom rules, WAF Managed Rules (Cloudflare Managed Ruleset, OWASP), Rate limiting rules, and optionally User Agent Blocking. **Put the Skip rule above any block/challenge rules**, because custom rules are evaluated top to bottom and stop at the first match. Click **Deploy**. The full Skip options need Cloudflare Pro or higher; Free plans have fewer. (Doc MODIFIED 2026-08-14.) |
| Notice that your user role can't edit certain fields | The user lacks the WordPress `unfiltered_html` capability, which AIOSEO requires for some fields as a security measure | Grant `unfiltered_html` to the role or use another account. Note: on multisite only Super Admins have it by default; it can also be disabled with `DISALLOW_UNFILTERED_HTML`. |
| AIOSEO Details column on Posts/Pages shows a pulsing circle and never loads (the column shows TruSEO score, Headline Analyzer score, SEO Title, Meta Description, Index Status, Link Assistant details) | A plugin or theme conflict, or a JS error | Run Health Check Troubleshoot on AIOSEO, reproduce, re-enable the theme, then plugins one by one. Check the browser console. Send the results to support through the "Basic question" form. (Doc PUBLISHED 2025-10-13.) |
| JS errors or broken AIOSEO screens | Stale cache or minified JS; outdated plugin; unsupported browser; conflict | Use the JS checklist above. |

### Activation, install, fatal errors, environment
| Symptom | Cause | Fix |
|---|---|---|
| "There has been a critical error on your website", or a fatal error about missing table `wp_actionscheduler_actions`, after activating or upgrading to v4.0.0+ | Since v4.0.0 AIOSEO uses the **Action Scheduler** library for cron. Another plugin bundles an older Action Scheduler, or the DB user can't create tables. | 1) Rename `/wp-content/plugins/all-in-one-seo-pack-pro` (or `all-in-one-seo-pack` for Lite) by FTP or cPanel to deactivate it. 2) Find `DB_USER` in `wp-config.php` and confirm with the host that the user has CREATE TABLE rights. 3) Install the standalone Action Scheduler plugin ("Source code (zip)" from its releases page). If activating it gives the same fatal error, ask the host to set the Action Scheduler tables' charset/collation to `utf8mb4_unicode_520_ci`. 4) Open Tools » **Scheduled Actions** and wait until "Action Scheduler migration in progress…" and "It appears one or more database tables were missing…" both disappear. 5) Rename the folder back and reactivate AIOSEO, then delete the Action Scheduler plugin. |
| "The uploaded file exceeds the upload_max_filesize directive" when installing Pro | The host's PHP upload limit is too low. The Pro zip is about 6 MB. | Ask the host to raise `upload_max_filesize` to at least **7 MB**. Otherwise install by FTP: unzip and upload the folder (doc calls it `all-in-one-seo-pro`) to `/wp-content/plugins/`, then activate it under Plugins. |
| Memory exhaustion errors | PHP memory limit too low | In `wp-config.php`: `define('WP_MEMORY_LIMIT','512M');` (front end) and `define('WP_MAX_MEMORY_LIMIT','512M');` (admin). Or in php.ini: `memory_limit = 512M`. Or in .htaccess: `php_value memory_limit 512M`. Otherwise ask the host. |
| Dashboard notice linking to "Supported PHP Versions" | PHP is outdated | Ask the host to upgrade to PHP **8.0+**. AIOSEO currently works on PHP **7.1+**. Support was dropped for 5.2/5.3 (Nov 2020), 5.4 (Aug 2022), 5.6 (Aug 2023) and **7.0 (May 2025)**. |
| Dashboard notice linking to "Update WordPress" | WordPress is outdated | Update to the latest version, "or at least WordPress 7.x" (doc MODIFIED 2026-08-21). Support for **5.9 and below** ends at the start of 2026. Back up first (Duplicator is suggested). |
| Licence won't activate; URL-related oddities | Mismatched WordPress Address / Site Address, or the host rewrites them | Hard-code WP_HOME and WP_SITEURL (see licensing-account.md, "Sites, activations, staging, client sites"). |
| Staging site uses up an activation | The hostname doesn't match the patterns the License Manager detects | Use `dev.`, `staging.` or `test.` subdomains, or contact support. |
| "Blank Title Formats Have Been Detected" notice | In v3.x the Title Format fields were emptied, so AIOSEO output no titles and WordPress generated them. The v4 migration carries over the empty formats, so per-post v3 SEO titles were not migrated. | Go to **All in One SEO » Search Appearance » Content Types**, open the post type (e.g. Pages), put smart tags in the **Title** field and click **Save Changes**. Set per-post titles in **AIOSEO Details** (now called AIOSEO Settings) in the editor. To recover v3 titles, contact support. |
| Need to install a plugin manually or edit files | — | FTP/SFTP with FileZilla: Host, Username, Password, Port (21 for FTP, 22 for SFTP) » Quickconnect » go to e.g. `public_html` » upload. |

### Sitemaps
| Symptom | Cause | Fix |
|---|---|---|
| Sitemap returns 404 | Sitemap disabled | **All in One SEO » Sitemaps** » the sitemap's tab » **Enable Sitemap** toggle On » **Open Sitemap**. If you use the Video or News sitemap, the main XML Sitemap should also be enabled. |
| Sitemap 404 or empty | No published content in the included Post Types/Taxonomies; **News Sitemap only includes content from the last 48 hours** | Publish content and check the Post Types and Taxonomies settings. |
| Content missing from the sitemap | Content is noindexed: **Show in Search Results = No** under Search Appearance, or No Index in Robots Meta (global or per post). Noindexed content is always excluded. | Remove the noindex if the content should be listed. |
| 404 on NGINX | Rewrite rules missing | Not needed on **v4.2.1+**. On older versions, add AIOSEO's NGINX rewrite rules. |
| 404 with Plain permalinks | On **v4.2.2 or lower**, sitemaps need pretty permalinks | Settings » Permalinks » anything but Plain. |
| 404 at /sitemap.xml although the sitemap is enabled | The sitemap filename was changed in the DB | **All in One SEO » Tools » Import / Export** » Export Settings » tick **Sitemaps** » **Export Settings**. In `aioseo-export-settings.json`, search for `"filename"`. Expected values are `sitemap` (XML) and `video-sitemap` (Video). Edit the value and re-import. |
| 404 or broken sitemap behind a CDN or cache | A CDN plugin or service rewrites or caches XML/XSL URLs | Deactivate it to test, then exclude XML and XSL URLs from caching or CDN rewriting (ask the plugin vendor or host). |
| Sitemap, robots.txt or llms.txt 404, stale or blocked after moving DNS to Cloudflare | Cloudflare cached an old 404 or HTML page, a cache rule caches XML/XSL, or Bot Fight Mode, AI bot blocking or a WAF rule challenges crawlers | Run `scripts/check-seo-output.mjs <url> --site` and read `server` and `cf-cache-status` (HIT on a 404 means a cached error). Purge the cache for `/sitemap*.xml`, `/*.xsl`, `/robots.txt` and `/llms*.txt`; add a Cache Rule that bypasses cache for those paths; check Security events for blocked Googlebot or Bingbot; confirm the origin still serves the sitemap with Cloudflare paused (development mode). If settings also fail to save, add the `/wp-json/aioseo/` Skip rule below. Cloudflare changes are site changes: get approval and note the rollback. |
| "Is my sitemap a file?" | — | No. All sitemaps are generated dynamically and there is no physical file. Page source shows the green line "This sitemap was dynamically generated". The "Dynamically Generate" setting was removed in v4.0. |

### Search appearance, indexing, display in Google
| Symptom | Cause | Fix |
|---|---|---|
| Google shows a different title/description from the one set | Google rewrites title links and snippets per query from page content and other sources | You can't force it. Follow the quality guidelines: unique, descriptive, within length, branded. AIOSEO still recommends setting them on every page. |
| A change isn't reflected in Google | Google hasn't recrawled yet; this can take days, weeks or months | Search `site:domain.com` » Tools » "Any time" » past week/month. In GSC URL Inspection use **Test Live URL** then **Request Indexing**. Submit the sitemap. On Elite: Search Statistics » **Index Status** tab, or the Index Status icon in the AIOSEO Details column on All Posts. |
| New content not yet indexed | Indexing normally takes hours to weeks, **about a week** for most content | Avoid an overloaded server, link to the new page prominently, avoid excessive internal links, use URL Inspection, keep it in the sitemap, keep quality high. |
| SEO title character counter higher than expected | The counter counts the whole rendered format: title + separator with spaces + Site Title | "FAQs \| All in One SEO" = 4 + 3 + 14 = **21** characters. |
| Sitelinks don't appear | Google decides per query | You can't force sitelinks. Use logical structure, nav that matches the structure, breadcrumbs, informative compact titles/headings, concise relevant anchor text, no repeated content. |
| Favicon doesn't show in Google | Not guaranteed even when the guidelines are met | Appearance » Customize » **Site Identity** » **Select site icon** » Publish. |
| Want to remove the date from Google results | Not controllable | Removing the date from WordPress output doesn't guarantee Google drops it. |
| Images don't appear in search | Google decides; images appear mostly on mobile | See "Images in search" in docs-seo-guidance.md. Check the Images column in the sitemap. |
| Star ratings don't appear | Self-serving reviews (LocalBusiness/Organization reviewing itself), invalid schema, review not visible on the page, or not yet recrawled | Fix these and validate with the Rich Results Test. |
| A TruSEO keyword disappeared | The post was closed without saving; keywords are stored with the post | Re-add the keyword and click Save/Update. |
| No TruSEO score on some pages | The page has dynamic content: Posts page, Privacy Policy page, BuddyPress pages, WooCommerce Cart/Checkout/My Account | Expected behaviour. |
| TruSEO results replaced by a note | The Block Editor is in Code Editor mode | Switch back to the Visual editor. |

---

