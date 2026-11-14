# D01 T02 §6: the skill copy differences, read and sorted

Measured at `489775c`, the section's first commit, before any copy changed. A changed line is one that `diff <claude file> <copy>` marks `<` or `>`.

| Kit | Skill file | `.agents` lines | `.codex` lines |
| --- | --- | --- | --- |
| `reviewer` | `independent-review/SKILL.md` | 2 | 0 |
| `todo` | `add-todo/SKILL.md` | 2 | 2 |
| `todo` | `create-todo/SKILL.md` | 6 | 4 |
| `todo` | `groom-plan/SKILL.md` | 2 | 2 |
| `todo` | `process-phase/SKILL.md` | 10 | 10 |
| `todo` | `process-plan/SKILL.md` | 90 | 67 |
| `todo` | `process-todo-file/SKILL.md` | 2 | 2 |
| `todo` | `process-todo-section/SKILL.md` | 8 | 8 |
| `todo` | `review-todo-section/SKILL.md` | 4 | 4 |
| `unattended` | `unattended-run/SKILL.md` | 2 | 2 |
| | Total | 128 over 10 files | 101 over 9 files |

## Intended differences, each declared in a patch

- The agent's name in each skill's `description` (`in Antigravity`, `in Codex`): the eight todo skills.
- The `--writer` value in a command the agent runs for itself (`agy`, `codex`): `independent-review` for Antigravity, `process-todo-section` for both.
- `$ARGUMENTS`, a Claude Code variable, against `<section-ref>` with the sentence that explains it: `process-todo-section` and `review-todo-section`.
- The agent's own skill folder in a path (`.agents/skills/create-todo/todo-template.md`, `.codex/skills/create-todo/todo-template.md`): `create-todo`.
- The file that wires the agent's Stop hook (`.agents/hooks.json`, `.codex/hooks.json`): `unattended-run`.
- The run guard, which is a different mechanism per agent (Claude Code's `CronCreate` heartbeat and session id, Antigravity's `schedule` timer and conversation id, Codex's Stop hook alone): the whole Run guard block and two later sentences of `process-plan`, and four passages of `process-phase`.

## Accidental differences, each resolved

1. `add-todo` description. Claude: "Search the tree for an existing home first". Both copies: "Search the todo/ tree for an existing home first". The copies hold the better text (the tree is named), so the Claude file takes it.
2. `create-todo` step 2, Antigravity only. Copy: "Copy `todo/templates/TODO-template.md` (or `.agents/skills/create-todo/todo-template.md`)". Claude and Codex: "Copy `<agent>/skills/create-todo/todo-template.md` (same file as `todo/templates/TODO-template.md`)". The copy takes the Claude wording with its own folder, which is the intended difference.
3. `create-todo` Frontmatter item, Antigravity only. Copy: "touches the frozen thread-safety or parity contract in the foundation plan". Claude and Codex: "touches the frozen thread-safety contract or another parity-frozen behavior". The copy takes the Claude text.
4. `process-phase` park and closeout markers, both copies (found by the review round, first read as intended). Copies: "`PARKED <UTC stamp> <one-line reason>`" and "a `## Closeout` heading". Claude: "`PARKED <UTC stamp> run=<run id> <one-line reason>` line in the run file (the run id `acquire` printed, so the Stop hook lets the turn end)" and "a `## Closeout run=<run id>` heading". The run guard's `end` refuses a marker without the run id for every agent, so the copies take the Claude text; who ends the guard stays the intended difference.

## The full diff of the skill trees since `489775c`

It holds the four resolutions above and nothing else: every other line of every copy is what it was, now written by the generator from the Claude file and its patch.

```diff
diff --git a/kits/todo/templates/.agents/skills/create-todo/SKILL.md b/kits/todo/templates/.agents/skills/create-todo/SKILL.md
index 611453e..2e26c68 100644
--- a/kits/todo/templates/.agents/skills/create-todo/SKILL.md
+++ b/kits/todo/templates/.agents/skills/create-todo/SKILL.md
@@ -15,9 +15,9 @@ Name the domain and the next free `TODO-NN` number in it (numbers are local to t
 
 ### 2. Author from the template
 
-Copy `todo/templates/TODO-template.md` (or `.agents/skills/create-todo/todo-template.md`) to `todo/<NN-domain>/TODO-NN-<short-name>.md` and fill every part:
+Copy `.agents/skills/create-todo/todo-template.md` (same file as `todo/templates/TODO-template.md`) to `todo/<NN-domain>/TODO-NN-<short-name>.md` and fill every part:
 
-- **Frontmatter:** `schema_version: 1`, a globally unique kebab-case `id` (it survives renames and never changes once referenced), `domain` matching the directory, `status: draft` until the file is reviewed then `active`, `title`. Optional: `depends_on` (whole files that must fully ship first; prefer section edges), `frozen: true` (touches the frozen thread-safety or parity contract in the foundation plan), `track` (the milestone, e.g. `M1`).
+- **Frontmatter:** `schema_version: 1`, a globally unique kebab-case `id` (it survives renames and never changes once referenced), `domain` matching the directory, `status: draft` until the file is reviewed then `active`, `title`. Optional: `depends_on` (whole files that must fully ship first; prefer section edges), `frozen: true` (touches the frozen thread-safety contract or another parity-frozen behavior), `track` (the milestone, e.g. `M1`).
 - **Goal:** one paragraph, plain terms, true when the file is done.
 - **Current state:** what exists right now, measured, with real paths and real gaps.
 - **Inputs:** the plan and SPEC sections, existing files with what each section consumes, and `-> XREF:` lines to related work.
diff --git a/kits/todo/templates/.agents/skills/process-phase/SKILL.md b/kits/todo/templates/.agents/skills/process-phase/SKILL.md
index 2f8e1b4..205173a 100644
--- a/kits/todo/templates/.agents/skills/process-phase/SKILL.md
+++ b/kits/todo/templates/.agents/skills/process-phase/SKILL.md
@@ -64,11 +64,11 @@ Long jobs never stall the run:
 - After launching a background job, confirm within a few minutes that its process exists and its output file is growing or it has finished. Never wait on a job whose process is gone: a job that ended without its result (killed, no output, no notification) is relaunched once, alone, and the relaunch recorded in the findings file and the run file; a second loss is a Critical event, and the row continues with the next step that does not need that result or parks as a leftover.
 - An idle wait longer than 15 minutes with no job alive is a stall: re-check the job, resume the row, and record it.
 
-Skip rows whose `resolve` is not exit 0 here, and rows `resolve --have auto` holds for a host this session does not meet (exit 4, with the host in `missing_needs`; step 1.3 records which), and re-check them after each stamp: the graph moves as rows flip. When every remaining open row is a leftover, the phase parks: write a column-0 `PARKED <UTC stamp> <one-line reason>` line in the run file followed by the park record (each leftover, what blocks it, where the blocker lives), commit the run file, and return to `process-plan` (or end, if pinned).
+Skip rows whose `resolve` is not exit 0 here, and rows `resolve --have auto` holds for a host this session does not meet (exit 4, with the host in `missing_needs`; step 1.3 records which), and re-check them after each stamp: the graph moves as rows flip. When every remaining open row is a leftover, the phase parks: write a column-0 `PARKED <UTC stamp> run=<run id> <one-line reason>` line in the run file (the run id `acquire` printed, so the Stop hook lets the turn end) followed by the park record (each leftover, what blocks it, where the blocker lives), commit the run file, and return to `process-plan` (or end, if pinned).
 
 ## Step 4: closeout
 
-When the phase table is all `[x]`: `process-todo-file` on any file the phase exhausted, re-run the full test suite once, confirm `query stats` and the regenerated plan show the phase complete, write the closeout under a `## Closeout` heading in the run file (what shipped, what was repaired, what was learned), commit, and report. A phase is complete when its table says so and the closeout is written: not before.
+When the phase table is all `[x]`: `process-todo-file` on any file the phase exhausted, re-run the full test suite once, confirm `query stats` and the regenerated plan show the phase complete, write the closeout under a `## Closeout run=<run id>` heading in the run file (what shipped, what was repaired, what was learned), commit, and report. A phase is complete when its table says so and the closeout is written: not before.
 
 ## Guardrails
 
diff --git a/kits/todo/templates/.claude/skills/add-todo/SKILL.md b/kits/todo/templates/.claude/skills/add-todo/SKILL.md
index b6cc70b..534afc0 100644
--- a/kits/todo/templates/.claude/skills/add-todo/SKILL.md
+++ b/kits/todo/templates/.claude/skills/add-todo/SKILL.md
@@ -1,6 +1,6 @@
 ---
 name: add-todo
-description: Front door for new work. Search the tree for an existing home first, then route to an existing section, a new section, or a whole new file via create-todo. Use whenever work needs capturing.
+description: Front door for new work. Search the todo/ tree for an existing home first, then route to an existing section, a new section, or a whole new file via create-todo. Use whenever work needs capturing.
 ---
 
 # Add TODO
diff --git a/kits/todo/templates/.codex/skills/process-phase/SKILL.md b/kits/todo/templates/.codex/skills/process-phase/SKILL.md
index 9ba3c49..7a57a96 100644
--- a/kits/todo/templates/.codex/skills/process-phase/SKILL.md
+++ b/kits/todo/templates/.codex/skills/process-phase/SKILL.md
@@ -64,11 +64,11 @@ Long jobs never stall the run:
 - After launching a background job, confirm within a few minutes that its process exists and its output file is growing or it has finished. Never wait on a job whose process is gone: a job that ended without its result (killed, no output, no notification) is relaunched once, alone, and the relaunch recorded in the findings file and the run file; a second loss is a Critical event, and the row continues with the next step that does not need that result or parks as a leftover.
 - An idle wait longer than 15 minutes with no job alive is a stall: re-check the job, resume the row, and record it.
 
-Skip rows whose `resolve` is not exit 0 here, and rows `resolve --have auto` holds for a host this session does not meet (exit 4, with the host in `missing_needs`; step 1.3 records which), and re-check them after each stamp: the graph moves as rows flip. When every remaining open row is a leftover, the phase parks: write a column-0 `PARKED <UTC stamp> <one-line reason>` line in the run file followed by the park record (each leftover, what blocks it, where the blocker lives), commit the run file, and return to `process-plan` (or end, if pinned).
+Skip rows whose `resolve` is not exit 0 here, and rows `resolve --have auto` holds for a host this session does not meet (exit 4, with the host in `missing_needs`; step 1.3 records which), and re-check them after each stamp: the graph moves as rows flip. When every remaining open row is a leftover, the phase parks: write a column-0 `PARKED <UTC stamp> run=<run id> <one-line reason>` line in the run file (the run id `acquire` printed, so the Stop hook lets the turn end) followed by the park record (each leftover, what blocks it, where the blocker lives), commit the run file, and return to `process-plan` (or end, if pinned).
 
 ## Step 4: closeout
 
-When the phase table is all `[x]`: `process-todo-file` on any file the phase exhausted, re-run the full test suite once, confirm `query stats` and the regenerated plan show the phase complete, write the closeout under a `## Closeout` heading in the run file (what shipped, what was repaired, what was learned), commit, and report. A phase is complete when its table says so and the closeout is written: not before.
+When the phase table is all `[x]`: `process-todo-file` on any file the phase exhausted, re-run the full test suite once, confirm `query stats` and the regenerated plan show the phase complete, write the closeout under a `## Closeout run=<run id>` heading in the run file (what shipped, what was repaired, what was learned), commit, and report. A phase is complete when its table says so and the closeout is written: not before.
 
 ## Guardrails
 
```
