# Human voice: writing that does not read as AI

The goal is an article a careful reader takes for the work of an experienced person, because it carries what such a person brings: specific facts, first-hand detail, a stated position and plain words. That is also what search engines reward (Google's helpful-content questions ask for first-hand experience, original information and a clear author) and what AI search engines quote.

## The principle

AI text is recognisable less by any single word than by **regression to the mean**: specific facts get replaced with generic, statistically likely phrasing, and evaluation words stand in for information (Wikipedia: Signs of AI writing). Kobak et al. (Science Advances, 2025) measured the post-ChatGPT surge in words like "delves" (28x), "underscores" (13.8x) and "showcasing" (10.7x): almost all style verbs and adjectives that add judgement without adding facts. Liang et al. (ICML 2024) found the same in peer reviews ("meticulous" 34.7x, "intricate" 11.2x, "commendable" 9.8x).

So the fix is never a synonym swap. The fix is content: replace the generic sentence with a specific one, or delete it.

## Never do these

Evasion tricks are banned. They are detectable, they damage the article and they can trigger spam policies:

- homoglyphs (look-alike Unicode letters), zero-width or invisible characters, Unicode tag characters
- deliberate typos or grammar errors
- "humanizer" paraphrasing tools, which change meaning after fact-checking
- writing to an AI-detector score; detectors are unreliable (OpenAI withdrew its own classifier in 2023 for low accuracy; Liang et al. 2023 found detectors flagged 61% of human TOEFL essays as AI)

Never invent experience, anecdotes, test results, customers, quotes or credentials. First-hand material comes from the user (see the intake in SKILL.md). Without it, the run stops at the brief and asks the user for it; a reportorial article without first-hand material is written only if the user explicitly chooses that and the house standard allows it.

## Write this way

1. **Every paragraph carries at least one checkable specific:** a number with unit and date, a named product, version, person, place or organisation, an observed detail, or a sourced quote.
2. **Use the author's real experience:** what they did, measured, saw or got wrong, with the surprises and failures left in.
3. **Take positions.** Say what you recommend and why, what you would not do, the trade-offs, and who should ignore the advice.
4. **Use plain verbs:** is, has, uses, shows, costs, takes. Not "serves as", "stands as", "boasts", "functions as".
5. **Explain mechanisms, not adjectives.** "It renders on the server, so the HTML already contains the text" beats "a robust, seamless solution".
6. **Let rhythm follow the content.** Short sentences make points; longer ones carry explanations. Do not fake variety mechanically.
7. **Keep terms consistent.** Pick one name for a thing and repeat it; do not rotate synonyms.
8. **Cut the scaffolding:** intros that restate the title, "In this article we will", signposting, and conclusions that summarise what the reader just read.
9. **Use structure only where it helps:** sentence-case headings, lists only for genuinely parallel items, tables only for real comparisons, almost no bold in body text.
10. **Name your sources in the sentence** ("Google's 2025 guidance says", "a 2024 Ahrefs study of 1.9 million citations found") rather than "studies show".

## Pattern catalogue and fixes

The linter (`scripts/lint-article.mjs`) counts most of these. A single hit is not proof of anything; clusters are the signal. Fix every cluster, and fix any single hit that adds no information.

| Pattern | Examples | Fix |
|---|---|---|
| Inflated significance | stands as, serves as, is a testament to, plays a crucial/pivotal/vital role, underscores its importance, reflects broader, setting the stage, evolving landscape, indelible mark, deeply rooted | Delete the importance claim; state the concrete consequence (a number, a date, who changed what) |
| Trailing -ing analysis | ", highlighting...", ", ensuring...", ", reflecting...", ", contributing to...", ", fostering...", ", showcasing..." | Cut the clause; if the point matters, make it its own sentence with evidence |
| Promotional tone | boasts, vibrant, rich, profound, nestled, in the heart of, groundbreaking, renowned, seamless, cutting-edge, game-changer, diverse array | Replace the adjective with a checkable fact ("won the 2019 X award") |
| AI vocabulary cluster | additionally, align with, bolster, crucial, deep dive, delve, enduring, enhance, foster, garner, highlight (verb), interplay, intricate, key (adjective), landscape (abstract), meticulous, navigate (abstract), pivotal, realm, robust, seamless, showcase, tapestry, testament, underscore, unlock, unleash, elevate, empower, leverage (verb), valuable, vibrant | Use the plain word, or better, replace the sentence with a specific one |
| Vague attribution | experts say, studies show, research suggests, industry reports, observers note, critics argue, many people | Name the person or organisation with date and link, or delete |
| Negative parallelism | not only X but also Y; it's not X, it's Y; no X, no Y, just Z; Y rather than X | State the positive claim; keep a contrast only if someone actually holds the rejected view |
| Rule of three | reflexive triplets of adjectives or clauses | Keep as many items as are true, often one or two, and develop them |
| Hedges and disclaimers | it's important to note, it's worth noting, it's crucial to, results may vary, while specific details are limited, based on available information | Delete; if a caveat is real, state it specifically |
| Formula sections | Challenges and future outlook; Key takeaways; Conclusion that restates; "Despite these challenges" | End on the last useful point, a recommendation or a next step |
| Collaborative residue | Certainly!, I hope this helps, let me know, would you like, here's a | Delete (hard fail) |
| Placeholders and tool artefacts | [Describe...], INSERT_, 2025-XX-XX, contentReference, oaicite, turn0search, [cite: 1], utm_source=chatgpt.com | Hard fail; resolve before any review |
| Title Case Headings | "How To Choose The Right Plan" | Sentence case unless the site's style guide says otherwise |
| Inline-header bullets | "- **Speed:** It is fast." repeated | Prose paragraphs with real transitions, or a table |
| Dashes | em dash, en dash, "--" or a spaced hyphen used as punctuation | None allowed, anywhere (body, headings, lists, tables, alt text, metadata). Use a comma, colon, full stop or parentheses. Write ranges with a hyphen (120-160) or "to". The linter hard-fails any dash |
| Bold overuse | bold phrases in most paragraphs | No bold in body prose, or one key term per section |
| Emoji and decorative tables | emoji in headings or bullets; three-row "key stats" tables | Remove |
| Paragraph openers | Additionally, Furthermore, Moreover, In addition | Start with the subject |
| Uniform sentences | five or more consecutive sentences of near-equal length | Recast so the rhythm follows the content |
| Copula avoidance | serves as, stands as, functions as, represents, features, offers (for "is" or "has") | is, has |

Signs that are not reliable on their own (do not "fix" them for their own sake): perfect grammar, formal register, transition words in normal use, curly quotes.

## Editor pass (run after every rewrite)

1. Run `node scripts/lint-article.mjs <article.md>`; resolve every hard fail and every cluster warning.
2. Read each paragraph and ask: does it contain a specific a generic article would not have? Is there first-hand material or a clearly marked opinion? If neither, rewrite it with real material or cut it.
3. Read the opening 100 words and the last 100 words aloud. These are where AI scaffolding concentrates.
4. Any new fact introduced while fixing goes back through the fact-check.
5. Rerun the linter: rewrites bring patterns back.
