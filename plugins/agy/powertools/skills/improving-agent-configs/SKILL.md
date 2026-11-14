---
name: improving-agent-configs
description: >-
  Use when auditing, refactoring, or tightening AGENTS.md, GEMINI.md, CLAUDE.md, CODEX.md, SKILL.md, or Antigravity plugin bundles (plugin.json, hooks.json, rules, skills). Catches stale paths, context bloat, cross-agent leaks, and broken formatting rules.
---

# Improving Agent Configs

Keep instruction files (`AGENTS.md`, `GEMINI.md`, `CLAUDE.md`, `CODEX.md`), skills (`SKILL.md`), and Antigravity plugins lean, truthful, isolated, and directly actionable.

## Audit workflow

1. **Inventory configs and plugins**: locate root and subdirectory instruction files, skills, hooks, and `plugin.json` manifests across the target repo or home customization root.
2. **Evaluate against [quality-criteria.md](./references/quality-criteria.md)**: check every file for accurate commands/paths, owning-layer pointers, progressive disclosure, strict agent isolation, prose formatting, and table width caps.
3. **Propose targeted tightening before large rewrites**: list specific removals (stale rules, boilerplate the agent already knows), relocations (heavy docs moved into `references/`), and fixes with exact file paths.
4. **Validate plugins and gates**:
   - Run `agy plugin validate <plugin_dir> --strict` for Antigravity plugins.
   - Verify skill YAML frontmatter `name` matches folder name and `description` states clear triggers in third person.
   - Verify `AGENTS.md` / `GEMINI.md` rules have no YAML frontmatter and stay concise (`< 24 KB`, well under aggregate rule budgets).
   - Run any repository format or sync checks (such as `tests.test_forge` and `forge.py self-sync` in Conclave repositories).
5. **Report concrete changes**: summarize what became shorter, clearer, or newly verified with clickable file links.
