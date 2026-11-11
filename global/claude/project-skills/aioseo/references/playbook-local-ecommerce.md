# Playbook: local SEO and WooCommerce/ecommerce SEO

Scope: task-based rules for two kinds of WordPress sites running AIOSEO Elite. Part A covers local businesses: Google Business Profile, NAP and citations, reviews, location pages, local keywords and links, Local Services Ads, local tracking and audits, and niche notes for law, healthcare, dental and restaurant sites. Part B covers WooCommerce stores: keyword split between category and product pages, product pages and variants, Product and Merchant listing structured data, Search Console product report fixes, category pages, faceted navigation, product attributes, stock changes, architecture, images and store audits. The rules merge roughly 120 aioseo.com blog posts (2017 to 2026) and restate them against Google's documentation where the posts are overstated or dated. AIOSEO features are named with a one-line path only; settings screens are documented in `schema-local-social.md`, `settings-search-appearance.md`, `sitemaps-robots-indexing.md` and `redirects-links.md`. Seasonal sale pages (Black Friday URL reuse) are in `playbook-monitoring-growth.md`; crawl, canonical and migration mechanics are in `playbook-technical.md`. Statistics are kept only with their source; "(vendor claim)" marks figures the posts give without a primary source. Menu labels change between plugin versions, so confirm on the live site before quoting a click path.

## Contents

Part A: Local SEO
- A1. How local ranking works (decision rules)
- A2. Google Business Profile: setup and maintenance
- A3. NAP consistency and citations
- A4. Reviews: getting, answering, marking up
- A5. Local structured data and the AIOSEO Local SEO addon
- A6. Location pages, multi-location and service-area businesses
- A7. Local keywords, content and links
- A8. Local Services Ads, Google Guaranteed and Google Screened
- A9. Local tracking, audits and timelines
- A10. Niche notes: law, healthcare, dental, restaurants
- A11. Local SEO scams to refuse

Part B: WooCommerce and ecommerce SEO
- B1. Keyword split: categories, products, content
- B2. Product pages
- B3. Variants and duplicate product content
- B4. Product and Merchant listing structured data
- B5. Fixing Search Console product report errors
- B6. Category pages
- B7. Faceted navigation and filter parameters
- B8. Product attributes and attribute archives
- B9. Out-of-stock, discontinued and seasonal products
- B10. Architecture, breadcrumbs, internal links and on-site search
- B11. Product images at scale
- B12. Affiliate products, non-cart catalogs and platform choice
- B13. Ecommerce SEO audit checklist

---

# Part A: Local SEO

## A1. How local ranking works (decision rules)

- Google documents three local ranking groups: **relevance** (how well the profile matches the query), **distance** (from the searcher or the location in the query) and **prominence** (how well known the business is: reviews, links, articles, directory listings, organic presence). Review count and review score are part of prominence. Plan every local task against these three.
- Distance cannot be optimised. A business will not rank in the Local Pack in a town where it has no address, whatever the website says. Service-area reach comes from relevance and prominence, not from city pages.
- The Local Pack shows three businesses with a map; "Local Finder" (more places) expands it. Directories such as Yelp often hold page-1 organic positions for local queries, so a listing on them is a way onto page 1 even when the site is not (see barnacle SEO in A7).
- Order of operations for a business starting from zero:
  1. Own website (a Facebook page alone is a rented platform with limited control; the posts call organic reach "2-6% of followers" (vendor claim)).
  2. Claim and complete the Google Business Profile.
  3. LocalBusiness structured data and NAP on the site.
  4. Core citations (aggregators, then major directories).
  5. A steady review routine.
  6. Location/service pages with unique content.
  7. Local links and local content.
  8. Track with a grid tool and Search Console.
- Treat these as unconfirmed, and never sell them as ranking levers: responding to reviews, posting on GBP, embedding a Google Map, having a local area code, uploading a set number of photos. All are reasonable for users and conversions. Google has not documented any as a ranking signal.
- NAP consistency helps Google match listings to one entity. Its effect is modest compared with relevance, distance and prominence; fix inconsistencies, but do not expect a ranking jump from citation clean-up alone.
- Survey data the posts cite: the Whitespark Local Search Ranking Factors survey has practitioners rating GBP signals as the most important local factor (an opinion survey, not a measurement; year not given in the posts).

Sources: https://aioseo.com/local-seo/, https://aioseo.com/rank-higher-on-google-maps/, https://aioseo.com/google-maps-seo/, https://aioseo.com/how-to-dominate-local-search-small-business-wordpress-guide/, https://aioseo.com/a-complete-local-seo-checklist/, https://aioseo.com/local-seo-strategy/, https://aioseo.com/facebook-vs-website-which-is-best-for-small-business/, https://aioseo.com/what-is-nap-in-seo/

## A2. Google Business Profile: setup and maintenance

Setup checklist:
1. Search the business name in Google (or Maps). If a profile exists, use "Own this business?" and claim it; otherwise create one. Verification is by postcard, phone, email or video depending on what Google offers; video verification is now common. A pre-opening profile is possible; the posts say "up to a year before launch", but check Google's current opening-date rules before relying on that.
2. **Business name:** the real-world name only. Adding keywords or cities to the name ("Joe's Plumbing Emergency Plumber Denver") breaks Google's guidelines and is a common cause of suspension.
3. **Primary category:** the most specific category that describes the core business (a personal trainer is not "Gym"). Google has about 4,000 categories (vendor claim). Add secondary categories only for services actually offered. Wrong categories are on the posts' list of things that hurt Maps rankings, and category is a documented relevance input.
4. **Address or service area:** service-area businesses with no premises customers visit hide the address and set service areas. Do not use a virtual office or PO box.
5. **Description:** up to 750 characters (Google's limit). Say what the business does, for whom and where, with the main service and city early. No URLs or promotional stuffing.
6. **Services and products:** list each service as its own item. Add products or a menu where the category supports it.
7. **Attributes:** fill every applicable attribute (accessibility, payment, amenities).
8. **Hours:** regular hours plus holiday and special hours. Searchers filter by "open now", so wrong hours lose visits. The claim that "Google penalises conflicting hours" is unconfirmed; keep site, GBP and directories identical anyway (the AIOSEO Opening Hours block helps keep the site copy in sync).
9. **Photos:** exterior, interior, team, work, products. The posts suggest 20-30 at launch and new photos monthly (vendor advice, not a Google threshold).
10. **Links and actions:** website URL (a clean URL or the location page for multi-location businesses), booking, ordering and messaging buttons where relevant.

Maintenance routine (about 15 minutes a month per the posts):
- Add a post or update (offers, events, news). Useful for users; ranking effect unconfirmed.
- Reply to new reviews (A4) and to messages if messaging is on.
- Check for suggested edits from users or Google and reject wrong ones.
- Update hours before holidays.
- Q&A: older posts tell you to seed and answer questions. Google has been changing or removing the Q&A feature, so check whether it exists for the profile before advising on it.
- Use the GBP Performance data (searches, calls, direction requests, website clicks) and the search-terms list for keyword ideas.

Facts that changed:
- GBP websites (Google's free site builder) shut down in March 2024; they redirected to the profile until 10 June 2024 and then returned 404. The profile itself was unaffected. If a business used one, it needs its own site and the GBP website field updated.
- "Google My Business" is the old name. Use "Google Business Profile".

AIOSEO: none of this happens in the plugin. The plugin's job is the site side: LocalBusiness data, hours and map blocks (A5).

Sources: https://aioseo.com/how-to-use-a-google-business-profile-to-imrpove-local-seo/, https://aioseo.com/rank-higher-on-google-maps/, https://aioseo.com/local-seo-tips/, https://aioseo.com/google-maps-seo/, https://aioseo.com/restaurant-seo/, https://aioseo.com/alternatives-to-googles-website-builder/, https://aioseo.com/a-complete-local-seo-checklist/

## A3. NAP consistency and citations

NAP rules:
- NAP = business name, address, phone. Treat hours, website URL and email as part of the same record.
- Write a **master NAP document** and copy from it everywhere: exact spelling, "St." vs "Street", "Suite 200" vs "#200", phone format. Small legal suffix differences ("LLC") are not worth chasing (vendor view).
- Show NAP as crawlable text (not an image) in the site footer and on the contact page, and on each location page for multi-location businesses.
- Use the main local number as the NAP phone. If call tracking is needed, keep the main number as the primary and the tracking number as an additional number where the platform allows.
- When anything changes (move, new number, rebrand), update GBP first, then the aggregators, then the directories, then the site.
- Find and merge or remove duplicate listings; duplicates split reviews and confuse matching.

Citation plan:
1. **Data aggregators first:** they feed many downstream directories and in-car GPS systems. The posts name Data Axle, Neustar Localeze, Foursquare and GPS Network, and recommend 1-4 aggregators.
2. **Major directories:** Bing Places, Apple Business Connect, Yelp, Facebook, YellowPages, BBB, Angi, Thumbtack, chamber of commerce.
3. **Industry and local directories:** for example Healthgrades, Zocdoc and the ADA directory for dentists; TripAdvisor, OpenTable and Resy for restaurants; bar association directories for lawyers.
4. Keep a spreadsheet of every listing, its login and its status.
5. Target roughly 25 good listings (vendor figure), quality over count.

Budgets the posts quote (BrightLocal-affiliated pricing, likely stale): about $75-80 for 25 citations via BrightLocal Citation Builder, $25-85 per aggregator, about $15 to correct an existing listing; use "Start Campaign" rather than "Buy Credits" packages of $1,000+. Whitespark offers similar services. Citations are a one-time job plus updates when details change; recurring "citation management" fees are rarely justified.

What citations are and are not:
- Most directory links are nofollow. Citations are for entity matching, reputation and referral traffic, not link building.
- The vendor anecdote that a single Neustar listing moved a Manhattan client "up many notches" is an anecdote, not evidence.
- Stats cited: BrightLocal research that 39% of consumers would choose another business if they found the wrong address; Neustar's estimate of about $10B in annual sales lost to inaccurate listings (both cited by the vendor, years not given).

AIOSEO: AIOSEO > Local SEO holds the site's NAP (business info) and outputs it in LocalBusiness markup and the Local Business Info block.

Sources: https://aioseo.com/what-is-nap-in-seo/, https://aioseo.com/how-to-get-local-seo-citations/, https://aioseo.com/local-seo-strategy/, https://aioseo.com/a-complete-local-seo-checklist/, https://aioseo.com/best-local-seo-tools/, https://aioseo.com/how-to-dominate-local-search-small-business-wordpress-guide/, https://aioseo.com/small-business-seo-scams-how-to-detect-and-avoid-them/

## A4. Reviews: getting, answering, marking up

Getting reviews:
- Ask every customer, steadily. Recency matters to buyers, and a burst followed by silence looks odd.
- Channels: verbal ask at the end of the job, an email about 24 hours after purchase or service, SMS, a QR code on receipts or the counter, window stickers and cards from Google's free marketing kit.
- Get the direct review link from the profile (search the business while logged in, then "Ask for reviews" or "Get more reviews"; the UI moves, so look for the share option in the profile manager).
- Allowed: asking everyone. Not allowed by Google's policy: paying or rewarding reviews (including giveaway entries, discounts or freebies), reviewing your own business, buying reviews, or "review gating" (asking only happy customers, or filtering unhappy ones away from Google). Fake reviews put the profile at risk.
- Yelp prohibits soliciting reviews at all. Do not run a "review us on Yelp" campaign; let Yelp reviews arrive organically.
- Report fake or competitor reviews through the profile; do not retaliate.

Answering reviews:
- Reply to every review, positive and negative, within a few days. Use a short template for thanks and a measured routine for complaints (acknowledge, take it offline, fix, follow up).
- Google says a mix of positive and negative reviews reads as more trustworthy; do not panic about a 4.6 average.
- Responding is good customer service. "Responding is a confirmed ranking signal" (restaurant post) is not confirmed by Google.
- A realistic goal from the posts: raise the average by about half a star over a year through volume (vendor goal, not a benchmark).

Survey figures cited (BrightLocal Local Consumer Review Survey, years not given in the posts): about 98% of consumers read online reviews; 85% say the average star rating matters; 76% compare businesses by rating; 73% are swayed most by recent reviews. Semrush research (vendor-cited, undated) found review quantity mattered more than rating once the average was at least 4.1. A Harvard Business School study (Luca, 2011) is cited for a 5-9% revenue change per one-star Yelp rating move.

Marking up reviews (where the posts mislead):
- Google stopped showing review snippets for **self-serving reviews** in September 2019: a LocalBusiness or Organization page marking up reviews of itself is not eligible, whether the reviews were collected on site or copied from Google or Yelp.
- Do not copy Google or Yelp reviews into Review or AggregateRating markup (the barnacle SEO post suggests this). It is not eligible and copying third-party reviews can breach those platforms' terms.
- Showing testimonials as visible content on the site is fine and helps conversion. Just do not expect stars in search for them.
- Product review markup on product pages is a different case (B4).

Sources: https://aioseo.com/how-to-manage-google-reviews-for-improved-seo/, https://aioseo.com/local-seo-strategy/, https://aioseo.com/restaurant-seo/, https://aioseo.com/rank-higher-on-google-maps/, https://aioseo.com/a-complete-local-seo-checklist/, https://aioseo.com/benefits-of-local-seo/, https://aioseo.com/how-to-use-barnacle-seo/, https://aioseo.com/seo-tips-small-businesses/

## A5. Local structured data and the AIOSEO Local SEO addon

What to do:
- Output one accurate LocalBusiness (or the most specific subtype: Restaurant, Dentist, LegalService, and so on) per real location, with name, address, phone, URL, geo coordinates, opening hours, price range and accepted payments where known. The data must match the GBP and the visible page.
- Organization data (logo, social profiles via sameAs) comes from the Knowledge Graph settings, not the local addon.
- LocalBusiness markup is not a ranking factor and does not create a Local Pack listing; the GBP does that. It helps Google understand and match the entity.
- Validate with the Rich Results Test or the Schema Markup Validator, and by viewing source and searching for `"@type"`.

AIOSEO paths (one line each; details in `schema-local-social.md`):
- Business info, hours, maps: **AIOSEO > Local SEO** (tabs Locations, Opening Hours, Maps, Import). Tier: "Plus and above" in 2026 posts; older posts say Pro.
- Several offices: **AIOSEO > Local SEO > Locations > Multiple Locations** toggle, which creates a Locations post type with per-location data.
- Business type and subtype: chosen in the Local SEO business info; types the catalog lacks (LegalService on a law firm) go in **AIOSEO Settings > Schema > Custom Schema**.
- Site display: blocks "AIOSEO Local - Business Info", "AIOSEO Local - Map" and the Opening Hours block, or the shortcode/widget/PHP equivalents.
- Map embed: the Maps tab needs your own Google Maps API key with Cloud Billing enabled. Restrict the key to your domain and the Maps APIs right after creating it.

Caveats:
- One post states AIOSEO outputs LocalBusiness and Opening Hours markup **on the homepage only** for a single-location setup. Google accepts LocalBusiness markup on the page that represents the location (often a contact or location page), and multi-location sites normally want it on each location page. Check what the plugin actually emits on Location posts (view source on a location URL) before telling a client the markup is per location.
- An embedded map is a convenience for visitors. The posts say it does not boost SEO, which matches Google's silence on it.
- Restaurant post: verify that the Restaurant JSON-LD appears in the homepage `<head>` after setup.

Sources: https://aioseo.com/how-to-add-local-business-schema-in-wordpress/, https://aioseo.com/local-seo/, https://aioseo.com/local-seo-tips/, https://aioseo.com/how-to-embed-google-maps-in-wordpress/, https://aioseo.com/restaurant-seo/, https://aioseo.com/law-firm-seo/, https://aioseo.com/diy-seo-projects-for-beginners/

## A6. Location pages, multi-location and service-area businesses

Decision rules:
- **One page per real location** (office, clinic, store), each with its own GBP. Content that only that page can have: address and NAP, map and directions, parking and access, staff or providers at that site, services offered there, opening hours, local photos, testimonials from that location's customers, local landmarks.
- **Service-area pages** are justified only where the business genuinely serves the area and has something specific to say (projects done there, local regulations, response times, area-specific pricing). Fifteen city pages that share the same 200 words with the city name swapped is the posts' own example of scaled content abuse, and it is also a doorway-page pattern under Google's spam policies.
- Do not run two near-identical websites for one location to occupy more of page 1 (the krav maga example in one post). That is a spam-policy risk, not a tactic.
- Link the GBP website field of each location to that location's page, not the homepage, when location pages exist.
- Keep location pages within a few clicks of the homepage (a locations index page, footer links) so they are crawled and not orphaned.

AIOSEO: the Multiple Locations toggle (A5) gives each location its own post with data and blocks; Link Assistant > Orphaned Posts finds location pages nothing links to.

Sources: https://aioseo.com/local-seo-strategy/, https://aioseo.com/healthcare-seo/, https://aioseo.com/keyword-research-tips-small-businesses/, https://aioseo.com/ai-generated-content/, https://aioseo.com/how-to-dominate-local-search-small-business-wordpress-guide/, https://aioseo.com/how-to-add-local-business-schema-in-wordpress/

## A7. Local keywords, content and links

Keywords:
- Patterns: service + city, service + neighbourhood or landmark, "best [service] in [city]", "[service] near me", urgency modifiers (emergency, same day, 24 hour), transaction modifiers (book, quote, price, cost). Long-tail beats head terms: "emergency hot water heater repair Denver" over "plumber".
- Restaurant patterns: cuisine + city, dish + neighbourhood, occasion + location ("birthday dinner downtown"), modifier + "near me", landmark + restaurants.
- Free sources: Google autocomplete, People Also Ask, Keyword Planner, Maps category suggestions, the GBP search-terms report, customer emails and calls.
- Prioritise terms where real local competitors rank, not only directories; a SERP full of directories means you also need directory listings.
- Title pattern for a local page: main service + city + brand, for example "Emergency Plumber in Chicago | SpeedyFix". Meta description: what you do, for whom, where, plus one credibility point.
- AIOSEO: set the focus keyphrase per page in **AIOSEO Settings > General**; TruSEO checks placement, but its placement checks are plugin heuristics, not Google requirements.

Content:
- Location pages (A6), service pages (one per service), neighbourhood guides, local event or sponsorship write-ups, answers to the five questions customers ask most.
- Conversational question content is fine for users and assistants; there is no separate "voice search" ranking system to optimise for, and the voice statistics in older posts (2017-2021) are dated.

Local links and mentions:
- Sponsorships of local teams and events, chamber of commerce and business associations, local schools and universities (scholarships only if genuine), local press and podcasts, supplier and partner pages, local resource pages, unlinked mentions found with Google Alerts (`"Brand" -site:yourdomain.com`).
- **Barnacle SEO:** complete strong profiles on platforms that already rank for your terms (GBP, Yelp, TripAdvisor, Angi, industry directories). The benefit is extra page-1 presence and referral traffic; profile links are mostly nofollow and do not build authority.
- Avoid link exchanges with "non-competing local businesses" at scale and any paid link without `rel="sponsored"`; both fall under Google's link spam policy.

Sources: https://aioseo.com/keyword-research-tips-small-businesses/, https://aioseo.com/local-seo-tips/, https://aioseo.com/restaurant-seo/, https://aioseo.com/local-seo/, https://aioseo.com/how-to-use-barnacle-seo/, https://aioseo.com/google-alerts-for-seo/, https://aioseo.com/guide-to-voice-search/, https://aioseo.com/how-to-use-a-serp-snippet-tool/

## A8. Local Services Ads, Google Guaranteed and Google Screened

- Local Services Ads (LSA) are pay-per-lead (not per click), appear above the Local Pack for eligible categories, and need no website. Google runs background checks on owners and field workers and, for some categories, licence checks.
- **Google Guaranteed** (home services) adds a reimbursement promise; the 2023 posts give a US lifetime cap of $2,000. **Google Screened** is the badge for licensed professions (law, real estate, financial and similar).
- Eligible categories in the 2023 posts include plumbing, electrical, HVAC, pest control, law, real estate, dentistry, tax services and tutoring. Categories, caps and countries change; check Google's current LSA pages before quoting.
- Practical rules from the posts: budget for roughly 10 leads a week to get enough data (vendor advice); dispute irrelevant leads (reviewed within about a week); answer calls fast because responsiveness affects LSA placement.
- LSA can bridge the gap while a new site and GBP gain traction. Paying for any Google ads does not improve organic or Local Pack rankings.

Sources: https://aioseo.com/what-are-local-services-ads/, https://aioseo.com/what-is-the-google-guaranteed-badge-for-local-businesses/, https://aioseo.com/how-to-dominate-local-search-small-business-wordpress-guide/, https://aioseo.com/law-firm-seo/, https://aioseo.com/a-complete-local-seo-checklist/

## A9. Local tracking, audits and timelines

Tracking:
- Local rank depends on the searcher's location, so a desk check in Chrome Incognito is misleading. Use a grid tool (BrightLocal Local Search Grid, Semrush local heatmaps, Whitespark rank tracker) that samples rank across a map.
- Measure outcomes: GBP Performance (calls, direction requests, website clicks), organic clicks per location page, tracked keywords, form submissions and calls from the site.
- AIOSEO: **Search Statistics** (Elite) for location-page clicks, impressions and keyword positions; these are Google Search Console averages, not grid positions.
- Judge on quarterly trends. If nothing moves after 3-4 months, re-check GBP completeness, categories and NAP consistency before anything else.

Local audit checklist:
1. GBP: verified, correct primary and secondary categories, real name, hours incl. holidays, services, attributes, photos, no duplicates, website link points to the right page.
2. NAP: identical on site, GBP, aggregators and the top directories; duplicates removed.
3. Reviews: count, recency, average, reply rate, any policy-breaking solicitation.
4. Site: one page per location or service with unique content; NAP in text; `tel:` links; LocalBusiness markup present and matching (view source); HTTPS; mobile layout with tap-friendly Call and Directions buttons; Core Web Vitals (LCP within 2.5 s, INP under 200 ms, CLS under 0.1); no stray noindex after a redesign.
5. AIOSEO: **AIOSEO > SEO Analysis** homepage audit, fix red items first; Search Statistics for slipping location pages.
6. Competitors: who holds the Local Pack in a grid, their categories, review counts and directory presence.

Timelines the posts give (vendor claims, keyword-dependent): first visible local movement in 3-6 months; GBP-driven gains for a restaurant in 4-8 weeks; competitive metro areas 6-12 months.

Sources: https://aioseo.com/local-seo-audit/, https://aioseo.com/local-seo-tips/, https://aioseo.com/local-seo-strategy/, https://aioseo.com/how-to-check-seo-rankings/, https://aioseo.com/rank-higher-on-google-maps/, https://aioseo.com/law-firm-seo/, https://aioseo.com/restaurant-seo/, https://aioseo.com/mobile-seo/

## A10. Niche notes: law, healthcare, dental, restaurants

Law firms:
- One page per practice area, one primary keyword each. Page structure: who you are, how the process works, who it is for, a clear call to action.
- Meta description: what you do + for whom + one credibility signal.
- Follow your state bar's advertising rules: no guarantees of outcomes, no unverifiable superlatives, no misleading results.
- Individual attorney bio pages with credentials, linked to the bar directory or LinkedIn for outside verification. Every legal article names the writer or reviewer and their credentials (YMYL).
- LegalService markup as custom schema on top of the LocalBusiness data.
- After a redesign, check HTTPS, mobile, speed, sitemap and that no noindex was left on.

Healthcare clinics:
- Credentialed author or medical reviewer on every informational page (AIOSEO Author SEO reviewer byline).
- No dosage advice or diagnostic statements; plain language; structure each condition or service page as what it is, who it is for, what to expect, when to seek care.
- An SEO score is not an accuracy score; every page needs editorial and clinical review. Expect results over months.
- Multi-location practices: one page per location with its providers, directions, parking and testimonials, each with its own GBP. Directories: Healthgrades, Zocdoc.

Dentists:
- One page per service (implants, whitening, emergency dentistry) with an FAQ section per service for patients (no FAQ rich result is available, see B4), YMYL accuracy, ADA directory and dental directories as citations.

Restaurants:
- Menu as HTML text, not a PDF or image. Reservation or order button above the fold. `tel:` link for calls.
- Directories: Yelp, TripAdvisor, OpenTable, Resy, Apple Business Connect, Bing Places, Facebook.
- Restaurant markup from the Local SEO addon; confirm it in the homepage source.
- AggregateRating for the restaurant itself is self-serving (A4) and will not show stars.
- The restaurant post's claims that Google "Ask Maps" weighs review wording and that public Instagram content is indexed from July 2025 are vendor claims; verify before acting on them.

Sources: https://aioseo.com/law-firm-seo/, https://aioseo.com/healthcare-seo/, https://aioseo.com/seo-for-dentists/, https://aioseo.com/restaurant-seo/, https://aioseo.com/how-to-boost-your-author-seo-in-wordpress/, https://aioseo.com/eeat-and-ymyl/

## A11. Local SEO scams to refuse

Refuse, and warn the client about:
- Calls or emails claiming to be "from Google" about NAP errors or a profile about to be suspended. Google does not cold-call for this.
- Guaranteed page-1 or Local Pack rankings.
- Monthly "citation management" fees for listings that only need updating when details change.
- Lists of "high-DA" links for sale, free guest posts with hidden private-network links, fake traffic.
- Fake Lighthouse or PageSpeed reports (re-run the URL in PageSpeed Insights yourself).
- Copy-paste "detailed audits" from free email addresses, recurring fees for work nobody can show.
- Fake reviews, review gating services, keyword-stuffed business names.

Sources: https://aioseo.com/small-business-seo-scams-how-to-detect-and-avoid-them/, https://aioseo.com/how-to-get-local-seo-citations/, https://aioseo.com/what-is-nap-in-seo/, https://aioseo.com/google-maps-seo/

---

# Part B: WooCommerce and ecommerce SEO

## B1. Keyword split: categories, products, content

Decision rules:
- **Category pages** target broader commercial terms ("women's cotton t-shirts").
- **Product pages** target specific long-tail and model terms ("women's blue cotton crew-neck t-shirt", brand + model number).
- **Blog and buying guides** target informational and comparison queries ("how to choose a running shoe for flat feet", "X vs Y") and link to categories and products.
- Never let a category and a product (or two categories) compete for the same keyword. Keep a keyword map: one primary keyword per URL (see `playbook-keywords-content.md`).
- Prioritise terms with clear buyer intent and real volume. New stores start with low-difficulty long-tail terms and move up as the site earns links and reviews.
- Sources of variants: autocomplete, People Also Ask, Search Console queries (AIOSEO **Search Statistics > Keyword Rank Tracker**, related keywords), competitor gaps (Semrush Keyword Gap, Ahrefs Content Gap) filtered to commercial and transactional intent.
- Check the SERP before assigning: if Google shows category-style listings for a term, a single product page will struggle, and the reverse.

Sources: https://aioseo.com/ecommerce-seo/, https://aioseo.com/ecommerce-seo-strategy/, https://aioseo.com/category-page-seo-for-woocommerce/, https://aioseo.com/ecommerce-seo-vs-normal-seo/, https://aioseo.com/woocommerce-seo-guide/, https://aioseo.com/keyword-gap-analysis/

## B2. Product pages

Checklist:
1. **H1** = the product name (WooCommerce does this by default). The **SEO title** can differ: product name + key attribute or differentiator + brand, front-loaded so it reads well when Google truncates or rewrites it. Set it in **AIOSEO Settings > General** on the product, or with smart-tag templates in **Search Appearance > Content Types > Products** for large catalogs (product attribute tags exist).
2. **Meta description:** what it is, the main benefit, a reason to buy (shipping, returns, warranty). Not a ranking factor; Google may replace it with page text.
3. **Description:** original copy written for buyers: specs, sizes, materials, use cases, care, compatibility, what is in the box. Do not paste the manufacturer's text. Manufacturer copy does not trigger a penalty, but it gives Google no reason to rank your page over every other store using the same words. Put the main product term early because it helps readers, not to hit a placement rule.
4. **Slug:** short and descriptive (`/product/blue-cotton-crew-tee/`). If a live product's slug changes, add a 301 (AIOSEO **URL Slug Monitor** prompts for it; **Redirects** for manual ones).
5. **Images:** see B11.
6. **Reviews:** show genuine customer reviews on the page; WooCommerce reviews feed the Product markup (B4).
7. **Shipping, returns and guarantees** visible near the buy button; these also feed Merchant listing data.
8. **Internal links:** from the category, related products, buying guides and blog posts.
9. **Breadcrumbs** with the correct primary category (B10).
10. Start with the highest-revenue or highest-margin products, then work down.
- AIOSEO: the TruSEO checklist runs in the product's AIOSEO Settings. Its keyphrase placement and density checks are heuristics; skip any that make the copy worse.
- Keep FAQ sections on product pages only if they answer real pre-sale questions. They no longer earn a rich result (B4).

Sources: https://aioseo.com/product-page-seo/, https://aioseo.com/ecommerce-seo/, https://aioseo.com/ecommerce-seo-checklist/, https://aioseo.com/woocommerce-seo-guide/, https://aioseo.com/ecommerce-seo-strategy/, https://aioseo.com/rank-math-review/

## B3. Variants and duplicate product content

- Duplicate content in a store (shared descriptions, the same product in two categories, sort and filter URLs) is not a penalty. Google picks one URL as canonical and filters the rest; Google's "duplicate content penalty" article says so. The real costs are diluted signals, wasted crawling on very large catalogs, and the wrong URL being shown.
- **Variants** (size, colour): keep one product URL with variant selection, and let the variations share that canonical. Give a variant its own indexable URL only when it has distinct search demand and its own copy and images.
- Google supports variant markup (ProductGroup with `hasVariant`/`variesBy`, introduced February 2024). Check whether the installed AIOSEO version outputs it before promising variant-level results; the blog posts do not mention it.
- Variation duplicates are a common reason products show as "Duplicate without user-selected canonical" or are not indexed. Fix with consistent internal links to the main URL and a canonical.
- AIOSEO outputs a self-referencing canonical on products by default; override per URL in **AIOSEO Settings > Advanced > Canonical URL**.
- The same product listed under several category paths: use a permalink structure without the category in product URLs, or a single primary category, so one URL exists.

Sources: https://aioseo.com/product-page-seo/, https://aioseo.com/best-woocommerce-seo-plugins/, https://aioseo.com/canonical-tags/, https://aioseo.com/duplicate-content/, https://aioseo.com/ecommerce-seo/

## B4. Product and Merchant listing structured data

Two Google experiences, two property sets:
- **Product snippets** (stars, price, availability under a normal result) need Product with `offers`, `review` or `aggregateRating`.
- **Merchant listings** (shopping-style results, the Shopping tab and free listings without a feed) need Product with `offers` and add shipping details, return policy, identifiers (GTIN, MPN, brand) and attributes (colour, size, material, pattern, energy rating).
- Google also accepts store-wide return and shipping policies at the Organization level; check what AIOSEO emits and avoid conflicting per-product values.
- Markup must match the visible page and, if you use Merchant Center, the feed: same price, currency, availability, shipping cost. Mismatches cause disapprovals and lost rich results.
- Structured data is not a ranking factor and rich results are never guaranteed; Google decides per query and device.

Field checklist per product: name, description, images, brand, SKU, GTIN/MPN/ISBN where they exist, price, currency, availability (InStock, OutOfStock, BackOrder, PreOrder), `priceValidUntil` for sale prices (recommended, not required; it clears a warning), item condition, shipping destinations and rates for every region you ship to, return policy, aggregate rating and reviews from real customers.

AIOSEO paths (details in `schema-local-social.md`):
- Store default: **Search Appearance > Content Types > Products > Schema Markup** = Product.
- Per product: **AIOSEO Settings > Schema > Generate Schema > Product** (or the pencil on the existing Product entry); WooCommerce price, availability, reviews and WooCommerce shipping (since AIOSEO 4.2.7) are read automatically, so the form shows only missing fields such as identifier type, identifier and brand.
- Reuse: **Save Schema as Template** for products that share fields.
- Validate: the Schema tab's **Validate Schema / Test with Google** button opens the Rich Results Test; also the Schema Markup Validator and the Search Console Product snippets and Merchant listings reports.
- No Merchant Center account is needed for the markup. Merchant Center itself is free and adds Shopping feeds and local inventory ads.

Review markup rules:
- Product reviews must be genuine reviews of that product by customers. Do not hand-enter reviews copied from other platforms, invent ratings, or mark up reviews of the store itself (self-serving, see A4).
- One post's FAQ ("Can I use product review schema for my own reviews? Yes") is risky. An editorial review of a product you sell, written by the store, is not an independent review.

Not worth adding for SERP gains:
- FAQPage on product or category pages: FAQ rich results were limited to authoritative government and health sites from August 2023 and stopped showing for all sites on 7 May 2026. AIOSEO's AI Content "FAQ with schema" output is harmless markup but earns no SERP feature.
- HowTo: rich results removed in 2023.
- Several posts promise CTR gains from rich results using vendor figures (for example "rich results get 58% of clicks vs 41%", "FAQ rich results 87% CTR" attributed to Milestone Research). Treat these as unverified (vendor claim).

Sources: https://aioseo.com/product-schema-markup/, https://aioseo.com/schema-types-to-boost-ecommerce/, https://aioseo.com/how-to-add-product-schema/, https://aioseo.com/how-to-add-google-merchant-center-listing-schema-to-wordpress/, https://aioseo.com/how-to-add-product-review-schema-in-wordpress/, https://aioseo.com/how-to-add-product-rich-snippets-in-wordpress/, https://aioseo.com/what-is-google-merchant-center-and-how-you-can-use-it-to-drive-sales/, https://aioseo.com/how-to-add-ecommerce-product-attributes/

## B5. Fixing Search Console product report errors

Workflow:
1. Open Search Console > Shopping (or Enhancements) > Product snippets and Merchant listings. Note each error and its example URLs.
2. Open an affected product in WordPress > **AIOSEO Settings > Schema** > edit the Product entry.
3. Fix by error:
   - "Either 'offers', 'review' or 'aggregateRating' should be specified": the product has no price/offer in the markup or no reviews. Fill price, currency and availability; make sure WooCommerce reviews are enabled and pulled in.
   - Missing `priceValidUntil` (warning): add the sale end date when a sale price is set; ignore it for regular prices if you prefer.
   - Missing brand, GTIN or MPN (warnings): add identifiers where the product has them; do not invent GTINs.
   - Missing `shippingDetails` or `hasMerchantReturnPolicy` (Merchant listings warnings): add shipping destinations for every region and the return policy, matching the visible policy page.
   - Invalid price or currency: check WooCommerce price display settings and tax-inclusive settings against the markup.
4. Re-test the URL in the Rich Results Test, then click **Validate fix** in Search Console.
5. For catalog-wide gaps, fix the template or the store default rather than product by product.

Sources: https://aioseo.com/how-to-fix-missing-schema-properties-for-woocommerce-products/, https://aioseo.com/product-schema-markup/, https://aioseo.com/how-to-add-product-schema/, https://aioseo.com/how-to-add-google-merchant-center-listing-schema-to-wordpress/

## B6. Category pages

Checklist (from the 2026 WooCommerce category post, corrected where needed):
1. **Category description:** a short, useful introduction for buyers (what the range covers, how to choose, key differences, links to sub-categories and guides). The post's author prefers 100-200 words; that is a preference, not a target, and the same post says there is no ideal word count. The text must be visible to users; if the theme hides category descriptions entirely, fix the theme rather than relying on hidden text.
2. **SEO title and description:** bulk templates in **Search Appearance > Taxonomies > Product Categories** (smart tags for category name and site name), then hand-written overrides for the top categories on the term's own AIOSEO settings.
3. **H1:** the theme should print the category name as the H1. Avoid generic H1s such as "Shop" or "Products".
4. **Sitemap:** product categories are in the AIOSEO sitemap by default; confirm the taxonomy is included and indexable in Search Appearance.
5. **Images:** banners compressed, descriptive filenames and alt text.
6. **Pagination:** AIOSEO adds "Page N" to paginated titles and descriptions (**Search Appearance > Advanced > Paged Format**). Each paginated page should self-canonicalise; do not canonicalise page 2+ to page 1, because that hides products linked only from deeper pages. Google stopped using `rel=prev/next` in 2019. Leave **Global Robots Meta > No Index Paginated** off unless deeper pages have no unique products and products are reachable another way.
7. **Filters and sorting:** see B7.
8. **Internal links:** products link back to their category; guides link to categories with descriptive anchors; check orphans with **Link Assistant > Orphaned Posts**.
9. **Breadcrumbs:** enabled and showing the primary category (B10).
10. **Monitor:** **Search Statistics** (Elite). High impressions with low CTR: rewrite the title and description. Page-2 positions: strengthen content and internal links.

Index decision: index categories with real search demand and enough products. Thin or near-empty categories either get merged, filled, or noindexed. Older posts tell you to noindex all categories and tags "to prioritise commercial pages"; that is wrong for stores, where product categories are often the best-ranking pages. Decide per taxonomy and per term.

Sources: https://aioseo.com/category-page-seo-for-woocommerce/, https://aioseo.com/pagination-seo/, https://aioseo.com/the-difference-between-tags-and-categories/, https://aioseo.com/ecommerce-seo-checklist/, https://aioseo.com/ecommerce-seo/

## B7. Faceted navigation and filter parameters

Google's December 2024 guidance on faceted navigation is the reference. Decide per facet:

- **Facets you do not want in search** (sort order, price slider ranges, multi-select combinations, view mode, session IDs, tracking parameters): prevent crawling. Options in Google's order of preference: block the parameter patterns in robots.txt, or make the filter state a URL fragment (`#`) or a non-link control. `rel=canonical` and `nofollow` are weaker: Google still has to crawl the URL to see a canonical.
- **Facets with real search demand** ("red dresses", "waterproof hiking boots"): give them a proper, linked, indexable URL, ideally a sub-category or a curated landing page with its own title, description and copy.
- If facet URLs stay crawlable: keep a consistent parameter order, use standard `&` separators, return 404 for empty or nonsensical combinations instead of an empty 200 page, and do not redirect them all to the base category.
- Do not combine a robots.txt block with a noindex or canonical on the same URLs; a blocked URL's tags are never seen. Blocked URLs can still be indexed (without content) if linked from elsewhere, so robots.txt is crawl control, not de-indexing.
- Crawl budget matters for large catalogs; Google's crawl-budget guide targets sites with about a million pages, or 10,000+ pages changing daily, and faceted navigation is the usual way stores reach that scale.

AIOSEO paths:
- **Search Appearance > Advanced > Crawl Cleanup > Query Arg Monitoring**: logs parameters; **Block Key** or **Block Key & Value** writes robots.txt rules. Expect weeks to months before Search Console reflects the change.
- Per-URL canonical to the base category: **AIOSEO Settings > Advanced > Canonical URL** (fine for a few URLs, not for thousands).
- Robots rules by hand: **Tools > Robots.txt Editor** (Google ignores `Crawl-delay`; `Clean-param` is a Yandex directive).
- Spot check with `site:store.com/product-category/x` and the Search Console Pages report ("Crawled, currently not indexed" on parameter URLs is normal and harmless if they are blocked or canonicalised).
- Google's URL Parameters tool was removed in 2022; parameter handling now lives entirely on your site.

Sources: https://aioseo.com/category-page-seo-for-woocommerce/, https://aioseo.com/what-is-a-url-parameter/, https://aioseo.com/query-arg-crawling-in-wordpress/, https://aioseo.com/how-to-delete-url-parameters-from-google-search-console/, https://aioseo.com/crawl-budget/, https://aioseo.com/ecommerce-seo/

## B8. Product attributes and attribute archives

- Attribute types: physical (size, weight, material), functional (compatibility, specs), emotional (eco-friendly, handcrafted). Use specific names customers search ("Cherry Red", "washable 5x7 rug") rather than internal codes.
- Attributes belong in the product copy, the Merchant listing markup (B4) and, where useful, the SEO title via smart tags.
- **Attribute archives** (WooCommerce **Products > Attributes > Enable Archives**) create URLs such as `/color/red/`. Index one only where it has search demand, enough products and something to say; noindex the rest. Noindexed archives should not be in the sitemap.
- AIOSEO paths:
  - **Search Appearance > Taxonomies > Product Attributes**: index or noindex, title and description templates; indexed attribute archives go into the XML sitemap.
  - Attributes in search snippets: **Tools > Code Snippets > "Enable WooCommerce Product Attributes in Search Appearance"** (needs the free WPCode plugin), then Use Snippet > Active > Update.
  - Copy the setup to another store: **Tools > Import/Export**.
- Show attribute values in visible tables on the product page; markup should never carry attributes the page does not show.

Sources: https://aioseo.com/product-attributes/, https://aioseo.com/how-to-enable-woocommerce-product-attributes-in-search-results/, https://aioseo.com/how-to-add-ecommerce-product-attributes/, https://aioseo.com/rank-math-review/

## B9. Out-of-stock, discontinued and seasonal products

Decision table:

| Situation | Action | Why |
|---|---|---|
| Temporarily out of stock | Keep the page live (200), set availability OutOfStock (or BackOrder/PreOrder) in WooCommerce so the markup follows, show a restock date, back-in-stock signup and alternatives | The URL keeps its signals and comes back when stock returns; Google can show the availability |
| Discontinued, close replacement exists | 301 to the replacement product | Users and links land on the nearest equivalent |
| Discontinued, no replacement, page has links or traffic | Keep the page with a clear "discontinued" note and links to alternatives or the category, or 301 to the most relevant category | Preserves value without a misleading redirect |
| Discontinued, no replacement, no links or traffic | 404 or 410 | Normal; Google treats 404 and 410 almost the same (410 may drop slightly faster) |
| Many products gone at once (range dropped) | Map each to the closest product or category in a CSV and import | Avoids mass 404s on URLs with backlinks |

Rules:
- Never redirect every removed product to the homepage; Google treats that as a soft 404. AIOSEO's "Redirect 404s to the Home Page" setting should stay off for stores.
- Do not noindex temporarily unavailable products.
- WooCommerce's "Hide out of stock items from the catalog" removes products from listings and internal links; the product URL still exists. Use it knowing that internal links disappear while stock is out.
- A vendor claim says Merchant listing markup "keeps out-of-stock items showing". The markup only reports availability; keep it accurate.
- AIOSEO paths: **Redirects** (301 single), **Redirects > Import/Export** (CSV bulk), **Redirects > 404 Logs** (find removed URLs still requested), **Broken Link Checker** (separate plugin) for internal links to removed products.
- Seasonal and sale pages (Black Friday, holiday gift guides): reuse the same URL every year and refresh it; see `playbook-monitoring-growth.md`.

Sources: https://aioseo.com/ecommerce-seo/, https://aioseo.com/how-to-easily-find-and-fix-orphan-pages-in-wordpress/, https://aioseo.com/how-to-automatically-redirect-404-pages-to-the-homepage-in-wordpress/, https://aioseo.com/how-to-redirect-links-in-bulk-using-a-csv-file/, https://aioseo.com/black-friday-seo/, https://aioseo.com/wordpress-redirects/

## B10. Architecture, breadcrumbs, internal links and on-site search

Architecture:
- Hierarchy: home > category > sub-category > product. Every product reachable within a few clicks; popular categories linked from the main navigation; no product reachable only through filters or search.
- Use pretty permalinks; avoid `?p=123`, session IDs and dates in product URLs.
- Choose category names and the category base carefully at launch; renaming categories or removing a base later changes URLs and needs redirects.

Breadcrumbs:
- Enable in **General Settings > Breadcrumbs**; display via the "AIOSEO - Breadcrumbs" block, shortcode, widget or theme template. BreadcrumbList markup is output automatically.
- When a product sits in several categories, set the **Primary Category** (or primary term) so the trail and markup show the main path.
- Breadcrumbs are not a ranking factor. They help users and give Google hierarchy and internal links. Google simplified breadcrumb display on mobile results in early 2025 (domain only), so their visible SERP value is now mostly on desktop.

Internal links:
- Category to product, product to category, related products, guides to categories and products with descriptive anchors.
- **Link Assistant** (Pro and up): **Links Report > Orphaned Posts** for orphan products and pages; suggestions with Add Link; **Domains Report** to audit outbound links.

On-site search:
- WooCommerce's default search is weak on SKUs and attributes; a search plugin that indexes product fields (the posts promote SearchWP) improves findability.
- Internal search result URLs should not be indexed. Pick one method: noindex the search results (they remain crawlable so Google sees the tag), or disallow them in robots.txt for crawl savings. Do not do both on the same URLs.
- AIOSEO: **Search Appearance > Advanced > Crawl Cleanup > Internal Site Search Cleanup** (query length cap, emoji and special character stripping, spam pattern blocking) and the Robots.txt Editor search-URL toggle.

Sources: https://aioseo.com/ecommerce-seo/, https://aioseo.com/how-to-use-primary-category-to-customize-breadcrumbs-wordpress/, https://aioseo.com/breadcrumb-seo/, https://aioseo.com/internal-site-search/, https://aioseo.com/ways-link-assistant-can-save-you-time-on-internal-and-external-link-building/, https://aioseo.com/ecommerce-seo-audit/, https://aioseo.com/best-wordpress-permalink-structure/

## B11. Product images at scale

- High-quality images of the actual product from several angles; for variants, images per colour or style.
- Descriptive filenames before upload (`blue-cotton-crew-tee-front.jpg`); alt text that describes what is shown, including the product name naturally; decorative images get empty alt.
- Compress and serve modern formats (WebP or AVIF; Google Search supports both), with responsive sizes (WordPress generates srcset) and lazy loading below the fold. Do not lazy-load the main product image, which is usually the LCP element.
- Images are included in the AIOSEO XML sitemap by default.
- Attachment pages are thin: **Search Appearance > Image SEO > Redirect Attachment URLs** (on by default).
- AIOSEO at scale:
  - **Search Appearance > Image SEO** (Image SEO addon, Plus/Pro in the posts): templates for alt, title, caption and filename from smart tags.
  - **Media Library > Bulk actions > Generate Alt Text for Images with AI**: about 10 AI credits per image per the docs. Review the output; AI alt text can mis-describe colour, material or model.
- Do not use AI-generated images that misrepresent a product. Images must match what customers receive.

Sources: https://aioseo.com/product-page-seo/, https://aioseo.com/category-page-seo-for-woocommerce/, https://aioseo.com/how-to-best-optimize-images-in-wordpress/, https://aioseo.com/wordpress-image-seo/, https://aioseo.com/gpt-image-2-vs-nano-banana-2/, https://aioseo.com/ecommerce-seo-strategy/

## B12. Affiliate products, non-cart catalogs and platform choice

Affiliate and external products:
- WooCommerce: **Products > Add New > Product data > External/Affiliate product**.
- Mark affiliate links `rel="sponsored"` (`nofollow` is also acceptable). Google treats these as hints; the posts' claim that affiliate links "must be nofollow to avoid penalties" overstates it, but undisclosed paid or affiliate links without a qualifying attribute do breach Google's link spam policy.
- Bulk-apply attributes and review link counts per page in **Link Assistant** (affiliate link overview and Domains Report).
- Affiliate product pages need original value (hands-on testing, comparisons, photos). Pages that only repeat the merchant's description are thin affiliate content in Google's guidelines.

Non-cart catalogs (service tiers, affiliate lists, product showcases without checkout):
- The "AIOSEO - Product" block outputs Product markup for a displayed product (tabs General, Identifiers, Offer, Reviews, Review Rating). It has no cart; pair with a payment plugin if selling. The same visible-content and genuine-review rules apply.

Platform choice (vendor view, keep for context):
- WooCommerce for physical or mixed stores, Easy Digital Downloads for digital goods. Hosted platforms (Shopify, Wix, Squarespace) give less control over URLs, robots and markup. AIOSEO only runs on WordPress.
- AIOSEO's **Sitemaps > General Sitemap > Additional Pages** (CSV) can list non-WordPress URLs on the same site. URLs on another host (a separate Shopify store) belong in that host's sitemap; cross-host sitemap entries need both hosts verified in Search Console or a robots.txt reference.
- Migrating a store between platforms: follow the migration steps in `playbook-technical.md` (URL map, 301s, sitemap, Search Console).

Sources: https://aioseo.com/best-woocommerce-affiliate-plugins/, https://aioseo.com/nofollow-vs-dofollow-links/, https://aioseo.com/how-to-add-products-to-wordpress/, https://aioseo.com/best-ecommerce-platform-for-seo/, https://aioseo.com/how-to-add-multiple-urls-to-your-sitemap-the-easy-way/, https://aioseo.com/how-to-add-the-sponsored-link-attribute-to-your-affiliate-links/

## B13. Ecommerce SEO audit checklist

Cadence: at least yearly, after a redesign, theme change, platform or plugin migration, and after an unexplained traffic drop.

1. **Keywords and mapping:** one primary keyword per category and product; no category/product overlap; gaps against 1-4 competitors filtered to commercial and transactional intent.
2. **Rank and traffic data:** **Search Statistics** (Elite): Content Performance Top Losing, Content Rankings (decay), Keyword Rank Tracker (keywords added from Search Console, focus keyphrases or CSV; data is Search Console average position, not scraped rank).
3. **On-page:** unique titles and descriptions, H1 = product or category name, logical H2/H3 for features, specs and reviews, clean slugs, original descriptions (spot-check against the manufacturer's text). Title and description lengths are soft guides; Google truncates by pixel width and rewrites often.
4. **Indexing:** Search Console Pages report; AIOSEO Index Status (Elite) on key products and categories; robots.txt not blocking products, categories, CSS or JS; sitemap present and synced; no accidental noindex on product types or categories.
5. **Structured data:** Product snippets and Merchant listings reports clean; markup matches page and feed; no self-serving or imported reviews.
6. **Facets and parameters:** crawlable parameter URLs under control (B7); internal search not indexed.
7. **Stock changes:** removed products redirected or returning 404/410 correctly; no homepage catch-all redirect; 404 log reviewed.
8. **Speed and mobile:** Core Web Vitals field data on product and category templates (LCP within 2.5 s, INP under 200 ms, CLS under 0.1); compressed images; caching; simple mobile checkout with guest checkout and wallets.
9. **Architecture and links:** click depth, breadcrumbs with primary category, orphan products, broken internal links (Broken Link Checker).
10. **Off-page:** reviews volume and recency, unlinked brand mentions, outreach for buying guides; no paid links without `rel="sponsored"`.
11. **Report:** findings per area, prioritised by impact and effort, with an owner and date for each fix. KPIs: organic revenue and conversions, organic clicks to products and categories, indexed product count, Core Web Vitals pass rate. Use bounce and engagement only as UX diagnostics; they are not ranking inputs.

Ecommerce statistics in these posts are almost all unsourced (for example "about 70% of shoppers start on Google", "53% abandon sites that load in over 3 seconds", "55% abandon carts over surprise shipping costs") (vendor claim). Do not quote them to clients as facts.

Sources: https://aioseo.com/ecommerce-seo-audit/, https://aioseo.com/ecommerce-seo-checklist/, https://aioseo.com/ecommerce-seo-trends/, https://aioseo.com/best-ecommerce-seo-tools/, https://aioseo.com/woocommerce-seo-guide/, https://aioseo.com/ecommerce-seo/, https://aioseo.com/best-woocommerce-seo-plugins/
