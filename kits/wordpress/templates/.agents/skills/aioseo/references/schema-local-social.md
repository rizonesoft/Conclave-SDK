# Schema, Local SEO, breadcrumbs and social

Schema output and generator, every schema type, Local Business SEO, breadcrumbs, social profiles, Facebook/Open Graph, X cards, Pinterest.

Built from a full read of aioseo.com/docs, /faqs and /blog on 2026-10-11 (AIOSEO Pro 5.0.2 on aioseo.com). Each section lists its source pages. Text in [brackets] is a reviewer note where the vendor advice looks dated or conflicts with Google guidance. UI labels move between versions: confirm on the live site before giving click paths as fact. Unresolved points are in open-questions.md.

## Contents

- Schema overview (what AIOSEO outputs automatically)
- Knowledge Graph settings (Person or Organization)
- Schema defaults per content type
- Schema Generator (per-post schema)
- Custom Schema (paste your own JSON-LD)
- Schema Templates
- Schema validation
- Schema type field reference
- Sitelinks Search Box
- Local SEO: activation and tier
- Local SEO: single location (Business Info)
- Local SEO: opening hours
- Local SEO: multiple locations
- Local SEO: displaying locations (widgets, blocks, shortcodes, PHP)
- Local SEO: Google Maps setup
- Local SEO: displaying maps
- Breadcrumbs: settings
- Breadcrumbs: templates (Pro)
- Breadcrumbs: primary term (Pro)
- Breadcrumbs: display methods
- Social Profiles (Knowledge Panel sameAs)
- Facebook / Open Graph: global settings
- Facebook: per-content settings
- X/Twitter cards: global settings
- Pinterest
- SEO Preview (admin bar)
- Emoji picker
- Deprecated Open Graph settings (v4.0)
- Troubleshooting: Facebook and X sharing
- WooCommerce product shipping and return policy schema

## Schema overview (what AIOSEO outputs automatically)
Sources: https://aioseo.com/docs/a-guide-to-schema-org-markup-for-rich-snippets/, https://aioseo.com/docs/configuring-the-schema-settings-in-all-in-one-seo/

- Output format: JSON-LD.
- Output on all Pages, Posts, CPTs, Categories, Tags, custom taxonomies, media attachments, date and author archives, 404 page and search results page:
  - Breadcrumb markup (BreadcrumbList)
  - Sitelinks Searchbox
- Knowledge Graph markup: Corporate Contact, Organization Logo, Local Business markup (Pro Plus+).
- Data AIOSEO uses to build schema: title of post/page/term; SEO Description or content/excerpt; Featured Image and its caption; content language (HTML lang); categories and tags; SEO Keywords; author's Facebook profile (when Show Facebook Author is on); author's Twitter profile (when Show Twitter Author is on).
- Pro schema types (Schema Catalog): Article, Book, Car, Course, Dataset, Event, Fact Check, FAQ, How To, Job Posting, Movie, Music, Person, Product, Product Review, Recipe, Service, Software (Application), Video, Web Page.
- Every type page repeats: values set in the generator appear only in the page source (JSON-LD), not as visible content; and search engines decide per query whether to show a rich result.
- External test tools the doc lists: Google Rich Results Test; Yandex Webmaster structured data validator (needs account); "Structured Data Testing Tool" [dated: Google retired SDTT; the general validator now lives at validator.schema.org].

## Knowledge Graph settings (Person or Organization)
Sources: https://aioseo.com/docs/configuring-the-schema-settings-in-all-in-one-seo/

Location: All in One SEO > Search Appearance > Global Settings tab > Knowledge Graph section.

| Setting | Notes |
|---|---|
| Website Name | Defaults to WordPress Settings > General > Site Title. Google may use it (WebSite name / site names in results). |
| Alternate Website Name | Any alternate name for the site. |
| Person or Organization | Chooses which fields follow. |

Organization fields: Organization Name (text or smart tags), Organization Description (text or smart tags), Email Address, Phone Number, Founding Date, Number of Employees (a number, or toggle to enter a range), Logo.
- Logo: minimum 112 x 112 px; JPEG, PNG, SVG, WEBP or GIF; URL must be crawlable and indexable. If empty, AIOSEO uses the theme's logo (if any).
- Phone: type normally with area code (and leading zero); AIOSEO outputs international format (adds + and country code, drops the leading zero).

Person fields: Choose a Person (dropdown lists only users with role Author, Editor or Administrator) or "Manually Enter Person" then Name and Logo. Person Logo: min 112 x 112 px, jpg/png/gif, crawlable and indexable. (Note the format lists differ between Organization and Person.)

## Schema defaults per content type
Sources: https://aioseo.com/docs/configuring-the-schema-settings-in-all-in-one-seo/, per-type pages listed below

Location: All in One SEO > Search Appearance > Content Types tab > (section per post type) > Schema Markup tab > Schema Type dropdown, then Save Changes. Tier: Pro Basic+.
- Some types show a second dropdown: Article > Article Type; Web Page > Web Page Type (includes FAQ Page).
- AIOSEO recommends: Posts = Article, Pages = Web Page.
- FAQ as a default is done as Schema Type = Web Page plus Web Page Type = FAQ Page (there is no separate "FAQ" content-type default).
- Types whose docs show a content-type default: Article, Car, Course, Dataset, Movie, Person, Product, Product Review, Recipe, Service, Software Application, Web Page (and FAQ via Web Page Type). Types documented only as per-post generator schema: Book, Event, Fact Check, How-To, Job Posting, Music, Video.

## Schema Generator (per-post schema)
Sources: https://aioseo.com/docs/setting-the-schema-type-for-individual-content/, https://aioseo.com/docs/configuring-the-schema-settings-in-all-in-one-seo/

Tier: Pro Basic+. Applies to Posts, Pages and CPTs.
1. Edit content > AIOSEO Settings section (below content) > Schema tab.
2. Generate Schema button opens the Schema Generator (tabs include the Schema Catalog, Custom Schema, Your Templates).
3. Click the Add Schema icon next to a type, complete fields, click Add Schema.
4. Added schema appears as a graph card under "Schema In Use" with Edit Schema and Delete Schema icons.
- Multiple schema types (graphs) can be added to one item.
- Per-post schema overrides the content-type default.

## Custom Schema (paste your own JSON-LD)
Sources: https://aioseo.com/docs/creating-custom-schema-markup-with-all-in-one-seo/

Tier: Pro Basic+. AIOSEO Settings > Schema tab > Generate Schema > Custom Schema tab.
- Paste JSON-LD into the editor; AIOSEO validates it for errors.
- Enter a name for the custom schema graph (required in practice).
- Add Schema saves it to the post; Save as Template stores it as a reusable template.
- The doc points to Google's per-type JSON-LD examples as starting material.

## Schema Templates
Sources: https://aioseo.com/docs/creating-reusable-schema-templates-in-all-in-one-seo/

Tier: Pro Basic+.
- Create: Schema Generator > pick a type from Schema Catalog > fill fields > Save Schema as Template > enter unique name > Save Template.
- Use: Generate Schema > Your Templates tab > Add Schema icon.
- Edit: Edit Template icon > change > Update Template.
- Delete: while editing, Delete Template > confirm "Yes, I want to delete this template".

## Schema validation
Sources: https://aioseo.com/docs/testing-your-schema-in-all-in-one-seo/

- AIOSEO Settings > Schema tab > Validate Schema button: popup shows the page's schema; Test With Google opens Google's Rich Results Test pre-populated with the markup; click Test Code. Left pane shows JSON, right pane results and errors.
- The doc says contact AIOSEO support for errors.

## Schema type field reference

All types: add via Schema Generator (Pro Basic+). "Default" = what AIOSEO prefills. Smart tags are allowed where noted.

### Article
Sources: https://aioseo.com/docs/setting-article-schema-markup-in-your-content/
- Content-type default: Schema Type = Article, then Article Type.
- General: Type (Article, Blog Post, News Article; Blog Post and News Article are more specific), Name (default post title; smart tags), Headline (default post title; smart tags), Description (default content; smart tags), Image (default featured image; upload, library or URL), Keywords.
- Author: name, optional author page URL.
- Dates: published and last-modified via date picker; Include Dates toggle (No = asks engines not to show dates).

### Book
Sources: https://aioseo.com/docs/setting-book-schema-markup-in-your-content/
- Title (default post title), Description (default content), Author, Image.
- Edition (repeatable, "Add Another Edition"): Title, Book Edition, Author, ISBN, Book Format (select), Date Published.
- Review: Rating, Headline, Content, Author. Review Rating: Rating Minimum, Rating Maximum.
- [Note: Google announced in June 2025 it is phasing out Book Actions rich results; Book markup still valid schema.org but expect no Google rich result.]

### Car (Vehicle)
Sources: https://aioseo.com/docs/setting-vehicle-car-schema-markup-in-your-content/ (PUBLISHED 2024-08-23)
- Content-type default: Schema Type = Car.
- Car Details: Name (e.g. "Used 2020 BMW 530i w/ Convenience Package"), Description, Brand, Image.
- Identifiers: Vehicle Identification Number (VIN), Configuration (body style/trim, e.g. S, SV, SL), Model, Model Year (YYYY).
- Offer: Price, Currency, Price Valid Until, Availability.
- Attributes: Color (OEM exterior), Interior Color, Interior Type, Body Type, Drive Wheel Configuration, Transmission, Seating Capacity, Number of Doors, Item Condition (new/used), Fuel Type.
- [Note: Google announced in June 2025 it is phasing out the Vehicle Listing rich result.]

### Course
Sources: https://aioseo.com/docs/setting-course-schema-markup-in-your-content/
- Name (default post title; smart tags), Description (default content; smart tags), Publish Date, About (skills keywords), Teaches (subject keywords), Prerequisites (text or URL of a prior course), Image.
- Course Provider: Name, URL, Image (logo). Leave blank to use the Knowledge Graph Organization.
- Offers (repeatable): Pricing Category (Paid, Subscription, Free, Partially Free), Price ("0" if free), Currency.
- Course Instances (repeatable): Mode (Online, Onsite, Blended), Workload (total minutes). Schedule: Duration (hours per Repeat Frequency unit), Repeat Count (number of units course lasts), Repeat Frequency (Daily, Weekly, Monthly, Yearly), Start Date, End Date. Instructor: Name, Description, Image.
- Reviews (repeatable): Rating, Headline, Content, Author. Review Rating: Minimum, Maximum.
- Syllabus Sections: Name, Description, Time Required (minutes).
- [Note: Google announced in June 2025 it is phasing out Course Info rich results; the Course list carousel may remain. Verify against current Google docs.]

### Dataset
Sources: https://aioseo.com/docs/setting-dataset-schema-markup-in-your-content/
- Name (default post title), Description (default content), Same As (URL of original publication), Alternative Names, Data Catalog (parent catalog name), Identifier (DOI or Compact Identifier), License, Accessible for Free, Keywords, Temporal Coverage, Spatial Coverage (coordinates).
- Sub Datasets (repeatable): Name, Description. Downloads (repeatable): Encoding Format, Content URL.

### Event
Sources: https://aioseo.com/docs/setting-event-schema-markup-in-your-content/ (MODIFIED 2026-06-11)
- Name (default post title), Description (default content), Type, Status, Attendance Mode (online, offline, both).
- Dates: Event Date (start and end date/time).
- Location: Name, URL, Street Address, Locality, Postal Code, Region, Country (dropdown).
- Offer: Price ("0" for free), Currency, Sale Start Date, URL (ticket page).
- Organizer: Type (Person or Organization), Name, URL. Blank = Knowledge Graph Organization.
- Performer: Type, Name, URL.
- Images (one or more). Review: Rating, Headline, Content, Author; Review Rating Min/Max.

### Fact Check (ClaimReview)
Sources: https://aioseo.com/docs/setting-fact-check-schema-markup-in-your-content/
- Name (default post title), Description (default content), Rating (how true/false the claim is), Date Published.
- Author: Type, Name, URL (the doc text says "organizer"; copy-paste wording). Blank = Knowledge Graph Organization.
- Claim: Appearance (link to where the claim was published, or inline description), Date Published, Author Type, Author Name, Author URL.
- [Note: Google announced in June 2025 it is phasing out ClaimReview (fact check) rich results in Search.]

### FAQ
Sources: https://aioseo.com/docs/setting-faq-page-schema-markup-in-your-content/
- Name (default post title), Description (default content). Questions (repeatable "Add Another Question"): Question, Answer.
- Content-type default: Web Page + Web Page Type = FAQ Page.
- The doc notes Google changed FAQ rich result eligibility in August 2023. [Note: since then FAQ rich results show only for well-known authoritative government and health sites; markup is still harmless but rarely produces a visual result.]

### How-To
Sources: https://aioseo.com/docs/setting-how-to-schema-markup-in-your-content/
- Name, Description, Supplies, Tools, Required Time (days, hours, minutes), Image (default featured image).
- Estimated Cost: Price, Currency.
- Steps (repeatable): Title, Details, URL (can be an anchor link to the step), Image.
- The doc notes the August 2023 Google change. [Note: Google removed How-To rich results entirely (desktop and mobile) in September 2023; recommending How-To schema for SERP gain is dated.]

### Job Posting
Sources: https://aioseo.com/docs/setting-job-posting-schema-markup-in-your-content/
- Job Title (default post title), Description (default content), Employment Type, Work from Home (100% remote).
- Location: address of employment.
- Hiring Organization: Name, URL, Logo. Blank = Knowledge Graph Organization.
- Salary: Pay Range, Pay Interval, Currency.
- Requirements: "Experience instead of Indication" (UI label as printed; means experience accepted in place of education), Months of Experience, Required Degree.
- Dates: Publish Date, Expiration Date.

### Movie
Sources: https://aioseo.com/docs/setting-movie-schema-markup-in-your-content/
- Name, Description, Director, Release Date, Image (default featured image).
- Review: Headline, Content, Author (default post author). Review Rating: Rating Value (average), Minimum, Maximum.
- Purpose given: movie carousel (title, director, image, star rating).

### Music
Sources: https://aioseo.com/docs/setting-music-schema-markup-in-your-content/
- Type (Music Group or Music Album), Name, Description, Image.

### Person
Sources: https://aioseo.com/docs/setting-person-schema-markup-in-your-content/
- Name, Description, Email, Job Title, Image (default featured image). Location: address.

### Product
Sources: https://aioseo.com/docs/setting-product-schema-markup-in-your-content/
- Product Details: Name (default post title), Description (default content), Brand, Image (default featured image).
- Identifiers: SKU, GTIN, MPN, ISBN.
- Offer: Price, Currency, Price Valid Until, Availability.
- Attributes (used for Google merchant listings): Material (slash-separated, e.g. cotton/polyester), Color (slash-separated, e.g. Red/Green/Black), Pattern (one only), Size (slash-separated, e.g. small/medium/large), EU Energy Rating (dropdown).
- Audience (merchant listings): Gender, Minimum Age, Maximum Age.
- Reviews (repeatable): Rating Value, Headline, Content, Author. Review Rating: Minimum, Maximum.
- Shipping Destinations (repeatable, merchant listings): Country, States, Postal Code, Price.
- WooCommerce: Product schema on a Woo product shows Autogenerate Fields (Yes = AIOSEO fills most fields from WooCommerce data; No = edit everything manually). No Review Rating section: AIOSEO uses WooCommerce reviews (if enabled). Brands read automatically from WooCommerce Brands and Perfect Brands for WooCommerce.
- Easy Digital Downloads: same Autogenerate Fields option on EDD Downloads; Review Rating section is shown, and reviews come from the EDD Reviews plugin.
- AIOSEO – Product block (Block Editor) displays a product and adds Product schema automatically; for sites showing products without an ecommerce plugin.

### Product Review
Sources: https://aioseo.com/docs/setting-product-review-schema-markup-in-your-content/ (PUBLISHED 2024-08-21)
- Content-type default available ("Product Review" in Schema Type).
- Product Details, Offer, Identifiers, Attributes, Audience: same fields as Product.
- Rating section: Rating (default scale 1 to 5), Headline, Content, Author (smart tags allowed), Positive Notes (keywords/keyphrases, e.g. "cheap", "user-friendly"), Negative Notes (e.g. "expensive", "difficult to use"). Positive/Negative Notes map to Google's pros and cons.
- Review Rating: Minimum, Maximum.

### Recipe
Sources: https://aioseo.com/docs/setting-recipe-schema-markup-in-your-content/
- Name, Description, Author (default post author), Ingredients (each with measurement, e.g. "1 tablespoon of flour"), Dish Type, Cuisine Type, Keywords, Image (default featured image).
- Nutrition: Amount of Servings, Calories (per serving).
- Time Required: Preparation Time, Cooking Time.
- Instructions (repeatable): Title, Details, Image.
- Reviews (repeatable): Rating Value, Headline, Content, Author; Review Rating Min/Max.
- AIOSEO – Recipe block displays a recipe and adds Recipe schema automatically.

### Service
Sources: https://aioseo.com/docs/setting-service-schema-markup-in-your-content/
- Name, Description, Type, Image. Offer: Price, Currency. Provider: Type (Person/Organization), Name, URL; blank = Knowledge Graph Organization.

### Software Application
Sources: https://aioseo.com/docs/setting-software-application-schema-markup-in-your-content/
- Content-type default label "Software Application"; generator label "Software".
- Name, Description, Category (select), Operating System. Offer: Price, Currency. Review Rating: Rating Value (average), Minimum, Maximum.

### Video
Sources: https://aioseo.com/docs/setting-video-schema-markup-in-your-content/
- Name, Description, Content URL (file, e.g. MP4/MOV), Embed URL (player, e.g. YouTube/Vimeo), Upload Date, Family Friendly, Thumbnail URL (default featured image).

### Web Page
Sources: https://aioseo.com/docs/setting-web-page-schema-markup-in-your-content/
- Content-type default: Schema Type = Web Page, then Web Page Type (options include FAQ Page; full list not given in docs).
- Per post: Add Schema next to Web Page, choose Type, Add Schema.

## Sitelinks Search Box
Sources: https://aioseo.com/docs/how-to-get-google-to-display-the-sitelinks-search-box/

- All in One SEO > Search Appearance > Advanced tab > Enable Sitelinks Search Box (On/Off). On = outputs the WebSite SearchAction markup Google looked for.
- Doc: no guarantee Google shows it.
- [Dated: Google removed the sitelinks search box from Search results in November 2024 and no longer uses this markup. Leaving it on is harmless; it brings no SERP feature.]

---

## Local SEO: activation and tier
Sources: https://aioseo.com/docs/local-business-seo-for-a-single-location/, https://aioseo.com/docs/local-business-seo-for-multiple-locations/

- Tier: Pro Plus or above (Local Business SEO addon, plugin folder `aioseo-local-business`).
- All in One SEO > Local SEO. Click Activate Local SEO if shown.
- Tabs referenced: Locations (contains Location Settings and Business Info), Opening Hours, Maps. (Later docs name the path "All in One SEO » Local SEO » Locations"; older function docs say "Local Seo -> Business Info".)
- Output: LocalBusiness schema. Docs: "Local Business Schema markup is ONLY output in the homepage source code" and "Opening Hours Schema markup is ONLY output in the homepage source code" (single location). The multiple-locations doc does not state where location schema is output (presumably each Location post).
- Search engines decide per query whether to show a knowledge card.

## Local SEO: single location (Business Info)
Sources: https://aioseo.com/docs/local-business-seo-for-a-single-location/

Location Settings: Multiple Locations = No for a single location. Business Info section is hidden when Multiple Locations = Yes.

| Field | Notes |
|---|---|
| Name | Business name |
| Image | Upload, library or URL (logo or premises photo) |
| Type | LocalBusiness subtype dropdown |
| Address fields | Primary address |
| Address Format | Smart tags for each address part; controls display via widget/block/shortcode/PHP only |
| Map | "Enter a query" field; places pin; needs Google Maps API key |
| Contact Info | Email, Phone, Fax (type without brackets/hyphens) |
| IDs | VAT ID, Tax ID |
| Payment Info | Price Indicator (dropdown), Currencies Accepted (dropdown), Payment Methods Accepted (comma-separated) |
| Area Served | Comma-separated cities, postal codes, etc. |

Save Changes at top or bottom.

## Local SEO: opening hours
Sources: https://aioseo.com/docs/local-business-seo-for-a-single-location/, https://aioseo.com/docs/adding-a-location-in-local-seo-addon/

Global (Local SEO > Opening Hours tab):
- Show Opening Hours (Yes/No; Yes + Save Changes to set and display).
- Display Info: shows how to output via widget, shortcode, block or PHP.
- Labels: text for days marked Open 24h and Closed.
- Open 24/7 toggle. Use 24h format toggle.
- Per day: open/close dropdowns plus Open 24h and Closed checkboxes.

Per Location (Opening Hours tab in the AIOSEO Local Business box): adds Use Defaults toggle (Yes = use global Opening Hours settings), then Show Opening Hours, Labels, Open 24/7, Use 24h format, per-day hours.

## Local SEO: multiple locations
Sources: https://aioseo.com/docs/local-business-seo-for-multiple-locations/, https://aioseo.com/docs/adding-a-location-in-local-seo-addon/ (MODIFIED 2026-08-14), https://aioseo.com/docs/enhanced-search-query-conflict/

Enable: Local SEO > Location Settings > Multiple Locations = Yes > Save Changes. Creates a Locations post type (WordPress menu item "Locations") with taxonomy Location Categories.

Advanced Locations Settings:

| Setting | Default / values | Notes |
|---|---|---|
| Locations Permalink | slug `location` | "Use custom slug" checkbox reveals a field replacing `location` |
| Locations Category Permalink | slug `locations-category` | "Use custom category slug" checkbox |
| Enhanced Search | No / Yes | Yes = locations included in on-site search (searches street address, city, zip) |
| Enhanced Search – Excerpt | On/Off (shown when Enhanced Search = Yes) | On = location addresses shown in search results |
| Custom Admin Labels | single and plural labels | Renames the Locations admin menu |

Adding a location: Locations > Add New. Title = location name; content area; sidebar has Location Categories and Featured Image. Below content: AIOSEO Settings (normal SEO) and AIOSEO Local Business box with tabs Business Info and Opening Hours.
- Business Info fields: Name, Type, Image (falls back to Featured Image), Address, Address Format (smart tags), Map (Enter a query), Contact Info (email/phone/fax), IDs (VAT/Tax), Price Indicator, Currencies Accepted, Payment Methods Accepted (comma list), Area Served (comma list).
- Import from other plugins: referenced, separate article (not in the docs).

Enhanced Search safeguards and troubleshooting:
- If AIOSEO detects a conflict with the WP search query, the option cannot be turned on.
- If it was on and a conflict appears later (plugin or WP update), AIOSEO disables it automatically and shows a warning.
- Symptom: warning / cannot enable. Cause: another plugin or update altering the search query. Fix: deactivate the newly installed plugin; identify whether a WP, plugin or theme update caused it; do not roll back versions without a DB backup (data loss risk); fresh install that cannot enable it: contact AIOSEO support.

## Local SEO: displaying locations (widgets, blocks, shortcodes, PHP)
Sources: https://aioseo.com/docs/displaying-locations-on-your-site/, function and shortcode pages below

Widgets (Appearance > Widgets, search "AIOSEO Local"):
- Business Info: Title; Location dropdown (only with Multiple Locations; otherwise uses global Business Info); Show labels, Show icons; Labels fields; checkbox per data item; After widget text.
- Opening Hours: Title; Location dropdown; Show title (shows "Our Opening Hours", editable in Label), Show icons (clock icon); checkbox per day; After widget text.
- Locations by Category: Title; Category dropdown; lists linked locations. Multiple Locations only.

Blocks (Block Editor only): AIOSEO Local – Business Info; AIOSEO Local – Opening Hours; AIOSEO Local – Locations (Location Category dropdown; Multiple Locations only); AIOSEO Local – Location Categories (lists categories, no settings). Business Info and Opening Hours blocks have no sidebar settings when Multiple Locations is off.

### Shortcode `[aioseo_local_business_info]` / PHP `aioseo_local_business_info( array $args )`

| Shortcode attr | PHP key | Default | Purpose |
|---|---|---|---|
| location_id | locationId | '' | Location post ID (Multiple Locations on). Empty with Multiple Locations off = global Business Info |
| show_labels | showLabels | true | Labels (Address:, Phone:, ...) |
| show_icons | showIcons | true | Icons |
| show_name | showName | true | Business name |
| show_address | showAddress | true | Address |
| show_phone | showPhone | true | Phone |
| show_fax | showFax | true | Fax |
| show_email | showEmail | true | Email |
| show_vat | showVat | true | VAT ID |
| show_tax | showTax | true | Tax ID |
| address_label | addressLabel | Address | Label text |
| phone_label | phoneLabel | Phone | Label text |
| fax_label | faxLabel | Fax | Label text |
| email_label | emailLabel | Email | Label text |
| vat_id_label | vatIdLabel | VAT ID | Label text |
| tax_id_label | taxIdLabel | Tax ID | Label text |

Example: `[aioseo_local_business_info location_id=100 show_labels=false show_fax=false]`
PHP: `<?php if( function_exists( 'aioseo_local_business_info' ) ) aioseo_local_business_info( array( 'locationId' => '1', 'showFax' => 'false', 'phoneLabel' => 'Call' ) ); ?>` (the doc's own example passes 'true' to every *Label key, which is wrong: label keys take text.)

### Shortcode `[aioseo_local_opening_hours]` / PHP `aioseo_local_opening_hours( array $args )`

| Shortcode attr | PHP key | Default |
|---|---|---|
| location_id | locationId | empty (Multiple Locations off = global Opening Hours) |
| show_title | showTitle | true |
| show_icons | showIcons | true |
| show_monday ... show_sunday | showMonday ... showSunday | true |
| label | label | "Our Opening Hours:" |

Example: `[aioseo_local_opening_hours location_id=4573 show_icons=false label="Hours of Operation:"]`. (Doc's PHP example has a syntax error: `'showWednesday => 'true'` is missing a quote, and sets `'label' => 'true'`.)

### Shortcode `[aioseo_local_locations]` / PHP `aioseo_local_locations( array $args )`
- category_id / categoryId: default empty; Location Category term ID (Multiple Locations on). Example `[aioseo_local_locations category_id=100]`.

### Finding IDs
- Location ID: edit the location, read `post=<ID>` in the URL.
- Location Category ID: edit the category, read `tag_ID=<ID>` in the URL.

### Template overrides
Sources: https://aioseo.com/docs/local-business-seo-template-overrides/
- Since Local Business SEO 1.1.0, blocks, widgets and shortcodes render via view files in `wp-content/plugins/aioseo-local-business/app/Views/`.
- Override by copying to `wp-content/themes/{your-theme}/aioseo/localBusiness/`: `BusinessInfo.php`, `OpeningHours.php`, `Locations.php`. (No map template mentioned.)

## Local SEO: Google Maps setup
Sources: https://aioseo.com/docs/setting-up-google-maps/, https://aioseo.com/docs/how-to-create-a-google-maps-api-key/, https://aioseo.com/docs/selecting-the-google-maps-apis-to-use-with-all-in-one-seo/, https://aioseo.com/docs/using-places-on-your-maps/

Location: All in One SEO > Local SEO > Maps tab.
- API Key field: paste key, Save Changes; a sample map appears in Map Preview. Invalid key shows a notice.
- Map Settings > Display Map: Widget, Shortcode, Gutenberg Block, PHP Code (informational choices).
- Default Map Style: Roadmap, Hybrid, Satellite, Terrain (overridable per map).
- Custom Marker: upload an image for the pin (block can override per map).

Google Cloud APIs:

| API | Required? | Used for |
|---|---|---|
| Maps JavaScript API | Required | Rendering maps (dynamic "Normal Map"; billed usage) |
| Geocoding API | Required | Plotting address entered in AIOSEO |
| Maps Embed API | Optional | "Business Map": interactive map with Street View, business name, address, Google Business star ratings, reviews, directions link |
| Places API | Optional | Search field inside the map |

Key creation (condensed): set up a Cloud Billing account (Create Account, name, Organization/Country if prompted, payments profile, Submit and enable billing) > Google Maps Platform > Get Started > select billing account / project > answer questionnaire > copy key > Maybe Later. Existing key: Cloud Console > project > APIs overview > Credentials > API key > API restrictions (tick the APIs above) > Application restrictions (add site to HTTP referrers, or server IP to IP addresses) > Save.
- Doc claims Google gives a $200 monthly credit. [Dated: Google replaced the $200 monthly credit with per-SKU free monthly usage caps in March 2025. Check current Maps pricing.] Doc also says Embed API requests are free and unlimited (still true for the Maps Embed API at last check).

Placing the pin:
- Single location: Local SEO > Locations > Map section > "Enter a query" (another page says "Enter a search query") field.
- Multiple: edit the Location post > Map section.

Business Map (Place-based map):
1. Enable Maps Embed API on the key's project.
2. Local SEO > Locations > Map section > enter address in Enter a query.
3. Zoom in until Google's own pin and business name show; click Google's pin. Latitude, Longitude and Place ID display above the map.
4. All maps (shortcode, widget, block, PHP) then render as Business Map.
- Only works for businesses listed in Google Business Profile. Default without this = Normal Map (custom marker plus name/address).

## Local SEO: displaying maps
Sources: https://aioseo.com/docs/displaying-maps-on-your-site/, https://aioseo.com/docs/shortcode-aioseo_local_map/, https://aioseo.com/docs/function-aioseo_local_map/

- Requires a Google Maps API key.
- Widget "AIOSEO Local Map": Title, Location dropdown (Multiple Locations), Show label ("Our location:", editable Label), Show icon, width/height (% or px).
- Block "AIOSEO Local Map": same plus custom map marker that overrides the Local SEO > Maps marker.
- Shortcode `[aioseo_local_map]` (Classic Editor / page builders) and PHP `<?php if( function_exists( 'aioseo_local_map' ) ) aioseo_local_map(); ?>`.

| Shortcode attr | PHP key | Default | Notes |
|---|---|---|---|
| location_id | locationId | (none) | Location post ID when Multiple Locations on; off = map from Local SEO > Locations Business Info |
| show_label | showLabel | true | "Our location:" |
| show_icon | showIcon | true | Map icon beside label |
| width | width | 100% | % or px |
| height | height | 450px | % or px |
| label | label | "Our location:" | Documented for shortcode; PHP list omits it but PHP example passes it |

---

## Breadcrumbs: settings
Sources: https://aioseo.com/docs/displaying-breadcrumbs-on-your-site/ (MODIFIED 2026-08-14)

Location: All in One SEO > General Settings > Breadcrumbs tab. Shows the four display methods, then Breadcrumb Settings with a live Preview.

| Setting | Notes |
|---|---|
| Separator | Pick a character; or Custom Separator field takes an HTML character code |
| Homepage Link | Toggle; shows "Home" first, linked to homepage |
| Homepage label | Changes "Home" text (front end only) |
| Breadcrumb Prefix | Text before the trail, e.g. "Breadcrumb Prefix » Home » ..." |
| Archive Format | Text for post type archive crumbs; smart tags, emoji |
| Search Result Format | Text for search page crumb |
| 404 Error Format | Text for 404 crumb |
| Current Item: Show current item | Shows current page as last crumb |
| Current Item: Link current item | Makes last crumb a link |

Critical gotcha: these settings affect only the visible front-end trail, not the BreadcrumbList schema in source, which follows schema rules. The schema "Home" label is changed only with the PHP filter `aioseo_schema_breadcrumbs_home` (signature not given in the docs).

Per post/term override: edit post or term > AIOSEO Settings > Advanced tab > Breadcrumbs section (preview) > toggle off "Use Default Settings" to reveal the same settings (plus template field in Pro).

## Breadcrumbs: templates (Pro)
Sources: https://aioseo.com/docs/setting-up-and-using-breadcrumbs-templates/

Tier: Pro Basic+. General Settings > Breadcrumbs > Breadcrumb Templates section, tabs per content type, taxonomy and archive; each section has a preview and a "Use a default template" toggle (turn off to edit).
- Show prefix link (only if Breadcrumb Prefix is filled).
- Show homepage link.
- Conditional: Show taxonomy link (post type has taxonomies); Show parent item link (hierarchical types/taxonomies); Show post type archive link (type has archive).
- Template editor: HTML of crumb output with smart tags and emoji.
- Parent item template (hierarchical types).
- Taxonomy priority (which taxonomy is used in the trail).
- Advanced tab: Show Paged Breadcrumb (crumb for page 2+), Paged Format (text); Unselected Taxonomy Terms (include unselected parent category: "Home » Child Cat » Post" vs "Home » Parent Cat » Child Cat » Post").

## Breadcrumbs: primary term (Pro)
Sources: https://aioseo.com/docs/setting-the-primary-term-for-breadcrumbs/

Tier: Pro Basic+. Works for any post type when a post is in more than one term of the same taxonomy.
- Block Editor and Classic Editor: sidebar field "Select Primary Category" appears once 2+ categories are ticked; choose and Update.

## Breadcrumbs: display methods
Sources: https://aioseo.com/docs/displaying-breadcrumbs-on-your-site/, https://aioseo.com/docs/shortcode-aioseo_breadcrumbs/, https://aioseo.com/docs/function-aioseo_breadcrumbs/, https://aioseo.com/docs/adding-breadcrumbs-to-your-site-using-the-aioseo-breadcrumbs-block/

- Shortcode: `[aioseo_breadcrumbs]` (no attributes documented).
- Block: "AIOSEO – Breadcrumbs" (search "AIOSEO" in the inserter). No block settings. Block Editor only; not Classic Editor or page builders.
- Widget: "AIOSEO – Breadcrumbs" in Appearance > Widgets; only an optional Title.
- PHP: `<?php if( function_exists( 'aioseo_breadcrumbs' ) ) aioseo_breadcrumbs(); ?>` in single.php, header.php or other templates; child theme recommended.
  - Exclude homepage: `<?php if( function_exists( 'aioseo_breadcrumbs' ) && ( !is_home() ) ) aioseo_breadcrumbs(); ?>`; if that fails: `... && ( !is_home() && !is_front_page() ) ...`.
  - Doc code example: call `aioseo_breadcrumbs()` in header.php after `wp_body_open()` and before `get_template_part( 'template-parts/header/site-header' )` (Twenty Twenty-One).
  - Timing: function page says it must run after the queried object (post, term or archive) is loaded, else nothing renders. Displaying-breadcrumbs page says it must run inside the WordPress loop. (Conflict: see Open questions. The header.php example is outside the loop, so "after the queried object is loaded" is the accurate rule.)

---

## Social Profiles (Knowledge Panel sameAs)
Sources: https://aioseo.com/docs/displaying-your-social-media-profiles-in-knowledge-panel/, https://aioseo.com/docs/setting-the-content-publisher-for-facebook/, https://aioseo.com/docs/setting-the-content-publisher-for-twitter/

- All in One SEO > Social Networks opens the Social Profiles screen: full URL fields for major networks; site-wide.
- "Use the same username for multiple social networks" checkbox reveals "Your Username" plus network checkboxes; AIOSEO fills the URLs.
- Additional Profiles box (bottom): any other profile URLs (e.g. TikTok, Telegram, Snapchat, Reddit, VK, WeChat, Sina Weibo, Tencent QQ, Kuaishou); included in the Knowledge Panel (Organization/Person sameAs) schema.
- Facebook Page URL field = Facebook publisher (article:publisher).
- Twitter URL field = Twitter Site, output as `twitter:site`.
- Per author: Users > edit user > Social Profiles tab at top of Edit User screen; same fields and same-username helper.
- Search engines decide what to show.

## Facebook / Open Graph: global settings
Sources: https://aioseo.com/docs/beginners-guide-to-social-networks-settings-for-facebook/, https://aioseo.com/docs/setting-a-default-image-for-facebook/, https://aioseo.com/docs/setting-the-object-types-for-facebook/, https://aioseo.com/docs/setting-the-content-author-for-facebook/, https://aioseo.com/docs/adding-your-facebook-admin-id/, https://aioseo.com/docs/adding-your-facebook-app-id/, https://aioseo.com/docs/setting-article-tags-for-facebook/, https://aioseo.com/docs/setting-the-site-name-for-facebook/, https://aioseo.com/docs/setting-facebook-social-meta-for-your-homepage/

Location: All in One SEO > Social Networks > Facebook tab.

| Setting | Section | Notes |
|---|---|---|
| Enable Open Graph Markup | top | Must be on for any OG output |
| Default Post Image Source / Default Term Image Source | General | See image source values below |
| Custom Field (name) | General | Shown when source = Image from Custom Field |
| Default Post Facebook Image / Default Term Facebook Image | General | Fallback image; theme logo used automatically if theme supports a logo |
| Site Name | General | og:site_name; smart tags, # picker, emoji |
| Show Facebook Author | General Facebook Settings | Yes/No |
| Default Post Type Object Types | General Facebook Settings | Dropdown per post type |
| Default Taxonomy Object Types | General Facebook Settings | Dropdown per taxonomy; Pro Basic+ |
| Home Page Settings: Image, Title, Description, Object Type + Preview | Home Page Settings | Used when homepage shows latest posts. AIOSEO recommends Object Type = Website |
| Facebook Admin ID | Advanced Settings (toggle to show) | fb:admins; multiple IDs comma-separated. Find via profile View Page Source, search "USER_ID" |
| Facebook App ID | Advanced Settings | fb:app_id; needed for apps collecting usage data |
| Facebook Author URL | Advanced Settings | Default author profile URL (with Show Facebook Author = Yes) |
| Automatically Generate Article Tags | Advanced Settings | Yes reveals sources: SEO keywords, categories, tags. Outputs article:tag |

Image source values (same list for Facebook and Twitter):
- Default Image (the Default ... Image setting)
- Featured Image
- Attached Image (first attached image)
- First Image in Content
- Image from Custom Field (enter field name)
- Post Author Image (author's profile picture)
- First Available Image (tries each of the above in turn)
- Per-post Image Source dropdown also has Custom Image (reveals upload/library/URL field).

Facebook image specs (docs): preferred 1200 x 630 px; minimum 200 x 200 px; GIF, JPEG, WEBP or PNG; no video or animated images. Troubleshooting page adds: ideal ratio 1.91:1, max 5 MB, examples 1640 x 856 or 3280 x 1712 (retina).

Per-user Facebook URL: Users > edit user > "All in One SEO" section > Facebook field > Update Profile (older wording; see Open questions vs Social Profiles tab).

Homepage set to static page: edit that page > AIOSEO Settings > Social tab > Facebook tab (Title, Description, Image Source, Video URL, Object Type; Preview with desktop/mobile icons). Object Type: AIOSEO recommends Website. Check homepage mode at Settings > Reading > "Your homepage displays".

## Facebook: per-content settings
Sources: https://aioseo.com/docs/configuring-the-facebook-settings-for-your-content/, https://aioseo.com/docs/sharing-content-on-whatsapp/

Applies to Posts, Pages, attachments, CPTs, categories, tags, custom taxonomies. Edit content > Social tab of AIOSEO Settings (one page calls it the "Social Appearance meta box") > Facebook tab.
- Facebook Preview.
- Facebook Title: smart tags (buttons or type #), text, emoji. Empty = SEO Title from General tab.
- Facebook Description: same. Empty = Meta Description from General tab.
- Image Source dropdown (+ Custom Image > Facebook Image).
- Video URL: any video URL as an alternative to an image (og:video).
- Object Type dropdown.
- Article Section (optional; category/categories) and Article Tags (optional; tags).
- WhatsApp uses the Facebook (Open Graph) values; no separate WhatsApp settings.

## X/Twitter cards: global settings
Sources: https://aioseo.com/docs/setting-the-card-type-for-twitter/, https://aioseo.com/docs/setting-a-default-image-for-twitter/, https://aioseo.com/docs/setting-the-content-author-for-twitter/, https://aioseo.com/docs/displaying-additional-data-for-written-by-and-reading-time/, https://aioseo.com/docs/sharing-content-on-slack/

Location: All in One SEO > Social Networks > Twitter tab > Twitter Card Settings.

| Setting | Values / notes |
|---|---|
| Default Card Type | Summary (title, description, thumbnail) or Summary with Large Image (title, description, large image) |
| Default Post Image Source / Default Term Image Source | Same values as Facebook |
| Default Post Twitter Image / Default Term Twitter Image | Fallback; theme logo auto-used if available |
| Show Twitter Author | Yes/No; outputs twitter:creator from the author's Twitter URL |
| Additional Data | Disabled by default. Enabled = outputs "Written by" (author) and "Estimated reading time" tags (used by Slack and others) |

Per-user Twitter URL: Users > edit user > All in One SEO section > Twitter field (older wording).
Twitter image specs (default-image page): min 144 x 144 for Summary, 300 x 157 for Summary Large Image; GIF/JPEG/WEBP/PNG; no video/animated. Troubleshooting page: min 300 x 157, ideal ratio 2:1, max 5 MB.

Per-content (AIOSEO Settings > Social tab > Twitter tab): Twitter Title (empty = Facebook Title if set, else SEO Title), Twitter Description (empty = Facebook Description if set, else Meta Description), Image Source (+ Custom Image > Twitter Image), Card Type.

Slack: uses the Twitter values. AIOSEO recommends Card Type = Summary with Large Image for Slack, and Additional Data = Enabled ("Enhanced Slack Sharing") to show Written by and Estimated reading time.

## Pinterest
Sources: https://aioseo.com/docs/how-to-verify-your-site-with-pinterest/, https://aioseo.com/docs/using-social-meta-for-pinterest-rich-pins/

Verification (HTML tag method; once per site):
1. Pinterest (business account recommended by Pinterest) > Settings > Link to Pinterest (Settings & Support menu, bottom left) > Websites > Claim.
2. Enter site URL, choose Add HTML tag, Copy.
3. WordPress: All in One SEO > General Settings > Webmaster Tools tab > Pinterest Site Verification block > Pinterest Verification Code field > Save Changes.
4. Back in Pinterest: Claim your website. Approval arrives by notification.

Rich Pins: Pinterest reads AIOSEO's Open Graph tags; you must validate/apply with Pinterest first. AIOSEO recommends setting homepage social meta first. (The local copy of this page is very short; details deferred to Pinterest's site.)

## SEO Preview (admin bar)
Sources: https://aioseo.com/docs/checking-your-seo-using-the-seo-preview/

Front end, logged in as Administrator: admin bar SEO > SEO Preview. Tabs:
- Google: snippet preview, mobile/desktop icons, Edit Snippet button. Google may rewrite.
- Facebook: Edit Facebook Meta Data button.
- Twitter (X): Edit X Meta Data button.
- SEO Inspector: all SEO and social meta AIOSEO outputs in source, Focus Keyword, passed/failed TruSEO checks; Edit Post button.

## Emoji picker
Sources: https://aioseo.com/docs/using-the-emojis-in-titles-and-descriptions/

- Emoji icon above Title/Description fields (SEO and social, breadcrumbs formats, templates). Select or search; remove by placing cursor after it and Backspace. [Google may drop emoji from titles/snippets.]

## Deprecated Open Graph settings (v4.0)
Sources: https://aioseo.com/docs/deprecated-opengraph-settings/

Removed when upgrading from pre-4.0:
- Use Content for Autogenerated Descriptions: replaced by using Post Content or Post Excerpt smart tags in Meta Description under Search Appearance > Content Types (applies to SEO and social).
- Run Shortcodes in Description: no longer needed; AIOSEO uses a WP core function to get content.
- Run Shortcodes in Title: removed; rarely used.

## Troubleshooting: Facebook and X sharing
Sources: https://aioseo.com/docs/troubleshooting-problems-with-sharing-content-on-facebook/, https://aioseo.com/docs/troubleshooting-problems-with-sharing-content-on-twitter/

First: deactivate all caching/minification/performance plugins, log in as admin, open the problem URL.

| Symptom | Cause | Fix |
|---|---|---|
| Wrong title/description/image on share | AIOSEO output differs from settings | View Page Source, search `og:` / `twitter:` under the `<!-- All in One SEO x.y.z -->` comment; if values differ from settings, contact AIOSEO support with the URL |
| Duplicate/conflicting tags | Theme or another plugin also outputs OG/Twitter tags | Search source for extra `og:`/`twitter:` blocks; switch theme / deactivate plugins one by one (Health Check & Troubleshooting plugin avoids affecting visitors) |
| Facebook shows old image | Facebook caches scraped data about 7 days | Admin bar SEO > Analyze this page > Facebook Debugger > Fetch new information / Scrape Again (repeat if needed); else wait |
| X shows old image | X caches about 7 days | Download the image, rename, re-upload and set it in AIOSEO; else wait |

Example OG output (from doc): og:site_name, og:type, og:title, og:description, og:url, og:image. Example Twitter output: `twitter:card` (e.g. summary_large_image), `twitter:site`, `twitter:creator`, `twitter:domain`, `twitter:title`, `twitter:description`, `twitter:image` (doc example shows title/description using `property=` and others `name=`).

---

## WooCommerce product shipping and return policy schema
Sources: https://aioseo.com/docs/using-all-in-one-seo-for-woocommerce-product-shipping-and-return-policy-schema/

- **No UI setting.** You add `shippingDetails` and `hasMerchantReturnPolicy` to the WooCommerce Product schema with a PHP filter. Doc PUBLISHED 2025-01-14.
- Steps:
  1. Back up the site.
  2. Install WPCode, then go to Code Snippets » Add Snippet » **Add Your Custom Code (New Snippet)**.
  3. Code Type **PHP Snippet**, paste the code, Insertion **Auto Insert** / **Run Everywhere**, click Save Snippet, toggle it **Active**.
  4. Test the product URL in Google's Rich Results Test.
- Filter: `aioseo_schema_output`. It receives `$graphs` (an array of schema graph arrays) and must return it.
- Helper: `aioseo()->helpers->isWooCommerceActive()`.

```php
add_filter( 'aioseo_schema_output', 'aioseo_add_shipping_details_and_return_policy' );
function aioseo_add_shipping_details_and_return_policy( $graphs ) {
  if ( is_singular( 'product' ) && aioseo()->helpers->isWooCommerceActive() ) {
    foreach ( $graphs as $index => $graph ) {
      if ( 'Product' === $graph['@type'] ) {
        if ( ! isset( $graphs[ $index ]['offers'] ) ) { $graphs[ $index ]['offers'] = []; }
        $graphs[ $index ]['offers']['shippingDetails'] = [
          '@type' => 'OfferShippingDetails',
          'shippingDestination' => [ '@type' => 'DefinedRegion', 'name' => 'Worldwide', 'addressCountry' => 'US' ],
          'deliveryTime' => [
            '@type' => 'ShippingDeliveryTime',
            'handlingTime' => [ '@type' => 'QuantitativeValue', 'minValue' => 1, 'maxValue' => 2, 'unitCode' => 'd' ],
            'transitTime'  => [ '@type' => 'QuantitativeValue', 'minValue' => 3, 'maxValue' => 5, 'unitCode' => 'd' ],
          ],
          'shippingRate' => [ '@type' => 'MonetaryAmount', 'value' => '10.00', 'currency' => 'USD' ],
        ];
        $graphs[ $index ]['offers']['hasMerchantReturnPolicy'] = [
          '@type' => 'MerchantReturnPolicy',
          'returnPolicyCategory' => 'MerchantReturnFiniteReturnWindow',
          'merchantReturnDays' => 30,
          'applicableCountry' => 'US',
          'returnFees' => 'FreeReturn',
          'returnMethod' => 'ReturnByMail',
        ];
      }
    }
  }
  return $graphs;
}
```
- Values to customise:
  - Shipping: `shippingDestination` name and `addressCountry`; handling and transit `minValue`/`maxValue` in days; `shippingRate` `value` and `currency`.
  - Returns: `merchantReturnDays`, `applicableCountry`, `returnFees`, `returnMethod`.
  - The structured data must match the policies stated on the site (consumer-protection note).
- Gotchas [my notes]:
  - The sample hard-codes a single policy for every product.
  - `name: Worldwide` alongside `addressCountry: US` is contradictory.
  - If AIOSEO outputs `offers` as a list or AggregateOffer (variable products), assigning string keys onto it may produce invalid markup. Verify in the Rich Results Test.
  - Since 2024-2025 Google also accepts shipping and return policies at the Organization level (and from Merchant Center), which may be the cleaner option site-wide.
  - Older uses of `'@type' => $graph['@type']` comparisons fail if `@type` is an array.
