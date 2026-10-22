"""Tests for the todo kit's scripts/lib/todo_graph.py and scripts/todo-graph.py: the graph refuses malformed work and stamps only real evidence."""
import importlib.util
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import types
import unittest

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "kits/todo/templates/scripts/lib"))
import todo_graph as tg  # noqa: E402

ADJACENCY = ("**Adjacency:** list=not-applicable (fixture); document=not-applicable (fixture); "
             "settings=not-applicable (fixture); reporting=not-applicable (fixture); "
             "notifications=not-applicable (fixture); permissions=not-applicable (fixture); "
             "audit=not-applicable (fixture); exchange=not-applicable (fixture); "
             "reverse=not-applicable (fixture)")


def section(n, title, phase, needs, extra=""):
    return (f"## {n}. {title}\n\n**Phase:** {phase}\n**Needs:** {needs}\n**Surface:** no\n\n**Build order:**\n\n"
            f"1. Do it. Done when: it shows.\n\n- [ ] Work.\n- [ ] Commit: `x: {title.lower()}`\n\n"
            f"**Test checkpoint:** `true` exits 0.{extra}\n")


def todo_file(rows, *, ident="alpha", domain="00-workspace", status="active", depends_on=None,
              table_override=None, inputs="- i"):
    """rows: (number, title, phase, needs, depends) tuples."""
    front = ["schema_version: 1", f"id: {ident}", f"domain: {domain}", f"status: {status}",
             'title: "TODO-01 -- A"']
    if depends_on is not None:
        front.append("depends_on: " + json.dumps(depends_on))
    table = table_override or "\n".join(
        f"| {i} | §{n} | {t} | {dep} | [ ] |" for i, (n, t, _, _, dep) in enumerate(rows, 1))
    bodies = "\n".join(section(n, t, ph, nd) for n, t, ph, nd, _ in rows)
    return ("---\n" + "\n".join(front) + "\n---\n\n# TODO-01 -- A\n\n> **Goal:** g.\n\n"
            "> **Current state:** c.\n\n## Inputs\n\n" + inputs + "\n\n## Outcome\n\n- o\n\n"
            + ADJACENCY + "\n\n"
            "## Implementation Order\n\n| Order | Section | Deliverable | Depends On | Status |\n"
            "| ----- | ------- | ----------- | ---------- | ------ |\n"
            + table + "\n\n" + bodies + "\n## Verification\n\n- v\n")


class Tree(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.tmp.name)
        (self.root / "todo/00-workspace").mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, text, name="TODO-01-a.md", domain="00-workspace", index=True):
        d = self.root / "todo" / domain
        d.mkdir(parents=True, exist_ok=True)
        (d / name).write_text(text, encoding="utf-8")
        if index:
            self.index(name, domain)

    def index(self, name, domain="00-workspace"):
        domain_index = self.root / "todo" / domain / "INDEX.md"
        existing = domain_index.read_text(encoding="utf-8") if domain_index.exists() else "# Index\n"
        if name not in existing:
            domain_index.write_text(existing + f"- {name}\n", encoding="utf-8")
        root_index = self.root / "todo/TODO-00-INDEX.md"
        root_existing = root_index.read_text(encoding="utf-8") if root_index.exists() else "# Index\n"
        entry = f"{domain}/{name}"
        if entry not in root_existing:
            root_index.write_text(root_existing + f"- {entry}\n", encoding="utf-8")

    def refuses(self, fragment):
        with self.assertRaises(tg.Refused) as ctx:
            tg.graph(self.root)
        self.assertIn(fragment, str(ctx.exception))


class Graph(Tree):
    def test_valid_tree_orders_by_phase_and_dependency(self):
        self.write(todo_file([(1, "Late", 1, "none", "--"), (2, "Early", 0, "none", "--"),
                              (3, "After early", 0, "windows-host", "§2")]))
        rows = tg.graph(self.root)
        self.assertEqual([r.ref for r in tg.ordered(rows)],
                         ["D00 T01 §2", "D00 T01 §3", "D00 T01 §1"])
        self.assertEqual(tg.disposition(rows["D00 T01 §2"], rows), 0)
        self.assertEqual(tg.disposition(rows["D00 T01 §3"], rows), 4)

    def test_table_order_decides_among_ready_sections(self):
        table = "| 1 | §2 | B | -- | [ ] |\n| 2 | §1 | A | -- | [ ] |"
        self.write(todo_file([(1, "A", 0, "none", "--"), (2, "B", 0, "none", "--")],
                             table_override=table))
        self.assertEqual([r.ref for r in tg.ordered(tg.graph(self.root))],
                         ["D00 T01 §2", "D00 T01 §1"])

    def test_empty_tree_refuses(self):
        self.refuses("missing or empty")

    def test_malformed_row_is_not_empty_work(self):
        self.write(todo_file([(1, "A", 0, "none", "--")], table_override="| 1 | §1 | A | -- | [?] |"))
        self.refuses("malformed implementation row")

    def test_row_without_body_refuses(self):
        text = todo_file([(1, "A", 0, "none", "--")]).replace(
            "| 1 | §1 | A | -- | [ ] |", "| 1 | §1 | A | -- | [ ] |\n| 2 | §2 | B | -- | [ ] |")
        self.write(text)
        self.refuses("row/body mismatch")

    def test_cycle_refuses(self):
        self.write(todo_file([(1, "A", 0, "none", "§2"), (2, "B", 0, "none", "§1")]))
        self.refuses("dependency cycle")

    def test_prerequisite_in_a_later_phase_refuses(self):
        self.write(todo_file([(1, "A", 0, "none", "§2"), (2, "B", 1, "none", "--")]))
        self.refuses("prerequisite in later phase")

    def test_unknown_need_refuses(self):
        self.write(todo_file([(1, "A", 0, "novamira", "--")]))
        self.refuses("unknown/duplicate Needs")

    def test_commit_must_be_the_last_item(self):
        self.write(todo_file([(1, "A", 0, "none", "--")]).replace(
            "- [ ] Commit: `x: a`", "- [ ] Commit: `x: a`\n- [ ] After."))
        self.refuses("Commit last")

    def test_malformed_checklist_item_refuses(self):
        for bad in ("- [?] Work.", "- [] Work.", "- [X] Work.", "- Work without checkbox."):
            self.write(todo_file([(1, "A", 0, "none", "--")]).replace("- [ ] Work.", bad))
            self.refuses("malformed checklist item")

    def test_empty_build_order_refuses(self):
        text = todo_file([(1, "A", 0, "none", "--")]).replace(
            "1. Do it. Done when: it shows.\n\n- [ ] Work.",
            "- [ ] Work. Done when: it shows.")
        self.write(text)
        self.refuses("executable Build order required")
        missing_second = todo_file([(1, "A", 0, "none", "--")]).replace(
            "1. Do it. Done when: it shows.",
            "1. Do it. Done when: it shows.\n2. Second step without acceptance criterion.")
        self.write(missing_second)
        self.refuses("executable Build order required")

    def test_empty_field_does_not_borrow_next_line(self):
        text = todo_file([(1, "A", 0, "none", "--")]).replace(
            "**Test checkpoint:** `true` exits 0.",
            "**Test checkpoint:**\n> **Deferred:** `later` -> XREF: D00 T01 §1")
        self.write(text)
        self.refuses("missing Test checkpoint field")

    def test_missing_todo_heading_refuses(self):
        text = todo_file([(1, "A", 0, "none", "--")]).replace("# TODO-01 -- A\n\n", "")
        self.write(text)
        self.refuses("missing TODO heading")

    def test_section_zero_refuses(self):
        self.write(todo_file([(0, "Zero", 0, "none", "--")]))
        self.refuses("malformed implementation row")

    def test_waiting_needs_are_not_ready(self):
        self.write(todo_file([(1, "A", 0, "owner-decision, windows-host", "--")]))
        rows = tg.graph(self.root)
        self.assertEqual(tg.disposition(rows["D00 T01 §1"], rows), 4)

    def test_operator_needs_are_not_ready(self):
        self.write(todo_file([(1, "A", 99, "operator", "--")]))
        rows = tg.graph(self.root)
        self.assertEqual(tg.disposition(rows["D00 T01 §1"], rows), 4)

    def test_draft_file_is_not_ready(self):
        self.write(todo_file([(1, "A", 0, "none", "--")], status="draft"))
        rows = tg.graph(self.root)
        self.assertEqual(tg.disposition(rows["D00 T01 §1"], rows), 4)

    def test_file_dependency_reaches_every_section(self):
        self.write(todo_file([(1, "A", 0, "none", "--")], ident="first"))
        self.write(todo_file([(1, "B", 1, "none", "--"), (2, "C", 1, "none", "--")],
                             ident="second", depends_on=["first"]), name="TODO-02-b.md")
        rows = tg.graph(self.root)
        self.assertEqual(rows["D00 T02 §2"].depends, ["D00 T01 §1"])

    def test_checked_row_without_stamp_refuses(self):
        self.write(todo_file([(1, "A", 0, "none", "--")]).replace("| [ ] |", "| [x] |"))
        self.refuses("checkbox/stamp/receipt mismatch")

    def test_missing_from_index_refuses(self):
        self.write(todo_file([(1, "A", 0, "none", "--")]), index=False)
        (self.root / "todo/TODO-00-INDEX.md").write_text("# Index\n", encoding="utf-8")
        (self.root / "todo/00-workspace/INDEX.md").write_text("# Index\n", encoding="utf-8")
        self.refuses("missing from domain index")

    def test_root_index_requires_domain_qualified_entry(self):
        self.write(todo_file([(1, "A", 0, "none", "--")], ident="first"))
        self.write(todo_file([(1, "B", 1, "none", "--")], ident="second", domain="01-engine"),
                   name="TODO-01-a.md", domain="01-engine", index=False)
        (self.root / "todo/01-engine/INDEX.md").write_text("# Index\n- TODO-01-a.md\n", encoding="utf-8")
        self.refuses("missing from root index: 01-engine/TODO-01-a.md")

    def test_adjacency_missing_key_refuses(self):
        text = todo_file([(1, "A", 0, "none", "--")]).replace(
            "reverse=not-applicable (fixture)", "reverse=not-applicable")
        self.write(text)
        self.refuses("adjacency entry malformed")

    def test_adjacency_blanket_form_is_valid(self):
        text = todo_file([(1, "A", 0, "none", "--")]).replace(
            ADJACENCY, "**Adjacency:** all=not-applicable (fixture with no record of its own)")
        self.write(text)
        self.assertEqual(len(tg.graph(self.root)), 1)

    def test_adjacency_blanket_reason_may_contain_semicolons(self):
        text = todo_file([(1, "A", 0, "none", "--")]).replace(
            ADJACENCY, "**Adjacency:** all=not-applicable (tooling over files; its records are the "
                       "files themselves, owned by their own sections)")
        self.write(text)
        self.assertEqual(len(tg.graph(self.root)), 1)

    def test_one_sided_xref_refuses(self):
        self.write(todo_file([(1, "A", 0, "none", "--")], ident="first"))
        self.write(todo_file([(1, "B", 0, "none", "--")], ident="second",
                             inputs="- -> XREF: D00 T01 §1 -- consumes it"), name="TODO-02-b.md")
        self.refuses("one-sided XREF")

    def test_reciprocal_xref_is_valid(self):
        self.write(todo_file([(1, "A", 0, "none", "--")], ident="first",
                             inputs="- -> XREF: D00 T02 §1 -- feeds it"))
        self.write(todo_file([(1, "B", 0, "none", "--")], ident="second",
                             inputs="- -> XREF: D00 T01 §1 -- consumes it"), name="TODO-02-b.md")
        self.assertEqual(len(tg.graph(self.root)), 2)

    def test_surface_yes_without_fidelity_refuses(self):
        text = todo_file([(1, "A", 0, "none", "--")]).replace("**Surface:** no", "**Surface:** yes")
        self.write(text)
        self.refuses("missing Fidelity field")

    def test_freeze_check_without_frozen_refuses(self):
        text = todo_file([(1, "A", 0, "none", "--")]).replace(
            "**Test checkpoint:**", "**Freeze check:** fixtures hold.\n\n**Test checkpoint:**")
        self.write(text)
        self.refuses("Freeze check must match frozen")

    def test_deferral_without_owner_refuses(self):
        text = todo_file([(1, "A", 0, "none", "--")]).replace(
            "**Test checkpoint:**", "> **Deferred:** later, somehow\n\n**Test checkpoint:**")
        self.write(text)
        self.refuses("without a resolving owner")

    def test_max_sections_per_file_refuses(self):
        rows = [(n, f"S{n}", 0, "none", "--") for n in range(1, 57)]
        self.write(todo_file(rows))
        self.refuses("over 55 sections")

    def test_max_items_per_section_refuses(self):
        many = "\n".join(f"- [ ] Item {i}." for i in range(1, 31))
        text = todo_file([(1, "A", 0, "none", "--")]).replace("- [ ] Work.", many)
        self.write(text)
        self.refuses("2-30 items")

    def test_overlong_deliverable_or_title_refuses(self):
        long_title = "A" * (tg.MAX_DELIVERABLE_LEN + 1)
        self.write(todo_file([(1, long_title, 0, "none", "--")]))
        self.refuses(f"deliverable/title over {tg.MAX_DELIVERABLE_LEN} chars")

    def test_title_that_wraps_the_generated_plan_table_refuses_naming_the_section(self):
        # Within the 88-character cell limit, but the plan pads every row to it: 60 characters make 103-character rows.
        self.write(todo_file([(1, "A", 0, "none", "--"), (2, "B" * 60, 0, "none", "--")]))
        with self.assertRaises(tg.Refused) as ctx:
            tg.projections(self.root, sync=True)
        self.assertIn("plan table for phase 0 wraps raw md", str(ctx.exception))
        self.assertIn("D00 T01 §2", str(ctx.exception))
        self.assertFalse((self.root / tg.PLAN).exists(), "a wrapping plan was written")
        self.write(todo_file([(1, "A", 0, "none", "--"), (2, "B" * 57, 0, "none", "--")]))
        tg.projections(self.root, sync=True)

    def test_superseded_without_successor_refuses(self):
        self.write(todo_file([(1, "A", 0, "none", "--")], status="superseded"))
        self.refuses("superseded TODO must name its successor")

    def test_projection_check_detects_drift(self):
        self.write(todo_file([(1, "A", 0, "none", "--")]))
        tg.projections(self.root, sync=True)
        tg.projections(self.root)
        path = self.root / "todo/00-workspace/TODO-01-a.md"
        path.write_text(path.read_text(encoding="utf-8").replace("**Phase:** 0", "**Phase:** 2"),
                        encoding="utf-8")
        with self.assertRaises(tg.Refused):
            tg.projections(self.root)

    def test_plan_names_come_from_plan_json(self):
        self.write(todo_file([(1, "A", 0, "none", "--"), (2, "B", 99, "none", "--")]))
        plan = tg.projection(self.root)
        self.assertIn("# Implementation plan\n", plan)
        self.assertIn("### Phase 0\n", plan)
        self.assertIn("### Phase 99: Manual, operator only\n", plan)
        self.assertNotIn("Recto", plan)
        self.assertNotIn("acceptance bar", plan)
        (self.root / "todo/plan.json").write_text(json.dumps({
            "title": "Site plan", "acceptance": "`design/SPEC.md`.", "phases": {"0": "Tooling"}}),
            encoding="utf-8")
        plan = tg.projection(self.root)
        self.assertIn("# Site plan\n", plan)
        self.assertIn("The acceptance bar is `design/SPEC.md`.", plan)
        self.assertIn("### Phase 0: Tooling\n", plan)

    def test_malformed_plan_json_refuses(self):
        self.write(todo_file([(1, "A", 0, "none", "--")]))
        config = self.root / "todo/plan.json"
        for bad, fragment in (({"phases": {"8": "x"}}, "unknown phase"),
                              ({"title": "t", "owner": "x"}, "may only hold"),
                              ({"phases": {"0": ""}}, "needs a name"),
                              ({"acceptance": ""}, "acceptance must be"),
                              ("{", "unreadable")):
            config.write_text(bad if isinstance(bad, str) else json.dumps(bad), encoding="utf-8")
            self.refuses(fragment)

    def test_resolve_accepts_windows_and_posix_paths_and_plan_rows(self):
        self.write(todo_file([(1, "A", 0, "none", "--")]))
        rows = tg.graph(self.root)
        for query in (
            "D00 T01 §1",
            "| [ ] | D00 T01 §1 | A | none | 2 |",
            "todo/00-workspace/TODO-01-a.md §1",
            r"R:\GitHub\RectoPDF\todo\00-workspace\TODO-01-a.md §1",
        ):
            self.assertEqual(tg.extract_ref(query, rows), ("D00 T01 §1", 0))
        self.assertEqual(tg.extract_ref(r"R:\GitHub\RectoPDF\todo\00-workspace\TODO-01-a.md §9", rows),
                         ("D00 T01 §9", 1))
        self.assertEqual(tg.extract_ref("no reference here", rows), (None, 2))


class Stamp(Tree):
    def setUp(self):
        super().setUp()
        self.write(todo_file([(1, "A", 0, "none", "--"), (2, "B", 0, "owner-decision", "--")]))
        report_path = self.root / "docs/reviews/00-workspace/D00-T01-s1.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text("# Review findings\n", encoding="utf-8")
        for args in (["init", "-q"], ["config", "user.email", "t@example.com"],
                     ["config", "user.name", "T"], ["add", "-A"], ["commit", "-qm", "x"]):
            subprocess.run(["git", "-C", str(self.root), *args], check=True)
        self.sha = subprocess.run(["git", "-C", str(self.root), "rev-parse", "HEAD"],
                                  capture_output=True, text=True).stdout.strip()
        self.reviews = [{"round": 1, "report": "docs/reviews/00-workspace/D00-T01-s1.md",
                         "verdict": "clean"}]

    def tick_work(self):
        path = self.root / "todo/00-workspace/TODO-01-a.md"
        path.write_text(path.read_text(encoding="utf-8").replace("- [ ] Work.", "- [x] Work.", 1),
                        encoding="utf-8")

    def test_stamp_writes_receipt_and_validates(self):
        self.tick_work()
        receipt = tg.stamp(self.root, "D00 T01 §1", self.sha, self.reviews, ["true -> ok"], "2026-10-13")
        rows = tg.graph(self.root)
        self.assertTrue(rows["D00 T01 §1"].done)
        self.assertEqual(json.loads((self.root / receipt).read_text(encoding="utf-8"))
                         ["implementation_sha"], self.sha)

    def test_stamp_accepts_the_current_round_cap(self):
        self.tick_work()
        reviews = [dict(self.reviews[0], verdict=f"stopped-at-{tg.REVIEW_ROUND_CAP}")]
        tg.stamp(self.root, "D00 T01 §1", self.sha, reviews, ["true -> ok"], "2026-10-22")
        self.assertTrue(tg.graph(self.root)["D00 T01 §1"].done)
        self.assertEqual(tg.REVIEW_ROUND_CAP, 22)

    def test_stamp_refuses_an_earlier_cap_on_a_new_receipt(self):
        self.tick_work()
        for verdict, message in (("stopped-at-3", "a new receipt's verdicts"),
                                 ("stopped-low-severity", "a new receipt's verdicts"),
                                 ("approve", "no valid review rounds")):
            with self.subTest(verdict=verdict):
                with self.assertRaisesRegex(tg.Refused, message):
                    tg.stamp(self.root, "D00 T01 §1", self.sha, [dict(self.reviews[0], verdict=verdict)],
                             ["true -> ok"], "2026-10-22")
        self.assertFalse((self.root / "docs/reviews/d00-t01-s1.json").exists())

    def test_stamp_refuses_malformed_reviews_without_crashing(self):
        self.tick_work()
        for reviews in (None, [dict(self.reviews[0], verdict=[])], [dict(self.reviews[0], verdict={})], ["x"]):
            with self.subTest(reviews=reviews):
                with self.assertRaises(tg.Refused):
                    tg.stamp(self.root, "D00 T01 §1", self.sha, reviews, ["true -> ok"], "2026-10-22")

    def test_receipts_written_under_earlier_caps_still_validate(self):
        # Receipts are never rewritten: every verdict an installed copy already recorded stays valid after a cap change.
        for verdict in ("clean", "fixed", "stopped-at-3", "stopped-at-8", "stopped-at-13", "stopped-at-22",
                        "stopped-low-severity"):
            with self.subTest(verdict=verdict):
                data = {"ref": "D00 T01 §1", "implementation_sha": self.sha, "date": "2026-10-13",
                        "reviews": [dict(self.reviews[0], verdict=verdict)], "checks": ["true -> ok"]}
                tg.receipt_data_ok(data, "D00 T01 §1", self.sha, root=self.root)
        data["reviews"] = [dict(self.reviews[0], verdict="stopped-at-4")]
        with self.assertRaisesRegex(tg.Refused, "no valid review rounds"):
            tg.receipt_data_ok(data, "D00 T01 §1", self.sha, root=self.root)


class QueryPlan(Tree):
    """`query plan`: the plan's names and every section's status, for readers that must not parse todo/ (plan R34)."""

    def setUp(self):
        super().setUp()
        self.write(todo_file([(1, "A", 0, "none", "--"), (2, "B", 0, "owner-decision", "--"),
                              (3, "C", 0, "none", "§1")]))
        self.write(todo_file([(1, "D", 1, "none", "--")], ident="beta", domain="01-later", status="draft"),
                   domain="01-later")
        (self.root / "todo/plan.json").write_text(json.dumps({
            "title": "Site plan", "acceptance": "`design/SPEC.md`.", "phases": {"0": "Tooling"}}), encoding="utf-8")
        report = self.root / "docs/reviews/00-workspace/D00-T01-s1.md"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text("# Review findings\n", encoding="utf-8")
        path = self.root / "todo/00-workspace/TODO-01-a.md"
        path.write_text(path.read_text(encoding="utf-8").replace("- [ ] Work.", "- [x] Work.", 1), encoding="utf-8")
        for args in (["init", "-q"], ["config", "user.email", "t@example.com"], ["config", "user.name", "T"],
                     ["config", "commit.gpgsign", "false"], ["add", "-A"], ["commit", "-qm", "x"]):
            subprocess.run(["git", "-C", str(self.root), *args], check=True)
        sha = subprocess.run(["git", "-C", str(self.root), "rev-parse", "HEAD"],
                             capture_output=True, text=True).stdout.strip()
        tg.stamp(self.root, "D00 T01 §1", sha, [{"round": 1, "report": str(report.relative_to(self.root)).replace("\\", "/"),
                                                  "verdict": "clean"}], ["true -> ok"], "2026-10-20")
        shutil.copytree(REPO / "kits/todo/templates/scripts", self.root / "scripts",
                        ignore=shutil.ignore_patterns("__pycache__"))

    def query(self):
        return subprocess.run([sys.executable, str(self.root / "scripts/todo-graph.py"), "query", "plan"],
                              capture_output=True, text=True, encoding="utf-8")

    def test_query_plan_reports_config_and_every_section(self):
        result = self.query()
        self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads(result.stdout)
        self.assertEqual((plan["title"], plan["acceptance"]), ("Site plan", "`design/SPEC.md`."))
        self.assertEqual(plan["phases"], {"0": "Tooling", "99": "Manual, operator only"})
        self.assertEqual(plan["sections"], [
            {"ref": "D00 T01 §1", "path": "todo/00-workspace/TODO-01-a.md", "title": "A", "phase": 0,
             "status": "verified", "depends": []},
            {"ref": "D00 T01 §2", "path": "todo/00-workspace/TODO-01-a.md", "title": "B", "phase": 0,
             "status": "blocked", "depends": []},
            {"ref": "D00 T01 §3", "path": "todo/00-workspace/TODO-01-a.md", "title": "C", "phase": 0,
             "status": "ready", "depends": ["D00 T01 §1"]},
            {"ref": "D01 T01 §1", "path": "todo/01-later/TODO-01-a.md", "title": "D", "phase": 1,
             "status": "deferred", "depends": []},
        ])

    def test_plan_status_edge_cases(self):
        # A verified section reads verified even in a file that is no longer active; a section waiting on another
        # file's unfinished section, or on an unfinished prerequisite in its own file, reads blocked.
        spec = importlib.util.spec_from_file_location("todo_graph_cli", REPO / "kits/todo/templates/scripts/todo-graph.py")
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)

        def row(ref, done=False, status="active", needs=(), depends=()):
            return types.SimpleNamespace(ref=ref, done=done, status=status, needs=list(needs), depends=list(depends))

        rows = {r.ref: r for r in (row("D01 T01 §1", done=True, status="done"), row("D02 T01 §1", status="draft"),
                                   row("D00 T01 §1", depends=["D02 T01 §1"]), row("D00 T01 §2"),
                                   row("D00 T01 §3", depends=["D00 T01 §2"]))}
        self.assertEqual({ref: cli.plan_status(r, rows) for ref, r in rows.items()},
                         {"D01 T01 §1": "verified", "D02 T01 §1": "deferred", "D00 T01 §1": "blocked",
                          "D00 T01 §2": "ready", "D00 T01 §3": "blocked"})

    def test_query_plan_refuses_an_unreadable_plan_json(self):
        (self.root / "todo/plan.json").write_text("{", encoding="utf-8")
        result = self.query()
        self.assertEqual(result.returncode, 2)
        self.assertIn("TODO refused: unreadable todo/plan.json", result.stderr)
        self.assertEqual(result.stdout, "")


class CliOutput(Tree):
    """The CLI's output is a contract other programs parse (the editor extension, process-plan): always UTF-8."""

    def test_query_output_is_utf8_whatever_the_console_code_page(self):
        self.write(todo_file([(1, "Only", 0, "none", "--")]))
        shutil.copytree(REPO / "kits/todo/templates/scripts", self.root / "scripts",
                        ignore=shutil.ignore_patterns("__pycache__"))
        # A Windows console's default: stdout in the ANSI code page, where the section sign is byte 0xa7.
        env = {**os.environ, "PYTHONIOENCODING": "cp1252", "PYTHONUTF8": "0"}
        result = subprocess.run([sys.executable, str(self.root / "scripts/todo-graph.py"), "query", "ready"],
                                capture_output=True, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([r["ref"] for r in json.loads(result.stdout.decode("utf-8"))], ["D00 T01 §1"])

if __name__ == "__main__":
    unittest.main()
