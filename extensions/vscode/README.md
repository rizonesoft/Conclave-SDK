# Conclave for VS Code

The Conclave VS Code extension: the reviewer pin editor for repositories provisioned by Conclave-SDK. It edits and tests `.conclave/reviewers.toml` through the workspace's own `scripts/review-dispatch.py`; it does not show, install or update kits (the `adopt-conclave` skill does that through `forge.py`). It is planned in `docs/plans/2026-10-16-vscode-extension.md`, designed in `docs/specs/2026-10-20-vscode-extension-design.md` and `design/SPEC.md`, and built through the SDK's `todo/` tree.

## Develop

Every command runs from this folder (`extensions/vscode/`); the Node toolchain stays here and `forge.py` never copies anything from it. It needs Node 22.13 or later in the 22 line, or Node 24 or later (`engines.node` in `package.json`, the floor of the locked dependencies; `.npmrc` sets `engine-strict`, so `npm ci` refuses an older Node instead of failing later): the VS Code test tools require it, and `npm test`'s glob needs Node 21's `node --test` patterns.

```bash
npm ci                    # install the pinned dev dependencies
npm run build             # bundle src/extension.ts to dist/extension.js
npm run lint              # ESLint over src and test
npm test                  # compile, then the unit tests (node --test) under test/unit
npm run test:integration  # compile, build, then the integration tests in a downloaded VS Code
```

Pure logic lives in `src/core/` with no `vscode` import, so the unit tests run it under plain Node; VS Code glue lives in `src/host/`. The integration tests open `test/fixtures/workspaces/shipped/`, a workspace holding the reviewer kit's shipped pin. `test/fixtures/pins/` is shared with the SDK's `tests/test_check_pin_contract.py`, which freezes the `--check-pin` contract the extension reads.

To try it by hand, open this folder in VS Code and run "Run Conclave" from the Run and Debug view.
