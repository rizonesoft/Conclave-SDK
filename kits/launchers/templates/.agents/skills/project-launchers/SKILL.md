---
name: project-launchers
description: Use when the operator asks to create, update, inspect, or remove Windows desktop shortcuts for this project, or when the project's title or icon changes.
---

# Project launchers

Follow the installed [docs/launchers.md](../../../docs/launchers.md) for `.conclave/launchers.json` fields, worked examples, refusal diagnosis, and all creation and removal commands. Do not duplicate or invent flags outside that guide.

## Steps

1. When the operator asks only to inspect existing shortcuts, skip creation and removal and go straight to step 3 (read-back works even when `.conclave/launchers.json` is invalid).
2. When creating, updating, or removing shortcuts, read `docs/launchers.md`, diagnose `.conclave/launchers.json` with `python scripts/lib/launchers.py show` when creating or updating, and run the documented creation or `-Remove` command in PowerShell 7 (`pwsh`) on Windows (reusing `-ShortcutDir`, `-IconDir`, `-Distro`, and `-Project` when removing).
3. Read each `.lnk` back in a fresh PowerShell 7 (`pwsh`) process without launching it, passing the shortcut path on standard input (`[Console]::In.ReadLine()`, outside the command text so apostrophes and `$` characters are never interpolated):

```powershell
'<path-to-link.lnk>' | pwsh -NoProfile -Command 'Add-Type -Path scripts/lib/ShellLink.cs; [Conclave.ShellLink]::Read([Console]::In.ReadLine()) | Format-List Target, Arguments, IconPath, Description'
```

4. Report the verified link paths, targets, arguments, and icons to the operator.

## Rule

A generated desktop shortcut is only ever started by the operator. Never launch, invoke, or double-click a `.lnk` file from an agent session.
