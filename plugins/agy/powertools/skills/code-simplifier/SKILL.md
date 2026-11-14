---
name: code-simplifier
description: >-
  Use after implementing a feature or fix when recently modified code looks overly nested, repetitive, or convoluted. Simplifies touched code for clarity and maintainability while preserving exact behavior and interfaces.
---

# Code Simplifier

Refine recently modified code to improve clarity, shallow nesting, and reuse without changing externally observable behavior.

## Scope and boundaries

- Focus strictly on files and functions modified in the current task unless a repository instruction specifies broader scope.
- Never alter public APIs, return shapes, error contracts, edge-case guards, or existing docstrings unrelated to your simplification.
- Never touch imported, generated, or vendor directories unless explicitly asked.

## Refinement checklist

1. **Preserve functionality first**: read the existing tests and callers so you know every invariant that must stay identical.
2. **Flatten control flow**: replace deep conditional trees with early returns and concise guard clauses.
3. **Deduplicate cleanly**: extract shared helpers or table-driven loops when two blocks in your change duplicate the same logic.
4. **Remove noise**: eliminate redundant intermediate variables, dead code paths, and speculative abstractions built for single-use callers.
5. **Match repo style**: align naming, error handling, and typing idioms with neighboring modules in the same package.
6. **Re-verify after simplifying**: run the full relevant test suite freshly and confirm behavior is 100% preserved.
