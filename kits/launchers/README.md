# Launchers kit

Gives any project the same family of Windows desktop links: `<Title> (<Agent>)` opens the project in a coding agent, and any further link the project declares runs a command in the project or opens its site. Every icon is the project's own icon with a mark in its corner, rendered on the machine. A Laravel, static or other web project gets the same shape as a WordPress one.

## What it needs and how to install it

It needs no other kit. The links are Windows shortcuts, so they are written on Windows; a project that lives in WSL is opened through `wsl.exe`, and a project on a Windows drive through PowerShell. Install it with `python forge.py kit <project> launchers`, set the project's title and icon in `.conclave/launchers.json`, and check it with `python forge.py doctor <project> launchers`. The SDK does not install this kit in itself (`SELF_KITS` in `forge.py`).

## What it installs

| File | What it is |
| ---- | ---------- |
| `.conclave/launchers.json` | The profile: the title, the icon, the agents that get a link, and further links |

## Doctor

`python forge.py doctor <project> launchers` reports:

- `profile`: `ok` when `.conclave/launchers.json` is there, `setup_required` with the install command when it is not.
