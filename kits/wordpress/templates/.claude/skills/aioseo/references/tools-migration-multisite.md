# Tools, migration, multilingual and multisite

Import/export, backups, reset, importing from other SEO plugins, WPCode, multisite networks, multilingual and hreflang.

Built from a full read of aioseo.com/docs, /faqs and /blog on 2026-10-11 (AIOSEO Pro 5.0.2 on aioseo.com). Each section lists its source pages. Text in [brackets] is a reviewer note where the vendor advice looks dated or conflicts with Google guidance. UI labels move between versions: confirm on the live site before giving click paths as fact. Unresolved points are in open-questions.md.

## Contents

- Translating SEO with WPML
- Tools: Import/Export, backups, reset, plugin migration, WPCode
- Multisite networks
- Free to Pro migration and installation
- Importing from other SEO plugins
- Multilingual, hreflang, translation, RTL
- API code snippets (how to add filters)

## Translating SEO with WPML
Source: https://aioseo.com/docs/translating-your-seo-with-wpml/

- WPML » **Translation Dashboard**: select content, then pick a translation method. AIOSEO fields (titles, descriptions) are translated together with the content.
- The page recommends WPML's **Private Translation Cloud (PTC)** AI translator; edits are made in the Advanced Translation Editor via "Edit translation" in the admin bar.
- Translated AIOSEO fields appear on the front end and in the page source.
- [The page is largely WPML promotion. It does not mention hreflang or per-language sitemaps.]

## Tools: Import/Export, backups, reset, plugin migration, WPCode

Sources: https://aioseo.com/docs/importing-and-exporting-aioseo-settings-and-meta-data/, https://aioseo.com/docs/backing-up-and-restoring-aioseo-settings/, https://aioseo.com/docs/resetting-the-settings-in-all-in-one-seo/, https://aioseo.com/docs/importing-settings-from-other-plugins/, https://aioseo.com/docs/importing-locations-from-other-plugins/, https://aioseo.com/docs/wpcode-snippet-library/

- Path: **All in One SEO > Tools**. Tabs: Robots.txt Editor, .htaccess Editor (Apache only), **Import/Export**, **Database Tools**, **Code Snippets**.
- **Import/Export > Export Settings**: tick setting groups > Export Settings. Downloads `aioseo-export-settings`.
- **Export Content**: tick post types > Export. The Taxonomies tab exports term SEO meta. Formats are **JSON or CSV**; use CSV to bulk-edit SEO meta in a spreadsheet and re-import it. Files are `aioseo-export-post-types` / `aioseo-export-taxonomies`. (The doc mentions both an "Export Content" and an "Export Settings" button here.)
- **Import/Restore AIOSEO Settings or Content**: Choose a File > Import. Success message: "Success! Your settings have been imported."
- **Backup Settings**: Create Backup makes a dated entry; Restore and Delete icons on each entry. Backups hold settings only, **not SEO meta data**.
- **Database Tools > Reset Settings**: tick areas, or **All AIOSEO Settings** > **Reset Selected Settings to Default**. AIOSEO recommends backing up first.
- **Import Settings From Other Plugins** (Import/Export tab): choose a plugin, tick settings, Import.
  - **Yoast SEO** and **Rank Math**: titles, meta descriptions, schema settings, social meta and more.
  - **SEOPress**: titles, meta descriptions, social meta.
  - Only installed plugins are listed. If you already removed the old plugin, reinstall it **without activating** so AIOSEO can detect it.
  - Deactivate the old SEO plugin after migrating, or you get duplicate meta tags.
  - Unsupported plugins (The SEO Framework, Squirrly and others) have no importer. Re-enter custom titles and descriptions by hand, or send a feature request. Sitemaps, schema and breadcrumbs regenerate automatically.
- **Local SEO > Import** tab (Plus+): imports locations from other plugins. Single Location goes to Local SEO > Locations tab; Multiple Locations go to the Locations post type. Importing multiple locations works **only from Yoast SEO**.
- **Code Snippets** tab: integrates with **WPCode**. **Activate WPCode** installs the free plugin. **Use Snippet** opens WPCode's Edit Snippet screen; switch the toggle on to activate.

---

## Multisite networks

Sources: https://aioseo.com/docs/how-to-add-your-aioseo-license-key-on-a-wordpress-multisite-network/, https://aioseo.com/docs/how-to-backup-and-restore-aioseo-site-settings-on-a-multisite-network/, https://aioseo.com/docs/how-to-import-and-export-aioseo-settings-and-meta-data-on-a-multisite-network/, https://aioseo.com/docs/how-to-import-settings-from-other-plugins-on-a-multisite-network/, https://aioseo.com/docs/how-to-reset-the-aioseo-site-settings-on-a-multisite-network/, https://aioseo.com/docs/robots-txt-editor-for-multisite-networks/

- **Licensing:**
  - Every subdomain and subdirectory site counts as a separate site, so the plan needs enough seats.
  - **Network Activate** AIOSEO Pro.
  - Network Admin > All in One SEO > **Network Settings**: paste the key > **Connect**. This activates the main network domain.
  - **Domain Activations** table (Elite): per-domain Activate row action; a red X turns into a green check. Subdirectory sites each need their own activation. Searchable; supports **Mercator** domain aliases; Bulk Actions to activate or deactivate.
  - A subsite can override with its own key in its own General Settings.
- **Network Tools** (Network Admin > All in One SEO > Network Tools), Elite, added in v4.2.5. Each tool has a **Site Selector**:
  - Import/Export: export settings and/or post type meta (Export All Settings, Export All Post Types) to an `aioseo-export-settings*` file; import into any site. This is how to copy SEO data between sites.
  - Import Settings From Other Plugins, per site.
  - Backup Settings: Create Backup, Restore, Delete. Global site settings only, not meta.
  - Database Tools > Reset Settings, per site.
  - Robots.txt Editor: network-wide rules plus per-site rules; subdomain networks only.

---

## Free to Pro migration and installation
Sources: https://aioseo.com/docs/how-do-i-upgrade-to-all-in-one-seo-pro/, https://aioseo.com/docs/is-the-free-version-of-all-in-one-seo-required-for-all-in-one-seo-pro-to-work/, https://aioseo.com/docs/will-my-data-be-lost-if-i-convert-from-the-free-version-to-the-pro-version/, https://aioseo.com/docs/how-to-manually-install-all-in-one-seo-pro-when-the-file-is-too-big/, https://aioseo.com/faqs/

- To upgrade: buy a plan, then download and install Pro (install doc: https://aioseo.com/docs/installing-all-in-one-seo-pro/). All settings and meta data carry over automatically.
- **The free plugin does not have to stay installed.** You can keep it active, or deactivate and delete it once Pro is active. Data is shared, so deleting Lite loses nothing.
- Plugin folder names: `all-in-one-seo-pack` (Lite) and `all-in-one-seo-pack-pro` (Pro, according to the Action Scheduler doc). The manual-install doc calls the Pro folder `all-in-one-seo-pro`; see Open questions.

## Importing from other SEO plugins
Sources: https://aioseo.com/docs/can-i-import-my-posts-and-terms-metadata-and-seo-settings-from-other-seo-plugins/, https://aioseo.com/docs/how-does-the-import-process-for-seo-data-work/

- AIOSEO has an importer for post/term meta and settings from other SEO plugins (https://aioseo.com/docs/importing-settings-from-other-plugins/).
- The older "How does the import process work" page is obsolete: it says it does not apply to v4.0+.

## Multilingual, hreflang, translation, RTL
Sources: https://aioseo.com/docs/which-multilingual-plugins-are-compatible-with-aioseo/, https://aioseo.com/docs/does-all-in-one-seo-output-hreflang-tags/, https://aioseo.com/docs/how-do-i-use-all-in-one-seo-in-my-language/, https://aioseo.com/docs/is-all-in-one-seo-translation-ready/, https://aioseo.com/docs/does-aioseo-support-right-to-left-rtl-languages-such-as-arabic-and-hebrew/, https://aioseo.com/faqs/

**Compatible multilingual plugins**
- **Universally** (https://universally.com/), the vendor's own plugin: "built to work with" AIOSEO.
- **WPML**: "fully compatible" (https://aioseo.com/docs/translating-your-seo-with-wpml/).
- The /faqs/ page (May 2026) lists only WPML. The newer doc pages add Universally.

**hreflang**
- **AIOSEO does not output hreflang tags.** They come from the multilingual plugin.
- With Universally or WPML, AIOSEO integrates so that translated pages' SEO data is handled correctly.
- With other multilingual plugins, behaviour varies and depends on that plugin's own integration and hreflang output. (Doc PUBLISHED 2026-06-17.)
- [Polylang, TranslatePress and Weglot are not mentioned anywhere in the docs.]

**Translating the AIOSEO interface**
- Translated into 50+ or 54+ languages; the pages disagree slightly.
- A language pack becomes installable once that language is **90% translated** on translate.wordpress.org.
- Install it via Dashboard » **Updates** » Translations » **Update Translations**.
- WordPress.org, not the developer, controls when packs are released.

**RTL:** fully supported (Arabic, Hebrew).

## API code snippets (how to add filters)
Sources: https://aioseo.com/docs/how-do-i-use-your-api-code-examples/

- AIOSEO has an extensive filter API for changes that have no setting (the docs document filters only; see developer-hooks.md).
- Add snippets with the **WPCode** plugin (PHP snippet), or in a **child theme's** `functions.php`. Code in a parent theme is wiped when the theme updates.
