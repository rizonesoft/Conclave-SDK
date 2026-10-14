# AgentForge TODO Workflow Plugin Rules

- Follow the TODO graph lifecycle: `add-todo`, `create-todo`, `process-todo-section`, `review-todo-section`, `process-todo-file`, `process-phase`, `process-plan`, and `groom-plan`.
- Never hand-edit `todo/implementation-plan.md` or hand-flip Implementation Order checkboxes; always use `python scripts/todo-graph.py stamp` and `plan --sync`.
- Write one line per paragraph and list item in Markdown prose, with no em dashes or en dashes.
