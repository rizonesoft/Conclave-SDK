---
name: project-launchers
description: Use when the operator asks to create, update, inspect, or remove Windows desktop shortcuts for this project, or when the project's title or icon changes.
---

# Project launchers

Follow the installed [docs/launchers.md](../../../docs/launchers.md) for `.conclave/launchers.json` fields, worked examples, refusal diagnosis, and all creation and removal commands. Do not duplicate or invent flags outside that guide.

## Steps

1. Read `docs/launchers.md` and inspect `.conclave/launchers.json`, diagnosing any profile error with `python scripts/lib/launchers.py show`.
2. Run the creation or `-Remove` command from `docs/launchers.md` in PowerShell 7 (`pwsh`) on Windows (reusing `-ShortcutDir`, `-IconDir`, `-Distro`, and `-Project` when removing).
3. After writing shortcuts, read each generated `.lnk` back in a fresh PowerShell 7 (`pwsh`) process without launching it by loading `scripts/lib/ShellLink.cs` and inspecting `Target`, `Arguments`, and `IconPath`:

```powershell
pwsh -NoProfile -Command "Add-Type -Path 'scripts/lib/ShellLink.cs'; [Conclave.ShellLink]::Read('<path-to-link.lnk>') | Format-List Target, Arguments, IconPath, Description"
```

4. Report the verified link paths, targets, arguments, and icons to the operator.

## Rule

A generated desktop shortcut is only ever started by the operator. Never launch, invoke, or double-click a `.lnk` file from an agent session.
