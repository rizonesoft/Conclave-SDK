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
import json
import os
import re
import sys
import tarfile

MAX_MEMBERS = 20_000
MAX_BYTES = 200 * 1024 * 1024
DRIVE = re.compile(r"^[A-Za-z]:")


class Unsafe(Exception):
    pass


def check(members):
    """The archive's single top folder, or Unsafe naming the first member that breaks a rule."""
    if not members:
        raise Unsafe("the archive is empty")
    if len(members) > MAX_MEMBERS:
        raise Unsafe(f"the archive holds more than {MAX_MEMBERS} members")
    if sum(m.size for m in members if m.isfile()) > MAX_BYTES:
        raise Unsafe(f"the archive expands to more than {MAX_BYTES // (1024 * 1024)} MB")
    tops = set()
    for member in members:
        name = member.name
        if not (member.isfile() or member.isdir()):
            raise Unsafe(f"{name!r} is not a regular file or a folder")
        if not name or name.startswith(("/", "\\")) or DRIVE.match(name):
            raise Unsafe(f"{name!r} is an absolute name")
        parts = [p for p in re.split(r"[/\\]", name) if p not in ("", ".")]
        if not parts or ".." in parts:
            raise Unsafe(f"{name!r} leaves the archive's folder")
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
        with tarfile.open(archive, "r:gz") as tar:
            members = tar.getmembers()
            top = check(members)
            if os.path.exists(destination) and os.listdir(destination):
                raise Unsafe(f"{destination} is not empty")
            os.makedirs(destination, exist_ok=True)
            tar.extractall(destination, members=members, filter="data")
    except Unsafe as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 2
    except (OSError, tarfile.TarError, EOFError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": f"the archive cannot be read: {exc}"}))
        return 2
    print(json.dumps({"ok": True, "top": top, "files": sum(1 for m in members if m.isfile())}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
