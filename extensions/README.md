# Extensions

Editor extensions for working with Conclave-SDK from an IDE. `forge.py` never copies anything from here into a project; an extension runs `forge.py` itself, from the SDK it bundles or the one the operator points it at.

| Folder | What it is |
| --- | --- |
| `vscode/` | The Conclave VS Code extension: the kit manager and the reviewer pin editor |

The VS Code extension is planned in `docs/plans/2026-10-16-vscode-extension.md` and built through the `todo/` tree. Its Node toolchain stays in its own folder.
