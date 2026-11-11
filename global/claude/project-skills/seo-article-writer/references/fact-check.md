# Fact-check procedure

Used twice: pass 1 checks the first draft, pass 2 checks the draft after the Codex review and every rewrite since pass 1. Both passes write a claims ledger (`templates/claims-ledger.md`). A pass that edits the article must re-extract claims from the edited text before it ends, because rewrites introduce new claims.

The method combines newsroom practice (Smith, *The Fact Checker's Bible*; Borel, *The Chicago Guide to Fact-Checking*; IFCN principles), lateral reading and SIFT (Wineburg and McGrew 2019; Caulfield 2019), and LLM-specific methods: atomic claim extraction (FActScore, Min et al. 2023), search-backed per-claim checks (SAFE, Wei et al. 2024), independent verification that never sees the draft's answer (Chain-of-Verification, Dhuliawala et al. 2023) and context-aware extraction (Claimify, Metropolitansky and Larson 2025).

Why every citation gets opened: language models fabricate or misquote sources often enough that unchecked citations are a known failure (Walters and Wilder 2023 found 18% of GPT-4 citations fabricated; Rao et al. 2026 found 3 to 13% of URLs from commercial LLMs and research agents hallucinated). The drafting context is the least reliable judge of its own facts.

## 1. Set the frame

Record in the ledger header: the as-of date (today), the audience, and the region or jurisdiction if prices, law, availability or units depend on it.

## 2. Extract atomic claims

Go sentence by sentence. Split compound sentences into single checkable propositions and make each one self-contained: replace pronouns, add the subject, the time and the place ("In 2025, X's revenue was Y", not "it grew to Y").

Include implicit claims:

- superlatives and firsts ("the largest", "the first", "only")
- causal claims ("X causes Y", "because")
- trends ("rising", "now more common")
- comparisons ("faster than", "cheaper than")
- every number, date, name, title, version, price and quote

Clearly marked opinion is not checked as fact, but the facts it rests on are.

## 3. Classify and prioritise

| Type | What to check |
|---|---|
| Number or statistic | Value, unit, base year, denominator, percent vs percentage points, who measured it and how |
| Date or timeline | Exact date, order of events |
| Name, title, affiliation | Spelling, current role, the right person among similar names |
| Quote or attribution | Exact wording, speaker, date, context, ellipses that change meaning |
| Product, price, spec, version | Current official documentation; these go stale within months |
| Legal, medical, financial, safety | Current primary text; highest stakes |
| Scientific or causal | Study design and population; correlation is not causation |
| Superlative or first | Strongest form of evidence needed; often false |
| Trend or forecast | Who forecast it, when, and on what basis |
| First-hand experience | Only the author can confirm; never invented |
| Common knowledge | Spot-check |

High priority: health, money, law, safety, statements about named people or companies, claims central to the argument, and every number, quote and superlative. These need one Tier 1 source or two independent Tier 2 sources (check that the two are not both copying the same original).

## 4. Verify each claim independently

- Turn the claim into a neutral question ("What was X's 2025 revenue?"), not a leading one ("Confirm X's revenue was Y"). Answer it from search, not from memory.
- Where the tooling allows, verify in fresh context: a subagent or Codex given the question but not the draft. Never ask the drafting context to grade itself.
- Read laterally: before trusting a site, check who runs it, what it sells and whether credible others cite it.
- Trace to the original: press coverage to the press release, release to the paper or dataset, aggregator to the official documentation. Read the original's wording, scope, sample, date and caveats.

## 5. Check each citation against its claim

- The URL resolves (fetch it). If it does not, try the Wayback Machine, then classify the link as rotted or fabricated.
- DOIs and ISBNs resolve to the stated work.
- The page contains the specific fact, not only the topic. Copy the supporting passage into the ledger.
- The article does not overstate the source: "may" turned into "does", correlation into causation, a mouse study into a human result, one country into the world, a preprint into peer-reviewed, a vendor claim into an independent finding.

## 6. Numbers, quotes, recency, names

- Recompute derived figures (percentages, growth, totals, conversions). Never mix two sources' figures in one comparison without saying so.
- Quotes: find the exact words in a primary recording, transcript or the speaker's own publication. Quote-aggregator sites are not sources.
- Recency: find the latest authoritative statement for anything time-sensitive. Prices and specs older than about 6 months, statistics older than the latest release and superseded law are "outdated". Write "as of <month year>" where values change.
- Names: spelling, current title, organisation.

## 7. Source tiers

- **Tier 1, primary or authoritative:** statutes, regulations, court records, official statistics, standards bodies, company filings, a vendor's own documentation about its own product, original datasets, the peer-reviewed paper itself, direct statements or recordings of the person quoted.
- **Tier 2, strong secondary:** systematic reviews, reputable news organisations with corrections policies, IFCN-signatory fact-checkers, academic books, recognised professional bodies.
- **Tier 3, usable with care and attribution:** preprints (labelled), trade press, named expert blogs, vendor studies (labelled as the vendor's claim). A Tier 3 source supports only an attributed claim: "According to X, ...". Wikipedia is a pointer to sources, never the citation.
- **Tier 4, never evidence:** anonymous or SEO content farms, affiliate "best X" roundups, pages that look AI-generated, quote sites, social posts (unless they are the primary statement), chatbot answers including this skill's own earlier drafts, pages that cite nothing.

## 8. Verdicts and actions

| Verdict | Meaning | Action |
|---|---|---|
| Supported | A Tier 1 or 2 source states it with matching scope and date | Keep; confirm the citation; log the passage |
| Partly supported | Core right, detail wrong or overstated | Rewrite to match the source exactly; recheck the rewrite |
| Unsupported | No adequate source after at least three targeted searches plus tracing | Remove, or turn into attributed opinion; if it is first-hand, ask the user |
| Contradicted | Good sources say otherwise | Correct or delete; if the argument depended on it, tell the user and rework the section |
| Outdated | Superseded price, version, statistic or law | Update with an "as of" date, or keep the old figure with its date |
| Unverifiable | Private data, prediction, anonymous claim, the author's own experience | Attribute and qualify, confirm with the user, or remove; never fake precision |
| Citation mismatch | Source exists but does not say this | Treat as unsupported until a correct source is found; replace the citation |
| Fabricated source | Link, DOI, quote or paper does not exist | Remove immediately; recheck every claim from the same drafting pass more strictly |

**Blocking rule.** The article cannot move to the next stage while any Unsupported, Contradicted, Citation mismatch or Fabricated item remains. Partly supported, Outdated and Unverifiable items must carry their completed edit.

## 9. Close the pass

- Re-extract claims from the revised text and check the new ones.
- Every external link in the article has a ledger row.
- No writing or SEO pass may add a fact after pass 2 without running these steps on it.
- Record a summary at the top of the ledger: claims checked, count per verdict, edits made, open questions for the user.
