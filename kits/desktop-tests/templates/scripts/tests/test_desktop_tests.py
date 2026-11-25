"""Tests for the desktop-tests kit (D04 T04 s1): config validation, real Windows UI Automation default/negative
fixtures, admitted InputWatch + smoke-input.ps1 runner, case reconciliation, bounded history, and automations integration."""
from __future__ import annotations

import ctypes
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

SCRIPTS = Path(__file__).resolve().parents[1]
PWSH = shutil.which("pwsh")
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
CSC = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
UIA_CLIENT = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Microsoft.NET/Framework64/v4.0.30319/WPF/UIAutomationClient.dll"
UIA_TYPES = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Microsoft.NET/Framework64/v4.0.30319/WPF/UIAutomationTypes.dll"


def _load_config_module():
    spec = importlib.util.spec_from_file_location("desktop_tests_cfg", SCRIPTS / "lib" / "desktop_tests.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


DT = _load_config_module()


def run_cmd(argv, *, cwd=None, env=None, timeout=120):
    return subprocess.run(
        argv, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout,
        creationflags=NO_WINDOW,
    )


class ConfigValidationTests(unittest.TestCase):
    def test_valid_and_invalid_configs(self):
        base = {
            "schema_version": 1, "prefix": "demo-app", "window_opens": "03:00", "window_closes": "06:00",
            "idle_minutes": 15, "history_limit": 60, "log_limit": 30, "test_command": None,
        }
        cfg = DT.validate_config(base)
        self.assertEqual(cfg["env_prefix"], "DEMO_APP")
        unset = dict(base, prefix=None)
        self.assertIsNone(DT.validate_config(unset, allow_unset=True)["env_prefix"])
        with self.assertRaises(DT.ConfigError):
            DT.validate_config(unset, allow_unset=False)
        for bad_patch in (
            {"prefix": "Bad_Prefix"},
            {"window_opens": "25:00"},
            {"window_closes": "03:00"},
            {"idle_minutes": 0},
            {"history_limit": -1},
            {"log_limit": True},
            {"test_command": []},
            {"extra_unknown": 1},
        ):
            with self.subTest(bad_patch=bad_patch):
                with self.assertRaises(DT.ConfigError):
                    DT.validate_config({**base, **bad_patch})


# Real WPF fixture app honoring LaunchShow.FirstWindowActivates() with a native UIA Button and TextBlock.
FIXTURE_APP_CS = r'''
using System;
using System.Windows;
using System.Windows.Automation;
using System.Windows.Controls;
using Conclave.DesktopTests;

public static class FixtureApp {
    [STAThread]
    public static void Main(string[] args) {
        bool forceActivate = args.Length > 0 && args[0] == "--activate";
        bool activate = forceActivate || LaunchShow.FirstWindowActivates();
        int clicks = 0;
        var win = new Window {
            Title = "ConclaveUiaFixtureWindow",
            Width = 260,
            Height = 140,
            Left = 40,
            Top = 40,
            ShowInTaskbar = false,
            ShowActivated = activate,
        };
        var lbl = new TextBlock { Text = "Clicks: 0" };
        AutomationProperties.SetAutomationId(lbl, "StatusLabel");
        var btn = new Button { Content = "Increment", Width = 100, Height = 30 };
        AutomationProperties.SetAutomationId(btn, "ActionButton");
        btn.Click += (s, e) => { clicks++; lbl.Text = "Clicks: " + clicks; };
        var panel = new StackPanel();
        panel.Children.Add(lbl);
        panel.Children.Add(btn);
        win.Content = panel;
        var app = new Application();
        app.Run(win);
    }
}
'''

# Real C# test driver exercising UIA InvokePattern + DeskObserver + SmokeInputGuard.
FIXTURE_DRIVER_CS = r'''
using System;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Threading;
using System.Windows.Automation;
using Conclave.DesktopTests;

public static class FixtureDriver {
    [StructLayout(LayoutKind.Sequential)] struct POINT { public int X, Y; }
    [DllImport("user32.dll")] static extern bool GetCursorPos(out POINT pt);
    [DllImport("user32.dll")] static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, UIntPtr dwExtraInfo);

    private static AutomationElement WaitForWindow(int pid, int timeoutMs) {
        DateTime end = DateTime.UtcNow.AddMilliseconds(timeoutMs);
        while (DateTime.UtcNow < end) {
            try {
                Process p = Process.GetProcessById(pid);
                if (p.HasExited) {
                    throw new InvalidOperationException("fixture process exited early with code " + p.ExitCode);
                }
                if (p.MainWindowHandle != IntPtr.Zero) {
                    return AutomationElement.FromHandle(p.MainWindowHandle);
                }
            } catch (ArgumentException) {
                throw new InvalidOperationException("fixture process exited before window appeared");
            }
            AutomationElement win = AutomationElement.RootElement.FindFirst(
                TreeScope.Children,
                new PropertyCondition(AutomationElement.ProcessIdProperty, pid));
            if (win != null) return win;
            Thread.Sleep(50);
        }
        throw new TimeoutException("fixture window did not appear for pid " + pid);
    }

    public static int Main(string[] args) {
        string mode = args[0];
        string prefix = args[1];
        string appExe = args.Length > 2 ? args[2] : "";
        if (mode == "untraited-helper") {
            SmokeInputGuard.Require(prefix, false, "SendKey");
            return 0;
        }
        if (mode == "real-input-action") {
            SmokeInputGuard.Require(prefix, true, "SendKey");
            Console.WriteLine("ADMITTED_OK tag=" + SmokeInputGuard.CurrentTag(prefix).ToString("X8"));
            return 0;
        }
        if (mode == "default-uia" || mode == "neg-focus" || mode == "neg-pointer" || mode == "neg-key") {
            bool forceActivate = mode == "neg-focus";
            int pid = 0;
            try {
                using (DeskObserver obs = new DeskObserver(new int[0])) {
                    pid = LaunchShow.StartNoActivate(appExe, forceActivate ? "--activate" : "", null);
                    obs.TrackPid(pid);
                    AutomationElement win = WaitForWindow(pid, 10000);
                    AutomationElement btn = win.FindFirst(TreeScope.Descendants,
                        new PropertyCondition(AutomationElement.AutomationIdProperty, "ActionButton"));
                    AutomationElement lbl = win.FindFirst(TreeScope.Descendants,
                        new PropertyCondition(AutomationElement.AutomationIdProperty, "StatusLabel"));
                    if (btn == null || lbl == null) throw new InvalidOperationException("missing UIA controls");
                    if (mode == "neg-pointer") {
                        POINT p;
                        if (GetCursorPos(out p)) {
                            SetCursorPos(p.X + 4, p.Y + 4);
                            Thread.Sleep(40);
                            SetCursorPos(p.X, p.Y);
                        } else {
                            // Locked or headless desktop denies SetCursorPos; exercise the same observer path.
                            obs.ObserveCursor(100, 100);
                            obs.ObserveCursor(104, 104);
                            obs.ObserveCursor(100, 100);
                        }
                    } else if (mode == "neg-key") {
                        if (obs.HasDesktopCursor) {
                            // Send a harmless unassigned key (0xE8) up/down via keybd_event.
                            keybd_event(0xE8, 0, 0, UIntPtr.Zero);
                            keybd_event(0xE8, 0, 2, UIntPtr.Zero);
                            Thread.Sleep(40);
                        } else {
                            // Locked or headless desktop blocks keybd_event; exercise the same observer hook path.
                            obs.ObserveInjectedKey(0xE8, 0x10);
                        }
                    } else if (mode == "neg-focus") {
                        Thread.Sleep(80);
                        if (!obs.HasDesktopCursor) {
                            // Locked or headless desktop has GetForegroundWindow()==0; exercise the same observer path.
                            obs.ObserveForegroundPid(pid);
                        }
                    }
                    InvokePattern inv = (InvokePattern)btn.GetCurrentPattern(InvokePattern.Pattern);
                    inv.Invoke();
                    string readBack = "";
                    for (int i = 0; i < 40; i++) {
                        readBack = (string)lbl.GetCurrentPropertyValue(AutomationElement.NameProperty);
                        if (readBack == "Clicks: 1") break;
                        Thread.Sleep(25);
                    }
                    if (readBack != "Clicks: 1") throw new InvalidOperationException("unexpected label: " + readBack);
                    obs.VerifyClean(mode);
                    Console.WriteLine("UIA_OK " + readBack);
                }
                return 0;
            } catch (RealInputRefusedException ex) {
                Console.Error.WriteLine("REFUSED: " + ex.Message);
                return 11;
            } finally {
                if (pid > 0) {
                    try {
                        using (Process p = Process.GetProcessById(pid)) {
                            if (!p.HasExited) { p.Kill(); p.WaitForExit(5000); }
                        }
                    } catch (ArgumentException) { }
                }
            }
        }
        return 2;
    }
}
'''


@unittest.skipUnless(os.name == "nt" and PWSH and CSC.is_file() and UIA_CLIENT.is_file(),
                     "Windows desktop UIA, PowerShell 7, and .NET Framework csc.exe required")
class DesktopTestsWindowsSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._shared = tempfile.TemporaryDirectory()
        cls.bin_dir = Path(cls._shared.name)
        guard_cs = SCRIPTS / "lib" / "DesktopTestGuard.cs"
        watch_cs = SCRIPTS / "lib" / "InputWatch.cs"
        app_cs = cls.bin_dir / "FixtureApp.cs"
        drv_cs = cls.bin_dir / "FixtureDriver.cs"
        app_cs.write_text(FIXTURE_APP_CS, encoding="utf-8")
        drv_cs.write_text(FIXTURE_DRIVER_CS, encoding="utf-8")
        cls.app_exe = cls.bin_dir / "FixtureApp.exe"
        cls.drv_exe = cls.bin_dir / "FixtureDriver.exe"
        cls.watch_exe = cls.bin_dir / "InputWatch.exe"
        wpf = UIA_CLIENT.parent
        for argv in (
            [str(CSC), "/nologo", "/target:winexe", f"/out:{cls.app_exe}",
             f"/r:{wpf / 'PresentationFramework.dll'}", f"/r:{wpf / 'PresentationCore.dll'}",
             f"/r:{wpf / 'WindowsBase.dll'}", f"/r:{UIA_CLIENT}", "/r:System.Xaml.dll",
             str(guard_cs), str(app_cs)],
            [str(CSC), "/nologo", f"/out:{cls.drv_exe}",
             f"/r:{UIA_CLIENT}", f"/r:{UIA_TYPES}", str(guard_cs), str(drv_cs)],
            [str(CSC), "/nologo", f"/out:{cls.watch_exe}", str(watch_cs)],
        ):
            r = run_cmd(argv)
            assert r.returncode == 0, r.stdout + r.stderr

    @classmethod
    def tearDownClass(cls):
        cls._shared.cleanup()

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "proj"
        self.state = Path(self._tmp.name) / "state"
        (self.root / ".conclave").mkdir(parents=True)
        (self.root / "scripts" / "lib").mkdir(parents=True)
        shutil.copyfile(SCRIPTS / "smoke-input.ps1", self.root / "scripts" / "smoke-input.ps1")
        shutil.copyfile(SCRIPTS / "lib" / "desktop_tests.py", self.root / "scripts" / "lib" / "desktop_tests.py")
        shutil.copyfile(SCRIPTS / "lib" / "InputWatch.cs", self.root / "scripts" / "lib" / "InputWatch.cs")
        self.write_cfg()

    def write_cfg(self, **overrides):
        cfg = {
            "schema_version": 1, "prefix": "demo", "window_opens": "03:00", "window_closes": "06:00",
            "idle_minutes": 15, "history_limit": 60, "log_limit": 30, "test_command": None,
            **overrides,
        }
        (self.root / ".conclave" / "desktop-tests.json").write_text(json.dumps(cfg), encoding="utf-8")

    def run_smoke(self, *args, extra_env=None):
        env = {**os.environ, **(extra_env or {})}
        return run_cmd(
            [PWSH, "-NoProfile", "-NonInteractive", "-File", str(self.root / "scripts" / "smoke-input.ps1"),
             "-ProjectRoot", str(self.root), "-StateFolder", str(self.state),
             "-Python", sys.executable, "-Watcher", str(self.watch_exe), *args],
            cwd=self.root, env=env,
        )

    def test_default_uia_fixture_operates_control_without_touching_desk_and_negative_fixtures_fail(self):
        # 1. Default UIA fixture invokes a real button via InvokePattern and reads back 'Clicks: 1' cleanly.
        ok = run_cmd([str(self.drv_exe), "default-uia", "demo", str(self.app_exe)])
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        self.assertIn("UIA_OK Clicks: 1", ok.stdout)
        # 2. Negative fixtures: transient focus steal, pointer move-and-restore, synthetic key, untraited helper.
        for neg in ("neg-focus", "neg-pointer", "neg-key", "untraited-helper"):
            with self.subTest(neg=neg):
                r = run_cmd([str(self.drv_exe), neg, "demo", str(self.app_exe)])
                self.assertNotEqual(r.returncode, 0, f"{neg} unexpectedly passed: {r.stdout}")
                self.assertIn("REFUSED:" if neg != "untraited-helper" else "RealInputRefusedException",
                              r.stdout + r.stderr)
        # 3. Direct DEMO_SMOKE_INPUT=1 without admitted smoke-input.ps1 session must refuse.
        direct = run_cmd([str(self.drv_exe), "real-input-action", "demo"],
                         env={**os.environ, "DEMO_SMOKE_INPUT": "1"})
        self.assertNotEqual(direct.returncode, 0, direct.stdout + direct.stderr)
        self.assertIn("no admitted watcher session", direct.stdout + direct.stderr)

    def test_admitted_run_and_admission_boundaries_and_custom_settings(self):
        # Runner stub that invokes the real FixtureDriver.exe real-input-action under the admitted session!
        runner_py = Path(self._tmp.name) / "real_runner.py"
        runner_py.write_text(
            "import subprocess, sys\n"
            f"DRV = {str(self.drv_exe)!r}\n"
            "if '--discover' in sys.argv:\n"
            "    print('DISCOVER RealSuite Case1')\n"
            "    sys.exit(0)\n"
            "r = subprocess.run([DRV, 'real-input-action', 'demo'], capture_output=True, text=True)\n"
            "print(r.stdout.strip())\n"
            "if r.returncode == 0:\n"
            "    print('CASE PASS RealSuite Case1')\n"
            "sys.exit(r.returncode)\n",
            encoding="utf-8",
        )
        self.state.mkdir(parents=True, exist_ok=True)
        # Refusals: outside window, unknown desktop, locked, busy (899s < 900s).
        for label, now_s, files, expected_reason in (
            ("outside-early", "2026-11-25T02:59:00", {"probe-locked": "0", "probe-idle": "1000"}, "outside-window"),
            ("outside-close", "2026-11-25T06:00:00", {"probe-locked": "0", "probe-idle": "1000"}, "outside-window"),
            ("unknown", "2026-11-25T03:00:00", {"probe-unknown": "1"}, "desktop-unknown"),
            ("locked", "2026-11-25T03:00:00", {"probe-locked": "1", "probe-idle": "1000"}, "desktop-locked"),
            ("busy-below", "2026-11-25T03:00:00", {"probe-locked": "0", "probe-idle": "899"}, "desktop-busy"),
        ):
            with self.subTest(case=label):
                for fn in ("probe-unknown", "probe-locked", "probe-idle"):
                    (self.state / fn).unlink(missing_ok=True)
                for fn, val in files.items():
                    (self.state / fn).write_text(val, encoding="utf-8")
                res = self.run_smoke("-Scheduled", "-TestProbes", "-NowOverride", now_s, "-RunnerCommand", str(runner_py))
                self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
                self.assertIn(expected_reason, res.stdout)
        # Eligible scheduled run at 03:00 with exactly 900s idle executes real case and passes!
        (self.state / "probe-unknown").unlink(missing_ok=True)
        (self.state / "probe-locked").write_text("0", encoding="utf-8")
        (self.state / "probe-idle").write_text("900", encoding="utf-8")
        ok = self.run_smoke("-Scheduled", "-TestProbes", "-NowOverride", "2026-11-25T03:00:00", "-RunnerCommand", str(runner_py))
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        self.assertIn("smoke-input: passed (1 case(s) across 1 class(es))", ok.stdout)
        # Changed settings (window 01:00-02:00, idle 5m=300s) take effect.
        self.write_cfg(window_opens="01:00", window_closes="02:00", idle_minutes=5)
        (self.state / "probe-idle").write_text("300", encoding="utf-8")
        custom_ok = self.run_smoke("-Scheduled", "-TestProbes", "-NowOverride", "2026-11-25T01:30:00", "-RunnerCommand", str(runner_py))
        self.assertEqual(custom_ok.returncode, 0, custom_ok.stdout + custom_ok.stderr)
        self.assertIn("smoke-input: passed", custom_ok.stdout)

    def test_mid_class_interruptions_kill_descendants_and_distinguish_tags(self):
        # Test: person input, foreign-tag input, own smoke-tag (continues!), lock, watcher loss, deadline.
        pid_file = Path(self._tmp.name) / "grandchild.pid"
        after_file = Path(self._tmp.name) / "after.txt"
        sleep_runner = Path(self._tmp.name) / "sleep_runner.py"
        sleep_runner.write_text(
            "import os, pathlib, subprocess, sys, time\n"
            f"PIDF = pathlib.Path({str(pid_file)!r})\n"
            f"AFTER = pathlib.Path({str(after_file)!r})\n"
            "if '--discover' in sys.argv:\n"
            "    print('DISCOVER SlowSuite Case1')\n"
            "    sys.exit(0)\n"
            "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], "
            "creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))\n"
            "PIDF.write_text(str(child.pid), encoding='utf-8')\n"
            "time.sleep(0.6 if os.environ.get('FAST_PASS') else 30)\n"
            "AFTER.write_text('late-input', encoding='utf-8')\n"
            "print('CASE PASS SlowSuite Case1')\n",
            encoding="utf-8",
        )
        # Helper wrapper watcher that sends a command to the real InputWatch.exe after startup.
        proxy_watch = Path(self._tmp.name) / "proxy_watch.py"
        proxy_watch.write_text(
            "import os, subprocess, sys, time\n"
            f"REAL = {str(self.watch_exe)!r}\n"
            "mode = os.environ.get('WATCH_ACTION', '')\n"
            "p = subprocess.Popen([REAL, *sys.argv[1:]], stdin=subprocess.PIPE, stdout=subprocess.PIPE, "
            "stderr=subprocess.PIPE, text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))\n"
            "line = p.stdout.readline().strip()\n"
            "print(line, flush=True)\n"
            "time.sleep(0.35)\n"
            "if mode == 'crash':\n"
            "    p.kill(); sys.exit(9)\n"
            "if mode in ('person', 'foreign-tag', 'smoke-tag'):\n"
            "    p.stdin.write(mode + '\\n'); p.stdin.flush()\n"
            "for cmd in sys.stdin:\n"
            "    p.stdin.write(cmd); p.stdin.flush()\n"
            "p.wait()\n",
            encoding="utf-8",
        )
        for action, expect_rc, expect_msg in (
            ("person", 1, "person-input"),
            ("foreign-tag", 1, "person-input"),
            ("crash", 1, "watcher-lost"),
            ("smoke-tag", 0, "smoke-input: passed"),
        ):
            with self.subTest(action=action):
                pid_file.unlink(missing_ok=True)
                after_file.unlink(missing_ok=True)
                extra = {"WATCH_ACTION": action}
                if action == "smoke-tag":
                    extra["FAST_PASS"] = "1"
                res = run_cmd(
                    [PWSH, "-NoProfile", "-NonInteractive", "-File", str(self.root / "scripts" / "smoke-input.ps1"),
                     "-ProjectRoot", str(self.root), "-StateFolder", str(self.state),
                     "-Python", sys.executable, "-Watcher", str(proxy_watch), "-RunnerCommand", str(sleep_runner)],
                    cwd=self.root, env={**os.environ, **extra},
                )
                self.assertEqual(res.returncode, expect_rc, res.stdout + res.stderr)
                self.assertIn(expect_msg, res.stdout)
                if expect_rc == 1:
                    self.assertFalse(after_file.exists(), "stopped class must not run subsequent input")
                    if pid_file.exists():
                        gpid = pid_file.read_text(encoding="utf-8").strip()
                        chk = run_cmd(["tasklist", "/FI", f"PID eq {gpid}", "/NH"])
                        self.assertNotIn(gpid, chk.stdout)

    def test_reconciliation_failures_and_bounded_history_and_missed_nights(self):
        # Test empty discovery, missing case, duplicate, skip, fail, nonzero exit after PASS.
        rec_runner = Path(self._tmp.name) / "rec_runner.py"
        rec_runner.write_text(
            "import os, sys\n"
            "mode = os.environ['REC_MODE']\n"
            "if '--discover' in sys.argv:\n"
            "    if mode != 'empty':\n"
            "        print('DISCOVER SuiteA Case1')\n"
            "        print('DISCOVER SuiteA Case2')\n"
            "    sys.exit(0)\n"
            "if mode == 'missing':\n"
            "    print('CASE PASS SuiteA Case1')\n"
            "elif mode == 'duplicate':\n"
            "    print('CASE PASS SuiteA Case1')\n"
            "    print('CASE PASS SuiteA Case1')\n"
            "    print('CASE PASS SuiteA Case2')\n"
            "elif mode == 'skip':\n"
            "    print('CASE PASS SuiteA Case1')\n"
            "    print('CASE SKIP SuiteA Case2')\n"
            "elif mode == 'fail':\n"
            "    print('CASE PASS SuiteA Case1')\n"
            "    print('CASE FAIL SuiteA Case2')\n"
            "elif mode == 'nonzero':\n"
            "    print('CASE PASS SuiteA Case1')\n"
            "    print('CASE PASS SuiteA Case2')\n"
            "    sys.exit(3)\n"
            "elif mode == 'ok':\n"
            "    print('CASE PASS SuiteA Case1')\n"
            "    print('CASE PASS SuiteA Case2')\n",
            encoding="utf-8",
        )
        self.write_cfg(history_limit=4, log_limit=2)
        for mode, needle in (
            ("empty", "discovery returned 0"),
            ("missing", "case-missing"),
            ("duplicate", "case-duplicate"),
            ("skip", "case-skipped"),
            ("fail", "case-failed"),
            ("nonzero", "class-exit-nonzero"),
        ):
            with self.subTest(mode=mode):
                r = self.run_smoke("-RunnerCommand", str(rec_runner), extra_env={"REC_MODE": mode})
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertIn(needle, r.stdout + r.stderr)
        ok = self.run_smoke("-RunnerCommand", str(rec_runner), extra_env={"REC_MODE": "ok"})
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        # Retention bound: history_limit=4, log_limit=2.
        hist_lines = [l for l in (self.state / "input-history.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
        self.assertEqual(len(hist_lines), 4)
        self.assertLessEqual(len(list((self.state / "logs").glob("*.log"))), 2)
        # Missed nights: install on 2026-11-20 10:00 (first_expected_night = 2026-11-21); check on 2026-11-24 08:00.
        # Even though on-demand runs exist, 0 scheduled runs exist -> 4 missed nights (21, 22, 23, 24)!
        inst = self.run_smoke("-Install", "-NoRegister", "-NowOverride", "2026-11-20T10:00:00")
        self.assertEqual(inst.returncode, 0, inst.stdout + inst.stderr)
        st = self.run_smoke("-Status", "-NowOverride", "2026-11-24T08:00:00")
        self.assertEqual(st.returncode, 0, st.stdout + st.stderr)
        summary = json.loads(st.stdout)
        self.assertEqual(summary["missed_nights"], 4, summary)
        self.assertEqual(summary["missed_dates"], ["2026-11-21", "2026-11-22", "2026-11-23", "2026-11-24"])

    def test_automations_integration_preserves_other_tasks(self):
        # Combined install with pre-existing task in .conclave/automations/tasks.json.
        auto_dir = self.root / ".conclave" / "automations"
        auto_dir.mkdir(parents=True)
        repo_root = Path(__file__).resolve().parents[5]
        shutil.copyfile(repo_root / "kits/automations/templates/.conclave/automations/run.py", auto_dir / "run.py")
        existing_manifest = {
            "schema_version": 1,
            "folder": "\\demo\\",
            "tasks": [{
                "name": "demo-health",
                "description": "Existing weekly health check",
                "command": ["python", "-c", "print('ok')"],
                "trigger": {"weekly": "Sunday", "at": "02:00"},
                "timeout_minutes": 10,
            }],
        }
        (auto_dir / "tasks.json").write_text(json.dumps(existing_manifest, indent=2), encoding="utf-8")
        inst = self.run_smoke("-Install", "-NoRegister", "-NowOverride", "2026-11-25T10:00:00")
        self.assertEqual(inst.returncode, 0, inst.stdout + inst.stderr)
        # run.py --check must accept the new daily task!
        chk = run_cmd([sys.executable, "-B", str(auto_dir / "run.py"), "--check"], cwd=self.root)
        self.assertEqual(chk.returncode, 0, chk.stdout + chk.stderr)
        updated = json.loads((auto_dir / "tasks.json").read_text(encoding="utf-8"))
        names = [t["name"] for t in updated["tasks"]]
        self.assertEqual(names, ["demo-health", "demo-real-input-smoke"])
        smoke_task = updated["tasks"][1]
        self.assertEqual(smoke_task["trigger"], {"daily": True, "at": "03:00", "random_delay_minutes": 0})
        self.assertEqual(smoke_task["timeout_minutes"], 180)
        self.assertIs(smoke_task["start_when_available"], False)
        self.assertIs(smoke_task["wake_to_run"], False)
        self.assertIs(smoke_task["exact_timeout"], True)
        # Uninstall removes ONLY demo-real-input-smoke and preserves demo-health!
        uninst = self.run_smoke("-Uninstall", "-NoRegister")
        self.assertEqual(uninst.returncode, 0, uninst.stdout + uninst.stderr)
        after = json.loads((auto_dir / "tasks.json").read_text(encoding="utf-8"))
        self.assertEqual([t["name"] for t in after["tasks"]], ["demo-health"])

    def test_mid_class_lock_and_deadline_stops_kill_descendants(self):
        pid_file = Path(self._tmp.name) / "grandchild_ld.pid"
        after_file = Path(self._tmp.name) / "after_ld.txt"
        trigger_runner = Path(self._tmp.name) / "trigger_runner.py"
        trigger_runner.write_text(
            "import os, pathlib, subprocess, sys, time\n"
            f"PIDF = pathlib.Path({str(pid_file)!r})\n"
            f"AFTER = pathlib.Path({str(after_file)!r})\n"
            f"STATE = pathlib.Path({str(self.state)!r})\n"
            "if '--discover' in sys.argv:\n"
            "    print('DISCOVER SlowSuite Case1')\n"
            "    sys.exit(0)\n"
            "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], "
            "creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))\n"
            "PIDF.write_text(str(child.pid), encoding='utf-8')\n"
            "time.sleep(0.25)\n"
            "if os.environ.get('TRIGGER') == 'lock':\n"
            "    (STATE / 'probe-locked').write_text('1', encoding='utf-8')\n"
            "elif os.environ.get('TRIGGER') == 'deadline':\n"
            "    (STATE / 'probe-now').write_text('2026-11-25T06:00:01', encoding='utf-8')\n"
            "time.sleep(30)\n"
            "AFTER.write_text('late-input', encoding='utf-8')\n"
            "print('CASE PASS SlowSuite Case1')\n",
            encoding="utf-8",
        )
        self.state.mkdir(parents=True, exist_ok=True)
        for trig, expect_reason in (("lock", "desktop-locked"), ("deadline", "deadline")):
            with self.subTest(trigger=trig):
                pid_file.unlink(missing_ok=True)
                after_file.unlink(missing_ok=True)
                (self.state / "probe-unknown").unlink(missing_ok=True)
                (self.state / "probe-locked").write_text("0", encoding="utf-8")
                (self.state / "probe-idle").write_text("1000", encoding="utf-8")
                (self.state / "probe-now").write_text("2026-11-25T05:59:55", encoding="utf-8")
                res = self.run_smoke(
                    "-Scheduled", "-TestProbes", "-RunnerCommand", str(trigger_runner),
                    extra_env={"TRIGGER": trig},
                )
                self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
                self.assertIn(expect_reason, res.stdout)
                self.assertFalse(after_file.exists(), "stopped class must not run subsequent input")
                if pid_file.exists():
                    gpid = pid_file.read_text(encoding="utf-8").strip()
                    chk = run_cmd(["tasklist", "/FI", f"PID eq {gpid}", "/NH"])
                    self.assertNotIn(gpid, chk.stdout)

    def test_standalone_install_empty_status_and_failed_replace_preserves_history(self):
        # Empty status before any run.
        empty_st = self.run_smoke("-Status", "-NowOverride", "2026-11-25T08:00:00")
        self.assertEqual(empty_st.returncode, 0, empty_st.stdout + empty_st.stderr)
        empty_summary = json.loads(empty_st.stdout)
        self.assertEqual(empty_summary["total_records"], 0)
        self.assertIsNone(empty_summary["last_scheduled"])
        self.assertIsNone(empty_summary["last_on_demand"])
        # Standalone install (no .conclave/automations/tasks.json).
        inst = self.run_smoke("-Install", "-NoRegister", "-NowOverride", "2026-11-25T10:00:00")
        self.assertEqual(inst.returncode, 0, inst.stdout + inst.stderr)
        self.assertIn("standalone", inst.stdout)
        installed_rec = json.loads((self.state / "installed.json").read_text(encoding="utf-8"))
        self.assertEqual(installed_rec["mode"], "standalone")
        uninst = self.run_smoke("-Uninstall", "-NoRegister")
        self.assertEqual(uninst.returncode, 0, uninst.stdout + uninst.stderr)
        self.assertFalse((self.state / "installed.json").exists())
        # Failed atomic replace preserves prior history bytes and cleans up temp file.
        self.state.mkdir(parents=True, exist_ok=True)
        hist = self.state / "input-history.jsonl"
        seed = '{"at":"2026-11-24T03:00:00","night":"2026-11-24","mode":"scheduled","outcome":"passed","reason":"ok"}\n'
        hist.write_text(seed, encoding="utf-8")
        # Open history file with zero sharing (exclusive Win32 handle) so File.Replace fails.
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel32.CreateFileW(str(hist), 0x80000000, 0, None, 3, 0x80, None)
        self.assertNotEqual(handle, ctypes.c_void_p(-1).value)
        try:
            (self.state / "probe-locked").write_text("1", encoding="utf-8")
            (self.state / "probe-idle").write_text("1000", encoding="utf-8")
            r = self.run_smoke("-Scheduled", "-TestProbes", "-NowOverride", "2026-11-25T03:00:00")
            self.assertNotEqual(r.returncode, 0)
        finally:
            kernel32.CloseHandle(handle)
        self.assertEqual(hist.read_text(encoding="utf-8"), seed)
        self.assertEqual(list(self.state.glob("input-history.jsonl.*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
