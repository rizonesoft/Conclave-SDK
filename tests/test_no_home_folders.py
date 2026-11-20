"""No kit script names a home folder, in any kit.

The wordpress kit's own test (`test_no_script_names_a_home_folder`) scans every script in the project it is installed
in, so a home folder in another kit's script fails that project's suite. The SDK never installs the wordpress kit
beside the others, so this test holds every kit's scripts to the same pattern here.
"""
from pathlib import Path
import re
import unittest

REPO = Path(__file__).resolve().parents[1]
# The wordpress kit's pattern, kept equal to it (kits/wordpress/templates/scripts/tests/test_site_access.py).
HOME = re.compile(r"/home/\w|[A-Za-z]:\\\\?Users")


class NoHomeFolder(unittest.TestCase):
    def test_no_kit_script_names_a_home_folder(self):
        scripts = sorted(p for p in REPO.glob("kits/*/templates/scripts/**/*.py") if "tests" not in p.parts)
        self.assertTrue(scripts)
        offenders = [f"{p.relative_to(REPO)}:{n}" for p in scripts
                     for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1) if HOME.search(line)]
        self.assertEqual(offenders, [])

    def test_the_pattern_is_the_wordpress_kits(self):
        source = (REPO / "kits/wordpress/templates/scripts/tests/test_site_access.py").read_text(encoding="utf-8")
        self.assertIn('r"/home/\\w|[A-Za-z]:\\\\\\\\?Users"', source)


if __name__ == "__main__":
    unittest.main()
