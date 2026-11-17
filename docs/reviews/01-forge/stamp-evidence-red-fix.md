## Round 1: astra (`gpt-6-astra` via `codex`)

- Writer: claude
- Run: 2026-11-17T16:30:25Z
- Candidate: 15847562ef73e3fe11cf9193eb51c15960a1fafa
- Effort: medium
- Lenses: adversarial, integration, source-defect, consistency, quality, optimization
- Lines: 16
- Digest: 1c875934f827224e

**P2: The unchanged-tree condition still blocks the recovery it intends to allow.** At `kits/todo/templates/.claude/skills/review-todo-section/SKILL.md:168`, “the stamped commit's tree reaches unchanged otherwise” requires more than preservation of the reviewed section. Between §5’s reconciled candidate `1dd6c56` and repair `ef25ac0`, 16 files changed, including unrelated dispatcher and stamp implementation changes. Literally applied, §5 still cannot stamp. Define preservation of the section’s reviewed implementation and contract, except for the separately reviewed repair, while allowing unrelated intervening changes.

The paired-run approach is otherwise sound as a procedural rule: it preserves the original red and requires an actual reviewed fix with green evidence. It can cover a defect the section itself caused, as §5 did; “fixed outside the section” describes the repair’s review route, not the defect’s origin. It does not authorize stamping an unfixed failure. These remain human evidence checks: `stamp` stores check strings without validating CI.

All six installed/template agent paragraphs match exactly. `AGENTS.md:64` agrees on paired evidence but omits the unchanged-tree restriction, so its acceptance conditions are broader. Align it with the clarified rule. CI reporting and red-first repair remain intact.

Static review at `15847562`; no files changed.

LENS adversarial: findings
LENS integration: findings
LENS source-defect: findings
LENS consistency: findings
LENS quality: findings
LENS optimization: clean
HIGHEST: P2
OVERALL: needs-attention

## Round 2: astra (`gpt-6-astra` via `codex`)

- Writer: claude
- Run: 2026-11-17T16:32:49Z
- Candidate: 03d09a548974f814082f75456d1d99772fd89adc
- Effort: medium
- Lenses: adversarial, integration, source-defect, consistency, quality, optimization
- Lines: 19
- Digest: 5fbd97bb0d5d59bb

**P2: The retained rerun cap still leaves a section without a completion route.** At `kits/todo/templates/.claude/skills/review-todo-section/SKILL.md:168`, a cancelled candidate gets at most three reruns, then stays open. `scripts/ci_status.py:383-386` enforces that limit. If all three attempts are cancelled while pending, the new exception cannot apply: there is no red failure and separately reviewed repair. For an already closed review chain, recording the blockage does not provide a way to finish. Define a recovery path that obtains evidence for the same candidate without weakening the checks.

The paired-run exception itself is sound as a procedural rule:

- It can cover a defect the section itself caused. “Fixed outside the section” describes the repair’s separate review, not the defect’s origin. Citing the original red preserves that history.
- It does not authorize stamping an unfixed failure: the green candidate must contain the reviewed repair and preserve the section’s reviewed files and TODO section apart from that repair.
- These are evidence-selection obligations, not automated guarantees. `stamp` validates nonempty check strings, not CI results or the relationship between the two commits.
- All six installed/template stamp paragraphs are identical. `AGENTS.md:64` agrees on the exception and preservation condition. Post-push reporting and red-first repair remain required.

This resolves the reported repaired-red deadlock, but not every route to an unstamppable section. Static review at `03d09a5`; no files changed or tests executed.

LENS adversarial: findings
LENS integration: findings
LENS source-defect: findings
LENS consistency: clean
LENS quality: clean
LENS optimization: clean
HIGHEST: P2
OVERALL: needs-attention

## Round 3: astra (`gpt-6-astra` via `codex`)

- Writer: claude
- Run: 2026-11-17T16:35:15Z
- Candidate: 517d786ee2ccfcc46fefa028858fb2c8cff56ddc
- Effort: medium
- Lenses: adversarial, integration, source-defect, consistency, quality, optimization
- Lines: 19
- Digest: 5a0131b587154f50

Two P2 findings remain in `--rerun`:

- **The idle check misses older active runs.** At `kits/todo/templates/scripts/ci_status.py:385`, it checks only the newest 10 runs. An older running build can fall outside that window after newer pending runs are cancelled. An in-memory reproduction against the candidate submitted three reruns despite an active run, then returned exit 4. Query unfinished runs independently of the newest-run window.
- **An idle snapshot does not guarantee execution.** Between the check at line 385 and submission at line 398, another push can occupy the concurrency group. The rerun can subsequently be cancelled while pending, but line 405 already consumes its allowance. Three such cancellations still leave a closed section unable to stamp. Preserve a recovery route for attempts cancelled without a verdict, and remove the unsupported “no later push can drop it” guarantee.

The paired-run exception itself is sound as a procedural rule. It can cover a defect the section caused: “fixed outside the section” describes the repair’s separate review, not the defect’s origin. Citing the original red preserves that history. It does not authorize stamping an unfixed failure: the green commit must contain the reviewed repair and preserve the section’s reviewed files and TODO section apart from that repair.

All six template/installed stamp paragraphs match. `AGENTS.md:64` agrees on paired evidence and preservation. Post-push reporting and red-first repair remain required. These are procedural evidence obligations, not automated CI validation by `stamp`.

Reviewed at `517d786`; no files changed. Verification included an in-memory reproduction, not live GitHub execution.

LENS adversarial: findings
LENS integration: findings
LENS source-defect: findings
LENS consistency: clean
LENS quality: findings
LENS optimization: clean
HIGHEST: P2
OVERALL: needs-attention

## Round 4: astra (`gpt-6-astra` via `codex`)

- Writer: claude
- Run: 2026-11-17T16:38:20Z
- Candidate: b97e21843ab91323e53d9bb7a6d1e01a1dc1f6ae
- Effort: medium
- Lenses: adversarial, integration, source-defect, consistency, quality, optimization
- Lines: 20
- Digest: 21bdddfbc31430b4

**P2: Infrastructure failures can still exhaust the completion route.** At `kits/todo/templates/scripts/ci_status.py:406-411`, three completed failed reruns permanently block another attempt. If those failures came from an infrastructure outage that subsequently clears, the candidate still cannot obtain green evidence through `--rerun`. The paired-run exception requires a reviewed repair, which an external outage’s recovery need not produce. An in-memory reproduction confirmed exit 4 after three failures. Provide an explicit recovery route after verified infrastructure recovery, preserving all failed evidence.

Otherwise, the rule is sound as a procedural obligation:

- It can cover a defect the section caused, but cannot legitimately hide it: the stamp must cite the original red and the reviewed repair’s green run.
- It does not authorize stamping an unfixed failure. The green commit must contain the repair and preserve the section’s reviewed files and TODO section apart from that repair.
- All six installed/template agent paragraphs match exactly. `AGENTS.md:64` agrees.
- Status-filtered queries cover older active runs. Cancelled attempts no longer exhaust the allowance, so cancellation races remain recoverable.
- Evidence selection remains procedural; `stamp` does not independently validate CI evidence.

Reviewed the specified commit without changing files. Verification used in-memory probes, not live GitHub reruns.

LENS adversarial: findings
LENS integration: findings
LENS source-defect: findings
LENS consistency: clean
LENS quality: clean
LENS optimization: clean
HIGHEST: P2
OVERALL: needs-attention

## Round 5: astra (`gpt-6-astra` via `codex`)

- Writer: claude
- Run: 2026-11-17T16:41:52Z
- Candidate: 1bd7111858ebf0736a2f28a777619257f56f9e7b
- Effort: medium
- Lenses: adversarial, integration, source-defect, consistency, quality, optimization
- Lines: 22
- Digest: 4eede6a8a90b29ed

**P2: Repeated infrastructure failures still lack a completion route.** `kits/todo/templates/scripts/ci_status.py:384-389` refuses every red rerun and delegates to `process-phase` step 3. That skill permits one infrastructure rerun, then declares a second red a real failure (`kits/todo/templates/.claude/skills/process-phase/SKILL.md:57`). If both attempts fail during an external outage that later clears, there is no code repair to review, so the paired-run exception cannot apply either. Provide an explicit retry route after verified infrastructure recovery, preserving the failed evidence.

**P3: Rerun help still describes the removed behavior.** `kits/todo/templates/scripts/ci_status.py:8`, `:361` and `:427` advertise failed-run retries, and line 8 still promises a three-attempt cap. Update these descriptions and the installed copy to match cancelled-only, uncapped retries.

Otherwise, the paired-evidence rule is sound as a procedural obligation:

- It can cover a defect the section itself caused. “Fixed outside the section” describes the repair’s review route, not the defect’s origin. Requiring the original red prevents legitimately hiding that history.
- It does not authorize an unfixed failure: the green commit must contain the reviewed repair and preserve the section’s reviewed files and TODO section apart from it.
- All six installed/template stamp paragraphs are identical. `AGENTS.md:64` agrees on paired evidence and preservation.
- Status-filtered queries cover older active runs. The idle check is not atomic, but cancellation races no longer exhaust a retry allowance.
- `stamp` still records evidence strings rather than independently validating CI.

Reviewed the specified commit without changing files. In-memory probes confirmed red refusal, busy exit 5, and five successive idle cancelled-run retries. No live GitHub reruns were performed.

LENS adversarial: findings
LENS integration: findings
LENS source-defect: findings
LENS consistency: findings
LENS quality: findings
LENS optimization: clean
HIGHEST: P2
OVERALL: needs-attention

## Round 6: astra (`gpt-6-astra` via `codex`)

- Writer: claude
- Run: 2026-11-17T16:43:51Z
- Candidate: 9a855c3ff372215abbbb29b159497d2a931fc741
- Effort: medium
- Lenses: adversarial, integration, source-defect, consistency, quality, optimization
- Lines: 19
- Digest: fb175fecdc891b68

Two findings remain at `9a855c3`:

- **P2: Cancelled candidates can still become permanently unstamppable.** `kits/todo/templates/.claude/skills/review-todo-section/SKILL.md:168` relies on retrying the original run indefinitely. GitHub permits reruns only within 30 days of the initial run. Once that expires, `ci_status.py:404-410` reports refusal without a recovery route. A cancelled candidate has neither green evidence nor the repaired-red exception. Define a fresh execution route for the exact reviewed candidate, preserving its original evidence. [GitHub rerun limits](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/re-run-workflows-and-jobs?tool=cli).
- **P3: Infrastructure retry instructions disagree.** `AGENTS.md:64` and `ci_status.py:387-388` still say one infrastructure rerun, while `process-phase/SKILL.md:57` now permits another after verified recovery. Align these descriptions so callers do not stop at the older limit.

The paired-evidence exception itself is sound as a procedural rule. It can cover a defect the section caused, but requires citing that original red. It does not authorize an unfixed failure: the green commit must contain the reviewed repair and preserve the section’s reviewed files and TODO section apart from that repair. Evidence selection remains procedural, not independently validated by `stamp`.

All six template/installed stamp paragraphs match, and AGENTS.md agrees on their preservation conditions. All six red-first paragraphs also match. The new outage-recovery sentence addresses the previous second-red blockage while retaining failed evidence.

Status-filtered idle checks cover older active runs. Cancellation races remain possible, but no longer exhaust a local retry allowance. In-memory probes confirmed red refusal, busy exit 5, idle submission and refusal reporting. No files changed or live reruns performed.

LENS adversarial: findings
LENS integration: findings
LENS source-defect: findings
LENS consistency: findings
LENS quality: clean
LENS optimization: clean
HIGHEST: P2
OVERALL: needs-attention

## Round 7: astra (`gpt-6-astra` via `codex`)

- Writer: claude
- Run: 2026-11-17T16:46:59Z
- Candidate: ac951dd3ec763dfff159ff976dfaa7ec6205304e
- Effort: medium
- Lenses: adversarial, integration, source-defect, consistency, quality, optimization
- Lines: 24
- Digest: 9b96d84e0aa5240b

The paired-evidence rule is sound procedurally, but the new expired-run fallback has two P2 findings.

1. **P2: Tag runs escape monitoring and repeat-call protection.** At `kits/todo/templates/scripts/ci_status.py:422`, the fallback dispatches on `ci/<commit>` without recording or subsequently checking that run. Normal `--since-last` and repeated `--rerun <commit>` calls still query `main`. A tag run can fail unnoticed; another invocation dispatches again even while its predecessor runs. With `tests.yml` cancelling in-progress runs outside main, repeated recovery attempts can prevent completion. Persist the recovery run identity, include it in normal reporting, and reuse its pending or completed result before dispatching again.

2. **P2: An existing tag is trusted without verifying its commit.** At `kits/todo/templates/scripts/ci_status.py:415`, “already exists” permits dispatch without resolving the tag. A pre-existing or moved tag can execute another commit while the tool describes it as the candidate’s exact tree. Verify the resolved tag and resulting run’s `headSha` against the requested SHA before accepting evidence. GitHub dispatch uses the selected branch or tag. [GitHub documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#workflow_dispatch).

On the requested policy questions:

- A section-caused defect may use the exception, but its original red must remain cited. “Fixed outside the section” describes the repair’s review route, not the defect’s origin.
- An unfixed failure does not qualify: the green commit must contain the reviewed repair and preserve the section’s reviewed files and TODO section apart from that repair.
- Idle-queue checks reduce cancellation risk but are not atomic. Unlimited cancelled-run retries remove the former retry-cap blockage; the tag lifecycle issues above still undermine completion.
- All six template/installed stamp paragraphs match. All six red-first paragraphs match. `AGENTS.md` agrees on paired evidence and the additional infrastructure retry after recovery.
- Step 3’s recovery retry is sound for the stated outage case and retains failed evidence.

Read-only review at `ac951dd`. In-memory probes confirmed two successive tag dispatches, no existing-tag lookup, and queries restricted to `main`. No files changed or live workflows started.

LENS adversarial: findings
LENS integration: findings
LENS source-defect: findings
LENS consistency: clean
LENS quality: findings
LENS optimization: clean
HIGHEST: P2
OVERALL: needs-attention

## Round 8: astra (`gpt-6-astra` via `codex`)

- Writer: claude
- Run: 2026-11-17T16:49:46Z
- Candidate: d8f9f7d3ea29fb1e4f7414c6e826cebb4f678326
- Effort: medium
- Lenses: adversarial, integration, source-defect, consistency, quality, optimization
- Lines: 24
- Digest: 16240f587ac3824b

The paired-evidence rule is sound procedurally, but recovery still has two P2 gaps at `d8f9f7d`.

1. **P2: A recovery run can escape monitoring after an abort.** In `kits/todo/templates/scripts/ci_status.py:425`, the recovery tag is recorded only in memory; dispatch happens at line 444, but persistence waits until line 466, after all workflows finish processing. If a subsequent workflow query fails, or the process stops after dispatch, `--since-last` has no record of the tag to monitor. Its run can fail unnoticed. An in-memory probe confirmed a successful dispatch followed by a second-workflow error without any state save. Persist the monitoring record before dispatch.

2. **P2: Some candidates still have no completion route.** The fresh-run fallback at `ci_status.py:417` handles only sufficiently old cancelled runs. An infrastructure-red run older than GitHub’s rerun window is rejected at line 396 and directed to a rerun that GitHub cannot perform. Likewise, a cancelled run that reaches GitHub’s 50-rerun limit within that window repeatedly fails at line 454 without reaching the fallback. Extend exact-commit recovery to these cases while retaining every failed attempt. [GitHub documents both limits](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/re-run-workflows-and-jobs?tool=cli).

On the requested policy questions:

- A section-caused failure can qualify, but cannot legitimately be hidden: its original red must be cited. “Fixed outside the section” describes the repair’s review route, not the defect’s origin.
- An unfixed failure does not qualify. The green commit must contain the reviewed repair and preserve the section’s reviewed files and TODO section apart from that repair. This remains a procedural requirement, not independently enforced evidence validation.
- All six template/installed stamp paragraphs match. All six red-first paragraphs match. `AGENTS.md` agrees on preservation and infrastructure retries.
- Idle-queue checks reduce cancellation risk but are not atomic. Retrying cancellations is reasonable; the recovery gaps above prevent the promised completion guarantee.
- Step 3’s additional retry after demonstrated outage recovery is sound and retains failed evidence, but does not resolve an expired infrastructure-red run.

Read-only review with in-memory probes. No files changed or live workflows started.

LENS adversarial: findings
LENS integration: findings
LENS source-defect: findings
LENS consistency: clean
LENS quality: findings
LENS optimization: clean
HIGHEST: P2
OVERALL: needs-attention

## Round 9: astra (`gpt-6-astra` via `codex`)

- Writer: claude
- Run: 2026-11-17T16:53:36Z
- Candidate: 2581ce19e9a7da6051cc5bcfff8c066be4c1d6c7
- Effort: medium
- Lenses: adversarial, integration, source-defect, consistency, quality, optimization
- Lines: 24
- Digest: f66ef33c141c59c1

The paired-evidence rule is sound procedurally, but CI recovery still has two P2 defects.

1. **P2: Infrastructure retry cannot recover a failed tag run.** At [ci_status.py:385](/D:/Conclave-SDK/kits/todo/templates/scripts/ci_status.py:385), `_fresh_run` returns an existing red tag run without retrying it. `--infrastructure` never reaches this helper. If the fresh run fails during an outage, the documented retry after recovery repeatedly returns exit 1. An in-memory probe confirmed zero rerun or dispatch requests. Pass the infrastructure intent through and retry the tag run while preserving its failed evidence.

2. **P2: Old tag failures are reported repeatedly as new failures.** At [ci_status.py:299](/D:/Conclave-SDK/kits/todo/templates/scripts/ci_status.py:299), tag runs are fetched regardless of age, but lines 344-348 discard their reported-attempt records after 35 days. Subsequent reads rediscover the same red indefinitely, including after its repair. A probe returned exit 0 for an already reported failure, then exit 1 on both following reads. Retain deduplication records for tag runs that remain eligible for retrieval.

On the requested policy questions:

- A section-caused failure can qualify, but cannot legitimately be hidden: its original red run must remain cited. “Fixed outside the section” describes the repair’s review route, not the defect’s origin.
- An unfixed failure does not qualify. The green commit must contain the reviewed repair and preserve the section’s reviewed files and TODO section apart from that repair. This is a procedural requirement, not automated evidence validation.
- Idle-queue checks reduce cancellation risk but are not atomic. Unlimited cancellation retries remove the former cap blockage; finding 1 still prevents the documented completion route.
- All six template and installed stamp paragraphs match. All six red-first paragraphs match, and `AGENTS.md` agrees.
- Step 3’s additional infrastructure retry after demonstrated recovery is sound and retains failed evidence, but finding 1 prevents it from working for recovery-tag failures.

Reviewed at `2581ce19` using static inspection and in-memory probes. No files changed or live workflows started.

LENS adversarial: findings
LENS integration: findings
LENS source-defect: findings
LENS consistency: clean
LENS quality: findings
LENS optimization: clean
HIGHEST: P2
OVERALL: needs-attention

## Round 10: astra (`gpt-6-astra` via `codex`)

- Writer: claude
- Run: 2026-11-17T16:56:57Z
- Candidate: 026c5ea1b7a07131c4dae8efb9b7819c66536329
- Effort: medium
- Lenses: adversarial, integration, source-defect, consistency, quality, optimization
- Lines: 24
- Digest: a9065bf319979677

The paired-evidence rule is sound procedurally, but two P2 recovery gaps remain at `026c5ea`.

1. **P2: Recovery-tag failures can go unnoticed.** [ci_status.py:300](D:/Conclave-SDK/kits/todo/templates/scripts/ci_status.py:300) reads only the latest five tag runs. Repeated fresh dispatches can push an unread failure outside that window. An in-memory probe with one failure followed by five cancellations returned exit 0 and omitted the failure. Read tag history through the cursor with pagination, preserving every unreported attempt.

2. **P2: A missing original run prevents recovery.** [ci_status.py:428](D:/Conclave-SDK/kits/todo/templates/scripts/ci_status.py:428) exits before reaching the fresh-run fallback when the candidate has no main-branch run. If that run was deleted, or never existed, repeated calls cannot obtain evidence, even though the exact-commit dispatch mechanism exists. A probe confirmed exit 1 with no dispatch. Consult existing recovery runs and permit fresh exact-commit execution in this case.

On the requested rule questions:

- A section-caused defect can qualify, but its original red must remain cited. “Fixed outside the section” describes the repair’s review route, not the defect’s origin.
- An unfixed failure does not qualify: the green commit must contain the reviewed repair and preserve the section’s reviewed files and TODO section apart from it. This is a procedural requirement, not automated evidence validation.
- Idle-queue checks reduce cancellation risk but are not atomic. Unlimited cancellation retries remove the previous retry-cap blockage; finding 2 still leaves a completion gap.
- All six installed/template stamp paragraphs match. All six red-first paragraphs match, and AGENTS.md agrees.
- Step 3’s additional infrastructure retry after demonstrated recovery is sound for the stated outage case and explicitly retains failed evidence.

Reviewed pinned files with in-memory probes. No files changed or live workflows started.

LENS adversarial: findings
LENS integration: findings
LENS source-defect: findings
LENS consistency: clean
LENS quality: findings
LENS optimization: clean
HIGHEST: P2
OVERALL: needs-attention

## Round 11: astra (`gpt-6-astra` via `codex`)

- Writer: claude
- Run: 2026-11-17T16:59:40Z
- Candidate: 118df328b6492601a51ee0884ee873d1cabab880
- Effort: medium
- Lenses: adversarial, integration, source-defect, consistency, quality, optimization
- Lines: 22
- Digest: 4e522f39d3a31535

The paired-evidence rule is sound procedurally, but the candidate still has a P2 monitoring defect.

**P2: A tracked recovery failure can be silently marked as reported.** [ci_status.py:307](D:/Conclave-SDK/kits/todo/templates/scripts/ci_status.py:307) merges recovery-tag runs into main’s history. On a first read, or after cursor corruption, lines 319-325 mark every completed run older than the newest completion as already reported. If a recovery run fails and a newer main run succeeds, the recovery failure disappears without being printed. An in-memory probe against `118df328` returned exit 0, printed only the green run, and marked both runs reported. Exempt tracked recovery runs from that first-read suppression and add a regression test.

On the requested questions:

- **Section-caused red:** It can qualify, but cannot legitimately be hidden. The original red must be cited. “Fixed outside the section” describes the repair’s review route, not the defect’s origin.
- **Unfixed failure:** It does not qualify. The green commit must contain the reviewed repair and preserve the section’s reviewed files and TODO section apart from that repair. This is a procedural requirement, not automated evidence validation.
- **Ability to finish:** Removing the retry cap and adding exact-commit recovery addresses the previous permanent refusals. Idle-queue checks reduce cancellation risk but cannot guarantee progress under continuous queue activity; retries still require an eventual idle opportunity.
- **Consistency:** All six installed/template stamp paragraphs match, as do all six red-first paragraphs. `AGENTS.md` agrees with both rules; the installed script matches its template.
- **Infrastructure retry:** Step 3’s additional retry after demonstrated outage recovery is sound and explicitly retains each red as evidence.

Reviewed pinned files with an in-memory probe. No files changed or live workflows started.

LENS adversarial: findings
LENS integration: findings
LENS source-defect: findings
LENS consistency: clean
LENS quality: findings
LENS optimization: clean
HIGHEST: P2
OVERALL: needs-attention

## Round 12: astra (`gpt-6-astra` via `codex`)

- Writer: claude
- Run: 2026-11-17T17:02:13Z
- Candidate: aa4439f54c9c78fa02edbe3c60bdd752c805bc50
- Effort: medium
- Lenses: adversarial, integration, source-defect, consistency, quality, optimization
- Lines: 22
- Digest: 5212f66a9cbcab3d

The paired-evidence rule is sound procedurally, but one P2 monitoring defect remains.

**P2: An unreadable recovery registry silently hides recovery failures.** At [ci_status.py:296](D:/Conclave-SDK/kits/todo/templates/scripts/ci_status.py:296), `since_last()` discards `_load_state()`’s error note. An unreadable `build/ci-status-reruns.json` therefore removes recovery tags from monitoring without warning. An in-memory probe reported the recovery red with a valid registry, but returned exit 0 and only main’s green with an unreadable registry. Treat this as unknown monitoring state, preserve the cursor, and report the error until recovery-tag discovery is restored.

On the requested questions:

- **Section-caused red:** It can qualify, but cannot legitimately be hidden. The original red must remain cited; “fixed outside the section” describes the repair’s review route, not the defect’s origin.
- **Unfixed failure:** It does not qualify. The green commit must contain the reviewed repair and preserve the section’s reviewed files and TODO section apart from that repair. This is procedural evidence validation, not automated enforcement.
- **Ability to finish:** Removing the retry cap and adding exact-commit recovery avoids the former permanent refusals. Idle checks are not atomic, and continuous queue activity can still starve retries; progress requires an eventual idle opportunity.
- **Consistency:** All six template/installed stamp paragraphs match, as do the six red-first paragraphs. `AGENTS.md` agrees. The installed script matches its template.
- **Infrastructure retry:** The additional retry after demonstrated outage recovery is sound and retains failed evidence. The registry defect above compromises monitoring of recovery runs.

Reviewed pinned files at `aa4439f` with an in-memory probe. No files changed or live workflows started.

LENS adversarial: findings
LENS integration: findings
LENS source-defect: findings
LENS consistency: clean
LENS quality: findings
LENS optimization: clean
HIGHEST: P2
OVERALL: needs-attention

## Round 13: astra (`gpt-6-astra` via `codex`)

- Writer: claude
- Run: 2026-11-17T17:04:38Z
- Candidate: ce873ce56d3fa73aef1e4b88b3c5e6cb318dd0cb
- Effort: medium
- Lenses: adversarial, integration, source-defect, consistency, quality, optimization
- Lines: 22
- Digest: 423408fd4e0e947d

The stamp rule is sound, but the recovery script has one P2 evidence-loss defect.

- **P2: `--rerun` can erase the recovery registry after a read failure.** In [ci_status.py](/D:/Conclave-SDK/kits/todo/templates/scripts/ci_status.py:425), an unreadable registry becomes `{}` plus a warning. Execution continues, and line 489 overwrites the registry, even when the candidate is already green and nothing was rerun. I reproduced this against the pinned source with in-memory mocks: exit `0`, replacement registry `{}`. Subsequent `--since-last` calls cannot discover the previously registered recovery tags, so their failures can go unnoticed. Preserve the registry and return unknown, as `since_last` already does. The installed script has the same defect.

The requested policy checks:

- **A red caused by the section remains visible.** The exception requires citing its original red run. “Fixed outside the section” describes the separately reviewed repair, not an exemption for section-caused defects.
- **An unfixed failure does not qualify.** The green commit must contain the reviewed repair and preserve the section’s reviewed files and TODO section apart from that repair. An unrelated green tip is insufficient.
- **The original stamping deadlock is removed.** A closed review chain can use the separately reviewed repair’s green evidence. Cancellation no longer exhausts a fixed retry allowance. Idle-queue retries remain conditional on a later retry when the queue clears; they do not guarantee eventual completion under continuous activity.
- **The wording agrees.** The relevant policy paragraphs are identical across all three agents’ template copies, and their installed copies match. AGENTS.md states the same evidence exception.
- **The additional infrastructure retry is reasonable.** It requires renewed infrastructure evidence, an indication that the outage cleared, and retention of every red attempt. It does not authorize retrying an unexplained product failure until green.

Reviewed the specified range and pinned files. Changed nothing; validation was static inspection plus the isolated reproduction above, without live CI mutations.

LENS adversarial: findings
LENS integration: findings
LENS source-defect: clean
LENS consistency: findings
LENS quality: findings
LENS optimization: clean
HIGHEST: P2
OVERALL: needs-attention

## Round 14: astra (`gpt-6-astra` via `codex`)

- Writer: claude
- Run: 2026-11-17T17:07:13Z
- Candidate: b72013431b2a9b0afe35bbe2708926e8ebb6687a
- Effort: medium
- Lenses: adversarial, integration, source-defect, consistency, quality, optimization
- Lines: 22
- Digest: 34092b64f591784d

The stamp rule is sound procedurally, but recovery still has one P2 monitoring defect.

**P2: Concurrent reruns can erase a recovery run’s monitoring record.** [ci_status.py:492](D:/Conclave-SDK/kits/todo/templates/scripts/ci_status.py:492) writes the caller’s stale registry snapshot. If another invocation registers and dispatches a recovery run in between, this closing write removes its entry. `--since-last` then cannot discover that tag’s failure. An in-memory interleaving against `b720134` dispatched two recovery runs, returned exit 0, and retained only one monitoring record. Atomic replacement prevents partial writes, not lost updates. Serialize registry read-modify-write operations or store recovery registrations independently, with a regression test.

On the requested questions:

- **Section-caused red:** It cannot legitimately be hidden. The original red must be cited. “Fixed outside the section” describes the repair’s review route, not the defect’s origin.
- **Unfixed failure:** It does not qualify. The green commit must contain the reviewed repair and preserve the section’s reviewed files and TODO section apart from that repair. An unrelated green tip is insufficient.
- **Ability to finish:** The exception removes the closed-review-chain deadlock. Cancellation retries no longer exhaust a fixed allowance. Idle-queue recovery still requires an eventual idle opportunity and another invocation; continuous activity can starve it.
- **Consistency:** The relevant paragraphs match across all three agents’ templates and installed copies. `AGENTS.md` agrees. The installed script matches its template.
- **Infrastructure retry:** The additional retry after demonstrated outage recovery is reasonable and explicitly retains failed evidence. It does not authorize retrying unexplained product failures until green.

Reviewed pinned files and used an isolated in-memory probe. No files changed or live workflows started.

LENS adversarial: findings
LENS integration: findings
LENS source-defect: clean
LENS consistency: clean
LENS quality: findings
LENS optimization: clean
HIGHEST: P2
OVERALL: needs-attention

## Writer note: bounded

- Round 14's P2 (concurrent registry writes) is closed by removal: the registry and the fresh-run-on-a-tag recovery are gone, and `--rerun` keeps no state. The review of this rule ends here after 14 rounds; the paired-evidence rule itself was found sound in every round from 2 on. What remains is written as known limits in `ci_status.py`'s docstring and `D01 T02 §8`'s note: a run GitHub will not rerun is written as open for the operator, and the idle-queue check is not atomic (a dropped rerun is simply run again).
