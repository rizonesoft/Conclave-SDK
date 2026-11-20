"""The unattended kit's shortcut tests (each driving pwsh on Windows) run from a fresh installed copy, in two halves
on two CI shards: this file runs the first half and tests/test_unattended_installed_shortcuts_2.py the second;
tests/test_unattended_installed.py runs the doctor and the rest of the installed suite. Whole, the shortcut tests
held one Windows runner for 18 to 24 minutes (2026-11-20), more than every other file together."""
import ast
import importlib.util
import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from test_forge import FORGE_ROOT, forge, suite_failure  # noqa: E402
from test_unattended_installed import SHORTCUTS, install_as_the_page_says  # noqa: E402

KIT_SHORTCUTS = FORGE_ROOT / "kits/unattended/templates/scripts/tests" / SHORTCUTS
HALVES = 2


def test_names(path):
    """`Class.test_method` for every test method a class in `path` defines, sorted: what unittest runs from it."""
    tree = ast.parse(pathlib.Path(path).read_text(encoding="utf-8"))
    return sorted(f"{node.name}.{item.name}" for node in tree.body if isinstance(node, ast.ClassDef)
                  for item in node.body if isinstance(item, ast.FunctionDef) and item.name.startswith("test"))


def half(names, k):
    """The k-th (1-based) of HALVES parts: every HALVES-th name, so the halves stay even as tests are added."""
    return names[k - 1::HALVES]


def run_installed_half(test, k):
    """Install a fresh copy, then run half `k` of its shortcut tests there, as check-all runs a suite: in a group
    of its own, the whole tree ended on a timeout, an interrupt or a clean finish."""
    with tempfile.TemporaryDirectory() as tmp:
        target = pathlib.Path(tmp).resolve() / "project"
        target.mkdir()
        install_as_the_page_says(target)
        tests = target / "scripts/tests"
        installed = tests / SHORTCUTS
        test.assertTrue(installed.is_file(), "the shortcut tests were not installed")
        names = half(test_names(installed), k)
        test.assertTrue(names, "this half holds no test")
        module = installed.stem
        suite = {"name": f"shortcuts-{k}", "kind": "unittest", "path": str(tests), "timeout": 2400,
                 "argv": [sys.executable, "-B", "-m", "unittest", *(f"{module}.{name}" for name in names)]}
        result = forge._run_suite(suite, dict(os.environ), tests)
        test.assertTrue(result["passed"], suite_failure(result))


class InstalledShortcutTestsTest(unittest.TestCase):

    def test_the_first_half_of_the_installed_copys_shortcut_tests_passes(self):
        run_installed_half(self, 1)

    def test_the_two_halves_are_every_test_unittest_runs_from_the_file(self):
        # The split never drops a test: the halves together are exactly what unittest's own loader finds.
        spec = importlib.util.spec_from_file_location("kit_test_shortcut_for_split", KIT_SHORTCUTS)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.path.insert(0, str(KIT_SHORTCUTS.parent))
        try:
            spec.loader.exec_module(module)
        finally:
            sys.path.remove(str(KIT_SHORTCUTS.parent))
        loaded = sorted(t.id().split(".", 1)[1] for t in
                        unittest.TestLoader().loadTestsFromModule(module)._tests for t in getattr(t, "_tests", [t]))
        names = test_names(KIT_SHORTCUTS)
        self.assertEqual(names, loaded)
        halves = [half(names, k) for k in range(1, HALVES + 1)]
        self.assertEqual(sorted(n for h in halves for n in h), names)
        self.assertLessEqual(max(map(len, halves)) - min(map(len, halves)), 1)


if __name__ == "__main__":
    unittest.main()
