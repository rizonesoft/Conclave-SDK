---
schema_version: 1
id: findings-triage
domain: 06-global
status: active
title: "TODO-04 -- Findings triage"
depends_on: ["private-overlay"]
---

# TODO-04 -- Findings triage

> **Goal:** Every entry in `todo/findings.md` is either scheduled in an open section, fixed with a test, or struck with its reason, so the plan holds all known work and nothing waits outside it.

> **Current state:** Measured 2026-11-21 at `3435bbf9`. `todo/findings.md` holds 16 open entries (lines starting `- ` without `~~`), mostly completion-review suggestions and defects noticed in passing, none of them owned by a section.

## Inputs

- `todo/findings.md` and the header rule it carries: strike an entry with its `DNN TNN §N` once scheduled via `add-todo`.
- The `add-todo` skill, which decides whether a finding becomes a new section or joins an open one.

## Outcome

- `grep -cE '^- [^~]' todo/findings.md` prints 0.
- Every struck entry names the section that owns it, the commit that fixed it, or why it was declined.

**Adjacency:** all=not-applicable (plan maintenance: no product records or user data)

**Adjacency rationale:** Triage moves known work into the plan; the work itself is built and reviewed in the sections it lands in.

## Implementation Order

| Order | Section | Deliverable | Depends On | Status |
| ----- | ------- | ----------- | ---------- | ------ |
| 1 | §1 | Every open finding scheduled, fixed or closed | -- | [ ] |

## 1. Every open finding scheduled, fixed or closed

`todo/findings.md` holds defects and suggestions noticed while building other sections. Unscheduled, they block nothing and are never built, so the plan is not complete while any stays open. This section settles the open findings on lines 7 to 27 (including `D00 T03 §15` finding #4 on line 24, `D00 T04 §1`..`§2` P3s on lines 25 to 26, and `D06 T03 §1` Reconciliation 9 P3 on line 27).

**Phase:** 10
**Needs:** none
**Surface:** no

**Build order:**

1. Classify every finding in the range against the current code. Done when: each is marked as a defect, a suggestion, already fixed or superseded.
2. Schedule, fix or strike each one. Done when: `grep -nE '^- [^~]' todo/findings.md` lists none of these lines, and `python scripts/todo-graph.py validate` passes.

- [ ] Triage the open findings on lines 7 to 12 of `todo/findings.md` (as of `3435bbf9`): check each against the code, then schedule it through `add-todo` into a new or existing open section, fix it in this section with a test when it is a small defect, or strike it with its reason (the commit that already fixed it, the section that superseded it, or a declined suggestion with why). Done when: no finding on those lines is left unstruck, and each struck one names a `DNN TNN §N`, a commit or a reason. Cheaper substitute: striking a finding as declined without checking the code.
- [ ] Triage the open findings on lines 13 to 17 of `todo/findings.md` (as of `3435bbf9`): check each against the code, then schedule it through `add-todo` into a new or existing open section, fix it in this section with a test when it is a small defect, or strike it with its reason (the commit that already fixed it, the section that superseded it, or a declined suggestion with why). Done when: no finding on those lines is left unstruck, and each struck one names a `DNN TNN §N`, a commit or a reason. Cheaper substitute: striking a finding as declined without checking the code.
- [ ] Triage the open findings on lines 18 to 22 of `todo/findings.md` (as of `3435bbf9`): check each against the code, then schedule it through `add-todo` into a new or existing open section, fix it in this section with a test when it is a small defect, or strike it with its reason (the commit that already fixed it, the section that superseded it, or a declined suggestion with why). Done when: no finding on those lines is left unstruck, and each struck one names a `DNN TNN §N`, a commit or a reason. Cheaper substitute: striking a finding as declined without checking the code.
- [ ] Triage the open findings on lines 23 to 27 of `todo/findings.md` (including `D00 T03 §15` Round 1 finding #4 on splitting `Resolute` `D00 T04 §50` and `Resolute-SDK` `D01 T01 §8`, `D00 T04 §1`..`§2` P3s, and `D06 T03 §1` Reconciliation 9 P3 on `_append_gitignore_rule` short-write `ftruncate` race): check each against the code, then schedule it through `add-todo` into a new or existing open section, fix it in this section with a test when it is a small defect, or strike it with its reason (the commit that already fixed it, the section that superseded it, or a declined suggestion with why). Done when: no finding on those lines is left unstruck, and each struck one names a `DNN TNN §N`, a commit or a reason. Cheaper substitute: striking a finding as declined without checking the code.
- [ ] Commit: `todo: settle findings lines 7 to 27 (D06 T04 §1)`

**Test checkpoint:** `python scripts/todo-graph.py validate` exits 0, and no line from 7 to 27 of `todo/findings.md` starts with `- ` without `~~`.

## Verification

- `grep -cE '^- [^~]' todo/findings.md` prints 0.
- `python scripts/todo-graph.py validate` and `python scripts/todo-graph.py plan --check` pass.
