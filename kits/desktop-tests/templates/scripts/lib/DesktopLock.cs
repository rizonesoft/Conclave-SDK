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
        private readonly IntPtr _hKillJob;
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
        public bool AcquiredAbandoned { get; private set; }
        public int HolderPid { get; private set; }
        public long HolderStartTicks { get; private set; }
        public string HolderStartUtc { get; private set; }
        public string HeldToken { get; private set; }
        public IntPtr JobHandle { get { return _hJob; } }

        internal DesktopLockHandle(
            IntPtr hMutex,
            IntPtr hLease,
            IntPtr hJob,
            IntPtr hKillJob,
            int ownerThreadId,
            string lockName,
            string recordPath,
            string leaseId,
            string leaseEventName,
            string jobName,
            bool inherited,
            bool acquiredAbandoned,
            int holderPid,
            long holderStartTicks,
            string holderStartUtc)
        {
            _hMutex = hMutex;
            _hLease = hLease;
            _hJob = hJob;
            _hKillJob = hKillJob;
            _ownerThreadId = ownerThreadId;
            LockName = lockName;
            _recordPath = recordPath;
            LeaseId = leaseId;
            _leaseEventName = leaseEventName;
            _jobName = jobName;
            _inherited = inherited;
            AcquiredAbandoned = acquiredAbandoned;
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
            if (_inherited || _hJob == IntPtr.Zero || _hKillJob == IntPtr.Zero)
                throw new InvalidOperationException("only the owning DesktopLockHandle can assign processes to the desktop job");
            DesktopLock.EnrollProcessInDesktopJobs(_hJob, _hKillJob, hProcess);
        }

        public int StartProcessInJob(string exePath, string arguments, string workingDirectory, IDictionary<string, string> env)
        {
            if (_disposed) throw new ObjectDisposedException("DesktopLockHandle");
            if (_inherited || _hJob == IntPtr.Zero || _hKillJob == IntPtr.Zero)
                throw new InvalidOperationException("only the owning DesktopLockHandle can start processes in the desktop job");
            return DesktopLock.StartProcessInJobHandle(_hJob, _hKillJob, exePath, arguments, workingDirectory, env);
        }

        public int RunProcessInJob(string exePath, string arguments, string workingDirectory, IDictionary<string, string> env)
        {
            if (_disposed) throw new ObjectDisposedException("DesktopLockHandle");
            if (_inherited || _hJob == IntPtr.Zero || _hKillJob == IntPtr.Zero)
                throw new InvalidOperationException("only the owning DesktopLockHandle can run processes in the desktop job");
            return DesktopLock.RunProcessInJobHandle(_hJob, _hKillJob, exePath, arguments, workingDirectory, env);
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

            bool drained = true;
            try
            {
                if (_hKillJob != IntPtr.Zero && _hJob != IntPtr.Zero)
                {
                    drained = DesktopLock.TerminateAndDrainJob(_hKillJob, _hJob, 5000);
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
                            Trace.WriteLine("DesktopLock: SetEvent failed (err=" + Marshal.GetLastWin32Error() + ")");
                        }
                    }
                    // Retain the last published holder record on disk: readers validate the lease event,
                    // next owners atomically replace it, and a failed drain preserves prior job identity.
                }
                finally
                {
                    if (_hMutex != IntPtr.Zero)
                    {
                        DesktopLock.ReleaseMutex(_hMutex);
                        DesktopLock.CloseHandle(_hMutex);
                    }
                    if (_hLease != IntPtr.Zero) DesktopLock.CloseHandle(_hLease);
                    if (_hKillJob != IntPtr.Zero) DesktopLock.CloseHandle(_hKillJob);
                    if (_hJob != IntPtr.Zero) DesktopLock.CloseHandle(_hJob);
                }
            }
            if (!drained)
            {
                throw new InvalidOperationException("desktop job '" + _jobName + "' did not drain to zero active processes within timeout");
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

        // Owner retains full control on mutex/job; on the lease event, even same-account openers get only
        // READ_CONTROL | SYNCHRONIZE (0x00120000) so only the creator's private CreateEventExW handle can SetEvent.
        private const string SddlMutex = "D:(A;;0x001F0001;;;OW)(A;;0x00100001;;;AU)";
        private const string SddlLeaseEvent = "D:(A;;0x00120000;;;OW)(A;;0x00100000;;;AU)";
        private const string SddlJob = "D:(A;;0x001F001F;;;OW)(A;;0x00000004;;;AU)";
        private const string SddlRecordDir = "D:(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)(A;OICI;FA;;;OW)(A;OICI;0x001301BF;;;AU)";

        internal enum LeaseState { Active, Inactive, Unknown }

        // Test-only hooks (default null/false in production).
        internal delegate bool QueryJobPidListDelegate(IntPtr hJob, int capacity, out int assigned, out int inList, out long[] pids, out int win32Err);
        internal static Action BeforeWaitForMutexForTest { get; set; }
        internal static Action<bool> BeforeRecordPublishForTest { get; set; }
        internal static bool FailRecordPublishForTest { get; set; }
        internal static QueryJobPidListDelegate QueryJobPidListForTest { get; set; }

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
            // Match desktop_tests.py 1-to-1: prefix.upper().replace("-", "_") preserves repeated and trailing hyphens.
            string mapped = prefix.Trim().ToUpperInvariant().Replace('-', '_');
            if (!Regex.IsMatch(mapped, "^[A-Z][A-Z0-9_]*$"))
                throw new ArgumentException("prefix produced invalid environment prefix: " + prefix, "prefix");
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

                IntPtr hPinnedPriorJob = IntPtr.Zero;
                string pinnedPriorJobName = null;
                List<IntPtr> pinnedMemberHandles = new List<IntPtr>();
                try
                {
                    // Pin the current holder's named tracking job (JOB_OBJECT_QUERY only; never blocks _hKillJob's
                    // KILL_ON_JOB_CLOSE) and snapshot SYNCHRONIZE handles to its active members inside the cleanup
                    // scope before waiting so a cap refusal never leaks hPinnedPriorJob or member handles.
                    HolderRecord preRec = TryReadHolderRecord(recordPath);
                    if (preRec != null && !string.IsNullOrEmpty(preRec.LeaseId))
                    {
                        pinnedPriorJobName = JobNameFor(preRec.LeaseId);
                        hPinnedPriorJob = OpenJobObjectW(JOB_OBJECT_QUERY, false, pinnedPriorJobName);
                        if (hPinnedPriorJob != IntPtr.Zero)
                        {
                            SnapshotJobMemberSyncHandles(hPinnedPriorJob, pinnedMemberHandles);
                        }
                    }

                    Action beforeWait = BeforeWaitForMutexForTest;
                    if (beforeWait != null) beforeWait();
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

                    bool acquiredAbandoned = (rc == WAIT_ABANDONED);
                    IntPtr hLease = IntPtr.Zero;
                    IntPtr hJob = IntPtr.Zero;
                    IntPtr hKillJob = IntPtr.Zero;
                    bool published = false;
                    try
                    {
                        // On EVERY handoff (normal, abandoned, late-arriving, or post-probe), verify prior desktop job quiescence.
                        DrainPriorJobFromRecord(recordPath, hPinnedPriorJob, pinnedPriorJobName, pinnedMemberHandles, 5000);
                        CloseHandleList(pinnedMemberHandles);
                        if (hPinnedPriorJob != IntPtr.Zero)
                        {
                            CloseHandle(hPinnedPriorJob);
                            hPinnedPriorJob = IntPtr.Zero;
                        }

                        Action<bool> beforePub = BeforeRecordPublishForTest;
                        if (beforePub != null) beforePub(acquiredAbandoned);

                        int selfPid = Process.GetCurrentProcess().Id;
                        long selfTicks;
                        if (!TryGetProcessCreationTicks(selfPid, out selfTicks))
                            throw new InvalidOperationException("failed to read current process creation time");
                        string selfUtc = DateTime.FromFileTimeUtc(selfTicks).ToString("O", CultureInfo.InvariantCulture);
                        string leaseId = Guid.NewGuid().ToString("N").Substring(0, 16);
                        string leaseName = LeaseEventNameFor(leaseId);
                        string jobName = JobNameFor(leaseId);

                        hLease = CreateSecureLeaseEvent(leaseName);
                        // Outer unnamed kill-on-close job (owner-only, assigned first so owner death during enrollment
                        // still kills a suspended child) + middle named tracking job (no KILL_ON_JOB_CLOSE; pinned by
                        // waiting successors and duplicated inheritable into enrolled children).
                        hKillJob = CreateKillOnCloseJob();
                        hJob = CreateSecureTrackingJob(jobName);

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
                            hKillJob,
                            Thread.CurrentThread.ManagedThreadId,
                            canonicalLock,
                            recordPath,
                            leaseId,
                            leaseName,
                            jobName,
                            false,
                            acquiredAbandoned,
                            selfPid,
                            selfTicks,
                            selfUtc);
                    }
                    finally
                    {
                        if (!published)
                        {
                            if (hKillJob != IntPtr.Zero && hJob != IntPtr.Zero)
                            {
                                TerminateAndDrainJob(hKillJob, hJob, 2000);
                            }
                            if (hKillJob != IntPtr.Zero) CloseHandle(hKillJob);
                            if (hJob != IntPtr.Zero) CloseHandle(hJob);
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
                    CloseHandleList(pinnedMemberHandles);
                    if (hPinnedPriorJob != IntPtr.Zero) CloseHandle(hPinnedPriorJob);
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
                IntPtr.Zero,
                Thread.CurrentThread.ManagedThreadId,
                canonicalLock,
                recordPath,
                tokLeaseId,
                leaseName,
                jobName,
                true,
                false,
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

        internal static LeaseState CheckHolderLeaseState(int pid, long expectedStartTicks, string leaseEventName)
        {
            if (pid <= 0 || expectedStartTicks <= 0 || string.IsNullOrEmpty(leaseEventName))
                return LeaseState.Unknown;

            IntPtr hLease = OpenEventW(SYNCHRONIZE, false, leaseEventName);
            if (hLease != IntPtr.Zero)
            {
                try
                {
                    uint w = WaitForSingleObject(hLease, 0);
                    if (w == WAIT_OBJECT_0) return LeaseState.Inactive; // Explicitly signaled on disposal.
                    if (w != WAIT_TIMEOUT) return LeaseState.Unknown;   // WAIT_FAILED or unexpected.
                }
                finally
                {
                    CloseHandle(hLease);
                }
            }
            else
            {
                int evErr = Marshal.GetLastWin32Error();
                if (evErr != ERROR_FILE_NOT_FOUND) return LeaseState.Unknown; // e.g. ERROR_ACCESS_DENIED
            }

            // Lease event is either still unsignaled or vanished: inspect owner process with 3-state semantics.
            IntPtr hProc = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, false, (uint)pid);
            if (hProc == IntPtr.Zero)
            {
                int pErr = Marshal.GetLastWin32Error();
                // ERROR_INVALID_PARAMETER (87) means no process with this PID exists.
                return pErr == 87 ? LeaseState.Inactive : LeaseState.Unknown;
            }
            try
            {
                uint exitCode;
                if (!GetExitCodeProcess(hProc, out exitCode)) return LeaseState.Unknown;
                if (exitCode != 259) return LeaseState.Inactive; // Confirmed exited.
                long c, e, k, u;
                if (!GetProcessTimes(hProc, out c, out e, out k, out u) || c <= 0) return LeaseState.Unknown;
                if (c != expectedStartTicks) return LeaseState.Inactive; // PID reused by a different process.
                return hLease != IntPtr.Zero ? LeaseState.Active : LeaseState.Inactive;
            }
            finally
            {
                CloseHandle(hProc);
            }
        }

        internal static bool IsHolderLeaseLive(int pid, long expectedStartTicks, string leaseEventName)
        {
            return CheckHolderLeaseState(pid, expectedStartTicks, leaseEventName) == LeaseState.Active;
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

        private static bool ReadHolderRecordForRecovery(string path, out HolderRecord rec)
        {
            rec = null;
            if (string.IsNullOrEmpty(path)) return false;
            try
            {
                using (var fs = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete))
                using (var sr = new StreamReader(fs, Encoding.UTF8))
                {
                    rec = ParseRecord(sr.ReadToEnd());
                }
            }
            catch (FileNotFoundException)
            {
                return false;
            }
            catch (DirectoryNotFoundException)
            {
                return false;
            }
            catch (IOException ex)
            {
                throw new InvalidOperationException("holder record is unreadable during handoff recovery: " + ex.Message, ex);
            }
            catch (UnauthorizedAccessException ex)
            {
                throw new InvalidOperationException("holder record access denied during handoff recovery: " + ex.Message, ex);
            }
            if (rec == null || rec.Pid <= 0 || rec.StartTicks <= 0 || string.IsNullOrEmpty(rec.LeaseId))
                throw new InvalidOperationException("holder record is malformed during handoff recovery");
            return true;
        }

        private static void DrainPriorJobFromRecord(
            string recordPath,
            IntPtr hPinnedPriorJob,
            string pinnedPriorJobName,
            List<IntPtr> pinnedMemberHandles,
            int timeoutMs)
        {
            HolderRecord prior;
            if (!ReadHolderRecordForRecovery(recordPath, out prior)) return;
            string priorJobName = JobNameFor(prior.LeaseId);
            bool usePinned = (hPinnedPriorJob != IntPtr.Zero
                && string.Equals(priorJobName, pinnedPriorJobName, StringComparison.OrdinalIgnoreCase));
            List<IntPtr> observedHandles = new List<IntPtr>();
            DateTime deadline = DateTime.UtcNow.AddMilliseconds(timeoutMs);
            try
            {
                while (true)
                {
                    int count;
                    if (usePinned)
                    {
                        count = QueryJobActiveProcessCount(hPinnedPriorJob, observedHandles);
                    }
                    else
                    {
                        // Open, query, and IMMEDIATELY close the query handle on each poll so our handle never
                        // prolongs the job's lifetime or blocks JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE!
                        IntPtr hJob = OpenJobObjectW(JOB_OBJECT_QUERY, false, priorJobName);
                        if (hJob == IntPtr.Zero)
                        {
                            int err = Marshal.GetLastWin32Error();
                            if (err == ERROR_FILE_NOT_FOUND)
                            {
                                LeaseState st = CheckHolderLeaseState(prior.Pid, prior.StartTicks, LeaseEventNameFor(prior.LeaseId));
                                if (st == LeaseState.Inactive) break;
                                if (st == LeaseState.Unknown)
                                    throw new InvalidOperationException("cannot verify prior lease state after desktop job vanished; refusing acquisition");
                                if (DateTime.UtcNow >= deadline)
                                    throw new InvalidOperationException("prior holder lease still appears active after job vanished");
                                Thread.Sleep(20);
                                continue;
                            }
                            throw new Win32Exception(err, "cannot verify quiescence of prior desktop job '" + priorJobName + "'");
                        }
                        try
                        {
                            count = QueryJobActiveProcessCount(hJob, observedHandles);
                        }
                        finally
                        {
                            CloseHandle(hJob);
                        }
                    }
                    if (count == 0) break;
                    if (DateTime.UtcNow >= deadline)
                        throw new InvalidOperationException("prior desktop job '" + priorJobName + "' still has " + count + " active process(es); refusing lock acquisition");
                    Thread.Sleep(20);
                }

                // Wait for every snapshotted member handle to signal EPROCESS exit (JobObjectBasicProcessIdList can
                // reach 0 shortly before kernel teardown signals WaitForSingleObject on a terminating process).
                if (usePinned && pinnedMemberHandles != null && !WaitForProcessHandlesToExit(pinnedMemberHandles, deadline))
                    throw new InvalidOperationException("prior desktop job '" + priorJobName + "' member did not finish exiting within timeout");
                if (!WaitForProcessHandlesToExit(observedHandles, deadline))
                    throw new InvalidOperationException("prior desktop job '" + priorJobName + "' member did not finish exiting within timeout");
            }
            finally
            {
                CloseHandleList(observedHandles);
            }
        }

        internal static bool TerminateAndDrainJob(IntPtr hKillJob, IntPtr hTrackJob, int timeoutMs)
        {
            List<IntPtr> memberHandles = new List<IntPtr>();
            try
            {
                SnapshotJobMemberSyncHandles(hTrackJob, memberHandles);
                TerminateJobObject(hKillJob, 1);
                DateTime deadline = DateTime.UtcNow.AddMilliseconds(timeoutMs);
                while (true)
                {
                    try
                    {
                        if (QueryJobActiveProcessCount(hTrackJob, memberHandles) == 0) break;
                    }
                    catch (Win32Exception)
                    {
                        return false;
                    }
                    if (DateTime.UtcNow >= deadline) return false;
                    Thread.Sleep(15);
                }
                return WaitForProcessHandlesToExit(memberHandles, deadline);
            }
            finally
            {
                CloseHandleList(memberHandles);
            }
        }

        private static void SnapshotJobMemberSyncHandles(IntPtr hJob, List<IntPtr> handles)
        {
            try
            {
                QueryJobActiveProcessCount(hJob, handles);
            }
            catch (Win32Exception)
            {
                // Best-effort snapshot before waiting; post-wait QueryJobActiveProcessCount enforces quiescence.
            }
        }

        private static void CloseHandleList(List<IntPtr> handles)
        {
            if (handles == null) return;
            foreach (IntPtr h in handles)
            {
                if (h != IntPtr.Zero) CloseHandle(h);
            }
            handles.Clear();
        }

        private static bool WaitForProcessHandlesToExit(List<IntPtr> handles, DateTime deadline)
        {
            if (handles == null) return true;
            foreach (IntPtr h in handles)
            {
                if (h == IntPtr.Zero) continue;
                int remMs = (int)Math.Ceiling((deadline - DateTime.UtcNow).TotalMilliseconds);
                if (remMs < 0) remMs = 0;
                uint rc = WaitForSingleObject(h, (uint)remMs);
                if (rc != WAIT_OBJECT_0) return false;
            }
            return true;
        }

        private static int QueryJobActiveProcessCount(IntPtr hJob)
        {
            return QueryJobActiveProcessCount(hJob, null);
        }

        private static int QueryJobActiveProcessCount(IntPtr hJob, List<IntPtr> collectSyncHandles)
        {
            // Dynamically grow JOBOBJECT_BASIC_PROCESS_ID_LIST buffer on ERROR_MORE_DATA or partial list
            // (inList < assigned) so large process trees never skip SYNCHRONIZE handle collection; fail closed
            // if the list still exceeds the safety cap.
            const int MaxCapacity = 65536;
            int capacity = 64;
            QueryJobPidListDelegate testOverride = QueryJobPidListForTest;
            while (true)
            {
                if (testOverride != null)
                {
                    int tAssigned, tInList, tErr;
                    long[] tPids;
                    bool tOk = testOverride(hJob, capacity, out tAssigned, out tInList, out tPids, out tErr);
                    if (!tOk)
                    {
                        if (tErr == 234)
                        {
                            if (capacity >= MaxCapacity)
                                throw new InvalidOperationException("desktop job process list exceeded enumeration cap (" + MaxCapacity + "); refusing lock acquisition");
                            capacity = Math.Min(MaxCapacity, capacity * 2);
                            continue;
                        }
                        throw new Win32Exception(tErr, "QueryInformationJobObject failed");
                    }
                    if (tInList < tAssigned)
                    {
                        if (capacity >= MaxCapacity)
                            throw new InvalidOperationException("desktop job process list remained incomplete (" + tInList + " of " + tAssigned + "); refusing lock acquisition");
                        capacity = Math.Min(MaxCapacity, Math.Max(capacity * 2, tAssigned + 16));
                        continue;
                    }
                    if (collectSyncHandles != null && tPids != null)
                    {
                        int tLim = Math.Min(tInList, tPids.Length);
                        for (int i = 0; i < tLim; i++)
                        {
                            if (tPids[i] > 0 && tPids[i] <= uint.MaxValue)
                            {
                                IntPtr hp = OpenProcess(SYNCHRONIZE, false, (uint)tPids[i]);
                                if (hp != IntPtr.Zero) collectSyncHandles.Add(hp);
                            }
                        }
                    }
                    return Math.Max(tAssigned, tInList);
                }
                int bufSize = 8 + IntPtr.Size * capacity;
                IntPtr buf = Marshal.AllocHGlobal(bufSize);
                try
                {
                    uint retLen;
                    bool ok = QueryInformationJobObject(hJob, JobObjectBasicProcessIdList, buf, (uint)bufSize, out retLen);
                    if (!ok)
                    {
                        int err = Marshal.GetLastWin32Error();
                        if (err == 234) // ERROR_MORE_DATA
                        {
                            if (capacity >= MaxCapacity)
                                throw new InvalidOperationException("desktop job process list exceeded enumeration cap (" + MaxCapacity + "); refusing lock acquisition");
                            capacity = Math.Min(MaxCapacity, capacity * 2);
                            continue;
                        }
                        throw new Win32Exception(err, "QueryInformationJobObject failed");
                    }
                    int assigned = Marshal.ReadInt32(buf, 0);
                    int inList = Marshal.ReadInt32(buf, 4);
                    if (inList < assigned)
                    {
                        if (capacity >= MaxCapacity)
                            throw new InvalidOperationException("desktop job process list remained incomplete (" + inList + " of " + assigned + "); refusing lock acquisition");
                        capacity = Math.Min(MaxCapacity, Math.Max(capacity * 2, assigned + 16));
                        continue;
                    }
                    if (collectSyncHandles != null && inList > 0)
                    {
                        int limit = Math.Min(inList, capacity);
                        for (int i = 0; i < limit; i++)
                        {
                            long pidVal = (IntPtr.Size == 8)
                                ? Marshal.ReadInt64(buf, 8 + i * 8)
                                : Marshal.ReadInt32(buf, 8 + i * 4);
                            if (pidVal > 0 && pidVal <= uint.MaxValue)
                            {
                                IntPtr hp = OpenProcess(SYNCHRONIZE, false, (uint)pidVal);
                                if (hp != IntPtr.Zero)
                                {
                                    collectSyncHandles.Add(hp);
                                }
                            }
                        }
                    }
                    return Math.Max(assigned, inList);
                }
                finally
                {
                    Marshal.FreeHGlobal(buf);
                }
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

        private static IntPtr CreateSecureTrackingJob(string name)
        {
            IntPtr sd;
            SECURITY_ATTRIBUTES sa = MakeSecurityAttributes(SddlJob, out sd);
            try
            {
                IntPtr h = CreateJobObjectW(ref sa, name);
                if (h == IntPtr.Zero)
                    throw new Win32Exception(Marshal.GetLastWin32Error(), "CreateJobObjectW failed for " + name);
                return h;
            }
            finally
            {
                if (sd != IntPtr.Zero) LocalFree(sd);
            }
        }

        private static IntPtr CreateKillOnCloseJob()
        {
            SECURITY_ATTRIBUTES sa = new SECURITY_ATTRIBUTES { nLength = Marshal.SizeOf(typeof(SECURITY_ATTRIBUTES)), bInheritHandle = false };
            IntPtr h = CreateJobObjectW(ref sa, null);
            if (h == IntPtr.Zero)
                throw new Win32Exception(Marshal.GetLastWin32Error(), "CreateJobObjectW failed for kill-on-close job");
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
                    throw new Win32Exception(err, "SetInformationJobObject failed for kill-on-close job");
                }
            }
            finally
            {
                Marshal.FreeHGlobal(ptr);
            }
            return h;
        }

        internal static void EnrollProcessInDesktopJobs(IntPtr hTrackJob, IntPtr hKillJob, IntPtr hProcess)
        {
            // Assign kill-on-close job FIRST so owner death between assignments still kills the suspended child.
            if (!AssignProcessToJobObject(hKillJob, hProcess))
                throw new Win32Exception(Marshal.GetLastWin32Error(), "AssignProcessToJobObject(killJob) failed");
            if (!AssignProcessToJobObject(hTrackJob, hProcess))
                throw new Win32Exception(Marshal.GetLastWin32Error(), "AssignProcessToJobObject(trackJob) failed");
            // Duplicate an inheritable JOB_OBJECT_QUERY handle of the named tracking job into the child so
            // Global\conclave-desktop-job-<lease_id> stays queryable while enrolled children/inheriting descendants exit.
            IntPtr dup;
            if (!DuplicateHandle(GetCurrentProcess(), hTrackJob, hProcess, out dup, JOB_OBJECT_QUERY, true, 0))
                throw new Win32Exception(Marshal.GetLastWin32Error(), "DuplicateHandle(trackJob) into child failed");
        }

        private static void EnsureRecordDirectory(string dir)
        {
            if (string.IsNullOrEmpty(dir)) return;
            string parent = Path.GetDirectoryName(dir);
            if (!string.IsNullOrEmpty(parent) && !Directory.Exists(parent))
            {
                Directory.CreateDirectory(parent);
            }
            IntPtr sd;
            SECURITY_ATTRIBUTES sa = MakeSecurityAttributes(SddlRecordDir, out sd);
            try
            {
                if (!CreateDirectoryW(dir, ref sa))
                {
                    int err = Marshal.GetLastWin32Error();
                    if (err != 183) // ERROR_ALREADY_EXISTS
                        throw new Win32Exception(err, "CreateDirectoryW failed for " + dir);
                    // Directory already existed: verify/repair its DACL if we own it (ignore ACCESS_DENIED when owned by another account).
                    bool present, defaulted;
                    IntPtr dacl;
                    if (GetSecurityDescriptorDacl(sd, out present, out dacl, out defaulted) && present)
                    {
                        uint rc = SetNamedSecurityInfoW(dir, 1 /* SE_FILE_OBJECT */, 4 /* DACL_SECURITY_INFORMATION */, IntPtr.Zero, IntPtr.Zero, dacl, IntPtr.Zero);
                        if (rc == 5) // ERROR_ACCESS_DENIED: created by another account; inspect and validate existing DACL.
                        {
                            ValidateExistingRecordDirectoryDacl(dir);
                        }
                        else if (rc != 0)
                        {
                            throw new Win32Exception((int)rc, "SetNamedSecurityInfoW failed for " + dir);
                        }
                    }
                }
            }
            finally
            {
                if (sd != IntPtr.Zero) LocalFree(sd);
            }
        }

        private static void ValidateExistingRecordDirectoryDacl(string dir)
        {
            IntPtr pDacl, existingSd;
            uint grc = GetNamedSecurityInfoW(dir, 1 /* SE_FILE_OBJECT */, 4 /* DACL_SECURITY_INFORMATION */,
                IntPtr.Zero, IntPtr.Zero, out pDacl, IntPtr.Zero, out existingSd);
            if (grc != 0)
                throw new Win32Exception((int)grc, "GetNamedSecurityInfoW failed while validating DACL for " + dir);
            try
            {
                if (!IsValidRecordDirectoryDaclBinary(pDacl))
                    throw new UnauthorizedAccessException("shared desktop-locks directory DACL is invalid for " + dir);
            }
            finally
            {
                LocalFree(existingSd);
            }
        }

        internal static bool IsValidRecordDirectoryDaclSddlForTest(string sddl)
        {
            IntPtr sd;
            if (!ConvertStringSecurityDescriptorToSecurityDescriptorW(sddl, 1, out sd, IntPtr.Zero))
                return false;
            try
            {
                bool present, defaulted;
                IntPtr dacl;
                if (!GetSecurityDescriptorDacl(sd, out present, out dacl, out defaulted) || !present)
                    return false;
                return IsValidRecordDirectoryDaclBinary(dacl);
            }
            finally
            {
                LocalFree(sd);
            }
        }

        private static bool IsValidRecordDirectoryDaclBinary(IntPtr pDacl)
        {
            if (pDacl == IntPtr.Zero) return false; // Null DACL grants Everyone full access.
            ACL_SIZE_INFORMATION info;
            if (!GetAclInformation(pDacl, out info, (uint)Marshal.SizeOf(typeof(ACL_SIZE_INFORMATION)), 2 /* AclSizeInformation */))
                return false;

            byte[] auSid = new byte[68];
            uint auLen = (uint)auSid.Length;
            byte[] wdSid = new byte[68];
            uint wdLen = (uint)wdSid.Length;
            if (!CreateWellKnownSid(17 /* WinAuthenticatedUserSid */, IntPtr.Zero, auSid, ref auLen)) return false;
            if (!CreateWellKnownSid(1 /* WinWorldSid */, IntPtr.Zero, wdSid, ref wdLen)) return false;

            bool auAppliesToDir = false;
            bool auAppliesToChildren = false;
            const uint RequiredModify = 0x001301BFu;
            // Reject Everyone allow ACEs with any write/add-file/add-subdir/delete-child/delete/DAC/owner/generic-write/generic-all bit.
            const uint ForbiddenWorldMask = 0x500D0156u;

            for (uint i = 0; i < info.AceCount; i++)
            {
                IntPtr pAce;
                if (!GetAce(pDacl, i, out pAce) || pAce == IntPtr.Zero) return false;
                byte aceType = Marshal.ReadByte(pAce, 0);
                // Fail closed on conditional, callback, object, or any ACE type we cannot evaluate.
                if (aceType != 0 /* ACCESS_ALLOWED_ACE_TYPE */ && aceType != 1 /* ACCESS_DENIED_ACE_TYPE */)
                    return false;
                byte aceFlags = Marshal.ReadByte(pAce, 1);
                uint mask = unchecked((uint)Marshal.ReadInt32(pAce, 4));
                IntPtr pSid = IntPtr.Add(pAce, 8);

                if (EqualSid(pSid, auSid))
                {
                    if (aceType == 1) return false;
                    // Reject ANY bit above Modify (0x001301BF), including FILE_DELETE_CHILD (0x40), WRITE_DAC, WRITE_OWNER, GENERIC_ALL.
                    if ((mask & ~RequiredModify) != 0) return false;
                    if (mask == RequiredModify)
                    {
                        bool inheritOnly = (aceFlags & 0x08) != 0;
                        bool oi = (aceFlags & 0x01) != 0;
                        bool ci = (aceFlags & 0x02) != 0;
                        if (!inheritOnly) auAppliesToDir = true;
                        if (oi && ci) auAppliesToChildren = true;
                    }
                }
                else if (EqualSid(pSid, wdSid))
                {
                    // Reject Everyone deny ACEs (they also deny AU) and any Everyone write/delete/DAC-modify allow ACE.
                    if (aceType == 1) return false;
                    if ((mask & ForbiddenWorldMask) != 0) return false;
                }
            }
            return auAppliesToDir && auAppliesToChildren;
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
            int i = 0, n = text.Length;
            SkipWs(text, ref i);
            if (i >= n || text[i] != '{') return null;
            i++;
            var map = new Dictionary<string, object>(StringComparer.Ordinal);
            SkipWs(text, ref i);
            if (i < n && text[i] == '}') { i++; }
            else
            {
                while (true)
                {
                    SkipWs(text, ref i);
                    string key = ReadJsonString(text, ref i);
                    if (key == null || map.ContainsKey(key)) return null;
                    SkipWs(text, ref i);
                    if (i >= n || text[i] != ':') return null;
                    i++;
                    SkipWs(text, ref i);
                    if (i >= n) return null;
                    object val;
                    if (text[i] == '"')
                    {
                        string sv = ReadJsonString(text, ref i);
                        if (sv == null) return null;
                        val = sv;
                    }
                    else
                    {
                        int start = i;
                        if (text[i] == '-') i++;
                        int digits = i;
                        while (i < n && text[i] >= '0' && text[i] <= '9') i++;
                        if (i == digits) return null;
                        long lv;
                        if (!long.TryParse(text.Substring(start, i - start), NumberStyles.Integer, CultureInfo.InvariantCulture, out lv))
                            return null;
                        val = lv;
                    }
                    map[key] = val;
                    SkipWs(text, ref i);
                    if (i >= n) return null;
                    if (text[i] == ',') { i++; continue; }
                    if (text[i] == '}') { i++; break; }
                    return null;
                }
            }
            SkipWs(text, ref i);
            if (i != n) return null;

            object oPid, oTicks, oUtc, oLease, oLock, oLabel;
            if (!map.TryGetValue("pid", out oPid) || !(oPid is long)) return null;
            if (!map.TryGetValue("start_ticks", out oTicks) || !(oTicks is long)) return null;
            if (!map.TryGetValue("start_utc", out oUtc) || !(oUtc is string)) return null;
            if (!map.TryGetValue("lease_id", out oLease) || !(oLease is string)) return null;
            if (!map.TryGetValue("lock_name", out oLock) || !(oLock is string)) return null;
            if (!map.TryGetValue("label", out oLabel) || !(oLabel is string)) return null;
            long pidL = (long)oPid;
            if (pidL <= 0 || pidL > int.MaxValue) return null;
            string startUtc = (string)oUtc, leaseId = (string)oLease, lockName = (string)oLock, label = (string)oLabel;
            if (string.IsNullOrEmpty(startUtc) || string.IsNullOrEmpty(leaseId) || string.IsNullOrEmpty(lockName))
                return null;
            return new HolderRecord
            {
                Pid = (int)pidL,
                StartTicks = (long)oTicks,
                StartUtc = startUtc,
                LeaseId = leaseId,
                LockName = lockName,
                Label = label
            };
        }

        private static void SkipWs(string s, ref int i)
        {
            while (i < s.Length && (s[i] == ' ' || s[i] == '\t' || s[i] == '\r' || s[i] == '\n')) i++;
        }

        private static string ReadJsonString(string s, ref int i)
        {
            if (i >= s.Length || s[i] != '"') return null;
            i++;
            StringBuilder sb = new StringBuilder();
            while (i < s.Length)
            {
                char c = s[i++];
                if (c == '"') return sb.ToString();
                if (c < 0x20) return null;
                if (c == '\\')
                {
                    if (i >= s.Length) return null;
                    char e = s[i++];
                    if (e == '"' || e == '\\' || e == '/') sb.Append(e);
                    else if (e == 'b') sb.Append('\b');
                    else if (e == 'f') sb.Append('\f');
                    else if (e == 'n') sb.Append('\n');
                    else if (e == 'r') sb.Append('\r');
                    else if (e == 't') sb.Append('\t');
                    else if (e == 'u' && i + 4 <= s.Length)
                    {
                        int code;
                        if (!int.TryParse(s.Substring(i, 4), NumberStyles.HexNumber, CultureInfo.InvariantCulture, out code)) return null;
                        sb.Append((char)code);
                        i += 4;
                    }
                    else return null;
                }
                else sb.Append(c);
            }
            return null;
        }

        internal static int StartProcessInJobHandle(IntPtr hTrackJob, IntPtr hKillJob, string exePath, string arguments, string workingDirectory, IDictionary<string, string> env)
        {
            IntPtr hProc;
            int pid = SpawnProcessInJobHandle(hTrackJob, hKillJob, exePath, arguments, workingDirectory, env, out hProc);
            CloseHandle(hProc);
            return pid;
        }

        internal static int RunProcessInJobHandle(IntPtr hTrackJob, IntPtr hKillJob, string exePath, string arguments, string workingDirectory, IDictionary<string, string> env)
        {
            IntPtr hProc;
            SpawnProcessInJobHandle(hTrackJob, hKillJob, exePath, arguments, workingDirectory, env, out hProc);
            try
            {
                uint w = WaitForSingleObject(hProc, 0xFFFFFFFFu);
                if (w != WAIT_OBJECT_0)
                    throw new Win32Exception(Marshal.GetLastWin32Error(), "WaitForSingleObject failed on child process");
                uint code;
                if (!GetExitCodeProcess(hProc, out code))
                    throw new Win32Exception(Marshal.GetLastWin32Error(), "GetExitCodeProcess failed on child process");
                return unchecked((int)code);
            }
            finally
            {
                CloseHandle(hProc);
            }
        }

        private static int SpawnProcessInJobHandle(IntPtr hTrackJob, IntPtr hKillJob, string exePath, string arguments, string workingDirectory, IDictionary<string, string> env, out IntPtr processHandle)
        {
            processHandle = IntPtr.Zero;
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

            bool ok = false;
            try
            {
                EnrollProcessInDesktopJobs(hTrackJob, hKillJob, pi.hProcess);
                if (ResumeThread(pi.hThread) == unchecked((uint)-1))
                {
                    int err = Marshal.GetLastWin32Error();
                    TerminateProcess(pi.hProcess, 1);
                    throw new Win32Exception(err, "ResumeThread failed for child pid " + pi.dwProcessId);
                }
                processHandle = pi.hProcess;
                ok = true;
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
                if (!ok) CloseHandle(pi.hProcess);
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
        private static extern bool CreateDirectoryW(string lpPathName, ref SECURITY_ATTRIBUTES lpSecurityAttributes);

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
        private static extern bool DuplicateHandle(
            IntPtr hSourceProcessHandle,
            IntPtr hSourceHandle,
            IntPtr hTargetProcessHandle,
            out IntPtr lpTargetHandle,
            uint dwDesiredAccess,
            bool bInheritHandle,
            uint dwOptions);

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

        [StructLayout(LayoutKind.Sequential)]
        private struct ACL_SIZE_INFORMATION
        {
            public uint AceCount;
            public uint AclBytesInUse;
            public uint AclBytesFree;
        }

        [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern uint GetNamedSecurityInfoW(
            string pObjectName,
            int ObjectType,
            uint SecurityInfo,
            IntPtr ppsidOwner,
            IntPtr ppsidGroup,
            out IntPtr ppDacl,
            IntPtr ppSacl,
            out IntPtr ppSecurityDescriptor);

        [DllImport("advapi32.dll", SetLastError = true)]
        private static extern bool GetAclInformation(
            IntPtr pAcl,
            out ACL_SIZE_INFORMATION pAclInformation,
            uint nAclInformationLength,
            int dwAclInformationClass);

        [DllImport("advapi32.dll", SetLastError = true)]
        private static extern bool GetAce(IntPtr pAcl, uint dwAceIndex, out IntPtr pAce);

        [DllImport("advapi32.dll", SetLastError = true)]
        private static extern bool CreateWellKnownSid(int WellKnownSidType, IntPtr DomainSid, byte[] pSid, ref uint cbSid);

        [DllImport("advapi32.dll")]
        private static extern bool EqualSid(IntPtr pSid1, byte[] pSid2);
    }
}
