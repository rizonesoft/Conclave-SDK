"""Records the digest of the kits this extension bundles with its version in extensions/vscode/sdk-digest.json
(plan R39). A kit change ships with a new extension version: run this after raising the version in package.json, and
tests/test_sdk_digest.py fails until the two agree. Standard library only; run from anywhere.

The record holds the version and each kit's digest from `forge.py digest`, not the SDK commit: a commit recorded here
could never be the one that contains this file. The bundle step writes the commit into sdk/SDK_COMMIT instead.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

EXTENSION = Path(__file__).resolve().parents[1]
SDK = EXTENSION.parents[1]
RECORD = EXTENSION / "sdk-digest.json"


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
    kits = json.loads(run.stdout)["kits"]
    version = json.loads((EXTENSION / "package.json").read_text(encoding="utf-8"))["version"]
    old = None
    if RECORD.is_file():
        old = json.loads(RECORD.read_text(encoding="utf-8"))
        if old.get("kits") != kits and old.get("version") == version:
            changed = sorted(k for k in set(kits) | set(old.get("kits", {})) if kits.get(k) != old["kits"].get(k))
            print(f"record-sdk-digest: the kits changed ({', '.join(changed)}) but the extension is still version "
                  f"{version}, which was recorded with the old kits: raise the version in package.json first.", file=sys.stderr)
            return 2
    record = {"version": version, "kits": dict(sorted(kits.items()))}
    if record != old:
        atomic_write(RECORD, json.dumps(record, indent=2) + "\n")
    print(f"record-sdk-digest: version {version}, {len(kits)} kits")
    return 0


if __name__ == "__main__":
    sys.exit(main())
