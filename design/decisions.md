# Design decisions

The owner's approval of the mockup and the answer to every question in `design/mockup/open-questions.md`. The plan (`docs/plans/2026-10-16-vscode-extension.md`) follows these; a later change to the design is a new dated entry here, applied to the mockup first.

## Approval

Approved: 2026-10-17, by the owner in the session, as it is, with no changes asked for.

- Frozen mockup source: `design/mockup/project/` at commit `22cdeed008ed6a573deb38ab8655f10d5deb31b0`.
- Frozen canvas: <https://claude.ai/artifact/RRxxX5W6pYFQ3b2Z4Fq2mv> version 22 (version id `1792187772-973c`). A later save from inside the page, version id `1792195601-ef7b`, carries the same `Main.dc.html` and `canvas.json` byte for byte.
- From here on, the mockup changes only through a dated entry below, applied to `design/mockup/project/` first and republished. The parity fixtures (`D02 T01 §11`) are exported from the current mockup source: the commit the latest dated entry below names, or the frozen commit above while there is none. The frozen commit stays the record of what the owner approved.

## Answers

1. Self-review warning (2026-10-17): warn whenever the reviewer's CLI is the writer's CLI, including a last-resort failover (option A). Superseded 2026-10-20 by "Reviewer routes" under Changes after approval: the pin now refuses such a route, so there is nothing left to warn about.
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

## Changes after approval

Each change is applied to `design/mockup/project/` first and republished to the same link.

### Reviewer routes (2026-10-20)

The owner, in the session: "the reviewers fallback, it should only be a different family reviewer + 1 fallback". The reviewer kit ships it (Conclave-SDK `9bd9cb1`, `1bcd0b7`): `load_pin` refuses a route that is not one reviewer and at most one fallback (`route 'claude' must list one reviewer and at most one fallback`), a reviewer of the writer's family (`... of the writer's own family; a review comes from a different family`), and a fallback of the reviewer's family (`... the fallback must be of a third family, not the reviewer's own`). The family is the CLI's: codex is OpenAI, agy Google, claude Anthropic. The shipped routes are claude `astra` then `gemini`, codex `gemini` then `sonnet`, gemini `astra` then `sonnet`.

Default taken for the editor, since the owner named the rule and not the screen: the route editor never offers a reviewer the pin would refuse, and a route that another edit breaks (a reviewer's CLI changed into the writer's family or its fallback's) shows `load_pin`'s refusal inline at the route row with Save off. A route row holds two chips, the reviewer and the fallback, and has no add button when full. Its add menu greys out, with the reason, a reviewer of the writer's family ("same family as the writer") and, for the fallback, a reviewer of the first chip's family ("same family as the reviewer"). A pin edited outside the editor that breaks the rule opens with `load_pin`'s refusal inline at the route row (answer 3), Save disabled. Answer 1's warning is gone. Current mockup source, for the parity fixtures: `design/mockup/project/` at commit `ff78d23c6a9a777eb16ffa1c24f3f490c476904b` (canvas version 26; the route change itself landed in `e30ea2f`, version 25). Applied to `design/mockup/project/Main.dc.html` in that commit and republished to the same link as canvas version 25 (version id `1792483021-13bf`); the live files matched the frozen commit byte for byte before the republish. The no-pin screen's description of the shipped pin still named the old three-reviewer chain and was corrected the same day while the interface SPEC was written (`D00 T01 §3`, `ff78d23`), and republished as version 26 (`1792485378-36d7`). Reversing it (warn instead of prevent) costs the add-menu rule in `D03 T01 §4` and the three refusal scenarios, and would let the editor offer routes the dispatcher refuses.

### Review findings on the SPEC and design spec (2026-10-20)

Independent review of `D00 T01 §3` and `§4` found states the design did not draw; each is a default taken by the writer, applied here first. Reversing any of them is a change to this file, the mockup and `design/SPEC.md`.

- A findings file `--list-rounds` cannot read back is a REVIEW ROUNDS row of its own (warning icon, the file name, `unreadable: not in the record format`, `Open {file}`), never dropped (`D06 T01 §3`).
- `load_pin` accepts any TOML layout of the pin (inline tables, quoted keys, arrays over several lines), but the editor edits only `[reviewers.<name>]` tables with one key per line and one-line route arrays (`docs/specs/2026-10-20-vscode-extension-design.md` section 2). A valid pin in another layout opens a read-only state, `This pin uses a layout the editor does not edit`, with `Open file` and `Retry`; the status bar reads `layout not editable` and REVIEWERS `valid; a layout the editor does not edit`. Rewriting the layout automatically was rejected: it would move or drop the owner's comments.
- The two badge backgrounds the theme has no variable for are colours the extension contributes (`conclave.badgeOkBackground`, `conclave.badgeErrorBackground`) with the mockup's values as their defaults, so the approved look stands and a theme can override it.
- The example round that no reviewer returned now skips two reviewers, as a route of one reviewer and one fallback can.
- Added the same day by `D00 T01 §6` (review round 3 of `§3`): in the `pin-layout` state REVIEWERS lists the reviewers and routes `--check-pin` returns, under its state row, since the pin is valid and reviews run; each reviewer's action is `Open reviewers.toml`, because no editor opens on that layout, and the view's description counts skipped reviewers as for a valid pin in the editor. The newer-schema state still lists none, since the extension does not know what a newer pin's entries mean. Reversing it hides who reviews while reviews run, and costs one condition in the mockup and `D06 T01 §4`.

Applied to `design/mockup/project/Main.dc.html` in `e37bd70` and republished to the same link as canvas version 27 (version id `1792496267-c8bd`); `design/screens/12-dark.png` and `12-light.png` were captured again from that version. Current mockup source, for the parity fixtures: `design/mockup/project/` at commit `e37bd70be836517a74e569fb231e9802352b2b0c` (canvas version 27).

## Other owner decisions

- Marketplace: no (2026-10-17). The extension is not listed on the Visual Studio Marketplace: the `.vsix` bundles every kit and `rizonetech/Conclave-SDK` is internal, so each version's `.vsix` is attached to a GitHub release of that repository and organization members install it from there (plan R22, `D04 T01 §6`).
- The SDK's own copy of the kits (2026-10-17): the SDK root keeps every file of the `base`, `todo` and `reviewer` kits, including base's `docs/agent-skills-and-rules-structure.md` and `scripts/verify-agent-tiers.mjs`, so `python forge.py sync . --include-scripts` stays the refresh command (`todo/findings.md`, `AGENTS.md:13`).
