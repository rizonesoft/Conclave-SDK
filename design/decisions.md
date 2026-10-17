# Design decisions

The owner's approval of the mockup and the answer to every question in `design/mockup/open-questions.md`. The plan (`docs/plans/2026-10-16-vscode-extension.md`) follows these; a later change to the design is a new dated entry here, applied to the mockup first.

## Approval

Approved: 2026-10-17, by the owner in the session, as it is, with no changes asked for.

- Frozen mockup source: `design/mockup/project/` at commit `22cdeed008ed6a573deb38ab8655f10d5deb31b0`.
- Frozen canvas: <https://claude.ai/artifact/RRxxX5W6pYFQ3b2Z4Fq2mv> version 22 (version id `1792187772-973c`). A later save from inside the page, version id `1792195601-ef7b`, carries the same `Main.dc.html` and `canvas.json` byte for byte.
- From here on, the mockup changes only through a dated entry below, applied to `design/mockup/project/` first and republished; the parity fixtures (`D02 T01 §11`) are exported from the frozen commit.

## Answers

1. Self-review warning (2026-10-17): warn whenever the reviewer's CLI is the writer's CLI, including a last-resort failover (option A).
2. Errors (2026-10-17): one error at a time; `load_pin` and the `{"ok": false, "error": ...}` contract stay as they are (option A).
3. Refused pins (2026-10-17): faults inside a parsable pin open the editor with an inline error; TOML that does not parse and a wrong top level show the "pin refused" screen (option A).
4. Editor type (2026-10-17): a webview panel opened by `conclave.openReviewers`, with its own Save, Discard, temp-file-then-rename write and stale-disk check; unsaved edits show as "(unsaved)" in the panel title (option A).
5. Comments on save (2026-10-17): decided in the design spec (`D00 T01 §4`) after a spike over the fixture pins, preferring a narrow hand-written editor if no maintained library round-trips the shipped pin byte for byte.
6. Test reviewer (2026-10-17): ask before every run, naming the model, the CLI and the writer (option A).
7. Python (2026-10-17): `conclave.pythonPath`, then `py -3` and `python` on Windows, `python3` and `python` in WSL, 3.11 or later; a set but unusable setting is an error, never a silent fallback (option A).
8. Reviewer kit source (2026-10-16): bundled in the `.vsix` from the build commit, with a local checkout (`conclave.sdkPath`) and GitHub (`conclave.sdkRef`) as overrides.
9. GitHub fetch (2026-10-17): VS Code's GitHub sign-in with the `repo` scope and no stored token, the ref resolved to a SHA, the tarball cached per SHA and extracted refusing `..`, absolute paths and links, and `forge.py` run only after a confirmation naming the repository and SHA (option A).
10. Entry points (2026-10-17): all four, the Command Palette command, the Explorer context menu item, the editor title button and the status bar item (option A).
11. Kits in the UI (2026-10-16): a Conclave view container in the Activity Bar with its own icon; the installer opens in that side bar; update and new repository use native quick picks; the view shows the current repository only.
12. Undo of a kit install (2026-10-17): no uninstall in the extension until forge has one; the operator's git is the undo, and the hash check proves the protected files did not change (option A).
13. Review rounds source (2026-10-17): `review-dispatch.py --list-rounds --json` in the reviewer kit, beside `record` (option A, `D06 T01 §3`).
14. Side bar layout (2026-10-16): the Kits tree stays its own section, with one section per feature under it, each shown only while its kit is in the folder.

## Other owner decisions

- The SDK's own copy of the kits (2026-10-17): the SDK root keeps every file of the `base`, `todo` and `reviewer` kits, including base's `docs/agent-skills-and-rules-structure.md` and `scripts/verify-agent-tiers.mjs`, so `python forge.py sync . --include-scripts` stays the refresh command (`todo/findings.md`, `AGENTS.md:13`).
