"""Bounded OOXML package unpacker enforcing entry, size, path, and symlink checks."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

try:
    from helpers import OOXML_FAMILY, safe_extract
except ImportError:
    from office.helpers import OOXML_FAMILY, safe_extract


def unpack_package(package: Path, dest: Path) -> None:
    """Safely unpack an OOXML package into an empty or non-existent directory."""
    if not package.is_file():
        raise ValueError(f"{package} is not a file")
    if package.suffix.lower() not in OOXML_FAMILY:
        raise ValueError(
            f"{package} must be one of: {', '.join(sorted(OOXML_FAMILY))}"
        )
    if dest.is_symlink():
        raise ValueError(f"destination must not be a symlink: {dest}")
    if dest.exists():
        if not dest.is_dir():
            raise ValueError(f"destination exists and is not a directory: {dest}")
        if any(dest.iterdir()):
            raise ValueError(f"destination directory is not empty: {dest}")

    dest.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(
        tempfile.mkdtemp(prefix=dest.name + ".", suffix=".tmp", dir=dest.parent)
    )
    try:
        with zipfile.ZipFile(package, "r") as zf:
            safe_extract(zf, stage)
        if dest.exists():
            dest.rmdir()
        os.replace(stage, dest)
    finally:
        if stage.exists():
            shutil.rmtree(stage, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Safely unpack an OOXML package (.docx/.pptx/.xlsx) into a directory."
    )
    parser.add_argument("package", help="Input OOXML package path")
    parser.add_argument("dest", help="Output unpacked directory path")
    args = parser.parse_args()

    package = Path(args.package)
    dest = Path(args.dest)
    try:
        unpack_package(package, dest)
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    print(f"Unpacked {package} to {dest}")


if __name__ == "__main__":
    main()
