## Plan review: astra (`gpt-6.2-astra` via `codex`)

- Writer: claude
- Run: 2026-11-19T08:14:00Z
- Candidate: 6cee3a0050a2f04a3bc87236745aa9ea1f2e3d59
- Effort: medium
- Lenses: plan
- Lines: 13
- Digest: 5a2986f5d7f78bba

1. **P1, §10 lines 363, 365–366.** An accepted pin can make filing unreachable. With `no_progress_cap = 3`, three consecutive data P2 reconciliations can stop the dispatcher while the stamp still requires six. `pass_cap` can also leave fewer than six reconciliations after plan, round and completion. Define which rule wins, or reject incompatible settings with a reason. Test both cases through dispatch and stamp.
2. **P1, §10 line 365.** The stamp currently checks that at least one `- Filed:` target exists. Two open P2s with only one filed can therefore satisfy every proposed test. Specify how each finding maps to a resolving TODO section, then test that omitting either finding refuses the stamp and that both mappings survive receipt read-back.
3. **P1, §10 lines 364–365.** A reply can contain a `P2 data` finding alongside an ordinary P2 and end with `P2 DATA: no`. As written, that files the data finding after three reconciliations. Define `yes` to mean *any* open P2 is data-related. Require dispatch and stamp to reject contradictory evidence or apply the longer cap, and test the same recorded mixed reply through both paths.
4. **P1, §10 lines 363–366 and the test checkpoint.** Hard-coded thresholds of 3 and 6 would pass. The dispatcher test could also pass if it refused every P2 reconciliation. Use a pin with different caps and prove, for each kind, that dispatch admits the last required reconciliation, refuses the next one before invoking the reviewer, and that stamp accepts `:filed` at that same boundary. Also exercise a P2-blocking pin with both keys omitted to prove the defaults.
5. **P1, §10 lines 365–366.** Stamp validation replays earlier transitions as well as checking the final pass. A final-pass-only change would accept a new chain that continued past a filing cap and later returned clean. Applying the new rule indiscriminately on replay has the opposite defect: it can invalidate an existing receipt built legally under an older pin. Specify the compatibility rule and test both a newly overrun chain and read-back of a previously valid chain.
6. **P2, §10 lines 364–366.** The dispatcher’s JSON `blocking` field currently depends only on `HIGHEST` and the pin’s severity list. Adding `p2_data` alone leaves callers seeing `blocking: true` on the very pass the stamp accepts as filed. Make the summary report the effective decision and test its value immediately before and at the cap.
7. **P2, §10 lines 363–364, 367.** Two existing user-facing paths are missing from the acceptance checks. `review_pin.py --caps`, which the writer skill directs users to run, would still omit both effective filing caps. The dispatcher also appends reply-format instructions from `review_pin.py` to the supplied prompt, so changing only the three Markdown prompts leaves custom prompts without the classification rule. Test the CLI read-back and the actual prompt delivered to a reviewer.
8. **P2, §10 test checkpoint.** `CONCLAVE_FULL_TESTS=1 python -m unittest tests.test_todo_graph` is POSIX shell syntax. It does not launch the stamp suite in the SDK’s Windows PowerShell workflow. Give a PowerShell-compatible invocation and verify that the gated stamp cases execute.

LENS plan: findings  
HIGHEST: P1  
PLAN: gaps  
OVERALL: needs-attention

## Writer note: plan review

All eight findings checked and taken into the section in 6bd7bda8 (a dated Corrected note, the items and the checkpoint):

- Planned: 1, a chain the no-progress cap stops files its P2s, and the data cap may not pass what pass_cap allows, in 6bd7bda8
- Planned: 2, one Filed line per open P2 by its number, each resolving and kept in the receipt, in 6bd7bda8
- Planned: 3, P2 DATA: yes when any P2 is data; a contradictory reply is incomplete to the dispatcher and refused by stamp, in 6bd7bda8
- Planned: 4, tests under caps 2 and 4 at both boundaries in dispatch and stamp, and a pin without the keys, in 6bd7bda8
- Planned: 5, the rule binds only a section whose pin has the keys; an overrun chain is refused and an older receipt still validates, in 6bd7bda8
- Planned: 6, the summary blocking field is the effective decision, in 6bd7bda8
- Planned: 7, --caps prints both caps and the appended reply format carries the tag rule, in 6bd7bda8
- Planned: 8, the checkpoint gives the PowerShell and bash invocations with no gated test skipped, in 6bd7bda8

## Round 1: astra (`gpt-6.2-astra` via `codex`)

- Writer: claude
- Run: 2026-11-19T08:50:34Z
- Candidate: bff0269d6cd61a06b35cc43294b2753b172a3415
- Effort: medium
- Lenses: adversarial, integration, source-defect, consistency, quality, optimization
- Lines: 33
- Digest: 988d0fed791f71f9

## Adversarial: needs-attention

1. **P1** `kits/todo/templates/scripts/lib/todo_graph.py:908` lets two open findings share one filed section. At the ordinary cap, give findings 1 and 2 separate `- Filed:` lines that both name `D00 T01 §2`. Both number checks pass, and the receipt deduplicates the targets to `["D00 T01 §2"]`. The stamp succeeds even though §10 requires each finding to have its own section.

## Integration: needs-attention

2. **P2** `kits/reviewer/templates/scripts/review-dispatch.py:1535` reports `blocking: true` when the stamp already permits filing. Set `no_progress_cap = 1`, keep the ordinary cap at 3, and return an ordinary P2 at completion and again at the first reconciliation. The summary calls `holds()` without the stall state. A caller following that summary requests another reconciliation, which the same dispatcher refuses.
3. **P2** `kits/reviewer/templates/scripts/review_pin.py:632` searches the entire reply for a data-risk tag, including the history a reconciliation must discuss. I reproduced this with a numbered item marking a previously data-tagged finding closed, a second item reporting an ordinary open P2, and a `no` footer. The contradiction check returned `True`, so the dispatcher discards a valid review.

## Source-defect: needs-attention

4. **P2** `kits/todo/templates/scripts/lib/todo_graph.py:906` counts closed findings as open. At the filing cap, return `1. Closed (P2): repair verified` and `2. Open (P2): repair still needed`, then file finding 2. The stamp demands a filed section for finding 1 as well. The reconciliation prompt explicitly asks reviewers to number both closed and open gaps, while §10 requires filing only open ones.
5. **P2** `kits/reviewer/templates/scripts/review_pin.py:876` returns before appending the classification instructions when a completion step has no lenses. Use a supported lensless completion step, enable both caps, and supply a project-owned prompt. The reviewer is asked only for `HIGHEST`. An ordinary P2 reply following that prompt gets the absent-line default and holds the section for six reconciliations instead of three.

## Consistency: needs-attention

6. **P2** `kits/reviewer/templates/scripts/review_pin.py:344` runs the cap-dependent validator even after `pass_cap` failed validation. I passed `faults()` the candidate pin with `pass_cap = "33"` in memory. It raised `TypeError` at line 614 while subtracting 3 from the string, losing the actionable pin diagnostic. The adjacent `no_progress_cap` check already handles this failed prerequisite.

## Quality: needs-attention

7. **P3** `tests/test_todo_graph.py:3032` asserts success for the duplicate-target case in finding 1. The fixture assigns both findings to §2, and the test never inspects the resulting receipt. A correct uniqueness check would turn this test red. The success case needs two distinct resolving targets and a read-back assertion for both.

## Optimization: approve

LENS adversarial: findings  
LENS integration: findings  
LENS source-defect: findings  
LENS consistency: findings  
LENS quality: findings  
LENS optimization: clean  
HIGHEST: P1  
P2 DATA: no  
OVERALL: needs-attention

## Writer note: round 1

All seven findings checked against the code and real; all fixed in 9f45c6b9, each with a test.

## Completion review: astra (`gpt-6.2-astra` via `codex`)

- Writer: claude
- Run: 2026-11-19T09:16:59Z
- Candidate: c21f7e65748594a2f226f1183f6950adf7b2303c
- Effort: low
- Lenses: plan-delivery, record
- Lines: 28
- Digest: 087c9e3d68408154

## Part 1. Completeness

1. **present**. The installed and template pins set the ordinary and data caps to 3 and 6. The reader validates both values, and `--caps` prints them. The CLI test uses 2 and 4, so hard-coded defaults would fail. Evidence in `.conclave/reviewers.toml:61`, `scripts/review_pin.py:614`, and `scripts/tests/test_review_pin.py:877`.
2. **present**. The prompts request per-finding tags, including for a project-owned prompt with a lensless completion step. Dispatcher tests cover an absent data declaration, an explicit contradiction, and admission of the last required reconciliation of each kind. Evidence in `scripts/review_pin.py:913` and `scripts/tests/test_three_pass.py:734`.
3. **present**. For single-line, status-first findings, the stamp tests cover both cap boundaries, P1 refusal, an overlong chain, missing and shared filing targets, and read-back of two distinct targets. The cap check is conditional on the section’s pinned schedule. Evidence in `scripts/lib/todo_graph.py:866`, `scripts/lib/todo_graph.py:890`, and `tests/test_todo_graph.py:3016`.
4. **missing-in-scope**. A numbered finding can put its severity on a continuation line. I passed the candidate parser `1. Open.` followed by an indented `P2 data: failed save reported as successful.`, then `2. Open (P2): other.` It returned only finding 2. In that case a contradictory `P2 DATA: no` escapes detection, the shorter cap applies, and filing finding 2 alone satisfies the ownership check. The reconciliation prompt requires numbering and tagging but does not require the tag on the first line. Evidence in `docs/reconciliation-review-prompt.md` under “Reply format”, `scripts/review_pin.py:635`, and `scripts/lib/todo_graph.py:896`.
5. **missing-in-scope**. A closed finding can still block the stamp. I passed the parser `1. P2 (closed): fixed.` followed by `2. Open (P2): pending.` It returned both findings as open. The writer must then file a spurious section for a repair the reviewer already verified. The regression covers only the status-first spelling `Closed (P2 data)`. Evidence in `scripts/review_pin.py:636` and `tests/test_todo_graph.py:3047`.
6. **present**. The rule appears in the reviewer kit and writer skill, with a copy check in `tests/test_forge.py:1078`. Commit `bff0269d` records the reviewer suite, gated stamp suite, skill checks and both required mutation failures. Commit `9f45c6b9` separately records the narrower post-repair runs. I verified the two parser results directly. The suite results are from those commit records.
7. **missing-in-scope**. The round-one record says all seven findings were fixed, including the closed-finding defect. Its test establishes one word order. The second probe above reproduces the same defect with severity first, so the closure claim exceeds the evidence. Evidence in `docs/reviews/00-reviewer/D00-T01-s10.md:84`, `scripts/tests/test_review_pin.py:772`, and `tests/test_todo_graph.py:3047`.

## Part 2. Excellence

The strongest direct alternative for these two lenses is a writer manually reconciling the final numbered review against the filed TODO sections. The writer can read the whole item, recognize its status, and verify its owner before stamping.

1. **in-scope**. The automated check loses an owner that manual reconciliation would retain and demands an owner that manual reconciliation would omit. The target is exact agreement on both observed replies. The multiline reply must yield findings 1 and 2, with finding 1 classified as data. The severity-first closed reply must yield only finding 2.

## Gaps

1. **missing-in-scope | P1**. A continuation-line tag lets the stamp accept a shorter cap and leave an open data finding without an owner.
2. **missing-in-scope | P2**. A severity-first closed finding forces the writer to file a section for completed work.
3. **missing-in-scope | P2**. The round-one closure record overstates what its closed-finding regression proves.
4. **in-scope | P1**. Match manual reconciliation on both reproduced replies, including finding number, open status and data classification.

LENS plan-delivery: findings  
LENS record: findings  
HIGHEST: P1  
P2 DATA: no  
COMPLETION: gaps

- Implemented: 4 and excellence 1, a finding is read whole (a tag on a continuation line is its own), in df6513c4
- Implemented: 5, a finding is closed when its heading says so in any word order (`P2 (closed):`), in df6513c4
- Implemented: 7, corrected: the round-1 note said the closed-finding defect was fixed; its test proved one word order only. The parser change and both probes as tests are in df6513c4

## Reconciliation review: astra (`gpt-6.2-astra` via `codex`)

- Writer: claude
- Run: 2026-11-19T09:23:02Z
- Candidate: 64d6a6354890ffe1630408b67717cc77b9d45bf8
- Effort: low
- Lenses: adversarial, integration, plan-delivery, record
- Lines: 16
- Digest: ff65262a84eb73ed

The section contract is unchanged. The repair covers all four original gaps, but introduces a P1 that can let an open data finding pass without an owner.

1. **Closed.** The continuation-line regression checks that finding 1 is classified as data, finding 2 is ordinary, and `P2 DATA: no` is rejected. The writer records the repair in `docs/reviews/00-reviewer/D00-T01-s10.md:125`. Evidence in `scripts/tests/test_review_pin.py:778`.
2. **Closed.** The stamp regression supplies `P2 (closed)` followed by an open P2, files only finding 2, and checks that the stamp records exactly that target. Evidence in `tests/test_todo_graph.py:3045` and `docs/reviews/00-reviewer/D00-T01-s10.md:126`.
3. **Closed.** The writer explicitly corrects the round-one claim and identifies the word order the earlier test missed. The new test covers that order. Evidence in `docs/reviews/00-reviewer/D00-T01-s10.md:127` and `scripts/tests/test_review_pin.py:781`.
4. **Closed.** The regression asserts the exact finding numbers and data flags for both replies reproduced by the completion reviewer. Evidence in `scripts/tests/test_review_pin.py:779`, `scripts/tests/test_review_pin.py:782`, and `docs/reviews/00-reviewer/D00-T01-s10.md:125`.

**New finding, P1.** The parser treats any occurrence of `closed` before the first colon as the finding’s status. I reproduced this with `1. Open (P2 data). A failed save is marked closed.` followed by `2. Open (P2): other.` and `P2 DATA: no`. The parser returned only `[('2', False)]`, and the contradiction check returned `False`. The stamp can therefore use the shorter cap and require an owner only for finding 2. Read the status from the finding’s label so evidence describing a closed record cannot override an explicit `Open`. Evidence in `kits/reviewer/templates/scripts/review_pin.py:651`, `scripts/review_pin.py:661`, `scripts/lib/todo_graph.py:891`, and `scripts/lib/todo_graph.py:898`.

LENS adversarial: findings  
LENS integration: findings  
LENS plan-delivery: findings  
LENS record: clean  
HIGHEST: P1  
P2 DATA: no  
RECONCILIATION: gaps

- Implemented: reconciliation 1's finding by redesign (the parser class reopened), in aa6e1fde: a finding's status is read from its label at the start only and the reading errs toward holding (a misread files an extra section or keeps the longer cap, never loses an open data finding)

## Reconciliation review: astra (`gpt-6.2-astra` via `codex`)

- Writer: claude
- Run: 2026-11-19T09:25:58Z
- Candidate: 76b2258a1c9133f18209786986731f5cd44671d6
- Effort: low
- Lenses: adversarial, integration, plan-delivery, record
- Lines: 15
- Digest: 85d567808a36ab3c

The section contract is unchanged at `todo/00-reviewer/TODO-01-three-pass-review.md:348`. One completion gap remains open.

1. **Closed.** A continuation-line `P2 data` tag stays with finding 1. The regression checks both finding numbers, their data classifications and rejection of a contradictory `P2 DATA: no`. `scripts/tests/test_review_pin.py:778`, `docs/reviews/00-reviewer/D00-T01-s10.md:125`
2. **Open, P2.** The stamp test covers `P2 (closed)`, but the severity-first label `P2 data (closed)` still fails. On the repaired candidate, I supplied `1. P2 data (closed): save failure fixed.` followed by `2. Open (P2): other.` The parser returned `[('1', True), ('2', False)]` and rejected the correct `P2 DATA: no`. The label matcher expects the parenthesis immediately after the severity and misses the `data` qualifier. This blocks a valid review despite the writer’s claim that either word order works. `scripts/review_pin.py:636`, `tests/test_todo_graph.py:3045`, `docs/reviews/00-reviewer/D00-T01-s10.md:126`
3. **Closed.** The writer corrected the historical round-one claim and identified the word order its test had missed. `docs/reviews/00-reviewer/D00-T01-s10.md:127`, `scripts/tests/test_review_pin.py:781`
4. **Closed.** The regression asserts the exact finding numbers and data classifications for both replies reproduced by the completion reviewer. `scripts/tests/test_review_pin.py:779`, `scripts/tests/test_review_pin.py:782`, `docs/reviews/00-reviewer/D00-T01-s10.md:125`
5. **Closed.** The earlier reconciliation’s open data finding survives the word `closed` in its evidence. The regression checks that both findings remain open and the contradictory declaration is rejected. `scripts/tests/test_review_pin.py:786`, `docs/reviews/00-reviewer/D00-T01-s10.md:156`

LENS adversarial: clean  
LENS integration: findings  
LENS plan-delivery: findings  
LENS record: findings  
HIGHEST: P2  
P2 DATA: no  
RECONCILIATION: gaps

- Implemented: reconciliation 2's gap 2, in 3b03f4e8 and 20f8eca2: the closed label takes the data qualifier (`P2 data (closed)`), with its probe as a test

## Reconciliation review: astra (`gpt-6.2-astra` via `codex`)

- Writer: claude
- Run: 2026-11-19T09:30:35Z
- Candidate: 2b48bbfd74b915c0e4b111e164b7be19a5e4d89f
- Effort: low
- Lenses: adversarial, integration, plan-delivery, record
- Lines: 18
- Digest: 8da37d8975ea1f8a

1. **closed**. The continuation-line severity stays with finding 1. The regression checks both finding numbers, classifies only finding 1 as data, and rejects the contradictory declaration. `scripts/tests/test_review_pin.py:778`, `docs/reviews/00-reviewer/D00-T01-s10.md:125`
2. **closed**. For `P2 (closed)`, the stamp regression files only the remaining open finding and verifies the recorded target. `tests/test_todo_graph.py:3045`, `docs/reviews/00-reviewer/D00-T01-s10.md:126`
3. **closed**. The writer corrected the round-one closure claim and identified the severity-first spelling the original test missed. `docs/reviews/00-reviewer/D00-T01-s10.md:127`, `scripts/tests/test_review_pin.py:781`
4. **closed**. The parser returns the exact finding numbers and data classifications required for both replies reproduced by the completion reviewer. `scripts/tests/test_review_pin.py:779`, `scripts/tests/test_review_pin.py:782`, `docs/reviews/00-reviewer/D00-T01-s10.md:125`
5. **closed**. The first reconciliation’s open data finding survives the word `closed` in its evidence, and the contradictory declaration is rejected. `scripts/tests/test_review_pin.py:790`, `docs/reviews/00-reviewer/D00-T01-s10.md:156`
6. **closed**. The second reconciliation’s `P2 data (closed)` label now leaves only finding 2 open and accepts `P2 DATA: no`. I ran the focused regression on the repaired candidate. `scripts/tests/test_review_pin.py:784`, `docs/reviews/00-reviewer/D00-T01-s10.md:184`

**New finding, P2.** Replaying the repository’s actual second reconciliation on the repaired candidate returned `[('2', True)]` and flagged its `P2 DATA: no` declaration as contradictory. Finding 2 is explicitly labeled ordinary `Open, P2`. Its evidence quotes `P2 data (closed)` to explain the parser defect. The repair searches the whole body for `P2 data`, so the quoted example overrides the finding’s own classification and the stamp rejects a valid review. The parser needs to distinguish a severity tag on a continuation line from a quoted tag in the evidence. `docs/reviews/00-reviewer/D00-T01-s10.md:171`, `docs/reviews/00-reviewer/D00-T01-s10.md:181`, `scripts/review_pin.py:655`, `scripts/review_pin.py:663`, `scripts/lib/todo_graph.py:891`

The section contract is unchanged between the failed completion candidate and the repaired candidate. `todo/00-reviewer/TODO-01-three-pass-review.md:348`

LENS adversarial: findings  
LENS integration: findings  
LENS plan-delivery: findings  
LENS record: clean  
HIGHEST: P2  
P2 DATA: no  
RECONCILIATION: gaps

- Implemented: reconciliation 3's finding by redesign (the classification class reopened), in 8bb099a1: the data cap reads every mention of `P2 data` (an ambiguity costs the longer cap), and only a finding labelled `P2 data` on its first line beside `P2 DATA: no` is refused, so quoted evidence never refuses a valid review

## Reconciliation review: astra (`gpt-6.2-astra` via `codex`)

- Writer: claude
- Run: 2026-11-19T09:42:38Z
- Candidate: b5725c5bf4c33a8b88408ebc5d80dbde145fa402
- Effort: low
- Lenses: adversarial, integration, plan-delivery, record
- Lines: 17
- Digest: bf2c39dee76032c6

The section contract is unchanged. Two read-only replays on `b5725c5` show that the repair still mishandles the distinction between a finding’s own tag and a tag quoted in its evidence.

1. **Open, P1.** The continuation-line probe now retains both finding numbers and selects the data cap, closing the ownership hole. But it recognizes finding 1 as data and still accepts `P2 DATA: no` as consistent. The unchanged contract requires dispatch to mark that reply incomplete and stamp to refuse it. The new test explicitly expects the opposite. `docs/reviews/00-reviewer/D00-T01-s10.md:125`, `todo/00-reviewer/TODO-01-three-pass-review.md:364`, `todo/00-reviewer/TODO-01-three-pass-review.md:365`, `scripts/tests/test_review_pin.py:765`, `scripts/review-dispatch.py:608`, `scripts/lib/todo_graph.py:891`
2. **Closed.** The stamp regression supplies `P2 (closed)` followed by an open P2, files only finding 2, and checks the exact target in the receipt. `docs/reviews/00-reviewer/D00-T01-s10.md:126`, `tests/test_todo_graph.py:3045`
3. **Closed.** The writer corrected the round-one record to state which word order its test actually proved. The added regression covers the severity-first form. `docs/reviews/00-reviewer/D00-T01-s10.md:127`, `scripts/tests/test_review_pin.py:791`
4. **Closed.** For the completion review’s two original probes, the parser matches the manual finding numbers, open status and data classification. The contradictory-footer decision remains open under item 1. `docs/reviews/00-reviewer/D00-T01-s10.md:125`, `scripts/tests/test_review_pin.py:786`
5. **Closed.** An explicit open label survives the word `closed` in the evidence. The regression retains both open findings and their respective classifications. `docs/reviews/00-reviewer/D00-T01-s10.md:156`, `scripts/tests/test_review_pin.py:802`
6. **Closed.** The `P2 data (closed)` regression excludes the repaired finding and leaves only ordinary finding 2 open. `docs/reviews/00-reviewer/D00-T01-s10.md:184`, `scripts/tests/test_review_pin.py:795`
7. **Open, P2.** Replaying the recorded second reconciliation still classified ordinary finding 2 as data, returning `[('2', True)]`. Dispatch now accepts the reply, but the quoted `P2 data (closed)` still selects the longer cap. The new integration test requires that incorrect classification. This can hold a valid filing past its ordinary cap. `docs/reviews/00-reviewer/D00-T01-s10.md:171`, `docs/reviews/00-reviewer/D00-T01-s10.md:215`, `scripts/review_pin.py:636`, `scripts/review_pin.py:659`, `scripts/tests/test_three_pass.py:774`

LENS adversarial: findings  
LENS integration: findings  
LENS plan-delivery: findings  
LENS record: findings  
HIGHEST: P1  
P2 DATA: no  
RECONCILIATION: gaps
