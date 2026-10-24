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

Superseded by One reviewer per route (2026-10-21) below.

The owner, in the session: "the reviewers fallback, it should only be a different family reviewer + 1 fallback". The reviewer kit ships it (Conclave-SDK `9bd9cb1`, `1bcd0b7`): `load_pin` refuses a route that is not one reviewer and at most one fallback (`route 'claude' must list one reviewer and at most one fallback`), a reviewer of the writer's family (`... of the writer's own family; a review comes from a different family`), and a fallback of the reviewer's family (`... the fallback must be of a third family, not the reviewer's own`). The family is the CLI's: codex is OpenAI, agy Google, claude Anthropic. The shipped routes are claude `astra` then `gemini`, codex `gemini` then `sonnet`, gemini `astra` then `sonnet`.

Default taken for the editor, since the owner named the rule and not the screen: the route editor never offers a reviewer the pin would refuse, and a route that another edit breaks (a reviewer's CLI changed into the writer's family or its fallback's) shows `load_pin`'s refusal inline at the route row with Save off. A route row holds two chips, the reviewer and the fallback, and has no add button when full. Its add menu greys out, with the reason, a reviewer of the writer's family ("same family as the writer") and, for the fallback, a reviewer of the first chip's family ("same family as the reviewer"). A pin edited outside the editor that breaks the rule opens with `load_pin`'s refusal inline at the route row (answer 3), Save disabled. Answer 1's warning is gone. Current mockup source, for the parity fixtures: `design/mockup/project/` at commit `ff78d23c6a9a777eb16ffa1c24f3f490c476904b` (canvas version 26; the route change itself landed in `e30ea2f`, version 25). Applied to `design/mockup/project/Main.dc.html` in that commit and republished to the same link as canvas version 25 (version id `1792483021-13bf`); the live files matched the frozen commit byte for byte before the republish. The no-pin screen's description of the shipped pin still named the old three-reviewer chain and was corrected the same day while the interface SPEC was written (`D00 T01 §3`, `ff78d23`), and republished as version 26 (`1792485378-36d7`). Reversing it (warn instead of prevent) costs the add-menu rule in `D03 T01 §4` and the three refusal scenarios, and would let the editor offer routes the dispatcher refuses.

### Review findings on the SPEC and design spec (2026-10-20)

Independent review of `D00 T01 §3` and `§4` found states the design did not draw; each is a default taken by the writer, applied here first. Reversing any of them is a change to this file, the mockup and `design/SPEC.md`.

- A findings file `--list-rounds` cannot read back is a REVIEW ROUNDS row of its own (warning icon, the file name, `unreadable: not in the record format`, `Open {file}`), never dropped (`D06 T01 §3`).
- `load_pin` accepts any TOML layout of the pin (inline tables, quoted keys, arrays over several lines), but the editor edits only `[reviewers.<name>]` tables with one key per line and one-line route arrays (`docs/specs/2026-10-20-vscode-extension-design.md` section 2). A valid pin in another layout opens a read-only state, `This pin uses a layout the editor does not edit`, with `Open file` and `Retry`; the status bar reads `layout not editable` and REVIEWERS `valid; a layout the editor does not edit`. Rewriting the layout automatically was rejected: it would move or drop the owner's comments.
- The two badge backgrounds the theme has no variable for are colours the extension contributes (`conclave.badgeOkBackground`, `conclave.badgeErrorBackground`) with the mockup's values as their defaults, so the approved look stands and a theme can override it.
- The example round that no reviewer returned now skips two reviewers, as a route of one reviewer and one fallback can.
- Added the same day by `D00 T01 §6` (review round 3 of `§3`): in the `pin-layout` state REVIEWERS lists the reviewers and routes `--check-pin` returns, under its state row, since the pin is valid and reviews run; each reviewer's action is `Open reviewers.toml`, because no editor opens on that layout, and the view's description counts skipped reviewers as for a valid pin in the editor. Applied in `2bb8ac8` and republished as canvas version 28 (version id `1792497090-0628`); current mockup source, for the parity fixtures: `design/mockup/project/` at commit `2bb8ac858871565c287cb890168215af9801ba44` (canvas version 28), superseding the one named below. The newer-schema state still lists none, since the extension does not know what a newer pin's entries mean. Reversing it hides who reviews while reviews run, and costs one condition in the mockup and `D06 T01 §4`.

Applied to `design/mockup/project/Main.dc.html` in `e37bd70` and republished to the same link as canvas version 27 (version id `1792496267-c8bd`); `design/screens/12-dark.png` and `12-light.png` were captured again from that version. Current mockup source, for the parity fixtures: `design/mockup/project/` at commit `e37bd70be836517a74e569fb231e9802352b2b0c` (canvas version 27).

### Read-only kit view and agent import (2026-10-20)

The owner, in the session, after the working-copy incident recorded in `docs/phase-runs/2026-10-20-phase-1.md`: "what if we strip the import kits from the extension and just make it read only. Just give you the information about what kits are installed or partially installed. The reviewers config is still useful", then "would it not be best to give the agent pre-existing knowledge of the kits so a kit source would not need to be configured. We can keep this in sync with a mechanism that forces the extension to be updated when the kit/s change", then "restructure the plan this way, then resume".

- The extension never installs, updates or sets up a repository. The Kits view shows each kit's state (installed, partly installed, not installed) and health, read from forge, with no Install, Update kits or Set up a new repository action. The kit installer, the update flow and the new repository wizard (plan R28, R29, R31, R32) are dropped, and the shipped new-repository code (`D05 T01 §4`) is removed.
- Importing and updating kits is an agent's job: an `adopt-conclave` skill in the base kit runs `forge.py` with judgment (dry runs first, conflicts and merges with the operator, the protected files checked with git afterwards).
- The reviewer editor stays as approved: its one write is `.conclave/reviewers.toml`.
- No kit source is configured: the extension reads every folder against the SDK bundled in it (`forge.py` and `kits/` from its build commit). `conclave.sdkPath` stays as a developer override for working on the SDK itself. The GitHub source (`conclave.sdkRepository`, `conclave.sdkRef`, the archive download and extractor) is dropped, the default taken for the owner's "a kit source would not need to be configured".
- Kept in sync by two checks: a digest of the bundled `forge.py` and `kits/`, recorded in the extension with its version, and a test in this repository that fails when the kits change without a new extension version; and a stamp forge writes into each project on every install (`.conclave/kits.json`, each kit's digest and the SDK commit and date it came from), which the extension compares with its own, saying "set up with newer kits than this extension" (update the extension) or "older kits than this extension" (ask your agent to update the kits) instead of calling the kits partly installed.
- Defaults taken where the owner named the rule and not the screen: the no-pin state says the reviewer kit is not installed and shows the agent request and the equivalent `python forge.py kit <folder> reviewer` command, both copyable; the no-dispatcher and old-dispatcher states do the same with `python forge.py sync <folder> --include-scripts`; a folder with no kit says how to import with the agent. The Reviewers and Plan sections' inline Install actions become the same copyable request.

Applied to `design/mockup/project/` in `3e25681` and `904569c` (`D00 T01 §7`) and republished to the same link as canvas version 30 (version id `1792530805-ecb0`); `design/screens/7`, `9` and `12` were captured again and `13` (kit stamps) and `14` (a folder with no kit) added, in both themes. Review rounds 1 and 2 of `D00 T01 §7` corrected it in `714f669` and `fc7d57e`, republished as canvas version 33 (`1792533727-8f5e`), and screen 7 was captured again from the `NoPin` artboard. `D00 T01 §9` then closed a context menu whose file or kit row leaves the view (`3eff853`, canvas version 35, `1792534716-fa73`). Its review round 1 also closed a menu whose pane leaves, and kept it closed (`e1fd21b`, canvas version 37, `1792536848-58a1`). Round 2 closed a kit menu on a workspace or folder switch that removes its row (`97a68d7`, canvas version 38, `1792538337-93a5`). `D00 T01 §11` closed a kit menu when the KITS section collapses (`8d00e9c`, canvas version 39, `1792540203-fedc`). Current mockup source, for the parity fixtures: `design/mockup/project/` at commit `8d00e9cce8c59eae776319f8ad6c03bc8dff06cc` (canvas version 39), superseding the one named above. Reversing it costs restoring the dropped flows (five unbuilt sections and the removed `D05 T01 §4` code from git) and the GitHub source (`D02 T01 §7`, `§12` to `§15`).

### One reviewer per route (2026-10-21)

The owner, in the session: "The reviewers do not need a fallback. It creates more issues than its useful." This supersedes Reviewer routes (2026-10-20). A route names exactly one reviewer, of another model family than the writer; a reviewer that is not installed, fails, times out, returns nothing or replies `OVERALL: blocked` gives no review (exit 1, never an approval), and no other reviewer runs in its place.

- The reviewer kit's `load_pin` refuses any route that is not a list of one name (`route 'claude' must list exactly one reviewer`), a name no reviewer has (`route 'claude' must list a defined reviewer`) and a reviewer of the writer's family (unchanged). The third-family message is gone. The pin keeps `schema_version = 1` and the list form, so a one-entry pin written before stays valid.
- The shipped pin drops the Gemini reviewer, which was only ever a fallback: `astra` and `sonnet`, with claude `["astra"]`, codex `["sonnet"]` and gemini `["astra"]`. Antigravity reviewers stay supported for a pin that defines one.
- The dispatcher's summary keeps its `failover` key, which the Test reviewer panel reads; it now holds at most one entry, the reviewer that gave no review and why.
- Defaults taken for the editor, since the owner named the rule and not the screen: a route row holds one chip with a remove button and no order controls; the add menu shows only on an empty row and disables a reviewer of the writer's family; a hand-edited route with more than one name shows every entry with the refusal inline, so the extras can be removed. The `fallback` tag, `listed twice`, `Add the fallback` and the reasons `already in this route` and `same family as the reviewer` are gone (`design/SPEC.md` sections 3 to 5, `D03 T01 §4`).

Applied to `design/mockup/project/Main.dc.html` in the working copy; the hosted canvas is not yet republished and `design/screens/3-*.png` are not yet captured again from it.

### Reviewer-only extension (2026-10-21)

The owner, in the session: "We need to simplify the VS code extension more, we will add features for later; remove everything related to the kits from the extension and just keep reviewers features", then, asked what happens to the side bar: "Keep Reviewers + Review rounds". This narrows Read-only kit view and agent import (2026-10-20) without reversing its rule that the extension never writes kits.

- The extension shows no kits and runs no `forge.py`. Removed from the extension: the forge runner and its parsers (`D02 T01 §9`), the per-folder kit state (`§10`, `§18`), folder work (`§19`), kit health (`D05 T01 §3`), the SDK source and `conclave.sdkPath` (`D02 T01 §7`), and the bundled SDK digest with its drift test (`D05 T02 §2`). The removal is `D02 T01 §24`.
- Deferred until the kit features return, not dropped: the Kits view and health detail (`D05 T02 §3`, `§5`, `§6`, file status `draft`), and the Plan and WordPress site side bar sections (`D06 T01 §5`, `§7`). The mockup keeps drawing them as the design to come back to; the parity fixtures and the acceptance walk cover only the reviewer editor, Reviewers and Review rounds.
- Kept: the reviewer editor and everything under it (Python resolution, the dispatcher client and workspace states, the pin text model, candidate checks, atomic save, Test reviewer), its entry points, and a Conclave side bar holding only Reviewers and Review rounds, with no Kits tree and no section gated on kit state (Reviewers shows the pin state; Review rounds shows while `scripts/review-dispatch.py` exists).
- Kept in the SDK, outside the extension: `forge.py` with `digest` and the kit stamp `.conclave/kits.json` (`D05 T02 §1`, `§8`, `§9`), and the `adopt-conclave` skill (`D05 T02 §7`). The no-pin and dispatcher states still show the copyable agent request and `forge.py` command, as text; nothing in the extension runs them.
- The extension no longer bundles `forge.py` or `kits/`, so a kit change no longer raises the extension's version.

Reversing it costs restoring the removed modules, tests and forge fixtures from git at `9107f77`, re-adding `conclave.sdkPath` and the digest test, and returning `kit-view` to `active`.

### Scheduled reviewer pin (2026-10-25)

The owner, in the session, asked for the reviewer kit to take the scheduled review loop and chose GPT-6 Astra with the full schedule for both the kit's shipped pin and the SDK's own pin. The dispatcher stays multi-CLI: Codex, Antigravity and Claude Code reviewers, one reviewer per route, never of the writer's family.

- The shipped pin is `astra` (`codex`, `gpt-6-astra`, `medium`) with `claude = ["astra"]`, plus a `[schedule]` table: `severity_stop_after = 0`, a medium plan pass, a medium completion pass, three fixed adversarial rounds at high, medium and low effort, a low-effort rotation of one lens per round, and a medium escalation after a low-effort P1.
- `load_pin` accepts `[schedule]` as an optional third table and checks its efforts against every routed CLI that takes one (Antigravity takes none). The top-level refusal text stays `the reviewer pin needs exactly schema_version = 1, [reviewers.*] and [routes]`, which the extension's error target matches.
- `--check-pin --json` adds a `schedule` key only when the pin has one; the summary keeps `failover`.
- The extension's pin text model knows only the `[reviewers.*]` and `[routes]` headers, so a pin with `[schedule]` opens in the read-only `pin-layout` state. Editing a scheduled pin in the editor waits for a later entry; the pin is edited by hand meanwhile.
- The todo kit's `SEVERITY_CUTOFF_ROUND` equals the shipped `severity_stop_after`, and the todo kit reads the dispatcher, so it depends on the reviewer kit.

## Other owner decisions

- Marketplace: no (2026-10-17). The extension is not listed on the Visual Studio Marketplace: the `.vsix` bundles every kit and `rizonetech/Conclave-SDK` is internal, so each version's `.vsix` is attached to a GitHub release of that repository and organization members install it from there (plan R22, `D04 T01 §6`).
- The SDK's own copy of the kits (2026-10-17): the SDK root keeps every file of the `base`, `todo` and `reviewer` kits, including base's `docs/agent-skills-and-rules-structure.md` and `scripts/verify-agent-tiers.mjs`, so `python forge.py sync . --include-scripts` stays the refresh command (`todo/findings.md`, `AGENTS.md:13`).
