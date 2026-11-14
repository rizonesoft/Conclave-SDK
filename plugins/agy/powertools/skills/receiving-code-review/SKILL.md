---
name: receiving-code-review
description: >-
  Use when receiving code review feedback from a cross-family reviewer, PR comment, or human teammate, before implementing suggestions or replying to review threads. Enforces technical verification against the codebase, YAGNI discipline, and zero performative agreement.
---

# Receiving Code Review

Code review is technical evaluation, not social compliance. Verify every claim against the real codebase before acting, push back with evidence when a suggestion is wrong or out of scope, and never open with performative praise.

## Intake sequence

Follow this order on every review item:

```text
READ -> UNDERSTAND -> VERIFY -> EVALUATE -> RESPOND -> IMPLEMENT
```

1. Read the full review without reacting or defending while reading.
2. Restate each item in concrete technical terms naming the exact file, symbol, and failure mode.
3. Verify each claim directly against the codebase (`read_file`, search, tests, and `git log`) before accepting it.
4. Evaluate whether fixing it helps real callers or breaks existing invariants or YAGNI constraints.
5. Respond with technical substance, and clarify any ambiguous item before touching code.
6. Implement valid fixes one item at a time at the owning layer, then verify each fix with fresh tests.

## Forbidden responses

Never write performative agreement or empty thanks:

- Forbidden: "You're absolutely right!", "Great catch!", "Thanks for pointing this out!", "Good eye!", or vague gratitude.
- Instead: state what you verified and what changes (`Fixed in path:line; <cause>`), or show the contradicting code or test output when pushing back.

## Clarifying partial ambiguity

When a review lists multiple items and one or more are ambiguous, do not silently implement only the clear subset if items interact or share a module: ask concise clarifying questions first so interdependent changes do not conflict.

## Judging severity and pushing back

Separate real runtime failures from hypothetical nitpicks:

- Real `P1` or `P2` defect under realistic inputs or documented contracts: fix at the owning layer and add a regression test.
- Reviewer misunderstood how the system works, missed existing invariants, or misread caller context: push back with exact `file:line` references, command output, or historical commit context.
- Requested abstraction, fallback, or configurability with zero real callers or evidence of need: ask the user or push back on YAGNI grounds rather than bloating the interface.
- Reviewer conflicts with explicit owner instructions or repository rules: follow the owner or repository rule and explain the constraint briefly.

## Inline replies on GitHub threads

When replying to pull request inline review comments, reply on the comment thread rather than posting only a top-level PR comment:

```powershell
gh api repos/{owner}/{repo}/pulls/{pr}/comments/{comment_id}/replies -f body="Verified and fixed in <sha>: <brief technical explanation>."
```
