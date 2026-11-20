"""The unattended kit's shortcut tests (71 of them, each driving pwsh on Windows) run from a fresh installed copy, on a
CI shard of their own; tests/test_unattended_installed.py runs the doctor and the rest of the installed suite
(2026-11-20: together they were one 17-minute test that held one Windows runner for 38 minutes)."""
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from test_forge import run_kit_suite, suite_failure  # noqa: E402
from test_unattended_installed import SHORTCUTS, install_as_the_page_says  # noqa: E402


class InstalledShortcutTestsTest(unittest.TestCase):

    def test_the_installed_copys_shortcut_tests_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = pathlib.Path(tmp).resolve() / "project"
            target.mkdir()
            install_as_the_page_says(target)
            shortcuts = target / "scripts/tests" / SHORTCUTS
            self.assertTrue(shortcuts.is_file(), "the shortcut tests were not installed")
            result = run_kit_suite(shortcuts, 2400)
            self.assertTrue(result["passed"], suite_failure(result))


if __name__ == "__main__":
    unittest.main()
