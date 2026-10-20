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


MAX_STREAM = MAX_BYTES + 64 * 1024 * 1024
MAX_METADATA = 1024 * 1024
METADATA = {b"x", b"g", b"L", b"K"}
WINDOWS_RESERVED = re.compile(r"^(con|prn|aux|nul|com[0-9]|lpt[0-9])(\..*)?$", re.IGNORECASE)
WINDOWS_FORBIDDEN = re.compile(r'[<>:"|?*\x00-\x1f]')


def header_size(block):
    """The size field of a tar header: octal, or base-256 when its first byte has the high bit set."""
    field = block[124:136]
    if field[0] & 0x80:
        return int.from_bytes(field[1:], "big")
    text = field.split(b"\0", 1)[0].strip()
    return int(text, 8) if text else 0


def prepass(archive):
    """Walks the raw tar headers through the gzip stream before tarfile reads anything, so a hostile archive is
    stopped on its decompressed size or one oversized metadata header (a PAX or GNU long-name payload, which tarfile
    reads whole into memory before it yields a member), never after the allocation."""
    total = 0
    with gzip.open(archive, "rb") as stream:
        def read(n):
            nonlocal total
            data = stream.read(n)
            total += len(data)
            if total > MAX_STREAM:
                raise Unsafe(f"the archive decompresses to more than {MAX_STREAM // (1024 * 1024)} MB")
            return data
        while True:
            block = read(512)
            if len(block) < 512 or block == bytes(512):
                return
            size = header_size(block)
            if block[156:157] in METADATA and size > MAX_METADATA:
                raise Unsafe(f"a metadata header of {size} bytes is larger than {MAX_METADATA} bytes")
            remaining = (size + 511) // 512 * 512
            while remaining:
                chunk = read(min(remaining, 1024 * 1024))
                if not chunk:
                    return
                remaining -= len(chunk)


def members_of(tar):
    """The archive's members, read one at a time so the limits stop a hostile archive before it is all in memory."""
    members, total = [], 0
    for member in tar:
        members.append(member)
        total += member.size if member.isfile() else 0
        if len(members) > MAX_MEMBERS:
            raise Unsafe(f"the archive holds more than {MAX_MEMBERS} members")
        if total > MAX_BYTES:
            raise Unsafe(f"the archive expands to more than {MAX_BYTES // (1024 * 1024)} MB")
    return members


def check(members):
    """The archive's single top folder, or Unsafe naming the first member that breaks a rule."""
    if not members:
        raise Unsafe("the archive is empty")
    tops, seen = set(), {}
    for member in members:
        name = member.name
        # A name seen before, exactly or differing only in case (one file on Windows and macOS), would let a later
        # member replace an earlier one: a git archive never repeats a name, so the archive is refused.
        folded = "/".join(p for p in re.split(r"[/\\]", name) if p not in ("", ".")).casefold()
        if folded in seen:
            raise Unsafe(f"{name!r} repeats {seen[folded]!r}" if seen[folded] != name else f"{name!r} appears twice")
        seen[folded] = name
        if not (member.isfile() or member.isdir()):
            raise Unsafe(f"{name!r} is not a regular file or a folder")
        if not name or name.startswith(("/", "\\")) or DRIVE.match(name):
            raise Unsafe(f"{name!r} is an absolute name")
        parts = [p for p in re.split(r"[/\\]", name) if p not in ("", ".")]
        if not parts or ".." in parts:
            raise Unsafe(f"{name!r} leaves the archive's folder")
        # Names Windows would change or read as something else (trailing dots or spaces are dropped, ':' opens an
        # alternate stream, CON or NUL is a device): one could replace another file, so the archive is refused.
        for part in parts:
            if part.endswith((".", " ")) or WINDOWS_FORBIDDEN.search(part) or WINDOWS_RESERVED.match(part):
                raise Unsafe(f"{name!r} has a part Windows cannot hold as written")
        tops.add(parts[0])
        if member.isfile() and len(parts) < 2:
            raise Unsafe(f"{name!r} is a file outside the archive's top folder")
    if len(tops) != 1:
        raise Unsafe(f"the archive has {len(tops)} top folders, not one")
    return tops.pop()


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
        prepass(archive)
        with tarfile.open(archive, "r:gz") as tar:
            members = members_of(tar)
            top = check(members)
            if os.path.exists(destination) and os.listdir(destination):
                raise Unsafe(f"{destination} is not empty")
            os.makedirs(destination, exist_ok=True)
            tar.extractall(destination, members=members, filter="data")
    except Unsafe as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 2
    except (OSError, tarfile.TarError, EOFError, ValueError, gzip.BadGzipFile) as exc:
        print(json.dumps({"ok": False, "error": f"the archive cannot be read: {exc}"}))
        return 2
    print(json.dumps({"ok": True, "top": top, "files": sum(1 for m in members if m.isfile())}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
