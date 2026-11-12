"""Shared code of the unattended kit: the run profile, the launch lock and claim, the ship counter.

The launcher (`scripts/unattended-run.py`) and the preflight (`scripts/unattended-preflight.py`) import this module.
It holds no project name: the project's own settings live in `.conclave/unattended.json` (the run profile).
"""
from __future__ import annotations

SCHEMA_VERSION = 1
