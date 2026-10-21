# Reviewer kit

Date: 2026-10-16. Owner decisions the same day: a pin, a dispatcher and a skill; GPT-6 Astra reviews everything except Astra's own work; Gemini 4 is Astra's failover and Sonnet 5 is Gemini 4's.

## Goal

Every project that wants independent review gets one place that names its reviewers (`.conclave/reviewers.toml`) and one command that runs a review round with failover (`scripts/review-dispatch.py`), the same way on Windows and WSL. The todo kit's `review-todo-section` uses it instead of naming Astra in prose.

## Routing

| Writer | Reviewers in failover order |
| --- | --- |
| `claude` | `astra`, `gemini`, `sonnet` |
| `gemini` | `astra`, `gemini`, `sonnet` |
| `codex` | `gemini`, `sonnet` (Astra never reviews Astra) |

| Reviewer | CLI | Model | Effort |
| --- | --- | --- | --- |
| `astra` | `codex exec` | `gpt-6-astra` | `medium` |
| `gemini` | `agy -p` | `gemini-4-argon-high` | in the model name |
| `sonnet` | `claude -p` | `claude-sonnet-5-5` | `high` |

Tested 2026-10-16 on a planted bug: all three ran headless, read-only (Codex `--sandbox read-only`, Antigravity `--mode plan --sandbox`, Claude `--permission-mode plan`), found it and changed nothing. Antigravity takes the prompt only as the `-p` value, not on stdin.

## Failover

A reviewer is skipped, with the reason recorded, when its CLI is not installed, it exits non-zero, it times out or it returns nothing. A review that finds problems is still a review. When every reviewer fails there is no review: the dispatcher exits 1, and that never counts as approval.

## Record

Each round prints a JSON summary and, with `--record`, appends a `## Round N` section (writer, reviewer, model, failover log, review text) to the findings file with an atomic write.

## Amended 2026-10-20

Owner decision: "the reviewers fallback, it should only be a different family reviewer + 1 fallback". A route names one reviewer and at most one fallback, and neither may be of the writer's family (codex is OpenAI, agy Google, claude Anthropic); the pin refuses anything else. The routes became Claude to Astra then Gemini 4, Codex to Gemini 4 then Sonnet 5.5, and Gemini to Astra then Sonnet 5.5. The routing table above is the original decision. The same day a reviewer whose sandbox could not read the repository returned a non-review, so the prompt gained `OVERALL: blocked`, which the dispatcher fails over.

## Amended 2026-10-21

Owner decision: "The reviewers do not need a fallback. It creates more issues than its useful." A route names exactly one reviewer, never of the writer's family; when it is not installed, fails, times out, returns nothing or replies `OVERALL: blocked` there is no review (exit 1), and no other reviewer runs. The shipped pin drops the Gemini reviewer: Claude and Gemini work go to Astra, Codex work to Sonnet 5.5. The summary's `failover` key stays and holds at most one entry. The Failover section above and the 2026-10-20 amendment are superseded (`design/decisions.md`, One reviewer per route, 2026-10-21).

## Reversal cost

Low: additive kit; the routing is data in the pin.
