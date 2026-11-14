---
name: parallel-precheck
description: >-
  Use before shipping nontrivial code changes to run four parallel read-only pre-check lenses via run_workflow (silent failures, simplification, type design, and layer/test gaps), polish findings, and then dispatch true cross-family review.
---

# Parallel Pre-check and Cross-Family Review

This skill runs a two-tier quality pipeline:

1. **Tier 1 (Pre-flight Polish, NEVER Final Review)**: runs four read-only specialist lenses concurrently through `run_workflow` on your diff so you catch obvious defects before external review.
2. **Tier 2 (True Independent Cross-Family Review)**: dispatches a different model family in read-only mode so you never sign off on your own model family's work.

## Tier 1: Parallel `run_workflow` lenses

Run [precheck_workflow.py](./scripts/precheck_workflow.py) with `run_workflow`:

- `ScriptPath`: absolute path to `scripts/precheck_workflow.py` inside this skill folder.
- `Cwd`: target repository root.
- `Args`: `{"cwd": "<repo_root>", "base": "HEAD"}` (or pass `"files": ["path/a.py", ...]` and `"purpose": "<short summary>"` to narrow scope).

The workflow runs four read-only `research` agents in parallel:

| Lens | Focus |
| ---- | ----- |
| `silent-failure-hunter` | Swallowed exceptions, silent fallbacks, missing error context |
| `code-simplifier` | Deep nesting, dead branches, redundant wrappers, over-engineering |
| `type-design-analyzer` | Leaky boundaries, unvalidated inputs, weak invariants |
| `layer-and-test-critic` | Symptom masking in wrong layers, missing regression/edge tests |

Fix legitimate findings from Tier 1 first, re-run local tests, and never treat Tier 1 clean output as final review sign-off.

## Tier 2: Cross-family review dispatch

Choose the route based on the repository:

1. **Repository with `.conclave/reviewers.toml` and `scripts/review-dispatch.py`**: use the repository's pinned reviewer via `scripts/review-prompt.py` (written to `R:\scratch`) and `python scripts/review-dispatch.py --kind round --writer agy ...` (see the repo's `independent-review` skill if installed).
2. **Repository without `.conclave/reviewers.toml`**: write a concise review prompt in `R:\scratch\review-prompt.md` naming the commit range/diff, changed files, and governing rules, then run `codex exec --sandbox read-only -C <repo_root> - < R:/scratch/review-prompt.md` (or via WSL `codex` if Codex runs there).
3. Process every returned finding through `receiving-code-review`: verify against real code before fixing, fix valid defects, push back with evidence on false positives, and re-verify tests.
