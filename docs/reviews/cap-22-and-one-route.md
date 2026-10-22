## Round 1: sol (`gpt-6.1-sol` via `codex`)

- Writer: claude
- Run: 2026-10-22T11:14:48Z
- Effort: xhigh
- Lines: 21
- Digest: 41db7cdefc6fafca

### adversarial: needs-attention

1. [kits/todo/templates/scripts/lib/todo_graph.py:625](R:/GitHub/Conclave-SDK/kits/todo/templates/scripts/lib/todo_graph.py:625) introduces unhandled `TypeError` paths. With otherwise valid stamp prerequisites, pass `reviews=None` or a review whose `verdict` is `[]` or `{}`. The base commit raises `Refused`; the candidate crashes before reaching the existing type checks. Reproduced in memory against both revisions. Validate the container and verdict types before iteration and set membership. The installed script has the same defect.

### consistency: advisory

2. [kits/reviewer/templates/.codex/skills/independent-review/agents/openai.yaml:3](R:/GitHub/Conclave-SDK/kits/reviewer/templates/.codex/skills/independent-review/agents/openai.yaml:3) sets `short_description` to 74 characters, exceeding the documented 64-character maximum. Reproduce by measuring the decoded string. Shorten both the template and installed copy.

### integration: needs-attention

3. [kits/reviewer/templates/.codex/skills/independent-review/SKILL.md:20](R:/GitHub/Conclave-SDK/kits/reviewer/templates/.codex/skills/independent-review/SKILL.md:20) unconditionally instructs Codex to use `--writer claude`. Following this skill for Codex-authored changes bypasses the intended missing-route refusal: the dispatcher selects GPT and labels the writer Claude, allowing review by the writer’s model family. An in-memory dispatcher probe confirmed that `claude` selects Sol while `codex` refuses. Preserve the actual writer identity and stop unsupported writers. The Antigravity skill and installed copies contain the same instruction.

### source-defect: needs-attention

Finding 3 contradicts [kits/reviewer/README.md:11](R:/GitHub/Conclave-SDK/kits/reviewer/README.md:11), which explicitly requires Codex and Gemini work to refuse. Changing the writer argument defeats that contract.

### record: advisory

The historical full-suite pass claims were not independently verified. I used read-only probes; executing those suites would create test fixtures, contrary to the no-file-modification instruction.

OVERALL: needs-attention

## Round 2: sol (`gpt-6.1-sol` via `codex`)

- Writer: claude
- Run: 2026-10-22T11:27:00Z
- Effort: xhigh
- Lines: 15
- Digest: 3194ad7d9f8b39ba

### adversarial: approve

### consistency: advisory

`kits/reviewer/templates/.codex/skills/independent-review/SKILL.md:23` still hard-codes `--writer claude` beneath the corrected actual-writer instruction. Label this example Claude-only or use an actual-writer placeholder to remove ambiguity. The Antigravity template and installed copies have the same example.

### integration: approve

### source-defect: approve

### record: advisory

The commit’s full-suite pass, skip counts, and external-repository receipt-validation claims were not independently reproduced. Verification used read-only, in-memory probes; the suites create fixture files.

OVERALL: approve
