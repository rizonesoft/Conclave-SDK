# AI features, AI credits, AI Insights and the MCP server

AIOSEO AI Copilot, AI Assistant, image generator, AI schema, credits, AI Insights, the MCP server and Abilities, the Chrome extension.

Built from a full read of aioseo.com/docs, /faqs and /blog on 2026-10-11 (AIOSEO Pro 5.0.2 on aioseo.com). Each section lists its source pages. Text in [brackets] is a reviewer note where the vendor advice looks dated or conflicts with Google guidance. UI labels move between versions: confirm on the live site before giving click paths as fact. Unresolved points are in open-questions.md.

## Contents

- AI credits system
- AIOSEO AI features (Copilot tab, blocks, bulk actions)
- AI Insights (brand visibility in AI search)
- AIOSEO MCP server and Abilities
- All in One SEO Analyzer Chrome Extension

## AI credits system

Sources: https://aioseo.com/docs/buying-and-managing-credits-for-the-aioseo-ai-features/, https://aioseo.com/docs/what-are-ai-credits-and-who-can-use-these/, https://aioseo.com/docs/how-do-i-know-how-many-credits-i-need/, https://aioseo.com/docs/do-ai-credits-roll-over/, https://aioseo.com/docs/can-i-get-a-refund-for-my-ai-credits/, https://aioseo.com/docs/what-happens-after-i-use-all-my-free-credits/, https://aioseo.com/docs/what-happens-if-i-use-all-my-paid-credits/, https://aioseo.com/docs/is-a-subscription-license-for-aioseo-pro-included-with-a-purchase-of-ai-credits/ (system introduced June 2025; FAQ pages 2026-05)

- Credits are separate from the Pro licence. Free (Lite) and Pro users can both use the AI features.
- Pro subscriptions include a block of credits. Buying credits does **not** include a Pro licence.
- Free users get "free trial credits" and must buy credits or upgrade once those are used up.
- Path: **General Settings > License tab > AI Credits** section.
  - **Get AI Credits** opens the PAYG pricing page: a slider, then Buy AI Credits, then checkout.
  - **Connect Account** links an existing aioseo.com credits account (log in and authorize).
  - Activating a Pro key connects automatically.
  - Display: remaining on the left, total received on the right (e.g. 150,000 / 200,000). The (?) hover shows the renewal date.
- Also visible at https://aioseo.com/account/ > Overview.
- **Consumption order:** subscription credits first, then PAYG.
- **Expiry:** Pro credits reset on the annual renewal date with **no rollover**; PAYG credits expire **1 year after purchase**.
- **Typical cost:** about **10 credits** per action. Bulk title, bulk description and bulk alt text are 10 credits each. Image cost depends on Quality. Every generate button shows its cost in advance.
- **Refund:** within **14 days** and only if **fewer than 500 credits** were used; request through Support.
- **AI Content defaults:** **All in One SEO > AI Suite > AI Content** tab (one page spells it "AI Suites").
  - Text: **Tone**, **Audience**.
  - Image: **Quality**, **Style**, **Aspect Ratio**.
  - Per-use settings override these defaults.

---

## AIOSEO AI features (Copilot tab, blocks, bulk actions)

Sources: https://aioseo.com/docs/generating-seo-titles-and-meta-descriptions-using-aioseo-ai/, https://aioseo.com/docs/generating-faqs-using-aioseo-ai/, https://aioseo.com/docs/generating-key-points-using-aioseo-ai/, https://aioseo.com/docs/generating-social-posts-using-aioseo-ai/, https://aioseo.com/docs/generating-schema-markup-using-aioseo-ai/ (2026-04), https://aioseo.com/docs/generating-image-alt-text-using-aioseo-ai/ (2026-04), https://aioseo.com/docs/using-the-ai-assistant-in-all-in-one-seo-to-create-content/ (2025-10), https://aioseo.com/docs/using-the-ai-image-generator-in-all-in-one-seo/ (2025-10), https://aioseo.com/docs/optimizing-your-content-with-aioseo-copilot/ (2026-08-06), https://aioseo.com/docs/using-openai-to-generate-seo-titles-and-meta-descriptions/

**Entry point:** Edit Post > AIOSEO Settings > **AI Copilot** tab. It shows the credit balance and the available actions. Tone choices include Friendly, Informal and Professional; Audience choices include Business, Educational and Technical. Both override the AI Suite defaults. Editor support for these actions: Block Editor, Classic Editor and supported page builders, unless noted otherwise below.

| Feature | Where | Output / notes |
|---|---|---|
| SEO Titles | AI Copilot > SEO Titles > Generate SEO Titles; or **Use AI Generator** button beside the Post Title field (Appearance tab) | Click **Add** to put the title in the Post Title field, **replacing existing text and smart tags** |
| Meta Descriptions | AI Copilot > Meta Descriptions; or Use AI Generator beside Meta Description | Add replaces the field contents, including smart tags |
| Bulk titles / descriptions | All Posts (any type) > tick posts > Bulk actions: **Generate SEO Titles with AI** / **Generate Meta Descriptions with AI** > Apply | Bulk Generator screen; "more suggestions" link with radio buttons; **Back to Posts** applies the choices. 10 credits each; titles and descriptions run as separate passes |
| FAQs | Place the cursor first, then AI Copilot > FAQs > Generate FAQs | Checkboxes > **Insert FAQ Blocks** (the AIOSEO FAQ block; FAQ schema is output automatically). Regenerate, Copy |
| Key Points (TL;DR) | Place the cursor first, then AI Copilot > Key Points | Insert Key Points Blocks; Regenerate; Copy |
| Social Posts | AI Copilot > Social Posts | Channels: Facebook, Instagram, LinkedIn, X (Twitter), marketing email. Per-channel tabs; **Copy only**, nothing is posted |
| AI Schema (Basic+) | AIOSEO Settings > **Schema** tab > Generate Schema > **AI Schema** tab | **Smart Schema** (no prompt) or **Prompt-Based Schema** (Your Prompt field). Results have checkboxes and expand to show markup. **Test with Google** opens the Rich Results Test. **Add Schema**; Regenerate Schema |
| Image Alt Text | Media Library (list) > select images > Bulk actions: **Generate Alt Text for Images with AI** | Progress screen; **10 credits per image** |
| AI Assistant block | Block Editor only: add block "**AIOSEO – AI Assistant**" | Prompt > Generate. Toolbar: translate, summarize, longer/shorter. Sidebar: Tone/Audience and credit use. Regenerate/Delete at the bottom |
| AI Image Generator | Image block > **Generate with AI**; existing image > **Edit with AI** (prompt and Quality > Regenerate); featured image > **Generate with AI** beside "Set featured image" | **Quality**: Low/Medium/High (affects cost). **Style**: Auto, 3D Render, Cinematic, Creative, Illustration, Minimalist, Stock Photo, Vibrant. **Aspect Ratio**: Landscape/Portrait/Square. Insert Image. Do not close the window while it generates. The image page says Block, Classic and page builders, but the steps use the Block Editor |
| **AI Copilot Optimize** (new 2026-08) | Optimization tab > Content Optimization > **Optimize with AI**; or AI Copilot tab > Auto-Optimize > **Optimize** | One run rewrites SEO title, meta description, headline and content, and fixes spelling. **Block Editor only.** Saves a WordPress revision first. Summary shows the new TruSEO score and before/after per entry, each with **Revert**, plus a "What's next" list. **Done** applies the changes but does **not save**; you must Save/Update, and a refresh before saving loses them. **Re-optimize** costs credits again. Undo after saving by restoring the pre-run revision. Takes under a minute for a short post, a couple of minutes for a long one. The before/after scores shown in the modal are illustrative only |

- **Legacy OpenAI integration:** added in 4.3.2 (General Settings > Advanced > **OpenAI API Key**, GPT-3.5 Turbo, Basic+). Replaced by AI credits in **v4.8.4 (June 2025)**. The old SEO Title and Meta Description Generators are superseded.
- The docs remind you that search engines may rewrite titles and snippets. Every AI page carries a disclaimer to verify accuracy. For schema, validate structured data before publishing.

---

## AI Insights (brand visibility in AI search)

Source: https://aioseo.com/docs/using-ai-insights-to-research-brand-performance-in-ai-search/ (published 2025-12-17)

- **BETA**, available with **AIOSEO Pro**. Keyword reports are "100% free for a limited time".
- Path: **All in One SEO > AI Suite**. Tabs: **Keyword Reports**, **Brand Tracker** (Coming Soon), **AI Content** (AI defaults).
- **Keyword Reports:** the "Discover Which Brands Rank in AI Search Results" section has an AI search field. Enter a query (e.g. "best dog food for puppies") and click **Generate**.
  - The Reports table shows Keyword, Status (it becomes Completed), brand count and date.
  - Tools: search, All Statuses filter, Bulk Actions > delete, and an arrow to open a report.
- **Report view:**
  - **Brands comparison table**: Brand, overall Rank, and a column per engine (**OpenAI, Claude, Gemini, DeepSeek, Perplexity**). Cell colours: dark blue = positions 1-3, lighter blue = mid, grey = low, dash = not mentioned. Paginated.
  - **AI Engine Results**: an expandable card per engine with Sources count and Brands count. Expanded: Brand Mentions pills (e.g. "Brand (#1)"), the full response, and the Web Search Sources links.
- Tip: specific long-tail queries give better insight.

---

## AIOSEO MCP server and Abilities

Source: https://aioseo.com/docs/connecting-an-ai-assistant-to-your-site-with-aioseos-mcp-server/ (published 2026-06-16, MODIFIED 2026-10-01)

- **Requirements:** WordPress **6.9+** (the release that added the Abilities API); AIOSEO **4.9.8+**; the free **MCP Adapter** WordPress plugin (AIOSEO installs it in one click).
- AIOSEO registers SEO "abilities" with the WordPress Abilities API; the MCP Adapter exposes them over MCP.
- **Ability counts:**
  - Free: **13** abilities covering posts, settings, notifications, robots.txt and site audits.
  - Pro: "doubles" that, adding terms (taxonomy SEO), redirects and Search Statistics.
  - The Link Assistant addon adds **four** more.
  - Search Statistics abilities are registered but return data only on **Elite**. Link Assistant abilities need the addon (Pro/Elite).
  - Categories in "View all abilities": Posts, Settings, Notifications, Robots.txt, Audit, Terms, Redirects, Search Statistics, Link Assistant.
- Path: **All in One SEO > AI Suite > MCP** tab, a 4-step wizard with a progress counter:
  1. **Registered SEO abilities**: green check; expand View all abilities.
  2. **Install MCP Adapter** button: downloads and activates it.
  3. **Generate Application Password**: shows the username and a one-time Application Password with a Copy button. It has the same access as your user account and is shown only once.
  4. **Test connection**: signs in and reports the number of abilities found; "Connection successful".
- **Connect to AI Client** tabs: **Claude Desktop, Claude Code CLI, Gemini CLI, Cursor, VS Code**. Each gives a ready config snippet (**Copy snippet**) and the config file location. The password is pre-filled only while you stay on the page. Restart the client after adding the snippet.
- ChatGPT is not supported directly (its connectors use a different sign-in method); use one of the listed clients instead.
- **Example tasks:** find posts missing meta descriptions, read and update SEO fields, create redirects, summarise Search Statistics, run site audits.
- **Revoke access:** WordPress profile > Application Passwords. A lost password means generating a new one and updating the client config.
- [Security: an Application Password grants the user's full capabilities, not just SEO. Use a dedicated low-privilege user where possible.]

---

## All in One SEO Analyzer Chrome Extension

Source: https://aioseo.com/docs/all-in-one-seo-analyzer-chrome-extension/ (published 2025-04-01)

- Free, from the Chrome Web Store. Works in any Chromium browser, including Edge. Pin it via the puzzle icon.
- **Tabs:**
  - **Overview**: SEO score; title and meta description length; URL indexability and self-referencing canonical check; keywords; robots meta; language; word and character count; links to robots.txt and the XML sitemap.
  - **Headings**: H1-H6 structure.
  - **Links**: internal, external, unique; CSV export.
  - **Images**: alt and title presence, missing ones; CSV export.
  - **Schema**: the page's markup.
  - **Social**: Open Graph and Twitter markup.
  - **Tools**: links to Business Name Generator, Advanced SEO Analyzer, Headline Analyzer, WordPress Theme Detector, Nameboy, Keyword Generator, Ahrefs, Web Archive, Buzzsumo, Majestic, Moz, PageSpeed Insights, Semrush, SimilarWeb, Structured Data Testing Tool, Whois, an `-inurl:https` search and a `site:domain.com` search.
  - **Settings**: Highlighting No-Follow Links; a link to the AIOSEO plugin.
- CSV export for links, images, headings and social OG data.
- [The Structured Data Testing Tool was retired by Google; use the Rich Results Test or validator.schema.org.]

---
