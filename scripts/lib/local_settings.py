"""Read local project and owner settings from `.conclave/local.toml` and `.private/local.toml`.

Installed by the Conclave-SDK base kit (and shared with kits that read local settings). Every settings reader
calls `read_local_settings(root)` or `load_local_settings(root)`: `.private/local.toml` supplies the owner's
defaults and `.conclave/local.toml` overrides it per key for this machine. A missing file is skipped; a broken
symlink, directory, unreadable file, or invalid TOML is always refused naming the file and reason.
"""

from __future__ import annotations

import copy
from pathlib import Path
import tomllib

LOCAL = ".conclave/local.toml"
OVERLAY = ".private/local.toml"


class LocalSettingsError(ValueError):
    """Raised when a local or overlay settings file cannot be read or parsed as UTF-8 TOML."""


def read_toml_file(path: Path | str, *, label: str | None = None) -> dict:
    """Read and parse one UTF-8 TOML file. Raises FileNotFoundError only when the path is genuinely absent
    (not a broken symlink); raises LocalSettingsError for a broken symlink, directory, I/O error, or bad TOML."""
    target = Path(path)
    shown = label if label is not None else str(target)
    if target.is_symlink() and not target.exists():
        raise LocalSettingsError(f"{shown}: not readable as UTF-8 TOML (broken symlink)")
    try:
        raw = target.read_bytes()
    except FileNotFoundError:
        if target.is_symlink():
            raise LocalSettingsError(f"{shown}: not readable as UTF-8 TOML (broken symlink)") from None
        raise
    except OSError as exc:
        raise LocalSettingsError(f"{shown}: not readable as UTF-8 TOML ({exc})") from None
    try:
        data = tomllib.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise LocalSettingsError(f"{shown}: not readable as UTF-8 TOML ({exc})") from None
    return data


def _merge_tables(base: dict, override: dict) -> dict:
    """Deep-merge two TOML tables per key with `override` winning. Recurses only when both values are tables;
    any other value in `override` (including `[]`, `""`, scalars, or a scalar over a table) replaces `base` whole."""
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _merge_tables(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def load_local_settings(root: Path | str) -> tuple[dict, tuple[str, ...]]:
    """Load `.private/local.toml` (overlay) and `.conclave/local.toml` (per-machine override) in one pass.

    Returns `(merged_data, loaded_rel_paths)`. Both files are validated whenever present (a broken or malformed
    overlay is refused even when the override is valid, and a broken override is refused rather than silently
    falling back to the overlay). When neither file exists, returns `({}, ())`.
    """
    base_dir = Path(root)
    loaded: list[str] = []
    tables: list[dict] = []
    for rel in (OVERLAY, LOCAL):
        try:
            data = read_toml_file(base_dir / rel, label=rel)
        except FileNotFoundError:
            continue
        loaded.append(rel)
        tables.append(data)
    if not tables:
        return {}, ()
    merged = copy.deepcopy(tables[0])
    for extra in tables[1:]:
        merged = _merge_tables(merged, extra)
    return merged, tuple(loaded)


def read_local_settings(root: Path | str) -> dict:
    """Return merged settings from `.private/local.toml` overridden per key by `.conclave/local.toml`."""
    data, _ = load_local_settings(root)
    return data
