# Kits

Reusable stack and agent overlays that Conclave-SDK copies into a new or existing repository for **Gemini / Antigravity (`.agents/`)**, **Claude Code (`.claude/`)**, and **OpenAI Codex (`.codex/`)**. They do not scaffold an application. They do not install global binaries. Each kit is additive: existing files stay byte-for-byte.

Install **base** on every project (or run `python forge.py init <target>`). Add **todo** where work is planned in TODO files and **reviewer** where work gets independent review. Then install the stack kit that matches the app.

```powershell
# Cross-platform via forge.py (supports --agent all|gemini|agy|claude|codex)
python forge.py kit /path/to/project base
python forge.py kit /path/to/project todo
python forge.py kit /path/to/project reviewer
python forge.py kit /path/to/laravel-project laravel
python forge.py kit /path/to/wordpress-project wordpress --host pressable   # or --host wpcom
python forge.py doctor /path/to/project
```

```bash
# Or directly via bash installers in Linux / WSL / Git Bash
kits/base/scripts/install.sh /path/to/project
kits/todo/scripts/install.sh /path/to/project
kits/reviewer/scripts/install.sh /path/to/project
kits/laravel/scripts/install.sh /path/to/laravel-project
kits/wordpress/scripts/install.sh /path/to/wordpress-project --host wpcom
```

Dry-run any of them with `--dry-run`. There is no `--force`.

`forge.py` notes what it installed in the project's `.conclave/kits.json`: the SDK commit, and for each file it wrote its kit and a digest of its bytes as installed. A file the project already had is never recorded. The record holds no path to the SDK and the project may delete it. The bash installers write no record.

## Layout

| Kit | What it is | Install when |
| --- | ---------- | ------------ |
| `base/` | Agent overlay: the four entry docs, safety skills | Every new repository (not a stack) |
| `todo/` | TODO skills, `todo-graph.py`, starter `todo/` tree | Work is planned in TODO files |
| `reviewer/` | Reviewer pin, review dispatcher, review skill | Independent review |
| `laravel/` | Boost MCP, `boost.json`, LSP, `laravel-boost`, pre-push hook | Tree has `artisan` |
| `wordpress/` | Site pin, pinned SSH/SFTP, WordPress MCP, DDEV, PHPCS | WordPress site project |

`base` is the generic agent layer. Laravel and WordPress kits do not copy it. Install `base` (or `forge.py init`) first when the target should speak the 3-agent contract.

## Each kit

```text
kits/<name>/
  README.md
  scripts/install.sh
  scripts/test-install.sh
  scripts/doctor.sh     # stack kits; read-only
  templates/            # files copied into the target
  hosts/<host>/templates/  # wordpress only: per-host files (pressable, wpcom)
```

`doctor` (`python forge.py doctor <target>` or `scripts/doctor.sh`) is read-only. Missing globals print `setup_required` and still exit 0 unless you pass `--strict`.

## Tests

The quick suite takes about a minute and includes a fresh install that runs a section through every review pass to its stamp. The full suite adds the stamp tests and the reviewer kit's own suite (several minutes): run it when a change touches the stamp, the dispatcher or the pin loader, and before a release.

```powershell
python -m unittest discover -s tests -v
$env:CONCLAVE_FULL_TESTS = '1'; python -m unittest discover -s tests -v; Remove-Item Env:CONCLAVE_FULL_TESTS
```

```bash
bash kits/base/scripts/test-install.sh
bash kits/todo/scripts/test-install.sh
bash kits/reviewer/scripts/test-install.sh
bash kits/laravel/scripts/test-install.sh
bash kits/wordpress/scripts/test-install.sh
```

## Operator globals

Stack kits never run `composer global` or `npm install -g`. The doctor names them.
