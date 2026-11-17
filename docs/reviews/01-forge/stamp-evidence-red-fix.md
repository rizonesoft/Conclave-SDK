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
