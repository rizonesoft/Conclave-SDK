## Round 1: astra (`gpt-6-astra` via `codex`)

- Writer: claude
- Run: 2026-11-17T14:00:25Z
- Candidate: a676ece5794dd3e66f214bfd0b4c05f9637013e0
- Effort: medium
- Lenses: adversarial, integration, source-defect, consistency, quality, optimization
- Lines: 57
- Digest: f3e0dd6fc78c5e5b

Reviewed the files at `a676ece` and the requested `b4debe0..d595ec6` diff. Changed nothing. These findings are from source inspection; I did not run tests.

1. **P1, integration/consistency/quality: the recovery chain still cannot stamp.**  
   `kits/reviewer/templates/scripts/review-dispatch.py:1324`; `kits/todo/templates/scripts/lib/todo_graph.py:832`.  
   Trigger: completion returns gaps; reconciliation changes the contract and returns complete; the writer restores the contract and obtains the newly permitted reconciliation. `three_pass_ok` rejects that chain because the preceding reconciliation returned complete. Its following blocking-severity check also rejects a preceding `HIGHEST: none`. The new regression test verifies dispatch acceptance but never stamps.  
   **Fix:** share the exceptional-transition predicate between dispatcher and stamp validation, preserving contract restoration, ancestry and pass caps. Extend the regression through actual stamp creation and receipt validation.

2. **P1, source-defect/integration: checking only before a row cannot enforce three pushes.**  
   Plan §8, item at line 309.  
   Trigger: a row starts with green CI, then pushes its plan corrections, implementation, fixes and findings while CI remains queued. Four or more pushes occur before another row is claimed. The prescribed gate never runs during that interval. A red arriving after the final boundary can also remain unobserved when the runner finishes.  
   **Fix:** observe CI after pushes and at run completion, with a durable observer covering results that arrive after the runner exits. At the threshold, prioritize obtaining a verdict over further ordinary implementation, while keeping commit, push and repair operations available.

3. **P2, source-defect/adversarial: commit distance is not a push count.**  
   Plan §8, item at line 306.  
   Trigger: repeated force pushes replace the single commit after the last green ancestor. Four pushes have occurred, but the proposed count remains one. Conversely, one push carrying twenty commits counts as twenty pushes. A rewritten history can remove the presumed verdict ancestor entirely.  
   **Fix:** count observed remote-ref updates, with durable before/after identities and explicit history-rewrite handling. Define missing observation history as unknown, requiring bounded settlement rather than inventing a count from ancestry.

4. **P2, adversarial/source-defect: choosing the newest verdict can erase an unseen red.**  
   Plan §8, items at lines 306–309.  
   Trigger: run A fails after the last observation; run B succeeds before the next observation. Selecting only the newest completed verdict reports B green without ever reporting A’s failure. The existing `ci_status.py` likewise selects a single decisive run.  
   **Fix:** retain an observation cursor and report every newly completed failure, including run attempts, before advancing it. Distinguish “current main is green” from “all intervening failures were observed.” Page beyond the existing ten-run window when necessary.

5. **P2, adversarial/integration: the retry limits do not bound the overall recovery episode.**  
   Plan §8, item at line 309.  
   Trigger: unknown-state errors alternate with cancelled settlement attempts, so neither consecutive limit is reached. Alternatively, successive repair pushes reveal different failures, so the “same failure” counter never reaches three. The runner can keep repairing or retrying indefinitely.  
   **Fix:** add an overall elapsed-time or attempt budget for unresolved CI recovery, persisted across heartbeat invocations and restarts. Keep the narrower counters, but terminate any exhausted recovery episode through the visible escalation path.

6. **P2, adversarial/integration: settlement has no specified SHA-to-run binding.**  
   Plan §8, item at line 308.  
   Trigger: settlement reads tip A and finds no run; another writer pushes B; `workflow_dispatch --ref main` starts B. Without checking the returned run’s `headSha`, B’s verdict can be attributed to A. Concurrent dispatches also make “wait for that run” ambiguous unless the exact run is identified.  
   **Fix:** bind settlement to an expected SHA and identified run ID, verify workflow, event and head SHA, and recheck the remote tip before reporting coverage. A moved tip or ambiguous dispatch must consume the bounded recovery budget and remain explicitly unresolved.

7. **P2, source-defect/integration: missing records verdicts have no settlement trigger.**  
   Plan §9, item at line 331.  
   Trigger: the code ancestor is green, but records-only runs are cancelled or never produce a verdict. Those pushes explicitly do not count toward §8’s threshold. Arbitrarily many records changes can therefore remain unchecked without causing settlement.  
   **Fix:** track records-check debt separately from suite debt. Reusing suite evidence must not erase the requirement to obtain and observe the records verdict for each required candidate.

8. **P2, integration: a cancelled candidate check can leave the stamp without a recovery route.**  
   Plan §11, item at line 369, together with §8 line 308.  
   Trigger: reviewed candidate A’s records run is cancelled. Main advances to records-only descendant B, which has green records and full-suite evidence. `--covers A` still refuses because A’s own records check is missing. `--settle` operates on main, so rerunning B cannot satisfy that condition. The plan supplies neither candidate-specific recovery nor a bounded escalation for this refusal.  
   **Fix:** specify how to rerun or execute the required checks against A, bound that operation, and visibly escalate if it cannot produce evidence. Keep A’s exact candidate identity throughout.

9. **P2, adversarial/source-defect: `--covers` can select stale green evidence over a later failure.**  
   Plan §11, item at line 369.  
   Trigger: code-equivalent candidate A has an earlier successful full run and a later failed full run. Records-only candidate B has a green records check. Searching for the “newest green full run” still selects A’s earlier success, allowing B to stamp despite the newer failure.  
   **Fix:** define precedence across attempts and equivalent candidates. A newer unresolved suite failure must prevent selection of an older success until a subsequent qualifying run resolves it.

What holds: the plan explicitly prohibits CI gates on commits and pushes, prioritizes red repair, bounds each individual settlement call, requires visible escalation for its named exhaustion cases, distinguishes records evidence from suite evidence, and requires all Linux shards to finish green with `fail-fast: false`. The dispatcher retains its pass cap. None of these changes explicitly removes a review pass. I found no separate optimization defect supported by the supplied measurements.

LENS adversarial: findings
LENS integration: findings
LENS source-defect: findings
LENS consistency: findings
LENS quality: findings
LENS optimization: clean
HIGHEST: P1
OVERALL: needs-attention

## Writer note: owner decision

- The owner kept the old system (every stamp cites a green run of the exact commit it stamps; a red main is repaired before any new row) and only the speed-ups that change no verdict. Findings 2 to 9 concern the gate, settlement, push count, records-only path and neighbour citation, all dropped in the commit that adds this note: `D01 T02 §8` now only reads CI after every push and reports every new failure (finding 4's cursor is taken: no failure is skipped by a later green), never blocking a commit or a push; the first `§9` and `§11` are gone; `§10` (Linux shards, `fail-fast: false`, a missing shard is no verdict) stays.
- Finding 1 (P1, the restored chain cannot stamp) is real: filed as `D01 T02 §11`, which shares one predicate between the dispatcher and `three_pass_ok` and proves the chain through `stamp`.
