# Final SEO and GEO audit

Run on the article after fact-check pass 2, with `seo.json` filled in. Record each item as pass, fixed or not applicable (with a reason) in `05-seo-audit.md`. Any fix that adds or changes a fact goes back through the fact-check procedure for that claim.

Start with the deterministic checks:

```
node <skill>/scripts/lint-article.mjs <article.md> --seo seo.json --site <domain>
```

Zero errors is required. Each warning is fixed or justified in the audit file.

## Intent and value

- [ ] The article answers the brief's primary query in the first 40 to 60 words (or the house standard's range).
- [ ] Content type and format match what ranks and gets cited for the query; the angle differs.
- [ ] Every essential fan-out question from the brief is answered here or linked.
- [ ] The information gain promised in the brief is present (first-hand material, data, verdict, current figures).
- [ ] Nothing a reader would skip: no filler intro, no summary conclusion, no generic sections.
- [ ] Recommendations name who should not follow them.

## Structure

- [ ] One H1, matching `post.title`. H2/H3 in order, sentence case, descriptive.
- [ ] Each section opens with its answer and names its subject in the first sentence.
- [ ] Sections of roughly 120-300 words; paragraphs under 120 words.
- [ ] Steps as numbered lists, comparisons as tables, key facts in text (not only in images).
- [ ] FAQ with 3 to 6 real questions (or the house standard's count), each answer starting with the direct answer; no invented questions.

## Evidence (GEO)

- [ ] Key claims have a named, linked source in the sentence; every link has a ledger row.
- [ ] Statistics have unit, date and source; time-sensitive facts say "as of".
- [ ] Quotes are real, exact and attributed.
- [ ] Terms are defined once, entities named consistently.
- [ ] No claim of experience the user did not supply.

## On-page SEO and AIOSEO

- [ ] Focus keyphrase: H1, SEO title, meta description (once), slug, first paragraph; a subheading where natural; no stuffing (under 3 per 100 words).
- [ ] 2 to 5 additional keyphrases chosen from the research.
- [ ] SEO title 400-600 px, distinct from other posts, no stale year.
- [ ] Meta description 120-155 characters (or the house standard's limit), unique, factual, not a keyword list.
- [ ] Slug short, lowercase, hyphenated, no dates or stop-word padding.
- [ ] Excerpt written (it is the default description fallback and appears in feeds).
- [ ] 3+ internal links with descriptive anchors that do not use the focus keyphrase, taken from and recorded in the project's link map if it has one (no reused anchor text for different targets); external links to primary sources; sponsored links marked.
- [ ] Featured image: original or licensed, 1200 px+ wide, not text-heavy, alt text, descriptive filename.
- [ ] Body images: informative, alt text accurate, compressed, in the house standard's format (otherwise JPG, PNG or WebP).
- [ ] Open Graph and X title and description set (or deliberately inherited), image set.
- [ ] Category (one primary), a few meaningful tags.
- [ ] FAQ schema only if visible on the page (the linter enforces this). HowTo schema only for a real, visible procedure and only if the house standard allows it.
- [ ] Robots default, canonical self (empty) unless the user says otherwise.
- [ ] Author is a real person with a bio page; reviewer noted if an expert reviewed it.
- [ ] Dates: publish date shown; "last updated" only after a substantive update.

## Human voice

- [ ] `lint-article.mjs` shows no AI-pattern warnings, or each remaining one is justified.
- [ ] Opening and closing 100 words read aloud without scaffolding or summary.
- [ ] Every paragraph has a specific (number, name, date, observed detail or sourced quote).
- [ ] The article states positions and trade-offs, not only neutral description.

## Metadata fact-check

Google's generative-AI guidance (updated 1 October 2026) requires fact-checking AI-written metadata too:

- [ ] SEO title, meta description, excerpt, OG and X text, alt texts, image captions and FAQ schema make no claim the article and ledger do not support.

## No AI-assistance line

- [ ] The article, excerpt and metadata contain no note saying AI assisted or wrote it.
