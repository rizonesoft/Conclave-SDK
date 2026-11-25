// Reusable Windows desktop test guard, no-activate launcher, and continuous desk observer (D04 T04 s1).
// Compiles under both .NET Framework 4.x (csc.exe) and modern .NET (dotnet) with zero external packages.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Threading;

namespace Conclave.DesktopTests
{
    /// <summary>Marks a test method or class as permitted to send real input when run under smoke-input.ps1.</summary>
    [AttributeUsage(AttributeTargets.Class | AttributeTargets.Method, AllowMultiple = false, Inherited = true)]
    public sealed class RealInputAttribute : Attribute
    {
        public string TraitName { get { return "Input"; } }
        public string TraitValue { get { return "Real"; } }
    }

    public sealed class RealInputRefusedException : InvalidOperationException
    {
        public RealInputRefusedException(string message) : base(message) { }
    }

    /// <summary>
    /// Enforces that real input runs only when:
    /// 1) the test carries [RealInput] / [Trait("Input","Real")],
    /// 2) <PREFIX>_SMOKE_INPUT=1 is set, AND
    /// 3) the run was admitted by smoke-input.ps1 (<PREFIX>_SMOKE_ADMITTED kernel event is signaled and
    ///    <PREFIX>_SMOKE_PERSON_EVENT exists and is unsignaled).
    /// Setting <PREFIX>_SMOKE_INPUT=1 directly in an ordinary test command is refused.
    /// </summary>
    public static class SmokeInputGuard
    {
        public static string EnvPrefix(string projectPrefix)
        {
            if (string.IsNullOrWhiteSpace(projectPrefix))
                throw new ArgumentException("projectPrefix is required", "projectPrefix");
            return projectPrefix.Trim().ToUpperInvariant().Replace('-', '_');
        }

        public static string InputVariable(string projectPrefix) { return EnvPrefix(projectPrefix) + "_SMOKE_INPUT"; }
        public static string AdmittedVariable(string projectPrefix) { return EnvPrefix(projectPrefix) + "_SMOKE_ADMITTED"; }
        public static string PersonVariable(string projectPrefix) { return EnvPrefix(projectPrefix) + "_SMOKE_PERSON_EVENT"; }
        public static string TagVariable(string projectPrefix) { return EnvPrefix(projectPrefix) + "_SMOKE_TAG"; }

        public static bool OptedIn(string projectPrefix)
        {
            return Environment.GetEnvironmentVariable(InputVariable(projectPrefix)) == "1";
        }

        public static bool ShouldSkipRealInput(string projectPrefix, out string reason)
        {
            if (!OptedIn(projectPrefix))
            {
                reason = "real input: run pwsh scripts/smoke-input.ps1 (" + InputVariable(projectPrefix) + "=1)";
                return true;
            }
            reason = null;
            return false;
        }

        public static long CurrentTag(string projectPrefix)
        {
            string raw = Environment.GetEnvironmentVariable(TagVariable(projectPrefix));
            long parsed;
            if (string.IsNullOrEmpty(raw) || !long.TryParse(raw, System.Globalization.NumberStyles.HexNumber,
                    System.Globalization.CultureInfo.InvariantCulture, out parsed) || parsed == 0)
            {
                throw new RealInputRefusedException("missing or invalid per-run input tag (" + TagVariable(projectPrefix) + ")");
            }
            return parsed;
        }

        public static void Require(string projectPrefix, bool hasRealInputTrait, string what)
        {
            if (!hasRealInputTrait)
            {
                throw new RealInputRefusedException(
                    what + " is real input, which only a test marked [RealInput] / [Trait(\"Input\", \"Real\")] may send");
            }
            if (!OptedIn(projectPrefix))
            {
                throw new RealInputRefusedException(
                    what + " is real input, sent only in an opted-in run (" + InputVariable(projectPrefix) + "=1)");
            }
            string admittedName = Environment.GetEnvironmentVariable(AdmittedVariable(projectPrefix));
            if (string.IsNullOrEmpty(admittedName))
            {
                throw new RealInputRefusedException(
                    what + " was refused: no admitted watcher session (" + AdmittedVariable(projectPrefix) + " is unset); run pwsh scripts/smoke-input.ps1");
            }
            EventWaitHandle admitted;
            if (!EventWaitHandle.TryOpenExisting(admittedName, out admitted))
            {
                throw new RealInputRefusedException(
                    what + " was refused: admitted session signal (" + admittedName + ") is gone");
            }
            using (admitted)
            {
                if (!admitted.WaitOne(0))
                {
                    throw new RealInputRefusedException(
                        what + " was refused: session is no longer admitted");
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
            STARTUPINFO si = new STARTUPINFO();
            si.cb = Marshal.SizeOf(typeof(STARTUPINFO));
            si.dwFlags = STARTF_USESHOWWINDOW;
            si.wShowWindow = SW_SHOWNOACTIVATE;
            PROCESS_INFORMATION pi;
            string cmdLine = "\"" + exePath + "\"" + (string.IsNullOrEmpty(arguments) ? "" : " " + arguments);
            var cmdBuf = new System.Text.StringBuilder(cmdLine);
            if (!CreateProcessW(exePath, cmdBuf, IntPtr.Zero, IntPtr.Zero, false, 0, IntPtr.Zero,
                    string.IsNullOrEmpty(workingDirectory) ? null : workingDirectory, ref si, out pi))
            {
                throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error());
            }
            CloseHandle(pi.hThread);
            CloseHandle(pi.hProcess);
            return (int)pi.dwProcessId;
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
            string lpApplicationName, System.Text.StringBuilder lpCommandLine, IntPtr lpProcessAttributes, IntPtr lpThreadAttributes,
            bool bInheritHandles, uint dwCreationFlags, IntPtr lpEnvironment, string lpCurrentDirectory,
            ref STARTUPINFO lpStartupInfo, out PROCESS_INFORMATION lpProcessInformation);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool CloseHandle(IntPtr hObject);
    }

    /// <summary>
    /// Continuously observes foreground ownership, pointer movement, and keyboard/mouse input during a default
    /// UI Automation test so transient focus steals, pointer move-and-restore, or synthetic keystrokes are caught.
    /// </summary>
    public sealed class DeskObserver : IDisposable
    {
        private const int WH_KEYBOARD_LL = 13;
        private const int WH_MOUSE_LL = 14;
        private const uint WM_QUIT = 0x0012;
        private readonly HashSet<int> _ownedPids = new HashSet<int>();
        private readonly List<string> _violations = new List<string>();
        private readonly object _gate = new object();
        private readonly ManualResetEventSlim _ready = new ManualResetEventSlim(false);
        private readonly ManualResetEventSlim _stop = new ManualResetEventSlim(false);
        private POINT _startCursor;
        private bool _hasCursor;
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
                throw new InvalidOperationException("DeskObserver hooks failed to start");
            _pollThread = new Thread(PollLoop) { IsBackground = true, Name = "DeskObserver-Poll" };
            _pollThread.Start();
        }

        public bool HasDesktopCursor { get { return _hasCursor; } }

        public void TrackPid(int pid)
        {
            lock (_gate) { _ownedPids.Add(pid); }
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

        private void CheckNow()
        {
            IntPtr fg = GetForegroundWindow();
            if (fg != IntPtr.Zero)
            {
                uint pid;
                GetWindowThreadProcessId(fg, out pid);
                ObserveForegroundPid((int)pid);
            }
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
            IntPtr mod = GetModuleHandle(null);
            IntPtr hKb = SetWindowsHookEx(WH_KEYBOARD_LL, kb, mod, 0);
            IntPtr hMs = SetWindowsHookEx(WH_MOUSE_LL, ms, mod, 0);
            _ready.Set();
            try
            {
                MSG msg;
                while (GetMessage(out msg, IntPtr.Zero, 0, 0) > 0) DispatchMessage(ref msg);
            }
            finally
            {
                if (hKb != IntPtr.Zero) UnhookWindowsHookEx(hKb);
                if (hMs != IntPtr.Zero) UnhookWindowsHookEx(hMs);
                GC.KeepAlive(kb);
                GC.KeepAlive(ms);
            }
        }

        public void VerifyClean(string testName)
        {
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
        }

        private delegate IntPtr HookProc(int nCode, IntPtr wParam, IntPtr lParam);

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
        [DllImport("user32.dll")] private static extern bool UnhookWindowsHookEx(IntPtr hhk);
        [DllImport("user32.dll")] private static extern IntPtr CallNextHookEx(IntPtr hhk, int nCode, IntPtr wParam, IntPtr lParam);
        [DllImport("user32.dll")] private static extern int GetMessage(out MSG lpMsg, IntPtr hWnd, uint min, uint max);
        [DllImport("user32.dll")] private static extern IntPtr DispatchMessage(ref MSG lpMsg);
        [DllImport("user32.dll")] private static extern bool PostThreadMessage(uint idThread, uint msg, IntPtr wParam, IntPtr lParam);
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode)] private static extern IntPtr GetModuleHandle(string lpModuleName);
        [DllImport("kernel32.dll")] private static extern uint GetCurrentThreadId();
    }
}
