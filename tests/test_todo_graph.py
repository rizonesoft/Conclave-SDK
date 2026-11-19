"""Tests for scripts/lib/todo_graph.py and scripts/todo-graph.py: the graph refuses malformed work and stamps only real evidence."""
import importlib.util
import io
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import types
import unittest
import unittest.mock
from unittest import mock

REPO = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "kits/todo/templates/scripts"
sys.path.insert(0, str(SCRIPTS / "lib"))
import todo_graph as tg  # noqa: E402

# The kits keep the dispatcher in the reviewer kit; an installed project has both side by side.
tg.DISPATCHER = REPO / "kits/reviewer/templates/scripts/review-dispatch.py"

ADJACENCY = ("**Adjacency:** list=not-applicable (fixture); document=not-applicable (fixture); "
             "settings=not-applicable (fixture); reporting=not-applicable (fixture); "
             "notifications=not-applicable (fixture); permissions=not-applicable (fixture); "
             "audit=not-applicable (fixture); exchange=not-applicable (fixture); "
             "reverse=not-applicable (fixture)")


def section(n, title, phase, needs, extra=""):
    return (f"## {n}. {title}\n\n**Phase:** {phase}\n**Needs:** {needs}\n**Surface:** no\n\n**Build order:**\n\n"
            f"1. Do it. Done when: it shows.\n\n- [ ] Work.\n- [ ] Commit: `x: {title.lower()}`\n\n"
            f"**Test checkpoint:** `true` exits 0.{extra}\n")


def envelope(n, reviewer="astra (`m` via `codex`)", overall="approve"):
    """One round as scripts/review-dispatch.py records it (without the optional Lines and Digest fields), at the
    uniform schedule the Stamp fixture pins."""
    return (f"## Round {n}: {reviewer}\n\n- Writer: claude\n- Run: 2026-10-21T00:00:00Z\n- Effort: low\n"
            f"- Lenses: adversarial\n\nReview text.\n\nOVERALL: {overall}\n\n")


# A reviewer pin whose schedule runs every round at the same effort and lens, so tests that are not about the schedule
# need not follow one; SCHEDULE_PIN is the live shape the schedule tests use.
UNIFORM_PIN = """schema_version = 1

[reviewers.astra]
cli = "codex"
model = "m"
effort = "medium"

[routes]
claude = ["astra"]

[schedule]
severity_stop_after = 3
plan = { effort = "medium", lenses = ["plan"] }
completion = { effort = "medium" }
rounds = [{ effort = "low", lenses = ["adversarial"] }]
rotation = { effort = "low", lenses = ["adversarial"] }
escalation = { effort = "low", lenses = ["adversarial"] }
"""
SCHEDULE_PIN = UNIFORM_PIN.split("[schedule]")[0] + """[schedule]
severity_stop_after = 3
plan = { effort = "medium", lenses = ["plan"] }
completion = { effort = "medium" }
rounds = [{ effort = "high", lenses = ["adversarial", "integration", "source-defect", "plan-delivery"] },
          { effort = "medium", lenses = ["adversarial"] }, { effort = "low", lenses = ["adversarial"] }]
rotation = { effort = "low", lenses = ["consistency", "quality", "design", "optimization", "record"] }
escalation = { effort = "medium", lenses = ["adversarial"] }
"""
STARTED = "> **Started:** 2026-10-23T00:00Z\n\n"


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

    def test_table_line_without_its_leading_pipe_refuses(self):
        text = todo_file([(1, "A", 0, "none", "--")]).replace(
            "| 1 | §1 | A | -- | [ ] |", "| 1 | §1 | A | -- | [ ] |\n | 2 | §999 | Orphan | -- | [ ] |")
        self.write(text)
        self.refuses("without a leading pipe")

    def test_unknown_level_two_heading_refuses(self):
        for bad in ("## Remaining work", "## Inputs ", "##\tNotes", "## Inputs", "## Verification", "## Outcome"):
            self.write(todo_file([(1, "A", 0, "none", "--"), (2, "B", 0, "none", "--")]).replace(
                "## 2. B\n", bad + "\n\n- [ ] Unfinished required work.\n\n## 2. B\n"))
            self.refuses("level-two headings must be")

    def test_deferral_marker_outside_a_blockquote_refuses(self):
        for bad in ("**Deferred:** Unimplemented required work.", ">**Resolved:** done -> XREF: §1",
                    "Note **Deferred:** later -> XREF: §2"):
            self.write(todo_file([(1, "A", 0, "none", "--"), (2, "B", 0, "none", "--")]).replace(
                "- [ ] Work.", "- [ ] Work.\n\n" + bad + "\n", 1))
            self.refuses("must open a blockquote line and say something")

    def test_checklist_item_in_another_spelling_refuses(self):
        for bad in ("1. [ ] Unfinished work.", "2) [x] Done elsewhere.", "> - [ ] Quoted work.", ">- [ ] Quoted.",
                    "  - [ ] Indented work.", "> 1. [ ] Quoted and numbered."):
            self.write(todo_file([(1, "A", 0, "none", "--"), (2, "B", 0, "none", "--")]).replace(
                "- [ ] Work.", "- [ ] Work.\n" + bad, 1))
            self.refuses("malformed checklist item")

    def test_two_deferral_markers_on_one_line_refuse(self):
        self.write(todo_file([(1, "A", 0, "none", "--"), (2, "B", 0, "none", "--")]).replace(
            "**Test checkpoint:** `true` exits 0.\n\n## 2. B",
            "**Test checkpoint:** `true` exits 0.\n> **Resolved:** old -> XREF: §2 **Deferred:** new unowned work.\n\n## 2. B"))
        self.refuses("one Deferred or Resolved marker per line")

    def test_reference_run_into_more_text_does_not_resolve(self):
        self.write(todo_file([(1, "A", 0, "none", "--")]))
        rows = tg.graph(self.root)
        for text in ("D00 T01 §1oops", "D00 T01 §1.5", "todo/00-workspace/TODO-01-a.md §1x"):
            self.assertEqual(tg.extract_ref(text, rows), (None, 2))
        for text in ("D00 T01 §1", "process D00 T01 §1.", "D00 T01 §1 (run file x)", "| 1 | D00 T01 §1 | A |"):
            self.assertEqual(tg.extract_ref(text, rows), ("D00 T01 §1", 0))

    def test_empty_deferral_marker_refuses(self):
        for bad in ("> **Deferred:**", "> **Resolved:**   "):
            self.write(todo_file([(1, "A", 0, "none", "--"), (2, "B", 0, "none", "--")]).replace(
                "**Test checkpoint:** `true` exits 0.\n\n## 2. B", "**Test checkpoint:** `true` exits 0.\n" + bad + "\n\n## 2. B"))
            self.refuses("must open a blockquote line and say something")

    def test_malformed_xref_does_not_resolve_to_another_section(self):
        for bad in ("-> XREF: D00 T999 §1", "-> XREF: §1x", "-> XREF: D00 T01 §1.5", "-> XREF:§1", "-> XREF: D00 T01 §1 -> XREF: D00 T99 §999",
                    "-> XREF: none yet"):
            self.write(todo_file([(1, "A", 0, "none", "--"), (2, "B", 0, "none", "--")], inputs="- i " + bad))
            with self.assertRaises(tg.Refused):
                tg.graph(self.root)
        self.write(todo_file([(1, "A", 0, "none", "--"), (2, "B", 0, "none", "--")],
                             inputs="- see §2 -> XREF: §2 (the second)"))
        tg.graph(self.root)

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

    def test_withdrawn_cloud_phase_98_refuses(self):
        # The phase list is closed: an unlisted phase refuses.
        self.write(todo_file([(1, "Cloud", 98, "none", "--")]))
        self.refuses("invalid Phase")

    def test_phase_outside_the_closed_list_refuses(self):
        self.write(todo_file([(1, "A", 50, "none", "--")]))
        self.refuses("invalid Phase")

    def plan(self, **keys):
        (self.root / "todo/plan.json").write_text(json.dumps(keys), encoding="utf-8")

    def test_a_project_lists_its_own_phase_numbers(self):
        # D03 T01 §1: a project's phases come from todo/plan.json's phase_list.
        self.write(todo_file([(1, "A", 12, "none", "--")]))
        self.plan(phase_list=[0, 12, 99])
        self.assertEqual([r.phase for r in tg.graph(self.root).values()], [12])
        self.plan(phase_list=[0, 3, 99])
        self.refuses("invalid Phase")

    def test_without_phase_list_the_default_is_0_to_7_and_99(self):
        self.write(todo_file([(1, "A", 7, "none", "--"), (2, "B", 99, "none", "--")]))
        self.assertEqual(sorted(r.phase for r in tg.graph(self.root).values()), [7, 99])
        self.write(todo_file([(1, "A", 8, "none", "--")]))
        self.refuses("invalid Phase")

    def test_a_phase_list_that_is_not_a_list_of_numbers_is_refused(self):
        self.write(todo_file([(1, "A", 0, "none", "--")]))
        for label, value in (("a string", "0,1"), ("an empty list", []), ("a duplicate", [0, 0]),
                             ("a negative number", [0, -1]), ("a boolean", [0, True]), ("past 999", [0, 1000]),
                             ("a number in a string", ["0"]), ("a fractional number", [0, 1.5])):
            with self.subTest(label):
                self.plan(phase_list=value)
                with self.assertRaises(tg.Refused) as ctx:
                    tg.graph(self.root)
                self.assertIn("todo/plan.json", str(ctx.exception))
                self.assertIn("phase_list", str(ctx.exception))

        self.plan(phase_list=[0, 999])
        self.assertEqual(len(tg.graph(self.root)), 1, "999, the top of the range, was refused")

    def test_phase_names_must_be_listed_phases(self):
        self.write(todo_file([(1, "A", 12, "none", "--")]))
        self.plan(phase_list=[0, 12, 99], phases={"12": "Twelve"})
        self.assertIn("### Phase 12: Twelve", tg.projection(self.root))
        self.plan(phase_list=[0, 12, 99], phases={"5": "Five"})  # 5 is a default phase this project leaves out
        self.refuses("unknown phase '5'")

    def test_the_manual_phase_is_last_for_dependencies_and_order_too(self):
        self.write(todo_file([(1, "Hundred", 100, "none", "--"), (2, "Manual", 99, "none", "§1")]))
        self.plan(phase_list=[0, 99, 100])
        rows = tg.graph(self.root)
        self.assertEqual([r.phase for r in tg.ordered(rows)], [100, 99])
        self.assertEqual(re.findall(r"^### Phase (\d+)", tg.projection(self.root), re.M), ["100", "99"])

    def test_the_plan_orders_phases_numerically_with_the_manual_phase_last(self):
        self.write(todo_file([(1, "A", 12, "none", "--"), (2, "B", 0, "none", "--"), (3, "C", 3, "none", "--"),
                              (4, "D", 150, "none", "--"), (5, "E", 99, "none", "--")]))
        self.plan(phase_list=[0, 12, 3, 99, 150])
        headings = re.findall(r"^### Phase (\d+)", tg.projection(self.root), re.M)
        self.assertEqual(headings, ["0", "3", "12", "150", "99"])
        self.assertEqual([r.phase for r in tg.ordered(tg.graph(self.root))], [0, 3, 12, 150, 99])

    def test_a_prerequisite_in_the_manual_phase_is_later_than_any_other(self):
        self.write(todo_file([(1, "Manual", 99, "none", "--"), (2, "After", 150, "none", "§1")]))
        self.plan(phase_list=[0, 99, 150])
        self.refuses("prerequisite in later phase")

    @staticmethod
    def items(text, count):
        """A todo_file text whose sections each hold count checklist items (count - 1 work items, then Commit)."""
        return text.replace("- [ ] Work.\n", "".join(f"- [ ] Work {i}.\n" for i in range(1, count)))

    def test_caps_that_cannot_be_read_are_refused(self):
        # D03 T01 §3: the size caps come from todo/plan.json, whole numbers within each cap's bounds.
        self.write(todo_file([(1, "A", 0, "none", "--")]))
        for label, caps, said in (("caps not an object", [40], "caps must be an object"),
                                  ("caps as text", "40", "caps must be an object"),
                                  ("an unknown cap", {"widest": 40}, "caps names 'widest'"),
                                  ("a review cap", {"pass_cap": 45}, "caps names 'pass_cap'"),
                                  ("a boolean", {"items_per_section": True}, "caps items_per_section must be"),
                                  ("a fraction", {"items_per_section": 40.5}, "caps items_per_section must be"),
                                  ("a string", {"deliverable_len": "100"}, "caps deliverable_len must be"),
                                  *((f"{name} at {value}", {name: value}, f"caps {name} must be a whole number "
                                     f"from {low} to {high}")
                                    for name, (_, low, high) in tg.CAPS.items() for value in (low - 1, high + 1))):
            with self.subTest(label):
                self.plan(caps=caps)
                with self.assertRaises(tg.Refused) as ctx:
                    tg.graph(self.root)
                self.assertIn("todo/plan.json: " + said, str(ctx.exception))

    def test_each_cap_takes_its_bounds_and_a_cap_left_out_keeps_its_default(self):
        self.write(todo_file([(1, "A", 0, "none", "--")]))
        for end in (1, 2):
            caps = {name: bounds[end] for name, bounds in tg.CAPS.items()}
            self.plan(caps=caps)
            self.assertEqual(tg.plan_config(self.root)["caps"], caps)
            self.assertEqual(len(tg.graph(self.root)), 1)
        self.plan(caps={"items_per_section": 40})
        self.assertEqual(tg.plan_config(self.root)["caps"],
                         {"sections_per_file": 55, "items_per_section": 40, "deliverable_len": 88, "table_row": 120})
        (self.root / "todo/plan.json").unlink()
        self.assertEqual(tg.plan_config(self.root)["caps"], {name: d for name, (d, _, _) in tg.CAPS.items()})

    def test_items_per_section_is_read_from_the_plan(self):
        self.write(self.items(todo_file([(1, "A", 0, "none", "--")]), 40))
        self.refuses("2-30 items")
        self.plan(caps={"items_per_section": 39})
        self.refuses("2-39 items")
        self.plan(caps={"items_per_section": 40})
        self.assertEqual(len(tg.graph(self.root)), 1)
        self.write(self.items(todo_file([(1, "A", 0, "none", "--")]), 4))
        self.plan(caps={"items_per_section": 3})  # a lowered cap
        self.refuses("2-3 items")
        self.write(todo_file([(1, "A", 0, "none", "--")]))  # Work and Commit: the fewest a section holds
        self.plan(caps={"items_per_section": 2})
        self.assertEqual(len(tg.graph(self.root)), 1)

    def test_deliverable_len_is_read_from_the_plan_for_the_cell_and_the_heading(self):
        long = "D" * 100
        for label, text in (
                ("both", todo_file([(1, long, 0, "none", "--")])),
                ("the cell", todo_file([(1, "A", 0, "none", "--")], table_override=f"| 1 | §1 | {long} | -- | [ ] |")),
                ("the heading", todo_file([(1, long, 0, "none", "--")], table_override="| 1 | §1 | A | -- | [ ] |"))):
            with self.subTest(label):
                self.write(text)
                (self.root / "todo/plan.json").unlink(missing_ok=True)
                self.refuses("deliverable/title over 88 chars")
                self.plan(caps={"deliverable_len": 99})
                self.refuses("deliverable/title over 99 chars")
                self.plan(caps={"deliverable_len": 100})
                self.assertEqual(len(tg.graph(self.root)), 1)

    def test_sections_per_file_is_read_from_the_plan(self):
        self.write(todo_file([(n, f"S{n}", 0, "none", "--") for n in range(1, 61)]))
        self.refuses("over 55 sections")
        self.plan(caps={"sections_per_file": 59})
        self.refuses("over 59 sections")
        self.plan(caps={"sections_per_file": 60})
        self.assertEqual(len(tg.graph(self.root)), 60)

    def test_table_row_is_read_from_the_plan_and_a_longer_deliverable_needs_it(self):
        self.write(todo_file([(1, "D" * 100, 0, "none", "--")]))
        self.plan(caps={"deliverable_len": 100})
        with self.assertRaises(tg.Refused) as ctx:
            tg.projection(self.root)
        self.assertIn("> 120 chars", str(ctx.exception))
        self.plan(caps={"deliverable_len": 100, "table_row": 160})
        self.assertIn("D" * 100, tg.projection(self.root))

    def test_the_kit_guidance_names_the_configured_cap_wherever_it_states_a_default(self):
        # D03 T01 §3: the round and the completion review each found a guidance line still stating 88 or 30 as fixed.
        # Each default cap a line states has the todo/plan.json key that overrides it within 80 characters (a key
        # elsewhere on the line missed the completion's case); index Scope cells, which no cap governs, are exempt.
        kit = REPO / "kits/todo/templates"
        guidance = [kit / "todo/README.md", kit / "docs/todo-workflow.md"] + [
            kit / agent / "skills" / skill / "SKILL.md" for agent in (".claude", ".agents", ".codex")
            for skill in ("add-todo", "create-todo", "groom-plan")]
        rules = ((re.compile(r"(?:<= |most |under |over )`?88\b"), "deliverable_len"),
                 (re.compile(r"\b(?:max|to|most) 30\b"), "items_per_section"),
                 (re.compile(r"\b55 sections\b"), "sections_per_file"))
        stale = [f"{path.relative_to(kit)}:{n}: {m[0]!r} without {key}" for path in guidance
                 for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
                 for pattern, key in rules for m in pattern.finditer(line)
                 if key not in line[max(0, m.start() - 80):m.end() + 80]
                 and "Scope" not in line[max(0, m.start() - 40):m.start()]]
        self.assertEqual(stale, [], "guidance states a default cap without naming its todo/plan.json key")

    # D03 T01 §4: the receipts folder comes from todo/plan.json (`layout.receipts`). Each value, and whether both kits'
    # readers take it: the graph's plan_config and the reviewer kit's scripts/review_layout.py.
    LAYOUTS = ((None, "docs/reviews"), ({}, "docs/reviews"), ({"receipts": "reviews"}, "reviews"),
               ({"receipts": "docs/kept/reviews"}, "docs/kept/reviews"), ({"receipts": "a_b.c-d"}, "a_b.c-d"),
               ({"receipts": ".claude/overnight/reviews"}, ".claude/overnight/reviews"),  # Impossible OS's own
               ({"receipts": "docs/./reviews"}, "layout receipts must be"), ({"receipts": ".."}, "layout receipts must be"),
               ([], "layout must be an object"), ("reviews", "layout must be an object"),
               ({"plan": "docs/plan.md"}, "docs/reviews"), ({"receipts": "reviews", "plan": "docs/plan.md"}, "reviews"),
               ({"other": 1}, "layout names 'other'"), ({"receipts": 3}, "layout receipts must be"),
               ({"receipts": ""}, "layout receipts must be"), ({"receipts": "/reviews"}, "layout receipts must be"),
               ({"receipts": "C:/reviews"}, "layout receipts must be"),
               ({"receipts": "docs\\reviews"}, "layout receipts must be"),
               ({"receipts": "docs/../reviews"}, "layout receipts must be"),
               ({"receipts": "./reviews"}, "layout receipts must be"), ({"receipts": "reviews/"}, "layout receipts must be"),
               ({"receipts": "my reviews"}, "layout receipts must be"),
               ({"root_index": "domains"}, "docs/reviews"), ({"receipts": "reviews", "root_index": "files"}, "reviews"))

    @staticmethod
    def review_layout():
        spec = importlib.util.spec_from_file_location("review_layout_under_test",
                                                      REPO / "kits/reviewer/templates/scripts/review_layout.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_the_receipts_folder_is_read_alike_by_the_graph_and_the_reviewer_kit(self):
        self.write(todo_file([(1, "A", 0, "none", "--")]))
        layout = self.review_layout()
        for value, expected in self.LAYOUTS:
            with self.subTest(layout=value):
                if value is None:
                    (self.root / "todo/plan.json").unlink(missing_ok=True)
                else:
                    self.plan(layout=value)
                if "/" in expected or "_" in expected or expected == "reviews":
                    self.assertEqual((tg.receipts_folder(self.root), layout.receipts_folder(self.root)),
                                     (expected, expected))
                    continue
                with self.assertRaises(tg.Refused) as graph:
                    tg.graph(self.root)
                with self.assertRaises(layout.LayoutError) as reviewer:
                    layout.receipts_folder(self.root)
                for ctx in (graph, reviewer):
                    self.assertIn("todo/plan.json: " + expected, str(ctx.exception))
                self.assertEqual(str(graph.exception), str(reviewer.exception), "the two kits say it alike")

    # D03 T01 §11: `layout.root_index` "domains" lets the root index list each domain's INDEX.md instead of every file.
    def domains_tree(self):
        self.write(todo_file([(1, "A", 0, "none", "--")]), index=False)
        self.write(todo_file([(1, "B", 0, "none", "--")], ident="beta", domain="01-engine"), domain="01-engine",
                   index=False)
        for domain, name in (("00-workspace", "TODO-01-a.md"), ("01-engine", "TODO-01-a.md")):
            (self.root / "todo" / domain / "INDEX.md").write_text(f"# Index\n- {name}\n", encoding="utf-8")
        (self.root / "todo/TODO-00-INDEX.md").write_text("# Index\n- 00-workspace/INDEX.md\n- 01-engine/INDEX.md\n",
                                                          encoding="utf-8")

    def test_a_root_index_of_domains_validates_under_domains(self):
        self.domains_tree()
        self.plan(layout={"root_index": "domains"})
        tg.graph(self.root)
        (self.root / "todo/TODO-00-INDEX.md").write_text("# Index\n- 00-workspace/INDEX.md\n", encoding="utf-8")
        self.refuses("missing from root index: 01-engine/INDEX.md")
        self.domains_tree()
        (self.root / "todo/01-engine/INDEX.md").write_text("# Index\n", encoding="utf-8")
        self.refuses("missing from domain index: 01-engine/TODO-01-a.md")

    def test_an_index_entry_counts_only_as_a_whole_path(self):
        self.domains_tree()
        self.plan(layout={"root_index": "domains"})
        root = self.root / "todo/TODO-00-INDEX.md"
        for listed, ok in (("[Workspace](./00-workspace/INDEX.md)", True), ("`00-workspace/INDEX.md`", True),
                           ("[Workspace](archive/00-workspace/INDEX.md)", False), ("x00-workspace/INDEX.md", False),
                           ("00-workspace/INDEX.mdx", False)):
            with self.subTest(listed):
                root.write_text(f"# Index\n- {listed}\n- 01-engine/INDEX.md\n", encoding="utf-8")
                if ok:
                    tg.graph(self.root)
                else:
                    self.refuses("missing from root index: 00-workspace/INDEX.md")
        self.plan(layout={"root_index": "files"})  # the same rule for a file entry
        root.write_text("# Index\n- archive/00-workspace/TODO-01-a.md\n- 01-engine/TODO-01-a.md\n", encoding="utf-8")
        self.refuses("missing from root index: 00-workspace/TODO-01-a.md")

    def test_the_key_and_not_its_presence_picks_the_rule(self):
        self.domains_tree()
        self.plan(layout={"root_index": "domains"})
        tg.graph(self.root)
        self.plan(layout={"root_index": "files"})
        self.refuses("missing from root index: 00-workspace/TODO-01-a.md")
        root = self.root / "todo/TODO-00-INDEX.md"
        root.write_text(root.read_text(encoding="utf-8") + "- 00-workspace/TODO-01-a.md\n- 01-engine/TODO-01-a.md\n",
                        encoding="utf-8")
        tg.graph(self.root)

    def test_root_index_takes_files_or_domains_only(self):
        self.write(todo_file([(1, "A", 0, "none", "--")]))
        for value in ("both", 1, None, ["domains"]):
            with self.subTest(value=value):
                self.plan(layout={"root_index": value})
                self.refuses("todo/plan.json: layout root_index must be files")

    def test_the_creating_and_closing_skills_follow_root_index(self):
        for agent in (".claude", ".agents", ".codex"):
            for skill, anchor in (("create-todo", "under Active TODOs in `todo/TODO-00-INDEX.md`"),
                                  ("process-todo-file", "Move its line in `todo/TODO-00-INDEX.md`")):
                text = (REPO / "kits/todo/templates" / agent / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
                at = text.index(anchor)
                self.assertIn("layout.root_index", text[at:at + 200], f"{agent} {skill}")

    def test_a_receipts_folder_linked_out_of_the_repository_is_refused_by_both_readers(self):
        self.write(todo_file([(1, "A", 0, "none", "--")]))
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        link = self.root / "reviews"
        if os.name == "nt":
            import _winapi  # a junction needs no privilege on Windows
            _winapi.CreateJunction(outside.name, str(link))
        else:
            os.symlink(outside.name, link)
        # The tree's own cleanup unlinks the link without following it; this one covers a run that stops before.
        self.addCleanup(lambda: os.path.lexists(link) and (os.rmdir(link) if os.name == "nt" else link.unlink()))
        self.plan(layout={"receipts": "reviews"})
        self.refuses("todo/plan.json: layout receipts must be a folder inside the repository")
        layout = self.review_layout()
        with self.assertRaises(layout.LayoutError):
            layout.receipts_folder(self.root)

    def test_a_receipts_folder_linked_inside_the_repository_is_refused_too(self):
        # D03 T01 §4 round 1: a findings file is never read through a link (report_ok), so its folder is never reached
        # through one, even a link to the repository's own docs/reviews.
        self.write(todo_file([(1, "A", 0, "none", "--")]))
        (self.root / "docs/reviews").mkdir(parents=True)
        link = self.root / "reviews"
        if os.name == "nt":
            import _winapi
            _winapi.CreateJunction(str(self.root / "docs/reviews"), str(link))
        else:
            os.symlink(self.root / "docs/reviews", link)
        self.addCleanup(lambda: os.path.lexists(link) and (os.rmdir(link) if os.name == "nt" else link.unlink()))
        for receipts in ("reviews", "reviews/sub"):
            with self.subTest(receipts=receipts):
                self.plan(layout={"receipts": receipts})
                self.refuses("layout receipts must be a folder inside the repository reached through no link")
                layout = self.review_layout()
                with self.assertRaises(layout.LayoutError) as ctx:
                    layout.receipts_folder(self.root)
                self.assertIn("reached through no link", str(ctx.exception))

    def test_a_section_s_receipt_and_findings_file_live_in_the_configured_folder(self):
        self.write(todo_file([(1, "A", 0, "none", "--")]))
        self.plan(layout={"receipts": "reviews"})
        self.assertEqual(tg.section_findings(self.root, "D00 T01 §1"), "reviews/00-workspace/D00-T01-s1.md")
        with self.assertRaises(tg.Refused) as ctx:
            tg.receipt_ok(self.root, "docs/reviews/d00-t01-s1.json", "D00 T01 §1", "0" * 40)
        self.assertIn("invalid receipt path", str(ctx.exception))
        with self.assertRaises(tg.Refused) as ctx:
            tg.report_ok(self.root, "docs/reviews/00-workspace/D00-T01-s1.md", "D00 T01 §1")
        self.assertIn("invalid review report path", str(ctx.exception))

    def test_the_kit_guidance_names_the_configured_plan_wherever_it_names_the_default(self):
        # D03 T01 §7: a mention of todo/implementation-plan.md names layout.plan within 80 characters. A skill's
        # frontmatter description is the trigger text agents match on, kept short; its body says the rest.
        kit = REPO / "kits/todo/templates"
        files = [p for p in kit.rglob("*.md") if "skills" in p.parts or p.name in ("todo-workflow.md", "README.md")]
        stale = [f"{path.relative_to(kit)}:{n}" for path in files
                 for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
                 if not line.startswith("description:")
                 for m in re.finditer(r"implementation-plan\.md", line)
                 if "layout.plan" not in line[max(0, m.start() - 80):m.end() + 80]]
        self.assertEqual(stale, [], "guidance names the default plan path without layout.plan")

    def test_the_section_skills_write_the_configured_folder_in_their_commands(self):
        # D03 T01 §4: a command that writes docs/reviews/ starts a project's review outside its configured folder.
        kit = REPO / "kits/todo/templates"
        skills = [kit / agent / "skills" / skill / "SKILL.md" for agent in (".claude", ".agents", ".codex")
                  for skill in ("process-todo-section", "review-todo-section")]
        literal = [f"{path.relative_to(kit)}:{n}" for path in skills
                   for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
                   if re.match(r"\s*python3? ", line) and "docs/reviews" in line]
        self.assertEqual(literal, [], "a command names docs/reviews/ instead of <receipts>/")
        for path in skills:
            self.assertIn("`<receipts>` being `layout.receipts` in `todo/plan.json`, `docs/reviews` by default",
                          path.read_text(encoding="utf-8"), f"{path.relative_to(kit)} never says what <receipts> is")

    # D03 T01 §8: given a faults list, graph records every refusal and goes on (validate --all).
    def faults(self):
        found = []
        tg.graph(self.root, faults=found)
        return [message for _, message in found]

    def test_every_fault_in_a_section_is_recorded_and_the_first_still_raises_without_the_list(self):
        self.write(todo_file([(1, "A", 42, "gpu", "--")]))
        self.assertEqual(self.faults(), ["invalid Phase: D00 T01 §1", "unknown/duplicate Needs (gpu): D00 T01 §1"])
        self.refuses("invalid Phase: D00 T01 §1")

    def test_a_section_under_an_unreadable_row_still_has_its_body_checked(self):
        # D03 T01 §5 (completion): Impossible OS's tables hid every section-level fault behind the row fault.
        text = todo_file([(1, "A", 0, "none", "--"), (2, "B", 0, "none", "§1")]).replace(
            "| 1 | §1 | A | -- | [ ] |", "| ⭐ | 1 | A | -- | [ ] |").replace("**Phase:** 0\n", "", 1)
        self.write(text.replace("**Needs:** none", "**Needs:** gpu", 1) + "\n- -> XREF: D00 T01 §1\n")
        found = self.faults()
        self.assertIn("malformed implementation row: todo/00-workspace/TODO-01-a.md", found)
        self.assertIn("missing Phase field", found)
        self.assertIn("unknown/duplicate Needs (gpu): D00 T01 §1", found)
        # It is no node of the graph, and nothing that names it is a second fault.
        self.assertFalse([m for m in found if "unresolved" in m and "§1" in m], found)
        self.refuses("malformed implementation row")

    def test_a_rowless_sections_valid_stamp_is_paired_with_its_receipt(self):
        # D03 T01 §13 (plan review): a valid stamp under an unreadable row still needs and checks its receipt.
        self.git("commit", "-q", "--allow-empty", "-m", "base")
        sha = self.git("rev-parse", "HEAD")
        stamp = f"> **Verified:** 2026-11-13 | §1 | {sha}\n"
        receipt_line = "> **Review:** `docs/reviews/d00-t01-s1.json`\n"
        receipt = self.root / "docs/reviews/d00-t01-s1.json"
        receipt.parent.mkdir(parents=True, exist_ok=True)
        base = todo_file([(1, "A", 0, "none", "--")]).replace("| 1 | §1 | A | -- | [ ] |", "| x | 1 | A | -- | [x] |")
        base = base.replace("- [ ] ", "- [x] ")
        cases = {"no Review line": (stamp, None), "missing receipt": (stamp + receipt_line, None),
                 "unreadable receipt": (stamp + receipt_line, b"\xff\xfe"), "invalid receipt": (stamp + receipt_line, b"{}")}
        for name, (lines, data) in cases.items():
            with self.subTest(name):
                receipt.unlink(missing_ok=True)
                if data is not None:
                    receipt.write_bytes(data)
                self.write(base.replace("\n## Verification", "\n" + lines + "\n## Verification"))
                found = [m for m in self.faults() if "§1" in m and not m.startswith("malformed implementation row")]
                if name == "no Review line":
                    self.assertIn("stamp/receipt mismatch: D00 T01 §1", found)
                else:
                    self.assertTrue(found and not any(m.startswith(("invalid stamp", "stamp/receipt")) for m in found),
                                    found)  # the receipt itself was checked and refused

    def test_a_rowless_section_with_a_valid_body_is_no_node_of_the_graph(self):
        text = todo_file([(1, "A", 0, "none", "--"), (2, "B", 0, "none", "--")]).replace(
            "| 1 | §1 | A | -- | [ ] |", "| ⭐ | 1 | A | -- | [ ] |")
        self.write(text)
        found, sections = [], None
        sections = tg.graph(self.root, faults=found)
        self.assertIn("malformed implementation row: todo/00-workspace/TODO-01-a.md", [m for _, m in found])
        self.assertNotIn("D00 T01 §1", sections)
        self.assertIn("D00 T01 §2", sections)

    def test_a_section_under_an_unreadable_row_has_its_own_stamp_checked(self):
        text = todo_file([(1, "A", 0, "none", "--")]).replace("| 1 | §1 | A | -- | [ ] |", "| x | 1 | A | -- | [x] |")
        self.write(text.replace("\n## Verification", "\n> **Verified:** 2026-11-13 | §1 | abc\n\n## Verification"))
        self.assertIn("invalid stamp: D00 T01 §1", self.faults())

    def test_a_section_under_bad_frontmatter_still_has_its_body_checked(self):
        # D03 T01 §5 (reconciliation): two Impossible OS files with a bad frontmatter line hid 42 sections.
        text = todo_file([(1, "A", 0, "none", "--")]).replace("status: active", "status: active\nnot a field line")
        self.write(text.replace("**Phase:** 0\n", "", 1).replace(
            "**Test checkpoint:** `true` exits 0.", "**Freeze check:** x\n\n**Test checkpoint:** `true` exits 0."))
        found = self.faults()
        self.assertIn("invalid or duplicate frontmatter: todo/00-workspace/TODO-01-a.md", found)
        self.assertIn("missing Phase field", found)
        # What the bad frontmatter would have said is not judged: no field, frozen or status fault follows from it.
        self.assertFalse([m for m in found if m.startswith(("frontmatter fields", "Freeze check", "file status"))], found)
        self.refuses("invalid or duplicate frontmatter")

    def test_a_section_in_a_file_with_no_table_still_has_its_body_checked(self):
        text = todo_file([(1, "A", 0, "none", "--")])
        table = text[text.index("## Implementation Order"):text.index("## 1.")]
        self.write(text.replace(table, "").replace("**Phase:** 0\n", "", 1))
        found = self.faults()
        self.assertIn("missing Implementation Order: todo/00-workspace/TODO-01-a.md", found)
        self.assertIn("missing Phase field", found)
        self.assertFalse([m for m in found if m.startswith(("invalid implementation order", "row/body"))], found)
        self.refuses("missing Implementation Order")

    # D03 T01 §12: one graph call reads each git answer and todo/plan.json once, and forgets them when it ends.
    def stamped_repo(self, sha, phase=0):
        """Two sections stamped on `sha` with receipts that fail their checks, committed: graph asks git about the
        stamp commit for each, and the faults are not empty."""
        rows = [(1, "A", phase, "none", "--"), (2, "B", 0, "none", "--")]
        text = todo_file(rows).replace("| [ ] |", "| [x] |").replace("- [ ] ", "- [x] ")
        for n in (1, 2):
            stamp = f"> **Verified:** 2026-11-13 | §{n} | {sha}\n> **Review:** `docs/reviews/d00-t01-s{n}.json`\n\n"
            text = text.replace(f"\n## {n + 1}." if n == 1 else "\n## Verification",
                                "\n" + stamp + (f"## {n + 1}." if n == 1 else "## Verification"), 1)
            receipt = self.root / f"docs/reviews/d00-t01-s{n}.json"
            receipt.parent.mkdir(parents=True, exist_ok=True)
            receipt.write_text("{}\n", encoding="utf-8")
        self.write(text.replace("status: active", "status: done"))
        self.git("add", "-A")
        self.git("commit", "-qm", "tree")

    def git(self, *args):
        if not (self.root / ".git").exists():
            for cmd in (["init", "-q"], ["config", "user.email", "t@example.com"], ["config", "user.name", "T"]):
                subprocess.run(["git", "-C", str(self.root), *cmd], check=True)
        return subprocess.run(["git", "-C", str(self.root), *args], check=True, capture_output=True,
                              text=True).stdout.strip()

    def git_calls(self, fn):
        real, calls = subprocess.run, []

        def spy(argv, *a, **k):
            if argv[:1] == ["git"]:
                calls.append(tuple(argv[3:]))
            return real(argv, *a, **k)

        with mock.patch.object(tg.subprocess, "run", spy):
            result = fn()
        return result, calls

    def test_a_graph_call_asks_git_each_question_once_and_finds_the_same_faults(self):
        self.git("commit", "-q", "--allow-empty", "-m", "base")
        self.stamped_repo("0" * 40)  # a stamp commit that is in no history: each section's lookup fails
        cached, calls = self.git_calls(self.faults)
        with mock.patch.object(tg, "CACHE_RUNS", False):
            uncached, raw_calls = self.git_calls(self.faults)
        self.assertTrue(cached)
        self.assertEqual(cached, uncached)
        self.assertEqual(len(calls), len(set(calls)), calls)  # each distinct command once
        self.assertGreater(len(raw_calls), len(set(raw_calls)), raw_calls)  # the fixture does repeat them uncached
        with mock.patch.object(tg, "CACHE_RUNS", False):
            with self.assertRaises(tg.Refused) as plain:
                tg.graph(self.root)
        with self.assertRaises(tg.Refused) as fast:
            tg.graph(self.root)
        self.assertEqual(str(fast.exception), str(plain.exception))

    def test_plan_json_is_read_once_per_graph_call(self):
        self.write(todo_file([(1, "A", 0, "none", "--"), (2, "B", 0, "none", "--")]))
        with mock.patch.object(tg, "_plan_config", wraps=tg._plan_config) as reads:
            tg.graph(self.root)
            tg.graph(self.root)
        self.assertEqual(reads.call_count, 2)

    def test_the_cache_ends_with_its_graph_call_whether_it_returns_or_raises(self):
        self.git("commit", "-q", "--allow-empty", "-m", "base")
        base = self.git("rev-parse", "HEAD")
        self.git("checkout", "-qb", "side")
        self.git("commit", "-q", "--allow-empty", "-m", "later")
        later = self.git("rev-parse", "HEAD")
        self.git("checkout", "-q", "-")
        self.git("reset", "-q", "--hard", base)
        self.stamped_repo(later, phase=12)
        before = self.faults()  # returned: the stamp commit is off the branch and phase 12 is unknown
        self.assertIn("invalid Phase: D00 T01 §1", before)
        self.assertTrue(any("not on this branch" in m for m in before), before)
        self.assertIsNone(tg._RUN_CACHE)
        self.git("merge", "-q", "--no-edit", "side")  # a new HEAD that holds the stamp commit
        (self.root / "todo/plan.json").write_text('{"phase_list": [0, 12]}\n', encoding="utf-8")
        after = self.faults()
        self.assertNotIn("invalid Phase: D00 T01 §1", after)
        self.assertFalse(any("not on this branch" in m for m in after), after)
        # After a call that raised, the next one reads a new commit and a new configuration fresh too.
        self.git("reset", "-q", "--hard", "HEAD~1")  # back to the tree commit: the stamp commit off the branch
        (self.root / "todo/plan.json").write_text('{"phase_list": [0, 12]}\n', encoding="utf-8")
        with self.assertRaises(tg.Refused) as first:
            tg.graph(self.root)
        self.assertIn("not on this branch", str(first.exception))
        self.assertIsNone(tg._RUN_CACHE)
        self.git("merge", "-q", "--no-edit", "side")
        (self.root / "todo/plan.json").write_text('{"phase_list": [0]}\n', encoding="utf-8")
        with self.assertRaises(tg.Refused) as second:
            tg.graph(self.root)
        self.assertEqual(str(second.exception), "invalid Phase: D00 T01 §1")  # the new plan.json, read fresh
        (self.root / "todo/plan.json").write_text('{"phase_list": [0, 12]}\n', encoding="utf-8")
        with self.assertRaises(tg.Refused) as third:
            tg.graph(self.root)
        self.assertNotIn("not on this branch", str(third.exception))  # the new HEAD, read fresh
        self.assertNotIn("invalid Phase", str(third.exception))

    def test_a_file_read_at_a_commit_answers_as_git_show_does(self):
        self.write(todo_file([(1, "A", 0, "none", "--")]))
        self.git("add", "-A")
        self.git("commit", "-qm", "x")
        head = self.git("rev-parse", "HEAD")
        rel = "todo/00-workspace/TODO-01-a.md"
        tg._RUN_CACHE = cache = {"git": {}, "config": {}, "batch": {}, "history": {}}
        try:
            for spec in (f"{head}:{rel}", f"{head}:todo/missing.md", f"{head}:todo", "nope:x"):
                fast = tg._git(self.root, "show", spec)
                plain = subprocess.run(["git", "-C", str(self.root), "show", spec], capture_output=True)
                self.assertEqual((fast.returncode == 0, fast.stdout if fast.returncode == 0 else b""),
                                 (plain.returncode == 0, plain.stdout if plain.returncode == 0 else b""), spec)
            for older, newer, expected in ((head, head, 0), (head, "HEAD", 0), ("f" * 40, head, None)):
                answer = tg._git(self.root, "merge-base", "--is-ancestor", older, newer)
                real = subprocess.run(["git", "-C", str(self.root), "merge-base", "--is-ancestor", older, newer],
                                      capture_output=True)
                self.assertEqual(answer.returncode, real.returncode, (older, newer))
        finally:
            tg._RUN_CACHE = None
            tg._end_run(cache)
        self.assertTrue(all(e["proc"].poll() is not None for e in cache["batch"].values()), "a batch outlived its run")

    def fake_batch(self, stdout):
        """A stand-in for `git cat-file --batch` whose output is `stdout` (a file-like object)."""
        proc = mock.Mock()
        proc.stdin, proc.stdout = io.BytesIO(), stdout
        proc.wait.return_value = 0
        proc.kill.side_effect = getattr(stdout, "killed", None)  # killing a process ends its output
        return proc

    def batch_read(self, stdout, timeout=30.0):
        """_git's `show` through a fake batch process inside a run, and how long it took; then the real answer."""
        self.write(todo_file([(1, "A", 0, "none", "--")]))
        self.git("add", "-A")
        self.git("commit", "-qm", "x")
        spec = self.git("rev-parse", "HEAD") + ":todo/00-workspace/TODO-01-a.md"
        tg._RUN_CACHE = cache = {"git": {}, "config": {}, "batch": {}, "history": {}}
        real_popen = subprocess.Popen
        try:
            fakes = [self.fake_batch(stdout)]  # the batch process; git show itself (the fallback) runs for real
            started = time.monotonic()
            with mock.patch.object(tg.subprocess, "Popen", lambda *a, **k: fakes.pop() if fakes else real_popen(*a, **k)):
                answer = tg._git(self.root, "show", spec, timeout=timeout)
                took = time.monotonic() - started  # the read alone, not the fixture or the comparison
        finally:
            tg._RUN_CACHE = None
            tg._end_run(cache)
        plain = real_popen(["git", "-C", str(self.root), "show", spec], stdout=subprocess.PIPE).communicate()[0]
        return answer, plain, took, cache

    def test_a_batch_reply_shorter_than_announced_is_answered_by_git_itself(self):
        answer, plain, _, cache = self.batch_read(io.BytesIO(b"abc blob 100\nabc"))
        self.assertEqual((answer.returncode, answer.stdout), (0, plain))  # the real file, not a truncated one
        self.assertTrue(all(e["broken"] for e in cache["batch"].values()))

    def test_a_batch_reply_that_never_comes_is_bounded_by_the_timeout(self):
        gate = threading.Event()
        stalled = mock.Mock()
        stalled.readline.side_effect = lambda: (gate.wait(5), b"")[1]  # stalls past the timeout until killed
        stalled.killed = gate.set
        answer, plain, took, cache = self.batch_read(stalled, timeout=0.5)
        gate.set()
        self.assertEqual((answer.returncode, answer.stdout), (0, plain))
        self.assertLess(took, 4)
        self.assertTrue(all(e["broken"] for e in cache["batch"].values()))

    def test_a_repeated_stamp_or_freeze_field_is_recorded_not_raised(self):
        # D03 T01 §5 (completion): one duplicate Verified line in Impossible OS ended validate --all for the whole tree.
        text = todo_file([(1, "A", 0, "none", "--"), (2, "B", 0, "none", "--")])
        twice = "> **Verified:** 2026-11-13 | §1 | x\n> **Verified:** 2026-11-14 | §1 | y\n\n## 2."
        self.write(text.replace("\n## 2.", "\n" + twice, 1).replace(
            "**Test checkpoint:** `true` exits 0.\n\n## Verification",
            "**Freeze check:** a\n**Freeze check:** b\n\n**Test checkpoint:** `true` exits 0.\n\n## Verification"))
        self.write(todo_file([(1, "C", 0, "gpu", "--")], ident="beta"), name="TODO-02-b.md")
        found = self.faults()
        self.assertIn("duplicate Verified field", found)
        self.assertIn("duplicate Freeze check field", found)
        self.assertIn("unknown/duplicate Needs (gpu): D00 T02 §1", found)
        self.refuses("duplicate Verified field")

    def test_faults_in_two_sections_of_one_file_and_in_another_file_are_all_recorded(self):
        self.write(todo_file([(1, "A", 42, "none", "--"), (2, "B", 0, "gpu", "--")]))
        self.write(todo_file([(1, "C", 0, "none", "--")], ident="beta").replace("**Surface:** no", "**Surface:** maybe"),
                   name="TODO-02-b.md")
        self.assertEqual(self.faults(), ["invalid Phase: D00 T01 §1", "unknown/duplicate Needs (gpu): D00 T01 §2",
                                         "Surface must be yes/no: D00 T02 §1"])

    def test_the_cross_file_checks_collect_too(self):
        self.write(todo_file([(1, "A", 0, "none", "§2"), (2, "B", 0, "none", "§1")],
                             inputs="- i -> XREF: D00 T09 §1"))  # a cycle, and an XREF to nothing
        self.write(todo_file([(1, "C", 0, "gpu", "--")], ident="beta"), name="TODO-02-b.md", index=False)
        found = self.faults()
        for expected in ("unresolved XREF target D00 T09 §1: todo/00-workspace/TODO-01-a.md",
                         "unknown/duplicate Needs (gpu): D00 T02 §1", "missing from domain index: 00-workspace/TODO-02-b.md",
                         "dependency cycle: D00 T01 §1"):
            self.assertIn(expected, found)

    def test_a_read_failure_and_bad_depends_on_are_recorded_with_their_path(self):
        self.write(todo_file([(1, "A", 0, "none", "--")]).replace("status: active", 'status: active\ndepends_on: ["x"'))
        self.write(todo_file([(1, "B", 0, "none", "--")], ident="beta"), name="TODO-02-b.md")
        self.write(todo_file([(1, "C", 0, "gpu", "--")], ident="gamma"), name="TODO-03-c.md")
        real = tg.read_text
        unreadable = self.root / "todo/00-workspace/TODO-02-b.md"

        def read_text(path):
            if pathlib.Path(path) == unreadable:
                raise OSError(5, "Input/output error")
            return real(path)

        found = []
        with unittest.mock.patch.object(tg, "read_text", read_text):
            tg.graph(self.root, faults=found)
        where = [w for w, _ in found]
        self.assertIn("todo/00-workspace/TODO-01-a.md", where, "the malformed depends_on, by its path")
        self.assertIn("todo/00-workspace/TODO-02-b.md", where, "the unreadable file, by its path")
        self.assertIn(("D00 T03 §1", "unknown/duplicate Needs (gpu): D00 T03 §1"), found)

    def test_a_fault_that_only_follows_from_another_is_not_recorded(self):
        self.write(todo_file([(1, "A", 0, "none", "--"), (2, "B", 42, "none", "--"), (3, "C", 0, "none", "§2")],
                             inputs="- i -> XREF: D00 T02 §1"))
        self.write(todo_file([(1, "D", 42, "none", "--")], ident="beta", inputs="- i -> XREF: D00 T01 §2"),
                   name="TODO-02-b.md")  # an active file whose only section cannot be read
        self.assertEqual(sorted(self.faults()), ["invalid Phase: D00 T01 §2", "invalid Phase: D00 T02 §1"])
        self.write(todo_file([(1, "A", 0, "none", "--"), (2, "B", 42, "none", "--"), (3, "C", 0, "none", "§9")]))
        self.assertIn("unresolved dependency: D00 T01 §9", self.faults(), "a reference to nothing is still recorded")

    def test_an_unreadable_index_is_recorded_and_the_walk_still_runs(self):
        # D03 T01 §8 round 1: an index read outside attempt() ended the run.
        self.write(todo_file([(1, "A", 0, "gpu", "§9")]))
        real = tg.read_text
        index = self.root / "todo/00-workspace/INDEX.md"

        def read_text(path):
            if pathlib.Path(path) == index:
                raise OSError(5, "Input/output error")
            return real(path)

        found = []
        with unittest.mock.patch.object(tg, "read_text", read_text):
            tg.graph(self.root, faults=found)
        messages = [m for _, m in found]
        self.assertIn("todo/00-workspace/INDEX.md", [w for w, _ in found])
        self.assertIn("unknown/duplicate Needs (gpu): D00 T01 §1", messages)
        self.assertIn("unresolved dependency: D00 T01 §9", messages, "the dependency walk ran after the index")

    def test_a_failed_section_in_a_third_file_does_not_hide_a_one_sided_xref(self):
        # D03 T01 §8 round 1: only a backlink into the originating file may stand in for the missing one.
        self.write(todo_file([(1, "A", 0, "none", "--")], inputs="- i -> XREF: D00 T02 §1"))
        self.write(todo_file([(1, "B", 0, "none", "--")], ident="beta", inputs="- i -> XREF: D00 T03 §1"),
                   name="TODO-02-b.md")
        self.write(todo_file([(1, "C", 42, "none", "--")], ident="gamma", inputs="- i -> XREF: D00 T02 §1"),
                   name="TODO-03-c.md")
        self.assertIn("one-sided XREF D00 T02 §1 has no pointer back: todo/00-workspace/TODO-01-a.md", self.faults())

    def test_a_section_left_out_of_the_graph_still_has_its_deferrals_checked(self):
        # D03 T01 §8 round 1: a deferral needs no Phase.
        self.write(todo_file([(1, "A", 42, "none", "--")]).replace(
            "**Test checkpoint:**", "> **Deferred:** abandoned\n\n**Test checkpoint:**", 1))
        self.assertEqual(self.faults(), ["invalid Phase: D00 T01 §1", "Deferred without a resolving owner: D00 T01 §1"])

    def test_a_missing_frontmatter_field_hides_only_the_checks_that_read_it(self):
        # D03 T01 §8 completion: Needs need no title.
        self.write(todo_file([(1, "A", 0, "gpu", "--")]).replace('title: "TODO-01 -- A"\n', "", 1))
        self.assertEqual(self.faults(), ["frontmatter fields: todo/00-workspace/TODO-01-a.md",
                                         "unknown/duplicate Needs (gpu): D00 T01 §1"])

    def test_a_missing_index_hides_only_its_own_checks(self):
        # D03 T01 §8 completion: each index is read whatever became of the other.
        self.write(todo_file([(1, "A", 0, "none", "--")]))
        (self.root / "todo/TODO-00-INDEX.md").unlink()
        (self.root / "todo/00-workspace/INDEX.md").write_text("# Index\n", encoding="utf-8")
        self.assertEqual(self.faults(), ["missing from domain index: 00-workspace/TODO-01-a.md",
                                         "missing todo/TODO-00-INDEX.md"])
        self.write(todo_file([(1, "A", 0, "none", "--")]))  # both indexes listed again
        (self.root / "todo/00-workspace/INDEX.md").unlink()
        root_index = self.root / "todo/TODO-00-INDEX.md"
        root_index.write_text("# Index\n", encoding="utf-8")
        self.assertEqual(self.faults(), ["missing domain index: todo/00-workspace/INDEX.md",
                                         "missing from root index: 00-workspace/TODO-01-a.md"])

    def test_faults_come_back_in_file_order_whichever_pass_found_them(self):
        # D03 T01 §8 completion: the dependency walk runs after every file is read, but its fault is the first file's.
        self.write(todo_file([(1, "A", 0, "none", "§9")]))
        self.write(todo_file([(1, "B", 0, "gpu", "--")], ident="beta"), name="TODO-02-b.md")
        self.assertEqual(self.faults(), ["unresolved dependency: D00 T01 §9", "unknown/duplicate Needs (gpu): D00 T02 §1"])

    def test_validate_all_prints_every_fault_and_exits_2(self):
        self.write(todo_file([(1, "A", 42, "gpu", "--")]))
        shutil.copytree(SCRIPTS, self.root / "scripts")
        run = subprocess.run([sys.executable, "-B", str(self.root / "scripts/todo-graph.py"), "validate", "--all"],
                             capture_output=True, text=True, encoding="utf-8", timeout=120)
        self.assertEqual(run.returncode, 2, run.stdout + run.stderr)
        self.assertEqual(run.stdout.splitlines(), ["D00 T01 §1: invalid Phase: D00 T01 §1",
                                                   "D00 T01 §1: unknown/duplicate Needs (gpu): D00 T01 §1"])
        sdk = subprocess.run([sys.executable, "-B", str(REPO / "scripts/todo-graph.py"), "validate", "--all"],
                             capture_output=True, text=True, encoding="utf-8", timeout=300)
        self.assertEqual(sdk.returncode, 0, sdk.stdout + sdk.stderr)
        self.assertRegex(sdk.stdout, r"^valid: \d+ sections")

    # D03 T01 §7: the plan path comes from todo/plan.json (`layout.plan`) and never lands on a file the plan does
    # not own.
    def test_a_plan_path_the_plan_does_not_own_is_refused_before_anything_is_written(self):
        self.write(todo_file([(1, "A", 0, "none", "--")]))
        (self.root / "docs").mkdir()
        notes = self.root / "docs/notes.md"
        notes.write_bytes(b"# Implementation plan\n\nHand notes under the plan's own heading.\n")
        for plan, said in (("todo/plan.json", "layout plan must be a .md file"), ("plan.txt", "layout plan must be"),
                           ("/plan.md", "layout plan must be"), ("C:/plan.md", "layout plan must be"),
                           ("docs/../plan.md", "layout plan must be"), ("todo/README.md", "does not own"),
                           ("TODO/readme.md", "does not own"), ("todo/00-workspace/plan.md", "does not own"),
                           ("docs/reviews/plan.md", "does not own"), ("docs/notes.md", "is not a generated plan")):
            with self.subTest(plan=plan):
                self.plan(layout={"plan": plan})
                before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
                with self.assertRaises(tg.Refused) as ctx:
                    tg.projections(self.root, sync=True)
                self.assertIn("todo/plan.json: layout plan", str(ctx.exception))
                self.assertIn(said, str(ctx.exception))
                self.assertEqual({p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}, before,
                                 "a refused plan path wrote something")

    def test_a_plan_path_on_or_above_the_receipts_folder_is_refused(self):
        # D03 T01 §7 round 1: a plan written where the receipts folder must be leaves no folder for the stamp.
        self.write(todo_file([(1, "A", 0, "none", "--")]))
        for receipts, plan in (("docs/reviews.md", "docs/reviews.md"), ("docs/reviews.md/receipts", "docs/reviews.md")):
            with self.subTest(receipts=receipts, plan=plan):
                self.plan(layout={"receipts": receipts, "plan": plan})
                with self.assertRaises(tg.Refused) as ctx:
                    tg.projections(self.root, sync=True)
                self.assertIn("or the receipts folder, a file in it or a folder above it", str(ctx.exception))
                self.assertFalse((self.root / plan).exists(), "nothing was written")

    def test_a_title_of_more_than_one_line_is_refused(self):
        # D03 T01 §7 round 1: a title is the plan's heading, and a second line would push the generated notice down
        # past where a configured plan is recognised as the plan's own.
        self.write(todo_file([(1, "A", 0, "none", "--")]))
        for title in ("One\nTwo", "One\r\nTwo"):
            with self.subTest(title=title):
                self.plan(title=title, layout={"plan": "docs/plan.md"})
                self.refuses("todo/plan.json: title must be one line of text")
        self.plan(title="One line", layout={"plan": "docs/plan.md"})
        tg.projections(self.root, sync=True)
        tg.projections(self.root, sync=True)  # its own output is recognised again

    def test_the_plan_is_written_and_checked_at_the_configured_path(self):
        self.write(todo_file([(1, "A", 0, "none", "--")]))
        self.plan(layout={"plan": "docs/plan.md"})
        tg.projections(self.root, sync=True)
        self.assertTrue((self.root / "docs/plan.md").is_file())
        self.assertFalse((self.root / tg.PLAN).exists(), "nothing at the default path")
        tg.projections(self.root)  # --check reads the configured path
        with open(self.root / "docs/plan.md", "a", encoding="utf-8") as handle:
            handle.write("a line plan --sync did not write\n")
        with self.assertRaises(tg.Refused) as ctx:
            tg.projections(self.root)
        self.assertIn("stale projection: docs/plan.md", str(ctx.exception))

    def test_an_owned_plan_regenerates_after_its_title_changes(self):
        self.write(todo_file([(1, "A", 0, "none", "--")]))
        self.plan(layout={"plan": "docs/plan.md"})
        tg.projections(self.root, sync=True)
        self.plan(layout={"plan": "docs/plan.md"}, title="Another title")
        tg.projections(self.root, sync=True)  # the notice, not the title, says the file is the plan's
        self.assertTrue((self.root / "docs/plan.md").read_text(encoding="utf-8").startswith("# Another title\n"))

    def test_without_a_plan_key_the_default_path_is_kept_as_before(self):
        self.write(todo_file([(1, "A", 0, "none", "--")]))
        (self.root / tg.PLAN).write_text("hand written\n", encoding="utf-8")  # the kit's own path, as before
        self.plan(layout={"receipts": "reviews"})
        self.assertEqual(tg.plan_file(self.root), tg.PLAN)
        tg.projections(self.root, sync=True)
        self.assertIn(tg.PLAN_NOTICE, (self.root / tg.PLAN).read_text(encoding="utf-8"))

    def test_a_project_names_its_own_needs_and_which_wait(self):
        # D03 T01 §2: Needs values and waiting Needs come from todo/plan.json.
        self.write(todo_file([(1, "A", 0, "gpu", "--"), (2, "B", 0, "owner-decision", "--")]))
        self.refuses("unknown/duplicate Needs (gpu)")
        self.plan(needs=["gpu", "owner-decision"], waiting=["gpu"])
        rows = tg.graph(self.root)
        self.assertEqual({ref: tg.disposition(r, rows) for ref, r in rows.items()},
                         {"D00 T01 §1": 4, "D00 T01 §2": 0}, "gpu waits and owner-decision does not, by this plan")
        self.plan(needs=["owner-decision"])
        self.refuses("unknown/duplicate Needs (gpu)")

    def test_needs_and_waiting_that_cannot_be_read_are_refused(self):
        self.write(todo_file([(1, "A", 0, "none", "--")]))
        for label, keys, said in (("needs not a list", {"needs": "gpu"}, "needs must be a list"),
                                  ("a malformed name", {"needs": ["GPU"]}, "needs must be a list"),
                                  ("a duplicate", {"needs": ["gpu", "gpu"]}, "needs must be a list"),
                                  ("the reserved none", {"needs": ["none"]}, "needs may not name none"),
                                  ("none waiting", {"needs": ["gpu"], "waiting": ["none"]}, "waiting may not name none"),
                                  ("waiting outside needs", {"needs": ["gpu"], "waiting": ["operator"]},
                                   "waiting names operator, which needs does not")):
            with self.subTest(label):
                self.plan(**keys)
                with self.assertRaises(tg.Refused) as ctx:
                    tg.graph(self.root)
                self.assertIn("todo/plan.json", str(ctx.exception))
                self.assertIn(said, str(ctx.exception))

    def test_needs_without_waiting_keeps_the_kits_waiting_needs_it_lists(self):
        self.write(todo_file([(1, "A", 0, "gpu", "--"), (2, "B", 0, "operator", "--")]))
        self.plan(needs=["gpu", "operator"])
        rows = tg.graph(self.root)
        self.assertEqual({ref: tg.disposition(r, rows) for ref, r in rows.items()},
                         {"D00 T01 §1": 0, "D00 T01 §2": 4})

    def test_without_needs_keys_the_defaults_hold(self):
        self.write(todo_file([(1, "A", 0, "owner-decision", "--"), (2, "B", 0, "attended", "--")]))
        rows = tg.graph(self.root)
        self.assertEqual({ref: tg.disposition(r, rows) for ref, r in rows.items()},
                         {"D00 T01 §1": 4, "D00 T01 §2": 0})

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

    def test_deliverable_or_title_over_max_len_refuses(self):
        self.write(todo_file([(1, "X" * 89, 0, "none", "--")]))
        self.refuses("deliverable/title over 88 chars (wraps raw md table): D00 T01 §1")
        # The limit is the title's, which the table shows; the "## N. " prefix appears in no table.
        self.write(todo_file([(1, "X" * 88, 0, "none", "--")]))
        tg.graph(self.root)

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

    def test_resolve_accepts_windows_and_posix_paths_and_plan_rows(self):
        self.write(todo_file([(1, "A", 0, "none", "--")]))
        rows = tg.graph(self.root)
        for query in (
            "D00 T01 §1",
            "| [ ] | D00 T01 §1 | A | none | 2 |",
            "todo/00-workspace/TODO-01-a.md §1",
            r"C:\work\Project\todo\00-workspace\TODO-01-a.md §1",
        ):
            self.assertEqual(tg.extract_ref(query, rows), ("D00 T01 §1", 0))
        self.assertEqual(tg.extract_ref(r"C:\work\Project\todo\00-workspace\TODO-01-a.md §9", rows),
                         ("D00 T01 §9", 1))
        self.assertEqual(tg.extract_ref("no reference here", rows), (None, 2))

    def test_deep_dependency_chain_validates_without_recursion_error(self):
        for file_num in range(1, 21):
            rows = []
            for sec_num in range(1, 56):
                if file_num == 20 and sec_num == 55:
                    dep = "--"
                elif sec_num < 55:
                    dep = f"D00 T{file_num:02d} §{sec_num + 1}"
                else:
                    dep = f"D00 T{file_num + 1:02d} §1"
                rows.append((sec_num, f"S{sec_num}", 0, "none", dep))
            self.write(todo_file(rows, ident=f"file-{file_num:02d}"),
                       name=f"TODO-{file_num:02d}-chain.md")
        parsed = tg.graph(self.root)
        self.assertEqual(len(parsed), 1100)
        ordered_refs = [r.ref for r in tg.ordered(parsed)]
        self.assertEqual(len(ordered_refs), 1100)
        self.assertEqual(ordered_refs[0], "D00 T20 §55")
        self.assertEqual(ordered_refs[-1], "D00 T01 §1")


# The stamp tests build a git repository per test and make real commits: minutes, not seconds. They run in the full
# suite (CONCLAVE_FULL_TESTS=1), which is for a change to the stamp, the dispatcher or the pin loader and for a
# release. The quick suite still stamps a section end to end in tests/test_three_pass_install.py.
slow = unittest.skipUnless(os.environ.get("CONCLAVE_FULL_TESTS"), "slow: set CONCLAVE_FULL_TESTS=1 for the full suite")


@slow
class Stamp(Tree):
    def setUp(self):
        super().setUp()
        self.write(todo_file([(1, "A", 0, "none", "--"), (2, "B", 0, "owner-decision", "--")]).replace(
            "**Test checkpoint:**", STARTED + "**Test checkpoint:**", 1))
        report_path = self.root / "docs/reviews/00-workspace/D00-T01-s1.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text("# Review findings\n\n" + envelope(1), encoding="utf-8")
        (self.root / ".conclave").mkdir()
        (self.root / tg.PIN).write_text(self.PIN_TEXT, encoding="utf-8")
        for args in (["init", "-q"], ["config", "user.email", "t@example.com"],
                     ["config", "user.name", "T"], ["add", "-A"], ["commit", "-qm", "x"]):
            subprocess.run(["git", "-C", str(self.root), *args], check=True)
        self.sha = self.head()
        self.start = self.sha  # the commit that records §1's Started line: the build began here
        self.reviews = [{"round": 1, "report": "docs/reviews/00-workspace/D00-T01-s1.md",
                         "verdict": "clean"}]
        self.write_completion()
        self.write_plan()

    COMPLETION = "docs/reviews/00-workspace/D00-T01-s1-completion.md"
    PLAN = "docs/reviews/00-workspace/D00-T01-s1.md"  # the section's own findings file, beside its rounds
    PIN_TEXT = UNIFORM_PIN  # the pin the first commit holds; ThreePassStamp commits a three-pass one there

    @staticmethod
    def only(text, plans):
        """The findings file text with only its plan reviews (plans) or with every record but them, header kept."""
        head, *records = re.split(r"(?m)^(?=## (?:Round |Plan review))", text)
        return head + "".join(r for r in records if r.startswith("## Plan review") == plans)

    def head(self):
        return subprocess.run(["git", "-C", str(self.root), "rev-parse", "HEAD"],
                              capture_output=True, text=True).stdout.strip()

    def commit(self, message="more"):
        for args in (["add", "-A"], ["commit", "-q", "--allow-empty", "-m", message]):
            subprocess.run(["git", "-C", str(self.root), *args], check=True)
        return self.head()

    def write_plan(self, review="1. Controls: all present.\n\nHIGHEST: none\n\nPLAN: complete\n\nOVERALL: approve",
                   reviewer="astra", cli="codex", writer="claude", effort="medium", lenses=("plan",), candidate=None,
                   path=None, keep=False):
        """A plan review as scripts/review-dispatch.py --kind plan records it (keep: after the attempts already there;
        otherwise the earlier plan reviews are dropped and the file's rounds stay)."""
        target = self.root / (path or self.PLAN)
        target.parent.mkdir(parents=True, exist_ok=True)
        if not keep and target.exists():
            target.write_bytes(self.only(target.read_bytes().decode("utf-8"), plans=False).encode("utf-8"))
        result = {"writer": writer, "reviewer": reviewer, "model": "m", "cli": cli, "effort": effort,
                  "lenses": list(lenses), "failover": [] if reviewer else [{"reviewer": "astra", "reason": "exited 3"}],
                  "review": review if reviewer else None}
        tg.review_dispatch().record_completion(target, result, "2026-10-22T00:00:00Z", candidate or self.start,
                                               kind="plan")

    def write_completion(self, review="1. Open file: present.\n\nCOMPLETION: complete", notes="", reviewer="sol",
                         candidate=None, path=None, effort="medium", keep=False):
        """A completion review as scripts/review-dispatch.py --kind completion records it, then the writer's notes."""
        target = self.root / (path or self.COMPLETION)
        target.parent.mkdir(parents=True, exist_ok=True)
        if not keep:
            target.unlink(missing_ok=True)
        result = {"writer": "claude", "reviewer": reviewer, "model": "gpt-6.1-sol", "cli": "codex", "effort": effort,
                  "failover": [] if reviewer else [{"reviewer": "sol", "reason": "exited 3"}],
                  "review": review if reviewer else None}
        tg.review_dispatch().record_completion(target, result, "2026-10-23T00:00:00Z", candidate or self.sha)
        if notes:
            with open(target, "a", encoding="utf-8", newline="") as handle:
                handle.write("\n" + notes + "\n")

    def ensure_plan(self, ref="D00 T01 §1"):
        """The returned plan review back in the section's own findings file when a test rewrote that file for its
        rounds (or never wrote it), as the real file carries it beside them. A file holding any plan attempt, or one
        the dispatcher cannot read, is left as the test wrote it. Returns the file."""
        report = tg.section_findings(self.root, ref)
        target = self.root / report
        plans = tg.review_dispatch().read_plans(target.read_bytes().decode("utf-8")) if target.exists() else []
        if plans == []:
            self.write_plan(path=report, keep=True)
        return report

    def stamp(self, *args, completion=None, plan=None, **kwargs):
        """tg.stamp on this tree, with a clean completion review and the section's own plan review unless the test
        names others (see ensure_plan)."""
        if plan is None:
            plan = self.ensure_plan(args[0])
        return tg.stamp(self.root, *args, completion=completion or {"report": self.COMPLETION, "verdict": "complete"},
                        plan=plan, **kwargs)

    def test_a_kept_chain_is_refused_as_plan_or_completion_under_a_rotation_pin(self):
        # D00 T01 §9: a section's earlier chain, kept as -chain<k>.md by replan, is closed.
        self.tick_work()
        plan = self.ensure_plan("D00 T01 §1")
        chain_plan = plan.replace(".md", "-chain1.md")
        shutil.copyfile(self.root / plan, self.root / chain_plan)
        chain_completion = self.COMPLETION.replace("-completion.md", "-chain1.md")
        shutil.copyfile(self.root / self.COMPLETION, self.root / chain_completion)
        for kwargs in ({"plan": chain_plan}, {"completion": {"report": chain_completion, "verdict": "complete"}}):
            with self.subTest(next(iter(kwargs))):
                with self.assertRaises(tg.Refused) as ctx:
                    self.stamp("D00 T01 §1", self.sha, self.reviews, ["true -> ok"], "2026-10-23", **kwargs)
                self.assertIn("is a kept earlier review chain", str(ctx.exception))
        self.stamp("D00 T01 §1", self.sha, self.reviews, ["true -> ok"], "2026-10-23")  # the own files stamp

    def completion_refuses(self, completion, fragment):
        before = self.snapshot()
        with self.assertRaises(tg.Refused) as ctx:
            self.stamp("D00 T01 §1", self.sha, self.reviews, ["true -> ok"], "2026-10-23", completion=completion)
        self.assertIn(fragment, str(ctx.exception))
        self.assertEqual(self.snapshot(), before, "a refused stamp wrote something")

    def test_a_stamp_without_a_completion_review_refuses(self):
        self.tick_work()
        before = self.snapshot()
        with self.assertRaises(tg.Refused) as ctx:
            tg.stamp(self.root, "D00 T01 §1", self.sha, self.reviews, ["true -> ok"], "2026-10-23")
        self.assertIn("--completion '<findings file>:<complete|completed|filed|reconciled>' is required",
                      str(ctx.exception))
        self.assertEqual(self.snapshot(), before)

    def test_an_unknown_completion_verdict_refuses(self):
        self.tick_work()
        for verdict in ("done", "gaps", "Complete", ""):
            with self.subTest(verdict=verdict):
                self.completion_refuses({"report": self.COMPLETION, "verdict": verdict},
                                        "--completion verdict must be one of complete, completed, filed")

    def test_a_findings_file_without_a_completion_review_refuses(self):
        self.tick_work()
        self.completion_refuses({"report": "docs/reviews/00-workspace/D00-T01-s1.md", "verdict": "complete"},
                                "holds no ## Completion review")
        self.completion_refuses({"report": "docs/reviews/00-workspace/none.md", "verdict": "complete"},
                                "missing or empty review report")
        self.completion_refuses({"report": "../outside.md", "verdict": "complete"}, "invalid review report path")

    def test_a_completion_pass_that_returned_no_review_refuses(self):
        self.tick_work()
        self.write_completion(reviewer=None)
        self.completion_refuses({"report": self.COMPLETION, "verdict": "complete"},
                                "must hold exactly one completion review returned by another model family")
        self.write_completion(review="1. Open file: present.\n\nCOMPLETION: unsure")
        self.completion_refuses({"report": self.COMPLETION, "verdict": "complete"},
                                "must hold exactly one completion review returned by another model family")

    def test_the_completion_verdict_must_match_the_review(self):
        self.tick_work()
        self.write_completion(review="1. Ctrl+O: missing-in-scope.\n\nCOMPLETION: gaps")
        self.completion_refuses({"report": self.COMPLETION, "verdict": "complete"},
                                "completion verdict complete needs a review ending COMPLETION: complete")
        receipt = self.stamp("D00 T01 §1", self.sha, self.reviews, ["true -> ok"], "2026-10-23",
                             completion={"report": self.COMPLETION, "verdict": "completed"})
        data = json.loads((self.root / receipt).read_text(encoding="utf-8"))
        self.assertEqual(data["completion"], {"report": self.COMPLETION, "verdict": "completed", "candidate": self.sha,
                                              "reviewer": "sol", "model": "gpt-6.1-sol", "filed": []})
        self.assertEqual(tg.review_rounds(self.root)["sections"][0]["completion"], "completed")

    def test_query_sequence_prints_the_chain_and_the_filing_coupling(self):
        # D03 T01 §15: the CLI on a valid tree whose stamped section filed another, and a missing receipt refusing.
        self.tick_work()
        self.write_completion(review="1. Recent files: missing-out-of-scope.\n\nCOMPLETION: gaps",
                              notes="- Filed: D00 T01 §2 (recent files)")
        receipt = self.stamp("D00 T01 §1", self.sha, self.reviews, ["true -> ok"], "2026-10-23",
                             completion={"report": self.COMPLETION, "verdict": "filed"})
        shutil.copytree(SCRIPTS, self.root / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(tg.DISPATCHER.parent, self.root / "scripts", dirs_exist_ok=True,  # the reviewer kit beside it
                        ignore=shutil.ignore_patterns("__pycache__", "tests"))
        cli = [sys.executable, str(self.root / "scripts/todo-graph.py"), "query", "sequence"]
        result = subprocess.run(cli, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout.decode("utf-8")),
                         {"chain": ["D00 T01 §2"],
                          "couplings": [{"filer": "D00 T01 §1", "filed": "D00 T01 §2", "state": "blocked"}]})
        (self.root / receipt).unlink()
        result = subprocess.run(cli, capture_output=True)
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn(b"receipt", result.stderr)

    def test_a_reopened_adopted_section_stamps_through_the_kit(self):
        # D03 T01 §9: adopted, reopened by unstamp, then stamped the kit's way with a fresh receipt.
        path = self.root / "todo/00-workspace/TODO-01-a.md"
        text = path.read_text(encoding="utf-8").replace("| 1 | §1 | A | -- | [ ] |", "| 1 | §1 | A | -- | [x] |")
        text = text.replace("- [ ] Work.", "- [x] Work.", 1).replace("- [ ] Commit: `x: a`", "- [x] Commit: `x: a`")
        path.write_text(text.replace("\n## 2.", f"\n> **Verified:** 2026-09-28 | commit `{self.sha[:10]}` | ok\n\n## 2.", 1),
                        encoding="utf-8")
        self.commit("stamped under the project's own tooling")
        self.assertEqual([r for r, _ in tg.adopt_stamps(self.root)], ["D00 T01 §1"])
        self.assertTrue(tg.graph(self.root)["D00 T01 §1"].done)
        tg.unstamp(self.root, "D00 T01 §1", "reopened to take the kit's stamp", "2026-11-14")
        self.assertFalse(tg.graph(self.root)["D00 T01 §1"].done)
        sha = self.commit("reopened")
        self.write_completion(candidate=sha)
        receipt = self.stamp("D00 T01 §1", sha, self.reviews, ["true -> ok"], "2026-11-15")
        self.assertTrue((self.root / receipt).is_file())
        self.assertTrue(tg.graph(self.root)["D00 T01 §1"].done)

    def test_a_stamped_section_resolves_as_verified_under_have(self):
        # D03 T01 §10 (completion): --have changes nothing for a stamped row, whatever the session lacks.
        self.tick_work()
        self.stamp("D00 T01 §1", self.sha, self.reviews, ["true -> ok"], "2026-10-23")
        shutil.copytree(SCRIPTS, self.root / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(tg.DISPATCHER.parent, self.root / "scripts", dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__", "tests"))
        for have in ("", "auto", "windows-host"):
            with self.subTest(have=have):
                result = subprocess.run([sys.executable, str(self.root / "scripts/todo-graph.py"), "resolve",
                                         "D00 T01 §1", "--have", have], capture_output=True)
                self.assertEqual(result.returncode, 3, result.stderr)

    def test_filed_gaps_must_be_listed_and_must_resolve(self):
        self.tick_work()
        gaps = "1. Recent files: missing-out-of-scope.\n\nCOMPLETION: gaps"
        filed = {"report": self.COMPLETION, "verdict": "filed"}
        self.write_completion(review=gaps)
        self.completion_refuses(filed, "completion verdict filed needs each filed section listed")
        self.write_completion(review=gaps, notes="- Filed: D00 T09 §1 (recent files)")
        self.completion_refuses(filed, "completion gap filed as D00 T09 §1, which does not resolve")
        self.write_completion(review=gaps, notes="- Filed: D00 T01 §1 (itself)")
        self.completion_refuses(filed, "cannot file a completion gap to itself")
        self.write_completion(review=gaps, notes="- Filed: D00 T01 §2 (recent files)")
        self.completion_refuses({"report": self.COMPLETION, "verdict": "completed"},
                                "and only filed lists any")
        receipt = self.stamp("D00 T01 §1", self.sha, self.reviews, ["true -> ok"], "2026-10-23", completion=filed)
        data = json.loads((self.root / receipt).read_text(encoding="utf-8"))
        self.assertEqual((data["completion"]["verdict"], data["completion"]["filed"]), ("filed", ["D00 T01 §2"]))
        tg.graph(self.root)

    def test_a_filed_section_that_stops_resolving_refuses(self):
        other = self.root / "todo/00-workspace/TODO-02-b.md"
        other.write_text(todo_file([(1, "Recent files", 0, "none", "--")], ident="bravo"), encoding="utf-8")
        self.index("TODO-02-b.md")
        self.tick_work()
        self.write_completion(review="1. Recent files: missing-out-of-scope.\n\nCOMPLETION: gaps",
                              notes="- Filed: D00 T02 §1 (recent files)")
        self.stamp("D00 T01 §1", self.sha, self.reviews, ["true -> ok"], "2026-10-23",
                   completion={"report": self.COMPLETION, "verdict": "filed"})
        other.unlink()
        self.refuses("completion gap filed as D00 T02 §1, which does not resolve: D00 T01 §1")

    def test_the_completion_candidate_is_the_stamped_commit_or_before_it(self):
        self.tick_work()
        subprocess.run(["git", "-C", str(self.root), "commit", "-q", "--allow-empty", "-m", "later"], check=True)
        later = subprocess.run(["git", "-C", str(self.root), "rev-parse", "HEAD"], capture_output=True,
                               text=True).stdout.strip()
        self.write_completion(candidate=later)
        self.completion_refuses({"report": self.COMPLETION, "verdict": "complete"},
                                "is not the stamped commit or an ancestor of it")
        self.write_completion(candidate="f" * 40)
        self.completion_refuses({"report": self.COMPLETION, "verdict": "complete"}, "not a commit")

    def test_a_receipt_records_the_completion_review_and_edits_refuse(self):
        self.tick_work()
        receipt = self.root / self.stamp("D00 T01 §1", self.sha, self.reviews, ["true -> ok"], "2026-10-23")
        data = json.loads(receipt.read_text(encoding="utf-8"))
        self.assertEqual(data["completion"]["verdict"], "complete")
        for key, value in (("verdict", "completed"), ("filed", ["D00 T01 §2"]), ("reviewer", "astra")):
            with self.subTest(key=key):
                edited = json.loads(json.dumps(data))
                edited["completion"][key] = value
                receipt.write_text(json.dumps(edited), encoding="utf-8")
                with self.assertRaises(tg.Refused):
                    tg.graph(self.root)
        receipt.write_text(json.dumps(data), encoding="utf-8")
        tg.graph(self.root)
        # An edit inside the recorded completion review breaks its digest, so the receipt no longer validates.
        path = self.root / self.COMPLETION
        path.write_text(path.read_text(encoding="utf-8").replace("present", "absent"), encoding="utf-8")
        self.refuses("is not a findings file the dispatcher can read")

    def test_a_receipt_from_before_the_completion_review_still_validates(self):
        # Receipts stamped before 2026-10-23 carry no completion field (nor the later plan and schedule); once frozen,
        # their presence-free shape stays valid.
        self.tick_work()
        receipt = self.root / self.stamp("D00 T01 §1", self.sha, self.reviews, ["true -> ok"], "2026-10-23")
        data = json.loads(receipt.read_text(encoding="utf-8"))
        del data["completion"], data["plan"], data["schedule"]
        receipt.write_text(json.dumps(data), encoding="utf-8")
        (self.root / self.COMPLETION).unlink()
        self.refuses(tg.LEGACY_RECEIPTS)
        (self.root / tg.RECEIPTS / tg.LEGACY_RECEIPTS).write_text(json.dumps(
            {"schema_version": 1, "receipts": {}, "before_plan": {"D00 T01 §1": tg.receipt_digest(data)}}),
            encoding="utf-8")
        tg.graph(self.root)
        self.assertIsNone(tg.review_rounds(self.root)["sections"][0]["completion"])

    def tick_work(self):
        path = self.root / "todo/00-workspace/TODO-01-a.md"
        path.write_text(path.read_text(encoding="utf-8").replace("- [ ] Work.", "- [x] Work.", 1),
                        encoding="utf-8")

    def test_stamp_writes_receipt_and_validates(self):
        self.tick_work()
        receipt = self.stamp("D00 T01 §1", self.sha, self.reviews, ["true -> ok"], "2026-10-13")
        rows = tg.graph(self.root)
        self.assertTrue(rows["D00 T01 §1"].done)
        self.assertEqual(json.loads((self.root / receipt).read_text(encoding="utf-8"))
                         ["implementation_sha"], self.sha)

    def test_a_configured_waiting_need_holds_the_stamp_and_a_later_one_refuses_the_stamped_section(self):
        # D03 T01 §2: the stamp and the stamped-section check read the project's waiting Needs, both ways.
        path = self.root / "todo/00-workspace/TODO-01-a.md"
        path.write_text(path.read_text(encoding="utf-8").replace("**Needs:** none", "**Needs:** gpu", 1),
                        encoding="utf-8")
        plan = self.root / "todo/plan.json"
        needs = ["gpu", "owner-decision"]
        plan.write_text(json.dumps({"needs": needs, "waiting": ["gpu"]}), encoding="utf-8")
        self.tick_work()
        with self.assertRaises(tg.Refused) as ctx:
            self.stamp("D00 T01 §1", self.sha, self.reviews, ["true -> ok"], "2026-10-13")
        self.assertIn("still waiting on gpu: D00 T01 §1", str(ctx.exception))
        plan.write_text(json.dumps({"needs": needs, "waiting": ["owner-decision"]}), encoding="utf-8")
        receipt = self.stamp("D00 T01 §1", self.sha, self.reviews, ["true -> ok"], "2026-10-13")
        self.assertTrue(tg.graph(self.root)["D00 T01 §1"].done)
        self.assertEqual(json.loads((self.root / receipt).read_text(encoding="utf-8"))["implementation_sha"], self.sha)
        plan.write_text(json.dumps({"needs": needs, "waiting": ["gpu", "owner-decision"]}), encoding="utf-8")
        with self.assertRaises(tg.Refused) as ctx:
            tg.graph(self.root)
        self.assertIn("stamped section has a waiting Need: D00 T01 §1", str(ctx.exception))

    def test_receipt_records_rounds_spent_against_the_cap(self):
        self.tick_work()
        report = self.root / "docs/reviews/00-workspace/D00-T01-s1.md"
        report.write_text("# Review findings\n\n" + envelope(1, "none") + envelope(2, overall="needs-attention")
                          + envelope(3), encoding="utf-8")
        reviews = [{"round": 2, "report": "docs/reviews/00-workspace/D00-T01-s1.md", "verdict": "fixed"},
                   {"round": 3, "report": "docs/reviews/00-workspace/D00-T01-s1.md", "verdict": "clean"}]
        receipt = self.stamp("D00 T01 §1", self.sha, reviews, ["true -> ok"], "2026-10-13")
        data = json.loads((self.root / receipt).read_text(encoding="utf-8"))
        self.assertEqual((data["rounds_spent"], data["round_cap"]), (3, tg.REVIEW_ROUND_CAP))
        self.assertNotIn("cap_outcome", data)
        summary = tg.review_rounds(self.root)
        self.assertEqual(summary["sections"][0]["rounds_spent"], 3)
        self.assertEqual(summary["summary"]["stopped_at_cap"], 0)

    def record_rounds(self, last, report="docs/reviews/00-workspace/D00-T01-s1.md"):
        (self.root / report).write_text("".join(envelope(n, overall="needs-attention") for n in range(1, last + 1)),
                                        encoding="utf-8")
        self.ensure_plan()

    def test_the_cap_is_33_and_earlier_caps_stay_valid(self):
        # Owner decision 2026-10-23: the review-round cap moved from 22 to 33.
        self.assertEqual(tg.REVIEW_ROUND_CAP, 33)
        self.assertIn("stopped-at-33", tg.VERDICTS)
        for earlier in (22, 13, 8, 3):
            self.assertIn(f"stopped-at-{earlier}", tg.VERDICTS)
        self.assertEqual(tg.EARLIER_CAPS, {8, 13, 22})

    def test_a_receipt_written_under_the_22_round_cap_still_validates(self):
        self.tick_work()
        self.record_rounds(22)
        stopped = [{"round": 22, "report": "docs/reviews/00-workspace/D00-T01-s1.md", "verdict": "stopped-at-22"}]
        with self.assertRaises(tg.Refused):  # a new stamp stops only at the current cap
            self.stamp("D00 T01 §1", self.sha, stopped, ["true -> ok"], "2026-10-13", cap_outcome="filed")
        self.record_rounds(33)
        receipt = self.root / self.stamp("D00 T01 §1", self.sha, [
            {"round": 33, "report": "docs/reviews/00-workspace/D00-T01-s1.md", "verdict": "stopped-at-33"}],
            ["true -> ok"], "2026-10-13", cap_outcome="filed")
        # The same section as a receipt from the 22-round era: 22 rounds, stopped-at-22, round_cap 22.
        self.record_rounds(22)
        data = json.loads(receipt.read_text(encoding="utf-8"))
        data.update(reviews=stopped, rounds_spent=22, round_cap=22)
        receipt.write_text(json.dumps(data), encoding="utf-8")
        tg.graph(self.root)
        data["round_cap"] = 33  # but a 22-round stop is not a stop at the 33-round cap
        receipt.write_text(json.dumps(data), encoding="utf-8")
        self.refuses("must be stopped-at-33")

    def test_a_stopped_review_must_say_what_was_done(self):
        self.tick_work()
        cap = tg.REVIEW_ROUND_CAP
        self.record_rounds(cap)
        stopped = [{"round": cap, "report": "docs/reviews/00-workspace/D00-T01-s1.md", "verdict": f"stopped-at-{cap}"}]
        with self.assertRaises(tg.Refused) as ctx:
            self.stamp("D00 T01 §1", self.sha, stopped, ["true -> ok"], "2026-10-13")
        self.assertIn("--cap-outcome", str(ctx.exception))
        with self.assertRaises(tg.Refused):
            self.stamp("D00 T01 §1", self.sha, self.reviews, ["true -> ok"], "2026-10-13",
                     cap_outcome="nothing stopped")
        receipt = self.stamp("D00 T01 §1", self.sha, stopped, ["true -> ok"], "2026-10-13",
                           cap_outcome="filed two leftovers as D00 T01 §2")
        data = json.loads((self.root / receipt).read_text(encoding="utf-8"))
        self.assertEqual((data["rounds_spent"], data["cap_outcome"]), (cap, "filed two leftovers as D00 T01 §2"))
        self.assertEqual(tg.review_rounds(self.root)["summary"]["stopped_at_cap"], 1)
        # A receipt that drops the outcome no longer validates.
        del data["cap_outcome"]
        (self.root / receipt).write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(tg.Refused):
            tg.graph(self.root)

    def test_a_receipt_without_rounds_spent_holds_only_what_the_old_process_wrote(self):
        self.tick_work()
        receipt = self.root / self.stamp("D00 T01 §1", self.sha, self.reviews, ["true -> ok"], "2026-10-13")
        data = json.loads(receipt.read_text(encoding="utf-8"))
        del data["rounds_spent"], data["round_cap"], data["plan"], data["schedule"]
        receipt.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(tg.Refused) as ctx:  # the old shape alone does not make a receipt old
            tg.graph(self.root)
        self.assertIn(tg.LEGACY_RECEIPTS, str(ctx.exception))
        legacy = self.root / tg.RECEIPTS / tg.LEGACY_RECEIPTS
        legacy.write_text(json.dumps({"schema_version": 1, "receipts": {"D00 T01 §1": tg.receipt_digest(data)}}),
                          encoding="utf-8")
        tg.graph(self.root)  # a frozen old receipt still validates
        data["date"] = "2026-10-22"
        receipt.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(tg.Refused):  # and any change to it is no longer the frozen receipt
            tg.graph(self.root)
        report = "docs/reviews/00-workspace/D00-T01-s1.md"
        for rounds in ([{"round": 9, "report": report, "verdict": "stopped-low-severity"}],
                       [{"round": 1, "report": report, "verdict": "stopped-at-33"}]):
            data["reviews"] = rounds
            receipt.write_text(json.dumps(data), encoding="utf-8")
            with self.subTest(rounds=rounds), self.assertRaises(tg.Refused) as ctx:
                tg.graph(self.root)
            self.assertIn("without rounds_spent", str(ctx.exception))

    def test_a_loop_past_the_cap_refuses_even_when_it_ends_clean(self):
        self.tick_work()
        report = "docs/reviews/00-workspace/D00-T01-s1.md"
        last = tg.REVIEW_ROUND_CAP + 1
        (self.root / report).write_text("".join(envelope(n, overall="needs-attention") for n in range(1, last))
                                        + envelope(last), encoding="utf-8")
        with self.assertRaises(tg.Refused) as ctx:
            self.stamp("D00 T01 §1", self.sha, [{"round": last, "report": report, "verdict": "clean"}],
                     ["true -> ok"], "2026-10-13")
        self.assertIn(f"over the {tg.REVIEW_ROUND_CAP}-round cap", str(ctx.exception))

    def test_a_repeated_round_number_refuses(self):
        self.tick_work()
        report = "docs/reviews/00-workspace/D00-T01-s1.md"
        (self.root / report).write_text("".join(envelope(1, overall="needs-attention") for _ in range(3))
                                        + envelope(1), encoding="utf-8")
        with self.assertRaises(tg.Refused) as ctx:
            self.stamp("D00 T01 §1", self.sha, self.reviews, ["true -> ok"], "2026-10-13")
        self.assertIn("must number its rounds 1 to 4 in order", str(ctx.exception))

    def test_a_loop_whose_last_round_returned_no_review_refuses(self):
        self.tick_work()
        report = "docs/reviews/00-workspace/D00-T01-s1.md"
        (self.root / report).write_text(envelope(1) + envelope(2, "none", overall="blocked"), encoding="utf-8")
        with self.assertRaises(tg.Refused) as ctx:  # round 2 ran after the approval and returned nothing
            self.stamp("D00 T01 §1", self.sha, self.reviews, ["true -> ok"], "2026-10-13")
        self.assertIn("ends with round 2, which returned no review", str(ctx.exception))

    def test_rounds_spent_must_be_what_the_findings_files_record(self):
        self.tick_work()
        receipt = self.root / self.stamp("D00 T01 §1", self.sha, self.reviews, ["true -> ok"], "2026-10-13")
        data = json.loads(receipt.read_text(encoding="utf-8"))
        data["rounds_spent"] = 999
        receipt.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(tg.Refused) as ctx:
            tg.graph(self.root)
        self.assertIn("receipt rounds_spent 999 is not the 1 rounds", str(ctx.exception))

    def test_a_receipt_names_a_cap_the_process_has_used(self):
        self.tick_work()
        receipt = self.root / self.stamp("D00 T01 §1", self.sha, self.reviews, ["true -> ok"], "2026-10-13")
        data = json.loads(receipt.read_text(encoding="utf-8"))
        data["round_cap"] = 50
        receipt.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(tg.Refused) as ctx:
            tg.graph(self.root)
        self.assertIn("round_cap is invalid", str(ctx.exception))

    def test_a_review_with_carriage_returns_is_read_as_the_dispatcher_wrote_it(self):
        self.tick_work()
        dispatch = tg.review_dispatch()
        review = ["Captured progress: 10%\rCaptured progress: 100%", "Example heading:", "## Round 999: none",
                  "OVERALL: approve"]
        text = ("## Round 1: astra (`m` via `codex`)\n\n- Writer: claude\n- Run: 2026-10-21T00:00:00Z\n"
                "- Effort: low\n- Lenses: adversarial\n"
                f"- Lines: 4\n- Digest: {dispatch.digest(review)}\n\n" + "\n".join(review) + "\n")
        (self.root / "docs/reviews/00-workspace/D00-T01-s1.md").write_bytes(text.encode("utf-8"))
        self.assertIsNotNone(dispatch.read_rounds(text))
        receipt = self.stamp("D00 T01 §1", self.sha, self.reviews, ["true -> ok"], "2026-10-13")
        self.assertEqual(json.loads((self.root / receipt).read_text(encoding="utf-8"))["rounds_spent"], 1)
        tg.graph(self.root)

    def test_a_round_verdict_must_match_its_review(self):
        self.tick_work()
        report = self.root / "docs/reviews/00-workspace/D00-T01-s1.md"
        before = self.snapshot()
        report.write_text(envelope(1, overall="needs-attention"), encoding="utf-8")
        with self.assertRaises(tg.Refused) as ctx:  # a rejecting review claimed as clean
            self.stamp("D00 T01 §1", self.sha, self.reviews, ["true -> ok"], "2026-10-13")
        self.assertIn("verdict matching clean", str(ctx.exception))
        fixed_only = [{"round": 1, "report": "docs/reviews/00-workspace/D00-T01-s1.md", "verdict": "fixed"}]
        with self.assertRaises(tg.Refused) as ctx:  # fixed, but no later round saw the fixes
            self.stamp("D00 T01 §1", self.sha, fixed_only, ["true -> ok"], "2026-10-13")
        self.assertIn("must end at its last reviewed round", str(ctx.exception))
        report.write_text(envelope(1), encoding="utf-8")
        with self.assertRaises(tg.Refused):  # an approving review claimed as fixed
            self.stamp("D00 T01 §1", self.sha,
                     fixed_only + [{"round": 1, "report": "docs/reviews/00-workspace/D00-T01-s1.md", "verdict": "clean"}],
                     ["true -> ok"], "2026-10-13")
        report.unlink()
        self.assertEqual({k: v for k, v in self.snapshot().items() if not k.endswith("D00-T01-s1.md")},
                         {k: v for k, v in before.items() if not k.endswith("D00-T01-s1.md")})

    def test_a_loop_ends_at_its_last_reviewed_round(self):
        self.tick_work()
        report = "docs/reviews/00-workspace/D00-T01-s1.md"
        (self.root / report).write_text(envelope(1) + envelope(2, overall="needs-attention"), encoding="utf-8")
        before = self.snapshot()
        for claimed in ([{"round": 1, "report": report, "verdict": "clean"}, {"round": 2, "report": report, "verdict": "fixed"}],
                        [{"round": 1, "report": report, "verdict": "clean"}]):
            with self.assertRaises(tg.Refused) as ctx:  # a later failing review cannot be left behind an approval
                self.stamp("D00 T01 §1", self.sha, claimed, ["true -> ok"], "2026-10-13")
            self.assertIn("must end at its last reviewed round (2)", str(ctx.exception))
        self.assertEqual(self.snapshot(), before)

    def test_a_severity_stop_with_a_p1_or_p2_finding_refuses(self):
        self.tick_work()
        report = "docs/reviews/00-workspace/D00-T01-s1.md"
        last = tg.SEVERITY_CUTOFF_ROUND + 1
        for finding in ("1. **P1: unresolved unsafe stamp.**\n\nHIGHEST: P1", "1. **P2: narrow.**\n\nHIGHEST: P2",
                        "- `x.py:1`: an untagged, unnumbered finding.", "1. **P3: fine.**\n\nHIGHEST: none",
                        "1. **P3: fine.**\nHIGHEST: P3\n2. a later line."):
            (self.root / report).write_text(
                "".join(envelope(n, overall="needs-attention") for n in range(1, last)) + envelope(last).replace(
                    "Review text.\n\nOVERALL: approve", f"{finding}\n\nOVERALL: needs-attention"),
                encoding="utf-8")
            with self.assertRaises(tg.Refused) as ctx:
                self.stamp("D00 T01 §1", self.sha,
                         [{"round": last, "report": report, "verdict": "stopped-low-severity"}], ["true -> ok"],
                         "2026-10-13", cap_outcome="filed")
            self.assertIn("does not declare HIGHEST: P3", str(ctx.exception))

    def test_a_round_heading_quoted_inside_a_review_is_not_counted(self):
        self.tick_work()
        (self.root / "docs/reviews/00-workspace/D00-T01-s1.md").write_text(
            "## Round 1: astra (`m` via `codex`)\n\n- Writer: claude\n- Run: 2026-10-21T00:00:00Z\n- Effort: low\n"
            "- Lenses: adversarial\n- Lines: 2\n\n"
            "## Round 999: none\nOVERALL: approve\n", encoding="utf-8")
        receipt = self.stamp("D00 T01 §1", self.sha, self.reviews, ["true -> ok"], "2026-10-13")
        self.assertEqual(json.loads((self.root / receipt).read_text(encoding="utf-8"))["rounds_spent"], 1)

    def test_rounds_spent_add_up_across_review_loops(self):
        self.tick_work()
        first = self.root / "docs/reviews/00-workspace/D00-T01-s1.md"
        cap = tg.REVIEW_ROUND_CAP
        first.write_text("".join(envelope(n, overall="needs-attention") for n in range(1, cap + 1)), encoding="utf-8")
        second = self.root / "docs/reviews/00-workspace/D00-T01-s1-loop2.md"
        second.write_text(envelope(1) + envelope(2), encoding="utf-8")
        reviews = [{"round": cap, "report": "docs/reviews/00-workspace/D00-T01-s1.md", "verdict": f"stopped-at-{cap}"},
                   {"round": 2, "report": "docs/reviews/00-workspace/D00-T01-s1-loop2.md", "verdict": "clean"}]
        receipt = self.stamp("D00 T01 §1", self.sha, reviews, ["true -> ok"], "2026-10-13",
                           cap_outcome="loop 1 hit the cap; the repair was filed and a second loop ran clean")
        self.assertEqual(json.loads((self.root / receipt).read_text(encoding="utf-8"))["rounds_spent"], cap + 2)

    def test_a_severity_stop_records_its_outcome(self):
        self.tick_work()
        self.record_rounds(tg.SEVERITY_CUTOFF_ROUND + 1)
        report = self.root / "docs/reviews/00-workspace/D00-T01-s1.md"
        report.write_text(report.read_text(encoding="utf-8").rsplit("OVERALL: needs-attention", 1)[0]
                          + "HIGHEST: P3\n\nOVERALL: needs-attention\n\n", encoding="utf-8")
        low =[{"round": tg.SEVERITY_CUTOFF_ROUND + 1, "report": "docs/reviews/00-workspace/D00-T01-s1.md",
                "verdict": "stopped-low-severity"}]
        with self.assertRaises(tg.Refused):
            self.stamp("D00 T01 §1", self.sha, low, ["true -> ok"], "2026-10-13")
        receipt = self.stamp("D00 T01 §1", self.sha, low, ["true -> ok"], "2026-10-13",
                           cap_outcome="round 9 had two P3 findings, filed as D00 T01 §2")
        data = json.loads((self.root / receipt).read_text(encoding="utf-8"))
        self.assertEqual(data["cap_outcome"], "round 9 had two P3 findings, filed as D00 T01 §2")
        summary = tg.review_rounds(self.root)["summary"]
        self.assertEqual((summary["stopped_low_severity"], summary["stopped_at_cap"]), (1, 0))

    def test_a_cap_stop_must_be_the_current_cap_reached(self):
        self.tick_work()
        self.record_rounds(tg.REVIEW_ROUND_CAP)
        before = self.snapshot()
        for n, verdict in ((1, f"stopped-at-{tg.REVIEW_ROUND_CAP}"), (3, "stopped-at-3"), (13, "stopped-at-13")):
            early = [{"round": n, "report": "docs/reviews/00-workspace/D00-T01-s1.md", "verdict": verdict}]
            with self.assertRaises(tg.Refused) as ctx:
                self.stamp("D00 T01 §1", self.sha, early, ["true -> ok"], "2026-10-13", cap_outcome="filed")
            self.assertRegex(str(ctx.exception), f"must be stopped-at-{tg.REVIEW_ROUND_CAP}|"
                                                 f"a cap stop is the round that returns review {tg.REVIEW_ROUND_CAP}")
        self.assertEqual(self.snapshot(), before)

    def test_a_severity_stop_with_only_p3_findings_stamps(self):
        self.tick_work()
        report = "docs/reviews/00-workspace/D00-T01-s1.md"
        last = tg.SEVERITY_CUTOFF_ROUND + 1
        (self.root / report).write_text(
            "".join(envelope(n, overall="needs-attention") for n in range(1, last)) + envelope(last).replace(
                "Review text.\n\nOVERALL: approve", "1. **P3: wording.**\n2. **P3: the comment describing P1 findings.**\n\nHIGHEST: P3\n\nOVERALL: needs-attention"),
            encoding="utf-8")
        self.stamp("D00 T01 §1", self.sha, [{"round": last, "report": report, "verdict": "stopped-low-severity"}],
                 ["true -> ok"], "2026-10-13", cap_outcome="two P3 findings filed")

    def test_outage_rounds_do_not_earn_a_stop(self):
        self.tick_work()
        report = "docs/reviews/00-workspace/D00-T01-s1.md"
        # At the live cutoff of 0 any returned review may stop; outages count toward no cutoff, which shows at 3.
        with mock.patch.object(tg, "SEVERITY_CUTOFF_ROUND", 3):
            last = 4
            (self.root / report).write_text(
                "".join(envelope(n, "none") for n in range(1, last)) + envelope(last).replace(
                    "Review text.\n\nOVERALL: approve", "1. **P3: wording.**\n\nHIGHEST: P3\n\nOVERALL: needs-attention"), encoding="utf-8")
            with self.assertRaises(tg.Refused) as ctx:
                self.stamp("D00 T01 §1", self.sha, [{"round": last, "report": report, "verdict": "stopped-low-severity"}],
                         ["true -> ok"], "2026-10-13", cap_outcome="filed")
            self.assertIn("follows only 1 returned reviews", str(ctx.exception))
        cap = tg.REVIEW_ROUND_CAP
        (self.root / report).write_text(envelope(1, "none") + "".join(
            envelope(n, overall="needs-attention") for n in range(2, cap + 1)), encoding="utf-8")
        with self.assertRaises(tg.Refused) as ctx:
            self.stamp("D00 T01 §1", self.sha, [{"round": cap, "report": report, "verdict": f"stopped-at-{cap}"}],
                     ["true -> ok"], "2026-10-13", cap_outcome="filed")
        self.assertIn("a cap stop is the round that returns review", str(ctx.exception))
        # Blocked or empty replies are not returned reviews either (at the cutoff of 3, as above).
        cutoff = mock.patch.object(tg, "SEVERITY_CUTOFF_ROUND", 3)
        cutoff.start()
        self.addCleanup(cutoff.stop)
        for filler in (envelope(1).replace("OVERALL: approve", "OVERALL: blocked"), envelope(1).replace("OVERALL: approve", ""),
                       envelope(1, "claude (`claude-opus-5` via `claude`)", overall="needs-attention")):
            (self.root / report).write_text("".join(filler.replace("## Round 1:", f"## Round {n}:") for n in range(1, last))
                                            + envelope(last).replace("Review text.\n\nOVERALL: approve",
                                                                     "1. **P3: wording.**\n\nHIGHEST: P3\n\nOVERALL: needs-attention"),
                                            encoding="utf-8")
            with self.assertRaises(tg.Refused) as ctx:
                self.stamp("D00 T01 §1", self.sha,
                         [{"round": last, "report": report, "verdict": "stopped-low-severity"}],
                         ["true -> ok"], "2026-10-13", cap_outcome="filed")
            self.assertIn("follows only 1 returned reviews", str(ctx.exception))
        # An outage before the cap moves the cap stop to the round that returns the cap's last review.
        (self.root / report).write_text(envelope(1, "none") + "".join(
            envelope(n, overall="needs-attention") for n in range(2, cap + 2)), encoding="utf-8")
        self.stamp("D00 T01 §1", self.sha, [{"round": cap + 1, "report": report, "verdict": f"stopped-at-{cap}"}],
                 ["true -> ok"], "2026-10-13", cap_outcome="filed")

    def test_a_severity_stop_before_the_cutoff_refuses(self):
        # The live cutoff is 0, so no round comes before it; the refusal is checked at the
        # earlier cutoff of 3, which a later decision could restore.
        with mock.patch.object(tg, "SEVERITY_CUTOFF_ROUND", 3):
            self.tick_work()
            self.record_rounds(3)
            before = self.snapshot()
            for n in (1, 3):
                early = [{"round": n, "report": "docs/reviews/00-workspace/D00-T01-s1.md",
                          "verdict": "stopped-low-severity"}]
                with self.assertRaises(tg.Refused) as ctx:
                    self.stamp("D00 T01 §1", self.sha, early, ["true -> ok"], "2026-10-13", cap_outcome="filed")
                self.assertIn("only after round 3", str(ctx.exception))
            self.assertEqual(self.snapshot(), before)

    def test_the_live_cutoff_stops_on_the_first_p3_round(self):
        self.assertEqual(tg.SEVERITY_CUTOFF_ROUND, 0)

    def test_a_claimed_round_must_be_a_reviewed_round_in_its_report(self):
        self.tick_work()
        report = self.root / "docs/reviews/00-workspace/D00-T01-s1.md"
        before = self.snapshot()
        for text in ("# No independent review has run\n", envelope(1, "none"), envelope(2),
                     envelope(1, "claude (`claude-opus-5` via `claude`)"),
                     envelope(1).replace("- Writer: claude", "- Writer: codex"),
                     envelope(1).replace("- Writer: claude", "- Writer: someone"),
                     envelope(1).replace("OVERALL: approve", "OVERALL: blocked"),
                     envelope(1).replace("OVERALL: approve", ""),
                     "## Round 1: astra (`m` via `codex`)\n\n- Writer: claude\n- Run: 2026-10-21T00:00:00Z\n- Lines: 0\n",
                     "## Round 1: fake\n\nNo reviewer returned a review.\n",
                     "## Round 1: astra (`m` via `codex`)\n\nNo metadata block.\n"):
            report.write_text(text, encoding="utf-8")
            with self.assertRaises(tg.Refused) as ctx:
                self.stamp("D00 T01 §1", self.sha, self.reviews, ["true -> ok"], "2026-10-13")
            self.assertRegex(str(ctx.exception), "is not a review returned by another model family|"
                                                 "is not a findings file the dispatcher can read|holds no returned review|"
                                                 "must number its rounds")
        for bad in (0, -1, True):
            with self.assertRaises(tg.Refused):
                self.stamp("D00 T01 §1", self.sha,
                         [{"round": bad, "report": "docs/reviews/00-workspace/D00-T01-s1.md", "verdict": "clean"}],
                         ["true -> ok"], "2026-10-13")
        report.write_text("# Review findings\n\n" + envelope(1), encoding="utf-8")
        receipt = self.stamp("D00 T01 §1", self.sha, self.reviews, ["true -> ok"], "2026-10-13")
        # A receipt edited to claim a round its report never recorded no longer validates.
        data = json.loads((self.root / receipt).read_text(encoding="utf-8"))
        data["reviews"][0]["round"] = 999
        data["rounds_spent"] = 999
        (self.root / receipt).write_text(json.dumps(data), encoding="utf-8")
        self.refuses("round 999 is not a review returned by another model family")

    def test_a_stamped_section_with_a_waiting_need_refuses(self):
        self.tick_work()
        self.stamp("D00 T01 §1", self.sha, self.reviews, ["true -> ok"], "2026-10-13")
        path = self.root / "todo/00-workspace/TODO-01-a.md"
        path.write_text(path.read_text(encoding="utf-8").replace("**Needs:** none", "**Needs:** owner-decision", 1),
                        encoding="utf-8")
        self.refuses("stamped section has a waiting Need")

    def test_stale_deferral_refuses_when_owner_stamps(self):
        self.tick_work()
        path = self.root / "todo/00-workspace/TODO-01-a.md"
        text = path.read_text(encoding="utf-8")
        target = "## 2. B\n"
        path.write_text(text.replace(target, target + "\n> **Deferred:** wait on 1 -> XREF: §1\n"),
                        encoding="utf-8")
        with self.assertRaises(tg.Refused) as ctx:
            self.stamp("D00 T01 §1", self.sha, self.reviews, ["true -> ok"], "2026-10-13")
        self.assertIn("stale deferral", str(ctx.exception))

    def test_unticked_items_refuse(self):
        with self.assertRaises(tg.Refused) as ctx:
            self.stamp("D00 T01 §1", self.sha, self.reviews, ["true -> ok"], "2026-10-13")
        self.assertIn("unticked", str(ctx.exception))

    def test_two_sections_stamped_on_one_commit_and_pin_ask_git_each_question_once(self):
        # D03 T01 §12 (completion): the success path, both stamps valid and sharing their commit and pin.
        path = self.root / "todo/00-workspace/TODO-01-a.md"
        text = path.read_text(encoding="utf-8").replace("**Needs:** owner-decision", "**Needs:** none")
        text = text.replace("- [ ] Work.", "- [x] Work.").replace(
            "**Test checkpoint:** `true` exits 0.\n\n## Verification", STARTED + "**Test checkpoint:** `true` exits 0."
            "\n\n## Verification")
        path.write_text(text, encoding="utf-8")
        starts = {1: self.start}  # §1 started in the first commit, §2 in this one
        self.sha = starts[2] = self.commit("§2 started")
        for n in (1, 2):
            self.start = starts[n]  # the candidate the section's plan review is recorded on
            report = f"docs/reviews/00-workspace/D00-T01-s{n}.md"
            (self.root / report).write_text("# Review findings\n\n" + envelope(1), encoding="utf-8")
            completion = f"docs/reviews/00-workspace/D00-T01-s{n}-completion.md"
            self.write_completion(path=completion, candidate=self.sha)
            self.stamp(f"D00 T01 §{n}", self.sha, [{"round": 1, "report": report, "verdict": "clean"}],
                       ["true -> ok"], "2026-10-23", completion={"report": completion, "verdict": "complete"})
        real, calls = subprocess.run, []

        def spy(argv, *a, **k):
            if argv[:1] == ["git"]:
                calls.append(tuple(argv[3:]))
            return real(argv, *a, **k)

        with mock.patch.object(tg.subprocess, "run", spy):
            cached = tg.graph(self.root)
        fast = list(calls)
        calls.clear()
        with mock.patch.object(tg.subprocess, "run", spy), mock.patch.object(tg, "CACHE_RUNS", False):
            uncached = tg.graph(self.root)
        self.assertEqual(cached, uncached)
        self.assertTrue(cached["D00 T01 §1"].done and cached["D00 T01 §2"].done)
        self.assertEqual(len(fast), len(set(fast)), fast)  # each distinct question once
        self.assertGreater(len(calls), len(set(calls)), "the shared commit and pin are asked about twice uncached")
        self.assertLess(len(fast), len(calls))

    def test_waiting_section_cannot_be_stamped(self):
        with self.assertRaises(tg.Refused):
            self.stamp("D00 T01 §2", self.sha, self.reviews, ["true -> ok"], "2026-10-13")

    def test_unknown_commit_refuses(self):
        self.tick_work()
        with self.assertRaises(tg.Refused):
            self.stamp("D00 T01 §1", "0" * 40, self.reviews, ["true -> ok"], "2026-10-13")

    def test_no_review_round_refuses(self):
        self.tick_work()
        with self.assertRaises(tg.Refused):
            self.stamp("D00 T01 §1", self.sha, [], ["true -> ok"], "2026-10-13")

    def test_missing_review_report_refuses(self):
        self.tick_work()
        for bad_path in (r"\Users\outside.md", "../outside.md", "docs/reviews/../outside.md", "outside.md"):
            bad_round = [{"round": 1, "report": bad_path, "verdict": "clean"}]
            with self.assertRaises(tg.Refused) as ctx:
                self.stamp("D00 T01 §1", self.sha, bad_round, ["true -> ok"], "2026-10-13")
            self.assertIn("invalid review report path", str(ctx.exception))
        missing = [{"round": 1, "report": "docs/reviews/00-workspace/missing.md", "verdict": "clean"}]
        with self.assertRaises(tg.Refused) as ctx:
            self.stamp("D00 T01 §1", self.sha, missing, ["true -> ok"], "2026-10-13")
        self.assertIn("missing or empty review report", str(ctx.exception))
        self.stamp("D00 T01 §1", self.sha, self.reviews, ["true -> ok"], "2026-10-13")
        (self.root / "docs/reviews/00-workspace/D00-T01-s1.md").unlink()
        self.refuses("missing or empty review report")

    def test_receipt_for_another_commit_refuses(self):
        self.tick_work()
        receipt = self.stamp("D00 T01 §1", self.sha, self.reviews, ["true -> ok"], "2026-10-13")
        data = json.loads((self.root / receipt).read_text(encoding="utf-8"))
        data["implementation_sha"] = "f" * 40
        (self.root / receipt).write_text(json.dumps(data), encoding="utf-8")
        self.refuses("receipt does not match its stamp")

    def test_matching_fabricated_sha_in_stamp_and_receipt_refuses(self):
        self.tick_work()
        receipt = self.stamp("D00 T01 §1", self.sha, self.reviews, ["true -> ok"], "2026-10-13")
        fake_sha = "0" * 40
        todo_path = self.root / "todo/00-workspace/TODO-01-a.md"
        todo_path.write_text(todo_path.read_text(encoding="utf-8").replace(self.sha, fake_sha),
                             encoding="utf-8")
        receipt_path = self.root / receipt
        receipt_path.write_text(receipt_path.read_text(encoding="utf-8").replace(self.sha, fake_sha),
                                encoding="utf-8")
        self.refuses("not a commit")

    def snapshot(self):
        self.ensure_plan()  # the fixture's plan review is put back before, not during, a refused stamp
        return {str(f.relative_to(self.root)): f.read_bytes()
                for f in self.root.rglob("*") if f.is_file() and ".git" not in f.parts}

    def test_bad_verdict_writes_nothing(self):
        self.tick_work()
        before = self.snapshot()
        bad = [{"round": 1, "report": "docs/reviews/00-workspace/D00-T01-s1.md", "verdict": "cleen"}]
        with self.assertRaises(tg.Refused):
            self.stamp("D00 T01 §1", self.sha, bad, ["true -> ok"], "2026-10-13")
        self.assertEqual(self.snapshot(), before)
        tg.graph(self.root)

    def test_bad_date_writes_nothing(self):
        self.tick_work()
        before = self.snapshot()
        with self.assertRaises(tg.Refused):
            self.stamp("D00 T01 §1", self.sha, self.reviews, ["true -> ok"], "13 Oct")
        self.assertEqual(self.snapshot(), before)

    def test_failed_stamp_write_rolls_back_receipt_and_allows_retry(self):
        self.tick_work()
        tg.projections(self.root, sync=True)
        before = self.snapshot()
        real_atomic = tg.atomic
        for fail_at in (2, 3):
            calls = []

            def fail_on_nth_write(path, data, target=fail_at):
                calls.append(path)
                if len(calls) == target:
                    raise OSError("simulated disk write failure")
                return real_atomic(path, data)

            tg.atomic = fail_on_nth_write
            try:
                with self.assertRaises(OSError):
                    self.stamp("D00 T01 §1", self.sha, self.reviews, ["true -> ok"],
                             "2026-10-13", sync_plan=True)
            finally:
                tg.atomic = real_atomic
            self.assertEqual(len(calls), 4 if fail_at == 3 else 2)
            self.assertFalse((self.root / "docs/reviews/d00-t01-s1.json").exists())
            self.assertEqual(self.snapshot(), before)
        receipt = self.stamp("D00 T01 §1", self.sha, self.reviews, ["true -> ok"],
                           "2026-10-13", sync_plan=True)
        self.assertTrue((self.root / receipt).is_file())
        tg.projections(self.root)

    def test_a_failed_write_of_a_configured_plan_rolls_the_stamp_back(self):
        # D03 T01 §7: the stamp writes and rolls back the plan at todo/plan.json's layout.plan.
        (self.root / "todo/plan.json").write_text('{"layout": {"plan": "docs/plan.md"}}\n', encoding="utf-8")
        self.tick_work()
        tg.projections(self.root, sync=True)
        plan = self.root / "docs/plan.md"
        before = self.snapshot()
        real_atomic = tg.atomic

        def fail_on_the_plan(path, data):
            if pathlib.Path(path) == plan:
                raise OSError("simulated disk write failure")
            return real_atomic(path, data)

        tg.atomic = fail_on_the_plan
        try:
            with self.assertRaises(OSError):
                self.stamp("D00 T01 §1", self.sha, self.reviews, ["true -> ok"], "2026-10-13", sync_plan=True)
        finally:
            tg.atomic = real_atomic
        self.assertEqual(self.snapshot(), before, "the TODO file, the receipts and the plan are as they were")
        self.stamp("D00 T01 §1", self.sha, self.reviews, ["true -> ok"], "2026-10-13", sync_plan=True)
        self.assertRegex(plan.read_text(encoding="utf-8"), r"\| \[x\] +\| D00 T01 §1 ")
        self.assertFalse((self.root / tg.PLAN).exists(), "nothing at the default path")

    def test_an_interrupted_stamp_rolls_back_and_allows_retry(self):
        self.tick_work()
        tg.projections(self.root, sync=True)
        before = self.snapshot()
        real_atomic = tg.atomic
        calls = []

        def interrupt_on_second_write(path, data):
            calls.append(path)
            if len(calls) == 2:
                raise KeyboardInterrupt
            return real_atomic(path, data)

        tg.atomic = interrupt_on_second_write
        try:
            with self.assertRaises(KeyboardInterrupt):
                self.stamp("D00 T01 §1", self.sha, self.reviews, ["true -> ok"], "2026-10-13", sync_plan=True)
        finally:
            tg.atomic = real_atomic
        self.assertEqual(self.snapshot(), before)
        self.stamp("D00 T01 §1", self.sha, self.reviews, ["true -> ok"], "2026-10-13", sync_plan=True)

    TODO_A = "todo/00-workspace/TODO-01-a.md"

    def two_rounds(self):
        """The findings file holds a needs-attention round 2 and a clean round 3; returns the two-round claim."""
        report = "docs/reviews/00-workspace/D00-T01-s1.md"
        (self.root / report).write_text("# Review findings\n\n" + envelope(1, "none") + envelope(2, overall="needs-attention")
                                        + envelope(3), encoding="utf-8")
        return [{"round": 2, "report": report, "verdict": "fixed"}, {"round": 3, "report": report, "verdict": "clean"}]

    def cut_short(self, keep_todo, reviews=None):
        """A real stamp, then the files put back as a process killed between its writes leaves them: the receipt kept
        and the plan (and, unless keep_todo, the TODO file) as they were before. Returns the receipt path, its bytes
        and the plan and TODO bytes before and after the stamp."""
        self.tick_work()
        self.ensure_plan()
        tg.projections(self.root, sync=True)
        todo, plan = self.root / self.TODO_A, self.root / tg.PLAN
        todo_before, plan_before = todo.read_bytes(), plan.read_bytes()
        receipt = self.stamp("D00 T01 §1", self.sha, reviews or self.reviews, ["true -> ok"], "2026-10-13", sync_plan=True)
        held = (self.root / receipt).read_bytes()
        todo_after = todo.read_bytes()
        plan.write_bytes(plan_before)
        if not keep_todo:
            todo.write_bytes(todo_before)
        return receipt, held, todo_before, todo_after, plan_before

    def retry(self, **kwargs):
        args = dict(sha=self.sha, reviews=self.reviews)
        args.update(kwargs)
        return self.stamp("D00 T01 §1", args["sha"], args["reviews"], ["true -> ok"], "2026-10-14", sync_plan=True)

    def test_a_stamp_killed_after_its_receipt_is_completed_by_the_same_retry(self):
        receipt, held, todo_before, todo_after, _ = self.cut_short(keep_todo=False)
        self.assertEqual(self.retry(), receipt)
        self.assertTrue(tg.graph(self.root)["D00 T01 §1"].done)
        self.assertIn("> **Verified:** 2026-10-14 | §1 | " + self.sha,
                      (self.root / self.TODO_A).read_text(encoding="utf-8"))
        tg.projections(self.root)

    def test_a_leftover_receipt_of_another_request_refuses_and_stays_as_it_was(self):
        receipt, held, todo_before, _, plan_before = self.cut_short(keep_todo=False)
        other = self.commit("later work")
        before = self.snapshot()
        with self.assertRaises(tg.Refused) as ctx:
            self.retry(sha=other)
        self.assertIn(receipt, str(ctx.exception))
        self.assertIn("commit", str(ctx.exception))
        self.assertEqual((self.root / receipt).read_bytes(), held)
        self.assertEqual(self.snapshot(), before, "a refused retry wrote something")

    def test_a_retry_whose_write_fails_puts_the_leftover_receipt_back(self):
        receipt, held, *_ = self.cut_short(keep_todo=False)
        before = self.snapshot()
        real_atomic = tg.atomic
        calls = []

        def fail_on_todo_write(path, data):
            calls.append(path)
            if len(calls) == 2:
                raise OSError("simulated disk write failure")
            return real_atomic(path, data)

        tg.atomic = fail_on_todo_write
        try:
            with self.assertRaises(OSError):
                self.retry()
        finally:
            tg.atomic = real_atomic
        self.assertEqual((self.root / receipt).read_bytes(), held)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.retry(), receipt)

    def test_a_stamp_killed_before_its_plan_write_is_completed_by_the_same_retry(self):
        receipt, held, _, todo_after, _ = self.cut_short(keep_todo=True)
        with self.assertRaises(tg.Refused):
            tg.projections(self.root)  # the state a kill leaves: plan --check fails
        self.assertEqual(self.retry(), receipt)
        tg.projections(self.root)
        self.assertEqual((self.root / receipt).read_bytes(), held)
        self.assertEqual((self.root / self.TODO_A).read_bytes(), todo_after)

    def test_a_stamped_section_refuses_a_request_that_differs_from_its_receipt(self):
        rounds = self.two_rounds()
        receipt, held, _, todo_after, plan_before = self.cut_short(keep_todo=True, reviews=rounds)
        other = self.commit("later work")
        verdict = [dict(rounds[1], verdict="fixed")]  # round 3 is a clean round: "fixed" does not match it
        for label, kwargs in (("commit", {"sha": other, "reviews": rounds}), ("reviews", {"reviews": rounds[1:]}),
                              ("verdict", {"reviews": verdict})):
            with self.subTest(label):
                before = self.snapshot()
                with self.assertRaises(tg.Refused) as ctx:
                    self.retry(**kwargs)
                if label != "verdict":  # a verdict the findings do not bear out is refused by its own check first
                    self.assertIn("already verified", str(ctx.exception))
                self.assertEqual(self.snapshot(), before, "a refused retry wrote something")
        self.assertEqual((self.root / receipt).read_bytes(), held)
        self.assertEqual((self.root / self.TODO_A).read_bytes(), todo_after)
        self.assertEqual((self.root / tg.PLAN).read_bytes(), plan_before)

    def test_a_failing_plan_write_on_the_retry_keeps_the_stamp_and_a_further_retry_succeeds(self):
        receipt, held, _, todo_after, plan_before = self.cut_short(keep_todo=True)
        real_atomic = tg.atomic

        def fail(path, data):
            raise OSError("simulated disk write failure")

        tg.atomic = fail
        try:
            with self.assertRaises(OSError):
                self.retry()
        finally:
            tg.atomic = real_atomic
        self.assertEqual((self.root / receipt).read_bytes(), held)
        self.assertEqual((self.root / self.TODO_A).read_bytes(), todo_after)
        self.assertEqual((self.root / tg.PLAN).read_bytes(), plan_before)
        self.assertEqual(self.retry(), receipt)
        tg.projections(self.root)

    def test_unstamp_reopens_a_regressed_section_and_allows_a_restamp(self):
        self.tick_work()
        tg.projections(self.root, sync=True)
        receipt = self.stamp("D00 T01 §1", self.sha, self.reviews, ["true -> ok"], "2026-10-13", sync_plan=True)
        before = self.snapshot()
        for bad in (("D00 T01 §2", "x"), ("D00 T01 §1", ""), ("D00 T01 §1", "two\nlines")):
            with self.assertRaises(tg.Refused):
                tg.unstamp(self.root, bad[0], bad[1], "2026-10-21")
        self.assertEqual(self.snapshot(), before)
        revoked = tg.unstamp(self.root, "D00 T01 §1", "checkpoint fails at abc1234; repair -> XREF: §2", "2026-10-21")
        rows = tg.graph(self.root)
        self.assertFalse(rows["D00 T01 §1"].done)
        self.assertEqual(tg.disposition(rows["D00 T01 §1"], rows), 0)
        self.assertFalse((self.root / receipt).exists())
        self.assertEqual((self.root / revoked).read_bytes(), before[str(pathlib.Path(receipt))])
        text = (self.root / "todo/00-workspace/TODO-01-a.md").read_text(encoding="utf-8")
        self.assertIn("> **Unstamped:** 2026-10-21: checkpoint fails", text)
        self.assertIn("- [ ] Commit:", text)
        tg.projections(self.root)  # the plan was synced
        self.stamp("D00 T01 §1", self.sha, self.reviews, ["true -> ok"], "2026-10-22", sync_plan=True)
        self.assertTrue(tg.graph(self.root)["D00 T01 §1"].done)

    def test_unstamping_a_prerequisite_leaves_its_consumers_stamped_and_suspect(self):
        path = self.root / "todo/00-workspace/TODO-02-b.md"
        path.write_text(todo_file([(1, "Base", 0, "none", "--"), (2, "Mid", 0, "none", "§1"), (3, "Top", 0, "none", "§2")],
                                  ident="bravo").replace("- [ ] Work.", "- [x] Work.")
                        .replace("**Test checkpoint:**", STARTED + "**Test checkpoint:**"), encoding="utf-8")
        self.index("TODO-02-b.md")
        self.commit("start bravo")
        for n in (1, 2, 3):
            self.stamp(f"D00 T02 §{n}", self.sha, self.reviews, ["true -> ok"], "2026-10-13")
        tg.unstamp(self.root, "D00 T02 §1", "checkpoint fails", "2026-10-21")
        rows = tg.graph(self.root)
        self.assertEqual([rows[f"D00 T02 §{n}"].done for n in (1, 2, 3)], [False, True, True])
        self.assertEqual(tg.suspects(self.root, "D00 T02 §1"), ["D00 T02 §2", "D00 T02 §3"])
        # New work on a suspect stamp waits, and cannot stamp, until the reopened ancestor re-stamps.
        extra = self.root / "todo/00-workspace/TODO-03-c.md"
        extra.write_text(todo_file([(1, "On top", 0, "none", "D00 T02 §3")], ident="charlie")
                         .replace("- [ ] Work.", "- [x] Work."), encoding="utf-8")
        self.index("TODO-03-c.md")
        rows = tg.graph(self.root)
        self.assertEqual(tg.disposition(rows["D00 T03 §1"], rows), 4)
        with self.assertRaises(tg.Refused) as ctx:
            self.stamp("D00 T03 §1", self.sha, self.reviews, ["true -> ok"], "2026-10-21")
        self.assertIn("resting on a reopened section", str(ctx.exception))
        extra.unlink()
        # Without the Unstamped note, a stamped consumer of an open section still refuses.
        path.write_text(path.read_text(encoding="utf-8").replace("> **Unstamped:** ", "> **Note:** "), encoding="utf-8")
        self.refuses("stamped section has open dependency")

    def test_an_interrupted_unstamp_rolls_back(self):
        self.tick_work()
        tg.projections(self.root, sync=True)
        self.stamp("D00 T01 §1", self.sha, self.reviews, ["true -> ok"], "2026-10-13", sync_plan=True)
        before = self.snapshot()
        real_atomic = tg.atomic
        calls = []

        def interrupt_on_second_write(path, data):
            calls.append(path)
            if len(calls) == 2:
                raise KeyboardInterrupt
            return real_atomic(path, data)

        tg.atomic = interrupt_on_second_write
        try:
            with self.assertRaises(KeyboardInterrupt):
                tg.unstamp(self.root, "D00 T01 §1", "regressed", "2026-10-21")
        finally:
            tg.atomic = real_atomic
        self.assertEqual(self.snapshot(), before)
        tg.graph(self.root)

    def test_stamping_the_last_section_marks_the_file_done(self):
        path = self.root / "todo/00-workspace/TODO-02-b.md"
        path.write_text(todo_file([(1, "Only", 0, "none", "--")], ident="bravo")
                        .replace("- [ ] Work.", "- [x] Work.")
                        .replace("**Test checkpoint:**", STARTED + "**Test checkpoint:**"), encoding="utf-8")
        self.index("TODO-02-b.md")
        self.commit("start bravo")
        self.stamp("D00 T02 §1", self.sha, self.reviews, ["true -> ok"], "2026-10-13")
        self.assertIn("status: done", path.read_text(encoding="utf-8"))
        self.assertTrue(tg.graph(self.root)["D00 T02 §1"].done)

    def test_malformed_receipt_refuses_instead_of_crashing(self):
        self.tick_work()
        receipt = self.stamp("D00 T01 §1", self.sha, self.reviews, ["true -> ok"], "2026-10-13")
        unhashable = json.dumps({"ref": "D00 T01 §1", "implementation_sha": self.sha,
                                 "reviews": [{"round": 1, "report": "r", "verdict": []}],
                                 "checks": ["x"], "date": "2026-10-13"})
        for bad in ("[]", json.dumps({"ref": "D00 T01 §1", "implementation_sha": self.sha,
                                      "reviews": [None], "checks": ["x"], "date": "2026-10-13"}),
                    "not json", unhashable):
            (self.root / receipt).write_text(bad, encoding="utf-8")
            self.refuses("receipt")

    def test_missing_receipt_refuses(self):
        self.tick_work()
        receipt = self.stamp("D00 T01 §1", self.sha, self.reviews, ["true -> ok"], "2026-10-13")
        (self.root / receipt).unlink()
        self.refuses("missing receipt")

    # The plan review and the review schedule (2026-10-24): stamp refuses a section whose reviews did not follow them.

    LOOP = "docs/reviews/00-workspace/D00-T01-s1.md"
    ROUND_1 = ["adversarial", "integration", "source-defect", "plan-delivery"]

    def live(self, surface=False):
        """Pin the live schedule shape (and, with surface, make §1 a surface section), committed as the stamped commit."""
        (self.root / tg.PIN).write_text(SCHEDULE_PIN, encoding="utf-8")
        if surface:
            path = self.root / "todo/00-workspace/TODO-01-a.md"
            path.write_text(path.read_text(encoding="utf-8").replace(
                "**Surface:** no", "**Surface:** yes\n**Fidelity:** f.\n**Job:** j.\n**Treatment:** t.\n**Chrome:** c.",
                1), encoding="utf-8")
        self.sha = self.commit("live schedule")

    def loop(self, steps, surface=False):
        """Record a review loop as the dispatcher would, each round at the pass `scheduled` gives it. A step is a
        severity (a returned needs-attention review declaring it), "clean", "outage", "self" (a self-review) or
        "malformed" (a reply without the final OVERALL line)."""
        dispatch = tg.review_dispatch()
        schedule = tg.pin_schedule(self.root, self.sha, "test")
        path = self.root / self.LOOP
        if path.exists():  # a fresh loop: the rounds go, the section's plan review stays
            path.write_bytes(self.only(path.read_bytes().decode("utf-8"), plans=True).encode("utf-8"))
        for step in steps:
            existing = path.read_bytes().decode("utf-8") if path.exists() else ""
            plan = dispatch.scheduled(schedule, "round", dispatch.read_rounds(existing), surface)
            result = {"writer": "claude", "effort": plan["effort"], "lenses": plan["lenses"], "failover": [],
                      "reviewer": "astra", "model": "m", "cli": "codex",
                      "review": "1. ok.\n\nHIGHEST: none\n\nOVERALL: approve"}
            if step == "outage":
                result.update(reviewer=None, review=None, skipped=[{"reviewer": "astra", "reason": "exited 3"}])
            elif step == "self":
                result.update(reviewer="opus", cli="claude")
            elif step == "malformed":
                result["review"] = "1. The reply stopped before its verdict."
            elif step != "clean":
                result["review"] = f"1. [{step}] gap.\n\nHIGHEST: {step}\n\nOVERALL: needs-attention"
            dispatch.record(path, result, "2026-10-23T00:00:00Z")
        self.reviews = [{"round": len(steps), "report": self.LOOP, "verdict": "clean"}]

    def edit_round(self, n, effort, lenses):
        """Rewrite round n's Effort and Lenses lines, which sit outside its digest, as a hand edit would."""
        path = self.root / self.LOOP
        text = path.read_bytes().decode("utf-8")
        start = text.index(f"## Round {n}: ")
        end = text.find("\n## Round ", start)
        end = len(text) if end < 0 else end
        block = re.sub(r"^- Effort: .*$", f"- Effort: {effort}", text[start:end], count=1, flags=re.M)
        block = re.sub(r"^- Lenses: .*$", f"- Lenses: {', '.join(lenses)}", block, count=1, flags=re.M)
        path.write_bytes((text[:start] + block + text[end:]).encode("utf-8"))

    def stamp_refuses(self, fragment):
        self.tick_work()
        before = self.snapshot()
        with self.assertRaises(tg.Refused) as ctx:
            self.stamp("D00 T01 §1", self.sha, self.reviews, ["true -> ok"], "2026-10-24")
        self.assertIn(fragment, str(ctx.exception))
        self.assertEqual(self.snapshot(), before, "a refused stamp wrote something")
        return str(ctx.exception)

    def test_a_stamp_without_a_plan_review_refuses(self):
        self.tick_work()
        before = self.snapshot()
        with self.assertRaises(tg.Refused) as ctx:
            tg.stamp(self.root, "D00 T01 §1", self.sha, self.reviews, ["true -> ok"], "2026-10-24",
                     completion={"report": self.COMPLETION, "verdict": "complete"})
        self.assertIn("--plan '<findings file>' is required", str(ctx.exception))
        self.assertEqual(self.snapshot(), before)

    def test_a_plan_review_must_be_one_returned_by_another_model_family(self):
        family = "must hold exactly one plan review returned by another model family"
        for kwargs in ({"reviewer": "opus", "cli": "claude"}, {"reviewer": None},
                       {"review": "1. ok.\n\nHIGHEST: none\n\nOVERALL: approve"},
                       {"review": "1. ok.\n\nOVERALL: approve\n\nPLAN: complete"}):
            with self.subTest(kwargs=kwargs):
                self.write_plan(**kwargs)
                self.stamp_refuses(family)
        self.write_plan()
        path = self.root / self.PLAN
        text = path.read_bytes().decode("utf-8")
        path.write_bytes(self.only(text, plans=False).encode("utf-8"))
        self.tick_work()
        with self.assertRaises(tg.Refused) as ctx:
            tg.stamp(self.root, "D00 T01 §1", self.sha, self.reviews, ["true -> ok"], "2026-10-24", plan=self.PLAN,
                     completion={"report": self.COMPLETION, "verdict": "complete"})
        self.assertIn("holds no ## Plan review", str(ctx.exception))
        path.write_bytes(text.encode("utf-8"))
        for plan in ("docs/reviews/00-workspace/D00-T01-s2.md", self.COMPLETION,
                     "docs\\reviews\\00-workspace\\D00-T01-s1.md", "../plan.md"):
            with self.subTest(plan=plan):
                self.tick_work()
                with self.assertRaises(tg.Refused) as ctx:
                    self.stamp("D00 T01 §1", self.sha, self.reviews, ["true -> ok"], "2026-10-24", plan=plan)
                self.assertIn(f"--plan must be the section's own findings file {self.PLAN}", str(ctx.exception))
        path.unlink()
        self.tick_work()
        with self.assertRaises(tg.Refused) as ctx:
            tg.stamp(self.root, "D00 T01 §1", self.sha, self.reviews, ["true -> ok"], "2026-10-24", plan=self.PLAN,
                     completion={"report": self.COMPLETION, "verdict": "complete"})
        self.assertIn("missing or empty review report", str(ctx.exception))

    def test_another_sections_plan_review_does_not_stand_in(self):
        # §2's own findings file holds a returned plan review on the build-start commit; §1 cannot stamp on it.
        other = "docs/reviews/00-workspace/D00-T01-s2.md"
        self.write_plan(path=other)
        self.tick_work()
        with self.assertRaises(tg.Refused) as ctx:
            self.stamp("D00 T01 §1", self.sha, self.reviews, ["true -> ok"], "2026-10-24", plan=other)
        self.assertIn(f"--plan must be the section's own findings file {self.PLAN}, not {other}", str(ctx.exception))
        # Nor through a receipt edited after the stamp to name it.
        receipt = self.root / self.stamp("D00 T01 §1", self.sha, self.reviews, ["true -> ok"], "2026-10-24")
        data = json.loads(receipt.read_text(encoding="utf-8"))
        data["plan"]["report"] = other
        receipt.write_text(json.dumps(data), encoding="utf-8")
        self.refuses(f"--plan must be the section's own findings file {self.PLAN}, not {other}")

    def test_a_plan_review_after_the_build_began_refuses(self):
        later = self.commit("the build")
        self.write_plan(candidate=later)
        self.stamp_refuses("is not the commit the build began at")
        self.write_plan(candidate="f" * 40)
        self.stamp_refuses("not a commit")
        # Without a Started line or a commit naming the section, there is no build start to check the plan against.
        self.write_plan()
        path = self.root / "todo/00-workspace/TODO-01-a.md"
        path.write_text(path.read_text(encoding="utf-8").replace(STARTED, ""), encoding="utf-8")
        self.stamp_refuses("cannot find the commit the build began at")

    def test_the_plan_and_completion_passes_run_at_their_scheduled_effort(self):
        self.live()
        self.loop(["clean"])
        self.write_plan(effort="high")
        self.stamp_refuses("the plan review in docs/reviews/00-workspace/D00-T01-s1.md ran at high")
        self.write_plan(lenses=("adversarial",))
        self.stamp_refuses("lenses ['adversarial']; the schedule expects medium with ['plan']")
        self.write_plan()
        self.write_completion(effort="xhigh")
        self.stamp_refuses("the completion review in docs/reviews/00-workspace/D00-T01-s1-completion.md ran at xhigh")

    def test_every_plan_and_completion_attempt_runs_at_its_scheduled_effort(self):
        self.live()
        self.loop(["clean"])
        self.write_plan(reviewer=None, effort="low", lenses=("adversarial",))
        self.write_plan(keep=True)
        self.stamp_refuses("the plan review in docs/reviews/00-workspace/D00-T01-s1.md ran at low with lenses "
                           "['adversarial']")
        self.write_plan()
        self.write_completion(reviewer=None, effort="low")
        self.write_completion(keep=True)
        self.stamp_refuses("the completion review in docs/reviews/00-workspace/D00-T01-s1-completion.md ran at low")

    def test_the_schedule_check_needs_no_temporary_directory(self):
        # A reviewer's read-only sandbox runs validate with no writable temporary directory.
        self.live()
        real = tempfile.tempdir
        tempfile.tempdir = str(self.root / "no-such-directory")
        try:
            schedule = tg.pin_schedule(self.root, self.sha, "D00 T01 §1")
        finally:
            tempfile.tempdir = real
        self.assertEqual(schedule["plan"], {"effort": "medium", "lenses": ["plan"]})

    def test_the_build_start_matches_the_whole_reference(self):
        (self.root / "src").mkdir(exist_ok=True)
        (self.root / "src/a.txt").write_text("a", encoding="utf-8")
        self.commit("build\n\nD00 T01 §11")
        (self.root / "src/b.txt").write_text("b", encoding="utf-8")
        mine = self.commit("build\n\nThe section (D00 T01 §1).")
        self.assertEqual(tg.build_start(self.root, "todo/00-workspace/TODO-01-a.md", "", "D00 T01 §1"), mine)

    def test_the_build_start_is_the_sections_own_whole_started_line(self):
        # §1's Started line is in the first commit; §2 records a prefix of it, then the identical line, later.
        path = "todo/00-workspace/TODO-01-a.md"

        def record(line):
            text = (self.root / path).read_text(encoding="utf-8")
            two = tg.section_text(text, 2)
            two_now = re.sub(r"(?m)^> \*\*Started:\*\* .*\n\n", "", two)
            two_now = two_now.replace("**Test checkpoint:**", line + "\n\n**Test checkpoint:**", 1)
            (self.root / path).write_text(text.replace(two, two_now), encoding="utf-8")
            return self.commit("start §2"), tg.section_text((self.root / path).read_text(encoding="utf-8"), 2)

        prefix, body = record("> **Started:** 2026-10-23")
        self.assertEqual(tg.build_start(self.root, path, body, "D00 T01 §2"), prefix)
        whole, body = record(STARTED.strip())
        self.assertEqual(tg.build_start(self.root, path, body, "D00 T01 §2"), whole)
        self.assertEqual(tg.build_start(self.root, path, tg.section_text((self.root / path).read_text(
            encoding="utf-8"), 1), "D00 T01 §1"), self.start)

    def test_round_1_runs_at_high_effort(self):
        self.live()
        self.loop(["clean"])
        self.edit_round(1, "medium", self.ROUND_1)
        message = self.stamp_refuses(f"{self.LOOP} round 1 ran at medium")
        self.assertIn(f"the schedule expects high with {self.ROUND_1} (position 1)", message)

    def test_round_1_runs_all_four_lenses(self):
        self.live()
        self.loop(["clean"])
        self.edit_round(1, "high", self.ROUND_1[:3])
        self.stamp_refuses(f"round 1 ran at high with lenses {self.ROUND_1[:3]}; the schedule expects high with "
                           f"{self.ROUND_1}")

    def test_a_rotation_round_runs_its_one_lens(self):
        self.live()
        self.loop(["P2", "P2", "P2", "clean"])
        self.edit_round(4, "low", ["quality"])
        self.stamp_refuses("round 4 ran at low with lenses ['quality']; the schedule expects low with ['consistency'] "
                           "(position 4)")

    def test_the_design_lens_is_only_for_surface_sections(self):
        self.live()
        self.loop(["P2", "P2", "P2", "P2", "P2", "clean"])
        self.edit_round(6, "low", ["design"])
        self.stamp_refuses("round 6 ran at low with lenses ['design']; the schedule expects low with ['optimization']")

    def test_a_low_round_with_a_p1_escalates_the_next(self):
        self.live()
        self.loop(["P2", "P2", "P1", "clean"])
        self.edit_round(4, "low", ["consistency"])
        self.stamp_refuses("round 4 ran at low with lenses ['consistency']; the schedule expects medium with "
                           "['adversarial'] (position 4, escalated)")

    def test_an_outage_or_a_self_review_does_not_advance_the_schedule(self):
        for skipped in ("outage", "self", "malformed"):
            with self.subTest(skipped=skipped):
                self.live()
                self.loop([skipped, "clean"])
                self.edit_round(2, "medium", ["adversarial"])
                self.stamp_refuses(f"round 2 ran at medium with lenses ['adversarial']; the schedule expects high with "
                                   f"{self.ROUND_1} (position 1)")

    def test_a_receipt_records_the_plan_review_and_schedule_and_edits_refuse(self):
        self.tick_work()
        receipt = self.root / self.stamp("D00 T01 §1", self.sha, self.reviews, ["true -> ok"], "2026-10-24")
        data = json.loads(receipt.read_text(encoding="utf-8"))
        self.assertEqual(data["plan"], {"report": self.PLAN, "candidate": self.sha, "reviewer": "astra", "model": "m",
                                        "effort": "medium", "lenses": ["plan"]})
        self.assertEqual(data["schedule"]["rounds"], [{"effort": "low", "lenses": ["adversarial"]}])
        edits = [("plan", "effort", "high"), ("plan", "lenses", []), ("plan", "candidate", "f" * 40),
                 ("plan", "reviewer", "sol"), ("plan", "model", "other"), ("plan", "report", self.COMPLETION),
                 ("plan", "extra", 1), ("schedule", "severity_stop_after", 2)]
        for where, key, value in edits:
            with self.subTest(where=where, key=key):
                edited = json.loads(json.dumps(data))
                edited[where][key] = value
                receipt.write_text(json.dumps(edited), encoding="utf-8")
                with self.assertRaises(tg.Refused):
                    tg.graph(self.root)
        for dropped, fragment in ((("plan",), "plan and schedule together"),
                                  (("plan", "schedule"), "a receipt without a plan review must be one of the old")):
            with self.subTest(dropped=dropped):
                edited = json.loads(json.dumps(data))
                for key in dropped:
                    del edited[key]
                receipt.write_text(json.dumps(edited), encoding="utf-8")
                self.refuses(fragment)
        receipt.write_text(json.dumps(data), encoding="utf-8")
        tg.graph(self.root)
        # The recorded plan pass is what the findings file still says: its effort line edited after the stamp refuses.
        path = self.root / self.PLAN
        path.write_bytes(path.read_bytes().replace(b"- Effort: medium", b"- Effort: high"))
        self.refuses("receipt plan does not match its findings file")

    def test_a_loop_that_follows_the_whole_schedule_stamps(self):
        self.live(surface=True)
        self.loop(["P2", "outage", "P2", "self", "P1", "P3", "P2", "P2", "P2", "clean"], surface=True)
        self.tick_work()
        receipt = self.root / self.stamp("D00 T01 §1", self.sha, self.reviews, ["true -> ok"], "2026-10-24")
        self.assertTrue(tg.graph(self.root)["D00 T01 §1"].done)
        rounds = tg.review_dispatch().read_rounds((self.root / self.LOOP).read_bytes().decode("utf-8"))
        self.assertEqual([(r["effort"], r["lenses"]) for r in rounds], [
            ("high", self.ROUND_1), ("medium", ["adversarial"]), ("medium", ["adversarial"]),
            ("low", ["adversarial"]), ("low", ["adversarial"]), ("medium", ["adversarial"]), ("low", ["quality"]),
            ("low", ["design"]), ("low", ["optimization"]), ("low", ["record"])])
        self.assertEqual(json.loads(receipt.read_text(encoding="utf-8"))["rounds_spent"], 10)


THREE_PASS_PIN = UNIFORM_PIN.split("[schedule]")[0] + """[schedule]
policy = "three-pass"
pass_cap = 45
plan = { effort = "medium", lenses = ["plan"] }
rounds = [{ effort = "medium", lenses = ["adversarial", "integration"] }]
completion = { effort = "medium", lenses = ["plan-delivery", "record"] }
reconciliation = { effort = "medium", lenses = ["adversarial", "plan-delivery", "record"] }
"""


class ThreePassStamp(Stamp):
    """The three-pass chain (plan, one round, completion, reconciliations) recorded by the dispatcher's own writers,
    stamped, and read back through the graph."""
    PIN_TEXT = THREE_PASS_PIN
    FILE = Stamp.PLAN
    CLI, MODEL = "codex", "m"   # what the fixture pin's one reviewer runs through
    LENSES = {"plan": ["plan"], "round": ["adversarial", "integration"], "completion": ["plan-delivery", "record"],
              "reconciliation": ["adversarial", "plan-delivery", "record"]}

    def setUp(self):
        super().setUp()
        # The rotation fixture's records go: a three-pass section keeps every pass in its own findings file.
        (self.root / self.COMPLETION).unlink()
        (self.root / self.FILE).write_text("# Review findings\n", encoding="utf-8")
        self.clock = 0

    def pin(self, text):
        """Commit another pin as the repository's first one would have been: only the tests of a moved pin use it."""
        (self.root / tg.PIN).write_text(text, encoding="utf-8")
        return self.commit("pin")

    def passed(self, kind, candidate, top="none", gaps=False, lenses=None, reviewer="astra", review=None, notes="",
               effort="medium"):
        """One returned pass as the dispatcher records it."""
        dispatch = tg.review_dispatch()
        self.clock += 1
        names = self.LENSES[kind] if lenses is None else lenses
        lines = [f"LENS {n}: {'findings' if gaps else 'clean'}" for n in names] + [f"HIGHEST: {top}"]
        if kind == "plan":
            lines += ["PLAN: gaps" if gaps else "PLAN: complete"]
        lines += [f"OVERALL: {'needs-attention' if gaps else 'approve'}"] if kind in ("plan", "round") else \
            [f"{kind.upper()}: {'gaps' if gaps else 'complete'}"]
        result = {"writer": "claude", "reviewer": reviewer, "model": self.MODEL, "cli": self.CLI, "effort": effort,
                  "lenses": names, "failover": [], "review": review or "\n".join(["1. text.", *lines])}
        when = f"2026-10-23T00:00:{self.clock:02d}Z"
        path = self.root / self.FILE
        if kind == "round":
            dispatch.record(path, result, when, candidate)
        else:
            dispatch.record_completion(path, result, when, candidate, kind=kind)
        if notes:
            with open(path, "a", encoding="utf-8", newline="") as handle:
                handle.write("\n" + notes + "\n")

    def build(self, message="build"):
        (self.root / "work.txt").write_text(message + "\n", encoding="utf-8")
        return self.commit(message)

    def chain(self, completion=("none", False), reconciliations=(), round_gaps=False, notes=""):
        """Plan at the start commit, a build, the round and the completion on it, then one repair commit and
        reconciliation per (top, gaps) pair; `notes` go under the last pass. Returns the last candidate."""
        self.passed("plan", self.start)
        self.tick_work()
        sha = self.build()
        self.passed("round", sha, top="P2" if round_gaps else "none", gaps=round_gaps)
        last = not reconciliations
        self.passed("completion", sha, *completion, notes=notes if last else "")
        for n, (top, gaps) in enumerate(reconciliations, 1):
            sha = self.build(f"repair {n}")
            self.passed("reconciliation", sha, top, gaps, notes=notes if n == len(reconciliations) else "")
        return sha

    def stamp3(self, sha, verdict="complete", round_verdict="clean"):
        receipt = tg.stamp(self.root, "D00 T01 §1", sha, [{"round": 1, "report": self.FILE, "verdict": round_verdict}],
                           ["true -> ok"], "2026-10-24", completion={"report": self.FILE, "verdict": verdict},
                           plan=self.FILE)
        self.assertTrue(tg.graph(self.root)["D00 T01 §1"].done)
        return json.loads((self.root / receipt).read_text(encoding="utf-8"))

    def stamp3_refuses(self, sha, fragment, verdict="complete", round_verdict="clean"):
        with self.assertRaises(tg.Refused) as ctx:
            self.stamp3(sha, verdict, round_verdict)
        self.assertIn(fragment, str(ctx.exception))
        self.assertFalse((self.root / "docs/reviews/d00-t01-s1.json").exists())

    def test_a_clean_chain_stamps_and_reads_back(self):
        data = self.stamp3(self.chain())
        self.assertEqual((data["passes_spent"], data["pass_cap"], data["rounds_spent"]), (3, 45, 1))
        self.assertEqual(data["schedule_sha"], self.start)
        self.assertEqual(data["schedule"]["policy"], "three-pass")

    def test_a_round_that_found_something_may_end_fixed(self):
        self.stamp3(self.chain(round_gaps=True), round_verdict="fixed")

    def test_gaps_need_a_reconciliation_that_ends_complete(self):
        sha = self.chain(completion=("P2", True))
        # `completed` is the rotation verdict for gaps fixed in the section: under three-pass a reconciliation proves it.
        self.stamp3_refuses(sha, "takes completion verdict complete or reconciled", verdict="completed")
        self.stamp3_refuses(sha, "needs a returned ## Reconciliation review", verdict="reconciled")
        repaired = self.build("repair")
        self.passed("reconciliation", repaired)
        data = self.stamp3(repaired, verdict="reconciled")
        self.assertEqual((data["passes_spent"], data["completion"]["candidate"]), (4, repaired))

    def test_a_reconciliation_that_still_has_gaps_does_not_stamp(self):
        sha = self.chain(completion=("P2", True), reconciliations=[("P2", True)])
        self.stamp3_refuses(sha, "a last reconciliation ending RECONCILIATION: complete", verdict="reconciled")

    def test_the_chain_is_one_plan_one_round_one_completion_in_order_on_the_stamped_commit(self):
        with self.subTest("two rounds"):
            sha = self.chain()
            self.passed("round", sha)
            self.stamp3_refuses(sha, "the review loop")
        self.setUp_again()
        with self.subTest("a round without a candidate"):
            self.passed("plan", self.start)
            self.tick_work()
            sha = self.build()
            self.passed("round", None)
            self.passed("completion", sha)
            self.stamp3_refuses(sha, "recorded no --candidate")
        self.setUp_again()
        with self.subTest("the last pass on another commit than the stamped one"):
            sha = self.chain()
            later = self.build("later")
            self.stamp3_refuses(later, "not the stamped commit")
            del sha
        self.setUp_again()
        with self.subTest("a completion on a commit before the round's"):
            self.passed("plan", self.start)
            self.tick_work()
            sha = self.build()
            later = self.build("more")
            self.passed("round", later)
            self.passed("completion", sha)
            self.stamp3_refuses(later, "must run after the round")
        self.setUp_again()
        with self.subTest("another reviewer than the pinned one"):
            self.passed("plan", self.start)
            self.tick_work()
            sha = self.build()
            self.passed("round", sha, reviewer="sol")
            self.passed("completion", sha)
            self.stamp3_refuses(sha, "not the reviewer astra")

    def replan_now(self, now="2026-10-25T00:00Z"):
        return tg.replan(self.root, "D00 T01 §1", "2026-10-25", now)

    def test_the_replan_route_keeps_the_chain_and_a_new_chain_stamps(self):
        # D00 T01 §9: a chain that cannot settle is re-planned. Followed end to end: the findings file is kept as
        # -chain1.md, Started is replaced (the old one in a dated note), the corrected section is committed, and a new
        # plan review, round and completion stamp it.
        self.chain(completion=("P2", True))
        own = self.root / self.FILE
        before = own.read_bytes()
        done = self.replan_now()
        kept = self.root / self.FILE.replace(".md", "-chain1.md")
        self.assertEqual((done["done"], kept.read_bytes(), own.exists()), ("moved", before, False))
        body = tg.graph(self.root)["D00 T01 §1"].body
        self.assertIn("> **Started:** 2026-10-25T00:00Z", body)
        self.assertNotIn("> **Started:** 2026-10-23T00:00Z", body)
        self.assertIn("**Corrected 2026-10-25:** re-planned with `todo-graph.py replan`; the build first began at "
                      "2026-10-23T00:00Z; its review chain is kept as `docs/reviews/00-workspace/D00-T01-s1-chain1.md`.",
                      body)
        self.start = self.commit("replan")  # the corrected section and its new Started, one commit
        own.write_text("# Review findings\n", encoding="utf-8")
        self.passed("plan", self.start)
        sha = self.build("rebuild")
        self.passed("round", sha)
        self.passed("completion", sha)
        data = self.stamp3(sha)
        self.assertEqual(data["plan"]["candidate"], self.start)
        self.assertEqual(kept.read_bytes(), before, "the stamp touched the kept chain")

    def test_a_second_replan_keeps_the_first_chain_and_a_retry_changes_nothing(self):
        self.chain(completion=("P2", True))
        self.replan_now()
        first = self.root / self.FILE.replace(".md", "-chain1.md")
        first_bytes = first.read_bytes()
        todo = self.root / "todo/00-workspace/TODO-01-a.md"
        after = todo.read_bytes()
        self.assertEqual(self.replan_now("2026-10-25T00:05Z")["done"], "already")  # a retry: nothing left to do
        self.assertEqual(todo.read_bytes(), after)
        self.commit("replan")
        (self.root / self.FILE).write_text("# Review findings\n", encoding="utf-8")
        self.passed("plan", self.head())
        self.replan_now("2026-10-26T00:00Z")
        second = self.root / self.FILE.replace(".md", "-chain2.md")
        self.assertTrue(second.exists())
        self.assertEqual(first.read_bytes(), first_bytes, "a second replan wrote over the first chain")
        # A stop after the move and before the TODO was written: the retry writes the note naming the new chain.
        self.commit("replan 2")
        (self.root / self.FILE).write_text("# Review findings\n", encoding="utf-8")
        os.replace(self.root / self.FILE, self.root / self.FILE.replace(".md", "-chain3.md"))
        self.assertEqual(self.replan_now("2026-10-27T00:00Z")["done"], "noted")
        self.assertIn("-chain3.md`.", tg.graph(self.root)["D00 T01 §1"].body)

    def test_query_rounds_lists_each_kept_chain_with_its_returned_passes(self):
        self.chain(completion=("P2", True))  # plan, round, completion: 3 returned
        self.replan_now()
        self.start = self.commit("replan")
        own = self.root / self.FILE
        own.write_text("# Review findings\n", encoding="utf-8")
        self.passed("plan", self.start, reviewer="", review="no review")  # an attempt that returned none
        self.passed("plan", self.start)
        self.replan_now("2026-10-26T00:00Z")  # chain2: one returned plan review
        self.start = self.commit("replan 2")
        own.write_text("# Review findings\n", encoding="utf-8")
        self.passed("plan", self.start)
        sha = self.build("rebuild")
        self.passed("round", sha)
        self.passed("completion", sha)
        self.stamp3(sha)
        (row,) = [r for r in tg.review_rounds(self.root)["sections"] if r["ref"] == "D00 T01 §1"]
        self.assertEqual(row["kept_chains"], [
            {"file": "docs/reviews/00-workspace/D00-T01-s1-chain1.md", "passes_returned": 3},
            {"file": "docs/reviews/00-workspace/D00-T01-s1-chain2.md", "passes_returned": 1}])
        self.assertEqual(row["rounds_spent"], 1)

    def test_replan_refuses_without_started_and_keeps_the_file(self):
        # Round 1 of D00 T01 §9: replan moved the findings file before it found the section had no Started line.
        todo = self.root / "todo/00-workspace/TODO-01-a.md"
        todo.write_text(todo.read_text(encoding="utf-8").replace("> **Started:** 2026-10-23T00:00Z\n\n", "", 1),
                        encoding="utf-8")
        own = self.root / self.FILE
        before = own.read_bytes()
        with self.assertRaises(tg.Refused) as ctx:
            self.replan_now()
        self.assertIn("has no '> **Started:**' line", str(ctx.exception))
        self.assertEqual(own.read_bytes(), before)
        self.assertEqual(list(own.parent.glob("*-chain*.md")), [])

    def test_a_retry_on_another_day_finds_the_note_and_changes_nothing(self):
        self.chain(completion=("P2", True))
        self.replan_now()
        todo = self.root / "todo/00-workspace/TODO-01-a.md"
        after = todo.read_bytes()
        self.assertEqual(tg.replan(self.root, "D00 T01 §1", "2026-10-26", "2026-10-26T09:00Z")["done"], "already")
        self.assertEqual(todo.read_bytes(), after)

    def test_replan_waits_for_a_pass_that_holds_the_sections_lock(self):
        # Round 1: replan moved the file while a reviewer was answering, so the pass landed in a new canonical file.
        self.chain(completion=("P2", True))
        own = self.root / self.FILE
        holder = subprocess.Popen([sys.executable, "-c",
                                   "import importlib.util, sys, time\n"
                                   "spec = importlib.util.spec_from_file_location('d', sys.argv[1])\n"
                                   "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)\n"
                                   "m.lock_section(sys.argv[2], 60); print('held', flush=True); time.sleep(60)\n",
                                   str(tg.review_dispatch().__file__), str(own)],
                                  stdout=subprocess.PIPE, text=True,
                                  creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.addCleanup(holder.wait, 10)
        self.addCleanup(holder.kill)
        self.addCleanup(holder.stdout.close)
        self.assertEqual(holder.stdout.readline().strip(), "held")
        before = own.read_bytes()
        with self.assertRaises(tg.Refused) as ctx:
            self.replan_now()
        self.assertIn("replan waits for it", str(ctx.exception))
        self.assertEqual((own.read_bytes(), list(own.parent.glob("*-chain*.md"))), (before, []))

    def test_query_rounds_lists_an_open_sections_kept_chains_read_as_bytes(self):
        # Round 1: an open section's chains were missing, and a lone carriage return in a review was read as a line
        # break, so the dispatcher's sealed digest failed and the passes read as None.
        self.passed("plan", self.start, review="1. a\rb.\nLENS plan: clean\nHIGHEST: none\nPLAN: complete\nOVERALL: approve")
        self.replan_now()
        (row,) = [r for r in tg.review_rounds(self.root)["sections"] if r["ref"] == "D00 T01 §1"]
        self.assertEqual(row, {"ref": "D00 T01 §1", "open": True, "kept_chains": [
            {"file": "docs/reviews/00-workspace/D00-T01-s1-chain1.md", "passes_returned": 1}]})
        self.assertEqual(tg.review_rounds(self.root)["summary"]["stamped"], 0)

    def test_a_kept_chain_is_refused_as_plan_or_completion_under_a_three_pass_pin(self):
        sha = self.chain()
        chain = self.FILE.replace(".md", "-chain1.md")
        shutil.copyfile(self.root / self.FILE, self.root / chain)
        for kwargs in ({"plan": chain}, {"completion": {"report": chain, "verdict": "complete"}}):
            with self.subTest(next(iter(kwargs))):
                args = {"completion": {"report": self.FILE, "verdict": "complete"}, "plan": self.FILE, **kwargs}
                with self.assertRaises(tg.Refused) as ctx:
                    tg.stamp(self.root, "D00 T01 §1", sha, [{"round": 1, "report": self.FILE, "verdict": "clean"}],
                             ["true -> ok"], "2026-10-24", **args)
                self.assertIn("is a kept earlier review chain", str(ctx.exception))
        self.stamp3(sha)

    def setUp_again(self):
        self.tearDown()
        self.setUp()

    def test_the_cap_is_the_sections_pins(self):
        self.tearDown()
        type(self).PIN_TEXT = THREE_PASS_PIN.replace("pass_cap = 45", "pass_cap = 4")
        try:
            self.setUp()
            sha = self.chain(completion=("P2", True), reconciliations=[("P2", True), ("none", False)])
            self.stamp3_refuses(sha, "allows 4 review passes (pass_cap), not 5", verdict="reconciled")
        finally:
            type(self).PIN_TEXT = THREE_PASS_PIN

    def test_a_reconciliation_must_have_been_eligible(self):
        with self.subTest("after a completion that was complete"):
            sha = self.chain(reconciliations=[("none", False)])
            self.stamp3_refuses(sha, "", verdict="reconciled")
        for label, pin, completion, recs, fragment in (
                ("below the blocking levels", 'pass_cap = 45\nblocking = ["P1", "P2"]', ("P3", True),
                 [("none", False)], "below the pin's blocking levels"),
                ("past a stalled chain", "pass_cap = 45\nno_progress_cap = 1", ("P2", True),
                 [("P2", True), ("none", False)], "no_progress_cap of 1")):
            self.tearDown()
            type(self).PIN_TEXT = THREE_PASS_PIN.replace("pass_cap = 45", pin)
            try:
                self.setUp()
                with self.subTest(label):
                    sha = self.chain(completion=completion, reconciliations=recs)
                    self.stamp3_refuses(sha, fragment, verdict="reconciled")
            finally:
                type(self).PIN_TEXT = THREE_PASS_PIN

    def p2_text(self, kind, data, findings=("P2",), top="P2", gaps=True):
        """A review of `kind` with numbered `findings` (each its tag), its HIGHEST and P2 DATA lines."""
        lines = [f"{n}. {tag}: a.py:{n} is wrong." for n, tag in enumerate(findings, 1)]
        lines += [f"LENS {name}: {'findings' if gaps else 'clean'}" for name in self.LENSES[kind]] + [f"HIGHEST: {top}"]
        lines += [] if data is None else [f"P2 DATA: {'yes' if data else 'no'}"]
        return "\n".join(lines + [f"{kind.upper()}: {'gaps' if gaps else 'complete'}"])

    def p2_chain(self, data, reconciliations, findings=("P2",), notes=None, top="P2"):
        """Under caps 2 (ordinary) and 4 (data): plan, round, a completion and `reconciliations` repairs, every one
        ending gaps with a P2 of `data`; `notes` (default: one Filed line per finding) go under the last pass."""
        self.tearDown()
        type(self).PIN_TEXT = THREE_PASS_PIN.replace(
            "pass_cap = 45", 'pass_cap = 45\nblocking = ["P1", "P2"]\np2_file_after = 2\np2_data_file_after = 4')
        try:
            self.setUp()
        finally:
            type(self).PIN_TEXT = THREE_PASS_PIN
        # A third section, so two open P2s can each be filed as a section of their own.
        self.write(todo_file([(1, "A", 0, "none", "--"), (2, "B", 0, "owner-decision", "--"),
                              (3, "C", 0, "owner-decision", "--")]).replace("**Test checkpoint:**",
                                                                             STARTED + "**Test checkpoint:**", 1))
        notes = "\n".join(f"- Filed: D00 T01 §{n + 1} (P2 {n}: a.py:{n})" for n in range(1, len(findings) + 1)) \
            if notes is None else notes
        self.passed("plan", self.start)
        self.tick_work()
        sha = self.build()
        self.passed("round", sha)
        last = not reconciliations
        self.passed("completion", sha, review=self.p2_text("completion", data, findings, top), top=top,
                    notes=notes if last else "")
        for n in range(1, reconciliations + 1):
            sha = self.build(f"repair {n}")
            self.passed("reconciliation", sha, review=self.p2_text("reconciliation", data, findings, top), top=top,
                        notes=notes if n == reconciliations else "")
        return sha

    def test_an_ordinary_p2_is_filed_at_its_cap_and_not_before(self):
        # D00 T01 §10: caps of 2 and 4, so the boundaries are the pin's, not hard-coded 3 and 6.
        self.stamp3_refuses(self.p2_chain(False, 1), "below the pin's blocking levels", verdict="filed")
        data = self.stamp3(self.p2_chain(False, 2), verdict="filed")
        self.assertEqual((data["completion"]["filed"], data["passes_spent"]), (["D00 T01 §2"], 5))

    def test_a_data_p2_is_filed_at_its_own_cap_and_an_absent_line_counts_as_data(self):
        self.stamp3_refuses(self.p2_chain(True, 3), "below the pin's blocking levels", verdict="filed")
        self.stamp3(self.p2_chain(True, 4), verdict="filed")
        self.stamp3_refuses(self.p2_chain(None, 2), "below the pin's blocking levels", verdict="filed")

    def test_a_p1_is_never_filed_and_a_chain_past_its_cap_is_refused(self):
        self.stamp3_refuses(self.p2_chain(False, 2, findings=("P1",), top="P1"), "below the pin's blocking levels",
                            verdict="filed")
        self.stamp3_refuses(self.p2_chain(False, 3), "the pin had already let be filed", verdict="filed")

    def test_each_open_p2_needs_a_section_of_its_own_and_a_contradiction_is_refused(self):
        two = ("P2", "P2")
        self.stamp3_refuses(self.p2_chain(False, 2, findings=two, notes="- Filed: D00 T01 §2 (P2 1: a.py:1)"),
                            "for P2 2", verdict="filed")
        # Round 1 of D00 T01 §10: two findings filed under one section passed.
        self.stamp3_refuses(self.p2_chain(False, 2, findings=two, notes="- Filed: D00 T01 §2 (P2 1: a.py:1)\n"
                                                                         "- Filed: D00 T01 §2 (P2 2: a.py:2)"),
                            "are filed under one section", verdict="filed")
        data = self.stamp3(self.p2_chain(False, 2, findings=two), verdict="filed")
        self.assertEqual(data["completion"]["filed"], ["D00 T01 §2", "D00 T01 §3"])
        self.stamp3_refuses(self.p2_chain(False, 2, findings=("P2 data",)), "while an open finding's label is P2 data",
                            verdict="filed")

    def test_a_finding_closed_after_its_severity_is_not_filed(self):
        # The completion review of D00 T01 §10: `P2 (closed):` was read as open and had to be filed.
        sha = self.p2_chain(False, 2, findings=("P2 (closed)", "P2"), notes="- Filed: D00 T01 §3 (P2 2: a.py:2)")
        self.assertEqual(self.stamp3(sha, verdict="filed")["completion"]["filed"], ["D00 T01 §3"])

    def test_a_closed_finding_is_neither_filed_nor_a_contradiction(self):
        # Round 1 of D00 T01 §10: a reconciliation numbers the gaps it closed, and those were counted as open.
        sha = self.p2_chain(False, 2, findings=("Closed (P2 data)", "P2"), notes="- Filed: D00 T01 §3 (P2 2: a.py:2)")
        data = self.stamp3(sha, verdict="filed")
        self.assertEqual(data["completion"]["filed"], ["D00 T01 §3"])

    def filed_case(self, blocking, reconciled):
        """A chain whose last pass ends HIGHEST: P2 and gaps, its finding filed as §2, under `blocking`."""
        self.tearDown()
        type(self).PIN_TEXT = THREE_PASS_PIN.replace("pass_cap = 45", f"pass_cap = 45\nblocking = {blocking}")
        try:
            self.setUp()
            note = "- Filed: D00 T01 §2 (the P2 finding)"
            if reconciled:
                return self.chain(completion=("P1", True), reconciliations=[("P2", True)], notes=note)
            return self.chain(completion=("P2", True), notes=note)
        finally:
            type(self).PIN_TEXT = THREE_PASS_PIN

    def test_filed_is_for_a_last_pass_below_the_blocking_levels(self):
        for reconciled in (False, True):
            with self.subTest(reconciled=reconciled, blocking="P1 and P2"):
                sha = self.filed_case('["P1", "P2"]', reconciled)
                self.stamp3_refuses(sha, "below the pin's blocking levels", verdict="filed")
            with self.subTest(reconciled=reconciled, blocking="P1 only"):
                sha = self.filed_case('["P1"]', reconciled)
                data = self.stamp3(sha, verdict="filed")
                self.assertEqual((data["completion"]["filed"], data["passes_spent"]),
                                 (["D00 T01 §2"], 4 if reconciled else 3))
        with self.subTest("a pin without blocking takes no filed verdict"):
            self.tearDown()
            self.setUp()
            sha = self.chain(completion=("P3", True), notes="- Filed: D00 T01 §2 (x)")
            self.stamp3_refuses(sha, "takes completion verdict complete or reconciled", verdict="filed")

    def test_the_receipt_is_held_to_the_pin_at_the_plan_reviews_candidate(self):
        self.passed("plan", self.start)
        self.tick_work()
        (self.root / tg.PIN).write_text(THREE_PASS_PIN.replace('"adversarial", "integration"', '"quality"', 1),
                                        encoding="utf-8")
        sha = self.build("build with a moved pin")
        # The dispatcher ran the round under the earlier pin, so the earlier lenses are what the stamp expects.
        self.passed("round", sha)
        self.passed("completion", sha)
        data = self.stamp3(sha)
        self.assertEqual(data["schedule"]["rounds"][0]["lenses"], ["adversarial", "integration"])
        receipt = self.root / "docs/reviews/d00-t01-s1.json"
        for label, change in (("deleted", lambda d: d.pop("schedule_sha")),
                              ("replaced by the stamped commit", lambda d: d.update(schedule_sha=sha)),
                              ("passes_spent edited", lambda d: d.update(passes_spent=2)),
                              ("pass_cap edited", lambda d: d.update(pass_cap=99)),
                              ("pass accounting dropped", lambda d: (d.pop("pass_cap"), d.pop("passes_spent")))):
            with self.subTest(label):
                edited = dict(data)
                change(edited)
                receipt.write_text(json.dumps(edited, indent=2) + "\n", encoding="utf-8")
                with self.assertRaises(tg.Refused):
                    tg.graph(self.root)
        receipt.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        tg.graph(self.root)

    def test_conditional_lenses_are_replayed_from_the_changed_files(self):
        self.tearDown()
        type(self).PIN_TEXT = THREE_PASS_PIN + (
            '\n[[schedule.conditional]]\nlenses = ["design"]\npasses = ["plan", "round"]\npaths = ["src/ui/"]\n')
        try:
            self.setUp()
            self.passed("plan", self.start, lenses=["plan", "design"])   # named with --paths before the build
            self.tick_work()
            (self.root / "src/ui").mkdir(parents=True)
            (self.root / "src/ui/a.txt").write_text("x\n", encoding="utf-8")
            sha = self.commit("ui build")
            self.passed("round", sha)                                      # recorded without the lens its files call for
            self.passed("completion", sha)
            self.stamp3_refuses(sha, "the schedule expects medium with ['adversarial', 'integration', 'design']")
            self.setUp_again()
            self.passed("plan", self.start)
            self.tick_work()
            sha = self.build()                                              # touches nothing under src/ui/
            self.passed("round", sha, lenses=["adversarial", "integration", "design"])
            self.passed("completion", sha)
            self.stamp3_refuses(sha, "the schedule expects medium with ['adversarial', 'integration']")
            self.setUp_again()
            self.passed("plan", self.start, lenses=["plan", "design"])
            self.tick_work()
            (self.root / "src/ui").mkdir(parents=True)
            (self.root / "src/ui/a.txt").write_text("x\n", encoding="utf-8")
            sha = self.commit("ui build")
            self.passed("round", sha, lenses=["adversarial", "integration", "design"])
            self.passed("completion", sha)
            self.stamp3(sha)
        finally:
            type(self).PIN_TEXT = THREE_PASS_PIN

    def ui_build(self, message="ui build"):
        (self.root / "src/ui").mkdir(parents=True, exist_ok=True)
        (self.root / "src/ui/a.txt").write_text(message + "\n", encoding="utf-8")
        return self.commit(message)

    def test_a_surface_no_section_that_changed_a_design_path_needs_the_design_lens_to_stamp(self):
        # The fixture section is `Surface: no`. A pin that keeps `design` in the round for --surface and also names
        # it in a conditional entry holds any section that changed a file under the entry's paths to the lens.
        gated = THREE_PASS_PIN.replace('lenses = ["adversarial", "integration"] }]',
                                       'lenses = ["adversarial", "integration", "design"] }]')
        self.assertNotEqual(gated, THREE_PASS_PIN)
        self.tearDown()
        type(self).PIN_TEXT = gated + ('\n[[schedule.conditional]]\nlenses = ["design"]\n'
                                       'passes = ["round", "reconciliation"]\npaths = ["src/ui/"]\n')
        with_design = ["adversarial", "integration", "design"]
        repaired = ["adversarial", "plan-delivery", "record", "design"]
        try:
            self.setUp()
            with self.subTest("no file under the paths: Surface: no still means no design lens"):
                self.passed("plan", self.start)
                self.tick_work()
                sha = self.build()
                self.passed("round", sha, lenses=with_design)
                self.passed("completion", sha)
                self.stamp3_refuses(sha, "the schedule expects medium with ['adversarial', 'integration']")
            self.setUp_again()
            with self.subTest("a UI file changed and the round has no LENS design"):
                self.passed("plan", self.start)
                self.tick_work()
                sha = self.ui_build()
                self.passed("round", sha)
                self.passed("completion", sha)
                self.stamp3_refuses(sha, f"the schedule expects medium with {with_design}")
            self.setUp_again()
            with self.subTest("the round has it and the reconciliation does not"):
                self.passed("plan", self.start)
                self.tick_work()
                sha = self.ui_build()
                self.passed("round", sha, lenses=with_design)
                self.passed("completion", sha, "P2", True)
                fixed = self.build("repair")
                self.passed("reconciliation", fixed)
                self.stamp3_refuses(fixed, f"the schedule expects medium with {repaired}", verdict="reconciled")
            self.setUp_again()
            with self.subTest("LENS design: clean on the round and the reconciliation stamps"):
                self.passed("plan", self.start)
                self.tick_work()
                sha = self.ui_build()
                self.passed("round", sha, lenses=with_design)
                self.passed("completion", sha, "P2", True)
                fixed = self.build("repair")
                self.passed("reconciliation", fixed, lenses=repaired)
                data = self.stamp3(fixed, verdict="reconciled")
                self.assertEqual(data["schedule"]["conditional"][0]["lenses"], ["design"])
                found = (self.root / self.FILE).read_text(encoding="utf-8")
                self.assertEqual(found.count("LENS design: clean"), 2)
        finally:
            type(self).PIN_TEXT = THREE_PASS_PIN

    def test_a_changed_promise_between_the_completion_and_its_reconciliation_refuses(self):
        todo = self.root / "todo/00-workspace/TODO-01-a.md"
        self.passed("plan", self.start)
        self.tick_work()
        sha = self.build()
        self.passed("round", sha)
        self.passed("completion", sha, "P2", True)
        text = todo.read_text(encoding="utf-8")
        todo.write_text(text.replace("- [x] Work.", "- [x] Work, but less of it.", 1), encoding="utf-8")
        narrowed = self.commit("narrow the section")
        self.passed("reconciliation", narrowed)
        self.stamp3_refuses(narrowed, "the section's contract changed", verdict="reconciled")

    def test_a_promise_narrowed_in_one_reconciliation_and_restored_in_the_next_stamps(self):
        # D02 T02 §5 (2026-11-12): reconciliation 1 restated a checkpoint, returned gaps for it, and reconciliation 2
        # restored it byte for byte; the stamp still refused, checking every reconciliation's candidate.
        todo = self.root / "todo/00-workspace/TODO-01-a.md"
        self.passed("plan", self.start)
        self.tick_work()
        sha = self.build()
        self.passed("round", sha)
        self.passed("completion", sha, "P2", True)
        text = todo.read_text(encoding="utf-8")
        todo.write_text(text.replace("- [x] Work.", "- [x] Work, but less of it.", 1), encoding="utf-8")
        narrowed = self.commit("narrow the section")
        self.passed("reconciliation", narrowed, "P1", True)
        todo.write_text(text, encoding="utf-8")
        restored = self.commit("restore the promise")
        self.passed("reconciliation", restored)
        self.stamp3(restored, verdict="reconciled")
    def restored_after_a_complete_reconciliation(self, restore=True, change=True, ask=None):
        """Plan, round, failed completion, a reconciliation that ends complete (HIGHEST: none) on a candidate that
        changed the promise (or not), then one on a candidate that restores it (or not). D01 T02 §11."""
        todo = self.root / "todo/00-workspace/TODO-01-a.md"
        self.passed("plan", self.start)
        self.tick_work()
        sha = self.build()
        self.passed("round", sha)
        self.passed("completion", sha, "P2", True)
        text = todo.read_text(encoding="utf-8")
        if change:
            todo.write_text(text.replace("- [x] Work.", "- [x] Work, but less of it.", 1), encoding="utf-8")
            changed = self.commit("reword the section")
        else:
            changed = self.build("repair")
        if ask:
            ask("reconciliation", changed)
        self.passed("reconciliation", changed)
        if restore:
            todo.write_text(text, encoding="utf-8")
            restored = self.commit("restore the promise")
        else:
            restored = self.build("another repair")
        if ask:
            ask("reconciliation", restored)
        self.passed("reconciliation", restored)
        return restored

    def test_a_promise_restored_after_a_complete_reconciliation_stamps(self):
        self.tearDown()
        type(self).PIN_TEXT = THREE_PASS_PIN.replace("pass_cap = 45", 'pass_cap = 45\nblocking = ["P1", "P2"]')
        try:
            self.setUp()
            with self.subTest("restored: stamps, and the receipt validates"):
                restored = self.restored_after_a_complete_reconciliation()
                data = self.stamp3(restored, verdict="reconciled")
                self.assertEqual((data["passes_spent"], data["completion"]["candidate"]), (5, restored))
                self.assertTrue(tg.graph(self.root)["D00 T01 §1"].done)   # the graph reads the receipt back
            self.setUp_again()
            with self.subTest("still changed after the second reconciliation: refused"):
                sha = self.restored_after_a_complete_reconciliation(restore=False)
                self.stamp3_refuses(sha, "the section's contract changed", verdict="reconciled")
            self.setUp_again()
            with self.subTest("a real complete before it (the promise unchanged): no further pass"):
                sha = self.restored_after_a_complete_reconciliation(restore=False, change=False)
                self.stamp3_refuses(sha, "only the last reconciliation", verdict="reconciled")
        finally:
            type(self).PIN_TEXT = THREE_PASS_PIN

    def test_the_dispatched_recovery_chain_stamps(self):
        # Completion review of D01 T02 §11: one chain, each reconciliation first asked of the dispatcher's own order
        # check on this repository (with the todo library beside it, as an install has it), then stamped and read back.
        self.tearDown()
        type(self).PIN_TEXT = THREE_PASS_PIN.replace("pass_cap = 45", 'pass_cap = 45\nblocking = ["P1", "P2"]')
        try:
            self.setUp()
            dispatch = tg.review_dispatch()
            (self.root / "scripts/lib").mkdir(parents=True, exist_ok=True)
            shutil.copyfile(SCRIPTS / "lib/todo_graph.py", self.root / "scripts/lib/todo_graph.py")
            schedule = tg.committed_pin(self.root, self.start, "D00 T01 §1")["schedule"]
            asked = []

            def ask(kind, candidate):
                dispatch.check_three_pass_order(kind, str(self.root / self.FILE), candidate, schedule)
                asked.append(candidate)
            with unittest.mock.patch.object(dispatch, "ROOT", self.root):
                restored = self.restored_after_a_complete_reconciliation(ask=ask)
                self.assertEqual(asked[-1], restored)
                # The chain is settled now: the dispatcher takes no further pass.
                with self.assertRaises(dispatch.Refused):
                    ask("reconciliation", self.build("one more"))
            data = self.stamp3(restored, verdict="reconciled")
            self.assertEqual((data["passes_spent"], data["completion"]["candidate"]), (5, restored))
            self.assertTrue(tg.graph(self.root)["D00 T01 §1"].done)
        finally:
            type(self).PIN_TEXT = THREE_PASS_PIN

    def test_a_complete_footer_never_overrides_a_blocking_finding(self):
        # Round 1 of D00 T01 §3: HIGHEST: P1 then COMPLETION: complete stamped as complete.
        with self.subTest("completion"):
            sha = self.chain(completion=("P1", False))
            self.stamp3_refuses(sha, "ends complete but declares HIGHEST: P1")
        self.setUp_again()
        with self.subTest("reconciliation"):
            sha = self.chain(completion=("P2", True), reconciliations=[("P2", False)])
            self.stamp3_refuses(sha, "ends complete but declares HIGHEST: P2", verdict="reconciled")
        self.tearDown()
        type(self).PIN_TEXT = THREE_PASS_PIN.replace("pass_cap = 45", 'pass_cap = 45\nblocking = ["P1", "P2"]')
        try:
            self.setUp()
            with self.subTest("a finding below the blocking levels does not hold a complete verdict"):
                self.stamp3(self.chain(completion=("P3", False)))
            self.setUp_again()
            with self.subTest("no HIGHEST line counts as P1 under a pin that names blocking levels"):
                # Round 2 of D00 T01 §3.
                self.passed("plan", self.start)
                self.tick_work()
                sha = self.build()
                self.passed("round", sha)
                self.passed("completion", sha, review="1. [P1] open.\nLENS plan-delivery: findings\n"
                                                      "LENS record: clean\nCOMPLETION: complete")
                self.stamp3_refuses(sha, "declares no HIGHEST line, which counts as P1")
        finally:
            type(self).PIN_TEXT = THREE_PASS_PIN

    def test_a_failed_plan_attempt_is_held_to_the_pin_at_its_own_candidate(self):
        # Round 1 of D00 T01 §3: an attempt that returned no review, made under another pin on another candidate,
        # was judged against the pin of the plan review that later returned.
        dispatch = tg.review_dispatch()
        (self.root / tg.PIN).write_text(THREE_PASS_PIN.replace('plan = { effort = "medium"', 'plan = { effort = "high"'),
                                        encoding="utf-8")
        other = self.commit("another pin, on another candidate")
        failed = {"writer": "claude", "reviewer": None, "effort": "high", "lenses": ["plan"], "review": None,
                  "failover": [{"reviewer": "astra", "reason": "timed out"}]}
        dispatch.record_completion(self.root / self.FILE, failed, "2026-10-22T00:00:00Z", other, kind="plan")
        self.stamp3(self.chain())
        # The same failed attempt on the returned plan review's own candidate is held to that pin, and refuses.
        self.setUp_again()
        dispatch.record_completion(self.root / self.FILE, failed, "2026-10-22T00:00:00Z", self.start, kind="plan")
        self.stamp3_refuses(self.chain(), "ran at high")

    def test_a_chain_reviewed_through_antigravity_stamps(self):
        # Completion review of D00 T01 §3: the dispatcher recorded no effort for Antigravity, and the replay refused.
        self.tearDown()
        type(self).PIN_TEXT = THREE_PASS_PIN.replace('cli = "codex"\nmodel = "m"\neffort = "medium"',
                                                     'cli = "agy"\nmodel = "gemini-4-argon-medium"')
        type(self).CLI, type(self).MODEL = "agy", "gemini-4-argon-medium"
        try:
            self.setUp()
            data = self.stamp3(self.chain())
            self.assertEqual((data["plan"]["effort"], data["plan"]["model"]), ("medium", "gemini-4-argon-medium"))
        finally:
            type(self).PIN_TEXT, type(self).CLI, type(self).MODEL = THREE_PASS_PIN, "codex", "m"

    def test_the_help_and_the_refusal_name_the_three_pass_order_and_verdicts(self):
        cli = subprocess.run([sys.executable, str(SCRIPTS / "todo-graph.py"), "stamp", "--help"],
                             capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(cli.returncode, 0, cli.stderr)
        text = " ".join(cli.stdout.split()).replace("- ", "-")   # argparse may wrap after a hyphen
        for needle in ("reconciled (three-pass pins)", "completed (rotation pins only)", "below the pin's blocking"):
            self.assertIn(needle, text)
        self.tick_work()
        with self.assertRaises(tg.Refused) as ctx:
            tg.stamp(self.root, "D00 T01 §1", self.sha, [{"round": 1, "report": self.FILE, "verdict": "clean"}],
                     ["true -> ok"], "2026-10-24", plan=self.FILE)
        self.assertIn("under a three-pass pin after the round, under a rotation pin before the rounds",
                      str(ctx.exception))

    def test_a_step_without_an_effort_is_recorded_and_replayed_with_none(self):
        self.tearDown()
        type(self).PIN_TEXT = THREE_PASS_PIN.replace(
            'rounds = [{ effort = "medium", lenses', 'rounds = [{ lenses')
        try:
            self.setUp()
            self.passed("plan", self.start)
            self.tick_work()
            sha = self.build()
            self.passed("round", sha, effort=None)
            self.passed("completion", sha)
            self.stamp3(sha)
            self.setUp_again()
            self.passed("plan", self.start)
            self.tick_work()
            sha = self.build()
            self.passed("round", sha)                       # recorded at medium, which the step does not set
            self.passed("completion", sha)
            self.stamp3_refuses(sha, "ran at medium")
        finally:
            type(self).PIN_TEXT = THREE_PASS_PIN

    def test_ticking_boxes_and_recording_evidence_does_not_change_the_promise(self):
        todo = self.root / "todo/00-workspace/TODO-01-a.md"
        before = tg.section_contract(self.root, self.start, "D00 T01 §1")
        self.tick_work()
        text = todo.read_text(encoding="utf-8")
        todo.write_text(text.replace("- [x] Work.", "- [x] Work. **Corrected 2026-11-11:** a note.", 1),
                        encoding="utf-8")
        ticked = self.commit("ticked, with a dated note")
        self.assertEqual(tg.section_contract(self.root, ticked, "D00 T01 §1"), before)
        todo.write_text(text.replace("- [x] Work.", "- [x] Other work.", 1), encoding="utf-8")
        changed = self.commit("another promise")
        self.assertNotEqual(tg.section_contract(self.root, changed, "D00 T01 §1"), before)

    def test_a_section_that_began_under_rotation_is_held_to_it_after_the_switch(self):
        self.tearDown()
        type(self).PIN_TEXT = UNIFORM_PIN
        try:
            Stamp.setUp(self)              # the rotation fixture: plan, completion and one clean round
        finally:
            type(self).PIN_TEXT = THREE_PASS_PIN
        self.tick_work()
        (self.root / tg.PIN).write_text(THREE_PASS_PIN, encoding="utf-8")
        switched = self.commit("switch to three-pass")
        self.write_completion(candidate=switched)
        receipt = self.stamp("D00 T01 §1", switched, self.reviews, ["true -> ok"], "2026-10-24")
        data = json.loads((self.root / receipt).read_text(encoding="utf-8"))
        self.assertEqual(data["schedule_sha"], self.start)
        self.assertNotIn("policy", data["schedule"])
        self.assertNotIn("passes_spent", data)
        self.assertTrue(tg.graph(self.root)["D00 T01 §1"].done)


# ThreePassStamp borrows Stamp's fixture and helpers, not its tests: those are the rotation contract and run once,
# in Stamp. unittest skips a name that is not callable.
for _name in dir(Stamp):
    if _name.startswith("test_") and _name not in vars(ThreePassStamp):
        setattr(ThreePassStamp, _name, None)


class PlanTable(Tree):
    def test_title_that_wraps_the_generated_plan_table_refuses_naming_the_section(self):
        # Within the 88-character cell limit, but the plan pads every row to it: 80 characters make rows wider than 120.
        self.write(todo_file([(1, "A", 0, "none", "--"), (2, "B" * 80, 0, "none", "--")]))
        with self.assertRaises(tg.Refused) as ctx:
            tg.projections(self.root, sync=True)
        self.assertIn("plan table for phase 0 wraps raw md", str(ctx.exception))
        self.assertIn("D00 T01 §2", str(ctx.exception))
        self.assertFalse((self.root / tg.PLAN).exists(), "a wrapping plan was written")
        self.write(todo_file([(1, "A", 0, "none", "--"), (2, "B" * 76, 0, "none", "--")]))
        tg.projections(self.root, sync=True)


class QueryPlan(Tree):
    """`query plan`: the plan's names and every section's status, for readers that must not parse todo/."""

    def setUp(self):
        super().setUp()
        self.write(todo_file([(1, "A", 0, "none", "--"), (2, "B", 0, "owner-decision", "--"),
                              (3, "C", 0, "none", "§1")]))
        self.write(todo_file([(1, "D", 1, "none", "--")], ident="beta", domain="01-later", status="draft"),
                   domain="01-later")
        (self.root / "todo/plan.json").write_text(json.dumps({
            "title": "Site plan", "acceptance": "`design/SPEC.md`.", "phases": {"0": "Tooling"}}), encoding="utf-8")
        shutil.copytree(SCRIPTS, self.root / "scripts", ignore=shutil.ignore_patterns("__pycache__"))

    def query(self):
        return subprocess.run([sys.executable, str(self.root / "scripts/todo-graph.py"), "query", "plan"],
                              capture_output=True, text=True, encoding="utf-8")

    def test_query_plan_reports_config_and_every_section(self):
        result = self.query()
        self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads(result.stdout)
        self.assertEqual((plan["title"], plan["acceptance"]), ("Site plan", "`design/SPEC.md`."))
        self.assertEqual(plan["phases"]["0"], "Tooling")
        self.assertEqual([(s["ref"], s["status"]) for s in plan["sections"]], [
            ("D00 T01 §1", "ready"), ("D00 T01 §2", "blocked"), ("D00 T01 §3", "blocked"), ("D01 T01 §1", "deferred")])
        self.assertEqual(plan["sections"][2]["depends"], ["D00 T01 §1"])

    def test_plan_status_edge_cases(self):
        # Verified reads verified even in an inactive file; waiting on another file or an open prerequisite is blocked.
        spec = importlib.util.spec_from_file_location("todo_graph_cli", SCRIPTS / "todo-graph.py")
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)

        def row(ref, done=False, status="active", needs=(), depends=()):
            return types.SimpleNamespace(ref=ref, done=done, status=status, needs=list(needs), depends=list(depends),
                                         waiting=tuple(sorted(set(needs) & tg.WAITING)))

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
    """The CLI's output is a contract other programs parse (process-plan, any program showing the plan): always UTF-8."""

    def test_query_output_is_utf8_whatever_the_console_code_page(self):
        self.write(todo_file([(1, "Only", 0, "none", "--")]))
        shutil.copytree(SCRIPTS, self.root / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
        env = {**os.environ, "PYTHONIOENCODING": "cp1252", "PYTHONUTF8": "0"}
        result = subprocess.run([sys.executable, str(self.root / "scripts/todo-graph.py"), "query", "ready"],
                                capture_output=True, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([r["ref"] for r in json.loads(result.stdout.decode("utf-8"))], ["D00 T01 §1"])


class QueryFrozen(Tree):
    """D03 T01 §14: `query frozen` reports Freeze-check coverage from the tree alone, faults and all."""

    def frozen_file(self, ident, rows, missing=()):
        text = todo_file(rows, ident=ident).replace("status: active", "status: active\nfrozen: true")
        for n, title, *_ in rows:
            if n not in missing:
                text = text.replace(f"## {n}. {title}\n\n", f"## {n}. {title}\n\n**Freeze check:** holds.\n\n", 1)
        return text

    def build(self):
        self.write(self.frozen_file("alpha", [(1, "A", 0, "none", "--"), (2, "B", 0, "none", "--"),
                                              (3, "C", 0, "none", "--")]))
        self.write(self.frozen_file("beta", [(1, "D", 0, "none", "--"), (2, "E", 0, "none", "--")], missing=(2,)),
                   name="TODO-02-b.md")
        self.write(todo_file([(1, "F", 0, "none", "--")], ident="gamma"), name="TODO-03-c.md")
        self.write("---\nnot a field line\n---\n\n# TODO-04 -- D\n", name="TODO-04-d.md")
        return {"files": [{"path": "todo/00-workspace/TODO-01-a.md", "sections": 3, "freeze_checks": 3,
                           "missing": []},
                          {"path": "todo/00-workspace/TODO-02-b.md", "sections": 2, "freeze_checks": 1,
                           "missing": ["D00 T02 §2"]}],
                "unreadable": ["todo/00-workspace/TODO-04-d.md"]}

    def test_each_frozen_file_has_its_coverage_in_path_order(self):
        expected = self.build()
        self.assertEqual(tg.frozen_files(self.root), expected)

    def test_a_tree_whose_validation_refuses_is_still_reported(self):
        expected = self.build()
        path = self.root / "todo/00-workspace/TODO-01-a.md"  # a stamp whose receipt is missing
        path.write_text(path.read_text(encoding="utf-8").replace("| 1 | §1 | A | -- | [ ] |", "| 1 | §1 | A | -- | [x] |")
                        .replace("\n## 2.", f"\n> **Verified:** 2026-11-13 | §1 | {'0' * 40}\n"
                                 "> **Review:** `docs/reviews/d00-t01-s1.json`\n\n## 2.", 1), encoding="utf-8")
        with self.assertRaises(tg.Refused):
            tg.graph(self.root)
        self.assertEqual(tg.frozen_files(self.root), expected)
        shutil.copytree(SCRIPTS, self.root / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
        result = subprocess.run([sys.executable, str(self.root / "scripts/todo-graph.py"), "query", "frozen"],
                                capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout.decode("utf-8")), expected)

    def test_a_freeze_check_in_any_spelling_the_validator_reads_counts(self):
        text = self.frozen_file("alpha", [(1, "A", 0, "none", "--"), (2, "B", 0, "none", "--")], missing=(1, 2))
        text = text.replace("## 1. A\n\n", "## 1. A\n\n> **Freeze check:** quoted.\n\n", 1)
        self.write(text.replace("## 2. B\n\n", "## 2. B\n\n**Freeze check:**   spaced.\n\n", 1))
        tg.graph(self.root)  # the validator accepts both spellings
        self.assertEqual(tg.frozen_files(self.root)["files"][0]["missing"], [])

    def test_no_frozen_file_is_an_empty_list_and_no_tree_refuses(self):
        self.write(todo_file([(1, "F", 0, "none", "--")]))
        self.assertEqual(tg.frozen_files(self.root), {"files": [], "unreadable": []})
        shutil.rmtree(self.root / "todo")
        with self.assertRaises(tg.Refused):
            tg.frozen_files(self.root)


class QuerySequence(Tree):
    """D03 T01 §15: the longest open chain and the sections each stamped section's completion review filed."""

    def test_the_longest_open_chain_runs_from_prerequisite_to_consumer(self):
        self.write(todo_file([(1, "A", 0, "none", "--"), (2, "B", 0, "none", "§1"), (3, "C", 0, "none", "§2"),
                              (4, "D", 0, "none", "--"), (5, "E", 0, "none", "§4")]))
        rows = tg.graph(self.root)
        self.assertEqual(tg.longest_chain(rows), ["D00 T01 §1", "D00 T01 §2", "D00 T01 §3"])
        rows["D00 T01 §1"].done = True  # a stamped section ends the path
        self.assertEqual(tg.longest_chain(rows), ["D00 T01 §2", "D00 T01 §3"])
        for row in rows.values():
            row.done = True
        self.assertEqual(tg.longest_chain(rows), [])

    def test_a_chain_longer_than_the_recursion_limit_is_found(self):
        n = sys.getrecursionlimit() + 200
        rows = {f"D00 T01 §{i}": tg.Section(f"D00 T01 §{i}", "todo/00-workspace/TODO-01-a.md", i, "S", 0,
                                            [f"D00 T01 §{i - 1}"] if i > 1 else [], [], False, "active", "", "", i)
                for i in range(1, n + 1)}
        chain = tg.longest_chain(rows)
        self.assertEqual((len(chain), chain[0], chain[-1]), (n, "D00 T01 §1", f"D00 T01 §{n}"))

    def test_of_two_equal_chains_the_one_plan_order_reaches_first_wins(self):
        table = ("| 1 | §3 | C | -- | [ ] |\n| 2 | §4 | D | §3 | [ ] |\n"
                 "| 3 | §1 | A | -- | [ ] |\n| 4 | §2 | B | §1 | [ ] |")
        self.write(todo_file([(1, "A", 0, "none", "--"), (2, "B", 0, "none", "§1"), (3, "C", 0, "none", "--"),
                              (4, "D", 0, "none", "§3")], table_override=table))
        self.assertEqual(tg.longest_chain(tg.graph(self.root)), ["D00 T01 §3", "D00 T01 §4"])

    def test_couplings_come_from_each_stamped_rows_own_receipt(self):
        self.write(todo_file([(1, "A", 0, "none", "--"), (2, "B", 0, "none", "--"), (3, "C", 0, "none", "§2"),
                              (4, "D", 0, "none", "--"), (5, "E", 0, "none", "--")]))
        rows = tg.graph(self.root)
        receipts = {"D00 T01 §1": {"completion": {"filed": ["D00 T01 §2", "D00 T01 §3"]}},
                    "D00 T01 §4": {"completion": {"filed": []}}, "D00 T01 §5": {}}  # §5: before completion reviews
        for ref, data in receipts.items():
            path = self.root / f"reviews/{ref[-1]}.json"  # a project's own receipts folder, not docs/reviews
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data), encoding="utf-8")
            rows[ref].done, rows[ref].receipt = True, path.relative_to(self.root).as_posix()
        self.assertEqual(tg.filing_couplings(self.root, rows),
                         [{"filer": "D00 T01 §1", "filed": "D00 T01 §2", "state": "ready"},
                          {"filer": "D00 T01 §1", "filed": "D00 T01 §3", "state": "blocked"}])
        rows["D00 T01 §2"].done = True  # the filed section stamped: its state is read afresh
        self.assertEqual([p["state"] for p in tg.filing_couplings(self.root, rows)], ["verified", "ready"])


class HostNeeds(Tree):
    """D03 T01 §10: a row needing a host this session does not meet is held, under `--have` and `detect`."""

    def setUp(self):
        super().setUp()
        self.write(todo_file([(1, "Host", 0, "windows-host", "--"), (2, "Two hosts", 0, "windows-host, arm64-host", "--"),
                              (3, "After four", 0, "none", "§4"), (4, "Waits", 0, "owner-decision", "--")]))
        self.write(todo_file([(1, "Draft", 0, "none", "--")], ident="beta", status="draft"), name="TODO-02-b.md")
        shutil.copytree(SCRIPTS, self.root / "scripts", ignore=shutil.ignore_patterns("__pycache__"))

    def cli(self, *args, env=None):
        result = subprocess.run([sys.executable, str(self.root / "scripts/todo-graph.py"), *args], capture_output=True,
                                env={**os.environ, "CONCLAVE_HAVE": "", **(env or {})})
        out = result.stdout.decode("utf-8")
        return result.returncode, (json.loads(out) if out.strip().startswith(("[", "{")) else out.strip())

    def ready(self, *have):
        return [r["ref"] for r in self.cli("query", "ready", *(("--have", have[0]) if have else ()))[1]]

    def test_query_ready_holds_a_row_whose_host_is_absent(self):
        self.assertEqual(self.ready(), ["D00 T01 §1", "D00 T01 §2"])  # without the flag: as before
        self.assertEqual(self.ready("windows-host"), ["D00 T01 §1"])
        self.assertEqual(self.ready(""), [])
        self.assertEqual(self.ready("windows-host,arm64-host"), ["D00 T01 §1", "D00 T01 §2"])  # every Need it names
        code, stats = self.cli("query", "stats", "--have", "")
        self.assertEqual((code, stats["ready"], stats["blocked"]), (0, 0, 5))  # the draft file's section too

    def test_resolve_names_the_missing_host_and_keeps_every_other_state(self):
        code, out = self.cli("resolve", "D00 T01 §2", "--have", "windows-host")
        self.assertEqual((code, out["exit"], out["missing_needs"]), (4, 4, ["arm64-host"]))
        code, out = self.cli("resolve", "D00 T01 §2", "--have", "windows-host,arm64-host")
        self.assertEqual((code, out["missing_needs"]), (0, []))
        everything = "windows-host,arm64-host,owner-decision"
        for ref in ("D00 T01 §3", "D00 T01 §4", "D00 T02 §1"):  # an unmet dependency, a waiting Need, a draft file
            with self.subTest(ref):
                self.assertEqual(self.cli("resolve", ref, "--have", everything)[0], 4)
        code, out = self.cli("resolve", "D00 T01 §2")
        self.assertEqual(code, 0)
        self.assertNotIn("missing_needs", out)

    def test_auto_is_the_set_detect_prints(self):
        code, printed = self.cli("detect", env={"CONCLAVE_HAVE": "attended, arm64-host"})
        self.assertEqual(code, 0)
        self.assertIn("attended", printed.split(","))
        auto = self.cli("query", "ready", "--have", "auto", env={"CONCLAVE_HAVE": "windows-host,arm64-host"})[1]
        self.assertEqual([r["ref"] for r in auto], ["D00 T01 §1", "D00 T01 §2"])
        self.assertNotIn("attended", self.cli("detect")[1].split(","))  # declared only while CONCLAVE_HAVE names it

    @staticmethod
    def fake_winreg(word):
        """A stand-in for winreg whose Word.Application key is there (`word`) or not."""
        def open_key(root, name):
            if not word:
                raise OSError("no such key")
            return object()
        return types.SimpleNamespace(HKEY_CLASSES_ROOT=0, OpenKey=open_key, CloseKey=lambda key: None)

    def probed(self, name="posix", machine="AMD64", env=None, soffice=None, word=False):
        """What `detect` prints on a machine described by its arguments, every probe mocked, as a set; checked against
        builtin_needs, which it prints with no project probe and nothing declared."""
        base = {"DISPLAY": "", "WAYLAND_DISPLAY": "", "SESSIONNAME": "", "CONCLAVE_HAVE": ""}
        spec = importlib.util.spec_from_file_location("todo_graph_cli_under_test", SCRIPTS / "todo-graph.py")
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        out = io.StringIO()
        class OsAs:  # the library's `os` with another platform name; pathlib and the rest keep the real one
            def __getattr__(self, attr):
                return name if attr == "name" else getattr(os, attr)
        with mock.patch.dict(os.environ, {**base, **(env or {})}), mock.patch.object(tg, "os", OsAs()), \
                mock.patch("platform.machine", return_value=machine), \
                mock.patch("shutil.which", return_value=soffice), \
                mock.patch.dict(sys.modules, {"winreg": self.fake_winreg(word)}), \
                mock.patch.object(sys, "argv", ["todo-graph.py", "detect"]), \
                mock.patch.object(cli, "session_needs", lambda: tg.session_needs(self.root)), \
                mock.patch("sys.stdout", out):
            self.assertEqual(cli.main(), 0)
            direct = tg.builtin_needs()
        printed = {v for v in out.getvalue().strip().split(",") if v}
        self.assertEqual(printed, direct)
        return printed

    def test_the_built_in_probes(self):
        self.assertEqual(self.probed(), set())  # every probe failing: no Need
        self.assertEqual(self.probed(machine="aarch64"), {"arm64-host"})
        self.assertEqual(self.probed(machine="ARM64"), {"arm64-host"})
        self.assertEqual(self.probed(env={"DISPLAY": ":0"}), {"display-session"})
        self.assertEqual(self.probed(env={"WAYLAND_DISPLAY": "wayland-0"}), {"display-session"})
        self.assertEqual(self.probed(soffice="/usr/bin/soffice"), {"libreoffice"})
        self.assertEqual(self.probed(name="nt"), {"windows-host"})  # no session, no Word
        self.assertEqual(self.probed(name="nt", env={"SESSIONNAME": "Console"}), {"windows-host", "display-session"})
        self.assertEqual(self.probed(name="nt", env={"SESSIONNAME": "RDP-Tcp#0"}), {"windows-host", "display-session"})
        self.assertEqual(self.probed(name="nt", env={"SESSIONNAME": "Services"}), {"windows-host"})
        self.assertEqual(self.probed(name="nt", word=True), {"windows-host", "office"})
        self.assertEqual(self.probed(word=True), set())  # Word's key is read on Windows only

    def test_a_configured_probe_makes_its_row_ready_under_auto(self):
        self.write(todo_file([(1, "Needs a GPU", 0, "gpu", "--")], ident="gamma"), name="TODO-03-c.md")
        for exit_code, ready in ((0, True), (1, False)):
            with self.subTest(exit_code=exit_code):
                self.plan(needs=["windows-host", "arm64-host", "owner-decision", "gpu"],
                          probes={"gpu": [sys.executable, "-c", f"raise SystemExit({exit_code})"]})
                self.assertEqual("D00 T03 §1" in self.ready("auto"), ready)
                code, out = self.cli("resolve", "D00 T03 §1", "--have", "auto")
                self.assertEqual((code, out["missing_needs"]), (0, []) if ready else (4, ["gpu"]))

    def test_a_configured_probe_that_times_out_holds_its_row(self):
        self.write(todo_file([(1, "Needs a GPU", 0, "gpu", "--")], ident="gamma"), name="TODO-03-c.md")
        self.plan(needs=["windows-host", "arm64-host", "owner-decision", "gpu"],
                  probes={"gpu": [sys.executable, "-c", f"import time; time.sleep({tg.PROBE_TIMEOUT + 20})"]})
        started = time.monotonic()
        self.assertNotIn("D00 T03 §1", self.ready("auto"))
        self.assertLess(time.monotonic() - started, tg.PROBE_TIMEOUT + 15)

    def test_a_projects_probes_prove_its_own_needs(self):
        needs = ["windows-host", "arm64-host", "owner-decision", "ffmpeg-jxl", "gpu"]
        for probes, fragment in (({"nope": ["x"]}, "probes names 'nope'"), ({"gpu": "x"}, "probes 'gpu' must be"),
                                 ({"gpu": []}, "probes 'gpu' must be"), ({"owner-decision": ["x"]}, "probes names"),
                                 ([], "probes must be an object")):
            with self.subTest(probes):
                self.plan(needs=needs, probes=probes)
                self.refuses("todo/plan.json: " + fragment)
        self.plan(needs=needs, probes={"ffmpeg-jxl": [sys.executable, "-c", "raise SystemExit(0)"],
                                       "gpu": [sys.executable, "-c", "raise SystemExit(1)"]})
        self.assertEqual(tg.session_needs(self.root) & {"ffmpeg-jxl", "gpu"}, {"ffmpeg-jxl"})

    def plan(self, **keys):
        (self.root / "todo/plan.json").write_text(json.dumps(keys), encoding="utf-8")

    def test_a_probe_runs_from_the_project_root_wherever_it_is_asked(self):
        (self.root / "scripts/check-host.py").write_text("raise SystemExit(0)\n", encoding="utf-8")
        self.plan(needs=["windows-host", "arm64-host", "owner-decision", "gpu"],
                  probes={"gpu": [sys.executable, "scripts/check-host.py"]})
        cwd = os.getcwd()
        try:
            os.chdir(self.root / "todo")  # a relative probe must not depend on where the graph was asked from
            self.assertIn("gpu", tg.session_needs(self.root))
        finally:
            os.chdir(cwd)

    def test_a_probe_that_hangs_is_stopped_with_its_children(self):
        pid_file = self.root / "child.pid"
        script = ("import subprocess, sys, time; "
                  "p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); "
                  f"open(r'{pid_file}', 'w').write(str(p.pid)); time.sleep(60)")
        started = time.monotonic()
        self.assertFalse(tg._run_probe([sys.executable, "-c", script], timeout=3))
        self.assertLess(time.monotonic() - started, 20)
        child = int(pid_file.read_text())
        for _ in range(50):
            if not self.alive(child):
                break
            time.sleep(0.1)
        self.assertFalse(self.alive(child), "the probe's child outlived its timeout")

    @staticmethod
    def alive(pid):
        if os.name == "nt":
            out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
            return str(pid) in out
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        return True

    def test_every_runner_asks_with_the_sessions_set(self):
        command = re.compile(r"(?:python3?|<python>) scripts/todo-graph\.py (?:query ready|resolve)\b[^`\n]*")
        for agent in (".claude", ".agents", ".codex"):
            for skill in ("process-plan", "process-phase"):
                text = (REPO / "kits/todo/templates" / agent / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")
                found = command.findall(text)
                self.assertTrue(found, f"{agent} {skill}")
                for line in found:
                    self.assertIn("--have auto", line, f"{agent} {skill}: {line}")
        guard = (REPO / "kits/todo/templates/scripts/campaign_guard.py").read_text(encoding="utf-8")
        self.assertIn('"query", "ready", *extra]', guard)  # the Stop hook's count asks with the set first
        self.assertIn('for extra in (["--have", "auto"], []):', guard)


class Adoption(Tree):
    """D03 T01 §9: the stamps a project made under its own tooling, frozen once at adoption."""

    REGISTRY = "docs/reviews/legacy-receipts.json"

    def setUp(self):
        super().setUp()
        for args in (["init", "-q"], ["config", "user.email", "t@example.com"], ["config", "user.name", "T"]):
            subprocess.run(["git", "-C", str(self.root), *args], check=True)

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), *args], check=True, capture_output=True,
                              text=True).stdout.strip()

    def commit(self, message="x"):
        self.git("add", "-A")
        self.git("commit", "-qm", message)
        return self.git("rev-parse", "HEAD")

    @staticmethod
    def foreign(text, stamp, drop_phase=False):
        """§1 of a two-section file as a project of its own stamped it: no Build order, ticked, its own stamp line."""
        text = text.replace("| 1 | §1 | A | -- | [ ] |", "| 1 | §1 | A | -- | [x] |")
        head, rest = text.split("## 1. A\n", 1)
        first, after = rest.split("\n## 2.", 1)
        first = first.replace("**Build order:**\n\n1. Do it. Done when: it shows.\n\n", "").replace("- [ ] ", "- [x] ")
        if drop_phase:
            first = first.replace("**Phase:** 0\n", "")
        return head + "## 1. A\n" + first.rstrip("\n") + "\n\n" + stamp + "\n\n## 2." + after

    def build(self):
        """File 01 stamped in RasterFold's format with a receipt of its own; file 02 in Impossible OS's, phase-less."""
        a = todo_file([(1, "A", 0, "none", "--"), (2, "B", 0, "none", "--")])
        b = todo_file([(1, "A", 0, "none", "--"), (2, "B", 0, "none", "--")], ident="beta")
        self.write(a)
        self.write(b, name="TODO-02-b.md")
        base = self.commit("base")
        self.write(self.foreign(a, f"> **Verified:** 2026-09-28 | §1 | {base}\n"
                                   "> **Review:** `docs/reviews/rf/d00-t01-s1.md`"))
        self.write(self.foreign(b, f"> **Verified:** 2026-04-17 | commit `{base[:8]}` | 5/5 items | build OK",
                                drop_phase=True), name="TODO-02-b.md")
        receipt = self.root / "docs/reviews/rf/d00-t01-s1.md"
        receipt.parent.mkdir(parents=True, exist_ok=True)
        receipt.write_text("## Panel\n\nGPT: approve\n", encoding="utf-8")
        self.commit("stamped under the project's own tooling")
        return base

    def repair(self, ref):
        """Bring a reopened fixture section to the kit's format: its Build order back, and a Phase when it has none."""
        name = "TODO-01-a.md" if ref == "D00 T01 §1" else "TODO-02-b.md"
        path = self.root / "todo/00-workspace" / name
        head, rest = path.read_text(encoding="utf-8").split("## 1. A\n", 1)
        first, after = rest.split("\n## 2.", 1)
        if "**Phase:**" not in first:
            first = first.replace("**Needs:**", "**Phase:** 0\n**Needs:**", 1)
        first = first.replace("**Surface:** no\n\n", "**Surface:** no\n\n**Build order:**\n\n1. Do it. Done when: it shows."
                                                    "\n\n", 1)
        path.write_text(head + "## 1. A\n" + first + "\n## 2." + after, encoding="utf-8")
        faults = []
        tg.graph(self.root, faults)
        self.assertFalse([f for f in faults if f[0] == ref], faults)

    def registry(self):
        path = self.root / self.REGISTRY
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None

    def test_adoption_freezes_each_format_with_its_full_commit(self):
        base = self.build()
        with self.assertRaises(tg.Refused):  # before adoption the kit refuses both stamps
            tg.graph(self.root)
        adopted = tg.adopt_stamps(self.root, {"todo/00-workspace/TODO-02-b.md": 0}, date="2026-11-13")
        self.assertEqual(adopted, [("D00 T01 §1", base), ("D00 T02 §1", base)])
        data = self.registry()
        self.assertEqual(data["adoption"], {"commit": self.git("rev-parse", "HEAD"), "date": "2026-11-13"})
        self.assertEqual(data["adopted"]["D00 T01 §1"]["review"], "docs/reviews/rf/d00-t01-s1.md")
        self.assertIsNone(data["adopted"]["D00 T02 §1"]["review"])
        rows = tg.graph(self.root)
        self.assertTrue(rows["D00 T01 §1"].done and rows["D00 T02 §1"].done)

    def test_a_stamp_off_the_branch_is_refused_and_nothing_is_written(self):
        self.build()
        self.git("checkout", "-qb", "side")
        side = self.commit("side") if False else None
        self.git("commit", "-q", "--allow-empty", "-m", "side")
        side = self.git("rev-parse", "HEAD")
        self.git("checkout", "-q", "-")
        path = self.root / "todo/00-workspace/TODO-02-b.md"
        path.write_text(re.sub(r"commit `[0-9a-f]+`", f"commit `{side[:9]}`", path.read_text(encoding="utf-8")),
                        encoding="utf-8")
        with self.assertRaises(tg.Refused) as ctx:
            tg.adopt_stamps(self.root, {"todo/00-workspace/TODO-02-b.md": 0})
        self.assertIn("D00 T02 §1: its stamp names no commit on this branch", str(ctx.exception))
        self.assertIsNone(self.registry())

    def test_adoption_runs_once_even_after_every_section_is_reopened(self):
        self.build()
        tg.adopt_stamps(self.root, {"todo/00-workspace/TODO-02-b.md": 0})
        before = (self.root / self.REGISTRY).read_bytes()
        with self.assertRaises(tg.Refused) as ctx:
            tg.adopt_stamps(self.root, {"todo/00-workspace/TODO-02-b.md": 0})
        self.assertIn("adopted its stamps already", str(ctx.exception))
        self.assertEqual((self.root / self.REGISTRY).read_bytes(), before)
        for ref in ("D00 T01 §1", "D00 T02 §1"):
            tg.unstamp(self.root, ref, "reopened to bring it to the kit's format", "2026-11-14")
            self.repair(ref)  # each reopened section is brought to the kit's format before the next reopens
        self.assertEqual(self.registry()["adopted"], {})
        with self.assertRaises(tg.Refused):
            tg.adopt_stamps(self.root, {"todo/00-workspace/TODO-02-b.md": 0})

    def test_the_phase_map_is_checked_before_anything_is_written(self):
        self.build()
        self.plan_json(phase_list=[0, 3])
        for bad in ({"todo/00-workspace/TODO-02-b.md": True}, {"todo/00-workspace/TODO-02-b.md": 7}, ["x"]):
            with self.subTest(bad):
                with self.assertRaises(tg.Refused):
                    tg.adopt_stamps(self.root, bad)
                self.assertIsNone(self.registry())
        with self.assertRaises(tg.Refused) as ctx:
            tg.adopt_stamps(self.root, {})
        self.assertIn("D00 T02 §1: no phase", str(ctx.exception))
        self.assertIsNone(self.registry())
        tg.adopt_stamps(self.root, {"todo/00-workspace/TODO-02-b.md": 0, "D00 T02 §1": 3})  # the section's own key wins
        self.assertEqual(self.registry()["adopted"]["D00 T02 §1"]["phase"], 3)

    def test_a_bad_body_phase_or_map_key_refuses_even_under_an_override(self):
        self.build()
        path = self.root / "todo/00-workspace/TODO-01-a.md"
        path.write_text(path.read_text(encoding="utf-8").replace("## 1. A\n\n**Phase:** 0", "## 1. A\n\n**Phase:** 9", 1),
                        encoding="utf-8")
        with self.assertRaises(tg.Refused) as ctx:  # the override cannot hide the body's own bad Phase
            tg.adopt_stamps(self.root, {"todo/00-workspace/TODO-02-b.md": 0, "D00 T01 §1": 0})
        self.assertIn("D00 T01 §1: its Phase 9 is not in phase_list", str(ctx.exception))
        self.assertIsNone(self.registry())
        path.write_text(path.read_text(encoding="utf-8").replace("## 1. A\n\n**Phase:** 9", "## 1. A\n\n**Phase:** 0", 1),
                        encoding="utf-8")
        for key in ("D00 T1 §1", "todo/x.md", "00-workspace/TODO-02-b.md"):
            with self.subTest(key):
                with self.assertRaises(tg.Refused):
                    tg.adopt_stamps(self.root, {key: 0})
                self.assertIsNone(self.registry())

    def plan_json(self, **keys):
        (self.root / "todo/plan.json").write_text(json.dumps(keys), encoding="utf-8")

    def test_a_changed_body_or_receipt_refuses_until_unstamp(self):
        self.build()
        tg.adopt_stamps(self.root, {"todo/00-workspace/TODO-02-b.md": 0})
        tg.graph(self.root)
        todo = self.root / "todo/00-workspace/TODO-01-a.md"
        receipt = self.root / "docs/reviews/rf/d00-t01-s1.md"
        original, receipt_bytes = todo.read_bytes(), receipt.read_bytes()
        for name, change in (("body", lambda: todo.write_bytes(original.replace(b"- [x] Work.", b"- [x] Work!", 1))),
                             ("receipt", lambda: receipt.write_bytes(receipt_bytes + b" ")),
                             ("receipt gone", receipt.unlink)):
            with self.subTest(name):
                change()
                self.refuses("adopted section changed since adoption: unstamp it first: D00 T01 §1")
                todo.write_bytes(original)
                receipt.write_bytes(receipt_bytes)
        tg.graph(self.root)

    def test_a_kit_format_adopted_section_is_frozen_too(self):
        text = todo_file([(1, "A", 0, "none", "--"), (2, "B", 0, "none", "--")])
        self.write(text)
        base = self.commit()
        stamped = text.replace("| 1 | §1 | A | -- | [ ] |", "| 1 | §1 | A | -- | [x] |").replace(
            "- [ ] Work.", "- [x] Work.", 1).replace("- [ ] Commit: `x: a`", "- [x] Commit: `x: a`").replace(
            "\n## 2.", f"\n> **Verified:** 2026-09-28 | §1 | {base}\n> **Review:** `docs/reviews/d00-t01-s1.json`\n\n## 2.", 1)
        self.write(stamped)
        (self.root / "docs/reviews").mkdir(parents=True, exist_ok=True)
        (self.root / "docs/reviews/d00-t01-s1.json").write_text("{}\n", encoding="utf-8")
        self.commit()
        tg.adopt_stamps(self.root)
        tg.graph(self.root)
        path = self.root / "todo/00-workspace/TODO-01-a.md"
        path.write_text(path.read_text(encoding="utf-8").replace("Do it. Done when", "Do it all. Done when", 1),
                        encoding="utf-8")
        self.refuses("adopted section changed since adoption")

    def test_the_graph_checks_still_hold_on_an_adopted_section(self):
        self.build()
        tg.adopt_stamps(self.root, {"todo/00-workspace/TODO-02-b.md": 0})
        path = self.root / "todo/00-workspace/TODO-01-a.md"
        good = path.read_text(encoding="utf-8")
        for name, text, fragment in (
                ("dependency", good.replace("| 2 | §2 | B | -- | [ ] |", "| 2 | §2 | B | §9 | [ ] |"),
                 "unresolved dependency"),
                ("phase order", good.replace("| 2 | §2 | B | -- | [ ] |", "| 2 | §2 | B | §1 | [ ] |").replace(
                    "## 2. B\n\n**Phase:** 0", "## 2. B\n\n**Phase:** 0").replace(
                    "| 1 | §1 | A | -- | [x] |", "| 1 | §1 | A | §2 | [x] |"), "stamped section has open dependency"),
                ("xref", good.replace("## Inputs\n\n- i", "## Inputs\n\n- i -> XREF: D00 T09 §1"), "unresolved XREF"),
        ):
            with self.subTest(name):
                path.write_text(text, encoding="utf-8")
                self.refuses(fragment)
        path.write_text(good, encoding="utf-8")
        index = self.root / "todo/TODO-00-INDEX.md"
        index.write_text(index.read_text(encoding="utf-8").replace("- 00-workspace/TODO-01-a.md\n", ""), encoding="utf-8")
        self.refuses("missing from root index: 00-workspace/TODO-01-a.md")

    def test_an_adopted_section_keeps_the_phase_order_check(self):
        self.build()
        self.plan_json(phase_list=[0, 1])
        tg.adopt_stamps(self.root, {"todo/00-workspace/TODO-02-b.md": 0, "D00 T01 §1": 1})
        tg.graph(self.root)
        path = self.root / "todo/00-workspace/TODO-02-b.md"  # an adopted phase-0 section on an adopted phase-1 one
        path.write_text(path.read_text(encoding="utf-8").replace("| 1 | §1 | A | -- | [x] |",
                                                                  "| 1 | §1 | A | D00 T01 §1 | [x] |"), encoding="utf-8")
        self.refuses("prerequisite in later phase: D00 T02 §1 -> D00 T01 §1")  # the row is outside the frozen body

    def test_the_cli_adopts_and_refuses_a_second_run(self):
        self.build()
        shutil.copytree(SCRIPTS, self.root / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
        (self.root / "phases.json").write_text('{"todo/00-workspace/TODO-02-b.md": 0}', encoding="utf-8")
        cli = [sys.executable, str(self.root / "scripts/todo-graph.py"), "adopt-stamps", "--phase-map",
               str(self.root / "phases.json")]
        first = subprocess.run(cli, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(first.stdout.splitlines()[-1], "adopted 2 stamps")
        self.assertTrue(first.stdout.startswith("adopted D00 T01 §1 at "))
        second = subprocess.run(cli, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(second.returncode, 2)
        self.assertIn("adopted its stamps already", second.stderr)
        (self.root / "phases.json").write_text("{not json", encoding="utf-8")
        self.assertEqual(subprocess.run(cli, capture_output=True).returncode, 2)

    def test_reopening_excuses_only_format_faults_of_reopened_sections(self):
        self.build()
        tg.adopt_stamps(self.root, {"todo/00-workspace/TODO-02-b.md": 0})
        todo_a = self.root / "todo/00-workspace/TODO-01-a.md"
        todo_b = self.root / "todo/00-workspace/TODO-02-b.md"
        tg.unstamp(self.root, "D00 T01 §1", "reopened first", "2026-11-14")  # A's §1 now open, unrepaired
        before = {p: p.read_bytes() for p in (self.root / "todo").rglob("*.md")}
        with self.assertRaises(tg.Refused) as ctx:  # an earlier reopened section still waits on repair
            tg.unstamp(self.root, "D00 T02 §1", "reopen", "2026-11-14")
        self.assertIn("D00 T01 §1: executable Build order required", str(ctx.exception))
        self.assertEqual({p: p.read_bytes() for p in before}, before)
        self.repair("D00 T01 §1")
        for name, path, old, new in (
                ("same file, another section", todo_b, "## 2. B\n\n**Phase:** 0\n", "## 2. B\n\n"),
                ("a graph fault in the reopened section", todo_a, "| 1 | §1 | A | -- | [ ] |", "| 1 | §1 | A | §9 | [ ] |")):
            with self.subTest(name):
                good = path.read_text(encoding="utf-8")
                path.write_text(good.replace(old, new, 1), encoding="utf-8")
                before = {p: p.read_bytes() for p in (self.root / "todo").rglob("*.md")}
                registry = (self.root / self.REGISTRY).read_bytes()
                with self.assertRaises(tg.Refused) as ctx:
                    tg.unstamp(self.root, "D00 T02 §1", "reopen", "2026-11-14")
                self.assertIn("leaves faults elsewhere", str(ctx.exception))
                self.assertEqual({p: p.read_bytes() for p in before}, before)
                self.assertEqual((self.root / self.REGISTRY).read_bytes(), registry)
                path.write_text(good, encoding="utf-8")
        tg.unstamp(self.root, "D00 T02 §1", "reopen", "2026-11-14")  # only format faults left: accepted

    def test_the_cli_says_the_plan_waits_for_the_repair(self):
        self.build()
        tg.adopt_stamps(self.root, {"todo/00-workspace/TODO-02-b.md": 0})
        shutil.copytree(SCRIPTS, self.root / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
        plan = self.root / "todo/implementation-plan.md"
        before = plan.read_bytes() if plan.exists() else None
        result = subprocess.run([sys.executable, str(self.root / "scripts/todo-graph.py"), "unstamp", "D00 T01 §1",
                                 "--reason", "reopen", "--date", "2026-11-14"], capture_output=True, text=True,
                                encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("plan not synchronized: repair first:", result.stdout)
        self.assertIn("  D00 T01 §1: executable Build order required: D00 T01 §1", result.stdout)
        self.assertNotIn("plan synchronized\n", result.stdout)
        self.assertEqual(plan.read_bytes() if plan.exists() else None, before)

    def test_unstamp_reopens_an_adopted_section_that_changed_or_whose_row_is_open(self):
        # D03 T01 §9 round 1: the refusal says to unstamp; unstamp must reach the changed section, and an open box.
        for case in ("body", "receipt gone", "open box"):
            with self.subTest(case):
                self.tearDown()
                self.setUp()
                self.build()
                todo = self.root / "todo/00-workspace/TODO-01-a.md"
                if case == "open box":
                    todo.write_text(todo.read_text(encoding="utf-8").replace("| 1 | §1 | A | -- | [x] |",
                                                                             "| 1 | §1 | A | -- | [ ] |"),
                                    encoding="utf-8")
                tg.adopt_stamps(self.root, {"todo/00-workspace/TODO-02-b.md": 0})
                if case == "body":
                    todo.write_text(todo.read_text(encoding="utf-8").replace("- [x] Work.", "- [x] Work!", 1),
                                    encoding="utf-8")
                elif case == "receipt gone":
                    (self.root / "docs/reviews/rf/d00-t01-s1.md").unlink()
                tg.unstamp(self.root, "D00 T01 §1", "reopened after a change", "2026-11-14")
                text = todo.read_text(encoding="utf-8")
                self.assertIn("| 1 | §1 | A | -- | [ ] |", text)
                self.assertNotIn("> **Verified:**", text.split("## 2.")[0])
                self.assertNotIn("D00 T01 §1", self.registry()["adopted"])

    def test_unstamp_reopens_an_adopted_section_and_rolls_back_on_any_other_fault(self):
        self.build()
        tg.adopt_stamps(self.root, {"todo/00-workspace/TODO-02-b.md": 0})
        snapshot = {p: p.read_bytes() for p in (self.root / "todo").rglob("*.md")}
        registry = (self.root / self.REGISTRY).read_bytes()
        other = self.root / "todo/00-workspace/TODO-02-b.md"  # an unrelated fault elsewhere: B's §2 loses its Phase
        other.write_text(other.read_text(encoding="utf-8").replace("## 2. B\n\n**Phase:** 0\n", "## 2. B\n\n", 1),
                         encoding="utf-8")
        snapshot[other] = other.read_bytes()
        with self.assertRaises(tg.Refused) as ctx:  # a fault there before the change refuses it
            tg.unstamp(self.root, "D00 T01 §1", "bring it to the kit's format", "2026-11-14")
        self.assertIn("leaves faults elsewhere", str(ctx.exception))
        self.assertEqual({p: p.read_bytes() for p in snapshot}, snapshot)
        self.assertEqual((self.root / self.REGISTRY).read_bytes(), registry)
        other.write_text(other.read_text(encoding="utf-8").replace("## 2. B\n\n", "## 2. B\n\n**Phase:** 0\n", 1),
                         encoding="utf-8")
        snapshot[other] = other.read_bytes()
        real = tg._faults_elsewhere  # and one the change causes rolls it all back
        calls = []

        def after_the_change(*args):
            calls.append(1)
            return real(*args) if len(calls) == 1 else ["todo/00-workspace/TODO-02-b.md: a fault the change caused"]
        with mock.patch.object(tg, "_faults_elsewhere", after_the_change), self.assertRaises(tg.Refused) as ctx:
            tg.unstamp(self.root, "D00 T01 §1", "bring it to the kit's format", "2026-11-14")
        self.assertIn("unstamp rolled back", str(ctx.exception))
        self.assertEqual({p: p.read_bytes() for p in snapshot}, snapshot)
        self.assertEqual((self.root / self.REGISTRY).read_bytes(), registry)
        self.assertTrue((self.root / "docs/reviews/rf/d00-t01-s1.md").is_file())
        self.assertFalse((self.root / "docs/reviews/rf/d00-t01-s1.revoked-2026-11-14.md").exists())
        tg.unstamp(self.root, "D00 T01 §1", "bring it to the kit's format", "2026-11-14")
        text = (self.root / "todo/00-workspace/TODO-01-a.md").read_text(encoding="utf-8")
        self.assertNotIn("> **Verified:**", text)
        self.assertNotIn("> **Review:**", text)
        self.assertIn("| 1 | §1 | A | -- | [ ] |", text)
        self.assertNotIn("D00 T01 §1", self.registry()["adopted"])
        self.assertTrue((self.root / "docs/reviews/rf/d00-t01-s1.revoked-2026-11-14.md").is_file())
        faults = []
        tg.graph(self.root, faults)
        self.assertIn(("D00 T01 §1", "executable Build order required: D00 T01 §1"), faults)


class Repository(unittest.TestCase):
    def test_the_authoring_template_copy_is_identical(self):
        # todo/README.md and create-todo name todo/templates/TODO-template.md and each agent's skill copy as one file.
        kit = REPO / "kits/todo/templates"
        canonical = (kit / "todo/templates/TODO-template.md").read_bytes()
        for agent in (".claude", ".agents", ".codex"):
            with self.subTest(agent=agent):
                self.assertEqual((kit / agent / "skills/create-todo/todo-template.md").read_bytes(), canonical)

    def test_the_stamp_command_reads_completion_as_findings_file_and_verdict(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("todo_graph_cli", SCRIPTS / "todo-graph.py")
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        self.assertEqual(cli.completion_review("docs/reviews/00-workspace/D00-T01-s1.md:filed"),
                         {"report": "docs/reviews/00-workspace/D00-T01-s1.md", "verdict": "filed"})
        for bad in ("docs/reviews/x.md", "docs/reviews/x.md:", ":complete"):
            with self.subTest(bad=bad), self.assertRaises(tg.Refused):
                cli.completion_review(bad)

    def test_the_repository_graph_validates_and_its_plan_is_current(self):
        # The SDK plans its own work with its installed copy of the kit (python forge.py self-sync).
        r = subprocess.run([sys.executable, str(REPO / "scripts/todo-graph.py"), "plan", "--check"],
                           capture_output=True, text=True, cwd=REPO)
        self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == "__main__":
    unittest.main()

