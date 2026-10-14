# Antigravity Output and Safety Rule

- Bound every shell command output (`Select-Object -First`, filtered test cases, or redirected logs to `R:\scratch` or `build/`).
- Treat `git status` as a concurrency lock: never write over unfamiliar uncommitted changes from another session without asking the user first.
- Never use em dashes or en dashes in authored Markdown or documentation prose. Write one line per paragraph and list item.
- Use atomic temporary-file-then-replace writes for all persistent data files.
- End code change reports with a `Layer:` line identifying the owning module.
