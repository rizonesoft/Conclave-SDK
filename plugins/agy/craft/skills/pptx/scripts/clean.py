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
    collapse_xml_space,
    get_rel_id_attr,
    is_valid_any_uri,
    local_elements,
    normalize_part_name,
    opc_part_key,
    opc_target,
    parse_xml_file,
    read_relationship,
    rels_source_part,
)


_SLIDE_REL_TYPES = (SLIDE_REL_TYPE, f"{STRICT_OFFICE_REL_NS}/slide")
_XMLNS_NS = "http://www.w3.org/2000/xmlns/"
_PRESENTATION_NS = (
    "http://schemas.openxmlformats.org/presentationml/2006/main",
    "http://purl.oclc.org/ooxml/presentationml/main",
)
_XML_WS = " \t\r\n"
_TOKEN_CHARS = frozenset(
    "!#$%&'*+-.0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ^_`abcdefghijklmnopqrstuvwxyz|~"
)
_EXTENSION_RE = re.compile(r"^(?:[!$&'()*+,:=@a-zA-Z0-9\-_~]|%[0-9a-fA-F]{2})+\Z")
_NCNAME_START = (
    r"A-Z_a-z\u00C0-\u00D6\u00D8-\u00F6\u00F8-\u02FF\u0370-\u037D"
    r"\u037F-\u1FFF\u200C-\u200D\u2070-\u218F\u2C00-\u2FEF\u3001-\uD7FF"
    r"\uF900-\uFDCF\uFDF0-\uFFFD\U00010000-\U000EFFFF"
)
_NCNAME_CHAR = _NCNAME_START + r"\-.0-9\u00B7\u0300-\u036F\u203F-\u2040"
_XML_ID_RE = re.compile(rf"^[{_NCNAME_START}][{_NCNAME_CHAR}]*\Z")


def _is_valid_content_type(value: str) -> bool:
    """Validate ST_ContentType from opc-contentTypes.xsd in linear O(n) time."""
    if "/" not in value:
        return False
    idx = value.find("/")
    media_type = value[:idx]
    if not media_type or not all(ch in _TOKEN_CHARS for ch in media_type):
        return False
    pos = idx + 1
    sub_start = pos
    while pos < len(value) and value[pos] in _TOKEN_CHARS:
        pos += 1
    if pos == sub_start:
        return False

    # 8-state NFA matching optional (; param = token | quoted-string)* parameters.
    states = {0}
    for ch in value[pos:]:
        code = ord(ch)
        next_states: set[int] = set()
        if 0 in states:
            if ch in _XML_WS:
                next_states.add(1)
            elif ch == ";":
                next_states.add(2)
        if 1 in states:
            if ch in _XML_WS:
                next_states.add(1)
            elif ch == ";":
                next_states.add(2)
        if 2 in states:
            if ch in _XML_WS:
                next_states.add(2)
            elif ch in _TOKEN_CHARS:
                next_states.add(3)
        if 3 in states:
            if ch in _TOKEN_CHARS:
                next_states.add(3)
            elif ch == "=":
                next_states.add(4)
        if 4 in states:
            if ch in _TOKEN_CHARS:
                next_states.add(5)
            elif ch == '"':
                next_states.add(6)
        if 5 in states:
            if ch in _TOKEN_CHARS:
                next_states.add(5)
            elif ch in _XML_WS:
                next_states.add(1)
            elif ch == ";":
                next_states.add(2)
        if 6 in states:
            if ch == '"':
                next_states.add(0)
            elif ch == "\\":
                next_states.add(6)
                next_states.add(7)
            elif (
                ch in _XML_WS
                or (0x20 <= code <= 0x7E)
                or (0xA0 <= code <= 0xFF)
            ):
                next_states.add(6)
        if 7 in states and 0x00 <= code <= 0x7F:
            next_states.add(6)
        if not next_states:
            return False
        states = next_states
    return bool(states & {0, 5})


def _package_files_by_key(unpacked_dir: Path) -> dict[str, Path]:
    root_resolved = unpacked_dir.resolve()
    files_by_key: dict[str, Path] = {}
    for file_path in sorted(unpacked_dir.rglob("*")):
        if not file_path.is_file():
            continue
        rel_posix = file_path.relative_to(unpacked_dir).as_posix()
        resolved = file_path.resolve()
        if not resolved.is_relative_to(root_resolved) or not resolved.is_file():
            raise RefusedToClean(
                f"{rel_posix} escapes package root; refusing to clean a damaged package."
            )
        key = opc_part_key(rel_posix)
        if key == "[trash]" or key.startswith("[trash]/"):
            continue
        if key in files_by_key:
            prev_rel = files_by_key[key].relative_to(unpacked_dir).as_posix()
            raise RefusedToClean(
                f"package contains equivalent OPC part names {prev_rel!r} and {rel_posix!r}; "
                "refusing to clean a damaged package."
            )
        files_by_key[key] = file_path
    return files_by_key


def _find_rels_files(files_by_key: dict[str, Path]) -> list[Path]:
    return [p for key, p in files_by_key.items() if key.endswith(".rels")]


def _slide_rids(pres_rels_path: Path, unpacked_dir: Path) -> dict[str, str]:
    source_part = rels_source_part(pres_rels_path, unpacked_dir)
    rels_dom = parse_xml_file(pres_rels_path)
    _validate_rels_dom(rels_dom, "ppt/_rels/presentation.xml.rels", source_part)

    rids: dict[str, str] = {}
    for rel in child_local_elements(rels_dom.documentElement, "Relationship"):
        rel_id, rel_type, target, target_mode = read_relationship(rel)
        if rel_type not in _SLIDE_REL_TYPES:
            continue
        part = opc_target(target, source_part, target_mode)
        if part is not None:
            rids[rel_id] = part
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


def _referenced_slide_keys(
    unpacked_dir: Path, files_by_key: dict[str, Path] | None = None
) -> set[str]:
    if files_by_key is None:
        files_by_key = _package_files_by_key(unpacked_dir)
    pres_path = files_by_key.get("ppt/presentation.xml")
    pres_rels_path = files_by_key.get("ppt/_rels/presentation.xml.rels")

    if pres_path is None or pres_rels_path is None:
        return set()

    rid_to_slide = _slide_rids(pres_rels_path, unpacked_dir)
    referenced_rids = set(_referenced_slide_rids(pres_path))
    return {
        opc_part_key(rid_to_slide[rid])
        for rid in referenced_rids
        if rid in rid_to_slide
    }


def get_slides_in_sldidlst(unpacked_dir: Path) -> set[str]:
    files_by_key = _package_files_by_key(unpacked_dir)
    return {
        files_by_key[key].name if key in files_by_key else posixpath.basename(key)
        for key in _referenced_slide_keys(unpacked_dir, files_by_key)
    }


class RefusedToClean(Exception):
    """The package does not look the way a readable package should."""


def _local_name(node) -> str:
    return node.localName or node.tagName.rsplit(":", 1)[-1]


def _validate_slide_id_list(
    pres_root, rid_to_slide: dict[str, str], files_by_key: dict[str, Path]
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
        if opc_part_key(target_rel) not in files_by_key:
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
                or not _is_valid_content_type(ctype)
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
            norm_part = normalize_part_name(part_name)
            ctype = attrs.get("ContentType", "")
            if (
                "PartName" not in attrs
                or "ContentType" not in attrs
                or norm_part is None
                or not _is_valid_content_type(ctype)
            ):
                raise RefusedToClean(
                    "[Content_Types].xml <Override> has invalid PartName or ContentType; "
                    "refusing to clean a damaged package."
                )
            key = opc_part_key(norm_part)
            if key in seen_parts:
                raise RefusedToClean(
                    f"[Content_Types].xml has duplicate <Override> PartName {part_name!r}; "
                    "refusing to clean a damaged package."
                )
            seen_parts.add(key)


def _validate_rels_dom(rels_dom, rels_label: str, source_part: str = "") -> None:
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
        rel_id, rel_type, target, target_mode = read_relationship(rel)
        if (
            "Id" not in attrs
            or "Type" not in attrs
            or "Target" not in attrs
            or not _XML_ID_RE.match(rel_id)
            or not is_valid_any_uri(rel_type)
            or not target
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
        if "TargetMode" in attrs and target_mode not in ("Internal", "External"):
            raise RefusedToClean(
                f"{rels_label} <Relationship> has invalid TargetMode {target_mode!r}; "
                "refusing to clean a damaged package."
            )
        try:
            opc_target(target, source_part, target_mode)
        except ValueError as exc:
            raise RefusedToClean(
                f"{rels_label} <Relationship> has invalid Target {target!r}: {exc}"
            ) from exc


def _validate_presentation_package(unpacked_dir: Path) -> dict[str, Path]:
    files_by_key = _package_files_by_key(unpacked_dir)
    ct_path = files_by_key.get("[content_types].xml")
    pres_path = files_by_key.get("ppt/presentation.xml")
    pres_rels_path = files_by_key.get("ppt/_rels/presentation.xml.rels")
    if ct_path is None or pres_path is None or pres_rels_path is None:
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

    for key, rels_file in files_by_key.items():
        if not key.endswith(".rels"):
            continue
        if opc_part_key(rels_file.parent.name) != "_rels" or (
            opc_part_key(rels_file.name) == ".rels" and rels_file.parent.parent != unpacked_dir
        ):
            raise RefusedToClean(
                f"{rels_file.relative_to(unpacked_dir).as_posix()} is not inside a _rels directory; "
                "refusing to clean a damaged package."
            )
        if key == "ppt/_rels/presentation.xml.rels":
            continue
        source_part = "" if key == "_rels/.rels" else rels_source_part(rels_file, unpacked_dir)
        _validate_rels_dom(
            parse_xml_file(rels_file),
            rels_file.relative_to(unpacked_dir).as_posix(),
            source_part,
        )

    _validate_slide_id_list(
        pres_root, _slide_rids(pres_rels_path, unpacked_dir), files_by_key
    )
    return files_by_key


def remove_orphaned_slides(unpacked_dir: Path) -> list[str]:
    files_by_key = _validate_presentation_package(unpacked_dir)

    slides_dir = unpacked_dir / "ppt" / "slides"
    pres_path = files_by_key.get("ppt/presentation.xml")
    pres_rels_path = files_by_key.get("ppt/_rels/presentation.xml.rels")

    if not slides_dir.exists():
        return []

    referenced_slide_keys = _referenced_slide_keys(unpacked_dir, files_by_key)
    on_disk = [
        file_path
        for key, file_path in files_by_key.items()
        if posixpath.dirname(key) == "ppt/slides"
        and posixpath.basename(key).startswith("slide")
        and key.endswith(".xml")
    ]

    if on_disk and not any(
        opc_part_key(s.relative_to(unpacked_dir).as_posix()) in referenced_slide_keys
        for s in on_disk
    ):
        listed = _referenced_slide_rids(pres_path) if pres_path is not None else []
        if listed:
            raise RefusedToClean(
                f"<p:sldIdLst> lists {len(listed)} slide(s) and none of the "
                f"{len(on_disk)} slide(s) on disk match any of them. Refusing to "
                f"delete them all: this is a parse failure, not an empty deck."
            )

    removed = []

    for slide_file in on_disk:
        rel_path = slide_file.relative_to(unpacked_dir).as_posix()
        if opc_part_key(rel_path) not in referenced_slide_keys:
            slide_file.unlink()
            removed.append(rel_path)

            rels_key = opc_part_key(f"ppt/slides/_rels/{slide_file.name}.rels")
            rels_file = files_by_key.get(rels_key)
            if rels_file is not None and rels_file.exists():
                rels_file.unlink()
                removed.append(rels_file.relative_to(unpacked_dir).as_posix())

    if removed and pres_rels_path is not None and pres_rels_path.exists():
        rels_dom = parse_xml_file(pres_rels_path)
        source_part = rels_source_part(pres_rels_path, unpacked_dir)
        changed = False

        for rel in list(child_local_elements(rels_dom.documentElement, "Relationship")):
            _, rel_type, target, target_mode = read_relationship(rel)
            if rel_type not in _SLIDE_REL_TYPES:
                continue
            part = opc_target(target, source_part, target_mode)
            if part is None:
                continue
            if opc_part_key(part) not in referenced_slide_keys:
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
        source_part = (
            ""
            if opc_part_key(rels_file.relative_to(unpacked_dir).as_posix()) == "_rels/.rels"
            else rels_source_part(rels_file, unpacked_dir)
        )
        dom = parse_xml_file(rels_file)
        for rel in child_local_elements(dom.documentElement, "Relationship"):
            _, _, target, target_mode = read_relationship(rel)
            part = opc_target(target, source_part, target_mode)
            if part is not None:
                referenced.add(part)

    return referenced


def remove_orphaned_rels_files(unpacked_dir: Path) -> list[str]:
    rels_parent_keys = {
        "ppt/charts/_rels",
        "ppt/diagrams/_rels",
        "ppt/drawings/_rels",
    }
    files_by_key = _package_files_by_key(unpacked_dir)
    removed = []

    for key, rels_file in list(files_by_key.items()):
        if posixpath.dirname(key) not in rels_parent_keys or not key.endswith(".rels"):
            continue
        base_name = posixpath.basename(key)[:-5]
        if not base_name:
            continue
        owner_dir = posixpath.dirname(posixpath.dirname(key))
        if f"{owner_dir}/{base_name}" not in files_by_key:
            rels_file.unlink()
            removed.append(rels_file.relative_to(unpacked_dir).as_posix())

    return removed


def get_referenced_files(unpacked_dir: Path) -> set[str]:
    return _referenced_by(_find_rels_files(_package_files_by_key(unpacked_dir)), unpacked_dir)


def remove_orphaned_files(unpacked_dir: Path, referenced: set) -> list[str]:
    referenced_keys = {
        opc_part_key(
            item.as_posix() if isinstance(item, Path) else str(item).replace("\\", "/").lstrip("/")
        )
        for item in referenced
    }
    resource_dir_keys = {
        "ppt/media",
        "ppt/embeddings",
        "ppt/charts",
        "ppt/diagrams",
        "ppt/tags",
        "ppt/drawings",
        "ppt/ink",
    }
    files_by_key = _package_files_by_key(unpacked_dir)
    removed = []

    for key, file_path in list(files_by_key.items()):
        if posixpath.dirname(key) in resource_dir_keys and key not in referenced_keys:
            file_path.unlink()
            removed.append(file_path.relative_to(unpacked_dir).as_posix())
            files_by_key.pop(key, None)

    for key, file_path in list(files_by_key.items()):
        if (
            posixpath.dirname(key) == "ppt/theme"
            and posixpath.basename(key).startswith("theme")
            and key.endswith(".xml")
            and key not in referenced_keys
        ):
            file_path.unlink()
            removed.append(file_path.relative_to(unpacked_dir).as_posix())
            files_by_key.pop(key, None)
            theme_rels_key = f"ppt/theme/_rels/{posixpath.basename(key)}.rels"
            theme_rels = files_by_key.get(theme_rels_key)
            if theme_rels is not None and theme_rels.exists():
                theme_rels.unlink()
                removed.append(theme_rels.relative_to(unpacked_dir).as_posix())
                files_by_key.pop(theme_rels_key, None)

    for key, file_path in list(files_by_key.items()):
        if (
            posixpath.dirname(key) == "ppt/notesslides"
            and key.endswith(".xml")
            and key not in referenced_keys
        ):
            file_path.unlink()
            removed.append(file_path.relative_to(unpacked_dir).as_posix())
            files_by_key.pop(key, None)

    for key, file_path in list(files_by_key.items()):
        if posixpath.dirname(key) == "ppt/notesslides/_rels" and key.endswith(".rels"):
            base_name = posixpath.basename(key)[:-5]
            if not base_name:
                continue
            notes_key = f"ppt/notesslides/{base_name}"
            if notes_key not in files_by_key:
                file_path.unlink()
                removed.append(file_path.relative_to(unpacked_dir).as_posix())
                files_by_key.pop(key, None)

    return removed


def update_content_types(unpacked_dir: Path, removed_files: list[str]) -> None:
    ct_path = _package_files_by_key(unpacked_dir).get("[content_types].xml")
    if ct_path is None or not ct_path.exists():
        return

    removed_keys = {opc_part_key(p.replace("\\", "/").lstrip("/")) for p in removed_files}
    dom = parse_xml_file(ct_path)
    changed = False

    for override in list(child_local_elements(dom.documentElement, "Override")):
        part_name = normalize_part_name(override.getAttribute("PartName"))
        if part_name is not None and opc_part_key(part_name) in removed_keys:
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

    files_by_key = _validate_presentation_package(unpacked_dir)

    if not _find_rels_files(files_by_key) or not get_referenced_files(unpacked_dir):
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
