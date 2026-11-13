#!/usr/bin/env python3
"""Measure what stops a project adopting the todo kit's graph (D03 T01 §5). The SDK's own script, in no kit.

    python scripts/adoption-dry-run.py <project repository> --config <plan.json written for it> --out <empty folder>

The project is cloned with its history into <out>/snapshot (so stamped sections find their commits), its working
tree's `todo/` and receipts folder are copied over the clone (so uncommitted work is measured too), the given
configuration becomes the snapshot's `todo/plan.json`, and the kit's every-fault validation (`graph(root, faults)`,
what `validate --all` runs) reads the snapshot as its root. The faults are grouped into refusal classes (the message
with its section, path and numbers taken out), each with its count of sections and one example.

The source is only ever read: every git command run against it passes --no-optional-locks, so it never takes the
index.lock a live campaign's commit needs, and its files are copied, never touched. A source that changes while it is
copied (a live campaign committing) is copied again, up to three copies, so a torn snapshot never reports refusals
the tree does not have. What was measured is written beside the result: <out>/manifest.json (every copied file's
SHA-256, the effective plan.json, the project's commit and the SDK commit whose validator ran) and
<out>/classes.json (the classes, then every fault).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

SDK = Path(__file__).resolve().parents[1]
COPIES = 3  # the most copies of a moving source before the snapshot is given up as torn


class DryRunError(Exception):
    """A dry run that cannot measure the tree it was given (exit 2)."""


def source_git(source, *args, check=True):
    """git against the source repository: always --no-optional-locks, never a write."""
    out = subprocess.run(["git", "--no-optional-locks", "-C", str(source), *args],
                         capture_output=True, text=True, timeout=600)
    if check and out.returncode != 0:
        raise DryRunError(f"git {' '.join(args)} failed in {source}: {out.stderr.strip()[:300]}")
    return out


def atomic_write(path, data):
    """Write bytes to path through a temporary file in its folder and os.replace."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def folder_files(source, folder):
    """{posix path relative to source: bytes digest} for every regular file under source/folder, and the links
    skipped (a link is never followed out of the tree)."""
    files, links = {}, []
    base = Path(source) / folder
    if not base.is_dir() or base.is_symlink():
        return files, ([folder] if base.is_symlink() else [])
    for top, dirs, names in os.walk(base, followlinks=False):
        for name in sorted(dirs):
            if (Path(top) / name).is_symlink():
                links.append((Path(top) / name).relative_to(source).as_posix())
        for name in sorted(names):
            path = Path(top) / name
            rel = path.relative_to(source).as_posix()
            if path.is_symlink() or not path.is_file():
                links.append(rel)
                continue
            files[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return files, links


def copy_folders(source, snapshot, folders):
    """Copy each folder of the source's working tree over the snapshot's own; returns {path: digest of the bytes
    copied} and the links skipped."""
    copied, links = {}, []
    for folder in folders:
        target = Path(snapshot) / folder
        if not target.resolve().is_relative_to(Path(snapshot).resolve()) or target.resolve() == Path(snapshot).resolve():
            raise DryRunError(f"refusing to replace {target}: it is not a folder inside the snapshot")
        if target.exists():
            shutil.rmtree(target)
        _, skipped = folder_files(source, folder)
        links += skipped
        base = Path(source) / folder
        if not base.is_dir() or base.is_symlink():
            continue
        for top, dirs, names in os.walk(base, followlinks=False):
            dirs[:] = [d for d in dirs if not (Path(top) / d).is_symlink()]
            for name in names:
                path = Path(top) / name
                if path.is_symlink() or not path.is_file():
                    continue
                rel = path.relative_to(source).as_posix()
                data = path.read_bytes()
                atomic_write(Path(snapshot) / rel, data)
                copied[rel] = hashlib.sha256(data).hexdigest()
    return copied, sorted(set(links))


def receipts_of(config, source):
    """The receipts folder the configuration names, checked by the kit's own reader of todo/plan.json against the
    source (its path rules: relative POSIX names, inside the repository, through no link), so the dry run copies and
    replaces only what the graph itself would read."""
    tg = load_graph()
    try:
        return tg.plan_config(Path(source), json.dumps(config))["receipts"]
    except tg.Refused as exc:
        raise DryRunError(f"the configuration is refused: {exc}") from None


def snapshot(source, snapshot_dir, config, after_copy=None):
    """Clone source into snapshot_dir and copy its working tree's todo/ and receipts folder over the clone, again
    while the source moves under the copy. after_copy(attempt) runs after each copy (a test changes the source there).
    Returns the manifest's snapshot part."""
    source, snapshot_dir = Path(source).resolve(), Path(snapshot_dir).resolve()
    commit = source_git(source, "rev-parse", "HEAD").stdout.strip()
    source_git(source, "clone", "--quiet", "--no-hardlinks", "--no-checkout", str(source), str(snapshot_dir))
    checkout = subprocess.run(["git", "-C", str(snapshot_dir), "checkout", "--quiet", "--detach", commit],
                              capture_output=True, text=True, timeout=600)
    if checkout.returncode != 0:
        raise DryRunError(f"the clone cannot check out {commit}: {checkout.stderr.strip()[:300]}")
    folders = ["todo", receipts_of(config, source)]
    moved, attempts = set(), 0
    while True:
        attempts += 1
        copied, links = copy_folders(source, snapshot_dir, folders)
        if after_copy is not None:
            after_copy(attempts)
        now = {}
        for folder in folders:
            now.update(folder_files(source, folder)[0])
        changed = {p for p in set(copied) | set(now) if copied.get(p) != now.get(p)}
        if not changed:
            break
        moved |= changed
        if attempts >= COPIES:
            raise DryRunError(f"the source kept changing over {COPIES} copies: {', '.join(sorted(changed)[:10])}")
    config_bytes = (json.dumps(config, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    atomic_write(snapshot_dir / "todo/plan.json", config_bytes)
    return {"source": str(source), "project_commit": commit, "folders": folders, "copies": attempts,
            "moved": sorted(moved), "links_skipped": links, "files": dict(sorted(copied.items())),
            "plan_json": config}


def load_graph():
    """The kit's graph library as the SDK installs it (scripts/lib equals kits/todo's copy; a test holds them equal),
    beside the reviewer kit's dispatcher that stamped sections are checked through."""
    lib = str(SDK / "scripts/lib")
    if lib not in sys.path:
        sys.path.insert(0, lib)
    import todo_graph
    return todo_graph


REF = re.compile(r"(?:D\d{2} )?(?:T\d{2} )?§\d+")
# A path: a file name with one of the tree's extensions (with any folders before it), or a folder under one of the
# roots a TODO tree names. Prose with a slash in it ("unknown/duplicate") is neither.
PATH = re.compile(r"(?<![\w<./-])\.?[\w.-]*(?:/[\w.-]+)*\.(?:md|json|toml|py)\b"
                  r"|(?<![\w<./-])(?:todo|docs|scripts|\.claude|\.conclave)/[\w./-]*")
# A Needs value the message quotes in parentheses, itself possibly holding one pair ("Idle machine (timing)").
NEEDS_VALUE = re.compile(r"Needs \((?:[^()]|\([^()]*\))*\)")
SHA = re.compile(r"\b[0-9a-f]{12,40}\b")
# The one kit message that ends by quoting the source line it refused (xrefs_of in todo_graph.py): the line is the
# example, not the class.
QUOTED_LINE = re.compile(r"(?<=^XREF must name exactly one well-formed section): .*\Z", re.S)
# A refused adoption quotes the stamp line it could not read: the stamp is the example, not the class.
ADOPTION_QUOTE = re.compile(r"(?<=^adoption refused: its stamp names no commit on this branch) \(.*\)\Z", re.S)
NUMBER = re.compile(r"\b\d+\b")


def refusal_class(message):
    """A fault's message with its section, path, quoted Needs value and numbers taken out, so faults of one kind
    group together."""
    text = QUOTED_LINE.sub(": <line>", message)
    text = ADOPTION_QUOTE.sub(" (<stamp>)", text)
    text = REF.sub("<ref>", text)
    text = NEEDS_VALUE.sub("Needs (<value>)", text)
    text = PATH.sub("<path>", text)
    text = SHA.sub("<sha>", text)
    return NUMBER.sub("N", text)


def classes(faults):
    """[{class, sections, faults, example}] by descending count of places, then by class."""
    groups = {}
    for where, message in faults:
        entry = groups.setdefault(refusal_class(message), {"places": set(), "faults": 0, "example": None})
        entry["places"].add(where)
        entry["faults"] += 1
        entry["example"] = entry["example"] or {"where": where, "message": message}
    return [{"class": name, "sections": len(e["places"]), "faults": e["faults"], "example": e["example"]}
            for name, e in sorted(groups.items(), key=lambda kv: (-len(kv[1]["places"]), kv[0]))]


def reopen_in_snapshot(snapshot_dir, refs):
    """In the snapshot only, take the stamp lines off the sections `refs` names, as the project would before it adopts
    the rest (the kit's unstamp does the same for a section already adopted)."""
    wanted = {}
    for ref in refs:
        m = re.fullmatch(r"D(\d{2}) T(\d{2}) §(\d+)", ref)
        if m:
            wanted.setdefault((m[1], m[2]), set()).add(m[3])
    for todo in sorted((Path(snapshot_dir) / "todo").glob("[0-9][0-9]-*/TODO-*.md")):
        name = re.fullmatch(r"TODO-(\d{2})-[a-z0-9-]+\.md", todo.name)
        numbers = wanted.get((todo.parent.name[:2], name[1] if name else ""), set())
        if not numbers:
            continue
        text = todo.read_text(encoding="utf-8")
        parts = re.split(r"(?m)^(?=## \d+\. )", text)
        for i, part in enumerate(parts):
            head = re.match(r"## (\d+)\. ", part)
            if head and head[1] in numbers:
                parts[i] = re.sub(r"(?m)^> \*\*(?:Verified|Review):\*\*[^\n]*\n?", "", part)
        atomic_write(todo, "".join(parts).encode("utf-8"))


def measure(snapshot_dir, adopt=False, phase_map=None):
    """Every fault the kit's validator finds in the snapshot, as (where, message) pairs, in file order. With `adopt`,
    the snapshot's own stamps are first frozen as the kit's `adopt-stamps` freezes them (D03 T01 §9), and a refused
    adoption is a fault of its own, so a failed adoption is measured, never silent."""
    tg = load_graph()
    faults = []
    reopened = []
    if adopt:
        try:
            tg.adopt_stamps(Path(snapshot_dir), phase_map)
        except tg.Refused as exc:
            lines = str(exc).splitlines()
            causes = [line.strip() for line in lines[1:] if line.strip()]
            if not causes:
                faults.append(("adoption", f"adoption refused: {lines[0] if lines else exc}"))
            for cause in causes:  # one fault per refused section, so each cause is measured as its own class
                where, _, why = cause.partition(": ")
                faults.append((where if why else "adoption", f"adoption refused: {why or cause}"))
                if why:
                    reopened.append(where)
            if reopened:  # what adoption clears once the project reopens the stamps it cannot adopt
                reopen_in_snapshot(Path(snapshot_dir), reopened)
                try:
                    tg.adopt_stamps(Path(snapshot_dir), phase_map)
                except tg.Refused as again:
                    faults.append(("adoption", f"adoption refused again: {str(again).splitlines()[0]}"))
    try:
        tg.graph(Path(snapshot_dir), faults)
    except Exception as exc:  # a crash is a refusal class of its own, never a silent pass
        faults.append(("validator", f"validator crashed: {type(exc).__name__}: {exc}"))
    return faults, reopened


def run(source, config, out, after_copy=None, adopt=False, phase_map=None):
    """The whole dry run into out (missing or empty). Returns (manifest, classes)."""
    out = Path(out)
    if out.exists() and any(out.iterdir()):
        raise DryRunError(f"--out must be a missing or empty folder: {out}")
    if not isinstance(config, dict):
        raise DryRunError("the configuration must be a JSON object (the plan.json to measure under)")
    receipts_of(config, source)  # a configuration the kit refuses is refused before anything is written
    out.mkdir(parents=True, exist_ok=True)
    manifest = snapshot(source, out / "snapshot", config, after_copy=after_copy)
    sdk = subprocess.run(["git", "--no-optional-locks", "-C", str(SDK), "rev-parse", "HEAD"],
                         capture_output=True, text=True, timeout=60)
    sdk_dirty = subprocess.run(["git", "--no-optional-locks", "-C", str(SDK), "status", "--porcelain", "--",
                                "scripts/lib"], capture_output=True, text=True, timeout=60)
    manifest["sdk_commit"] = sdk.stdout.strip() or None
    manifest["sdk_validator_dirty"] = bool(sdk_dirty.stdout.strip())
    faults, reopened = measure(out / "snapshot", adopt=adopt, phase_map=phase_map)
    manifest["adopted"] = adopt
    manifest["reopened_for_adoption"] = reopened  # stamps it could not adopt, taken off in the snapshot alone
    found = classes(faults)
    atomic_write(out / "manifest.json", (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    atomic_write(out / "classes.json", (json.dumps({"classes": found, "faults": [list(f) for f in faults]},
                                                   indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    return manifest, found


def main(argv=None):
    parser = argparse.ArgumentParser(description="Measure what stops a project adopting the todo kit's graph.")
    parser.add_argument("source", help="the project repository (read only)")
    parser.add_argument("--config", required=True, help="the todo/plan.json to measure the project under")
    parser.add_argument("--out", required=True, help="a missing or empty folder for the snapshot and the results")
    parser.add_argument("--adopt-stamps", action="store_true",
                        help="freeze the snapshot's own stamps first, as the kit's adopt-stamps does")
    parser.add_argument("--phase-map", help="with --adopt-stamps: the phase map adopt-stamps takes")
    args = parser.parse_args(argv)
    try:
        config = json.loads(Path(args.config).read_text(encoding="utf-8"))
        phase_map = json.loads(Path(args.phase_map).read_text(encoding="utf-8")) if args.phase_map else None
        manifest, found = run(args.source, config, args.out, adopt=args.adopt_stamps, phase_map=phase_map)
    except (DryRunError, OSError, ValueError) as exc:
        print(f"adoption-dry-run: {exc}", file=sys.stderr)
        return 2
    print(f"project {manifest['project_commit']} measured by SDK {manifest['sdk_commit']}"
          f" ({len(manifest['files'])} files copied in {manifest['copies']} copies,"
          f" {len(manifest['moved'])} moved)")
    for entry in found:
        ex = entry["example"]
        print(f"{entry['sections']:>6} places {entry['faults']:>6} faults  {entry['class']}")
        print(f"{'':>28}e.g. {ex['where']}: {ex['message'][:200]}")
    print(f"{len(found)} refusal classes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
