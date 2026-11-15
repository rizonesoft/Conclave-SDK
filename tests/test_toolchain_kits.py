"""The two toolchain kits as the SDK holds them (D04 T02).

The kits' own scripts are tested in the kits, under `kits/toolchain-<name>/templates/scripts/tests/`.
"""
import pathlib
import shutil
import sys
import tempfile
import unittest

SDK_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SDK_ROOT))
import forge  # noqa: E402

# One source, two kits: the tool check and its tests ship in both, so a project with either kit has a tested script.
SHARED = ("scripts/toolchain-check.py", "scripts/tests/test_toolchain_check.py")


def differing(root):
    """The shared files whose copy in the web kit is not byte for byte the C and C++ kit's."""
    cpp, web = root / "kits/toolchain-cpp/templates", root / "kits/toolchain-web/templates"
    return [rel for rel in SHARED
            if not (web / rel).is_file() or (cpp / rel).read_bytes() != (web / rel).read_bytes()]


class SharedCheckTests(unittest.TestCase):
    def test_the_web_kits_copies_are_the_cpp_kits_files_byte_for_byte(self):
        self.assertEqual(differing(SDK_ROOT), [])

    def test_one_changed_byte_in_either_copy_is_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            scratch = pathlib.Path(tmp).resolve()
            for kit in ("toolchain-cpp", "toolchain-web"):
                shutil.copytree(SDK_ROOT / "kits" / kit, scratch / "kits" / kit,
                                ignore=shutil.ignore_patterns("__pycache__"))
            self.assertEqual(differing(scratch), [])
            for kit, rel in (("toolchain-web", SHARED[0]), ("toolchain-cpp", SHARED[1])):
                with self.subTest(kit=kit, rel=rel):
                    path = scratch / "kits" / kit / "templates" / rel
                    kept = path.read_bytes()
                    path.write_bytes(kept + b"\n")
                    self.assertEqual(differing(scratch), [rel])
                    path.write_bytes(kept)
            (scratch / "kits/toolchain-web/templates" / SHARED[1]).unlink()
            self.assertEqual(differing(scratch), [SHARED[1]])

    def test_each_kits_tests_are_a_suite_of_check_all(self):
        suites = {suite["name"]: suite["path"] for suite in forge.SUITES}
        for kit in ("toolchain-cpp", "toolchain-web"):
            self.assertEqual(suites.get(f"kit-{kit}"), f"kits/{kit}/templates/scripts/tests")
            self.assertIn(kit, forge.list_kits())


if __name__ == "__main__":
    unittest.main()
