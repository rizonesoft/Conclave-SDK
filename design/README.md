# Design

The interface design for the Conclave VS Code extension in `extensions/vscode/`: the reviewer pin editor and the kit manager.

| Item | Where |
| --- | --- |
| Clickable mockup (Design canvas) | <https://claude.ai/artifact/RRxxX5W6pYFQ3b2Z4Fq2mv> |
| Mockup source | `design/mockup/project/` (`canvas.json` and one `.dc.html` per artboard) |
| Activity Bar icon | `extensions/vscode/media/conclave.svg` (24 px, one colour) |
| Icon concepts and the icon in use | <https://claude.ai/artifact/CK6Bf7r5g3UCsqme5FBfvc> |
| Icon concepts source | `design/icon-concepts/project/` (pulled from the canvas above) |
| Platform audit | `design/platform-audit.md` (native, webview or chrome, per element) |
| Open design questions | `design/mockup/open-questions.md` |
| Decisions and approval | `design/decisions.md` (written by `D00 T01 §2`) |
| Interface SPEC | `design/SPEC.md` (written by `D00 T01 §3`) |

The mockup's `Main.dc.html` is the whole editor. The other artboards mount it with a theme and a scenario. Its control bar (outside the VS Code window) switches between Dark Modern and Light Modern and among 22 scenarios: the shipped pin, a missing CLI, a file changed on disk, one scenario per dispatcher error, the refused and newer-schema pins, and the no-pin, no-dispatcher, old-dispatcher, no-Python and untrusted states (the first three show the agent request and the forge command, each copyable). The mockup imitates `load_pin` only to show its exact messages; the extension itself always asks `scripts/review-dispatch.py --check-pin`.

The Conclave icon at the foot of the Activity Bar switches the side bar to the Conclave view. The icon is the Council mark from the Conclave icon concepts (seven agent seats around one core), drawn as a 24 px single-colour glyph that VS Code tints like its own icons. The view holds the Kits tree for the current repository only, read only: every kit's state, its health badge and, expanded, one row per doctor check. In a one-folder window (the default, `orchard-web`) that is the folder; in a multi-root workspace it is the active editor's folder, named beside the KITS heading, and a Switch folder action picks another. Nothing in the view installs, updates or sets up a repository (`design/decisions.md`, Read-only kit view and agent import, 2026-10-20): a kit's context menu has Health and Copy import request (the `adopt-conclave` agent request and the `python forge.py kit` command it stands for), a kit set up from newer kits than the extension reads `newer kits than this extension` and one from older kits `older kits than this extension` with Copy update request, and a folder with no kit says how to import kits with the agent. The doctor rows follow `forge.py` at `97cca1d`. A third control, SDK source, switches between the bundled SDK and `conclave.sdkPath` (a developer override), and the artboards' `sidebar` prop opens the Kits view in each state (`kits`, `kits-health`, `kits-stamps`, `kits-empty`, `sections`). Under the Kits tree sit the feature sections, one per feature, each shown only while its kit is in the folder: REVIEWERS (pin state, reviewers with CLI status, routes, and Open Reviewer Settings), PLAN (ready sections and phases from `todo-graph.py query plan`), REVIEW ROUNDS (round records from `review-dispatch.py --list-rounds`) and WORDPRESS SITE (doctor's site checks). Plan and rounds data in the mockup is example data in the shape those queries will print (`D06 T01 §2` and §3). A fourth control, Workspace, switches between one folder and a multi-root workspace (the artboards' `workspace` prop).

The mockup draws every icon from the codicon SVG sources of `@vscode/codicons` 0.0.45 (`src/icons/<name>.svg`), inline, so the build names the same icons. Codicons are by Microsoft, licensed CC BY 4.0. `design/platform-audit.md` records which elements VS Code draws from the extension API and what the mockup changed so each is buildable 1:1.

## Requirement map

Where each requirement in `docs/plans/2026-10-16-vscode-extension.md` shows in the mockup (scenario names are the control bar's).

| Requirement | Where in the mockup |
| --- | --- |
| R1, R2 cards and per-CLI effort | Every editor scenario; the gemini card shows the agy note |
| R3 add, rename, delete | Card header pencil and bin; Add reviewer card |
| R4 route rows | Routes: a reviewer and a fallback chip, drag, move, remove |
| R5 family rule | Add menu greys out the writer's and reviewer's family |
| R6 no-route notice | Remove both codex reviewers |
| R7 to R9 inline errors, Save gating | The 14 `Error:` scenarios; `Refused: schema_version = 2` |
| R10 CLI status | Status: agy is not on PATH |
| R11 Test reviewer | Test reviewer on any card |
| R12 preview and diff | reviewers.toml panel, Preview and Diff against disk |
| R13 to R15 save, stale, discard | Save, Discard; File changed on disk while open |
| R16 no pin | No pin yet: the agent request and `forge.py kit` command, each copyable |
| R17 refused pin | Refused: TOML does not parse; Refused: schema_version = 2 |
| R18 dispatcher missing or old | No or old dispatcher: the agent request and `forge.py sync` |
| R19 no Python, untrusted | No Python 3.11 or later; Workspace not trusted |
| R21 schema range | Pin newer than the extension |
| R24 SDK source | SDK source control (bundled, `conclave.sdkPath`); `conclave.sdkPath` unusable |
| R26 entry points | Entry points artboards: palette, Explorer menu, title button, status bar |
| R27, R30 Kits view and health | Kits artboards: states, badges, doctor rows, Activity Bar badge |
| R40 kit stamps | Kits view: kit stamps newer and older; kit context menu; a folder with no kit |
| R28 kit install | dropped 2026-10-20 (read-only kit view, `design/decisions.md`) |
| R29 update | dropped 2026-10-20 (read-only kit view, `design/decisions.md`) |
| R31 new repository | dropped 2026-10-20 (read-only kit view, `design/decisions.md`) |
| R32 protected files | dropped 2026-10-20 (read-only kit view, `design/decisions.md`) |
| R33 feature sections | Sections artboard: Kits tree, then one section per installed kit |
| R34 Plan | PLAN section: ready now, phases named from `todo/plan.json` |
| R35 Review rounds | REVIEW ROUNDS section: a reviewed round and one with no review |
| R36 WordPress site | WORDPRESS SITE section: doctor's site checks after a fresh install |
| R37 Reviewers section | REVIEWERS section: pin state, CLI status, routes, every pin state |
