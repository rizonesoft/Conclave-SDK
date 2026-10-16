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

## Reversal cost

Low: additive kit; the routing is data in the pin.
