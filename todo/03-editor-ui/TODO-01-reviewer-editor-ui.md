---
schema_version: 1
id: reviewer-editor-ui
domain: 03-editor-ui
status: active
title: "TODO-01 -- Reviewer Editor UI"
---

# TODO-01 -- Reviewer Editor UI

> **Goal:** The "Reviewers" webview renders the approved design from `design/SPEC.md` in the operator's VS Code theme and drives every edit, check, save, status and test through messages to the host modules of `D02 T01`. It holds no validation rules: what it shows as an error is what the dispatcher said. Every control on the SPEC surface works or names the section that owns it.

> **Current state:** Measured 2026-10-16. No webview exists. The surface is specified only by requirements R1 to R19 in `docs/plans/2026-10-16-vscode-extension.md`; `design/SPEC.md` and `design/screens/` arrive with `D00 T01 §3`, and the host modules with `D02 T01`.

## Inputs

- `design/SPEC.md` §1 to §7 and `design/screens/`: the approved surface, its controls, states and exact texts.
- `design/decisions.md`: the owner's answers (for example one error versus all) and the changes after approval (the reviewer route rule of 2026-10-20). **Corrected 2026-10-20:** named the same-CLI warning, which that rule superseded.
- `extensions/vscode/src/core/pinText.ts`, `extensions/vscode/src/host/candidate.ts`, `extensions/vscode/src/host/save.ts`, `extensions/vscode/src/host/dispatcher.ts`, `extensions/vscode/src/host/testReviewer.ts` from `D02 T01`, and the kit install and update flows from `D05 T01 §6` and `D05 T01 §7`.
- -> XREF: D00 T01 §3 -- `design/SPEC.md` is the Fidelity source of every section here
- -> XREF: D02 T01 §5 -- candidate validation and `canSave`
- -> XREF: D04 T01 §2 -- the WSL check walks this surface
- -> XREF: D05 T02 §7 -- the no-pin and dispatcher states show the adopt-conclave agent request
- -> XREF: D02 T01 §11 -- the parity fixtures and `expectParity` every surface section here asserts
- Every `npm`, `npx` and `node` command in this file runs in `extensions/vscode/`.

## Outcome

- Opening `conclave.openReviewers` on the shipped workspace shows the three reviewer cards, three route rows of one reviewer each (**Corrected 2026-10-20:** were rows with the self-review warnings, before `design/decisions.md`, Reviewer routes, 2026-10-20; **Corrected 2026-10-21:** were rows of a reviewer and one fallback, before One reviewer per route), a clean preview, and CLI status, in Dark Modern and Light Modern, matching `design/screens/`.
- Every edit updates the preview and diff, shows the dispatcher's error at its field, disables Save while refused, and Save writes the file that the preview showed.
- Each empty and failure state from `design/SPEC.md` §7 renders with its action.

**Adjacency:** list=not-applicable (one pin per workspace folder); document=not-applicable (no printable output beyond the pin itself); settings=not-applicable (every setting is consumed in D02 T01 §2 or D02 T01 §7); reporting=not-applicable (no summaries); notifications=not-applicable (states render in the panel); permissions=not-applicable (the trust and read-only refusals are owned by D02 T01 §3 and D02 T01 §6 and only displayed here); audit=not-applicable (the output channel is owned by D02 T01 §3); exchange=not-applicable (no import or export); reverse=applicable @ D03 T01 §8

**Adjacency rationale:** The webview is a view over host state. Its one owned reverse path is Discard and Reload in §8, which call `discard()` and `reload()` from `D02 T01 §6`; a delete or rename made in the panel is undone by Discard before Save, and by the file's git history after Save.

## Implementation Order

| Order | Section | Deliverable | Depends On | Status |
| ----- | ------- | ----------- | ---------- | ------ |
| 1 | §1 | Webview shell, theming and message bridge | D00 T01 §3, D02 T01 §1, D02 T01 §11 | [ ] |
| 2 | §2 | Reviewer cards with per-CLI effort | §1, D02 T01 §4 | [ ] |
| 3 | §3 | Reviewer add, rename and delete | §2 | [ ] |
| 4 | §4 | Route rows with one reviewer each | §1, D02 T01 §4 | [ ] |
| 5 | §5 | No-route notice | §4 | [ ] |
| 6 | §6 | Inline validation and Save gating | §2, §4, D02 T01 §5 | [ ] |
| 7 | §7 | TOML preview with diff against disk | §6 | [ ] |
| 8 | §8 | Save, discard and reload flow | §6, D02 T01 §6 | [ ] |
| 9 | §9 | Reviewer status and Test reviewer panel | §2, D02 T01 §8 | [ ] |
| 10 | §10 | Empty and failure states | §1, D02 T01 §3, D00 T01 §8 | [ ] |
| 11 | §11 | Entry points: command, menus and status bar | §1, D02 T01 §3 | [ ] |

## 1. Webview shell, theming and message bridge

Every later section renders inside this panel. This section replaces the placeholder from `D02 T01 §1` with the real shell: a webview with a strict Content Security Policy, the layout regions from `design/SPEC.md` §1, colours only from VS Code's theme variables, and a typed message bridge between `extensions/vscode/src/webview/` and `extensions/vscode/src/host/panel.ts`. It shows no pin data yet beyond the state name.

**Phase:** 2
**Needs:** none
**Surface:** yes
**Fidelity:** `design/SPEC.md` §1 Layout and theming; `design/screens/1-dark.png` and `design/screens/1-light.png`.
**Job:** Give the operator one place, styled like the rest of VS Code, where the pin's reviewers, routes, preview and status sit together.
**Treatment:** Native webview with `--vscode-*` CSS variables only; regions as the SPEC lays them out; no custom fonts.
**Chrome:** Editor-area panel titled "Reviewers: <folder>" with the codicon from the SPEC; one panel per workspace folder, revealed if already open.

**Build order:**

1. Write `extensions/vscode/src/host/panel.ts` and `extensions/vscode/src/webview/main.ts` with the bridge. Done when: the panel shows the host state name and round-trips a `ping` message.
2. Lay out the SPEC regions with theme variables. Done when: screenshots in both themes match `design/screens/1-*.png` region for region.

- [ ] Define the message types in `extensions/vscode/src/shared/messages.ts` (host to webview: `state`, `model`, `check`, `preview`, `status`, `testResult`; webview to host: `edit`, `save`, `discard`, `reload`, `test`, `openKitInstall`, `openKitUpdate`, `openRaw`). Done when: both sides compile against the one file. Cheaper substitute: untyped `any` messages.
- [ ] Write `extensions/vscode/src/host/panel.ts` creating the panel with `enableScripts`, `localResourceRoots` limited to `extensions/vscode/dist/webview`, and a CSP allowing only the nonce'd script and the extension's stylesheet. Done when: an integration test reads the HTML and finds the CSP and nonce. Cheaper substitute: `default-src *`.
- [ ] Bundle `extensions/vscode/src/webview/main.ts` and `extensions/vscode/src/webview/styles.css` to `extensions/vscode/dist/webview/` in `extensions/vscode/esbuild.mjs`. Done when: `npm run build` writes both and the panel loads them. Cheaper substitute: inline script strings in TypeScript.
- [ ] Lay out the regions of `design/SPEC.md` §1 in `extensions/vscode/src/webview/styles.css` using only `var(--vscode-*)` colours. Done when: `grep -E "#[0-9a-fA-F]{3,6}|rgb\(" src/webview/styles.css` finds nothing. Cheaper substitute: fixed dark colours.
- [ ] Reveal the existing panel for a folder instead of opening a second one. Done when: running `conclave.openReviewers` twice leaves one panel. Cheaper substitute: a new panel per run.
- [ ] Keep state across hide and show with `getState`/`setState` in the webview. Done when: switching editor tabs and back keeps unsaved edits. Cheaper substitute: `retainContextWhenHidden` on every panel.
- [ ] Capture Dark Modern and Light Modern screenshots of the shell into `extensions/vscode/test/screens/1-*.png` and compare them by eye against `design/screens/1-*.png`, noting any difference in the section's commit body. Done when: both screenshots exist. Cheaper substitute: checking one theme.
- [ ] Assert mockup parity for every scenario this section draws in `extensions/vscode/test/parity/webview-shell-theming-and-message-bridge.parity.test.ts` with `expectParity` from D02 T01 §11. Done when: the test passes and fails when one label, description, icon, badge, order or action differs from the mockup's fixture. Cheaper substitute: comparing by eye against the mockup.
- [ ] Commit: `ui: webview shell, theming and message bridge`

**Test checkpoint:** `cd extensions/vscode && npm run test:integration -- --grep panel` passes, asserting the CSP, the nonce, one panel per folder and a `ping` round trip; it fails when the CSP meta tag is removed.

## 2. Reviewer cards with per-CLI effort

The operator edits each reviewer in a card (plan R1, R2). This section renders one card per reviewer from `readPin` and sends field edits to the host, which applies them with `setField` from `D02 T01 §4`. The effort control follows the CLI: codex and claude get their allowed lists, agy hides effort and shows the note. It must not decide validity: an out-of-list value from a hand-edited file still displays and is flagged by §6.

**Phase:** 2
**Needs:** none
**Surface:** yes
**Fidelity:** `design/SPEC.md` §2 Reviewer cards; `design/screens/2-dark.png` and `design/screens/2-light.png`.
**Job:** Let the operator see and change which CLI, model and effort each reviewer uses.
**Treatment:** One card per reviewer in file order: name heading, `cli` select, `model` text input, `effort` select or the agy note.
**Chrome:** Card header carries the status badge slot used by §9 and the rename and delete actions used by §3.

**Build order:**

1. Render cards in `extensions/vscode/src/webview/cards.ts` from the `model` message. Done when: the shipped workspace shows astra, gemini and sonnet with their values.
2. Send field edits and handle CLI changes. Done when: each edit round-trips through `setField` and the preview from §7 shows only that line changed.

- [ ] Render a card per reviewer in `extensions/vscode/src/webview/cards.ts` in file order with name, `cli`, `model` and `effort` from the `model` message. Done when: the integration test reads three cards with the shipped values. Cheaper substitute: alphabetical order that differs from the file.
- [ ] Offer `cli` as a select of codex, agy and claude, and render an unknown value from disk as a selected "(unknown: <value>)" option. Done when: the `refused-bad-cli.toml` workspace shows the unknown value. Cheaper substitute: snapping an unknown value to the first option.
- [ ] Offer `effort` as a select of `EFFORTS[cli]` (codex: low, medium, high, xhigh; claude adds max), cited from `scripts/review-dispatch.py`. Done when: the astra card lists four options and the sonnet card five. Cheaper substitute: one list for both CLIs.
- [ ] Hide `effort` for agy and show the note from `design/SPEC.md` §2 naming `gemini-4-argon-high`. Done when: the gemini card shows the note and no effort control. Cheaper substitute: a disabled effort select.
- [ ] Send `edit` messages for `cli`, `model` and `effort`; on a change to agy send the effort removal, and on a change from agy send the SPEC's default effort. Done when: switching astra to agy and back produces the two expected pin texts. Cheaper substitute: leaving a stale effort on an agy reviewer.
- [ ] Commit `model` input on blur and Enter, not on every keystroke, so each edit is one check. Done when: typing a model name triggers one check. Cheaper substitute: a check per keystroke.
- [ ] Make every control reachable by keyboard with labels from the SPEC. Done when: tabbing through a card reaches each control and a screen reader name is set on each. Cheaper substitute: mouse only.
- [ ] Write `extensions/vscode/test/integration/cards.test.ts` covering render, each field edit, and both CLI switches. Done when: the tests pass and fail when the agy note is removed. Cheaper substitute: snapshot only.
- [ ] Assert mockup parity for every scenario this section draws in `extensions/vscode/test/parity/reviewer-cards-with-per-cli-effort.parity.test.ts` with `expectParity` from D02 T01 §11. Done when: the test passes and fails when one label, description, icon, badge, order or action differs from the mockup's fixture. Cheaper substitute: comparing by eye against the mockup.
- [ ] Commit: `ui: reviewer cards with per-CLI effort`

**Test checkpoint:** `cd extensions/vscode && npm run test:integration -- --grep cards` passes and fails when the effort list for claude omits `max`.

## 3. Reviewer add, rename and delete

Reviewers are added, renamed and deleted from the panel (plan R3). This section wires those actions to `addReviewer`, `renameReviewer` and `deleteReviewer` from `D02 T01 §4`. Rename rewrites every route entry. Delete first lists the routes that will lose the reviewer and asks to confirm. Names are not checked here: a bad name is flagged by §6 from the dispatcher's message.

**Phase:** 2
**Needs:** none
**Surface:** yes
**Fidelity:** `design/SPEC.md` §2 Reviewer cards (add, rename, delete); `design/screens/2-dark.png` and `design/screens/2-light.png`.
**Job:** Let the operator change who the reviewers are without hand-editing tables and route arrays.
**Treatment:** "Add reviewer" button after the last card; rename inline in the card header; delete in the card header with an inline confirmation.
**Chrome:** Confirmation lives in the card, not a modal, as the SPEC shows.

**Build order:**

1. Add and rename in `extensions/vscode/src/webview/cards.ts`. Done when: both round-trip and the preview shows the expected text.
2. Delete with route impact. Done when: the confirmation lists the affected routes and confirming removes them.

- [ ] Add "Add reviewer" in `extensions/vscode/src/webview/cards.ts`, opening a new card with a name field and the SPEC's defaults, sent as `addReviewer`. Done when: adding `opus` with cli claude shows a new card and a new table in the preview before `[routes]`. Cheaper substitute: appending raw text to the preview.
- [ ] Rename inline in the card header, sent as `renameReviewer`. Done when: renaming `sonnet` to `sonnet-55` updates the card and both route rows that name it. Cheaper substitute: renaming the card only.
- [ ] Refuse a rename to a name another reviewer already has, in the webview, before sending. Done when: renaming `gemini` to `astra` shows the SPEC's message and sends nothing. Cheaper substitute: letting the text model produce a duplicate table that TOML cannot parse.
- [ ] Show delete's inline confirmation listing every route that names the reviewer, sent as `deleteReviewer` on confirm. Done when: deleting `gemini` lists the claude, gemini and codex rows. Cheaper substitute: deleting without saying which routes lose it.
- [ ] Cancel delete and rename with Escape, leaving the model unchanged. Done when: no `edit` message is sent on cancel. Cheaper substitute: no cancel path.
- [ ] Write `extensions/vscode/test/integration/reviewerCrud.test.ts` covering add, rename, duplicate-name refusal, delete with route impact and cancel. Done when: all pass and the rename test fails if route entries are left stale. Cheaper substitute: testing add only.
- [ ] Assert mockup parity for every scenario this section draws in `extensions/vscode/test/parity/reviewer-add-rename-and-delete.parity.test.ts` with `expectParity` from D02 T01 §11. Done when: the test passes and fails when one label, description, icon, badge, order or action differs from the mockup's fixture. Cheaper substitute: comparing by eye against the mockup.
- [ ] Commit: `ui: reviewer add, rename and delete`

**Test checkpoint:** `cd extensions/vscode && npm run test:integration -- --grep reviewerCrud` passes and fails when `renameReviewer` is replaced by a header-only rename.

## 4. Route rows with one reviewer each

**Corrected 2026-10-20:** was "Route rows with ordered failover editing", for a list of any length. The owner's family route rule (`design/decisions.md`, Reviewer routes, 2026-10-20) made a route a reviewer and one fallback.

**Corrected 2026-10-21:** was "Route rows with a reviewer and one fallback", with two numbered chips, drag and keyboard reordering, the `fallback` tag and a third-family rule. The owner dropped the fallback (`design/decisions.md`, One reviewer per route, 2026-10-21): a route names exactly one reviewer, never of the writer's family, so a row holds one chip with no order controls, and the add menu shows only on an empty row and disables only a reviewer of the writer's family.

Each writer's route is one reviewer of another model family (plan R4, R5). This section renders the claude, codex and gemini rows and edits them with add and remove, sending `setRoute` and `removeRoute` from `D02 T01 §4`. The add menu, shown only while the row has no chip, disables with the reason a reviewer of the writer's family. It shows a route that names an undefined reviewer as written, so §6 can flag it, and a hand-edited route with more than one name shows every entry with the dispatcher's refusal from §6, so the extras can be removed.

**Phase:** 2
**Needs:** none
**Surface:** yes
**Fidelity:** `design/SPEC.md` §3 Route rows; `design/screens/3-dark.png` and `design/screens/3-light.png`.
**Job:** Let the operator choose, for each writer, the one reviewer from another model family.
**Treatment:** One row per writer in the order claude, codex, gemini; one chip with the reviewer's name and a remove button; an add menu at the row end only while the row has no chip.
**Chrome:** Row label names the writer; the no-route notice from §5 replaces the chip when the route is absent.

**Build order:**

1. Render rows in `extensions/vscode/src/webview/routes.ts`. Done when: the shipped workspace shows the three rows, one chip each.
2. Edit by add and remove. Done when: each edit sends one `setRoute` or `removeRoute`, the preview shows the new array, and no edit offers a route the pin refuses.

- [ ] Render a row per writer in `extensions/vscode/src/webview/routes.ts` with one chip per route entry, from the `model` message. Done when: the shipped codex row shows the one chip `gemini`. Cheaper substitute: the route as plain text.
- [ ] Implement `routeChoices(model, writer)` in `extensions/vscode/src/core/routeChoices.ts` returning each defined reviewer with its disabled reason, `same family as the writer` (codex is OpenAI, agy Google, claude Anthropic, as `FAMILY` and `WRITER_FAMILY` in `review-dispatch.py`) or none. Done when: `extensions/vscode/test/unit/routeChoices.test.ts` gives, for the gemini row, gemini disabled as `same family as the writer` and astra and sonnet enabled, and fails when agy's family is removed. Cheaper substitute: offering every reviewer and letting Save refuse.
- [ ] Add from a menu built from `routeChoices`, each disabled option labelled with its reason, shown only while the row has no chip. Done when: the shipped claude row shows no add menu, and the `refused-empty-route.toml` workspace's codex row menu disables astra as `same family as the writer`. Cheaper substitute: a free-text add.
- [ ] Remove a chip, sending `setRoute`, and send `removeRoute` when the last chip goes. Done when: removing the codex chip removes the `codex` key from `[routes]`, and on the `refused-route-too-long.toml` workspace removing gemini writes `claude = ["astra"]`. Cheaper substitute: writing `codex = []`, which the dispatcher refuses.
- [ ] Add a route to a writer that has none, from the no-route notice's action. Done when: adding gemini to an absent codex route writes `codex = ["gemini"]`. Cheaper substitute: requiring a hand edit.
- [ ] Show an undefined reviewer named on disk as a chip marked unknown. Done when: the `refused-undefined-reviewer.toml` workspace shows the chip. Cheaper substitute: hiding the unknown name.
- [ ] Write `extensions/vscode/test/integration/routes.test.ts` covering render, the one-chip limit, add with the family-disabled choices, remove to absent, add to absent and a hand-edited route of two names. Done when: all pass and fail when the last remove writes an empty array. Cheaper substitute: render test only.
- [ ] Assert mockup parity for every scenario this section draws in `extensions/vscode/test/parity/route-rows-with-one-reviewer-each.parity.test.ts` with `expectParity` from D02 T01 §11. Done when: the test passes and fails when one label, description, icon, badge, order or action differs from the mockup's fixture. Cheaper substitute: comparing by eye against the mockup.
- [ ] Commit: `ui: route rows with one reviewer each`

**Test checkpoint:** `cd extensions/vscode && npm run test:integration -- --grep routes` passes and fails when removing the last chip writes `[]` instead of removing the key, or when the add menu offers a reviewer of the writer's family.

## 5. No-route notice

**Corrected 2026-10-20:** was "Self-review warning and no-route notice". The owner's family route rule (`design/decisions.md`, Reviewer routes, 2026-10-20) makes the pin refuse a reviewer of the writer's family, and §4's add menu never offers one, so the warning has nothing left to warn about. Removed for that reason: `selfReview(model)`, its unit test cases (astra added to the codex row, the gemini-to-agy pairing), and rendering the warning on a chip. A hand-edited pin that breaks the rule shows the dispatcher's refusal inline through §6.

A writer with no route gets no review at all, and the dispatcher allows it (plan R6). This section computes it in `extensions/vscode/src/core/routeNotices.ts` from the model (advice, not validation: the dispatcher has no rule for it) and shows it as the SPEC words it.

**Phase:** 2
**Needs:** none
**Surface:** yes
**Fidelity:** `design/SPEC.md` §3 Route rows (no-route notice); `design/screens/3-dark.png` and `design/screens/3-light.png`.
**Job:** Stop the operator from leaving a writer with no review without noticing.
**Treatment:** Notice text in place of the chips on an absent route, with an add action.
**Chrome:** The notice never disables Save; it is not an error.

**Build order:**

1. Write `extensions/vscode/src/core/routeNotices.ts`. Done when: unit tests over the fixtures produce one notice per writer with no route.
2. Render them in `extensions/vscode/src/webview/routes.ts`. Done when: the shipped workspace shows none and `valid-no-codex-route.toml` shows exactly one.

- [ ] Implement `missingRoutes(model)` returning each of claude, codex and gemini with no route. Done when: `valid-no-codex-route.toml` yields codex. Cheaper substitute: treating an absent route as an error.
- [ ] Write `extensions/vscode/test/unit/routeNotices.test.ts` over the valid fixtures. Done when: the tests pass, `valid-shipped.toml` yields no notice, and they fail when `missingRoutes` stops reporting codex on `valid-no-codex-route.toml`. Cheaper substitute: one case.
- [ ] Render the no-route notice in place of the chips, saying the writer gets no review and the dispatcher will refuse it, with the add action from §4. Done when: the `valid-no-codex-route.toml` workspace shows it on the codex row. Cheaper substitute: an empty row with no text.
- [ ] Assert mockup parity for every scenario this section draws in `extensions/vscode/test/parity/no-route-notice.parity.test.ts` with `expectParity` from D02 T01 §11. Done when: the test passes and fails when one label, description, icon, badge, order or action differs from the mockup's fixture. Cheaper substitute: comparing by eye against the mockup.
- [ ] Commit: `ui: no-route notice`

**Test checkpoint:** `cd extensions/vscode && npm test -- --test-name-pattern=routeNotices` passes and fails when `missingRoutes` stops reporting a writer with no route.

## 6. Inline validation and Save gating

Errors come only from the dispatcher (plan R7 to R9). This section shows the latest `check` result from `D02 T01 §5` at the target `errorTarget` names (a card field, a route row, or the file), with the `Refused` text verbatim, and disables Save while it shows. When the check is running, the panel says so and Save stays disabled.

**Phase:** 2
**Needs:** none
**Surface:** yes
**Fidelity:** `design/SPEC.md` §4 Validation and Save; `design/screens/4-dark.png` and `design/screens/4-light.png`.
**Job:** Tell the operator exactly what the dispatcher will refuse, where, before anything is saved.
**Treatment:** Error text under the targeted field or row in `--vscode-errorForeground` with an error border; file-level errors in a strip above the cards.
**Chrome:** Save button in the panel toolbar, disabled with a tooltip giving the reason while refused or checking.

**Build order:**

1. Render `check` results in `extensions/vscode/src/webview/validation.ts`. Done when: each refused fixture shows its message at its target.
2. Gate Save on `canSave`. Done when: Save is disabled for every refused fixture and while a check runs.

- [ ] Render the error at the target from `errorTarget` in `extensions/vscode/src/webview/validation.ts`, text verbatim. Done when: `refused-agy-effort.toml` shows the message under the gemini card's model area as the SPEC places it. Cheaper substitute: a toast.
- [ ] Render file-level errors (unparsable, schema, unknown message) in the strip above the cards. Done when: `refused-unparsable.toml` shows `unreadable reviewer pin:` with tomllib's line and column. Cheaper substitute: hiding parse errors.
- [ ] Clear errors when a later check returns `ok` true. Done when: fixing the field removes the error without reopening the panel. Cheaper substitute: errors that persist until reload.
- [ ] Show a checking indicator while a check is in flight. Done when: a slow fake dispatcher shows it. Cheaper substitute: no indicator, so a stale result looks current.
- [ ] Disable Save from `canSave`, with a tooltip naming the reason (refused, checking, unchanged). Done when: the integration test reads the disabled state and tooltip for each. Cheaper substitute: an enabled Save that fails on click.
- [ ] Write `extensions/vscode/test/integration/validation.test.ts` walking every refused fixture through the panel. Done when: each shows its message at its target and Save is disabled, and the test fails if one message is paraphrased. Cheaper substitute: three fixtures.
- [ ] Assert mockup parity for every scenario this section draws in `extensions/vscode/test/parity/inline-validation-and-save-gating.parity.test.ts` with `expectParity` from D02 T01 §11. Done when: the test passes and fails when one label, description, icon, badge, order or action differs from the mockup's fixture. Cheaper substitute: comparing by eye against the mockup.
- [ ] Commit: `ui: inline dispatcher errors and Save gating`

**Test checkpoint:** `cd extensions/vscode && npm run test:integration -- --grep validation` passes and fails when Save is left enabled for `refused-bad-effort.toml`.

## 7. TOML preview with diff against disk

The operator sees exactly what Save will write (plan R12). This section renders the candidate text with comments as the text model produced it, and a line diff against the loaded disk text, so an edit shows as only the lines it changed.

**Phase:** 2
**Needs:** none
**Surface:** yes
**Fidelity:** `design/SPEC.md` §6 TOML preview and diff; `design/screens/6-dark.png` and `design/screens/6-light.png`.
**Job:** Prove to the operator that Save changes only what they edited and keeps every comment.
**Treatment:** Monospace preview using the editor font variables; added, removed and unchanged lines styled with the diff editor's theme variables.
**Chrome:** Toggle between preview and diff in the region header, and an "Open file" action that opens the raw pin.

**Build order:**

1. Write `extensions/vscode/src/core/lineDiff.ts`. Done when: unit tests over the golden edits produce the expected hunks.
2. Render preview and diff in `extensions/vscode/src/webview/preview.ts`. Done when: one edit on the shipped workspace shows one changed line.

- [ ] Implement `lineDiff(before, after)` in `extensions/vscode/src/core/lineDiff.ts` (a Myers or patience line diff, no dependency unless the spec names one). Done when: unit tests over `extensions/vscode/test/fixtures/edits/` match expected hunks. Cheaper substitute: marking every line changed.
- [ ] Render the candidate in `extensions/vscode/src/webview/preview.ts` with `--vscode-editor-font-family` and size. Done when: the preview of the unchanged shipped pin equals the file text. Cheaper substitute: a reformatted preview.
- [ ] Render the diff with `--vscode-diffEditor-insertedTextBackground` and `--vscode-diffEditor-removedTextBackground`. Done when: renaming sonnet shows only the header and two route lines changed. Cheaper substitute: colours not from the theme.
- [ ] Show "No changes" when the candidate equals disk. Done when: after Discard the diff says so. Cheaper substitute: an empty pane.
- [ ] Wire "Open file" to `vscode.window.showTextDocument` on the pin, sent as `openRaw`. Done when: the integration test sees the pin editor open. Cheaper substitute: no way to the raw file.
- [ ] Write `extensions/vscode/test/unit/lineDiff.test.ts` and `extensions/vscode/test/integration/preview.test.ts`. Done when: both pass and the integration test fails when a comment is dropped from the preview. Cheaper substitute: unit tests only.
- [ ] Assert mockup parity for every scenario this section draws in `extensions/vscode/test/parity/toml-preview-with-diff-against-disk.parity.test.ts` with `expectParity` from D02 T01 §11. Done when: the test passes and fails when one label, description, icon, badge, order or action differs from the mockup's fixture. Cheaper substitute: comparing by eye against the mockup.
- [ ] Commit: `ui: TOML preview with diff against disk`

**Test checkpoint:** `cd extensions/vscode && npm test -- --test-name-pattern=lineDiff && npm run test:integration -- --grep preview` passes and fails when `lineDiff` marks unchanged comment lines as changed.

## 8. Save, discard and reload flow

This section wires the toolbar to `D02 T01 §6`: Save writes atomically and shows the re-check, Discard returns to disk, and a stale or externally changed file offers Reload (plan R13 to R15). It owns the editor's reverse path. A save refused as stale or read-only leaves the operator's edits in the panel.

**Phase:** 2
**Needs:** none
**Surface:** yes
**Fidelity:** `design/SPEC.md` §4 Validation and Save (Save, Discard, stale and read-only messages); `design/screens/4-dark.png` and `design/screens/4-light.png`.
**Job:** Let the operator commit their edits safely, or back out of them, and never lose someone else's change to the file.
**Treatment:** Save and Discard in the toolbar; a stale banner with Reload and "Keep my edits"; the re-check result in the status strip after each save.
**Chrome:** Ctrl+S in the focused panel saves; the panel title shows a dirty marker while the candidate differs from disk.

**Build order:**

1. Wire Save, Discard and the dirty marker in `extensions/vscode/src/webview/toolbar.ts`. Done when: Save writes the previewed text and Discard restores disk.
2. Handle stale, read-only and external change. Done when: each shows its SPEC message and keeps or restores edits as specified.

- [ ] Send `save` from the toolbar and Ctrl+S in `extensions/vscode/src/webview/toolbar.ts`, only when `canSave`. Done when: saving a model edit writes the previewed text, read back from disk in the test. Cheaper substitute: Save that writes the webview's own serialisation.
- [ ] Show the post-save re-check result from `D02 T01 §6` in the status strip. Done when: a save logs a check and the strip shows its time. Cheaper substitute: assuming the save was valid.
- [ ] Send `discard` with a confirmation when there are edits, restoring the loaded text. Done when: Discard after a rename shows the original cards and "No changes". Cheaper substitute: Discard without confirmation that loses work on a misclick.
- [ ] Show the stale banner when the host reports `stale` or the watcher reports a change, offering Reload (re-read disk) and "Keep my edits" (keep the candidate, Save stays disabled until Reload). Done when: an external edit during a session shows the banner and both choices behave as the SPEC says. Cheaper substitute: silently reloading over edits.
- [ ] Show the read-only refusal with the path, keeping edits. Done when: a read-only pin shows the message and the cards keep their edits. Cheaper substitute: a raw error.
- [ ] Set the panel title's dirty marker from candidate versus disk. Done when: the title gains the marker after an edit and loses it after Save or Discard. Cheaper substitute: no dirty indication.
- [ ] Write `extensions/vscode/test/integration/saveFlow.test.ts` covering save and re-check, discard, stale with both choices, read-only and the dirty marker. Done when: all pass and fail when Keep my edits leaves Save enabled. Cheaper substitute: testing Save only.
- [ ] Assert mockup parity for every scenario this section draws in `extensions/vscode/test/parity/save-discard-and-reload-flow.parity.test.ts` with `expectParity` from D02 T01 §11. Done when: the test passes and fails when one label, description, icon, badge, order or action differs from the mockup's fixture. Cheaper substitute: comparing by eye against the mockup.
- [ ] Commit: `ui: save, discard and reload flow`

**Test checkpoint:** `cd extensions/vscode && npm run test:integration -- --grep saveFlow` passes and fails when the stale banner's Reload is wired to Save.

## 9. Reviewer status and Test reviewer panel

The operator sees whether each reviewer can run and can test one on a planted bug (plan R10, R11). This section shows the `clis` map from the latest `ready` check as a badge on each card, and a Test reviewer action per card that runs `D02 T01 §8` and shows running, review, no review and refused outcomes.

**Phase:** 2
**Needs:** none
**Surface:** yes
**Fidelity:** `design/SPEC.md` §5 Status and Test reviewer; `design/screens/5-dark.png` and `design/screens/5-light.png`.
**Job:** Tell the operator which reviewers will actually run on this machine and prove a reviewer works before relying on it.
**Treatment:** Badge in the card header (found or not found, with the SPEC's text); Test reviewer button; result region under the card with the review text in a scrollable monospace block.
**Chrome:** A running test shows a progress indicator and Cancel; one test runs at a time per panel.

**Build order:**

1. Render badges in `extensions/vscode/src/webview/status.ts`. Done when: each card shows its CLI's state from `clis`.
2. Wire Test reviewer and its outcomes. Done when: the fake-CLI integration test shows review, no review and cancel.

- [ ] Render a badge per card from `clis[cli]` in `extensions/vscode/src/webview/status.ts`, with the SPEC's text for found and not found (not found says a round routed to the reviewer has no review). Done when: a workspace where `agy` is off PATH shows not found on gemini only. Cheaper substitute: a status computed in TypeScript with `which`.
- [ ] Refresh badges after every check and save. Done when: installing a fake CLI on PATH and saving flips the badge. Cheaper substitute: badges set once at open.
- [ ] Add Test reviewer to each card, sent as `test` with the reviewer name, disabled while the candidate is refused or another test runs. Done when: clicking runs the confirmation from `D02 T01 §8`. Cheaper substitute: testing the saved pin when the candidate differs.
- [ ] Show the running state with Cancel wired to the host's cancellation token. Done when: Cancel on a hanging fake CLI ends the run and shows "Cancelled". Cheaper substitute: no cancel.
- [ ] Show the review outcome text verbatim, the skipped reviewer's reason, or the refusal message, per `design/SPEC.md` §5. Done when: each fake-CLI case shows its outcome. Cheaper substitute: success only.
- [ ] Write `extensions/vscode/test/integration/status.test.ts` covering badges, refresh, each outcome and cancel. Done when: all pass and fail when the badge ignores `clis`. Cheaper substitute: a badge render test only.
- [ ] Assert mockup parity for every scenario this section draws in `extensions/vscode/test/parity/reviewer-status-and-test-reviewer-panel.parity.test.ts` with `expectParity` from D02 T01 §11. Done when: the test passes and fails when one label, description, icon, badge, order or action differs from the mockup's fixture. Cheaper substitute: comparing by eye against the mockup.
- [ ] Commit: `ui: reviewer status and Test reviewer`

**Test checkpoint:** `cd extensions/vscode && npm run test:integration -- --grep status` passes and fails when Test reviewer stays enabled on a refused candidate.

## 10. Empty and failure states

**Corrected 2026-10-20:** review of `D00 T01 §4` found that `load_pin` accepts TOML layouts the editor cannot edit in place (inline tables, quoted keys, arrays over several lines); a valid pin in one is the read-only `pin-layout` state (`design/decisions.md`, 2026-10-20; design spec section 2), added below.

When the workspace is not `ready`, the panel replaces the editor with the state's explanation and action (plan R16 to R19, R21). This section renders `no-pin` (the agent request and the `forge.py kit` command, copyable), `refused` (message and Open file), `no-dispatcher` and `old-dispatcher` (the agent request and the `forge.py sync --include-scripts` command, copyable), the SDK source refusal from `D02 T01 §7` (`sdk-path-invalid`), (**Corrected 2026-10-20, read-only kit view, `design/decisions.md`:** `no-pin` opened the side bar kit installer and the dispatcher states the update flow, and the GitHub refusals were rendered; both flows and the GitHub source are dropped), `no-python` (the candidates tried and the setting), `untrusted` (Manage Workspace Trust) and `unsupported-schema`.

**Phase:** 2
**Needs:** none
**Surface:** yes
**Fidelity:** `design/SPEC.md` §7 Empty and failure states; `design/screens/7-dark.png` and `design/screens/7-light.png`.
**Job:** Tell the operator why the editor cannot open the pin and give the one action that fixes it.
**Treatment:** Centred message with the SPEC's heading, body and one primary action per state; commands shown in a copyable code block.
**Chrome:** The toolbar hides Save and Discard in these states; a Retry action re-runs the classification.

**Build order:**

1. Render each state in `extensions/vscode/src/webview/states.ts`. Done when: each workspace under `extensions/vscode/test/fixtures/workspaces/` shows its state.
2. Wire each action. Done when: each action calls its host command and Retry re-classifies.

- [ ] Render `no-pin` saying the reviewer kit is not installed, with the `adopt-conclave` agent request (`D05 T02 §7`) and `python forge.py kit <workspace> reviewer`, each with a Copy button. Done when: the `no-pin` workspace shows both and each copy places its text on the clipboard. Cheaper substitute: writing a default pin from the extension. (**Corrected 2026-10-20, read-only kit view, `design/decisions.md`:** opened the side bar kit installer preset to `reviewer`.)
- [ ] Render `refused` with the `Refused` text verbatim and Open file. Done when: the `refused` workspace shows the dispatcher's message. Cheaper substitute: a generic "invalid pin".
- [ ] Render `no-dispatcher` and `old-dispatcher`, each with its own heading, the agent request to update the kits and `python forge.py sync <workspace> --include-scripts`, each with a Copy button. Done when: both workspaces show their heading and both copy actions. Cheaper substitute: the command only. (**Corrected 2026-10-20, read-only kit view, `design/decisions.md`:** the primary action opened the kit update flow.)
- [ ] Render the SDK source refusal `sdk-path-invalid` from `D02 T01 §7` inside the state that asked for the SDK, with its SPEC text and Open Settings at `conclave.sdkPath`. Done when: a bad `conclave.sdkPath` shows the text and action. Cheaper substitute: one "SDK missing" message. (**Corrected 2026-10-20, read-only kit view, `design/decisions.md`:** also rendered the four GitHub refusals, dropped with the GitHub source in `D02 T01 §21`.)
- [ ] Re-classify the workspace when `.conclave/reviewers.toml` or `scripts/review-dispatch.py` appears or changes, so the editor opens once the agent has installed the kit. Done when: writing the pin into a `no-pin` workspace opens the editor without Retry. Cheaper substitute: Retry only. (**Corrected 2026-10-20, read-only kit view, `design/decisions.md`:** showed forge's installed file list from the dropped install and update flows.)
- [ ] Render `no-python` listing each candidate tried and its reason from `D02 T01 §2`, with Open Settings on `conclave.pythonPath`. Done when: a run with a bad setting shows it. Cheaper substitute: "Python not found".
- [ ] Render `untrusted` with Manage Workspace Trust (`workbench.trust.manage`). Done when: an untrusted run shows it and starts no process. Cheaper substitute: an empty panel.
- [ ] Render `unsupported-schema` naming the found and supported versions. Done when: a stubbed version 2 shows it. Cheaper substitute: rendering it as refused.
- [ ] Render `pin-layout` with `design/SPEC.md` §7's wording, `Open file` and `Retry`, and no editable control. Done when: a webview test with the inline-table pin shows the state, and Retry after the file is rewritten in the editable layout opens the editor. Cheaper substitute: rendering it as refused.
- [ ] Add Retry to every state, re-running the `D02 T01 §3` classification. Done when: fixing the cause and pressing Retry opens the editor. Cheaper substitute: reopening the panel.
- [ ] Write `extensions/vscode/test/integration/emptyStates.test.ts` walking every workspace and state. Done when: all pass and fail when `old-dispatcher` renders as `refused`. Cheaper substitute: two states.
- [ ] Assert mockup parity for every scenario this section draws in `extensions/vscode/test/parity/empty-and-failure-states.parity.test.ts` with `expectParity` from D02 T01 §11. Done when: the test passes and fails when one label, description, icon, badge, order or action differs from the mockup's fixture. Cheaper substitute: comparing by eye against the mockup.
- [ ] Commit: `ui: empty and failure states`

**Test checkpoint:** `cd extensions/vscode && npm run test:integration -- --grep emptyStates` passes and fails when the `old-dispatcher` state shows the `refused` layout.

## 11. Entry points: command, menus and status bar

**Corrected 2026-10-20:** review of `D00 T01 §4` found that `load_pin` accepts TOML layouts the editor cannot edit in place (inline tables, quoted keys, arrays over several lines); a valid pin in one is the read-only `pin-layout` state (`design/decisions.md`, 2026-10-20; design spec section 2), added below.

The operator needs a way in (plan R26). This section contributes the Command Palette command "Conclave: Open Reviewer Settings", an Explorer context menu item and an editor title button on `.conclave/reviewers.toml`, and a status bar item that shows the workspace state from `D02 T01 §3` and opens the panel. Each one opens the panel for the workspace folder that holds the pin, revealing the panel when it is already open.

**Phase:** 2
**Needs:** none
**Surface:** yes
**Fidelity:** `design/SPEC.md` §8 Entry points and SDK source; `design/screens/8-dark.png` and `design/screens/8-light.png`.
**Job:** Let the operator open the reviewer editor from wherever they are, and see the pin's state without opening it.
**Treatment:** Stock VS Code contributions only: a categorised command, `explorer/context` and `editor/title` menu entries with the SPEC's codicon, and a left-aligned status bar item with a codicon and a short state text.
**Chrome:** No custom UI. The status bar tooltip names the state and the folder; the item uses `statusBarItem.errorBackground` only while the pin is refused.

**Build order:**

1. Contribute the command and menus in `extensions/vscode/package.json` and route them in `extensions/vscode/src/host/entryPoints.ts`. Done when: each opens the panel for the right folder.
2. Add the status bar item in `extensions/vscode/src/host/statusItem.ts`. Done when: its text follows the §3 state and clicking it opens the panel.

- [ ] Contribute `conclave.openReviewers` in `extensions/vscode/package.json` `contributes.commands` with `category` `Conclave`, `title` `Open Reviewer Settings` and the SPEC's icon, shown in the Command Palette only while a workspace folder is open (`menus.commandPalette` `when` `workspaceFolderCount > 0`). Done when: the palette lists "Conclave: Open Reviewer Settings". Cheaper substitute: an uncategorised title.
- [ ] Contribute an `explorer/context` entry "Open in Conclave Reviewers" with `when` `resourceFilename == reviewers.toml && resourceDirname =~ /[\\/]\.conclave$/`. Done when: right-clicking the pin shows it and right-clicking any other `reviewers.toml` does not. Cheaper substitute: the item on every TOML file.
- [ ] Contribute an `editor/title` entry in the `navigation` group with the same `when` clause. Done when: opening the pin as text shows the button, and it is absent on other files. Cheaper substitute: a button on every editor.
- [ ] Route the command's `Uri` argument in `extensions/vscode/src/host/entryPoints.ts` to the workspace folder that contains it, falling back to the active editor's folder, then the only folder, then a folder picker. Done when: an integration test on a two-folder workspace opens the second folder's panel from its pin. Cheaper substitute: always the first folder.
- [ ] Create the status bar item in `extensions/vscode/src/host/statusItem.ts` with text from the §3 state and the SPEC's wording (for example `Reviewers: valid`, `Reviewers: 1 problem`, `Reviewers: no pin`, `Reviewers: dispatcher too old`), the folder in the tooltip, and the command `conclave.openReviewers`. Done when: an integration test reads the text for `ready`, `refused` and `no-pin` workspaces. Cheaper substitute: a static "Reviewers" label.
- [ ] Show `layout not editable` with the warning icon in the status bar item for a `pin-layout` workspace (`design/SPEC.md` §7). Done when: the integration test reads it for the inline-table pin. Cheaper substitute: showing `valid`.
- [ ] Show the status item only for a folder with `.conclave/` or `scripts/review-dispatch.py`, following the active editor's folder in a multi-root window. Done when: a folder with neither shows no item. Cheaper substitute: the item in every window.
- [ ] Set `statusBarItem.errorBackground` only while the saved pin or the candidate is refused. Done when: the test reads the background for refused and for ready. Cheaper substitute: a hard-coded red.
- [ ] Write `extensions/vscode/test/integration/entryPoints.test.ts` covering the command, both menus' `when` clauses, folder routing and the status item. Done when: all pass and fail when the `explorer/context` `when` clause is removed. Cheaper substitute: testing the command only.
- [ ] Assert mockup parity for every scenario this section draws in `extensions/vscode/test/parity/entry-points-command-menus-and-status-ba.parity.test.ts` with `expectParity` from D02 T01 §11. Done when: the test passes and fails when one label, description, icon, badge, order or action differs from the mockup's fixture. Cheaper substitute: comparing by eye against the mockup.
- [ ] Commit: `ui: entry points from the palette, menus and status bar`

**Test checkpoint:** `cd extensions/vscode && npm run test:integration -- --grep entryPoints` passes, and fails when the status item text ignores the §3 state.

## Verification

- On the shipped workspace, both themes match `design/screens/` region for region, and every control in `design/SPEC.md` works in the Extension Development Host.
- `npm run test:integration` passes every suite named in §1 to §10.
- `python scripts/todo-graph.py validate` and `python scripts/todo-graph.py plan --check` pass.
