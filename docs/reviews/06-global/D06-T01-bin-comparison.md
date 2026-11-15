# R:/Bin comparison, 2026-11-16

Evidence for `D06 T01 §1` (the registered plugin folders) and `§2` (the whole of both folders). Every file under `R:/Bin/claude` and `R:/Bin/codex` (466, with `node_modules` and `__pycache__` set aside as derived) was hashed with line endings normalised and looked up among every blob `origin/main` has held under `global/` and `plugins/` (683 blobs, at `d416eaf`). 378 matched a blob byte for byte. The 88 that did not are listed below by kind; none holds content the repository lacks.

## Differs only in lines naming the old folders (28)

Each was diffed against its closest counterpart, at the import commit `f06262c` or at `main`; every changed line names an old folder, an old repository or the new location, and no other line differs. The count is the changed lines on both sides.

- `R:/Bin/claude/connections/bunny-net/README.md`: `plugins/claude/bunny-net/README.md` at `f06262c`, 12 lines
- `R:/Bin/claude/connections/domains-co-za/README.md`: `plugins/claude/domains-co-za/README.md` at `f06262c`, 14 lines
- `R:/Bin/claude/rules/hooks/article_check.py`: `global/claude/hooks/article_check.py` at `f06262c`, 2 lines
- `R:/Bin/claude/rules/hooks/article_rules.py`: `global/claude/hooks/article_rules.py` at `f06262c`, 2 lines
- `R:/Bin/claude/rules/hooks/verify_install.py`: `global/claude/hooks/verify_install.py` at `f06262c`, 4 lines
- `R:/Bin/claude/scripts/import-bunny-net.sh`: `global/claude/scripts/import-bunny-net.sh` at `f06262c`, 2 lines
- `R:/Bin/claude/scripts/import-domains-co-za.sh`: `global/claude/scripts/import-domains-co-za.sh` at `f06262c`, 2 lines
- `R:/Bin/claude/scripts/register-claude.sh`: `global/claude/scripts/register-claude.sh` at `f06262c`, 2 lines
- `R:/Bin/claude/skills/global/process-ticktick-task/SKILL.md`: `global/claude/skills/process-ticktick-task/SKILL.md` at `f06262c`, 2 lines
- `R:/Bin/codex/atera/README.md`: `plugins/codex/atera/README.md` at `f06262c`, 6 lines
- `R:/Bin/codex/bunny-net/README.md`: `plugins/codex/bunny-net/README.md` at `f06262c`, 2 lines
- `R:/Bin/codex/cloud-access/linux/README.md`: `plugins/codex/cloud-access/linux/README.md` at `f06262c`, 2 lines
- `R:/Bin/codex/cloud-access/README.md`: `plugins/codex/cloud-access/README.md` at `f06262c`, 2 lines
- `R:/Bin/codex/conclave/CLOUD.md`: `plugins/codex/conclave/CLOUD.md` at `f06262c`, 16 lines
- `R:/Bin/codex/conclave/README.md`: `plugins/codex/conclave/README.md` at `f06262c`, 12 lines
- `R:/Bin/codex/docs/brand-permissions/DRAFTS.md`: `plugins/codex/docs/brand-permissions/DRAFTS.md` at `main`, 2 lines
- `R:/Bin/codex/docs/PLUGIN_DESIGN.md`: `plugins/codex/docs/PLUGIN_DESIGN.md` at `main`, 2 lines
- `R:/Bin/codex/domains-co-za/README.md`: `plugins/codex/domains-co-za/README.md` at `f06262c`, 14 lines
- `R:/Bin/codex/outlook-graph/README.md`: `plugins/codex/outlook-graph/README.md` at `f06262c`, 6 lines
- `R:/Bin/codex/pressable/README.md`: `plugins/codex/pressable/README.md` at `f06262c`, 16 lines
- `R:/Bin/codex/rules/codex.md`: `global/codex/rules/codex.md` at `f06262c`, 2 lines
- `R:/Bin/codex/rules/hooks.json`: `global/codex/rules/hooks.json` at `f06262c`, 12 lines
- `R:/Bin/codex/skills/global/process-ticktick-task/SKILL.md`: `global/codex/skills/process-ticktick-task/SKILL.md` at `f06262c`, 2 lines
- `R:/Bin/codex/skills/project/README.md`: `global/codex/skills/file-to-ticktick/README.md` at `f06262c`, 10 lines
- `R:/Bin/codex/skills/README.md`: `global/codex/skills/README.md` at `f06262c`, 8 lines
- `R:/Bin/codex/website-router/DESIGN.md`: `plugins/codex/website-router/DESIGN.md` at `f06262c`, 2 lines
- `R:/Bin/codex/website-router/FILES.md`: `plugins/codex/website-router/FILES.md` at `f06262c`, 4 lines
- `R:/Bin/codex/website-router/README.md`: `plugins/codex/website-router/README.md` at `f06262c`, 8 lines

## The old repositories' own glue and verification logs (9)

No counterpart, left out on purpose (`docs/plans/2026-11-11-sdk-audit-and-roadmap.md`, "Left out: each repository's own glue, verification and deployment logs"): their top-level READMEs and `CLAUDE.md` describe the retired repositories, and the `VERIFICATION.md` files are dated deployment logs.

- `R:/Bin/claude/CLAUDE.md`
- `R:/Bin/claude/connections/bunny-net/docs/VERIFICATION.md`
- `R:/Bin/claude/connections/domains-co-za/docs/VERIFICATION.md`
- `R:/Bin/claude/README.md`
- `R:/Bin/claude/rules/README.md`
- `R:/Bin/codex/README.md`
- `R:/Bin/codex/rules/README.md`
- `R:/Bin/codex/rules/VERIFICATION.md`
- `R:/Bin/codex/skills/VERIFICATION.md`

## Derived, local or backup material (51)

Each file is named under its folder. The site ids in the first folder's names are the connection ids `plugins/codex/website-router/CONNECTIONS.md` already lists.

- `R:/Bin/codex/website-router/.local/` (31 files): one site inventory and the abilities, definitions and tools each connected WordPress site reported, written by `scripts/inspect.mjs` and rebuilt by running it. This is the client site list the owner dropped (roadmap, item 2), and `plugins/codex/**/.local/` is ignored by git.
  - `R:/Bin/codex/website-router/.local/inventory.json`
  - `R:/Bin/codex/website-router/.local/jmr-group-production-abilities.json`
  - `R:/Bin/codex/website-router/.local/jmr-group-production-definitions.json`
  - `R:/Bin/codex/website-router/.local/jmr-group-production-tools.json`
  - `R:/Bin/codex/website-router/.local/redfern-shop-production-abilities.json`
  - `R:/Bin/codex/website-router/.local/redfern-shop-production-definitions.json`
  - `R:/Bin/codex/website-router/.local/redfern-shop-production-tools.json`
  - `R:/Bin/codex/website-router/.local/rizonesoft-abilities.json`
  - `R:/Bin/codex/website-router/.local/rizonesoft-definitions.json`
  - `R:/Bin/codex/website-router/.local/rizonesoft-staging-abilities.json`
  - `R:/Bin/codex/website-router/.local/rizonesoft-staging-definitions.json`
  - `R:/Bin/codex/website-router/.local/rizonesoft-staging-eu-abilities.json`
  - `R:/Bin/codex/website-router/.local/rizonesoft-staging-eu-definitions.json`
  - `R:/Bin/codex/website-router/.local/rizonesoft-staging-eu-tools.json`
  - `R:/Bin/codex/website-router/.local/rizonesoft-staging-tools.json`
  - `R:/Bin/codex/website-router/.local/rizonesoft-tools.json`
  - `R:/Bin/codex/website-router/.local/rizonetech-abilities.json`
  - `R:/Bin/codex/website-router/.local/rizonetech-definitions.json`
  - `R:/Bin/codex/website-router/.local/rizonetech-launch-abilities.json`
  - `R:/Bin/codex/website-router/.local/rizonetech-launch-definitions.json`
  - `R:/Bin/codex/website-router/.local/rizonetech-launch-eu-abilities.json`
  - `R:/Bin/codex/website-router/.local/rizonetech-launch-eu-definitions.json`
  - `R:/Bin/codex/website-router/.local/rizonetech-launch-eu-tools.json`
  - `R:/Bin/codex/website-router/.local/rizonetech-launch-tools.json`
  - `R:/Bin/codex/website-router/.local/rizonetech-tools.json`
  - `R:/Bin/codex/website-router/.local/swiss-hotel-school-staging-abilities.json`
  - `R:/Bin/codex/website-router/.local/swiss-hotel-school-staging-definitions.json`
  - `R:/Bin/codex/website-router/.local/swiss-hotel-school-staging-tools.json`
  - `R:/Bin/codex/website-router/.local/vormann-production-abilities.json`
  - `R:/Bin/codex/website-router/.local/vormann-production-definitions.json`
  - `R:/Bin/codex/website-router/.local/vormann-production-tools.json`
- `R:/Bin/codex/.local/releases/` (5 files): packaged release zips of `conclave`, `pressable` and `website-router`, rebuilt from the sources.
  - `R:/Bin/codex/.local/releases/conclave-0.1.0.zip`
  - `R:/Bin/codex/.local/releases/conclave-0.1.2.zip`
  - `R:/Bin/codex/.local/releases/pressable-0.1.0.zip`
  - `R:/Bin/codex/.local/releases/website-router-0.1.0.zip`
  - `R:/Bin/codex/.local/releases/website-router-0.2.1.zip`
- `R:/Bin/codex/.local/tunnel-client/` (10 files): the downloaded tunnel client v0.0.15. The 7 extracted files are byte for byte the ones under `plugins/codex/.local/tunnel-client/v0.0.15/` (SHA-256 compared); the other 3 are its download zip and two notes on setting it up (`configuration.md`, `onboarding.md`).
  - `R:/Bin/codex/.local/tunnel-client/configuration.md`
  - `R:/Bin/codex/.local/tunnel-client/onboarding.md`
  - `R:/Bin/codex/.local/tunnel-client/tunnel-client-v0.0.15-windows-amd64.zip`
  - `R:/Bin/codex/.local/tunnel-client/v0.0.15/LICENSE`
  - `R:/Bin/codex/.local/tunnel-client/v0.0.15/NOTICE`
  - `R:/Bin/codex/.local/tunnel-client/v0.0.15/cloudflared-manifest.json`
  - `R:/Bin/codex/.local/tunnel-client/v0.0.15/cloudflared.exe`
  - `R:/Bin/codex/.local/tunnel-client/v0.0.15/tunnel-client-v0.0.15-windows-amd64-licenses.txt`
  - `R:/Bin/codex/.local/tunnel-client/v0.0.15/tunnel-client-v0.0.15-windows-amd64.spdx.json`
  - `R:/Bin/codex/.local/tunnel-client/v0.0.15/tunnel-client.exe`
- `R:/Bin/codex/.migration-backup/` (5 files): the Codex configuration, hook file and two scheduled-task definitions saved before the 2026-11-10 move, and a `verify.mjs` check script. Both tasks are live with actions outside `R:/Bin` (`Rizonetech Conclave Cloud Access` running, `Rizonetech Plugin Cloud Access` disabled), and the live configuration has replaced the saved one.
  - `R:/Bin/codex/.migration-backup/conclave-task.xml`
  - `R:/Bin/codex/.migration-backup/provider-task.xml`
  - `R:/Bin/codex/.migration-backup/verify.mjs`
  - `R:/Bin/codex/.migration-backup/windows-config.toml`
  - `R:/Bin/codex/.migration-backup/windows-hooks.json`
