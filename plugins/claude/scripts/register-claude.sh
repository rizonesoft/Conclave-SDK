#!/usr/bin/env bash
# Register (or re-register) every Claude connection plugin in plugins/claude/ with Claude Code at user scope.
# The work is in register_claude.py beside this file, which runs the same way on Windows and in WSL.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
if command -v python3 >/dev/null 2>&1; then PY=python3; else PY=python; fi
exec "$PY" "$HERE/register_claude.py" "$@"
