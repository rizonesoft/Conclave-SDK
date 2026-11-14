"""Add a slide to a PPTX: duplicate an existing slide or instantiate a layout.

Does all of the package bookkeeping, so the deck stays valid:
  - writes the new ppt/slides/slideN.xml (and its .rels, minus any
    notesSlide reference, so the source's speaker notes aren't shared)
  - registers it in [Content_Types].xml
  - adds a slide relationship with a fresh rId to presentation.xml.rels
  - inserts <p:sldId id="..." r:id="..."/> with a fresh id into
    <p:sldIdLst>: at the end, or after --after SLIDE
  - counts the new slide in docProps/app.xml

Works on an unpacked directory (during an editing session) or directly on a
.pptx/.potx file (extracted to a temp dir, then rezipped atomically; the
temp dir is discarded, so unpack the output if you still need to edit the
new slide's content).

Usage:
    python add_slide.py unpacked/ slide2.xml                 # duplicate slide2
    python add_slide.py unpacked/ slideLayout3.xml           # new slide from a layout
    python add_slide.py unpacked/ slide2.xml --after slide2.xml
    python add_slide.py deck.pptx slide2.xml                 # rewrite deck.pptx in place
    python add_slide.py deck.pptx slide2.xml -o out.pptx

A duplicated slide still holds the source's content: edit ppt/slides/slideN.xml
(printed on success) to change it. To list layouts: ls <dir>/ppt/slideLayouts/
"""

import argparse
import posixpath
import re
import sys
from typing import NoReturn
import tempfile
import zipfile
from pathlib import Path
from xml.parsers.expat import ExpatError

from office.helpers import (
    CONTENT_TYPES_NS,
    OFFICE_REL_NS,
    PACKAGE_RELS_NS,
    SLIDE_REL_TYPE,
    STRICT_OFFICE_REL_NS,
    append_ns_child,
    atomic_copy,
    atomic_write_bytes,
    atomic_write_text,
    child_local_elements,
    collapse_xml_space,
    ensure_ns_prefix,
    get_rel_id_attr,
    local_elements,
    normalize_part_name,
    opc_target,
    parse_xml_bytes,
    parse_xml_file,
    read_relationship,
    rezip,
    safe_extract,
)

MINIMAL_SLIDE_XML = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld>
    <p:spTree>
      <p:nvGrpSpPr>
        <p:cNvPr id="1" name=""/>
        <p:cNvGrpSpPr/>
        <p:nvPr/>
      </p:nvGrpSpPr>
      <p:grpSpPr>
        <a:xfrm>
          <a:off x="0" y="0"/>
          <a:ext cx="0" cy="0"/>
          <a:chOff x="0" y="0"/>
          <a:chExt cx="0" cy="0"/>
        </a:xfrm>
      </p:grpSpPr>
    </p:spTree>
  </p:cSld>
  <p:clrMapOvr>
    <a:masterClrMapping/>
  </p:clrMapOvr>
</p:sld>'''

SHARED_PART_TYPES = ("chart", "diagramData", "oleObject", "package")

_TRANSITIONAL_P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
_STRICT_P_NS = "http://purl.oclc.org/ooxml/presentationml/main"
SLIDE_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.presentationml.slide+xml"
TAGS_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.presentationml.tags+xml"

SLIDE_ID_MIN = 256
SLIDE_ID_MAX = 2147483647


def _die(msg: str) -> NoReturn:
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(1)


def _node_local_name(node) -> str:
    return node.localName or node.tagName.rsplit(":", 1)[-1]


def _root_with_local_name(dom, local_name: str, label: str):
    root = dom.documentElement
    if root is None or _node_local_name(root) != local_name:
        raise ValueError(f"invalid {label} root element")
    return root


def get_next_slide_number(slides_dir: Path) -> int:
    existing = [int(m.group(1)) for f in slides_dir.glob("slide*.xml")
                if (m := re.fullmatch(r"slide(\d{1,9})\.xml", f.name))]
    return max(existing) + 1 if existing else 1


def parse_source(source: str) -> tuple[str, str | None]:
    if source.startswith("slideLayout") and source.endswith(".xml"):
        return ("layout", source)

    return ("slide", None)


def create_slide_from_layout(unpacked_dir: Path, layout_file: str, after: str | None = None) -> str:
    slides_dir = unpacked_dir / "ppt" / "slides"
    rels_dir = slides_dir / "_rels"
    layout_path = unpacked_dir / "ppt" / "slideLayouts" / layout_file

    if not layout_path.exists():
        _die(f"{layout_path} not found")

    next_num = get_next_slide_number(slides_dir)
    dest = f"slide{next_num}.xml"
    after_rid = _precheck_registration(unpacked_dir, after, dest)
    slides_dir.mkdir(parents=True, exist_ok=True)

    atomic_write_text(slides_dir / dest, MINIMAL_SLIDE_XML, encoding="utf-8")

    rels_dir.mkdir(exist_ok=True)
    rels_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/{layout_file}"/>
</Relationships>'''
    atomic_write_text(rels_dir / f"{dest}.rels", rels_xml, encoding="utf-8")

    _register_slide(unpacked_dir, dest, layout_file, after_rid)
    return dest


def duplicate_slide(unpacked_dir: Path, source: str, after: str | None = None) -> str:
    slides_dir = unpacked_dir / "ppt" / "slides"
    rels_dir = slides_dir / "_rels"
    source_slide = slides_dir / source

    if not source_slide.exists():
        _die(f"{source_slide} not found")

    next_num = get_next_slide_number(slides_dir)
    dest = f"slide{next_num}.xml"
    after_rid = _precheck_registration(unpacked_dir, after, dest)

    atomic_copy(source_slide, slides_dir / dest)

    source_rels = rels_dir / f"{source}.rels"
    shared_parts: list[str] = []
    if source_rels.exists():
        dest_rels = rels_dir / f"{dest}.rels"
        atomic_copy(source_rels, dest_rels)
        rels_dom = parse_xml_file(dest_rels)
        rels_root = _root_with_local_name(rels_dom, "Relationships", dest_rels.name)
        shared_kinds: set[str] = set()
        for rel in list(child_local_elements(rels_root, "Relationship")):
            _, rel_type, _, _ = read_relationship(rel)
            if rel_type.endswith("/relationships/notesSlide"):
                rels_root.removeChild(rel)
            elif rel_type.endswith("/relationships/tags"):
                _with_own_tags_part(unpacked_dir, rel, f"ppt/slides/{dest}")
            elif "/relationships/" in rel_type:
                kind = rel_type.rsplit("/relationships/", 1)[-1]
                if kind in SHARED_PART_TYPES:
                    shared_kinds.add(kind)
        atomic_write_bytes(
            dest_rels,
            rels_dom.toxml(encoding="UTF-8", standalone=rels_dom.standalone),
        )
        shared_parts = sorted(shared_kinds)

    _register_slide(unpacked_dir, dest, source, after_rid)
    if shared_parts:
        print(
            f"Note: {dest} shares its {', '.join(shared_parts)} part(s) with {source} "
            f"(they are referenced, not copied): editing those parts changes both slides"
        )
    return dest


def _ensure_content_type_override(
    unpacked_dir: Path, part_name: str, content_type: str
) -> None:
    content_types_path = unpacked_dir / "[Content_Types].xml"
    dom = parse_xml_file(content_types_path)
    root = _root_with_local_name(dom, "Types", "[Content_Types].xml")
    wanted = normalize_part_name(part_name)
    if wanted is not None and any(
        normalize_part_name(el.getAttribute("PartName")) == wanted
        for el in child_local_elements(root, "Override")
    ):
        return
    append_ns_child(
        dom,
        root,
        "Override",
        {"PartName": part_name, "ContentType": content_type},
        expected_ns=CONTENT_TYPES_NS,
    )
    atomic_write_bytes(
        content_types_path,
        dom.toxml(encoding="UTF-8", standalone=dom.standalone),
    )


def _with_own_tags_part(unpacked_dir: Path, rel, slide_part: str) -> None:
    _, _, raw_target, target_mode = read_relationship(rel)
    try:
        source = opc_target(raw_target, slide_part, target_mode) if raw_target else None
    except ValueError:
        source = None
    if source is None or not (unpacked_dir / source).is_file():
        return

    tags_dir = (unpacked_dir / source).parent
    names = [f.name for f in tags_dir.iterdir()]
    content_types_path = unpacked_dir / "[Content_Types].xml"
    if content_types_path.is_file():
        ct_dom = parse_xml_file(content_types_path)
        ct_root = _root_with_local_name(ct_dom, "Types", "[Content_Types].xml")
        names.extend(
            norm_part.rsplit("/", 1)[-1]
            for el in child_local_elements(ct_root, "Override")
            if (norm_part := normalize_part_name(el.getAttribute("PartName")))
        )
    taken = [int(m.group(1)) for name in names if (m := re.fullmatch(r"tag(\d{1,9})\.xml", name, re.I))]
    copy = tags_dir / f"tag{max(taken, default=0) + 1}.xml"
    atomic_copy(unpacked_dir / source, copy)

    part = copy.relative_to(unpacked_dir).as_posix()
    _ensure_content_type_override(unpacked_dir, f"/{part}", TAGS_CONTENT_TYPE)
    relative = posixpath.relpath(part, posixpath.dirname(slide_part))
    rel.setAttribute("Target", relative)


def _precheck_registration(unpacked_dir: Path, after: str | None, dest: str) -> str | None:
    pres_path = unpacked_dir / "ppt" / "presentation.xml"
    if not pres_path.exists():
        _die(f"{pres_path} not found: is this an unpacked PPTX?")
    pres_dom = parse_xml_file(pres_path)
    root = _root_with_local_name(pres_dom, "presentation", "presentation.xml")

    sld_id_lst = _only_child(root, "sldIdLst")
    if sld_id_lst is None and _only_child(root, "sldMasterIdLst") is None:
        _die("presentation.xml has no <p:sldIdLst> (or <p:sldMasterIdLst> to anchor a new one)")

    stale = []
    content_types = unpacked_dir / "[Content_Types].xml"
    if content_types.exists():
        ct_dom = parse_xml_file(content_types)
        ct_root = _root_with_local_name(ct_dom, "Types", "[Content_Types].xml")
        if any(
            normalize_part_name(el.getAttribute("PartName")) == f"ppt/slides/{dest}"
            for el in child_local_elements(ct_root, "Override")
        ):
            stale.append("[Content_Types].xml")
    pres_rels = unpacked_dir / "ppt" / "_rels" / "presentation.xml.rels"
    if pres_rels.exists() and _find_slide_relationship_dom(
        parse_xml_file(pres_rels), dest
    ):
        stale.append("presentation.xml.rels")
    if stale:
        _die(
            f"{dest} is still registered in {' and '.join(stale)} but absent from ppt/slides/: "
            f"run clean.py first"
        )

    if not after:
        return None
    after_rid = _rid_for_slide(unpacked_dir, after)
    if sld_id_lst is None or not any(
        get_rel_id_attr(el) == after_rid
        for el in child_local_elements(sld_id_lst, "sldId")
    ):
        _die(f"{after} ({after_rid}) is not listed in <p:sldIdLst>")
    return after_rid


def _register_slide(unpacked_dir: Path, dest: str, source_desc: str, after_rid: str | None) -> None:
    _add_to_content_types(unpacked_dir, dest)
    rid = _add_to_presentation_rels(unpacked_dir, dest)
    slide_id = _get_next_slide_id(unpacked_dir)
    pos, total = _insert_into_sld_id_lst(unpacked_dir, slide_id, rid, after_rid)

    _count_slide_in_app_properties(unpacked_dir, pos)

    print(f"Created ppt/slides/{dest} from {source_desc}")
    print(
        f'Inserted <p:sldId id="{slide_id}" r:id="{rid}"/> into <p:sldIdLst> '
        f"at position {pos} of {total}"
    )


def _count_slide_in_app_properties(unpacked_dir: Path, position: int) -> None:
    path = unpacked_dir / "docProps" / "app.xml"
    if not path.is_file():
        return
    try:
        dom = parse_xml_file(path)
        slides = _only_child(dom.documentElement, "Slides")
        was = int(slides.firstChild.data)
        if not _add_slide_title(dom, was, position):
            return
    except (AttributeError, LookupError, ValueError, TypeError, OSError, ExpatError):
        return  
    slides.firstChild.data = str(was + 1)
    atomic_write_bytes(path, dom.toxml(encoding="UTF-8", standalone=dom.standalone))


def _add_slide_title(dom, was: int, position: int) -> bool:
    heading_pairs = _only_child(dom.documentElement, "HeadingPairs")
    titles_of_parts = _only_child(dom.documentElement, "TitlesOfParts")
    if heading_pairs is None and titles_of_parts is None:
        return True
    headings, titles = _only_child(heading_pairs, "vector"), _only_child(titles_of_parts, "vector")
    pairs = [v.getElementsByTagName("*")[0] for v in _elements(headings)]
    names = [n.firstChild.data if n.firstChild else "" for n in pairs[0::2]]
    counts = pairs[1::2]
    sizes = [int(c.firstChild.data) for c in counts]
    entries = _elements(titles)
    consistent = (
        int(headings.getAttribute("size")) == 2 * len(counts) == len(_elements(headings))
        and int(titles.getAttribute("size")) == len(entries) == sum(sizes)
    )
    titled = [i for i, name in enumerate(names) if name == "Slide Titles"]
    as_long = [i for i in titled or range(len(sizes)) if sizes[i] == was > 0]
    if not consistent or len(as_long) != 1:
        return False
    (group,) = as_long

    title = entries[0].cloneNode(False)
    title.appendChild(dom.createTextNode(f"Slide {was + 1}"))
    at = sum(sizes[:group]) + min(position - 1, was)
    titles.insertBefore(title, entries[at] if at < len(entries) else None)
    titles.setAttribute("size", str(len(entries) + 1))
    counts[group].firstChild.data = str(was + 1)
    return True


def _elements(node) -> list:
    return [c for c in node.childNodes if c.nodeType == c.ELEMENT_NODE]


def _only_child(node, local_name: str):
    found = child_local_elements(node, local_name)
    return found[0] if len(found) == 1 else None


def _add_to_content_types(unpacked_dir: Path, dest: str) -> None:
    _ensure_content_type_override(
        unpacked_dir, f"/ppt/slides/{dest}", SLIDE_CONTENT_TYPE
    )


def _find_slide_relationship_dom(rels_dom, slide_name: str) -> str | None:
    root = _root_with_local_name(rels_dom, "Relationships", "presentation.xml.rels")
    expected_part = f"ppt/slides/{slide_name}"
    for rel in child_local_elements(root, "Relationship"):
        rid, _, target, target_mode = read_relationship(rel)
        if not target:
            continue
        part = opc_target(target, "ppt/presentation.xml", target_mode)
        if part == expected_part and rid:
            return rid
    return None


def _find_slide_relationship(pres_rels: str, slide_name: str) -> str | None:
    return _find_slide_relationship_dom(parse_xml_bytes(pres_rels.encode("utf-8")), slide_name)


def _add_to_presentation_rels(unpacked_dir: Path, dest: str) -> str:
    pres_rels_path = unpacked_dir / "ppt" / "_rels" / "presentation.xml.rels"
    rels_dom = parse_xml_file(pres_rels_path)
    rels_root = _root_with_local_name(rels_dom, "Relationships", "presentation.xml.rels")

    existing = _find_slide_relationship_dom(rels_dom, dest)
    if existing:
        return existing

    pres_dom = parse_xml_file(unpacked_dir / "ppt" / "presentation.xml")
    pres_root = _root_with_local_name(pres_dom, "presentation", "presentation.xml")

    used: set[int] = set()
    for rel in child_local_elements(rels_root, "Relationship"):
        rel_id, _, _, _ = read_relationship(rel)
        if (m := re.fullmatch(r"rId(\d{1,9})", rel_id)):
            used.add(int(m.group(1)))
    for el in pres_dom.getElementsByTagName("*"):
        if not el.attributes:
            continue
        for i in range(el.attributes.length):
            attr = el.attributes.item(i)
            if attr.namespaceURI in (OFFICE_REL_NS, STRICT_OFFICE_REL_NS) or attr.name.endswith(":id"):
                if (m := re.fullmatch(r"rId(\d{1,9})", collapse_xml_space(attr.value))):
                    used.add(int(m.group(1)))

    rid = f"rId{max(used) + 1 if used else 1}"
    slide_rel_type = (
        f"{STRICT_OFFICE_REL_NS}/slide"
        if pres_root.namespaceURI == _STRICT_P_NS
        else SLIDE_REL_TYPE
    )
    append_ns_child(
        rels_dom,
        rels_root,
        "Relationship",
        {"Id": rid, "Type": slide_rel_type, "Target": f"slides/{dest}"},
        expected_ns=PACKAGE_RELS_NS,
    )
    atomic_write_bytes(
        pres_rels_path,
        rels_dom.toxml(encoding="UTF-8", standalone=rels_dom.standalone),
    )

    return rid


def _get_next_slide_id(unpacked_dir: Path) -> int:
    pres_dom = parse_xml_file(unpacked_dir / "ppt" / "presentation.xml")
    pres_root = _root_with_local_name(pres_dom, "presentation", "presentation.xml")
    used: set[int] = set()
    for el in local_elements(pres_root, "sldId"):
        raw = el.getAttribute("id").strip()
        if raw.isdigit() and len(raw) <= 10:
            used.add(int(raw))

    candidate = max((i for i in used if i >= SLIDE_ID_MIN), default=SLIDE_ID_MIN - 1) + 1
    if candidate <= SLIDE_ID_MAX and candidate not in used:
        return candidate
    for i in range(SLIDE_ID_MIN, SLIDE_ID_MAX + 1):
        if i not in used:
            return i
    _die("no slide id available in [256, 2147483647]: the deck is full")


def _create_child_element(dom, parent, local_name: str):
    if parent.namespaceURI:
        qname = f"{parent.prefix}:{local_name}" if parent.prefix else local_name
        return dom.createElementNS(parent.namespaceURI, qname)
    return dom.createElement(local_name)


def _insert_into_sld_id_lst(
    unpacked_dir: Path, slide_id: int, rid: str, after_rid: str | None = None
) -> tuple[int, int]:
    pres_path = unpacked_dir / "ppt" / "presentation.xml"
    pres_dom = parse_xml_file(pres_path)
    root = _root_with_local_name(pres_dom, "presentation", "presentation.xml")

    if any(get_rel_id_attr(el) == rid for el in local_elements(root, "sldId")):
        _die(f"presentation.xml already references {rid}; refusing to add a duplicate")

    rel_ns = STRICT_OFFICE_REL_NS if root.namespaceURI == _STRICT_P_NS else OFFICE_REL_NS
    r_prefix = ensure_ns_prefix(pres_dom, root, rel_ns, default_prefix="r")

    sld_id_lst = _only_child(root, "sldIdLst")
    if sld_id_lst is None:
        master_lst = _only_child(root, "sldMasterIdLst")
        if master_lst is None:
            _die("presentation.xml has no <p:sldIdLst> (or <p:sldMasterIdLst> to anchor a new one)")
        sld_id_lst = _create_child_element(pres_dom, root, "sldIdLst")
        root.insertBefore(sld_id_lst, master_lst.nextSibling)

    entry = _create_child_element(pres_dom, sld_id_lst, "sldId")
    entry.setAttribute("id", str(slide_id))
    entry.setAttributeNS(rel_ns, f"{r_prefix}:id", rid)

    if after_rid:
        anchor = next(
            (el for el in child_local_elements(sld_id_lst, "sldId") if get_rel_id_attr(el) == after_rid),
            None,
        )
        if anchor is None:
            _die(f"{after_rid} is not listed in <p:sldIdLst>")
        sld_id_lst.insertBefore(entry, anchor.nextSibling)
    else:
        sld_id_lst.appendChild(entry)

    atomic_write_bytes(
        pres_path,
        pres_dom.toxml(encoding="UTF-8", standalone=pres_dom.standalone),
    )

    entries = child_local_elements(sld_id_lst, "sldId")
    position = next(
        (i for i, el in enumerate(entries, 1) if get_rel_id_attr(el) == rid),
        len(entries),
    )
    return position, len(entries)


def _rid_for_slide(unpacked_dir: Path, slide_name: str) -> str:
    pres_rels_path = unpacked_dir / "ppt" / "_rels" / "presentation.xml.rels"
    rid = _find_slide_relationship_dom(parse_xml_file(pres_rels_path), slide_name)
    if not rid:
        _die(f"{slide_name} has no relationship in presentation.xml.rels")
    return rid


def add_slide(unpacked_dir: Path, source: str, after: str | None = None) -> str:
    source_type, layout_file = parse_source(source)
    if source_type == "layout" and layout_file is not None:
        return create_slide_from_layout(unpacked_dir, layout_file, after)
    return duplicate_slide(unpacked_dir, source, after)


def add_slide_to_package(
    package: Path, source: str, after: str | None = None, output: Path | None = None
) -> str:
    out = output or package
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        with zipfile.ZipFile(package) as zf:
            safe_extract(zf, tmp_path)
        dest = add_slide(tmp_path, source, after)
        rezip(tmp_path, out)
    print(f"Wrote {out}: the new slide is ppt/slides/{dest} inside it (unpack to edit its content)")
    return dest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Add a slide to a PPTX: duplicate a slide or instantiate a layout. "
        "Registers content types, relationships, and <p:sldIdLst>."
    )
    parser.add_argument("target", help="Unpacked PPTX directory OR a .pptx/.potx file")
    parser.add_argument(
        "source",
        help="slideN.xml to duplicate, or slideLayoutN.xml to create from a layout "
        "(list layouts with: ls <dir>/ppt/slideLayouts/)",
    )
    parser.add_argument(
        "--after",
        metavar="SLIDE",
        help="insert after this slide, e.g. slide2.xml (default: append at the end)",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="output file (only with a .pptx/.potx target; default: rewrite the input in place)",
    )
    args = parser.parse_args()

    target = Path(args.target)
    if target.is_dir():
        if args.output:
            parser.error("--output is only valid for .pptx/.potx input; a directory is modified in place")
        try:
            add_slide(target, args.source, args.after)
        except (OSError, ValueError, ExpatError) as e:
            _die(str(e))
    elif target.is_file() and target.suffix.lower() in (".pptx", ".potx"):
        try:
            add_slide_to_package(target, args.source, args.after, Path(args.output) if args.output else None)
        except (OSError, ValueError, ExpatError, zipfile.BadZipFile) as e:
            _die(str(e))
    else:
        _die(f"{target} is neither a directory nor a .pptx/.potx file")


if __name__ == "__main__":
    main()
