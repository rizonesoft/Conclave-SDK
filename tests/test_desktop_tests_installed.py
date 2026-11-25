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

    @unittest.skipUnless(os.name == "nt", "Windows Task Scheduler combined install test runs on Windows")
    def test_combined_automations_and_desktop_tests_real_scheduler_registration_and_manual_task_preservation(self):
        self.assertTrue(bool(PWSH), "pwsh is required on Windows")
        prefix = f"conclave-dt-comb-{os.getpid()}"
        folder = f"\\{prefix}\\"
        smoke_task = f"{prefix}-real-input-smoke"
        manual_task = f"{prefix}-manual-backup"
        cleanup_ps = (
            f"foreach ($n in @('{smoke_task}', '{manual_task}')) {{ "
            f"Unregister-ScheduledTask -TaskPath '{folder}' -TaskName $n -Confirm:$false -ErrorAction Ignore }}; "
            f"$s = New-Object -ComObject Schedule.Service; $s.Connect(); "
            f"try {{ $s.GetFolder('\\').DeleteFolder('{prefix}', 0) }} catch {{ }}"
        )
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "comb-proj"
            state = Path(tmp) / "state"
            target.mkdir()
            forge.apply_kit(target, "automations")
            forge.apply_kit(target, "desktop-tests")
            cfg_path = target / ".conclave/desktop-tests.json"
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            cfg["prefix"] = prefix
            cfg_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
            manifest_path = target / ".conclave/automations/tasks.json"
            manifest = {"schema_version": 1, "folder": folder, "tasks": []}
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            runner_py = str((target / ".conclave/automations/run.py").resolve())
            try:
                # Register a manual task in the same folder using pythonw.exe with the exact runner/cwd args
                # but WITHOUT the conclave-automations ownership tag (must be preserved, not deleted!).
                rc_m, out_m, err_m = _run_tree([
                    PWSH, "-NoProfile", "-NonInteractive", "-Command",
                    f"$a = New-ScheduledTaskAction -Execute 'pythonw.exe' -Argument '\"{runner_py}\" {manual_task}' -WorkingDirectory '{target}'; "
                    f"$t = New-ScheduledTaskTrigger -Daily -At '04:00'; "
                    f"Register-ScheduledTask -TaskPath '{folder}' -TaskName '{manual_task}' -Description 'User manual task' -Action $a -Trigger $t -Force | Out-Null",
                ])
                self.assertEqual(rc_m, 0, out_m + err_m)
                # Real combined install WITHOUT -NoRegister (executes .conclave/automations/install.ps1).
                rc_i, out_i, err_i = _run_tree([
                    PWSH, "-NoProfile", "-NonInteractive", "-File", str(target / "scripts/smoke-input.ps1"),
                    "-ProjectRoot", str(target), "-StateFolder", str(state), "-Python", sys.executable,
                    "-Install", "-NowOverride", "2026-11-25T10:00:00",
                ], cwd=target)
                self.assertEqual(rc_i, 0, out_i + err_i)
                # Inspect registered combined task AND confirm manual task survived.
                rc_chk, out_chk, err_chk = _run_tree([
                    PWSH, "-NoProfile", "-NonInteractive", "-Command",
                    f"$s = Get-ScheduledTask -TaskPath '{folder}' -TaskName '{smoke_task}'; "
                    f"$m = Get-ScheduledTask -TaskPath '{folder}' -TaskName '{manual_task}' -ErrorAction SilentlyContinue; "
                    f"[ordered]@{{ manualExists=[bool]$m; logon=[string]$s.Principal.LogonType; "
                    f"swa=$s.Settings.StartWhenAvailable; wake=$s.Settings.WakeToRun; "
                    f"lim=[string]$s.Settings.ExecutionTimeLimit; exe=[IO.Path]::GetFileName([string]$s.Actions[0].Execute); "
                    f"args=[string]$s.Actions[0].Arguments; trigClass=[string]$s.Triggers[0].CimClass.CimClassName; "
                    f"trigStart=[string]$s.Triggers[0].StartBoundary }} | ConvertTo-Json",
                ])
                self.assertEqual(rc_chk, 0, out_chk + err_chk)
                info = json.loads(out_chk)
                self.assertTrue(info["manualExists"], "manual task in same folder must be preserved")
                self.assertEqual(info["logon"], "Interactive")
                self.assertIs(info["swa"], False)
                self.assertIs(info["wake"], False)
                self.assertEqual(info["lim"], "PT3H")
                self.assertEqual(info["exe"].lower(), "pythonw.exe")
                self.assertEqual(info["args"], f'"{runner_py}" {smoke_task}')
                self.assertEqual(info["trigClass"], "MSFT_TaskDailyTrigger")
                self.assertIn("T03:00:00", info["trigStart"])
                # Real combined uninstall removes smoke task and STILL preserves manual task.
                rc_u, out_u, err_u = _run_tree([
                    PWSH, "-NoProfile", "-NonInteractive", "-File", str(target / "scripts/smoke-input.ps1"),
                    "-ProjectRoot", str(target), "-StateFolder", str(state), "-Python", sys.executable,
                    "-Uninstall",
                ], cwd=target)
                self.assertEqual(rc_u, 0, out_u + err_u)
                rc_after, out_after, err_after = _run_tree([
                    PWSH, "-NoProfile", "-NonInteractive", "-Command",
                    f"$s = Get-ScheduledTask -TaskPath '{folder}' -TaskName '{smoke_task}' -ErrorAction SilentlyContinue; "
                    f"$m = Get-ScheduledTask -TaskPath '{folder}' -TaskName '{manual_task}' -ErrorAction SilentlyContinue; "
                    f"if ($s -or -not $m) {{ exit 1 }}",
                ])
                self.assertEqual(rc_after, 0, out_after + err_after)
            finally:
                _run_tree([PWSH, "-NoProfile", "-NonInteractive", "-Command", cleanup_ps])


if __name__ == "__main__":
    unittest.main()
