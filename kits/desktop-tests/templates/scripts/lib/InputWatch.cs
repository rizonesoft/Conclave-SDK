// Low-level keyboard and mouse hook watcher for real-input desktop smoke runs (D04 T04 s1).
// Compiles cleanly with .NET Framework 4.x csc.exe (zero external dependencies).
// Accepts only injected events whose dwExtraInfo matches this run's fresh per-run tag (or the watcher's
// own release tag). Any untagged, local, or foreign-tagged injected input (e.g. remote control) sets the
// named personEvent immediately and blocks subsequent smoke input.
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
        private const long ReleaseTag = 0x434E5232; // "CNR2"

        private static long _smokeTag;
        private static string _recordFile = "";
        private static DateTime _latestPerson = DateTime.MinValue;
        private static readonly AutoResetEvent Wake = new AutoResetEvent(false);
        private static EventWaitHandle _personEvent;
        private static bool _guard;
        private static bool _personCame;
        private static readonly object Gate = new object();
        private static readonly SortedSet<int> SmokeHeld = new SortedSet<int>();
        private static readonly HashSet<int> PersonHeld = new HashSet<int>();
        private static HookProc _keysProc, _mouseProc;

        public static int Main(string[] args)
        {
            string file = null;
            string personName = null;
            string tagHex = null;
            bool guard = false;
            for (int i = 0; i < args.Length; i++)
            {
                if (args[i] == "--file" && i + 1 < args.Length) file = args[++i];
                else if (args[i] == "--person-event" && i + 1 < args.Length) personName = args[++i];
                else if (args[i] == "--tag" && i + 1 < args.Length) tagHex = args[++i];
                else if (args[i] == "--guard") guard = true;
            }
            if (string.IsNullOrEmpty(file) || string.IsNullOrEmpty(tagHex))
            {
                Console.Error.WriteLine("input-watch: --file <path> and --tag <hex> are required");
                return 2;
            }
            if (!long.TryParse(tagHex, NumberStyles.HexNumber, CultureInfo.InvariantCulture, out _smokeTag) || _smokeTag == 0 || _smokeTag == ReleaseTag)
            {
                Console.Error.WriteLine("input-watch: invalid --tag hex value: " + tagHex);
                return 2;
            }
            _guard = guard;
            _recordFile = Path.GetFullPath(file);
            if (!string.IsNullOrEmpty(personName))
            {
                _personEvent = new EventWaitHandle(false, EventResetMode.ManualReset, personName);
            }
            uint threadId = GetCurrentThreadId();
            _keysProc = (code, wParam, lParam) =>
            {
                if (code >= 0)
                {
                    KBDLLHOOKSTRUCT st = (KBDLLHOOKSTRUCT)Marshal.PtrToStructure(lParam, typeof(KBDLLHOOKSTRUCT));
                    uint msg = (uint)wParam.ToInt64();
                    bool injected = (st.flags & LLKHF_INJECTED) != 0;
                    bool isSmoke = IsSmokeEvent(injected, st.extra.ToInt64());
                    bool down = msg == WM_KEYDOWN || msg == WM_SYSKEYDOWN;
                    bool up = msg == WM_KEYUP || msg == WM_SYSKEYUP;
                    if (ProcessEvent(isSmoke, (int)st.vkCode, down, up)) return new IntPtr(1);
                }
                return CallNextHookEx(IntPtr.Zero, code, wParam, lParam);
            };
            _mouseProc = (code, wParam, lParam) =>
            {
                if (code >= 0)
                {
                    MSLLHOOKSTRUCT st = (MSLLHOOKSTRUCT)Marshal.PtrToStructure(lParam, typeof(MSLLHOOKSTRUCT));
                    uint msg = (uint)wParam.ToInt64();
                    int btn = (msg == WM_LBUTTONDOWN || msg == WM_LBUTTONUP) ? 1
                            : (msg == WM_RBUTTONDOWN || msg == WM_RBUTTONUP) ? 2
                            : (msg == WM_MBUTTONDOWN || msg == WM_MBUTTONUP) ? 4 : 0;
                    bool injected = (st.flags & LLMHF_INJECTED) != 0;
                    bool isSmoke = IsSmokeEvent(injected, st.extra.ToInt64());
                    bool down = msg == WM_LBUTTONDOWN || msg == WM_RBUTTONDOWN || msg == WM_MBUTTONDOWN;
                    bool up = msg == WM_LBUTTONUP || msg == WM_RBUTTONUP || msg == WM_MBUTTONUP;
                    if (ProcessEvent(isSmoke, btn, down, up)) return new IntPtr(1);
                }
                return CallNextHookEx(IntPtr.Zero, code, wParam, lParam);
            };

            WriteRecord(null, "");
            IntPtr mod = GetModuleHandle(null);
            IntPtr hKeys = SetWindowsHookEx(WH_KEYBOARD_LL, _keysProc, mod, 0);
            IntPtr hMouse = SetWindowsHookEx(WH_MOUSE_LL, _mouseProc, mod, 0);
            if (hKeys == IntPtr.Zero || hMouse == IntPtr.Zero)
            {
                if (hKeys != IntPtr.Zero) UnhookWindowsHookEx(hKeys);
                if (hMouse != IntPtr.Zero) UnhookWindowsHookEx(hMouse);
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
                        // Simulated injected event carrying another sender's tag (remote control / other runner).
                        long foreignTag = _smokeTag ^ 0x55AA;
                        ProcessEvent(IsSmokeEvent(true, foreignTag), 0, false, false);
                    }
                    else if (cmd == "smoke-tag")
                    {
                        // Simulated injected event carrying this run's exact tag (must NOT trigger personEvent).
                        ProcessEvent(IsSmokeEvent(true, _smokeTag), 0, false, false);
                    }
                    else if (cmd == "release")
                    {
                        List<int> released = ReleaseHeld();
                        Console.Out.WriteLine("released " + string.Join(",", released));
                        Console.Out.Flush();
                    }
                    else if (cmd == "quit")
                    {
                        PostThreadMessage(threadId, WM_QUIT, IntPtr.Zero, IntPtr.Zero);
                        break;
                    }
                }
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
                    UnhookWindowsHookEx(hKeys);
                    UnhookWindowsHookEx(hMouse);
                    GC.KeepAlive(maxLife);
                }
            }
            return 0;
        }

        private static bool IsSmokeEvent(bool injected, long extra)
        {
            return injected && (extra == _smokeTag || extra == ReleaseTag);
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

        private static List<int> ReleaseHeld()
        {
            List<int> copy;
            lock (Gate)
            {
                copy = new List<int>(SmokeHeld);
                SmokeHeld.Clear();
            }
            return copy;
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
