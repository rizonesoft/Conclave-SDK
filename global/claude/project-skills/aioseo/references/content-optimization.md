# Per-post settings and content optimisation

The AIOSEO Settings meta box, TruSEO, Headline Analyzer, Writing Assistant, SEO Revisions, Author SEO (E-E-A-T), content blocks (TOC, FAQ, Recipe, Product, Local).

Built from a full read of aioseo.com/docs, /faqs and /blog on 2026-10-11 (AIOSEO Pro 5.0.2 on aioseo.com). Each section lists its source pages. Text in [brackets] is a reviewer note where the vendor advice looks dated or conflicts with Google guidance. UI labels move between versions: confirm on the live site before giving click paths as fact. Unresolved points are in open-questions.md.

## Contents

- Content Optimization tab (TruSEO site-wide settings)
- TruSEO content analysis (per post)
- Headline Analyzer
- Writing Assistant (SEOBoost)
- Per-post AIOSEO Settings (overview of tabs)
- Redirect from the Edit Post screen
- SEO Revisions
- Author SEO (E-E-A-T)
- Content blocks: Table of Contents
- Table of Contents Plus (separate plugin documented on aioseo.com)
- Content blocks: FAQ, Recipe, Product, HTML Sitemap
- Content blocks: Local SEO (map, locations, hours, business info)
- TruSEO content analysis (overview)
- Keywords (focus keyword and additional keywords)

## Content Optimization tab (TruSEO site-wide settings)
Sources: https://aioseo.com/docs/content-optimization-settings/ (PUBLISHED 2026-08-12, new), https://aioseo.com/docs/how-to-disable-truseo-content-analysis/, https://aioseo.com/docs/how-to-disable-the-headline-analyzer/

- Location: All in One SEO » General Settings » **Content Optimization** tab. **Since v5.0. Before v5.0, the TruSEO and Headline Analyzer toggles were on General Settings » Advanced.**
- Group **TruSEO & Content Settings**: all five options are on by default, and all are site-wide.

| Option | Default | What it does | Shown when |
|---|---|---|---|
| TruSEO | On | Analyses content for basic SEO issues, keyword use and readability | Always |
| Highlighter | On | Marks sentences that need work, directly in the editor. This is only the default; each post can override it with the **Highlight** toggle on its Optimization tab | TruSEO on |
| Highlight style | Underline | **Underline** (default, subtler) or **Highlight** (coloured background). Both flag the same sentences | TruSEO and Highlighter on |
| Spell Checker | On | Highlights misspellings and suggests fixes. Needs the Highlighter | TruSEO and Highlighter on |
| Headline Analyzer | On | Scores post titles. Independent: it keeps working with TruSEO off | Always |

- Turning off the Spell Checker or the Headline Analyzer removes that area (the Spelling or Headline tab) from every post's Optimization tab.
- Turning off TruSEO stops keyword, basics and readability analysis and spelling flags. It does not affect the Headline Analyzer.
- To stop only the in-editor marks, turn off the Highlighter and leave TruSEO on, or turn Highlight off per post.
- None of these settings change front-end output or rankings. They are writing aids only.
- Group **Writing Assistant** (card): connects to SEOBoost. It has a Learn More link and **Create a Free Account** and **Connect to an Existing Account** buttons. **Post Types** has **Include all post types** selected by default; clear it to choose individual types. It works independently of TruSEO.
- Click Save Changes at the bottom.

## TruSEO content analysis (per post)
Sources: https://aioseo.com/docs/using-truseo-content-analysis-to-optimize-your-content/ (PUBLISHED 2026-08-06, MODIFIED 2026-08-26), https://aioseo.com/docs/understanding-the-truseo-page-analysis-recommendations/ (MODIFIED 2026-08-26), https://aioseo.com/docs/getting-keyphrase-suggestions-from-semrush/ (MODIFIED 2026-08-26), https://aioseo.com/docs/including-custom-fields-in-the-seo-page-analysis/, https://aioseo.com/docs/dashboard-widgets-in-all-in-one-seo/

**Where it is.** Edit post » AIOSEO Settings (below the content) » **Optimization** tab (labelled "Optimization (NEW!)" in builder screenshots). The **Content Optimization** score is out of 100 and updates live. Next to the score are an **Optimize with AI** button and a **Highlight** toggle; switching Highlight off clears the markers.

There are five area tabs: **Keywords, Basics, Spelling, Readability, Headline**. Each area splits its checks into **Improvements** and **Good**, and Good starts collapsed.

**Limits and compatibility**
- The TruSEO Highlighter works only in the Block Editor and the Classic Editor, not in page builders ("support … in future releases").
- TruSEO is disabled on pages without static content: the WordPress static Posts page, the Privacy Policy page, and the WooCommerce Cart, Checkout and My Account pages.

**Keywords tab**
- Type a phrase in **Add a focus keyword** and click **Add Keyword**. You can add several keywords; each gets its own Score and Improvements count in a table.
- **At most 10 keywords in Additional Keywords**, to protect edit-screen performance.
- AIOSEO recommends one main keyword plus a couple of close variations.
- Keyword checks run per keyword, inside each keyword's row. Some run only against the focus keyword, and the check text says so.

| Keyword check | Tests |
|---|---|
| Keyword length | The phrase is a workable length; shorter phrases are easier to target |
| Function words in keyword | The keyword is made of words people actually search |
| Keyword in SEO title | Present, and how early |
| Keyword in slug | Present in the URL |
| Keyword in meta description | Present |
| Keyword in introduction | In the first paragraph |
| Keyword in subheading | At least one subheading has it |
| Keyword in image alt attributes | Needs a focus keyword and at least one image |
| Keyword density | Frequency relative to post length; overuse is flagged |
| Keyword distribution | Spread through the post |
| Competing links | Internal links on the post that use the keyword as anchor text |
| Keyword cannibalization | Other posts on the site target the same keyword; it names them |

[Keyword density and exact-match placement are AIOSEO heuristics, not Google ranking signals. Treat them as hints.]

**Semrush keyword suggestions.** After adding a focus keyword, click **Discover additional keywords** under "Add an additional keyword". This opens a Semrush login or free signup; approve the site connection. A table then shows related keywords with search volume and a trend graph. Pro users get an **Add Keyword** button on each row.

**Basics tab**

| Check | Tests |
|---|---|
| Page title width | Rendered pixel width of the SEO title, not a character count |
| Single title | One main heading (H1) |
| Text length | Enough content to establish the topic |
| Meta description length | Over 160 characters may be cut off |
| Internal links | At least one link to a related post or page on the site |
| Outbound links | At least one link to a credible external source |
| Images and videos | At least one image or video |

**Readability tab.** The score is out of 100. **AIOSEO recommends 60-80 for most audiences.**

| Check | Tests |
|---|---|
| Content length | Enough text for readability to mean anything |
| Sentence length | Sentences of comfortable length |
| Sentence beginnings | Runs of consecutive sentences starting with the same word |
| Long paragraphs | Paragraphs over the recommended **150 words** |
| Missing subheadings | Long posts split into sections |
| Passive voice | Mostly active voice |
| Transition words | Words like however, because, for example |
| Word complexity | Mostly familiar words |

**Spelling tab.** Lists each misspelled word with how often it appears and suggested corrections; select a suggestion to apply it. **Add to dictionary** suppresses the word site-wide, on every post. **Manage Dictionary** (link at the top) reviews saved words.

**Headline tab.** See Headline Analyzer below.

**Custom fields in TruSEO** (**Basic or higher**). Search Appearance » Content Types » the post type » **Custom Fields** tab. Enter custom field names one per line and Save Changes. Those fields' content is then included in the TruSEO analysis.

**Where scores appear elsewhere:** the AIOSEO Details column, the AIOSEO Overview widget, the Site Audit, and Email Reports.

AIOSEO says the recommendations are best practices, not rules: stop when a change would hurt the content.

## Headline Analyzer
Sources: https://aioseo.com/docs/using-the-headline-analyzer-in-all-in-one-seo/, https://aioseo.com/docs/how-to-disable-the-headline-analyzer/, https://aioseo.com/docs/content-optimization-settings/, https://aioseo.com/docs/using-the-seo-analysis-tool/

- Location: Edit post » AIOSEO Settings » Optimization » **Headline** tab. The score out of 100 sits beside "Headline". It works in both the Classic Editor and the Block Editor. There is also a Headline Analyzer tab under All in One SEO » SEO Analysis.
- Score bands: **70+ good, 40-69 room to improve, below 40 needs work.**
- **Testing alternatives**: type into the **Headline** field and the score updates live. This does not change the post title or mark the post as unsaved. Once the text differs, **Reset** and **Apply** buttons appear, with the gain or loss against the original (for example +33). **Apply** writes the new text into the post title.
- **Breakdown** (Word balance):

| Group | Target |
|---|---|
| Common Words | 20-30% |
| Uncommon Words | 10-20% |
| Emotional Words | 10-15% |
| Power Words | At least 1. Moves the score the most, so check it first |

  A group counts as met once it reaches its target; going over does not count against you. Each group lists the words it matched. There is a vendor "Word Bank" page of word lists. Beginning & Ending Words shows the first and last words.
- Final checks:
  - **Character Count**: target about 55 characters.
  - **Word Count**: 5-9 words, about 6 is best.
  - **Sentiment**: positive, neutral or negative; positive engages more.
  - **Headline Type**: How-To, List, Question or General; lists and how-tos engage more.
- **Limitations**: scores **English headlines only** (content set to another language is skipped) and **skips WooCommerce product titles**.
- **Turning it off**: General Settings » Content Optimization » Headline Analyzer toggle » Save Changes. It is site-wide only, with no per-post switch. The Headline tab disappears everywhere. The other areas (Keywords, Basics, Spelling, Readability) keep working.
- [The headline score is a CTR-copywriting heuristic. Google often rewrites titles, and the score is not a ranking factor.]

## Writing Assistant (SEOBoost)
Sources: https://aioseo.com/docs/how-to-use-the-writing-assistant-in-aioseo/, https://aioseo.com/docs/content-optimization-settings/

- Needs a separate **SEOBoost** account; a free trial or free account is available.
- **Connect**: the older page says General Settings » **Writing Assistant** tab; the newer page (2026-08-12) shows a Writing Assistant card on the **Content Optimization** tab (see Open questions). Click **Create a Free Account** or **Connect to an Existing Account**, log in in the popup, authorize, and **select a workspace**.
- Settings: **Post Types**, either Include all post types (default) or a chosen list. Save.
- **Use**: Edit post » the **AIOSEO Writing Assistant** section below AIOSEO Settings. There is also a **Pencil icon** at the top right of the block-editor sidebar that opens it in the sidebar.
- **Generate a New Report** fields:
  - **Keyword**: medium- and long-tail phrases work best.
  - **Region**: the target audience's search region.
  - **Language**: the content's main language.

  A report takes a few minutes. Reports can also be viewed on the SEOBoost site.
- Report sections:
  - **Report Keyword**.
  - **Grade Summary**, with columns Your Content (grade, word count, readability), Typical Top 10, and Typical 11-30 (Google, for the chosen region and language).
  - **Top Competitor Content**.
  - **Report Details** and **Report History**.
  - **Optimization Wizard**: top-ranking related terms, with See Examples (snippets from ranking articles with links), Heading Presence, Uses and Importance columns.
  - **Competitors**: the top 30 ranking URLs with readability, word count and grade. Sortable, and exportable via the **CSV** button.

## Per-post AIOSEO Settings (overview of tabs)
Sources: https://aioseo.com/docs/setting-the-seo-title-and-description-for-your-content/ (MODIFIED 2026-10-06), https://aioseo.com/docs/page-builder-integrations/, https://aioseo.com/docs/setting-the-robots-meta-for-individual-content/, https://aioseo.com/docs/canonical-urls-in-all-in-one-seo/, https://aioseo.com/docs/setting-the-sitemap-priority-and-frequency-for-individual-content/, https://aioseo.com/docs/configuring-the-twitter-settings-for-your-content/, https://aioseo.com/docs/preventing-the-modified-date-for-content-from-changing/

- The meta box is **AIOSEO Settings**, below the content. It applies to Posts, Pages, Media Attachments, CPTs, Categories, Tags and custom taxonomies; editing terms requires Pro.
- Builder screenshots show these tabs: **Appearance** (General / Search Appearance), **Optimization (NEW!)**, **Schema**, **AI Copilot**, **Redirects**, **SEO Revisions**, **Advanced**.
- The newer X/Twitter doc refers to a separate **Social Appearance** meta box with Facebook and X (Twitter) tabs; older docs say a Social tab inside AIOSEO Settings.
- **General / Search Appearance**: SERP Preview (desktop and mobile icons), Title (Post Title, Page Title and so on), and Meta Description.
  - Each field has smart-tag buttons, a **View all tags** link, `#` autocomplete, and an emoji picker.
  - A per-post value overrides the format set in Search Appearance.
  - Search engines may rewrite titles and descriptions.
- **Advanced tab**:
  - **Robots Setting** (toggle Use Default Settings to override; see Robots Meta).
  - Breadcrumbs trail preview (seen in a screenshot).
  - **Canonical URL**: enter the full URL to override the canonical WordPress outputs.
  - **Keywords** (only if Use Meta Keywords is on).
  - **Priority** and **Frequency** for the sitemap (Basic or higher).
- **Sitemap Priority and Frequency** (per post, Basic or higher): Priority runs 0.0-1.0 (1.0 most important; the default is 0.5 per the doc) and Change Frequency is a dropdown. **AIOSEO recommends leaving both on Default**, because AIOSEO calculates them. [Google ignores `<priority>` and `<changefreq>`, so there is no reason to tune them.]
- **Don't update the modified date**: a checkbox in the Status & visibility panel (Block Editor) or the publish box (Classic Editor). Tick it before Update to keep the existing modified date. Works in Block, Classic and supported page builders. Use it for minor edits you don't want to signal.
- **Reviewer**: a dropdown in the post sidebar (Author SEO; see below).
- **Redirects tab**: see Redirect from edit screen.

## Redirect from the Edit Post screen
Source: https://aioseo.com/docs/how-to-redirect-a-post-from-the-edit-post-screen/

- Redirection Manager needs **Basic or higher**; some advanced features need **Pro or higher**.
- Edit post » AIOSEO Settings » **Redirects** tab. It is the same form as Redirects » Redirection Manager, with **Source URL** pre-filled.
- **Target URL**: relative or absolute. You can type a post title, slug or ID to autocomplete.
- **Comment**: optional.
- **Redirect Type**: **301 Moved Permanently** (content deleted or moved) or **307 Temporary Redirect**, among others.
- Click **Add Redirect**. The row has an **Enabled** toggle. Hover for **Check Redirect**, **Edit** and **Delete**.
- Advanced options match the Redirection Manager: Ignore Slash, Ignore Case, Query Parameters, Custom Rules.

## SEO Revisions
Source: https://aioseo.com/docs/tracking-changes-to-your-seo-using-seo-revisions/

- Needs **Plus, Pro or Elite**. Each tier has a maximum number of stored revisions; **Plus = 15**. The doc does not give the other tiers' numbers.
- The cap is a rolling maximum per stored set, not a monthly or yearly quota: the oldest revision is dropped when a new one would exceed it.
- Location: Edit item » AIOSEO Settings » **SEO Revisions** tab.
- It records only changes made in the AIOSEO Settings section, newest first, with the user and date/time.
- Actions:
  - **View Revision** icon.
  - **Add Note** (hover); **Edit Note** to change or delete a note.
  - **Compare**: the Compare Revisions screen has a slider. The left pane (pink) is before and the right pane (green) is after.
  - **Restore This Revision** (on the Compare screen).
  - **Delete Revision** icon, then **Yes, delete revision**. This deletes only the record; the change is not undone.
- **Integration**: revisions show as markers on Search Statistics detailed content reports, so changes can be matched against Google performance.

## Author SEO (E-E-A-T)
Sources: https://aioseo.com/docs/adding-author-seo-e-e-a-t-to-your-site/, https://aioseo.com/docs/displaying-detailed-author-information-on-your-site/, https://aioseo.com/docs/using-author-seo-e-e-a-t-for-long-term-ranking-improvements/

**Tiers**

| Item | Tier |
|---|---|
| Author SEO feature and addon | **Plus or higher** |
| Author Bio block (compact excerpt) | Plus or higher |
| Full Author Bio | **Pro or higher** |
| Author Name block | Pro or higher |
| Reviewer Name block | Pro or higher |

**Enable.** Feature Manager » activate **Author SEO (E-E-A-T)**. This adds an **Author SEO** tab to every user's Profile.

**Global settings: Search Appearance » Author SEO**
- **Display Info**: a reference list of the blocks, shortcodes and PHP functions.
- **Append Author Bio to Posts**: automatically adds the Author Excerpt below posts.
- **Post Types**: only post types that support authors.
- **Author Experience Topics (E-E-A-T)** table:
  - Columns: **Name** (required), **URL** (an authoritative page on the topic), **Same as URLs** (several allowed).
  - Add Item to add a row; the delete icon removes one. Save Changes.
  - Only admins define topics here; writers can only pick from them.

**User profile » Author SEO tab**

| Field | Notes |
|---|---|
| Enable Author Info | Per-user kill switch |
| Alumni Of | School name and URL, with Add Item for more |
| Employer | Current organisation |
| Job Title | Title at that employer |
| Knows About | Choose from the global Author Experience Topics |
| Awards | Not shown in blocks; output in schema (Award) |
| Spoken Languages | Not shown in blocks; output as `knowsLanguage` schema |
| Author Image | Square headshot. Falls back to Gravatar |
| Author Excerpt | Short bio. Defaults to the **Author Biography** smart tag, which is WP Profile » Biographical Info |
| Author Bio | Long bio |
| Author Bio URL | Target of the "See Full Bio" link. Empty means the author archive |
| Append Author Bio to Posts | "Use Default Setting" toggle; turn it off, then use the second toggle to force it on or off for this user |
| Social Profiles | Each URL entered shows a social icon in the excerpt and bio (opens in a new tab) |

**Reviewer.** A **Reviewer** dropdown in the Edit Post sidebar. Pick a user who reviewed the content (a trust signal). It is used by the Reviewer Name block.

**Blocks** (Block Editor only; search "AIOSEO")
- **AIOSEO – Author Bio**: **Show Compact Author Bio** toggle (on = excerpt, off = full bio). When compact, a **Show "See Full Bio" link** toggle appears.
- **AIOSEO – Author Name**: name and image, with a hover tooltip showing the excerpt.
  - Settings: **Show Label** ("Written By:"), **Show Image**, **Show Tooltip**, **Show "See Full Bio" link**.
  - The See Full Bio link goes to the author archive.
- **AIOSEO – Reviewer Name**: the same as Author Name, with the label "Reviewed By:". It may need **Browse all** to find it in the inserter.
- **Important**: if you add the Author Bio block by hand, disable Append Author Bio to Posts, or two bios render.

**Shortcodes**
```
[aioseo_eeat_author_bio compact="true"]    // Author Excerpt
[aioseo_eeat_author_bio compact="false"]   // full Author Bio
[aioseo_eeat_author_tooltip show-label="true" show-image="true" show-tooltip="true"]
[aioseo_eeat_reviewer_tooltip show-label="true" show-image="true" show-tooltip="true"]
```

**PHP** (theme templates). **These must run inside the Loop, or they render nothing.**
```php
<?php aioseo_eeat_author_bio( $compact = true ); ?>    // excerpt
<?php aioseo_eeat_author_bio( $compact = false ); ?>   // full bio
<?php aioseo_eeat_author_tooltip( $showLabel = true, $showImage = true, $showTooltip = true ); ?>
<?php aioseo_eeat_reviewer_tooltip( $showLabel = true, $showImage = true, $showTooltip = true ); ?>
```

**Strategy page advice (2025-01)**
- Build an About or Meet the Team page and link author names to it.
- Link credentials to authoritative institutions.
- Add media mentions and real-world experience.
- Set Spoken Languages for multilingual sites.
- Assign reviewers to health, finance and legal (YMYL) content.
- Build topic clusters per author and interlink with Link Assistant.
- Customise author archives.
- Use Local SEO for region-bound credentials.
- Baseline in GSC and GA, then monitor.
- Pitfalls: overstated expertise, stale bios, inconsistent profiles.

[E-E-A-T is a quality-rater concept and not a direct ranking factor. Author schema and bios support it, but they do not replace real expertise.]

## Content blocks: Table of Contents
Source: https://aioseo.com/docs/adding-a-table-of-contents-to-your-site-using-all-in-one-seo/

- Block **AIOSEO – Table of Contents** (Block Editor only). It lists the H1-H6 headings in the content, indented by level. It is empty when there are no headings.
- **Settings**:
  - **List Style**: bulleted or numbered.
  - **Collapsible**: when on, set the collapsed title and the expanded title.
  - **Synced Table of Contents**: builds one unified TOC from several section TOCs, for example a top-level TOC plus one per section.
- **Toolbar on the block**:
  - **Reorder** (drag and drop in a popup, then Done). This changes only the TOC order, not the headings.
  - The **link icon** edits an item's anchor; click X to save.
  - The **visibility icon** hides an item on the front end.
  - Click Done to save.
- No tier is stated.

## Table of Contents Plus (separate plugin documented on aioseo.com)
Source: https://aioseo.com/docs/table-of-contents-plus/ (PUBLISHED 2026-06-02)

This is the separate WordPress plugin "Table of Contents Plus" (TOC+); its docs are now hosted on aioseo.com. Its settings are under **Settings » TOC+**, and there is a **TOC+ widget** in Appearance » Widgets.

- **Defaults**: auto-inserts before the first heading, **on pages only** (not posts or CPTs), when there are **4 or more headings** (Main Options » Show when).
  - CPT auto-insertion works only if the theme calls `the_content()`.
  - Advanced options: exclude heading levels (for example h5 and h6), disable the bundled CSS, top offset, restrict to a URL path, lowercase and hyphenated anchors.
- **Title variable** `%PAGE_NAME%`, for example "Contents for %PAGE_NAME%".
- **Exclude headings**: separate with a pipe `|`; `*` is a wildcard; matching is case-insensitive. Examples: `Fruit*`, `*Fruit Diet*`, `Apple Tree|Oranges|Yellow Bananas`.
- Wrapping fails if the theme sets `clear` on headings. Fix: `h1, h2, h3, h4, h5, h6 { clear: none; }`.
- **Shortcodes** (missing parameters fall back to the settings):
  - `[toc]`: `label`, `no_label` (true/false), `wrapping` (left/right), `heading_levels="3,4,5"`, `exclude` (pipe, wildcard or regex), `class`.
  - `[no_toc]`: suppresses the TOC on that item.
  - `[sitemap]`: all pages and categories.
  - `[sitemap_pages]`: `heading` (1-6), `label`, `no_label`, `exclude` (IDs), `exclude_tree` (ID).
  - `[sitemap_categories]`: the same attributes, for categories.
  - `[sitemap_posts]`: `order` (ASC/DESC), `orderby` (title, date, ID, rand, and other WP_Query values), `separate` (default true; groups by first letter).
- To show the TOC on only some pages: turn off auto-insert for that type and add `[toc]` where needed, or use the restrict-path option.
- **Developers**:
  - Filter `toc_url_anchor_target`, for example:
    ```php
    function my_custom_anchor( $anchor ) { return strtoupper( $anchor ); }
    add_filter( 'toc_url_anchor_target', 'my_custom_anchor' );
    ```
  - `toc_get_index( $content = '', $prefix_url = '' )` returns the list items without the outer UL or OL. `$content` defaults to the current `$post`; `$prefix_url` set to true uses the permalink. Example: `echo '<ul id="my_toc">' . toc_get_index() . '</ul>';`. A second example builds child-page indexes with WP_Query and `toc_get_index( get_the_content(), get_permalink( $id ) )`.
- Sitemap styling is inherited. If you pasted the shortcode with `code` tags, remove them; put the shortcode on its own line.

## Content blocks: FAQ, Recipe, Product, HTML Sitemap
Sources: https://aioseo.com/docs/adding-faqs-to-your-site-using-all-in-one-seo/, https://aioseo.com/docs/displaying-recipes-on-your-site-using-all-in-one-seo/ (PUBLISHED 2025-11-06), https://aioseo.com/docs/displaying-products-on-your-site-using-all-in-one-seo/ (PUBLISHED 2025-11-06), https://aioseo.com/docs/using-a-block-to-display-your-html-sitemap/

All are Block Editor only, not Classic Editor or builders. Search "AIOSEO" in the inserter.

**AIOSEO – FAQ**
- Fields: "Write a question…" and "Write an answer…".
- It outputs **FAQ schema**, which needs **Basic or higher**.
- Settings:
  - **Title Wrapper**: H1, H2, H3, H4 or DIV for the question.
  - **Display Block** toggle: hide it from visitors while search engines still see it.
  - Color (text and background).
  - Typography (answer size and line height).
- [Google limits FAQ rich results to well-known government and health sites (since August 2023). Hiding FAQ content visually while keeping its schema conflicts with Google's structured-data guidelines, so do not use Display Block off for schema.]

**AIOSEO – Recipe** (**Basic or higher**). It outputs Recipe schema, so there is no need to add Recipe schema in the Schema settings. Tabs:
- **General**: Name, Description and Author (smart tags allowed); Ingredients (press Enter after each, for example "1 tablespoon of flour"); Dish Type; Cuisine Type; Keywords; Image.
- **Nutrition**: Servings; Calories per serving.
- **Time Required**: Preparation Time and Cooking Time, in minutes.
- **Instructions**: steps with Title, Details and Image. Use Add Another Instruction and Delete.
- **Reviews**: Rating Value, Headline, Content, Author. Use Add Another Review.
- **Review Rating**: Rating Minimum and Rating Maximum.
- Click Save or Delete inside the block, then save the post.

**AIOSEO – Product** (**Basic or higher**). It outputs Product schema and suits sites without an e-commerce plugin. Tabs:
- **General**: Name and Description (smart tags), Brand, Image.
- **Identifiers**: SKU, GTIN, MPN, ISBN.
- **Offer**: Price, Sale Price, Currency, Price Valid Until, Availability.
- **Attributes**: Material and Color (slash-separated, for example cotton/polyester or Red/Green/Black), Pattern (only one), Size (slash-separated), EU Energy Rating (dropdown).
- **Audience**: Gender, Minimum Age.
- **Reviews**: as for Recipe.
- **Review Rating**: Min and Max.
- **Shipping Destinations**: Country, States, Postal Code, Price. Use Add Another Shipping Destination.
- Click Save or Delete in the block.
- [Self-authored reviews in Product or Recipe schema can breach Google's review-snippet policies. Use only genuine third-party reviews.]

**AIOSEO – HTML Sitemap**
- Renders according to Sitemaps » HTML Sitemap.
- Turn off **Use Default Settings** in the block sidebar to override per block; the settings mirror the HTML Sitemap screen.

## Content blocks: Local SEO (map, locations, hours, business info)
Sources: https://aioseo.com/docs/adding-a-map-of-your-location-to-your-site/, https://aioseo.com/docs/displaying-a-list-of-locations-on-your-site/, https://aioseo.com/docs/displaying-opening-hours-on-your-site/ (MODIFIED 2026-04-15), https://aioseo.com/docs/displaying-your-business-location-information-on-your-site/

Local SEO needs **Plus or higher**. These are Block Editor only; search "AIOSEO Local". Other docs cover shortcodes and widgets for non-block editors.

| Block | Settings |
|---|---|
| **AIOSEO Local – Map** | Location dropdown (with Multiple Locations on; otherwise the single Local SEO location). **Show label** (label text default "Our location:", editable in Label). **Show icon**. Custom map marker (overrides Local SEO » Maps). Width and height in % or px |
| **AIOSEO Local – Locations** | Needs Multiple Locations on. **Location Category** dropdown; lists that category's locations, each linked |
| **AIOSEO Local – Location Categories** | No settings; lists the location categories, each linked |
| **AIOSEO Local – Opening Hours** | With a single location there are no sidebar settings (it uses the Local SEO Opening Hours tab). With multiple: Location; **Show title** ("Our Opening Hours", editable in Label); **Show icons** (clock); a toggle per day of the week |
| **AIOSEO Local – Business Info** | With a single location there are no settings. With multiple: Location; **Show labels** (field names such as Address, Phone, Email, editable in the Labels section); **Show icons**; a toggle per field |

## TruSEO content analysis (overview)
Sources: https://aioseo.com/docs/what-is-truseo/, https://aioseo.com/docs/using-the-focus-keyphrase-to-analyze-your-content/

- **Recently reworked:** both docs MODIFIED 2026-08-26 and describe a new layout.
- **Location:** post editor » **AIOSEO Settings** section below the content » **Optimization** tab » **Content Optimization** panel.
- **Overall score** out of 100 sits beside the "Content Optimization" heading. The same overall score shows beside the Save button at the top of the editor.
- **Five area tabs:**

| Tab | Checks | Badge |
|---|---|---|
| Keywords | How well the content targets each keyword added | Per-keyword scores inside the tab |
| Basics | Title, meta description, links, images | Count of items needing attention |
| Spelling | Misspellings | Count |
| Readability | Ease of reading | Score /100 |
| Headline | How clickable the post title is (Headline Analyzer) | Score /100 |

- **Score bands:** **80+ good**, **50–79 okay**, **under 50 needs improvement**. Badge colours: green good, orange/red needs work.
- **Check groups:** each area lists checks under **Improvements**, plus a collapsed **Good** group. Scores update live without saving.
- **Editor support:**
  - Runs in the Block Editor, the Classic Editor and "supported page builders".
  - The **TruSEO Highlighter only works in the Block Editor and Classic Editor**, not page builders (page builder support is promised for future releases).
  - It reads the visual editor; in Code Editor mode a note replaces the results.
- **Disabled on:** the static Posts page, Privacy Policy page, WooCommerce Cart, Checkout and My Account, and BuddyPress pages (BuddyPress is listed only in the FAQ section).
- **To turn it off:** **All in One SEO » General Settings » Content Optimization** tab.
- **AIOSEO recommends** treating the score as a guide. Stop working through Improvements when further changes would hurt writing quality. A good score doesn't guarantee rankings.

## Keywords (focus keyword and additional keywords)
Sources: https://aioseo.com/docs/using-the-focus-keyphrase-to-analyze-your-content/

- **Location:** AIOSEO Settings » **Optimization** » **Keywords** tab.
- **Adding keywords:**
  - The field reads **Add a focus keyword** when the post has none, and **Add an additional keyword** afterwards. Then click **Add Keyword**.
  - The first keyword added becomes the focus keyword.
- **Limits and tier:**
  - "A maximum of ten keywords", to avoid Edit Post performance problems. The FAQ section says "up to 10 additional keywords alongside its focus keyword".
  - Multiple keywords is a **Pro** feature.
- **Each row** shows a Score out of 100 and an Improvements count. Suggestions are grouped Improvements/Good; for example, keyword density reports the current count and the recommended count for that length.
- **Focus-keyword-only checks:** some checks run only against the focus keyword, e.g. the keyword in image alt attributes.
- **Changing the focus keyword:** click the circle at the start of a row (the filled circle marks the current one). If you remove the focus keyword, the first remaining keyword becomes the new focus.
- **Row Actions:**
  - **Open Keyword Performance Tracker**: rank tracker, part of Search Statistics, **Elite**, needs Google Search Console data.
  - **Edit Keyword.**
  - **Remove Keyword.**
  - An expand/collapse toggle.
- **Saving:** keywords are stored with the post and need **Save/Update**.
- **Keyword ideas:** the **Discover additional keywords** link gives Semrush-powered suggestions.
- **AIOSEO recommends** focusing a post on only a few keywords.
