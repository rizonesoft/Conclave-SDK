# Global Engineering Rules

Applies alongside repository `AGENTS.md` and `GEMINI.md` files, where repository rules win if more specific.

## 1. Fix at the owning layer

- Never hide a fault behind output buffers, post-render HTML rewrites, CSS `!important` hiding, swallowed exceptions, lint or type suppressions, skipped tests, or `--no-verify`.
- Trace the defect and fix the layer that owns the invariant: settings in settings, content in stored content, behavior in the producing code, data in the source or importer.
- Allow a workaround only when the owning layer genuinely cannot express the fix; keep it narrow, mark it with `WORKAROUND: <reason>` on or up to three lines above it, and name it as a workaround.
- Whenever a turn edits code, end the final response with a `Layer:` line naming the owning layer, the changed layer, and any workaround.

## 2. Leave touched areas sound

- Fix real defects found in the code you touch at their owning layer and add a regression test that fails before the fix and passes after it.
- Report genuinely unrelated defects in the response as `file:line` entries without leaving unsolicited `TODO` comments.

## 3. Act, then report

- Carry out routine, reversible tasks immediately without asking "shall I proceed" or confirming an already answered confirmation.
- Ask first only before destructive or irreversible actions, credential creation/rotation/exposure, force-pushes, shared/production changes, or missing business intent; use `ask_question` with the `(Recommended)` option first when multiple design choices exist.
- Lead reports with the outcome, state exact file paths with clickable `[basename](file:///...)` links, and finish with verified follow-ups.

## 4. Trunk-based git hygiene

- Develop straight on `main` and never create git branches or worktrees unless the user explicitly asks for isolation in that task.
- Inspect `git status --short` and dirty diffs before staging, stage named files cleanly, and never discard user edits with `reset`, `checkout`, `restore`, or `clean`.
- Never add `Co-Authored-By` lines or AI attribution to commits, PRs, or generated content, and confirm commits with `git log --oneline -1` and `git status --short`.

## 5. Verification and independent review

- Run fresh proving commands in the current turn and read full output plus exit status before claiming work is fixed, passing, or complete.
- Never treat same-model subagents (`invoke_subagent` or `run_workflow`) as final sign-off; use them only for parallel discovery and pre-flight polish.
- Run cross-family review on nontrivial changes (`python scripts/review-dispatch.py --writer agy` where `.conclave/reviewers.toml` exists, else read-only `codex exec`), verify every finding against the code, and push back with evidence rather than performative agreement.

## 6. Secrets, prose, scratch, and process hygiene

- Never print, echo, log, or commit secret values; check the 1Password `Conclave` vault with boolean or count checks before asking for credentials.
- Never write em dashes or en dashes anywhere (prose, code, comments, commit messages, or responses); write one line per Markdown paragraph and list item.
- Keep temporary and scratch files in `R:\scratch` (`/mnt/r/scratch` in WSL), never left behind in repositories.
- Wrap heavy full builds and full suites with `bosun run -- <cmd>` when `bosun` is on `PATH`, pass `CREATE_NO_WINDOW` or `-NoNewWindow` for console children in launcher tests, and kill whole process trees (`taskkill /T` or process groups) on timeout or teardown.

## 7. Creative writing and articles

- Use NLP phrasing for creative writing (articles, page copy, marketing copy, product descriptions): answer first, question-shaped headings, short active sentences, clear named entities, no stock AI phrasing, and no em or en dashes.
- Add original value with primary sources, first-hand detail, E-E-A-T signals (named author, honest limits, review date), sourced figures, and never include a line claiming AI wrote or assisted with the article.
- Claude researches, writes, and rewrites articles; Antigravity and Codex only review (facts, AI-sounding prose, SEO) and suggest without rewriting the text, and never use humanizer or paraphrasing tools.
- Run `article_check.py` (or the repository's `scripts/article-check.py`) on every draft and written-back post, fixing every `FAIL` and answering every `WARN`.

## 8. Orchestrator (Carbon) Cadence and Design Contracts

- Under Orchestrator (Carbon), Carbon plans one TODO section per `exit_plan_mode` handoff (reading the section and the repository's design contract, verifying claims against the codebase, and naming exact tokens, shared `Chrome:` controls, states, and visual gates), and sets `Re-plan if:` so Hydrogen hands back to Carbon after each section's `stamp` and `ci_status.py` check before resolving the next ready row whether `Surface` is `yes` or `no`.
- Hand back immediately mid-section to Carbon whenever a needed design token or shared `Chrome:` control is missing, the pinned reviewer returns `COMPLETION: gaps` or a `P1` or `P2` architectural or design-contract finding, or Hydrogen fails twice on the same fix.
- Run `python scripts/design-lint.py` before committing UI edits whenever present (`strict` zero-raw-literal mode with shrink-only baseline on custom token-system apps, `theme-only` raw-color mode on accepted-look native apps like `ScratchPad`), fix every finding using tokens or theme resources, and never grow a baseline without operator approval.
