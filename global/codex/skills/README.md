# Codex skills

`global/` contains only `process-ticktick-task` and `file-to-ticktick`, installed for every project on Windows and WSL. `project/` holds portable repository-specific skills and is not accepted by the global deployer. Plugin-bundled skills stay with their plugins.

[Official Codex skill documentation](https://developers.openai.com/codex/skills) identifies `$HOME/.agents/skills` as the user-level directory (checked 13 October 2026). The deployer targets that location, independent of CODEX_HOME. It does not modify bundled system skills or legacy `$CODEX_HOME/skills` copies. If duplicate names are reported, inspect the duplicate before changing it.

Preview and deploy from `R:\Codex`:

```powershell
python skills/deploy.py process-ticktick-task
python skills/deploy.py file-to-ticktick
python skills/deploy.py process-ticktick-task --apply
python skills/deploy.py file-to-ticktick --apply
wsl.exe -e python3 /mnt/r/Codex/skills/deploy.py process-ticktick-task --apply
wsl.exe -e python3 /mnt/r/Codex/skills/deploy.py file-to-ticktick --apply
```

From WSL use `python3 /mnt/r/Codex/skills/deploy.py <name> [--apply]`. Only a direct folder name beneath this repository's `skills/global` is accepted. Paths, traversal, symlinks and junctions are refused. Installation verifies SHA256 for every source/destination file, excludes `__pycache__` and bytecode, and replaces only the named deployed skill. Existing copies are kept outside discovery under `~/.codex/skill-backups/<name>-<timestamp>`. Other skills are untouched. On failure, inspect the reported backup and destination before retrying.

Run all skill tests on each platform:

```text
python -m unittest discover -s skills/global/process-ticktick-task/scripts
python -m unittest discover -s skills/tests
```

Use `python3` in WSL. See [verification](VERIFICATION.md) for live checks, platform versions and remaining Outlook limitations. These skills were ported from a supplied reference design into independent Codex-owned source. They neither call nor load that reference at runtime.
