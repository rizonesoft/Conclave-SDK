"""Create thumbnail grids from PowerPoint presentation slides.

Creates a grid layout of slide thumbnails for quick visual analysis.
Labels each thumbnail with its XML filename (e.g., slide1.xml).
Hidden slides are shown with a placeholder pattern.

Usage:
    python thumbnail.py input.pptx [output_prefix] [--cols N]

Examples:
    python thumbnail.py presentation.pptx
    # Creates: thumbnails.jpg

    python thumbnail.py template.pptx grid --cols 4
    # Creates: grid.jpg (or grid-1.jpg, grid-2.jpg for large decks)
"""

import argparse
import os
import posixpath
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as _stdlib_et
import xml.parsers.expat as _expat
import zipfile
from pathlib import Path

from office.helpers import (
    MAX_ARCHIVE_BYTES,
    MAX_MEMBER_BYTES,
    SLIDE_REL_TYPE,
    STRICT_OFFICE_REL_NS,
    child_local_elements,
    get_rel_id_attr,
    local_elements,
    opc_target,
    open_zip_member,
    parse_xml_bytes,
    read_relationship,
    read_zip_member,
    validate_archive,
)
from office.soffice import run_process_tree, run_soffice
from PIL import Image, ImageDraw, ImageFont


THUMBNAIL_WIDTH = 300
CONVERSION_DPI = 100
MAX_COLS = 6
DEFAULT_COLS = 3
JPEG_QUALITY = 95
GRID_PADDING = 20
BORDER_WIDTH = 2
FONT_SIZE_RATIO = 0.10
LABEL_PADDING_RATIO = 0.4
MAX_THUMBNAIL_XML_BYTES = 32 * 1024 * 1024


def main():
    parser = argparse.ArgumentParser(
        description="Create thumbnail grids from PowerPoint slides."
    )
    parser.add_argument("input", help="Input PowerPoint file (.pptx)")
    parser.add_argument(
        "output_prefix",
        nargs="?",
        default="thumbnails",
        help="Output prefix for image files (default: thumbnails)",
    )
    parser.add_argument(
        "--cols",
        type=int,
        default=DEFAULT_COLS,
        help=f"Number of columns (default: {DEFAULT_COLS}, max: {MAX_COLS})",
    )

    args = parser.parse_args()

    cols = min(args.cols, MAX_COLS)
    if args.cols > MAX_COLS:
        print(f"Warning: Columns limited to {MAX_COLS}")

    input_path = Path(args.input)
    if not input_path.exists() or input_path.suffix.lower() != ".pptx":
        print(f"Error: Invalid PowerPoint file: {args.input}", file=sys.stderr)
        sys.exit(1)

    output_path = Path(f"{args.output_prefix}.jpg")

    try:
        slide_info = get_slide_info(input_path)

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            visible_images = convert_to_images(input_path, temp_path)

            if not visible_images and not any(s["hidden"] for s in slide_info):
                print("Error: No slides found", file=sys.stderr)
                sys.exit(1)

            slides = build_slide_list(slide_info, visible_images, temp_path)

            grid_files = create_grids(slides, cols, THUMBNAIL_WIDTH, output_path)

            print(f"Created {len(grid_files)} grid(s):")
            for grid_file in grid_files:
                print(f"  {grid_file}")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


class _DtdRejectingStream:
    def __init__(self, stream):
        self._stream = stream
        self._guard = _expat.ParserCreate()
        self._finished = False

        def _forbid(*_args):
            raise ValueError("XML DTD and entity declarations are forbidden")

        self._guard.StartDoctypeDeclHandler = _forbid
        self._guard.EntityDeclHandler = _forbid
        self._guard.UnparsedEntityDeclHandler = _forbid
        self._guard.ExternalEntityRefHandler = _forbid

    def read(self, size=-1):
        chunk = self._stream.read(size)
        if chunk:
            self._guard.Parse(chunk, False)
        elif size != 0 and not self._finished:
            self._finished = True
            self._guard.Parse(b"", True)
        return chunk


def _is_hidden(
    zf: zipfile.ZipFile,
    part: str,
    budget: list[int] | None = None,
    max_member_bytes: int = MAX_MEMBER_BYTES,
    max_bytes: int = MAX_ARCHIVE_BYTES,
) -> bool:
    try:
        from defusedxml import ElementTree as et_mod
    except (ImportError, AttributeError):
        et_mod = _stdlib_et
    try:
        with open_zip_member(
            zf,
            part,
            budget=budget,
            max_member_bytes=max_member_bytes,
            max_bytes=max_bytes,
        ) as f:
            for _, root in et_mod.iterparse(_DtdRejectingStream(f), events=("start",)):
                return root.get("show") in ("0", "false")  
    except (KeyError, SyntaxError, ValueError, _expat.ExpatError):
        return False
    return False


def get_slide_info(pptx_path: Path) -> list[dict]:
    with zipfile.ZipFile(pptx_path, "r") as zf:
        validate_archive(
            zf,
            max_bytes=MAX_ARCHIVE_BYTES,
            max_member_bytes=MAX_MEMBER_BYTES,
        )
        budget = [0]
        rels_content = read_zip_member(
            zf,
            "ppt/_rels/presentation.xml.rels",
            budget=budget,
            max_member_bytes=MAX_THUMBNAIL_XML_BYTES,
            max_bytes=MAX_ARCHIVE_BYTES,
        )
        rels_dom = parse_xml_bytes(rels_content, max_bytes=MAX_THUMBNAIL_XML_BYTES)

        slide_rel_types = (SLIDE_REL_TYPE, f"{STRICT_OFFICE_REL_NS}/slide")
        rid_to_part = {}
        for rel in child_local_elements(rels_dom.documentElement, "Relationship"):
            rel_id, rel_type, target, target_mode = read_relationship(rel)
            if rel_type not in slide_rel_types:
                continue
            part = opc_target(target, "ppt/presentation.xml", target_mode)
            if part is not None:
                rid_to_part[rel_id] = part

        pres_content = read_zip_member(
            zf,
            "ppt/presentation.xml",
            budget=budget,
            max_member_bytes=MAX_THUMBNAIL_XML_BYTES,
            max_bytes=MAX_ARCHIVE_BYTES,
        )
        pres_dom = parse_xml_bytes(pres_content, max_bytes=MAX_THUMBNAIL_XML_BYTES)

        present = set(zf.namelist())

        slides = []
        for sld_id in local_elements(pres_dom.documentElement, "sldId"):
            part = rid_to_part.get(get_rel_id_attr(sld_id))
            if part is not None and part in present:
                slides.append(
                    {
                        "name": posixpath.basename(part),
                        "hidden": _is_hidden(
                            zf,
                            part,
                            budget=budget,
                            max_member_bytes=MAX_MEMBER_BYTES,
                            max_bytes=MAX_ARCHIVE_BYTES,
                        ),
                    }
                )

        return slides


def build_slide_list(
    slide_info: list[dict],
    visible_images: list[Path],
    temp_dir: Path,
) -> list[tuple[Path, str]]:
    visible_count = sum(1 for info in slide_info if not info["hidden"])
    rendered_hidden = len(visible_images) == len(slide_info) != visible_count

    if not rendered_hidden and visible_count != len(visible_images):
        raise ValueError(
            f"LibreOffice rendered {len(visible_images)} page(s) for {visible_count} "
            f"visible slide(s) of {len(slide_info)}; thumbnails would be mislabeled"
        )

    if visible_images:
        with Image.open(visible_images[0]) as img:
            placeholder_size = img.size
    else:
        placeholder_size = (1920, 1080)

    slides = []
    visible_idx = 0

    for info in slide_info:
        if info["hidden"] and not rendered_hidden:
            placeholder_path = temp_dir / f"hidden-{info['name']}.jpg"
            placeholder_img = create_hidden_placeholder(placeholder_size)
            placeholder_img.save(placeholder_path, "JPEG")
            slides.append((placeholder_path, f"{info['name']} (hidden)"))
        else:
            label = f"{info['name']} (hidden)" if info["hidden"] else info["name"]
            slides.append((visible_images[visible_idx], label))
            visible_idx += 1

    return slides


def create_hidden_placeholder(size: tuple[int, int]) -> Image.Image:
    img = Image.new("RGB", size, color="#F0F0F0")
    draw = ImageDraw.Draw(img)
    line_width = max(5, min(size) // 100)
    draw.line([(0, 0), size], fill="#CCCCCC", width=line_width)
    draw.line([(size[0], 0), (0, size[1])], fill="#CCCCCC", width=line_width)
    return img


def convert_to_images(pptx_path: Path, temp_dir: Path) -> list[Path]:
    pdf_path = temp_dir / f"{pptx_path.stem}.pdf"

    result = run_soffice(
        ["--headless", "--convert-to", "pdf", "--outdir", str(temp_dir), str(pptx_path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not pdf_path.exists():
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"PDF conversion failed: {detail}" if detail else "PDF conversion failed")

    result = run_process_tree(
        [
            "pdftoppm",
            "-jpeg",
            "-r",
            str(CONVERSION_DPI),
            str(pdf_path),
            str(temp_dir / "slide"),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError("Image conversion failed")

    return sorted(temp_dir.glob("slide-*.jpg"))


def create_grids(
    slides: list[tuple[Path, str]],
    cols: int,
    width: int,
    output_path: Path,
) -> list[str]:
    max_per_grid = cols * (cols + 1)
    grid_files = []

    for chunk_idx, start_idx in enumerate(range(0, len(slides), max_per_grid)):
        end_idx = min(start_idx + max_per_grid, len(slides))
        chunk_slides = slides[start_idx:end_idx]

        grid = create_grid(chunk_slides, cols, width)

        if len(slides) <= max_per_grid:
            grid_filename = output_path
        else:
            stem = output_path.stem
            suffix = output_path.suffix
            grid_filename = output_path.parent / f"{stem}-{chunk_idx + 1}{suffix}"

        grid_filename.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            prefix=grid_filename.name + ".", suffix=".jpg", dir=grid_filename.parent
        )
        os.close(fd)
        tmp_path = Path(tmp_name)
        try:
            grid.save(str(tmp_path), format="JPEG", quality=JPEG_QUALITY)
            os.replace(tmp_path, grid_filename)
        except BaseException:
            tmp_path.unlink(missing_ok=True)
            raise
        grid_files.append(str(grid_filename))

    return grid_files


def create_grid(
    slides: list[tuple[Path, str]],
    cols: int,
    width: int,
) -> Image.Image:
    font_size = int(width * FONT_SIZE_RATIO)
    label_padding = int(font_size * LABEL_PADDING_RATIO)

    with Image.open(slides[0][0]) as img:
        aspect = img.height / img.width
    height = int(width * aspect)

    rows = (len(slides) + cols - 1) // cols
    grid_w = cols * width + (cols + 1) * GRID_PADDING
    grid_h = rows * (height + font_size + label_padding * 2) + (rows + 1) * GRID_PADDING

    grid = Image.new("RGB", (grid_w, grid_h), "white")
    draw = ImageDraw.Draw(grid)

    try:
        font = ImageFont.load_default(size=font_size)
    except Exception:
        font = ImageFont.load_default()

    for i, (img_path, slide_name) in enumerate(slides):
        row, col = i // cols, i % cols
        x = col * width + (col + 1) * GRID_PADDING
        y_base = (
            row * (height + font_size + label_padding * 2) + (row + 1) * GRID_PADDING
        )

        label = slide_name
        bbox = draw.textbbox((0, 0), label, font=font)
        text_w = bbox[2] - bbox[0]
        draw.text(
            (x + (width - text_w) // 2, y_base + label_padding),
            label,
            fill="black",
            font=font,
        )

        y_thumbnail = y_base + label_padding + font_size + label_padding

        with Image.open(img_path) as img:
            img.thumbnail((width, height), Image.Resampling.LANCZOS)
            w, h = img.size
            tx = x + (width - w) // 2
            ty = y_thumbnail + (height - h) // 2
            grid.paste(img, (tx, ty))

            if BORDER_WIDTH > 0:
                draw.rectangle(
                    [
                        (tx - BORDER_WIDTH, ty - BORDER_WIDTH),
                        (tx + w + BORDER_WIDTH - 1, ty + h + BORDER_WIDTH - 1),
                    ],
                    outline="gray",
                    width=BORDER_WIDTH,
                )

    return grid


if __name__ == "__main__":
    main()
