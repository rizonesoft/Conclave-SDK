# Open design questions from the mockup

Date: 2026-10-16. Mockup: <https://claude.ai/artifact/RRxxX5W6pYFQ3b2Z4Fq2mv>. Answers are recorded in `design/decisions.md` by `D00 T01 §2`; every answer was recorded by 2026-10-17 (8, 11 and 14 on 2026-10-16, the rest and the mockup approval on 2026-10-17). Each question lists the options and a recommendation.

## 1. Does the same CLI with a different model count as self-review?

The shipped pin routes `sonnet` (CLI `claude`) on the claude row and `gemini` (CLI `agy`) on the gemini row, both as last-resort failovers. The mockup warns on both.

- A. Warn whenever the reviewer's CLI is the writer's CLI (the mockup today).
- B. Warn only when the reviewer's model is the writer's own model, which the pin does not know.
- C. Warn on the same CLI only when it is the first reviewer in the route.

Recommendation: A. The pin cannot know which model wrote the work, and a same-CLI review shares the writer's tooling and prompts; a last-resort failover still deserves the warning.

## 2. One error at a time, or every error?

`load_pin` raises on the first fault, so `--check-pin` reports one message. The mockup shows one, with a line saying the next appears once it is fixed.

- A. Keep one error: `load_pin` stays exactly as it is and the contract stays `{"ok": false, "error": ...}`.
- B. Change `load_pin` to collect every fault and `--check-pin` to return `"errors": [...]`.

Recommendation: A for the first release. B changes the dispatcher's own refusal path for every caller and needs its own SDK section.

## 3. Which per-field faults open the editor, and which send the operator to the raw file?

The mockup opens the editor with an inline error for faults inside a parsable pin (bad name, unknown key, bad CLI, model or effort, route faults) and shows the "pin refused" screen for TOML that does not parse and for a wrong top level (`schema_version`, missing or extra tables).

- A. As the mockup shows.
- B. Every refused pin goes to the refused screen.

Recommendation: A. The editor can fix every per-field fault with its own controls; it cannot safely edit text that does not parse.

## 4. Custom editor or webview panel?

- A. A webview panel opened by the command `conclave.openReviewers`, with its own Save, Discard and atomic write (the mockup).
- B. A `CustomTextEditorProvider` for `.conclave/reviewers.toml`, which gets VS Code's dirty state, undo and Ctrl+S for free but saves through VS Code's own write path.

Recommendation: A. The brief requires a temp file and rename and a stale-disk check; B hands the write to VS Code. Undo inside the panel is Discard.

## 5. How are comments kept on edit?

- A. A narrow hand-written editor for the pin's grammar (tables, string values, one-line string arrays), editing text spans only.
- B. A comment-preserving TOML library.

Recommendation: decide in the design spec after a spike over the fixture pins; prefer A if no maintained library round-trips the shipped pin byte for byte.

## 6. Should Test reviewer ask before it runs?

It makes a real model call through the reviewer's CLI. The mockup asks every time, naming the model, CLI and writer.

- A. Ask every time (the mockup).
- B. Ask once per session.

Recommendation: A.

## 7. Python resolution order

The mockup tries `conclave.pythonPath`, then `py -3`, then `python` on Windows, and `python3`, then `python` in WSL, needing 3.11 or later.

- A. As the mockup shows; a set but unusable setting is an error, never a silent fallback.
- B. Also try the Python extension's selected interpreter before discovery.

Recommendation: A, with B considered later; the dispatcher is stdlib only and needs no project environment.

## 8. Where does the reviewer kit install come from?

Answered by the owner on 2026-10-16, in two steps: first from GitHub as well as a local checkout, then, with the extension moved into Conclave-SDK, bundled in the `.vsix` with both as overrides. The bundle is `forge.py` and `kits/` copied from the commit the extension is built from, so it is a build output of the SDK, not a second source. Bundling the kit's files in the extension stays ruled out, because it would make the extension a second source of the kit, which the SDK forbids.

## 9. How is the SDK fetched from GitHub when `conclave.sdkRef` is set?

`rizonetech/Conclave-SDK` is internal (an organization member must be signed in) and has no tags, so a download pins a commit of a branch.

- A. VS Code's GitHub sign-in (`repo` scope, no stored token), resolve `conclave.sdkRef` (default `main`) to a SHA, download that commit's tarball, cache it per SHA in the extension's global storage, extract refusing `..`, absolute paths and links, and run `forge.py` only after a confirmation naming the repository and SHA.
- B. `git clone --depth 1` with the operator's own git credentials into the same cache.
- C. The `gh` CLI.

Recommendation: A. It needs no git or `gh` on the side the extension runs on (Windows or Remote WSL), and it pins exactly which code runs. The same source also powers "Update from Conclave-SDK", which runs `forge.py sync <workspace> --include-scripts` for a missing or old dispatcher.

## 10. Which entry points open the editor?

- A. All four: the Command Palette command "Conclave: Open Reviewer Settings", "Open in Conclave Reviewers" on the pin's Explorer context menu, an editor title button when the pin is open as text, and a status bar item that shows the pin's state and opens the editor.
- B. The command only.

Recommendation: A. The status bar item is the one that matters most: it shows whether the pin is valid without opening anything.

## 11. Where do the kits live in the UI?

- A. A Conclave view container in the Activity Bar with a native Kits tree (state, health badge, inline Install and Health, and child rows for each doctor check), plus native quick picks for the install, update and new repository steps.
- B. A Kits tab inside the reviewer webview.

Recommendation: A. Native views follow the theme, keyboard and accessibility of VS Code for free, and the Kits view is useful in folders that have no reviewer pin.

Answered in part by the owner on 2026-10-16: the Conclave view container sits in the Activity Bar with its own icon, and Install opens the kit installer in that side bar rather than in quick picks. The mockup draws it as a second view under the Kits tree (a `WebviewView`), shown while an install is open. Update and new repository keep quick picks until the owner says otherwise. The owner also asked on 2026-10-16 for the view to show the current repository only, not every workspace folder: in a multi-root workspace it follows the active editor's folder, with a Switch folder action.

## 12. What is the undo of a kit install?

`forge.py` has no uninstall. Every file an install adds is a file in the workspace, so the operator's git is the undo, and every install, update and init proves by hash that the protected project files did not change.

- A. No uninstall in the extension until forge has one (the plan today).
- B. Add `forge.py kit --remove` to the SDK first, then an Uninstall action.

Recommendation: A for the first release.

## 13. Where does the Review rounds section get its rounds?

The dispatcher appends rounds to Markdown records (`docs/reviews/<topic>.md`) and cannot list them. The owner asked on 2026-10-16 for a Review rounds section.

- A. Add `review-dispatch.py --list-rounds --json` to the reviewer kit, beside `record`, so the code that writes the format also reads it back (`D06 T01 §3`).
- B. Parse the `## Round N` headings in the extension.

Recommendation: A. It follows `--check-pin`: the extension never reimplements a kit's format, and a test in the kit fails when the writer and the reader drift. The Plan section takes the same route with `todo-graph.py query plan` (`D06 T01 §2`).

## 14. How is the side bar organised as features grow?

Answered by the owner on 2026-10-16: one section per feature under the Kits tree, which stays its own section. Each section shows only while its kit is in the current folder. The first sections are Reviewers, Plan, Review rounds and WordPress site (plan R33 to R37, `D06 T01`).
