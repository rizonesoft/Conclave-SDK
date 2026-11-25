#!/usr/bin/env python3
"""Loader and validator for `.conclave/desktop-tests.json` (D04 T04 s1). Stdlib only."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

CONFIG_REL = Path(".conclave/desktop-tests.json")
PREFIX_RE = re.compile(r"^[a-z][a-z0-9-]{0,31}$")
HHMM_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
ALLOWED_KEYS = frozenset({
    "schema_version", "prefix", "window_opens", "window_closes",
    "idle_minutes", "history_limit", "log_limit", "test_command",
})


class ConfigError(ValueError):
    """Raised when `.conclave/desktop-tests.json` is missing, unreadable, or invalid."""


def _whole_positive(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def _parse_hhmm(value: object, field: str) -> tuple[int, int]:
    if not isinstance(value, str):
        raise ConfigError(f"{field}: must be an HH:MM string")
    m = HHMM_RE.fullmatch(value)
    if not m:
        raise ConfigError(f"{field}: must be HH:MM (00:00 to 23:59), got {value!r}")
    return int(m.group(1)), int(m.group(2))


def env_prefix(prefix: str) -> str:
    return prefix.upper().replace("-", "_")


def validate_config(data: object, *, allow_unset: bool = False) -> dict:
    if not isinstance(data, dict):
        raise ConfigError("config root must be a JSON object")
    unknown = sorted(set(data) - ALLOWED_KEYS)
    if unknown:
        raise ConfigError(f"unknown key(s): {', '.join(unknown)}")
    missing = sorted(ALLOWED_KEYS - set(data))
    if missing:
        raise ConfigError(f"missing key(s): {', '.join(missing)}")
    if data["schema_version"] != 1 or isinstance(data["schema_version"], bool):
        raise ConfigError("schema_version: must be 1")
    prefix = data["prefix"]
    if prefix is None:
        if not allow_unset:
            raise ConfigError("prefix: must be set (lower-case letters, digits, hyphens)")
    elif not isinstance(prefix, str) or not PREFIX_RE.fullmatch(prefix):
        raise ConfigError(f"prefix: must match ^[a-z][a-z0-9-]{{0,31}}$, got {prefix!r}")
    opens_h, opens_m = _parse_hhmm(data["window_opens"], "window_opens")
    closes_h, closes_m = _parse_hhmm(data["window_closes"], "window_closes")
    if (opens_h, opens_m) == (closes_h, closes_m):
        raise ConfigError("window_closes: must differ from window_opens")
    for field in ("idle_minutes", "history_limit", "log_limit"):
        if not _whole_positive(data[field]):
            raise ConfigError(f"{field}: must be a positive whole number")
    test_cmd = data["test_command"]
    if test_cmd is not None:
        if not isinstance(test_cmd, list) or not test_cmd or not all(isinstance(c, str) and c for c in test_cmd):
            raise ConfigError("test_command: must be null or a non-empty list of non-empty strings")
    result = dict(data)
    result["env_prefix"] = env_prefix(prefix) if isinstance(prefix, str) else None
    return result


def load_config(path: Path | None = None, root: Path | None = None, *, allow_unset: bool = False) -> dict:
    if path is None:
        base = Path(root) if root is not None else Path.cwd()
        path = base / CONFIG_REL
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"cannot read {path}: {exc}") from exc
    try:
        parsed = json.loads(raw)
    except ValueError as exc:
        raise ConfigError(f"invalid JSON in {path}: {exc}") from exc
    return validate_config(parsed, allow_unset=allow_unset)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate and print .conclave/desktop-tests.json")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_show = sub.add_parser("show", help="Validate and print the config as one JSON line")
    p_show.add_argument("--root", default=".", help="Project root holding .conclave/desktop-tests.json")
    p_show.add_argument("--allow-unset", action="store_true", help="Allow prefix: null (fresh install check)")
    args = parser.parse_args(argv)
    try:
        cfg = load_config(root=Path(args.root), allow_unset=args.allow_unset)
    except ConfigError as exc:
        print(f"desktop-tests: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(cfg, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
