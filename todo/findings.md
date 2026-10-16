# Findings

Unscheduled defects noticed while working on another section. Record each entry with `file:line` and strike it with its `DNN TNN §N` reference once scheduled via `add-todo`.

- `AGENTS.md:13`: the documented refresh, `python forge.py sync . --include-scripts`, also writes the base kit's `docs/agent-skills-and-rules-structure.md` and `scripts/verify-agent-tiers.mjs` into the SDK root, which `5e36d31` removed on purpose (the SDK's `scripts/` is only the todo and reviewer kits' copy), and rewrites the CRLF installed skills as LF. Found 2026-10-16 while refreshing `scripts/todo-graph.py`; the two files were deleted again by hand. Every SDK-side section that refreshes a copy (D01 T01, D06 T01 §2 and §3) runs this command.
