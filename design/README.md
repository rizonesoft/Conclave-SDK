# Design

The interface design for the Conclave VS Code extension in `extensions/vscode/`: the reviewer pin editor and the kit manager.

| Item | Where |
| --- | --- |
| Clickable mockup (Design canvas) | <https://claude.ai/artifact/RRxxX5W6pYFQ3b2Z4Fq2mv> |
| Mockup source | `design/mockup/project/` (`canvas.json` and one `.dc.html` per artboard) |
| Open design questions | `design/mockup/open-questions.md` |
| Decisions and approval | `design/decisions.md` (written by `D00 T01 §2`) |
| Interface SPEC | `design/SPEC.md` (written by `D00 T01 §3`) |

The mockup's `Main.dc.html` is the whole editor. The other artboards mount it with a theme and a scenario. Its control bar (outside the VS Code window) switches between Dark Modern and Light Modern and among 22 scenarios: the shipped pin, a missing CLI, a file changed on disk, one scenario per dispatcher error, the refused and newer-schema pins, and the no-pin, no-dispatcher, old-dispatcher, no-Python and untrusted states. The mockup imitates `load_pin` only to show its exact messages; the extension itself always asks `scripts/review-dispatch.py --check-pin`.

## Requirement map

Where each requirement in `docs/plans/2026-10-16-vscode-extension.md` shows in the mockup (scenario names are the control bar's).

| Requirement | Where in the mockup |
| --- | --- |
| R1, R2 cards and per-CLI effort | Every editor scenario; the gemini card shows the agy note |
| R3 add, rename, delete | Card header pencil and bin; Add reviewer card |
| R4 route rows | Routes: drag, move buttons, add menu, remove |
| R5 self-review warning | Ready: sonnet on claude, gemini on gemini |
| R6 no-route notice | Remove both codex reviewers |
| R7 to R9 inline errors, Save gating | The 11 `Error:` scenarios; `Refused: schema_version = 2` |
| R10 CLI status | Status: agy is not on PATH |
| R11 Test reviewer | Test reviewer on any card |
| R12 preview and diff | reviewers.toml panel, Preview and Diff against disk |
| R13 to R15 save, stale, discard | Save, Discard; File changed on disk while open |
| R16 no pin | No pin yet |
| R17 refused pin | Refused: TOML does not parse; Refused: schema_version = 2 |
| R18 dispatcher missing or old | No scripts/review-dispatch.py; Dispatcher without --check-pin |
| R19 no Python, untrusted | No Python 3.11 or later; Workspace not trusted |
| R21 schema range | Pin newer than the extension |
| R24 SDK source | Not drawn yet (open item in `D00 T01 §1`) |
| R26 entry points | Not drawn yet (open item in `D00 T01 §1`) |
| R27 to R32 kit manager | Not drawn yet (open items in `D00 T01 §1`) |
