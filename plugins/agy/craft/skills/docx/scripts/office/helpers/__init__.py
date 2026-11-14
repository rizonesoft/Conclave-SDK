import io
import os
import posixpath
import re
import shutil
import stat
import tempfile
import urllib.parse
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

SLIDE_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide"


def one_line(text: str, limit: int) -> str:
    return "".join(c if c.isprintable() else c.encode("unicode_escape").decode() for c in text)[:limit]


def opc_target(target: str, source_part: str, target_mode: str = "") -> str | None:
    if not target:
        return None
    if target_mode.lower() == "external":
        return None
    target = urllib.parse.unquote(target)

    if _SCHEME_RE.match(target):
        return None

    if "\\" in target:
        raise ValueError(f"relationship target is not a POSIX part name: {target!r}")

    if target.startswith("/"):
        joined = target.lstrip("/")
    else:
        joined = posixpath.join(posixpath.dirname(source_part), target)

    parts: list[str] = []
    for segment in posixpath.normpath(joined).split("/"):
        if segment in ("", "."):
            continue
        if segment == "..":
            if not parts:
                raise ValueError(f"relationship target escapes the package: {target!r}")
            parts.pop()
        else:
            parts.append(segment)

    if not parts:
        raise ValueError(f"relationship target resolves to nothing: {target!r}")
    return "/".join(parts)


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
