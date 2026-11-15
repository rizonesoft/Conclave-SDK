#!/usr/bin/env python3
"""Say whether the project's compile database (`compile_commands.json`) can be trusted.

    python scripts/compdb-check.py [--root <project>] [--pins <pin file>] [--path <database>]
                                   [--build-file <file>]... [--json]

clangd is only as good as the compile database it reads: a stale one gives wrong diagnostics. This reads the
database the pin file names (`compdb.path` in `.conclave/toolchain-cpp.json`, `compile_commands.json` under the pin
file's `root` when it names none; `--path`, relative to `--root`, overrides it) and reports one status:

    current   it parses, every source file it names exists, and no build file is newer than it
    stale     a build file is newer than it, or a source file it names no longer exists (each is named)
    unknown   a build file named by the pin file or by --build-file cannot be read, so freshness cannot be told
    invalid   it cannot be read, is not a JSON list of entries, or holds an entry that is not one (the entry is
              named by its number)
    missing   there is no file at its path

The build files are those of `--build-file` (relative to `--root`), else the pin file's `compdb.build_files`, else
`build.ninja`, `Makefile` and `CMakeLists.txt` where they exist in the pin file's `root` and beside the database.

It exits 0 for `current`, 1 for any other status, 2 for bad usage or a pin file that does not load. It never
regenerates the database: when the pin file gives the project's own command (`compdb.regenerate`), that command is
printed and nothing is run. It reads and reports, and writes nothing. Standard library only.
"""
import argparse
import importlib.util
import json
import shlex
import sys
from pathlib import Path

PINS = ".conclave/toolchain-cpp.json"
BUILD_FILES = ("build.ninja", "Makefile", "CMakeLists.txt")
NAMED = 20   # the most files a report names; the rest are counted


def _pins_module():
    """toolchain-check.py, which owns the pin file's format, loaded from beside this script."""
    path = Path(__file__).resolve().parent / "toolchain-check.py"
    spec = importlib.util.spec_from_file_location("_toolchain_check", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def entry_fault(entry):
    """What is wrong with one entry of a compile database, or None. The format requires each entry's `directory`,
    its `file`, and the compile command as `command` (one string) or `arguments` (a list)."""
    if not isinstance(entry, dict):
        return "not an object"
    for key in ("directory", "file"):
        if key not in entry:
            return f"no `{key}`"
        if not isinstance(entry[key], str) or not entry[key].strip():
            return f"`{key}` is not a non-empty string"
    if "command" not in entry and "arguments" not in entry:
        return "neither `command` nor `arguments`"
    if "command" in entry and (not isinstance(entry["command"], str) or not entry["command"].strip()):
        return "`command` is not a command line"
    if "arguments" in entry:
        arguments = entry["arguments"]
        if (not isinstance(arguments, list) or not arguments
                or any(not isinstance(argument, str) for argument in arguments) or not arguments[0].strip()):
            return "`arguments` is not a list of strings that starts with the compiler"
    return None


def _shown(path, project):
    try:
        return path.relative_to(project).as_posix()
    except ValueError:
        return path.as_posix()


def _reason(exc):
    return exc.strerror or str(exc)


def check_database(project, pin_file, path=None, build_files=None):
    """The state of the compile database of a project whose pin file is loaded: {"path", "status", "detail",
    "entries", "newer", "gone", "regenerate"}. `path` and `build_files`, relative to the project, override the pin
    file's. No fault of the file system raises: it is a status."""
    project = Path(project).resolve()
    base = project / pin_file["root"]
    compdb = pin_file["compdb"]
    database = (project / path) if path is not None else (base / compdb["path"])
    result = {"path": _shown(database, project), "status": None, "detail": "", "entries": None, "newer": [],
              "gone": [], "regenerate": list(compdb["regenerate"])}

    def ended(status, detail):
        result.update(status=status, detail=detail)
        return result

    try:
        raw = database.read_bytes()
        written = database.stat().st_mtime_ns
    except FileNotFoundError:
        return ended("missing", f"{result['path']} does not exist")
    except OSError as exc:
        return ended("invalid", f"{result['path']} cannot be read ({_reason(exc)})")
    try:
        entries = json.loads(raw.decode("utf-8"))
    except UnicodeDecodeError as exc:
        return ended("invalid", f"{result['path']} is not UTF-8 ({exc.reason})")
    except (ValueError, RecursionError) as exc:
        return ended("invalid", f"{result['path']} is not JSON ({exc})")
    if not isinstance(entries, list):
        return ended("invalid", f"{result['path']} is not a JSON list of entries")
    if not entries:
        return ended("invalid", f"{result['path']} holds no entry, so it describes no build")
    for number, entry in enumerate(entries, 1):
        fault = entry_fault(entry)
        if fault:
            return ended("invalid", f"{result['path']}: entry {number}: {fault}")
    result["entries"] = len(entries)

    # The build files: named ones must be readable, the usual ones are compared where they exist.
    if build_files is not None:
        files, source = [project / file for file in build_files], "--build-file"
    elif compdb["build_files"] is not None:
        files, source = [base / file for file in compdb["build_files"]], "the pin file"
    else:
        files, source = [folder / name for folder in (base, database.parent) for name in BUILD_FILES], None
    times, unreadable = {}, []
    for file in files:
        try:
            times[file] = file.stat().st_mtime_ns
        except OSError as exc:
            if source is None:
                continue   # a usual build file the project does not have is no fault
            missing = isinstance(exc, FileNotFoundError)
            unreadable.append(f"{_shown(file, project)} ({'it does not exist' if missing else _reason(exc)})")
    result["newer"] = [_shown(file, project) for file, changed in times.items() if changed > written]

    gone = {}
    for entry in entries:
        directory = Path(entry["directory"])
        if not directory.is_absolute():
            directory = database.parent / directory
        source_file = Path(entry["file"])
        if not source_file.is_absolute():
            source_file = directory / source_file
        if source_file not in gone and not source_file.is_file():
            gone[source_file] = _shown(source_file, project)
    result["gone"] = list(gone.values())[:NAMED]

    if result["newer"] or gone:
        parts = []
        if result["newer"]:
            parts.append(f"older than {', '.join(result['newer'])}")
        if gone:
            more = f" and {len(gone) - NAMED} more" if len(gone) > NAMED else ""
            parts.append(f"{len(gone)} source file(s) it names no longer exist: {', '.join(result['gone'])}{more}")
        return ended("stale", f"{result['path']}: " + "; ".join(parts))
    if unreadable:
        return ended("unknown", f"{result['path']}: a build file named by {source} cannot be read, so its "
                                f"freshness cannot be told: {', '.join(unreadable)}")
    count = "1 entry" if len(entries) == 1 else f"{len(entries)} entries"
    return ended("current", f"{result['path']}, {count}")


def regenerate_line(result):
    """The project's own command that writes the database again, for a database that is not current, or None.
    It is shown, never run: a check that builds is not read-only."""
    if result["status"] == "current" or not result["regenerate"]:
        return None
    return "regenerate with: " + shlex.join(result["regenerate"])


def main(argv=None):
    parser = argparse.ArgumentParser(prog="compdb-check.py",
                                     description="Say whether the compile database can be trusted. Runs nothing.")
    parser.add_argument("--root", default=".", help="the project (default: the working directory)")
    parser.add_argument("--pins", help=f"the pin file (default: {PINS} under the root)")
    parser.add_argument("--path", help="the compile database, relative to the root (default: the pin file's)")
    parser.add_argument("--build-file", action="append", help="a file the database must not be older than, relative "
                                                              "to the root (repeatable; default: the pin file's)")
    parser.add_argument("--json", action="store_true", help="print the report as one JSON document")
    args = parser.parse_args(argv)
    project = Path(args.root).resolve()
    pins = Path(args.pins) if args.pins else project / PINS
    module = _pins_module()
    try:
        pin_file = module.load_pin_file(pins)
    except module.PinError as exc:
        print(f"compdb-check: {exc}", file=sys.stderr)
        if args.json:
            print(json.dumps({"path": None, "status": "refused", "detail": str(exc), "entries": None, "newer": [],
                              "gone": [], "regenerate": []}, indent=2))
        return 2
    result = check_database(project, pin_file, path=args.path, build_files=args.build_file)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"compile database: {result['status']}: {result['detail']}")
        line = regenerate_line(result)
        if line:
            print(line)
    return 0 if result["status"] == "current" else 1


if __name__ == "__main__":
    sys.exit(main())
