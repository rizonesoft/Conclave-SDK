## Plan review: astra (`gpt-6.2-astra` via `codex`)

- Writer: claude
- Run: 2026-11-19T07:51:58Z
- Candidate: f9078fbd532a3d350ec375093352fe867997d886
- Effort: medium
- Lenses: plan
- Lines: 14
- Digest: 137af59b49ae624a

1. **P1, lines 305, 314, 318-319, 323.** The skill can pass with an empty body. Its acceptance check only excludes project names and machine paths, `skill-copies --check` checks generated copies, and the checkpoint removes a heading from the *page*. Require the installed `project-launchers` skill in all three agent directories to have discovery metadata, point to the installed `docs/launchers.md`, cover creation and removal, and reserve launching for the operator. Check the hand-authored Codex `agents/openai.yaml` separately. Deleting the page reference, the operator-only rule, or the YAML must fail the checkpoint.

2. **P1, lines 313, 316, 318, 323.** A removal heading can survive while the command beneath it omits `-Remove` and **writes** shortcuts. Run the commands taken from the installed page against a scratch project and destination. Require creation to write the expected links and removal to delete those links and their icons while preserving an unrelated link. For the skill’s read-back step, specify how to inspect the saved target, arguments and icon without opening the link. The script’s `link written:` output gives only a path.

3. **P2, lines 316, 318.** The instructions omit choices that affect whether removal finds anything. Document `-ShortcutDir` and `-IconDir`, reusing them for removal, and preserving the same project identity when using `-Distro` and `-Project`. Explain that changing the profile takes effect on rerun, that a successful rerun removes stale everyday links, and that `-Remove` works with an invalid profile. Identify `unattended-shortcut.ps1` as the separate owner of campaign creation and removal when that kit is installed.

4. **P2, lines 316-317, 323.** Topic matching and loading one `url` entry leave the profile instructions largely untested. Use the actual example from the page with the shipped profile and a real project-relative icon. Show the fresh install’s unset `title` and `icon`, the accepted PNG and ICO formats, and the default and effect of `skip_permissions`. Include a working `run` example that identifies which shell interprets it on Windows and WSL. Check that the documented way to diagnose an invalid profile produces the stated refusal and that the documented correction makes the same profile load.

5. **P2, line 320.** The two documentation links resolve in different places. The README lives in the SDK and points into `templates/docs`. The unattended guide lives beside `launchers.md` only after installation. Require the test to follow the README link in the checkout and the unattended link in a project provisioned with `unattended`. A source-tree-relative link can pass in the checkout and break for every operator.

LENS plan: findings  
HIGHEST: P1  
PLAN: gaps  
OVERALL: needs-attention
