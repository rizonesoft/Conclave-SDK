import io
import os
import posixpath
import re
import shutil
import stat
import tempfile
import urllib.parse
import xml.etree.ElementTree as _stdlib_et
import xml.parsers.expat as _expat
import zipfile
from pathlib import Path

OOXML_FAMILY = {
    ".docx": "docx",
    ".dotx": "docx",
    ".pptx": "pptx",
    ".potx": "pptx",
    ".xlsx": "xlsx",
    ".xltx": "xlsx",
}

_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*:")
_PCT_SLASH_RE = re.compile(r"%2f|%5c", re.IGNORECASE)
_BAD_PCT_RE = re.compile(r"%(?![0-9A-Fa-f]{2})")
_PCT_PAIR_RE = re.compile(r"%([0-9A-Fa-f]{2})")
_IPV6_HOST_RE = re.compile(r"^\[[0-9A-Fa-f:.]+\](?::[0-9]*)?\Z")
_XML_SPACE_RUN_RE = re.compile(r"[ \t\r\n]+")
_UNRESERVED_BYTES = frozenset(
    b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"
)
_ASCII_PCHAR = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~!$&'()*+,;=:@ "
)

SLIDE_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide"
PACKAGE_RELS_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
OFFICE_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
STRICT_OFFICE_REL_NS = "http://purl.oclc.org/ooxml/officeDocument/relationships"
MAX_XML_DEPTH = 256
XML_PARSE_ERRORS = (_expat.ExpatError, _stdlib_et.ParseError, LookupError, ValueError)


def collapse_xml_space(value: str) -> str:
    return _XML_SPACE_RUN_RE.sub(" ", value).strip(" ")


def read_relationship(rel_el) -> tuple[str, str, str, str]:
    if hasattr(rel_el, "getAttribute"):
        raw_id = rel_el.getAttribute("Id") or ""
        raw_type = rel_el.getAttribute("Type") or ""
        raw_target = rel_el.getAttribute("Target") or ""
        target_mode = rel_el.getAttribute("TargetMode") or ""
    else:
        raw_id = rel_el.get("Id") or ""
        raw_type = rel_el.get("Type") or ""
        raw_target = rel_el.get("Target") or ""
        target_mode = rel_el.get("TargetMode") or ""
    return (
        collapse_xml_space(raw_id),
        collapse_xml_space(raw_type),
        collapse_xml_space(raw_target),
        target_mode,
    )


def one_line(text: str, limit: int) -> str:
    return "".join(c if c.isprintable() else c.encode("unicode_escape").decode() for c in text)[:limit]


def _is_valid_decoded_char(ch: str) -> bool:
    code = ord(ch)
    if code < 0x80:
        return 0x20 <= code <= 0x7E
    return (
        0xA0 <= code <= 0x10FFFF
        and not (0xD800 <= code <= 0xDFFF)
        and code not in (0xFFFE, 0xFFFF)
    )


def _is_valid_uri_char(ch: str, extra_ascii: str = "") -> bool:
    code = ord(ch)
    if code < 0x80:
        return ch in _ASCII_PCHAR or ch == "%" or ch in extra_ascii
    return (
        0xA0 <= code <= 0x10FFFF
        and not (0xD800 <= code <= 0xDFFF)
        and code not in (0xFFFE, 0xFFFF)
    )


def _strict_unquote(value: str) -> str:
    if _BAD_PCT_RE.search(value):
        raise ValueError("invalid percent-encoding")
    try:
        decoded = urllib.parse.unquote(value, encoding="utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError("invalid UTF-8 percent-encoding") from exc
    if not all(_is_valid_decoded_char(ch) for ch in decoded):
        raise ValueError("URI contains control or noncharacter codepoints")
    return decoded


def is_valid_any_uri(value: str) -> bool:
    if not isinstance(value, str):
        return False
    collapsed = collapse_xml_space(value)
    if (
        not collapsed
        or _BAD_PCT_RE.search(collapsed)
        or collapsed.count("#") > 1
        or not all(_is_valid_decoded_char(ch) for ch in collapsed)
    ):
        return False
    before_frag, _, frag = collapsed.partition("#")
    if "[" in frag or "]" in frag:
        return False
    hier_part, _, query = before_frag.partition("?")
    if "[" in query or "]" in query:
        return False
    scheme_match = _SCHEME_RE.match(hier_part)
    rest = hier_part[scheme_match.end():] if scheme_match else hier_part
    if rest.startswith("//"):
        authority, _, path_part = rest[2:].partition("/")
        if "[" in path_part or "]" in path_part:
            return False
        if "[" in authority or "]" in authority:
            userinfo, sep, hostport = authority.rpartition("@")
            if (sep and ("[" in userinfo or "]" in userinfo)) or not _IPV6_HOST_RE.match(hostport):
                return False
    elif "[" in rest or "]" in rest:
        return False
    return True


def _is_valid_part_segment(segment: str) -> bool:
    return bool(
        segment
        and "/" not in segment
        and "\\" not in segment
        and not segment.endswith(".")
        and all(_is_valid_decoded_char(ch) for ch in segment)
    )


def _validated_source_segments(source_part: str) -> list[str]:
    if source_part.startswith("//") or source_part.endswith("/"):
        raise ValueError(f"relationship source part is not a valid OPC part name: {source_part!r}")
    base_raw = source_part.removeprefix("/")
    base_parts = base_raw.split("/") if base_raw else []
    if not base_parts or not all(_is_valid_part_segment(seg) for seg in base_parts):
        raise ValueError(f"relationship source part is not a valid OPC part name: {source_part!r}")
    return base_parts


def opc_target(target: str, source_part: str, target_mode: str = "") -> str | None:
    if target_mode == "External":
        if not is_valid_any_uri(target):
            raise ValueError(f"external relationship target is not a valid URI: {target!r}")
        return None
    if target_mode not in ("", "Internal"):
        raise ValueError(f"invalid relationship TargetMode: {target_mode!r}")

    raw = collapse_xml_space(target)
    if not raw:
        raise ValueError("relationship target is empty")
    if _BAD_PCT_RE.search(raw):
        raise ValueError(f"relationship target has invalid percent-encoding: {target!r}")
    if _SCHEME_RE.match(raw):
        raise ValueError(f"internal relationship target cannot have a URI scheme: {target!r}")
    if raw.startswith("//"):
        raise ValueError(f"internal relationship target cannot have a URI authority: {target!r}")
    if "\\" in raw:
        raise ValueError(f"relationship target is not a POSIX part name: {target!r}")

    path_ref, frag_sep, fragment = raw.partition("#")
    if frag_sep:
        if not all(_is_valid_uri_char(ch, "/?") for ch in fragment):
            raise ValueError(f"relationship target fragment has invalid URI characters: {target!r}")
        try:
            _strict_unquote(fragment)
        except ValueError as exc:
            raise ValueError(f"relationship target fragment has invalid percent-encoding: {target!r}") from exc

    if "?" in path_ref:
        raise ValueError(f"internal relationship target cannot have a query component: {target!r}")
    if _PCT_SLASH_RE.search(path_ref):
        raise ValueError(f"relationship target is not a POSIX part name: {target!r}")
    if not all(_is_valid_uri_char(ch, "/") for ch in path_ref):
        raise ValueError(f"relationship target has invalid URI characters: {target!r}")
    if path_ref and not path_ref.startswith("/") and ":" in path_ref.split("/", 1)[0]:
        raise ValueError(f"relative relationship target first segment cannot contain ':': {target!r}")

    if not path_ref:
        if not frag_sep or not source_part:
            raise ValueError(f"relationship target resolves to nothing: {target!r}")
        return "/".join(_validated_source_segments(source_part))

    parts: list[str] = []
    if not path_ref.startswith("/") and source_part:
        parts.extend(_validated_source_segments(source_part)[:-1])

    raw_segments = path_ref[1:].split("/") if path_ref.startswith("/") else path_ref.split("/")
    for idx, raw_seg in enumerate(raw_segments):
        is_last = idx == len(raw_segments) - 1
        if not raw_seg:
            raise ValueError(f"relationship target has an empty path segment: {target!r}")
        try:
            seg = _strict_unquote(raw_seg)
        except ValueError as exc:
            raise ValueError(f"relationship target has invalid percent-encoding: {target!r}") from exc
        if seg == ".":
            if is_last:
                raise ValueError(f"relationship target resolves to a directory: {target!r}")
            continue
        if seg == "..":
            if not parts:
                raise ValueError(f"relationship target escapes the package: {target!r}")
            if is_last:
                raise ValueError(f"relationship target resolves to a directory: {target!r}")
            parts.pop()
            continue
        if not _is_valid_part_segment(seg):
            raise ValueError(f"relationship target is not a valid OPC part name: {target!r}")
        parts.append(seg)

    if not parts:
        raise ValueError(f"relationship target resolves to nothing: {target!r}")
    return "/".join(parts)


def normalize_part_name(part_name: str) -> str | None:
    if not isinstance(part_name, str):
        return None
    collapsed = collapse_xml_space(part_name)
    if (
        not collapsed.startswith("/")
        or collapsed.endswith("/")
        or "\\" in collapsed
        or "?" in collapsed
        or "#" in collapsed
        or _BAD_PCT_RE.search(collapsed)
        or not all(_is_valid_uri_char(ch, "/") for ch in collapsed[1:])
    ):
        return None
    for match in _PCT_PAIR_RE.finditer(collapsed):
        octet = int(match.group(1), 16)
        if octet in (0x2F, 0x5C) or octet in _UNRESERVED_BYTES or octet < 0x20 or octet == 0x7F:
            return None
    segments: list[str] = []
    for raw_seg in collapsed[1:].split("/"):
        if not raw_seg:
            return None
        try:
            seg = _strict_unquote(raw_seg)
        except ValueError:
            return None
        if not _is_valid_part_segment(seg):
            return None
        segments.append(seg)
    return "/".join(segments) if segments else None


def rels_source_part(rels_file: Path, unpacked_dir: Path) -> str:
    owner_dir = rels_file.parent.parent.relative_to(unpacked_dir)
    part = posixpath.join(owner_dir.as_posix(), rels_file.name[: -len(".rels")])
    return part.removeprefix("./")


def part_text(data: bytes) -> str:
    return data.decode("utf-8", "surrogateescape")


XML_SPACE = " \t\r\n"


def rendered_text(text: str, preserve: bool) -> str:
    return text if preserve else text.strip(XML_SPACE)


MAX_ARCHIVE_ENTRIES = 10_000
MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
MAX_MEMBER_BYTES = 128 * 1024 * 1024
_EXTRACT_CHUNK = 64 * 1024


def validate_archive(
    zf: zipfile.ZipFile,
    max_entries: int = MAX_ARCHIVE_ENTRIES,
    max_bytes: int = MAX_ARCHIVE_BYTES,
    max_member_bytes: int = MAX_MEMBER_BYTES,
) -> None:
    infos = zf.infolist()
    if len(infos) > max_entries:
        raise ValueError(f"archive entry count {len(infos)} exceeds limit {max_entries}")
    declared_total = 0
    for m in infos:
        if stat.S_ISLNK(m.external_attr >> 16):
            raise ValueError(f"symlink archive entry not allowed: {m.filename!r}")
        if m.file_size < 0 or m.file_size > max_member_bytes:
            raise ValueError(f"archive member exceeds size budget: {m.filename!r}")
        declared_total += m.file_size
        if declared_total > max_bytes:
            raise ValueError(f"archive declared size exceeds limit {max_bytes} bytes")


class _BoundedZipStream(io.RawIOBase):
    def __init__(
        self,
        raw: io.BufferedIOBase,
        name: str,
        budget: list[int] | None,
        max_member_bytes: int,
        max_bytes: int,
    ) -> None:
        super().__init__()
        self._raw = raw
        self._name = name
        self._budget = budget
        self._max_member_bytes = max_member_bytes
        self._max_bytes = max_bytes
        self._member_read = 0

    def readable(self) -> bool:
        return True

    def readinto(self, b) -> int:
        if self.closed:
            raise ValueError("I/O operation on closed file")
        remaining_member = self._max_member_bytes - self._member_read
        if self._budget is not None:
            remaining_total = self._max_bytes - self._budget[0]
            remaining = min(remaining_member, remaining_total)
        else:
            remaining = remaining_member
        to_read = min(len(b), max(0, remaining) + 1)
        data = self._raw.read(to_read)
        n = len(data)
        if n == 0:
            return 0
        self._member_read += n
        if self._member_read > self._max_member_bytes:
            raise ValueError(
                f"archive member {self._name!r} exceeds unpacked limit {self._max_member_bytes}"
            )
        if self._budget is not None:
            self._budget[0] += n
            if self._budget[0] > self._max_bytes:
                raise ValueError(
                    f"archive exceeds unpacked byte budget {self._max_bytes}"
                )
        b[:n] = data
        return n

    def close(self) -> None:
        if not self.closed:
            try:
                self._raw.close()
            finally:
                super().close()


def open_zip_member(
    zf: zipfile.ZipFile,
    name: str,
    *,
    budget: list[int] | None = None,
    max_member_bytes: int = MAX_MEMBER_BYTES,
    max_bytes: int = MAX_ARCHIVE_BYTES,
) -> io.BufferedReader:
    info = zf.getinfo(name)
    if stat.S_ISLNK(info.external_attr >> 16):
        raise ValueError(f"symlink archive entry not allowed: {name!r}")
    member_cap = min(max_member_bytes, max_bytes)
    if info.file_size < 0 or info.file_size > member_cap:
        raise ValueError(f"archive member exceeds size budget: {name!r}")
    if budget is not None and budget[0] + info.file_size > max_bytes:
        raise ValueError(f"archive exceeds unpacked byte budget: {name!r}")
    raw = zf.open(info, "r")
    try:
        stream = _BoundedZipStream(raw, name, budget, max_member_bytes, max_bytes)
        return io.BufferedReader(stream, buffer_size=_EXTRACT_CHUNK)
    except BaseException:
        raw.close()
        raise


def read_zip_member(
    zf: zipfile.ZipFile,
    name: str,
    *,
    budget: list[int] | None = None,
    max_member_bytes: int = MAX_MEMBER_BYTES,
    max_bytes: int = MAX_ARCHIVE_BYTES,
) -> bytes:
    chunks: list[bytes] = []
    with open_zip_member(
        zf,
        name,
        budget=budget,
        max_member_bytes=max_member_bytes,
        max_bytes=max_bytes,
    ) as fh:
        while True:
            chunk = fh.read(_EXTRACT_CHUNK)
            if not chunk:
                break
            chunks.append(chunk)
    return b"".join(chunks)


def safe_extract(
    zf: zipfile.ZipFile,
    dest: Path,
    max_entries: int = MAX_ARCHIVE_ENTRIES,
    max_bytes: int = MAX_ARCHIVE_BYTES,
    max_member_bytes: int = MAX_MEMBER_BYTES,
) -> None:
    dest = dest.resolve()
    infos = zf.infolist()
    if len(infos) > max_entries:
        raise ValueError(f"archive entry count {len(infos)} exceeds limit {max_entries}")

    declared_total = 0
    targets: list[tuple[zipfile.ZipInfo, Path]] = []
    for m in infos:
        if stat.S_ISLNK(m.external_attr >> 16):
            raise ValueError(f"symlink archive entry not allowed: {m.filename!r}")
        target = (dest / m.filename).resolve()
        if not target.is_relative_to(dest):
            raise ValueError(f"unsafe archive entry: {m.filename!r}")
        if m.file_size < 0 or m.file_size > max_member_bytes:
            raise ValueError(f"archive member exceeds size budget: {m.filename!r}")
        declared_total += m.file_size
        if declared_total > max_bytes:
            raise ValueError(f"archive declared size exceeds limit {max_bytes} bytes")
        targets.append((m, target))

    total_written = 0
    for m, target in targets:
        if m.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        member_written = 0
        try:
            with zf.open(m, "r") as src, open(target, "wb") as dst:
                while True:
                    chunk = src.read(_EXTRACT_CHUNK)
                    if not chunk:
                        break
                    member_written += len(chunk)
                    total_written += len(chunk)
                    if member_written > max_member_bytes or total_written > max_bytes:
                        raise ValueError("archive exceeds unpacked byte budget")
                    dst.write(chunk)
        except BaseException:
            target.unlink(missing_ok=True)
            raise


def folder_entries(package: Path) -> list[str]:
    with zipfile.ZipFile(package) as zf:
        return [info.filename for info in zf.infolist() if info.is_dir()]


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Atomically write bytes to path via a sibling temp file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=path.parent
    )
    tmp_path = Path(tmp_name)
    fd_open = True
    try:
        with os.fdopen(fd, "wb") as fh:
            fd_open = False
            fh.write(data)
        if path.exists():
            mode = path.stat().st_mode & 0o777
        else:
            umask = os.umask(0)
            os.umask(umask)
            mode = 0o666 & ~umask
        os.chmod(tmp_path, mode)
        os.replace(tmp_path, path)
    finally:
        if fd_open:
            try:
                os.close(fd)
            except OSError:
                pass
        tmp_path.unlink(missing_ok=True)


def atomic_write_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    """Atomically write text to path via a sibling temp file."""
    atomic_write_bytes(path, text.encode(encoding))


def atomic_copy(src: Path, dst: Path) -> None:
    """Atomically copy src to dst via a sibling temp file."""
    with open(src, "rb") as src_fh:
        dst.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            prefix=dst.name + ".", suffix=".tmp", dir=dst.parent
        )
        tmp_path = Path(tmp_name)
        fd_open = True
        try:
            with os.fdopen(fd, "wb") as dst_fh:
                fd_open = False
                shutil.copyfileobj(src_fh, dst_fh)
            try:
                shutil.copystat(src, tmp_path)
            except OSError:
                pass
            os.replace(tmp_path, dst)
        finally:
            if fd_open:
                try:
                    os.close(fd)
                except OSError:
                    pass
            tmp_path.unlink(missing_ok=True)


def rezip(src_dir: Path, out_path: Path) -> None:
    files = sorted(p for p in src_dir.rglob("*") if p.is_file())
    ct = src_dir / "[Content_Types].xml"
    fd, tmp_name = tempfile.mkstemp(
        prefix=out_path.name + ".", suffix=".tmp", dir=out_path.parent
    )
    tmp_out = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as fh:
            with zipfile.ZipFile(fh, "w", zipfile.ZIP_DEFLATED) as zf:
                if ct.exists():
                    zf.write(ct, ct.relative_to(src_dir), compress_type=zipfile.ZIP_STORED)
                for f in files:
                    if f == ct:
                        continue
                    zf.write(f, f.relative_to(src_dir))
        if out_path.exists():
            mode = out_path.stat().st_mode & 0o777
        else:
            umask = os.umask(0)
            os.umask(umask)
            mode = 0o666 & ~umask
        os.chmod(tmp_out, mode)
        os.replace(tmp_out, out_path)
    finally:
        if tmp_out.exists():
            tmp_out.unlink()


def _guard_xml_bytes(data: bytes) -> None:
    parser = _expat.ParserCreate()
    depth = 0

    def _forbid(*_args):
        raise ValueError("XML DTD and entity declarations are forbidden")

    def _start(_name, _attrs):
        nonlocal depth
        depth += 1
        if depth > MAX_XML_DEPTH:
            raise ValueError(f"XML nesting depth exceeds limit {MAX_XML_DEPTH}")

    def _end(_name):
        nonlocal depth
        if depth > 0:
            depth -= 1

    parser.StartDoctypeDeclHandler = _forbid
    parser.EntityDeclHandler = _forbid
    parser.UnparsedEntityDeclHandler = _forbid
    parser.ExternalEntityRefHandler = _forbid
    parser.StartElementHandler = _start
    parser.EndElementHandler = _end
    parser.Parse(data, True)


def _wrap_defusedxml_error(fn, data: bytes):
    try:
        return fn(data)
    except Exception as exc:
        if type(exc).__module__.startswith("defusedxml"):
            raise ValueError(str(exc)) from exc
        raise


def parse_xml_bytes(data: bytes, max_bytes: int = MAX_MEMBER_BYTES):
    if len(data) > max_bytes:
        raise ValueError(f"XML document size {len(data)} exceeds limit {max_bytes}")
    _guard_xml_bytes(data)
    try:
        import defusedxml.minidom as _minidom
        parse_fn = _minidom.parseString
    except (ImportError, AttributeError):
        import xml.dom.minidom as _minidom
        parse_fn = _minidom.parseString
    return _wrap_defusedxml_error(parse_fn, data)


def parse_xml_file(path: Path, max_bytes: int = MAX_MEMBER_BYTES):
    size = path.stat().st_size
    if size > max_bytes:
        raise ValueError(f"XML file {path.name} size {size} exceeds limit {max_bytes}")
    return parse_xml_bytes(path.read_bytes(), max_bytes=max_bytes)


def parse_et_bytes(data: bytes, max_bytes: int = MAX_MEMBER_BYTES):
    if len(data) > max_bytes:
        raise ValueError(f"XML document size {len(data)} exceeds limit {max_bytes}")
    _guard_xml_bytes(data)
    try:
        from defusedxml.ElementTree import fromstring as _et_fromstring
    except (ImportError, AttributeError):
        _et_fromstring = _stdlib_et.fromstring
    return _wrap_defusedxml_error(_et_fromstring, data)


def parse_et_file(path: Path, max_bytes: int = MAX_MEMBER_BYTES):
    size = path.stat().st_size
    if size > max_bytes:
        raise ValueError(f"XML file {path.name} size {size} exceeds limit {max_bytes}")
    return parse_et_bytes(path.read_bytes(), max_bytes=max_bytes)


def _node_local_name(node) -> str:
    return node.localName or node.tagName.rsplit(":", 1)[-1]


def child_local_elements(node, local_name: str) -> list:
    if node is None:
        return []
    return [
        c
        for c in node.childNodes
        if c.nodeType == c.ELEMENT_NODE and _node_local_name(c) == local_name
    ]


def local_elements(node, local_name: str) -> list:
    if node is None:
        return []
    return [
        el for el in node.getElementsByTagName("*") if _node_local_name(el) == local_name
    ]


def append_ns_child(
    dom,
    parent,
    local_name: str,
    attrs: dict[str, str],
    expected_ns: str | None = None,
):
    if parent is None:
        raise ValueError("cannot append child to None XML parent")
    if expected_ns is not None and parent.namespaceURI not in (None, "", expected_ns):
        raise ValueError(
            f"unexpected XML namespace {parent.namespaceURI!r}, expected {expected_ns!r}"
        )
    if parent.namespaceURI:
        qname = f"{parent.prefix}:{local_name}" if parent.prefix else local_name
        el = dom.createElementNS(parent.namespaceURI, qname)
    else:
        el = dom.createElement(local_name)
    for k, v in attrs.items():
        el.setAttribute(k, v)
    parent.appendChild(el)
    return el


def ensure_ns_prefix(dom, root, target_ns: str, default_prefix: str = "r") -> str:
    if root.attributes:
        for i in range(root.attributes.length):
            attr = root.attributes.item(i)
            if attr.value == target_ns and (
                attr.prefix == "xmlns" or attr.name.startswith("xmlns:")
            ):
                pfx = attr.localName or attr.name.split(":", 1)[1]
                if pfx and pfx != "xmlns":
                    return pfx

    used_bindings: dict[str, set[str]] = {}
    candidate_prefixes: list[str] = []
    for el in dom.getElementsByTagName("*"):
        if not el.attributes:
            continue
        for i in range(el.attributes.length):
            attr = el.attributes.item(i)
            if attr.prefix == "xmlns" or attr.name.startswith("xmlns:"):
                pfx = attr.localName or attr.name.split(":", 1)[1]
                if pfx and pfx != "xmlns":
                    used_bindings.setdefault(pfx, set()).add(attr.value)
                    if attr.value == target_ns:
                        candidate_prefixes.append(pfx)

    for pfx in candidate_prefixes:
        if (
            not root.hasAttribute(f"xmlns:{pfx}")
            and used_bindings.get(pfx) == {target_ns}
        ):
            root.setAttribute(f"xmlns:{pfx}", target_ns)
            return pfx

    prefix = default_prefix
    idx = 0
    while prefix in used_bindings:
        idx += 1
        prefix = f"{default_prefix}{idx}"
    root.setAttribute(f"xmlns:{prefix}", target_ns)
    return prefix


def get_rel_id_attr(el) -> str:
    return collapse_xml_space(
        el.getAttributeNS(OFFICE_REL_NS, "id")
        or el.getAttributeNS(STRICT_OFFICE_REL_NS, "id")
        or el.getAttribute("r:id")
        or ""
    )
