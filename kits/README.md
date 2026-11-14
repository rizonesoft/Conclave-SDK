# Kits

Reusable stack and agent overlays that Conclave-SDK copies into a new or existing repository for **Gemini / Antigravity (`.agents/`)**, **Claude Code (`.claude/`)**, and **OpenAI Codex (`.codex/`)**. They do not scaffold an application. They do not install global binaries. Each kit is additive: existing files stay byte-for-byte.

Install **base** on every project (or run `python forge.py init <target>`). Add **todo** where work is planned in TODO files and **reviewer** where work gets independent review. Add **unattended** (after **todo**) where a `process-plan` run should keep going with nobody at the keyboard: it is being built in `todo/02-unattended/TODO-02-unattended-kit.md`, and the SDK does not install it in itself. Then install the stack kit that matches the app.

```powershell
# Cross-platform via forge.py (supports --agent all|gemini|agy|claude|codex)
python forge.py kit /path/to/project base
python forge.py kit /path/to/project todo
python forge.py kit /path/to/project reviewer
python forge.py kit /path/to/project unattended   # after todo; runs in Linux or WSL (tmux)
python forge.py kit /path/to/laravel-project laravel
python forge.py kit /path/to/wordpress-project wordpress --host pressable   # or --host wpcom
python forge.py doctor /path/to/project
```

`forge.py` is the only installer, on Windows, Linux and WSL alike. Dry-run any kit with `--dry-run`. There is no `--force`.

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
  templates/            # files copied into the target
  hosts/<host>/templates/  # wordpress only: per-host files (pressable, wpcom)
```

`doctor` (`python forge.py doctor <target> [<kit>]`) is read-only and prints its report as JSON. Missing globals are reported as `setup_required` and it still exits 0 unless you pass `--strict` (exit 3); a target that is not a folder exits 2.

## Tests

The quick suite takes about a minute and includes a fresh install that runs a section through every review pass to its stamp. The full suite adds the stamp tests and the reviewer kit's own suite (several minutes): run it when a change touches the stamp, the dispatcher or the pin loader, and before a release.

```powershell
python -m unittest discover -s tests -v
$env:CONCLAVE_FULL_TESTS = '1'; python -m unittest discover -s tests -v; Remove-Item Env:CONCLAVE_FULL_TESTS
```

Each kit's install is tested in `tests/test_kit_install.py`, on every host. `python forge.py check-all` runs every suite the repository holds (`--only <name>` and `--skip <name>` choose suites, `--full` adds the gated tests), and refuses a test file no suite runs.

```powershell
python -m unittest tests.test_kit_install
python forge.py check-all
```

## Operator globals

Stack kits never run `composer global` or `npm install -g`. The doctor names them.
