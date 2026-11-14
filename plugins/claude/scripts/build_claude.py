#!/usr/bin/env python3
"""Build the Claude connection plugins and stamp each bundle with the digest of the sources it was built from.

    python <SDK>/plugins/claude/scripts/build_claude.py [--check] [name ...]

For every plugin (all of them when none is named) this runs `npm ci` (always, so the bundle holds the dependencies
the lockfile names), then `npm run build`, then writes `dist/source.sha256`. `dist/server.mjs` and the stamp are tracked in git, so a fresh
checkout runs the servers without a build step. `--check` builds nothing: it reports each bundle that is missing or
was built from other sources and exits 1. The stamp is a digest, not a file time, because a checkout gives every
file an arbitrary time. Standard library only.
"""
import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGINS = ("domains-co-za", "bunny-net")
BUNDLE = Path("dist") / "server.mjs"
STAMP = Path("dist") / "source.sha256"


def source_files(plugin_dir):
    """Everything the bundle is built from: the two package manifests and every file under src/."""
    plugin_dir = Path(plugin_dir)
    files = [plugin_dir / name for name in ("package.json", "package-lock.json") if (plugin_dir / name).is_file()]
    src = plugin_dir / "src"
    files += [p for p in src.rglob("*") if p.is_file()] if src.is_dir() else []
    return sorted(files, key=lambda p: p.relative_to(plugin_dir).as_posix())


def source_digest(plugin_dir):
    """SHA-256 over the source files' relative paths and content, with line endings normalised to LF."""
    plugin_dir = Path(plugin_dir)
    digest = hashlib.sha256()
    for path in source_files(plugin_dir):
        digest.update(path.relative_to(plugin_dir).as_posix().encode("utf-8") + b"\0")
        digest.update(path.read_bytes().replace(b"\r\n", b"\n") + b"\0")
    return digest.hexdigest()


def stale(plugin_dir):
    """Why the plugin's bundle cannot be trusted to match its sources, or None when it does."""
    plugin_dir = Path(plugin_dir)
    if not (plugin_dir / BUNDLE).is_file():
        return "%s is missing" % BUNDLE.as_posix()
    stamp = plugin_dir / STAMP
    if not stamp.is_file():
        return "%s is missing" % STAMP.as_posix()
    if stamp.read_text(encoding="utf-8").strip() != source_digest(plugin_dir):
        return "%s was built from other sources than src/ now holds" % BUNDLE.as_posix()
    return None


def write_stamp(plugin_dir):
    target = Path(plugin_dir) / STAMP
    fd, tmp = tempfile.mkstemp(dir=str(target.parent), prefix=".stamp-", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write((source_digest(plugin_dir) + "\n").encode("utf-8"))
        os.replace(tmp, target)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def build(plugin_dir):
    npm = shutil.which("npm")
    if not npm:
        raise SystemExit("npm is not on PATH")
    # Always a clean install: a node_modules left from another lockfile would be bundled under the new stamp.
    subprocess.run([npm, "ci", "--no-audit", "--no-fund"], cwd=str(plugin_dir), check=True, stdout=subprocess.DEVNULL)
    subprocess.run([npm, "run", "build"], cwd=str(plugin_dir), check=True, stdout=subprocess.DEVNULL)
    write_stamp(plugin_dir)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("names", nargs="*", help="plugins to build (default: all): %s" % ", ".join(PLUGINS))
    parser.add_argument("--check", action="store_true", help="build nothing; exit 1 when a bundle is missing or stale")
    args = parser.parse_args(argv)
    unknown = [name for name in args.names if name not in PLUGINS]
    if unknown:
        parser.error("unknown plugin: %s (choose from %s)" % (", ".join(unknown), ", ".join(PLUGINS)))
    failed = False
    for name in args.names or PLUGINS:
        if not args.check:
            build(ROOT / name)
        problem = stale(ROOT / name)
        print("%s: %s" % (name, problem or ("current" if args.check else "built")))
        failed = failed or bool(problem)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
