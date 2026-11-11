# Licensing, plans, account and requirements

Plans, licence behaviour, activations, AI credits billing, support, requirements.

Built from a full read of aioseo.com/docs, /faqs and /blog on 2026-10-11 (AIOSEO Pro 5.0.2 on aioseo.com). Each section lists its source pages. Text in [brackets] is a reviewer note where the vendor advice looks dated or conflicts with Google guidance. UI labels move between versions: confirm on the live site before giving click paths as fact. Unresolved points are in open-questions.md.

## Contents

- Licence model and pricing
- What a Pro purchase includes; free vs Pro
- Sites, activations, staging, client sites
- Account area tasks (aioseo.com/account)
- AI credits
- Support channels, GDPR, usage tracking
- Requirements and platform compatibility

## Licence model and pricing
Sources: https://aioseo.com/faqs/, https://aioseo.com/docs/how-does-your-pricing-work/, https://aioseo.com/docs/can-i-buy-a-lifetime-or-monthly-license/, https://aioseo.com/docs/can-i-purchase-a-custom-plan-with-specific-features-and-site-activations/, https://aioseo.com/docs/can-i-purchase-more-than-one-plan/, https://aioseo.com/docs/do-you-charge-tax-or-vat/, https://aioseo.com/docs/do-you-offer-special-pricing-for-nonprofits-and-charities/, https://aioseo.com/docs/what-payment-methods-do-you-accept/

- AIOSEO Pro is sold as an **annual recurring licence**, charged automatically each year to the credit card or PayPal account used at purchase.
- **Annual only.** There are no lifetime or monthly plans.
- **Sale and promo prices apply to the first year only.** Renewals bill at the regular price.
- **No custom plans** built from chosen features or site counts. To get a feature, buy the tier that includes it.
- **Multiple plans are allowed.** Log in at https://aioseo.com/account/ (the FAQ says https://aioseo.com/login/), go to https://aioseo.com/pricing/, pick a plan and check out.
- **Payment methods:** credit card or PayPal. You cannot switch a subscription between PayPal and credit card because of payment-processor restrictions (stated on the FAQ page only).
- **Tax/VAT:** added where your country requires it and shown at checkout and on the receipt. Prices on the Pricing page exclude tax/VAT.
- **Nonprofit/charity pricing:** exists, details at https://aioseo.com/seo-for-non-profit-organizations/.
- **Plan tiers and what each includes:** none of these pages lists the contents of each tier. They all point to https://aioseo.com/pricing/. Tier facts that do appear in the docs:
  - **Elite:** Index Status (Search Statistics » Index Status tab, and the Index Status icon in the AIOSEO Details column).
  - **Elite:** Search Statistics and the Keyword Rank Tracker / "Open Keyword Performance Tracker".
  - **Pro (any paid tier):** multiple keywords per post.
  - **Pro addons named here:** Image SEO addon (auto alt text, titles, captions), Video Sitemap addon, Local SEO addon. Link Assistant is "in All in One SEO Pro". SEO Revisions is "in All in One SEO Pro".
  - Tiers are not stated here for SEO Alerts, IndexNow, Schema Generator, Breadcrumbs, Redirects, llms.txt or AI features.

## What a Pro purchase includes; free vs Pro
Sources: https://aioseo.com/docs/whats-included-in-my-purchase-of-all-in-one-seo-pro/, https://aioseo.com/docs/what-is-the-difference-between-the-free-version-of-all-in-one-seo-and-all-in-one-seo-pro/, https://aioseo.com/docs/how-long-will-i-receive-support-and-updates-for/, https://aioseo.com/docs/will-the-plugin-work-without-a-license-key/, https://aioseo.com/docs/i-have-the-free-version-can-i-just-buy-support/, https://aioseo.com/faqs/

For as long as the subscription is active, a purchase includes:
- **Premium features:** whatever the purchased plan includes.
- **Plugin updates.**
- **Premium support:** Monday to Friday, US East Coast business hours only.

Without a licence key:
- The Pro plugin **still runs**. AIOSEO does not recommend running it that way.
- Premium-feature settings and addons are unavailable, and plugin updates stop.

Expired or cancelled licence:
- Premium features, updates and support all stop.
- SEO data and settings stay in the WordPress database. Nothing is lost.

Support access:
- Free users **cannot buy support on its own**. Support needs a current Pro subscription.

## Sites, activations, staging, client sites
Sources: https://aioseo.com/docs/how-many-sites-can-i-install-all-in-one-seo-pro-on/, https://aioseo.com/docs/do-staging-test-or-development-sites-count-towards-my-licenses/, https://aioseo.com/docs/can-i-use-all-in-one-seo-on-client-sites/, https://aioseo.com/docs/setting-wp_home-and-wp_siteurl-in-the-wp-config-php-file/, https://aioseo.com/faqs/

- **Site count:** set by the plan (see the Pricing page). If you get a "maximum activations" notice you believe is wrong, contact support.
- **Staging, test and dev sites do not count** toward activations. The License Manager recognises them only by hostname:
  - subdomains such as `dev.mysite.com`, `staging.mysite.com` and `test.mysite.com`;
  - names used by major hosts' staging features.
  - Any other naming may consume an activation. Ask support to fix it.
- **Client sites:** buy one plan that covers all client sites, or one plan per client. Clients can also buy through your affiliate link, which pays a **20% commission** (https://aioseo.com/affiliates/).
- **Wrong site URLs break licence activation.** If WordPress Address / Site Address (Settings » General) misbehave, licence activation and other features can fail. Fix:
  1. Back up the site.
  2. Ask the host whether it rewrites WP_HOME/WP_SITEURL dynamically.
  3. In `wp-config.php`, check for or add these lines before `/* That's all, stop editing! Happy publishing. */`:
     ```php
     define('WP_HOME','https://mydomain.com/');
     define('WP_SITEURL','https://mydomain.com/');
     ```
  4. Make sure both exactly match the live URL, including www vs non-www and http vs https.

## Account area tasks (aioseo.com/account)
Sources: https://aioseo.com/docs/can-i-cancel-my-account/, https://aioseo.com/docs/can-i-upgrade-downgrade-my-subscription/, https://aioseo.com/docs/can-i-get-an-invoice-for-my-payment/, https://aioseo.com/docs/how-do-i-change-my-payment-information/, https://aioseo.com/docs/how-to-renew-your-aioseo-license/, https://aioseo.com/docs/where-can-i-find-my-download-link-and-license-key/, https://aioseo.com/docs/where-can-i-download-all-in-one-seo/, https://aioseo.com/docs/i-cant-log-in-to-my-account/, https://aioseo.com/docs/i-dont-see-my-purchase-information-in-the-account-area/, https://aioseo.com/docs/i-havent-received-my-receipt-or-login-details/, https://aioseo.com/docs/what-is-your-policy-on-refunds/, https://aioseo.com/faqs/

| Task | Where / how |
|---|---|
| Download link and licence key | In the purchase receipt email, which arrives as soon as payment is approved (check spam). Also on the **Downloads** tab at https://aioseo.com/account/ (direct: https://aioseo.com/account/downloads/). |
| Download the free plugin | https://wordpress.org/plugins/all-in-one-seo-pack/ |
| Cancel | **Billing** tab » Subscriptions table » **Cancel** link » follow the prompts. Data in WP is kept. |
| Upgrade or downgrade | **Downloads** tab » **Upgrade** button/link next to the plan » choose the licence level » checkout. Allowed at any time. |
| Invoice (PDF) | **Billing** tab » **Generate Invoice** link » fill in the form. Alternatively, use the basic contact form and include business name, address and tax ID if they should appear on the invoice. |
| Change card | **Billing** tab. The new card is used for future payments. |
| Change PayPal source | In PayPal: Settings (gear) » Payments » **Automatic payments** » the pre-approved payment for **"Semper Plugins"** » **Change Payment Method** » Save. |
| Renew an expired licence | **Billing** tab » Subscriptions » **Resubscribe** link » checkout. |
| Renew early | Not possible before the renewal date. Wait for expiry, then Resubscribe. |
| Failed auto-renewal | AIOSEO emails you and the licence may expire. Update payment details. If the status shows **On hold** or **Expired**, use Resubscribe. |
| Can't log in | https://aioseo.com/login/ » "Forget your password" » purchase email » **Reset Password**. Check spam. |
| Purchase not shown in account / no receipt | Contact support at https://aioseo.com/contact/ with the purchase email address. |
| Refund | Within **14 days** of the first purchase, 100% back (FAQ). No refunds after 14 days or on renewals. Doc page: form at https://aioseo.com/refund-survey/. FAQ page: Contact » "Complete a Form" under "I have a basic question" » "Account or Subscription question" » "I'd like a refund". |
| Support ticket | Account » **Support** tab (https://aioseo.com/account/support/) » "create a support ticket". |
| Changelog | https://aioseo.com/changelog/ |
| Feature suggestion | https://aioseo.com/feature-suggestion/ |
| Public roadmap | None. |
| Testimonials | Send through the contact form (name, optional photo, location, website link). May appear on /testimonials/ or /trends/. |

## AI credits
Sources: https://aioseo.com/faqs/

- **What they are:** tokens spent by AIOSEO's generative AI features. Both free and paid users can use them.
- **Cost per use:** a typical AI action costs **about 10 credits**.
- **Free trial credits used up:** upgrade to Pro, or buy **PAYG credits** on the AI Credits Pricing page.
- **Paid credits used up:** upgrade to Pro, upgrade the licence tier, or buy PAYG credits.
- **No rollover:**
  - Pro users' credits **reset at the annual renewal**, and unused credits are lost.
  - PAYG credits expire **one year after purchase**.
- **Refund:** within 14 days, provided **fewer than 500 credits** have been used.
- **Credits and licences are separate:**
  - Buying credits does not include a Pro licence.
  - Buying Pro does include AI credits. The amount per tier is not stated.

## Support channels, GDPR, usage tracking
Sources: https://aioseo.com/docs/do-you-offer-phone-support/, https://aioseo.com/faqs/, https://aioseo.com/docs/is-all-in-one-seo-compliant-with-gdpr/, https://aioseo.com/docs/usage-tracking/, https://aioseo.com/docs/privately-sharing-login-credentials-with-our-support-team/, https://aioseo.com/docs/how-to-add-a-temporary-administrator-login-to-your-site/

**Support channels**
- No phone support.
- The doc page (MODIFIED 2026-08-14) says there is **24×7 chat support on the Contact page**. The /faqs/ page (MODIFIED 2026-05-20) says there is **no phone or chat** support. These contradict each other; the doc is the newer of the two.
- Pro subscribers open tickets from the Account » Support tab.

**GDPR**
- AIOSEO claims to be "100% GDPR compliant" because it collects no personal data covered by GDPR.

**Usage tracking**
- Data is synced **weekly**. It collects:
  - PHP, WordPress, MySQL and AIOSEO versions;
  - PHP `SERVER_SOFTWARE` combined with an AIOSEO option called "SAS", used to identify hosts;
  - theme and plugin names and versions;
  - for customers, **licence key, email and URL**;
  - AIOSEO settings;
  - site and user counts, and whether the site is multisite;
  - the usage-tracking config itself.
- [These pages do not say where tracking is turned on or off or whether it is opt-in. The browser-support page mentions "opt-in tracking".]

**Giving support access to a site**
- Create a temporary admin rather than sharing your own password:
  1. Users » Add New.
  2. Username `aioseo` or `allinoneseo`. The support email address was obfuscated in the source.
  3. Role: Administrator. Copy the generated password.
  4. Click **Add New User**.
  5. Back up the site first (UpdraftPlus is suggested).
  6. Delete the user once support is finished.
- Sharing the credentials:
  - The ticket form at Account » Support » "create a support ticket" has a section called **"Access to your WordPress website"** with two options: "I will provide access by creating a temporary administrator user account" and "...by sharing my own administrator user account".
  - Choosing the first option shows a **SupportAlly Secrets** link. Paste the username and password there and click **Create Secret Link**. Put that link in the **SupportAlly Secrets Link** field, fill the mandatory login-URL field, and leave the username and password fields empty.
  - Reason: the ticket's contents, including any password typed into it, are copied into the email thread.

---

## Requirements and platform compatibility
Sources: https://aioseo.com/docs/what-are-the-minimum-requirements-for-all-in-one-seo-pack/, https://aioseo.com/docs/supported-php-version/, https://aioseo.com/docs/update-wordpress/, https://aioseo.com/docs/whats-required-to-use-aioseo/, https://aioseo.com/docs/does-all-in-one-seo-work-on-a-wordpress-com-site/, https://aioseo.com/docs/does-all-in-one-seo-work-on-non-wordpress-sites/, https://aioseo.com/docs/do-i-need-coding-skills-to-use-aioseo/, https://aioseo.com/docs/will-all-in-one-seo-slow-down-my-website/, https://aioseo.com/docs/who-should-use-aioseo/, https://aioseo.com/docs/how-is-aioseo-better-than-other-seo-plugins/

| Item | Requirement |
|---|---|
| WordPress | Minimum page: "5.7 up to latest". Its footnote: 5.6 support ended summer 2025, and everything below 6.0 is dropped at the start of 2026. Update page: 5.9 and below dropped at the start of 2026; recommends latest, "at least 7.x". **Effective minimum in late 2026: WP 6.0+.** |
| PHP | 7.1+ works; 8.0+ recommended; 7.0 dropped May 2025 |
| Database | MySQL 5.7+ or MariaDB 10.4+ |
| Hosting | Self-hosted WordPress, or WordPress.com **Business plan** (only Business can install custom plugins; there is a separate WordPress.com install doc). Does **not** work on non-WordPress sites. |
| Coding | None needed |
| Performance | Vendor claims it does not slow sites down (marketing claim, no data) |
| Host recommendation | SiteGround (aioseo.com is hosted there) |
