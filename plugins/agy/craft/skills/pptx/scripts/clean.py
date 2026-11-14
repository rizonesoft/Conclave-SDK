"""Remove unreferenced files from an unpacked PPTX directory.

Usage: python clean.py <unpacked_dir>

Example:
    python clean.py unpacked/

This script removes:
- Orphaned slides (not in sldIdLst) and their relationships
- [trash] directory (unreferenced files)
- Orphaned .rels files for deleted resources
- Unreferenced media, embeddings, charts, diagrams, drawings, ink files
- Unreferenced theme files
- Unreferenced notes slides
- Content-Type overrides for deleted files
"""

import posixpath
import re
import sys
from pathlib import Path
from xml.parsers.expat import ExpatError

from office.helpers import (
    CONTENT_TYPES_NS,
    PACKAGE_RELS_NS,
    SLIDE_REL_TYPE,
    STRICT_OFFICE_REL_NS,
    atomic_write_bytes,
    child_local_elements,
    get_rel_id_attr,
    local_elements,
    opc_target,
    parse_xml_file,
    rels_source_part,
)


_SLIDE_REL_TYPES = (SLIDE_REL_TYPE, f"{STRICT_OFFICE_REL_NS}/slide")
_XMLNS_NS = "http://www.w3.org/2000/xmlns/"
_PRESENTATION_NS = (
    "http://schemas.openxmlformats.org/presentationml/2006/main",
    "http://purl.oclc.org/ooxml/presentationml/main",
)
_TOKEN_PART = r"[!#$%&'*+\-.0-9A-Z^_`a-z|~]+"
_CONTENT_TYPE_RE = re.compile(
    rf"^{_TOKEN_PART}/{_TOKEN_PART}(?:\s*;\s*{_TOKEN_PART}=(?:{_TOKEN_PART}|\"[^\x00-\x1F\x7F\"]*\"))*$"
)
_EXTENSION_RE = re.compile(r"^(?:[!$&'()*+,:=@a-zA-Z0-9\-_~]|%[0-9a-fA-F]{2})+$")
_XML_ID_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9._-]*$")


def _slide_rids(pres_rels_path: Path, unpacked_dir: Path) -> dict[str, str]:
    source_part = rels_source_part(pres_rels_path, unpacked_dir)
    rels_dom = parse_xml_file(pres_rels_path)
    _validate_rels_dom(rels_dom, "ppt/_rels/presentation.xml.rels")

    rids: dict[str, str] = {}
    for rel in child_local_elements(rels_dom.documentElement, "Relationship"):
        if rel.getAttribute("Type") not in _SLIDE_REL_TYPES:
            continue
        part = opc_target(
            rel.getAttribute("Target"), source_part, rel.getAttribute("TargetMode")
        )
        if part is not None:
            rids[rel.getAttribute("Id")] = part
    return rids


def _referenced_slide_rids(pres_path: Path) -> list[str]:
    if not pres_path.exists():
        return []
    pres_dom = parse_xml_file(pres_path)
    return [
        rid
        for el in local_elements(pres_dom.documentElement, "sldId")
        if (rid := get_rel_id_attr(el))
    ]


def get_slides_in_sldidlst(unpacked_dir: Path) -> set[str]:
    pres_path = unpacked_dir / "ppt" / "presentation.xml"
    pres_rels_path = unpacked_dir / "ppt" / "_rels" / "presentation.xml.rels"

    if not pres_path.exists() or not pres_rels_path.exists():
        return set()

    rid_to_slide = _slide_rids(pres_rels_path, unpacked_dir)
    referenced_rids = set(_referenced_slide_rids(pres_path))

    return {
        posixpath.basename(rid_to_slide[rid])
        for rid in referenced_rids
        if rid in rid_to_slide
    }


class RefusedToClean(Exception):
    """The package does not look the way a readable package should."""


def _local_name(node) -> str:
    return node.localName or node.tagName.rsplit(":", 1)[-1]


def _validate_slide_id_list(
    pres_root, rid_to_slide: dict[str, str], unpacked_dir: Path
) -> None:
    sld_lists = child_local_elements(pres_root, "sldIdLst")
    for sld_lst in sld_lists:
        for child in sld_lst.childNodes:
            if child.nodeType != child.ELEMENT_NODE:
                continue
            if _local_name(child) not in ("sldId", "extLst"):
                raise RefusedToClean(
                    f"<p:sldIdLst> contains unexpected element <{child.tagName}>; "
                    "refusing to clean a damaged package."
                )

    root_resolved = unpacked_dir.resolve()
    for sld_el in local_elements(pres_root, "sldId"):
        rid = get_rel_id_attr(sld_el)
        if not rid:
            raise RefusedToClean(
                "<p:sldIdLst> contains a <p:sldId> without a relationship id; "
                "refusing to clean a damaged package."
            )
        target_rel = rid_to_slide.get(rid)
        if not target_rel:
            raise RefusedToClean(
                f"<p:sldIdLst> references unknown or invalid slide relationship {rid!r}; "
                "refusing to clean a damaged package."
            )
        target_path = (unpacked_dir / target_rel).resolve()
        if not target_path.is_relative_to(root_resolved) or not target_path.is_file():
            raise RefusedToClean(
                f"<p:sldIdLst> relationship {rid!r} targets missing or invalid slide "
                f"{target_rel!r}; refusing to clean a damaged package."
            )


def _unqualified_attrs(el, allowed: set[str], label: str) -> dict[str, str]:
    attrs = el.attributes
    values: dict[str, str] = {}
    if attrs is None:
        return values
    for idx in range(attrs.length):
        attr = attrs.item(idx)
        if (
            attr.namespaceURI == _XMLNS_NS
            or attr.name == "xmlns"
            or attr.name.startswith("xmlns:")
        ):
            continue
        if attr.namespaceURI:
            raise RefusedToClean(
                f"{label} has unexpected namespaced attribute {attr.name!r}; "
                "refusing to clean a damaged package."
            )
        if attr.name not in allowed:
            raise RefusedToClean(
                f"{label} has unexpected attribute {attr.name!r}; "
                "refusing to clean a damaged package."
            )
        values[attr.name] = attr.value
    return values


def _ensure_no_unexpected_children(
    el, allowed_local: set[str] | None, required_ns: str | None, label: str
) -> list:
    children = []
    for child in el.childNodes:
        if child.nodeType in (el.TEXT_NODE, el.CDATA_SECTION_NODE):
            if allowed_local is not None and child.data.strip():
                raise RefusedToClean(
                    f"{label} contains unexpected text content; "
                    "refusing to clean a damaged package."
                )
        elif child.nodeType == child.ELEMENT_NODE:
            if allowed_local is None:
                raise RefusedToClean(
                    f"{label} contains unexpected element <{child.tagName}>; "
                    "refusing to clean a damaged package."
                )
            if required_ns is not None and child.namespaceURI != required_ns:
                raise RefusedToClean(
                    f"{label} element <{child.tagName}> has wrong namespace "
                    f"{child.namespaceURI!r}; refusing to clean a damaged package."
                )
            if _local_name(child) not in allowed_local:
                raise RefusedToClean(
                    f"{label} contains unexpected element <{child.tagName}>; "
                    "refusing to clean a damaged package."
                )
            children.append(child)
    return children


def _validate_content_types_dom(ct_dom) -> None:
    ct_root = ct_dom.documentElement
    if (
        ct_root is None
        or _local_name(ct_root) != "Types"
        or ct_root.namespaceURI != CONTENT_TYPES_NS
    ):
        raise RefusedToClean(
            "[Content_Types].xml must have <Types> in the OPC content-types namespace; "
            "refusing to clean a damaged package."
        )
    _unqualified_attrs(ct_root, set(), "[Content_Types].xml <Types>")
    children = _ensure_no_unexpected_children(
        ct_root,
        {"Default", "Override"},
        CONTENT_TYPES_NS,
        "[Content_Types].xml <Types>",
    )

    seen_extensions: set[str] = set()
    seen_parts: set[str] = set()
    for child in children:
        name = _local_name(child)
        _ensure_no_unexpected_children(
            child, set(), CONTENT_TYPES_NS, f"[Content_Types].xml <{name}>"
        )
        if name == "Default":
            attrs = _unqualified_attrs(
                child, {"Extension", "ContentType"}, "[Content_Types].xml <Default>"
            )
            ext = attrs.get("Extension", "")
            ctype = attrs.get("ContentType", "")
            if (
                "Extension" not in attrs
                or "ContentType" not in attrs
                or not _EXTENSION_RE.match(ext)
                or not _CONTENT_TYPE_RE.match(ctype)
            ):
                raise RefusedToClean(
                    "[Content_Types].xml <Default> has invalid Extension or ContentType; "
                    "refusing to clean a damaged package."
                )
            key = ext.lower()
            if key in seen_extensions:
                raise RefusedToClean(
                    f"[Content_Types].xml has duplicate <Default> Extension {ext!r}; "
                    "refusing to clean a damaged package."
                )
            seen_extensions.add(key)
        else:
            attrs = _unqualified_attrs(
                child, {"PartName", "ContentType"}, "[Content_Types].xml <Override>"
            )
            part_name = attrs.get("PartName", "")
            ctype = attrs.get("ContentType", "")
            if (
                "PartName" not in attrs
                or "ContentType" not in attrs
                or not part_name.startswith("/")
                or len(part_name) <= 1
                or "\\" in part_name
                or any(ch.isspace() or ord(ch) < 32 or ord(ch) == 127 for ch in part_name)
                or not _CONTENT_TYPE_RE.match(ctype)
            ):
                raise RefusedToClean(
                    "[Content_Types].xml <Override> has invalid PartName or ContentType; "
                    "refusing to clean a damaged package."
                )
            key = part_name.lower()
            if key in seen_parts:
                raise RefusedToClean(
                    f"[Content_Types].xml has duplicate <Override> PartName {part_name!r}; "
                    "refusing to clean a damaged package."
                )
            seen_parts.add(key)


def _validate_rels_dom(rels_dom, rels_label: str) -> None:
    rels_root = rels_dom.documentElement
    if (
        rels_root is None
        or _local_name(rels_root) != "Relationships"
        or rels_root.namespaceURI != PACKAGE_RELS_NS
    ):
        raise RefusedToClean(
            f"{rels_label} must have <Relationships> in the OPC relationships namespace; "
            "refusing to clean a damaged package."
        )
    _unqualified_attrs(rels_root, set(), f"{rels_label} <Relationships>")
    children = _ensure_no_unexpected_children(
        rels_root,
        {"Relationship"},
        PACKAGE_RELS_NS,
        f"{rels_label} <Relationships>",
    )

    seen_ids: set[str] = set()
    for rel in children:
        _ensure_no_unexpected_children(
            rel, None, None, f"{rels_label} <Relationship>"
        )
        attrs = _unqualified_attrs(
            rel, {"Id", "Type", "Target", "TargetMode"}, f"{rels_label} <Relationship>"
        )
        rel_id = attrs.get("Id", "")
        rel_type = attrs.get("Type", "")
        target = attrs.get("Target", "")
        if (
            "Id" not in attrs
            or "Type" not in attrs
            or "Target" not in attrs
            or not _XML_ID_RE.match(rel_id)
            or not rel_type.strip()
            or not target.strip()
        ):
            raise RefusedToClean(
                f"{rels_label} <Relationship> has missing or invalid Id, Type, or Target; "
                "refusing to clean a damaged package."
            )
        if rel_id in seen_ids:
            raise RefusedToClean(
                f"{rels_label} has duplicate relationship Id {rel_id!r}; "
                "refusing to clean an ambiguous package."
            )
        seen_ids.add(rel_id)
        if "TargetMode" in attrs and attrs["TargetMode"] not in ("Internal", "External"):
            raise RefusedToClean(
                f"{rels_label} <Relationship> has invalid TargetMode {attrs['TargetMode']!r}; "
                "refusing to clean a damaged package."
            )


def _validate_presentation_package(unpacked_dir: Path) -> None:
    ct_path = unpacked_dir / "[Content_Types].xml"
    pres_path = unpacked_dir / "ppt" / "presentation.xml"
    pres_rels_path = unpacked_dir / "ppt" / "_rels" / "presentation.xml.rels"
    if not ct_path.is_file() or not pres_path.is_file() or not pres_rels_path.is_file():
        raise RefusedToClean(
            "missing [Content_Types].xml, ppt/presentation.xml, or "
            "ppt/_rels/presentation.xml.rels; "
            "refusing to delete files from an incomplete PPTX package."
        )

    _validate_content_types_dom(parse_xml_file(ct_path))

    pres_dom = parse_xml_file(pres_path)
    pres_root = pres_dom.documentElement
    if (
        pres_root is None
        or _local_name(pres_root) != "presentation"
        or pres_root.namespaceURI not in _PRESENTATION_NS
    ):
        raise RefusedToClean(
            "ppt/presentation.xml root element is not <presentation>; "
            "refusing to clean a damaged package."
        )
    if not child_local_elements(pres_root, "sldIdLst") and not child_local_elements(
        pres_root, "sldMasterIdLst"
    ):
        raise RefusedToClean(
            "ppt/presentation.xml has neither <sldIdLst> nor <sldMasterIdLst>; "
            "refusing to clean a damaged package."
        )

    pres_rels_resolved = pres_rels_path.resolve()
    for rels_file in sorted(unpacked_dir.rglob("*.rels")):
        if rels_file.resolve() == pres_rels_resolved:
            continue
        _validate_rels_dom(
            parse_xml_file(rels_file), rels_file.relative_to(unpacked_dir).as_posix()
        )

    _validate_slide_id_list(
        pres_root, _slide_rids(pres_rels_path, unpacked_dir), unpacked_dir
    )


def remove_orphaned_slides(unpacked_dir: Path) -> list[str]:
    _validate_presentation_package(unpacked_dir)

    slides_dir = unpacked_dir / "ppt" / "slides"
    slides_rels_dir = slides_dir / "_rels"
    pres_rels_path = unpacked_dir / "ppt" / "_rels" / "presentation.xml.rels"

    if not slides_dir.exists():
        return []

    referenced_slides = get_slides_in_sldidlst(unpacked_dir)
    on_disk = sorted(slides_dir.glob("slide*.xml"))

    if on_disk and not any(s.name in referenced_slides for s in on_disk):
        listed = _referenced_slide_rids(unpacked_dir / "ppt" / "presentation.xml")
        if listed:
            raise RefusedToClean(
                f"<p:sldIdLst> lists {len(listed)} slide(s) and none of the "
                f"{len(on_disk)} slide(s) on disk match any of them. Refusing to "
                f"delete them all: this is a parse failure, not an empty deck."
            )

    removed = []

    for slide_file in on_disk:
        if slide_file.name not in referenced_slides:
            rel_path = slide_file.relative_to(unpacked_dir).as_posix()
            slide_file.unlink()
            removed.append(rel_path)

            rels_file = slides_rels_dir / f"{slide_file.name}.rels"
            if rels_file.exists():
                rels_file.unlink()
                removed.append(rels_file.relative_to(unpacked_dir).as_posix())

    if removed and pres_rels_path.exists():
        rels_dom = parse_xml_file(pres_rels_path)
        source_part = rels_source_part(pres_rels_path, unpacked_dir)
        changed = False

        for rel in list(child_local_elements(rels_dom.documentElement, "Relationship")):
            if rel.getAttribute("Type") not in _SLIDE_REL_TYPES:
                continue
            part = opc_target(
                rel.getAttribute("Target"), source_part, rel.getAttribute("TargetMode")
            )
            if part is None:
                continue
            if posixpath.basename(part) not in referenced_slides:
                if rel.parentNode:
                    rel.parentNode.removeChild(rel)
                    changed = True

        if changed:
            atomic_write_bytes(
                pres_rels_path,
                rels_dom.toxml(encoding="UTF-8", standalone=rels_dom.standalone),
            )

    return removed


def remove_trash_directory(unpacked_dir: Path) -> list[str]:
    trash_dir = unpacked_dir / "[trash]"
    removed = []

    if trash_dir.exists() and trash_dir.is_dir():
        for file_path in sorted(p for p in trash_dir.rglob("*") if p.is_file()):
            rel_path = file_path.relative_to(unpacked_dir).as_posix()
            removed.append(rel_path)
            file_path.unlink()
        for sub_dir in sorted(
            (p for p in trash_dir.rglob("*") if p.is_dir()),
            key=lambda p: len(p.parts),
            reverse=True,
        ):
            sub_dir.rmdir()
        trash_dir.rmdir()

    return removed


def _referenced_by(rels_files, unpacked_dir: Path) -> set[str]:
    referenced: set[str] = set()

    for rels_file in rels_files:
        source_part = rels_source_part(rels_file, unpacked_dir)
        dom = parse_xml_file(rels_file)
        for rel in child_local_elements(dom.documentElement, "Relationship"):
            part = opc_target(
                rel.getAttribute("Target"), source_part, rel.getAttribute("TargetMode")
            )
            if part is not None:
                referenced.add(part)

    return referenced


def remove_orphaned_rels_files(unpacked_dir: Path) -> list[str]:
    resource_dirs = ["charts", "diagrams", "drawings"]
    removed = []

    for dir_name in resource_dirs:
        rels_dir = unpacked_dir / "ppt" / dir_name / "_rels"
        if not rels_dir.exists():
            continue

        for rels_file in sorted(rels_dir.glob("*.rels")):
            resource_file = rels_dir.parent / rels_file.name.removesuffix(".rels")
            if not resource_file.exists():
                rels_file.unlink()
                removed.append(rels_file.relative_to(unpacked_dir).as_posix())

    return removed


def get_referenced_files(unpacked_dir: Path) -> set[str]:
    return _referenced_by(sorted(unpacked_dir.rglob("*.rels")), unpacked_dir)


def remove_orphaned_files(unpacked_dir: Path, referenced: set) -> list[str]:
    referenced_posix = {
        item.as_posix() if isinstance(item, Path) else str(item).replace("\\", "/").lstrip("/")
        for item in referenced
    }
    resource_dirs = ["media", "embeddings", "charts", "diagrams", "tags", "drawings", "ink"]
    removed = []

    for dir_name in resource_dirs:
        dir_path = unpacked_dir / "ppt" / dir_name
        if not dir_path.exists():
            continue

        for file_path in sorted(dir_path.glob("*")):
            if not file_path.is_file():
                continue
            rel_path = file_path.relative_to(unpacked_dir).as_posix()
            if rel_path not in referenced_posix:
                file_path.unlink()
                removed.append(rel_path)

    theme_dir = unpacked_dir / "ppt" / "theme"
    if theme_dir.exists():
        for file_path in sorted(theme_dir.glob("theme*.xml")):
            rel_path = file_path.relative_to(unpacked_dir).as_posix()
            if rel_path not in referenced_posix:
                file_path.unlink()
                removed.append(rel_path)
                theme_rels = theme_dir / "_rels" / f"{file_path.name}.rels"
                if theme_rels.exists():
                    theme_rels.unlink()
                    removed.append(theme_rels.relative_to(unpacked_dir).as_posix())

    notes_dir = unpacked_dir / "ppt" / "notesSlides"
    if notes_dir.exists():
        for file_path in sorted(notes_dir.glob("*.xml")):
            if not file_path.is_file():
                continue
            rel_path = file_path.relative_to(unpacked_dir).as_posix()
            if rel_path not in referenced_posix:
                file_path.unlink()
                removed.append(rel_path)

        notes_rels_dir = notes_dir / "_rels"
        if notes_rels_dir.exists():
            for file_path in sorted(notes_rels_dir.glob("*.rels")):
                notes_file = notes_dir / file_path.name.removesuffix(".rels")
                if not notes_file.exists():
                    file_path.unlink()
                    removed.append(file_path.relative_to(unpacked_dir).as_posix())

    return removed


def update_content_types(unpacked_dir: Path, removed_files: list[str]) -> None:
    ct_path = unpacked_dir / "[Content_Types].xml"
    if not ct_path.exists():
        return

    removed_set = {p.replace("\\", "/").lstrip("/") for p in removed_files}
    dom = parse_xml_file(ct_path)
    changed = False

    for override in list(child_local_elements(dom.documentElement, "Override")):
        part_name = override.getAttribute("PartName").replace("\\", "/").lstrip("/")
        if part_name in removed_set:
            if override.parentNode:
                override.parentNode.removeChild(override)
                changed = True

    if changed:
        atomic_write_bytes(
            ct_path,
            dom.toxml(encoding="UTF-8", standalone=dom.standalone),
        )


def clean_unused_files(unpacked_dir: Path) -> list[str]:
    all_removed = []

    _validate_presentation_package(unpacked_dir)

    if not list(unpacked_dir.rglob("*.rels")) or not get_referenced_files(unpacked_dir):
        raise RefusedToClean(
            "no relationship in this package names a part we can resolve. "
            "Refusing to treat every file as unreferenced."
        )

    slides_removed = remove_orphaned_slides(unpacked_dir)
    all_removed.extend(slides_removed)

    trash_removed = remove_trash_directory(unpacked_dir)
    all_removed.extend(trash_removed)

    while True:
        removed_rels = remove_orphaned_rels_files(unpacked_dir)
        referenced = get_referenced_files(unpacked_dir)
        removed_files = remove_orphaned_files(unpacked_dir, referenced)

        total_removed = removed_rels + removed_files
        if not total_removed:
            break

        all_removed.extend(total_removed)

    if all_removed:
        update_content_types(unpacked_dir, all_removed)

    return all_removed


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python clean.py <unpacked_dir>", file=sys.stderr)
        print("Example: python clean.py unpacked/", file=sys.stderr)
        sys.exit(1)

    unpacked_dir = Path(sys.argv[1])

    if not unpacked_dir.exists():
        print(f"Error: {unpacked_dir} not found", file=sys.stderr)
        sys.exit(1)

    try:
        removed = clean_unused_files(unpacked_dir)
    except (RefusedToClean, ValueError, ExpatError) as e:
        print(f"Error: {e}", file=sys.stderr)
        print("Nothing was deleted.", file=sys.stderr)
        sys.exit(1)

    if removed:
        print(f"Removed {len(removed)} unreferenced files:")
        for f in removed:
            print(f"  {f}")
    else:
        print("No unreferenced files found")
