# Kits

Reusable stack and agent overlays that AgentForge or Conclave copies into another repository. They do not scaffold an application. They do not install global binaries. Each kit is additive: existing files stay byte-for-byte.

Install **base** on every project (or run `python forge.py init <target>`). Then install the stack kit that matches the app.

```powershell
# Cross-platform via forge.py (Windows PowerShell, macOS, Linux, WSL)
python forge.py kit /path/to/project base
python forge.py kit /path/to/laravel-project laravel
python forge.py kit /path/to/wordpress-project wordpress
```

```bash
# Or directly via bash installers
kits/base/scripts/install.sh /path/to/project
kits/laravel/scripts/install.sh /path/to/laravel-project
kits/wordpress/scripts/install.sh /path/to/wordpress-project
```

Dry-run any of them with `--dry-run`. There is no `--force`.

## Layout

| Kit | What it is | Install when |
| --- | ---------- | ------------ |
| `base/` | Agent overlay (`AGENTS.md`, `.agents`, `.claude`, `.codex`) | Every new repo |
| `laravel/` | Boost MCP, `boost.json`, LSP client, Boost skill, pre-push | Tree has `artisan` |
| `wordpress/` | WP-CLI/PHPCS doctor, WPCS config, safety skill, MCP sample | Has `wp-load.php` |

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

`doctor.sh` is read-only. Missing globals print `setup_required` and still exit 0 unless you pass `--strict`.

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
