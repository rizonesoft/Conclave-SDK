# Developer reference

PHP filters, REST API, functions and Composer. Real code examples are in hook-examples.md.

Built from a full read of aioseo.com/docs, /faqs and /blog on 2026-10-11 (AIOSEO Pro 5.0.2 on aioseo.com). Each section lists its source pages. Text in [brackets] is a reviewer note where the vendor advice looks dated or conflicts with Google guidance. UI labels move between versions: confirm on the live site before giving click paths as fact. Unresolved points are in open-questions.md.

## Contents

- Read this first: source quality
- Master hook table
- Output control hooks
- Title, description, keywords
- Canonical, robots meta, rel next/prev
- Social tags (Open Graph, Twitter) and social image
- Schema hooks
- Post/term data model, translations API
- Sitemap hooks
- Breadcrumb hooks
- Table of Contents prefix
- llms.txt filters
- Shortcode parsing, editor link format, page builders, metabox
- Admin UI, access control, public post types, user profile
- Importers, redirect logs, email reports
- Local Business hooks
- REST API (fetch and update AIOSEO data)
- Installing via Composer
- Other snippets

## Read this first: source quality

- The page text only showed "Code Embed Fallback" where each example sits; the real code was recovered separately from the WPCode embeds and is used verbatim below. Three embeds are empty in the source: the SQL query on `aioseo_local_business_post_type_name` (wpcode j57g13n5), the SQL query on `aioseo_local_business_taxonomy_name` (e50xv4z5) and the tag list on `aioseo_twitter_tags` (qo9xm8wo). The SQL shown for those two pages is mine, marked [reconstructed].
- The embed source URLs use hyphenated slugs (e.g. `https://aioseo.com/docs/aioseo_access_control_excluded_roles/`); the page URLs use underscores (`/docs/aioseo_access_control_excluded_roles/`). Same pages.
- Several vendor snippets have bugs (syntax errors, type mismatches, multibyte-unsafe truncation). They are reproduced as published and flagged under each one as **Bug in doc code**. Do not paste those unmodified.
- Vendor snippets use named functions (often the same name on one page, e.g. two `redirects_log_skip` or two `aioseo_filter_schema_output`). Adding two snippets from the same page as-is causes a fatal "cannot redeclare function" error. Rename or use closures.
- All 86 pages show MODIFIED 2026-08-14 (bulk re-save on the same day), so the MODIFIED date says nothing about content changes. PUBLISHED dates are given where useful.
- Every hook documented here is a **filter** (`add_filter`). No action hooks (`add_action`) are documented. `aioseo_save_post`/`aioseo_save_term` sound like actions but are filters that receive and must return the model object.
- No WP-CLI commands and no JS API are documented. `aioseo()` helpers that appear: `aioseo()->head->output()`, `aioseo()->helpers->isWooCommerceActive()`, `aioseo()->helpers->dateTimeToIso8601( $datetime )`, `aioseo()->access->isAdmin()`.
- Several pages say "Arguments (1)" but list 2 or 3. Extra arguments arrive only if you pass `$accepted_args` to `add_filter()` (e.g. `add_filter( 'aioseo_sitemap_exclude_posts', 'fn', 10, 2 );`). The vendor code does this where it uses them.
- Where to put code: AIOSEO recommends the WPCode plugin (it sanity-checks snippets before activating). The `aioseo_flush_output_buffer` page says the (child) theme `functions.php` works and to never use the parent theme (wiped on update). `aioseo_disable_link_format` must go in a plugin/mu-plugin/Code Snippets, not `functions.php` (see below). [Note: an mu-plugin is the safest place for anything that must load before the theme.]

## Master hook table

Type is "filter" for all. "Since" only where the docs give it. Licence/addon is my inference from the feature the hook belongs to unless stated. Shapes marked "(from code)" come from the vendor snippets, not the prose.

### Output control (global kill switches and head sections)

| Hook | Args (in order) | Controls | Default / return | Since |
|---|---|---|---|---|
| `aioseo_disable` | `$disabled` (bool) | Stops AIOSEO outputting anything on the frontend (meta, Open Graph, schema, etc.) | `false`; return `true` to disable | - |
| `aioseo_meta_views` | `$views` (array) | Which head sections are output. Views: `meta` (all general meta: description, robots, etc.), `social` (Open Graph + Twitter), `schema` (JSON-LD), `analytics` (Google Analytics code, deprecated) | Return the array minus views to drop; `[]` = nothing (from code) | - |
| `aioseo_disable_title_rewrites` | `$disabled` (bool) | Stops AIOSEO rewriting the `<title>` | `false` | - |
| `aioseo_flush_output_buffer` | `$enabled` (bool) | Whether AIOSEO flushes the output buffer after rewriting the title. Turn off to fix conflicts with other plugins that output-buffer at the same time | `true` | - |
| `aioseo_schema_disable` | `$disabled` (bool) | Stops schema (JSON-LD) output | `false` | - |
| `aioseo_hide_version_number` | `$hide` (bool) | Hides the AIOSEO version number on the frontend | return `true` to hide | - |

### Title, description, keywords, canonical, robots, pagination

| Hook | Args | Controls | Default / return | Since |
|---|---|---|---|---|
| `aioseo_title` | `$title` (string) | Final SEO `<title>` | string | - |
| `aioseo_description` | `$description` (string) | Final meta description | string | - |
| `aioseo_keywords` | `$keywords` (string, comma-separated, no spaces in the example) | Meta keywords | string | - |
| `aioseo_canonical_url` | `$url` (string) | Canonical URL | string; `''` suppresses the tag (from code) | - |
| `aioseo_robots_meta` | `$attributes` (array keyed by directive: `noindex`, `nofollow`, `noarchive`, `nosnippet`, `noimageindex`, `noodp`, `notranslate`, `max-snippet`, `max-image-preview`, `max-video-preview`; value `''` = off, value = directive name to output, e.g. `'noindex' => 'noindex'`) (from code) | Robots meta tag attributes | array | - |
| `aioseo_next_link` | `$next` (string) | `rel="next"` link on paginated pages | string; `''` suppresses | - |
| `aioseo_prev_link` | `$previous` (string) | `rel="prev"` link on paginated pages | string; `''` suppresses | - |

### Social (Open Graph / Twitter)

| Hook | Args | Controls | Default / return | Since |
|---|---|---|---|---|
| `aioseo_facebook_tags` | `$facebookMeta` (array, property => value, e.g. `og:title`, `article:published_time`) | All Facebook / Open Graph tags output | array; `[]` removes all OG tags; a key set to `''` drops that tag (from code) | - |
| `aioseo_twitter_tags` | `$twitterMeta` (array, name => value, e.g. `twitter:title`) | All Twitter (X) card tags output | array | - |
| `aioseo_thumbnail_size` | `$imageSize` (string or array) | Image size used for `og:image` | `"fullsize"`; allowed `fullsize`, `large`, `medium`, `thumbnail`, or `[ width, height ]` in px e.g. `[ 200, 300 ]` | - |
| `aioseo_social_image_ignore_cover_block` | `$ignore` (bool) | Whether Block Editor Cover blocks are skipped when the image source is "First Image in Content" | prose: default `true`; see code/prose conflict below | - |

### Schema

| Hook | Args | Controls | Default / return | Since |
|---|---|---|---|---|
| `aioseo_schema_disable` | `$disabled` (bool) | (see Output control) | `false` | - |
| `aioseo_schema_graphs` | `$graphs` (array of graph name strings, e.g. `'Article'`) | Which graphs are built for the page | array | - |
| `aioseo_schema_output` | `$graphs` (list of graph arrays, each with `@type` and properties such as `author`, `breadcrumb`, `datePublished`) | The final JSON-LD graph data | array | - |
| `aioseo_schema_json_flags` | `$flags` (int) | Flags passed to `json_encode` for schema output | int | 4.3.3 |

### Post/term data model (load/save, translations)

| Hook | Args | Controls | Return | Since |
|---|---|---|---|---|
| `aioseo_get_post` | `$post` (`AIOSEO\Common\Models\Post`; properties used in code: `post_id`, `title`) | All SEO/social/schema data for one post when loaded | the model object | 4.2.2 |
| `aioseo_get_term` | `$term` (`AIOSEO\Pro\Models\Term`; properties used: `term_id`, `title`) | Same for a term when loaded (Pro model) | the model object | 4.2.2 |
| `aioseo_save_post` | `$post` (`AIOSEO\Common\Models\Post`) | Post SEO data just before it is saved | the model object | 4.2.2 |
| `aioseo_save_term` | `$term` (`AIOSEO\Pro\Models\Term`) | Term SEO data just before it is saved | the model object | 4.2.2 |
| `aioseo_get_post_id` | `$postId` (int) | The post ID whose SEO data AIOSEO uses for the current request (code example: use post 123's data on the `product` post type archive) | int | - (page published 2023-08-29) |

### Sitemaps

| Hook | Args | Controls | Return | Since |
|---|---|---|---|---|
| `aioseo_sitemap_additional_pages` | `$pages` (array of `[ 'loc', 'lastmod' (e.g. `'2020-12-11 11:11'`), 'changefreq' (e.g. `'always'`), 'priority' (float) ]`) (from code) | Entries of the Additional Pages sitemap. Requires the toggle **All in One SEO > Sitemaps > Additional Pages** set On | array | - |
| `aioseo_sitemap_exclude_posts` | `$ids` (array of post IDs), `$type` (string sitemap type; `'general'` = the XML sitemap) | Posts excluded from the sitemap | array | - |
| `aioseo_sitemap_exclude_terms` | `$ids` (array of term IDs), `$type` (string; `'general'`) | Terms excluded from the sitemap | array | - |
| `aioseo_sitemap_images` | `$images` (array; code appends plain image URL strings), `$post` (WP_Post) | Images listed for a specific post | array | 4.1.3; `$post` added 4.1.7 |
| `aioseo_sitemap_indexes` | `$indexes` (array of `[ 'loc' => url, 'lastmod' => ISO 8601, 'count' => int ]`) | Indexes in the root (general) sitemap index | array | 4.1.5 |
| `aioseo_sitemap_lastmod_disable` | `$disabled` (bool) | Removes the Last Updated (`lastmod`) date from the sitemap index, only for post type and taxonomy sitemaps (not date/author archive sitemaps) | return `true` to disable | - |
| `aioseo_sitemap_post` | `$entry` (array; keys `language` (main URL locale) and `languages` (list of `[ 'language' => locale, 'location' => url ]`) from code), `$postId` (int), `$postType` (string) | One post's sitemap entry; advertise translations for the multilingual sitemap | array | 4.2.2 |
| `aioseo_sitemap_term` | `$entry` (array, same keys), `$termId` (int), `$taxonomy` (string) | One term's sitemap entry; translations | array | 4.2.2 |
| `aioseo_sitemap_rss` | `$entries` (array of entry arrays; `pubDate` key, RFC 2822 format `D, d M Y H:i:s O`) (from code) | Entries in the RSS sitemap/feed | array | 4.0.0 |

### Breadcrumbs

| Hook | Args | Controls | Return | Since |
|---|---|---|---|---|
| `aioseo_breadcrumbs_output` | `$display` (bool) | Show/hide breadcrumbs | bool | - |
| `aioseo_breadcrumbs_trail` | `$crumbs` (array of crumb arrays; `reference` holds the source object, e.g. `WP_Term`) (from code) | Add/change/remove any crumb | array | - |
| `aioseo_breadcrumbs_template` | `$templateItem` (**array** with key `template` holding the HTML, per code; prose says string), `$crumb` (array with `reference`) | HTML template of one crumb; template can use the smart tag `#breadcrumb_label` | the `$templateItem` array | - |
| `aioseo_breadcrumbs_separator` | `$separator` (string HTML) | Separator HTML between crumbs | string | - |
| `aioseo_breadcrumbs_separator_symbol` | `$symbol` (string) | Separator symbol only | string | - |
| `aioseo_breadcrumbs_show_current_item` | `$showCurrentItem` (bool), `$type` (string, breadcrumb type), `$reference` (array, reference for the current crumb) | Show/hide the last (current) crumb | bool | - |
| `aioseo_breadcrumbs_link_current_item` | `$linkCurrentItem` (bool) | Link or unlink the current crumb | bool | - |
| `aioseo_woocommerce_breadcrumb_hide_shop` | `$hide` (bool) | Hide the WooCommerce Shop page crumb | return `true` to hide | - (page published 2024-11-18) |

### Table of Contents block

| Hook | Args | Controls | Return | Since |
|---|---|---|---|---|
| `aioseo_toc_hash_prefix` | `$prefix` (string) | Prefix of anchor IDs/links generated by the TOC block | default `"aioseo-"`; any string or `''` | 4.7.1 |

### llms.txt / llms-full.txt

| Hook | Args | Controls | Return |
|---|---|---|---|
| `aioseo_llms_post_title` | `$title` (string), `$post` (WP_Post) | Post title in llms.txt and llms-full.txt | string; `''` excludes the post from the LLMS files |
| `aioseo_llms_term_title` | `$title` (string), `$term` (WP_Term) | Term name in llms.txt and llms-full.txt | string; `''` excludes the term |
| `aioseo_llms_post_description` | `$description` (string), `$post` (WP_Post) | Post description in llms.txt (source: AIOSEO meta description, else excerpt) | string; `''` omits the description |
| `aioseo_llms_term_description` | `$description` (string), `$term` (WP_Term) | Term description in llms.txt (source: AIOSEO meta description, else term description) | string; `''` omits the description |

Page published 2026-01-08, no since-version given. The vendor code declares the object as optional (`$post = null`, `$term = null`) and guards with `is_a( $post, 'WP_Post' )`, which suggests the object may be missing in some call paths. The title filters apply to both files; the description filter pages say only "llms.txt" (open question).

### Shortcodes and editor integration

| Hook | Args | Controls | Default / return | Since |
|---|---|---|---|---|
| `aioseo_conflicting_shortcodes` | `$conflictingShortcodes` (array, `'Label' => '[shortcode_tag]'`) (from code) | Shortcodes AIOSEO will not parse | array; merge in more | - |
| `aioseo_disable_shortcode_parsing` | `$disabled` (bool) | Stops AIOSEO parsing shortcodes at all | `false` | - |
| `aioseo_disable_link_format` | `$disabled` (bool) | Disables the custom link format AIOSEO adds to Block Editor and Classic Editor | return `true` to disable | - |
| `aioseo_page_builder_integration_disable` | `$disabled` (bool), `$pagebuilder` (string, builder name) | Disables AIOSEO's page builder integrations | return `true` to disable | 4.1.7 |
| `aioseo_post_metabox_priority` | `$priority` (string) | Priority of the AIOSEO metabox on Edit Post/Term screens | `'high'`; [WordPress values: `high`, `core`, `default`, `low`] | - |

### Admin UI, access, users

| Hook | Args | Controls | Default / return | Since |
|---|---|---|---|---|
| `aioseo_show_in_admin_bar` | `$enabled` (bool) | AIOSEO admin bar menu | `true` | - |
| `aioseo_show_seo_news` | `$enabled` (bool) | AIOSEO dashboard widget (SEO News) | `true` | - |
| `aioseo_flyout_menu_enable` (confirmed by code; page URL says `_disable`) | `$enabled` (bool) | AIOSEO flyout (floating help) menu in admin | return `false` to hide | 4.1.5 |
| `aioseo_access_control_excluded_roles` | `$roles` (array of role slugs, e.g. `'customer'`) (from code) | Roles excluded/ignored by Access Control (Pro) | array | 4.1.4 |
| `aioseo_public_post_types` | `$postTypes` (array; items are arrays with `name` when not names-only), `$namesOnly` (bool), `$hasArchivesOnly` (bool) | Post types AIOSEO treats as public (settings screens, sitemaps, etc.) | array | 4.1.6 |
| `aioseo_public_taxonomies` | `$taxonomies` (array; items arrays with `name`), `$namesOnly` (bool) | Taxonomies AIOSEO treats as public | array | 4.1.6 |
| `aioseo_user_profile_tab_disable` | `$disable` (bool) | Hides the AIOSEO social profile fields on the WP Edit Profile page | return `true` to hide (code); prose says "defaults to true" | 4.2.2 |
| `aioseo_user_profile_tab_allowed_user_ids` | `$user_ids` (array), `$user_id` (int, current user) | Lets listed users without editing permissions edit their own Author SEO data | array | - (page published 2024-05-21) |

### Importers, redirects, email reports

| Hook | Args | Controls | Default / return | Since |
|---|---|---|---|---|
| `aioseo_import_rank_math_posts_per_action` | `$number` (int) | Posts per batch when importing from Rank Math | `100` (code example sets 250) | - |
| `aioseo_import_seopress_posts_per_action` | `$number` (int) | Posts per batch, SEOPress import | `100` | - |
| `aioseo_import_yoast_seo_posts_per_action` | `$number` (int) | Posts per batch, Yoast SEO import | `100` | - |
| `aioseo_redirects_log_skip` | `$skip` (bool), `$data` (array; keys `http_code` (int, e.g. 404) and `url` (request path, e.g. `'/config.json'`) from code) | Skip writing a Redirects log / 404 log entry (Redirects addon) | return `true` to skip | - (page published 2024-03-19) |
| `aioseo_report_summary_enable` | (bool) | Delivery of SEO Email Reports. Does not affect **Send Test Email** | return `false` to stop delivery | 4.7.7 |

### Local Business addon (Locations, business info / opening hours output)

| Hook | Args | Controls | Default | Since |
|---|---|---|---|---|
| `aioseo_local_business_post_type` | `$post_type` (array, register_post_type args; `supports` is an array) | Location CPT registration options | - | - |
| `aioseo_local_business_post_type_name` | `$name` (string) | CPT name | `aioseo-location` | - |
| `aioseo_local_business_post_type_slug` | `$slug` (string) | CPT rewrite slug | `location` | - |
| `aioseo_local_business_post_type_single_label` | `$label` (string) | CPT singular label | `Location` | - |
| `aioseo_local_business_post_type_plural_label` | `$label` (string) | CPT plural label | `Locations` | - |
| `aioseo_local_business_taxonomy` | `$taxonomy` (array, register_taxonomy args) | Location category taxonomy options | - | - |
| `aioseo_local_business_taxonomy_name` | `$name` (string) | Taxonomy name | `aioseo-location-category` | - |
| `aioseo_local_business_taxonomy_slug` | `$slug` (string) | Taxonomy rewrite slug | `locations-category` | - |
| `aioseo_local_business_get_location` | `$information` (object; business name at `$information->locations->business->name`), `$postId` (int, location ID) | Location information when retrieved (affects schema and output) | - | - |
| `aioseo_local_business_address_tags` | `$tags` (list of tag arrays, each with `id`, e.g. `'streetLineTwo'`) (from code) | Available address-format tags | - | - |
| `aioseo_local_business_address_tag_value` | `$tagValue` (string), `$tag` (array with `id`), `$id` (int, page/post ID) | The replaced value of one address-format tag | - | - |
| `aioseo_local_business_output_business_info_instance` | `$instance` (array of display toggles, e.g. `showPhone`), `$postId` (int), `$locationData` (object) | Business info display options | - | - |
| `aioseo_local_business_output_business_info_location_data` | `$locationData` (object; `name`), `$instance` (array), `$postId` (int) | Business info data being rendered | - | - |
| `aioseo_local_business_output_opening_hours_instance` | `$instance` (array; day toggles e.g. `showSunday`), `$postId` (int), `$openingHoursData` (object) | Opening hours display options | - | - |
| `aioseo_local_business_output_opening_hours_data` | `$openingHoursData` (object; labels at `->labels`, e.g. `->labels->closed`), `$instance` (array), `$postId` (int) | Opening hours data being rendered | - | - |
| `aioseo_local_business_info_email_icon` | `$icon` (string HTML; prose says SVG, code returns an `<img>` tag) | Email icon in business info | - | - |
| `aioseo_local_business_info_location_icon` | `$icon` (string HTML) | Location (address) icon | - | - |
| `aioseo_local_business_info_phone_icon` | `$icon` (string HTML) | Phone icon | - | - |
| `aioseo_local_business_opening_hours_icon` | `$icon` (string HTML) | Opening hours icon | - | - |

Count: 80 hooks from single pages + 4 LLMS hooks = 84 distinct filters.

## Output control hooks
Sources: https://aioseo.com/docs/aioseo_disable/, https://aioseo.com/docs/aioseo_meta_views/, https://aioseo.com/docs/aioseo_disable_title_rewrites/, https://aioseo.com/docs/aioseo_flush_output_buffer/, https://aioseo.com/docs/aioseo_schema_disable/, https://aioseo.com/docs/aioseo_hide_version_number/, https://aioseo.com/docs/outputting-aioseos-data-in-the-head-without-using-wp_head/

- `aioseo_disable` is the all-or-nothing switch. `aioseo_meta_views` is the granular one: return `[]` for nothing, or drop `social` / `schema` / `meta`. `analytics` is deprecated (GA moved out of AIOSEO).
- `aioseo_flush_output_buffer`: AIOSEO rewrites the title via output buffering. If another plugin also buffers (some caching/optimisation plugins) and titles break or output duplicates, return `false`.
- `aioseo_schema_disable` example disables schema on WooCommerce single products (useful when WooCommerce or another plugin outputs its own Product schema).

`aioseo_disable` (no output on term archives):
```php
add_filter( 'aioseo_disable', 'aioseo_disable_term_output' );
function aioseo_disable_term_output( $disabled ) {
   if ( is_category() || is_tag() || is_tax() ) {
      return true;
   }
   return false;
}
```
Note: returns `false` instead of `$disabled` otherwise, which overrides any other callback that disabled output. Return `$disabled` in your own code.

`aioseo_meta_views` (nothing on category archives):
```php
add_filter( 'aioseo_meta_views', 'aioseo_filter_meta_views' );
function aioseo_filter_meta_views( $views ) {
   if ( is_category() ) {
      return [];
   }
   return $views;
}
```

`aioseo_disable_title_rewrites` (no title rewrite on term archives; same `return false` caveat):
```php
add_filter( 'aioseo_disable_title_rewrites', 'aioseo_disable_term_title_rewrites' );
function aioseo_disable_term_title_rewrites( $disabled ) {
   if ( is_category() || is_tag() || is_tax() ) {
      return true;
   }
   return false;
}
```

```php
add_filter( 'aioseo_flush_output_buffer', '__return_false' );
```

`aioseo_schema_disable` (uses the helper `aioseo()->helpers->isWooCommerceActive()`):
```php
add_filter( 'aioseo_schema_disable', 'aioseo_disable_schema_products' );
function aioseo_disable_schema_products( $disabled ) {
   if ( is_singular( 'product' ) && aioseo()->helpers->isWooCommerceActive() ) {
      return true;
   }
   return $disabled;
}
```

```php
add_filter( 'aioseo_hide_version_number', '__return_true' );
```

### Outputting head data without `wp_head()` (verbatim from docs)
For themes that do not call `wp_head()`:
```php
if ( function_exists( 'aioseo' ) ) {
	aioseo()->head->output();
}
```
Control which sections print with `aioseo_meta_views`.

## Title, description, keywords
Sources: https://aioseo.com/docs/aioseo_title/, https://aioseo.com/docs/aioseo_description/, https://aioseo.com/docs/aioseo_keywords/

- These filter the final rendered strings (after smart tags are replaced), not the stored values. To change stored values use `aioseo_save_post` or the REST API.
- Prose says "each post"; code uses `is_singular()`, i.e. every singular page/post/CPT.
- [Note: Google does not use meta keywords; `aioseo_keywords` only matters for other engines/legacy. Google truncates titles/descriptions by pixel width anyway.]

Append to title / limit title to 60 characters:
```php
add_filter( 'aioseo_title', 'aioseo_filter_title' );
function aioseo_filter_title( $title ) {
   if ( is_singular() ) {
      return $title . 'some additional title content here';
   }
   return $title;
}
```
```php
add_filter( 'aioseo_title', 'aioseo_filter_title' );
function aioseo_filter_title( $title ) {
   if ( strlen($title) > 60 ) {
      $title = substr($title, 0, 60);
   }
   return $title;
}
```
**Bug in doc code:** `strlen`/`substr` count bytes, so non-ASCII titles are cut short and can be cut mid-character (broken UTF-8). Use `mb_strlen`/`mb_substr`. Also both snippets declare `aioseo_filter_title`; using both is a fatal error.

Limit description / append to description:
```php
add_filter( 'aioseo_description', 'aioseo_filter_description' );
function aioseo_filter_description( $description ) {
   if ( strlen($description) > 160 ) {
      $description = substr($description, 0, 159);
   }
   return $description;
}
```
```php
add_filter( 'aioseo_description', 'aioseo_filter_description' );
function aioseo_filter_description( $description ) {
   if ( is_singular() ) {
      return $description . 'some additional description content here';
   }
   return $description;
}
```
Same byte-vs-character bug; this one cuts to 159 characters although the prose says 160. Same duplicate function name.

`aioseo_keywords` (add a keyword on singular pages):
```php
add_filter( 'aioseo_keywords', 'aioseo_filter_keywords' );
function aioseo_filter_keywords( $keywords ) {
   if ( is_singular() ) {
      $keywords = explode( ',', $keywords );
      array_push( $keywords, 'anotherkeyword' );
      $keywords = implode( ',', $keywords );
   }
   return $keywords ;
}
```

## Canonical, robots meta, rel next/prev
Sources: https://aioseo.com/docs/aioseo_canonical_url/, https://aioseo.com/docs/aioseo_robots_meta/, https://aioseo.com/docs/aioseo_next_link/, https://aioseo.com/docs/aioseo_prev_link/

Canonical: prose says the example removes it "for posts"; code removes it on every singular page.
```php
add_filter( 'aioseo_canonical_url', 'aioseo_filter_canonical_url' );
function aioseo_filter_canonical_url( $url ) {
   if ( is_singular() ) {
      return '';
   }
   return $url;
}
```
[Note: removing canonicals is rarely a good idea; change the URL instead.]

Robots attributes (the structure the page documents):
```php
$attributes = [
	'noindex'           => '',
	'nofollow'          => '',
	'noarchive'         => '',
	'nosnippet'         => '',
	'noimageindex'      => '',
	'noodp'             => '',
	'notranslate'       => '',
	'max-snippet'       => '',
	'max-image-preview' => '',
	'max-video-preview' => ''
];
```
Example (the prose says it adds `index` and `nofollow`; the code actually sets **`noindex`** and `nofollow` on every singular page, which deindexes the whole site's content if copied):
```php
add_filter( 'aioseo_robots_meta', 'aioseo_filter_robots_meta' );
function aioseo_filter_robots_meta( $attributes ) {
   if ( is_singular() ) {
      $attributes['noindex']  = 'noindex';
      $attributes['nofollow'] = 'nofollow';
   }
   return $attributes;
}
```
So to emit a directive set its key to its own name; `''` means not set. There is no `index` key; "index" is the absence of `noindex`.

Rel next/prev (suppress):
```php
add_filter( 'aioseo_next_link', 'aioseo_filter_next_link' );
function aioseo_filter_next_link( $next ) {
   return '';
}
```
```php
add_filter( 'aioseo_prev_link', 'aioseo_filter_prev_link' );
function aioseo_filter_prev_link( $previous ) {
   return '';
}
```
[Note: Google stopped using rel=next/prev in 2019; Bing still reads them.]

## Social tags (Open Graph, Twitter) and social image
Sources: https://aioseo.com/docs/aioseo_facebook_tags/, https://aioseo.com/docs/aioseo_twitter_tags/, https://aioseo.com/docs/aioseo_thumbnail_size/, https://aioseo.com/docs/aioseo_social_image_ignore_cover_block/

- Tag arrays are keyed by the tag property/name. The pages' own list of keys did not survive (the Twitter list embed is empty; no Facebook list embed exists in the recovered set). The lists are described as "not exhaustive".

Change `og:title` for post ID 14:
```php
add_filter( 'aioseo_facebook_tags', 'aioseo_filter_facebook_title' );
function aioseo_filter_facebook_title( $facebookMeta ) {
   if ( is_singular() && 14 === get_the_ID() ) {
      $facebookMeta['og:title'] = "A different title";
   }
   return $facebookMeta;
}
```
Remove the article date tags (setting the value to `''` drops the tag):
```php
add_filter( 'aioseo_facebook_tags', 'aioseo_filter_facebook_article_tags' );
function aioseo_filter_facebook_article_tags( $facebookMeta ) {
   if ( is_singular() ) {
      $facebookMeta['article:published_time'] = '';
      $facebookMeta['article:modified_time']  = '';
   }
   return $facebookMeta;
}
```
Remove all OG tags on URLs containing `/listing-detail/` (this snippet is in the embed set but is not described in the page prose):
```php
add_filter( 'aioseo_facebook_tags', 'aioseo_filter_remove_facebook_tags' );
function aioseo_filter_remove_facebook_tags( $facebookMeta ) {
    $uri = parse_url( $_SERVER['REQUEST_URI'], PHP_URL_PATH );
    if ( strpos( $uri, '/listing-detail/' ) !== false ) {
        return array();
    }
    return $facebookMeta;
}
```

Change the Twitter title for post 14:
```php
add_filter( 'aioseo_twitter_tags', 'aioseo_filter_twitter_title' );
function aioseo_filter_twitter_title( $twitterMeta ) {
   if ( is_singular() && '14' === get_the_ID() ) {
      $twitterMeta['twitter:title'] = "A different title";
   }
   return $twitterMeta;
}
```
**Bug in doc code:** `'14' === get_the_ID()` compares a string to the int that `get_the_ID()` returns, so it is never true. Use `14 === get_the_ID()` as the Facebook example does.

`og:image` size:
```php
add_filter( 'aioseo_thumbnail_size', function( $imageSize ) {
    return 'large';
} );
```

Cover block as social image:
```php
add_filter( 'aioseo_social_image_ignore_cover_block', '__return_true' );
```
**Code/prose conflict:** the prose says the filter "enables you to use the image in a Cover block" and that `$ignore` "defaults to true" (Cover blocks ignored). The code returns `true`, which by that description is the default and changes nothing. To actually use Cover block images with "First Image in Content", return `false` (`'__return_false'`). Test before relying on either.

## Schema hooks
Sources: https://aioseo.com/docs/aioseo_schema_disable/, https://aioseo.com/docs/aioseo_schema_graphs/, https://aioseo.com/docs/aioseo_schema_output/, https://aioseo.com/docs/aioseo_schema_json_flags/, https://aioseo.com/docs/removing-published-date-from-article-schema/

- `aioseo_schema_graphs` works on graph **names** before they are built. `aioseo_schema_output` works on the **built** graphs (each an array with `@type` and properties).

Add Article graph to posts:
```php
add_filter( 'aioseo_schema_graphs', 'aioseo_filter_schema_graphs' );
function aioseo_filter_schema_graphs( $graphs ) {
   if ( is_singular( 'post' ) && ! in_array( 'Article', $graphs, true ) ) {
      $graphs[] = 'Article';
   }
   return $graphs;
}
```

Remove Article schema on posts:
```php
add_filter( 'aioseo_schema_output', 'aioseo_filter_schema_output' );
function aioseo_filter_schema_output( $graphs ) {
	if ( is_singular( 'post' ) ) {
 	   foreach ( $graphs as $index => $graph ) {
			if ( 'Article' === $graph['@type'] ) {
				unset( $graphs[ $index ] );
			}
		}
	}
	return $graphs;
}
```
Remove the author from Article on posts (also removes the `Person` graph that the author points to):
```php
add_filter( 'aioseo_schema_output', 'aioseo_filter_schema_output' );
function aioseo_filter_schema_output( $graphs ) {
	if ( is_singular( 'post' ) ) {
 	   foreach ( $graphs as $index => $graph ) {
			if ( 'Article' === $graph['@type'] ) {
				unset( $graphs[ $index ]['author'] );
			}
			if ( 'Person' === $graph['@type'] ) {
				unset( $graphs[ $index ] );
			}
		}
	}
	return $graphs;
}
```
Remove `BreadcrumbList` **and** the `breadcrumb` reference other graphs (e.g. WebPage) hold to it, so no dangling `@id` reference remains:
```php
add_filter( 'aioseo_schema_output', 'aioseo_filter_schema_output' );
function aioseo_filter_schema_output( $graphs ) {
    foreach ( $graphs as $index => $graph ) {
		if ( 'BreadcrumbList' === $graph['@type'] ) {
			unset( $graphs[ $index ] );
		}
		foreach ( $graph as $key => $value ) {
			if ( 'breadcrumb' === $key ) {
				unset( $graphs[ $index ][ $key ] );
			}
		}
	}
	return $graphs;
}
```
Remove `datePublished`/`dateModified` from Article/BlogPosting/NewsArticle (identical to the "Removing Published Date from Article Schema" guide):
```php
add_filter( 'aioseo_schema_output', 'aioseo_filter_schema_output' );
function aioseo_filter_schema_output( $schema ) {
	foreach ( $schema as $index => $graphData ) {
		if ( empty( $graphData['@type'] ) ) {
			continue;
		}
		$type = strtolower( $graphData['@type'] );
		switch ( $type ) {
			case 'article':
			case 'blogposting':
			case 'newsarticle':
				unset( $schema[ $index ]['datePublished'] );
				unset( $schema[ $index ]['dateModified'] );
				break;
			default:
				break;
		}
	}
	return $schema;
}
```
Gotcha from the guide: Google may still show the date; check the theme and other plugins for dates in the source (visible bylines, OG `article:*_time` tags, other schema). [Note: also strip the OG date tags with `aioseo_facebook_tags` (example above). Google's guidance is to give correct dates rather than hide them; hiding them does not reliably remove dates from results.]
Code notes: the Article examples compare `'Article' === $graph['@type']` exactly, so they miss `BlogPosting`/`NewsArticle` graphs (use the lowercase switch from the date example), and they leave gaps in the array indexes (harmless for `json_encode` of a graph list only if AIOSEO re-indexes; add `array_values()` if output turns into an object). `strtolower()` would error if a graph's `@type` is an array (possible with custom graphs); guard with `is_string()`.

`aioseo_schema_json_flags` (4.3.3). The example **replaces** the flags (it ignores the incoming value) with pretty-print, unescaped slashes and unescaped unicode:
```php
add_filter( 'aioseo_schema_json_flags', function() {
	return JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE;
} );
```
AIOSEO says "some users report better SEO performance when non-Latin unicode characters are not escaped". [Note: escaped `\uXXXX` and literal UTF-8 are equivalent JSON and Google parses both; this is readability, not ranking. `JSON_PRETTY_PRINT` adds page weight; to only stop escaping use `fn( $flags ) => $flags | JSON_UNESCAPED_UNICODE`.]

## Post/term data model, translations API
Sources: https://aioseo.com/docs/aioseo_get_post/, https://aioseo.com/docs/aioseo_get_term/, https://aioseo.com/docs/aioseo_save_post/, https://aioseo.com/docs/aioseo_save_term/, https://aioseo.com/docs/aioseo_get_post_id/, https://aioseo.com/docs/localizing-aioseo-data-via-the-translations-api/

- AIOSEO stores per-post/term SEO data in its own tables **`aioseo_posts`** and **`aioseo_terms`** (with the WP table prefix, e.g. `wp_aioseo_posts`), not in post/term meta. `get_post_meta()` will not find it and multilingual plugins cannot translate it like normal meta.
- Introduced in 4.2.2 for multilingual plugin developers: localise post/term meta output, integrate with the multilingual sitemap, localise AIOSEO options (e.g. default title/description formats; no hook for options is named).
- Load filters `aioseo_get_post` / `aioseo_get_term`: data is typically loaded once per request and should stay consistent through the request. Receive and return the model object. Properties are "subject to change" and not documented; the examples use `post_id` / `term_id` (cast with `(int)`) and `title`.
- Save filters `aioseo_save_post` / `aioseo_save_term` run before save. **Gotcha:** in the Block Editor the save hook runs **twice** (once via the editor's REST save, once via the regular POST request). Make callbacks idempotent (assign, never append). AIOSEO sanitises filtered data but asks you to sanitise too.
- Term model class is `AIOSEO\Pro\Models\Term` (Pro namespace), so term hooks are a Pro feature.
- Confirmed compatible: WPML. Possibly compatible, unconfirmed: TranslatePress, Polylang, Weglot, MultilingualPress, qTranslate-XT, WPGlobus.

```php
add_filter( "aioseo_get_post", "aioseo_filter_post_data" );
function aioseo_filter_post_data( $post ) {
	if ( 10 === (int) $post->post_id ) {
		$post->title = 'Some new title here';
	}
	return $post;
}
```
```php
add_filter( "aioseo_get_term", "aioseo_filter_term_data" );
function aioseo_filter_term_data( $term ) {
	if ( 12 === (int) $term->term_id ) {
		$term->title = 'Some new title here';
	}
	return $term;
}
```
```php
add_filter( "aioseo_save_post", "aioseo_filter_post_data" );
function aioseo_filter_post_data( $post ) {
	if ( 10 === (int) $post->post_id ) {
		$post->title = 'Some new title here';
	}
	return $post;
}
```
```php
add_filter( "aioseo_save_term", "aioseo_filter_term_data" );
function aioseo_filter_term_data( $term ) {
	if ( 12 === (int) $term->term_id ) {
		$term->title = 'Some new title here';
	}
	return $term;
}
```
(The load and save examples reuse the function names `aioseo_filter_post_data` / `aioseo_filter_term_data`; rename if you use both.)

`aioseo_get_post_id`: use another post's SEO data on a page that is not a post, here the `product` archive (WooCommerce Shop):
```php
add_filter( 'aioseo_get_post_id', 'aioseo_change_post_id' );
function aioseo_change_post_id( $postId ) {
	if( is_post_type_archive( 'product' ) ) {
		$postId = 123;
	}
	return $postId;
}
```

[Note: in AIOSEO's source the post model has further columns such as `description`, `keywords`, `keyphrases`, `canonical_url`, `og_title`, `og_description`, `twitter_title`, `robots_noindex`, `robots_nofollow`, `schema`, `priority`, `frequency`. Not stated in these docs; check the REST `aioseo_meta_data` field for the exact list.]

## Sitemap hooks
Sources: https://aioseo.com/docs/aioseo_sitemap_additional_pages/, https://aioseo.com/docs/aioseo_sitemap_exclude_posts/, https://aioseo.com/docs/aioseo_sitemap_exclude_terms/, https://aioseo.com/docs/aioseo_sitemap_images/, https://aioseo.com/docs/aioseo_sitemap_indexes/, https://aioseo.com/docs/aioseo_sitemap_lastmod_disable/, https://aioseo.com/docs/aioseo_sitemap_post/, https://aioseo.com/docs/aioseo_sitemap_term/, https://aioseo.com/docs/aioseo_sitemap_rss/

Additional pages (needs **All in One SEO > Sitemaps > Additional Pages** On):
```php
add_filter( 'aioseo_sitemap_additional_pages', 'aioseo_sitemap_add_additional_pages' );
function aioseo_sitemap_add_additional_pages( $pages ) {
	$pages[] = [
		'loc'        => 'https://example.com/additional-page',
		'lastmod'    => '2020-12-11 11:11',
		'changefreq' => 'always',
		'priority'   => (float) 1.0
	];
	return $pages;
}
```

Exclude post 614 / term 412 from the XML sitemap (`$type` `'general'` = XML sitemap; other sitemaps such as video/news/RSS presumably pass other values):
```php
add_filter( 'aioseo_sitemap_exclude_posts', 'aioseo_sitemap_filter_excluded_posts', 10, 2 );
function aioseo_sitemap_filter_excluded_posts( $ids, $type ) {
   if ( 'general' === $type ) {
      $ids[] = 614;
   }
   return $ids;
}
```
```php
add_filter( 'aioseo_sitemap_exclude_terms', 'aioseo_sitemap_filter_excluded_terms', 10, 2 );
function aioseo_sitemap_filter_excluded_terms( $ids, $type ) {
   if ( 'general' === $type ) {
      $ids[] = 412;
   }
   return $ids;
}
```

Images from an ACF Image field `custom_image` (field must return an array with `id`). Entries are plain image URL strings:
```php
add_filter( 'aioseo_sitemap_images', 'aioseo_filter_sitemap_images', 10, 2 );
function aioseo_filter_sitemap_images( $images, $post ) {
	if ( ! function_exists( 'get_field' ) ) {
		return $images;
	}
	$customImage = get_field( 'custom_image', $post->ID );
	if ( ! empty( $customImage ) ) {
		$images[] = wp_get_attachment_image_url( $customImage['id'] );
	}
	return $images;
}
```

Extra index in the root sitemap index. `lastmod` uses the helper `aioseo()->helpers->dateTimeToIso8601()`. The prose says each index has "two properties" then lists three (`loc`, `lastmod`, `count`) and writes "ISO 8061" (typo for 8601):
```php
add_filter( 'aioseo_sitemap_indexes', 'aioseo_add_sitemap_index' );
function aioseo_add_sitemap_index( $indexes ) {
	$indexes[] = [
		'loc'     => 'https://somedomain.com/custom-sitemap.xml',
		'lastmod' => aioseo()->helpers->dateTimeToIso8601( '2021-09-08 12:02' ),
		'count'   => 1000
	];
	return $indexes;
}
```

Remove lastmod from post type and taxonomy sitemaps in the index (not date/author archive sitemaps):
```php
add_filter( 'aioseo_sitemap_lastmod_disable', '__return_true' );
```

Multilingual alternates for post 10 / term 12:
```php
add_filter( "aioseo_sitemap_post", "aioseo_filter_sitemap_post", 10, 2 );
function aioseo_filter_sitemap_post( $entry, $postId ) {
	if ( 10 === $postId ) {
		// Set the language code for the main URL.
        $entry['language']  = 'en_US'
		// Add the translated versions (language code + URL).
		$entry['languages'] = [
			[
				'language' => 'en_CA'
				'location' => 'https://example.com/ca/page
			],
			[
				'language' => 'en_UK'
				'location' => 'https://example.com/uk/page
			]
		];
	}
	return $entry;
}
```
```php
add_filter( "aioseo_sitemap_term", "aioseo_filter_sitemap_term", 10, 2 );
function aioseo_filter_sitemap_term( $entry, $termId ) {
	if ( 12 === $termId) {
		// Set the language code for the main URL.
        $entry['language']  = 'en_US'
		// Add the translated versions (language code + URL).
		$entry['languages'] = [
			[
				'language' => 'en_CA'
				'location' => 'https://example.com/ca/page
			],
			[
				'language' => 'en_UK'
				'location' => 'https://example.com/uk/page
			]
		];
	}
	return $entry;
}
```
**Bug in doc code:** both snippets are not valid PHP: missing `;` after `$entry['language'] = 'en_US'`, missing `,` after each `'language' => '...'`, and unterminated strings (`'https://example.com/ca/page` has no closing quote). Pasting them causes a parse error that can take the site down (WPCode would refuse to activate them). Also `en_UK` is not a valid locale (`en_GB`). **Signature note:** the prose lists 3 parameters (`$entry, $postId, $postType` / `$entry, $termId, $taxonomy`) but the code registers only 2 (`10, 2`); use `10, 3` if you need the type/taxonomy. Corrected form:
```php
add_filter( 'aioseo_sitemap_post', function ( $entry, $postId, $postType ) {
	if ( 10 === $postId ) {
		$entry['language']  = 'en_US';
		$entry['languages'] = [
			[ 'language' => 'en_CA', 'location' => 'https://example.com/ca/page' ],
			[ 'language' => 'en_GB', 'location' => 'https://example.com/uk/page' ],
		];
	}
	return $entry;
}, 10, 3 );
```

RSS sitemap: convert `pubDate` to another timezone, for platforms that require one (e.g. Yandex News / Zen / Dzen):
```php
add_filter( 'aioseo_sitemap_rss', 'aioseo_filter_rss_sitemap_entries' );
function aioseo_filter_rss_sitemap_entries( $entries ) {
	$entries = array_map( function ( $entry ) {
		if ( empty( $entry['pubDate'] ) ) {
			return $entry;
		}
		$dateTime = new DateTime();
		$dateTime->setTimestamp( strtotime( $entry['pubDate'] ) );
		$dateTime->setTimezone( new DateTimeZone( 'Europe/Moscow' ) );
		$entry['pubDate'] = date_format( $dateTime, 'D, d M Y H:i:s O' );
		return $entry;
	}, $entries );
	return $entries;
}
```

[Note: AIOSEO sitemaps can be cached; after adding filters, re-save sitemap settings or clear caches to see changes. Not stated in these pages.]

## Breadcrumb hooks
Sources: https://aioseo.com/docs/aioseo_breadcrumbs_output/, https://aioseo.com/docs/aioseo_breadcrumbs_trail/, https://aioseo.com/docs/aioseo_breadcrumbs_template/, https://aioseo.com/docs/aioseo_breadcrumbs_separator/, https://aioseo.com/docs/aioseo_breadcrumbs_separator_symbol/, https://aioseo.com/docs/aioseo_breadcrumbs_show_current_item/, https://aioseo.com/docs/aioseo_breadcrumbs_link_current_item/, https://aioseo.com/docs/aioseo_woocommerce_breadcrumb_hide_shop/

Each crumb is an array whose `reference` is the source object (e.g. `WP_Term`, so `->slug` works).

```php
add_filter( 'aioseo_breadcrumbs_output', 'aioseo_breadcrumbs_output' );
function aioseo_breadcrumbs_output( $display ) {
	if ( is_singular( 'page' ) ) {
		$display = false;
	}
	return $display;
}
```
```php
add_filter( 'aioseo_breadcrumbs_trail', 'aioseo_breadcrumbs_trail' );
function aioseo_breadcrumbs_trail( $crumbs ) {
	foreach ( $crumbs as $key => $crumb ) {
		if ( is_a( $crumb['reference'], 'WP_Term' ) && 'uncategorized' === $crumb['reference']->slug ) {
			unset( $crumbs[ $key ] );
		}
	}
	return $crumbs;
}
```
`aioseo_breadcrumbs_template`. **Signature correction:** the prose says `$templateItem` is a string; the code treats it as an array and sets `$templateItem['template']`. The template HTML can use the smart tag `#breadcrumb_label`:
```php
add_filter( 'aioseo_breadcrumbs_template', 'aioseo_breadcrumbs_template', 10, 2 );
function aioseo_breadcrumbs_template( $templateItem, $crumb ) {
	if ( is_a( $crumb['reference'], 'WP_Term' ) && 'uncategorized' === $crumb['reference']->slug ) {
		$templateItem['template'] = '<span class="aioseo-breadcrumb">
			#breadcrumb_label
		</span>';
	}
	return $templateItem;
}
```
```php
add_filter( 'aioseo_breadcrumbs_separator', 'aioseo_breadcrumbs_separator' );
function aioseo_breadcrumbs_separator( $separator ) {
	if ( is_singular( 'page' ) ) {
		$separator = '<span class="my-separator">-></span>';
	}
	return $separator;
}
```
```php
add_filter( 'aioseo_breadcrumbs_separator_symbol', 'aioseo_breadcrumbs_separator_symbol' );
function aioseo_breadcrumbs_separator_symbol( $symbol ) {
	if ( is_singular( 'page' ) ) {
		$symbol = '->';
	}
	return $symbol;
}
```
```php
add_filter( 'aioseo_breadcrumbs_show_current_item', 'aioseo_breadcrumbs_show_current_item', 10, 3 );
function aioseo_breadcrumbs_show_current_item( $showCurrentItem, $type, $reference ) {
	if ( is_singular( 'page' ) ) {
		$showCurrentItem = false;
	}
	return $showCurrentItem;
}
```
```php
add_filter( 'aioseo_breadcrumbs_link_current_item', 'aioseo_breadcrumbs_link_current_item', 10 );
function aioseo_breadcrumbs_link_current_item( $linkCurrentItem ) {
	if ( is_singular( 'page' ) ) {
		$linkCurrentItem = false;
	}
	return $linkCurrentItem;
}
```
```php
add_filter( 'aioseo_woocommerce_breadcrumb_hide_shop', '__return_true' );
```
(The trail example leaves a gap in the array indexes; add `array_values()` if anything downstream expects a list.)

## Table of Contents prefix
Sources: https://aioseo.com/docs/aioseo_toc_hash_prefix/

- Default prefix `aioseo-` on TOC block anchors. Since 4.7.1. Only affects new posts and headings that do not already have an ID; existing anchors keep theirs.

```php
add_filter( 'aioseo_toc_hash_prefix', function( $prefix ) {
    return 'mysite-';
} );
```
```php
add_filter( 'aioseo_toc_hash_prefix', function( $prefix ) {
    return '';
} );
```

## llms.txt filters
Sources: https://aioseo.com/docs/aioseo-llms-filters/

- Customise how posts/terms appear in `/llms.txt` and `/llms-full.txt`. Each filter gets the value and the WP object (`WP_Post`/`WP_Term`) for conditional logic (ID, post type, taxonomy, meta).
- `''` from a title filter **excludes** that post/term from the LLMS files; `''` from a description filter omits only the description.
- All vendor examples register with `10, 2` and declare the object optional (`= null`) with an `is_a()` guard.

```php
add_filter( 'aioseo_llms_post_title', 'aioseo_filter_llms_post_title', 10, 2 );
function aioseo_filter_llms_post_title( $title, $post = null ) {
	if ( is_a( $post, 'WP_Post' ) && 14 === $post->ID ) {
		$title = 'Featured: ' . $title;
	}
	return $title;
}
```
```php
add_filter( 'aioseo_llms_term_title', 'aioseo_filter_llms_term_title', 10, 2 );
function aioseo_filter_llms_term_title( $title, $term = null ) {
    if ( is_a( $term, 'WP_Term' ) ) {
        $taxonomy = get_taxonomy( $term->taxonomy );
        if ( $taxonomy ) {
            $title = $taxonomy->labels->singular_name . ': ' . $title;
        }
    }
    return $title;
}
```
```php
add_filter( 'aioseo_llms_post_description', 'aioseo_filter_llms_post_description', 10, 2 );
function aioseo_filter_llms_post_description( $description, $post = null ) {
    if ( is_a( $post, 'WP_Post' ) && 14 === $post->ID ) {
        $description = 'This is a featured post. ' . $description;
    }
    return $description;
}
```
```php
add_filter( 'aioseo_llms_post_description', 'aioseo_filter_remove_llms_post_description', 10, 2 );
function aioseo_filter_remove_llms_post_description( $description, $post = null ) {
    if ( is_a( $post, 'WP_Post' ) && 14 === $post->ID ) {
        return '';
    }
    return $description;
}
```
```php
add_filter( 'aioseo_llms_term_description', 'aioseo_filter_llms_term_description', 10, 2 );
function aioseo_filter_llms_term_description( $description, $term = null ) {
    if ( is_a( $term, 'WP_Term' ) && 'category' === $term->taxonomy && $term->count > 0 ) {
        $description .= ' This category contains ' . $term->count . ' posts.';
    }
    return $description;
}
```

## Shortcode parsing, editor link format, page builders, metabox
Sources: https://aioseo.com/docs/aioseo_conflicting_shortcodes/, https://aioseo.com/docs/aioseo_disable_shortcode_parsing/, https://aioseo.com/docs/aioseo_disable_link_format/, https://aioseo.com/docs/aioseo_page_builder_integration_disable/, https://aioseo.com/docs/aioseo_post_metabox_priority/

- AIOSEO parses shortcodes in content (for generated descriptions and content-based smart tags). Some shortcodes conflict (break or have side effects), so AIOSEO keeps a list it never parses, keyed `'Label' => '[tag]'`. Add yours via `aioseo_conflicting_shortcodes`, or stop all parsing with `aioseo_disable_shortcode_parsing`.
- `aioseo_disable_link_format`: the link formats are enqueued **before the theme's `functions.php` loads**, so register it in a custom plugin or the Code Snippets plugin.
- `aioseo_page_builder_integration_disable` (4.1.7): the example only disables everything; the 2nd arg (builder name) allows per-builder disabling, but the name strings are not documented. [Note: AIOSEO integrates with Elementor, Divi, SeedProd, WPBakery, Avada, Thrive Architect, SiteOrigin; names are likely lowercase slugs such as `elementor`. Verify.]
- `aioseo_post_metabox_priority`: default `'high'`; set `'low'` to push the metabox below others.

```php
add_filter( 'aioseo_conflicting_shortcodes', 'aioseo_filter_conflicting_shortcodes' );
function aioseo_filter_conflicting_shortcodes( $conflictingShortcodes ) {
   $conflictingShortcodes = array_merge( $conflictingShortcodes, [
		'WISDM Group Registration' => '[wdm_group_users]',
		'WISDM Quiz Reporting'     => '[wdm_quiz_statistics_details]',
		'WISDM Course Review'      => '[rrf_course_review]'
   ] );
   return $conflictingShortcodes;
}
```
```php
add_filter( 'aioseo_disable_shortcode_parsing', '__return_true' );
```
```php
add_filter( 'aioseo_disable_link_format', '__return_true' );
```
```php
add_filter( 'aioseo_page_builder_integration_disable', '__return_true' );
```
```php
add_filter( 'aioseo_post_metabox_priority', 'aioseo_filter_metabox_priority' );
function aioseo_filter_metabox_priority( $priority) {
   return 'low';
}
```

## Admin UI, access control, public post types, user profile
Sources: https://aioseo.com/docs/aioseo_show_in_admin_bar/, https://aioseo.com/docs/aioseo_show_seo_news/, https://aioseo.com/docs/aioseo_flyout_menu_disable/, https://aioseo.com/docs/aioseo_access_control_excluded_roles/, https://aioseo.com/docs/aioseo_public_post_types/, https://aioseo.com/docs/aioseo_public_taxonomies/, https://aioseo.com/docs/aioseo_user_profile_tab_disable/, https://aioseo.com/docs/aioseo_user_profile_tab_allowed_user_ids/

```php
add_filter( 'aioseo_show_in_admin_bar', 'aioseo_disable_admin_bar' );
function aioseo_disable_admin_bar( $enabled ) {
   return false;
}
```
```php
add_filter( 'aioseo_show_seo_news', 'aioseo_disable_dashboard_widget' );
function aioseo_disable_dashboard_widget( $enabled ) {
   return false;
}
```

Flyout menu. **Resolved:** the hook is `aioseo_flyout_menu_enable` (code and page title agree; only the URL slug says `_disable`). Hide it for everyone except admins, using the helper `aioseo()->access->isAdmin()`:
```php
add_filter( 'aioseo_flyout_menu_enable', 'aioseo_filter_flyout_menu_enable' );
function aioseo_filter_flyout_menu_enable( $enabled ) {
	if ( ! aioseo()->access->isAdmin() ) {
		$enabled = false;
	}
	return $enabled;
}
```

Access Control (4.1.4): `$roles` is a list of role slugs. Remove `customer` from the excluded roles so it can be managed in Access Control:
```php
add_filter( 'aioseo_access_control_excluded_roles', 'aioseo_filter_access_control_excluded_roles' );
function aioseo_filter_access_control_excluded_roles( $roles ) {
	if ( ( $key = array_search( 'customer', $roles ) ) !== false ) {
		unset( $roles[ $key ] );
	}
	return $roles;
}
```

Public post types / taxonomies (4.1.6): remove the `movie` CPT / `genre` taxonomy from what AIOSEO treats as public (hides them from AIOSEO settings and sitemaps). Items are arrays with a `name` key; the post type example guards with `is_array()` because with `$namesOnly` the items are plain name strings. The taxonomy example lacks that guard and would break when names-only strings are passed. The taxonomy prose ("A list of roles being ignored") is a copy-paste error.
```php
add_filter( 'aioseo_public_post_types', 'aioseo_filter_public_post_types' );
function aioseo_filter_public_post_types( $postTypes ) {
  $filteredPostTypes = [];
  foreach ( $postTypes as $postTypeObject ) {
    if ( is_array( $postTypeObject ) && 'movie' === $postTypeObject['name'] ) {
      continue;
    }
    $filteredPostTypes[] = $postTypeObject;
  }
  return $filteredPostTypes;
}
```
```php
add_filter( 'aioseo_public_taxonomies', 'aioseo_filter_public_taxonomies' );
function aioseo_filter_public_taxonomies( $taxonomies ) {
	$filteredTaxonomies = [];
	foreach ( $taxonomies as $taxonomiesObject ) {
		if ( 'genre' === $taxonomiesObject['name'] ) {
			continue;
		}
		$filteredTaxonomies[] = $taxonomiesObject;
	}
	return $filteredTaxonomies;
}
```

Hide the social profile fields on Edit Profile (4.2.2). The code returns `true` to hide, so the real default is presumably `false`, despite the prose's "defaults to true":
```php
add_filter( "aioseo_user_profile_tab_disable", "__return_true" );
```

Author SEO for users without edit rights. The example adds the current user whenever they lack `edit_posts`, i.e. it opens Author SEO editing to every such user (subscribers included). Use a fixed ID list to restrict:
```php
add_filter( 'aioseo_user_profile_tab_allowed_user_ids', 'aioseo_profile_tab_allowed_users', 10, 2 );
function aioseo_profile_tab_allowed_users( $user_ids, $user_id ) {
	if ( ! user_can( $user_id, 'edit_posts' ) ) {
		$user_ids[] = $user_id;
	}
	return $user_ids;
}
```

## Importers, redirect logs, email reports
Sources: https://aioseo.com/docs/aioseo_import_rank_math_posts_per_action/, https://aioseo.com/docs/aioseo_import_seopress_posts_per_action/, https://aioseo.com/docs/aioseo_import_yoast_seo_posts_per_action/, https://aioseo.com/docs/aioseo_redirects_log_skip/, https://aioseo.com/docs/aioseo_report_summary_enable/

- Import batch size defaults to 100 posts per action. Examples raise it to 250. Lower it on weak hosts (timeouts). [Note: imports run as Action Scheduler batches.]

```php
add_filter( 'aioseo_import_rank_math_posts_per_action', 'aioseo_increase_rank_math_posts_import');
function aioseo_increase_rank_math_posts_import( $number ) {
	return 250;
}
```
```php
add_filter( 'aioseo_import_seopress_posts_per_action', 'aioseo_increase_seopress_posts_import');
function aioseo_increase_seopress_posts_import( $number ) {
	return 250;
}
```
```php
add_filter( 'aioseo_import_yoast_seo_posts_per_action', 'aioseo_increase_yoast_posts_import');
function aioseo_increase_yoast_posts_import( $number ) {
	return 250;
}
```

`aioseo_redirects_log_skip` (Redirects addon). `$data['http_code']` (int) and `$data['url']` (path). Skip 404 logging for specific URLs, or for all 404s. Both snippets declare `redirects_log_skip`; use one:
```php
add_filter( 'aioseo_redirects_log_skip', 'redirects_log_skip', 10, 2 );
function redirects_log_skip( $skip, $data ) {
    // Define a list of unwanted URLs
    $ignoreUrls = [
        '/config.json',
        '/home',
        '/main',
        '/server-status',
        '/private'
    ];
    // Skip logging these URLs if they result in a 404 error
    if ( 404 === $data['http_code'] && in_array( $data['url'], $ignoreUrls, true ) ) {
        $skip = true;
    }
    return $skip;
}
```
```php
add_filter( 'aioseo_redirects_log_skip', 'redirects_log_skip', 10, 2 );
function redirects_log_skip( $skip, $data ) {
	if ( 404 === $data['http_code'] ) {
		$skip = true;
	}
	return $skip;
}
```
[Note: `in_array( $data['url'], ... , true )` is an exact match; query strings or trailing slashes defeat it.]

Stop SEO Email Report delivery (4.7.7; Send Test Email still works):
```php
add_filter( 'aioseo_report_summary_enable', '__return_false' );
```

## Local Business hooks
Sources: https://aioseo.com/docs/aioseo_local_business_post_type/, https://aioseo.com/docs/aioseo_local_business_post_type_name/, https://aioseo.com/docs/aioseo_local_business_post_type_slug/, https://aioseo.com/docs/aioseo_local_business_post_type_single_label/, https://aioseo.com/docs/aioseo_local_business_post_type_plural_label/, https://aioseo.com/docs/aioseo_local_business_taxonomy/, https://aioseo.com/docs/aioseo_local_business_taxonomy_name/, https://aioseo.com/docs/aioseo_local_business_taxonomy_slug/, https://aioseo.com/docs/aioseo_local_business_get_location/, https://aioseo.com/docs/aioseo_local_business_address_tags/, https://aioseo.com/docs/aioseo_local_business_address_tag_value/, https://aioseo.com/docs/aioseo_local_business_output_business_info_instance/, https://aioseo.com/docs/aioseo_local_business_output_business_info_location_data/, https://aioseo.com/docs/aioseo_local_business_output_opening_hours_instance/, https://aioseo.com/docs/aioseo_local_business_output_opening_hours_data/, https://aioseo.com/docs/aioseo_local_business_info_email_icon/, https://aioseo.com/docs/aioseo_local_business_info_location_icon/, https://aioseo.com/docs/aioseo_local_business_info_phone_icon/, https://aioseo.com/docs/aioseo_local_business_opening_hours_icon/

Needs the Local Business addon (Plus and up per AIOSEO pricing; not stated in these pages). With multiple locations AIOSEO registers a CPT and taxonomy:

| Item | Default | Filter |
|---|---|---|
| Post type name | `aioseo-location` | `aioseo_local_business_post_type_name` |
| Post type slug | `location` | `aioseo_local_business_post_type_slug` |
| Singular / plural label | `Location` / `Locations` | `..._post_type_single_label` / `..._post_type_plural_label` |
| Taxonomy name | `aioseo-location-category` | `aioseo_local_business_taxonomy_name` |
| Taxonomy slug | `locations-category` | `aioseo_local_business_taxonomy_slug` |

Gotchas:
- Changing the **name** (not slug) orphans existing locations/categories in wp-admin. Back up the DB, then rename in the DB. The doc's SQL embeds are empty; equivalent [reconstructed]:
  ```sql
  UPDATE wp_posts SET post_type = 'franchise-location' WHERE post_type = 'aioseo-location';
  UPDATE wp_term_taxonomy SET taxonomy = 'franchise-state' WHERE taxonomy = 'aioseo-location-category';
  ```
  Replace `wp_` with your table prefix.
- Changing a **slug** gives 404s until rewrite rules are flushed: **Settings > Permalinks > Save Changes**.
- The plural-label page's prose says "the post type single label is changed ... to Franchises" (copy error); the code correctly changes the plural label.

Registration:
```php
add_filter( 'aioseo_local_business_post_type', 'aioseo_change_local_business_post_type' );
function aioseo_change_local_business_post_type( $post_type ) {
	$post_type['supports'][] = 'excerpt';
	$post_type['supports'][] = 'page-attributes';
	return $post_type;
}
```
```php
add_filter( 'aioseo_local_business_post_type_name', 'aioseo_change_local_business_post_type_name' );
function aioseo_change_local_business_post_type_name( $name ) {
	$name = 'franchise-location';
	return $name;
}
```
```php
add_filter( 'aioseo_local_business_post_type_slug', 'aioseo_change_local_business_post_type_slug' );
function aioseo_change_local_business_post_type_slug( $slug ) {
	$slug = 'franchise';
	return $slug;
}
```
```php
add_filter( 'aioseo_local_business_post_type_single_label', 'aioseo_change_local_business_post_type_single_label' );
function aioseo_change_local_business_post_type_single_label( $label ) {
	$label = 'Franchise';
	return $label;
}
```
```php
add_filter( 'aioseo_local_business_post_type_plural_label', 'aioseo_change_local_business_post_type_plural_label' );
function aioseo_change_local_business_post_type_plural_label( $label ) {
	$label = 'Franchises';
	return $label;
}
```
```php
add_filter( 'aioseo_local_business_taxonomy', 'aioseo_change_local_business_taxonomy' );
function aioseo_change_local_business_taxonomy( $taxonomy ) {
	$taxonomy['hierarchical'] = true;
	return $taxonomy;
}
```
```php
add_filter( 'aioseo_local_business_taxonomy_name', 'aioseo_change_local_business_taxonomy_name' );
function aioseo_change_local_business_taxonomy_name( $name ) {
	$name = 'franchise-state';
	return $name;
}
```
```php
add_filter( 'aioseo_local_business_taxonomy_slug', 'aioseo_change_local_business_taxonomy_slug' );
function aioseo_change_local_business_taxonomy_slug( $slug ) {
	$slug = 'franchise-state';
	return $slug;
}
```

Location data (note the nested path `$information->locations->business->name`; `$postId` 19 is the location post ID; both are compared with `===`, so `$postId` must be an int):
```php
add_filter( 'aioseo_local_business_get_location', 'aioseo_change_local_business_get_location', 10, 2 );
function aioseo_change_local_business_get_location( $information, $postId ) {
	if ( 19 === $postId ) {
		$information->locations->business->name .= ' LLC';
	}
	return $information;
}
```

Address format tags (`$tags` is a list of arrays with `id`, not keyed by tag name):
```php
function aioseo_change_local_business_address_tags( $tags ) {
	foreach ( $tags as $key => $tag ) {
		if ( 'streetLineTwo' === $tag['id'] ) {
			unset( $tags[ $key ] );
		}
	}
	return $tags;
}
add_filter( 'aioseo_local_business_address_tags', 'aioseo_change_local_business_address_tags' );
```
```php
add_filter( 'aioseo_local_business_address_tag_value', 'aioseo_change_local_business_address_tag_value', 10, 3 );
function aioseo_change_local_business_address_tag_value( $tagValue, $tag, $id ) {
	if ( 'streetLineTwo' === $tag['id'] ) {
		$tagValue = '';
	}
	return $tagValue;
}
```

Business info and opening hours output:
```php
add_filter( 'aioseo_local_business_output_business_info_instance', 'aioseo_change_local_business_output_business_info_instance', 10, 3 );
function aioseo_change_local_business_output_business_info_instance( $instance, $postId, $locationData ) {
	$instance['showPhone'] = false;
	return $instance;
}
```
```php
add_filter( 'aioseo_local_business_output_business_info_location_data', 'aioseo_change_local_business_output_business_info_location_data', 10, 3 );
function aioseo_change_local_business_output_business_info_location_data( $locationData, $instance, $postId ) {
	$locationData->name .= ' LLC';
	return $locationData;
}
```
```php
add_filter( 'aioseo_local_business_output_opening_hours_instance', 'aioseo_change_local_business_output_opening_hours_instance', 10, 3 );
function aioseo_change_local_business_output_opening_hours_instance( $instance, $postId, $openingHoursData ) {
	$instance['showSunday'] = false;
	return $instance;
}
```
```php
add_filter( 'aioseo_local_business_output_opening_hours_data', 'aioseo_change_local_business_output_opening_hours_data', 10, 3 );
function aioseo_change_local_business_output_opening_hours_data( $openingHoursData, $instance, $postId ) {
	$openingHoursData->labels->closed = __( 'Closed today.' );
	return $openingHoursData;
}
```
(`__( 'Closed today.' )` has no text domain; add yours for translation.)

Icons. The prose says the argument is an SVG; the code returns an `<img>` tag pointing at the theme's `assets/images/`, so any HTML works. `get_template_directory_uri()` is the parent theme; use `get_stylesheet_directory_uri()` for a child theme:
```php
add_filter( 'aioseo_local_business_info_email_icon', 'aioseo_change_local_business_info_email_icon');
function aioseo_change_local_business_info_email_icon( $icon ) {
	return '<img src="'.get_template_directory_uri().'/assets/images/email-icon.png"/>';
}
```
```php
add_filter( 'aioseo_local_business_info_location_icon', 'aioseo_change_local_business_info_location_icon');
function aioseo_change_local_business_info_location_icon( $icon ) {
	return '<img src="'.get_template_directory_uri().'/assets/images/location-icon.png"/>';
}
```
```php
add_filter( 'aioseo_local_business_info_phone_icon', 'aioseo_change_local_business_info_phone_icon');
function aioseo_change_local_business_info_phone_icon( $icon ) {
	return '<img src="'.get_template_directory_uri().'/assets/images/phone-icon.png"/>';
}
```
```php
add_filter( 'aioseo_local_business_opening_hours_icon', 'aioseo_change_local_business_opening_hours_icon');
function aioseo_change_local_business_opening_hours_icon( $icon ) {
	return '<img src="'.get_template_directory_uri().'/assets/images/hours-icon.png"/>';
}
```

## REST API (fetch and update AIOSEO data)
Sources: https://aioseo.com/docs/fetching-updating-aioseo-data-via-the-wordpress-rest-api/

- Tier: "available in All in One SEO Lite and All in One SEO Pro" (doc wording). The Composer page also lists a separate `aioseo/rest-api` addon package. [Open question: whether the addon is still required.]
- No custom endpoints. AIOSEO adds fields to core WP REST **GET** routes for posts and terms: `/wp/v2/posts`, `/wp/v2/pages`, `/wp/v2/media`, `/wp/v2/categories`, `/wp/v2/tags`, plus every CPT/taxonomy with REST support enabled.

| Field | Content | Use |
|---|---|---|
| `aioseo_head` | Raw HTML string AIOSEO would print in `<head>` (meta, OG, Twitter, schema) | Headless: print as-is into the frontend head |
| `aioseo_head_json` | Same values as JSON, **without** HTML tags | Filter/process; you build the tags yourself |
| `aioseo_meta_data` | The row from AIOSEO's custom post/term table as JSON | Read before modifying and writing back |

- Updating: authenticate (WP REST auth: application passwords, cookie+nonce, etc.). The user needs at least one of `aioseo_page_general_settings`, `aioseo_page_social_settings`, `aioseo_page_schema_settings`, `aioseo_page_advanced_settings`. POST/PUT to the core route with `aioseo_meta_data` in the body containing any keys present in the `aioseo_meta_data` field:

```json
{ "aioseo_meta_data": { "title": "NEW TITLE", "description": "NEW DESCRIPTION" } }
```
Example: `POST /wp-json/wp/v2/posts/123` with that body. Stored `title`/`description` can contain smart tags (e.g. `#post_title #separator_sa #site_title`) [my note].

Use cases named: headless WordPress; external systems (e.g. ERP with WooCommerce integration) managing SEO data.

## Installing via Composer
Sources: https://aioseo.com/docs/installing-all-in-one-seo-via-composer/ (published 2025-05-20)

Prereqs: Composer, a Composer-managed WordPress, an active licence key for Pro.

```bash
composer config repositories.aioseo composer https://licensing.aioseo.com/packages/
# Lite (no auth)
composer require "aioseo/lite:*"
# Pro and addons: auth with licence key
composer config -g http-basic.licensing.aioseo.com key [YOUR_LICENSE_KEY]
composer require "aioseo/pro:*"
composer require "aioseo/redirects:*"
composer require "aioseo/link-assistant:*"
composer require "aioseo/eeat:*"
composer require "aioseo/image-seo:*"
composer require "aioseo/index-now:*"
composer require "aioseo/video-sitemap:*"
composer require "aioseo/news-sitemap:*"
composer require "aioseo/local-business:*"
composer require "aioseo/rest-api:*"
# update
composer update aioseo/pro
composer require "aioseo/pro:4.3.0"   # pin a version
```
- HTTP basic username is literally `key`; password is the licence key.
- Default path `wp-content/plugins/`. Custom path in composer.json:
  ```json
  "extra": { "installer-paths": { "wp-content/plugins/{$name}/": ["type:wordpress-plugin"] } }
  ```
- Troubleshooting: Authentication errors -> licence inactive/mistyped, or licence lacks access to that package. Package not found -> licence not authorised for the package, or misspelled name (`aioseo/pro`, `aioseo/lite`). Path issues -> plugin directory missing or not writable.
- [Note: `composer config -g http-basic...` stores the licence key in plain text in the global `auth.json`; in CI use the `COMPOSER_AUTH` env var/secret. Never commit `auth.json`.]

## Other snippets

All 98 WPCode embeds on the docs belong to the hook pages and the LLMS filters page; three are empty in the source (noted above). The five developer guides have their code inline.
