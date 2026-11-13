"""The adoption report's lift-or-leave tables (D03 T01 §6) hold to their inventories, and every lift names a section."""
import pathlib
import re
import sys
import unittest

REPO = pathlib.Path(__file__).resolve().parents[1]
REPORT = REPO / "docs/plans/2026-11-13-todo-graph-adoption.md"
sys.path.insert(0, str(REPO / "scripts/lib"))
import todo_graph as tg  # noqa: E402  the SDK's installed copy of the kit's graph, as scripts/todo-graph.py loads it

REF = re.compile(r"D\d{2} T\d{2} §[1-9]\d*")
# (inventory block name, the table's header cell, the Decision and Reason columns, how a row names its entry)
TABLES = (("commands", "Command", 4, 5, lambda cell: cell.removeprefix("query ")),
          ("checks", "Check", 1, 2, lambda cell: cell))


def inventory(text, name):
    m = re.search(r"^```inventory " + name + r"\n(.*?)^```$", text, re.S | re.M)
    return m[1].split() if m else None


def table(text, header):
    """The rows of the first table whose first header cell is `header`, as lists of cells."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if re.fullmatch(r"\| " + re.escape(header) + r" \|.*\|", line):
            rows = []
            for row in lines[i + 2:]:
                if not row.startswith("|"):
                    break
                rows.append([c.strip() for c in row.strip("|").split("|")])
            return rows
    return None


def problems(text, sections):
    """Every way the report's tables fail their inventories or their sections; empty when they hold."""
    found = []
    for name, header, decision_col, reason_col, entry_of in TABLES:
        listed, rows = inventory(text, name), table(text, header)
        if listed is None or rows is None:
            found.append(f"{name}: no inventory block or no table")
            continue
        if len(listed) != len(set(listed)):
            found.append(f"{name}: the inventory repeats an entry")
        seen = []
        for row in rows:
            entry = entry_of(row[0].strip("`"))
            seen.append(entry)
            if entry not in listed:
                found.append(f"{name}: row {entry} is in no inventory")
            decision, reason = row[decision_col], row[reason_col]
            if decision not in ("lift", "leave"):
                found.append(f"{name}: row {entry} decides {decision!r}, not lift or leave")
            elif decision == "leave" and not reason:
                found.append(f"{name}: leave row {entry} gives no reason")
            elif decision == "lift":
                refs = REF.findall(reason)
                if not refs:
                    found.append(f"{name}: lift row {entry} names no section")
                for ref in refs:
                    if ref not in sections:
                        found.append(f"{name}: lift row {entry} names {ref}, which the graph does not resolve")
                    elif entry not in sections[ref].body:
                        found.append(f"{name}: lift row {entry} names {ref}, whose body never names {entry}")
        for entry in listed:
            if seen.count(entry) != 1:
                found.append(f"{name}: {entry} has {seen.count(entry)} rows, not one")
    return found


class AdoptionReport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = REPORT.read_text(encoding="utf-8")
        cls.sections = tg.graph(REPO)

    def test_the_tables_hold_to_their_inventories_and_every_lift_names_its_section(self):
        self.assertEqual(problems(self.text, self.sections), [])
        self.assertEqual(len(inventory(self.text, "commands")), 18)
        self.assertEqual(len(inventory(self.text, "checks")), 67)

    def mutated(self, old, new):
        self.assertIn(old, self.text)
        return problems(self.text.replace(old, new, 1), self.sections)

    def test_a_lift_row_without_its_section_fails(self):
        self.assertTrue(self.mutated("| lift | D03 T01 §14 |", "| lift | see below |"))

    def test_a_lift_row_naming_a_section_that_does_not_exist_fails(self):
        self.assertTrue(self.mutated("| lift | D03 T01 §14 |", "| lift | D03 T01 §99 |"))

    def test_a_lift_row_naming_a_section_that_does_not_own_it_fails(self):
        self.assertTrue(self.mutated("| lift | D03 T01 §14 |", "| lift | D03 T01 §1 |"))

    def test_a_duplicated_row_fails(self):
        row = "| `requires-unknown` | lift | D03 T01 §10 |\n"
        self.assertTrue(self.mutated(row, row + row))

    def test_an_inventory_entry_with_no_row_fails(self):
        self.assertTrue(self.mutated("| `vacuous-kind` | leave |", "| `vacuous-kind-gone` | leave |"))

    def test_a_row_with_no_inventory_entry_fails(self):
        self.assertTrue(self.mutated("growth design\n```", "growth\n```"))


if __name__ == "__main__":
    unittest.main()
