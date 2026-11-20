"""The unattended kit installed as docs/unattended-run.md says: its doctor, then the installed copy's own suite apart
from the shortcut tests, which tests/test_unattended_installed_shortcuts.py runs on another CI shard (2026-11-20:
together they were one 17-minute test that held one Windows runner for 38 minutes). This is the one run of the
unattended kit's suite on each OS: the copy is the kit's files byte for byte, so the kit folder's own run is not
repeated (the kits-linux job skips kit-unattended)."""
import json
import os
import pathlib
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from test_forge import forge, run_kit_suite, suite_failure  # noqa: E402

# The installed test file tests/test_unattended_installed_shortcuts.py runs; this file runs every other one.
SHORTCUTS = "test_shortcut.py"


def install_as_the_page_says(target):
    """init with the todo kit (the run guard) and the unattended kit, the profile set as docs/unattended-run.md
    says (D02 T02 §11)."""
    assert forge.main(["init", str(target), "--kit", "todo", "--kit", "unattended"]) == 0
    path = target / ".conclave/unattended.json"
    profile = json.loads(path.read_text(encoding="utf-8"))
    (target / "docs/unattended-prompt.md").rename(target / "docs/project-run.md")
    profile.update(name="demo-run", model="claude-opus-5-5", effort="max", idle_minutes=30, tick_seconds=120,
                   prompt_file="docs/project-run.md", preflight=[{"name": "suite", "command": ["python3", "-m", "unittest"],
                                                            "timeout_seconds": 900}])
    path.write_text(json.dumps(profile), encoding="utf-8")


class InstalledUnattendedKitTest(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.target = pathlib.Path(self._tmp.name).resolve() / "project"
        self.target.mkdir()

    def checks(self):
        return {c["name"]: c for c in forge.doctor_repo(self.target, "unattended")["checks"]}

    def test_a_fresh_install_set_up_as_the_page_says_passes_its_doctor_and_its_tests(self):
        install_as_the_page_says(self.target)
        self.assertTrue((self.target / "docs/unattended-run.md").is_file(), "the operator's page is not installed")
        checks = self.checks()
        for agent_dir in (".agents", ".claude", ".codex"):
            self.assertEqual(checks[f"skill:unattended-run:{agent_dir}"]["status"], "ok", agent_dir)
        # Every check passes; the one expected exception is tmux on Windows, where the run lives in WSL (and on a
        # machine with no tmux at all, which the doctor says how to fix).
        expected = {"tmux": "setup_required"} if os.name == "nt" or not shutil.which("tmux") else {}
        self.assertEqual({n: c["status"] for n, c in checks.items() if c["status"] != "ok"}, expected)
        if os.name == "nt":
            self.assertIn("WSL", checks["tmux"]["detail"])
        # The installed copy's every test file but the shortcut tests, which the shortcuts file runs; a file the kit
        # adds later is found here. The shortcut file stays installed: test_unattended.py reads it. The limit only
        # catches a hang, and the whole process tree is ended when it trips, pwsh children included.
        tests = self.target / "scripts/tests"
        self.assertTrue((tests / SHORTCUTS).is_file(), "the shortcut tests were not installed")
        others = sorted(p for p in tests.glob("test*.py") if p.name != SHORTCUTS)
        self.assertTrue(others, "no other installed test file")
        for path in others:
            with self.subTest(path.name):
                result = run_kit_suite(path, 2400)
                self.assertTrue(result["passed"], suite_failure(result))
        # A kit file removed afterwards is one the doctor reports missing.
        (self.target / ".codex/skills/unattended-run/SKILL.md").unlink()
        (self.target / "docs/unattended-run.md").unlink()
        checks = self.checks()
        self.assertEqual(checks["skill:unattended-run:.codex"]["status"], "missing")
        self.assertEqual(checks["docs/unattended-run.md"]["status"], "missing")


if __name__ == "__main__":
    unittest.main()
