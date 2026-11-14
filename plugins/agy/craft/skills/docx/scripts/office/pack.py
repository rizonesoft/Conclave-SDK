"""Atomic OOXML package packer omitting ZIP directory entries."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from helpers import OOXML_FAMILY, reject_output_inside_source, rezip
except ImportError:
    from office.helpers import OOXML_FAMILY, reject_output_inside_source, rezip


def pack_package(src_dir: Path, out_path: Path) -> None:
    """Atomically pack an unpacked OOXML directory into an Office package."""
    if not src_dir.is_dir():
        raise ValueError(f"{src_dir} is not a directory")
    if not (src_dir / "[Content_Types].xml").is_file():
        raise ValueError(f"{src_dir} is missing [Content_Types].xml")
    if out_path.suffix.lower() not in OOXML_FAMILY:
        raise ValueError(
            f"{out_path} must be one of: {', '.join(sorted(OOXML_FAMILY))}"
        )
    reject_output_inside_source(src_dir, out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rezip(src_dir, out_path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Atomically pack an unpacked directory into an OOXML package (.docx/.pptx/.xlsx)."
    )
    parser.add_argument("src_dir", help="Unpacked OOXML directory path")
    parser.add_argument("output", help="Output OOXML package path")
    args = parser.parse_args()

    src_dir = Path(args.src_dir)
    out_path = Path(args.output)
    try:
        pack_package(src_dir, out_path)
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    print(f"Packed {src_dir} to {out_path}")


if __name__ == "__main__":
    main()
