# Security

## Reporting a vulnerability

Report it privately. Do not open a public issue for a vulnerability.

- While the repository is internal, GitHub offers no private reporting for it: tell the repository owner directly, in a private message, not in an issue or a pull request.
- If the repository is made public, turn on private vulnerability reporting (Settings, Code security) and use the **Security** tab, then **Report a vulnerability**.
- Say what you found, where (a file and line, or a command), what an attacker gains, and the steps that show it.

A confirmed vulnerability is fixed at the layer that owns it, with a test that fails before the fix, and the report is credited unless you ask otherwise.

## What is in scope

- `forge.py`: writing outside the target project, following a link out of it, or overwriting a file a project owns.
- The kits' scripts: the review dispatcher, the todo graph and its stamp, the campaign guard and the automations runner, including what they do with input from a repository they do not trust.
- A credential that any script prints, logs, writes to disk or passes on a command line.

## What the repository never holds

The repository holds no secret. Credentials live in a vault and reach a process through its environment for that run only. A commit that adds a token, a key or a credentials file is a vulnerability: report it the same way.

## Supported versions

The `main` branch is the supported version. A project that copied a kit owns its copy, so a fix here reaches it only when the project takes the change.
