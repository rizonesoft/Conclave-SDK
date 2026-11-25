"""Installed desktop-tests kit integration tests (runs in Windows CI under tests/, D04 T04 s1)."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

FORGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FORGE_ROOT))
import forge  # noqa: E402

PWSH = shutil.which("pwsh")
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
CSC = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
UIA_CLIENT = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Microsoft.NET/Framework64/v4.0.30319/WPF/UIAutomationClient.dll"


class DesktopTestsInstalledTest(unittest.TestCase):
    def test_kit_install_detection_and_doctor(self):
        self.assertIn("desktop-tests", forge.list_kits())
        self.assertIn("desktop-tests", forge.KIT_ORDER)
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "desktop-proj"
            target.mkdir()
            forge.apply_kit(target, "desktop-tests")
            self.assertIn("desktop-tests", forge.installed_kits(target))
            report = forge.doctor_repo(target, "desktop-tests")
            rows = {c["name"]: c["status"] for c in report["checks"]}
            self.assertEqual(rows["runner"], "ok")
            self.assertEqual(rows["guard"], "ok")
            self.assertEqual(rows["watcher"], "ok")
            self.assertEqual(rows["config"], "setup_required")
            # Configure prefix and verify doctor reports ok.
            cfg_path = target / ".conclave/desktop-tests.json"
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            cfg["prefix"] = "fixture-app"
            cfg_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
            report2 = forge.doctor_repo(target, "desktop-tests")
            rows2 = {c["name"]: c["status"] for c in report2["checks"]}
            self.assertEqual(rows2["config"], "ok")

    @unittest.skipUnless(os.name == "nt" and PWSH and CSC.is_file() and UIA_CLIENT.is_file(),
                         "Windows desktop UIA default fixture runs on Windows")
    def test_installed_fixture_runs_default_uia_test_with_nonzero_cases(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "desktop-proj"
            target.mkdir()
            forge.apply_kit(target, "desktop-tests")
            r = subprocess.run(
                [sys.executable, "-m", "unittest", "discover", "-s", str(target / "scripts/tests"),
                 "-p", "test_desktop_tests.py", "-k", "test_default_uia_fixture", "-v"],
                cwd=target, capture_output=True, text=True, timeout=180, creationflags=NO_WINDOW,
            )
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            out = r.stdout + r.stderr
            self.assertIn("Ran 1 test", out)
            self.assertNotIn("skipped", out.lower())


if __name__ == "__main__":
    unittest.main()
