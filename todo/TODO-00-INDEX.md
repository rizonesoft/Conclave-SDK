# TODO-00 -- Root Index

Governing plan: [docs/plans/2026-10-16-vscode-extension.md](../docs/plans/2026-10-16-vscode-extension.md), the Conclave VS Code extension in `extensions/vscode/`. Generated plan: [implementation-plan.md](./implementation-plan.md).

## Active TODOs

| Domain | File | Scope |
| ------ | ---- | ----- |
| 02 | 02-extension-core/TODO-01-extension-core.md | Extension host modules |
| 03 | 03-editor-ui/TODO-01-reviewer-editor-ui.md | Reviewers webview surface |
| 04 | 04-ship/TODO-01-ship-extension.md | Acceptance, vsix, review, marketplace |
| 00 | 00-design/TODO-01-reviewer-editor-design.md | Mockup, SPEC, design spec |
| 05 | 05-kit-manager/TODO-02-kit-view.md | Deferred: Kits view, kit stamp, digest, adopt-conclave |
| 06 | 06-feature-sections/TODO-01-feature-sections.md | Reviewers, rounds; Plan, site deferred |

## Completed TODOs

| Domain | File | Scope | Completed |
| ------ | ---- | ----- | --------- |
| 01 | 01-pin-contract/TODO-01-check-pin-contract.md | check-pin and its contract | 2026-10-20 |
| 05 | 05-kit-manager/TODO-01-kit-manager.md | Superseded by TODO-02-kit-view.md | 2026-10-20 |

The `--check-pin` contract is documented in `kits/reviewer/README.md` and frozen by `tests/test_check_pin_contract.py`. The design it produced: [design/SPEC.md](../design/SPEC.md), [design/decisions.md](../design/decisions.md) and [the design spec](../docs/specs/2026-10-20-vscode-extension-design.md).
