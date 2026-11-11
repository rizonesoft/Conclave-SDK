# API and automation

How to read and change AIOSEO data without clicking through wp-admin. The sources are the AIOSEO REST API doc (https://aioseo.com/docs/fetching-updating-aioseo-data-via-the-wordpress-rest-api/) and the MCP server doc (https://aioseo.com/docs/connecting-an-ai-assistant-to-your-site-with-aioseos-mcp-server/, modified 2026-10-01). The "Write traps" section was checked against the all-in-one-seo-pack 5.0.3 source code (free plugin; the Elite code is not public).

## Contents

- Choosing a route
- REST fields on core routes
- Write traps (verified in source)
- Creating a post with AIOSEO data
- Abilities API and the MCP server
- Bulk changes without code
- Composer installs
- Credentials

## Choosing a route

| Need | Route |
|---|---|
| See what a page outputs | Public fetch (`scripts/check-seo-output.mjs`), or `GET /wp-json/wp/v2/<type>/<id>` and read `aioseo_head` / `aioseo_head_json` |
| Read or update one post's SEO fields | REST `aioseo_meta_data`, or the `aioseo-posts/seo-data-get` / `seo-data-update` abilities |
| Find posts missing descriptions, list TruSEO scores, read settings, run the site audit | Abilities (MCP or the Abilities REST route) |
| Redirects, term SEO, Search Statistics, Link Assistant from an AI client | MCP abilities (Pro; Search Statistics data needs Elite; Link Assistant needs the addon) |
| Hundreds of titles or descriptions | Tools » Import/Export » Export Content as CSV, edit, re-import (back up first) |
| Site-wide settings | wp-admin, one group at a time. There is no general settings write API in the docs; the `aioseo-settings/get` ability is read-only |

## REST fields on core routes

AIOSEO adds no custom endpoints for content. It adds three fields to the core routes for posts, pages, media, categories, tags and every custom post type or taxonomy with `show_in_rest`:

| Field | Content |
|---|---|
| `aioseo_head` | The HTML AIOSEO would print in `<head>` (meta, Open Graph, X, JSON-LD). Read-only |
| `aioseo_head_json` | The same values as JSON without tags. Read-only |
| `aioseo_meta_data` | The row from AIOSEO's own table (`aioseo_posts` / `aioseo_terms`). Readable and writable |

The docs call the REST fields free in Lite and Pro; the Composer page still lists an `aioseo/rest-api` addon package (see open-questions.md).

**Write:** `POST /wp-json/wp/v2/posts/<id>` (or the type's route) with `{"aioseo_meta_data": {...}}`. Authenticate as a user who can edit the item and holds at least one of the capabilities `aioseo_page_general_settings`, `aioseo_page_social_settings`, `aioseo_page_schema_settings`, `aioseo_page_advanced_settings`. Administrators and Editors have them by default; AIOSEO's SEO Manager and SEO Editor roles do too (see Access Control).

**Always read back** the item after writing and compare `aioseo_meta_data` and `aioseo_head`. Clear page caches before judging the front end.

## Write traps (verified in source)

1. **Patch semantics.** Keys left out keep their stored value. Unknown keys are silently ignored, so a typo looks like success. Since 5.0.3 a forbidden or invalid payload returns 403 or 400 and nothing is saved.
2. **Keyphrases must be written three ways:** `focus_keyword` (string), `additional_keywords` (`[{"word": "...", "score": 0}]`) and `keyphrases` (`{"focus": {"keyphrase": "...", "score": 0, "analysis": {}}, "additional": [{"keyphrase": "...", "score": 0, "analysis": {}}]}`). The 5.x editor reads the first two; a write to `keyphrases` alone is invisible in the editor.
3. **Robots use short names on write:** `default` (true = follow global settings), `noindex`, `nofollow`, `noarchive`, `nosnippet`, `noimageindex`, `notranslate`, `noodp`, `maxSnippet`, `maxVideoPreview`, `maxImagePreview`. Reads return `robots_*` names; writing those does nothing. An override needs `"default": false`.
4. **Schema is replaced whole.** Sending `schema` overwrites the item's entire schema object. To add a graph: GET the current `aioseo_meta_data.schema`, add or replace the item in `customGraphs` (match on `id`), send the whole object back, then confirm the graph appears in `aioseo_head_json`.
5. **`_aioseo_*` post meta is write-only mirror data** for translation plugins. Writing it changes nothing. Use `aioseo_meta_data`.
6. **TruSEO and Headline scores are computed in the browser.** A REST write does not update `seo_score`. Open the post in the editor once to refresh them.
7. **New posts:** include `aioseo_meta_data` in the create request so AIOSEO creates its row. The Abilities API returns 404 for posts without a row.
8. **Smart tags are stored literally** (`#post_title #separator_sa #site_title`) and resolved at output time. The AI "Add" buttons and some bulk tools replace smart tags with plain text.
9. **Never send `status`** when updating a published item: `"draft"` unpublishes it.

Useful `aioseo_meta_data` keys: `title`, `description`, `canonical_url`, `og_title`, `og_description`, `og_object_type`, `og_image_type`, `og_image_custom_url`, `og_article_section`, `og_article_tags`, `twitter_use_og`, `twitter_card`, `twitter_title`, `twitter_description`, `twitter_image_type`, `pillar_content` (Cornerstone), `priority`, `frequency`, `schema`, plus the keyphrase and robots keys above. Read an existing item first to see the exact shape on that site's version.

The seo-article-writer skill ships `build-aioseo-payload.mjs`, which builds a correct payload (keyphrase triple-write, robots, social, FAQ graph for read-modify-write) from a small JSON file. Reuse it rather than hand-building payloads.

## Creating a post with AIOSEO data

1. Upload media (`POST /wp/v2/media`), then set `alt_text`, `title`, `caption` on each.
2. Resolve category and tag IDs; create missing terms only with approval.
3. `POST /wp/v2/posts` with `title`, `slug`, `excerpt`, `content`, `status: "draft"`, `categories`, `tags`, `author`, `featured_media` and `aioseo_meta_data`.
4. Schema read-modify-write if a custom graph is needed.
5. Read back and verify. Publishing is a separate, explicit user decision.
6. By hand in the editor: primary category (the REST shape of `primary_term` is unverified), the Reviewer (Author SEO), and one editor load for TruSEO.

## Abilities API and the MCP server

AIOSEO (4.9.8+) registers "abilities" with the WordPress Abilities API (WordPress 6.9+). The free MCP Adapter plugin exposes them over MCP; they are also callable over REST.

- **REST route** (core Abilities controller): list with `GET /wp-json/wp-abilities/v1/abilities`; run with `/wp-json/wp-abilities/v1/abilities/<namespace>/<ability>/run`. Read-only abilities run with `GET` (input as a query parameter); others with `POST` and `{"input": {...}}`. Read each ability's annotations and input schema before calling it.
- **Known abilities** (5.0.3 source): `aioseo-posts/seo-data-get`, `aioseo-posts/seo-data-update` (title, description, canonical, focus and additional keyphrases, cornerstone, robots, OG and X title and description; no schema), `aioseo-posts/list-missing-seo`, `aioseo-posts/list-truseo-score`, `aioseo-settings/get`, `aioseo-audit/site-get`. Lite has 13 abilities in total (posts, settings, notifications, robots.txt, audit); Pro roughly doubles that (terms, redirects, Search Statistics); Link Assistant adds four. Run the listing on the site for the current set.
- **MCP setup:** All in One SEO » AI Suite » **MCP** tab: (1) registered abilities, (2) **Install MCP Adapter**, (3) **Generate Application Password** (shown once), (4) **Test connection**. The **Connect to AI Client** tabs give config snippets for Claude Desktop, Claude Code CLI, Gemini CLI, Cursor and VS Code. The docs say ChatGPT is not supported directly; one 2026 blog post says it is (see open-questions.md).
- In Claude Code, the user adds the server themselves from the snippet (it contains the Application Password). Then start a new session and check `claude mcp list`. Never take the password through chat.

## Bulk changes without code

- **Quick Edit** in the AIOSEO Details column: title and description inline, per row (terms on Pro).
- **CSV round trip:** Tools » Import/Export » Export Content (choose post types or taxonomies, CSV), edit in a spreadsheet, import. Export a JSON copy first as the rollback.
- **AI bulk actions** (credits): All Posts » Bulk actions » Generate SEO Titles / Meta Descriptions with AI; Media Library (list view) » Generate Alt Text for Images with AI. Review every suggestion; these replace existing values and smart tags.
- **Image SEO addon:** Media Library » Bulk actions » Autogenerate image attributes.
- **Link Assistant:** bulk Add Link and Dismiss for internal link suggestions.
- **Redirects:** CSV or JSON import, and import from other redirect plugins.

## Composer installs

Lite installs from Packagist. Pro and addons use AIOSEO's Composer repository with HTTP basic auth: username `key`, password = the licence key. `composer config -g http-basic...` stores the key in plain text in the global `auth.json`. For CI, use a `COMPOSER_AUTH` secret, and never commit `auth.json`. Details in developer-hooks.md.

## Credentials

- Use the connection or credential store the session provides. Never put an Application Password or licence key in chat, command arguments, logs, tool output or repository files.
- Prefer a dedicated WordPress user with the least role that works, one Application Password per client, and revoke it when the work ends (Users » Profile » Application Passwords).
- If no write access exists, hand the user the payload or a numbered wp-admin checklist instead.
