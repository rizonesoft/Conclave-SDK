---
name: independent-review
description: Get an independent review of your own work from the reviewer pinned in .conclave/reviewers.toml (a different model family from yours) through scripts/review-dispatch.py, then verify and act on every finding. Use before calling a nontrivial change done, before a commit that ships, or when a TODO section needs its review round.
---

# Independent review

Your own review is not enough for a nontrivial change: a different model reviews it. `.conclave/reviewers.toml` names who reviews whose work, and `scripts/review-dispatch.py` runs the round.

| Work written by | Reviewer |
| --- | --- |
| Claude (Opus 5.5) | GPT-6.1 Sol at xhigh |

Claude Opus writes and GPT reviews: the pin routes no other writer, so a round for Codex or Gemini work refuses (owner decision 2026-10-22, after trials of other writer and reviewer pairs). The route names exactly one reviewer, never of the writer's own model family: the pin refuses anything else.

## Steps

1. Review your own change first and fix what you find.
2. Write the review prompt to a scratch file, not the repository, from `docs/review-round-prompt.md`: name the candidate commit or range, the governing documents, and the lenses that apply.
3. Run the round naming the agent that wrote the change as the writer, never another: only `claude` has a route, so a round for Codex or Gemini work refuses, which is no review:

   ```bash
   # Claude-written work, the only route:
   python3 scripts/review-dispatch.py --writer claude --prompt <scratch>/review-prompt.md --record docs/reviews/<topic>.md
   ```

   On Windows use `python` instead of `python3`; the command is otherwise the same.
4. Read the review. Verify every finding against the code before acting: fix what is real, and record why anything else is not.
5. Commit fixes as new commits and run another round on the new tip, up to 22 rounds (a round that returns no review does not count). A unit that needs patching three rounds running gets re-thought, not patched again.

## Rules

- The dispatcher's JSON output and the `## Round N` section it appends are the evidence. A verdict with no record is an opinion.
- Exit 1 means the reviewer returned no review, and no other reviewer runs in its place. That is never an approval: say so, and do not ship on it.
- A reviewer that could not reach the work (its sandbox could not read the repository) replies `OVERALL: blocked`, which is no review. If its sandbox keeps failing, put the diff in the prompt.
- Reviewers run read-only. Never pass a reviewer a secret, and never ask it to edit files.
- Change reviewers only in `.conclave/reviewers.toml`, never by calling a model directly.
