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

## The full diff of the skill trees since `489775c`

It holds the three resolutions above and nothing else: every other line of every copy is what it was, now written by the generator from the Claude file and its patch.

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
```
