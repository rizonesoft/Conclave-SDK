"""Extract a Conclave-SDK tarball from GitHub, refusing the whole archive if any member is unsafe.

    python -I extract_sdk.py <archive.tar.gz> <destination folder>

Ships inside the extension and runs with the workspace's resolved Python in isolated mode (design spec section 8);
nothing from the archive runs. Every member is checked before anything is written: it must be a regular file or a
directory, its name must not be absolute (a leading / or \\, or a drive letter) or hold a .. segment on either
separator, and it must lie inside the archive's single top folder. Only then is the archive extracted, with tarfile's
"data" filter as a second layer (that filter alone strips a leading / and keeps links that stay inside the target, so
it is not the check). Prints one JSON object: {"ok": true, "top": <top folder>, "files": <count>} and exit 0, or
{"ok": false, "error": <reason>} and exit 2. Stdlib only.
"""
import gzip
import json
import os
import re
import sys
import tarfile

MAX_MEMBERS = 20_000
MAX_BYTES = 200 * 1024 * 1024
MAX_ARCHIVE = 100 * 1024 * 1024
DRIVE = re.compile(r"^[A-Za-z]:")


class Unsafe(Exception):
    pass


def shown(name):
    """A name as a refusal quotes it: at most 120 characters, so a hostile name never fills the reply or the log."""
    return repr(name if len(name) <= 120 else name[:120] + "...")


MAX_STREAM = MAX_BYTES + 64 * 1024 * 1024
MAX_METADATA = 1024 * 1024
MAX_CHAIN = 8
MAX_PAX_KEYS = 16
MAX_NAME = 4096
MAX_MTIME = 2 ** 33
PAX_KEYS = {"path", "linkpath", "comment"}
EXTENDED = {tarfile.XHDTYPE, tarfile.XGLTYPE, tarfile.SOLARIS_XHDTYPE, tarfile.GNUTYPE_LONGNAME, tarfile.GNUTYPE_LONGLINK}
WINDOWS_RESERVED = re.compile(r"^(con|prn|aux|nul|com[0-9]|lpt[0-9])(\..*)?$", re.IGNORECASE)
WINDOWS_FORBIDDEN = re.compile(r'[<>:"|?*\x00-\x1f]')


class Bounded(tarfile.TarInfo):
    """tarfile's own header parse with the limits in it, so the limits see exactly the boundaries extraction uses.

    tarfile reads an extended header's whole payload (PAX x, g or Solaris X; GNU long name or link) into memory before
    it yields the member the header describes, and it follows a chain of them recursively. TarInfo has no public hook
    for that, so this overrides the private dispatch every header passes through (_proc_member, stable since Python
    3.2), refusing on the header's own size before the payload is read. Sparse members are refused outright, before
    any map is read: a git archive never holds one, and a GNU sparse 1.0 map is read from the stream with no bound.
    """

    def _proc_member(self, tarfile_):
        if self.type in EXTENDED:
            if self.size > MAX_METADATA:
                raise Unsafe(f"a metadata header of {self.size} bytes is larger than {MAX_METADATA} bytes")
            chain = getattr(tarfile_, "_conclave_chain", 0) + 1
            if chain > MAX_CHAIN:
                raise Unsafe(f"more than {MAX_CHAIN} extended headers in a row")
            tarfile_._conclave_chain = chain
        else:
            tarfile_._conclave_chain = 0
        if self.type == tarfile.GNUTYPE_SPARSE:
            raise Unsafe(f"{shown(self.name)} is a sparse file")
        return super()._proc_member(tarfile_)

    # Every member gets the PAX headers that apply to it, the global ones included, applied and copied here. git writes
    # one key in its global header (comment) and one or two in a member's (path, linkpath): any other key, a name
    # longer than MAX_NAME bytes or more than MAX_PAX_KEYS keys is refused before tarfile applies or copies anything.
    def _apply_pax_info(self, pax_headers, encoding, errors):
        if len(pax_headers) > MAX_PAX_KEYS:
            raise Unsafe(f"a PAX header with {len(pax_headers)} keys, more than {MAX_PAX_KEYS}")
        for key, value in pax_headers.items():
            if key not in PAX_KEYS:
                raise Unsafe(f"a PAX header holds {shown(key)}, which git does not write")
            if key != "comment" and len(value) > MAX_NAME:
                raise Unsafe(f"a PAX {key} of {len(value)} characters, longer than {MAX_NAME}")
        return super()._apply_pax_info(pax_headers, encoding, errors)

    # _proc_pax hands a PAX header that names a GNU sparse map to one of these before anything else reads it (3.11.4
    # to 3.14); refusing here, without delegating, means no map is parsed.
    def _proc_gnusparse_00(self, next_, *args):
        raise Unsafe(f"{shown(next_.name)} is a sparse file (a GNU sparse map, refused before it is read)")

    def _proc_gnusparse_01(self, next_, *args):
        raise Unsafe(f"{shown(next_.name)} is a sparse file (a GNU sparse map, refused before it is read)")

    def _proc_gnusparse_10(self, next_, *args):
        raise Unsafe(f"{shown(next_.name)} is a sparse file (a GNU sparse map, refused before it is read)")


class Capped:
    """The decompressed stream under tarfile, refusing a read or seek past MAX_STREAM: tarfile skips member data with
    forward seeks, which decompress without passing through read, so the position is what is checked."""

    def __init__(self, stream):
        self._stream = stream

    def _check(self, position):
        if position > MAX_STREAM:
            raise Unsafe(f"the archive decompresses to more than {MAX_STREAM // (1024 * 1024)} MB")

    def read(self, size=-1):
        if size is None or size < 0:
            size = MAX_STREAM + 1 - self._stream.tell()
        self._check(self._stream.tell() + min(size, MAX_STREAM + 1))
        return self._stream.read(size)

    def seek(self, offset, whence=0):
        target = offset if whence == 0 else self._stream.tell() + offset if whence == 1 else MAX_STREAM + 1
        self._check(target)
        return self._stream.seek(offset, whence)

    def tell(self):
        return self._stream.tell()


class Seen:
    """What check_member has seen so far, by case-folded name: every name, the files, the folders a name implies, and
    the top folders."""

    def __init__(self):
        self.names, self.files, self.parents, self.tops = {}, set(), set(), set()


def check_member(member, seen):
    """Refuses a member that breaks a rule, the moment tarfile has read it: before the next member is read, so a rule
    that sees one bad member (a name repeated by a global PAX path, a second top folder) stops the archive there."""
    name = member.name
    if len(name.encode("utf-8", "surrogateescape")) > MAX_NAME:
        raise Unsafe(f"a name of {len(name)} characters is longer than {MAX_NAME}")
    # A name seen before, exactly or differing only in case (one file on Windows and macOS), would let a later member
    # replace an earlier one: a git archive never repeats a name, so the archive is refused.
    folded = "/".join(p for p in re.split(r"[/\\]", name) if p not in ("", ".")).casefold()
    if folded in seen.names:
        earlier = seen.names[folded]
        raise Unsafe(f"{shown(name)} repeats {shown(earlier)}" if earlier != name else f"{shown(name)} appears twice")
    seen.names[folded] = name
    if not (member.isfile() or member.isdir()):
        raise Unsafe(f"{shown(name)} is not a regular file or a folder")
    if not name or name.startswith(("/", "\\")) or DRIVE.match(name):
        raise Unsafe(f"{shown(name)} is an absolute name")
    parts = [p for p in re.split(r"[/\\]", name) if p not in ("", ".")]
    if not parts or ".." in parts:
        raise Unsafe(f"{shown(name)} leaves the archive's folder")
    # Names Windows would change or read as something else (trailing dots or spaces are dropped, ':' opens an
    # alternate stream, CON or NUL is a device): one could replace another file, so the archive is refused.
    for part in parts:
        if part.endswith((".", " ")) or WINDOWS_FORBIDDEN.search(part) or WINDOWS_RESERVED.match(part):
            raise Unsafe(f"{shown(name)} has a part Windows cannot hold as written")
    seen.tops.add(parts[0])
    if len(seen.tops) > 1:
        raise Unsafe(f"the archive has {len(seen.tops)} top folders, not one")
    if member.isfile() and len(parts) < 2:
        raise Unsafe(f"{shown(name)} is a file outside the archive's top folder")
    # A file where a folder is needed, in either order (a/b after the file a, or the file a after a/b): extraction
    # would write one and then fail on the other, leaving a partial folder.
    folded_parts = folded.split("/")
    ancestors = ["/".join(folded_parts[:i]) for i in range(1, len(folded_parts))]
    clash = next((a for a in ancestors if a in seen.files), None)
    if clash is not None:
        raise Unsafe(f"{shown(name)} needs {shown(seen.names[clash])} to be a folder, but it is a file")
    if member.isfile():
        if folded in seen.parents:
            raise Unsafe(f"{shown(name)} is a file, but an earlier name needs it to be a folder")
        seen.files.add(folded)
    seen.parents.update(ancestors)
    # tarfile writes the header's time with os.utime, which raises OverflowError past the platform's range: a git
    # archive carries the commit time, so anything outside 1970 to 2242 is refused before anything is written.
    if not 0 <= member.mtime < MAX_MTIME:
        raise Unsafe(f"{shown(name)} has the time {member.mtime}, outside 1970 to 2242")


def members_of(tar):
    """The archive's members and its single top folder, each member checked as it is read, so the limits and rules
    stop a hostile archive before the rest of it is read."""
    members, total, seen = [], 0, Seen()
    for member in tar:
        # Its PAX headers are applied by now (name, size); kept, they would hold every member's copy until extraction.
        member.pax_headers = {}
        check_member(member, seen)
        members.append(member)
        total += member.size if member.isfile() else 0
        if len(members) > MAX_MEMBERS:
            raise Unsafe(f"the archive holds more than {MAX_MEMBERS} members")
        if total > MAX_BYTES:
            raise Unsafe(f"the archive expands to more than {MAX_BYTES // (1024 * 1024)} MB")
    if not members:
        raise Unsafe("the archive is empty")
    return members, seen.tops.pop()


def main(argv):
    if len(argv) != 3:
        print(json.dumps({"ok": False, "error": "usage: extract_sdk.py <archive.tar.gz> <destination folder>"}))
        return 2
    archive, destination = argv[1], argv[2]
    if not hasattr(tarfile, "data_filter"):
        print(json.dumps({"ok": False, "error": f"Python {sys.version.split()[0]} has no tarfile data filter (3.11.4 or later)"}))
        return 2
    try:
        if os.path.getsize(archive) > MAX_ARCHIVE:
            raise Unsafe(f"the archive is larger than {MAX_ARCHIVE // (1024 * 1024)} MB")
        with gzip.open(archive, "rb") as stream, tarfile.open(fileobj=Capped(stream), mode="r:", tarinfo=Bounded) as tar:
            members, top = members_of(tar)
            if os.path.exists(destination) and os.listdir(destination):
                raise Unsafe(f"{destination} is not empty")
            os.makedirs(destination, exist_ok=True)
            tar.extractall(destination, members=members, filter="data")
    except Unsafe as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 2
    except (OSError, tarfile.TarError, EOFError, ValueError, OverflowError, gzip.BadGzipFile, RecursionError) as exc:
        print(json.dumps({"ok": False, "error": f"the archive cannot be read: {exc}"}))
        return 2
    print(json.dumps({"ok": True, "top": top, "files": sum(1 for m in members if m.isfile())}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
