"""Records the digest of the SDK this extension bundles (forge.py and the kits) with its version in
extensions/vscode/sdk-digest.json (plan R39). A change to forge.py or a kit ships with a new, higher extension version:
run this after raising the version in package.json, and tests/test_sdk_digest.py fails until the two agree. Standard
library only; run from anywhere.

The record holds the version, forge.py's digest and each kit's digest from `forge.py digest`, not the SDK commit: a
commit recorded here could never be the one that contains this file. The bundle step writes the commit into
sdk/SDK_COMMIT instead.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

EXTENSION = Path(__file__).resolve().parents[1]
SDK = EXTENSION.parents[1]
RECORD = EXTENSION / "sdk-digest.json"


def version_key(version: str) -> tuple:
    """A version's order: its numeric parts, so 0.0.10 is after 0.0.9. Anything else is refused."""
    if not re.fullmatch(r"\d+(\.\d+)*", version):
        raise ValueError(f"version {version!r} is not numbers separated by dots")
    return tuple(int(part) for part in version.split("."))


def atomic_write(path: Path, text: str) -> None:
    fd, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as out:
            out.write(text)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main() -> int:
    run = subprocess.run([sys.executable, str(SDK / "forge.py"), "digest"], capture_output=True, text=True)
    if run.returncode != 0:
        print(f"record-sdk-digest: forge.py digest failed: {run.stderr.strip()}", file=sys.stderr)
        return 1
    digest = json.loads(run.stdout)
    version = json.loads((EXTENSION / "package.json").read_text(encoding="utf-8"))["version"]
    record = {"version": version, "forge": digest["forge"], "kits": dict(sorted(digest["kits"].items()))}
    old = json.loads(RECORD.read_text(encoding="utf-8")) if RECORD.is_file() else None
    if old is not None and (old.get("forge"), old.get("kits")) != (record["forge"], record["kits"]):
        try:
            higher = version_key(version) > version_key(old["version"])
        except ValueError as exc:
            print(f"record-sdk-digest: {exc}", file=sys.stderr)
            return 2
        if not higher:
            print(f"record-sdk-digest: forge.py or the kits changed but the extension's version {version} is not higher "
                  f"than the recorded {old['version']}: raise the version in package.json first.", file=sys.stderr)
            return 2
    if record != old:
        atomic_write(RECORD, json.dumps(record, indent=2) + "\n")
    print(f"record-sdk-digest: version {version}, forge.py and {len(record['kits'])} kits")
    return 0


if __name__ == "__main__":
    sys.exit(main())
