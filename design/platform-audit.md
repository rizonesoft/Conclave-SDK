# Platform audit of the mockup

Date: 2026-10-16. Mockup: <https://claude.ai/artifact/RRxxX5W6pYFQ3b2Z4Fq2mv>, source `design/mockup/project/`. Purpose: make every element the extension draws buildable 1:1 before the owner approves the mockup, so nothing is approximated during the build.

Each element is one of three kinds. **Native** is drawn by VS Code from the extension API, so the mockup may only show what that API can render. **Webview** is the extension's own HTML (the Reviewers editor; the kit installer was too until it was dropped on 2026-10-20), so it can match the mockup exactly. **Chrome** is VS Code itself or the mockup's own controls, drawn for context and never built.

## Changed in the mockup by this audit

- Icons (native and webview): every hand-drawn icon is now the real codicon, drawn inline from the SVG sources of `@vscode/codicons` 0.0.45 (the icon set VS Code uses), so the build names the same icon (`ThemeIcon` ids in trees and title actions, the bundled codicon font in the webviews). Two names are aliases with no source of their own: `circle-large-outline` is drawn from `circle-large`, and `repo-create` is only a plus, so Set up a new repository uses `new-folder`. Only the Conclave mark stays an SVG.
- Kit health badge (native, Kits tree): a `TreeItem` has no badge. The pill ("ok" or a count on a tinted background) became a `FileDecoration` on the item's `resourceUri`: at most two characters, coloured text without a background, and the label tinted the same colour. A healthy kit now has no decoration; its state icon already says installed.
- Group rows (native, Reviewers and Plan sections): a `TreeItem` label cannot be bold or a different size, so "Routes" and "Ready now" are plain labels.
- View title actions (native, every section header): VS Code shows them only while the pane is hovered or focused (unless the user sets `workbench.view.alwaysShowHeaderActions`). The mockup now hides them otherwise; a pane with a selected row or the open installer counts as focused.
- Reviewers tab (native): a `WebviewPanel` has no dirty dot (only custom editors have one, open question 4), so unsaved edits now show as "(unsaved)" in the panel title. Its icon is an image (`WebviewPanel.iconPath` takes light and dark files, not a codicon), so the tab shows the Conclave mark.
- Notifications (native): the save and refresh messages are `showInformationMessage` notifications, so the mockup's toast gained the close button VS Code draws.

## Native elements that already fit

- Activity Bar: `viewsContainers.activitybar` with `media/conclave.svg`; the count badge is `TreeView.badge` (`ViewBadge`, a number and a tooltip).
- Section headers: one view per section in the `conclave` container; `TreeView.description` gives the folder name or the "N of M verified" text beside the title; `TreeView.title` can change at run time.
- Tree rows: `label`, `description` (always the muted colour), `iconPath` as a `ThemeIcon` with a `ThemeColor`, `tooltip`, `collapsibleState`, and inline actions from `menus.view/item/context` group `inline`, shown on hover and on the selected row.
- State colours map to theme colours: installed and ok `testing.iconPassed`, partly installed and setup required `list.warningForeground`, missing and error `list.errorForeground`, info and ready `notificationsInfoIcon.foreground`, not installed and blocked `disabledForeground`.
- Hiding a section without its kit: `when` clauses on context keys (`conclave.kit.<kit>`); Switch folder: a view title action with `when` `workspaceFolderCount > 1`.
- Status bar: `StatusBarItem` text with `$(codicon)` prefixes and a tooltip; only the error and warning background colours exist, and the mockup uses neither.
- ~~Installer and update result panes: each a `WebviewView` in the `conclave` container (INSTALL KIT and UPDATE KITS), shown by a context key while an install is open or an update result is waiting; Close is a view title action, and an update started from the Command Palette reveals the container first.~~ (dropped 2026-10-20 with the install, update and new repository flows, `design/decisions.md`, Read-only kit view and agent import).

## Native elements added for entry points, update and new repository (`D00 T01 §1`)

- Command Palette: `contributes.commands` with `category` `Conclave`; the palette lists them as "Conclave: <title>".
- Explorer context menu: `menus.explorer/context` in the `navigation` group, shown for `.conclave/reviewers.toml` only (`when` on `resourcePath`); the rest of the menu is VS Code's.
- Editor title button: `menus.editor/title` with the Conclave mark, shown for the pin open as text; the ellipsis next to it is VS Code's.
- Status bar item: a `StatusBarItem` with a `$(pass)`, `$(error)` or `$(warning)` codicon, the state text, a tooltip and a command.
- ~~Quick picks: `createQuickPick` with `title`, `step` and `totalSteps`, `QuickInputButtons.Back` on later steps, and for kits `canSelectMany` (VS Code draws the toggle-all checkbox, the count and OK). A QuickPick has no message line, so the update scope sits in the confirmation dialog.~~ (dropped 2026-10-20 with the install, update and new repository flows, `design/decisions.md`, Read-only kit view and agent import); the Switch folder pick stays a plain `showQuickPick`.
- ~~The folder step: `createInputBox` with its `prompt` under the input, Browse as a title `QuickInputButton` with the `folder` codicon, and Enter to accept; an input box has no list and no OK button.~~ (dropped 2026-10-20 with the install, update and new repository flows, `design/decisions.md`, Read-only kit view and agent import).
- ~~Confirmation dialogs: `showInformationMessage` with `modal: true`, `detail` and button labels. The mockup draws VS Code's custom dialog style; with `window.dialogStyle` set to `native` (the default on Windows) the system draws the same message, detail and buttons in its own box.~~ (dropped 2026-10-20 with the install, update and new repository flows, `design/decisions.md`, Read-only kit view and agent import).
- ~~Notifications with actions: `showInformationMessage` and `showErrorMessage` with item labels (Open, Open in New Window, Add to Workspace, Show log); they stay until answered.~~ (dropped 2026-10-20 with the install, update and new repository flows, `design/decisions.md`, Read-only kit view and agent import).

## Native elements added for the read-only kit view (`D00 T01 §7`, 2026-10-20)

- Kit stamps: a `TreeItem` with `ThemeIcon` `arrow-circle-up` (`notificationsInfoIcon.foreground`) and description `newer kits than this extension`, or `arrow-circle-down` (`list.warningForeground`) and `older kits than this extension`; the tooltip names the stamp's commit and date and what to do.
- Kit context menu: `menus.view/item/context` on kit items, with `Health`, `Copy import request` and, on older kits, `Copy update request`; each copy is `vscode.env.clipboard.writeText` and a `showInformationMessage` naming what was copied.
- A folder with no kit, and an unusable `conclave.sdkPath`: the Kits view's `viewsWelcome` content (text and a command button) in place of the tree.
- The editor's no-pin and dispatcher states (webview): the agent request and the forge command in code blocks, each with a Copy button.

## Webview elements

- The Reviewers editor is HTML (the installer body was too, dropped 2026-10-20). They match the mockup if they use the same tokens mapped to `--vscode-*` variables (`D00 T01 §1`), the bundled codicon font (allowed by the webview CSP through `webview.cspSource`), and the same markup and text.

## Chrome, never built

- The mockup control bar (theme, scenario, SDK source, workspace), the title bar and window controls, the menus, the other Activity Bar icons, the Explorer and its files, the status bar's branch, problems, encoding and line ending items, and the second editor tab.
- The example data (the orchard workspace, its plan, round records and site) is test input for the parity fixtures, not product content.

## Limits that stay

- Pane sizes: VS Code splits the side bar between open panes and the user drags the sashes; the mockup's heights are one possible layout.
- Tree indentation, row height and the twisty are VS Code's own (8 px per level plus the twisty, 22 px rows); the mockup imitates them.
- A `FileDecoration` badge cannot exceed two characters, so a kit with more than 99 failing checks shows 99.
