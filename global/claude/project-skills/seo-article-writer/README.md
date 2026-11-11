# seo-article-writer

A Claude Code skill that researches, writes, fact-checks, cross-reviews (with OpenAI Codex) and SEO/GEO-audits one blog article at a time, then sets it up in WordPress with All in One SEO (AIOSEO) Elite. It is project-independent: copy the folder into any repository.

## Pipeline

| Stage | Who | Output |
|---|---|---|
| 1. Research and brief | Claude (+ SEO connector if present) | `00-brief.md`, `sources.md` (user approves) |
| 2. Draft | Claude | `01-draft.md`, `seo.json` |
| 3. Fact-check pass 1 | Claude with fresh-context verifiers | `02-claims-pass1.md`, `02-draft.md` |
| 4. Independent review | Codex (read-only, live web search) | `03-codex-review.json`, `03-review-response.md`, `03-draft.md` |
| 5. Fact-check pass 2 | Claude | `04-claims-pass2.md` |
| 6. SEO/GEO audit and voice edit | Claude + `lint-article.mjs` | `05-seo-audit.md`, `final.md` (user approves) |
| 7. AIOSEO + WordPress | Claude | `wp-payload.json`, `post.html`, WordPress draft |

## Install in a repository

Copy this folder to `<repo>/.claude/skills/seo-article-writer/` (project skill) or `~/.claude/skills/seo-article-writer/` (all projects), then start a new Claude Code session. Ask for an article ("write a blog post about ...") or run `/seo-article-writer`.

Requirements:

- Node 18 or later (the scripts have no dependencies).
- Codex CLI installed and logged in: `codex --version`, `codex login status`. The review always runs with `-s read-only`, whatever the Codex default sandbox is.
- For stage 7: WordPress REST access through a connection that stores the Application Password securely. Without it the skill produces the files and a manual checklist.

## Project house rules

A project can override the skill's defaults with `seo-article-writer.json` in its root or `.claude/` folder (template: `templates/project.example.json`): its article standard, voice files, checker and post-write commands, link map, query baseline, working folder, protected post IDs, backup step, reviewer pin file and unattended mode. House limits fail the linter as errors. The review script takes the model and effort only from the pin file (for example `.conclave/reviewers.toml`) and refuses anything else. `guard-post.mjs` refuses protected posts and fails closed. With `unattended`, gates pass on writer and reviewer agreement and articles without first-hand material are parked instead of asked about.

## Roles

Claude researches, writes and rewrites. Codex reviews only (facts, intent, AI-sounding prose, invented experience, SEO/GEO) and never edits the text, so every change stays inside the fact-check chain.

## Scripts

```
node scripts/lint-article.mjs <article.md> [--seo seo.json] [--keyphrase "..."] [--site example.com] [--project seo-article-writer.json] [--json]
node scripts/codex-review.mjs --article <draft.md> --brief <brief.md> [--ledger <ledger.md>] [--out review.json] [--effort high] [--model <name>] [--project seo-article-writer.json]
node scripts/build-aioseo-payload.mjs <seo.json> [--out wp-payload.json]
node scripts/guard-post.mjs --project seo-article-writer.json --post <id> [--post <id> ...]
node scripts/to-gutenberg.mjs <article.md> [--media media-map.json] [--out post.html]
```

## Research basis (October 2026)

The rules cite their sources inline. Main ones:

- Google Search Central: *Optimizing your website for generative AI features* (May 2026), AI features and your website, spam policies (August 2026), generative AI content guidance (1 October 2026: fact-check all AI content and metadata), helpful content, title links, snippets, publication dates, image SEO, Article structured data, FAQ rich results retired 7 May 2026.
- Search Quality Rater Guidelines, 11 September 2025.
- Microsoft Bing: optimising content for AI search answers (October 2025), Webmaster Guidelines (2026).
- Aggarwal et al., GEO (KDD 2024); Ahrefs, SE Ranking, Indig/Gauge, Semrush citation studies (2025-2026).
- Wikipedia: Signs of AI writing; Kobak et al. (Science Advances 2025); Liang et al. (2023, 2024, 2025).
- FActScore, SAFE, Chain-of-Verification, Claimify; IFCN principles; SIFT and lateral reading.
- AIOSEO 5.0.3 source code and aioseo.com documentation.

Revisit the references when Google, Bing or AIOSEO publish major changes.
