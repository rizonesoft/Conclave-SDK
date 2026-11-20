"""The second half of the installed unattended kit's shortcut tests, on a CI shard of its own; the first half and
the split's rule are in tests/test_unattended_installed_shortcuts.py."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from test_unattended_installed_shortcuts import run_installed_half  # noqa: E402


class InstalledShortcutTestsSecondHalfTest(unittest.TestCase):

    def test_the_second_half_of_the_installed_copys_shortcut_tests_passes(self):
        run_installed_half(self, 2)


if __name__ == "__main__":
    unittest.main()
