// Guard, launch-show, and continuous desk-observation helpers for Windows desktop UI tests (D04 T04 s1).
// Compiles with .NET Framework 4.x csc.exe or modern .NET (zero external dependencies).
// Parameterized by project prefix so every consuming repository keeps its own environment variable names.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;

namespace Conclave.DesktopTests
{
    /// <summary>Marks a test class or method as real-input (opt-in only, never run by default).</summary>
    [AttributeUsage(AttributeTargets.Class | AttributeTargets.Method, AllowMultiple = false)]
    public sealed class RealInputAttribute : Attribute
    {
        public string Reason { get; private set; }
        public RealInputAttribute(string reason = "sends real keyboard or mouse input")
        {
            Reason = reason;
        }
    }

    public sealed class RealInputRefusedException : InvalidOperationException
    {
        public RealInputRefusedException(string message) : base(message) { }
    }

    /// <summary>
    /// Enforces both the trait gate and an admitted, actively watched runner session before any real-input
    /// helper may move the pointer, press a key, or take the foreground.
    /// </summary>
    public static class SmokeInputGuard
    {
        public static string EnvPrefix(string projectPrefix)
        {
            if (string.IsNullOrWhiteSpace(projectPrefix))
                throw new ArgumentException("projectPrefix is required", "projectPrefix");
            return projectPrefix.Trim().ToUpperInvariant().Replace('-', '_');
        }

        public static string OptInVariable(string projectPrefix) { return EnvPrefix(projectPrefix) + "_SMOKE_INPUT"; }
        public static string AdmittedVariable(string projectPrefix) { return EnvPrefix(projectPrefix) + "_SMOKE_ADMITTED"; }
        public static string PersonVariable(string projectPrefix) { return EnvPrefix(projectPrefix) + "_SMOKE_PERSON_EVENT"; }
        public static string AliveVariable(string projectPrefix) { return EnvPrefix(projectPrefix) + "_SMOKE_WATCHER_ALIVE"; }
        public static string TagVariable(string projectPrefix) { return EnvPrefix(projectPrefix) + "_SMOKE_TAG"; }

        /// <summary>Returns null when opted in, or a skip reason for default runs.</summary>
        public static string SkipReasonOrNull(string projectPrefix)
        {
            string varName = OptInVariable(projectPrefix);
            if (string.Equals(Environment.GetEnvironmentVariable(varName), "1", StringComparison.Ordinal))
                return null;
            return "real-input test: set " + varName + "=1 via scripts/smoke-input.ps1 to run";
        }

        public static uint CurrentTag(string projectPrefix)
        {
            string raw = Environment.GetEnvironmentVariable(TagVariable(projectPrefix));
            uint tag;
            if (string.IsNullOrEmpty(raw) || !uint.TryParse(raw, NumberStyles.HexNumber, CultureInfo.InvariantCulture, out tag) || tag == 0)
            {
                throw new RealInputRefusedException(
                    "real-input tag missing or invalid (" + TagVariable(projectPrefix) + ")");
            }
            return tag;
        }

        /// <summary>
        /// Refuses unless: (1) caller carries [RealInput], (2) opt-in variable is 1, (3) runner's
        /// admitted kernel event exists and is signaled, (4) watcher's own kernel alive event exists
        /// and is signaled, (5) watcher's person event exists and is unsignaled, and (6) per-run tag is valid.
        /// </summary>
        public static void Require(string projectPrefix, bool hasRealInputTrait, string what)
        {
            if (!hasRealInputTrait)
            {
                throw new RealInputRefusedException(
                    what + " was called from a test without [RealInput]; default tests must not touch the desk");
            }
            string optIn = OptInVariable(projectPrefix);
            if (!string.Equals(Environment.GetEnvironmentVariable(optIn), "1", StringComparison.Ordinal))
            {
                throw new RealInputRefusedException(
                    what + " was refused: " + optIn + " is not 1");
            }
            string admittedName = Environment.GetEnvironmentVariable(AdmittedVariable(projectPrefix));
            if (string.IsNullOrEmpty(admittedName))
            {
                throw new RealInputRefusedException(
                    what + " was refused: no admitted watcher session (" + AdmittedVariable(projectPrefix) + " is unset; run via scripts/smoke-input.ps1)");
            }
            EventWaitHandle admitted;
            if (!EventWaitHandle.TryOpenExisting(admittedName, out admitted))
            {
                throw new RealInputRefusedException(
                    what + " was refused: admitted session signal (" + admittedName + ") is not live");
            }
            using (admitted)
            {
                if (!admitted.WaitOne(0))
                {
                    throw new RealInputRefusedException(
                        what + " was refused: session is no longer admitted");
                }
            }
            string aliveName = Environment.GetEnvironmentVariable(AliveVariable(projectPrefix));
            if (string.IsNullOrEmpty(aliveName))
            {
                throw new RealInputRefusedException(
                    what + " was refused: no watcher-liveness signal (" + AliveVariable(projectPrefix) + " is unset)");
            }
            EventWaitHandle alive;
            if (!EventWaitHandle.TryOpenExisting(aliveName, out alive))
            {
                throw new RealInputRefusedException(
                    what + " was refused: input watcher (" + aliveName + ") is no longer alive");
            }
            using (alive)
            {
                if (!alive.WaitOne(0))
                {
                    throw new RealInputRefusedException(
                        what + " was refused: input watcher stopped");
                }
            }
            string personName = Environment.GetEnvironmentVariable(PersonVariable(projectPrefix));
            if (string.IsNullOrEmpty(personName))
            {
                throw new RealInputRefusedException(
                    what + " was refused: no active input watcher (" + PersonVariable(projectPrefix) + " is unset)");
            }
            EventWaitHandle person;
            if (!EventWaitHandle.TryOpenExisting(personName, out person))
            {
                throw new RealInputRefusedException(
                    what + " was refused: input watcher signal (" + personName + ") is gone");
            }
            using (person)
            {
                if (person.WaitOne(0))
                {
                    throw new RealInputRefusedException(
                        what + " was refused: a person or untagged input arrived at the desk");
                }
            }
            CurrentTag(projectPrefix);
        }
    }

    /// <summary>
    /// Reads STARTUPINFO.wShowWindow (nCmdShow) so apps started with SW_SHOWNOACTIVATE / SW_SHOWNA /
    /// SW_SHOWMINNOACTIVE leave the operator's window in front, and starts child processes with SW_SHOWNOACTIVATE.
    /// </summary>
    public static class LaunchShow
    {
        public const int STARTF_USESHOWWINDOW = 0x1;
        public const short SW_SHOWNOACTIVATE = 4;
        public const short SW_SHOWMINNOACTIVE = 7;
        public const short SW_SHOWNA = 8;
        private const uint CREATE_SUSPENDED = 0x4;

        public static bool Activates(int flags, short show)
        {
            if ((flags & STARTF_USESHOWWINDOW) == 0) return true;
            return show != SW_SHOWNOACTIVATE && show != SW_SHOWNA && show != SW_SHOWMINNOACTIVE;
        }

        public static bool FirstWindowActivates()
        {
            STARTUPINFO info = new STARTUPINFO();
            info.cb = Marshal.SizeOf(typeof(STARTUPINFO));
            GetStartupInfoW(ref info);
            return Activates(info.dwFlags, info.wShowWindow);
        }

        public static int StartNoActivate(string exePath, string arguments, string workingDirectory)
        {
            return StartNoActivateTracked(exePath, arguments, workingDirectory, null);
        }

        /// <summary>
        /// Starts a child with SW_SHOWNOACTIVATE in a suspended state, registers its PID via onPidBeforeResume
        /// before its first instruction executes, and then resumes the primary thread.
        /// </summary>
        public static int StartNoActivateTracked(
            string exePath, string arguments, string workingDirectory, Action<int> onPidBeforeResume)
        {
            STARTUPINFO si = new STARTUPINFO();
            si.cb = Marshal.SizeOf(typeof(STARTUPINFO));
            si.dwFlags = STARTF_USESHOWWINDOW;
            si.wShowWindow = SW_SHOWNOACTIVATE;
            PROCESS_INFORMATION pi;
            string cmdLine = "\"" + exePath + "\"" + (string.IsNullOrEmpty(arguments) ? "" : " " + arguments);
            var cmdBuf = new StringBuilder(cmdLine);
            uint flags = onPidBeforeResume != null ? CREATE_SUSPENDED : 0u;
            if (!CreateProcessW(exePath, cmdBuf, IntPtr.Zero, IntPtr.Zero, false, flags, IntPtr.Zero,
                    string.IsNullOrEmpty(workingDirectory) ? null : workingDirectory, ref si, out pi))
            {
                throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());
            }
            try
            {
                if (onPidBeforeResume != null)
                {
                    onPidBeforeResume((int)pi.dwProcessId);
                    if (ResumeThread(pi.hThread) == unchecked((uint)-1))
                    {
                        throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());
                    }
                }
                return (int)pi.dwProcessId;
            }
            catch
            {
                TerminateProcess(pi.hProcess, 1);
                throw;
            }
            finally
            {
                CloseHandle(pi.hThread);
                CloseHandle(pi.hProcess);
            }
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct STARTUPINFO
        {
            public int cb;
            public IntPtr lpReserved;
            public IntPtr lpDesktop;
            public IntPtr lpTitle;
            public int dwX, dwY, dwXSize, dwYSize, dwXCountChars, dwYCountChars, dwFillAttribute, dwFlags;
            public short wShowWindow, cbReserved2;
            public IntPtr lpReserved2, hStdInput, hStdOutput, hStdError;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct PROCESS_INFORMATION
        {
            public IntPtr hProcess, hThread;
            public uint dwProcessId, dwThreadId;
        }

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode)]
        private static extern void GetStartupInfoW(ref STARTUPINFO info);

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern bool CreateProcessW(
            string lpApplicationName, StringBuilder lpCommandLine, IntPtr lpProcessAttributes, IntPtr lpThreadAttributes,
            bool bInheritHandles, uint dwCreationFlags, IntPtr lpEnvironment, string lpCurrentDirectory,
            ref STARTUPINFO lpStartupInfo, out PROCESS_INFORMATION lpProcessInformation);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern uint ResumeThread(IntPtr hThread);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool TerminateProcess(IntPtr hProcess, uint uExitCode);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool CloseHandle(IntPtr hObject);
    }

    /// <summary>
    /// Continuously observes foreground ownership (via SetWinEventHook + polling), pointer movement, and
    /// low-level keyboard/mouse hooks during a default UI Automation test. Fails closed if hooks fail to install.
    /// </summary>
    public sealed class DeskObserver : IDisposable
    {
        private const int WH_KEYBOARD_LL = 13;
        private const int WH_MOUSE_LL = 14;
        private const uint EVENT_SYSTEM_FOREGROUND = 0x0003;
        private const uint WINEVENT_OUTOFCONTEXT = 0x0000;
        private const uint WM_QUIT = 0x0012;
        private const uint WM_FLUSH = 0x0401;
        private readonly HashSet<int> _ownedPids = new HashSet<int>();
        private readonly List<string> _violations = new List<string>();
        private readonly object _gate = new object();
        private readonly ManualResetEventSlim _ready = new ManualResetEventSlim(false);
        private readonly ManualResetEventSlim _stop = new ManualResetEventSlim(false);
        private readonly ManualResetEventSlim _flushed = new ManualResetEventSlim(false);
        private POINT _startCursor;
        private bool _hasCursor;
        private string _hookError;
        private Thread _hookThread;
        private Thread _pollThread;
        private uint _hookThreadId;
        private bool _disposed;

        public DeskObserver(IEnumerable<int> ownedPids)
        {
            foreach (int pid in ownedPids) _ownedPids.Add(pid);
            _hasCursor = GetCursorPos(out _startCursor);
            _hookThread = new Thread(RunHooks) { IsBackground = true, Name = "DeskObserver-Hooks" };
            _hookThread.Start();
            if (!_ready.Wait(5000))
                throw new InvalidOperationException("DeskObserver hooks failed to start within timeout");
            if (!string.IsNullOrEmpty(_hookError))
            {
                Dispose();
                throw new InvalidOperationException("DeskObserver failed closed: " + _hookError);
            }
            _pollThread = new Thread(PollLoop) { IsBackground = true, Name = "DeskObserver-Poll" };
            _pollThread.Start();
        }

        public bool HasDesktopCursor { get { return _hasCursor; } }

        public void TrackPid(int pid)
        {
            lock (_gate) { _ownedPids.Add(pid); }
        }

        public int LaunchNoActivate(string exePath, string arguments, string workingDirectory)
        {
            return LaunchShow.StartNoActivateTracked(exePath, arguments, workingDirectory, TrackPid);
        }

        private void Record(string violation)
        {
            lock (_gate)
            {
                if (_violations.Count < 16) _violations.Add(violation);
            }
        }

        public void ObserveCursor(int x, int y)
        {
            if (!_hasCursor)
            {
                _startCursor = new POINT { X = x, Y = y };
                _hasCursor = true;
                return;
            }
            if (x != _startCursor.X || y != _startCursor.Y)
            {
                Record("pointer moved from (" + _startCursor.X + "," + _startCursor.Y + ") to (" + x + "," + y + ")");
            }
        }

        public void ObserveInjectedKey(uint vkCode, uint flags)
        {
            if ((flags & 0x10) != 0) Record("injected keyboard input vk=" + vkCode);
        }

        public void ObserveInjectedMouse(long msg, uint flags)
        {
            if ((flags & 0x01) != 0) Record("injected mouse input msg=0x" + msg.ToString("X"));
        }

        public void ObserveForegroundPid(int pid)
        {
            bool ours;
            lock (_gate) { ours = _ownedPids.Contains(pid); }
            if (ours) Record("owned process " + pid + " took the foreground window");
        }

        public void ObserveForegroundHandle(IntPtr hwnd)
        {
            if (hwnd == IntPtr.Zero) return;
            uint pid;
            GetWindowThreadProcessId(hwnd, out pid);
            ObserveForegroundPid((int)pid);
        }

        private void CheckNow()
        {
            ObserveForegroundHandle(GetForegroundWindow());
            POINT now;
            if (GetCursorPos(out now))
            {
                ObserveCursor(now.X, now.Y);
            }
        }

        private void PollLoop()
        {
            while (!_stop.IsSet)
            {
                CheckNow();
                Thread.Sleep(5);
            }
        }

        private void RunHooks()
        {
            _hookThreadId = GetCurrentThreadId();
            HookProc kb = (code, wParam, lParam) =>
            {
                if (code >= 0)
                {
                    KBDLLHOOKSTRUCT st = (KBDLLHOOKSTRUCT)Marshal.PtrToStructure(lParam, typeof(KBDLLHOOKSTRUCT));
                    ObserveInjectedKey(st.vkCode, st.flags);
                }
                return CallNextHookEx(IntPtr.Zero, code, wParam, lParam);
            };
            HookProc ms = (code, wParam, lParam) =>
            {
                if (code >= 0)
                {
                    MSLLHOOKSTRUCT st = (MSLLHOOKSTRUCT)Marshal.PtrToStructure(lParam, typeof(MSLLHOOKSTRUCT));
                    ObserveInjectedMouse(wParam.ToInt64(), st.flags);
                }
                return CallNextHookEx(IntPtr.Zero, code, wParam, lParam);
            };
            WinEventDelegate fgEv = (hWinEventHook, eventType, hwnd, idObject, idChild, dwEventThread, dwmsEventTime) =>
            {
                ObserveForegroundHandle(hwnd);
            };
            IntPtr mod = GetModuleHandle(null);
            IntPtr hKb = SetWindowsHookEx(WH_KEYBOARD_LL, kb, mod, 0);
            IntPtr hMs = SetWindowsHookEx(WH_MOUSE_LL, ms, mod, 0);
            IntPtr hFg = SetWinEventHook(EVENT_SYSTEM_FOREGROUND, EVENT_SYSTEM_FOREGROUND, IntPtr.Zero, fgEv, 0, 0, WINEVENT_OUTOFCONTEXT);
            if (hKb == IntPtr.Zero || hMs == IntPtr.Zero || hFg == IntPtr.Zero)
            {
                _hookError = "hook installation failed (kb=" + hKb + ", ms=" + hMs + ", fg=" + hFg + ", err=" + Marshal.GetLastWin32Error() + ")";
                if (hKb != IntPtr.Zero) UnhookWindowsHookEx(hKb);
                if (hMs != IntPtr.Zero) UnhookWindowsHookEx(hMs);
                if (hFg != IntPtr.Zero) UnhookWinEvent(hFg);
                _ready.Set();
                return;
            }
            _ready.Set();
            try
            {
                MSG msg;
                while (GetMessage(out msg, IntPtr.Zero, 0, 0) > 0)
                {
                    if (msg.message == WM_FLUSH) _flushed.Set();
                    else DispatchMessage(ref msg);
                }
            }
            finally
            {
                _flushed.Set();
                UnhookWindowsHookEx(hKb);
                UnhookWindowsHookEx(hMs);
                UnhookWinEvent(hFg);
                GC.KeepAlive(kb);
                GC.KeepAlive(ms);
                GC.KeepAlive(fgEv);
            }
        }

        public void VerifyClean(string testName)
        {
            if (_hookThreadId != 0 && !_disposed)
            {
                _flushed.Reset();
                if (PostThreadMessage(_hookThreadId, WM_FLUSH, IntPtr.Zero, IntPtr.Zero))
                {
                    _flushed.Wait(1000);
                }
            }
            CheckNow();
            List<string> found;
            lock (_gate) { found = new List<string>(_violations); }
            if (found.Count > 0)
            {
                throw new RealInputRefusedException(
                    testName + " touched the operator's desk during a default test: " + string.Join("; ", found));
            }
        }

        public void Dispose()
        {
            if (_disposed) return;
            _disposed = true;
            _stop.Set();
            if (_hookThreadId != 0) PostThreadMessage(_hookThreadId, WM_QUIT, IntPtr.Zero, IntPtr.Zero);
            if (_pollThread != null) _pollThread.Join(2000);
            if (_hookThread != null) _hookThread.Join(2000);
            _ready.Dispose();
            _stop.Dispose();
            _flushed.Dispose();
        }

        private delegate IntPtr HookProc(int nCode, IntPtr wParam, IntPtr lParam);
        private delegate void WinEventDelegate(IntPtr hWinEventHook, uint eventType, IntPtr hwnd, int idObject, int idChild, uint dwEventThread, uint dwmsEventTime);

        [StructLayout(LayoutKind.Sequential)]
        private struct POINT { public int X; public int Y; }

        [StructLayout(LayoutKind.Sequential)]
        private struct MSG { public IntPtr hwnd; public uint message; public IntPtr wParam; public IntPtr lParam; public uint time; public POINT pt; }

        [StructLayout(LayoutKind.Sequential)]
        private struct KBDLLHOOKSTRUCT { public uint vkCode, scanCode, flags, time; public IntPtr extra; }

        [StructLayout(LayoutKind.Sequential)]
        private struct MSLLHOOKSTRUCT { public POINT pt; public uint mouseData, flags, time; public IntPtr extra; }

        [DllImport("user32.dll")] private static extern IntPtr GetForegroundWindow();
        [DllImport("user32.dll")] private static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint pid);
        [DllImport("user32.dll")] private static extern bool GetCursorPos(out POINT pt);
        [DllImport("user32.dll", SetLastError = true)] private static extern IntPtr SetWindowsHookEx(int idHook, HookProc lpfn, IntPtr hMod, uint dwThreadId);
        [DllImport("user32.dll", SetLastError = true)] private static extern bool UnhookWindowsHookEx(IntPtr hhk);
        [DllImport("user32.dll")] private static extern IntPtr CallNextHookEx(IntPtr hhk, int nCode, IntPtr wParam, IntPtr lParam);
        [DllImport("user32.dll", SetLastError = true)] private static extern IntPtr SetWinEventHook(uint eventMin, uint eventMax, IntPtr hmodWinEventProc, WinEventDelegate lpfnWinEventProc, uint idProcess, uint idThread, uint dwFlags);
        [DllImport("user32.dll")] private static extern bool UnhookWinEvent(IntPtr hWinEventHook);
        [DllImport("user32.dll")] private static extern int GetMessage(out MSG lpMsg, IntPtr hWnd, uint min, uint max);
        [DllImport("user32.dll")] private static extern IntPtr DispatchMessage(ref MSG lpMsg);
        [DllImport("user32.dll")] private static extern bool PostThreadMessage(uint idThread, uint msg, IntPtr wParam, IntPtr lParam);
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode)] private static extern IntPtr GetModuleHandle(string lpModuleName);
        [DllImport("kernel32.dll")] private static extern uint GetCurrentThreadId();
    }
}
