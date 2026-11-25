// Low-level keyboard and mouse hook watcher for real-input desktop smoke runs (D04 T04 s1).
// Compiles cleanly with .NET Framework 4.x csc.exe (zero external dependencies).
// Accepts only injected events whose dwExtraInfo matches this run's fresh per-run tag.
// During ReleaseHeld(), accepts a per-run derived release tag strictly for key-up/button-up events
// while releasing keys/buttons via Win32 SendInput. Owns its own kernel alive EventWaitHandle so
// watcher crash or exit is instantaneously visible to SmokeInputGuard.Require.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;

namespace Conclave.DesktopTests
{
    public static class InputWatchProgram
    {
        private const int WH_KEYBOARD_LL = 13;
        private const int WH_MOUSE_LL = 14;
        private const uint LLKHF_INJECTED = 0x10;
        private const uint LLMHF_INJECTED = 0x01;
        private const uint WM_QUIT = 0x0012;
        private const uint WM_KEYDOWN = 0x0100, WM_KEYUP = 0x0101, WM_SYSKEYDOWN = 0x0104, WM_SYSKEYUP = 0x0105;
        private const uint WM_LBUTTONDOWN = 0x0201, WM_LBUTTONUP = 0x0202, WM_RBUTTONDOWN = 0x0204, WM_RBUTTONUP = 0x0205;
        private const uint WM_MBUTTONDOWN = 0x0207, WM_MBUTTONUP = 0x0208;
        private const uint INPUT_MOUSE = 0, INPUT_KEYBOARD = 1;
        private const uint KEYEVENTF_KEYUP = 0x0002;
        private const uint MOUSEEVENTF_LEFTUP = 0x0004, MOUSEEVENTF_RIGHTUP = 0x0010, MOUSEEVENTF_MIDDLEUP = 0x0040;

        private static long _smokeTag;
        private static long _releaseTag;
        private static int _releasing;
        private static string _recordFile = "";
        private static DateTime _latestPerson = DateTime.MinValue;
        private static bool _guard;
        private static bool _personCame;
        private static EventWaitHandle _personEvent;
        private static EventWaitHandle _aliveEvent;
        private static readonly object Gate = new object();
        private static readonly HashSet<int> PersonHeld = new HashSet<int>();
        private static readonly HashSet<int> SmokeHeld = new HashSet<int>();
        private static readonly AutoResetEvent Wake = new AutoResetEvent(false);

        private static HookProc _keysProc;
        private static HookProc _mouseProc;

        public static int Main(string[] args)
        {
            if (args.Length < 2)
            {
                Console.Error.WriteLine("usage: InputWatch.exe <recordFile> <hexTag> [personEvent] [guard:0|1] [aliveEvent]");
                return 2;
            }
            _recordFile = args[0];
            if (!long.TryParse(args[1], NumberStyles.HexNumber, CultureInfo.InvariantCulture, out _smokeTag) || _smokeTag == 0)
            {
                Console.Error.WriteLine("input-watch: invalid hex tag");
                return 2;
            }
            _releaseTag = (_smokeTag ^ 0x5A5A5A5AL) & 0x7FFFFFFFL;
            if (_releaseTag == 0 || _releaseTag == _smokeTag) _releaseTag = (_smokeTag ^ 0x3C3C3C3CL) & 0x7FFFFFFFL;
            if (args.Length >= 3 && !string.IsNullOrEmpty(args[2]))
            {
                _personEvent = new EventWaitHandle(false, EventResetMode.ManualReset, args[2]);
            }
            _guard = args.Length >= 4 && args[3] == "1";
            if (args.Length >= 5 && !string.IsNullOrEmpty(args[4]))
            {
                _aliveEvent = new EventWaitHandle(true, EventResetMode.ManualReset, args[4]);
            }

            uint threadId = GetCurrentThreadId();
            WriteRecord(null, "");

            _keysProc = (code, wParam, lParam) =>
            {
                if (code >= 0)
                {
                    KBDLLHOOKSTRUCT st = (KBDLLHOOKSTRUCT)Marshal.PtrToStructure(lParam, typeof(KBDLLHOOKSTRUCT));
                    uint msg = (uint)wParam.ToInt64();
                    bool down = msg == WM_KEYDOWN || msg == WM_SYSKEYDOWN;
                    bool up = msg == WM_KEYUP || msg == WM_SYSKEYUP;
                    bool injected = (st.flags & LLKHF_INJECTED) != 0;
                    bool smoke = IsSmokeEvent(injected, st.extra.ToInt64(), up);
                    if (ProcessEvent(smoke, (int)st.vkCode, down, up))
                    {
                        return (IntPtr)1;
                    }
                }
                return CallNextHookEx(IntPtr.Zero, code, wParam, lParam);
            };

            _mouseProc = (code, wParam, lParam) =>
            {
                if (code >= 0)
                {
                    MSLLHOOKSTRUCT st = (MSLLHOOKSTRUCT)Marshal.PtrToStructure(lParam, typeof(MSLLHOOKSTRUCT));
                    uint msg = (uint)wParam.ToInt64();
                    int btn = msg == WM_LBUTTONDOWN || msg == WM_LBUTTONUP ? 1
                        : msg == WM_RBUTTONDOWN || msg == WM_RBUTTONUP ? 2
                        : msg == WM_MBUTTONDOWN || msg == WM_MBUTTONUP ? 4 : 0;
                    bool down = msg == WM_LBUTTONDOWN || msg == WM_RBUTTONDOWN || msg == WM_MBUTTONDOWN;
                    bool up = msg == WM_LBUTTONUP || msg == WM_RBUTTONUP || msg == WM_MBUTTONUP;
                    bool injected = (st.flags & LLMHF_INJECTED) != 0;
                    bool smoke = IsSmokeEvent(injected, st.extra.ToInt64(), up);
                    if (ProcessEvent(smoke, btn, down, up))
                    {
                        return (IntPtr)1;
                    }
                }
                return CallNextHookEx(IntPtr.Zero, code, wParam, lParam);
            };

            IntPtr mod = GetModuleHandle(null);
            IntPtr hKeys = SetWindowsHookEx(WH_KEYBOARD_LL, _keysProc, mod, 0);
            IntPtr hMouse = SetWindowsHookEx(WH_MOUSE_LL, _mouseProc, mod, 0);
            if (hKeys == IntPtr.Zero || hMouse == IntPtr.Zero)
            {
                if (hKeys != IntPtr.Zero) UnhookWindowsHookEx(hKeys);
                if (hMouse != IntPtr.Zero) UnhookWindowsHookEx(hMouse);
                if (_aliveEvent != null) { _aliveEvent.Reset(); _aliveEvent.Dispose(); }
                Console.Error.WriteLine("input-watch: failed to install hooks (error " + Marshal.GetLastWin32Error() + ")");
                return 70;
            }

            new Thread(WriterLoop) { IsBackground = true, Name = "input-watch-writer" }.Start();
            new Thread(() =>
            {
                string line;
                while ((line = Console.In.ReadLine()) != null)
                {
                    string cmd = line.Trim();
                    if (cmd == "person")
                    {
                        ProcessEvent(false, 0, false, false);
                    }
                    else if (cmd == "foreign-tag")
                    {
                        long foreignTag = _smokeTag ^ 0x55AA;
                        ProcessEvent(IsSmokeEvent(true, foreignTag, false), 0, false, false);
                    }
                    else if (cmd == "release-tag-when-idle")
                    {
                        // Fixed/release tag sent as ordinary input while not releasing must trigger personEvent.
                        ProcessEvent(IsSmokeEvent(true, _releaseTag, false), 0, false, false);
                    }
                    else if (cmd == "smoke-tag")
                    {
                        ProcessEvent(IsSmokeEvent(true, _smokeTag, false), 0, false, false);
                    }
                    else if (cmd.StartsWith("hold ", StringComparison.Ordinal))
                    {
                        int vk;
                        if (int.TryParse(cmd.Substring(5), out vk) && vk > 0)
                        {
                            ProcessEvent(true, vk, true, false);
                        }
                    }
                    else if (cmd == "release")
                    {
                        string report = ReleaseHeld();
                        Console.Out.WriteLine("released " + report);
                        Console.Out.Flush();
                    }
                    else if (cmd == "quit")
                    {
                        PostThreadMessage(threadId, WM_QUIT, IntPtr.Zero, IntPtr.Zero);
                        return;
                    }
                }
                // Parent closed stdin or terminated: release any held inputs and exit promptly.
                ReleaseHeld();
                PostThreadMessage(threadId, WM_QUIT, IntPtr.Zero, IntPtr.Zero);
            }) { IsBackground = true, Name = "input-watch-stdin" }.Start();

            using (Timer maxLife = new Timer(_ => PostThreadMessage(threadId, WM_QUIT, IntPtr.Zero, IntPtr.Zero),
                null, TimeSpan.FromHours(4), Timeout.InfiniteTimeSpan))
            {
                Console.Out.WriteLine("watching");
                Console.Out.Flush();
                try
                {
                    MSG msg;
                    while (GetMessage(out msg, IntPtr.Zero, 0, 0) > 0) DispatchMessage(ref msg);
                }
                finally
                {
                    if (_aliveEvent != null) { _aliveEvent.Reset(); _aliveEvent.Dispose(); }
                    UnhookWindowsHookEx(hKeys);
                    UnhookWindowsHookEx(hMouse);
                    GC.KeepAlive(maxLife);
                }
            }
            return 0;
        }

        private static bool IsSmokeEvent(bool injected, long extra, bool isUp)
        {
            if (!injected) return false;
            if (extra == _smokeTag) return true;
            if (isUp && Volatile.Read(ref _releasing) == 1 && extra == _releaseTag) return true;
            return false;
        }

        private static bool ProcessEvent(bool smoke, int key, bool down, bool up)
        {
            lock (Gate)
            {
                if (smoke && up && key != 0 && !SmokeHeld.Contains(key)) return true;
                if (smoke && _guard && _personCame && !(up && key != 0 && SmokeHeld.Contains(key))) return true;
                bool changed = false;
                if (!smoke)
                {
                    _latestPerson = DateTime.UtcNow;
                    _personCame = true;
                    changed = true;
                    if (_personEvent != null) _personEvent.Set();
                }
                if (key != 0 && !smoke)
                {
                    if (down) PersonHeld.Add(key);
                    if (up) PersonHeld.Remove(key);
                }
                if (key != 0)
                {
                    if (down && smoke) changed |= !PersonHeld.Contains(key) && SmokeHeld.Add(key);
                    else if (up || down) changed |= SmokeHeld.Remove(key);
                }
                if (changed) Wake.Set();
                return false;
            }
        }

        private static string ReleaseHeld()
        {
            List<int> copy;
            lock (Gate)
            {
                copy = new List<int>(SmokeHeld);
                SmokeHeld.Clear();
            }
            if (copy.Count == 0) return "";
            var results = new List<string>();
            Volatile.Write(ref _releasing, 1);
            try
            {
                foreach (int key in copy)
                {
                    INPUT inp = new INPUT();
                    if (key == 1 || key == 2 || key == 4)
                    {
                        inp.type = INPUT_MOUSE;
                        inp.u.mi.dwFlags = key == 1 ? MOUSEEVENTF_LEFTUP : key == 2 ? MOUSEEVENTF_RIGHTUP : MOUSEEVENTF_MIDDLEUP;
                        inp.u.mi.dwExtraInfo = (UIntPtr)(ulong)_releaseTag;
                    }
                    else
                    {
                        inp.type = INPUT_KEYBOARD;
                        inp.u.ki.wVk = (ushort)key;
                        inp.u.ki.dwFlags = KEYEVENTF_KEYUP;
                        inp.u.ki.dwExtraInfo = (UIntPtr)(ulong)_releaseTag;
                    }
                    uint sent = SendInput(1, new[] { inp }, Marshal.SizeOf(typeof(INPUT)));
                    results.Add(key + ":" + (sent == 1 ? "ok" : "err" + Marshal.GetLastWin32Error()));
                }
            }
            finally
            {
                Volatile.Write(ref _releasing, 0);
            }
            return string.Join(",", results);
        }

        private static void WriterLoop()
        {
            while (Wake.WaitOne())
            {
                DateTime? latest;
                string held;
                lock (Gate)
                {
                    latest = _latestPerson == DateTime.MinValue ? (DateTime?)null : _latestPerson;
                    held = string.Join(",", SmokeHeld);
                }
                WriteRecord(latest, held);
            }
        }

        private static void WriteRecord(DateTime? latest, string held)
        {
            string text = (latest.HasValue ? latest.Value.ToString("O", CultureInfo.InvariantCulture) : "none") + "\n" + held + "\n";
            string tmp = _recordFile + "." + Process.GetCurrentProcess().Id + ".tmp";
            string dir = Path.GetDirectoryName(_recordFile);
            if (!string.IsNullOrEmpty(dir)) Directory.CreateDirectory(dir);
            File.WriteAllText(tmp, text, new UTF8Encoding(false));
            if (File.Exists(_recordFile)) File.Replace(tmp, _recordFile, null, true);
            else File.Move(tmp, _recordFile);
        }

        private delegate IntPtr HookProc(int nCode, IntPtr wParam, IntPtr lParam);
        [StructLayout(LayoutKind.Sequential)] private struct POINT { public int X, Y; }
        [StructLayout(LayoutKind.Sequential)] private struct MSG { public IntPtr hwnd; public uint message; public IntPtr wParam, lParam; public uint time; public POINT pt; }
        [StructLayout(LayoutKind.Sequential)] private struct KBDLLHOOKSTRUCT { public uint vkCode, scanCode, flags, time; public IntPtr extra; }
        [StructLayout(LayoutKind.Sequential)] private struct MSLLHOOKSTRUCT { public POINT pt; public uint mouseData, flags, time; public IntPtr extra; }

        [StructLayout(LayoutKind.Sequential)]
        private struct MOUSEINPUT
        {
            public int dx, dy;
            public uint mouseData, dwFlags, time;
            public UIntPtr dwExtraInfo;
        }
        [StructLayout(LayoutKind.Sequential)]
        private struct KEYBDINPUT
        {
            public ushort wVk, wScan;
            public uint dwFlags, time;
            public UIntPtr dwExtraInfo;
        }
        [StructLayout(LayoutKind.Sequential)]
        private struct HARDWAREINPUT { public uint uMsg; public ushort wParamL, wParamH; }
        [StructLayout(LayoutKind.Explicit)]
        private struct InputUnion
        {
            [FieldOffset(0)] public MOUSEINPUT mi;
            [FieldOffset(0)] public KEYBDINPUT ki;
            [FieldOffset(0)] public HARDWAREINPUT hi;
        }
        [StructLayout(LayoutKind.Sequential)]
        private struct INPUT { public uint type; public InputUnion u; }

        [DllImport("user32.dll", SetLastError = true)] private static extern uint SendInput(uint nInputs, INPUT[] pInputs, int cbSize);
        [DllImport("user32.dll", SetLastError = true)] private static extern IntPtr SetWindowsHookEx(int idHook, HookProc lpfn, IntPtr hMod, uint dwThreadId);
        [DllImport("user32.dll", SetLastError = true)] private static extern bool UnhookWindowsHookEx(IntPtr hhk);
        [DllImport("user32.dll")] private static extern IntPtr CallNextHookEx(IntPtr hhk, int nCode, IntPtr wParam, IntPtr lParam);
        [DllImport("user32.dll")] private static extern int GetMessage(out MSG lpMsg, IntPtr hWnd, uint min, uint max);
        [DllImport("user32.dll")] private static extern IntPtr DispatchMessage(ref MSG lpMsg);
        [DllImport("user32.dll")] private static extern bool PostThreadMessage(uint idThread, uint msg, IntPtr wParam, IntPtr lParam);
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode)] private static extern IntPtr GetModuleHandle(string lpModuleName);
        [DllImport("kernel32.dll")] private static extern uint GetCurrentThreadId();
    }
}
