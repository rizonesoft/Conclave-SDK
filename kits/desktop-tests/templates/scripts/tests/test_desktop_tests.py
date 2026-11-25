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
                    if (!th.Join(2000)) {
                        throw new InvalidOperationException("secondary thread did not exit");
                    }
                    obs.InvokeGlobalForegroundCallbackForTest(new IntPtr(0x12340000), secondaryTid);
                    obs.VerifyClean(mode);
                }
                return 0;
            } catch (RealInputRefusedException ex) {
                Console.Error.WriteLine("REFUSED: " + ex.Message);
                return 11;
            }
        }
        if (mode == "neg-focus-pid-hook") {
            try {
                int selfPid = Process.GetCurrentProcess().Id;
                using (DeskObserver obs = new DeskObserver(new[] { selfPid })) {
                    // Exercise the registered per-PID WinEventDelegate directly with a synthetic invalid HWND and unsnapshotted TID.
                    obs.InvokePidForegroundCallbackForTest(selfPid, new IntPtr(0x12340000), 0x7FFFFFFEu);
                    obs.VerifyClean(mode);
                }
                return 0;
            } catch (RealInputRefusedException ex) {
                Console.Error.WriteLine("REFUSED: " + ex.Message);
                return 11;
            }
        }
        if (mode == "track-late-ack") {
            int pidA = Process.GetCurrentProcess().Id;
            int pidB = pidA + 1;
            var aEntered = new ManualResetEventSlim(false);
            var releaseA = new ManualResetEventSlim(false);
            var bQueued = new ManualResetEventSlim(false);
            var bEntered = new ManualResetEventSlim(false);
            var releaseB = new ManualResetEventSlim(false);
            var bDone = new ManualResetEventSlim(false);
            int aWaitTimedOut = 0;
            int bWaitTimedOut = 0;
            Exception bError = null;
            using (DeskObserver obs = new DeskObserver(new int[0], flushTimeoutMs: 2000)) {
                obs.BeforeTrackInstallForTest = p => {
                    if (p == pidA) {
                        aEntered.Set();
                        if (!releaseA.Wait(5000)) Interlocked.Exchange(ref aWaitTimedOut, 1);
                    } else if (p == pidB) {
                        bEntered.Set();
                        if (!releaseB.Wait(5000)) Interlocked.Exchange(ref bWaitTimedOut, 1);
                    }
                };
                obs.AfterTrackEnqueueForTest = p => {
                    if (p == pidB) bQueued.Set();
                };
                bool aTimedOut = false;
                try {
                    obs.TrackPid(pidA, 80);
                } catch (InvalidOperationException ex) {
                    aTimedOut = ex.Message.IndexOf("timed out", StringComparison.OrdinalIgnoreCase) >= 0;
                }
                if (!aTimedOut || !aEntered.Wait(2000)) {
                    Console.Error.WriteLine("expected pidA registration to enter and time out");
                    return 13;
                }
                var threadB = new Thread(() => {
                    try { obs.TrackPid(pidB, 4000); }
                    catch (Exception ex) { bError = ex; }
                    finally { bDone.Set(); }
                }) { IsBackground = true };
                threadB.Start();
                if (!bQueued.Wait(2000)) {
                    Console.Error.WriteLine("pidB did not enqueue its request before releasing pidA");
                    releaseA.Set();
                    releaseB.Set();
                    return 17;
                }
                // Release A only after B has enqueued under _trackQueue; A's late acknowledgement must not complete B.
                releaseA.Set();
                if (!bEntered.Wait(2000)) {
                    Console.Error.WriteLine("pidB registration never reached hook thread after pidA completed");
                    releaseB.Set();
                    return 14;
                }
                if (bDone.Wait(150)) {
                    Console.Error.WriteLine("pidB completed prematurely on pidA late acknowledgement");
                    releaseB.Set();
                    return 15;
                }
                releaseB.Set();
                if (!bDone.Wait(3000) || bError != null) {
                    Console.Error.WriteLine("pidB failed after release: " + (bError == null ? "timeout" : bError.Message));
                    return 16;
                }
                if (Volatile.Read(ref aWaitTimedOut) != 0 || Volatile.Read(ref bWaitTimedOut) != 0) {
                    Console.Error.WriteLine("hook-wait timed out before explicit release (a=" + aWaitTimedOut + ", b=" + bWaitTimedOut + ")");
                    return 18;
                }
            }
            Console.WriteLine("TRACK_LATE_ACK_OK");
            return 0;
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
            DesktopLockHandle liveLock = null;
            try {
                if (liveDesk && mode != "default-uia") {
                    liveLock = DesktopLock.Acquire(prefix, mode);
                }
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
            } catch (DesktopLockBusyException ex) {
                Console.Error.WriteLine("LOCK_BUSY: " + ex.Message);
                return 21;
            } catch (RealInputRefusedException ex) {
                Console.Error.WriteLine("REFUSED: " + ex.Message);
                return 11;
            } finally {
                if (liveLock != null) liveLock.Dispose();
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


LOCK_DRIVER_CS = r'''
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Threading;
using Conclave.DesktopTests;

public static class LockDriver {
    private const uint READ_CONTROL = 0x00020000;
    private const uint DACL_SECURITY_INFORMATION = 0x00000004;
    private const int SE_KERNEL_OBJECT = 6;
    private const uint SYNCHRONIZE = 0x00100000;

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern IntPtr OpenMutexW(uint dwDesiredAccess, bool bInheritHandle, string lpName);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern IntPtr OpenEventW(uint dwDesiredAccess, bool bInheritHandle, string lpName);
    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool CloseHandle(IntPtr hObject);
    [DllImport("kernel32.dll")]
    private static extern IntPtr LocalFree(IntPtr hMem);
    [DllImport("advapi32.dll", SetLastError = true)]
    private static extern uint GetSecurityInfo(
        IntPtr handle, int ObjectType, uint SecurityInfo,
        IntPtr ppsidOwner, IntPtr ppsidGroup, IntPtr ppDacl, IntPtr ppSacl, out IntPtr ppSecurityDescriptor);
    [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern bool ConvertSecurityDescriptorToStringSecurityDescriptorW(
        IntPtr SecurityDescriptor, uint RequestedStringSDRevision, uint SecurityInformation,
        out IntPtr StringSecurityDescriptor, IntPtr StringSecurityDescriptorLen);

    private static string ReadDaclSddl(IntPtr h) {
        IntPtr sd;
        uint rc = GetSecurityInfo(h, SE_KERNEL_OBJECT, DACL_SECURITY_INFORMATION, IntPtr.Zero, IntPtr.Zero, IntPtr.Zero, IntPtr.Zero, out sd);
        if (rc != 0) throw new InvalidOperationException("GetSecurityInfo failed: " + rc);
        try {
            IntPtr sddlPtr;
            if (!ConvertSecurityDescriptorToStringSecurityDescriptorW(sd, 1, DACL_SECURITY_INFORMATION, out sddlPtr, IntPtr.Zero))
                throw new InvalidOperationException("ConvertSecurityDescriptorToStringSecurityDescriptorW failed: " + Marshal.GetLastWin32Error());
            try { return Marshal.PtrToStringUni(sddlPtr); }
            finally { LocalFree(sddlPtr); }
        } finally {
            LocalFree(sd);
        }
    }

    private static Dictionary<string, string> CopyEnv(string extraKey, string extraVal) {
        var env = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        foreach (System.Collections.DictionaryEntry de in Environment.GetEnvironmentVariables())
            env[(string)de.Key] = (string)de.Value;
        if (extraKey != null) env[extraKey] = extraVal;
        return env;
    }

    public static int Main(string[] args) {
        string cmd = args[0];
        string prefix = args[1];
        string selfExe = Process.GetCurrentProcess().MainModule.FileName;
        try {
            if (cmd == "hold") {
                using (var h = DesktopLock.Acquire(prefix, "lock-driver-hold")) {
                    Console.WriteLine("HELD pid=" + h.HolderPid + " ticks=" + h.HolderStartTicks
                        + " utc=" + h.HolderStartUtc + " lease=" + h.LeaseId
                        + " leaseEvent=" + h.LeaseEventName + " job=" + h.JobName
                        + " record=" + h.RecordPath + " lock=" + h.LockName + " token=" + h.HeldToken);
                    Console.Out.Flush();
                    string line = Console.In.ReadLine();
                    if (line == "exit-raw") Environment.Exit(0);
                }
                Console.WriteLine("RELEASED");
                Console.Out.Flush();
                return 0;
            }
            if (cmd == "wait-acquire") {
                bool holdUntilStdin = args.Length > 2 && args[2] == "hold";
                Console.WriteLine("WAITING");
                Console.Out.Flush();
                using (var h = DesktopLock.Acquire(prefix, "lock-driver-wait")) {
                    Console.WriteLine("ACQUIRED pid=" + h.HolderPid + " ticks=" + h.HolderStartTicks
                        + " inherited=" + h.Inherited + " record=" + h.RecordPath + " lock=" + h.LockName);
                    Console.Out.Flush();
                    if (holdUntilStdin) Console.In.ReadLine();
                }
                Console.WriteLine("DONE");
                return 0;
            }
            if (cmd == "check-dacl") {
                using (var h = DesktopLock.Acquire(prefix, "lock-driver-dacl")) {
                    IntPtr hm = OpenMutexW(READ_CONTROL, false, h.LockName);
                    IntPtr he = OpenEventW(READ_CONTROL, false, h.LeaseEventName);
                    if (hm == IntPtr.Zero || he == IntPtr.Zero)
                        throw new InvalidOperationException("failed to reopen handles with READ_CONTROL");
                    try {
                        string mSddl = ReadDaclSddl(hm);
                        string eSddl = ReadDaclSddl(he);
                        Console.WriteLine("MUTEX_DACL=" + mSddl);
                        Console.WriteLine("LEASE_DACL=" + eSddl);
                    } finally {
                        CloseHandle(hm);
                        CloseHandle(he);
                    }
                }
                return 0;
            }
            if (cmd == "fail-publish") {
                DesktopLock.FailRecordPublishForTest = true;
                bool failed = false;
                try {
                    using (DesktopLock.Acquire(prefix, "lock-driver-fail")) { }
                } catch (IOException) {
                    failed = true;
                } finally {
                    DesktopLock.FailRecordPublishForTest = false;
                }
                if (!failed) return 31;
                Console.WriteLine("FAILED_PUBLISH_OK");
                Console.Out.Flush();
                Console.In.ReadLine();
                return 0;
            }
            if (cmd == "pause-before-publish") {
                string resumeFile = args[2];
                DesktopLock.BeforeRecordPublishForTest = () => {
                    Console.WriteLine("BEFORE_PUBLISH");
                    Console.Out.Flush();
                    DateTime dl = DateTime.UtcNow.AddSeconds(15);
                    while (!File.Exists(resumeFile) && DateTime.UtcNow < dl) Thread.Sleep(25);
                };
                using (var h = DesktopLock.Acquire(prefix, "lock-driver-pause")) {
                    Console.WriteLine("PUBLISHED pid=" + h.HolderPid + " record=" + h.RecordPath);
                    Console.Out.Flush();
                    Console.In.ReadLine();
                }
                return 0;
            }
            if (cmd == "hold-with-job-child") {
                using (var h = DesktopLock.Acquire(prefix, "lock-driver-job-parent")) {
                    var env = CopyEnv(DesktopLock.EnvPrefix(prefix) + "_DESKTOP_HELD", h.HeldToken);
                    int cpid = h.StartProcessInJob(selfExe, "sleep-forever " + prefix, Environment.CurrentDirectory, env);
                    Console.WriteLine("READY pid=" + h.HolderPid + " child_pid=" + cpid + " job=" + h.JobName + " record=" + h.RecordPath);
                    Console.Out.Flush();
                    Console.In.ReadLine();
                }
                return 0;
            }
            if (cmd == "sleep-forever") {
                Thread.Sleep(60000);
                return 0;
            }
            if (cmd == "test-inheritance-parent") {
                string mode = args[2];
                using (var h = DesktopLock.Acquire(prefix, "lock-driver-parent")) {
                    string envKey = DesktopLock.EnvPrefix(prefix) + "_DESKTOP_HELD";
                    if (mode == "job-child") {
                        var env = CopyEnv(envKey, h.HeldToken);
                        int cpid = h.StartProcessInJob(selfExe, "child-inherit-verify " + prefix + " " + args[3], Environment.CurrentDirectory, env);
                        using (Process cp = Process.GetProcessById(cpid)) { cp.WaitForExit(10000); }
                        Console.WriteLine("PARENT_STILL_HELD");
                        Console.Out.Flush();
                        Console.In.ReadLine();
                    } else if (mode == "non-job-child") {
                        var psi = new ProcessStartInfo(selfExe, "child-inherit-verify " + prefix + " " + args[3]) {
                            UseShellExecute = false, CreateNoWindow = true
                        };
                        psi.EnvironmentVariables[envKey] = h.HeldToken;
                        psi.EnvironmentVariables[DesktopLock.EnvPrefix(prefix) + "_DESKTOP_WAIT_S"] = "0";
                        using (Process cp = Process.Start(psi)) { cp.WaitForExit(10000); }
                    } else if (mode == "reused-pid-child") {
                        // Rewrite BOTH token AND holder record to real parent PID + wrong start_ticks (startTicks + 1).
                        long forgedTicks = h.HolderStartTicks + 1;
                        string forgedToken = h.HolderPid + ":" + forgedTicks + ":" + h.LeaseId + ":" + h.LockName;
                        var forgedRec = new DesktopLock.HolderRecord {
                            Pid = h.HolderPid, StartTicks = forgedTicks, StartUtc = h.HolderStartUtc,
                            LeaseId = h.LeaseId, JobName = h.JobName, LockName = h.LockName, Label = "forged"
                        };
                        DesktopLock.WriteHolderRecordAtomic(h.RecordPath, forgedRec);
                        var env = CopyEnv(envKey, forgedToken);
                        env[DesktopLock.EnvPrefix(prefix) + "_DESKTOP_WAIT_S"] = "0";
                        int cpid = h.StartProcessInJob(selfExe, "child-inherit-verify " + prefix + " " + args[3], Environment.CurrentDirectory, env);
                        using (Process cp = Process.GetProcessById(cpid)) { cp.WaitForExit(10000); }
                    } else if (mode == "post-check-barrier") {
                        string pastFile = args[3], goFile = args[4], actedFile = args[5];
                        var env = CopyEnv(envKey, h.HeldToken);
                        int cpid = h.StartProcessInJob(selfExe,
                            "child-post-check " + prefix + " \"" + pastFile + "\" \"" + goFile + "\" \"" + actedFile + "\"",
                            Environment.CurrentDirectory, env);
                        DateTime dl = DateTime.UtcNow.AddSeconds(10);
                        while (!File.Exists(pastFile) && DateTime.UtcNow < dl) Thread.Sleep(20);
                        Console.WriteLine("CHILD_PAST_CHECK child_pid=" + cpid + " record=" + h.RecordPath);
                        Console.Out.Flush();
                        string action = Console.In.ReadLine();
                        if (action == "dispose") {
                            // Normal disposal closes/drains the desktop job before releasing the mutex!
                        }
                    }
                }
                Console.WriteLine("PARENT_DISPOSED");
                Console.Out.Flush();
                return 0;
            }
            if (cmd == "child-inherit-verify") {
                string outFile = args[2];
                try {
                    using (var ch = DesktopLock.Acquire(prefix, "child-inherit")) {
                        ch.EnsureStillHeld();
                        File.WriteAllText(outFile, "OK inherited=" + ch.Inherited + " pid=" + ch.HolderPid);
                    }
                    return 0;
                } catch (Exception ex) {
                    File.WriteAllText(outFile, "ERR " + ex.GetType().Name + ": " + ex.Message);
                    return 21;
                }
            }
            if (cmd == "child-post-check") {
                string pastFile = args[2], goFile = args[3], actedFile = args[4];
                using (var ch = DesktopLock.Acquire(prefix, "child-post-check")) {
                    ch.EnsureStillHeld();
                    File.WriteAllText(pastFile, "PAST_CHECK");
                    DateTime dl = DateTime.UtcNow.AddSeconds(10);
                    while (!File.Exists(goFile) && DateTime.UtcNow < dl) Thread.Sleep(20);
                    if (File.Exists(goFile)) {
                        File.WriteAllText(actedFile, "ACTED");
                    }
                }
                return 0;
            }
            if (cmd == "hold-lease-reader") {
                string leaseEventName = args[2];
                IntPtr he = OpenEventW(SYNCHRONIZE, false, leaseEventName);
                if (he == IntPtr.Zero) return 41;
                try {
                    Console.WriteLine("READER_OPEN");
                    Console.Out.Flush();
                    Console.In.ReadLine();
                } finally {
                    CloseHandle(he);
                }
                return 0;
            }
            return 2;
        } catch (DesktopLockBusyException ex) {
            Console.Error.WriteLine("BUSY: " + ex.Message);
            return 21;
        } catch (ArgumentException ex) {
            Console.Error.WriteLine("INVALID: " + ex.Message);
            return 22;
        }
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
        lock_cs = SCRIPTS / "lib" / "DesktopLock.cs"
        watch_cs = SCRIPTS / "lib" / "InputWatch.cs"
        app_cs = cls.bin_dir / "FixtureApp.cs"
        drv_cs = cls.bin_dir / "FixtureDriver.cs"
        lock_drv_cs = cls.bin_dir / "LockDriver.cs"
        app_cs.write_text(FIXTURE_APP_CS, encoding="utf-8")
        drv_cs.write_text(FIXTURE_DRIVER_CS, encoding="utf-8")
        lock_drv_cs.write_text(LOCK_DRIVER_CS, encoding="utf-8")
        cls.app_exe = cls.bin_dir / "FixtureApp.exe"
        cls.drv_exe = cls.bin_dir / "FixtureDriver.exe"
        cls.lock_drv_exe = cls.bin_dir / "LockDriver.exe"
        cls.watch_exe = cls.bin_dir / "InputWatch.exe"
        wpf = UIA_CLIENT.parent
        for argv in (
            [str(CSC), "/nologo", "/target:winexe", f"/out:{cls.app_exe}",
             f"/r:{wpf / 'PresentationFramework.dll'}", f"/r:{wpf / 'PresentationCore.dll'}",
             f"/r:{wpf / 'WindowsBase.dll'}", f"/r:{UIA_CLIENT}", "/r:System.Xaml.dll",
             str(guard_cs), str(app_cs)],
            [str(CSC), "/nologo", f"/out:{cls.drv_exe}",
             f"/r:{UIA_CLIENT}", f"/r:{UIA_TYPES}", "/r:System.Windows.Forms.dll",
             str(guard_cs), str(lock_cs), str(drv_cs)],
            [str(CSC), "/nologo", f"/out:{cls.lock_drv_exe}", str(lock_cs), str(lock_drv_cs)],
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
        shutil.copyfile(SCRIPTS / "capture-window.ps1", self.root / "scripts" / "capture-window.ps1")
        shutil.copyfile(SCRIPTS / "lib" / "desktop_tests.py", self.root / "scripts" / "lib" / "desktop_tests.py")
        shutil.copyfile(SCRIPTS / "lib" / "DesktopLock.cs", self.root / "scripts" / "lib" / "DesktopLock.cs")
        shutil.copyfile(SCRIPTS / "lib" / "InputWatch.cs", self.root / "scripts" / "lib" / "InputWatch.cs")
        self.write_cfg()
        self.state.mkdir(parents=True, exist_ok=True)
        # Default unlocked idle probes for test harness runs.
        (self.state / "probe-locked").write_text("0", encoding="utf-8")
        (self.state / "probe-idle").write_text("1000", encoding="utf-8")
        self._test_lock = f"conclave-dt-test-{os.getpid()}-{time.time_ns()}"

    def write_cfg(self, **overrides):
        cfg = {
            "schema_version": 1, "prefix": "demo", "window_opens": "03:00", "window_closes": "06:00",
            "idle_minutes": 15, "history_limit": 60, "log_limit": 30, "test_command": None,
            **overrides,
        }
        (self.root / ".conclave" / "desktop-tests.json").write_text(json.dumps(cfg), encoding="utf-8")

    def run_smoke(self, *args, extra_env=None, include_watcher=True):
        env = {**os.environ, "DEMO_DESKTOP_LOCK": self._test_lock, **(extra_env or {})}
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
            ("neg-focus-pid-hook", "took the foreground window"),
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
        # Late acknowledgement from a timed-out TrackPid(A) must not prematurely complete TrackPid(B).
        late_ack = run_cmd([str(self.drv_exe), "track-late-ack", "demo"])
        self.assertEqual(late_ack.returncode, 0, late_ack.stdout + late_ack.stderr)
        self.assertIn("TRACK_LATE_ACK_OK", late_ack.stdout)
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

    def _parse_kv(self, line):
        parts = line.strip().split()
        out = {}
        for tok in parts[1:]:
            if "=" in tok:
                k, v = tok.split("=", 1)
                out[k] = v
        return out

    def test_desktop_lock_contention_bounds_canonical_name_and_dacl(self):
        lock_name = f"conclave-dt-contend-{os.getpid()}-{time.time_ns()}"
        env_a = {**os.environ, "DEMO_DESKTOP_LOCK": lock_name}
        proc_a = subprocess.Popen(
            [str(self.lock_drv_exe), "hold", "demo"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, env=env_a, creationflags=NO_WINDOW,
        )
        try:
            held_line = proc_a.stdout.readline().strip()
            self.assertTrue(held_line.startswith("HELD "), f"unexpected hold line: {held_line}")
            info = self._parse_kv(held_line)
            # Unqualified override must canonicalize to Global\<name>.
            self.assertEqual(info["lock"], f"Global\\{lock_name}")
            # Process 2 waits 1s and refuses naming Process 1's exact pid and start time.
            t0 = time.monotonic()
            res_b = run_cmd(
                [str(self.lock_drv_exe), "wait-acquire", "demo"],
                env={**os.environ, "DEMO_DESKTOP_LOCK": f"Global\\{lock_name}", "DEMO_DESKTOP_WAIT_S": "1"},
            )
            elapsed = time.monotonic() - t0
            self.assertEqual(res_b.returncode, 21, res_b.stdout + res_b.stderr)
            self.assertGreaterEqual(elapsed, 0.7)
            self.assertIn(f"pid={info['pid']}", res_b.stderr)
            self.assertIn(f"started={info['utc']}", res_b.stderr)
            self.assertIn(f"ticks={info['ticks']}", res_b.stderr)
        finally:
            try:
                proc_a.stdin.write("release\n")
                proc_a.stdin.flush()
                proc_a.communicate(timeout=10)
            except Exception:
                proc_a.kill()
                proc_a.communicate()

        # Unsupported namespaces (Local\, Session\1\) refuse before any desktop access.
        for bad_ns in ("Local\\bad-lock", "Session\\1\\bad-lock", "bad lock"):
            with self.subTest(bad_ns=bad_ns):
                r = run_cmd([str(self.lock_drv_exe), "wait-acquire", "demo"],
                            env={**os.environ, "DEMO_DESKTOP_LOCK": bad_ns, "DEMO_DESKTOP_WAIT_S": "0"})
                self.assertEqual(r.returncode, 22, r.stdout + r.stderr)
                self.assertIn("INVALID:", r.stderr)

        # Wait bounds: negative, invalid, and excessive (>86400) fail closed; unset (default 120) and 0 succeed.
        for bad_wait in ("-1", "abc", "86401"):
            with self.subTest(bad_wait=bad_wait):
                r = run_cmd([str(self.lock_drv_exe), "wait-acquire", "demo"],
                            env={**os.environ, "DEMO_DESKTOP_LOCK": lock_name, "DEMO_DESKTOP_WAIT_S": bad_wait})
                self.assertEqual(r.returncode, 22, r.stdout + r.stderr)
                self.assertIn("INVALID:", r.stderr)
        clean_wait_env = {k: v for k, v in os.environ.items() if k.upper() != "DEMO_DESKTOP_WAIT_S"}
        clean_wait_env["DEMO_DESKTOP_LOCK"] = lock_name
        r_unset = run_cmd([str(self.lock_drv_exe), "wait-acquire", "demo"], env=clean_wait_env)
        self.assertEqual(r_unset.returncode, 0, r_unset.stdout + r_unset.stderr)
        r_zero = run_cmd([str(self.lock_drv_exe), "wait-acquire", "demo"],
                         env={**clean_wait_env, "DEMO_DESKTOP_WAIT_S": "0"})
        self.assertEqual(r_zero.returncode, 0, r_zero.stdout + r_zero.stderr)

        # DACL check via separate creator READ_CONTROL handle: AU has only 0x00100001 on mutex and 0x00100000 on lease event (no WRITE_DAC).
        dacl_res = run_cmd([str(self.lock_drv_exe), "check-dacl", "demo"],
                           env={**os.environ, "DEMO_DESKTOP_LOCK": f"conclave-dt-dacl-{os.getpid()}-{time.time_ns()}"})
        self.assertEqual(dacl_res.returncode, 0, dacl_res.stdout + dacl_res.stderr)
        lines = dict(ln.split("=", 1) for ln in dacl_res.stdout.strip().splitlines() if "=" in ln)
        self.assertIn("(A;;0x100001;;;AU)", lines["MUTEX_DACL"])
        self.assertNotIn("WD", lines["MUTEX_DACL"].split(";;;AU")[0].split("(")[-1])
        self.assertIn("(A;;0x100000;;;AU)", lines["LEASE_DACL"])

    def test_desktop_lock_kill_recovery_late_successor_failed_publish_and_two_reader_handoff(self):
        # 1. Synchronized kill test: Process 2 already open & waiting before Process 1 is killed acquires at once.
        lock1 = f"conclave-dt-kill-{os.getpid()}-{time.time_ns()}"
        env1 = {**os.environ, "DEMO_DESKTOP_LOCK": lock1, "DEMO_DESKTOP_WAIT_S": "15"}
        p1 = subprocess.Popen([str(self.lock_drv_exe), "hold", "demo"],
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True, env=env1, creationflags=NO_WINDOW)
        p2 = None
        try:
            held1 = self._parse_kv(p1.stdout.readline())
            p2 = subprocess.Popen([str(self.lock_drv_exe), "wait-acquire", "demo", "hold"],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  text=True, env=env1, creationflags=NO_WINDOW)
            self.assertEqual(p2.stdout.readline().strip(), "WAITING")
            time.sleep(0.25)  # Give p2 time to enter WaitForSingleObject on the mutex.
            t_kill = time.monotonic()
            p1.kill()
            p1.communicate(timeout=10)
            acq_line = p2.stdout.readline().strip()
            elapsed = time.monotonic() - t_kill
            self.assertTrue(acq_line.startswith("ACQUIRED "), f"expected ACQUIRED, got: {acq_line}")
            self.assertLess(elapsed, 4.0, f"abandoned mutex recovery took {elapsed:.2f}s")
            info2 = self._parse_kv(acq_line)
            # Read back the replacement record while p2 still holds the lock.
            rec_doc = json.loads(Path(info2["record"]).read_text(encoding="utf-8"))
            self.assertEqual(rec_doc["pid"], int(info2["pid"]))
            self.assertNotEqual(rec_doc["pid"], int(held1["pid"]))
        finally:
            if p1.poll() is None:
                p1.kill()
                p1.communicate()
            if p2 is not None:
                try:
                    p2.stdin.write("release\n")
                    p2.stdin.flush()
                    p2.communicate(timeout=10)
                except Exception:
                    p2.kill()
                    p2.communicate()

        # 2. Late-arriving successor after last handle close drains prior desktop job before acquiring.
        lock2 = f"conclave-dt-late-{os.getpid()}-{time.time_ns()}"
        env2 = {**os.environ, "DEMO_DESKTOP_LOCK": lock2, "DEMO_DESKTOP_WAIT_S": "5"}
        p_parent = subprocess.Popen([str(self.lock_drv_exe), "hold-with-job-child", "demo"],
                                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True, env=env2, creationflags=NO_WINDOW)
        ready = self._parse_kv(p_parent.stdout.readline())
        p_parent.kill()
        p_parent.communicate(timeout=10)
        # Late-arriving successor enters AFTER p_parent closed all handles.
        late = run_cmd([str(self.lock_drv_exe), "wait-acquire", "demo"], env=env2)
        self.assertEqual(late.returncode, 0, late.stdout + late.stderr)
        self.assertIn("ACQUIRED ", late.stdout)
        # Verify the prior job child is dead.
        child_pid = int(ready["child_pid"])
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        h_ch = kernel32.OpenProcess(0x1000, False, child_pid)
        if h_ch:
            ec = ctypes.c_uint(0)
            kernel32.GetExitCodeProcess(h_ch, ctypes.byref(ec))
            kernel32.CloseHandle(h_ch)
            self.assertNotEqual(ec.value, 259, "prior desktop job child must have exited before successor entered")

        # 3. Failed record publication rolls back mutex so Process 2 acquires while Process 1 stays alive.
        lock3 = f"conclave-dt-failpub-{os.getpid()}-{time.time_ns()}"
        env3 = {**os.environ, "DEMO_DESKTOP_LOCK": lock3, "DEMO_DESKTOP_WAIT_S": "1"}
        p_fail = subprocess.Popen([str(self.lock_drv_exe), "fail-publish", "demo"],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  text=True, env=env3, creationflags=NO_WINDOW)
        try:
            self.assertEqual(p_fail.stdout.readline().strip(), "FAILED_PUBLISH_OK")
            r_next = run_cmd([str(self.lock_drv_exe), "wait-acquire", "demo"], env=env3)
            self.assertEqual(r_next.returncode, 0, r_next.stdout + r_next.stderr)
            self.assertIn("ACQUIRED ", r_next.stdout)
        finally:
            try:
                p_fail.stdin.write("quit\n")
                p_fail.stdin.flush()
                p_fail.communicate(timeout=10)
            except Exception:
                p_fail.kill()
                p_fail.communicate()

        # 4. Locked-record deletion + two-reader handoff: Reader 1 holds A's lease handle AND locks A's JSON open;
        # A disposes cleanly; B acquires and pauses BEFORE publishing; Reader 2 must report 'holder identity unavailable'
        # (never attributes A) and A's inheritance token must fail.
        lock4 = f"conclave-dt-handoff-{os.getpid()}-{time.time_ns()}"
        env4 = {**os.environ, "DEMO_DESKTOP_LOCK": lock4, "DEMO_DESKTOP_WAIT_S": "0"}
        resume_file = Path(self._tmp.name) / "resume-b.txt"
        pa = subprocess.Popen([str(self.lock_drv_exe), "hold", "demo"],
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True, env=env4, creationflags=NO_WINDOW)
        reader1 = None
        pb = None
        h_rec_lock = None
        try:
            info_a = self._parse_kv(pa.stdout.readline())
            # Reader 1 opens A's lease event handle AND locks A's JSON against deletion (no FILE_SHARE_DELETE).
            reader1 = subprocess.Popen([str(self.lock_drv_exe), "hold-lease-reader", "demo", info_a["leaseEvent"]],
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       text=True, env=env4, creationflags=NO_WINDOW)
            self.assertEqual(reader1.stdout.readline().strip(), "READER_OPEN")
            h_rec_lock = kernel32.CreateFileW(info_a["record"], 0x80000000, 0x00000003, None, 3, 0x80, None)
            self.assertNotEqual(h_rec_lock, ctypes.c_void_p(-1).value)
            # A disposes cleanly while staying alive: deletion hits locked file, lease event is signaled, mutex releases!
            pa.stdin.write("release\n")
            pa.stdin.flush()
            self.assertEqual(pa.stdout.readline().strip(), "RELEASED")
            # B acquires the mutex and pauses BEFORE publishing its record over A's locked-open JSON.
            pb = subprocess.Popen([str(self.lock_drv_exe), "pause-before-publish", "demo", str(resume_file)],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  text=True, env={**env4, "DEMO_DESKTOP_WAIT_S": "5"}, creationflags=NO_WINDOW)
            self.assertEqual(pb.stdout.readline().strip(), "BEFORE_PUBLISH")
            # Reader 2 (zero-wait Acquire) runs while Reader 1 still holds A's lease handle and A's JSON is on disk.
            r2 = run_cmd([str(self.lock_drv_exe), "wait-acquire", "demo"],
                         env={**env4, "DEMO_DESKTOP_HELD": info_a["token"]})
            self.assertEqual(r2.returncode, 21, r2.stdout + r2.stderr)
            self.assertIn("holder identity unavailable", r2.stderr)
            self.assertNotIn(f"pid={info_a['pid']}", r2.stderr)
        finally:
            if h_rec_lock and h_rec_lock != ctypes.c_void_p(-1).value:
                kernel32.CloseHandle(h_rec_lock)
            resume_file.write_text("go", encoding="utf-8")
            for p in (pb, reader1, pa):
                if p is not None:
                    try:
                        if p.stdin:
                            p.stdin.write("quit\n")
                            p.stdin.flush()
                        p.communicate(timeout=10)
                    except Exception:
                        p.kill()
                        p.communicate()

    def test_desktop_lock_inheritance_reused_pid_and_child_lifetime(self):
        # 1. Job-member child inherits immediately and disposing it does NOT release parent's lock.
        lock1 = f"conclave-dt-inh-{os.getpid()}-{time.time_ns()}"
        env1 = {**os.environ, "DEMO_DESKTOP_LOCK": lock1, "DEMO_DESKTOP_WAIT_S": "0"}
        child_out = Path(self._tmp.name) / "child-ok.txt"
        p_par = subprocess.Popen([str(self.lock_drv_exe), "test-inheritance-parent", "demo", "job-child", str(child_out)],
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 text=True, env=env1, creationflags=NO_WINDOW)
        try:
            self.assertEqual(p_par.stdout.readline().strip(), "PARENT_STILL_HELD")
            self.assertIn("OK inherited=True", child_out.read_text(encoding="utf-8"))
            # Outsider is STILL blocked by parent after child disposed its inherited handle.
            out_r = run_cmd([str(self.lock_drv_exe), "wait-acquire", "demo"], env=env1)
            self.assertEqual(out_r.returncode, 21, out_r.stdout + out_r.stderr)
        finally:
            try:
                p_par.stdin.write("done\n")
                p_par.stdin.flush()
                p_par.communicate(timeout=10)
            except Exception:
                p_par.kill()
                p_par.communicate()

        # 2. Non-job child with valid token is refused.
        nonjob_out = Path(self._tmp.name) / "child-nonjob.txt"
        r_nj = run_cmd([str(self.lock_drv_exe), "test-inheritance-parent", "demo", "non-job-child", str(nonjob_out)],
                       env={**os.environ, "DEMO_DESKTOP_LOCK": f"conclave-dt-nj-{os.getpid()}-{time.time_ns()}"})
        self.assertEqual(r_nj.returncode, 0, r_nj.stdout + r_nj.stderr)
        self.assertIn("ERR DesktopLockBusyException", nonjob_out.read_text(encoding="utf-8"))

        # 3. Reused-PID descendant test (mutation-sensitive): real parent->child inside desktop job,
        # BOTH token and holder record carry real parent PID + wrong start_ticks (startTicks+1) -> MUST refuse!
        reused_out = Path(self._tmp.name) / "child-reused.txt"
        r_ru = run_cmd([str(self.lock_drv_exe), "test-inheritance-parent", "demo", "reused-pid-child", str(reused_out)],
                       env={**os.environ, "DEMO_DESKTOP_LOCK": f"conclave-dt-ru-{os.getpid()}-{time.time_ns()}"})
        self.assertEqual(r_ru.returncode, 0, r_ru.stdout + r_ru.stderr)
        self.assertIn("ERR DesktopLockBusyException", reused_out.read_text(encoding="utf-8"))

        # 4. Both owner kill AND normal owner disposal with child paused AFTER EnsureStillHeld() and BEFORE desktop action.
        for stop_kind in ("dispose", "kill"):
            with self.subTest(stop_kind=stop_kind):
                lk = f"conclave-dt-life-{stop_kind}-{os.getpid()}-{time.time_ns()}"
                env_l = {**os.environ, "DEMO_DESKTOP_LOCK": lk, "DEMO_DESKTOP_WAIT_S": "5"}
                past = Path(self._tmp.name) / f"past-{stop_kind}.txt"
                go = Path(self._tmp.name) / f"go-{stop_kind}.txt"
                acted = Path(self._tmp.name) / f"acted-{stop_kind}.txt"
                pa = subprocess.Popen(
                    [str(self.lock_drv_exe), "test-inheritance-parent", "demo", "post-check-barrier",
                     str(past), str(go), str(acted)],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, env=env_l, creationflags=NO_WINDOW,
                )
                try:
                    line = pa.stdout.readline().strip()
                    self.assertTrue(line.startswith("CHILD_PAST_CHECK "), line)
                    if stop_kind == "dispose":
                        pa.stdin.write("dispose\n")
                        pa.stdin.flush()
                        self.assertEqual(pa.stdout.readline().strip(), "PARENT_DISPOSED")
                        pa.communicate(timeout=10)
                    else:
                        pa.kill()
                        pa.communicate(timeout=10)
                    # New Owner B acquires the lock, then opens the barrier; the old child must NEVER act.
                    rb = run_cmd([str(self.lock_drv_exe), "wait-acquire", "demo"], env=env_l)
                    self.assertEqual(rb.returncode, 0, rb.stdout + rb.stderr)
                    go.write_text("go", encoding="utf-8")
                    time.sleep(0.25)
                    self.assertFalse(acted.exists(), f"old child acted after owner {stop_kind} and new owner entry")
                finally:
                    if pa.poll() is None:
                        pa.kill()
                        pa.communicate()

    def test_smoke_input_capture_window_and_live_fixture_lock_enforcement(self):
        # Use a hyphenated project prefix to prove MY_APP_DESKTOP_* env-name mapping end-to-end.
        self.write_cfg(prefix="my-app")
        lk = f"conclave-dt-smoke-{os.getpid()}-{time.time_ns()}"
        env_hold = {**os.environ, "MY_APP_DESKTOP_LOCK": lk}
        holder = subprocess.Popen([str(self.lock_drv_exe), "hold", "my-app"],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  text=True, env=env_hold, creationflags=NO_WINDOW)
        runner_called = Path(self._tmp.name) / "runner-called.txt"
        runner_py = Path(self._tmp.name) / "smoke-lock-runner.py"
        runner_py.write_text(
            "import os, pathlib, sys\n"
            f"pathlib.Path({str(runner_called)!r}).write_text(os.environ.get('MY_APP_DESKTOP_HELD', ''), encoding='utf-8')\n"
            "if '--discover' in sys.argv:\n"
            "    print('DISCOVER C1 t1')\n"
            "elif '--run-class' in sys.argv:\n"
            "    print('CASE PASS C1 t1')\n",
            encoding="utf-8",
        )
        try:
            held_info = self._parse_kv(holder.stdout.readline())
            contend_env = {"MY_APP_DESKTOP_LOCK": lk, "MY_APP_DESKTOP_WAIT_S": "0"}
            # 1. Scheduled smoke-input under contention: exit 0, skipped desktop-locked-by-other, holder in history, 0 runner starts.
            r_sched = self.run_smoke("-Scheduled", "-TestProbes", "-NowOverride", "2026-11-25T03:15:00",
                                     "-RunnerCommand", str(runner_py), extra_env=contend_env)
            self.assertEqual(r_sched.returncode, 0, r_sched.stdout + r_sched.stderr)
            self.assertIn("desktop-locked-by-other", r_sched.stdout)
            self.assertFalse(runner_called.exists())
            hist_rows = [json.loads(ln) for ln in (self.state / "input-history.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()]
            self.assertEqual(hist_rows[-1]["outcome"], "skipped")
            self.assertEqual(hist_rows[-1]["reason"], "desktop-locked-by-other")
            self.assertEqual(hist_rows[-1]["holder"]["pid"], int(held_info["pid"]))
            # 2. On-demand smoke-input under contention: exit 1, 0 runner starts.
            r_ond = self.run_smoke("-TestProbes", "-NowOverride", "2026-11-25T03:15:00",
                                   "-RunnerCommand", str(runner_py), extra_env=contend_env)
            self.assertEqual(r_ond.returncode, 1, r_ond.stdout + r_ond.stderr)
            self.assertIn("desktop-locked-by-other", r_ond.stderr)
            self.assertFalse(runner_called.exists())
            # 3. capture-window.ps1 under contention: exit 1, no output file created.
            cap_out = Path(self._tmp.name) / "cap-busy.txt"
            r_cap = run_cmd(
                [PWSH, "-NoProfile", "-NonInteractive", "-File", str(self.root / "scripts" / "capture-window.ps1"),
                 "-ProjectRoot", str(self.root), "-Python", sys.executable, "-Out", str(cap_out)],
                cwd=self.root, env={**os.environ, **contend_env},
            )
            self.assertEqual(r_cap.returncode, 1, r_cap.stdout + r_cap.stderr)
            self.assertIn("refused (busy)", r_cap.stderr)
            self.assertFalse(cap_out.exists())
            # 4. Live-desk negative fixture under contention: exit 21 with LOCK_BUSY and zero desktop calls.
            r_live = run_cmd(
                [str(self.drv_exe), "neg-focus", "my-app", str(self.app_exe)],
                env={**os.environ, "CONCLAVE_TEST_LIVE_DESK": "1", **contend_env},
            )
            self.assertEqual(r_live.returncode, 21, r_live.stdout + r_live.stderr)
            self.assertIn("LOCK_BUSY:", r_live.stderr)
        finally:
            try:
                holder.stdin.write("release\n")
                holder.stdin.flush()
                holder.communicate(timeout=10)
            except Exception:
                holder.kill()
                holder.communicate()

        # After release: capture-window.ps1 succeeds and creates -Out, and smoke-input.ps1 runs & exports MY_APP_DESKTOP_HELD!
        cap_ok = Path(self._tmp.name) / "cap-ok.txt"
        r_cap2 = run_cmd(
            [PWSH, "-NoProfile", "-NonInteractive", "-File", str(self.root / "scripts" / "capture-window.ps1"),
             "-ProjectRoot", str(self.root), "-Python", sys.executable, "-Out", str(cap_ok)],
            cwd=self.root, env={**os.environ, "MY_APP_DESKTOP_LOCK": lk, "MY_APP_DESKTOP_WAIT_S": "5"},
        )
        self.assertEqual(r_cap2.returncode, 0, r_cap2.stdout + r_cap2.stderr)
        self.assertTrue(cap_ok.exists())
        r_run = self.run_smoke("-Scheduled", "-TestProbes", "-NowOverride", "2026-11-25T03:20:00",
                               "-RunnerCommand", str(runner_py),
                               extra_env={"MY_APP_DESKTOP_LOCK": lk, "MY_APP_DESKTOP_WAIT_S": "5"})
        self.assertEqual(r_run.returncode, 0, r_run.stdout + r_run.stderr)
        self.assertTrue(runner_called.exists())
        self.assertIn(f":Global\\{lk}", runner_called.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
