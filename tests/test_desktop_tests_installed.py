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
            self.assertEqual(rows["capture"], "ok")
            self.assertEqual(rows["guard"], "ok")
            self.assertEqual(rows["desktop-lock"], "ok")
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
            # Resolve 8.3 short paths (e.g. RUNNER~1 -> runneradmin on Windows CI) so WorkingDirectory matches install.ps1.
            base = Path(tmp).resolve()
            if os.name == "nt":
                import ctypes
                buf = ctypes.create_unicode_buffer(1024)
                n = ctypes.windll.kernel32.GetLongPathNameW(str(base), buf, len(buf))
                if 0 < n < len(buf):
                    base = Path(buf.value)
            target = base / "comb-proj"
            state = base / "state"
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
                # but WITHOUT the conclave-automations ownership tag (must be preserved, not deleted!), AND
                # pre-register a legacy pre-tag task matching the manifest description (must upgrade cleanly!).
                rc_m, out_m, err_m = _run_tree([
                    PWSH, "-NoProfile", "-NonInteractive", "-Command",
                    f"$pw = (Get-Command pythonw.exe).Source; "
                    f"$a1 = New-ScheduledTaskAction -Execute $pw -Argument '\"{runner_py}\" {manual_task}' -WorkingDirectory '{target}'; "
                    f"$t = New-ScheduledTaskTrigger -Daily -At '04:00'; "
                    f"Register-ScheduledTask -TaskPath '{folder}' -TaskName '{manual_task}' -Description 'User manual task' -Action $a1 -Trigger $t -Force | Out-Null; "
                    f"$a2 = New-ScheduledTaskAction -Execute $pw -Argument '\"{runner_py}\" {smoke_task}' -WorkingDirectory '{target}'; "
                    f"Register-ScheduledTask -TaskPath '{folder}' -TaskName '{smoke_task}' -Description 'Nightly real-input desktop UI tests for {prefix}' -Action $a2 -Trigger $t -Force | Out-Null",
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
                # Direct uninstall of a legacy pre-tag task (WITHOUT reinstalling first!) must also remove it
                # while still preserving the manual task alongside it.
                legacy_manifest = {
                    "schema_version": 1, "folder": folder,
                    "tasks": [{
                        "name": smoke_task,
                        "description": f"Nightly real-input desktop UI tests for {prefix}",
                        "command": ["pwsh", "-NoProfile", "-NonInteractive", "-File", "scripts/smoke-input.ps1", "-Scheduled"],
                        "trigger": {"daily": True, "at": "03:00", "random_delay_minutes": 0},
                        "timeout_minutes": 180, "start_when_available": False, "wake_to_run": False, "exact_timeout": True,
                    }],
                }
                manifest_path.write_text(json.dumps(legacy_manifest, indent=2), encoding="utf-8")
                rc_leg, out_leg, err_leg = _run_tree([
                    PWSH, "-NoProfile", "-NonInteractive", "-Command",
                    f"$pw = (Get-Command pythonw.exe).Source; "
                    f"$a2 = New-ScheduledTaskAction -Execute $pw -Argument '\"{runner_py}\" {smoke_task}' -WorkingDirectory '{target}'; "
                    f"$t = New-ScheduledTaskTrigger -Daily -At '03:00'; "
                    f"Register-ScheduledTask -TaskPath '{folder}' -TaskName '{smoke_task}' -Description 'Nightly real-input desktop UI tests for {prefix}' -Action $a2 -Trigger $t -Force | Out-Null",
                ])
                self.assertEqual(rc_leg, 0, out_leg + err_leg)
                rc_du, out_du, err_du = _run_tree([
                    PWSH, "-NoProfile", "-NonInteractive", "-File", str(target / "scripts/smoke-input.ps1"),
                    "-ProjectRoot", str(target), "-StateFolder", str(state), "-Python", sys.executable,
                    "-Uninstall",
                ], cwd=target)
                self.assertEqual(rc_du, 0, out_du + err_du)
                rc_after2, out_after2, err_after2 = _run_tree([
                    PWSH, "-NoProfile", "-NonInteractive", "-Command",
                    f"$s = Get-ScheduledTask -TaskPath '{folder}' -TaskName '{smoke_task}' -ErrorAction SilentlyContinue; "
                    f"$m = Get-ScheduledTask -TaskPath '{folder}' -TaskName '{manual_task}' -ErrorAction SilentlyContinue; "
                    f"if ($s -or -not $m) {{ exit 1 }}",
                ])
                self.assertEqual(rc_after2, 0, out_after2 + err_after2)
                # Ambiguous ownership (legacy untagged task registered under a different pythonw.exe path):
                # direct uninstall MUST refuse (exit 2), keep the task untouched, and retain the manifest entry!
                manifest_path.write_text(json.dumps(legacy_manifest, indent=2), encoding="utf-8")
                rc_amb, out_amb, err_amb = _run_tree([
                    PWSH, "-NoProfile", "-NonInteractive", "-Command",
                    f"$a3 = New-ScheduledTaskAction -Execute 'C:\\OtherPython\\pythonw.exe' -Argument '\"{runner_py}\" {smoke_task}' -WorkingDirectory '{target}'; "
                    f"$t = New-ScheduledTaskTrigger -Daily -At '03:00'; "
                    f"Register-ScheduledTask -TaskPath '{folder}' -TaskName '{smoke_task}' -Description 'Nightly real-input desktop UI tests for {prefix}' -Action $a3 -Trigger $t -Force | Out-Null",
                ])
                self.assertEqual(rc_amb, 0, out_amb + err_amb)
                rc_ref, out_ref, err_ref = _run_tree([
                    PWSH, "-NoProfile", "-NonInteractive", "-File", str(target / "scripts/smoke-input.ps1"),
                    "-ProjectRoot", str(target), "-StateFolder", str(state), "-Python", sys.executable,
                    "-Uninstall",
                ], cwd=target)
                self.assertEqual(rc_ref, 2, out_ref + err_ref)
                self.assertIn("manifest retained", err_ref)
                retained = json.loads(manifest_path.read_text(encoding="utf-8"))
                self.assertEqual([t["name"] for t in retained["tasks"]], [smoke_task])
                rc_kept, out_kept, err_kept = _run_tree([
                    PWSH, "-NoProfile", "-NonInteractive", "-Command",
                    f"$t = Get-ScheduledTask -TaskPath '{folder}' -TaskName '{smoke_task}' -ErrorAction Stop; "
                    f"if ([string]$t.Actions[0].Execute -ne 'C:\\OtherPython\\pythonw.exe') {{ exit 1 }}",
                ])
                self.assertEqual(rc_kept, 0, out_kept + err_kept)
            finally:
                _run_tree([PWSH, "-NoProfile", "-NonInteractive", "-Command", cleanup_ps])

    @unittest.skipUnless(os.name == "nt", "Windows desktop lock cross-project test runs on Windows")
    def test_two_installed_projects_different_prefixes_contend_on_default_global_lock(self):
        self.assertTrue(bool(PWSH), "pwsh is required on Windows")
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp).resolve()
            alpha = base / "proj-alpha"
            beta = base / "proj-beta"
            alpha.mkdir()
            beta.mkdir()
            for proj, pfx in ((alpha, "alpha"), (beta, "beta")):
                forge.apply_kit(proj, "desktop-tests")
                cfg_p = proj / ".conclave/desktop-tests.json"
                cfg = json.loads(cfg_p.read_text(encoding="utf-8"))
                cfg["prefix"] = pfx
                cfg_p.write_text(json.dumps(cfg, indent=2), encoding="utf-8")

            # Clean env with NO *_DESKTOP_LOCK overrides: both installed projects must contend on Global\conclave-desktop-lock.
            clean_env = {k: v for k, v in os.environ.items()
                         if not k.upper().endswith("_DESKTOP_LOCK") and not k.upper().endswith("_DESKTOP_HELD")}
            ready_file = base / "alpha-ready.txt"
            release_file = base / "alpha-release.txt"
            holder_py = base / "hold.py"
            holder_py.write_text(
                "import pathlib, sys, time\n"
                "pathlib.Path(sys.argv[1]).write_text('held', encoding='utf-8')\n"
                "dl = time.time() + 20\n"
                "while not pathlib.Path(sys.argv[2]).exists() and time.time() < dl:\n"
                "    time.sleep(0.05)\n",
                encoding="utf-8",
            )
            proc_a = subprocess.Popen(
                [PWSH, "-NoProfile", "-NonInteractive", "-File", str(alpha / "scripts/capture-window.ps1"),
                 "-ProjectRoot", str(alpha), "-Python", sys.executable,
                 "-Command", sys.executable, str(holder_py), str(ready_file), str(release_file)],
                cwd=alpha, env=clean_env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                creationflags=NO_WINDOW,
            )
            try:
                import time
                dl = time.time() + 20
                while not ready_file.exists() and time.time() < dl:
                    if proc_a.poll() is not None:
                        self.fail(f"proj-alpha exited early ({proc_a.returncode}): {proc_a.stdout.read()} | {proc_a.stderr.read()}")
                    time.sleep(0.05)
                self.assertTrue(ready_file.exists(), "proj-alpha did not acquire default desktop lock")

                # proj-beta with a DIFFERENT prefix and NO override must refuse and not create -Out.
                beta_out = base / "beta-capture.txt"
                env_b = {**clean_env, "BETA_DESKTOP_WAIT_S": "0"}
                proc_b = subprocess.run(
                    [PWSH, "-NoProfile", "-NonInteractive", "-File", str(beta / "scripts/capture-window.ps1"),
                     "-ProjectRoot", str(beta), "-Python", sys.executable, "-Out", str(beta_out)],
                    cwd=beta, env=env_b, capture_output=True, text=True, timeout=60, creationflags=NO_WINDOW,
                )
                self.assertEqual(proc_b.returncode, 1, proc_b.stdout + proc_b.stderr)
                self.assertIn("Global\\conclave-desktop-lock", proc_b.stderr)
                self.assertIn(f"pid={proc_a.pid}", proc_b.stderr)
                self.assertFalse(beta_out.exists(), "capture output must not be created while lock is busy")
            finally:
                release_file.write_text("go", encoding="utf-8")
                try:
                    out_a, err_a = proc_a.communicate(timeout=15)
                except subprocess.TimeoutExpired:
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc_a.pid)],
                                   capture_output=True, creationflags=NO_WINDOW)
                    out_a, err_a = proc_a.communicate()
            self.assertEqual(proc_a.returncode, 0, out_a + err_a)

            # After proj-alpha releases, proj-beta succeeds and writes -Out.
            beta_out2 = base / "beta-capture-ok.txt"
            proc_b2 = subprocess.run(
                [PWSH, "-NoProfile", "-NonInteractive", "-File", str(beta / "scripts/capture-window.ps1"),
                 "-ProjectRoot", str(beta), "-Python", sys.executable, "-Out", str(beta_out2)],
                cwd=beta, env={**clean_env, "BETA_DESKTOP_WAIT_S": "5"},
                capture_output=True, text=True, timeout=60, creationflags=NO_WINDOW,
            )
            self.assertEqual(proc_b2.returncode, 0, proc_b2.stdout + proc_b2.stderr)
            self.assertTrue(beta_out2.exists())


if __name__ == "__main__":
    unittest.main()
