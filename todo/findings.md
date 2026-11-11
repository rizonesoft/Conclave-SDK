# Findings

Unscheduled defects noticed while working on another section. Record each entry with `file:line` and strike it with its `DNN TNN §N` reference once scheduled via `add-todo`.

- 2026-11-12, `kits/reviewer/templates/scripts/review-prompt.py:201`: `--candidate`, `--failed` and `--last` refuse an abbreviated SHA (`--last must be a full 40-character lowercase commit SHA, got '8969664'`), which cost a rerun in `D02 T01 §3`. Resolve any commit name with `git rev-parse --verify <name>^{commit}` and use the full SHA it prints, refusing only a name git cannot resolve.
