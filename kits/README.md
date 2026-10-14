# Kits

Reusable stack and agent overlays that Conclave-SDK copies into a new or existing repository for **Gemini / Antigravity (`.agents/`)**, **Claude Code (`.claude/`)**, and **OpenAI Codex (`.codex/`)**. They do not scaffold an application. They do not install global binaries. Each kit is additive: existing files stay byte-for-byte.

Install **base** on every project (or run `python forge.py init <target>`). Then install the stack kit that matches the app.

```powershell
# Cross-platform via forge.py (supports --agent all|gemini|agy|claude|codex)
python forge.py kit /path/to/project base
python forge.py kit /path/to/laravel-project laravel
python forge.py kit /path/to/wordpress-project wordpress
python forge.py doctor /path/to/project
```

```bash
# Or directly via bash installers in Linux / WSL / Git Bash
kits/base/scripts/install.sh /path/to/project
kits/laravel/scripts/install.sh /path/to/laravel-project
kits/wordpress/scripts/install.sh /path/to/wordpress-project
```

Dry-run any of them with `--dry-run`. There is no `--force`.

## Layout

| Kit | What it is | Install when |
| --- | ---------- | ------------ |
| `base/` | Agent overlay (`AGENTS.md`, `GEMINI.md`, `CLAUDE.md`, `CODEX.md`, safety skills) | Every new repository (not a stack) |
| `laravel/` | Boost MCP, `boost.json`, stdio LSP client, `laravel-boost` skill, pre-push hook | Tree has `artisan` (root or child) |
| `wordpress/` | WP-CLI/PHPCS doctor, WordPress-Extra config, site-safety skill, MCP example | Tree has `wp-load.php` or `wp-config.php` |

`base` is the generic agent layer. Laravel and WordPress kits do not copy it. Install `base` (or `forge.py init`) first when the target should speak the 3-agent contract.

## Each kit

```text
kits/<name>/
  README.md
  scripts/install.sh
  scripts/test-install.sh
  scripts/doctor.sh     # stack kits; read-only
  templates/            # files copied into the target
```

`doctor` (`python forge.py doctor <target>` or `scripts/doctor.sh`) is read-only. Missing globals print `setup_required` and still exit 0 unless you pass `--strict`.

## Tests

```powershell
python -m unittest discover -s tests -v
```

```bash
bash kits/base/scripts/test-install.sh
bash kits/laravel/scripts/test-install.sh
bash kits/wordpress/scripts/test-install.sh
```

## Operator globals

Stack kits never run `composer global` or `npm install -g`. The doctor names them.
