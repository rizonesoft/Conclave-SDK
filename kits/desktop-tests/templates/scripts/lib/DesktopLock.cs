using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;

namespace Conclave.DesktopTests
{
    public sealed class DesktopLockBusyException : Exception
    {
        public string LockName { get; private set; }
        public int? HolderPid { get; private set; }
        public long? HolderStartTicks { get; private set; }
        public string HolderStartUtc { get; private set; }
        public string HolderLabel { get; private set; }

        public DesktopLockBusyException(
            string message,
            string lockName,
            int? holderPid,
            long? holderStartTicks,
            string holderStartUtc,
            string holderLabel)
            : base(message)
        {
            LockName = lockName;
            HolderPid = holderPid;
            HolderStartTicks = holderStartTicks;
            HolderStartUtc = holderStartUtc;
            HolderLabel = holderLabel;
        }
    }

    public sealed class DesktopLockLostException : Exception
    {
        public DesktopLockLostException(string message) : base(message) { }
    }

    public sealed class DesktopLockHandle : IDisposable
    {
        private readonly IntPtr _hMutex;
        private readonly IntPtr _hLease;
        private readonly IntPtr _hJob;
        private readonly int _ownerThreadId;
        private readonly string _recordPath;
        private readonly string _leaseEventName;
        private readonly string _jobName;
        private readonly bool _inherited;
        private bool _disposed;

        public string LockName { get; private set; }
        public string RecordPath { get { return _recordPath; } }
        public string LeaseId { get; private set; }
        public string LeaseEventName { get { return _leaseEventName; } }
        public string JobName { get { return _jobName; } }
        public bool Inherited { get { return _inherited; } }
        public int HolderPid { get; private set; }
        public long HolderStartTicks { get; private set; }
        public string HolderStartUtc { get; private set; }
        public string HeldToken { get; private set; }
        public IntPtr JobHandle { get { return _hJob; } }

        internal DesktopLockHandle(
            IntPtr hMutex,
            IntPtr hLease,
            IntPtr hJob,
            int ownerThreadId,
            string lockName,
            string recordPath,
            string leaseId,
            string leaseEventName,
            string jobName,
            bool inherited,
            int holderPid,
            long holderStartTicks,
            string holderStartUtc)
        {
            _hMutex = hMutex;
            _hLease = hLease;
            _hJob = hJob;
            _ownerThreadId = ownerThreadId;
            LockName = lockName;
            _recordPath = recordPath;
            LeaseId = leaseId;
            _leaseEventName = leaseEventName;
            _jobName = jobName;
            _inherited = inherited;
            HolderPid = holderPid;
            HolderStartTicks = holderStartTicks;
            HolderStartUtc = holderStartUtc;
            HeldToken = holderPid.ToString(CultureInfo.InvariantCulture)
                + ":" + holderStartTicks.ToString(CultureInfo.InvariantCulture)
                + ":" + leaseId
                + ":" + lockName;
        }

        public void AssignProcessToJob(IntPtr hProcess)
        {
            if (_disposed) throw new ObjectDisposedException("DesktopLockHandle");
            if (_inherited || _hJob == IntPtr.Zero)
                throw new InvalidOperationException("only the owning DesktopLockHandle can assign processes to the desktop job");
            if (!DesktopLock.AssignProcessToJobObject(_hJob, hProcess))
                throw new Win32Exception(Marshal.GetLastWin32Error(), "AssignProcessToJobObject failed");
        }

        public int StartProcessInJob(string exePath, string arguments, string workingDirectory, IDictionary<string, string> env)
        {
            if (_disposed) throw new ObjectDisposedException("DesktopLockHandle");
            if (_inherited || _hJob == IntPtr.Zero)
                throw new InvalidOperationException("only the owning DesktopLockHandle can start processes in the desktop job");
            return DesktopLock.StartProcessInJobHandle(_hJob, exePath, arguments, workingDirectory, env);
        }

        public void EnsureStillHeld()
        {
            if (_disposed) throw new DesktopLockLostException("desktop lock handle has already been disposed");
            if (!DesktopLock.IsHolderLeaseLive(HolderPid, HolderStartTicks, _leaseEventName))
                throw new DesktopLockLostException("desktop lock lease is no longer active for holder pid=" + HolderPid);
            if (_inherited)
            {
                if (!DesktopLock.IsCurrentProcessInNamedJob(_jobName))
                    throw new DesktopLockLostException("inherited process is not a member of active desktop job " + _jobName);
                DesktopLock.HolderRecord rec = DesktopLock.TryReadHolderRecord(_recordPath);
                if (rec == null || rec.Pid != HolderPid || rec.StartTicks != HolderStartTicks || rec.LeaseId != LeaseId)
                    throw new DesktopLockLostException("holder record no longer matches inherited lease " + LeaseId);
            }
        }

        public void Dispose()
        {
            if (_disposed) return;
            if (!_inherited && Thread.CurrentThread.ManagedThreadId != _ownerThreadId)
            {
                throw new InvalidOperationException(
                    "DesktopLockHandle must be disposed on the thread that acquired it (owner="
                    + _ownerThreadId + ", current=" + Thread.CurrentThread.ManagedThreadId + ")");
            }
            _disposed = true;
            if (_inherited) return;

            try
            {
                if (_hJob != IntPtr.Zero)
                {
                    DesktopLock.TerminateAndDrainJob(_hJob, 5000);
                }
            }
            finally
            {
                try
                {
                    if (_hLease != IntPtr.Zero)
                    {
                        if (!DesktopLock.SetEvent(_hLease))
                        {
                            // Record error only after releasing mutex in finally; signaling must not block mutex release.
                            Trace.WriteLine("DesktopLock: SetEvent failed (err=" + Marshal.GetLastWin32Error() + ")");
                        }
                    }
                    if (!string.IsNullOrEmpty(_recordPath))
                    {
                        try
                        {
                            if (File.Exists(_recordPath)) File.Delete(_recordPath);
                        }
                        catch (IOException)
                        {
                            // Intentional: lease event is already permanently signaled so a locked-open record cannot authorize inheritance or misattribute ownership.
                        }
                        catch (UnauthorizedAccessException)
                        {
                            // Intentional: same as IOException above; mutex release must still execute unconditionally.
                        }
                    }
                }
                finally
                {
                    if (_hMutex != IntPtr.Zero)
                    {
                        DesktopLock.ReleaseMutex(_hMutex);
                        DesktopLock.CloseHandle(_hMutex);
                    }
                    if (_hLease != IntPtr.Zero) DesktopLock.CloseHandle(_hLease);
                    if (_hJob != IntPtr.Zero) DesktopLock.CloseHandle(_hJob);
                }
            }
        }
    }

    public static class DesktopLock
    {
        public const string DefaultLockName = "Global\\conclave-desktop-lock";
        public const int DefaultWaitSeconds = 120;
        public const int MaxWaitSeconds = 86400;

        internal const uint SYNCHRONIZE = 0x00100000;
        internal const uint MUTEX_MODIFY_STATE = 0x00000001;
        internal const uint MUTEX_OPS_ACCESS = SYNCHRONIZE | MUTEX_MODIFY_STATE; // 0x00100001
        internal const uint EVENT_ALL_ACCESS = 0x001F0003;
        internal const uint CREATE_EVENT_MANUAL_RESET = 0x00000001;
        internal const uint JOB_OBJECT_QUERY = 0x00000004;
        internal const uint PROCESS_QUERY_LIMITED_INFORMATION = 0x1000;
        internal const uint TH32CS_SNAPPROCESS = 0x00000002;
        internal const uint WAIT_OBJECT_0 = 0x00000000;
        internal const uint WAIT_ABANDONED = 0x00000080;
        internal const uint WAIT_TIMEOUT = 0x00000102;
        internal const uint CREATE_SUSPENDED = 0x00000004;
        internal const uint CREATE_NO_WINDOW = 0x08000000;
        internal const uint CREATE_UNICODE_ENVIRONMENT = 0x00000400;
        internal const int JobObjectBasicProcessIdList = 3;
        internal const int JobObjectExtendedLimitInformation = 9;
        internal const uint JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000;
        internal const int ERROR_FILE_NOT_FOUND = 2;

        // Owner retains full control (including READ_CONTROL); AuthenticatedUsers gets only operational rights.
        private const string SddlMutex = "D:(A;;0x001F0001;;;OW)(A;;0x00100001;;;AU)";
        private const string SddlLeaseEvent = "D:(A;;0x001F0003;;;OW)(A;;0x00100000;;;AU)";
        private const string SddlJob = "D:(A;;0x001F001F;;;OW)(A;;0x00100004;;;AU)";
        private const string SddlRecordDir = "D:(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)(A;OICI;FA;;;OW)(A;OICI;0x001301BF;;;AU)";

        // Test-only hooks (default null/false in production).
        internal static Action BeforeRecordPublishForTest { get; set; }
        internal static bool FailRecordPublishForTest { get; set; }

        internal sealed class HolderRecord
        {
            public int Pid;
            public long StartTicks;
            public string StartUtc;
            public string LeaseId;
            public string LockName;
            public string Label;
        }

        public static string LeaseEventNameFor(string leaseId)
        {
            return "Global\\conclave-desktop-lease-" + leaseId;
        }

        public static string JobNameFor(string leaseId)
        {
            return "Global\\conclave-desktop-job-" + leaseId;
        }

        public static string EnvPrefix(string prefix)
        {
            if (string.IsNullOrWhiteSpace(prefix))
                throw new ArgumentException("prefix must be non-empty", "prefix");
            string mapped = Regex.Replace(prefix.Trim().ToUpperInvariant(), "[^A-Z0-9]+", "_").Trim('_');
            if (string.IsNullOrEmpty(mapped))
                throw new ArgumentException("prefix produced empty environment prefix: " + prefix, "prefix");
            return mapped;
        }

        public static string ResolveLockName(string prefix)
        {
            string envKey = EnvPrefix(prefix) + "_DESKTOP_LOCK";
            string raw = Environment.GetEnvironmentVariable(envKey);
            if (string.IsNullOrWhiteSpace(raw)) return DefaultLockName;
            return CanonicalizeLockName(raw.Trim());
        }

        public static string CanonicalizeLockName(string raw)
        {
            if (string.IsNullOrWhiteSpace(raw)) return DefaultLockName;
            string name = raw.Trim();
            string remainder;
            int slash = name.IndexOf('\\');
            if (slash >= 0)
            {
                string ns = name.Substring(0, slash);
                if (!ns.Equals("Global", StringComparison.OrdinalIgnoreCase))
                    throw new ArgumentException("unsupported desktop lock namespace '" + ns + "\\'; use Global\\<name> or an unqualified name");
                remainder = name.Substring(slash + 1);
            }
            else
            {
                remainder = name;
            }
            if (string.IsNullOrEmpty(remainder) || remainder.Length > 180 || remainder.IndexOf('\\') >= 0)
                throw new ArgumentException("invalid desktop lock name: " + raw);
            foreach (char c in remainder)
            {
                if (char.IsControl(c) || char.IsWhiteSpace(c))
                    throw new ArgumentException("desktop lock name must not contain whitespace or control characters: " + raw);
            }
            return "Global\\" + remainder;
        }

        public static int ResolveWaitSeconds(string prefix, int? waitSecondsOverride = null)
        {
            int secs;
            if (waitSecondsOverride.HasValue)
            {
                secs = waitSecondsOverride.Value;
            }
            else
            {
                string envKey = EnvPrefix(prefix) + "_DESKTOP_WAIT_S";
                string raw = Environment.GetEnvironmentVariable(envKey);
                if (string.IsNullOrWhiteSpace(raw))
                {
                    secs = DefaultWaitSeconds;
                }
                else
                {
                    if (!int.TryParse(raw.Trim(), NumberStyles.Integer, CultureInfo.InvariantCulture, out secs))
                        throw new ArgumentOutOfRangeException(envKey, "invalid desktop lock wait seconds: '" + raw + "'");
                }
            }
            if (secs < 0 || secs > MaxWaitSeconds)
                throw new ArgumentOutOfRangeException("waitSeconds", "desktop lock wait seconds must be in [0, " + MaxWaitSeconds + "], got " + secs);
            return secs;
        }

        public static string RecordDirectory()
        {
            string baseDir = Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData);
            if (string.IsNullOrWhiteSpace(baseDir)) baseDir = Path.GetTempPath();
            return Path.Combine(baseDir, "Conclave", "desktop-locks");
        }

        public static string RecordPathForLock(string canonicalLockName)
        {
            string canonical = CanonicalizeLockName(canonicalLockName);
            using (SHA256 sha = SHA256.Create())
            {
                byte[] hash = sha.ComputeHash(Encoding.UTF8.GetBytes(canonical));
                StringBuilder sb = new StringBuilder(hash.Length * 2);
                foreach (byte b in hash) sb.Append(b.ToString("x2", CultureInfo.InvariantCulture));
                return Path.Combine(RecordDirectory(), sb.ToString() + ".json");
            }
        }

        public static DesktopLockHandle Acquire(string prefix, string label, int? waitSecondsOverride = null)
        {
            string envPrefix = EnvPrefix(prefix);
            string canonicalLock = ResolveLockName(prefix);
            int waitSeconds = ResolveWaitSeconds(prefix, waitSecondsOverride);
            string recordPath = RecordPathForLock(canonicalLock);
            EnsureRecordDirectory(Path.GetDirectoryName(recordPath));

            IntPtr hMutex = CreateSecureMutex(canonicalLock);
            try
            {
                // Check inheritance via <ENV_PREFIX>_DESKTOP_HELD first.
                string heldToken = Environment.GetEnvironmentVariable(envPrefix + "_DESKTOP_HELD");
                DesktopLockHandle inherited = TryInherit(hMutex, canonicalLock, recordPath, heldToken);
                if (inherited != null)
                {
                    CloseHandle(hMutex);
                    hMutex = IntPtr.Zero;
                    return inherited;
                }

                uint waitMs = checked((uint)waitSeconds * 1000u);
                uint rc = WaitForSingleObject(hMutex, waitMs);
                if (rc != WAIT_OBJECT_0 && rc != WAIT_ABANDONED)
                {
                    if (rc == WAIT_TIMEOUT)
                    {
                        throw BuildBusyException(canonicalLock, recordPath, waitSeconds);
                    }
                    throw new Win32Exception(Marshal.GetLastWin32Error(), "WaitForSingleObject failed on " + canonicalLock + " (rc=0x" + rc.ToString("X") + ")");
                }

                IntPtr hLease = IntPtr.Zero;
                IntPtr hJob = IntPtr.Zero;
                bool published = false;
                try
                {
                    // On EVERY handoff (normal, abandoned, late-arriving, or post-probe), verify prior desktop job quiescence.
                    DrainPriorJobFromRecord(recordPath, 5000);

                    Action beforePub = BeforeRecordPublishForTest;
                    if (beforePub != null) beforePub();

                    int selfPid = Process.GetCurrentProcess().Id;
                    long selfTicks;
                    if (!TryGetProcessCreationTicks(selfPid, out selfTicks))
                        throw new InvalidOperationException("failed to read current process creation time");
                    string selfUtc = DateTime.FromFileTimeUtc(selfTicks).ToString("O", CultureInfo.InvariantCulture);
                    string leaseId = Guid.NewGuid().ToString("N").Substring(0, 16);
                    string leaseName = LeaseEventNameFor(leaseId);
                    string jobName = JobNameFor(leaseId);

                    hLease = CreateSecureLeaseEvent(leaseName);
                    hJob = CreateSecureJob(jobName);

                    HolderRecord rec = new HolderRecord
                    {
                        Pid = selfPid,
                        StartTicks = selfTicks,
                        StartUtc = selfUtc,
                        LeaseId = leaseId,
                        LockName = canonicalLock,
                        Label = string.IsNullOrWhiteSpace(label) ? "desktop-lock" : label.Trim()
                    };

                    if (FailRecordPublishForTest)
                        throw new IOException("simulated holder record publication failure");
                    WriteHolderRecordAtomic(recordPath, rec);
                    published = true;

                    IntPtr ownedMutex = hMutex;
                    hMutex = IntPtr.Zero;
                    return new DesktopLockHandle(
                        ownedMutex,
                        hLease,
                        hJob,
                        Thread.CurrentThread.ManagedThreadId,
                        canonicalLock,
                        recordPath,
                        leaseId,
                        leaseName,
                        jobName,
                        false,
                        selfPid,
                        selfTicks,
                        selfUtc);
                }
                finally
                {
                    if (!published)
                    {
                        if (hJob != IntPtr.Zero)
                        {
                            TerminateAndDrainJob(hJob, 2000);
                            CloseHandle(hJob);
                        }
                        if (hLease != IntPtr.Zero)
                        {
                            SetEvent(hLease);
                            CloseHandle(hLease);
                        }
                        if (hMutex != IntPtr.Zero)
                        {
                            ReleaseMutex(hMutex);
                        }
                    }
                }
            }
            finally
            {
                if (hMutex != IntPtr.Zero) CloseHandle(hMutex);
            }
        }

        private static DesktopLockHandle TryInherit(IntPtr hMutex, string canonicalLock, string recordPath, string heldToken)
        {
            if (string.IsNullOrWhiteSpace(heldToken)) return null;
            int tokPid;
            long tokTicks;
            string tokLeaseId;
            string tokLock;
            if (!TryParseHeldToken(heldToken, out tokPid, out tokTicks, out tokLeaseId, out tokLock)) return null;
            if (!string.Equals(tokLock, canonicalLock, StringComparison.Ordinal)) return null;

            // 1. Verify (tokPid, tokTicks) is a live ancestor in the real OS process tree.
            if (!IsLiveAncestorWithStartTicks(tokPid, tokTicks)) return null;

            // 2. Verify holder record matches token.
            HolderRecord rec = TryReadHolderRecord(recordPath);
            if (rec == null || rec.Pid != tokPid || rec.StartTicks != tokTicks
                || !string.Equals(rec.LeaseId, tokLeaseId, StringComparison.Ordinal)
                || !string.Equals(rec.LockName, canonicalLock, StringComparison.Ordinal))
                return null;

            // 3. Verify owner alive + manual-reset lease event still unsignaled (readers cannot mutate).
            string leaseName = LeaseEventNameFor(tokLeaseId);
            string jobName = JobNameFor(tokLeaseId);
            if (!IsHolderLeaseLive(tokPid, tokTicks, leaseName)) return null;

            // 4. Verify current process is a member of the holder's named desktop job.
            if (!IsCurrentProcessInNamedJob(jobName)) return null;

            // 5. Verify main mutex is currently contended (not already released by the parent).
            uint probe = WaitForSingleObject(hMutex, 0);
            if (probe == WAIT_OBJECT_0 || probe == WAIT_ABANDONED)
            {
                ReleaseMutex(hMutex);
                return null;
            }
            if (probe != WAIT_TIMEOUT) return null;

            return new DesktopLockHandle(
                IntPtr.Zero,
                IntPtr.Zero,
                IntPtr.Zero,
                Thread.CurrentThread.ManagedThreadId,
                canonicalLock,
                recordPath,
                tokLeaseId,
                leaseName,
                jobName,
                true,
                tokPid,
                tokTicks,
                rec.StartUtc);
        }

        private static bool TryParseHeldToken(string raw, out int pid, out long startTicks, out string leaseId, out string lockName)
        {
            pid = 0;
            startTicks = 0;
            leaseId = null;
            lockName = null;
            int c1 = raw.IndexOf(':');
            if (c1 <= 0) return false;
            int c2 = raw.IndexOf(':', c1 + 1);
            if (c2 <= c1 + 1) return false;
            int c3 = raw.IndexOf(':', c2 + 1);
            if (c3 <= c2 + 1 || c3 >= raw.Length - 1) return false;
            if (!int.TryParse(raw.Substring(0, c1), NumberStyles.Integer, CultureInfo.InvariantCulture, out pid) || pid <= 0) return false;
            if (!long.TryParse(raw.Substring(c1 + 1, c2 - c1 - 1), NumberStyles.Integer, CultureInfo.InvariantCulture, out startTicks) || startTicks <= 0) return false;
            leaseId = raw.Substring(c2 + 1, c3 - c2 - 1);
            lockName = raw.Substring(c3 + 1);
            return !string.IsNullOrEmpty(leaseId) && !string.IsNullOrEmpty(lockName);
        }

        private static DesktopLockBusyException BuildBusyException(string canonicalLock, string recordPath, int waitSeconds)
        {
            HolderRecord rec = TryReadHolderRecord(recordPath);
            if (rec != null && !string.IsNullOrEmpty(rec.LeaseId))
            {
                string leaseName = "Global\\conclave-desktop-lease-" + rec.LeaseId;
                if (IsHolderLeaseLive(rec.Pid, rec.StartTicks, leaseName))
                {
                    string msg = "desktop lock '" + canonicalLock + "' is held by pid=" + rec.Pid
                        + " started=" + rec.StartUtc + " (ticks=" + rec.StartTicks + ", label=" + rec.Label
                        + "); waited " + waitSeconds + "s";
                    return new DesktopLockBusyException(msg, canonicalLock, rec.Pid, rec.StartTicks, rec.StartUtc, rec.Label);
                }
            }
            return new DesktopLockBusyException(
                "desktop lock '" + canonicalLock + "' is held by another process (holder identity unavailable); waited " + waitSeconds + "s",
                canonicalLock,
                null,
                null,
                null,
                null);
        }

        internal static bool IsHolderLeaseLive(int pid, long expectedStartTicks, string leaseEventName)
        {
            if (pid <= 0 || expectedStartTicks <= 0 || string.IsNullOrEmpty(leaseEventName)) return false;
            long liveTicks;
            if (!TryGetProcessCreationTicks(pid, out liveTicks) || liveTicks != expectedStartTicks) return false;
            IntPtr hLease = OpenEventW(SYNCHRONIZE, false, leaseEventName);
            if (hLease == IntPtr.Zero) return false;
            try
            {
                return WaitForSingleObject(hLease, 0) == WAIT_TIMEOUT;
            }
            finally
            {
                CloseHandle(hLease);
            }
        }

        internal static bool IsCurrentProcessInNamedJob(string jobName)
        {
            if (string.IsNullOrEmpty(jobName)) return false;
            IntPtr hJob = OpenJobObjectW(JOB_OBJECT_QUERY, false, jobName);
            if (hJob == IntPtr.Zero) return false;
            try
            {
                bool inJob;
                return IsProcessInJob(GetCurrentProcess(), hJob, out inJob) && inJob;
            }
            finally
            {
                CloseHandle(hJob);
            }
        }

        private static void DrainPriorJobFromRecord(string recordPath, int timeoutMs)
        {
            HolderRecord prior = TryReadHolderRecord(recordPath);
            if (prior == null || string.IsNullOrEmpty(prior.LeaseId)) return;
            string priorJobName = JobNameFor(prior.LeaseId);
            DateTime deadline = DateTime.UtcNow.AddMilliseconds(timeoutMs);
            while (true)
            {
                // Open, query, and IMMEDIATELY close the query handle on each poll so our handle never
                // prolongs the job's lifetime or blocks JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE!
                IntPtr hJob = OpenJobObjectW(JOB_OBJECT_QUERY, false, priorJobName);
                if (hJob == IntPtr.Zero)
                {
                    int err = Marshal.GetLastWin32Error();
                    if (err == ERROR_FILE_NOT_FOUND)
                    {
                        // Job name is gone; also verify prior owner is no longer holding an active lease.
                        if (!IsHolderLeaseLive(prior.Pid, prior.StartTicks, LeaseEventNameFor(prior.LeaseId)))
                            return;
                        if (DateTime.UtcNow >= deadline)
                            throw new InvalidOperationException("prior holder lease still appears active after job vanished");
                        Thread.Sleep(20);
                        continue;
                    }
                    throw new Win32Exception(err, "cannot verify quiescence of prior desktop job '" + priorJobName + "'");
                }
                int count;
                try
                {
                    count = QueryJobActiveProcessCount(hJob);
                }
                finally
                {
                    CloseHandle(hJob);
                }
                if (count == 0) return;
                if (DateTime.UtcNow >= deadline)
                    throw new InvalidOperationException("prior desktop job '" + priorJobName + "' still has " + count + " active process(es); refusing lock acquisition");
                Thread.Sleep(20);
            }
        }

        internal static void TerminateAndDrainJob(IntPtr hJob, int timeoutMs)
        {
            TerminateJobObject(hJob, 1);
            DateTime deadline = DateTime.UtcNow.AddMilliseconds(timeoutMs);
            while (DateTime.UtcNow < deadline)
            {
                int count = QueryJobActiveProcessCount(hJob);
                if (count == 0) return;
                Thread.Sleep(15);
            }
        }

        private static int QueryJobActiveProcessCount(IntPtr hJob)
        {
            // Buffer for JOBOBJECT_BASIC_PROCESS_ID_LIST (2 uint header + up to 64 IntPtr PIDs).
            int bufSize = 8 + IntPtr.Size * 64;
            IntPtr buf = Marshal.AllocHGlobal(bufSize);
            try
            {
                uint retLen;
                bool ok = QueryInformationJobObject(hJob, JobObjectBasicProcessIdList, buf, (uint)bufSize, out retLen);
                if (!ok)
                {
                    int err = Marshal.GetLastWin32Error();
                    if (err == 234) // ERROR_MORE_DATA -> definitely > 0 active processes
                        return 65;
                    throw new Win32Exception(err, "QueryInformationJobObject failed");
                }
                int assigned = Marshal.ReadInt32(buf, 0);
                int inList = Marshal.ReadInt32(buf, 4);
                return Math.Max(assigned, inList);
            }
            finally
            {
                Marshal.FreeHGlobal(buf);
            }
        }

        public static bool TryGetProcessCreationTicks(int pid, out long creationTicks)
        {
            creationTicks = 0;
            if (pid <= 0) return false;
            IntPtr hProc = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, false, (uint)pid);
            if (hProc == IntPtr.Zero) return false;
            try
            {
                uint exitCode;
                if (!GetExitCodeProcess(hProc, out exitCode) || exitCode != 259) // STILL_ACTIVE
                    return false;
                long c, e, k, u;
                if (!GetProcessTimes(hProc, out c, out e, out k, out u)) return false;
                creationTicks = c;
                return c > 0;
            }
            finally
            {
                CloseHandle(hProc);
            }
        }

        private static bool IsLiveAncestorWithStartTicks(int targetPid, long targetStartTicks)
        {
            int curPid = Process.GetCurrentProcess().Id;
            long curTicks;
            if (!TryGetProcessCreationTicks(curPid, out curTicks)) return false;

            Dictionary<int, int> parentMap = SnapshotParentPids();
            HashSet<int> visited = new HashSet<int>();
            visited.Add(curPid);

            for (int depth = 0; depth < 64; depth++)
            {
                int parentPid;
                if (!parentMap.TryGetValue(curPid, out parentPid) || parentPid <= 0) return false;
                if (!visited.Add(parentPid)) return false;
                long parentTicks;
                if (!TryGetProcessCreationTicks(parentPid, out parentTicks)) return false;
                if (parentTicks > curTicks) return false; // PID reused after child started
                if (parentPid == targetPid)
                {
                    return parentTicks == targetStartTicks;
                }
                curPid = parentPid;
                curTicks = parentTicks;
            }
            return false;
        }

        private static Dictionary<int, int> SnapshotParentPids()
        {
            var map = new Dictionary<int, int>();
            IntPtr snap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
            if (snap == IntPtr.Zero || snap == new IntPtr(-1)) return map;
            try
            {
                PROCESSENTRY32 entry = new PROCESSENTRY32();
                entry.dwSize = (uint)Marshal.SizeOf(typeof(PROCESSENTRY32));
                if (Process32First(snap, ref entry))
                {
                    do
                    {
                        map[(int)entry.th32ProcessID] = (int)entry.th32ParentProcessID;
                    } while (Process32Next(snap, ref entry));
                }
            }
            finally
            {
                CloseHandle(snap);
            }
            return map;
        }

        private static IntPtr CreateSecureMutex(string name)
        {
            IntPtr sd;
            SECURITY_ATTRIBUTES sa = MakeSecurityAttributes(SddlMutex, out sd);
            try
            {
                IntPtr h = CreateMutexExW(ref sa, name, 0, MUTEX_OPS_ACCESS);
                if (h == IntPtr.Zero)
                    throw new Win32Exception(Marshal.GetLastWin32Error(), "CreateMutexExW failed for " + name);
                return h;
            }
            finally
            {
                if (sd != IntPtr.Zero) LocalFree(sd);
            }
        }

        private static IntPtr CreateSecureLeaseEvent(string name)
        {
            IntPtr sd;
            SECURITY_ATTRIBUTES sa = MakeSecurityAttributes(SddlLeaseEvent, out sd);
            try
            {
                IntPtr h = CreateEventExW(ref sa, name, CREATE_EVENT_MANUAL_RESET, EVENT_ALL_ACCESS);
                if (h == IntPtr.Zero)
                    throw new Win32Exception(Marshal.GetLastWin32Error(), "CreateEventExW failed for " + name);
                return h;
            }
            finally
            {
                if (sd != IntPtr.Zero) LocalFree(sd);
            }
        }

        private static IntPtr CreateSecureJob(string name)
        {
            IntPtr sd;
            SECURITY_ATTRIBUTES sa = MakeSecurityAttributes(SddlJob, out sd);
            try
            {
                IntPtr h = CreateJobObjectW(ref sa, name);
                if (h == IntPtr.Zero)
                    throw new Win32Exception(Marshal.GetLastWin32Error(), "CreateJobObjectW failed for " + name);
                JOBOBJECT_EXTENDED_LIMIT_INFORMATION info = new JOBOBJECT_EXTENDED_LIMIT_INFORMATION();
                info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
                int size = Marshal.SizeOf(typeof(JOBOBJECT_EXTENDED_LIMIT_INFORMATION));
                IntPtr ptr = Marshal.AllocHGlobal(size);
                try
                {
                    Marshal.StructureToPtr(info, ptr, false);
                    if (!SetInformationJobObject(h, JobObjectExtendedLimitInformation, ptr, (uint)size))
                    {
                        int err = Marshal.GetLastWin32Error();
                        CloseHandle(h);
                        throw new Win32Exception(err, "SetInformationJobObject failed for " + name);
                    }
                }
                finally
                {
                    Marshal.FreeHGlobal(ptr);
                }
                return h;
            }
            finally
            {
                if (sd != IntPtr.Zero) LocalFree(sd);
            }
        }

        private static void EnsureRecordDirectory(string dir)
        {
            if (string.IsNullOrEmpty(dir)) return;
            bool existed = Directory.Exists(dir);
            Directory.CreateDirectory(dir);
            if (!existed)
            {
                IntPtr sd;
                if (ConvertStringSecurityDescriptorToSecurityDescriptorW(SddlRecordDir, 1, out sd, IntPtr.Zero))
                {
                    try
                    {
                        bool present, defaulted;
                        IntPtr dacl;
                        if (GetSecurityDescriptorDacl(sd, out present, out dacl, out defaulted) && present)
                        {
                            // Best-effort ACL on newly created shared directory; ignore ACCESS_DENIED if pre-owned.
                            SetNamedSecurityInfoW(dir, 1 /* SE_FILE_OBJECT */, 4 /* DACL_SECURITY_INFORMATION */, IntPtr.Zero, IntPtr.Zero, dacl, IntPtr.Zero);
                        }
                    }
                    finally
                    {
                        LocalFree(sd);
                    }
                }
            }
        }

        private static SECURITY_ATTRIBUTES MakeSecurityAttributes(string sddl, out IntPtr sd)
        {
            if (!ConvertStringSecurityDescriptorToSecurityDescriptorW(sddl, 1, out sd, IntPtr.Zero))
                throw new Win32Exception(Marshal.GetLastWin32Error(), "ConvertStringSecurityDescriptorToSecurityDescriptorW failed");
            return new SECURITY_ATTRIBUTES
            {
                nLength = Marshal.SizeOf(typeof(SECURITY_ATTRIBUTES)),
                lpSecurityDescriptor = sd,
                bInheritHandle = false
            };
        }

        internal static void WriteHolderRecordAtomic(string path, HolderRecord rec)
        {
            string dir = Path.GetDirectoryName(path);
            EnsureRecordDirectory(dir);
            string json = SerializeRecord(rec);
            string tmp = path + "." + Process.GetCurrentProcess().Id + "." + Guid.NewGuid().ToString("N").Substring(0, 8) + ".tmp";
            File.WriteAllText(tmp, json, new UTF8Encoding(false));
            try
            {
                if (!MoveFileExW(tmp, path, 0x00000001 | 0x00000008)) // MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH
                {
                    throw new IOException("MoveFileExW failed (err=" + Marshal.GetLastWin32Error() + ")");
                }
            }
            catch
            {
                try { if (File.Exists(tmp)) File.Delete(tmp); } catch (IOException) { }
                throw;
            }
        }

        internal static HolderRecord TryReadHolderRecord(string path)
        {
            if (string.IsNullOrEmpty(path) || !File.Exists(path)) return null;
            try
            {
                using (var fs = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete))
                using (var sr = new StreamReader(fs, Encoding.UTF8))
                {
                    return ParseRecord(sr.ReadToEnd());
                }
            }
            catch (IOException)
            {
                return null;
            }
            catch (UnauthorizedAccessException)
            {
                return null;
            }
        }

        private static string SerializeRecord(HolderRecord rec)
        {
            return "{"
                + "\"pid\":" + rec.Pid.ToString(CultureInfo.InvariantCulture) + ","
                + "\"start_ticks\":" + rec.StartTicks.ToString(CultureInfo.InvariantCulture) + ","
                + "\"start_utc\":\"" + EscapeJson(rec.StartUtc) + "\","
                + "\"lease_id\":\"" + EscapeJson(rec.LeaseId) + "\","
                + "\"lock_name\":\"" + EscapeJson(rec.LockName) + "\","
                + "\"label\":\"" + EscapeJson(rec.Label) + "\""
                + "}\n";
        }

        private static string EscapeJson(string s)
        {
            if (string.IsNullOrEmpty(s)) return "";
            StringBuilder sb = new StringBuilder(s.Length + 8);
            foreach (char c in s)
            {
                if (c == '\\') sb.Append("\\\\");
                else if (c == '"') sb.Append("\\\"");
                else if (c == '\r') sb.Append("\\r");
                else if (c == '\n') sb.Append("\\n");
                else if (c == '\t') sb.Append("\\t");
                else if (c < 32) sb.Append("\\u" + ((int)c).ToString("x4", CultureInfo.InvariantCulture));
                else sb.Append(c);
            }
            return sb.ToString();
        }

        private static HolderRecord ParseRecord(string text)
        {
            if (string.IsNullOrWhiteSpace(text)) return null;
            int pid;
            long ticks;
            if (!TryExtractInt(text, "pid", out pid)) return null;
            if (!TryExtractLong(text, "start_ticks", out ticks)) return null;
            return new HolderRecord
            {
                Pid = pid,
                StartTicks = ticks,
                StartUtc = ExtractString(text, "start_utc"),
                LeaseId = ExtractString(text, "lease_id"),
                LockName = ExtractString(text, "lock_name"),
                Label = ExtractString(text, "label")
            };
        }

        private static bool TryExtractInt(string json, string key, out int value)
        {
            value = 0;
            Match m = Regex.Match(json, "\"" + Regex.Escape(key) + "\"\\s*:\\s*(-?\\d+)");
            return m.Success && int.TryParse(m.Groups[1].Value, NumberStyles.Integer, CultureInfo.InvariantCulture, out value);
        }

        private static bool TryExtractLong(string json, string key, out long value)
        {
            value = 0;
            Match m = Regex.Match(json, "\"" + Regex.Escape(key) + "\"\\s*:\\s*(-?\\d+)");
            return m.Success && long.TryParse(m.Groups[1].Value, NumberStyles.Integer, CultureInfo.InvariantCulture, out value);
        }

        private static string ExtractString(string json, string key)
        {
            Match m = Regex.Match(json, "\"" + Regex.Escape(key) + "\"\\s*:\\s*\"((?:\\\\.|[^\"\\\\])*)\"");
            if (!m.Success) return null;
            string raw = m.Groups[1].Value;
            StringBuilder sb = new StringBuilder(raw.Length);
            for (int i = 0; i < raw.Length; i++)
            {
                if (raw[i] == '\\' && i + 1 < raw.Length)
                {
                    char n = raw[++i];
                    if (n == 'n') sb.Append('\n');
                    else if (n == 'r') sb.Append('\r');
                    else if (n == 't') sb.Append('\t');
                    else if (n == 'u' && i + 4 < raw.Length)
                    {
                        int code;
                        if (int.TryParse(raw.Substring(i + 1, 4), NumberStyles.HexNumber, CultureInfo.InvariantCulture, out code))
                        {
                            sb.Append((char)code);
                            i += 4;
                        }
                    }
                    else sb.Append(n);
                }
                else sb.Append(raw[i]);
            }
            return sb.ToString();
        }

        internal static int StartProcessInJobHandle(IntPtr hJob, string exePath, string arguments, string workingDirectory, IDictionary<string, string> env)
        {
            StringBuilder cmd = new StringBuilder();
            cmd.Append('"').Append(exePath).Append('"');
            if (!string.IsNullOrEmpty(arguments)) cmd.Append(' ').Append(arguments);

            IntPtr envBlock = IntPtr.Zero;
            if (env != null)
            {
                var sorted = new SortedDictionary<string, string>(env, StringComparer.OrdinalIgnoreCase);
                StringBuilder eb = new StringBuilder();
                foreach (var kv in sorted)
                {
                    if (kv.Key == null || kv.Value == null) continue;
                    eb.Append(kv.Key).Append('=').Append(kv.Value).Append('\0');
                }
                eb.Append('\0');
                envBlock = Marshal.StringToHGlobalUni(eb.ToString());
            }

            STARTUPINFO si = new STARTUPINFO();
            si.cb = Marshal.SizeOf(typeof(STARTUPINFO));
            PROCESS_INFORMATION pi;
            try
            {
                uint flags = CREATE_SUSPENDED | CREATE_NO_WINDOW | (envBlock != IntPtr.Zero ? CREATE_UNICODE_ENVIRONMENT : 0u);
                if (!CreateProcessW(null, cmd, IntPtr.Zero, IntPtr.Zero, false, flags, envBlock, workingDirectory, ref si, out pi))
                    throw new Win32Exception(Marshal.GetLastWin32Error(), "CreateProcessW failed for " + exePath);
            }
            finally
            {
                if (envBlock != IntPtr.Zero) Marshal.FreeHGlobal(envBlock);
            }

            try
            {
                if (!AssignProcessToJobObject(hJob, pi.hProcess))
                {
                    int err = Marshal.GetLastWin32Error();
                    TerminateProcess(pi.hProcess, 1);
                    throw new Win32Exception(err, "AssignProcessToJobObject failed for child pid " + pi.dwProcessId);
                }
                if (ResumeThread(pi.hThread) == unchecked((uint)-1))
                {
                    int err = Marshal.GetLastWin32Error();
                    TerminateProcess(pi.hProcess, 1);
                    throw new Win32Exception(err, "ResumeThread failed for child pid " + pi.dwProcessId);
                }
                return (int)pi.dwProcessId;
            }
            finally
            {
                CloseHandle(pi.hThread);
                CloseHandle(pi.hProcess);
            }
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct SECURITY_ATTRIBUTES
        {
            public int nLength;
            public IntPtr lpSecurityDescriptor;
            [MarshalAs(UnmanagedType.Bool)] public bool bInheritHandle;
        }

        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
        private struct PROCESSENTRY32
        {
            public uint dwSize;
            public uint cntUsage;
            public uint th32ProcessID;
            public IntPtr th32DefaultHeapID;
            public uint th32ModuleID;
            public uint cntThreads;
            public uint th32ParentProcessID;
            public int pcPriClassBase;
            public uint dwFlags;
            [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 260)] public string szExeFile;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct JOBOBJECT_BASIC_LIMIT_INFORMATION
        {
            public long PerProcessUserTimeLimit;
            public long PerJobUserTimeLimit;
            public uint LimitFlags;
            public UIntPtr MinimumWorkingSetSize;
            public UIntPtr MaximumWorkingSetSize;
            public uint ActiveProcessLimit;
            public UIntPtr Affinity;
            public uint PriorityClass;
            public uint SchedulingClass;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct IO_COUNTERS
        {
            public ulong ReadOperationCount, WriteOperationCount, OtherOperationCount;
            public ulong ReadTransferCount, WriteTransferCount, OtherTransferCount;
        }

        [StructLayout(LayoutKind.Sequential)]
        private struct JOBOBJECT_EXTENDED_LIMIT_INFORMATION
        {
            public JOBOBJECT_BASIC_LIMIT_INFORMATION BasicLimitInformation;
            public IO_COUNTERS IoInfo;
            public UIntPtr ProcessMemoryLimit, JobMemoryLimit, PeakProcessMemoryUsed, PeakJobMemoryUsed;
        }

        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
        private struct STARTUPINFO
        {
            public int cb;
            public IntPtr lpReserved, lpDesktop, lpTitle;
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

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern IntPtr CreateMutexExW(ref SECURITY_ATTRIBUTES lpMutexAttributes, string lpName, uint dwFlags, uint dwDesiredAccess);

        [DllImport("kernel32.dll", SetLastError = true)]
        internal static extern bool ReleaseMutex(IntPtr hMutex);

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern IntPtr CreateEventExW(ref SECURITY_ATTRIBUTES lpEventAttributes, string lpName, uint dwFlags, uint dwDesiredAccess);

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern IntPtr OpenEventW(uint dwDesiredAccess, bool bInheritHandle, string lpName);

        [DllImport("kernel32.dll", SetLastError = true)]
        internal static extern bool SetEvent(IntPtr hEvent);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern uint WaitForSingleObject(IntPtr hHandle, uint dwMilliseconds);

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern IntPtr CreateJobObjectW(ref SECURITY_ATTRIBUTES lpJobAttributes, string lpName);

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern IntPtr OpenJobObjectW(uint dwDesiredAccess, bool bInheritHandle, string lpName);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool SetInformationJobObject(IntPtr hJob, int infoClass, IntPtr lpInfo, uint cbLength);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool QueryInformationJobObject(IntPtr hJob, int infoClass, IntPtr lpInfo, uint cbLength, out uint lpReturnLength);

        [DllImport("kernel32.dll", SetLastError = true)]
        internal static extern bool AssignProcessToJobObject(IntPtr hJob, IntPtr hProcess);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool TerminateJobObject(IntPtr hJob, uint uExitCode);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool IsProcessInJob(IntPtr hProcess, IntPtr hJob, out bool result);

        [DllImport("kernel32.dll")]
        private static extern IntPtr GetCurrentProcess();

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern IntPtr OpenProcess(uint dwDesiredAccess, bool bInheritHandle, uint dwProcessId);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool GetExitCodeProcess(IntPtr hProcess, out uint lpExitCode);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool GetProcessTimes(IntPtr hProcess, out long creation, out long exit, out long kernel, out long user);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern IntPtr CreateToolhelp32Snapshot(uint dwFlags, uint th32ProcessID);

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern bool Process32First(IntPtr hSnapshot, ref PROCESSENTRY32 lppe);

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern bool Process32Next(IntPtr hSnapshot, ref PROCESSENTRY32 lppe);

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern bool MoveFileExW(string lpExistingFileName, string lpNewFileName, uint dwFlags);

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern bool CreateProcessW(
            string lpApplicationName,
            StringBuilder lpCommandLine,
            IntPtr lpProcessAttributes,
            IntPtr lpThreadAttributes,
            bool bInheritHandles,
            uint dwCreationFlags,
            IntPtr lpEnvironment,
            string lpCurrentDirectory,
            ref STARTUPINFO lpStartupInfo,
            out PROCESS_INFORMATION lpProcessInformation);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern uint ResumeThread(IntPtr hThread);

        [DllImport("kernel32.dll", SetLastError = true)]
        private static extern bool TerminateProcess(IntPtr hProcess, uint uExitCode);

        [DllImport("kernel32.dll", SetLastError = true)]
        internal static extern bool CloseHandle(IntPtr hObject);

        [DllImport("kernel32.dll")]
        private static extern IntPtr LocalFree(IntPtr hMem);

        [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern bool ConvertStringSecurityDescriptorToSecurityDescriptorW(
            string StringSecurityDescriptor,
            uint StringSDRevision,
            out IntPtr SecurityDescriptor,
            IntPtr SecurityDescriptorSize);

        [DllImport("advapi32.dll", SetLastError = true)]
        private static extern bool GetSecurityDescriptorDacl(
            IntPtr pSecurityDescriptor,
            out bool lpbDaclPresent,
            out IntPtr pDacl,
            out bool lpbDaclDefaulted);

        [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern uint SetNamedSecurityInfoW(
            string pObjectName,
            int ObjectType,
            uint SecurityInfo,
            IntPtr psidOwner,
            IntPtr psidGroup,
            IntPtr pDacl,
            IntPtr pSacl);
    }
}
