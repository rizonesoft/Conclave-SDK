"""Tests for scripts/adoption-dry-run.py, the SDK's measure of what stops a project adopting the kit's graph."""
import hashlib
import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from test_todo_graph import todo_file  # noqa: E402  the graph tests' fixture writer

SPEC = importlib.util.spec_from_file_location("adoption_dry_run", REPO / "scripts/adoption-dry-run.py")
assert SPEC is not None and SPEC.loader is not None
dry = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(dry)


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True).stdout.strip()


def tree_bytes(root):
    """{relative path: digest} of every file under root, .git included."""
    out = {}
    for top, _, names in os.walk(root):
        for name in names:
            path = pathlib.Path(top) / name
            out[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


class DryRun(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = pathlib.Path(self.tmp.name)
        self.source, self.out = base / "project", base / "scratch" / "run"
        self.source.mkdir()
        git(self.source, "init", "-q")
        git(self.source, "config", "user.email", "t@example.com")
        git(self.source, "config", "user.name", "T")

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, rel, text):
        path = self.source / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def tree(self, files):
        """files: {(domain, name): todo text}; writes them and both indexes."""
        root_index = ["# Index"]
        for (domain, name), text in files.items():
            self.write(f"todo/{domain}/{name}", text)
            self.write(f"todo/{domain}/INDEX.md", f"# Index\n- {name}\n")
            root_index.append(f"- {domain}/{name}")
        self.write("todo/TODO-00-INDEX.md", "\n".join(root_index) + "\n")

    def commit(self):
        git(self.source, "add", "-A")
        git(self.source, "commit", "-qm", "x")
        return git(self.source, "rev-parse", "HEAD")

    def classes_of(self, found):
        return [entry["class"] for entry in found]

    def test_two_planted_faults_are_two_classes_and_nothing_outside_scratch_is_written(self):
        self.tree({("00-workspace", "TODO-01-a.md"): todo_file([(1, "A", 12, "none", "--")]),
                   ("01-engine", "TODO-01-b.md"): todo_file([(1, "B", 0, "Idle machine", "--")], ident="beta",
                                                            domain="01-engine")})
        self.commit()
        before = tree_bytes(self.source)
        manifest, found = dry.run(self.source, {"title": "P"}, self.out)
        names = self.classes_of(found)
        self.assertEqual(len(found), 2, names)
        self.assertTrue(any("Phase" in n for n in names), names)
        self.assertTrue(any("Needs" in n for n in names), names)
        for entry in found:
            self.assertEqual(entry["sections"], 1)
            self.assertNotRegex(entry["class"], r"§\d|D\d\d T\d\d|todo/")
        self.assertEqual(tree_bytes(self.source), before)
        self.assertEqual(sorted(p.name for p in self.out.iterdir()), ["classes.json", "manifest.json", "snapshot"])
        saved = json.loads((self.out / "classes.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["classes"], found)
        self.assertEqual(manifest["plan_json"], {"title": "P"})
        self.assertEqual(json.loads((self.out / "snapshot/todo/plan.json").read_text(encoding="utf-8")),
                         {"title": "P"})
        # The faults were the snapshot's: the validator ran on the snapshot as its root, not on its own home.
        tg, roots = dry.load_graph(), []
        real = tg.graph
        with mock.patch.object(tg, "graph", lambda root, faults=None: roots.append(root) or real(root, faults)):
            dry.measure(self.out / "snapshot")
        self.assertEqual(roots, [self.out / "snapshot"])
        self.assertNotEqual(pathlib.Path(roots[0]).resolve(), tg.ROOT)

    def test_every_git_call_against_the_source_takes_no_optional_locks(self):
        self.tree({("00-workspace", "TODO-01-a.md"): todo_file([(1, "A", 0, "none", "--")])})
        self.commit()
        real, calls = subprocess.run, []

        def spy(argv, *args, **kwargs):
            calls.append(list(argv))
            return real(argv, *args, **kwargs)

        with mock.patch.object(dry.subprocess, "run", spy):
            dry.run(self.source, {"title": "P"}, self.out)
        source = str(self.source.resolve())
        against = [c for c in calls if c and c[0] == "git" and source in c]
        self.assertGreaterEqual(len(against), 2, calls)  # rev-parse and clone at least
        for call in against:
            self.assertEqual(call[1], "--no-optional-locks", call)

    def test_a_dirty_source_file_is_measured_and_left_as_it_was(self):
        self.tree({("00-workspace", "TODO-01-a.md"): todo_file([(1, "A", 0, "none", "--")])})
        self.commit()
        dirty = todo_file([(1, "A", 0, "none", "--"), (2, "Dirty", 0, "none", "--")])
        self.write("todo/00-workspace/TODO-01-a.md", dirty)
        before = (self.source / "todo/00-workspace/TODO-01-a.md").read_bytes()
        manifest, found = dry.run(self.source, {"title": "P"}, self.out)
        self.assertEqual(found, [])
        self.assertEqual(manifest["files"]["todo/00-workspace/TODO-01-a.md"], hashlib.sha256(before).hexdigest())
        self.assertEqual((self.source / "todo/00-workspace/TODO-01-a.md").read_bytes(), before)
        self.assertEqual((self.out / "snapshot/todo/00-workspace/TODO-01-a.md").read_bytes(), before)
        self.assertIn("todo/00-workspace/TODO-01-a.md", git(self.source, "status", "--porcelain"))

    def test_a_source_that_moves_during_the_copy_is_copied_again(self):
        self.tree({("00-workspace", "TODO-01-a.md"): todo_file([(1, "A", 0, "none", "--")])})
        self.commit()
        later = todo_file([(1, "A", 12, "none", "--")])  # a campaign's mid-copy edit that plants a real fault

        def campaign(attempt):
            if attempt == 1:
                self.write("todo/00-workspace/TODO-01-a.md", later)

        manifest, found = dry.run(self.source, {"title": "P"}, self.out, after_copy=campaign)
        self.assertEqual(manifest["copies"], 2)
        self.assertEqual(manifest["moved"], ["todo/00-workspace/TODO-01-a.md"])
        self.assertEqual((self.out / "snapshot/todo/00-workspace/TODO-01-a.md").read_text(encoding="utf-8"), later)
        self.assertTrue(any("Phase" in n for n in self.classes_of(found)))

    def test_a_source_that_never_settles_is_refused_not_measured(self):
        self.tree({("00-workspace", "TODO-01-a.md"): todo_file([(1, "A", 0, "none", "--")])})
        self.commit()

        def campaign(attempt):
            self.write("todo/00-workspace/TODO-01-a.md", todo_file([(1, f"A{attempt}", 0, "none", "--")]))

        with self.assertRaises(dry.DryRunError):
            dry.run(self.source, {"title": "P"}, self.out, after_copy=campaign)
        self.assertFalse((self.out / "classes.json").exists())

    def test_the_receipts_folder_the_configuration_names_is_copied(self):
        self.tree({("00-workspace", "TODO-01-a.md"): todo_file([(1, "A", 0, "none", "--")])})
        self.write(".claude/overnight/reviews/note.md", "kept\n")
        self.commit()
        self.write(".claude/overnight/reviews/uncommitted.md", "new\n")
        manifest, _ = dry.run(self.source, {"title": "P", "layout": {"receipts": ".claude/overnight/reviews"}},
                              self.out)
        self.assertIn(".claude/overnight/reviews/uncommitted.md", manifest["files"])
        self.assertTrue((self.out / "snapshot/.claude/overnight/reviews/uncommitted.md").is_file())

    def test_a_broken_receipt_is_reported(self):
        self.tree({("00-workspace", "TODO-01-a.md"): todo_file([(1, "A", 0, "none", "--")])})
        sha = self.commit()
        path = self.source / "todo/00-workspace/TODO-01-a.md"
        text = path.read_text(encoding="utf-8").replace("| [ ] |", "| [x] |").replace(
            "\n## Verification", f"\n> **Verified:** 2026-11-13 | §1 | {sha}\n"
                                 "> **Review:** `docs/reviews/d00-t01-s1.json`\n\n## Verification")
        path.write_text(text, encoding="utf-8")
        self.commit()
        _, found = dry.run(self.source, {"title": "P"}, self.out)
        self.assertTrue(found, "a stamp with no receipt must be a fault")
        self.assertTrue(any("receipt" in e["example"]["message"].lower() for e in found), found)

    @unittest.skipUnless(os.environ.get("CONCLAVE_FULL_TESTS"), "slow: set CONCLAVE_FULL_TESTS=1 for the full suite")
    def test_the_sdk_snapshot_with_its_stamped_sections_reports_no_fault(self):
        config = json.loads((REPO / "todo/plan.json").read_text(encoding="utf-8"))
        manifest, found = dry.run(REPO, config, self.out)
        self.assertEqual(found, [], found[:3])
        self.assertTrue(any(p.startswith("docs/reviews/") and p.endswith(".json") for p in manifest["files"]))
        self.assertEqual(manifest["project_commit"], git(REPO, "rev-parse", "HEAD"))

    def test_an_out_folder_that_holds_anything_is_refused(self):
        self.out.mkdir(parents=True)
        (self.out / "keep.txt").write_text("x", encoding="utf-8")
        with self.assertRaises(dry.DryRunError):
            dry.run(self.source, {"title": "P"}, self.out)
        self.assertEqual([p.name for p in self.out.iterdir()], ["keep.txt"])

    def test_refusal_classes_take_out_sections_paths_and_numbers(self):
        self.assertEqual(dry.refusal_class("invalid Phase 12: D01 T02 §3"), "invalid Phase N: <ref>")
        self.assertEqual(dry.refusal_class("missing from root index: 01-engine/TODO-01-b.md"),
                         "missing from root index: <path>")
        # Prose with a slash is not a path, and a Needs phrase is a value: RasterFold's 44 "Idle machine (timing)"
        # and 34 "ffmpeg with libjxl (benchmarks)" faults are one class.
        self.assertEqual(dry.refusal_class("unknown/duplicate Needs (Idle machine (timing)): D01 T02 §1"),
                         "unknown/duplicate Needs (<value>): <ref>")
        self.assertEqual(dry.refusal_class("unknown/duplicate Needs (Windows host (build/test)): D10 T03 §2"),
                         "unknown/duplicate Needs (<value>): <ref>")
        self.assertEqual(dry.refusal_class("docs/reviews/00-workspace/D00-T01-s11.md holds no returned review: D00 "
                                           "T01 §11"), "<path> holds no returned review: <ref>")
        self.assertEqual(dry.refusal_class("the reviewer pin at 6b5aa11efc622c3d5a8fcbfb7c3da0a40bb82750 does not "
                                           "load"), "the reviewer pin at <sha> does not load")
        self.assertEqual(dry.refusal_class("2-30 items required: ARM64 x"), "N-N items required: ARM64 x")
        # A quoted source line is the example, not the class: Impossible OS's 60 XREF faults are one class.
        for line in ("- -> XREF: `todo/x/TODO-01-a.md §2,§3` -- demand paging", "**Inputs (XREFs):** -> XREF: x §1",
                     "> **Deferred:** [H] MSI ISR drains -> XREF: D01 T17", "6. S3/S4 are REFUSED -> XREF: none"):
            self.assertEqual(dry.refusal_class(f"XREF must name exactly one well-formed section: {line}"),
                             "XREF must name exactly one well-formed section: <line>")


if __name__ == "__main__":
    unittest.main()
