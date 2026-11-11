# Settings and Search Appearance

Plugin setup, General Settings, Search Appearance (global, content types, taxonomies, archives, media, advanced), robots meta, canonical URLs, smart tags, Image SEO, admin display controls.

Built from a full read of aioseo.com/docs, /faqs and /blog on 2026-10-11 (AIOSEO Pro 5.0.2 on aioseo.com). Each section lists its source pages. Text in [brackets] is a reviewer note where the vendor advice looks dated or conflicts with Google guidance. UI labels move between versions: confirm on the live site before giving click paths as fact. Unresolved points are in open-questions.md.

## Contents

- Installation, licence activation, upgrading from Lite
- Addons and Feature Manager (single site and multisite)
- Automatic updates, announcements, uninstall
- Setup Wizard
- SEO Checklist
- Dashboard widgets and Display Controls (admin bar, columns, widgets)
- Access Control
- Hiding the AIOSEO meta box on edit screens
- RSS Content (anti-scraping)
- Page builder integrations
- AIOSEO Details column and Quick Edit
- Smart tags (titles, descriptions and other fields)
- Search Appearance: Global Settings (title separator, home page)
- Search Appearance: Content Types (posts, pages, CPTs)
- Search Appearance: Taxonomies (categories, tags, custom, product attributes)
- Search Appearance: Archives (author, date, CPT archives, search page)
- Search Appearance: Media attachments, Redirect Attachment URLs
- Search Appearance: Advanced (global robots, paging, keywords, shortcodes, crawl cleanup, query args)
- Robots meta (per type and per item)
- Canonical URLs
- Link attributes (nofollow, sponsored, UGC, title)
- X (Twitter) social settings
- Image SEO addon
- SEO meta concepts (vendor guidance)
- SEO Alerts
- Media attachments (Redirect Attachment URLs)

## Installation, licence activation, upgrading from Lite
Sources: https://aioseo.com/docs/installing-all-in-one-seo-pro/, https://aioseo.com/docs/how-to-add-your-license-key-in-all-in-one-seo-pro/, https://aioseo.com/docs/how-to-upgrade-from-all-in-one-seo-lite-to-pro/, https://aioseo.com/docs/installation-instructions-for-wordpress-com-users/, https://aioseo.com/docs/how-to-handle-issues-with-installing-all-in-one-seo-pro/

- Download: log in at https://aioseo.com/login/, then My Account » Downloads tab » Download AIOSEO. You get `aioseo-pro-v###.zip`. Do not let the browser unzip it, because WordPress only accepts the zip.
- Install: Plugins » Add New » Upload Plugin » Choose File » Install Now » Activate Plugin.
- Activating Pro automatically imports all SEO data and settings from Lite with no data loss. Lite is then deactivated and can be deleted.
- Licence: All in One SEO » General Settings shows the License Key field (the "License screen"). Paste the key from the purchase receipt email and click Activate.
- Lite-to-Pro automatic upgrade: paste the key into Lite's General Settings » License Key » Activate. A "Connect with AIOSEO and Upgrade to Pro" screen appears; click **Connect and Install AIOSEO Pro**.
- WordPress.com: upload the zip via My Site » Plugins » Upload Plugin, then open WP Admin and enter the key. The doc says every paid WP.com plan (Personal, Premium, Business, Commerce) allows third-party plugins and only Free does not. [Check this against current WordPress.com plan names and rules; for a long time plugins needed Business or higher.]

Troubleshooting installs:

| Symptom | Cause | Fix |
|---|---|---|
| "Destination folder already exists" | An earlier install failed and left files behind, but no entry under Plugins | Delete `/wp-content/plugins/all-in-one-seo-pack-pro` over FTP or with a File Manager plugin, then reinstall |
| "Permission denied" / "Could not create directory" | Server filesystem permissions | Install manually over FTP (unzip, upload the `all-in-one-seo-pro` folder to `/wp-content/plugins/`, activate), or ask the host to fix permissions |
| "The uploaded file exceeds the upload_max_filesize directive" | PHP upload limit | Raise the upload limit (separate doc), or use FTP |
| Any other error | n/a | Manual FTP install |

The two folder names disagree: `all-in-one-seo-pack-pro` (delete step) and `all-in-one-seo-pro` (upload step). See Open questions.

## Addons and Feature Manager (single site and multisite)
Sources: https://aioseo.com/docs/feature-manager/, https://aioseo.com/docs/installing-addons-for-all-in-one-seo-pro/, https://aioseo.com/docs/how-to-use-the-aioseo-feature-manager-on-a-multisite-network/

- Addons: Author SEO (E-E-A-T), Image SEO, IndexNow, Link Assistant, Local SEO, News Sitemap, Video Sitemap. The Pricing page says which plan includes each.
- Three ways to install an addon:
  1. All in One SEO » Feature Manager: use the toggle (shows "Deactivated") or **Activate All Features**.
  2. The splash screen on the addon's own settings page, with an Activate button:
     - Author SEO: Search Appearance » Author SEO
     - Image SEO: Search Appearance » Image SEO
     - Link Assistant: All in One SEO » Link Assistant
     - Local SEO: All in One SEO » Local SEO
     - News Sitemap: Sitemaps » News Sitemap
     - Video Sitemap: Sitemaps » Video Sitemap
  3. Plugins » Add New » Upload Plugin, with the addon zip from the aioseo.com account Downloads tab.
- Multisite Network Feature Manager (**Elite only**): Network Admin » All in One SEO » Feature Manager. Changes apply to the whole network, and a confirmation modal appears; click **Yes, process this network change**.

## Automatic updates, announcements, uninstall
Sources: https://aioseo.com/docs/enabling-automatic-updates-for-all-in-one-seo/, https://aioseo.com/docs/hiding-plugin-notifications-in-the-notifications-center/, https://aioseo.com/docs/how-to-remove-all-settings-and-data-when-you-uninstall-all-in-one-seo/

All three live under All in One SEO » General Settings » Advanced tab.

| Setting | Values | Default / notes |
|---|---|---|
| Automatic Updates | None, Minor Only, All | Lite: auto-updates off by default. Pro: updates itself by default |
| Announcements | Show / Hide | Hides only the vendor's notifications in the Notifications Center (All in One SEO » Dashboard). Configuration warnings generated by the plugin still show |
| Uninstall AIOSEO | Toggle | When on, all AIOSEO data and settings are deleted the next time the plugin is deactivated and deleted. Click Save Changes |

## Setup Wizard
Source: https://aioseo.com/docs/setting-up-all-in-one-seo-with-the-setup-wizard/ (PUBLISHED 2026-06-17, new page)

It opens automatically on first activation and takes under 10 minutes. Start with **Let's Get Started**. Steps:

1. **Site category**: Blog, News Channel, Online Store, Small Offline Business, and so on. Also set the Home Page Title and Home Page Meta Description using tag buttons. Click Save and Continue.
2. **Additional Site Information**: Person or Organization (most business and brand sites should pick Organization), then name or organization name, description, phone, logo, default social share image, and social profile URLs (Facebook, X, Instagram, TikTok, LinkedIn).
3. **SEO features**: sitemaps, broken link checker, image SEO, schema, "Optimized Search Appearance" and others. Recommended features are on by default.
4. **Search Appearance**: live SERP preview; site status **Under Construction** or **Live Site** (Under Construction keeps the site out of search results); post types; multiple authors; attachment pages; email reports. Click Save and Continue.
5. **Connect to Google Search Console** (this powers Search Statistics), or **Skip this Step**.
6. **Finish**: **Go to SEO Checklist**.

Every choice is site-wide and can be changed later in settings.

## SEO Checklist
Source: https://aioseo.com/docs/using-the-seo-checklist-in-all-in-one-seo/ (PUBLISHED 2026-02-17, MODIFIED 2026-10-06)

- Location: All in One SEO » General Settings » **SEO Checklist** tab.
- UI: a progress bar (for example "1/13 Tasks Completed"), Incomplete and Completed tabs, Bulk Actions with Apply, and a Priority filter (High = red dot, Medium = orange, Low = blue, Optional).
- Tasks table columns: Title, Priority, Time Estimate, Actions. Actions are **View Explanation** and **Dismiss** (Dismiss moves the task to Completed without doing it).
- An SEO Checklist widget appears on the AIOSEO Dashboard once the Setup Wizard is complete.
- Dismiss tasks that do not apply to the site.

## Dashboard widgets and Display Controls (admin bar, columns, widgets)
Sources: https://aioseo.com/docs/dashboard-widgets-in-all-in-one-seo/, https://aioseo.com/docs/hiding-the-aioseo-admin-bar-menu/, https://aioseo.com/docs/hiding-the-aioseo-column-on-all-posts-screens/, https://aioseo.com/docs/hiding-the-aioseo-column-on-taxonomy-screens/, https://aioseo.com/docs/hiding-the-aioseo-dashboard-widget/

Widgets appear on both the WordPress Dashboard and the AIOSEO Dashboard:
- **AIOSEO Overview**: pick a post type in **Choose a Post Type** to see TruSEO counts for Needs Improvement, Okay, Good, No TruSEO Score Yet, and posts without a Focus Keyword. Each count links to a filtered post list.
- **SEO Setup**: shows Setup Wizard progress, with an **Improve SEO Rankings** button.
- There is also an SEO News widget on the WP Dashboard.

**Display Controls need Basic or higher.** All are under General Settings » Advanced:

| Setting | Default | Effect |
|---|---|---|
| Admin Bar Menu | Show | Set Hide to remove the SEO admin-bar menu. The menu is only ever visible to Administrators |
| Post Type Columns | Include All Post Types checked | Uncheck it, then uncheck individual post types to remove the AIOSEO Details column from their list screens |
| Taxonomy Columns | Include All Taxonomies checked | The same, for Categories, Tags and custom taxonomy screens |
| Dashboard Widgets | All checked | Uncheck a widget to remove it for all Administrators, then Save Changes |

## Access Control
Source: https://aioseo.com/docs/access-control-settings/

- **Basic or higher.** Location: All in One SEO » General Settings » **Access Control** tab.
- Default permissions by role:

| Role | Default access |
|---|---|
| Editor | General Settings, Search Appearance, Social Networks, plus all per-page and per-post settings |
| Author | Per-post and per-page SEO settings, only on content they can already edit |
| Contributor | The same as Author |
| SEO Manager | General Settings, Redirections, plus per-page and per-post settings |
| SEO Editor | Per-page and per-post settings only |

- SEO Manager and SEO Editor are roles that AIOSEO adds.
- To customise a role, switch off its **Use Default Settings** toggle. Checkboxes then appear under **General SEO Settings** (main plugin screens) and **Post SEO Settings** (the AIOSEO areas on Add New and Edit screens). Check a box to grant access and uncheck it to remove access. For example, check Social Networks Settings for Editor.

## Hiding the AIOSEO meta box on edit screens
Source: https://aioseo.com/docs/how-to-hide-the-aioseo-settings-on-the-edit-content-screens-in-wordpress/

Hiding the meta box only hides the UI. SEO output in the page source carries on.

- **Your user only**:
  - Classic Editor: Screen Options » uncheck AIOSEO Settings.
  - Block Editor: the three-dot menu » Options » uncheck AIOSEO Settings.
  - Either way it applies to every item of that content type for that user. Repeat for each post type and taxonomy screen.
- **All users**: Search Appearance » Content Types (or the Taxonomies or Media tab) » a type's **Advanced** tab » **Show AIOSEO Meta Box** toggle.

## RSS Content (anti-scraping)
Source: https://aioseo.com/docs/how-to-protect-your-content-with-rss-content-settings/

- Location: General Settings » **RSS Content** tab. It has two fields, **Before Your Content** and **After Your Content**, which are added above and below each post in the RSS feed (for example `/feed/`). After Your Content ships with default text.
- Tags available in these fields: Author Link, Author Link (Alt), Author Name, Category Title, Post Date, Post Link, Post Link (Alt), Post Title, Site Link, Site Link (Alt), Site Title. The "(Alt)" versions output the link URL as the link text. Typing `#` lists the tags. An emoji picker is available.
- Purpose: scraped copies link back to the original.

## Page builder integrations
Source: https://aioseo.com/docs/page-builder-integrations/ (MODIFIED 2026-10-06)

Works out of the box with nothing to enable. Save inside the builder as normal.

| Builder | Where the AIOSEO UI is |
|---|---|
| Avada | AIOSEO button in the menu bar (panel) |
| Bricks | AIOSEO button in the menu bar (popup) |
| Divi | AIOSEO gear icon in the left menu (popup). Close and reopen freely; settings save when the page saves |
| Elementor | AIOSEO button in the top bar (side panel) |
| Oxygen | AIOSEO button in the menu bar (popup) |
| SeedProd | AIOSEO button on landing pages; Save |
| SiteOrigin | AIOSEO button in the Live Editor menu bar |
| Thrive Architect | AIOSEO Settings item in the right-hand menu |
| WPBakery | AIOSEO button in the menu bar (popup) |

Gotchas: the TruSEO Highlighter does not work in builders, and AIOSEO blocks work only in the Block Editor. With builders that rely on shortcodes, auto-generated descriptions may need **Run Shortcodes** (see Search Appearance » Advanced).

## AIOSEO Details column and Quick Edit
Sources: https://aioseo.com/docs/using-aioseo-details-on-the-posts-screen/ (MODIFIED 2026-10-06), https://aioseo.com/docs/using-the-quick-edit-feature-in-all-in-one-seo/, https://aioseo.com/docs/checking-the-index-status-of-content/

- The **AIOSEO Details** column appears on list screens for every post type and taxonomy. It shows:
  - **Index Status** icon (**Elite**): green = indexed, orange = excluded, red = error. Hover for details.
  - **Headline Analyzer score**.
  - **TruSEO score**, coloured red, orange or green. The first calculation can take a while.
  - **SEO Title**, with a pixel-width indicator. **Maximum recommendation is 600 px**, because Google truncates by pixel width.
  - **Meta Description**, with a character count. The general guidance is 120-160 characters; Google truncates at about 155-160.
  - **Link Assistant** icons (internal, external, affiliate links).
  - **Broken Link Checker** count (needs the free Broken Link Checker plugin).
- **Quick Edit**: click the pencil next to Title or Description to edit inline with the same smart-tag field, then **Save Changes** or **Discard Changes** (another page says **Save** or **Cancel**).
  - Works for Posts, Pages, Products, Media and CPTs.
  - Works for Categories, Tags and custom taxonomies on **Pro**.
- To hide the column, see Display Controls.

## Smart tags (titles, descriptions and other fields)
Sources: https://aioseo.com/docs/using-the-smart-tags-in-titles-and-descriptions/, https://aioseo.com/docs/custom-fields-in-titles-and-descriptions/, https://aioseo.com/docs/adding-woocommerce-product-attributes-to-seo-title-or-description/, https://aioseo.com/docs/setting-unique-seo-titles-and-descriptions-for-paginated-content/

- Insert tags with the buttons above a field, the **View all tags** link (which has a "Search for an item" box and a description of each tag), or by typing `#`.
- Tags appear as chips. Delete with Backspace or Delete, and cut, copy and paste them between fields. There is an emoji picker icon above fields.
- Common tags named in these docs: Post Title, Separator, Site Title, Tagline, Page Number, Author Biography, Custom Field, Taxonomy Name, WooCommerce Price.
- **Custom Field** smart tag: pick it, then type the field name in **Enter a custom field name** and press Enter. **The name is case-sensitive.** It works in:
  - Content Types, Taxonomies and Media title and description formats.
  - Home Page title and description on Global Settings.
  - Per-post Title and Description, Facebook Title and Description, and Twitter Title and Description.
  - Any field where it appears in the tag list.
- **WooCommerce product attributes in titles and descriptions**: use the **Taxonomy Name** smart tag and enter the attribute slug **prefixed with `pa_`** (for example Size becomes `pa_size`).
  - Use the Custom Field tag for Woo meta. Field names given: `_visibility`, `_regular_price`, `_sale_price`, `_weight`, `_length`, `_width`, `_height`, `_stock`, `_tax_status`, `_tax_class`.
  - The WooCommerce Price tag outputs only the sale price when one exists. Use Custom Field `_regular_price` to show the regular price as well.
- **Paged Format** (Search Appearance » Advanced): appended to titles and descriptions on paginated pages so each page is unique. The default is "Page" plus the **Page Number** smart tag.

## Search Appearance: Global Settings (title separator, home page)
Sources: https://aioseo.com/docs/setting-a-title-separator/, https://aioseo.com/docs/setting-the-seo-for-your-home-page/, https://aioseo.com/docs/quick-start-guide/

- **Title Separator**: Search Appearance (Global Settings tab). Click one of the preset characters, for example `|` or `–`, or enter an HTML entity in **Custom HTML entity**. The Preview updates. It is used wherever the Separator smart tag appears.
- **Home page SEO.** First check Settings » Reading » "Your homepage displays".
  - **Latest posts**: Search Appearance » **Home Page Settings** section, with Preview, **Home Title**, **Meta Description**, and **Keywords** (only if meta keywords are on).
  - **Static page**: edit that page » AIOSEO Settings » Page Title and Meta Description. Keywords are on the Advanced tab.
- The Beginners Guide order: home page meta » Person or Organization (Schema settings) » show or hide content in search results » per-content meta » XML sitemap » Social (Facebook guide).

## Search Appearance: Content Types (posts, pages, CPTs)
Sources: https://aioseo.com/docs/setting-the-seo-title-and-description-format-for-posts/, https://aioseo.com/docs/setting-the-seo-title-and-description-format-for-pages/, https://aioseo.com/docs/setting-the-seo-title-and-description-format-for-custom-post-types/, https://aioseo.com/docs/showing-or-hiding-your-content-in-search-results/, https://aioseo.com/docs/how-to-optimize-your-web-stories-with-all-in-one-seo/, https://aioseo.com/docs/manage-your-buddypress-groups-seo-with-all-in-one-seo/, https://aioseo.com/docs/setting-the-seo-for-woocommerce-content/

Search Appearance » **Content Types** has one section per post type: Posts, Pages, Products, Stories, Activities (BuddyPress) and so on. Each section has these sub-tabs:
- Title & Description:
  - **Show in Search Results** (Yes/No).
  - Preview.
  - **<Type> Title** format, for example Post Title, Page Title, Product Title or Story Title.
  - **Meta Description** format.
- **Advanced**: Robots Meta Settings and **Show AIOSEO Meta Box**.
- **Custom Fields**: custom fields for TruSEO.
- Schema: not covered in the docs.

Notes:
- The title and description fields are hidden when Show in Search Results is No.
- A per-post title or description overrides the format.
- **AIOSEO repeatedly warns**: auto-generated titles and descriptions can be poor quality and ignored by search engines; ones you write yourself work best.
- **Show in Search Results = No does three things:**
  1. Outputs `noindex` on that content.
  2. Excludes it from AIOSEO sitemaps.
  3. Disables all SEO features for that content.

  Content set to noindex also disappears from the sitemap Post Types and Taxonomies picker.
- Per-item overrides work in either direction. Edit the item » Advanced » Robots Settings » turn off Use Default Settings » check or uncheck **No Index** » Update. This works for any post type, and for taxonomies on Pro.
- **Content AIOSEO recommends excluding from search**: media attachments, the default Uncategorized category, privacy and terms pages, and user profile pages on membership sites.
- **Web Stories** (needs Google's Web Stories plugin): a **Stories** section with Story Title and Meta Description. AIOSEO outputs **AmpStory** schema automatically. Published 2024-12.
- **BuddyPress**:
  - Sections Activities (BuddyPress), Groups (Group Title), and Members (BuddyPress).
  - For Members, the Meta Description can hold an author bio or achievements.
  - AIOSEO outputs **DiscussionForumPosting** schema for Activities.
- **WooCommerce**: products are a post type (Products section). Product categories, tags and attributes are taxonomies; editing individual terms needs Pro.

## Search Appearance: Taxonomies (categories, tags, custom, product attributes)
Sources: https://aioseo.com/docs/setting-the-seo-title-and-description-format-for-categories/, https://aioseo.com/docs/setting-the-seo-title-and-description-format-for-tags/, https://aioseo.com/docs/setting-the-seo-title-and-description-format-for-custom-taxonomies/, https://aioseo.com/docs/setting-the-seo-for-woocommerce-product-attributes/, https://aioseo.com/docs/how-to-strip-the-category-base-in-wordpress/

- Search Appearance » **Taxonomies** has one section per taxonomy: Categories (Category Title), Tags (Tag Title), Product Categories, **Product Attributes** (shown once any Woo attributes exist), and so on. Each has Show in Search Results, Preview, Title, Meta Description and an Advanced tab.
- **Per-term override**: Edit Term screen » AIOSEO Settings » Title or Description fields. Category, tag and custom-taxonomy pages say "Pro only"; the Product Attributes page says **Basic or higher**.
  - For a Woo attribute term: Products » Attributes » click the attribute » click the term » AIOSEO Settings.
  - WordPress and AIOSEO treat a product attribute as a taxonomy.
- **Remove Category Base Prefix** (added in v4.2.0): Search Appearance » Taxonomies » Categories » **Advanced** tab, below Robots Meta Settings. Set Yes and Save Changes. Old `/category/x/` URLs then redirect to `/x/`.
  - **Gotcha**: if a post has the same slug as a category, visitors are redirected to the category archive and never see the post.

## Search Appearance: Archives (author, date, CPT archives, search page)
Sources: https://aioseo.com/docs/setting-the-seo-title-and-description-format-for-author-and-date-archives/, https://aioseo.com/docs/setting-the-seo-title-and-description-format-for-custom-post-type-archives/, https://aioseo.com/docs/setting-the-seo-title-and-description-format-for-the-search-results-page/

- Search Appearance » **Archives**: sections for **Author Archives**, **Date Archives**, each CPT archive (for example Movies), and **Search Page**. Each has Show in Search Results, Preview, Title and Meta Description. The format applies to that archive type.
- **Search Page**: **Show in Search Results defaults to No**, because internal search results should not be indexed. Set it to Yes to reveal Search Page Title and Meta Description.
- Date archives suit news sites; author archives suit multi-author sites with followings.

## Search Appearance: Media attachments, Redirect Attachment URLs
Sources: https://aioseo.com/docs/redirecting-attachment-pages/, https://aioseo.com/docs/setting-the-seo-title-and-description-format-for-media-attachments/, https://aioseo.com/docs/showing-or-hiding-your-content-in-search-results/

- Location: Search Appearance » **Image SEO** tab in newer pages. Older pages and screenshots call it the **Media** tab (see Open questions).
- **Redirect Attachment URLs**:

| Value | Behaviour |
|---|---|
| Disabled | Attachment pages are live and indexable. Media Title and Meta Description formats and Show in Search Results appear |
| **Attachment** (default, AIOSEO recommends) | The attachment page redirects to the file itself |
| Attachment Parent | Redirects to the post the file was uploaded to. **If the file is unattached (Media Library "Uploaded to" column shows "(Unattached)"), the attachment page still shows** |

- With Disabled: set the Media Title and Meta Description formats. Per-item overrides are on the Edit Media screen.
- AIOSEO says most sites should keep attachments out of search.

## Search Appearance: Advanced (global robots, paging, keywords, shortcodes, crawl cleanup, query args)
Sources: https://aioseo.com/docs/using-the-robots-meta-settings-in-all-in-one-seo/, https://aioseo.com/docs/setting-noindex-and-nofollow-on-paginated-content/, https://aioseo.com/docs/setting-noindex-for-rss-feeds/, https://aioseo.com/docs/setting-unique-seo-titles-and-descriptions-for-paginated-content/, https://aioseo.com/docs/keyword-settings/, https://aioseo.com/docs/where-did-my-seo-keywords-go-in-all-in-one-seo-v4-0/, https://aioseo.com/docs/running-shortcodes/, https://aioseo.com/docs/crawl-cleanup-best-practices/, https://aioseo.com/docs/using-the-query-arg-monitoring-in-all-in-one-seo/

All of these are under Search Appearance » **Advanced**.

**Global Robots Meta** (default: Use Default Settings). Turn the toggle off to reveal checkboxes, including:
- **No Index Paginated**: noindex on page 2 and later.
- **No Follow Paginated**.
- **No Index RSS Feeds**: **checked by default**, so AIOSEO noindexes feeds. Uncheck to allow indexing.
- The full robots set (see Robots Meta below).

[Noindexing page 2 and later of archives can slow discovery of deep posts. Google advises leaving paginated pages indexable with self-canonicals. Use No Index Paginated with care.]

**Paged Format**: see Smart tags.

**Meta keywords** (off by default; only Yandex uses them):

| Setting | Effect |
|---|---|
| Use Meta Keywords = Yes | Adds a **Keywords** field to each item's Advanced tab (type a keyword and press Enter; X removes it) and to Home Page Settings |
| Use Categories for Meta Keywords | Adds post categories as keywords |
| Use Tags for Meta Keywords | Adds post tags as keywords |
| Dynamically Generate Meta Keywords | Builds keywords for the latest-posts homepage, static Blog page, category, tag, date and author archives from the keywords of the posts they contain |

The Keywords field moved to the Advanced tab in v4.0. Output: `<meta name="keywords" itemprop="keywords" content="…" />`.

**Run Shortcodes** (added in v4.2.0; **off by default for new installs**)
- Controls whether AIOSEO parses shortcodes in content when building the title, description, schema and OG/Twitter images.
- Parsing can cause conflicts: shortcodes run too early or twice, duplicated or missing content, broken forms, missing stylesheets.
- Turn it on only if you want auto-generated meta from shortcode-heavy builders such as Elementor or Divi, and test the site afterwards.
- Finer control: filters **`aioseo_disable_shortcode_parsing`** and **`aioseo_conflicting_shortcodes`**. Each has its own doc page (https://aioseo.com/docs/aioseo_disable_shortcode_parsing/, https://aioseo.com/docs/aioseo_conflicting_shortcodes/); signatures are not given here.

**Crawl Cleanup** (toggle at the bottom of Advanced). It is for advanced users and mainly matters for large sites. It has three tabs.

1. **RSS Feeds**: turning Crawl Cleanup on disables most feeds by default. A disabled feed URL redirects to the homepage or the most relevant archive (for example the author archive for an author feed).

| Feed | Default with Crawl Cleanup |
|---|---|
| Global RSS Feed | Enabled. Do NOT disable (subscribers, SEO) |
| Global Comments RSS Feed | Disabled |
| Static Posts Page Feed (only shown with a static blog page such as /blog/) | Enabled. Do NOT disable |
| Author Feeds | Enabled |
| Post Comment Feeds | Disabled |
| Search Feed | Disabled |
| Attachments Feed | Disabled |
| Paginated RSS Feeds | Disabled |
| Post Type Archive Feeds | None enabled |
| Taxonomy Feeds | Only Categories enabled |
| Atom Feed | Disabled |
| RDF/RSS 1.0 Feed | Disabled |

2. **Unwanted Bots**: tick individual crawlers or **All AI Crawlers** (under Block AI Crawlers). Rules are written into WordPress's **dynamic** robots.txt. A physical robots.txt file is not touched; **AIOSEO recommends deleting any static robots.txt.**

3. **Internal Site Search Cleanup**:
   - **Filter Search**: when on, reveals:
     - **Max. Number of Characters**: default **50**; AIOSEO recommends 1-50.
     - **Emojis and Other Special Characters**: blocks such searches.
     - **Common Spam Patterns**: blocks known spam patterns.
   - **Redirect Pretty to "RAW" URLs**: redirects `/search/…` to `/?s=`.
   - **Block Crawling of Internal Site Search URLs**: adds a Disallow to the dynamic robots.txt. A static file is not touched.

**Query Arg Monitoring** (toggle at the bottom of Advanced; Save Changes)
- **Optimize UTM Parameters**: 301-redirects UTM query parameters to the `#` (fragment) equivalent to prevent duplicate URLs.
- **Log Retention**: a dropdown of how long logs are kept. Logs go in the DB table **`_aioseo_crawl_cleanup_logs`** (with the WP table prefix). It can grow fast, so watch its size.
- **Block Query Arg**: a table logs every query key and value seen.
  - Block by **key** (any value) or **key + value**.
  - Bulk Actions can block or delete entries.
  - A form above the table accepts any key and/or value, and **Regex** works for keys.
- Use it to stop bad-actor query strings from polluting search results.

## Robots meta (per type and per item)
Sources: https://aioseo.com/docs/using-the-robots-meta-settings-in-all-in-one-seo/, https://aioseo.com/docs/setting-the-robots-meta-for-individual-content/, https://aioseo.com/docs/showing-or-hiding-your-content-in-search-results/

- Three levels, from most specific to least:
  1. Per item: AIOSEO Settings » Advanced » **Robots Setting**.
  2. Per type: Search Appearance » Content Types, Taxonomies, Media or Archives » the type's **Advanced** tab » **Robots Meta Settings**. For example Search Appearance » Content Types » Posts » Advanced.
  3. Global: Search Appearance » Advanced » **Global Robots Meta**.

  Each level has a Use Default Settings toggle; turn it off to show the checkboxes. They are meant for advanced users.

| Directive | Meaning per AIOSEO |
|---|---|
| No Index | Keep this content out of search results |
| No Follow | Do not follow the links in it |
| No Archive | Do not show a cached copy [Google retired cached pages in 2024; still honoured by some engines] |
| No Translate | Do not offer a translation in results |
| No Image Index | Do not index the images on the page |
| No Snippet | No text snippet or video preview in results |
| No ODP | Do not use Open Directory Project data [DMOZ closed in 2017; obsolete] |
| Max Snippet | Maximum characters in the snippet |
| Max Video Preview | Maximum seconds of video preview |
| Max Image Preview | Maximum image preview size (none, standard or large in Google terms) |

## Canonical URLs
Source: https://aioseo.com/docs/canonical-urls-in-all-in-one-seo/

WordPress already outputs canonicals, and AIOSEO adds to them. To override per item: AIOSEO Settings » **Advanced** » **Canonical URL**, entering the full URL. Example use: a post that resolves under two category paths. The SEO Analysis tool flags a missing canonical, which usually means a theme or plugin removed it.

## Link attributes (nofollow, sponsored, UGC, title)
Source: https://aioseo.com/docs/adding-nofollow-sponsored-and-title-attributes-to-links/

- **Classic Editor**: Insert Link » **Link Options** (gear) gives a Title field and checkboxes **Add rel="nofollow" to link**, **Add rel="sponsored" to link** and **Add rel="UGC" to link**.
- **Block Editor**: Add Link » Link Settings dropdown gives toggles **Add "nofollow" to link** and **Add "sponsored" to link**. UGC is not mentioned for the Block Editor.
- Guidance from the doc:
  - The title attribute has negligible SEO value; do not stuff it.
  - Use sponsored for ads and paid links.
  - Use UGC for comments and forums.
  - Use nofollow for external links that give no SEO benefit to your site.
- [The doc says "each time you link to an external site, you give them a little of your SEO value". This framing is dated: since 2019 Google treats nofollow as a hint, and linking to good sources is not a loss.]

## X (Twitter) social settings
Sources: https://aioseo.com/docs/beginners-guide-to-social-networks-settings-for-twitter/, https://aioseo.com/docs/configuring-the-twitter-settings-for-your-content/, https://aioseo.com/docs/setting-twitter-social-meta-for-your-homepage/

- **Global**: All in One SEO » Social Networks » **Twitter** tab.
  - **Enable Twitter Cards**: keep it on.
  - Default Card Type.
  - Image Source.
  - Default Twitter image as a fallback.
  - **Home Page Settings** (when the homepage shows latest posts): Preview, **Card Type**, **Home Page Image** (Upload or Select Image, or paste a URL), **Home Page Title**, **Description**.
- **Per item and static homepage**: edit » the **Social Appearance** meta box (newer page) or the Social tab (older) » **X (Twitter)** tab.
  - X (Twitter) Preview, with desktop and mobile icons.
  - **Use Data from Facebook Tab**.
  - **X Title**, **X Description**.
  - **Image Source** (Custom Image reveals **X Image**).
  - **X Card Type**: **Summary** or **Summary with Large Image**.
- **Fallbacks**: an empty X Title uses the Facebook Title, then the SEO Title. An empty X Description uses the Facebook Description, then the Meta Description.
- **Image sizes**: Summary needs at least 144x144 at 1:1. Summary with Large Image needs at least 300x157 at 2:1.
- These apply to posts, pages, attachments, CPTs and all taxonomies.

## Image SEO addon
Source: https://aioseo.com/docs/using-the-image-seo-features-in-all-in-one-seo/

- Needs **Plus or higher**. Location: Search Appearance » **Image SEO** tab » **Activate Image SEO**, or via the Feature Manager.
- It sets title, alt, caption and description attributes and filenames automatically, for images in post content.
- Tabs: **Title, Alt Tag, Caption, Description, Filename**.

| Setting | Tabs | Detail |
|---|---|---|
| Title Format | Title | Smart tags, `#`, or text. Builds the image title attribute |
| Alt Tag Format | Alt Tag | Builds alt text. Doc: "also used as a ranking factor" |
| Caption Format / **Autogenerate Caption on Upload** | Caption | The toggle generates a caption for new uploads |
| Description Format / **Autogenerate Description on Upload** | Description | The description shows on the attachment page |
| **Strip Punctuation** | Every tab | Choose the characters to strip, and optionally convert spaces to dashes or underscores |
| **Casing** | Every tab | Disabled, Lower Case, Title Case (major words capitalised), Sentence Case |
| **Exclude Posts / Pages** | Title, Alt Tag | Autocomplete by title. Excluded content keeps its own attributes |
| **Exclude Terms** | Title, Alt Tag | Excludes posts in those categories, tags or terms |
| **Words to Strip** | Filename | One word per line, removed from image filenames |

- **Bulk for existing media**: Media Library in **list view** » select items » Bulk actions » **Autogenerate image attributes** » Apply. This applies the caption and description generation.
- **AI alt text**: Media Library » select images » Bulk actions » **Generate Alt Text for Images with AI**. It shows progress and remaining AI credits. **Each alt text costs 10 AI credits.**
- [Format-generated alt text such as "%image title% | %site title%" is weak for accessibility. Review it, or prefer real descriptions or the AI option.]

## SEO meta concepts (vendor guidance)
Source: https://aioseo.com/docs/what-is-seo-meta/

- Title: `<title>…</title>`. It is "typically 60-70 characters"; Google truncates by pixel width, and all-caps text is wider. Keep titles short, descriptive and unique across all pages, posts and terms.
- Description: `<meta name="description" content="…" />`, output below the AIOSEO comment line. It is "typically around 160 characters but can be as much as 320" [320 dates from 2017-2018; Google reverted to about 155-160]. Keep descriptions unique.
- Search engines may ignore your title or description and show an H1 or page text instead.
- The doc says search engines "may penalize" duplicate titles and descriptions [there is no penalty; duplicates simply perform worse and may be rewritten].
- Meta keywords have no value except for Yandex, and are off by default.

## SEO Alerts
Sources: https://aioseo.com/docs/seo-alerts/

- **New feature:** doc PUBLISHED 2026-06-24.
- **Location:** **All in One SEO » Tools » SEO Alerts** tab.
- **Tier:** not stated. The doc says only "All you need is All in One SEO installed and activated", which suggests it is available in Lite.

| Setting | Behaviour / default |
|---|---|
| **Enable SEO Alerts** (toggle) | Must be On for monitoring. When on, AIOSEO checks the site **every hour**. |
| Homepage is noindexed | On by default. Alerts if the homepage carries noindex. |
| Robots.txt fails to load | On by default. Alerts if robots.txt returns an error. |
| XML Sitemaps fail to load | On by default. Alerts if any XML sitemap returns an error. |
| **SEO Alerts Delivery » Slack Webhook URL** | Slack incoming-webhook URL. Optional. |
| **Email Addresses** + **Add Email Address** button | Add one or more recipients. Use email, Slack or both. |
| Save Changes | Required to start monitoring. |

- **De-duplication:** the same issue triggers at most **one alert per day**.
- **Slack webhook setup:** create an app at https://api.slack.com/apps » enable **Incoming Webhooks** on the app's settings » **Add New Webhook** » copy the URL.
- Gotchas [my notes]:
  - Hourly checks presumably run on WP-Cron / Action Scheduler, so low-traffic sites without a real cron may check less often.
  - A firewall that blocks loopback requests could cause false "fails to load" alerts.
- The doc's next step points to the "SEO Checklist".

## Media attachments (Redirect Attachment URLs)
Sources: https://aioseo.com/docs/what-are-media-attachments-and-should-i-submit-them-to-search-engines/

- **Location:** **All in One SEO » Search Appearance » Image SEO** tab » first setting, **Redirect Attachment URLs**.
- **Values:**
  - **Disabled**: keep attachment pages.
  - **Attachment**: redirect to the media file itself.
  - **Attachment Parent**: redirect to the post the media is embedded in. AIOSEO says "if in doubt, choose this".
- **AIOSEO recommends:**
  - Most sites, where attachment pages are thin: Attachment or Attachment Parent.
  - Sites with rich attachment pages (e.g. a photography theme showing EXIF or location): Disabled, then set **Show in Search Results = Yes**.
- **Effect on images:** none. Images stay in the XML Sitemap unless **Exclude Images** is ticked, and Google may still choose not to index them.
- [WordPress 6.4+ disables attachment pages by default for new installs (`wp_attachment_pages_enabled` option). The Image SEO tab location may differ by version; elsewhere AIOSEO puts this under the Media/Attachments content type.]
