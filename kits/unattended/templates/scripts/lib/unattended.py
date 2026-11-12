"""Shared code of the unattended kit. It will hold the run profile loader, the launch lock and claim and the ship counter
(D02 T02 §2 onward); so far it holds only the schema version.

The launcher (`scripts/unattended-run.py`) and the preflight (`scripts/unattended-preflight.py`) will import it.
It holds no project name: the project's own settings live in `.conclave/unattended.json` (the run profile).
"""
from __future__ import annotations

SCHEMA_VERSION = 1
