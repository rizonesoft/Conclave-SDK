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


def _run_tree(argv, *, cwd=None, timeout=180):
    proc = subprocess.Popen(
        argv, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=NO_WINDOW,
    )
    try:
        out, err = proc.communicate(timeout=timeout)
        return proc.returncode, out, err
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                           capture_output=True, creationflags=NO_WINDOW)
        else:
            proc.kill()
        proc.communicate()
        raise


class DesktopTestsInstalledTest(unittest.TestCase):
    def test_kit_install_detection_and_doctor_including_invalid_config_strict(self):
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
            self.assertEqual(rows["config-lib"], "ok")
            self.assertEqual(rows["config"], "setup_required")
            self.assertGreater(report["missing_or_setup_required"], 0)
            # Configure prefix and verify doctor reports ok (0 issues).
            cfg_path = target / ".conclave/desktop-tests.json"
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            cfg["prefix"] = "fixture-app"
            cfg_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
            report2 = forge.doctor_repo(target, "desktop-tests")
            rows2 = {c["name"]: c["status"] for c in report2["checks"]}
            self.assertEqual(rows2["config"], "ok")
            self.assertEqual(report2["missing_or_setup_required"], 0)
            # Invalid config MUST fail strict doctor (missing_or_setup_required > 0).
            cfg["window_opens"] = "99:99"
            cfg_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
            report3 = forge.doctor_repo(target, "desktop-tests")
            rows3 = {c["name"]: c["status"] for c in report3["checks"]}
            self.assertEqual(rows3["config"], "error")
            self.assertGreater(report3["missing_or_setup_required"], 0)

    @unittest.skipUnless(os.name == "nt", "Windows desktop UIA default fixture runs on Windows")
    def test_installed_fixture_runs_default_uia_test_with_nonzero_cases(self):
        # On Windows, missing prerequisites must FAIL rather than silently skip.
        self.assertTrue(bool(PWSH), "pwsh is required on Windows")
        self.assertTrue(CSC.is_file(), f"csc.exe not found at {CSC}")
        self.assertTrue(UIA_CLIENT.is_file(), f"UIAutomationClient.dll not found at {UIA_CLIENT}")
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "desktop-proj"
            target.mkdir()
            forge.apply_kit(target, "desktop-tests")
            # Runs ONLY the pure positive default UIA fixture (never touches the operator's desk).
            rc, out, err = _run_tree(
                [sys.executable, "-m", "unittest", "discover", "-s", str(target / "scripts/tests"),
                 "-p", "test_desktop_tests.py", "-k", "test_default_uia_fixture_operates_control_without_touching_desk", "-v"],
                cwd=target, timeout=180,
            )
            combined = out + err
            self.assertEqual(rc, 0, combined)
            self.assertIn("Ran 1 test", combined)
            self.assertNotIn("skipped", combined.lower())


if __name__ == "__main__":
    unittest.main()
