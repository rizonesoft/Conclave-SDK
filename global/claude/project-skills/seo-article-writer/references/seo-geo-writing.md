# Writing for search and AI answers

Apply while drafting. `seo-geo-audit.md` checks the result. Read `human-voice.md` alongside this file: the two must hold together, and where a rule here would make the prose robotic, the human-voice rule wins.

Google's position (May 2026 guide on generative AI features): optimising for AI search "is still SEO", there is no special format, schema, file or length for AI, and what helps is non-commodity content with a unique point of view, clear headings and good images. Microsoft Bing (October 2025) adds that AI answers favour clear, self-contained, fact-anchored passages. The rules below satisfy both without writing "for machines".

## Opening

- Answer the main question in the first 40 to 60 words (or the house standard's range): the direct answer, then the one condition or caveat that matters. Rater guidelines want "the most helpful and essential" content near the top (QRG 5.2.2), and an analysis of 18,000 ChatGPT citations found 44% came from the first 30% of the text (Indig and Gauge, 2026).
- No throat-clearing, no restating the title, no "in this article". The second paragraph can say who the article is for or what it covers if that helps the reader decide to stay.
- Include the focus keyphrase in the first paragraph where it reads naturally.

## Sections

- Each H2 opens with its answer in one or two sentences, then explains, then gives evidence (numbers, steps, examples, a table).
- A section should make sense when read alone: name the subject in its first sentence instead of starting with "This" or "It". Apply this to section openers, definitions, key claims and FAQ answers; elsewhere write normally.
- Keep sections focused. About 120 to 300 words between headings works well (SE Ranking 2025 associated 120 to 180-word sections with more ChatGPT citations; AIOSEO warns past 300 words without a subheading).
- Paragraphs: one idea, usually 2 to 4 sentences, never over about 120 words.
- Use a numbered list for steps, a table for comparisons and specifications, bullets only for genuinely parallel items. Keep every key fact in HTML text, never only in an image, chart, tab, accordion or PDF.

## Headings

- Exactly one H1 (the post title). H2 and H3 in order, no skipped levels (Google does not mind order, screen readers do).
- Sentence case. No emoji, no keyword stuffing, no template headings such as "Conclusion" or "Key takeaways".
- Use the reader's question wording where it matches real queries; use descriptive signposts otherwise ("What it costs after year one", "When not to use it"). The headings alone should read as a sensible outline.
- Put the focus keyphrase or a close variant in at least one H2 or H3 only where it reads naturally.

## Evidence and citability

The GEO study (Aggarwal et al., KDD 2024) measured visibility gains in generative engines from adding quotations (+41%), statistics (+31%), fluent writing (+28%) and cited sources (+28%); keyword stuffing lowered visibility (-8%). The engine was a 2023 simulation, so treat the numbers as direction, not promise. In practice:

- Every key claim carries a named, linked source in the sentence: "Google's spam policy, updated August 2026, defines scaled content abuse as ...".
- Statistics carry a unit, a date and who measured them. Prefer primary data.
- Quotes are real and attributable, from a primary source or the user's own interview. Never invent or paraphrase inside quotation marks.
- Definitions use a plain pattern: "[Term] is [category] that [does what] for [whom]". Define each term once, on first use.
- Name entities exactly (products, versions, organisations, people, places) and keep the names consistent.
- State relationships with verbs ("X replaced Y in 2025 because ..."), keeping the conditions that make a claim true.
- Write "as of <month year>" for prices, versions, statistics and rules that change.

## First-hand experience

Experience is the E that generic AI content cannot fake, and Google's guidance asks for it directly. Use the user's material: what they did, measured, paid, saw and got wrong, with dates and numbers. Mark opinion as opinion. If the user supplied no experience, the run stops at the brief and asks for it (see SKILL.md, stage 1). Write without it only when the user explicitly chooses to and the house standard allows it, and then never imply testing that did not happen.

## Links

- Internal: 3 or more links to genuinely related posts or pillar pages, with descriptive anchor text that says what the target page is about. Never "click here" or "read more".
- External: link the primary source for each key claim. Only link sources you trust. Mark sponsored or affiliate links and untrusted or user-generated ones with a rel value in the Markdown link title, which the converter turns into the `rel` attribute: `[text](https://url "sponsored")`, `[text](https://url "nofollow")`, `[text](https://url "ugc")`. Do not write raw HTML links.
- Every link must resolve (the fact-check verifies this).

## Keywords

- Focus keyphrase in: the H1 (near the front if natural), the SEO title, the meta description, the slug, the first paragraph, and one subheading if natural.
- Elsewhere, use natural variants and pronouns. There is no target density; AIOSEO's 0.5 to 2.5% band is a stuffing alarm, not a goal. Keyword stuffing is a spam policy at Google and Bing and lowered visibility in the GEO study.
- Meta keywords are ignored by Google; skip them.

## Images

- A featured image that is original or properly licensed, at least 1200 px wide, not mostly text, not a logo.
- Additional images where they add information: screenshots, photos of the real thing, diagrams. Place them next to the text they illustrate.
- Descriptive file names (`renewal-price-comparison.jpg`), in the format the house standard sets (otherwise JPG, PNG or WebP), compressed.
- Alt text describes what the image shows and why it is there, under about 125 characters, keyphrase only if it is truthfully part of the image. Decorative images get empty alt text. Google's October 2026 guidance says AI-written alt text must be fact-checked like the body.

## FAQ section

- Include an FAQ of 3 to 6 questions real readers ask (People Also Ask, forums, support tickets) that the body does not already answer, or the count the house standard sets. If there are fewer real questions, use fewer and say so in the audit; never invent questions to reach a number.
- Each answer starts with the direct answer (yes, no, a number, a name), then one to three supporting sentences, and restates the subject so it stands alone.
- Write the FAQ in Markdown as an H2 with one H3 per question and the answer as the paragraph below it. The visible text is the source of truth.
- FAQPage schema is optional and comes from one place only: `seo.json` `aioseo.schema.faq`, with each question and answer copied exactly from the visible text (the checker enforces this). Do not also use AIOSEO's FAQ block, which adds its own schema and would duplicate it. Google stopped showing FAQ rich results on 7 May 2026, so the markup is for accuracy and other engines, not a Google rich result.

## Step-by-step procedures

- Write a real procedure as a numbered list, one action per step, with the result the reader should see.
- HowTo schema is allowed for a real procedure that is visible on the page, when the house standard allows it. Google removed How-To rich results in 2023, so it brings no Google rich result; add it in AIOSEO's Schema Generator only if the house standard asks for it, with the steps copied exactly from the visible list.

## Ending

End on the last useful thing: a recommendation, a decision rule, a next step or a link to the next article in the journey. No summary of what was just said.

## Dates and author

- Show the publish date, and a "Last updated" date only after a substantive update. Never change dates or add the current year to a title without real changes; Google lists that as a red flag.
- A real, named author with a bio linked from the byline. Never a fake persona, AI headshot or invented credentials.
- Do not add a note, byline line or footer saying AI assisted or wrote the article. The named author takes responsibility for it.

## Never

- Write to a word count, to an SEO-plugin score or to an AI-detector score.
- Pad with filler FAQs, generic "why you'll love this" sections, repeated images or summaries.
- Hide text, cloak, or add invisible characters.
- Publish anything the fact-check has not cleared, including the title, description, alt text and schema.
- Produce many near-identical articles from one template (scaled content abuse).
