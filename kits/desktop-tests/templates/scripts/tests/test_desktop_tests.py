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
    proc = subprocess.Popen(
        argv, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        creationflags=NO_WINDOW,
    )
    try:
        out, err = proc.communicate(timeout=timeout)
        return subprocess.CompletedProcess(argv, proc.returncode, out, err)
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                           capture_output=True, creationflags=NO_WINDOW)
        else:
            proc.kill()
        proc.communicate()
        raise


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
using System.Runtime.InteropServices;
using System.Windows;
using System.Windows.Automation;
using System.Windows.Controls;
using System.Windows.Interop;
using System.Windows.Threading;
using Conclave.DesktopTests;

public static class FixtureApp {
    private const int WS_POPUP = unchecked((int)0x80000000);
    private const int WS_EX_TOOLWINDOW = 0x00000080;
    private const int WS_EX_NOACTIVATE = 0x08000000;
    private const int SW_SHOWNOACTIVATE = 4;
    [DllImport("user32.dll")] private static extern bool ShowWindow(IntPtr hwnd, int nCmdShow);

    [STAThread]
    public static void Main(string[] args) {
        bool forceActivate = args.Length > 0 && args[0] == "--activate";
        bool activatesFromStartup = LaunchShow.FirstWindowActivates();
        if (!forceActivate && activatesFromStartup) {
            Environment.Exit(14);
        }
        bool activate = forceActivate || activatesFromStartup;
        int clicks = 0;
        var lbl = new TextBlock { Text = "Clicks: 0" };
        AutomationProperties.SetAutomationId(lbl, "StatusLabel");
        var btn = new Button { Content = "Increment", Width = 100, Height = 30 };
        AutomationProperties.SetAutomationId(btn, "ActionButton");
        btn.Click += (s, e) => { clicks++; lbl.Text = "Clicks: " + clicks; };
        var panel = new StackPanel();
        panel.Children.Add(lbl);
        panel.Children.Add(btn);
        if (!activate) {
            // Create hidden with WS_EX_NOACTIVATE and show via SW_SHOWNOACTIVATE so Win32 never
            // activates the window or emits EVENT_SYSTEM_FOREGROUND, while exposing the full WPF UIA tree.
            var p = new HwndSourceParameters("ConclaveUiaFixtureWindow") {
                PositionX = 40,
                PositionY = 40,
                Width = 260,
                Height = 140,
                WindowStyle = WS_POPUP,
                ExtendedWindowStyle = WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW,
            };
            using (var src = new HwndSource(p)) {
                src.RootVisual = panel;
                ShowWindow(src.Handle, SW_SHOWNOACTIVATE);
                Dispatcher.Run();
            }
            return;
        }
        var win = new Window {
            Title = "ConclaveUiaFixtureWindow",
            Width = 260,
            Height = 140,
            Left = 40,
            Top = 40,
            ShowInTaskbar = false,
            ShowActivated = true,
            Content = panel,
        };
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
    [StructLayout(LayoutKind.Sequential)] struct MOUSEINPUT { public int dx, dy; public uint mouseData, dwFlags, time; public UIntPtr dwExtraInfo; }
    [StructLayout(LayoutKind.Sequential)] struct KEYBDINPUT { public ushort wVk, wScan; public uint dwFlags, time; public UIntPtr dwExtraInfo; }
    [StructLayout(LayoutKind.Sequential)] struct HARDWAREINPUT { public uint uMsg; public ushort wParamL, wParamH; }
    [StructLayout(LayoutKind.Explicit)] struct InputUnion { [FieldOffset(0)] public MOUSEINPUT mi; [FieldOffset(0)] public KEYBDINPUT ki; [FieldOffset(0)] public HARDWAREINPUT hi; }
    [StructLayout(LayoutKind.Sequential)] struct INPUT { public uint type; public InputUnion u; }
    delegate bool EnumWindowsProc(IntPtr hwnd, IntPtr lParam);
    [DllImport("user32.dll")] static extern bool EnumWindows(EnumWindowsProc cb, IntPtr lParam);
    [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr hwnd);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr hwnd, out uint pid);
    [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] static extern bool GetCursorPos(out POINT pt);
    [DllImport("user32.dll")] static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, UIntPtr dwExtraInfo);
    [DllImport("user32.dll", SetLastError = true)] static extern uint SendInput(uint n, INPUT[] inputs, int cbSize);
    [DllImport("user32.dll")] static extern bool SetForegroundWindow(IntPtr hwnd);
    [DllImport("kernel32.dll")] static extern uint GetCurrentThreadId();

    private static AutomationElement WaitForWindow(int pid, int timeoutMs) {
        DateTime end = DateTime.UtcNow.AddMilliseconds(timeoutMs);
        while (DateTime.UtcNow < end) {
            try {
                using (Process p = Process.GetProcessById(pid)) {
                    if (p.HasExited) {
                        throw new InvalidOperationException("fixture process exited early with code " + p.ExitCode);
                    }
                    if (p.MainWindowHandle != IntPtr.Zero) {
                        return AutomationElement.FromHandle(p.MainWindowHandle);
                    }
                }
            } catch (ArgumentException) {
                throw new InvalidOperationException("fixture process exited before window appeared");
            }
            IntPtr foundHwnd = IntPtr.Zero;
            EnumWindows((h, lp) => {
                uint wpid;
                GetWindowThreadProcessId(h, out wpid);
                if ((int)wpid == pid && IsWindowVisible(h)) {
                    foundHwnd = h;
                    return false;
                }
                return true;
            }, IntPtr.Zero);
            if (foundHwnd != IntPtr.Zero) {
                return AutomationElement.FromHandle(foundHwnd);
            }
            Thread.Sleep(50);
        }
        throw new TimeoutException("fixture window did not appear for pid " + pid);
    }

    private static uint SafeSendInput(uint n, INPUT[] inputs, int cbSize, ref int calls) {
        calls++;
        if (Environment.GetEnvironmentVariable("CONCLAVE_TEST_LIVE_DESK") != "1") {
            throw new RealInputRefusedException("SendInput refused at native boundary: CONCLAVE_TEST_LIVE_DESK is not 1");
        }
        return SendInput(n, inputs, cbSize);
    }

    public static int Main(string[] args) {
        string mode = args[0];
        string prefix = args[1];
        string appExe = args.Length > 2 ? args[2] : "";
        if (mode == "untraited-helper") {
            SmokeInputGuard.Require(prefix, false, "SendKey");
            return 0;
        }
        if (mode == "neg-flush-timeout") {
            try {
                using (DeskObserver obs = new DeskObserver(new int[0], flushTimeoutMs: 100)) {
                    obs.DelayHookQueueForTest(350);
                    obs.VerifyClean(mode);
                }
                return 0;
            } catch (RealInputRefusedException ex) {
                Console.Error.WriteLine("REFUSED: " + ex.Message);
                return 11;
            }
        }
        if (mode == "neg-focus-destroyed") {
            try {
                int selfPid = Process.GetCurrentProcess().Id;
                using (DeskObserver obs = new DeskObserver(new[] { selfPid })) {
                    if (obs.InstalledPidHookCount < 1) {
                        throw new InvalidOperationException("per-PID foreground hook was not installed");
                    }
                    // Spawn a secondary thread, snapshot it via TrackPid, let it exit completely so OpenThread fails,
                    // then deliver a destroyed HWND + exited TID through the real WinEvent callback path.
                    uint secondaryTid = 0;
                    var started = new ManualResetEventSlim(false);
                    var release = new ManualResetEventSlim(false);
                    var th = new Thread(() => {
                        secondaryTid = GetCurrentThreadId();
                        started.Set();
                        release.Wait(2000);
                    }) { IsBackground = true };
                    th.Start();
                    if (!started.Wait(2000) || secondaryTid == 0) {
                        throw new InvalidOperationException("secondary thread did not start");
                    }
                    obs.TrackPid(selfPid);
                    release.Set();
                    th.Join(2000);
                    obs.InvokeGlobalForegroundCallbackForTest(new IntPtr(0x12340000), secondaryTid);
                    obs.VerifyClean(mode);
                }
                return 0;
            } catch (RealInputRefusedException ex) {
                Console.Error.WriteLine("REFUSED: " + ex.Message);
                return 11;
            }
        }
        if (mode == "real-input-action") {
            SmokeInputGuard.Require(prefix, true, "SendKey");
            uint tag = SmokeInputGuard.CurrentTag(prefix);
            bool liveDesk = Environment.GetEnvironmentVariable("CONCLAVE_TEST_LIVE_DESK") == "1";
            int sendInputCalls = 0;
            uint sent = 0;
            if (liveDesk) {
                var down = new INPUT { type = 1 };
                down.u.ki = new KEYBDINPUT { wVk = 0xE8, dwFlags = 0, dwExtraInfo = (UIntPtr)tag };
                var up = new INPUT { type = 1 };
                up.u.ki = new KEYBDINPUT { wVk = 0xE8, dwFlags = 2, dwExtraInfo = (UIntPtr)tag };
                POINT cur;
                bool unlockedDesktop = GetCursorPos(out cur);
                sent = SafeSendInput(2, new[] { down, up }, Marshal.SizeOf(typeof(INPUT)), ref sendInputCalls);
                if (unlockedDesktop && sent != 2) {
                    Console.Error.WriteLine("SendInput inserted " + sent + " of 2 events on unlocked desktop");
                    return 12;
                }
            }
            Console.WriteLine("ADMITTED_OK tag=" + tag.ToString("X8") + " live=" + liveDesk + " calls=" + sendInputCalls + " sent=" + sent);
            return 0;
        }
        if (mode == "default-uia" || mode == "neg-focus" || mode == "neg-pointer" || mode == "neg-key") {
            bool liveDesk = Environment.GetEnvironmentVariable("CONCLAVE_TEST_LIVE_DESK") == "1";
            bool forceActivate = mode == "neg-focus" && liveDesk;
            int pid = 0;
            try {
                using (DeskObserver obs = new DeskObserver(new int[0])) {
                    pid = obs.LaunchNoActivate(appExe, forceActivate ? "--activate" : "", null);
                    AutomationElement win = WaitForWindow(pid, 45000);
                    AutomationElement btn = win.FindFirst(TreeScope.Descendants,
                        new PropertyCondition(AutomationElement.AutomationIdProperty, "ActionButton"));
                    AutomationElement lbl = win.FindFirst(TreeScope.Descendants,
                        new PropertyCondition(AutomationElement.AutomationIdProperty, "StatusLabel"));
                    if (btn == null || lbl == null) throw new InvalidOperationException("missing UIA controls");
                    if (mode == "neg-pointer") {
                        POINT p;
                        if (liveDesk && GetCursorPos(out p)) {
                            SetCursorPos(p.X + 4, p.Y + 4);
                            Thread.Sleep(40);
                            SetCursorPos(p.X, p.Y);
                        } else {
                            obs.ObserveCursor(100, 100);
                            obs.ObserveCursor(104, 104);
                            obs.ObserveCursor(100, 100);
                        }
                    } else if (mode == "neg-key") {
                        if (liveDesk && obs.HasDesktopCursor) {
                            keybd_event(0xE8, 0, 0, UIntPtr.Zero);
                            keybd_event(0xE8, 0, 2, UIntPtr.Zero);
                            Thread.Sleep(40);
                        } else {
                            obs.ObserveInjectedKey(0xE8, 0x10);
                        }
                    } else if (mode == "neg-focus") {
                        Thread.Sleep(40);
                        if (!liveDesk || !obs.HasDesktopCursor) {
                            int hwndVal = (int)win.GetCurrentPropertyValue(AutomationElement.NativeWindowHandleProperty);
                            obs.ObserveForegroundHandle(new IntPtr(hwndVal));
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
             f"/r:{UIA_CLIENT}", f"/r:{UIA_TYPES}", "/r:System.Windows.Forms.dll", str(guard_cs), str(drv_cs)],
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
        self.state.mkdir(parents=True, exist_ok=True)
        # Default unlocked idle probes for test harness runs.
        (self.state / "probe-locked").write_text("0", encoding="utf-8")
        (self.state / "probe-idle").write_text("1000", encoding="utf-8")

    def write_cfg(self, **overrides):
        cfg = {
            "schema_version": 1, "prefix": "demo", "window_opens": "03:00", "window_closes": "06:00",
            "idle_minutes": 15, "history_limit": 60, "log_limit": 30, "test_command": None,
            **overrides,
        }
        (self.root / ".conclave" / "desktop-tests.json").write_text(json.dumps(cfg), encoding="utf-8")

    def run_smoke(self, *args, extra_env=None, include_watcher=True):
        env = {**os.environ, **(extra_env or {})}
        cmd = [PWSH, "-NoProfile", "-NonInteractive", "-File", str(self.root / "scripts" / "smoke-input.ps1"),
               "-ProjectRoot", str(self.root), "-StateFolder", str(self.state), "-Python", sys.executable]
        if include_watcher:
            cmd += ["-Watcher", str(self.watch_exe)]
        cmd += list(args)
        return run_cmd(cmd, cwd=self.root, env=env)

    def test_default_uia_fixture_operates_control_without_touching_desk(self):
        # Pure positive WPF + UIA InvokePattern + DeskObserver test (zero desk activity!).
        ok = run_cmd([str(self.drv_exe), "default-uia", "demo", str(self.app_exe)])
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        self.assertIn("UIA_OK Clicks: 1", ok.stdout)

    def test_negative_fixtures_and_direct_bypass_refuse(self):
        # Negative fixtures (focus steal, pointer move-and-restore, injected key, untraited helper) all refuse.
        for neg, expect_detail in (
            ("neg-focus", "took the foreground window"),
            ("neg-focus-destroyed", "took the foreground window"),
            ("neg-flush-timeout", "timed out waiting for hook-thread flush acknowledgement"),
            ("neg-pointer", "pointer moved"),
            ("neg-key", "injected keyboard input"),
            ("untraited-helper", "RealInputRefusedException"),
        ):
            with self.subTest(neg=neg):
                r = run_cmd([str(self.drv_exe), neg, "demo", str(self.app_exe)])
                self.assertNotEqual(r.returncode, 0, f"{neg} unexpectedly passed: {r.stdout}")
                combined = r.stdout + r.stderr
                if neg != "untraited-helper":
                    self.assertIn("REFUSED:", combined)
                self.assertIn(expect_detail, combined)
        # Direct DEMO_SMOKE_INPUT=1 without admitted smoke-input.ps1 session must refuse.
        direct = run_cmd([str(self.drv_exe), "real-input-action", "demo"],
                         env={**os.environ, "DEMO_SMOKE_INPUT": "1"})
        self.assertNotEqual(direct.returncode, 0, direct.stdout + direct.stderr)
        self.assertIn("no admitted watcher session", direct.stdout + direct.stderr)
        # Unset prefix returns exact documented exit code 2.
        self.write_cfg(prefix=None)
        bad_cfg = self.run_smoke("-Status", include_watcher=False)
        self.assertEqual(bad_cfg.returncode, 2, bad_cfg.stdout + bad_cfg.stderr)
        # Test-harness overrides without -RunnerCommand are refused with exit code 2.
        self.write_cfg(prefix="demo")
        refused_ovr = self.run_smoke("-Scheduled", "-TestProbes", "-NowOverride", "2026-11-25T03:00:00", include_watcher=False)
        self.assertEqual(refused_ovr.returncode, 2, refused_ovr.stdout + refused_ovr.stderr)

    def test_admitted_run_and_admission_boundaries_and_custom_settings(self):
        runner_py = Path(self._tmp.name) / "real_runner.py"
        runner_py.write_text(
            "import os, subprocess, sys\n"
            f"DRV = {str(self.drv_exe)!r}\n"
            "if '--discover' in sys.argv:\n"
            "    print('DISCOVER RealSuite Case1')\n"
            "    sys.exit(0)\n"
            "r = subprocess.run([DRV, 'real-input-action', 'demo'], capture_output=True, text=True)\n"
            "print(r.stdout.strip())\n"
            "if r.returncode == 0:\n"
            "    if os.environ.get('CONCLAVE_TEST_LIVE_DESK') != '1' and 'live=False calls=0' not in r.stdout:\n"
            "        sys.exit(13)\n"
            "    print('CASE PASS RealSuite Case1')\n"
            "sys.exit(r.returncode)\n",
            encoding="utf-8",
        )
        # On-demand enforces the SAME admission rules: outside-window, locked, and busy-below-idle all refuse!
        ondem_outside = self.run_smoke("-TestProbes", "-NowOverride", "2026-11-25T14:00:00", "-RunnerCommand", str(runner_py))
        self.assertEqual(ondem_outside.returncode, 1)
        self.assertIn("outside-window", ondem_outside.stderr)
        (self.state / "probe-locked").write_text("1", encoding="utf-8")
        ondem_locked = self.run_smoke("-TestProbes", "-NowOverride", "2026-11-25T03:00:00", "-RunnerCommand", str(runner_py))
        self.assertEqual(ondem_locked.returncode, 1)
        self.assertIn("desktop-locked", ondem_locked.stderr)
        (self.state / "probe-locked").write_text("0", encoding="utf-8")
        (self.state / "probe-idle").write_text("899", encoding="utf-8")
        ondem_busy = self.run_smoke("-TestProbes", "-NowOverride", "2026-11-25T03:00:00", "-RunnerCommand", str(runner_py))
        self.assertEqual(ondem_busy.returncode, 1)
        self.assertIn("desktop-busy", ondem_busy.stderr)
        (self.state / "probe-idle").write_text("1000", encoding="utf-8")
        # Scheduled refusals: outside window, unknown desktop, locked, busy (899s < 900s).
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
        # Eligible scheduled AND on-demand runs at 03:00 with exactly 900s idle execute real case and pass!
        (self.state / "probe-unknown").unlink(missing_ok=True)
        (self.state / "probe-locked").write_text("0", encoding="utf-8")
        (self.state / "probe-idle").write_text("900", encoding="utf-8")
        ok = self.run_smoke("-Scheduled", "-TestProbes", "-NowOverride", "2026-11-25T03:00:00", "-RunnerCommand", str(runner_py))
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        self.assertIn("smoke-input: passed (1 case(s) across 1 class(es))", ok.stdout)
        od_ok = self.run_smoke("-TestProbes", "-NowOverride", "2026-11-25T03:00:00", "-RunnerCommand", str(runner_py))
        self.assertEqual(od_ok.returncode, 0, od_ok.stdout + od_ok.stderr)
        self.assertIn("smoke-input: passed (1 case(s) across 1 class(es))", od_ok.stdout)
        # Changed settings (window 01:00-02:00, idle 5m=300s) take effect.
        self.write_cfg(window_opens="01:00", window_closes="02:00", idle_minutes=5)
        (self.state / "probe-idle").write_text("300", encoding="utf-8")
        custom_ok = self.run_smoke("-Scheduled", "-TestProbes", "-NowOverride", "2026-11-25T01:30:00", "-RunnerCommand", str(runner_py))
        self.assertEqual(custom_ok.returncode, 0, custom_ok.stdout + custom_ok.stderr)
        self.assertIn("smoke-input: passed", custom_ok.stdout)

    def test_watcher_stdin_eof_exits_promptly_and_release_tag_rejected_when_idle(self):
        rec = Path(self._tmp.name) / "watch-eof.txt"
        p = subprocess.Popen(
            [str(self.watch_exe), str(rec), "12345678", "", "1", ""],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            creationflags=NO_WINDOW,
        )
        try:
            self.assertEqual(p.stdout.readline().strip(), "watching")
            # Hold a key and release it; verify release output is emitted.
            p.stdin.write("hold 232\nrelease\n")
            p.stdin.flush()
            rel_line = p.stdout.readline().strip()
            self.assertTrue(rel_line.startswith("released 232:"), rel_line)
            # Closing stdin without 'quit' must cause watcher to exit promptly (not linger 4 hours).
            p.stdin.close()
            rc = p.wait(timeout=5)
            self.assertEqual(rc, 0)
        finally:
            if p.poll() is None:
                p.kill()
                p.wait(timeout=5)

    def test_mid_class_interruptions_kill_descendants_and_distinguish_tags(self):
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
            "time.sleep(0.8 if os.environ.get('FAST_PASS') else 30)\n"
            "AFTER.write_text('late-input', encoding='utf-8')\n"
            "print('CASE PASS SlowSuite Case1')\n",
            encoding="utf-8",
        )
        proxy_watch = Path(self._tmp.name) / "proxy_watch.py"
        proxy_watch.write_text(
            "import os, pathlib, subprocess, sys, time\n"
            f"REAL = {str(self.watch_exe)!r}\n"
            f"PIDF = pathlib.Path({str(pid_file)!r})\n"
            "mode = os.environ.get('WATCH_ACTION', '')\n"
            "p = subprocess.Popen([REAL, *sys.argv[1:]], stdin=subprocess.PIPE, stdout=subprocess.PIPE, "
            "stderr=subprocess.PIPE, text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))\n"
            "line = p.stdout.readline().strip()\n"
            "print(line, flush=True)\n"
            "# Wait deterministically until grandchild.pid exists so descendant containment is always verified.\n"
            "deadline = time.time() + 10.0\n"
            "while not PIDF.exists() and time.time() < deadline:\n"
            "    time.sleep(0.05)\n"
            "if mode == 'crash':\n"
            "    p.kill(); sys.exit(9)\n"
            "if mode in ('person', 'foreign-tag', 'release-tag-when-idle', 'smoke-tag'):\n"
            "    p.stdin.write(mode + '\\n'); p.stdin.flush()\n"
            "for cmd in sys.stdin:\n"
            "    p.stdin.write(cmd); p.stdin.flush()\n"
            "p.wait()\n",
            encoding="utf-8",
        )
        for action, expect_rc, expect_msg in (
            ("person", 1, "person-input"),
            ("foreign-tag", 1, "person-input"),
            ("release-tag-when-idle", 1, "person-input"),
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
                     "-ProjectRoot", str(self.root), "-StateFolder", str(self.state), "-TestProbes",
                     "-NowOverride", "2026-11-25T03:00:00",
                     "-Python", sys.executable, "-Watcher", str(proxy_watch), "-RunnerCommand", str(sleep_runner)],
                    cwd=self.root, env={**os.environ, **extra},
                )
                self.assertEqual(res.returncode, expect_rc, res.stdout + res.stderr)
                self.assertIn(expect_msg, res.stdout)
                self.assertTrue(pid_file.exists(), "grandchild must have started before interruption")
                if expect_rc == 1:
                    self.assertFalse(after_file.exists(), "stopped class must not run subsequent input")
                    gpid = pid_file.read_text(encoding="utf-8").strip()
                    chk = run_cmd(["tasklist", "/FI", f"PID eq {gpid}", "/NH"])
                    self.assertNotIn(gpid, chk.stdout)

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
            "time.sleep(0.2)\n"
            "if os.environ.get('TRIGGER') == 'lock':\n"
            "    (STATE / 'probe-locked').write_text('1', encoding='utf-8')\n"
            "elif os.environ.get('TRIGGER') == 'deadline':\n"
            "    (STATE / 'probe-now').write_text('2026-11-25T06:00:01', encoding='utf-8')\n"
            "time.sleep(30)\n"
            "AFTER.write_text('late-input', encoding='utf-8')\n"
            "print('CASE PASS SlowSuite Case1')\n",
            encoding="utf-8",
        )
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
                self.assertTrue(pid_file.exists(), "grandchild must have started before stop")
                self.assertFalse(after_file.exists(), "stopped class must not run subsequent input")
                gpid = pid_file.read_text(encoding="utf-8").strip()
                chk = run_cmd(["tasklist", "/FI", f"PID eq {gpid}", "/NH"])
                self.assertNotIn(gpid, chk.stdout)

    def test_reconciliation_failures_and_bounded_history_and_missed_nights(self):
        rec_runner = Path(self._tmp.name) / "rec_runner.py"
        rec_runner.write_text(
            "import os, sys\n"
            "mode = os.environ['REC_MODE']\n"
            "if '--discover' in sys.argv:\n"
            "    if mode == 'dup-disc':\n"
            "        print('DISCOVER SuiteA Case1')\n"
            "        print('DISCOVER SuiteA Case1')\n"
            "    elif mode == 'case-sens':\n"
            "        print('DISCOVER SuiteA Case1')\n"
            "        print('DISCOVER SuiteA case1')\n"
            "    elif mode != 'empty':\n"
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
            "elif mode == 'case-sens':\n"
            "    print('CASE PASS SuiteA Case1')\n"
            "elif mode == 'ok':\n"
            "    print('CASE PASS SuiteA Case1')\n"
            "    print('CASE PASS SuiteA Case2')\n",
            encoding="utf-8",
        )
        self.write_cfg(history_limit=4, log_limit=2)
        for mode, needle in (
            ("empty", "discovery returned 0"),
            ("dup-disc", "duplicate discovered case"),
            ("case-sens", "case-missing:SuiteA/case1"),
            ("missing", "case-missing"),
            ("duplicate", "case-duplicate"),
            ("skip", "case-skipped"),
            ("fail", "case-failed"),
            ("nonzero", "class-exit-nonzero"),
        ):
            with self.subTest(mode=mode):
                r = self.run_smoke("-TestProbes", "-NowOverride", "2026-11-25T03:00:00",
                                   "-RunnerCommand", str(rec_runner), extra_env={"REC_MODE": mode})
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertIn(needle, r.stdout + r.stderr)
        # Install on 2026-11-20 10:00 (first_expected_night = 2026-11-21); run scheduled night 2026-11-21!
        inst = self.run_smoke("-Install", "-NoRegister", "-NowOverride", "2026-11-20T10:00:00")
        self.assertEqual(inst.returncode, 0, inst.stdout + inst.stderr)
        sched_ok = self.run_smoke("-Scheduled", "-TestProbes", "-NowOverride", "2026-11-21T03:00:00",
                                  "-RunnerCommand", str(rec_runner), extra_env={"REC_MODE": "ok"})
        self.assertEqual(sched_ok.returncode, 0, sched_ok.stdout + sched_ok.stderr)
        # Run 5 on-demand runs to evict the 2026-11-21 scheduled entry from history_limit=4!
        for _ in range(5):
            od = self.run_smoke("-TestProbes", "-NowOverride", "2026-11-25T03:00:00",
                                "-RunnerCommand", str(rec_runner), extra_env={"REC_MODE": "ok"})
            self.assertEqual(od.returncode, 0, od.stdout + od.stderr)
        hist_lines = [l for l in (self.state / "input-history.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
        self.assertEqual(len(hist_lines), 4)
        self.assertLessEqual(len(list((self.state / "logs").glob("*.log"))), 2)
        # Reinstall on 2026-11-24 must preserve first_expected_night=2026-11-21!
        reinst = self.run_smoke("-Install", "-NoRegister", "-NowOverride", "2026-11-24T10:00:00")
        self.assertEqual(reinst.returncode, 0, reinst.stdout + reinst.stderr)
        # 2026-11-21 ran scheduled (even though evicted from history_limit=4), so only 22, 23, 24 are missed!
        st = self.run_smoke("-Status", "-NowOverride", "2026-11-24T08:00:00")
        self.assertEqual(st.returncode, 0, st.stdout + st.stderr)
        summary = json.loads(st.stdout)
        self.assertEqual(summary["missed_nights"], 3, summary)
        self.assertEqual(summary["missed_dates"], ["2026-11-22", "2026-11-23", "2026-11-24"])
        # Legacy 1-element JSON array ["2026-11-21"] (unwrapped to string by PowerShell ConvertFrom-Json) must survive read and write.
        (self.state / "scheduled-nights.json").write_text('["2026-11-21"]', encoding="utf-8")
        st_leg = self.run_smoke("-Status", "-NowOverride", "2026-11-24T08:00:00")
        self.assertEqual(st_leg.returncode, 0, st_leg.stdout + st_leg.stderr)
        self.assertEqual(json.loads(st_leg.stdout)["missed_dates"], ["2026-11-22", "2026-11-23", "2026-11-24"])
        sched2 = self.run_smoke("-Scheduled", "-TestProbes", "-NowOverride", "2026-11-22T03:00:00",
                                "-RunnerCommand", str(rec_runner), extra_env={"REC_MODE": "ok"})
        self.assertEqual(sched2.returncode, 0, sched2.stdout + sched2.stderr)
        st_leg2 = self.run_smoke("-Status", "-NowOverride", "2026-11-24T08:00:00")
        self.assertEqual(json.loads(st_leg2.stdout)["missed_dates"], ["2026-11-23", "2026-11-24"])
        # Legacy {floor_date, dates} ledger must enforce floor_date before and after migration write.
        (self.state / "scheduled-nights.json").write_text(
            json.dumps({"floor_date": "2026-11-22", "dates": ["2026-11-22"]}), encoding="utf-8"
        )
        st_fl1 = self.run_smoke("-Status", "-NowOverride", "2026-11-24T08:00:00")
        self.assertEqual(st_fl1.returncode, 0, st_fl1.stdout + st_fl1.stderr)
        self.assertEqual(json.loads(st_fl1.stdout)["missed_dates"], ["2026-11-23", "2026-11-24"])
        sched3 = self.run_smoke("-Scheduled", "-TestProbes", "-NowOverride", "2026-11-23T03:00:00",
                                "-RunnerCommand", str(rec_runner), extra_env={"REC_MODE": "ok"})
        self.assertEqual(sched3.returncode, 0, sched3.stdout + sched3.stderr)
        st_fl2 = self.run_smoke("-Status", "-NowOverride", "2026-11-24T08:00:00")
        self.assertEqual(json.loads(st_fl2.stdout)["missed_dates"], ["2026-11-24"])
        migrated = json.loads((self.state / "scheduled-nights.json").read_text(encoding="utf-8"))
        self.assertEqual(migrated.get("floor_date"), "2026-11-22")

    def test_automations_integration_ownership_and_standalone_modes(self):
        # Empty status before any run.
        empty_st = self.run_smoke("-Status", "-NowOverride", "2026-11-25T08:00:00")
        self.assertEqual(empty_st.returncode, 0, empty_st.stdout + empty_st.stderr)
        empty_summary = json.loads(empty_st.stdout)
        self.assertEqual(empty_summary["total_records"], 0)
        self.assertIsNone(empty_summary["last_scheduled"])
        # Standalone install/uninstall (no .conclave/automations/tasks.json).
        inst_s = self.run_smoke("-Install", "-NoRegister", "-NowOverride", "2026-11-25T10:00:00")
        self.assertEqual(inst_s.returncode, 0, inst_s.stdout + inst_s.stderr)
        self.assertIn("standalone", inst_s.stdout)
        self.assertEqual(json.loads((self.state / "installed.json").read_text(encoding="utf-8"))["mode"], "standalone")
        self.assertEqual(self.run_smoke("-Uninstall", "-NoRegister").returncode, 0)
        self.assertFalse((self.state / "installed.json").exists())

        # Combined automations install (standalone test, zero SDK-relative path dependency!).
        auto_dir = self.root / ".conclave" / "automations"
        auto_dir.mkdir(parents=True)
        # Null folder must be refused without mutating tasks.json or installed.json.
        (auto_dir / "tasks.json").write_text(json.dumps({"schema_version": 1, "folder": None, "tasks": []}), encoding="utf-8")
        null_res = self.run_smoke("-Install", "-NoRegister", "-NowOverride", "2026-11-25T10:00:00")
        self.assertEqual(null_res.returncode, 2, null_res.stdout + null_res.stderr)
        self.assertFalse((self.state / "installed.json").exists())
        # Same-named unrelated task (including one that merely passes smoke-input.ps1 as an argument) must NOT be touched.
        unrelated = {
            "schema_version": 1, "folder": "\\demo\\",
            "tasks": [{"name": "demo-real-input-smoke", "description": "User backup task",
                       "command": ["python", "backup.py", "scripts/smoke-input.ps1"],
                       "trigger": {"weekly": "Sunday", "at": "02:00"}, "timeout_minutes": 10}],
        }
        (auto_dir / "tasks.json").write_text(json.dumps(unrelated, indent=2), encoding="utf-8")
        self.assertEqual(self.run_smoke("-Install", "-NoRegister", "-NowOverride", "2026-11-25T10:00:00").returncode, 2)
        self.assertEqual(self.run_smoke("-Uninstall", "-NoRegister").returncode, 2)
        # Valid manifest with pre-existing task preserves other task across install and uninstall.
        existing_manifest = {
            "schema_version": 1, "folder": "\\demo\\",
            "tasks": [{"name": "demo-health", "description": "Existing weekly health check",
                       "command": ["python", "-c", "print('ok')"],
                       "trigger": {"weekly": "Sunday", "at": "02:00"}, "timeout_minutes": 10}],
        }
        (auto_dir / "tasks.json").write_text(json.dumps(existing_manifest, indent=2), encoding="utf-8")
        inst = self.run_smoke("-Install", "-NoRegister", "-NowOverride", "2026-11-25T10:00:00")
        self.assertEqual(inst.returncode, 0, inst.stdout + inst.stderr)
        updated = json.loads((auto_dir / "tasks.json").read_text(encoding="utf-8"))
        self.assertEqual([t["name"] for t in updated["tasks"]], ["demo-health", "demo-real-input-smoke"])
        smoke_task = updated["tasks"][1]
        self.assertEqual(smoke_task["trigger"], {"daily": True, "at": "03:00", "random_delay_minutes": 0})
        self.assertEqual(smoke_task["timeout_minutes"], 180)
        self.assertIs(smoke_task["start_when_available"], False)
        self.assertIs(smoke_task["wake_to_run"], False)
        self.assertIs(smoke_task["exact_timeout"], True)
        uninst = self.run_smoke("-Uninstall", "-NoRegister")
        self.assertEqual(uninst.returncode, 0, uninst.stdout + uninst.stderr)
        after = json.loads((auto_dir / "tasks.json").read_text(encoding="utf-8"))
        self.assertEqual([t["name"] for t in after["tasks"]], ["demo-health"])

    def test_failed_replace_and_unreadable_history_preserve_prior_bytes(self):
        hist = self.state / "input-history.jsonl"
        seed = '{"at":"2026-11-24T03:00:00","night":"2026-11-24","mode":"scheduled","outcome":"passed","reason":"ok"}\n'
        hist.write_text(seed, encoding="utf-8")
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        # Exclusive Win32 handle blocks both read and replace: smoke-input must fail closed and leave history intact!
        handle = kernel32.CreateFileW(str(hist), 0x80000000, 0, None, 3, 0x80, None)
        self.assertNotEqual(handle, ctypes.c_void_p(-1).value)
        try:
            (self.state / "probe-locked").write_text("1", encoding="utf-8")
            (self.state / "probe-idle").write_text("1000", encoding="utf-8")
            r = self.run_smoke("-Scheduled", "-TestProbes", "-NowOverride", "2026-11-25T03:00:00",
                               "-RunnerCommand", str(Path(self._tmp.name) / "unused.py"))
            self.assertNotEqual(r.returncode, 0)
        finally:
            kernel32.CloseHandle(handle)
        self.assertEqual(hist.read_text(encoding="utf-8"), seed)
        self.assertEqual(list(self.state.glob("input-history.jsonl.*.tmp")), [])

    def test_real_windows_task_scheduler_install_ownership_and_uninstall(self):
        # Exercises real Windows Task Scheduler registration, inspection, ownership refusal, and cleanup.
        unique_prefix = f"conclave-dt-{os.getpid()}"
        task_name = f"{unique_prefix}-real-input-smoke"
        task_path = f"\\{unique_prefix}\\"
        self.write_cfg(prefix=unique_prefix)
        cleanup_ps = (
            f"Unregister-ScheduledTask -TaskPath '{task_path}' -TaskName '{task_name}' -Confirm:$false -ErrorAction Ignore; "
            f"$s = New-Object -ComObject Schedule.Service; $s.Connect(); "
            f"try {{ $s.GetFolder('\\').DeleteFolder('{unique_prefix}', 0) }} catch {{ }}"
        )
        try:
            # 1. Pre-existing unrelated scheduled task (even one mentioning smoke-input.ps1 and -Scheduled!) must be refused.
            script_path = str(self.root / "scripts" / "smoke-input.ps1")
            reg_other = run_cmd([
                PWSH, "-NoProfile", "-NonInteractive", "-Command",
                f"$a = New-ScheduledTaskAction -Execute 'pwsh.exe' -Argument '-File backup.ps1 \"{script_path}\" -Scheduled'; "
                f"$t = New-ScheduledTaskTrigger -Daily -At '04:00'; "
                f"Register-ScheduledTask -TaskPath '{task_path}' -TaskName '{task_name}' -Action $a -Trigger $t -Force | Out-Null",
            ])
            self.assertEqual(reg_other.returncode, 0, reg_other.stdout + reg_other.stderr)
            ref_inst = self.run_smoke("-Install", "-NowOverride", "2026-11-25T10:00:00", include_watcher=False)
            self.assertEqual(ref_inst.returncode, 2, ref_inst.stdout + ref_inst.stderr)
            ref_uninst = self.run_smoke("-Uninstall", include_watcher=False)
            self.assertEqual(ref_uninst.returncode, 2, ref_uninst.stdout + ref_uninst.stderr)
            # Remove the unrelated task so we can test genuine owned install.
            run_cmd([PWSH, "-NoProfile", "-NonInteractive", "-Command", cleanup_ps])
            # 2. Owned standalone install registers a real Interactive Daily 03:00 3-hour task with StartWhenAvailable=False, WakeToRun=False.
            inst = self.run_smoke("-Install", "-NowOverride", "2026-11-25T10:00:00", include_watcher=False)
            self.assertEqual(inst.returncode, 0, inst.stdout + inst.stderr)
            inspect = run_cmd([
                PWSH, "-NoProfile", "-NonInteractive", "-Command",
                f"$t = Get-ScheduledTask -TaskPath '{task_path}' -TaskName '{task_name}'; "
                f"[ordered]@{{ logon=[string]$t.Principal.LogonType; swa=$t.Settings.StartWhenAvailable; "
                f"wake=$t.Settings.WakeToRun; lim=[string]$t.Settings.ExecutionTimeLimit; "
                f"exe=[string]$t.Actions[0].Execute; args=[string]$t.Actions[0].Arguments; "
                f"wd=[string]$t.Actions[0].WorkingDirectory; "
                f"trigClass=[string]$t.Triggers[0].CimClass.CimClassName; "
                f"trigStart=[string]$t.Triggers[0].StartBoundary }} | ConvertTo-Json",
            ])
            self.assertEqual(inspect.returncode, 0, inspect.stdout + inspect.stderr)
            info = json.loads(inspect.stdout)
            self.assertEqual(info["logon"], "Interactive")
            self.assertIs(info["swa"], False)
            self.assertIs(info["wake"], False)
            self.assertEqual(info["lim"], "PT3H")
            self.assertEqual(info["exe"].lower(), "pwsh.exe")
            self.assertEqual(info["args"], f'-NoProfile -NonInteractive -File "{script_path}" -Scheduled')
            self.assertEqual(Path(info["wd"]).resolve(), self.root.resolve())
            self.assertEqual(info["trigClass"], "MSFT_TaskDailyTrigger")
            self.assertIn("T03:00:00", info["trigStart"])
            # 3. Owned uninstall removes it cleanly.
            uninst = self.run_smoke("-Uninstall", include_watcher=False)
            self.assertEqual(uninst.returncode, 0, uninst.stdout + uninst.stderr)
            gone = run_cmd([
                PWSH, "-NoProfile", "-NonInteractive", "-Command",
                f"if (Get-ScheduledTask -TaskPath '{task_path}' -TaskName '{task_name}' -ErrorAction SilentlyContinue) {{ exit 1 }}",
            ])
            self.assertEqual(gone.returncode, 0)
        finally:
            run_cmd([PWSH, "-NoProfile", "-NonInteractive", "-Command", cleanup_ps])

    def test_uninstall_fails_closed_on_scheduler_errors_and_missing_folder(self):
        # 1. Standalone uninstall with ObjectNotFound followed by PermissionDenied from Get-ScheduledTask
        # must exit 2, retain installed.json, and never invoke Unregister-ScheduledTask.
        inst = self.run_smoke("-Install", "-NoRegister", "-NowOverride", "2026-11-25T10:00:00", include_watcher=False)
        self.assertEqual(inst.returncode, 0, inst.stdout + inst.stderr)
        inst_file = self.state / "installed.json"
        self.assertTrue(inst_file.exists())
        unreg_marker = Path(self._tmp.name) / "unreg_called.txt"
        script = str(self.root / "scripts" / "smoke-input.ps1")
        shadow_cmd = (
            "function Get-ScheduledTask { [CmdletBinding()] param($TaskPath, $TaskName) "
            "Write-Error -Message 'not found' -Category ObjectNotFound; "
            "Write-Error -Message 'access denied 0x80041003' -Category PermissionDenied }; "
            f"function Unregister-ScheduledTask {{ Set-Content -LiteralPath '{unreg_marker}' -Value 'called' }}; "
            f"& '{script}' -ProjectRoot '{self.root}' -StateFolder '{self.state}' -Python '{sys.executable}' -Uninstall; "
            "exit $LASTEXITCODE"
        )
        res = run_cmd([PWSH, "-NoProfile", "-NonInteractive", "-Command", shadow_cmd], cwd=self.root)
        self.assertEqual(res.returncode, 2, res.stdout + res.stderr)
        self.assertIn("installed state retained", res.stderr)
        self.assertTrue(inst_file.exists(), "installed.json must be retained on scheduler lookup failure")
        self.assertFalse(unreg_marker.exists(), "Unregister-ScheduledTask must not run on lookup failure")
        # 2. Combined uninstall with cleared folder in tasks.json must exit 2 and retain the manifest entry.
        auto_dir = self.root / ".conclave" / "automations"
        auto_dir.mkdir(parents=True)
        manifest = {
            "schema_version": 1, "folder": None,
            "tasks": [{
                "name": "demo-real-input-smoke",
                "description": "Nightly real-input desktop UI tests for demo",
                "command": ["pwsh", "-NoProfile", "-NonInteractive", "-File", "scripts/smoke-input.ps1", "-Scheduled"],
                "trigger": {"daily": True, "at": "03:00", "random_delay_minutes": 0},
                "timeout_minutes": 180, "start_when_available": False, "wake_to_run": False, "exact_timeout": True,
            }],
        }
        manifest_path = auto_dir / "tasks.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        for extra_flags in (("-Uninstall",), ("-Uninstall", "-NoRegister")):
            with self.subTest(flags=extra_flags):
                comb_res = self.run_smoke(*extra_flags, include_watcher=False)
                self.assertEqual(comb_res.returncode, 2, comb_res.stdout + comb_res.stderr)
                self.assertIn("manifest retained", comb_res.stderr)
                retained = json.loads(manifest_path.read_text(encoding="utf-8"))
                self.assertEqual([t["name"] for t in retained["tasks"]], ["demo-real-input-smoke"])


if __name__ == "__main__":
    unittest.main()
