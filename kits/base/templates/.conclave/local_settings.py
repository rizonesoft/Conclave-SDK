"""Read local project and owner settings from `.conclave/local.toml` and `.private/local.toml`.

Installed by the Conclave-SDK base kit (and shared with kits that read local settings). Every settings reader
calls `read_local_settings(root)` or `load_local_settings(root)`: `.private/local.toml` supplies the owner's
defaults and `.conclave/local.toml` overrides it per key for this machine. A missing file is skipped; a broken
symlink, directory, unreadable file, or invalid TOML is always refused naming the file and reason.
"""

from __future__ import annotations

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
        return tomllib.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise LocalSettingsError(f"{shown}: not readable as UTF-8 TOML ({exc})") from None


def _merge_into(base: dict, override: dict) -> dict:
    """Iteratively merge `override` into freshly parsed `base` in place with `override` winning.
    Merges nested values only when both sides are tables; any other value in `override` (including `[]`, `""`,
    scalars, or a scalar over a table) replaces `base` whole. Iterative so deeply nested TOML never hits
    Python's recursion limit."""
    stack: list[tuple[dict, dict]] = [(base, override)]
    while stack:
        dst, src = stack.pop()
        for key, value in src.items():
            if key in dst and isinstance(dst[key], dict) and isinstance(value, dict):
                stack.append((dst[key], value))
            else:
                dst[key] = value
    return base


def load_local_settings(root: Path | str) -> tuple[dict, tuple[str, ...]]:
    """Load `.private/local.toml` (overlay) and `.conclave/local.toml` (per-machine override) in one pass.

    Returns `(merged_data, loaded_rel_paths)`. Both files are validated whenever present (a broken or malformed
    overlay is refused even when the override is valid, and a broken override is refused rather than silently
    falling back to the overlay). When neither file exists, returns `({}, ())`.
    """
    base_dir = Path(root)
    loaded: list[str] = []
    merged: dict | None = None
    for rel in (OVERLAY, LOCAL):
        try:
            data = read_toml_file(base_dir / rel, label=rel)
        except FileNotFoundError:
            continue
        loaded.append(rel)
        if merged is None:
            merged = data
        else:
            _merge_into(merged, data)
    return (merged if merged is not None else {}), tuple(loaded)


def read_local_settings(root: Path | str) -> dict:
    """Return merged settings from `.private/local.toml` overridden per key by `.conclave/local.toml`."""
    data, _ = load_local_settings(root)
    return data
