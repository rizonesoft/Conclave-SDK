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


def _merge_into(
    base: dict,
    override: dict,
    origins: dict[tuple[str, ...], str] | None = None,
    source: str = "",
) -> dict:
    """Iteratively merge `override` into freshly parsed `base` in place with `override` winning.
    Merges nested values only when both sides are tables; any other value in `override` (including `[]`, `""`,
    scalars, or a scalar over a table) replaces `base` whole. Iterative so deeply nested TOML never hits
    Python's recursion limit."""
    stack: list[tuple[dict, dict, tuple[str, ...]]] = [(base, override, ())]
    while stack:
        dst, src, prefix = stack.pop()
        for key, value in src.items():
            path = (*prefix, key)
            if key in dst and isinstance(dst[key], dict) and isinstance(value, dict):
                stack.append((dst[key], value, path))
            else:
                was_table = key in dst and isinstance(dst[key], dict)
                dst[key] = value
                if origins is not None:
                    if was_table:
                        prefix_len = len(path)
                        for old in [p for p in origins if len(p) > prefix_len and p[:prefix_len] == path]:
                            del origins[old]
                    origins[path] = source
                    if isinstance(value, dict):
                        _record_origins(value, origins, source, path)
    return base


def _record_origins(
    table: dict,
    origins: dict[tuple[str, ...], str],
    source: str,
    prefix: tuple[str, ...] = (),
) -> None:
    """Iteratively record which file supplied each key path tuple in `table`."""
    stack: list[tuple[dict, tuple[str, ...]]] = [(table, prefix)]
    while stack:
        cur, pref = stack.pop()
        for key, value in cur.items():
            path = (*pref, key)
            origins[path] = source
            if isinstance(value, dict):
                stack.append((value, path))


def load_local_settings_with_origins(root: Path | str) -> tuple[dict, tuple[str, ...], dict[tuple[str, ...], str]]:
    """Load `.private/local.toml` and `.conclave/local.toml` in one pass and return `(merged, loaded, origins)`
    where `origins` maps key-path tuples (e.g. `("vault",)`, `("vault", "cli")`) to the winning file."""
    base_dir = Path(root)
    loaded: list[str] = []
    origins: dict[tuple[str, ...], str] = {}
    merged: dict | None = None
    for rel in (OVERLAY, LOCAL):
        try:
            data = read_toml_file(base_dir / rel, label=rel)
        except FileNotFoundError:
            continue
        loaded.append(rel)
        if merged is None:
            merged = data
            _record_origins(data, origins, rel)
        else:
            _merge_into(merged, data, origins, rel)
    return (merged if merged is not None else {}), tuple(loaded), origins


def load_local_settings(root: Path | str) -> tuple[dict, tuple[str, ...]]:
    """Load `.private/local.toml` (overlay) and `.conclave/local.toml` (per-machine override) in one pass.

    Returns `(merged_data, loaded_rel_paths)`. Both files are validated whenever present (a broken or malformed
    overlay is refused even when the override is valid, and a broken override is refused rather than silently
    falling back to the overlay). When neither file exists, returns `({}, ())`.
    """
    merged, loaded, _ = load_local_settings_with_origins(root)
    return merged, loaded


def read_local_settings(root: Path | str) -> dict:
    """Return merged settings from `.private/local.toml` overridden per key by `.conclave/local.toml`."""
    data, _ = load_local_settings(root)
    return data
